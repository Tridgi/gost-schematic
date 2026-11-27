# R48 integration candidate

Independent draft, no merge or release authorization. Exact parents: editor b6c4095c1c1d505b96d8a7fff3f5c9c09fee5448, updater eeb291151dc9a543b3e6174d274eff47206e0995, native QA cd076ed0a12e69f67f405069d27b422fd866a12a. RC1 base 8d805c777f831231704d15a8cff5ba4fc0c3a837 remains unchanged.

- Editor R43–R47 junction connection and annotation properties/drag/keyboard; R47 source gate was still running when staged.
- R41–R42 About, native version, signed update policy, bounded download and cancellation. Unsigned preview only; no production signing key or A→B proof.
- QA real native About and unsigned refusal, Cargo.lock hash and retained artifact, full TL494 regression.
- Explicit overlap resolution: App install guard, EditorShell About state/menu/dialog/shortcut guard, e2e union (updater exact selectors + all editor tests). Preserve all gates, no reduced assertions.

Required: exact-head Python/source/native acceptance, full TL494 23/15/62/16/2/23 topology, 77 bends/38 crossings/5282207 µm baseline, no new geometry errors. Native editor feature checks and owner local acceptance remain separate; no claim of normative font rendering or signed self-update until verified.
