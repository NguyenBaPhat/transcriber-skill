# transcriber-skill

Skill phiên âm audio (Việt, Nhật, Anh, ...) bằng MCP Gemini: cài đặt, phiên âm verbatim, tự rà chính tả/định dạng, kiểm tra bằng script, chấm WER/CER.

- `skill/audio-transcriber/SKILL.md`: hướng dẫn đầy đủ, từ cài đặt đến báo cáo cuối.
- `skill/audio-transcriber/scripts/`: `server.py` (MCP server), `setup_mcp.sh`, `validate_format.py`, `wer.py`, `cer.py`.
- `audio-sample*/`: file audio mẫu, bản phiên âm chuẩn (`*_groundtruth.txt`) và kết quả Gemini (`out_*.txt`) dùng để đo độ chính xác.

Cần Gemini API key (đặt trong `.env`, **không** commit), `uv` và Claude Code. Xem `SKILL.md`.

## Nguồn dữ liệu mẫu

Các file audio mẫu là bản **cắt và/hoặc nối** từ dữ liệu công khai bên dưới. Bản phiên âm chuẩn đi kèm lấy từ chính các bộ dữ liệu đó.

| Thư mục | Nguồn | Giấy phép |
|---|---|---|
| `audio-sample-vi/`, `audio-sample-ja/` | [FLEURS](https://huggingface.co/datasets/google/fleurs) (Google), các câu tiếng Việt và tiếng Nhật nối liền | CC BY 4.0 |
| `audio-sample-multi/` | [AMI Meeting Corpus](https://groups.inf.ed.ac.uk/ami/corpus/), cuộc họp IS1009a, đoạn giây 60–300, qua mirror [FluidInference/ami-corpus-mirror](https://huggingface.co/datasets/FluidInference/ami-corpus-mirror) | CC BY 4.0 |
| `audio-sample/` | [John Markoff interview, part 4](https://commons.wikimedia.org/wiki/File:JohnMarkoff041306part4.ogg) (Wikimedia Commons), ghi âm bởi Alison Chaiken và Ann Arbor (KFJC), 2006 | CC BY-SA 3.0 |

Nếu bạn dùng lại các file này, hãy giữ ghi nguồn và tuân thủ giấy phép của từng bộ dữ liệu.
