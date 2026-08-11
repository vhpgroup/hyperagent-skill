# Hyperagent Skills — bản dựng lại cho local

Bảy skill dựng lại từ Hyperagent, đóng gói ở dạng **trung lập với harness**: không
phụ thuộc Claude Code, không phụ thuộc Qwen, không phụ thuộc runtime nào của
Hyperagent.

**Nhóm tài liệu** — trích nguyên từ knowledge base:

| Skill  | Làm được gì | Cách hoạt động |
|--------|-------------|----------------|
| `pdf`  | Đọc, trích text/bảng, merge, split, xoay, watermark, mã hoá, điền form, OCR | pypdf + pdfplumber + reportlab |
| `docx` | Tạo, đọc, sửa Word; tracked changes, comments, redlining | Sửa OOXML thô + validate bằng XSD |
| `xlsx` | Tạo, đọc, sửa, làm sạch spreadsheet; công thức, biểu đồ | openpyxl + pandas |
| `pptx` | Tạo, đọc, sửa slide deck; layout, speaker notes | PptxGenJS (tạo mới) + OOXML (sửa) |

**Nhóm tool** — viết mới, thay cho các tool chạy phía server của Hyperagent:

| Skill | Thay cho | Cách hoạt động |
|---|---|---|
| `research` | Search, Find Similar, Exa Answer/Research/Websets | Exa API (mặc định), hoặc DDG / SearXNG |
| `browser` | 12 browser tool (Stagehand) | Playwright cục bộ, không cần key |
| `interactive` | Webpages, Slides | HTML + server xem trước cục bộ |

**Đính chính một khẳng định trước đây trong repo này:** tôi từng viết rằng Exa
Research và Websets "không phải endpoint riêng, chỉ là search + LLM tổng hợp".
Điều đó SAI. Exa có API thật cho cả hai: **Websets** là API async đầy đủ
(create-a-webset, items, searches, enrichments, monitors, webhooks), và deep
research đi qua **Agent API** async (create-a-run, get-a-run, list-run-events).
Chúng chưa được dựng lại ở đây — xem mục "Còn thiếu".

### Còn thiếu so với Hyperagent

| Tool | Trạng thái |
|---|---|
| Exa Websets | Chưa làm. Exa có API async thật, dựng được, cần thêm vòng poll. |
| Exa Research | Chưa làm. Đi qua Agent API async của Exa. |
| Thread Search | Phụ thuộc harness — phải biết transcript lưu ở đâu mới index được. |
| HyperApps | Không dựng lại được: cần runtime giữ phiên agent + cầu RPC từ iframe. |
| Tables, Documents | Chưa làm. Cần một lớp lưu trữ (SQLite + thư mục markdown là đủ). |

### Lưu ý về nguồn gốc nhóm skill tài liệu

Bốn skill tài liệu ở đây trích từ bản ghi của Hyperagent, và bản đó là một
**snapshot cũ** của `github.com/anthropics/skills`. Upstream đã refactor sang
kiến trúc khác: không còn `office/pack.py` và `office/unpack.py`, `helpers/`
chứa thêm `pptx_chart.py`/`pptx_slide.py`/`pptx_theme.py`, và `helpers/__init__.py`
export hằng số dùng chung (bản ở đây là file rỗng — đúng với kiến trúc cũ, vì
các module import trực tiếp `from helpers.merge_runs import ...`).

Hệ quả thực tế: **không thể copy lẻ file từ upstream về đây** — ví dụ
`thumbnail.py` gốc import `office.helpers.SLIDE_REL_TYPE`, thứ không tồn tại
trong kiến trúc cũ. Muốn dùng bản gốc thì phải đồng bộ cả cây, rồi test lại.
Bản trong repo này đã được kiểm là chạy được với chính kiến trúc của nó.

---

## 1. Cấu trúc

