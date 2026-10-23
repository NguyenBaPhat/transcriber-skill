---
name: audio-transcriber
description: Phiên âm audio (Việt, Nhật, Anh, ...) verbatim bằng MCP Gemini (`claudio`, model gemini-3.8-flash), kèm timestamp, nhãn người nói, bước tự rà chính tả/định dạng, kiểm tra bằng script, và chấm WER/CER nếu có bản chuẩn. Dùng khi người dùng đưa file audio (.wav .mp3 .ogg .flac .aac .aiff) và muốn bản transcript, hoặc muốn cài/sửa MCP nghe audio. Dùng cả khi họ nhắc "transcribe", "phiên âm", "nghe file audio", "gỡ băng".
---

# Audio Transcriber (MCP Gemini)

Mình (Claude) **không nghe được audio trực tiếp**. Skill này dùng một MCP server gọi Gemini để nghe file, trả về chữ, rồi bạn kiểm tra và lưu thành transcript.

Thư mục skill (`<SKILL_DIR>`) chứa:

| File | Việc |
|---|---|
| `scripts/server.py` | MCP server `claudio` đã vá (model đọc từ `GEMINI_MODEL`, mặc định `gemini-3.8-flash`) |
| `scripts/setup_mcp.sh` | Đăng ký MCP vào Claude Code, không in API key |
| `scripts/validate_format.py` | Kiểm tra định dạng transcript |
| `scripts/wer.py` | Chấm WER (ngôn ngữ có dấu cách: Việt, Anh) |
| `scripts/cer.py` | Chấm CER (Nhật, Trung, ...) |
| `scripts/check_key.py` | Kiểm tra Gemini API key dùng được (cả key `AIza…` lẫn `AQ.…`), nói rõ nguyên nhân nếu hỏng |
| `scripts/scan_secrets.sh` | Quét bí mật (key, token) trong file và lịch sử git **trước khi commit/push** |

Quy tắc chung: **không bao giờ in hay ghi API key** ra màn hình, log, file hay câu trả lời.

---

## Bước 0: Cổng ủy quyền (bắt buộc, làm trước tiên)

Audio được gửi cho Google (Gemini). Hỏi người dùng nếu chưa rõ:

- Audio là **file mẫu/test** hay **dữ liệu thật của khách hàng/dự án**?
- Nếu là dữ liệu thật: có **NDA hoặc quy định dự án cấm AI/dịch vụ bên thứ ba** không? Chỉ tiếp tục khi người dùng xác nhận **đã được phép bằng văn bản**. Nếu không chắc, **dừng lại và hỏi**, không tự upload.
- Không đưa audio dự án thật qua công cụ này chỉ vì "thử cho nhanh".

---

## Bước 1: Cài đặt (làm một lần mỗi máy)

Yêu cầu: `uv` và `claude` (Claude Code) có trong PATH, và một Gemini API key.

1. **Kiểm tra key.** Key nằm trong biến môi trường `GEMINI_API_KEY` hoặc file `.env` với một trong các tên: `GEMINI_API_KEY`, `Gemini_key`, `GEMINI_KEY`, `GOOGLE_API_KEY`. Chỉ in **tên biến**, không in giá trị, ví dụ:
   ```bash
   sed -E 's/=.*/=<hidden>/' /đường/dẫn/.env
   ```
   **Có hai dạng key, cả hai đều dùng được, không cần đổi gì:**
   - Cổ điển: bắt đầu bằng `AIza`, dài 39 ký tự.
   - Kiểu mới: bắt đầu bằng `AQ.`, dài hơn (khoảng 50+ ký tự).

   Khi dán key vào `.env`: không thêm khoảng trắng hay xuống dòng giữa key, dấu nháy bao ngoài thì được (script tự bỏ). Nếu key có dạng khác hai dạng trên, script chỉ cảnh báo rồi vẫn thử.
2. **Kiểm tra key trước** (không in key, báo rõ nguyên nhân nếu hỏng):
   ```bash
   python3 -I <SKILL_DIR>/scripts/check_key.py --env-file /đường/dẫn/.env
   ```
   `KEY DÙNG ĐƯỢC` là qua. Nếu Gemini đang chậm hoặc quá tải ở bước 3 của script thì chỉ là cảnh báo, key vẫn hợp lệ. Lỗi `reported as leaked` nghĩa là Google đã thu hồi key: phải tạo key MỚI (xem bảng lỗi).
   `setup_mcp.sh` tự chạy bước này, key hỏng thì dừng và **không** đổi cấu hình MCP (bỏ qua bằng `--skip-check`).
