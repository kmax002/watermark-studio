# Watermark Studio

A private browser app for individually watermarked video copies and later copy-ID
recovery. Designed for an NVIDIA Runpod Pod, with a portable Python/FFmpeg engine.
This source package contains **no films, recipient records, existing copy IDs,
private recovery keys, private credentials or Windows Python installation**.

## Use the app

1. Unlock with **`password`** (or your own password if you set one).
2. Upload a video, choose a batch name, copy count and maximum size in decimal GB.
   The storage note shows free space and what the next copy needs.
3. Download and back up the **PRIVATE recovery JSON** and optional recipient CSV.
4. Download the verified MP4s. Give each viewer only their assigned MP4.
5. To check a suspected leak, upload the leaked video and the original recovery
   JSON. Start with a 30-second window. A recovered ID identifies a copy, not a person.

**You do not need to keep videos on RunPod.** Once you have downloaded your
videos and backed up the small private recovery JSON, you can terminate the Pod.
Months later, launch a fresh Pod and upload only the suspected stolen video and
that recovery file. The checker reports the original batch's copy label/number;
it needs neither the original movie nor the old Pod's storage. Keep the optional
recipient CSV locally if you want to look up who received that number. The public
template contains no recovery keys; losing your recovery file prevents recovery.

Uploads use 8 MiB chunks. If interrupted, choose the same file in the same tab to
resume. Completed uploads and job status survive a page refresh. Processing
continues with the browser closed while the Pod remains running. After a server
restart, unfinished jobs become interrupted and are **not automatically repeated**.
Already verified downloads stay available. A new batch creates new IDs.

One password protects one owner's workspace. Everyone with that password can see
all its videos, private keys and jobs. Share the **template**, and have each creator
launch their own Pod. The default login is the public word `password`; optionally
set `APP_PASSWORD` to a private value. This is not a multi-tenant service.

## Public RunPod template

