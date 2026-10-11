# Watermark Studio

This standalone app is separate from Film Desk and the existing private recovery
folder. Never include film media, private registers, keys, recipient mappings,
`.data`, `.env`, the harness `.film` directory, or local runtime environments in
source packages, containers or public repositories.

Use the exact pinned PixelSeal checkpoint and payload format. Never regenerate
existing recovery IDs when reading a register. New batches receive fresh keys.
Never release an output before full decode, file-size and strict watermark checks.
Aggregate and both temporal halves must agree; inconclusive is not no watermark.
Identify copy IDs, never claim a person is identified or leaks are prevented.

One authenticated owner per Pod. Keep password-required startup, secure cookies
on HTTPS, bounded chunked uploads, allowlisted file downloads, bounded media
protocols, single-worker locks, cancellation and no automatic restart/retry.

Tests must use synthetic content and fresh disposable registers. No paid Pod
or remote media upload is implied by local development. Do not claim container,
GPU or Runpod validation from CPU tests. Keep VALIDATION.md truthful.
