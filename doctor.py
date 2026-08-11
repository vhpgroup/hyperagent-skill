#!/usr/bin/env python3
"""
Kiểm tra bundle Hyperagent Document Skills bằng cách CHẠY THẬT.

    python doctor.py

Khác với việc chỉ `import` thư viện: script này tạo file thật, chạy đúng
những script mà SKILL.md bảo agent chạy, rồi đọc kết quả ngược lại. Mục đích
là để bạn biết chắc đường nào dùng được trước khi giao việc thật cho agent.

Exit code 0 nếu mọi thứ bắt buộc đều đạt (phần tuỳ chọn thiếu vẫn coi là đạt).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, "skills")

G, R, Y, B, D, X = "\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[2m", "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    G = R = Y = B = D = X = ""

results = []          # (category, label, status, detail)  status: ok|fail|skip|warn


def record(cat, label, status, detail=""):
    results.append((cat, label, status, detail))
    icon = {"ok": G + "  OK  " + X, "fail": R + " FAIL " + X,
            "skip": D + " SKIP " + X, "warn": Y + " WARN " + X}[status]
    line = "  [%s] %s" % (icon, label)
    if detail:
        line += D + "  — " + detail + X
    print(line)


def run(cmd, cwd=None, timeout=120):
    """Chạy lệnh, trả về (rc, output gộp stdout+stderr)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode, p.stdout.decode("utf-8", "replace").strip()
    except FileNotFoundError:
        return 127, "không tìm thấy lệnh"
    except subprocess.TimeoutExpired:
        return 124, "quá thời gian chờ"


def head(title):
    print("\n" + B + title + X)


# ══════════════════════════════════════════════════ 1. Python
def check_python():
    head("1. Python")
    v = sys.version_info
    vs = "%d.%d.%d" % (v.major, v.minor, v.micro)
    if v >= (3, 10):
        record("python", "Phiên bản Python " + vs, "ok")
    else:
        record("python", "Phiên bản Python " + vs, "fail",
               "cần >= 3.10 (validate.py dùng match/case)")

    required = ["pypdf", "pdfplumber", "openpyxl", "lxml", "defusedxml", "PIL"]
    optional = {"pdf2image": "render PDF ra ảnh",
                "reportlab": "tạo PDF từ đầu",
                "pandas": "phân tích bảng",
                "pytesseract": "OCR"}
    import importlib
    for m in required:
        try:
            importlib.import_module(m)
            record("python", "import %s" % m, "ok")
        except Exception as e:
            record("python", "import %s" % m, "fail", type(e).__name__)
    for m, why in optional.items():
        try:
            importlib.import_module(m)
            record("python", "import %s" % m, "ok", why)
        except Exception:
            record("python", "import %s" % m, "skip", "tuỳ chọn — mất: " + why)


# ══════════════════════════════════════════════════ 2. Binary hệ thống
def check_binaries():
    head("2. Binary hệ thống")

    rc, out = run(["pdftoppm", "-v"])
    if rc in (0, 99) or "poppler" in out.lower():
        ver = out.splitlines()[0] if out else ""
        record("bin", "poppler (pdftoppm)", "ok", ver[:40])
    else:
        record("bin", "poppler (pdftoppm)", "fail",
               "pdf2image không chạy → mất render PDF ra ảnh")

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        rc, out = run([soffice, "--version"], timeout=90)
        record("bin", "LibreOffice", "ok" if rc == 0 else "warn",
               (out.splitlines()[0][:40] if out else soffice))
    else:
        record("bin", "LibreOffice", "skip",
               "tuỳ chọn — mất: recalc công thức Excel, export PDF, đọc .doc")

    for name, why in (("pandoc", "trích docx sang markdown kèm tracked changes"),
                      ("tesseract", "OCR PDF scan")):
        if shutil.which(name):
            record("bin", name, "ok")
        else:
            record("bin", name, "skip", "tuỳ chọn — mất: " + why)

    if shutil.which("node"):
        rc, out = run(["node", "--version"])
        record("bin", "Node.js", "ok", out)
        np = os.path.join(HERE, "node_modules")
        for pkg in ("docx", "pptxgenjs"):
            if os.path.isdir(os.path.join(np, pkg)):
                record("bin", "npm: " + pkg, "ok")
            else:
                record("bin", "npm: " + pkg, "skip",
                       "tuỳ chọn — mất đường TẠO MỚI file")
    else:
        record("bin", "Node.js", "skip",
               "tuỳ chọn — mất đường TẠO MỚI docx/pptx")


