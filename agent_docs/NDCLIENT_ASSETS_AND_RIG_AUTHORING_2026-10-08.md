# NDClient: complete asset migration and creature authoring

Companion to [the master plan](NDCLIENT_IMPLEMENTATION_PLAN_2026-10-08.md).
Scope is every currently selected production asset and its registration/behavior,
not a spell-only atlas migration. Originals remain preserved under [ASSETS.md](../ASSETS.md).

**Current status:** the human resumed foundation repair later on October 8, with live app review instead of exported screenshot/video galleries.
The [asset recovery handoff](NDCLIENT_ENVIRONMENT_ASSET_RECOVERY_HANDOFF_2026-10-08.md) governs that repair. It corrects the missing
assembly/adjacency obligation: registered assets cannot be composed independently
merely because they share a material or have valid pivots. The current private
release `catalog-57cfb7346605f23f01fb` exists (10,563 files); the earlier small-copy
statement is historical. Complete copying is not correct rendering, complete
metadata consumption or approval of the rejected terraced-keep scene.

The handoff takes precedence for environment selection and source recovery.
Its §3.5 incorporates the animated-wall author's
[positioning notes](PIXI_WALL_DOOR_ELEVATION_POSITIONING_HANDOFF_2026-10-08.md).
Source family/assembly relationships, native owner and edge, frame versus bank
pose, base height, occurrence units, stair/cliff contacts and matching companion
registration are required data distinctions. Full-cell padding/atlas UVs do not
authorize changing pivots. Intact-only solid banks are not complete destruction
support. Missing calibration is recorded at its existing owner; it is not filled
by a client-wide ideal-wall formula. Foundation A0–A4 specifies the repair use.
Resumption does not authorize a replacement scene with guessed asset pairings,
unrequested sprite scaling or wholesale recopying of the already installed release.

## 1. Complete delivery, existing authority

“Move assets” means deliver all selected assets through an immutable private browser
release. Do not delete the installed Pygame art or put gigabytes of PNGs into the
NDClient Git history. A physical local copy in an ignored directory is required;
a symlink into an old checkout is not the delivery. Archive, production art and
public JSON retain their owners.

The [inventory](audits/ndclient-plan-20261008/asset-authoring-inventory.json) records
all **43 fixed-rig files** and their actual clips/frames/layers. Combined with the
modular root, the effective catalog contains **44 rigs**. Current environment data
declares **368 banks, 17 door bindings, 12 traps, 40 wrecks and 113 props**.
`assets.json` has 1,417 resource registrations. These are registrations with reuse,
not unique binary files; deduplicate against AnimationData resources before summing.

| Family | Current source | Migration/authoring requirement |
|---|---|---|
| Terrain/walls/details | `assets.json`, `world_bindings.json`, environment banks | Original pivots, composition roles, animated banks, support/depth masks |
| Doors/windows | `environment_art.json`, named source receipts | Frame/leaf/insert/open/destruction variants, exact timing, aperture and selection masks distinct |
| Props/traps/wrecks | Environment and prop source bindings | Native finite state selects animation, release/commit and destruction result |
| Water/deposits/residue | World/asset materials | Colour/normal/noise and receiving-face registration; no new chemistry |
| Modular characters | Root BodyRig, rig tables, layer registrations | Body/gear/Magic/Effect slots, masks, palette/material and explicit order |
| Goblins/animals/demons | `game/data/rigs/*.json` | Same BodyRig/BodyClip path; fixed body, original shadow/accents and semantic contexts |
| Equipment/floor items | Item appearance/material/attachment sources and content item visual ledger | Same appearance before/drop/loot; preserve item-owned coatings and enchantments |
| Spell/action/condition media | Selected current bundles | Flat/layered/registered storage and coupled planes; authored time preserved |
| UI | `ui_media.json`, new icon handoff, accepted portraits | Exact keys/roles, smooth icon filtering, no old-bank silent fallback |

Walk registered dependencies, not filename guesses. Unselected archive content may
be indexed for authors, but is not downloaded at runtime merely because it exists.
No original sheet is pruned to make the browser release smaller.

### 1.1 Installed source size is not a scene's file count

A read-only filesystem census on 8 October found **11,080 files / 4,669,872,861
bytes** (about 4.35 GiB) under `game/assets/`. This includes installed duplicate,
historical and unselected files; it is not a selected dependency-closure count and
does not prescribe copying all of them into the browser release. Examples within
that source tree: `neuroclient/` has 1,282 files, `rigs/` 865, `packed/` 927,
`wall_media/` 999, `fps32/` 1,149 and `persistent_spells/` 40. The accepted new
Fireball and smooth icon handoff also have separate source locations.

