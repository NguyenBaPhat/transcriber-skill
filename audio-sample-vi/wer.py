#!/usr/bin/env python3
"""WER/CER: python3 wer.py reference.txt hypothesis.txt
Bỏ nhãn [..], [mm:ss], Speaker N:, dấu câu, chữ hoa; so khớp theo từ (âm tiết tiếng Việt)."""
import re, sys, unicodedata

def norm(s):
    s = unicodedata.normalize("NFC", s.lower())
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"speaker\s*\d+\s*:", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return s.split()

def edit(a, b):
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        p, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            p, d[j] = d[j], min(d[j] + 1, d[j-1] + 1, p + (a[i-1] != b[j-1]))
    return d[-1]

ref = norm(open(sys.argv[1], encoding="utf-8").read())
hyp = norm(open(sys.argv[2], encoding="utf-8").read())
e = edit(ref, hyp)
print(f"từ chuẩn: {len(ref)}  từ Gemini: {len(hyp)}  lỗi: {e}  WER: {e/len(ref):.2%}  (độ chính xác ≈ {1-e/len(ref):.2%})")