3. **Chạy thử cài đặt, không thay đổi gì:**
   ```bash
   bash <SKILL_DIR>/scripts/setup_mcp.sh --env-file /đường/dẫn/.env --dry-run
   ```
4. **Cài thật:**
   ```bash
   bash <SKILL_DIR>/scripts/setup_mcp.sh --env-file /đường/dẫn/.env
   ```
   Kết quả mong đợi: `claudio: ... - ✔ Connected`. Tùy chọn: `--model`, `--name`, `--scope local|user|project`, `--skip-check`.
5. **Mở SESSION MỚI** của Claude Code. Session đang chạy chỉ nạp danh sách MCP lúc khởi động, nên sẽ không thấy tool mới. Đây là điều dễ bị bỏ sót nhất.

Vì sao `setup_mcp.sh` làm như vậy (đừng đổi nếu chưa hiểu):
- Dùng `server.py` **đã vá**, không dùng gói `claudio` trên PyPI, vì bản gốc ghi cứng model `gemini-3-pro-preview` (Google đã ngừng, lỗi 404).
- Ghim `mcp<2`, vì `mcp` 2.x đổi API (`FastMCP` thành `MCPServer`), bản gốc bị lỗi import.
- `uv --native-tls` và `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` trỏ tới CA hệ thống, vì mạng công ty có SSL inspection thường gây `CERTIFICATE_VERIFY_FAILED` / `UnknownIssuer`. Đây là dùng chứng chỉ hệ thống, **không tắt** xác thực SSL. Tuyệt đối không tắt verify để "lách".
- Key được lưu vào file cấu hình của Claude Code (ví dụ `~/.claude.json`). Nhắc người dùng không chia sẻ file đó.

## Bước 2: Xác nhận tool dùng được

Trong session mới, tìm tool bằng `ToolSearch` với `select:mcp__claudio__listen_to_audio,mcp__claudio__ask_about_audio` (hoặc từ khóa "listen_to_audio"). Nếu không thấy:

1. Chạy `claude mcp list`. Nếu `claudio` là `✘ Failed`, chạy thử trực tiếp để xem lỗi (xem bảng xử lý lỗi ở cuối).
2. Nếu `✔ Connected` mà session vẫn không thấy tool, yêu cầu người dùng mở session mới.
3. **Không** tự cài MCP khác, không chạy model cục bộ (Whisper...), trừ khi người dùng đồng ý.

## Bước 3: Phiên âm

Gọi `mcp__claudio__listen_to_audio(file_path, question)` với **đường dẫn tuyệt đối**. Định dạng hỗ trợ: `.wav .mp3 .ogg .flac .aac .aiff` (không có `.m4a`; nếu cần, báo người dùng đổi định dạng).

**Câu hỏi (prompt) cho một người nói:**
```
Transcribe this audio VERBATIM in {LANGUAGE}. Write exactly what is spoken; do not clean up, paraphrase or correct the speech. Keep filler words, repetitions and false starts. One sentence per line, each line starting with [mm:ss.s] (one decimal place). Write [unintelligible] where you cannot hear clearly; never guess. Start at 00:00.0 and continue to the very end of the file. Output only the transcript lines, no commentary.
```

**Câu hỏi cho nhiều người nói:** thêm vào cuối prompt:
```
Label each line with the speaker as "Speaker 1:", "Speaker 2:" ... in order of first appearance (keep labels consistent for the whole file), placed right after the timestamp. When speakers overlap, write separate lines, one per speaker. Mark non-speech sounds as [laughter], [noise], [music], [unintelligible] when they occur.
```