# ══════════════════════════════════════════════════ 3. Chạy thật
def check_xlsx(tmp):
    head("3. xlsx — tạo, giải nén, validate, đóng gói lại")
    S = os.path.join(SKILLS, "xlsx", "scripts")
    src = os.path.join(tmp, "test.xlsx")

    try:
        from openpyxl import Workbook, load_workbook
        wb = Workbook(); ws = wb.active
        ws["A1"] = "Item"; ws["B1"] = "Qty"
        ws["A2"] = "Widget"; ws["B2"] = 5
        ws["B3"] = "=B2*2"
        wb.save(src)
        record("xlsx", "tạo file bằng openpyxl", "ok", "3 dòng, 1 công thức")
    except Exception as e:
        record("xlsx", "tạo file bằng openpyxl", "fail", str(e)[:60])
        return

    unpacked = os.path.join(tmp, "x_unpacked")
    rc, out = run([sys.executable, os.path.join(S, "office", "unpack.py"), src, unpacked])
    if rc == 0:
        n = sum(len(f) for _, _, f in os.walk(unpacked))
        record("xlsx", "office/unpack.py", "ok", "%d file XML" % n)
    else:
        record("xlsx", "office/unpack.py", "fail", out.splitlines()[-1][:70] if out else "")
        return

    rc, out = run([sys.executable, os.path.join(S, "office", "validate.py"), src])
    record("xlsx", "office/validate.py", "ok" if rc == 0 else "fail",
           (out.splitlines()[-1][:70] if out else ""))

    repacked = os.path.join(tmp, "repacked.xlsx")
    rc, out = run([sys.executable, os.path.join(S, "office", "pack.py"),
                   unpacked, repacked, "--original", src])
    if rc != 0 or not os.path.exists(repacked):
        record("xlsx", "office/pack.py", "fail", out.splitlines()[-1][:70] if out else "")
        return
    record("xlsx", "office/pack.py", "ok")

    try:
        from openpyxl import load_workbook
        ws = load_workbook(repacked).active
        good = ws["A2"].value == "Widget" and ws["B2"].value == 5
        record("xlsx", "đọc lại sau roundtrip", "ok" if good else "fail",
               "A2=%r B2=%r" % (ws["A2"].value, ws["B2"].value))
    except Exception as e:
        record("xlsx", "đọc lại sau roundtrip", "fail", str(e)[:60])

    recalc = os.path.join(S, "recalc.py")
    if shutil.which("soffice") or shutil.which("libreoffice"):
        rc, out = run([sys.executable, recalc, src], cwd=S, timeout=180)
        record("xlsx", "recalc.py (cần LibreOffice)", "ok" if rc == 0 else "warn",
               (out.splitlines()[-1][:70] if out else ""))
    else:
        record("xlsx", "recalc.py", "skip", "không có LibreOffice")


def check_pdf(tmp):
    head("4. pdf — tạo, trích text, render ảnh")
    S = os.path.join(SKILLS, "pdf", "scripts")
    src = os.path.join(tmp, "test.pdf")

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(src, pagesize=letter)
        c.drawString(100, 700, "Hyperagent doctor smoke test")
        c.drawString(100, 680, "dong thu hai")
        c.save()
        record("pdf", "tạo PDF bằng reportlab", "ok")
    except Exception as e:
        record("pdf", "tạo PDF bằng reportlab", "skip", "thiếu reportlab")
        return

    try:
        from pypdf import PdfReader
        r = PdfReader(src)
        record("pdf", "pypdf đọc được", "ok", "%d trang" % len(r.pages))
    except Exception as e:
        record("pdf", "pypdf đọc được", "fail", str(e)[:60])

    try:
        import pdfplumber
        with pdfplumber.open(src) as pdf:
            txt = pdf.pages[0].extract_text() or ""
        ok = "doctor" in txt
        record("pdf", "pdfplumber trích text", "ok" if ok else "warn",
               repr(txt[:35]))
    except Exception as e:
        record("pdf", "pdfplumber trích text", "fail", str(e)[:60])

    rc, out = run([sys.executable, os.path.join(S, "check_fillable_fields.py"), src])
    record("pdf", "check_fillable_fields.py", "ok" if rc == 0 else "fail",
           (out.splitlines()[-1][:60] if out else ""))

    rc, out = run([sys.executable, os.path.join(S, "extract_form_structure.py"),
                   src, os.path.join(tmp, "structure.json")])
    record("pdf", "extract_form_structure.py", "ok" if rc == 0 else "fail",
           (out.splitlines()[-1][:60] if out else ""))

    # Chú ý: script này KHÔNG tự tạo thư mục đích, phải mkdir trước.
    imgdir = os.path.join(tmp, "pages")
    os.makedirs(imgdir, exist_ok=True)
    rc, out = run([sys.executable, os.path.join(S, "convert_pdf_to_images.py"), src, imgdir])
    if rc == 0 and os.path.isdir(imgdir) and os.listdir(imgdir):
        record("pdf", "convert_pdf_to_images.py (cần poppler)", "ok",
               "%d ảnh" % len(os.listdir(imgdir)))
    else:
        record("pdf", "convert_pdf_to_images.py (cần poppler)", "fail",
               out.splitlines()[-1][:60] if out else "không tạo được ảnh")


