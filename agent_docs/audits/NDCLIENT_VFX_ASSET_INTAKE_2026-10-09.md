# NDClient existing VFX intake — 9 October 2026

## Replacement delivery — current intake

The Factory completed the selected 23 families plus Sleep, Burning Hands,
Thunderwave, Color Spray and Ice Knife's burst. **Copy complete.** The entry
point for editable client data is `NDClient/authoring/catalog-index.json`.
Artwork uses named spell/component directories directly. The raw localized
Factory manifest and bank source manifests are intake provenance under
`.runtime/vfx-replacements/`. Original source:
`/mnt/c/Users/tommaso/Documents/assets/VFXFactory/exports/selected-23-completion-20261009/delivery/HANDOFF.md`.

- 28 spell families, 193 paired banks, 400 unique media identities.
- All 38 previously pending XYZ references covered, including 32 shared
  ground-fire/burning-Web aliases. Aliases reuse their delivered bank.
- Paired packets: 1,106,899,490 bytes (1.031 GiB). Manifests and newly needed
  preserved/live resources bring the selected copy to 1,323,523,723 bytes,
  before the localized entry manifest. These are on-disk bytes, not GPU residency.
- Preserved flat projectile/condition pages, casting resources, procedural
  lightning textures and Wind/Ice/Thorns operator meshes/textures are included.
  Existing installed files are reused; modular accents select the full V1.3.
- Ten superseded frigid-air pages (1,615,387 bytes) from the earlier ordinary
  intake were removed from the local copy and receipts. Their only owner now
  uses the new directional paired bank; original engine files remain untouched.
- No legacy XYZ or replaced old packed pages are selected. The source manifest
  retains historical `production_storage`; the local manifest removes it only
  for replaced layers. All delivered bindings, recipes and direction/window/
  coalescing data are retained. Live file paths are localized; the sources remain
  untouched. Conditions remain in their separate existing folders.

`tools/prepare_vfx_replacements.py` reproduces this intake from the delivery,
Factory and engine roots with `--copy`. It does not re-export, resize, resample,
repack or process checksums. `.runtime/vfx-replacements/summary.json` and
`files.jsonl` record the result; ordinary-copy receipts are reconciled with it.
The original handoff stays at source, preserving its linked spell contracts and
export evidence without duplicating its old bank lists into the installation.

Copy verification resolves every selected bank packet, preserved page, live
resource and operator texture sibling; no paths are missing. Packet sizes match
their source manifests. Current receipts report zero pending XYZ references and
zero deferred selected families. Artwork and local records remain Git-ignored.
This was a copy check, not another export/checksum or visual validation pass.

The delivered Fireball keeps 46 frames at 24 FPS. Other rates stay authored.
The appearance/geometry planes, radiance, matrices, crop and pivot must be
consumed together. Historical wall halves in one coalescing group are one draw;
geometry alpha is part of the normal, not opacity; additive RGB at zero opacity
must survive. Ice Knife's burst is now enabled in the tracked client copy, keeping
its delivered debris/flash semantics. This preparation does not claim renderer
implementation or visual acceptance.

## Editable authoring and final organization

The original engine authoring was imported once through its existing effective
exporter into tracked `NDClient/authoring/`. Original Pygame JSON was not edited.
All 149 spell/effect drafts, 160 condition recipes and 236 condition media layers
remain present. The selected closure contains 1,054 media identities, 392 paired
replacement selections, 193 shared banks and 1,540 resource bindings.

`spells/` contains recipes; `catalog/` contains the existing action/condition/rig
and related fields; `media/{definitions,storage,banks}/` separates existing
identities, selections and shared capture metadata. `world.json` owns spatial,
construction, concentration and deposit maps once; the catalog index references
those values rather than creating duplicate editable owners.

Artwork now uses `vfx/{spells,areas,conditions,actions,shared}/` with readable
spell/component names. Modular accents still share the complete V1.3 library.
The effective recipe walk found 50 omitted child-outcome/image dependencies
(2,227,216 bytes); only those referenced files were added. No legacy XYZ copied.

The source schema accepts the assembled client copy. Five focused authoring
checks cover replacement timing/storage, components/directions and single-source
world edits; all 65,260 media references resolve. The importer refuses to
replace existing client authoring. Complete application release assembly and
rendering remain future implementation, not implied by these data checks.