Lưu ý khi gọi:
- Kết quả có đuôi `--- Session ID: xxxx ...`. **Cắt bỏ phần đuôi này** khi lưu transcript; giữ lại session ID để hỏi tiếp.
- Nếu kết quả **dừng trước cuối file** (từng gặp: file 6:51 chỉ ra tới 6:21), gọi `mcp__claudio__ask_about_audio(session_id, "Continue from mm:ss.s to the end, same format")` rồi nối kết quả. Kiểm tra không bị trùng hoặc sót ở chỗ nối.
- File dài: Gemini dễ bỏ sót hoặc cắt. Nên yêu cầu theo từng khoảng (ví dụ mỗi 5 phút) nếu file dài hơn khoảng 10 phút.
- Không tin tuyệt đối vào timestamp (xem phần Hạn chế).

### Khi kết quả là `None`, rỗng hoặc lỗi (đặc biệt hay gặp với file tiếng Nhật)

**Một kết quả không có dòng `[mm:ss.s]` nào, hoặc bắt đầu bằng `Error`, hoặc chỉ là chữ `None` là THẤT BẠI, không được lưu thành transcript và không được coi là xong.**

Từng gặp: file tiếng Nhật cùng một file khi thì trả `None`, khi thì chạy bình thường. Nguyên nhân thật là Gemini **chặn đầu vào chập chờn** (`block_reason=OTHER`, không có candidate nào), kèm lỗi `503 high demand`, không liên quan nội dung file. Bản `server.py` hiện tại đã tự thử lại tối đa 3 lần (chờ 5s, 15s, 30s) và báo lý do cụ thể thay vì `None`. Vì vậy:

1. **Đọc thông báo lỗi**, đừng đoán. Chú ý phần `HINT:` ở cuối.
2. Lỗi tạm thời (`503`, `UNAVAILABLE`, `block_reason=OTHER`, timeout): đợi khoảng 1 đến 2 phút rồi **gọi lại cả file** vài lần. Mỗi lần gọi có thể mất 1 đến 2 phút khi Gemini bận, đó là bình thường.
3. Vẫn thất bại sau khoảng 3 lần gọi: **chia audio thành các đoạn ngắn hơn** (khoảng 1 đến 2 phút, cắt ở chỗ ngắt câu), phiên âm từng đoạn rồi nối lại, cộng mốc thời gian của đoạn vào từng dòng. Với WAV có thể cắt bằng module `wave` của Python.
4. Lỗi **không tạm thời** thì thử lại cũng vô ích, hãy xử lý đúng gốc:
   - `reported as leaked` / `API_KEY_INVALID` / `403`: vấn đề ở key (xem bảng lỗi).
   - `404`: sai tên model, đặt `GEMINI_MODEL`.
   - `CERTIFICATE_VERIFY_FAILED`: thiết lập CA hệ thống (xem bảng lỗi).
5. Lỗi sau khi **đã đổi key**: tiến trình MCP đang chạy vẫn giữ key cũ. Chạy lại `setup_mcp.sh` rồi **mở session mới**.
6. Cuối cùng vẫn không được thì **báo thẳng cho người dùng** lý do và những gì đã thử. Không bịa transcript, không lấy bản cũ của lần chạy khác thay vào.

## Bước 4: Lưu file

Lưu vào đường dẫn người dùng chỉ định (nếu không nói, đặt cạnh file audio với tên `<tên_audio>_transcript.txt`), UTF-8 không BOM, mỗi dòng dạng:
```
[mm:ss.s] Nội dung
[mm:ss.s] Speaker 1: Nội dung      (khi có nhiều người nói)
```
Không dòng trống, không lời dẫn, không khối markdown, có xuống dòng cuối file.

## Bước 5: Tự rà soát chính tả và định dạng (không bỏ qua)

Đọc lại file vừa lưu và **sửa trực tiếp**:

**a) Chính tả**
- Lỗi gõ, thiếu/thừa dấu, sai dấu thanh, sai chữ.
- Thống nhất một kiểu viết trong cả file (một từ không viết hai kiểu khác nhau).
- Tên riêng, từ mượn, thuật ngữ: viết đúng chính tả phổ biến. Nếu **không chắc**, dùng `ask_about_audio` để nghe lại đúng đoạn đó rồi mới sửa.
- Con số: thống nhất một kiểu.
- Nếu dự án có **guideline chính tả riêng**, guideline thắng mọi mặc định bên dưới.

