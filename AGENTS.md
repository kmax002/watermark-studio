# Watermark Studio

This standalone app is separate from Film Desk and the existing private recovery
folder. Never include film media, private registers, keys, recipient mappings,
`.data`, `.env`, the harness `.film` directory, or local runtime environments in
source packages, containers or public repositories.

Use the exact pinned PixelSeal checkpoint and payload format. Never regenerate
existing recovery IDs when reading a register. New batches receive fresh keys.
The optional starting number defaults to 1 and changes copy labels consistently
in filenames, recipient CSVs and recovery results. It never resumes or reuses
an earlier batch's keys or IDs. Keep the recovery JSON for every batch.
Runtime frame batches must be even so the pinned step_size=2 remains aligned.
Keep full-resolution FP32 attenuation, the original strength and all recovery
checks when changing performance settings. Respect container CPU quotas, not
just the visible host CPU count. Never infer a real-movie speedup from a synthetic
benchmark. Do not stop a container with unbacked temporary storage to update it;
an idle worker can load an updated checkout while the server stays alive.
Never release an output before full decode, file-size and strict watermark checks.
Aggregate and both temporal halves must agree; inconclusive is not no watermark.
Detection reads every native video frame. Do not restore fixed 6 fps sampling:
it can miss stronger phases of the temporal watermark. Do not duplicate frames
to satisfy the minimum evidence count. Preserve strict authentication/halves.
Identify copy IDs, never claim a person is identified or leaks are prevented.

One authenticated owner per Pod. At the user's request, missing or empty
APP_PASSWORD defaults to the literal `password` for simple setup. Preserve a
nonempty custom password (8+ characters) and never prompt during startup.
Keep login required, secure cookies
on HTTPS, bounded chunked uploads, allowlisted file downloads, bounded media
protocols, single-worker locks, cancellation and no automatic restart/retry.
Storage admission checks one output plus an equal temporary allowance and 2 GB
headroom before launch and before every copy. Do not reserve every copy's size
ceiling upfront; short clips can be much smaller. Keep finished outputs and the
same private recovery register available if the next copy cannot fit.

Tests must use synthetic content and fresh disposable registers. No paid Pod
or remote media upload is implied by local development. Do not claim container,
GPU or Runpod validation from CPU tests. Keep VALIDATION.md truthful.
