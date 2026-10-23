#!/usr/bin/env python3
"""Claudio - MCP server for audio understanding via Gemini.

Based on the public `claudio` package, patched for the audio-transcriber skill:
  - model comes from GEMINI_MODEL (default gemini-3.8-flash); the original hardcodes a retired model
  - "*transcribe*" models are sent single-turn (they reject multi-turn chat) and their
    audio_transcription.text is extracted
  - empty / blocked / overloaded replies are retried, then reported with a clear reason
    instead of returning the string "None"

Environment:
  GEMINI_API_KEY   required. Both key formats work: classic "AIza..." and new-style "AQ.…"
  GEMINI_MODEL     optional, default gemini-3.8-flash
  GEMINI_RETRIES   optional, default 3 (extra attempts after the first)
"""

import os
import re
import sys
import time
import uuid
from pathlib import Path

from google import genai
from google.genai import types
from mcp.server.fastmcp import FastMCP

# Validate API key at startup (never print the key itself)
api_key = (os.getenv("GEMINI_API_KEY") or "").strip().strip("\"'")
if not api_key:
    print("Error: GEMINI_API_KEY environment variable is required", file=sys.stderr)
    sys.exit(1)

if re.fullmatch(r"AIza[0-9A-Za-z_-]{35}", api_key):
    KEY_KIND = "classic (AIza...)"
elif api_key.startswith("AQ."):
    KEY_KIND = "new-style (AQ....)"
else:
    KEY_KIND = "unrecognized format"
    print("Warning: GEMINI_API_KEY has an unrecognized format; will try it anyway", file=sys.stderr)

# Initialize Gemini client
client = genai.Client(api_key=api_key)

# Initialize MCP server (stdio only)
mcp = FastMCP("claudio")

# Session storage: session_id -> (chat_session, uploaded_file)
sessions: dict[str, tuple] = {}

# Supported audio MIME types (per Gemini docs)
# https://ai.google.dev/gemini-api/docs/audio
SUPPORTED_MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".aiff": "audio/aiff",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}

# 20MB threshold for inline vs Files API
INLINE_SIZE_LIMIT = 20 * 1024 * 1024

RETRIES = max(0, int(os.getenv("GEMINI_RETRIES", "3")))
RETRY_DELAYS = (5, 15, 30)
TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL",
                     "DEADLINE", "timed out", "timeout", "Connection", "ConnectError", "ReadError")


def get_mime_type(file_path: str) -> str | None:
    """Get MIME type for an audio file."""
    ext = Path(file_path).suffix.lower()
    return SUPPORTED_MIME_TYPES.get(ext)


def extract_text(response) -> str:
    """Collect answer text from every part. response.text is None when the text lives in
    other parts (e.g. audio_transcription.text) or when the reply is blocked/empty."""
    texts = []
    for cand in response.candidates or []:
        for part in (cand.content.parts if cand.content and cand.content.parts else []):
            if getattr(part, "thought", False):
                continue
            if part.text:
                texts.append(part.text)
            elif getattr(part, "audio_transcription", None) and part.audio_transcription.text:
                texts.append(part.audio_transcription.text)
    return "\n".join(texts).strip()


def describe_empty(response) -> str:
    """Explain why a reply has no text, so an empty answer is never mistaken for success."""
    info = [f"prompt_feedback={response.prompt_feedback}"]
    for cand in response.candidates or []:
        kinds = [k for p in (cand.content.parts if cand.content and cand.content.parts else [])
                 for k, v in p.model_dump(exclude_none=True).items() if v]
        info.append(f"finish_reason={cand.finish_reason}, part_kinds={kinds}")
    if not response.candidates:
        info.append("no candidates")
    return "; ".join(info)


def friendly_error(e: Exception) -> str:
    """Turn an API exception into an actionable one-line message (never includes the key)."""
    msg = str(e)
    low = msg.lower()
    if "reported as leaked" in low:
        hint = "API key was disabled by Google because it leaked. Create a NEW key, update .env, rerun setup_mcp.sh, open a new session."
    elif "api_key_invalid" in low or "api key not valid" in low or "api key expired" in low:
        hint = "API key is invalid or expired. Check .env (classic keys start with AIza, new-style keys with AQ.) and rerun setup_mcp.sh."
    elif "403" in msg or "PERMISSION_DENIED" in msg:
        hint = "Permission denied (403). The key may lack access to this model or the Generative Language API is disabled for its project."
    elif "404" in msg or "NOT_FOUND" in msg:
        hint = "Model not found (404). Set GEMINI_MODEL to a model your key can use (list: GET /v1beta/models)."
    elif "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        hint = "Quota or rate limit exceeded (429). Wait about a minute, send shorter audio, or check the key's plan."
    elif "503" in msg or "UNAVAILABLE" in msg:
        hint = "Gemini is overloaded (503). Usually temporary; retry later."
    elif "certificate" in low or "ssl" in low:
        hint = "SSL verification failed. Point SSL_CERT_FILE/REQUESTS_CA_BUNDLE to the system CA bundle; do not disable verification."
    else:
        hint = ""
    return f"{msg[:400]}" + (f" | HINT: {hint}" if hint else "")


