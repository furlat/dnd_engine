# Character, equipment and UI asset inventory — 24 September 2026

This is an actionable dependency inventory, not deletion or rebaking authority. No production code, media or installed package changed. It uses the existing 62,769-file `/home/tommaso/Dev/neurodragon_art/art-manifest.json`, baseline `508f5f8d38cc2e6982b73c44ee7f911b794c042a`. Sizes and content identities are copied from that manifest; no images, source packs or raster corpus were scanned or hashed.

## Production decision

**Retain 461 character files, totaling 61,571,143 bytes.** They cover all eight initialized rigs, every installed modular appearance/equipment category selected by supported native options, and the actually selected attack overlays. A further **67 spell-owned actor overlay sheets, 4,727,083 bytes**, are cross-referenced as production dependencies; the VFX inventory should merge these claims rather than count them twice.

Three installed character overlays are not selected by the present consumers:

| Backup/source-only candidate | Manifest bytes | Reason |
| --- | ---: | --- |
| `game/assets/neuroclient/spritesheets/Magic2/Attack5.png` | 223,972 | Selected casts use their explicit colored `sourceSheet`; no supported equipped item selects Magic2 |
| `game/assets/neuroclient/spritesheets/Slash1/Attack5.png` | 118,505 | Current offhand Attack5 profile has no slash layer; no selected cast/child recipe uses this original sheet |
| `game/assets/neuroclient/spritesheets/Slash2/Attack5.png` | 118,505 | Same unselected Attack5 overlay case |

Retain those originals in the source archive. Their omission is a proposed production-pack decision, not permission to delete them from the current working tree. A positive dependency from another audited consumer overrides a negative claim here.

## Why these are runtime dependencies

`game.encounter_play` initializes every JSON rig binding (`game/encounter_play.py:109`), resolves actors from disclosed historical state and preloads standing poses. The normal scene path loads **all eight facing rows** (`game/scene.py:55`), not merely the current four camera views. Motion, attacks, equipment transitions, body actions, conditions and life changes request further clips through `game/choreography_draw.py:39` and `game/animation_draw.py:215`.

`resolve_actor_layers` selects root body/hair/beard from `AppearanceConfig` and equipment from the supported native item-visual ledger (`game/animation_data.py:70`). It respects active weapon sets, hidden-item policy and variant tints. Fixed rigs use baked body/shadow categories; they do not acquire modular equipment layers merely because the creature owns an item. Goblin attack slashes are the deliberate shared root-sheet exception.

The inventory follows these selections, rather than treating every resource/catalog row as used or treating the default fighter/sorcerer/goblin scene as the whole game. Every selected body clip has a concrete consumer:

| Clips | Consumer |
| --- | --- |
| Idle | Standing/rest scene |
| Run | Ordinary movement, including speed-modified movement |
| Rolling | Jump and supported ground-save hops |
| TakeDamage | Damage and forced movement |
| Die | Death, falling asleep/prone and reverse waking/recovery |
| Taunt | Equipment changes and enabled body actions |
| Kick | Shove |
| Attack1–Attack6 | Authored weapon profile variants and casts |
| Special1 | Authored casts and body actions |

All 14 root clips require their declared **15 frames and eight rows**. The current loader copies each selected complete row, including appearance layers that a later action sample hides. Do not discard equipment animation sheets because that item happens to be hidden during one sampled cast. All-frame/root-layer requests were checked against the actual in-memory loader request function.

## Installation bundles and sheet sizes

| Suggested installation bundle | Selected physical sheets | Bytes | Logical cell size |
| --- | ---: | ---: | --- |
| `character.modular` | 373 | 52,284,914 | 128×128 |
| `character.demonbeast01` | 16 | 1,140,454 | 128×128 |
| `character.demonbeast02` | 16 | 1,220,692 | 128×128 |
| `character.demonbeast03` | 16 | 1,229,273 | 128×128 |
| `character.goblin01` | 14 | 1,782,360 | 128×128 |
| `character.greywolf` | 6 | 273,994 | 64×64 |
| `character.orc01` | 14 | 2,856,207 | 128×128 |
| `character.skeletonarcher05` | 6 | 783,249 | 128×128 |
| Existing spell actor-overlay owners | 67 | 4,727,083 | 128×128 |

