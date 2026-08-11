---
name: hsmt-engine
description: "Gửi hồ sơ HSMT vào engine bền vững, theo dõi tiến độ, duyệt kết quả và tải báo cáo Excel. Dùng skill này trong OpenClaw khi người dùng muốn chạy toàn bộ HSMT Product Matcher thay vì gọi từng script rời."
---

# HSMT Engine Client

Engine chạy mặc định tại `http://127.0.0.1:8787`. Biến môi trường bắt buộc:

- `HSMT_ENGINE_URL`
- `HSMT_API_TOKEN`

## Quy trình

1. Gửi một hoặc nhiều DOCX/PDF:

```bash
python "{baseDir}/scripts/client.py" submit file.docx --project "Tên gói thầu"
```

2. Theo dõi job tới `awaiting_review`:

```bash
python "{baseDir}/scripts/client.py" status JOB_ID
python "{baseDir}/scripts/client.py" download JOB_ID results ./results.json
```

3. Đọc `results.json`. Chỉ duyệt khi các dòng `Đạt` có URL và bằng chứng phù hợp:

```bash
python "{baseDir}/scripts/client.py" approve JOB_ID --note "Đã kiểm tra"
```

4. Chờ `completed`, sau đó tải Excel:

```bash
python "{baseDir}/scripts/client.py" download JOB_ID excel ./HSMT_KetQua_PhanTich.xlsx
```

Không tự duyệt nếu còn lỗi ký hiệu `>=/<=` trong PDF, thiếu model chính xác, hoặc nguồn chỉ là trang bán hàng không có datasheet.
