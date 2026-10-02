# Remaining environment content using existing rules

User request: finish the window tasks, recover the environment handoff, and
implement missing assets in the engine and renderer where no particular new
gameplay ruling is required. Windows are complete; clouds, NPCs, spells,
multi-storey maps and new support/mounting behavior are outside this change.

## Contract and source

Input is ordinary authored item creation, committed placement and native attacks
or walking. Output is a targetable physical object with the appropriate native
footprint, height and channels, followed by one destruction event, the same UUID
as a persistent wreck, and the exact reviewed four-view animation. Rendering
consumes saved subjective events; it must not infer mechanics from pictures.

The source is the artist's `house-prefabs/decor-study/reviewed-manifest.json`
under `/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/`.
Only its exact accepted metadata paths are consumable. The consolidated interiors
handoff and September 23 intake supply placement restrictions. The October 1
production audit is a discovery aid; its gap count includes source-only artwork,
alternate impacts and stale identity matches. Reconcile against live bindings.

## Content

The established passive batch is 41 missing subjects:

- A5/A6 unlit clay ovens and A7 lidded pottery.
- B5/B6/B9/B11 parked carts; B8 timber pile; B10/B14/B17/B18/B19
  occupied market counters; B15 dummy, B16 grindstone, B20 produce tub,
  B21 hide rack, B23 feed trough, B24 notice board, B27 crib, B28 table,
  B37/B38 covered tables, B44/B45 freestanding banners, B52 signpost,
  B54 freestanding board, B57 archery target, B58 log, B60 apparatus,
  B61 alchemy bench.
- C2 anvil, C4 cannonball pile, C8 unlit crucible, C10 grave marker,
  C11 monument; E1–E4 hay bales; generated unlit candlesticks.

Also include A1 spent ashes, B39/B40 rugs and E5–E11 loose straw. These ten
floor objects need no new rules. The refreshed artist delta additionally confirms
FirePlace as a cold fire pit and B13 as loose floorboards: **53 additions** in all. Keep ordinary item identity/HP/destruction,
author nonblocking and nonoccupying placement independently, and draw their
flat surfaces against the existing ground-depth compositor. Do not turn cosmetic
floor props into spell/terrain conditions. Original art scale and pivots stay fixed.

These are fixed composite props: decorative contents remain part of their owner.
Parked carts do not acquire vehicle actions; workshop furniture does not acquire
crafting. Use the existing coarse placement/height model, explicitly authored
per object rather than inferred at runtime from alpha or names.

## Implementation and verification

1. Reconcile the artist's current delta, record remaining holds, and independently
   review this plan for anti-slop and anti-OOP/ECS concerns before implementation.
2. Extend the existing passive `WorldPropProfile` with independent walking/band
   flags, preserving defaults. Add the selected semantic IDs to that existing
   ledger; reuse its builder, Health, ItemDestructionProfile and owned debris.
   No new behavior classes, event kinds or content registry.
3. Author source declarations and prop bindings. Preserve source directories
   privately, import only the new selections to staging, and reuse the existing
   lossless environment pager. Merge only new registrations and update the private
   production manifest. Existing installed banks must remain unchanged.
4. Add an explicit flat-ground presentation flag to prop data and feed its
   projected ground depths to the existing compositor. This is independent of
   native movement blocking. Validate it under walking actors, shadows and raised
   support in all cameras; do not change cloud/volume composition.
5. Exercise every added item through real placement/damage/destruction tests,
   including cold wreck initialization, independent flat-prop collision flags,
   rotation and representative multi-cell footprints. Preserve damage cause,
   physical clearance timing, same-UUID remains and existing terrain ownership.
6. Capture native interactions once and replay their saved inputs in four cameras
   for both observers. Verify intact/contact continuity, full authored playback,
   stable wrecks and walk-through. Include walking over intact floor coverings.
   Inspect final pixels as well as event checks, then obtain both final reviews.

## Holds

Mounted signs/banners/shelves/tools and table-supported decorations need correct
support registration and floor-reaching destruction. Stairs/platforms/scaffolds,
open canopies/tents/cages and monumental arches need an explicit occupancy/use
interpretation. B7, wash-basin and washstand visibly spill water: do not silently
substitute dry wreckage. Lit fireplace C1 needs a light-state contract. New cannon
shapes need their actual device/muzzle authoring. Fixture destruction is still
marked candidate pending the artist's current confirmation. The four held banks
B22/B48/B49/B50 remain excluded. Foliage has no accepted fracture/burning package.
Roof/building assemblies and multi-Z remain separate. Missing art/placement is
reported separately from missing game rules, rather than claiming everything
outside the selected batch requires a new mechanic.

