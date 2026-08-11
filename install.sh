#!/usr/bin/env bash
# Cài đặt bundle Hyperagent Document Skills trên Ubuntu.
#
#   bash install.sh
#
# Script này KHÔNG cần sudo và KHÔNG động vào Python hệ thống.
# Nó tạo virtualenv .venv trong thư mục bundle và cài mọi thứ vào đó.
# Node packages cũng cài cục bộ vào ./node_modules, không dùng npm -g.

set -uo pipefail
cd "$(dirname "$0")"
BUNDLE_DIR="$(pwd)"

RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; DIM=$'\e[2m'; RST=$'\e[0m'
ok()   { echo "  ${GRN}OK${RST}    $*"; }
warn() { echo "  ${YLW}CHÚ Ý${RST} $*"; }
err()  { echo "  ${RED}LỖI${RST}  $*"; }

echo
echo "Cài đặt Hyperagent Document Skills"
echo "Thư mục: $BUNDLE_DIR"
echo

# ---------------------------------------------------------------- Python
echo "[1/4] Kiểm tra Python (cần >= 3.10)"

PY=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  cur="$(python3 --version 2>&1 || echo 'không tìm thấy')"
  err "Không có Python >= 3.10. Hiện tại: $cur"
  echo
  echo "  Bundle này bắt buộc 3.10+ vì office/validate.py dùng match/case"
  echo "  và office/pack.py dùng annotation kiểu 'str | None'. Trên 3.9 trở"
  echo "  xuống chúng là syntax error, không phải cảnh báo."
  echo
  echo "  Ubuntu 22.04 trở lên đã có sẵn 3.10+. Nếu bạn đang ở 20.04:"
  echo "    sudo add-apt-repository ppa:deadsnakes/ppa"
  echo "    sudo apt update && sudo apt install python3.11 python3.11-venv"
  echo "    bash install.sh"
  exit 1
fi
ok "$PY ($($PY --version 2>&1 | cut -d' ' -f2))"

# ---------------------------------------------------------------- venv
echo
echo "[2/4] Tạo virtualenv"
# Ubuntu tách module venv ra gói riêng, và từ 23.04 chặn pip toàn hệ thống
# (PEP 668). Dùng venv là cách tránh cả hai vấn đề cùng lúc.
if [ ! -d .venv ]; then
  if ! "$PY" -m venv .venv 2>/tmp/venv_err.txt; then
    err "Tạo venv thất bại:"
    sed 's/^/        /' /tmp/venv_err.txt
    echo
    echo "  Thường là do thiếu gói venv. Chạy:"
    echo "    sudo apt install $(basename $PY)-venv"
    exit 1
  fi
  ok "đã tạo .venv"
else
  ok ".venv đã có sẵn, dùng lại"
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip

echo
echo "[3/4] Cài thư viện Python"
if python -m pip install --quiet -r requirements.txt; then
  ok "đã cài từ requirements.txt"
else
  err "pip install thất bại. Chạy lại không có --quiet để xem chi tiết:"
  echo "    source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# ---------------------------------------------------------------- Node
echo
echo "[4/4] Cài thư viện Node (chỉ cần cho việc TẠO MỚI docx/pptx)"
NODE_MAJOR=0
NODE_BIN_DIR=""
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node --version 2>/dev/null | sed 's/^v//' | cut -d. -f1)"
  NODE_MAJOR="${NODE_MAJOR:-0}"
  NODE_BIN_DIR="$(dirname "$(command -v node)")"
fi

# Cạm bẫy riêng của Ubuntu 22.04: `apt install nodejs` cho Node 12.22.9,
# đã hết vòng đời từ 4/2022. Cài được nhưng rất dễ vỡ khi build.
if [ "$NODE_MAJOR" -gt 0 ] && [ "$NODE_MAJOR" -lt 18 ]; then
  warn "Node v$NODE_MAJOR quá cũ (Ubuntu 22.04 mặc định cho v12, đã EOL 4/2022)."
  echo "        Nên nâng lên LTS trước khi cài lib:"
  echo "          curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -"
  echo "          sudo apt install -y nodejs"
  echo "        Vẫn thử cài tiếp, nhưng nếu lỗi thì đây là nguyên nhân."
fi

if command -v npm >/dev/null 2>&1; then
  if npm install --silent --no-fund --no-audit docx pptxgenjs >/tmp/npm_err.txt 2>&1; then
    ok "đã cài docx + pptxgenjs vào ./node_modules"
  else
    warn "npm install thất bại — xem /tmp/npm_err.txt"
    warn "Bỏ qua được: bạn vẫn đọc/sửa được file có sẵn, chỉ mất đường tạo mới."
  fi
else
  warn "không có npm. Bỏ qua."
  warn "Mất đường tạo docx/pptx MỚI. Đọc/sửa file có sẵn vẫn bình thường."
  echo "        Muốn có: sudo apt install nodejs npm"
fi

# ---------------------------------------------------------------- env.sh
PATH_EXPORT=""
if [ -n "$NODE_BIN_DIR" ]; then
  PATH_EXPORT="export PATH=\"$NODE_BIN_DIR:\$PATH\""
fi
cat > env.sh <<EOF
# source env.sh  — nạp môi trường cho bundle này
export HYPERAGENT_SKILLS="$BUNDLE_DIR/skills"
$PATH_EXPORT
export NODE_PATH="$BUNDLE_DIR/node_modules\${NODE_PATH:+:\$NODE_PATH}"
source "$BUNDLE_DIR/.venv/bin/activate"
if [ -f "\${HOME}/.config/hyperagent/secrets.env" ]; then
  source "\${HOME}/.config/hyperagent/secrets.env"
fi
EOF
ok "đã ghi env.sh"

echo
echo "────────────────────────────────────────────────────────"
echo "Cài xong. Giờ chạy kiểm tra thật:"
echo
echo "  ${DIM}source env.sh${RST}"
echo "  ${DIM}python doctor.py${RST}"
echo
echo "doctor.py sẽ tạo file thật rồi unpack/pack/validate để xác nhận"
echo "đường nào chạy được, thay vì chỉ kiểm tra import."
echo "────────────────────────────────────────────────────────"
echo
