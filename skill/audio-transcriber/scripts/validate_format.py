#!/usr/bin/env python3
"""Kiểm tra định dạng file phiên âm.

Dùng: python3 -I validate_format.py FILE [--speakers] [--duration GIÂY]
  --speakers  : mỗi dòng phải có nhãn "Speaker N:" sau mốc thời gian
  --duration  : mốc cuối không được vượt quá thời lượng audio (giây)

Dòng hợp lệ:  [mm:ss.s] Nội dung          hoặc   [mm:ss.s] Speaker 1: Nội dung
Thoát với mã 1 nếu có lỗi (in danh sách lỗi), 0 nếu sạch.
"""
import re
import sys

args = sys.argv[1:]
if not args:
    sys.exit(__doc__)
path = args[0]
need_spk = "--speakers" in args
duration = float(args[args.index("--duration") + 1]) if "--duration" in args else None

raw = open(path, "rb").read()
errors, warns = [], []
if raw.startswith(b"\xef\xbb\xbf"):
    errors.append("File có BOM; phải là UTF-8 không BOM")
try:
    text = raw.decode("utf-8-sig")
except UnicodeDecodeError:
    sys.exit("LỖI: file không phải UTF-8")
if "\r" in text:
    errors.append("Có ký tự \\r (CRLF); dùng LF")
if not text.endswith("\n"):
    errors.append("Thiếu xuống dòng ở cuối file")

pat = re.compile(r"^\[(\d{2,}):(\d{2}\.\d)\] (Speaker \d+: )?(\S(?:.*\S)?)$")
junk = re.compile(r"session id|follow-up|ask_about_audio|^-{3,}$|^```", re.I)
prev, n = -1.0, 0
for i, line in enumerate(text.split("\n")[:-1] if text.endswith("\n") else text.split("\n"), 1):
    if not line.strip():
        errors.append(f"dòng {i}: dòng trống"); continue
    if junk.search(line):
        errors.append(f"dòng {i}: còn phần thừa của MCP/markdown: {line[:40]!r}"); continue
    m = pat.match(line)
    if not m:
        errors.append(f"dòng {i}: sai định dạng, không khớp '[mm:ss.s] ...' hoặc thừa/thiếu khoảng trắng: {line[:50]!r}"); continue
    n += 1
    t = int(m[1]) * 60 + float(m[2])
    if t < prev:
        errors.append(f"dòng {i}: mốc thời gian giảm ({t:.1f}s < {prev:.1f}s)")
    elif t == prev:
        warns.append(f"dòng {i}: trùng mốc với dòng trước ({t:.1f}s)")
    prev = t
    if need_spk and not m[3]:
        errors.append(f"dòng {i}: thiếu nhãn 'Speaker N:'")
    if duration is not None and t > duration + 0.5:
        errors.append(f"dòng {i}: mốc {t:.1f}s vượt thời lượng audio {duration:.1f}s")

if n == 0:
    errors.append("Không có dòng phiên âm hợp lệ nào")
print(f"{path}: {n} dòng hợp lệ, {len(errors)} lỗi, {len(warns)} cảnh báo")
for e in errors:
    print("  LỖI:", e)
for w in warns:
    print("  cảnh báo:", w)
sys.exit(1 if errors else 0)