```
skills/<tên>/
├── SKILL.md          # Hướng dẫn chính — đây là thứ agent đọc
├── references/       # Tài liệu sâu, chỉ load khi cần
└── scripts/          # Python thực thi được
manifest.json         # Index máy đọc được: mô tả, dependency, script
requirements.txt
```

`SKILL.md` có YAML frontmatter ở đầu. Đó chỉ là **metadata tuỳ chọn** — harness nào
không hiểu thì bỏ qua, đọc phần markdown bên dưới là đủ. Không có gì bắt buộc phải
theo chuẩn Claude Code.

**Điểm cần hiểu về bản chất:** đây **không phải thư viện, mà là hướng dẫn**. Script chỉ
lo phần cơ khí (giải nén, đóng gói, validate). Phần khó — đọc XML thô rồi viết ra đoạn
sửa đúng schema — là model tự làm. Nên chất lượng đầu ra phụ thuộc model nhiều hơn
phụ thuộc code. Xem mục 5.

---

## 2. Cài đặt

### Cách nhanh trên Ubuntu

```bash
bash install.sh      # không cần sudo, tạo .venv riêng
source env.sh
python doctor.py     # kiểm tra bằng cách chạy thật
```

#### Ubuntu 22.04 LTS (jammy) — lưu ý riêng

- **Python: xong sẵn.** 22.04 có Python 3.10.12, vừa đủ ngưỡng 3.10+. Không cần
  deadsnakes, không cần làm gì thêm.
- **PEP 668: không ảnh hưởng.** Việc chặn `pip install` toàn hệ thống chỉ bắt đầu
  từ 23.04. `install.sh` vẫn dùng venv cho sạch, nhưng bạn không gặp lỗi
  `externally-managed-environment` trên 22.04.
- **Node: đây mới là chỗ vấp.** `sudo apt install nodejs` trên jammy cài **v12.22.9**,
  đã hết vòng đời từ tháng 4/2022. Nếu bạn cần đường tạo mới docx/pptx thì nâng lên
  LTS trước:

  ```bash
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt install -y nodejs
  ```

  `install.sh` sẽ tự phát hiện và cảnh báo nếu thấy Node < 18. Nếu bạn không định tạo
  file docx/pptx mới thì bỏ qua Node hoàn toàn cũng được.
- **LibreOffice + poppler:** bạn đã cài rồi. `doctor.py` sẽ xác nhận và chạy luôn nhóm
  test docx/pptx (nhóm này cần LibreOffice để sinh file mẫu).

`install.sh` tự tìm Python >= 3.10, tạo virtualenv trong thư mục bundle, cài thư viện
Python và Node cục bộ. Nó **không cần sudo** và **không động vào Python hệ thống** —
đây là chủ ý, vì Ubuntu từ 23.04 chặn `pip install` toàn hệ thống theo PEP 668, cài
thẳng sẽ báo `externally-managed-environment`.

`doctor.py` không chỉ kiểm tra `import`. Nó tạo file xlsx/pdf/docx/pptx thật, chạy đúng
những script mà `SKILL.md` bảo agent chạy, rồi đọc kết quả ngược lại — nên nó phản ánh
đúng cái agent sẽ gặp. Mục nào `SKIP` đều kèm dòng giải thích bỏ đi thì mất tính năng gì.

Phần dưới là chi tiết thủ công, nếu bạn muốn tự kiểm soát.

### Python 3.10 trở lên — bắt buộc

Không phải khuyến nghị mà là bắt buộc cứng. `office/validate.py` dùng `match/case`,
còn `office/pack.py` và `docx/scripts/comment.py` dùng annotation kiểu `str | None`
(PEP 604). Cả hai đều là **syntax error** trên Python 3.9. Đã kiểm bằng cách compile
toàn bộ 51 script dưới 3.9: `validate.py` fail ở cả docx, xlsx lẫn pptx.

```bash
python3 --version        # phải >= 3.10
pip install -r requirements.txt
```

### Binary hệ thống

Chia làm hai mức. **Chỉ `poppler` là gần như bắt buộc**, phần còn lại là tuỳ chọn và
README này ghi rõ bỏ đi thì mất gì.