The current logical sheet layout is already 15 columns × 8 directions: 1920×1024 for 128px cells, 960×512 for Wolf's 64px cells. These dimensions come from bound rig metadata and loader rectangles, not a new image inspection.

The modular bundle contains 26 installed identity/equipment categories × 14 clips = 364 sheets, plus nine selected Slash1/Slash2 sheets. Preserve separate tintable layers and separate shadow data. The fixed rig bundles contain selected vendor body/shadow sheets, not the whole purchased packs or precomposited vendor backups. Demon Attack6 aliases Attack1; Wolf Attack6 aliases Attack1. Preserve aliases without making physical copies. Goblin reuses root Slash1/Slash2 Attack1 and Attack2; do not duplicate these into its bundle.

The existing manifest reports one exact duplicate pair among the selected files: Misty Step's actor cast sheet and `persistent_spells/body-cast.png`, each 90,754 bytes. A packaging deduplication could retain one payload with two resource aliases. This is existing-manifest evidence only, and the saving is small.

## Fixed sizes to bake: none for actor bodies or their attached overlays

Preserve the original canonical cells and registration. There is no universal final actor display size:

```text
height = source cell height × appearance.visual_scale × condition.scale
         × (128 / 64) × camera.zoom
width  = corresponding source width × the same factors × appearance.visual_scale_x
```

The consumer is `game/animation_draw.py:496`; contacts acquire native appearance and condition scaling in `game/combat.py:69`. Camera zoom is one of 0.15, 0.35, 0.5, 0.75, 1.0. Native appearance scale and width are independently configurable in `(0, 4]`. Enlarge/Reduce currently uses 1.175/0.75 and interpolates transitions. Real premades already differ: Barbarian scale/width 1.1, Sorcerer 0.9, Fighter 1.0. Goblin appearance has another authored scale.

Therefore:

- Keep neutral source pixels, original pivots/body/socket positions, all facing rows and all selected frames. Do not bake one default outfit, tint, condition or zoom into production body sheets.
- Existing per-layer/per-clip sheets are a sensible production unit. Bundle them for installation; do not explode them into hundreds of standalone frame files.
- Lossless transparent trimming/page packing is a possible later storage improvement, with logical cell size and per-frame offsets preserved. The current body loader expects a regular sheet, so trimming requires an explicit loader adapter and output comparison. No savings estimate is asserted without examining pixels, and no trimming was performed.
- No need for an all-outfit atlas or a new per-character rendering class. The combinatorial identity/gear space is intentionally composed at runtime.

## Missing supported choices are a coverage gap, not unused assets

The native authored inventory contains **76 mechanically supported base categories and 205 named variants: 281 options**. The only unsupported mechanical category is Rusty Blade, which is excluded. Its Melee2 picture remains needed by other supported equipment.

For every one of the 281 options, this audit constructed its retained visual item, called the actual `resolve_actor_layers` with its primary native slot and appropriate weapon set, and passed the result to `_actor_media_requests` for the selected clips:

- **65 options bind fully** to installed modular body/gear sheets.
- **216 options select one or more missing sheets** and the actual request function raises `missing required rig layer`.
- Combined with allowed appearance choices, this is **81 absent modular categories × 14 clips = 1,134 missing binding requests**. These are shared missing categories, not 216 independent new defects or 1,134 new features.

The dependency ledger names the exact options, layers, missing clips and failure messages. Typical missing supported items include weapons using Melee4–Melee25, uninstalled armor/head/hand variants and other bow/shield/shoe variants. This is not merely permissive legacy vocabulary: the retained item resolver reaches these layers through existing mechanical factory bindings and authored variants. Importing them was not authorized by this inventory task.

Appearance probes additionally established:

