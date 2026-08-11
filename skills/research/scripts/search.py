#!/usr/bin/env python3
"""
Tìm kiếm web. Ba backend, chọn bằng biến môi trường RESEARCH_BACKEND.

    python scripts/search.py "câu truy vấn"
    python scripts/search.py "query" -n 10 --json
    RESEARCH_BACKEND=exa python scripts/search.py "query" --category research_paper

Backend:
  exa      (mặc định) Exa API. Cần EXA_API_KEY. Tìm theo ngữ nghĩa — mô tả ý
           thay vì gõ từ khoá. Đây là thứ Hyperagent đang dùng.
  ddg      DuckDuckGo, không cần key. Dự phòng khi hết quota hoặc test nhanh.
           Lưu ý: scrape HTML, không phải API chính thức, dễ bị rate-limit.
  searxng  SearXNG tự host. Cần SEARXNG_URL. Riêng tư, không giới hạn, chất
           lượng tuỳ engine bạn bật.

Đầu ra mặc định là text cho người/model đọc. Dùng --json khi cần parse.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 30
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def die(msg, code=1):
    print("Lỗi: " + msg, file=sys.stderr)
    sys.exit(code)


def http_json(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", UA)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        die("HTTP %d từ %s\n%s" % (e.code, urllib.parse.urlparse(url).netloc, body))
    except urllib.error.URLError as e:
        die("không kết nối được %s (%s)" % (urllib.parse.urlparse(url).netloc, e.reason))


# ───────────────────────────────────────────────────────────── ddg
def search_ddg(query, n, **kw):
    """DuckDuckGo qua thư viện ddgs. Không cần key."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS      # tên gói cũ
        except ImportError:
            die("thiếu thư viện. Cài: pip install ddgs")
    out = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=n):
            out.append({
                "title": r.get("title", ""),
                "url": r.get("href") or r.get("link", ""),
                "snippet": r.get("body", ""),
            })
    return out


# ───────────────────────────────────────────────────────────── searxng
def search_searxng(query, n, **kw):
    base = os.environ.get("SEARXNG_URL", "").rstrip("/")
    if not base:
        die("backend searxng cần biến SEARXNG_URL, ví dụ http://localhost:8080")
    qs = urllib.parse.urlencode({"q": query, "format": "json"})
    data = http_json(base + "/search?" + qs)
    out = []
    for r in (data.get("results") or [])[:n]:
        out.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        })
    if not out:
        print("Chú ý: SearXNG trả 0 kết quả. Kiểm tra instance đã bật format=json "
              "trong settings.yml chưa (mặc định bị tắt).", file=sys.stderr)
    return out


# ───────────────────────────────────────────────────────────── exa
def search_exa(query, n, category=None, domains=None, text=False, **kw):
    key = os.environ.get("EXA_API_KEY")
    if not key:
        die("backend exa cần biến EXA_API_KEY")
    payload = {"query": query, "numResults": n, "type": "auto"}
    if category:
        payload["category"] = category
    if domains:
        payload["includeDomains"] = domains
    if text:
        payload["contents"] = {"text": True}
    else:
        payload["contents"] = {"summary": True, "highlights": True}
    data = http_json("https://api.exa.ai/search",
                     data=json.dumps(payload).encode(),
                     headers={"x-api-key": key, "Content-Type": "application/json"})
    out = []
    for r in data.get("results", []):
        snippet = r.get("summary") or ""
        if not snippet and r.get("highlights"):
            snippet = " … ".join(r["highlights"][:2])
        if not snippet:
            snippet = (r.get("text") or "")[:400]
        out.append({
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "snippet": snippet,
            "published": r.get("publishedDate") or "",
            "author": r.get("author") or "",
        })
    return out


BACKENDS = {"ddg": search_ddg, "searxng": search_searxng, "exa": search_exa}


def main():
    ap = argparse.ArgumentParser(description="Tìm kiếm web, backend cắm rời.")
    ap.add_argument("query")
    ap.add_argument("-n", "--num", type=int, default=8, help="Số kết quả (mặc định 8)")
    ap.add_argument("--backend", default=os.environ.get("RESEARCH_BACKEND", "exa"),
                    choices=sorted(BACKENDS), help="Ghi đè RESEARCH_BACKEND")
    ap.add_argument("--category", help="Chỉ Exa: company, research_paper, news, "
                                       "github, tweet, pdf, linkedin, people")
    ap.add_argument("--domains", nargs="*", help="Chỉ Exa: giới hạn tên miền")
    ap.add_argument("--text", action="store_true",
                    help="Chỉ Exa: lấy full text thay vì summary")
    ap.add_argument("--json", action="store_true", help="Xuất JSON")
    args = ap.parse_args()

    fn = BACKENDS[args.backend]
    results = fn(args.query, args.num, category=args.category,
                 domains=args.domains, text=args.text)

    if args.json:
        print(json.dumps({"backend": args.backend, "query": args.query,
                          "results": results}, ensure_ascii=False, indent=2))
        return

    if not results:
        print("Không có kết quả.")
        return
    print("%d kết quả (%s) cho: %s\n" % (len(results), args.backend, args.query))
    for i, r in enumerate(results, 1):
        print("%d. %s" % (i, r["title"] or "(không tiêu đề)"))
        print("   %s" % r["url"])
        meta = " · ".join(x for x in (r.get("published", ""), r.get("author", "")) if x)
        if meta:
            print("   %s" % meta)
        if r["snippet"]:
            s = " ".join(r["snippet"].split())
            print("   %s" % (s[:300] + ("…" if len(s) > 300 else "")))
        print()


if __name__ == "__main__":
    main()
