# Assets

**Current copy rule:** use original meaningful filenames in organized family/source
folders under `NDClient/.media/{smallscale,environment,ui,vfx}/`. The rejected
`objects/` store was removed. No checksums, deduplication machinery or encoded
filenames. Source authoring/bindings remain unchanged.

**Current Smallscale selection — 9 October:** use exactly
`NDClient/.media/smallscale/modular/` for the complete unified Fantasy Character
Creator V1.3 archive (3,888 source sheets), and `smallscale/authored/` for all ten
owned non-modular packs (7,351 selected source sheets), including creatures not
implemented by the backend. Preserve original layer/action/creature filenames.
The older 1,281-sheet modular subset is no longer installed separately. Its 50
pixel differences matched old NeuroClient; both supplied V1.3 vendor packages
agree on the replacement artwork. This is source-version reconciliation, not
permission to preserve those differences as overrides. The 18 GunFire PNGs in
the vendor archive are fully transparent; file counts do not count usable effects.
Existing rig source references reuse the full pack files. Only the 98 genuinely
derived animal/dinosaur shadows have additional named files within those packs.
Modular spell accents use the same V1.3 library. Source archives, engine artwork
and canonical bindings remain unchanged. No new creature/action bindings were made.

**9 October VFX copy completed:** existing spell, condition (including spell-induced),
area, action and shared effects are organized under `NDClient/.media/vfx/`.
The 23 re-exported spell families are deferred in `areas/reexports-23/`;
all retired XYZ banks remain excluded, including dependencies outside those 23.
The [intake record](agent_docs/audits/NDCLIENT_VFX_ASSET_INTAKE_2026-10-09.md)
records the category layout, exact source owners and remaining replacement gaps.
3,582 source files resolve to 3,508 unique payloads / 431,848,969 bytes (411.8 MiB),
with 421,983,641 newly added bytes after reusing existing installed payloads.
Artwork now lives directly in those readable category paths.
201 exact source references retain complete authoring (99,174,770 logical bytes).
No renderer, binding, frame-rate or image changes were made. The five additional
spell cases still needing non-XYZ replacements are Sleep, Burning Hands,
Thunderwave, Color Spray and Ice Knife's burst; the user has added them to the
Godot handoff. Ground-fire/burning-Web banks are also listed as pending.

**9 October VFX replacement policy — user correction:** the old spell/VFX XYZ
banks are abandoned and fully substituted by new exports. Do not migrate them,
convert them offline for the new client, or use them as a temporary fallback.
The census below describes historical/current engine storage, not an import list.
Original files remain preserved; this instruction does not authorize deletion.
Retain the full authored behavior, including condition application/sustain/removal,
and update media references through their existing owners when replacements are
selected. The preferred direction is depth/normal coverage across world VFX,
including conditions, as the exports become available. Coverage is not yet a
universal per-layer requirement or an all-assets-first development gate. Registered
placement, layer/elevation composition and lighting still need correct consumers;
extra channels alone do not repair those systems.

**Earlier 9 October spell/VFX inspection — before the authorized copy:** the user next
asked to inspect existing engine spells while replacement exports are arriving.
The [registered-media census](.runtime/spell-asset-review-20261009/inventory.json)
and [asset rows](.runtime/spell-asset-review-20261009/assets.csv) follow the 32
explicit bundles in `game/animation_data.py`: 1,112 media declarations, 1,090
storage records, 186 legacy surface phases, 4,717 existing referenced files and
3,862,518,298 on-disk bytes. Of these, 2,987,855,390 bytes are 250 surface ZIPs;
874,662,908 bytes are 4,467 PNGs. Counts deduplicate paths, not file content.
This measures registered media storage, not the whole future copy closure or GPU
residency; extra caster/noise/condition/action resources are separate dependencies.

