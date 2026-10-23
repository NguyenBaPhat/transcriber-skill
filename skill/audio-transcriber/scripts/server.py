#!/usr/bin/env python3
"""Claudio - MCP server for audio understanding via Gemini.

Set the GEMINI_API_KEY environment variable before running.
"""

import os
import sys
import uuid
from pathlib import Path

from google import genai
from google.genai import types
from mcp.server.fastmcp import FastMCP

# Validate API key at startup
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY environment variable is required", file=sys.stderr)
    sys.exit(1)

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


def get_mime_type(file_path: str) -> str | None:
    """Get MIME type for an audio file."""
    ext = Path(file_path).suffix.lower()
    return SUPPORTED_MIME_TYPES.get(ext)


class SingleTurn:
    """Chat-like wrapper that sends the audio with every question as a single-turn request."""

    def __init__(self, model: str, audio_part):
        self.model = model
        self.audio_part = audio_part

    def send_message(self, question: str):
        response = client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=[self.audio_part, types.Part.from_text(text=question)])],
        )
        # Transcribe models return text in audio_transcription.text, so response.text is None
        texts = []
        for part in response.candidates[0].content.parts:
            if part.text:
                texts.append(part.text)
            elif getattr(part, "audio_transcription", None) and part.audio_transcription.text:
                texts.append(part.audio_transcription.text)
        return _Reply("\n".join(texts))


class _Reply:
    def __init__(self, text: str):
        self.text = text


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

        # Transcribe models reject multi-turn chat: send audio + question as one turn each call
        if "transcribe" in model_name:
            chat = SingleTurn(model_name, audio_part)
            answer = chat.send_message(question).text
            session_id = generate_session_id()
            sessions[session_id] = (chat, uploaded_file)
            return f"{answer}\n\n---\nSession ID: {session_id}\n(Use this ID with ask_about_audio for follow-up questions)"

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

        # Send the actual question
        response = chat.send_message(question)
        answer = response.text

        # Store session
        session_id = generate_session_id()
        sessions[session_id] = (chat, uploaded_file)

        return f"{answer}\n\n---\nSession ID: {session_id}\n(Use this ID with ask_about_audio for follow-up questions)"

    except Exception as e:
        return f"Error communicating with Gemini: {str(e)}"


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
        response = chat.send_message(question)
        return response.text

    except Exception as e:
        return f"Error communicating with Gemini: {str(e)}"


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
