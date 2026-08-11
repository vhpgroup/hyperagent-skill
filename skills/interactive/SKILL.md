---
name: interactive
description: Dùng skill này khi cần tạo sản phẩm trực quan bằng HTML — trang web, báo cáo, dashboard, trang landing, hoặc slide deck/bài trình bày. Bao gồm dựng khung slide có sẵn điều hướng, xem trước bằng server cục bộ, và định hướng thiết kế để chọn phong cách hợp nội dung. KHÔNG dùng cho tài liệu Word/PDF/Excel — dùng skill docx/pdf/xlsx.
---

# Interactive

Thay thế cho nhóm INTERACTIVE của Hyperagent (Webpages, Slides). HyperApps
không có bản tương đương ở local — nó gắn với runtime của platform.

## Điểm cốt lõi phải hiểu trước

Ở Hyperagent, `PublishWebpage` chỉ làm đúng một việc tầm thường: lưu HTML rồi
sinh URL. **Giá trị nằm ở phần định hướng thiết kế, không nằm ở cái tool.**
Nên phần dài nhất của tài liệu này là mục Thiết kế, không phải mục Lệnh.

## Lệnh

```bash
# Dựng khung slide deck đã có sẵn toàn bộ điều hướng
python scripts/new_deck.py noi-dung.md -o deck.html --title "Tiêu đề"
python scripts/new_deck.py slides.json -o deck.html
python scripts/new_deck.py --blank -o deck.html

# Xem trước trong trình duyệt
python scripts/preview.py bao-cao.html --open
python scripts/preview.py ./thu-muc/ --port 8080
```

Trang web thường thì **cứ viết thẳng file HTML** bằng công cụ ghi file, rồi
`preview.py` để xem. Không cần script sinh khung.

`new_deck.py` tồn tại vì phần khó của slide HTML không phải nội dung mà là
điều hướng: phím mũi tên, chấm chỉ vị trí, bộ đếm, vuốt cảm ứng, thoát bằng
Escape. Script lo sẵn phần đó. **Nhưng phần thẩm mỹ nó để trung tính — bạn
phải sửa.** Xem mục dưới.

## Định hướng thiết kế

Trước khi gõ HTML, tự hỏi: **nội dung này giống vật thật nào?** Một báo cáo tài
chính, một lookbook thời trang, một tài liệu kỹ thuật, một bài luận cá nhân —
bốn thứ đó không được phép trông giống nhau.

Không có một phong cách "mặc định an toàn". Nhiều thanh ghi đều hợp lệ như
nhau: tối và kịch tính, màu thương hiệu rực, mono kỹ thuật, ảnh tràn viền, vui
tươi nhiều màu, đơn sắc tối giản, lưới dữ liệu dày đặc. Chọn cái hợp **nội dung
này**, không phải cái quen tay.

### Vài loại nội dung dễ bị chọn sai phong cách

Mấy nhóm dưới đây hay bị kéo về kiểu "nền kem + serif viết tay", và đó thường
là lựa chọn sai:

- **Portfolio thiết kế / studio** → trắng tinh `#ffffff`, lưới module, sans
  trung tính (Inter, Helvetica), không trang trí. Thanh ghi Rams/Apple là
  *chính xác*, không phải *ấm áp*.
- **Tin tức / báo chí** → trắng, serif kiểu nhật báo, dải ngày tháng, lead in
  nghiêng. Không phải layout tạp chí thủ công.
- **Báo cáo thị trường / dashboard** → lưới kiểu terminal Bloomberg trắng-xanh,
  hoặc đỏ-trên-nền-nhạt kiểu Economist. Dữ liệu là nhân vật chính; khung quanh
  nó nên trông như công cụ chuyên nghiệp dùng hằng ngày.
- **Thương hiệu / mỹ phẩm / thời trang** → nền trắng sạch với đúng một màu nhấn
  của chính thương hiệu đó, ảnh sản phẩm tràn viền.

Khi đề bài **có nêu** gợi ý cụ thể (màu, chất liệu, thời kỳ, thương hiệu, địa
danh — "thép và muối biển", "Bauhaus", "xanh navy đậm") thì **theo gợi ý đó**,
đừng đè bằng mặc định của nhóm. Mặc định chỉ dùng khi đề bài im lặng về phong cách.

### Nguyên tắc chung

- **Đầu tư vào typography.** Google Fonts qua `<link>`. Font là thứ quyết định
  cảm giác nhanh nhất.
- **Chừa khoảng thở.** Padding ngang tối thiểu ~5% mỗi bên. Slide thì càng
  rộng rãi càng tốt, chữ ít thôi.
- **Ảnh thật thắng ảnh AI** khi chủ thể là thứ có thật. Nhúng bằng `<img src>`.
- **Tránh sáo rỗng AI-art**: hạt sáng lấp lánh, quả cầu neon, hoạ tiết bo mạch.
- **Đừng bịa dòng bản quyền** hay ghi công cho ai.

## Khác biệt so với Hyperagent

| | Hyperagent | Ở đây |
|---|---|---|
| Lưu trữ | S3, có link chia sẻ | File cục bộ |
| Xem | Artifact nhúng trong chat | `preview.py`, chỉ localhost |
| Chia sẻ | Link công khai | Tự thêm tunnel, hoặc copy file |
| Lịch sử phiên bản | Có | Không, tự dùng git |
| HyperApps | Có | **Không port được** |

Muốn chia sẻ ra ngoài: `cloudflared tunnel --url http://localhost:8000`, hoặc
đẩy file lên GitHub Pages / Netlify.

`preview.py` mặc định chỉ nghe `127.0.0.1`, cố ý — để không hở nội dung nháp
ra mạng LAN. Muốn xem từ máy khác thì `--host 0.0.0.0`, và tự cân nhắc.

## Vì sao HyperApps không port được

HyperApp là widget tương tác **gọi ngược lại được các tool của agent** (search,
tables, spawn agent) ngay trong lúc người dùng bấm. Nó cần một runtime giữ
phiên agent sống và một cầu nối RPC từ iframe về server. Ở local, tương đương
gần nhất là bạn tự viết một web app nhỏ có backend gọi model của bạn — tức là
một dự án riêng, không phải một skill.
