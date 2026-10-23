#!/usr/bin/env python3
"""Kiểm tra Gemini API key có dùng được không. Không bao giờ in key.

Dùng: python3 -I check_key.py [--env-file PATH] [--model gemini-3.8-flash] [--no-generate]

Key lấy từ biến môi trường GEMINI_API_KEY, hoặc từ file .env (GEMINI_API_KEY / Gemini_key / GEMINI_KEY / GOOGLE_API_KEY).
Hỗ trợ cả hai dạng key:
  - cổ điển: "AIza" + 35 ký tự (tổng 39)
  - kiểu mới: bắt đầu bằng "AQ." (dài hơn, khoảng 50+ ký tự)
Mã thoát: 0 = key dùng được; 1 = lỗi (in nguyên nhân và cách xử lý).
"""
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

NAMES = ("GEMINI_API_KEY", "GEMINI_KEY", "GOOGLE_API_KEY")
BASE = "https://generativelanguage.googleapis.com/v1beta"


def find_key(env_file):
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k, "biến môi trường GEMINI_API_KEY"
    for f in [env_file, ".env", os.path.expanduser("~/.env")]:
        if not f or not os.path.isfile(f):
            continue
        for line in open(f, encoding="utf-8", errors="replace"):
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_]+)\s*=\s*(.*)$", line)
            if m and m[1].upper() in NAMES:
                v = m[2].strip().strip("\"'").strip()
                if v:
                    return v, f"file {f}"
    return "", ""


def kind(k):
    if re.fullmatch(r"AIza[0-9A-Za-z_-]{35}", k):
        return "cổ điển (AIza…)"
    if k.startswith("AQ."):
        return "kiểu mới (AQ.…)"
    return "dạng lạ (không phải AIza… hay AQ.…), vẫn thử"


def ssl_context():
    ctx = ssl.create_default_context()
    if not os.environ.get("SSL_CERT_FILE"):
        for c in ("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/cert.pem"):
            if os.path.isfile(c):
                ctx = ssl.create_default_context(cafile=c)
                break
    return ctx


def call(key, path, body=None):
    # Key đi trong header, không nằm trên URL (tránh lộ vào log)
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90, context=ssl_context()) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except Exception:
            return e.code, {}
    except Exception as e:  # mạng/SSL
        return 0, {"error": {"message": f"{type(e).__name__}: {str(e)[:200]}"}}


def explain(code, data):
    msg = (data.get("error", {}) or {}).get("message", "")
    low = msg.lower()
    if code == 0:
        if "certificate" in low or "ssl" in low:
            return "Lỗi SSL. Đặt SSL_CERT_FILE trỏ tới CA hệ thống (vd /etc/ssl/certs/ca-certificates.crt). KHÔNG tắt xác thực SSL."
        return f"Không kết nối được tới Google: {msg}"
    if "reported as leaked" in low:
        return "Key đã bị Google VÔ HIỆU HÓA vì bị lộ. Tạo key MỚI trong Google AI Studio, xóa key cũ, cập nhật .env, chạy lại setup_mcp.sh, mở session mới."
    if code in (400, 401) and ("api key" in low or "api_key" in low):
        return "Key không hợp lệ hoặc hết hạn. Kiểm tra lại .env (khoảng trắng, dấu nháy, thiếu ký tự); key phải bắt đầu bằng AIza hoặc AQ."
    if code == 403:
        return f"Bị từ chối (403): {msg[:160]}. Key có thể thiếu quyền hoặc API Generative Language chưa bật cho project của key."
    if code == 429:
        return "Hết quota/rate limit (429). Chờ khoảng 1 phút hoặc kiểm tra gói của key."
    if code in (500, 503):
        return f"Gemini đang lỗi/quá tải ({code}), thường tạm thời. Thử lại sau."
    return f"HTTP {code}: {msg[:200]}"


def main():
    a = sys.argv[1:]
    env_file = a[a.index("--env-file") + 1] if "--env-file" in a else ""
    model = a[a.index("--model") + 1] if "--model" in a else "gemini-3.8-flash"
    key, src = find_key(env_file)
    if not key:
        print("KHÔNG TÌM THẤY KEY. Đặt GEMINI_API_KEY hoặc dùng --env-file (biến: GEMINI_API_KEY / Gemini_key / GOOGLE_API_KEY).")
        sys.exit(1)
    print(f"Key: tìm thấy trong {src}; dạng {kind(key)}; độ dài {len(key)} (không in giá trị)")

    code, data = call(key, "/models?pageSize=1")
    if code != 200:
        print("1) Liệt kê model: THẤT BẠI ->", explain(code, data))
        sys.exit(1)
    print("1) Liệt kê model: OK")

    code, data = call(key, f"/models/{model}")
    if code == 404:
        print(f"2) Model {model}: KHÔNG CÓ với key này. Chọn model khác (--model) hoặc đặt GEMINI_MODEL.")
        sys.exit(1)
    if code != 200:
        print(f"2) Model {model}: THẤT BẠI ->", explain(code, data))
        sys.exit(1)
    print(f"2) Model {model}: có")

    if "--no-generate" not in a:
        code, data = call(key, f"/models/{model}:generateContent",
                          {"contents": [{"parts": [{"text": "Reply with the single word: OK"}]}]})
        if code in (0, 429, 500, 503):
            # Key đã qua bước 1-2 nên hợp lệ; dịch vụ chỉ đang chậm/quá tải/giới hạn tạm thời
            print("3) Gọi thử sinh văn bản: CẢNH BÁO (không phải lỗi key) ->", explain(code, data))
        elif code != 200:
            print("3) Gọi thử sinh văn bản: THẤT BẠI ->", explain(code, data))
            sys.exit(1)
        else:
            print("3) Gọi thử sinh văn bản: OK")
    print("KEY DÙNG ĐƯỢC.")


if __name__ == "__main__":
    main()
