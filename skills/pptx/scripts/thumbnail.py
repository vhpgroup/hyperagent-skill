#!/usr/bin/env python3
"""
Render một bài thuyết trình thành ảnh contact-sheet để xem nhanh toàn bộ layout.

    python scripts/thumbnail.py presentation.pptx
    python scripts/thumbnail.py deck.pptx --output grid.jpg --cols 4
    python scripts/thumbnail.py already_converted.pdf

Sinh ra `thumbnails.jpg`: lưới các slide, mỗi ô đánh số slide. Dùng ở bước 1
của quy trình sửa pptx — nhìn lưới này để chọn layout phù hợp trước khi
unpack và chỉnh XML.

Yêu cầu:
  - LibreOffice (`soffice`) để chuyển .pptx sang PDF. Không cần nếu đầu vào
    đã là .pdf.
  - poppler (`pdftoppm`), qua thư viện pdf2image, để render PDF ra ảnh.
  - Pillow để ghép lưới.

GHI CHÚ VỀ NGUỒN GỐC: script này KHÔNG có trong bản skill gốc trích từ
Hyperagent — tài liệu có nhắc `scripts/thumbnail.py` nhưng file không tồn tại
trong bản ghi. Đây là bản dựng lại theo đúng mô tả trong `references/editing.md`
("Review `thumbnails.jpg` to see layouts").
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def find_soffice():
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    return None


def pptx_to_pdf(src, outdir):
    """Chuyển .pptx/.ppt sang PDF bằng LibreOffice. Trả về đường dẫn PDF."""
    soffice = find_soffice()
    if not soffice:
        sys.exit(
            "Lỗi: không tìm thấy LibreOffice (soffice), cần nó để chuyển "
            "PowerPoint sang PDF.\n"
            "  Ubuntu: sudo apt install libreoffice-impress\n"
            "  macOS:  brew install --cask libreoffice\n"
            "Hoặc tự chuyển sang PDF trước rồi chạy script với file .pdf."
        )
    proc = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", outdir, src],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300,
    )
    stem = os.path.splitext(os.path.basename(src))[0]
    pdf = os.path.join(outdir, stem + ".pdf")
    if proc.returncode != 0 or not os.path.exists(pdf):
        sys.exit("Lỗi: LibreOffice không chuyển được sang PDF.\n" +
                 proc.stdout.decode("utf-8", "replace")[:500])
    return pdf


def render_pages(pdf, dpi):
    try:
        from pdf2image import convert_from_path
    except ImportError:
        sys.exit("Lỗi: thiếu pdf2image. Cài: pip install pdf2image "
                 "(và poppler-utils ở mức hệ thống).")
    try:
        return convert_from_path(pdf, dpi=dpi)
    except Exception as e:
        sys.exit("Lỗi: render PDF thất bại (%s: %s).\n"
                 "Thường là do thiếu poppler. Ubuntu: sudo apt install poppler-utils"
                 % (type(e).__name__, e))


def build_grid(images, cols, thumb_width, padding, label):
    from PIL import Image, ImageDraw

    if not images:
        sys.exit("Lỗi: không có trang nào để ghép.")

    ratio = images[0].height / images[0].width
    tw = thumb_width
    th = int(tw * ratio)
    label_h = 22 if label else 0

    cols = max(1, min(cols, len(images)))
    rows = (len(images) + cols - 1) // cols

    grid_w = cols * tw + (cols + 1) * padding
    grid_h = rows * (th + label_h) + (rows + 1) * padding

    sheet = Image.new("RGB", (grid_w, grid_h), (240, 240, 240))
    draw = ImageDraw.Draw(sheet)

    for i, img in enumerate(images):
        r, c = divmod(i, cols)
        x = padding + c * (tw + padding)
        y = padding + r * (th + label_h + padding)
        sheet.paste(img.resize((tw, th), Image.LANCZOS), (x, y))
        # viền cho dễ phân biệt slide nền trắng
        draw.rectangle([x, y, x + tw - 1, y + th - 1], outline=(170, 170, 170))
        if label:
            draw.text((x + 4, y + th + 4), "Slide %d" % (i + 1), fill=(40, 40, 40))

    return sheet


def main():
    ap = argparse.ArgumentParser(
        description="Ghép các slide thành một ảnh lưới để xem nhanh layout.")
    ap.add_argument("input", help="File .pptx, .ppt hoặc .pdf")
    ap.add_argument("-o", "--output", default="thumbnails.jpg",
                    help="Ảnh đầu ra (mặc định: thumbnails.jpg)")
    ap.add_argument("--cols", type=int, default=3, help="Số cột (mặc định: 3)")
    ap.add_argument("--width", type=int, default=480,
                    help="Bề rộng mỗi thumbnail, pixel (mặc định: 480)")
    ap.add_argument("--dpi", type=int, default=80, help="DPI khi render (mặc định: 80)")
    ap.add_argument("--padding", type=int, default=12, help="Khoảng cách, pixel")
    ap.add_argument("--no-labels", action="store_true", help="Không ghi số slide")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        sys.exit("Lỗi: không thấy file %s" % args.input)

    ext = os.path.splitext(args.input)[1].lower()
    tmp = tempfile.mkdtemp(prefix="pptx_thumb_")
    try:
        pdf = args.input if ext == ".pdf" else pptx_to_pdf(args.input, tmp)
        pages = render_pages(pdf, args.dpi)
        sheet = build_grid(pages, args.cols, args.width, args.padding,
                           not args.no_labels)
        sheet.save(args.output, "JPEG", quality=85)
        print("Đã ghi %s (%d slide, lưới %d cột, %dx%d px)" %
              (args.output, len(pages), min(args.cols, len(pages)),
               sheet.width, sheet.height))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
