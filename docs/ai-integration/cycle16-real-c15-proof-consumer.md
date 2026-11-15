# Cycle 16 — real source-locked C15 owner proof consumption (read-only)

**Owner:** MCP/AI, existing Draft PR #111 only. **Integration mode:** offline,
read-only, no project writes, no generated/synthetic physical connections.
Frozen physical source: `e695c415fdced164b0e0c39c5249d030795a0aa6`.

## 1. What actually exists

The prior installed-wheel command `python -m examples.agent_tl494_cycle13_quickstart
--out NEW_DIR` still runs the real original 23-part, 15-net, 62-PinRef signed
source, reviews the exact 7 physical catalog glyph variants with native
`mcp.ClientSession`, exports 14 real catalogue SVG/PNG images, 11 denied
malicious CLI mutations, a seven-stage typed handoff and `BLOCKED_PARTIAL`.
Those images are individual UGO review images, **NOT a routed TL494 sheet**.

New in Cycle16, `cycle16_owner_proof.review_c15_owner_proof` consumes the REAL
owner-produced `C15_REAL_TL494_DELIVERY.json` plus 2 actual physical source
`TL494-A3-{clean,diagnostic}-source-b.svg` views and the independent
`native/TL494-compact-A3-route-drc.json` route account. This is the
`SourceSnapshot → PlacementProposal → RouteCandidate → RenderedProof → QA`
**evidence interface**, not a new generator and not an auto-merging MCP writer.
You must obtain the owner-produced folder from the authorized RECON C15 run.
A purported JSON-only image recognition result is not accepted.

The first real two-stage owner consumer workflow is
`.github/workflows/ai-cycle16-owner-proof-real.yml`. It separately checks out
exact fixed owner SHAs, executes real source/NET/PAINT on 23/15/62, then runs the
read-only consumer using a fresh **noneditable installed wheel outside the
checkout**. It produces actual clean/diagnostic SVG and **DRAFT-only**
300 DPI PNG previews; the C15 source manifest itself does not vouch for
those raster previews or final print QA.

## 2. One end-user command on installed wheel

Existing user-approved `C15_REAL_TL494_DELIVERY.json` must reside in an
already-created, trusted local folder alongside both native SVG files and
its `native/` DRC JSON. This command creates a **new** output folder; it
cannot overwrite existing evidence, follow symlink/junction ancestors,
rewrite source or write the schematic project.

Windows PowerShell (after wheel installed into the venv):

```powershell
$py = "$env:USERPROFILE\gse-wheel-venv\Scripts\python.exe"
& $py -m examples.agent_tl494_cycle13_quickstart `
  --owner-c15-dir "C:\verified-recon-c15-output" `
  --out "$env:TEMP\tl494-c16-review-new"
```

Linux (after wheel installed into venv):

```bash
$HOME/gse-wheel-venv/bin/python -m examples.agent_tl494_cycle13_quickstart \
  --owner-c15-dir "$HOME/verified-recon-c15-output" \
  --out "$HOME/tl494-c16-review-new"
```

For a faster proof-only check (no native MCP image gallery), both platforms
can run from an installed wheel:

```bash
python -m examples.agent_tl494_cycle16_owner_proof \
  --owner-c15-dir /absolute/path/to/real/C15-output \
  --out /absolute/path/to/new/readonly-proof
```

For a missing owner manifest, omit `--owner-c15-dir`: the result is
`BLOCKED_NO_OWNER_C15_PROOF`. An invalid/tampered owner folder is a
`REJECTED` with stable `C16_*` code, CLI exit 3 (no fake approval).

Inspect `source-c16-owner-candidate-proof.json`: exact original Net
memberships and signed source are verified locally against the packaged
frozen original; route complete-Net count, 62 source PinRefs, 16 DA1 leads,
two separately non-electrical `b-X2`/`b-R5` lines, font SHA, all
image bytes and route DRC source names are cross-checked. Source file SHA and
actual 1 µm SVG coordinates are checked; clean and diagnostic wire
signatures must match **exactly**. Their green editor squares must be **0**
and **16**, respectively. No `$d_` ELK dummy becomes a physical part.

The seven original UGO preview pairs are still *not* proof of full sheet.
`routed_native_drc_errors: 0` on a **partial** graph cannot become a
print permission. As currently implemented, the native C15 producer has
no final PNG300 or independent QA evidence in its three-file output
manifest; the consumer always returns **`BLOCKED_PARTIAL`** for fewer than
15 complete source nets, or **`BLOCKED_INDEPENDENT_QA`** even if an external
owner reports all 15 complete. It never returns `print_ready=true`.

## 3. Exact trust and interface boundaries

- **SourceSnapshot:** independent installed, Git-blob locked source; 23 parts,
  15 literal original named electrical Nets, 62 physical PinRef memberships,
  16 DA1 physical contacts, 2 non-electrical b. Original 91 wires/37
  junctions and 9 DRC ERR/32 WARN remain a negative historical fixture.
- **PlacementProposal:** 23 original component reference identities only,
  bounded 2.5 mm grid relocation, real A3/A2; ELK `FIXED_POS` means
  **relative-to-part** pinned local pin positions, NOT absolute sheet XY.
  Always revalidate world coordinates and 10mm frame Type A.
- **RouteCandidate:** 15 literal source Nets with exact member sets,
  per-Net connected PinRefs, genuine NET owner 15-tree graph, no
  extra/deleted PinRefs, fake T/X, virtual ground/PE or fictitious
  continuation conductors. A native route count/DRC error count is still
  owner-submitted evidence, not an independent graph proof.
- **RenderedProof:** trusted-sha file names only, no outside-folder or
  symlink traversal, SVG XML with native leads and 2 actual non-connectable
  continuation lines at exact integer µm, same wire identities in both
  views, genuine font hash as **producer-claimed** evidence. The consumer
  does NOT independently read or cryptographically authenticate the
  physical font bytes in the external owner stage.
- **QA gate:** no global post-render wire/symbol/text DRC and no independent
  manual source-photo review has been performed by the MCP consumer;
  `print_ready`, `mcp_write_tools_enabled` and `mutated` are ALWAYS false.

The owner-provided commit SHA fields are surfaced as **unverified
external provenance**, never treated as a cryptographic authentication
of GitHub source history. Current RECON C15 report pins an earlier NET
router snapshot; do not report it as the latest NET code unless the exact
pinned SHA matches the separate checkout. Neither this module nor the
CLI imports or executes untrusted external owner Python modules.

## 4. Required next owners

**NET #114:** fix the reproduced 1 µm off-path false negative in
`_visibility_path`; provide current genuine `GlobalRoutePreview` all
15 source Net members + physical route geometry for native independently
rechecked DRC.

**RECON #115:** preserve and update the C15 producer’s source-name PinRef
bijection and signed 16-pin DA1; emit real typed placement and correctly
pinned NET versions. No wholesale reference PR merge.

**PAINT #93:** add genuine 300 DPI PNG to the same signed file manifest,
full printed ink/letter DRC metadata, 16 diagnostic vs 0 clean markers.
**QA #99 / ESKD #112:** independently authorize 15/15 + actual full
printed 3/2/1 mm DRC + authentic font+photo comparison.

No external MIT/GPL/LGPL/EPL library is imported into the native
read-only consumer. netlistsvg and ELK are conceptual interface references;
no foreign code, virtual pin or write MCP tool is shipped.
