---
name: browser
description: Dùng skill này khi cần một trình duyệt thật — trang render bằng JavaScript, trang cần đăng nhập, điền form, bấm nút, cuộn để tải thêm, chụp màn hình, hoặc khi fetch thường trả về rỗng/403. Bao gồm điều hướng, tìm selector, thao tác nhiều bước trong cùng phiên, và giữ đăng nhập giữa các lần chạy. KHÔNG dùng cho trang tĩnh đơn giản — skill research nhanh và rẻ hơn nhiều.
---

# Browser

Thay thế cho nhóm BROWSER của Hyperagent (12 tool Stagehand) bằng Playwright
chạy cục bộ. Không cần API key, không gọi ra dịch vụ nào.

## Cài

```bash
pip install playwright
python -m playwright install chromium
sudo python -m playwright install-deps chromium     # Ubuntu, cần sudo
```

Bỏ bước `install-deps` thì Chromium thường báo thiếu `libnss3`/`libasound2`.

## Khác biệt cốt lõi so với Stagehand

Stagehand nhận lệnh bằng ngôn ngữ tự nhiên ("bấm nút Đăng nhập") vì có một LLM
ở giữa dịch sang selector. Ở đây không có lớp đó. Quy trình đúng là:

```
observe  →  đọc selector  →  click/fill
```

Tốn thêm một vòng, nhưng đổi lại kết quả tất định và không tốn token cho lớp
dịch. **Đừng đoán selector** — chạy `observe` trước, nó in ra selector dùng
được ngay.

## Lệnh

```bash
# Đọc nội dung (kể cả trang JS)
python scripts/browse.py get https://vidu.com
python scripts/browse.py get URL --wait "div.ket-qua"     # chờ phần tử xuất hiện
python scripts/browse.py get URL --html                   # lấy HTML thay vì text

# Xem có gì bấm được, kèm selector
python scripts/browse.py observe https://vidu.com
python scripts/browse.py observe URL --json

# Chụp màn hình
python scripts/browse.py shot URL -o anh.png --full

# Nhiều bước trong CÙNG một phiên
python scripts/browse.py steps kichban.json
```

### File kịch bản

Mảng JSON, chạy tuần tự trong một phiên trình duyệt:

```json
[
  {"goto": "https://vidu.com/dang-nhap"},
  {"fill": ["input#email", "toi@vidu.com"]},
  {"fill": ["input#password", "..."]},
  {"click": "button[type=submit]"},
  {"wait": "div.bang-dieu-khien"},
  {"scroll": "bottom"},
  {"eval": "Array.from(document.querySelectorAll('.item')).map(e=>e.innerText)"},
  {"screenshot": "ket-qua.png"},
  {"text": true}
]
```

Khoá hợp lệ: `goto`, `click`, `fill` (cặp [selector, giá trị]), `press`,
`wait` (selector hoặc số mili giây), `scroll` (`top`/`bottom`/số px), `text`,
`html`, `screenshot`, `eval` (JS, trả kết quả về), `sleep`.

Bước nào hỏng thì script dừng, in **số thứ tự bước, loại lỗi, và nội dung bước
đó**. Đọc thông báo rồi sửa đúng bước ấy, đừng chạy lại cả kịch bản mù.

## Giữ đăng nhập

Mỗi lần gọi script là một tiến trình mới, nhưng cookie vẫn còn nhờ thư mục
user-data cố định (mặc định `~/.cache/agent-browser`, đổi bằng `BROWSER_PROFILE`).

Đăng nhập một lần bằng cửa sổ thật:

```bash
python scripts/browse.py get https://site.com/login --headed --keep-open 120
```

Tự tay đăng nhập trong 120 giây đó. Các lần sau chạy headless vẫn còn phiên.
Đây là cách xử lý 2FA và captcha — **đừng cố tự động hoá hai thứ này.**

Cần nhiều tài khoản thì tách profile:

```bash
BROWSER_PROFILE=~/.cache/browser-taikhoan2 python scripts/browse.py get URL
```

## Khi nào KHÔNG dùng skill này

Trang tĩnh thì `research/scripts/fetch.py` nhanh hơn nhiều lần và không tốn
RAM. Chỉ chuyển sang browser khi fetch đã thất bại — rỗng, thiếu nội dung,
hoặc 403.

## Lưu ý thực tế

- **Đọc bảng/danh sách dài**: dùng `eval` với `querySelectorAll` để lấy đúng
  mảng dữ liệu, thay vì `text` rồi tự parse cả trang. Sạch hơn và tốn ít token hơn.
- **Nội dung tải khi cuộn**: lặp `{"scroll":"bottom"}` + `{"sleep":1500}` vài
  lần trước khi đọc.
- **Chờ đúng cách**: ưu tiên `{"wait": "selector"}` hơn `{"sleep": n}`. Sleep
  cố định vừa chậm vừa hay hỏng khi mạng lag.
- **Tôn trọng site**: đừng bắn hàng loạt request. Có `robots.txt` và điều khoản
  sử dụng thì tuân thủ.
- **Chạy trên server không màn hình**: `--headed` cần X server. Không có thì
  dùng `xvfb-run python scripts/browse.py ... --headed`.