## Review record

The anti-slop reviewer confirmed the 41 original passive subjects and the water/mount
holds. The ECS reviewer confirmed the existing native placement contract can
represent rugs/straw with two independent passive flags; flat presentation must
be explicitly authored, not inferred from passability. Both require actual
walk-across pixels to validate the floor ordering. Both final reviews approve the implementation, including the floor compositor
corrections and sparse overlapping layers.


## Completion — October 1

All 53 IDs are native `environment.furniture.*` content with existing Health,
ordinary item damage/destruction and same-UUID remains. Twelve are walkable and
nonoccupying; eleven use explicitly authored flat-ground presentation. The cold
fire pit is passable but its small upright rim retains ordinary sprite depth.
One-cell footprints and height bands are authored coarse gameplay geometry at
the existing prop scale; they are not claimed to be recovered mesh dimensions.

The refreshed artist handoff is
`/mnt/c/Users/tommaso/Documents/assets/environment-production-audit/production-delta/HANDOFF.txt`.
Its exact reviewed paths were reconciled against production. The remaining **20
floor candidates** are the tents/canopies, platforms/scaffolds/ladder, cages/arch,
water fixtures/well, lit fireplace and wheeled cannon listed above. The artist
corrected generated-tool-rack to wall mounting; it is not a floor candidate.
Mounted/support-dependent art and unapproved banks remain explicit holds.

The existing importer gained an optional authored-bank selection so installing
new banks cannot rewrite old packed registrations. New art adds **306 packed
files / 38,197,511 bytes**. Full originals, including source projects and raw
frames, remain under `neurodragon_art/sources/environment-content-20261001/`
(**7,775 files / 479,165,558 bytes**). All new installed/private-production bytes
were checked against their manifest hashes. The complete local private release
now contains 4,945 files / 2,858,909,585 bytes. No binary artwork enters public Git.

Floor covers use the existing per-pixel painter. Same-height terrain under their
alpha is transferred beneath them, preserving translucency on raised support;
actors/contact shadows remain above their support. Connected overlapping covers
share the existing ordered depth bands, so sparse straw cannot disappear behind
a translucent rug. Other heights, airborne destruction frames and cached images
are preserved. Scenes without floor covers take the unchanged fast path. Neither
cloud composition nor window occlusion rules changed.

