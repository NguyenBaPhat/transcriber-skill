#!/usr/bin/env python3
"""CER (tỷ lệ lỗi ký tự) cho tiếng Nhật: python3 cer.py reference.txt hypothesis.txt
Bỏ nhãn [..], Speaker N:, dấu câu (kể cả 、。「」), khoảng trắng; chuẩn hóa NFKC (chữ/số toàn-bán giác)."""
import re, sys, unicodedata

def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = re.sub(r"speaker\s*\d+\s*:", "", s, flags=re.I)
    return [c for c in s.lower() if not unicodedata.category(c).startswith(("P", "S", "Z", "C"))]

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
print(f"ký tự chuẩn: {len(ref)}  ký tự Gemini: {len(hyp)}  lỗi: {e}  CER: {e/len(ref):.2%}  (độ chính xác ≈ {1-e/len(ref):.2%})")
