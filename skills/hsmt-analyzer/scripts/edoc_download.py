#!/usr/bin/env python3
"""
edoc_download.py — Tải file HSMT từ muasamcong bằng fileId qua endpoint edocproxy
KHÔNG cần đăng nhập, reCAPTCHA, hay VNeGP Client Agent.

fileId lấy từ DOM trang chi tiết gói thầu (tab "Hồ sơ mời thầu"):
    <span id="FILEID,TÊN FILE" class="tags-fileAttach file-download-all">
    -> phần trước dấu phẩy là fileId.

Dùng:
    python3 edoc_download.py <fileId> [outdir]
    python3 edoc_download.py <fileId1,fileId2,...> [outdir]
"""
import sys, os, re, urllib.parse, urllib.request

BASE = "https://muasamcong.mpi.gov.vn/api/unau/edocproxy/file/share/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


def download(file_id: str, outdir: str = ".") -> str:
    file_id = file_id.strip()
    req = urllib.request.Request(BASE + file_id, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
        cd = resp.headers.get("content-disposition", "")
        m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
        fname = urllib.parse.unquote(m.group(1)) if m else f"{file_id}.bin"
    fname = os.path.basename(fname.replace("\\", "/"))
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, fname)
    with open(path, "wb") as f:
        f.write(data)
    # sanity: DOCX/ZIP begin with PK; PDF with %PDF
    head = data[:4]
    kind = "DOCX/ZIP" if head[:2] == b"PK" else "PDF" if head == b"%PDF" else "?"
    print(f"OK  {file_id} -> {path}  ({len(data):,} bytes, {kind})")
    return path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ids = sys.argv[1].split(",")
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    for fid in ids:
        if fid.strip():
            try:
                download(fid, outdir)
            except Exception as e:
                print(f"ERR {fid}: {e}")