**b) Mặc định theo ngôn ngữ (khi chưa có guideline)**
- *Tiếng Việt:* viết "tỷ" thống nhất (không lẫn "tỉ"); kiểu đặt dấu thanh nhất quán trong file (hòa/hoà); tên riêng viết hoa nhất quán; số theo guideline (ví dụ "5 trận" hoặc "năm trận", chọn một).
- *Tiếng Nhật:* không đổi tùy tiện kanji/hiragana/katakana; giữ cách viết katakana nhất quán; chữ số bán giác (`2人`); dấu câu `、。`. Nhớ: cùng một từ có nhiều cách viết hợp lệ (ベルサーチ/ヴェルサーチ, 繋/つな), nên đừng "sửa" nếu không cần.
- *Tiếng Anh:* giữ dạng khẩu ngữ nếu dự án yêu cầu verbatim (`gonna`, `wanna`); nếu không có yêu cầu, ghi rõ bạn đã chọn kiểu nào.

**c) Định dạng:** đúng mẫu ở Bước 4; mốc thời gian không giảm; không dòng trống; không khoảng trắng thừa đầu/cuối dòng.

**d) Quy tắc quan trọng:** chỉ sửa chính tả và định dạng.
- **Không** thêm, bỏ hay thay từ khi chưa nghe lại để xác nhận.
- **Không thêm dấu câu làm đổi cách ngắt ý** (từng gặp: AI thêm dấu phẩy làm tách cụm từ sai). Nếu dự án không yêu cầu dấu câu, giữ nguyên.
- Giữ nguyên từ đệm, lặp từ, câu bỏ dở (verbatim), đừng "làm sạch".

## Bước 6: Kiểm tra bằng script

```bash
python3 -I <SKILL_DIR>/scripts/validate_format.py FILE_TRANSCRIPT.txt [--speakers] [--duration GIÂY]
```
Phải ra `0 lỗi`. Có lỗi thì sửa file rồi chạy lại (lỗi hay gặp: còn đuôi `Session ID`, mốc thời gian giảm, dòng trống, thiếu nhãn người nói khi dùng `--speakers`).

## Bước 7 (tùy chọn): Chấm điểm khi có bản chuẩn

Chỉ làm khi người dùng **có sẵn bản phiên âm chuẩn** và muốn đo độ chính xác. **Không đọc bản chuẩn trước khi chốt bản của bạn** (tránh sửa theo đáp án).

```bash
python3 -I <SKILL_DIR>/scripts/wer.py CHUAN.txt TRANSCRIPT.txt     # Việt, Anh
python3 -I <SKILL_DIR>/scripts/cer.py CHUAN.txt TRANSCRIPT.txt     # Nhật, Trung
```
Hai script bỏ nhãn `[..]`, `Speaker N:`, dấu câu và chữ hoa. Khi diễn giải, **tách riêng**: (1) lỗi nghe nhầm thật, (2) khác biệt cách viết (katakana, "gonna"/"going to", "5"/"năm"), (3) chỗ bản chuẩn có thể sai. Đừng báo một con số thô như thể đó là độ chính xác thật.

## Bước 8: Báo cáo cuối

Báo ngắn gọn, thành thật:
1. File transcript đã lưu ở đâu, số dòng, thời lượng bao phủ.
2. Những gì đã sửa ở Bước 5 (liệt kê ngắn: cũ → mới).
3. Kết quả `validate_format.py`.
4. WER/CER nếu có chấm, kèm phân loại ở Bước 7.
5. **Các chỗ còn chưa chắc** (tên riêng, đoạn nói chồng, đoạn nghi nghe nhầm) để người dùng nghe lại.
6. Nói rõ **chưa kiểm chứng với audio gốc** nếu bạn không có bản chuẩn: bạn không nghe được audio, mọi nhận xét chỉ dựa trên kết quả Gemini.

---

## Hạn chế đã đo (đừng hứa quá)

Kết quả thử trên các file mẫu (một lần chạy mỗi file, `gemini-3.8-flash`, có bước rà chính tả):