## Earlier ordinary-media pass

The following records the previous partial intake. Its deferred list is resolved
by the replacement delivery above; its counts describe that earlier pass only.

Scope: copy existing spell, condition, action and area VFX into the recreated
NDClient repository, excluding the 23 re-exported spell families and every
retired XYZ bank. This is asset preparation, not renderer implementation or
visual acceptance. Original artwork and canonical engine bindings stay unchanged.

## Completed copy

- 3,582 source files; 3,508 unique payloads / 431,848,969 bytes (411.8 MiB).
- 3,481 newly added payloads / 421,983,641 bytes; existing installed payloads reused.
- 201 exact source snapshots / 99,174,770 logical bytes.
- 126 spell drafts preserved, 23 deferred; 160 condition recipes and 236 condition-layer definitions.
- Category files: 646 spell, 844 condition, 1,856 area, 94 action and 142 shared.

The initial copy was completed before the folder correction. All current receipt
paths now point to the named category files. No missing referenced files or unbound
selected sheets. Zero media or local receipts are tracked in Git. These checks
confirm the intake, not runtime rendering or artistic acceptance.

## Organization

Under `/home/tommaso/Dev/NDClient/.media/vfx/`:

| Folder | Contents |
| --- | --- |
| `spells/` | Ordinary spell casts, hands, deliveries and impacts. |
| `conditions/` | Condition application, maintained effects, removal, markers and material dependencies, including spell-induced conditions. |
| `areas/` | AoE and persistent world effects, constructions, ground effects and deposits. Grouping follows the native spell catalog and world bindings. |
| `areas/reexports-23/` | Current Factory replacement batch; see the current intake above. Its grouping also includes directional/single-target effects without changing their native semantics. |
| `actions/` | Class/action effects, weapon trails, movement/reaction and body-release dependencies. |
| `shared/` | Artwork required across categories and existing modular casting layers. |

Each category's `intake-index.json` is a generated copy receipt identifying existing
owners, assets, file locations and omitted retired banks. It is not a new runtime
binding catalog. These paths contain the actual artwork with meaningful source
filenames. The rejected object store has been removed; there is no checksum or
deduplication step. Shared dependencies keep their readable source subfolders.

Canonical source snapshots and detailed receipts are under
`NDClient/.runtime/vfx-assets/`. Full original JSON retains pivots, facing banks,
frame rectangles, timing, cast sockets, materials, conditions and lifecycle
relationships. A historical asset ID in those snapshots does not mean its artwork
was installed. The current engine/source documents remain their authority.

## Deferred assets

The 23 spell families come from the 17 `new_families` entries in the existing
replacement comparison, plus Fireball, Fog Cloud, Darkness, Cloudkill, Incendiary
Cloud and Stinking Cloud. Exact IDs are recorded in `selection.json` and the
deferred folder. Only dependencies independently needed by included effects may
be retained; an excluded spell's standalone cast is not a copy root.

The inspection also found retired XYZ dependencies outside that batch:

- Sleep's area effect.
- Burning Hands and Thunderwave areas.
- Color Spray's area layers.
- Ice Knife's burst.
- Existing ground-fire and burning-Web layers.

Their recipes and unaffected dependencies are retained, but the retired banks
are not copied, converted or used as fallbacks. The user reports adding the five
spell cases to the Godot agent's handoff. Ground-fire/Web dependencies remain
separately identified in the copy receipt. Conditions retain independent ownership
even when their originating spell's area export is deferred.

## Reproduction and evidence

The offline tool is `NDClient/tools/prepare_vfx_assets.py`. Run with
`--engine /mnt/c/users/tommaso/documents/dev/dnd_engine` for selection, adding
`--copy` to copy. It follows the explicit bundle list in `game/animation_data.py`,
the existing condition sources, spell/child drafts, world bindings and action
media. It does not scan the entire asset archive or regenerate SDKs.

`summary.json`, `files.jsonl` and `references.jsonl` record source-to-destination
locations and source references. No checksum fields or hashed storage are needed.
Media and local receipts are Git-ignored. No resizing, recoloring, packing or
playback-rate change is included.

The scope reviewer checked family exclusion, shared dependencies, condition
ownership and explicit XYZ gaps. This does not certify future renderer behavior.