def is_transient(e: Exception) -> bool:
    msg = str(e)
    if "reported as leaked" in msg.lower() or "API_KEY_INVALID" in msg:
        return False
    return any(m in msg for m in TRANSIENT_MARKERS)


def ask_with_retry(send):
    """Call send() (returns a Gemini response). Retry transient errors and empty/blocked
    replies with backoff. Returns (text, error_message); exactly one of them is None."""
    last = "unknown error"
    attempts = RETRIES + 1
    for attempt in range(attempts):
        try:
            response = send()
        except Exception as e:  # noqa: BLE001 - surface any SDK/network error to the caller
            last = friendly_error(e)
            if attempt < attempts - 1 and is_transient(e):
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                continue
            return None, f"Error communicating with Gemini: {last}"
        text = extract_text(response)
        if text:
            return text, None
        # Empty reply: Gemini sometimes blocks the prompt intermittently (block_reason=OTHER)
        last = f"Gemini returned no text ({describe_empty(response)})"
        if attempt < attempts - 1:
            time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
    return None, (f"Error: {last} after {attempts} attempts. "
                  "HINT: try again later, or split the audio into shorter parts and transcribe each.")


class SingleTurn:
    """Chat-like wrapper that sends the audio with every question as a single-turn request."""

    def __init__(self, model: str, audio_part):
        self.model = model
        self.audio_part = audio_part

    def send_message(self, question: str):
        return client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=[self.audio_part, types.Part.from_text(text=question)])],
        )


def generate_session_id() -> str:
    """Generate a short unique session ID."""
    return uuid.uuid4().hex[:8]


@mcp.tool()
async def listen_to_audio(file_path: str, question: str) -> str:
    """
    Start listening to an audio file and ask a question about it.
    Returns an answer along with a session_id for follow-up questions.

    Args:
        file_path: Path to a local audio file (mp3, wav, flac, etc.)
        question: Your question about the audio (e.g., "Describe this music",
                  "What instruments are playing?", "Transcribe the lyrics")
    """
    # Validate file exists
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        return f"Error: File not found: {file_path}"

    # Get MIME type
    mime_type = get_mime_type(str(path))
    if not mime_type:
        supported = ", ".join(SUPPORTED_MIME_TYPES.keys())
        return f"Error: Unsupported audio format. Supported formats: {supported}"

    try:
        # Read audio file
        audio_bytes = path.read_bytes()
        file_size = len(audio_bytes)

        # Upload to Gemini
        if file_size > INLINE_SIZE_LIMIT:
            # Use Files API for large files
            uploaded_file = client.files.upload(
                file=path,
                config={"mime_type": mime_type}
            )
            # Convert uploaded file to a Part for use in chat
            audio_part = types.Part.from_uri(
                file_uri=uploaded_file.uri,
                mime_type=uploaded_file.mime_type
            )
        else:
            # Use inline data for smaller files
            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type=mime_type
            )
            uploaded_file = None

        model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

        if "transcribe" in model_name:
            # Transcribe models reject multi-turn chat: send audio + question as one turn each call
            chat = SingleTurn(model_name, audio_part)
        else:
            # Create chat session with audio context
            chat = client.chats.create(
                model=model_name,
                history=[
                    types.Content(
                        role="user",
                        parts=[
                            audio_part,
                            types.Part.from_text(text="I'm sharing an audio file with you. Please listen to it carefully so you can answer questions about it.")
                        ]
                    ),
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text="I've received and listened to the audio file. I'm ready to answer any questions you have about it - whether about the music, instruments, lyrics, mood, or any other aspects of the audio.")]
                    )
                ]
            )

        # Send the actual question (retries transient errors and empty/blocked replies)
        answer, error = ask_with_retry(lambda: chat.send_message(question))
        if error:
            return error

        # Store session
        session_id = generate_session_id()
        sessions[session_id] = (chat, uploaded_file)

        return f"{answer}\n\n---\nSession ID: {session_id}\n(Use this ID with ask_about_audio for follow-up questions)"

    except Exception as e:  # noqa: BLE001
        return f"Error communicating with Gemini: {friendly_error(e)}"


@mcp.tool()
async def ask_about_audio(session_id: str, question: str) -> str:
    """
    Ask a follow-up question about audio from an existing session.

    Args:
        session_id: Session ID from a previous listen_to_audio call
        question: Your follow-up question about the audio
    """
    if session_id not in sessions:
        return f"Error: Session '{session_id}' not found. Use listen_to_audio first to start a new session."

    try:
        chat, _ = sessions[session_id]
        answer, error = ask_with_retry(lambda: chat.send_message(question))
        return error or answer

    except Exception as e:  # noqa: BLE001
        return f"Error communicating with Gemini: {friendly_error(e)}"


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
