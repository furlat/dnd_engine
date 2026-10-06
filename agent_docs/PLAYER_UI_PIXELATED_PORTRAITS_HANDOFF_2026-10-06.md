# Pixelated portraits — production handoff, 6 October 2026

**Creature extension:** [Summon and goblin portraits handoff](/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/agent_docs/SUMMON_GOBLIN_PORTRAITS_HANDOFF_2026-10-06.md) contains the new matching painted bank for the 24 unique summon bodies and 17 authored goblin variants, with exact creature/rig bindings and three native sizes. It is a separate portrait delivery; this original bank remains available.

**Scope: portraits only.** The human stopped the transparent UI/control direction. Do not import that HUD, its controls, frames or full UI archives from the earlier handoff. This document replaces the earlier UI handoff for the requested delivery. The portraits are prepared assets; production installation has not been performed here.

## Files

- [Portrait-only asset archive](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/pixelated-portraits-only-2026-10-06.zip)
- [Exact portrait manifest](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/portraits/manifest.json)
- [Visual comparison](http://127.0.0.1:8784/fantasy-hud-study-2026-10-06/portraits.html)
- Asset root: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06`. Manifest file paths resolve relative to this root, or to the extracted archive root.

## Delivered bank

**56 existing portraits × 3 sizes = 168 PNGs.** These are the original game portraits processed through the existing CIE pixelation pipeline. Their identities and source files are preserved.

**Two optional repaint samples × 3 sizes = 6 PNGs.** Sable and the shield fighter have BG1/2-inspired Imagen repaint alternatives. These are samples, not a replacement for the 56-portrait bank. Use `existing-cie` for the bank; choose `painted-cie` only if that alternative is wanted.

| UI role | Manifest field | Native pixels |
|---|---|---|
| Initiative | `files.initiative` | 36 × 48 |
| Party / active character | `files.hud` | 48 × 64 |
| Character sheet / inspection | `files.sheet` | 96 × 128 |

All variants use the same centred 3:4 crop for each character. Each size was generated directly from its source, resized with premultiplied alpha and processed once through D65 CIE76 using the existing 64-colour palette. No frame or label is baked into the portraits.

## Integration

1. Read `portraits/manifest.json`; match each original portrait identity using `key` and `source`. `aliases` identifies the characters used in the comparison. Keep the existing character/portrait associations.
2. Choose the role-specific PNG. Display it at its native size; use nearest-neighbour sampling for intentional integer enlargement. Do not resize the 36 × 48 version into the 96 × 128 inspection portrait.
3. Keep selection, active-turn indicators, borders, HP and condition markers as separate UI elements. This delivery does not prescribe a new HUD layout.
4. Keep original portraits available during integration. The manifest records source and output SHA-256 values for checking the imported files.

## Checks and provenance

174 PNG paths and hashes were verified for this delivery. The preceding portrait audit verified the three native sizes, palette and unchanged source hashes. Visual comparison remains available above; these checks do not imply production installation.

The archive contains only portraits, their manifest, the palette/profile and this handoff. It excludes the abandoned transparency experiments and unrelated UI artwork. Reproduction source: [pixelate_portraits.py](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/authoring/pixelate_portraits.py). Repaint prompts: [portrait-prompts.json](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/fantasy-hud-study-2026-10-06/authoring/portrait-prompts.json); the two samples were generated with the built-in image tool, then pixelated.
