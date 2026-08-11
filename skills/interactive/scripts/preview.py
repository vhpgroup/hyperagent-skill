#!/usr/bin/env python3
"""
Xem trước file HTML bạn vừa tạo, bằng một web server cục bộ.

    python scripts/preview.py bao-cao.html
    python scripts/preview.py ./trang-web/ --port 8080
    python scripts/preview.py deck.html --once      # tắt ngay sau 1 request

Đây là phần thay cho PublishWebpage/PublishSlides của Hyperagent. Khác biệt:
Hyperagent đẩy file lên S3 rồi trả link chia sẻ được; ở local thì chỉ phục vụ
trong máy bạn. Muốn chia sẻ ra ngoài thì tự thêm tunnel (cloudflared, ngrok)
hoặc copy file đi.

Mặc định chỉ nghe trên 127.0.0.1 để không hở ra mạng LAN. Muốn xem từ máy khác
thì thêm --host 0.0.0.0 và tự chịu trách nhiệm.
"""
import argparse
import functools
import http.server
import os
import socket
import socketserver
import sys
import threading
import webbrowser


def free_port(start, host):
    for p in range(start, start + 50):
        with socket.socket() as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    sys.exit("Lỗi: không tìm được cổng trống trong khoảng %d–%d" % (start, start + 50))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *a):
        sys.stderr.write("  %s\n" % (fmt % a))

    def end_headers(self):
        # Không cache, để F5 là thấy bản mới ngay khi đang sửa
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()


def main():
    ap = argparse.ArgumentParser(description="Server xem trước HTML cục bộ.")
    ap.add_argument("path", help="File .html hoặc thư mục")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1",
                    help="Mặc định chỉ localhost. Dùng 0.0.0.0 để mở ra LAN.")
    ap.add_argument("--open", action="store_true", help="Tự mở trình duyệt")
    ap.add_argument("--once", action="store_true", help="Thoát sau request đầu tiên")
    args = ap.parse_args()

    path = os.path.abspath(args.path)
    if not os.path.exists(path):
        sys.exit("Lỗi: không thấy %s" % path)

    if os.path.isdir(path):
        root, page = path, ""
    else:
        root, page = os.path.dirname(path) or ".", os.path.basename(path)

    port = free_port(args.port, args.host)
    handler = functools.partial(QuietHandler, directory=root)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, port), handler) as httpd:
        url = "http://%s:%d/%s" % (
            "localhost" if args.host == "127.0.0.1" else args.host, port, page)
        print("Đang phục vụ %s" % root)
        print("  %s" % url)
        if args.host == "0.0.0.0":
            print("  CẢNH BÁO: đang mở ra toàn mạng, không chỉ máy này.")
        print("  Ctrl+C để dừng.\n")

        if args.open:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()

        try:
            if args.once:
                httpd.handle_request()
            else:
                httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nĐã dừng.")


if __name__ == "__main__":
    main()
