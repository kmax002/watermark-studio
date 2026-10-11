# Third-party notices

Watermark Studio application source is distributed under GPL-2.0-only. The full
license is in `LICENSE`. The payload module was adapted from the project's local
experimental watermarking tools, without any private registers or film data.

## Meta VideoSeal / PixelSeal

Copyright (c) Meta Platforms, Inc. and affiliates.
MIT-licensed upstream source at https://github.com/facebookresearch/videoseal.
Exact repository commit: `870ca7fb33578b90f14c602016b6c2788096226e`.
Its license is retained in `/opt/videoseal/LICENSE` in the built container.
Official model: https://dl.fbaipublicfiles.com/videoseal/pixelseal/checkpoint.pth.
SHA-256: `0c5665cff20eb6ce1b5aaa7d91c19dafb418bfee32d02dd3344e4ed60d9d75bd`.
This project is not endorsed by Meta or Runpod.

## BCH library

`bchlib` 2.1.3 declares GPL-2.0. Its license is supplied with the installed
distribution. Upstream source: https://github.com/jkent/python-bchlib.
Versioned source distributions: https://pypi.org/project/bchlib/2.1.3/#files.
The application uses it for error correction, not as a watermark model.

## FFmpeg and other dependencies

FFmpeg is installed from the Ubuntu package repositories in the container;
the package's copyright/license files remain under `/usr/share/doc`. This build
uses libx264. Preserve the licenses and corresponding source obligations for the
specific FFmpeg build and codec libraries you redistribute.

PyTorch, torchvision, FastAPI, NumPy and the other pinned dependencies retain their
respective package licenses. Source ZIPs contain application code and setup recipes,
not redistributed copies of these binaries or pretrained weights. The container
build installs them explicitly from their upstream/package-registry sources.