| Native appearance option | Present behavior |
| --- | --- |
| NakedBody, NakedBody2 | Bind |
| NakedBody3 | Fails: missing root Idle sheet |
| Head10, Head22 | Bind |
| Head1, Head9, Head16, Head17 | Fail: missing root Idle sheet |

The existing Barbarian premade explicitly names Head17 (`dnd/content/characters/premades.py:265`), so the gap is not purely an arbitrary hypothetical choice. The root skeleton warrior uses NakedBody2; the premade skeleton archer uses its separate fixed rig. Keep both.

Unbound legacy rig-table categories such as mounts/backpacks are not promoted to production dependencies simply because they are named. No installed files for those categories occur in this manifest. Their source packs remain source material. Fixed rigs also legitimately lack some humanoid action clips; the inventory records their capabilities, rather than requiring every rig to grow all 14 clips. Existing ranged binding can use an explicit Idle body with a reported gap; missing melee clips cannot bind, and missing ordinary modular layers raise instead of silently substituting art (`game/attack.py:252`, `game/animation_draw.py:233`).

## Portraits, icons, UI and fonts

The installed manifest contains no portrait, spell-icon, UI-image or font files. Native `portrait_key` remains metadata; the current encounter UI draws text, rectangles, target indicators and actor labels, not NeuroClient portraits or action icons. Do not import an old UI asset catalog as an implicit packaging dependency.

Fonts are real dependencies outside this licensed-art manifest:

| Consumer | Current selection | Current WSL owner |
| --- | --- | --- |
| Labels/menu/logs/debug | `pygame.font.Font(None, 18)` | Pygame `freesansbold.ttf` |
| Target count | `pygame.font.Font(None, 17)` | Same Pygame font |
| Floating damage/healing | `SysFont("monospace", 20, bold=True)` | OS resolves `/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf` |
| Floating badges | `SysFont("monospace", 16, bold=True)` | Same OS font |

Font paths were resolved through the current Pygame font API. They were not hashed/copied into the art package. Dynamic labels and numbers should not become a fixed image atlas. OS font resolution is an external deployment dependency and can affect cross-platform appearance; changing that selection is separate work, not a silent packaging adjustment. Developer-only `animation_preview` sans fonts are outside the `encounter_play` runtime.

## Machine-readable outputs

Directory: `.runtime/asset-inventory-20260924/characters/`.

- `files.jsonl`: **531 per-physical-file decisions**. Includes manifest path/bytes/hash, production boolean, owners, real consumers, needed frame/row lists, scale classification, existing packaging, suggested bundle and evidence. 528 true, three backup/source-only false; 67 true rows intentionally overlap VFX ownership.
- `physical-files.json`: the same records as an indented array.
- `bundles.json`: complete path lists and sizes for the eight character bundles and cross-referenced spell actors.
- `rigs.json`: all eight rig identities, creature bindings, semantic/source clip aliases, frame counts, registration and missing clip capabilities.
- `clip-consumers.json`: selected clip-to-runtime-owner map.
- `equipment-options.json`: all 281 supported base/variant selections, resolved layers and actual consumer probe result.
- `modular-category-options.json`, `missing-dependencies.json`: exact installed versus absent categories and clip requests.
- `appearance-request-probes.json`, `all-rig-request-probes.json`: nine permitted body/head option probes and all eight fixed/default rig request probes, without image IO.
- `unsupported-mechanical-source-options.json`: Rusty Blade and its existing explicit reason.
- `identical-files-from-manifest.json`: duplicate evidence using existing manifest identities only.
- `ui-and-fonts.json`: UI non-dependencies and concrete external font dependencies.
- `summary.json`: counts and scope. `build_inventory.py` reproduces the main dependency records with the project UV environment and no media IO.

All eight initialized rig request probes pass for their existing default layers and mapped selected clips. These are metadata/selector checks, not a claim that every spell/creature combination has been rendered or all broader game tests pass. No broad test suite was rerun. Missing resources were neither substituted nor counted as installed production files.
