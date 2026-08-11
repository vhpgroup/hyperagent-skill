#!/usr/bin/env python3
"""
Tải một hoặc nhiều URL rồi bóc lấy phần nội dung chính, bỏ menu/quảng cáo/footer.

    python scripts/fetch.py https://example.com/bai-viet
    python scripts/fetch.py url1 url2 url3 --max-chars 4000
    python scripts/fetch.py https://example.com --format json
    python scripts/fetch.py https://example.com --raw          # HTML thô

Đây là bản thay thế cho ExaContents. Thứ tự ưu tiên bộ bóc tách:
  1. trafilatura  — tốt nhất cho bài báo/blog, giữ được cấu trúc
  2. readability  — thuật toán của Mozilla, ổn định
  3. regex thô    — chỉ gỡ thẻ, dùng khi không cài gì

Trang render bằng JavaScript sẽ ra nội dung rỗng hoặc thiếu. Gặp trường hợp đó
thì chuyển sang skill `browser`, đừng cố retry ở đây.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request

TIMEOUT = 30
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def download(url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        ctype = r.headers.get("Content-Type", "")
        raw = r.read()
    return raw, ctype


def strip_tags(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|aside)\b.*?</\1>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                 ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(a, b)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def get_title(html):
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    return " ".join(m.group(1).split()) if m else ""


def extract(url, html):
    """Trả về (text, extractor_đã_dùng)."""
    try:
        import trafilatura
        got = trafilatura.extract(html, include_comments=False,
                                  include_tables=True, url=url)
        if got and got.strip():
            return got.strip(), "trafilatura"
    except ImportError:
        pass
    except Exception:
        pass

    try:
        from readability import Document
        doc = Document(html)
        got = strip_tags(doc.summary())
        if got and got.strip():
            return got.strip(), "readability"
    except ImportError:
        pass
    except Exception:
        pass

    return strip_tags(html), "regex (thô — cài trafilatura để có kết quả tốt hơn)"


def handle_pdf(raw):
    try:
        import io
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for p in pdf.pages:
                parts.append(p.extract_text() or "")
        return "\n\n".join(parts).strip(), "pdfplumber"
    except ImportError:
        return "", "PDF nhưng thiếu pdfplumber"
    except Exception as e:
        return "", "PDF, bóc tách lỗi: %s" % type(e).__name__


def fetch_one(url, max_chars, raw_mode):
    try:
        raw, ctype = download(url)
    except urllib.error.HTTPError as e:
        return {"url": url, "ok": False, "error": "HTTP %d" % e.code}
    except Exception as e:
        return {"url": url, "ok": False, "error": "%s: %s" % (type(e).__name__, e)}

    if "application/pdf" in ctype.lower() or url.lower().endswith(".pdf"):
        text, how = handle_pdf(raw)
        title = ""
    else:
        html = raw.decode("utf-8", "replace")
        if raw_mode:
            return {"url": url, "ok": True, "title": get_title(html),
                    "extractor": "raw", "content": html}
        title = get_title(html)
        text, how = extract(url, html)

    truncated = False
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
        truncated = True

    return {"url": url, "ok": True, "title": title, "extractor": how,
            "chars": len(text), "truncated": truncated, "content": text}


def main():
    ap = argparse.ArgumentParser(description="Tải URL và bóc nội dung chính.")
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--max-chars", type=int, default=8000,
                    help="Cắt bớt mỗi trang (mặc định 8000, 0 = không cắt)")
    ap.add_argument("--raw", action="store_true", help="Trả HTML thô, không bóc tách")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    results = [fetch_one(u, args.max_chars, args.raw) for u in args.urls]

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    for i, r in enumerate(results):
        if i:
            print("\n" + "─" * 70 + "\n")
        if not r["ok"]:
            print("KHÔNG TẢI ĐƯỢC %s — %s" % (r["url"], r["error"]))
            continue
        print("URL:   %s" % r["url"])
        if r.get("title"):
            print("Tiêu đề: %s" % r["title"])
        print("Bóc bằng: %s · %d ký tự%s" %
              (r["extractor"], r.get("chars", 0),
               " (đã cắt)" if r.get("truncated") else ""))
        print()
        print(r["content"])
        if not r["content"].strip():
            print("(rỗng — nhiều khả năng trang render bằng JavaScript. "
                  "Dùng skill browser thay vì retry ở đây.)")

    if any(not r["ok"] for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