Native inputs were saved for every addition before rendering. The
[complete object review](http://127.0.0.1:8767/environment-content-20261001/index.html)
contains all 53 intact/destroyed states in four cameras and links to **32 passing
representative clips**, with both observers, contact/break/settle, walking over
covers, and raised-floor cases. These consume the saved public event packets;
the overview hides actors solely to inspect objects. Source/native bank timing
is preserved; the recordings use 32 FPS. Representative temporal frames were
inspected; final aesthetic approval belongs to the human.

The wider validation exposed a legacy demo that opened a door from ten feet
away. The new window-era hand-contact validation correctly rejects that. The
demo now starts its operator at its existing authored near-probe position,
within five feet; physical reach rules were not relaxed.


Validation: the combined native content, prop playback, depth, jump, window and
architecture run passed **302 checks**, with 17 setup errors sharing that legacy
demo reach issue. After its correction, the full affected demo/presentation,
terrain, boundary and ash suites passed **125 checks**. The final depth suite
passed **22 checks**, including sparse/reversed overlapping coverings; scoped
production and changed presentation-test typing is clean. All 32 clips pass
recorded-event checks and all linked media/input files are reachable. No
unrelated full-suite pass is claimed.

The final physical-access suite passed **20 checks**, including adjacent door
open/close and rejection of remote hand use without changing the door. Scoped
whitespace checks pass; newly installed artwork remains ignored and untracked.

## October 1 occupancy and light audit

The user resumed the one-tile selection review. Registration of all 53 items
was not certification of their spatial authoring: the intake script assigned
all 53 a single-cell footprint and disabled sight/propagation blocking for all.
The current review therefore supersedes any implication that every item above
is ready for placement with physically verified geometry.

The existing engine does support multi-cell center objects: rotated offsets,
equal-height support validation, atomic collision admission, per-support indexing,
light invalidation, far-end targeting, movement/removal and same-UUID destruction.
Boundary objects remain single boundary placements. The existing multicell and
world-prop suites pass **112 tests**. This is not a new architecture requirement.

A separate native probe placed and destroyed every batch item and checked actual
walking, sight, light-source delivery, propagation and terrain cost. Current facts:
**53 one-cell placements; 41 blocking/occupying props; 12 walkable/nonoccupying
props; all 53 pass sight, ordinary light and propagation; no emitters.** All
wrecks release physical occupancy and sight; 21 leave double-cost terrain,
32 leave normal terrain. These observations do not approve the authoring.

The [per-object audit](http://127.0.0.1:8767/environment-content-20261001/occupancy/index.html)
shows real H1 paving, intact/destroyed states in four cameras, each native
channel and a review disposition. It retains the original recorded gameplay
inputs. Its JSON contains the 53 probe results. Current selection:

- **36 provisional one-tile candidates:** visual fit and existing low/open-body
  or decorative-floor semantics; final human review remains required.
- **4 height/optics reviews:** clay oven, unlit crucible, stacked hay and upright
  hay. Their solid body/height warrants deliberate optical/propagation authoring;
  blanket transmission should not be accepted from a passing mechanics test.
- **13 deferred from this selection:** parked cart, loaded wagon, wheelbarrow,
  covered handcart and the five market counters/stalls lack certified footprint
  registration in the artist's current handoff. The felled log visibly extends
  beyond the single support. Red/pale covered tables and loose floorboards have
  visibly elevated intact media relative to their supplied ground anchor and
  must have registration corrected before occupancy is certified.

The nine cart/counter holds are uncertainty holds, not a claim that every one
requires multiple cells; a wheelbarrow may fit after proper registration. Sprite
width, height, shadows and roof overhang alone are not collision footprints.
No art was deleted and no new production admission registry was invented. Existing
item IDs remain intact for existing worlds/recorded inputs; the audit gallery
excludes deferred entries from its default selection. No gameplay values were
silently changed during review. The next bounded authoring pass can resolve the
four channel choices and correct/admit existing-rule placements if requested.

## Authorized correction — October 1

The user rejected the audit-only stop and requests actual repairs with the
original Blender author, followed by native gameplay videos. Keep this bounded
to the 53 props, their existing physical channels, footprints/registration,
and demonstrations. The user explicitly confirmed multi-cell props are now in scope because the
engine already supports them. Author coarse cell footprints and corresponding
registrations from the original visible supports, identifying these as gameplay
authorship rather than recovered 3D meshes; do not shrink sprites to fit.

Requested behavior: solid props block walking and physical shots through their
occupied cells; tall opaque bodies also block ordinary sight/light, while low
or narrow bodies can remain optically open. Floor dressing remains passable.
Inputs are actual native movement, ranged attacks/spells and object damage.
The observable boundary is action availability/execution, actual spatial facts,
and event-driven four-camera playback before/after destruction.

1. Have the original Blender thread recover/correct source-ground anchors and
   physical bounds for the 53 existing assets, with specific attention to carts,
   market fixtures, log, floating covered tables and floorboards. Preserve the
   original private sources, camera poses and authored scale/timing. Consume
   finite source corrections through current registrations/placement profiles.
2. Correct explicit prop channel authoring through WorldPropProfile and existing
   WorldPlacementSpec/ItemDestructionProfile only. Verify low solid stove blocks
   physical shots without using vision as a replacement for attack access; use
   ordinary optics for genuinely tall solid bodies. Do not change shared window,
   cloud, jump, or attack architecture unless a concrete feature regression
   demonstrates it is required for this request.
3. Add behavioral regression coverage for blocked movement, real ranged attack
   discovery/execution, light/sight and the same queries after destruction.
   Capture actual events once and render human-readable gameplay clips with H1
   floor artwork: attempted entry/shot, walking around, object destruction, and
   successful passage/shot after clearance. Include corrected registrations and
   multi-cell support where supplied. No static-only completion claim.

Required independent reviews: anti-slop and anti-OOP/ECS, both for this bounded
approach and its final implementation. The root owns game behavior/integration;
the Blender thread owns source geometry/registration corrections.


Correction review: both the anti-slop and ECS reviewers approved reuse of the
existing profile/placement/destruction owners. ECS review reproduced Fire Bolt
bypassing an optically open projectile barrier. The bounded correction adds an
explicit physical-access declaration to SpellAction and authors Fire Bolt with
PROJECTILE access; it does not infer native rules from VFX projectile metadata
or change unrelated remote spells. Existing preflight/discovery/execution
checks consume the declaration.

## Completed physical correction

The user explicitly included larger props after confirming the existing engine
already supports multiple cells. The artist authored coarse gameplay placement
from the original directional artwork, with source limitations documented in
`placement-registration-53/HANDOFF.txt` and its JSON patches, preserved privately
under `sources/environment-content-20261001/placement-registration-20261001/`.
No original mesh dimensions or exact collision hulls are claimed.

- Parked cart, loaded wagon and felled log occupy East offsets `(0,0),(1,0)`.
  Native rotation, targeting any support and destruction keep one UUID. Wrecks
  retain both supports while clearing physical blocking and adding the existing
  authored debris cost.
- Barrow, handcart and the five counters/stalls retain one supporting cell.
  Handles, canvas and canopy overhang do not automatically add solid ground.
- All 41 solid props block movement and physical shots/propagation. Clay oven,
  loaded wagon and stacked/upright hay also block sight and ordinary light.
  Other low or open structures remain optically open. The 11 valid floor
  dressings pass movement, sight/light and physical shots. All remain unlit.
- Red/pale covered tables use `[192,204.5]` for every intact/break/wreck frame.
  The three two-cell bodies retain the source geometric centre at
  `[192,271.36]` and use pose-specific anchor-cell pivots. Actual renderer pose
  registration is E `[160.25,255.485]`, S `[223.75,255.485]`,
  W `[223.75,287.235]`, N `[160.25,287.235]`. These are **art poses**, not native
  cardinal names. Tests compare the real camera projection in all 16
  orientation/camera combinations. Pixels, scale and frame clocks are unchanged.
- **B13 loose_floorboards is still held.** W/N views depict a supported raised
  panel; its identity/grounding is inconsistent across views. Existing ID and
  archived media are preserved for old worlds, but it is excluded from the
  current 52-object review and is not claimed repaired or suitable for placement.

Both final anti-slop and ECS reviewers approved the correction. The ECS reviewer
also independently checked all 24 overridden installed banks against importer
source declarations. Final native-prop and full prop-presentation suites pass
174 tests; independent reviewers reran 68 native access checks and three
registration checks. The initial 136-test native/multicell/window suite passed.
The broader spell/architecture run passed its 90 existing tests; its one new
content-test failure was a wrongly classified cold fire pit expectation, corrected
as passable floor dressing and covered by the final 174-test run. During validation,
moving fixture creation before actor setup changed subjective event membership;
restoring the original source/placement ordering corrected all nine affected
opaque-prop replay tests. No renderer behavior was changed to hide those failures.
Scoped typing is clean. Two additional saved-event presentation tests pass for
bow and Fire Bolt delivery. The first review captures invoked those attacks
directly, leaving the normal authored action binding absent. The fixture now
registers the equipped bow/spell and uses normal action discovery/execution;
replacement recordings must have zero presentation gaps. No renderer change
was needed.

The [combined gameplay review](http://127.0.0.1:8767/environment-content-20261001/gameplay/index.html)
contains **106 passing recordings with zero presentation gaps**: 52 props plus the stove Fire Bolt comparison,
with both observers and four camera corners. Fresh native commands exercise
rejection without cost, legal detour and shot, object damage/destruction, then
shooting and movement across the cleared supports. Floor dressing is crossed
while intact. Capture writes native/public inputs once, then replays the saved
public bytes. Rejected commands do not invent attack animation. The collection
links to original videos, inputs and traces, and defaults to attacker views.
All 430 page/media/input/trace HTTP resources are reachable, and gallery JavaScript
passes its syntax check. Fresh bow/Fire Bolt projectile frames and the two-cell
wagon/cart intact/wreck states were visually inspected, alongside the earlier
table registration checks;
user aesthetic approval remains separate from the automated replay checks.
