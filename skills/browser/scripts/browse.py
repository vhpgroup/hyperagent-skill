#!/usr/bin/env python3
"""
Điều khiển trình duyệt thật bằng Playwright. Thay thế nhóm Browser tools của
Hyperagent (vốn chạy trên Stagehand).

    # Lấy nội dung một trang (kể cả trang render bằng JavaScript)
    python scripts/browse.py get https://example.com
    python scripts/browse.py get URL --html --wait "div.results"

    # Xem có những phần tử tương tác nào, kèm selector để dùng ở bước sau
    python scripts/browse.py observe https://example.com

    # Chụp màn hình
    python scripts/browse.py shot https://example.com -o trang.png --full

    # Chuỗi thao tác nhiều bước trong CÙNG một phiên
    python scripts/browse.py steps kichban.json

GIỮ ĐĂNG NHẬP GIỮA CÁC LẦN CHẠY
Mỗi lần gọi script là một tiến trình mới, nhưng cookie/session vẫn còn nhờ
`--profile` trỏ tới một thư mục user-data cố định (mặc định ~/.cache/agent-browser).
Đăng nhập một lần bằng `--headed`, các lần sau chạy headless vẫn còn phiên:

    python scripts/browse.py get https://site.com/login --headed --keep-open 120

KHÁC BIỆT SO VỚI STAGEHAND
Stagehand nhận lệnh bằng ngôn ngữ tự nhiên ("bấm nút Đăng nhập") vì có LLM ở
giữa dịch sang selector. Ở đây không có lớp đó, nên quy trình là:
`observe` để xem selector → rồi mới `click`/`fill`. Tốn thêm một vòng nhưng
không tốn token cho lớp dịch, và kết quả tất định hơn.

FILE KỊCH BẢN cho `steps` là một mảng JSON, chạy tuần tự:
[
  {"goto": "https://example.com"},
  {"fill": ["input[name=q]", "từ khoá"]},
  {"click": "button[type=submit]"},
  {"wait": "div.result"},
  {"scroll": "bottom"},
  {"text": true},
  {"screenshot": "ket-qua.png"}
]
Khoá hợp lệ: goto, click, fill, press, wait (selector hoặc số mili giây),
scroll (top/bottom/số px), text, html, screenshot, eval, sleep.
"""
import argparse
import json
import os
import sys

DEFAULT_PROFILE = os.path.expanduser("~/.cache/agent-browser")
NAV_TIMEOUT = 45000


def need_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        sys.exit(
            "Lỗi: thiếu Playwright.\n"
            "  pip install playwright\n"
            "  python -m playwright install chromium\n"
            "  python -m playwright install-deps chromium   # cần sudo trên Ubuntu"
        )


class Browser:
    def __init__(self, profile, headed, width, height):
        self.profile = profile
        self.headed = headed
        self.width, self.height = width, height
        self._pw = None
        self.ctx = None
        self.page = None

    def __enter__(self):
        sync_playwright = need_playwright()
        self._pw = sync_playwright().start()
        os.makedirs(self.profile, exist_ok=True)
        try:
            self.ctx = self._pw.chromium.launch_persistent_context(
                self.profile,
                headless=not self.headed,
                viewport={"width": self.width, "height": self.height},
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception as e:
            self._pw.stop()
            msg = str(e)
            hint = ""
            if "executable doesn't exist" in msg.lower():
                hint = "\nChạy: python -m playwright install chromium"
            elif "host system is missing" in msg.lower() or "libnss" in msg.lower():
                hint = ("\nThiếu thư viện hệ thống. Trên Ubuntu:\n"
                        "  sudo python -m playwright install-deps chromium\n"
                        "  (hoặc: sudo apt install libnss3 libnspr4 libasound2)")
            sys.exit("Lỗi: không khởi động được Chromium.\n" + msg[:400] + hint)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.set_default_timeout(NAV_TIMEOUT)
        return self

    def __exit__(self, *exc):
        try:
            if self.ctx:
                self.ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    def goto(self, url):
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url
        self.page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)

    def text(self):
        return self.page.inner_text("body")

    def observe(self, limit=40):
        """Liệt kê phần tử tương tác kèm selector dùng được ngay."""
        js = """
        () => {
          const sel = 'a[href], button, input, textarea, select, [role=button], [onclick]';
          const out = [];
          for (const el of document.querySelectorAll(sel)) {
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            const st = getComputedStyle(el);
            if (st.visibility === 'hidden' || st.display === 'none') continue;
            let s = el.tagName.toLowerCase();
            if (el.id) s += '#' + CSS.escape(el.id);
            else if (el.name) s += '[name="' + el.name + '"]';
            else if (el.getAttribute('aria-label'))
              s += '[aria-label="' + el.getAttribute('aria-label') + '"]';
            else if (el.className && typeof el.className === 'string') {
              const c = el.className.trim().split(/\\s+/).slice(0, 2)
                        .map(x => '.' + CSS.escape(x)).join('');
              if (c) s += c;
            }
            out.push({
              tag: el.tagName.toLowerCase(),
              type: el.getAttribute('type') || '',
              text: (el.innerText || el.value || el.placeholder || '').trim().slice(0, 70),
              href: el.getAttribute('href') || '',
              selector: s
            });
          }
          return out;
        }
        """
        return self.page.evaluate(js)[:limit]