| Loại audio | Kết quả | Ghi chú |
|---|---|---|
| Tiếng Việt, giọng đọc (FLEURS) | WER ≈ 1.1% – 2.2% (độ chính xác 97.8–98.9%) | Lỗi còn lại: tên riêng/từ nước ngoài, chênh cách viết |
| Tiếng Nhật, giọng đọc (FLEURS) | CER ≈ 1.2% – 1.3% (≈ 98.7–98.8%, hai lần chạy) | Phần lớn là khác biệt cách viết katakana/kanji/số; lỗi nghe nhầm thật nằm ở chỗ khác nhau giữa các lần chạy. Hay gặp `None`/503 chập chờn (xem mục xử lý lỗi) |
| Tiếng Anh, họp 4 người, nói chồng (AMI) | WER ≈ 16% thô; khoảng 12–13% sau chuẩn hóa; khoảng 8% nếu bỏ từ đệm | Khó hơn nhiều; nhãn người nói rất ít sai (≈ 2/64 lượt) |

- **Chưa chứng minh được trên 98% cho hội thoại thật** (nói chồng, từ đệm, thổ ngữ). Luôn khuyến nghị người nghe lại trước khi nộp.
- **Timestamp không đáng tin cho yêu cầu lệch dưới 500ms.** Đo thật: tiếng Việt lệch trung vị ≈ 0.46s (9/16 mốc ≤ 0.5s); tiếng Nhật lệch trung vị ≈ 1.5s (5/14 mốc ≤ 0.5s, thường muộn 1–3s). Cần căn chỉnh bằng công cụ chuyên dụng (forced alignment) nếu yêu cầu chặt.
- Gemini hay **viết lại khẩu ngữ thành văn viết** (`gonna` thành `going to`) và **ít đánh dấu `[unintelligible]`**; nói chồng chỉ xử lý sơ sài.
- Lỗi tập trung ở **tên riêng, từ mượn, số**. Luôn kiểm tra các mục này.
- Chưa thử với file dài hơn 20 MB (server dùng Files API cho file lớn; chưa kiểm chứng).

## Bảo mật khi dùng git (bài học đã trả giá)

Key Gemini từng bị dán vào một file trong repo **công khai** và chỉ khoảng 2 phút sau Google đã thu hồi nó. Xóa khỏi commit sau không cứu được: key vẫn nằm trong lịch sử git.

- **Không bao giờ** đặt key vào file nằm trong repo (kể cả `SKILL.md`, README, ghi chú). Chỉ để trong `.env`, và `.env` phải nằm trong `.gitignore`.
- **Trước mỗi lần commit/push**, chạy: `bash <SKILL_DIR>/scripts/scan_secrets.sh <THƯ_MỤC_REPO> --env-file /đường/dẫn/.env`. Nó quét cả hai dạng key (`AIza…` và `AQ.…`), token GitHub, khóa riêng, đúng giá trị key trong `.env`, và cả lịch sử git. Báo `PHÁT HIỆN BÍ MẬT` thì **dừng**, không push.
- Nếu key đã lộ: thu hồi ngay trong Google AI Studio và tạo key mới. Chỉ ghi đè lịch sử git (`filter-repo` + `push --force`) khi người dùng đồng ý rõ ràng, vì nó phá lịch sử của repo.
- Không in key khi debug; che bằng `sed -E 's/(AIza|AQ\.)[A-Za-z0-9_-]+/\1<ẨN>/g'`.

## Không nên dùng model `gemini-3.5-transcribe`

Đã thử: model này **không tuân theo yêu cầu định dạng** (không timestamp, không xuống dòng), kém hơn `gemini-3.8-flash` trên cùng file, và bị giới hạn quota ≈ 10,000 token đầu vào mỗi phút (khoảng 25 token mỗi giây audio, nên file hơn khoảng 6 phút dễ lỗi 429). `server.py` vẫn hỗ trợ nếu đặt `GEMINI_MODEL=gemini-3.5-transcribe` (gửi một lượt, trích `audio_transcription.text`), nhưng không khuyến nghị.

