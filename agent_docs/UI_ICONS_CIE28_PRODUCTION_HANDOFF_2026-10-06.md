# Player UI artwork package — 6 October 2026

Forward this file with the [complete private archive](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ui-icons-cie28-production-2026-10-06.zip). Full archive: 79.9 MiB; lean runtime archive inside: 802.0 KiB. Archive SHA-256: `da85d0f936d05e9e4630cc3c0060dcbd142ed9c778233dfbddb5e80691b84f11`. CRC and every indexed file hash were verified.

**597 native CIE28 icons:** accepted base bank 549 + 48 new choice/control assets. All 48 subjects in PLAYER_UI_ARTWORK_HANDOFF_2026-10-06.md have explicit image mappings. Ten additional Blender UI skin resources and their editable .blend source are included. New choices and skin still need the human's visual acceptance; the base bank is accepted for handoff. No production installation has been performed.

[Choice preview](http://127.0.0.1:8784/ui-icons-cie28-delivery-2026-10-05/choices.html?owner=spell.conjure_animals&review=choices-v2) · [UI skin](http://127.0.0.1:8784/ui-icons-cie28-delivery-2026-10-05/skin.html) · [Accepted full bank](http://127.0.0.1:8784/ui-icons-cie28-delivery-2026-10-05/?view=all)

## Files to read after extracting

- `ui-icons-cie28-delivery-2026-10-05/HANDOFF.md`: complete integration contract and source/reproduction details.
- `runtime-manifest.json`: default 584 icon entries; 13 unindexed recovered keys remain inactive. Three additional source images are included for explicit Fly/escape-jaw requested bindings, making 587 icon PNGs in the lean payload. 515 recovered keys are authenticated in the current media snapshot.
- `player-ui-manifest.json` and `PLAYER_UI_RECONCILIATION.md`: exact required keys, native owners, shared files and intended meaning for all 48 requested subjects. No 48 duplicate images were generated.
- `variant-manifest.json` and `VARIANTS.md`: 103 actual choice/context mappings, slot unlocks and exact serialized parameters. 24 illustrated summon portraits cover 42 selections; Fey shares animal art while retaining its own spell/recipe. Includes Fire Shield warm/chill, five Protection from Energy types, abilities, curse modes, Blindness/Deafness, Command, Eyebite, Spirit Guardians and shared wall forms/sides.
- `skin/manifest.json`, `skin/charcoal-ui-skin.blend` and `SKIN.md`: panel 64px/inset8, slot48/inset6, button64×32/inset6, tooltip64/inset6 and requested states. Corner pixels stay fixed; tile edges and stretch solid centres only. Text remains live.
- `overlays/manifest.json`: accepted independent 28px pixel border. It remains available alongside the separate new Blender skin candidate.
- `cie28-runtime-art.zip`: lean art and mapping payload; masters, old WebPs and Blender source stay out of runtime media.
- `PACKAGE_INDEX.json` and `authoring/expanded-delivery-checks.json`: file hashes and completed validation. The full archive also contains original inputs, saved masters, references, exact prompts and the existing CIE pipeline snapshot.

## User decisions and production ownership

Keep the selected **CIE28** style and 28px native images, despite the other document's preferred 64px icons. Use integer nearest-neighbour scaling, separate frames and zero-gap touching slots. Final game scale remains undecided. Preserve recovered portraits and existing weapon/material substitutions. Environment interactions stay world sprite plus action verb, not new inventory/actionbar buttons.

Use the current authenticated media installer and presentation ownership. Refresh native ContentRefs/contract hashes; do not rename keys silently, infer identities from labels, insert runtime aliases or create another registry. Attack inherits equipped weapon artwork; the shared generic illustration is fallback only. Summoned/Tile Residue shared icons are fallback status illustrations with explicit labels, not newly invented mechanics. Keep the original Charmed/Bane VFX and the separate overhead condition-marker system intact.

Configuration-supported choices are distinguished from currently discovery-exposed options. Fire Shield is warm/chill; Protection from Energy does not include Poison. Stone offers panels only; Ice/Force panels or dome; Fire/Thorns straight or ring; Wind keeps path placement. Numeric geometry and target selection use UI labels/targeting rather than more textures.

The artwork and package are complete for forwarding. Review the newly added choices/skin, then production owns bindings, shared-widget integration and actual HUD scale testing. No thread messages were sent.