def run_step(b, step, results):
    if "goto" in step:
        b.goto(step["goto"])
    if "sleep" in step:
        b.page.wait_for_timeout(int(step["sleep"]))
    if "wait" in step:
        w = step["wait"]
        if isinstance(w, (int, float)):
            b.page.wait_for_timeout(int(w))
        else:
            b.page.wait_for_selector(w)
    if "fill" in step:
        sel, val = step["fill"]
        b.page.fill(sel, val)
    if "click" in step:
        b.page.click(step["click"])
    if "press" in step:
        b.page.keyboard.press(step["press"])
    if "scroll" in step:
        s = step["scroll"]
        if s == "bottom":
            b.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif s == "top":
            b.page.evaluate("window.scrollTo(0, 0)")
        else:
            b.page.evaluate("window.scrollBy(0, %d)" % int(s))
    if "eval" in step:
        results.append({"eval": b.page.evaluate(step["eval"])})
    if step.get("text"):
        results.append({"url": b.page.url, "title": b.page.title(), "text": b.text()})
    if step.get("html"):
        results.append({"url": b.page.url, "html": b.page.content()})
    if "screenshot" in step:
        b.page.screenshot(path=step["screenshot"], full_page=step.get("full", False))
        results.append({"screenshot": step["screenshot"]})


def main():
    ap = argparse.ArgumentParser(description="Điều khiển trình duyệt bằng Playwright.")
    ap.add_argument("--profile", default=os.environ.get("BROWSER_PROFILE", DEFAULT_PROFILE),
                    help="Thư mục user-data để giữ cookie/đăng nhập")
    ap.add_argument("--headed", action="store_true", help="Hiện cửa sổ (để đăng nhập tay)")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--keep-open", type=int, default=0,
                    help="Giữ cửa sổ mở N giây trước khi đóng (dùng khi --headed)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("get", help="Mở trang, in nội dung")
    g.add_argument("url")
    g.add_argument("--html", action="store_true", help="In HTML thay vì text")
    g.add_argument("--wait", help="Chờ selector này xuất hiện trước khi đọc")
    g.add_argument("--max-chars", type=int, default=10000)

    o = sub.add_parser("observe", help="Liệt kê phần tử tương tác + selector")
    o.add_argument("url")
    o.add_argument("--limit", type=int, default=40)
    o.add_argument("--json", action="store_true")

    s = sub.add_parser("shot", help="Chụp màn hình")
    s.add_argument("url")
    s.add_argument("-o", "--output", default="screenshot.png")
    s.add_argument("--full", action="store_true", help="Chụp cả trang")
    s.add_argument("--wait")

    st = sub.add_parser("steps", help="Chạy kịch bản JSON nhiều bước")
    st.add_argument("file")
    st.add_argument("--json", action="store_true")

    args = ap.parse_args()

    with Browser(args.profile, args.headed, args.width, args.height) as b:
        if args.cmd == "get":
            b.goto(args.url)
            if args.wait:
                b.page.wait_for_selector(args.wait)
            print("URL:   %s" % b.page.url)
            print("Tiêu đề: %s" % b.page.title())
            print()
            body = b.page.content() if args.html else b.text()
            if args.max_chars and len(body) > args.max_chars:
                print(body[:args.max_chars])
                print("\n… (đã cắt, tổng %d ký tự)" % len(body))
            else:
                print(body)

        elif args.cmd == "observe":
            b.goto(args.url)
            items = b.observe(args.limit)
            if args.json:
                print(json.dumps(items, ensure_ascii=False, indent=2))
            else:
                print("%d phần tử tương tác trên %s\n" % (len(items), b.page.url))
                for it in items:
                    label = it["text"] or it["href"][:50] or "(không nhãn)"
                    print("  %-9s %-45s %s" %
                          (it["tag"] + (":" + it["type"] if it["type"] else ""),
                           it["selector"][:45], label))

        elif args.cmd == "shot":
            b.goto(args.url)
            if args.wait:
                b.page.wait_for_selector(args.wait)
            b.page.screenshot(path=args.output, full_page=args.full)
            print("Đã lưu %s" % args.output)

        elif args.cmd == "steps":
            with open(args.file, encoding="utf-8") as fh:
                steps = json.load(fh)
            results = []
            for i, step in enumerate(steps, 1):
                try:
                    run_step(b, step, results)
                except Exception as e:
                    print("Bước %d thất bại (%s): %s" % (i, type(e).__name__, str(e)[:200]),
                          file=sys.stderr)
                    print("Bước đó là: %s" % json.dumps(step, ensure_ascii=False),
                          file=sys.stderr)
                    sys.exit(1)
            if args.json:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            else:
                for r in results:
                    if "text" in r:
                        print("URL: %s\nTiêu đề: %s\n\n%s" % (r["url"], r["title"], r["text"]))
                    elif "html" in r:
                        print(r["html"])
                    elif "screenshot" in r:
                        print("Đã lưu ảnh: %s" % r["screenshot"])
                    elif "eval" in r:
                        print(json.dumps(r["eval"], ensure_ascii=False))

        if args.keep_open:
            print("Giữ cửa sổ %d giây…" % args.keep_open, file=sys.stderr)
            b.page.wait_for_timeout(args.keep_open * 1000)


if __name__ == "__main__":
    main()
