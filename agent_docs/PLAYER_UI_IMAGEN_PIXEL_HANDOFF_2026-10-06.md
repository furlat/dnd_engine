> **Superseded by the human’s portrait-only delivery.** The transparent UI/control direction was stopped. Do not import the HUD, controls, frames or full UI archives from this document. Use [the portrait-only handoff](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/agent_docs/PLAYER_UI_PIXELATED_PORTRAITS_HANDOFF_2026-10-06.md).

# Minimal player UI artwork — 6 October 2026

**Status: visual review candidates. Not installed or accepted in production.** The accepted CIE28 ability bank is unchanged. The new frames, transparent control repaints and portrait options below need the human's visual decision.

Canonical workspace: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06`.

[Interactive HUD](http://127.0.0.1:8784/fantasy-hud-study-2026-10-06/?review=transparent-panels-controls-v5) · [Portrait comparison](http://127.0.0.1:8784/fantasy-hud-study-2026-10-06/portraits.html) · [Study](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/RESEARCH.md) · [Resolution review](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/resolutions.html).

## Current human direction

- Visibility takes priority over decorative chrome. No opaque HUD, inventory, log or tooltip backing plates. No blur, broad gradient, vignette or ornamental filler.
- Structure uses thin separate iron edges and dividers. Panel interiors are genuinely transparent. Live text uses a local glyph outline for contrast.
- Use familiar icons instead of repeating their labels. Counts, HP, character identity and the current-turn prompt remain text. Tooltips and accessible labels explain icons.
- Action-economy icons must not carry square black backgrounds. The action, bonus, reaction, movement, filters and End Turn repaints are isolated RGBA subjects.
- Ability icons touch with zero gaps. Their edge overlays are separate resources; do not bake a border into an icon.
- Empty HUD/panel space must not capture world input. Visible controls and the log's reading/scrolling area retain their actual input regions. The preview verifies pass-through; production owns final input routing.

The previous Blender frame experiment, broad copper/leather Imagen skin, opaque popup fill and black-backed resource controls are rejected directions. Do not use them from recovery folders.

## Runtime resources

The lean archive is [fantasy-hud-runtime-art.zip](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/fantasy-hud-runtime-art.zip). It contains 215 PNGs, exact manifests, palette/profile, size profiles and this handoff. Existing ability art and competitor references are not duplicated in it.

| Set | Manifest | Contents |
|---|---|---|
| Thin borders | [minimal-skin/manifest.json](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/minimal-skin/manifest.json) | 16 resources: action and slot states, hollow button states, hollow panel/tooltip edges, health track and red fill |
| Transparent fantasy controls | [controls/transparent/manifest.json](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/controls/transparent/manifest.json) | 9 subjects at both 20×20 and 28×28: 18 files |
| Familiar client utility glyphs | [controls/manifest.json](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/controls/manifest.json) | 7 native 20×20 CIE glyphs: sheet, pack, book, history, close, rows and concentration |
| Portraits | [portraits/manifest.json](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/portraits/manifest.json) | 56 existing portraits × 3 native sizes, plus 2 Imagen repaint samples × 3 sizes: 174 files |

All source identities and hashes are preserved. The original WebP portraits and original control icons were not changed. Transparent repaints retain the existing nine `ui.*` semantic keys; manifest rows distinguish their native size. Select a size variant explicitly; do not treat repeated keys as a last-row-wins index.

### Frames and slicing

| Resource | Native pixels | Fixed inset on each side |
|---|---|---|
| Action overlay | 28×28 | 3 px |
| Slot / portrait edge | 48×48 | 5 px |
| Hollow panel / tooltip | 64×64 | 8 px |
| Hollow button edge | 64×24 | 6 px |
| Health track | 48×8 | 3 px |
| Red health fill tile | 8×4 | no slicing |

Use the exact manifest insets. Corners stay fixed; tile designated straight edges and the transparent centre. Do not stretch sampled texture or include corner caps in repeated centre/edge regions. No frame has baked text or an icon. All centres of hollow resources remain alpha zero. Hover and selection have distinct square edges; disabled and button states share art where the sheet has no distinct state. Native availability, labels and focus remain separate live presentation.

### Pixel sizes and portraits

[LAYOUT_PROFILES.json](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/LAYOUT_PROFILES.json) records tested display sizes at 960×540, 1280×720, 1920×1080, 1920×1200 and 2560×1440. The review uses native 28-pixel ability art at integer nearest 2× by default; 1× and 3× remain comparison settings. These are proposed review sizes, not a locked production scale contract.

Initiative portraits are 36×48, party/active portraits 48×64, and inspection portraits 96×128. Each is processed directly to those final pixels, using the same centred 3:4 source geometry. They display at 1×; the comparison separately labels nearest 2× enlargement. Do not resize a whole HUD screenshot or pixelate text.

The existing-bank CIE version and the two BG1/2-inspired repaints are alternatives. Only Sable and the shield fighter have generated repaint samples; this is not a claim that all 56 were regenerated. Repaints preserve the original identities and have no baked frame.

## Production boundary

This is an art and interaction fixture, not an engine-connected encounter. The screenshot is our actual game; displayed resources, item details, costs, turns and log rolls are examples. Production must bind current observer-authorized facts and admitted action rows. The fixtures do not grant spells or class actions.

Keep native action discovery, source-item identities, rank/form choices, condition ownership, log wording, commands and world picking in their existing owners. Stable filters should not move pinned keybind positions. Turn order and inspected-character focus require distinct indicators.

No other thread was read or messaged. This file and the archives are for the human to forward. Existing production media and its authenticated index were not modified.

## Sources and reproduction

Imagen was used through the built-in tool with the actual HUD screenshot and existing icon/portrait references. Crop and premultiplied native resize precede one existing D65 CIE76 / 64-colour pass. Transparent RGB is zeroed; no black-key background removal is used.

Masters, prompts, crops and scripts are in the separate [authoring archive](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-imagen-pixel-2026-10-06.zip). The master/crop relationships are recorded in manifests. Utility glyphs reuse the client's Lucide symbols, with their ISC licence included; these were rasterized at native size and CIE processed.

Run `authoring/minimal_skin.py`, `authoring/transparent_controls.py` and `authoring/pixelate_portraits.py` with the existing CodexFX pipeline environment. `authoring/glyph_render.cjs` uses the client's local Lucide and Playwright installation; `authoring/stage_controls.py` performs its CIE pass. Paths are explicit source dependencies, not files to copy into gameplay.

## Verification

[Validation results](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/review/validation.json) cover all five viewport sizes, exact native portrait geometry, touching shortcuts, no missing images or JavaScript errors, empty-space pass-through, item inspection, nested log details, Fire Shield choices, stable filters, row toggle and Escape closing.

The bank's palette, dimensions, source hashes and transparent edges were checked. Runtime ZIP paths, CRC and file hashes are audited in `PACKAGE_INDEX.json`. These checks establish asset/preview consistency; they do not replace human visual acceptance.