The partial 197-file copy therefore cannot represent full migration. Counting only
files also hides that one sheet holds many directional frames while one archive
contains several companion banks. Selection comes from the complete authored graph,
not directory counts. Preserve all originals; resolve and install all selected
dependencies across the family table above, with current replacements applied.
Full closure bytes remain a release-build result, not an estimate invented here.

Track source coverage, resolved/installed dependencies, renderer support and Studio
support separately in the existing coverage report. Runtime loading remains demand
based; neither all-at-once GPU residency nor a demo-only release is acceptable.

## 2. Migration procedure

Follow the [representation contract](NDCLIENT_EFFECT_REPRESENTATION_PREFLIGHT_2026-10-08.md).
Complete the release alongside production integration; usable media does not wait
for unrelated conversion or packing. N0–N3 organize ownership and final coverage,
not a requirement to finish processing the entire library before rendering it.
Original source planes remain preserved; delivering every raw plane at runtime is
not required. The representation chapter fixes compact geometry, blood/ground
batches and owner-local fields now; N1/N3 verify them in the production runtime.

1. Pin engine/public-data/private-art-manifest revisions. Read current manifests,
   not historical GB counts in old receipts.
2. Build the dependency graph with unique bytes, encoding, dimensions, alpha,
   rows/banks, timings and companion relations. Missing selected references,
   unregistered installed files and unused archive files are distinct findings.
3. Copy usable accepted media unchanged. Convert in private staging only where the
   production consumer requires a different geometry/access format or the actual
   renderer cannot load a source. Keep source hashes and source-to-output mapping.
   Further repacking needs a demonstrated loading benefit. Never apply colour
   compression/gamma to numeric data or decode whole archives at game startup.
4. Reuse existing modular/fixed sheets and frame regions. Preserve full-cell
   origin, padding semantics, sockets and matching shadow/accents. Never crop
   colour independently from masks or normalize all characters to human height.
5. Publish the release index only after referenced immutable files exist. Explicitly
   copy the selected release into NDClient's ignored local media directory using
   §2.1. Do not copy the full authoring archive or rely on an old checkout's symlink.
6. Check samples and registration at each storage boundary, duration/frame equality
   and all selected references. Prove package output in production scenes. Normal
   startup does not re-hash or scan the entire art library.

Preserve source FPS: VFX generally 32, many creatures 12, some environment frames
use uneven sample times. Never force every bank to 15 frames or the display refresh
rate. Authored elapsed time selects the sample independently from rendering Hz.
The sole explicit exception is the requested Fireball proof: selected v4 has
46 frames at 24 FPS, with a manifest duration of 1.916667 seconds. Globe stays
at its existing 32 FPS. Fireball's
paired appearance/depth-normal format does not force eight-byte planes onto other
families. N−1 fixes the source-owner contract; N0 implements and migrates
those existing types once. Coupled planes share readiness and resource lifetimes.

### 2.1 Repository and local-copy runbook

These are the N0 implementation tasks. Reference snapshots and the fresh NDClient
repository were subsequently created, but N0 is incomplete and production is now
stopped. Preserve that setup instead of repeating it. N−1's contracts and §5.4's complete release boundary are now specified; their
implementation remains outstanding. A reduced scene installer
does not satisfy steps 5–7. The existing Fireball export remains selected.

| Location | What is created/copied | Git and ownership |
|---|---|---|
| `/home/tommaso/Dev/NDClient/` | Fresh WSL TypeScript/Pixi/Vite client and production Studio | **New Git repository**, initial branch `codex/ndclient`; source, shaders, tooling, lockfile and small authored test fixtures tracked |
| `/home/tommaso/Dev/ndclient-reference/2026-10-08/` | Pinned NeuroClient/NeuroMapEditor source snapshots, revision receipts and current standalone proof source | Private read-only reference, outside NDClient Git; not a second client or new managed worktree |
| `/home/tommaso/Dev/neurodragon_art-production/` | Existing art repo; separate derived browser-release staging/output | Reuse existing private art ownership; do not create a second asset repository |
| `/home/tommaso/Dev/NDClient/public/media/<release-id>/` | **Physical copy** of selected browser-ready art and matching manifests | Entire `/public/media/` ignored and untracked in NDClient Git; immutable release-relative URLs |
| `/home/tommaso/Dev/NDClient/.runtime/` | Local SDK package, build receipts, recordings, captures, temporary staging | Ignored; large logs/videos and private recordings never enter source commits |
| Existing `dnd_engine` checkout | Existing server/SDK and canonical authored sources | Remains in place; no new backend repository, rules port or history reset |

