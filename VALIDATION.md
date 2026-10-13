# Validation, updated 13 October 2026

## Completed locally

- 18 automated protocol/security tests pass on Windows/Python 3.11 and
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
  16-character rule. The Pod was stopped; that app and template version accepted an
  owner-selected password of 8+ characters. Thirteen local tests and an actual
  8-character login check passed after that change. The successful GPU run used
  that updated version, with authentication still required and an owner-selected password.
- All cloud media were neutral synthetic tests. No film or existing private key
  was uploaded. No network volume was created. The Pod was stopped at 01:55:12
  and deleted at 01:55:27 on 12 October 2026 (Europe/Zurich), confirmed by RunPod's
  audit log. The displayed balance moved from $7.37 to $7.33 (about $0.04 total),
  within the approved $3 cap. This is a rounded balance change, not an itemized bill.

## Default-password setup update (v0.1.2)

At the user's request, new deployments use the literal `password` when
`APP_PASSWORD` is missing or empty. A nonempty custom value still takes precedence.
Startup no longer asks for a password or requires a template override. The login
page, public-template instructions and source ZIP instructions show the default.

All 14 tests pass on Windows/Python 3.11 and Ubuntu/Python 3.12, including actual
HTTP authentication with missing, empty and custom environment values. The custom
case rejects the default password; all three cases still require login. Linux
startup-script syntax also passes. No additional GPU Pod or model test was run
for this setup-only update; the GPU results above refer to the stated earlier commit.

## Storage admission update (v0.1.3, 13 October)

The old check reserved `(copies + 1) * maximum GB + 2 GB` before starting,
regardless of duration. A 50-copy batch at 1.5 GB therefore required 78.5 GB free,
even if its short outputs would be much smaller. Admission now requires only one
copy's limit plus an equal temporary allowance and 2 GB headroom. It is checked
before launching the worker and again before each copy. The page shows actual
free space, next-copy allowance, and the separate full-batch maximum estimate.

All 18 tests pass on Windows and Ubuntu. Regression cases admit 50/30/20 copies
at the 5 GB boundary, reject insufficient space before creating a job, and leave
leak checks independent of output storage. A simulated renderer and decreasing
free-space fixture verify a stop after the first checked copy preserves that
file, its verification record and the original 50-copy recovery register.
This fixture does not run a model or establish video quality.

A neutral local browser fixture simulated 6 GB free. Default-password login,
50-copy admission at 1.5 GB, immediate rejection of a 10 GB per-copy limit, and
switching to leak checking all behaved as expected. JavaScript syntax passes.
No GPU Pod, paid generation, private media, or Elliot account was used or changed.
The earlier RunPod GPU validation remains limited to its stated source commit.

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