[Open Watermark Studio on RunPod](https://console.runpod.io/hub/template/kxe3r4aicz).
Choose **Configure Pod**, select a GPU and deploy. Wait for setup, open the
**HTTP service on port 7860**, and sign in with **`password`**. No password setup
is required. Each creator runs a separate workspace on their own Pod.
The password unlocks the workspace and its files; recipients of downloaded MP4s
do not need it. Optionally set `APP_PASSWORD` (8+ characters) through **Set overrides**
before deploying to use your own password.

Budget enough disk for the original plus all outputs and about 10 GB for software.
Copies are processed one at a time. Starting and each subsequent copy require free
space for one output at its chosen limit, an equal temporary allowance, and 2 GB
headroom: **5 GB free at the default 1.5 GB limit**. The app does not reserve every
copy's maximum upfront. Short videos can produce much smaller files, so a batch
may fit even when its combined maximum would not. The page shows both numbers.
If storage falls below the next-copy allowance, processing stops before that copy;
finished downloads and the recovery JSON remain available. Download and back them
up before removing a batch. Unfinished copies do not resume automatically.
RunPod's deployment screen may require you to add the template's recommended
volume explicitly. If you use only container storage, download everything before
stopping as well as terminating the Pod. Storage on RunPod is never your backup.
See `VALIDATION.md` for the current deployment test status.

## Runpod setup from the source ZIP

1. Start an official Runpod PyTorch 2.8 / CUDA 12.8 GPU Pod. Expose HTTP port **7860**.
   A GPU with at least 16 GB VRAM is a conservative starting point, not a measured
   minimum. Budget storage for your source plus the copy count times your file-size
   limit, plus about 10 GB for software/model. Twenty 1.5 GB copies need at least
   30 GB for outputs alone. Use persistent storage mounted at `/workspace`.
2. Upload and extract this source ZIP under `/workspace` using the Pod's file manager.
3. In its terminal, run `bash start-runpod.sh` from the extracted folder. It uses
   `password` when `APP_PASSWORD` is empty or unset, installs dependencies in its own
   environment, and fetches the exact public model revision and verified weights.
4. Open the Pod's **HTTP service on port 7860**. Sign in with **`password`** unless
   you set your own password.

Keep the process running in the Pod terminal. For routine sharing, use the
container/template route below so the application starts automatically.
Download outputs and private recovery data before terminating a Pod. Persistent
Pod storage is not a backup; its lifecycle depends on the storage type chosen.

## Publish a reusable template

The simplest route uses the public source repository and Runpod's existing PyTorch
image. No container registry account or GitHub Actions permissions are required.
`tools/template.py` prepares a template JSON for an immutable source commit. On
first start, the Pod installs the app and verified public model on its volume.
Later starts reuse that installation. `APP_PASSWORD` is optional; its default is `password`.

```sh
python tools/template.py https://github.com/OWNER/watermark-studio FULL_COMMIT_SHA runpod-source-template.json
```

Save that template in your Runpod account, test it on a GPU, then share its Runpod
template link. Template creation does not launch a GPU; deploying a Pod does.
The generated template is public. Its empty `APP_PASSWORD` field uses the app's
default `password` automatically. Never put a private custom password in a public template.

For faster startup, the optional prebuilt container route is:

1. Put **only this directory** in a Git repository. The Docker build context uses a
   strict allowlist; do not add `.data`, `.env`, model weights or private footage.
2. Build on a Linux Docker host:

   ```sh
   docker build -t YOUR_REGISTRY/watermark-studio:0.1.0 .
   docker push YOUR_REGISTRY/watermark-studio:0.1.0
   ```

   Alternatively, copy `examples/github-container.yml` to
   `.github/workflows/container.yml`. That manually triggered workflow builds
   and pushes `ghcr.io/OWNER/REPOSITORY:0.1.0`. Make that package available to the
   intended users. The workflow does not create or rent a Pod.
3. In Runpod, create a Pod template using that published image, **7860/http**,
   a 30 GB container disk, and suitable `/workspace` volume capacity. The file
   `runpod-template.json` is the prebuilt-container configuration reference; its
   image is a placeholder. This is separate from the generated source template.
4. The default login is **`password`**, with no setup required. Optionally set
   **APP_PASSWORD** to your own value (8+ characters) for that deployment.
   Never bake a private custom password into an image or public template.
5. Validate the GPU deployment using the neutral smoke test before sharing the
   template link. Only then publish/share the template through Runpod.

The full model is baked into the Docker image. Jobs do not download models, send
videos to third-party inference APIs, or call Film Desk/Seedance. GPU and storage
charges are billed by Runpod while the rented resources exist.

## What the app changes

- Accepts SDR videos lasting 4 seconds to 4 hours, even dimensions from 256 to 3840
  pixels, and 1 to 120 fps. Inputs with HDR, rotation metadata or non-square pixels
  are rejected with an explanation, rather than silently tone-mapped/reoriented.
- Output retains aspect ratio, with the longest edge capped at 1920 pixels, H.264
  video and the first audio track converted to AAC 192 kbps. Variable-frame-rate
  input is normalised to its average frame rate. Extra audio/subtitle tracks and
  metadata are omitted. Uploaded originals are preserved.
- File-size control leaves encoding headroom. Every final file is measured; an
  oversized or unreadable copy is withheld, not silently released or re-encoded.
- Every output receives a full decode check, duration/dimension/audio-presence
  checks, and authenticated watermark recovery at seven windows for videos over
  24 seconds (one window for shorter videos). Aggregate and both temporal halves
  must identify the same registered ID. These are sampled watermark checks.
- Cancel stops processing; verified copies and the recovery file remain. Files can
  be removed explicitly in the app after backing them up. No background auto-retry.

Version 0.1.3 replaces the old full-batch storage rejection. Existing Pods pinned
to an earlier release keep that version; refreshing the browser does not update
their app. New deployments from the public template use the updated release.

## Recovery format and limits

PixelSeal uses a 256-bit message containing a fresh 32-bit per-batch token,
64-bit HMAC bound to the source SHA-256, and BCH error correction. Keys are
generated with OS randomness; duplicate tokens within a batch are rejected.
`app/payload.py` retains the existing experimental decoder and strict two-half rule.

New recovery files use `watermark-studio-v1`. The checker also accepts compatible
`film-issued-copies-v1` recovery files with the exact same model and payload settings.
It never reissues or modifies their keys. No original movie or expected copy ID is
needed to check a candidate. Keep the recovery file: a replacement random key or
the public model cannot reconstruct it.

Recovery does not prove who leaked a video, rule out payload transplantation or
establish chain of custody. Crop, resize, low bitrate, collusion and deliberate
removal can defeat the mark. An inconclusive result does not prove absence. The
application does not promise leak prevention, universal invisibility or reliable
arbitrarily short clips. The file-size limit does not guarantee perceptual quality.

## Local development and checks

Python 3.11/3.12, FFmpeg, PyTorch and torchvision are required. Install
`requirements.txt` in an isolated environment, then point `VIDEOSEAL_REPO` at the
pinned repository with its verified checkpoint. `tools/fetch_model.py` performs
explicit setup downloads; model substitution fails verification.

```sh
python -m unittest discover -s tests -v
# Explicit real-model test, synthetic content only; creates a NEW directory:
WATERMARK_DEVICE=cpu python tools/smoke_test.py /tmp/watermark-smoke
# GPU deployment check (same test, no additional inference-provider service):
python tools/smoke_test.py /workspace/watermark-smoke
```

For local HTTP only, set `COOKIE_SECURE=0` and bind to **127.0.0.1**. Runpod uses
HTTPS and must keep `COOKIE_SECURE=1`. The default login is `password`; optionally
set `APP_PASSWORD` to your own value, then start:

```sh
python -m uvicorn app.server:factory --factory --host 127.0.0.1 --port 7860 --workers 1 --no-access-log
```

One server owns a data directory using an OS file lock. Do not run multiple workers.
Authenticated routes serve only explicitly released files. Uploads stream to owned
IDs, all jobs are local subprocesses, and supported media demuxers/network protocols
are restricted. Public state contains no raw payloads, recovery secrets or server paths.

See `VALIDATION.md` for what was actually tested. The source package is experimental.

## License and upstream

Application source: GPL-2.0-only, see `LICENSE`. Dependencies retain their own
licenses; see `THIRD_PARTY_NOTICES.md`. Preserve notices and source obligations
when distributing a combined container.

- [Runpod custom templates](https://docs.runpod.io/pods/templates/create-custom-template)
- [Runpod template management](https://docs.runpod.io/pods/templates/manage-templates)
- [Meta VideoSeal / PixelSeal](https://github.com/facebookresearch/videoseal)