1. **Preserve the starting references.** Record HEAD and status of NeuroClient and
   NeuroMapEditor. Save a Git bundle of committed refs and a working-source snapshot
   containing tracked modifications and relevant untracked source/configuration.
   Exclude `node_modules`, derived builds/caches and large art; record their source
   locations/releases separately. Preserve changed source bytes, not only a HEAD
   hash. Do not reset/checkout either reference. The snapshot can be read during
   porting even if the original directory later changes.
2. **Retain the successful proof.** Copy the demo's source/scripts, environment
   selection, README and small numeric receipts to the reference snapshot. Copy
   its selected Fireball export into preserved private sources if it is still only
   in an author worktree; retain the source manifest/hash. Do not make a symlink
   to that worktree the only future copy. Keep old and replacement Fireball releases
   separately; neither overwrites the installed 32 FPS bank or full originals.
3. **Retain the existing repository.** This step was performed before the production
   stop; verify its ignore rules and preserve it. For a genuinely absent future
   destination only, check the path before `git init -b
   codex/ndclient`; never initialize over unrelated existing contents. Add ignore
   rules **before copying**: `/public/media/`, `/.runtime/`, `/dist/`, `/node_modules/`,
   `/.env.local` and local package-manager caches. Do not use a blanket `*.json`
   ignore: actual authored configuration and small fixtures remain reviewable.
   No remote, push, private art publication or migration of engine Git history is
   part of this local setup task.
4. **Install source/build dependencies.** Pin the proved Pixi 8.22.0 and use the
   existing delivered `@neurodragon/player-sdk` package. Build/package that SDK from
   its owner into a local `.runtime/vendor/` tarball, then install the exact version
   via the chosen package manager; keep its revision and lockfile. A bootstrap
   script accepts the engine checkout path and creates that package before install.
   Do not copy SDK source into `src/`, regenerate the protocol or make browser code
   import `/mnt/c/...` paths. Document this order for a fresh checkout.
5. **Produce the private release.** Walk the selected dependency inventory across
   **all families** in §1. Reuse unchanged approved PNGs and companions; apply only
   the measured packing/geometry conversions where necessary. Preserve source
   names/IDs, timing, crops, pivots and semantic bindings. Pin the currently accepted
   icons/portraits and supersede them only via the user's later handoff. Derived
   release metadata is generated by the existing exporter, not hand-edited copies
   of canonical `game/data/` or another independently authored registry.
6. **Copy, then publish locally.** A small tool accepts the private release source
   and NDClient media root, copies to an ignored temporary sibling, verifies the
   referenced byte lengths/hashes once, then renames it to `<release-id>`. Install
   the matching generated presentation/resource index with it. Only then select
   that release in local configuration. No destructive `rsync --delete` against
   source archives; no force-add; no Git LFS pointers in the public client repo.
   Deduplicate within the release by resource hash; keep originals in their owners.
7. **Verify ownership and relocatability once.** Use `git check-ignore` on a copied
   image/geometry/manifest, and `git ls-files public/media .runtime` to verify zero
   tracked payloads. Inspect candidate source changes for accidental binary/log
   additions. Start with only the copied release path: resource requests must stay
   within the local release URL, not NeuroClient/Pygame directories. Do not scan
   or hash the entire archive on application launch. Report copied unique files,
   disk bytes and the release ID, separately from decoded/GPU residency.
8. **Document repeatable launch.** Supply setup/media-install/dev/build commands,
   server URL/origin configuration and the static production-media URL mapping.
   Server may stay on Windows; client/media live on WSL storage. Starting the client
   neither launches another rules engine nor rebuilds the SDK/assets. Vite's build
   may copy the private media directory into ignored `dist/`; distribute/deploy
   those private bytes separately from public source publication.

The same installer updates later releases; it is a finite copy/install tool, not a
new asset service or package framework. The initial snapshot is preserved privately;
selected reusable code is copied into its final NDClient modules and adapted there.
Do not ship the old app, proof controls or duplicate renderer alongside production.
Anti-slop and anti-OOP/ECS review checks these ownership boundaries with N0.

