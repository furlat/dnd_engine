# Material selection checkpoint — independent anti-slop review

2026-10-05. Review of Step C working changes in `animation.py`, `animation_draw.py`, `attack.py`, and `test_spell_palettes.py`. No production edits by reviewer.

## Initial disposition: changes required

The shared `effective_layer_palette` direction is appropriate: one pure choice supplies both loader treatment and cache identity, automatic colors require the resolved spell palette, and explicit isolated source sheets preserve their accepted baked pixels. Cache identity includes the full effective PaletteTreatment (including noise/gamma/untinted), while rig/clip/view row remain in the containing cache key. No parallel material registry or new graphics pipeline is introduced.

Two issues must close before approval:

1. **Reference loading retains the obsolete category gate.** `load_reference_media` still rejects explicit unbaked Effect2/Effect4/Buff9 and categories absent from `vfx_source_hues`. This contradicts the now-general exact palette treatment and leaves two authorities for material support. Replace this guard with the shared effective treatment validation. The new actual-pixel test directly exercises `load_cast_rows`, so it cannot catch this admission failure; exercise a real reference-media load for one formerly rejected category.
2. **Literal white attack authoring must remain white.** `_attack_layers` initially injected damage secondary/tertiary colors into every slash, even `tint="white"` or literal integer tints. The actual `ranged` profile authors white on both hit and miss. Respect explicit colors as explicit treatment; only element-derived authoring should inherit the damage palette. Otherwise material cleanup silently changes the meaning of authored ranged accents.

## Confirmed good behavior

- Explicit sourceSheet+override returning no runtime treatment matches existing documented offline bake semantics. The pre-existing shared-sheet override test verifies preserving those baked pixels.
- Automatic layers still get their owning palette through `_layer_palette` and no longer use category hue selection in the row loader.
- Removing the Magic3 near-white special case is consistent with exact replacement and avoids overriding a selected material after loading.
- The new pixel regression exercises two palettes over real source sheet rows and proves changed cache entries, nonempty output, and allowed output colors.
- Other `_colored` uses for different media are not covered by this bounded correction; do not claim the whole renderer no longer uses tint.

This checkpoint does not establish final all-material authoring coverage, visual approval of all casts, or a portable presentation export.

## Correction review — approved

Re-read the corrected source after the two findings. **APPROVE the bounded material checkpoint.**

- The full `load_animation_media` admission path now invokes `effective_layer_palette` and no longer gates supported overlays by the hue table or a hardcoded Effect2/Effect4/Buff9 list. (The initial finding called this the reference-media path; the actual public function is `load_animation_media`.)
- The new full-loader regression constructs a real Effect4 aura, compiles its cast, loads ordinary actor appearances, and checks four resulting rows are nonempty and contain only the declared exact palette. This covers the path the first direct-row test missed.
- `_attack_layers` now uses the element ramp only for `$element` tokens. Literal integer colors and `white` become explicit one-color treatments, preserving their authored semantics.
- The parent reports 50 passing tests across spell palettes and True Strike. This reviewer inspected the test and source changes; it did not independently rerun that suite or claim new visual approval.

Both initial blockers are closed. Baked override semantics, exact replacement and cache ownership remain consistent. Broader per-content visual acceptance and other media tint paths remain outside this receipt.