def check_docx_pptx(tmp):
    head("5. docx / pptx — giải nén, validate, đóng gói lại")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")

    for kind in ("docx", "pptx"):
        S = os.path.join(SKILLS, kind, "scripts")
        src = os.path.join(tmp, "sample." + kind)

        # Cần một file mẫu. Dùng LibreOffice tạo từ file text là cách chắc nhất
        # mà không phụ thuộc Node.
        made = False
        if soffice:
            txt = os.path.join(tmp, "seed_%s.txt" % kind)
            with open(txt, "w") as fh:
                fh.write("Hyperagent doctor smoke test\nDong thu hai\n")
            outdir = os.path.join(tmp, "so_" + kind)
            os.makedirs(outdir, exist_ok=True)
            target = "docx" if kind == "docx" else "pptx:Impress MS PowerPoint 2007 XML"
            rc, out = run([soffice, "--headless", "--convert-to", target,
                           "--outdir", outdir, txt], timeout=180)
            cand = os.path.join(outdir, "seed_%s.%s" % (kind, kind))
            if rc == 0 and os.path.exists(cand):
                shutil.copy(cand, src); made = True

        if not made:
            record(kind, "tạo file mẫu", "skip",
                   "cần LibreOffice để sinh file mẫu — bỏ qua nhóm test này")
            continue
        record(kind, "tạo file mẫu bằng LibreOffice", "ok")

        unpacked = os.path.join(tmp, kind + "_unpacked")
        rc, out = run([sys.executable, os.path.join(S, "office", "unpack.py"), src, unpacked])
        if rc != 0:
            record(kind, "office/unpack.py", "fail", out.splitlines()[-1][:70] if out else "")
            continue
        n = sum(len(f) for _, _, f in os.walk(unpacked))
        record(kind, "office/unpack.py", "ok", "%d file XML" % n)

        rc, out = run([sys.executable, os.path.join(S, "office", "validate.py"), src])
        record(kind, "office/validate.py", "ok" if rc == 0 else "fail",
               (out.splitlines()[-1][:70] if out else ""))

        repacked = os.path.join(tmp, "repacked." + kind)
        rc, out = run([sys.executable, os.path.join(S, "office", "pack.py"),
                       unpacked, repacked, "--original", src])
        if rc == 0 and os.path.exists(repacked):
            try:
                zipfile.ZipFile(repacked).testzip()
                record(kind, "office/pack.py + roundtrip", "ok")
            except Exception as e:
                record(kind, "office/pack.py + roundtrip", "fail", str(e)[:60])
        else:
            record(kind, "office/pack.py", "fail", out.splitlines()[-1][:70] if out else "")


# ══════════════════════════════════════════════════ tổng kết
def summary():
    head("Tổng kết")
    n_ok = sum(1 for r in results if r[2] == "ok")
    n_fail = sum(1 for r in results if r[2] == "fail")
    n_skip = sum(1 for r in results if r[2] == "skip")
    n_warn = sum(1 for r in results if r[2] == "warn")

    print("  %s%d đạt%s   %s%d hỏng%s   %s%d cảnh báo%s   %s%d bỏ qua%s" %
          (G, n_ok, X, R, n_fail, X, Y, n_warn, X, D, n_skip, X))

    if n_fail:
        print("\n  " + R + "Những mục hỏng:" + X)
        for cat, label, status, detail in results:
            if status == "fail":
                print("    - [%s] %s %s" % (cat, label, D + detail + X))
        print("\n  Skill tương ứng sẽ không chạy đúng. Sửa xong chạy lại doctor.py.")
    else:
        print("\n  " + G + "Mọi thứ bắt buộc đều đạt." + X)

    if n_skip:
        print("\n  " + D + "Mục bỏ qua là tính năng tuỳ chọn — xem cột giải thích"
              " để biết mất gì." + X)
    return 1 if n_fail else 0


def main():
    print()
    print(B + "Hyperagent Document Skills — kiểm tra cài đặt" + X)
    print(D + "Chạy thật, không chỉ kiểm tra import." + X)

    if not os.path.isdir(SKILLS):
        print(R + "\nKhông tìm thấy thư mục skills/ cạnh doctor.py" + X)
        return 2

    tmp = tempfile.mkdtemp(prefix="hyperagent_doctor_")
    try:
        check_python()
        check_binaries()
        check_xlsx(tmp)
        check_pdf(tmp)
        check_docx_pptx(tmp)
        return summary()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        print()


if __name__ == "__main__":
    sys.exit(main())
