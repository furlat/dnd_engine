# NDClient group D — new icons and portraits copied

9 October 2026. User-authorized artwork preparation under the
[single implementation plan](../NDCLIENT_IMPLEMENTATION_PLAN_COMPLETE_2026-10-08.md).
This records the completed copy, not implemented UI or an additional runtime catalog.

Source: [/mnt/c/Users/tommaso/Documents/assets/dnd-engine-icons-and-portraits/README.md](/mnt/c/Users/tommaso/Documents/assets/dnd-engine-icons-and-portraits/README.md).
Destination: `/home/tommaso/Dev/NDClient/.media/ui/`, with `icons/smooth48/` and
`portraits/192x256/` folders and readable filenames; ignored by Git. Originals remain untouched.

## Selected banks and assignments

| Bank beneath source `banks/` | Included | Existing assignment owner |
|---|---|---|
| `ui-icons-bg3-glyphs-2026-10-07` | 594 images; 620 native keys; 103 choice records | `replacement-bindings.json`, `choice-bindings.json`, `manifest.json` |
| `portraits-bg-study-2026-10-08/full-matrix-v2` | 312 player portraits | `production-lookup.json` |
| `portraits-bg-study-2026-10-08/white-expansion` | 120 current wardrobe-v2 player portraits | `production-lookup.json` |
| `creature-portraits-bg1-2026-10-08` | 229 NPC/source portraits | `production-lookup.json`, `manifest.json`, `ROSTER.md` |

The NPC lookup retains **43 exact existing `contentRef` / `rigId` assignments**.
The other **186** entries remain identified by their source art keys, available
for later explicit NPC selection; no content IDs are fabricated. The **432 player
portraits** remain selectable character/future-NPC art. Names and class/species
tags describe the pictures, not a new gameplay restriction or implemented class.
Existing manifestation/alias evidence remains in the original NPC manifest.

The replacement table's intentional icon aliases are retained. Choices resolve
through their exact `iconKey` and that table; the older `file` values carried in
choice provenance are not a reason to copy old variant-icon artwork. The full
source records are preserved without changing their meaning.

## Production-size copies

**Final user selection: smooth48 icons and 192×256 portraits only.** The initial
multi-format intake was broader than needed. The 1,188 local smooth144/CIE28 icon
copies were removed after checking other intake references, freeing 15,207,173
bytes. Originals and source assignment metadata remain unchanged. The 594
smooth48 icons occupy 2,387,494 bytes and preserve premultiplied-alpha Lanczos
downsampling with no baked backgrounds, borders, cooldowns or recoloring.

The comparison revealed that the classic 110×170 export changes the original
3:4 aspect ratio and crops the sides. Ashhook's master is 1086×1448; its classic
crop is `[74, 0, 1011, 1448]`, removing parts of the ears. The user therefore
selected the existing **192×256 smooth RGB export** for every portrait.

All **3,305 other local portrait variants were removed**, freeing 51,736,680
bytes after checking other intake references. Keep a single portrait image per
identity. Smaller views scale it; specific UI slots may deliberately crop on need.
Do not pre-export another size collection or reinterpret different aspect-ratio
crops as simple resizes. Originals and the exact assignment lookups are unchanged.

The preparation tool defaults to `--portrait-role preview` (192×256). The saved
choice in `.runtime/portrait-size-review/choice.json` records the explicit chat
decision; the review page now displays only retained images.

## Actual copied size and checks

- **1,255 final PNG payloads / 65,509,677 bytes (62.5 MiB)**: 594 smooth48 icons
  and 661 portraits at 192×256. Portrait artwork alone is 63,122,183 bytes.
- **18 exact source-reference snapshots / 8,555,513 bytes (8.2 MiB)**.
- Combined A/B/environment/UI artwork: **2,804,788,918 bytes (2.612 GiB)**.
- Earlier intake checked source images against delivered
  manifests. All copied bytes verified; derivative source hashes and operations
  recorded. All expected image and reference paths exist; no media tracked in Git.
- Small smooth-icon and portrait samples inspected. This is not a claim that the
  absent production HUD has been visually accepted.

Tool: [`prepare_ui_assets.py`](/home/tommaso/Dev/NDClient/tools/prepare_ui_assets.py).
Receipt: [summary.json](/home/tommaso/Dev/NDClient/.runtime/ui-assets/summary.json),
`files.jsonl`, `references.jsonl` and `authoring-reference/` in that same directory.
The receipts associate source bank/key/role with copied payload; source lookups
remain the assignment authority rather than a second handwritten binding system.

Excluded: full-resolution masters, face-review crops, reference/review pictures,
rejected versions, ZIPs, stopped `full-matrix`, earlier icon/portrait generations
and `white-expansion-clothing-v1`. The last contains earlier outfits for the same
120 people, not 120 additional identities. They remain preserved at source.