| Binary | Mức | Bỏ đi thì mất gì |
|--------|-----|------------------|
| **poppler** | Nên có | `pdf2image` không chạy → mất render PDF ra ảnh, kéo theo mất luôn phần điền form không-fillable. Rất nhẹ, vài MB. |
| **Node.js + npm** | Nên có nếu dùng docx/pptx | Mất đường tạo docx/pptx **mới từ đầu**. Vẫn đọc/sửa file có sẵn bình thường. |
| **LibreOffice** | Tuỳ chọn | Mất 3 thứ: recalc công thức Excel (`xlsx/scripts/recalc.py`), convert Office → PDF, convert `.doc` cũ → `.docx`. Nặng ~600 MB–1 GB. Nếu bạn không đụng file Excel có công thức thì bỏ qua được. |
| **ImageMagick** | Tuỳ chọn | `pdf/references/forms.md` dùng `magick ... -crop` để phóng to vùng ảnh khi tinh chỉnh toạ độ ô điền form. Không có thì bước zoom refinement phải làm cách khác. |
| **pandoc** | Tuỳ chọn | Mất đường trích docx → markdown kèm tracked changes. |
| **tesseract** | Tuỳ chọn | Mất OCR PDF scan. |

```bash
# macOS
brew install poppler node
brew install --cask libreoffice              # tuỳ chọn
brew install pandoc tesseract imagemagick    # tuỳ chọn

# Ubuntu / Debian
sudo apt install poppler-utils nodejs npm
sudo apt install libreoffice                        # tuỳ chọn
sudo apt install pandoc tesseract-ocr imagemagick   # tuỳ chọn

# Windows
winget install oschwartz10612.Poppler OpenJS.NodeJS
winget install TheDocumentFoundation.LibreOffice   # tuỳ chọn
```

### Node (chỉ khi cần tạo docx/pptx mới)

```bash
npm install -g docx pptxgenjs
```

---

## 3. Cắm vào harness

Bundle không giả định harness nào. Ba cách phổ biến:

**a) Đọc trực tiếp (đơn giản nhất, hợp với endpoint OpenAI-compatible).**
Nạp `manifest.json` vào system prompt để model biết có những skill nào. Khi request
khớp mô tả một skill, đọc `skills/<tên>/SKILL.md` rồi nối vào context. Model làm phần
còn lại bằng tool chạy shell. Đây là cách rẻ nhất và không cần hạ tầng gì.

**b) Claude Code.** Copy `skills/*` vào `~/.claude/skills/`. Frontmatter đã đúng chuẩn,
chạy được ngay.

**c) MCP server.** Bọc script thành tool nếu harness của bạn nói MCP (Qwen Code, Cline,
OpenHands). Hơi thừa cho trường hợp này vì phần lớn giá trị nằm ở markdown chứ không
nằm ở script — cách (a) thường đủ.

**Lưu ý về đường dẫn:** `SKILL.md` viết lệnh dạng `python scripts/foo.py`, ngầm định
cwd là thư mục skill. Harness của bạn cần `cd` vào đó, hoặc bạn sửa lại thành đường
dẫn tuyệt đối.

---

## 4. Đã loại khỏi bundle

- Toàn bộ skill media (`hyperframes`, `hyperframes-cli`, `hyperframes-registry`, `gsap`,
  `website-to-hyperframes`, `remotion-to-hyperframes`, `video-prompting`,
  `video-continuation-patterns`, `advanced-image-techniques`) — theo yêu cầu.
- `connection-setup-wizard` — chạy trên HyperApp runtime, không tồn tại ngoài Hyperagent.
- `context-builder` — không có script nào, chỉ là quy trình gọi integration và
  `CreateMemory` của platform. Copy về thì file vẫn còn nhưng vô dụng.

---

## 5. Yêu cầu về model — đọc trước khi đổi sang model nhỏ