The [replacement comparison](.runtime/spell-asset-review-20261009/replacement-candidates.json)
links the Factory's current `paired-family-completion.json` (108 banks, not 108
spells) and six core exports. The author reports verified transport for those
packets; this inspection confirms their manifest availability, not visual parity
or runtime acceptance. Corrected/calibrated/retry paths come from that completion
index, not the older partial audit. The five compact cloud candidates preserve
448×448 source pixels with 896×896 authored display and separate apply/hold/clear
semantics. Keep the accepted Fireball v4 (26,675,421 bytes) distinct from the newer
official-project candidate (27,489,227 bytes); no automatic replacement was made.

Keep spell recipes, body/cast semantics, sockets, palette/material instructions,
condition media and `world_bindings.json` spatial lifecycles with the artwork.
Several apply/hold registrations share the same file: union paths before summing
or copying. Current compact geometry types exist but none of these stored media
registrations yet select the new `geometry` field. Depth/normal channels need
their paired registration and raw-byte interpretation, not ordinary colour-image
loading. Preserve authored rates and timing; Fireball's accepted 24 FPS does not
authorize a blanket conversion from 32 FPS. This earlier inspection copied no VFX
and changed no renderer, artwork, binding or native behavior. The subsequent
authorized copy is recorded above.

**9 October environment metadata supplement:** the supplied
`fantasy-unified-catalog/data-authoring-2026-10-09/` records/evidence are copied
unchanged into NDClient's ignored environment references: 465 files / 8,810,760
bytes, covering all 60 named requests. The [environment handoff](agent_docs/audits/ndclient-environment-assets-20261009/README.md#missing-metadata-received--9-october)
maps the records to their existing owners and preserves the unresolved physical
door mounts, fractional timber-flight rise and estimate qualifications. No new
images or candidate bindings were installed; this is authored data for later use.

**9 October group D:** the [new icon/portrait intake](agent_docs/audits/NDCLIENT_UI_ASSET_INTAKE_2026-10-09.md)
is complete in NDClient's ignored media store: 594 icons covering 620 exact keys
and 103 choices, plus 661 portraits (43 existing creature assignments, 186
unassigned NPC/source portraits and 432 selectable player portraits). The user's
final selection is **smooth48 icons and 192×256 portraits only**. Local
smooth144/CIE28 and other portrait-size copies were removed; originals remain
unchanged. Smaller views scale this same portrait image; deliberate UI crops
may be applied as needed. Source lookups and manifests are preserved exactly.
Final UI artwork is 65,509,677 bytes; all prepared artwork is 2,804,788,918 bytes.
Full-resolution masters, old banks, review images and earlier duplicate outfits
remain at source. Renderer/UI implementation has not resumed.

**9 October environment migration information:** the [consolidated handoff](agent_docs/audits/ndclient-environment-assets-20261009/README.md)
joins current engine selections with source registrations, prefab/adjacency
records and corrected editor height/contact/layer semantics. Use those existing
inputs regardless of whether they are in the unified art catalog. Its tables
locate selected source metadata and actual registration values; they are audit
documents, not replacement runtime bindings. The subsequent authorized copy is
complete: 7,735 unique environment PNGs / 585,362,999 bytes and 3,687 exact source
references / 182,498,742 bytes, including the metadata supplement above. Receipts live in the ignored
`/home/tommaso/Dev/NDClient/.runtime/environment-assets/`; artwork shares the
named `.media/environment/` folders. The combined A/B/environment artwork is
2,739,279,241 bytes. Arena/crowd media, project/archive files and review composites
are excluded; shared adjacency records are retained. Desert remains deferred.

**9 October NDClient character intake:** the human initially authorized A
(Smallscale modular) and B (all owned fixed-creature sheets), followed by the
environment copy above, for the recreated WSL repository.
Original sources and existing bindings remain unchanged. The complete current
plan §7.2 uses one ignored `NDClient/.media/` store, served later through `/media/`;
this supersedes the historical `public/media` instruction below and avoids Vite
copying artwork into `dist`. The repository README and ignored A/B intake receipt
record exact source members, counts and sizes. Copying all B sheets does not
create new mappings or override the existing mapping study/canonical rig JSON.
The human selected B's combined/with-shadow sheets instead of duplicate
shadowless body sheets. Omit the latter when their corresponding combined source
exists; retain separate authored effects and shadows. A is unchanged. Originals
stay in their source archives; this selection does not rewrite existing bindings
or mean a shadow-selecting shader has already been implemented.

| Location | Purpose |
| --- | --- |
| `/home/tommaso/Dev/neurodragon_art/` | Preserved full installed-art snapshot and inventory. Never prune or overwrite it to make a production build. |
| `/home/tommaso/Dev/neurodragon_art/sources/` | New original packs and full authored exports, kept privately. Existing external authoring projects stay in their own locations. |
| `/home/tommaso/Dev/neurodragon_art-production/` | Private production Git LFS repository: selected frames, shared payloads and packed sheets/geometry. Build separately from the archive. |
| `game/assets/` | Local installed production art. Ignored by Git; not the place to keep the only copy of an original. |
| `game/data/` | Public authored behavior, bindings, registration and schemas. The asset installer must not overwrite these. |

Keep pixels, binary geometry and generated previews private. Keep code and
authored JSON contracts public. Put review output in `.runtime/` or `output/`.
Importers update media registration/storage, never rewrite selected recipes.

October 8 ordinary solid-wall destruction reuses four original Unity debris
banks: 64 exact RGBA frames packed without resampling, 12 FPS, source pivots and
1300 ms cleanup. Source assignments and consumer requirements are in
[the Pixi wall handoff](agent_docs/WALL_BREAKABILITY_PIXI_HANDOFF_2026-10-08.md).
Preserved payloads and nine paired-observer native recordings live privately in
`sources/solid-wall-debris-20261008/`; production copies are under
`game/assets/environment/wall_debris/`. All prior manifest entries and approved
window media remain unchanged. Pygame is retired; browser acceptance is pending.

October 8 exception: the human requested a new single-view Fireball proof
at **24 FPS**, preserving its two-second duration. Follow
[the dedicated export handoff](agent_docs/FIREBALL_SINGLE_VIEW_PIXI_HANDOFF_2026-10-08.md)
for the paired eight-byte/depth-layer contract. Preserve the 32 FPS installed bank
and full originals. The export and standalone Pixi proof are now delivered; this
is not a production installation or global FPS conversion. The human selected
**fireball-single-view-24fps-v4** as the demo/NDClient default. Its complete delivery
is preserved in `sources/fireball-single-view-24fps-v4/`; the demo uses a physical
ignored copy under `.runtime/ndclient-fireball-proof/media/`. The handoff pins its
manifest and retimed source/light curve (46 frames, 24 FPS, 1.916667 seconds).
Keep v1–v3 preserved; retain v1 as historical
evidence and the installed 32 FPS bank unchanged. No external agent messaging. See the
[proof receipt](agent_docs/audits/ndclient-plan-20261008/FIREBALL_PROOF.md).

The human resumed NDClient's foundation repair later on October 8. The
[environment asset recovery handoff](agent_docs/NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md)
now governs source recovery: complete assemblies and compatibility records must
be consumed, not just copied individual sprites. The current private browser
release exists; its presence does not certify rendering or compatible composition.
The [master §§0.3–0.4 and §5.4](agent_docs/NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md)
record actual status, settled contracts and full selected-family release requirements.
A read-only installed-tree census found 11,080 files / 4,669,872,861 bytes, including
historical/unselected files. Do not confuse that census, a scene's loaded pages,
or the partial 197-file copy with the complete resolved browser release.

NDClient's setup explicitly copies the selected private browser release
to `/home/tommaso/Dev/NDClient/public/media/<release-id>/`, ignored and untracked in
the fresh client Git repository. Add ignore rules before copying and verify zero
tracked media. Preserve originals and canonical authored JSON in their current
owners; do not depend on a symlink to an old checkout. The
[repository and copy runbook](agent_docs/NDCLIENT_ASSETS_AND_RIG_AUTHORING_2026-10-08.md#21-repository-and-local-copy-runbook)
also preserves NeuroClient/NeuroMapEditor references and the standalone proof.

October 6 player UI intake keeps the original CIE28 icon delivery and the
portrait-only exports unchanged. `devtools/import_ui_icons.py` registers selected
icons in `game/data/ui_media.json`; role-specific portraits use the same media
catalog and native `ContentPresentation.portrait_key`. The 56 existing player
portraits have 36×48 initiative, 48×64 HUD and 96×128 sheet exports; optional
artist repaints remain unselected. Full sources are preserved privately under
`sources/ui-pixelated-portraits-20261006/`.

The later summon/goblin handoff adds 41 exact creature portrait associations
(123 unchanged PNGs), stored in `sources/creature-portraits-20261006/` and installed
under `game/assets/ui_pixelated/creatures/`. `--creatures` validates the pinned
runtime archive, exact content and rig identities, body source hashes and all
three portrait roles. Animals and their fey instances use the same creature
descriptor. Older goblin identities are not aliases for the 17 new portraits.
The large artist authoring archive remains private and is not installed as game
media. Public Git receives bindings and provenance, never these images or clips.

October 4 spell-hand completion selects six unchanged original modular
`Magic2/Attack1–6.png` sheets from the existing NeuroClient authoring directory.
They are registered as `/support-spells/cast-hands/Magic2-AttackN.png`, installed
under `game/assets/support_spells/cast-hands/` and retained in the private
production release (1,496,267 bytes total). These support True Strike's real
weapon poses; existing exact shortsword/shortbow charges remain selected first.
Other newly enabled casts reuse already installed isolated casting sheets.

October4 production-gap intake preserves originals under
`sources/production-gaps-20261004/`. `devtools/import_production_gap_media.py`
installs116 selected files into the existing weather/solar, lightning and wall
bundles: eight Cone headings, four complete Call Lightning views and Wind's
isolated block response with its original mesh/texture. Source registrations
and hashes are in each bundle's `production-gap-source.json` and the
[intake receipt](agent_docs/audits/SPELL_GAP_ASSET_INTAKE_2026-10-04.md).
The human permits Cone's nearest-direction bank plus a small residual rotation;
this does not alter its native targeting or authorize arbitrary asset stretching.

October 2 Holds/Fear/Scorching sources are preserved under
`sources/holds-eefffc58e8c5/`, `sources/fear-eyebite-deb28a4f625f/`,
`sources/fear-diagonal-v7-20261002/` and `sources/scorching-isolated-v23-16a3b4f1525d/`.
Use their named `devtools.import_*_media` adapters and existing registered atlas
packer. Installed selections: Holds8pages/503,957bytes, Fear46pages/39,824,994bytes,
Scorching16pages/1,246,355bytes. Retain all camera banks/pivots and finite phases;
Holds has a one-frame quiet sustain, Fear a source-authored loop overlap, and
Scorching14 finite travel samples. Source archives include deferred counterparts;
they are not production bindings. Private install receipts are in the spell queue.

Wall of Fire retains its complete pinned delivery in
`sources/wall-of-fire-20261001/`. `devtools/import_wall_media.py` installs the
82 original atlas pages (31,027,806 bytes) into `game/assets/wall_media/` and the
private production repository. Application selects frames 0–47; hold selects
48–111 at 32 FPS, sharing the same pages. Keep all four native camera rows,
front/back layers, crop offsets and pivot. These pages already fit 128×64 tile
supports at pixel scale 1; do not apply the character rig's tile scale. Rings,
diagonals, fine XYZ occlusion and physical height registration remain undelivered.
Public phase registrations and the independently authored cast recipe live in
`game/data/wall_media/`; spatial composition lives in `world_bindings.json`.

New support-condition exports retain their 144 Hz originals in
`sources/support-batch-20260924/`. Use `devtools/repack_support_media.py` to build
separate 32 FPS production sheets, then `devtools/import_support_condition_media.py`
to install the selected group. Preserve durations, camera banks, pivots and crop
offsets; casting hands keep their rig frame rate. This packer handles billboards,
not paired XYZ/cloud banks. Recipes remain independently authored in `game/data/`.

Five maintained clouds now use two-second formation and two-second loops at
32 FPS from `sources/cloud-two-second-20260924/`. Import the five stationary
`cloud-two-second-surfaces-v1/<spell>/surface-manifest.json` entry points using
`devtools.import_persistent_spells.import_volume`. Source frames 0–63 become
application; 64–127 become hold, whose runtime start stays 0. Frame 128 is a
diagnostic duplicate, never playback. The optional rolling variants remain
archived and unbound; Cloudkill's rolling art has a fixed source +X bias.

Insect Plague retains `sources/cloud-height-companion32-v1/`. Production still
uses 24 ZIP banks containing matched RGBA/XYZ/ownership samples. Keep all three
coordinates; dropping Y prevents correct spherical clipping. Keep numerical
camera registration and crop pivots. Prior source banks remain in
`sources/short-cloud-loops32-v1/`, `sources/cloud-height-companion32-v1/` and the
previous releases; old XZ pages are in `sources/cloud-installed-before-xyz-20260924/`.

Fixed Fantasy windows preserve the full delivery in
`sources/fixed-windows-20261001/`. `devtools/import_windows.py` packs the approved
four-view selections into 66 production sheets/masks (21,128,454 bytes) under
`game/assets/environment/windows/`. These are copied into the private production
repository and included in its installer manifest. Public bindings remain in
`game/data/environment_art.json` and `game/data/window_media_sources.json`.
Keep uneven 24 FPS sample times, exact source pivots, selection masks, and both
parent-break variants; the after-insert variant prevents broken bars reappearing.

The October 1 passive environment batch preserves full sources in
`sources/environment-content-20261001/`. Its 53 native props use 306 additional
production PNGs (38,197,511 bytes) under `game/assets/environment/props/content-*`.
Use `devtools/import_environment_props.py --bank <authored-id>` for a bounded
selection, then the existing environment pager; preserve the accepted source's
12 FPS timing, frame count, pivots and row ordering. Installed and private copies
are included in `art-manifest.json`; the full local release now totals 4,945 files
and 2,858,909,585 bytes. Unselected/candidate art remains archived and unbound.

Install explicitly:

```bash
uv run --no-sync python devtools/art.py install --source /home/tommaso/Dev/neurodragon_art-production
```

Base release: `spell-fps32-20260924`, now extended by `fixed-windows-20261001`, following `cloud-two-second-20260924`
and the prior XYZ/support/cleanup releases. It contains **4,430 files / 2.669 GB**,
saving 1.616 GB (37.7%) from the preceding 4.285 GB installation. Selected media
for 248 spell asset records uses 32 FPS; actor animation and slower projectile
phases retain their authored clocks. Fireball's explosion uses 64 genuine samples
from its dense original. Full delivery sources are preserved in
`sources/spell-fps32-20260924/`. The five two-second clouds remain unchanged;
their complete XYZ archives occupy 636 MB instead of 1.963 GB.
Keep shared footpoint pages even when one consuming spell gets repacked.
Its paths require the matching frame registrations and hold lengths; the
original snapshot alone cannot replace this release. Normal game startup does
not install, scan or verify the asset library.

Keep the code revision paired with its art release. Preserve originals before
accepting a new delivery; regenerate production into a separate staging directory.
Private remote publication and removal from historical Git commits are separate
from ignoring/untracking the current files.

Detailed setup is in [PRIVATE_ART.md](PRIVATE_ART.md). Current packaging decisions
are in the [asset inventory](agent_docs/PRODUCTION_ASSET_INVENTORY_2026-09-24.md).

Fixed windows now retain the dense missing-frame delivery beside the original
sparse exports in `sources/fixed-windows-20261001/destruction-showcase/dense-production/`.
`devtools/import_windows.py` installs its112 directional sheets (128,033,920bytes)
and seven matching existing solid-wall banks. All source models/transforms remain
unchanged; dense bank times are24FPS,61frames except G9 insert37. Original intact
pixels and pivot160240 remain separate; never substitute the Blender rest render.

Window parent walls also carry separate aperture masks aligned with the intact
bank. These ten sheets exempt only the authored opening from finite actor-face
occlusion; selection masks and ordinary RGBA transparency have separate roles.
Solid sibling banks opt in without an aperture. Masks are preserved privately
with the production sheets and installer receipt.

Window insert destruction now comes from
`sources/fixed-window-inserts-20261001/`, passed as the required
`--insert-source` argument to `devtools/import_windows.py`. The old dense
`window` banks are combined previews: they include a standing parent wall and
must never be drawn as independent inserts. The replacement manifest explicitly
identifies insert-only components; all 36 sheets retain the original raw RGBA,
24 FPS timing, frames and registration. Full-parent and after-insert parent banks
are unchanged. Previous installed sheets remain preserved in
`sources/fixed-window-inserts-before-fix-20261001/`. Replacement media totals
7,462,104 bytes (previously 21,927,043); both installation manifests are updated.

Review floors use the four unchanged Fantasy Ground H1 paving sprites, registered
as `terrain.paving.*`. Source provenance is in `game/data/review_floor_source.json`;
originals are preserved in `sources/review-floor-h1-20261001/` and the private
production repository. The review recorder selects them for stone floors by
default; `--floor scene` restores the original scene bindings. No procedural
floor replacement, altered gameplay material or new rendering path is involved.

Environment registration corrections are preserved in
`sources/environment-content-20261001/placement-registration-20261001/`.
`game/data/environment_prop_sources.json` owns optional `ground_pivot` and
`pivots_by_pose` overrides; the importer applies them equally to intact and
breaking banks. Table anchors and two-cell cart/wagon/log registrations change
no pixels, frame counts, timing or scale. Sprite pose names follow
`game.projection.camera_pose`, not native cardinal rotation names. Keep the
original pivot as the geometric centre when authoring an offset anchor cell.
B13 remains a source hold; do not place it as a flat floor decal.

Wall heat accents preserve the complete delivery in
`sources/surface-ignition-20261001/`. `devtools/import_surface_contacts.py`
installs only eight directional formation banks, 48 frames at 32 FPS and original
paired camera layers: 64 atlas pages, 33,069,487 bytes. These are decorative
contacts; they do not create terrain. `devtools/import_wall_masks.py` preserves
`sources/wall-safe-mask-20261001/` and installs matching raw R8 masks
(4,119,132 bytes). Keep mask rectangles/pivots/clocks matched to original wall
crops. Masks classify native physical sides/base height; they are not XYZ data.
Tint copies RGB through the bounded frame cache and preserves original alpha.

October 1 diagonal Wall of Fire companion: preserve the complete pinned delivery
in `sources/wall-diagonal-20261001/`. Import with `devtools/import_wall_media.py
--merge`, then `devtools/import_wall_masks.py --merge`; these retain cardinal
registrations/masks and prior release receipts. Four new banks add 31,891,557
RGBA bytes and 3,903,128 mask bytes. Both physical-side masks travel with their
exact color/camera/frame crop. Canonical camera-relative reuse is visually accepted by the user. Preserve
full originals; production replacement still needs typed mapping integration.

Matched-height circular Wall of Fire originals are preserved in
`sources/wall-ring-gameplay-20261001/`. Existing merge importers install
27,629,255 RGBA bytes and 4,852,565 mask bytes, retaining four views, crop offsets,
original pivot and formation48/hold64 at32FPS. Public optional `wallRing` banks
register fixed radius10ft/width1ft. Donor outer/inner masks map to positive/negative;
safe outside tints front only, safe inside rear only. Whole-ring media requires
complete received shell coverage and no suppression; partial views remain an
explicit gap pending the requested matching ownership companion. No radius warp.

October 2 item media: preserve the complete `Stand-alone Character creator - 2D
Fantasy V1.3.zip` in `sources/item-equipment-20261002/`. The explicit public
`game/data/item_media_sources.json` selects 645 unchanged sheets, 86,538,120 bytes:
weapon/shield/offhand action banks, original Slash1/Slash2 Attack5 accents, and
separated apparel Idle frames. Import with
`uv run --no-sync python devtools/import_item_media.py --archive <original.zip>
--preserved /home/tommaso/Dev/neurodragon_art/sources/item-equipment-20261002
--production /home/tommaso/Dev/neurodragon_art-production`. The importer installs
private production and local assets, updates the production manifest, and writes
an exact SHA-256 receipt. Original alpha, frame clocks and pixels remain intact.
`game/data/item_appearances.json` explicitly registers category-qualified hand
substitutions and sampled ground frames/pivots/tints/contact shadows. Offhand
geometry reuse is approximate and accepted; floor apparel retains its separated
layer composite. The archive supplies no separate consumable bottle/potion art;
those ground appearances remain unbound.

October 2 roster item appearances share 235 additional original action sheets
(32,487,518 bytes), preserved in `sources/item-equipment-20261002/` and installed
privately. `devtools/author_roster_item_appearances.py` generates passive recipes
from the pinned intake; colors use palette replacement, never extra painted sheets.
`devtools/import_item_media.py --path <registered-path>` installs a bounded selection.
Preserve the first admission receipt; the authoring tool refuses to overwrite it.
The later selected offhand-longsword recipe/binding reuses existing Melee2 and
Offhand1 banks; it adds zero original sheets and preserves the first receipt.

Bestow Curse originals remain in `sources/bestow-curse-8aa6f9ef813c/`.
`devtools/import_curse_media.py` installs 120 accepted atlas pages (1,882,300 bytes);
local/private copies are hash checked and listed in the private installer manifest.

Holy support originals and normalized symbol contracts remain in
`sources/divine-support-20261002/`. The bounded delivery installs 56 original
RGBA PNG atlas pages (6,696,513 bytes) under `game/assets/divine_media/` and in
the private production repository. The installer manifest retains previous
entries; exact local/private SHA verification and a preserved prior-manifest
backup accompany the source receipt. No XYZ pages are selected for this batch.

October 2 ordinary backpack gear adds 14 unchanged original Bag2 action sheets
(2,025,461 bytes), selected by `ordinary-gear-admission.json` and verified against
local/private copies in `backpack-copy-verification.json`. The complete vendor ZIP
and prior installation receipt remain in `sources/item-equipment-20261002/`.
Cloak now has its own passive rig layer (Bag1), distinct from backpack (Bag2);
no source pixels, shadows or palette-replacement behavior changed.

Slow originals remain in `sources/control-slow-d0c688dbeb5b/`. The bounded
production delivery preserves eight unchanged RGBA atlas pages (2,872,507 bytes),
local/private hash verification and every prior manifest entry; no XYZ is selected.
Receipt: `.runtime/spell-queue-20261002/slow-private-install-receipt.json`.

The final roster Maul binding reuses the installed Melee11 banks with a source-zone
palette swap. It adds zero media pages; native weapon.maul owns its own rules.
The modular hammer head remains explicitly smaller than the fixed source art.

Continual Flame originals remain in `sources/continual-flame-v41-7863efac984b/`.
The accepted fixed-origin v41_0 installs eight unchanged RGBA pages (540,600
bytes), with shared48-frame onset/64-frame hold at32FPS and original pivot.
Both source variants remain archived. Local/private hashes and prior manifest
entries are preserved; receipt: `.runtime/spell-queue-20261002/continual-private-install-receipt.json`.

Flame Strike v15 originals remain in `sources/flame-strike-v15-6e290dcc4e50/`.
Lossless2048px atlases preserve all96 samples, original pivots/offsets and656
nonempty RGBA crops:496→168pages,84,368,797→83,434,119bytes. Selected staging:
`staging/flame-strike-v15-2048/`; local/private installer hashes agree, all prior
manifest records retained. Receipt: `.runtime/spell-queue-20261002/flame-strike-private-install-receipt.json`.

Holds originals, including the deferred Ogre bank, remain in
`sources/holds-eefffc58e8c5/`. Both spells reuse the accepted human chains for
humanoid recipients; no unknown-anatomy scaling. Selected human bind53/still1/
release87 samples pack into8pages/503,957bytes, retaining all768 addressed crops
exactly. `devtools/import_hold_media.py` registers those phases through existing
paged storage. Private/local hashes and prior installer entries are preserved;
receipt: `.runtime/spell-queue-20261002/holds-private-install-receipt.json`.

Hypnotic originals remain in `sources/hypnotic-589d88efa3e7/`. The registered atlas
packer preserves748 exact crops in24 pages (4,096,916bytes); use
`devtools/import_hypnotic_media.py` for96 finite rosette/128 loop samples, excluding
the duplicate endpoint. Two approved Incapacitated cue pages (823bytes) come from
`devtools/bake_incapacitated_media.py` and its pinned artist reference. The26-file
private install receipt is `hypnotic-private-install-receipt.json` in the spell queue.

October 4 Finger of Death preserves the complete accepted normal/cameo source in
`sources/finger-of-death-20261004/`. Original native heading captures retain all
128 banks / 13,312 RGBA cells; the unrotated camera-zero branches match all416
accepted original frames exactly. `devtools/export_finger_media.py` captures the
unchanged models/materials; `devtools/export_finger_components.py` exports the
three original Darkness meshes, HDR gradients, noise and splinters. The existing
lossless packer/verified installer in `devtools/import_finger_media.py` installs
156 payloads (34,101,016 bytes), with local/private hashes and preserved prior
manifest. Public selections are in `game/data/finger_media/`. Keep independent
camera resources, owner headings, paired layers, original pivots and32FPS clocks;
do not rotate a 2D isometric hand to invent another heading. The procedural donor
uses the existing world compositor; its palette differs from the bone hand.
# October 4 — original modular casting banks

The reviewed [casting assignments](agent_docs/art/SPELL_CAST_ASSIGNMENTS_2026-10-04.md)
select 21 original Magic2/Effect1/3/4/5 motion banks (7,659,330 bytes total).
Six already installed Magic2 banks are reused by resource address; fifteen
original banks are installed without painting, resizing or alpha changes.
Private source receipt:
`/home/tommaso/Dev/neurodragon_art/sources/modular-casting-20261004`.
Production manifest remains `/home/tommaso/Dev/neurodragon_art-production/art-manifest.json`.
The review archive keeps the per-bank source/runtime SHA256 receipt. Automatic
palette replacement and the existing delivered noise texture recolor only
isolated overlay pixels. Runtime retains the ordinary Studio recipes.

October 5 repair additionally selects the original `Effect2/Attack4.png` and
`Effect3/Attack4.png` banks for the reviewed ground-cast assignments. The two
unchanged sheets total 1,523,231 bytes; exact local/private hashes and the prior
private installer manifest are retained in
`/home/tommaso/Dev/neurodragon_art/sources/modular-casting-repair-20261005/`.
Their ordinary NeuroClient resource bindings are installed with the sheets.

October5 remaining-marks intake preserves the original seven isolated overhead
banks and their source contracts in `sources/remaining-marks-20261005/`.
`devtools/import_remaining_marks.py` installs unchanged32FPS straight-RGBA sheets
through existing necrotic media storage; no Steam/surface or actor artwork is
selected. Seven files total 1521508bytes. Current marker integration remains
under user review; source acceptance is not a substitute for gameplay acceptance.

October5 steady debuff-marker intake installs thirteen unchanged single-frame
RGBA glyphs from `steady-markers-v2` (10,282 bytes). Source contracts and original
PNGs remain in `sources/debuff-markers-steady-20261005/`; the existing verified
installer records local/private SHA256 equality and preserves the prior manifest.
`devtools/import_debuff_markers.py` merges ordinary registered-media storage.
Only new overhead glyphs are bound; existing body/ground effects remain intact.

October 5 marker update: accepted `distinct-slow-v3` adds the fourteenth steady
bank, `movement_slowed.png` (gold boot/down-arrow). The verified importer retains
previously authored media sizes when importing an updated delivery. This new
bank is also sized to the Blindness/Deafness reference footprint; existing body
VFX and source pixels are preserved.
