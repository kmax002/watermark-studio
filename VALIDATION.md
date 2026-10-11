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

## Not established

- No GPU Pod was rented or charged, and no Runpod API request was submitted.
- Docker Desktop's Linux engine was unavailable. The Dockerfile has not been
  built here; do not describe the image as built or deployed.
- Responsive breakpoints, drag/drop and very large browser uploads have not been
  checked. The successful browser test used small neutral files.
- No claim of universal watermark robustness, guaranteed invisibility,
  arbitrary-film perceptual quality or statistically calibrated false attribution.
- No user movie, private recovery register or recipient record was used in these
  tests, copied into the source package, or sent to a remote service.

## Before advertising a one-click deployment

Create a template for the pinned public source commit (or build the container),
launch one explicitly budgeted GPU Pod, open the actual browser interface, run
the included neutral smoke test, and confirm upload/download, cancellation and
persistent storage through the Runpod proxy. Save the exact image/source/GPU
details and results, then publish the tested template link.
