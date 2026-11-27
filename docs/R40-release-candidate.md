# R40 / RC1 — release integration and acceptance

Feature freeze: R39 is the final planned routing feature before RC1. The
integration branch is based on R39 commit
`597c84afadce1756d5f46e028270383e2438a53e` (CI + Visual CAD PASS, 170
unit tests, 52 Chromium tests; Windows acceptance still running at branch
creation). The last fully verified fallback is R38 commit
`f2b3b65c141e5d07094cc1ce99d7122f5cfdc3c4`.
R39's measured TL494 result: all 33 crossing-channel proposals rejected,
77 bends, 38 crossings, 5282207 um, 78 wires, 33 straight wires.
No new numerical improvement claimed. The R40 branch changes CI and
release documentation only; production routing code and frozen source
are unchanged.

## Release gate

- [ ] Direct integration PR against current main, no divergent changes.
- [ ] Main CI and all Visual CAD jobs PASS on the exact candidate.
- [ ] All eight actual TL494 stages retain 23 components, 15 connected
  Nets, 62 PinRefs, 16 physical DA1 pins, 2 non-electrical b graphics,
  23 placed labels, zero errors/geometry warnings/overflow, and the
  protected final R38 baseline or better.
- [ ] Python/browser label geometry parity and SVG/PNG300 (A3
  4961x3508 pixels) for all eight stages.
- [ ] Rust tests and exact-commit bundled Python sidecar checks PASS.
- [ ] Real installed NSIS/WebView2 small-project authoring and persistence
  scenario plus complete TL494 two launches, Unicode Save As, digest
  preservation and SVG/PNG300 export PASS.
- [ ] Download the exact accepted installer artifact and verify its
  SHA-256 against its manifest and SHA256SUMS.txt.
- [ ] Visual inspection of the exported schematic and actual user
  installation/launch, editing and saving on their Windows PC.
- [ ] User approval to merge the integration PR to main.
- [ ] Repeat CI and installed Windows acceptance on the new main SHA.
- [ ] Publish a GitHub Release only after main acceptance and approval.

## CI design

The source gate runs on every PR and every main push, not only selected
paths. The native workflow includes PRs targeting main and all main
pushes; full TL494 flags R33/R35/R36/R37/R38/R39 are enabled for that
release path. Exact PR head is checked out, and the base SHA must be its
ancestor; if main advances, refresh the candidate before accepting it.
Source gate tests GitHub's PR merge checkout. No main merge is performed
by this workflow.

The native job hashes the staged NSIS installer before and after the
real installed-app tests, requires all six full-acceptance flags and
six full TL494 evidence files, copies the identical installer only
after success, and publishes it together with manifest.json and
SHA256SUMS.txt. The manifest contains source SHA, source tree, base SHA,
run ID/attempt, byte size and installer hash. The artifact is
`gscad-verified-windows-installer-<run_id>-<run_attempt>` (30 days).
It demonstrates native acceptance only; the other CI jobs and manual
review are separately required. Failed jobs must not publish a
verified installer. Full native diagnostic evidence remains available
even on failure when generated.

## Limitations and rollback

Product version and application identifier remain unchanged in RC1
until release naming/version is agreed. No code-signing certificate
is configured by R40. Font export remains `FONT_RENDER_UNVERIFIED`;
this is a functional engineering preview, not a normative ESKD print
certification. No new release or main merge without user approval.
If R39/R40 acceptance cannot be completed, prepare an equivalent
release gate on the exact verified R38 fallback, not an unverified
mixed branch. Preserve all prior stacked PRs until integration succeeds.
