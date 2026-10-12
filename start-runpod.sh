#!/usr/bin/env bash
# Upload/extract the source ZIP on an official Runpod PyTorch 2.8 / CUDA 12.8 Pod,
# expose HTTP port 7860, then run: bash start-runpod.sh
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export WATERMARK_DATA="${WATERMARK_DATA:-/workspace/watermark-studio-data}"
export VIDEOSEAL_REPO="${VIDEOSEAL_REPO:-/workspace/watermark-studio-model/videoseal}"
export COOKIE_SECURE=1
export WATERMARK_DEVICE=cuda
export APP_PASSWORD="${APP_PASSWORD:-password}"
if [[ ${#APP_PASSWORD} -lt 8 ]]; then printf 'Password must be at least 8 characters.\n'; exit 1; fi
command -v ffmpeg >/dev/null || { apt-get update; apt-get install -y ffmpeg; }
python -m venv --system-site-packages .venv
source .venv/bin/activate
printf 'torch==2.8.0\ntorchvision==0.23.0\n' > .venv/torch-constraints.txt
python -m pip install -c .venv/torch-constraints.txt -r requirements.txt
python tools/fetch_model.py
exec python -m uvicorn app.server:factory --factory --host 0.0.0.0 --port 7860 --workers 1 --no-access-log
