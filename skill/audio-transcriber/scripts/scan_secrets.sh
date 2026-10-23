#!/usr/bin/env bash
# Quét bí mật TRƯỚC KHI commit/push. Không in giá trị bí mật.
# Dùng: bash scan_secrets.sh [THƯ_MỤC_REPO=.] [--env-file PATH]
# Kiểm tra: (1) mẫu key Google cổ điển "AIza…" và kiểu mới "AQ.…", GitHub token, khóa riêng;
#           (2) đúng giá trị key đang nằm trong .env (trong file đang theo dõi, chưa theo dõi và lịch sử git).
# Thoát 1 nếu thấy gì.
set -uo pipefail
REPO="."; ENV_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    *) REPO="$1"; shift ;;
  esac
done
cd "$REPO" || exit 2
FOUND=0

PATTERN='AIza[0-9A-Za-z_-]{30,}|AQ\.[0-9A-Za-z_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{30,}|BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY'
echo "[1] Mẫu bí mật trong file (kể cả chưa theo dõi):"
HITS=$(grep -rIlE "$PATTERN" . --exclude-dir=.git 2>/dev/null || true)
if [ -n "$HITS" ]; then echo "$HITS" | sed 's/^/   CÓ: /'; FOUND=1; else echo "   sạch"; fi

KEY=""
for f in "$ENV_FILE" ./.env ../.env "$HOME/.env"; do
  [ -n "$f" ] && [ -f "$f" ] || continue
  KEY="$(grep -iE '^(export[[:space:]]+)?(GEMINI_API_KEY|GEMINI_KEY|GOOGLE_API_KEY)[[:space:]]*=' "$f" | head -1 | cut -d= -f2- | tr -d "\"' \r" || true)"
  [ -n "$KEY" ] && break
done
if [ -n "$KEY" ]; then
  echo "[2] Đúng giá trị key trong .env (độ dài ${#KEY}):"
  F=$(grep -rIlF -- "$KEY" . --exclude-dir=.git 2>/dev/null || true)
  if [ -n "$F" ]; then echo "$F" | sed 's/^/   CÓ trong file: /'; FOUND=1; else echo "   không có trong file"; fi
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    H=$(git log --all --oneline -S"$KEY" 2>/dev/null | head -3)
    if [ -n "$H" ]; then echo "$H" | sed 's/^/   CÓ trong lịch sử git: /'; FOUND=1; else echo "   không có trong lịch sử git"; fi
  fi
else
  echo "[2] Bỏ qua: không tìm thấy key trong .env để so khớp"
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[3] Mẫu bí mật nằm trong LỊCH SỬ git (chỉ cảnh báo, không chặn):"
  OLD=$(git log --all --oneline -G"$PATTERN" 2>/dev/null | head -5)
  if [ -n "$OLD" ]; then
    echo "$OLD" | sed 's/^/   CẢNH BÁO commit cũ có mẫu bí mật: /'
    echo "   Key trong các commit này coi như đã lộ nếu repo public: thu hồi nó. Muốn xóa khỏi lịch sử cần ghi đè lịch sử (git filter-repo + push --force), hãy cân nhắc kỹ."
  else
    echo "   sạch"
  fi
fi

[ "$FOUND" = 0 ] && echo "SẠCH: an toàn để commit." || echo "PHÁT HIỆN BÍ MẬT: KHÔNG commit/push. Xóa khỏi file, và nếu đã lộ thì thu hồi key ngay."
exit "$FOUND"