Đây là phần dễ vấp nhất khi rời khỏi model lớn.

**Cần vision:** phần điền PDF form không có fillable field (`pdf/references/forms.md`)
bắt buộc phải nhìn được ảnh. Quy trình là render trang ra PNG → xác định vị trí ô →
crop zoom để tinh chỉnh toạ độ. Model text-only không làm được đường này. Các thao tác
PDF còn lại thì không cần vision.

**Cần reasoning mạnh:** `docx` và `pptx` sửa XML thô. Model yếu sẽ sinh XML sai schema.
Có 39 file XSD validate nên nó sẽ *báo lỗi* thay vì tạo file hỏng — nhưng vòng lặp sửa
lỗi có thể không hội tụ. Nếu model của bạn không đủ mạnh, cân nhắc thay bằng
`python-docx` / `python-pptx` cho tác vụ thường ngày, đổi lại mất tracked-changes và
redlining.

**Cần context rộng:** `SKILL.md` của docx là 20 KB, `pdf/references/reference.md` còn
dài hơn. Cộng thêm XML đang sửa thì đừng chạy ở cửa sổ 8k–32k.

**Dễ nhất:** `xlsx` (qua openpyxl) và phần đọc/merge/split của `pdf` — model tầm trung
làm ổn.

---

## 6. Ghi chú về nguồn

- Script là **100% Python** (43 file gốc), cộng 113 file XSD schema và 3 XML template.
  Không có JS nào trong scripts — nhưng tài liệu của `docx`/`pptx` *có* hướng dẫn dùng
  thư viện Node (`docx`, `pptxgenjs`) cho đường tạo file mới.
- Thư viện dùng chung `office/` giống hệt nhau từng byte giữa docx và xlsx.
- **`pptx` đã được vá:** lúc trích, `pptx/scripts/office/` thiếu `unpack.py`,
  `soffice.py`, `validate.py`, thư mục `validators/` và 4 file XSD — dù `SKILL.md` của
  nó có gọi `unpack.py`. Các file thiếu đã được copy từ `docx` (đã đối chiếu hash, giống
  hệt). Nếu `pptx` chạy lỗi ở bước unpack/validate thì đây là chỗ đầu tiên nên nghi.
- **`pptx/scripts/thumbnail.py` là bản dựng lại, không phải bản gốc.** Bản ghi skill
  trên Hyperagent thiếu file này, dù `SKILL.md` và `references/editing.md` đều gọi
  `python scripts/thumbnail.py` ở **bước 1 của quy trình sửa pptx**. Đã fetch lại hai
  lần với `force` để xác nhận không phải lỗi tải: nguồn chỉ có 42 file và không có nó.
  Bản dựng lại làm đúng như tài liệu mô tả — render slide thành lưới ảnh `thumbnails.jpg`
  có đánh số — bằng LibreOffice (pptx → pdf) + poppler + Pillow. Nó cũng nhận thẳng
  `.pdf` nếu bạn đã tự chuyển. Vì là bản viết lại, hành vi có thể khác bản gốc của
  Anthropic ở chi tiết.
- `scripts/office/` **cố tình không phải Python package** (không có `__init__.py`).
  Các file trong đó import kiểu `from helpers.merge_runs import ...`, nên chỉ chạy đúng
  khi gọi trực tiếp `python scripts/office/unpack.py`. Đừng cố `import office.unpack` —
  sẽ lỗi `No module named 'helpers'`. `SKILL.md` đã hướng dẫn đúng cách gọi.
- Script của `pdf` **không có cờ `--help`**, chúng nhận positional argument. Gõ
  `--help` sẽ ra `FileNotFoundError` vì nó hiểu đó là tên file.

### Đã test tới đâu

Chạy thật trên Python 3.11.15, kết quả `doctor.py`: **31 đạt, 0 hỏng, 1 cảnh báo,
6 bỏ qua**. Cả bốn skill đều đã được chạy end-to-end.

Đã xác minh bằng cách chạy:

- **xlsx** — tạo file bằng openpyxl → `unpack.py` (9 XML) → `pack.py` → đọc lại bằng
  openpyxl, dữ liệu còn nguyên.
- **docx** — dựng OOXML tối thiểu → `unpack.py` → `validate.py` chạy qua bộ 39 XSD,
  báo `All validations PASSED!` → `pack.py` → validate lại → zip toàn vẹn, nội dung
  không mất.
- **pdf** — reportlab tạo file → pypdf đọc → pdfplumber trích text → 
  `check_fillable_fields.py`, `extract_form_structure.py`, `convert_pdf_to_images.py`
  (render qua poppler) đều chạy đúng.
- **pptx** — `pptxgenjs` sinh deck 2 slide → `unpack.py` (20 XML) → `pack.py` → roundtrip
  giữ nguyên nội dung slide. `validate.py` báo một lỗi schema, xem mục dưới.
- **Đường tạo mới bằng Node** — thư viện `docx` sinh file rồi cho qua `validate.py`:
  `All validations PASSED!`.
- Compile toàn bộ 51 script dưới Python 3.9 → đó là cách phát hiện ràng buộc 3.10+.
- Đối chiếu hash thư viện `office/` giữa các skill; kiểm dangling reference trong
  `SKILL.md`.

- **research với Exa key thật** — cả 4 endpoint đã chạy: `/search`, `/answer`
  (trả lời kèm 6 nguồn), `/findSimilar`, `/contents`. Tổng chi phí test ~$0.016.
- **research fallback** — `fetch.py` bóc bằng trafilatura, `search.py --backend ddg`.
- **browser** — Chromium thật: mở trang, click, chuyển trang, cuộn, chụp ảnh;
  `observe` trả selector dùng được; profile giữ cookie qua các lần chạy.
- **interactive** — sinh deck từ markdown, kiểm đủ hợp đồng điều hướng.

**Vẫn chưa test:** `recalc.py`, export PDF, đọc `.doc` (đều cần LibreOffice), pandoc,
tesseract, đường điền PDF form cần vision, và Exa Websets / Agent API (chưa viết).

### Lỗi schema của pptxgenjs — biết trước để đỡ mất công

Nếu bạn tạo deck bằng `pptxgenjs` rồi chạy `validate.py`, nó sẽ báo:

```
ppt/presentation.xml: Element 'notesMasterIdLst': This element is not expected.
```

**Đây là lỗi thượng nguồn của pptxgenjs, không phải của skill.** `pml.xsd` yêu cầu thứ tự
`sldMasterIdLst → notesMasterIdLst → sldIdLst → sldSz`, còn pptxgenjs xuất
`notesMasterIdLst` sau `sldIdLst`. Đã kiểm chứng: lỗi có sẵn trong file gốc pptxgenjs
vừa sinh ra, và pipeline unpack/pack giữ nguyên thứ tự đó chứ không tạo thêm lỗi.
PowerPoint vẫn mở file bình thường.

Điều này quan trọng với agent: chạy `validate.py` trần trên file pptxgenjs sẽ ra `FAILED`
và agent có thể sa vào vòng lặp "sửa lỗi" một thứ nó không gây ra. Cách tránh là luôn
truyền `--original`:

```bash
python scripts/office/pack.py unpacked/ out.pptx --original input.pptx
```

Khi có `--original`, validator chỉ báo lỗi **mới phát sinh** so với file gốc, nên lỗi
sẵn có được bỏ qua. Đã kiểm: `validate.py` trần thoát mã 1, còn `pack.py --original`
thoát mã 0 trên cùng file đó.

### Một điểm về `validate.py`

`office/validate.py` **cố ý chỉ hỗ trợ `.docx` và `.pptx`**. Đưa file `.xlsx` vào nó sẽ
in `Validation not supported for file type .xlsx` và thoát mã 1. Đó là hành vi đúng,
không phải lỗi — spreadsheet không có validator trong bộ này.