### 2.2 Animated assets: Pixi source check and packing policy

Rechecked 8 October against official Pixi guides and the installed **8.22.0**
source. This is a delivery decision and source audit, not a repacking performance
claim. Preserve useful sheets and accepted loose frames. Consider packing only
for an actual loading/texture constraint or measured improvement, never solely
because frames are loose. Do not build one whole-game atlas.
Pixi recommends sheets to reduce texture count; shared sources expose frame views
without copying their pixels. [Performance guide](https://pixijs.com/8.x/guides/concepts/performance-tips),
[texture guide](https://pixijs.com/8.x/guides/components/textures).

**Current source evidence:**

* All 43 fixed creature rig JSONs already select per-clip `sheets`; for example
  Bison's body and shadow each use their original directional Idle/Run/etc. sheets.
* Of 368 environment banks, 284 use `frames_by_pose`, with **26,344 colour-frame
  references to 850 unique image paths**. 847 of those paths have multiple frame
  references. The other 84 banks use `path`; these counts describe registration,
  not a full image decode or a unique-asset-size total. For example A1 door frames
  refer to rectangles in `packed/environment/.../color-000.png`, and D1 intact
  wall uses four pose rectangles in one sheet. A numbered filename is not proof
  of an individually stored animation frame.
* The selected v4 Fireball proof has **184 separate gzip payloads**: 46 frames
  × two bands × appearance/geometry. Its worker caches compressed bytes but
  decompresses evicted frames again, and `frames.js` creates/uploads new texture
  sources on each miss. The historical v1 repeat run uploaded another complete
  decoded bank and its four-age run stalled. Source inspection identifies resource
  churn, but does not attribute the stall to request count alone. V4’s successful
  single-cast playback does not close this concurrent resource-lifetime obligation.

**Offline delivery choices:**

| Family | Page and load unit | Playback |
|---|---|---|
| Modular layers, fixed bodies, gear | Retain suitable current sheets; otherwise atlas compatible clip/facing/layer sets by use and lifetime. Reuse identical pages by hash. | Select frame rectangles, no per-actor copies or recomposition into a new CPU image |
| Animated doors/windows/props/destruction | Use existing packed colour/companion pages where suitable; keep idle/open/break lifetime groups separate when it avoids loading long destruction banks just to show an intact object. | Existing sample times and state-change markers; matching colour/depth/aperture selection |
| Small flat VFX, markers, icons/portraits | Reuse current images/sheets with appropriate filtering and encoding. Atlas only to solve measured source/upload churn; keep smooth UI and nearest pixel art on compatible sources. | Shared frame views, existing authored clocks and marker cycling |
| Large layered VFX including Fireball | Reuse accepted independently loadable frame payloads or existing pages. Temporal packing is an optional remedy for measured delivery cost, not a prerequisite. Keep appearance/geometry aligned per band. | Absolute-time frame → resource/rect lookup, current and upcoming resources ready together |

Use the actual renderer's texture-size limit. Preserve scale 1, all frames,
authored durations and view reuse; never split or downscale a usable source merely
to satisfy an invented page-size or byte target. Packing can increase decoded
memory through padding. Where a measured problem justifies it, compare source and
candidate in the production workload, including upload stalls and allocated bytes,
before choosing the change. Do not launch a library-wide packing campaign.

When packing is needed, use the existing offline packers/registration export with
a Pixi atlas adapter. Do not introduce a second asset-authoring database. Pixi's AssetPack
TexturePacker is a reference/optional build tool, not a required runtime service.
Its documented defaults enable trim, rotation, animation-name detection and an
alpha threshold; do not apply these blindly. Override to preserve full source
timing/IDs, scale 1 and no atlas rotation initially. Trim ordinary transparent art
losslessly only; for additive radiance retain pixels with RGB even if alpha is zero,
and retain required geometry coverage. [AssetPack options](https://pixijs.io/assetpack/docs/guide/pipes/texture-packer/).

Store the original full-cell size, trim offset and pivot/socket registration
alongside each region. Colour and numeric companions share the **same chosen
packing layout per band**; near/far bands can retain different registered crops.
Do not independently trim or rotate a normal/depth plane. Use padding appropriate
to the sampler and UV clamping to the region. Numeric validity outside the region
must remain invalid; do not extrude valid depth into empty padding. Pixel art and
packed geometry use nearest sampling and no automatic mipmap generation; smooth
UI gets its own linear-sampled pages and bleed-safe padding.

**One loader/resource owner, not two caches competing for the same sources:**

1. Standard colour sheets use Pixi `Assets`/`Spritesheet` and shared `TextureSource`
   regions. Keep ordinary flat assets on that path. Source identity is immutable
   release resource/hash plus the declared sampling/encoding descriptor; different
   actors, cameras and frame views do not duplicate that source.
2. The existing resource owner adds only the needed byte-plane loader for encoded
   combined radiance and numeric companions. Preserve exact RG16 depth codes,
   oct-normal bytes, invalid sentinel and no-premultiply upload; do not send these
   through a browser colour decode, lossy image conversion or sRGB transform.
   A page has source dimensions and a per-frame rect; this is derived packing
   metadata at the existing media owner, not another animation protocol.
3. Pixi 8.22.0's spritesheet loader follows `related_multi_packs` automatically.
   For a large streaming animation, publish independently addressable page
   records without an eager all-pages linkage; request the relevant page closure
   through the same owner. Small intentionally resident sheets may keep ordinary
   multipack behavior. Do not make a hidden `Assets.load()` fetch the entire bank.
   [Pinned loader source](https://github.com/pixijs/pixijs/blob/v8.22.0/src/spritesheet/spritesheetAsset.ts).
4. Scene/actor/upcoming-effect bundles describe demand, not a second copy of bytes.
   Background fetch can prepare likely next resources, but fetch completion is not
   GPU readiness. Pin active pages and a byte-budgeted lookahead across **all cast
   ages**; keep download/decode/upload queues bounded. A seek replaces speculative
   demand without destroying pages still leased by another cast. Use bounded
   compressed/decoded/GPU caches and deduplicate in-flight work; the proof's
   unbounded compressed map and repeated re-decode are not production policy.
   [Background loading](https://pixijs.com/8.x/guides/components/assets/background-loader).
5. Use Pixi Prepare for compatible uploads; it limits **items**, not bytes/time
   (default four uploads), so page sizing and measured per-frame upload admission
   still matter. Colour/geometry become ready atomically before presentation may
   advance. Resource waits must not stop SDK ingestion or UI input. Release at
   **page source** granularity only after the last lease, never by destroying one
   frame with `texture.destroy(true)` while its neighbours remain in use. Separate
   GPU unload from CPU eviction; report retained raw buffers too.
   [Prepare API](https://pixijs.download/v8.22.0/docs/rendering.PrepareUpload.html),
   [texture lifetime](https://pixijs.com/8.x/guides/components/textures).

**Animation timing remains ours.** Pixi `AnimatedSprite` defaults to using
`Ticker.shared`. World animation must instead sample the single displayed clock:
select the existing atlas region directly in the shared renderer. If an ordinary
sprite uses AnimatedSprite as a view, disable `autoUpdate`/autoplay and set its
frame explicitly. Do not drive rules, phase commits or asset lifetimes through
`onComplete`; do not let automatic anchor changes replace authored sockets. This
preserves pause/backwards seek, uneven times and synchronized body/Magic/Effect
layers. Packing does not change FPS or double-apply playback speed.
[Pinned animation source](https://github.com/pixijs/pixijs/blob/v8.22.0/src/scene/sprite-animated/AnimatedSprite.ts).

Atlas packing is also distinct from GPU compression. Keep numeric planes exact;
the selected initial release uses existing PNG appearance and lossless gzip raw
planes. GPU-compressed appearance is outside this phase, not another undecided
format. PNG/WebP/gzip transfer
savings alone do not shrink decoded RGBA memory. Do not add a universal codec
conversion or multi-resolution export campaign to this task.
[Compressed textures](https://pixijs.com/8.x/guides/components/assets/compressed-textures).

**Bounded acceptance:** reuse the current proof and representative existing rig,
animated door and marker cases. Verify frame/pivot/timing/paired alignment across
page boundaries, first/repeat/four-age playback, seek, shared-page release and
context restoration. Count HTTP requests, decode repeats, source creations, upload
bytes/stalls, page occupancy and CPU/GPU high-water marks separately. Compare equal
content/quality at scale 1. Atlases do not guarantee custom depth meshes batch;
the existing explicit world-batch plan still applies. Close actual resource churn
and buffering before claiming the packed release solves them. Keep the finite
findings in the existing proof receipt rather than adding a new benchmark framework.

## 3. Fixed creatures already have the required shared model

`BodyRig` owns cell geometry, facing rows, slots/categories, clips, native wings,
pose sockets, rest anchors and context bindings. `BodyClip` owns frames/FPS/source
sheets, original accents and anchors. Typed content/movement qualifiers select
body contexts. Do not introduce Goblin/Animal renderer classes.

Inspected examples:

* Goblin17: 128×128 fixed body, shadow and original effect slot. Attack5's registered
  accent follows the body; its muzzle art must not generate a duplicate attack or
  projectile. The ordinary ranged recipe still owns the actual delivery.
* GreyWolf: 64×64 source and actual Run/damage/death/attack clips, with semantic
  aliases. Preserve the approved **200% original artwork size** at its existing
  appearance owner; never derive art scale from rules creature size.
* Imp05: ordinary lying pose and distinct Explode terminal animation with its
  original accent/rest anchors. Prone-to-death must not stand up first.

Aliased semantic clips share source images. A fixed sprite may still have shadow
and accent layers; fixed means baked equipment/body artwork, not one flat picture.
Do not invent modular slots for that baked gear. Retain accepted item loot and
corpse behavior; this phase does not commission repaints, weapons or wing art.

## 4. Actual rig-authoring code required

Implement `src/studio/rig/` as inspector/edit/preview functions over the existing
BodyRig schema. It calls the production body sampler/render operations, not a
preview-only animator. Source-map saves target `game/data/rigs/<id>.json` or the
existing modular source. Adding a rig does not duplicate a spell/action definition.

| Inspector | Required editing and review |
|---|---|
| Identity | Rig/content associations, provenance, source availability and declared slots; no accidental mass rebinding |
| Clip bank | Source clip versus semantic name, actual frames/FPS, rows, sheet/region/crop/pivot; loop and step |
| Registration | Ground origin, supported body/head/face/hand/weapon sockets, rest anchors and ground-depth socket; handles save full-cell coordinates |
| Timing | Context-appropriate prepare/release/contact/effect/commit, normalized travel and recovery; validate frame bounds |
| Roles | Idle/walk/run/fly/jump, melee/ranged/cast, damage/avoidance/shove/equipment, condition entry/hold/exit/death using typed qualifiers |
| Layers | Body/shadow/original accents, slots/categories/exclusions, palette/material mask; no fictitious removable fixed-sprite gear |
| Rest/death | Final-rest/source death, allowed entry reversal, disappearance/remains, prone-to-death; no generic death-as-all-conditions fallback |
| Scale | Source pixels, existing appearance scale, on-map size and lifecycle scale shown separately; no unrequested resizing |
| Capabilities | Native wings, supported contexts/sockets and explicit permitted fallback/missing source poses |
| Real case | Ordinary native movement/action/condition recording on the selected rig, with palette/gear/cameras and external VFX |

Only offer anchors meaningful to the role. Do not invent Attack3/Walk or mirror a
facing outside source registration. Editing sprites does not grant attacks, flight
speed or other native abilities. Existing game behavior/content remains native.

A new rig draft can be initialized from a registered source bank; missing required
contexts stay explicit before production selection. Reuse current semantic
validation for publication. Immediate browser field checks do not become a second
authoritative capability rules engine.

## 5. Environment authoring uses the same workspace

Environment inspector: original frame/pivot per pose, sample times, depth range,
selection/aperture masks, separate parent/insert/leaf sources, release/state-change
frames, destruction-without-attachment variants and support registration. Preview
actual door/window/prop transitions with actors on both sides and all four cameras.
Native facts still drive open/broken/active state.

This is not a map-editor rewrite. NeuroMapEditor remains a reference for grid/layer
separation and placement workflow. Converting arbitrary authoring ZGrids into new
gameplay topology is separate from the client migration.

## 6. Acceptance denominator

All 44 rigs use one body path; every declared clip/context is inspectable. Parameterized
mapping coverage accounts for every rig. End-to-end visual cases include modular
human, Goblin17, wolf, winged demon and a large fixed creature, checking native size,
shadow, all facings, damage/blood, prone/death, flight, summon/despawn and gear where
applicable. Do not call five examples coverage of the remaining mappings.

Every selected environment resource resolves with unchanged timing/registration.
Native cases exercise doors, intact/broken inserts, parent break, traps, wrecks,
light changes and cutaway. Studio can browse the full index while normal play loads
only the scene's resource closure.