## Bảng xử lý lỗi

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `claude mcp list`: `✘ Failed to connect` | `uvx` không tải được gói qua mạng có SSL inspection | Dùng `setup_mcp.sh` (đã có `--native-tls`); chạy tay lệnh trong `claude mcp list` để xem lỗi thật |
| `CERTIFICATE_VERIFY_FAILED` / `UnknownIssuer` | CA công ty không nằm trong bundle của Python | `SSL_CERT_FILE` và `REQUESTS_CA_BUNDLE` trỏ tới `/etc/ssl/certs/ca-certificates.crt` (script đã làm). Không tắt SSL verify |
| `404 ... models/gemini-3-pro-preview is no longer available` | Đang dùng bản `claudio` gốc | Dùng `server.py` trong skill này |
| `No module named 'mcp.server.fastmcp'` | `mcp` 2.x | Ghim `mcp<2` (script đã làm) |
| `400 Multiturn chat is not enabled for this model` | Model `*-transcribe` không hỗ trợ chat nhiều lượt | Dùng `gemini-3.8-flash`, hoặc `server.py` của skill (đã xử lý) |
| Kết quả `None` hoặc rỗng với model transcribe | Văn bản nằm ở `audio_transcription.text` | `server.py` của skill đã xử lý |
| `429 RESOURCE_EXHAUSTED` | Hết quota theo phút (hoặc key hết hạn mức) | Chờ khoảng 1 phút rồi thử lại; chia nhỏ file; kiểm tra gói/billing của key |
| `403 ... Your API key was reported as leaked` | Google đã **thu hồi** key vì nó bị lộ (thường do commit lên repo công khai, dán vào file dùng chung, ...) | Tạo key MỚI trong Google AI Studio, xóa key cũ, cập nhật `.env`, chạy `check_key.py`, chạy lại `setup_mcp.sh`, mở session mới. Key đã lộ không dùng lại được dù xóa khỏi file |
| `400/401 API key not valid` / `API_KEY_INVALID` | Key sai, thiếu ký tự, thừa khoảng trắng/xuống dòng, hoặc hết hạn | `python3 -I scripts/check_key.py --env-file ...` để xem; key phải bắt đầu bằng `AIza` hoặc `AQ.` |
| Key bắt đầu bằng `AQ.` có chạy được không? | Có | Cả `AIza…` và `AQ.…` đều dùng được qua SDK; `check_key.py` nhận diện cả hai. Không cần đổi gì khác |
| Kết quả là `None`, hoặc `Gemini returned no text (... block_reason=OTHER ...)` | Gemini chặn đầu vào chập chờn (từng gặp với file tiếng Nhật), không gắn với một câu cụ thể | Đợi 1 đến 2 phút gọi lại; sau khoảng 3 lần thì chia nhỏ audio (xem mục "Khi kết quả là None, rỗng hoặc lỗi") |
| `503 UNAVAILABLE ... high demand`, hoặc gọi quá lâu rồi timeout | Gemini quá tải, tạm thời | Server tự thử lại; nếu vẫn lỗi đợi vài phút rồi gọi lại; một lần gọi có thể mất 1 đến 2 phút |
| Tool `listen_to_audio` không xuất hiện | Session cũ chưa nạp MCP mới | Mở session mới |
| Đã đổi key nhưng vẫn báo key cũ/403 | Tiến trình MCP đang chạy giữ key cũ | Chạy lại `setup_mcp.sh`, mở session mới |
| `GEMINI_API_KEY environment variable is required` | Thiếu biến môi trường trong cấu hình MCP | Chạy lại `setup_mcp.sh` với `--env-file` đúng |
| Transcript dừng giữa chừng | Gemini cắt đầu ra | `ask_about_audio` với "continue from mm:ss.s" |

## Danh sách kiểm tra trước khi báo hoàn thành

- [ ] Đã qua Bước 0 (ủy quyền) nếu là audio thật.
- [ ] Kết quả không phải `None`/rỗng/`Error` (nếu có, đã xử lý theo mục "Khi kết quả là None, rỗng hoặc lỗi").
- [ ] Transcript phủ đến cuối file, không bị cắt.
- [ ] Đã bỏ đuôi `Session ID` khỏi file.
- [ ] Đã rà chính tả/định dạng (Bước 5) và `validate_format.py` ra 0 lỗi.
- [ ] Báo rõ chỗ chưa chắc và rằng chưa kiểm chứng với audio gốc (nếu không có bản chuẩn).
- [ ] Không lộ API key ở bất kỳ đâu; nếu có commit/push thì đã chạy `scan_secrets.sh` và báo `SẠCH`.
