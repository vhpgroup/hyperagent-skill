---
name: research
description: Dùng skill này khi cần tìm thông tin trên web — tra cứu sự kiện, nghiên cứu chủ đề, thu thập nguồn, tìm bài viết/công ty/paper tương tự, hoặc trả lời câu hỏi cần dẫn nguồn. Bao gồm tìm kiếm ngữ nghĩa, lấy nội dung sạch từ URL, và các quy trình nghiên cứu nhiều bước. KHÔNG dùng cho trang cần đăng nhập hoặc render bằng JavaScript — chuyển sang skill browser.
---

# Research

Thay thế cho nhóm RESEARCH của Hyperagent (Search, Find Similar, Exa Answer,
Exa Research, Exa Websets).

## Điểm cốt lõi phải hiểu trước

Sáu tool đó chỉ dựa trên **hai primitive**: *tìm kiếm* và *lấy nội dung*.
Exa Research và Exa Websets không phải endpoint riêng — chúng là vòng lặp
search + đọc + tổng hợp, do một LLM điều phối. **Bạn chính là LLM đó.** Nên
đừng đi tìm script `research.py`; hãy chạy các bước ở mục "Quy trình" bên dưới.

## Cấu hình

```bash
export EXA_API_KEY=...            # backend mặc định
export RESEARCH_BACKEND=exa       # exa | ddg | searxng
```

| Backend | Key | Khi nào dùng |
|---|---|---|
| `exa` | có | Mặc định. Tìm theo ngữ nghĩa, chất lượng tốt nhất cho agent. Tính phí/request. |
| `ddg` | không | Hết quota, hoặc test nhanh. Scrape HTML nên dễ bị rate-limit. |
| `searxng` | không | Tự host, riêng tư. Cần `SEARXNG_URL`. Tốt cho nội dung tiếng Việt vì proxy qua Google. |

## Lệnh

```bash
# Tìm kiếm
python scripts/search.py "câu truy vấn"
python scripts/search.py "query" -n 10 --json
python scripts/search.py "query" --category research_paper      # chỉ Exa
python scripts/search.py "query" --domains arxiv.org            # chỉ Exa
python scripts/search.py "query" --backend ddg                  # ép backend

# Lấy nội dung sạch từ URL (dùng trafilatura, không tốn credit Exa)
python scripts/fetch.py https://vidu.com/bai-viet
python scripts/fetch.py url1 url2 --max-chars 4000 --format json

# Trả lời có trích dẫn (Exa Answer)
python scripts/exa_tools.py answer "câu hỏi cụ thể"
python scripts/exa_tools.py answer "câu hỏi" --schema schema.json

# Tìm trang tương tự (Find Similar)
python scripts/exa_tools.py similar https://vidu.com/bai-viet -n 10

# Lấy nội dung qua cache Exa (sạch hơn fetch.py, nhưng tốn credit)
python scripts/exa_tools.py contents URL --text
```

**`fetch.py` hay `exa_tools.py contents`?** Mặc định dùng `fetch.py` — miễn phí
và đủ tốt cho phần lớn trang. Chuyển sang `contents` khi `fetch.py` trả về rỗng
hoặc lẫn rác, hoặc khi cần `--livecrawl always` để chắc chắn nội dung tươi.

## Quy trình

### Tra cứu nhanh một sự kiện
Dùng `exa_tools.py answer`. Nó tự tìm và tổng hợp kèm nguồn, một lệnh là xong.
Đừng tự search rồi đọc thủ công cho những câu hỏi có đáp án dứt khoát.

### Nghiên cứu sâu một chủ đề (thay Exa Research)
1. `search.py` với 2–4 truy vấn diễn đạt khác nhau. Đừng chỉ một truy vấn —
   tìm ngữ nghĩa nhạy với cách diễn đạt, hỏi khác nhau sẽ ra tập nguồn khác nhau.
2. Đọc snippet, chọn 5–8 URL đáng đọc kỹ.
3. `fetch.py url1 url2 …` một lần cho tất cả.
4. Tổng hợp. **Mỗi khẳng định phải gắn với một URL cụ thể.** Chỗ nào các nguồn
   mâu thuẫn thì nói rõ là mâu thuẫn, đừng chọn bừa một bên.
5. Chỗ nào không tìm được thì nói thẳng là không tìm được. Khoảng trống được
   nêu ra có giá trị hơn khoảng trống bị lấp bằng phỏng đoán.

### Dựng bảng dữ liệu có cấu trúc (thay Exa Websets)
1. `search.py --json -n 25` để có tập ứng viên rộng.
2. Lọc theo tiêu chí, giữ những cái đạt.
3. `fetch.py` từng cái để trích các trường cần.
4. Xuất CSV/JSON. **Ô nào không xác minh được thì để trống**, đừng suy đoán —
   một bảng có ô trống thì dùng được, một bảng có số bịa thì độc hại.

### Tìm thứ tương tự
`exa_tools.py similar <url>`. Hợp để phân tích đối thủ, tìm paper liên quan,
tìm nguồn cùng chủ đề. Chỉ Exa làm được; DDG và SearXNG không có khái niệm này.

## Giới hạn — biết trước để khỏi mất công

- **Trang render bằng JavaScript** → `fetch.py` trả về rỗng hoặc thiếu. Đừng
  retry, chuyển thẳng sang skill `browser`.
- **Trang cần đăng nhập** → skill `browser` với `--headed` để đăng nhập một lần.
- **Bị chặn 403** → nhiều site chặn client không phải trình duyệt. Dùng `browser`.
- **PDF** → `fetch.py` xử lý được nếu có `pdfplumber`. Cần trích bảng thì dùng
  skill `pdf`.
- **`ddg` trả 0 kết quả** → gần như chắc chắn là bị rate-limit, không phải
  không có kết quả. Chờ chút hoặc đổi backend.

## Dựng SearXNG nếu muốn tự host

```bash
docker run -d --name searxng -p 8080:8080 \
  -v "${PWD}/searxng:/etc/searxng" searxng/searxng
# Sửa /etc/searxng/settings.yml, thêm json vào search.formats
# (mặc định chỉ có html, không sửa thì script trả 0 kết quả)
export RESEARCH_BACKEND=searxng SEARXNG_URL=http://localhost:8080
```
