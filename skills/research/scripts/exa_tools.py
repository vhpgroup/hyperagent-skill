#!/usr/bin/env python3
"""
Các endpoint Exa còn lại, tương ứng những tool cùng tên trong Hyperagent.

    # Exa Answer — câu trả lời có trích dẫn nguồn
    python scripts/exa_tools.py answer "SpaceX được định giá bao nhiêu?"
    python scripts/exa_tools.py answer "câu hỏi" --schema schema.json

    # Find Similar — tìm trang tương tự về mặt ngữ nghĩa
    python scripts/exa_tools.py similar https://example.com/bai-viet -n 10
    python scripts/exa_tools.py similar URL --exclude-domains example.com

    # Contents — lấy nội dung đã làm sạch từ cache của Exa
    python scripts/exa_tools.py contents URL1 URL2 --text
    python scripts/exa_tools.py contents URL --livecrawl always

Tất cả cần biến môi trường EXA_API_KEY.

Endpoint và payload lấy từ OpenAPI chính thức của Exa (docs.exa.ai), không
phải viết theo trí nhớ. Nhưng LƯU Ý: code này chưa được chạy thử với key thật —
xem mục "Đã test tới đâu" trong README.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.exa.ai"
TIMEOUT = 120


def die(msg, code=1):
    print("Lỗi: " + msg, file=sys.stderr)
    sys.exit(code)


def call(path, payload):
    key = os.environ.get("EXA_API_KEY")
    if not key:
        die("thiếu biến môi trường EXA_API_KEY.\n"
            "  export EXA_API_KEY=...\n"
            "Hoặc dùng backend khác: RESEARCH_BACKEND=ddg python scripts/search.py ...")
    req = urllib.request.Request(
        API + path, data=json.dumps(payload).encode(), method="POST")
    req.add_header("x-api-key", key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        if e.code == 401:
            die("401 — EXA_API_KEY sai hoặc hết hạn.")
        if e.code == 402:
            die("402 — tài khoản Exa hết credit.")
        die("HTTP %d từ Exa\n%s" % (e.code, body))
    except urllib.error.URLError as e:
        die("không kết nối được api.exa.ai (%s)" % e.reason)


def show_cost(data):
    c = (data.get("costDollars") or {}).get("total")
    if c is not None:
        print("\n[chi phí request này: $%.4f]" % c, file=sys.stderr)


# ─────────────────────────────────────────────────────────── answer
def cmd_answer(args):
    payload = {"query": args.query, "text": args.text}
    if args.schema:
        with open(args.schema, encoding="utf-8") as fh:
            payload["outputSchema"] = json.load(fh)
    data = call("/answer", payload)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    ans = data.get("answer")
    print(json.dumps(ans, ensure_ascii=False, indent=2)
          if isinstance(ans, (dict, list)) else (ans or "(không có câu trả lời)"))

    cites = data.get("citations") or []
    if cites:
        print("\nNguồn:")
        for i, c in enumerate(cites, 1):
            print("  %d. %s" % (i, c.get("title") or "(không tiêu đề)"))
            print("     %s" % c.get("url", ""))
            if c.get("publishedDate"):
                print("     %s" % c["publishedDate"][:10])
    show_cost(data)


# ─────────────────────────────────────────────────────────── similar
def cmd_similar(args):
    payload = {"url": args.url, "numResults": args.num}
    if args.exclude_domains:
        payload["excludeDomains"] = args.exclude_domains
    if args.include_domains:
        payload["includeDomains"] = args.include_domains
    payload["contents"] = {"text": True} if args.text else \
        {"summary": True, "highlights": True}
    data = call("/findSimilar", payload)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    results = data.get("results", [])
    if not results:
        print("Không tìm thấy trang tương tự.")
        return
    print("%d trang tương tự với %s\n" % (len(results), args.url))
    for i, r in enumerate(results, 1):
        print("%d. %s" % (i, r.get("title") or "(không tiêu đề)"))
        print("   %s" % r.get("url", ""))
        snip = r.get("summary") or " … ".join(r.get("highlights") or [])[:300] \
            or (r.get("text") or "")[:300]
        if snip:
            print("   %s" % " ".join(snip.split())[:300])
        print()
    show_cost(data)


# ─────────────────────────────────────────────────────────── contents
def cmd_contents(args):
    payload = {"urls": args.urls}
    if args.text:
        payload["text"] = True
    else:
        payload["summary"] = True
        payload["highlights"] = True
    if args.livecrawl:
        payload["livecrawl"] = args.livecrawl
    data = call("/contents", payload)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    for i, r in enumerate(data.get("results", [])):
        if i:
            print("\n" + "─" * 70 + "\n")
        print("URL:   %s" % r.get("url", ""))
        if r.get("title"):
            print("Tiêu đề: %s" % r["title"])
        print()
        print(r.get("text") or r.get("summary") or
              "\n".join(r.get("highlights") or []) or "(rỗng)")
    for s in data.get("statuses", []) or []:
        if s.get("status") != "success":
            print("\n[%s: %s]" % (s.get("id", ""), s.get("status")), file=sys.stderr)
    show_cost(data)


def main():
    ap = argparse.ArgumentParser(description="Exa Answer / Find Similar / Contents.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("answer", help="Trả lời câu hỏi kèm trích dẫn nguồn")
    a.add_argument("query")
    a.add_argument("--text", action="store_true", help="Kèm full text của nguồn")
    a.add_argument("--schema", help="File JSON Schema để ép đầu ra có cấu trúc")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_answer)

    s = sub.add_parser("similar", help="Tìm trang tương tự theo ngữ nghĩa")
    s.add_argument("url")
    s.add_argument("-n", "--num", type=int, default=10)
    s.add_argument("--include-domains", nargs="*")
    s.add_argument("--exclude-domains", nargs="*")
    s.add_argument("--text", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_similar)

    c = sub.add_parser("contents", help="Lấy nội dung sạch từ cache Exa")
    c.add_argument("urls", nargs="+")
    c.add_argument("--text", action="store_true", help="Full text thay vì summary")
    c.add_argument("--livecrawl", choices=["always", "fallback", "never"],
                   help="Kiểm soát độ tươi của nội dung")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_contents)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
