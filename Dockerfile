FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIDEOSEAL_REPO=/opt/videoseal WATERMARK_DATA=/workspace/watermark-studio-data \
    COOKIE_SECURE=1 WATERMARK_DEVICE=cuda
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN printf 'torch==2.8.0\ntorchvision==0.23.0\n' > /tmp/torch-constraints.txt \
    && python -m pip install -c /tmp/torch-constraints.txt -r requirements.txt
RUN git clone https://github.com/facebookresearch/videoseal.git /opt/videoseal \
    && git -C /opt/videoseal checkout 870ca7fb33578b90f14c602016b6c2788096226e \
    && mkdir -p /opt/videoseal/ckpts \
    && curl --fail --location --retry 2 https://dl.fbaipublicfiles.com/videoseal/pixelseal/checkpoint.pth -o /opt/videoseal/ckpts/pixelseal_checkpoint.pth \
    && echo '0c5665cff20eb6ce1b5aaa7d91c19dafb418bfee32d02dd3344e4ed60d9d75bd  /opt/videoseal/ckpts/pixelseal_checkpoint.pth' | sha256sum -c -
COPY app /app/app
COPY static /app/static
COPY tools /app/tools
COPY tests /app/tests
COPY README.md THIRD_PARTY_NOTICES.md LICENSE /app/
RUN python -m pytest tests -q
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/health', timeout=3)"
ENTRYPOINT []
CMD ["python", "-m", "uvicorn", "app.server:factory", "--factory", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--no-access-log"]
