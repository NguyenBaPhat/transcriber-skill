#!/usr/bin/env bash
# Đăng ký MCP "claudio" (Gemini nghe audio) vào Claude Code.
# Dùng: bash setup_mcp.sh [--env-file PATH] [--model gemini-3.8-flash] [--name claudio] [--scope local|user|project] [--dry-run]
# Không bao giờ in API key ra màn hình.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE=""
MODEL="gemini-3.8-flash"
NAME="claudio"
SCOPE="local"
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --model)    MODEL="$2"; shift 2 ;;
    --name)     NAME="$2"; shift 2 ;;
    --scope)    SCOPE="$2"; shift 2 ;;
    --dry-run)  DRY=1; shift ;;
    *) echo "Tham số lạ: $1" >&2; exit 2 ;;
  esac
done

command -v uv >/dev/null     || { echo "THIẾU: uv. Cài: https://docs.astral.sh/uv/ (curl -LsSf https://astral.sh/uv/install.sh | sh)" >&2; exit 1; }
command -v claude >/dev/null || { echo "THIẾU: claude CLI (Claude Code)" >&2; exit 1; }
[ -f "$HERE/server.py" ]     || { echo "THIẾU: $HERE/server.py" >&2; exit 1; }

# 1. Tìm API key: biến môi trường trước, rồi file .env (tên biến không phân biệt hoa/thường)
KEY="${GEMINI_API_KEY:-}"
if [ -z "$KEY" ]; then
  CANDIDATES=("$ENV_FILE" "./.env" "$HERE/../.env" "$HOME/.env")
  for f in "${CANDIDATES[@]}"; do
    [ -n "$f" ] && [ -f "$f" ] || continue
    KEY="$(grep -iE '^(export[[:space:]]+)?(GEMINI_API_KEY|GEMINI_KEY|GOOGLE_API_KEY)[[:space:]]*=' "$f" | head -1 | cut -d= -f2- | tr -d "\"' \r" || true)"
    [ -n "$KEY" ] && { echo "Đã tìm thấy key trong: $f (không in giá trị)"; break; }
  done
fi
[ -n "$KEY" ] || { echo "KHÔNG TÌM THẤY API KEY. Đặt GEMINI_API_KEY hoặc dùng --env-file PATH (biến: GEMINI_API_KEY / Gemini_key / GOOGLE_API_KEY)." >&2; exit 1; }

# 2. Bundle CA hệ thống (cần khi mạng công ty có SSL inspection -> lỗi CERTIFICATE_VERIFY_FAILED)
CA=""
for c in /etc/ssl/certs/ca-certificates.crt /etc/pki/tls/certs/ca-bundle.crt /etc/ssl/cert.pem; do
  [ -f "$c" ] && { CA="$c"; break; }
done
ENV_ARGS=(-e "GEMINI_API_KEY=$KEY" -e "GEMINI_MODEL=$MODEL")
[ -n "$CA" ] && ENV_ARGS+=(-e "SSL_CERT_FILE=$CA" -e "REQUESTS_CA_BUNDLE=$CA")

CMD=(uv run --no-project --native-tls --with google-genai --with "mcp<2" python "$HERE/server.py")

if [ "$DRY" = 1 ]; then
  echo "[dry-run] claude mcp remove $NAME   (nếu đã có)"
  echo "[dry-run] claude mcp add $NAME -s $SCOPE -e GEMINI_API_KEY=<hidden> -e GEMINI_MODEL=$MODEL ${CA:+-e SSL_CERT_FILE=$CA -e REQUESTS_CA_BUNDLE=$CA} -- ${CMD[*]}"
  exit 0
fi

claude mcp remove "$NAME" -s "$SCOPE" >/dev/null 2>&1 || true
claude mcp add "$NAME" -s "$SCOPE" "${ENV_ARGS[@]}" -- "${CMD[@]}" 2>&1 | sed "s/$KEY/<hidden>/g"
echo "--- Trạng thái:"
claude mcp list 2>&1 | grep -F "$NAME" | sed "s/$KEY/<hidden>/g" || true
echo "XONG. Hãy MỞ SESSION MỚI của Claude Code để tool mcp__${NAME}__listen_to_audio xuất hiện."
