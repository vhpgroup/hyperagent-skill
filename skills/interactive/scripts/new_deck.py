#!/usr/bin/env python3
"""
Dựng khung một slide deck HTML chạy được, đã có sẵn toàn bộ phần điều hướng.

    python scripts/new_deck.py noi-dung.md -o deck.html
    python scripts/new_deck.py slides.json -o deck.html --title "Báo cáo Q3"
    python scripts/new_deck.py --blank -o deck.html      # khung rỗng để tự sửa

ĐẦU VÀO
  Markdown: mỗi slide cách nhau bằng một dòng `---`. Dòng `# ...` hoặc `## ...`
  đầu tiên thành tiêu đề, phần còn lại thành nội dung; `- ` thành gạch đầu dòng.

  JSON: [{"title": "...", "bullets": ["...", "..."], "note": "..."}]

VÌ SAO CẦN SCRIPT NÀY
Phần khó của slide HTML không phải nội dung mà là điều hướng: phím mũi tên,
chấm chỉ vị trí, bộ đếm, vuốt trên cảm ứng, thoát bằng Escape. Script sinh sẵn
những thứ đó để bạn chỉ còn lo nội dung và thẩm mỹ.

Phần THẨM MỸ thì script cố tình để trung tính. Đừng dùng nguyên si — đọc mục
"Định hướng thiết kế" trong SKILL.md rồi sửa màu, font, nhịp điệu cho khớp nội
dung. Một deck ra mắt sản phẩm và một deck báo cáo hội đồng quản trị không nên
trông giống nhau.
"""
import argparse
import html
import json
import os
import re
import sys

TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; overflow: hidden; }
  body {
    font-family: Inter, system-ui, -apple-system, sans-serif;
    background: #0f1115; color: #e9ecf1;
  }
  .slide {
    position: absolute; inset: 0;
    display: none; flex-direction: column; justify-content: center;
    padding: 6vh 8vw;
    opacity: 0; transition: opacity .35s ease;
  }
  .slide.active { display: flex; opacity: 1; }
  .slide h1 {
    font-size: clamp(2.2rem, 5.5vw, 4.2rem); font-weight: 800;
    line-height: 1.08; letter-spacing: -.02em; margin: 0 0 .6em;
  }
  .slide ul { margin: 0; padding-left: 1.1em; }
  .slide li {
    font-size: clamp(1rem, 1.9vw, 1.5rem); line-height: 1.6;
    margin-bottom: .55em; max-width: 46ch;
  }
  .slide p {
    font-size: clamp(1rem, 1.9vw, 1.5rem); line-height: 1.6; max-width: 60ch;
  }
  nav.dots {
    position: fixed; bottom: 22px; left: 50%; transform: translateX(-50%);
    display: flex; gap: 9px; z-index: 10;
  }
  nav.dots button {
    width: 9px; height: 9px; border-radius: 50%; border: 0; padding: 0;
    background: #3a4050; cursor: pointer; transition: background .2s, transform .2s;
  }
  nav.dots button.on { background: #e9ecf1; transform: scale(1.25); }
  .counter {
    position: fixed; bottom: 18px; right: 26px;
    font-size: .8rem; color: #79808f; font-variant-numeric: tabular-nums;
  }
  .arrow {
    position: fixed; top: 50%; transform: translateY(-50%);
    background: none; border: 0; color: #59606f; cursor: pointer;
    font-size: 2rem; padding: 12px; line-height: 1; transition: color .2s;
  }
  .arrow:hover { color: #e9ecf1; }
  .arrow[disabled] { opacity: .2; cursor: default; }
  #prev { left: 10px; } #next { right: 10px; }
  @media print { .slide { display: flex !important; opacity: 1 !important;
    position: relative; page-break-after: always; height: 100vh; }
    nav.dots, .counter, .arrow { display: none; } }
</style>
</head>
<body>

__SLIDES__

<button class="arrow" id="prev" aria-label="Slide trước">&#8249;</button>
<button class="arrow" id="next" aria-label="Slide sau">&#8250;</button>
<nav class="dots" id="dots"></nav>
<div class="counter" id="counter"></div>

<script>
(function () {
  const slides = Array.from(document.querySelectorAll('.slide'));
  const dots = document.getElementById('dots');
  const counter = document.getElementById('counter');
  const prev = document.getElementById('prev');
  const next = document.getElementById('next');
  let i = 0;

  slides.forEach((_, n) => {
    const b = document.createElement('button');
    b.setAttribute('aria-label', 'Slide ' + (n + 1));
    b.addEventListener('click', () => go(n));
    dots.appendChild(b);
  });

  function go(n) {
    i = Math.max(0, Math.min(n, slides.length - 1));
    slides.forEach((s, k) => s.classList.toggle('active', k === i));
    Array.from(dots.children).forEach((d, k) => d.classList.toggle('on', k === i));
    counter.textContent = (i + 1) + ' / ' + slides.length;
    prev.disabled = i === 0;
    next.disabled = i === slides.length - 1;
    if (location.hash !== '#' + (i + 1)) history.replaceState(null, '', '#' + (i + 1));
  }

  prev.addEventListener('click', () => go(i - 1));
  next.addEventListener('click', () => go(i + 1));

  document.addEventListener('keydown', e => {
    if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); go(i + 1); }
    else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); go(i - 1); }
    else if (e.key === 'Home') go(0);
    else if (e.key === 'End') go(slides.length - 1);
    else if (e.key === 'Escape') window.parent.postMessage({ type: 'close-fullscreen' }, '*');
  });

  // Cho phép trang cha điều khiển khi deck nằm trong iframe
  window.addEventListener('message', e => {
    if (e.data && e.data.type === 'navigate') {
      go(i + (e.data.direction === 'next' ? 1 : -1));
    }
  });

  // Vuốt trên cảm ứng, ngưỡng 50px
  let x0 = null;
  document.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; }, { passive: true });
  document.addEventListener('touchend', e => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 50) go(i + (dx < 0 ? 1 : -1));
    x0 = null;
  }, { passive: true });

  go(parseInt((location.hash || '#1').slice(1), 10) - 1 || 0);
})();
</script>
</body>
</html>
"""

BLANK = [{"title": "Tiêu đề bài trình bày",
          "bullets": ["Ý thứ nhất", "Ý thứ hai", "Ý thứ ba"]},
         {"title": "Slide thứ hai", "body": "Thay nội dung này."}]


def parse_markdown(text):
    slides = []
    for chunk in re.split(r"(?m)^---\s*$", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        title, rest = "", []
        for ln in lines:
            m = re.match(r"^#{1,3}\s+(.*)", ln)
            if m and not title:
                title = m.group(1).strip()
            else:
                rest.append(ln)
        bullets = [re.sub(r"^[-*]\s+", "", l).strip()
                   for l in rest if re.match(r"^\s*[-*]\s+", l)]
        body = "\n".join(l for l in rest
                         if l.strip() and not re.match(r"^\s*[-*]\s+", l)).strip()
        s = {"title": title}
        if bullets:
            s["bullets"] = bullets
        if body:
            s["body"] = body
        slides.append(s)
    return slides


def render(slides):
    out = []
    for s in slides:
        parts = ['<section class="slide">']
        if s.get("title"):
            parts.append("  <h1>%s</h1>" % html.escape(s["title"]))
        if s.get("bullets"):
            parts.append("  <ul>")
            for b in s["bullets"]:
                parts.append("    <li>%s</li>" % html.escape(b))
            parts.append("  </ul>")
        if s.get("body"):
            for para in s["body"].split("\n\n"):
                parts.append("  <p>%s</p>" % html.escape(para.strip()))
        parts.append("</section>")
        out.append("\n".join(parts))
    return "\n\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Sinh slide deck HTML có sẵn điều hướng.")
    ap.add_argument("input", nargs="?", help="File .md hoặc .json")
    ap.add_argument("--blank", action="store_true", help="Sinh khung mẫu 2 slide")
    ap.add_argument("-o", "--output", default="deck.html")
    ap.add_argument("--title", default="Bài trình bày")
    args = ap.parse_args()

    if args.blank or not args.input:
        slides = BLANK
    else:
        if not os.path.exists(args.input):
            sys.exit("Lỗi: không thấy %s" % args.input)
        raw = open(args.input, encoding="utf-8").read()
        slides = (json.loads(raw) if args.input.lower().endswith(".json")
                  else parse_markdown(raw))

    if not slides:
        sys.exit("Lỗi: không tách được slide nào từ đầu vào.")

    doc = (TEMPLATE.replace("__TITLE__", html.escape(args.title))
                   .replace("__SLIDES__", render(slides)))
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print("Đã ghi %s — %d slide." % (args.output, len(slides)))
    print("Xem thử: python scripts/preview.py %s --open" % args.output)
    print("Nhớ chỉnh lại thẩm mỹ cho khớp nội dung, đừng để nguyên mặc định.")


if __name__ == "__main__":
    main()
