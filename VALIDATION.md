# Validation, 12 October 2026

## Completed locally

- 13 automated protocol/security tests pass on Windows/Python 3.11 and
  Ubuntu 24.04/Python 3.12. They cover authentication, request size/CSRF guards,
  resumable chunk writes, private-state redaction, withheld download protection,
  register validation, conflicting IDs, restart interruption and size budgets.
- Real PixelSeal processing on Windows CPU: two distinct watermarked copies of
  a neutral 8-second 1280x720 synthetic clip, with tone audio, passed complete
  decode and strict aggregate/two-half recovery checks. A CRF24 recompression
  recovered the correct first copy; the clean control was inconclusive. The
  source hash stayed unchanged.
- The same real-model test passed independently on Ubuntu 24.04 with the pinned
  Python dependencies, PyTorch 2.8.0 CPU and torchvision 0.23.0 CPU. This tests
  Linux installation and actual model/FFmpeg behavior, not a Docker image.
- A live local HTTP test used real chunked upload, an actual background worker,
  private recovery download and checked MP4 download. Its downloaded hash matched
  the saved verification record, public state excluded the secret, simultaneous
  processing was refused, and cancellation settled without releasing a video.
  This complete HTTP test passed on both Windows and Ubuntu Linux.
- JavaScript syntax, Python compilation and Linux shell syntax were checked.
- The actual browser login, tab controls, private recovery download and recovery
  upload were exercised. A separate, initially empty workspace received only the
  recompressed synthetic leak and its original recovery JSON through browser file
  uploads. Its real CPU worker recovered **Neutral 001**, with matching aggregate
  and two-half results. No original video or previous workspace data was supplied.
  Desktop browser layout was inspected visually.

The worker's original stdin-based parent monitor blocked model imports on Windows.
It was replaced with process identity monitoring (PID plus process creation time).
The successful HTTP test above ran after that fix.

## RunPod GPU and browser test

- The public template is https://console.runpod.io/hub/template/kxe3r4aicz.
- One user-approved disposable Pod used an RTX 3090 (24 GB), 32 vCPUs and
  125 GB RAM in EU-CZ-1, at $0.50/hour plus $0.004/hour container storage.
  The image was `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`; the tested
  source commit was `956902a4fea766afc1696498be4b93893b97d870`.
- The official image installed the pinned app and verified PixelSeal model,
  and served the actual app over the RunPod HTTPS proxy on port 7860.
- Browser login, synthetic-video upload, two-copy GPU processing, private recovery
  download and both MP4 downloads succeeded. Both downloaded hashes matched
  `verification.json`, both copies were distinct, and the source was unchanged.
  Each output passed a full decode and aggregate/two-half watermark verification.
- A second disposable processing job was cancelled without releasing a video.
- After downloading the results, the original cloud batch (including its private
  recovery key) and original upload were deleted. Copy 001 was recompressed locally
  with H.264 CRF24, and only this suspected leak and the downloaded recovery JSON
  were uploaded again. The GPU checker recovered **RunPod test 001**, with agreement
  across the aggregate and both disjoint halves. Its report downloaded successfully.
- An initial startup rejected an 8-character password because of the earlier
  16-character rule. The Pod was stopped; the app and template now accept an
  owner-selected password of 8+ characters. Thirteen local tests and an actual
  8-character login check passed after that change. The successful GPU run used
  that updated version, with authentication still required and no shared password.
- All cloud media were neutral synthetic tests. No film or existing private key
  was uploaded. No network volume was created. The Pod was stopped at 01:55:12
  and deleted at 01:55:27 on 12 October 2026 (Europe/Zurich), confirmed by RunPod's
  audit log. The displayed balance moved from $7.37 to $7.33 (about $0.04 total),
  within the approved $3 cap. This is a rounded balance change, not an itemized bill.

## Not established

- Docker Desktop's Linux engine was unavailable. The Dockerfile has not been
  built here; do not describe the image as built or deployed.
- Responsive breakpoints, drag/drop and very large browser uploads have not been
  checked. The successful browser test used small neutral files.
- No claim of universal watermark robustness, guaranteed invisibility,
  arbitrary-film perceptual quality or statistically calibrated false attribution.
- No user movie, pre-existing private recovery register or recipient record was
  used in these tests, copied into the source package, or sent to a remote service.

## Deployment limits

The public source template was tested; the alternative custom Dockerfile was not
built. First startup installs dependencies and downloads the verified model.
The cloud test used temporary container storage; network-volume persistence and
resuming a stopped Pod with persistent storage were not tested. The demonstrated
workflow keeps recovery files locally and can use a fresh workspace later.
This short synthetic test does not establish quality or robustness for every film.
