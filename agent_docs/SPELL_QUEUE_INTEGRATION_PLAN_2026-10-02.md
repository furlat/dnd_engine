# Queued spell production integration — 2 October 2026

## Scope and checkpoint

Spells lane: `01a0fd33-69ff-7321-bada-ba124e477822`. Items parent:
`01a07ba5-da90-76f0-9d86-483be186de09`. Same checkout and branch;
starting commit `3f2158f934f198f7edcb93f559fb1fda8b70e1f0`.
Coordination: `.runtime/lane-coordination-20261002/README.md`.

Bring the 21 queued spells' accepted artwork through the existing native
events, authored animation recipes and subjective replay. This is an integration
plan, not approval of new gameplay rules or a replacement spell executor.
All 21 have backend classes and catalog entries. Thirteen now have production bindings:
Bestow Curse, Beacon of Hope, Daylight, Mass Healing Word, Divine Word, Slow,
Continual Flame, Flame Strike, Hold Person, Hold Monster, Fear, Scorching Ray and Hypnotic Pattern.
The other eight remain in progress; source release is not completed integration.

Source root: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/`.
Entry: `QUEUED_ARTWORK_HANDOFF_2026-10-02.md`. The human released its named
accepted packets for production integration on October 2. Historical UNSENT
headers do not hold those named accepted packets; unapproved candidates remain
excluded. Pin actual manifest/checksum revisions before packing. Source approval
and completed exports do not themselves establish engine visual acceptance.

## Intake and readiness

All paths below are relative to the source root. Each row still requires source
verification, public registration and real-event integration before completion.

| Spell | Primary contract | Integration requirements / known gap |
| --- | --- | --- |
| Beacon of Hope | `divine-support-batch/production-handoff/HANDOFF.md` | Accepted application and upper spiral; sustain frames125–188. Source-owned condition lifecycle; no invented immediate heal. |
| Daylight | Same divine handoff | Accepted elevated warm orb; sustain47–110. Bind actual native lighting owner/position; fixture brightness is not a lighting rule. |
| Mass Healing Word | Same divine handoff | Accepted finite donor wisps/body pulse per actual recipient. Group concurrent recipients from one resolution; no projectile or permanent aura. |
| Divine Word | Same divine handoff | Accepted proclamation/recipient release. Branch from native outcomes; global Blind/Deaf symbols. Dedicated stun artwork absent. |
| Continual Flame | `fire-spells-review/interactions/production-handoff/HANDOFF.md` | Accepted fixed anchor v41; bind actual object socket. Stable pivot; never recenter against changing sprite bounds. |
| Scorching Ray | Fire handoff / `ASSET-REGISTER.json` | Accepted separate v23 export; confirm canonical manifest with artist. Actual rays, targets, miss/impact/cancellation and contact timing. |
| Flame Strike | Same fire handoff/register | Accepted separate v15 export; confirm canonical manifest. Authoritative area footprint; recipients from the same native resolution share formation/contact presentation. |
| Hold Person | `control-binding-study/production-handoff/HANDOFF.md` | Accepted human attachment, finite bind/removal and completed frame96 quiet sustain. No repeated binding loop. |
| Hold Monster | Same Holds handoff | Accepted Ogre reference attachment; other rig dimensions need measured profiles, not a preview scale assumption. |
| Hypnotic Pattern | `control-binding-study/production-handoff/HYPNOTIC_PATTERN.md` | Accepted finite rosette and cosmetic concentration spiral. Native square membership includes corners; no new entrant hazard from decorative circle. |
| Slow | `control-binding-study/production-handoff/SLOW.md` | Accepted crimson/charcoal exact128-frame loop; exclude diagnostic duplicate128. Native action/movement facts govern rates. |
| Fear | `control-binding-study/production-handoff/FEAR_EYEBITE.md` | Accepted finite cone and shared Frightened. Source backend controls fleeing; generic Frightened must not gain flee behavior. |
| Eyebite | Same Fear/Eyebite handoff | Accepted caster eye, application, distinct Sickened/Frightened and existing Sleep dependency. Directed fixture vectors are not arbitrary target coverage; artist completing source contract. |
| Finger of Death | `death-curse-review/production-handoff/HANDOFF.md`, `FINGER_OF_DEATH_NORMAL.md`, `COUNTERSPELL_CAMEO.md` | Normal and true cancellation mutually exclusive. Actual caster socket/target geometry required; arbitrary vectors/spatial delivery pending. Successful save remains normal damage branch, never Counterspell cameo. |
| Bestow Curse | `death-curse-review/bestow-curse-study/production-handoff/HANDOFF.md` | Explicitly accepted Oct2 revision8aa6f9ef813c; four separate marks, source-owned touch/body/head lifecycle. Validate current moving head attachment and exact clear/resist outcomes. |
| Wall of Thorns | `wall-spells-study/thorns-production-handoff/HANDOFF.md`, `thorns-modular-completion/README.md` | Accepted living/contact artwork. Artist now confirms40 modular color banks, exact2s maintain, separate retirement and RG16 XYZ/alpha-validity. Reprojection≤0.04px. Accepted color packet is released. Optional position tests remain authoring supplements. |
| Wind Wall | `wall-spells-study/wind-contact-v3/README.md`, `wind-modular-completion/README.md` | Accepted formation/arrow gust. Artist confirms40 modular color banks. Optional repaired position captures are not runtime intake gates. Ordered path/mitered connectors; no invented recurring crossing damage. Gas behavior remains native-owned. |
| Wall of Stone | `wall-spells-study/stone-ice-modules-v1/README.md` | Accepted completed sections/three variants/four native grid headings and owner-local geometry are released. Preserve source lifecycle/registration. Local break and permanent owner use native facts. |
| Wall of Ice | Stone/Ice study; `stone-ice-frost-v5/README.md`; Force V2 handoff for dome | Transparent panels local break/frigid air; dome120sharedHP whole-shell break. Still intact dome, no idle motion. Completed four-heading section/color packet is released; optional companion tests do not gate intake. Keep accepted stable color compositing. |
| Wall of Force | `wall-spells-study/force-disintegrate-v2/production-handoff/HANDOFF.md` | Accepted V2 panels/dome with V1 dependencies. Invisible physical rules remain; cosmetic cue is not native visibility. No ordinary HP break; Disintegrate removes whole owner. V1 dependencies are fully resolved and hash pinned. Placement/Y-sorting must follow actual engine owners. |
| Disintegrate | Same Force V2 handoff; `wall-spells-study/disintegrate-outcomes/HANDOFF.md` | Accepted projectile; exact caster socket/first Force intersection/target extent/depth required. Dust/save/object supplements are unapproved candidates; do not silently install them. |

Latest artist status supersedes stale index statements that Hold sustain or
Thorns/Wind headings/short loops/retirement have not been exported. Source
artwork release now permits their intake independently of optional position maps. Hold sustain is16 frame96 PNG layers,
Person/Monster ×4cameras ×rear/front, tested in8 extended source lifecycles.

## Implementation sequence

1. **Freeze intake per group after release.** Record source root, selected
   manifest/revision/hash, dependencies, approval and explicit artist/human release
   evidence identifying the permitted group and manifest in a
   private receipt under `.runtime/spell-queue-20261002/`. Verify root-relative
   paths/checksums and V1 symlink dependencies; preserve originals in the private
   archive before generating any production output. Do not scan/rebuild unrelated
   packs or run competing native Godot captures.
   Each group receipt must name the existing binding/recipe schema, exact JSON
   identities and bounded file patch; request any schema extension separately.
2. **Pack accepted media independently.** Reuse the existing importer/storage
   contracts. Add bounded importer adapters only for actual source formats;
   keep pixels separate from authored behavior. Stage outside installed assets.
   Select32FPS frames once, preserve native clock/phase length, remove verification
   duplicates and retain required rear/front/camera/shadow banks. Per-pixel XYZ is
   optional: add it only for a reproducible unresolved depth/clipping problem and
   measure the incremental installed bytes. Keep existing working cloud/Fireball
   XYZ contracts intact; overhead glyphs require anchors, not position maps.
   Share atlas pages across phases; still Ice/Hold sustain needs one sample per
   view/layer. Record bytes/frame/page counts and dependency deduplication.
   Preserve original palette swaps/RGBA; no RGB multiplication or atlas resizing
   without registration-aware validation. Source geometry drives scale/pivots;
   never apply character rig scale blindly to world volumes.
3. **Support/control/curse binding first.** Divine support, Continual Flame,
   Holds, Hypnotic, Slow, Fear and Bestow Curse use existing cast/action recipes
   and source-owned condition media. Add explicit assets and recipes in the
   appropriate existing bundles, requesting shared catalog ownership first.
   Separate cast, application, quiet sustain, individual recovery and removal.
   Shared Blind/Deaf/Paralysis/Incapacitated/Frightened/Sickened attach to native
   identities, not spell names. Reuse Sleep/Charmed dependencies. Two sources may
   share one visual identity, but clearing one must not erase the other.
4. **Directed and finite AoE deliveries.** Integrate Scorching Ray/Flame Strike
   only against their confirmed manifests. Eyebite/Finger/Disintegrate wait for
   adequate directed source registration. Use existing action delivery/cancellation
   phases and actual pose sockets, target contact, impact outcome. No fixed
   fixture target offsets or broad2D rotation of isometric frames. Contact
   presentation precedes injury feedback without changing native resolution time.
5. **Walls through accepted geometry/lifecycle contracts.** Bind actual native owners,
   shapes/ordered points, section IDs, breaks, retirement and permanent Stone.
   Thorns/Wind use8native headings and their authored connectors; Stone/Ice use
   their4grid directions. No renderer restriction may silently alter admitted
   shapes. Ordinary sections use owner-local wall geometry. A demonstrated
   unresolved depth bug may justify bounded optional XYZ/validity companions;
   do not claim deep translucent volume reconstruction. Preserve current actor/
   wall/terrain occlusion and subjective disclosure; additional depth problems
   require bounded shared-compositor changes, not painting all walls over actors.
   Ice breach air maps exact former geometry and existing first-crossing event.
   Dome remains hollow and whole-owner120HP. Force destruction uses native whole
   owner removal. No Chilled/Frozen or general surface system added here.
   Preserve `wall_media_limitation` for incomplete disclosed rings. Unsupported
   geometry/disclosure must produce an explicit presentation limitation, never a
   full fixture substitute, hidden-section leak or altered native shape.
6. **Install and accept as one coordinated group.** Parent grants shared files
   or applies bounded patches; serialize private production manifest/install.
   Pair code and art receipts. Generate standard engine-gallery recordings from
   saved native events with all4cameras and paired subjective observers. Use the
   actual wooden floor tiles requested by the user, no handmade floor. Every clip includes readable
   application, maintain/movement, triggering outcomes and cleanup, not one-second
   snapshots. Source HTML previews are intake evidence, not gameplay acceptance.

Steps1–2 can prepare receipts/source analysis now; copying/installing the unreleased
package is gated. Sequence groups by complete release, not by fabricated rollout
milestones. Every queued spell remains accounted for, including blocked deliveries.

## Architecture and edit ownership

Retain the current ECS split: engine emits authoritative facts; projection/replay
retains only observer-admitted facts; authored recipes select animation; compositor
uses registered samples/geometry. No new parallel spell executor, per-spell actor
class, generic runtime property interpreter, late imports or reflection shortcuts.
Do not derive saves, targets, HP, conditions or terrain from artwork or fixture
seconds. The existing backend class list is not certification of every mechanic;
document actual discovered rule gaps for human discussion before changing rules.

Own lane docs, new bounded spell-specific importer/presentation files and scoped
tests. Shared ownership requests go in
`.runtime/lane-coordination-20261002/spells-shared-change-requests.md` before edits.
This includes current bundle JSON, loader, condition recipes/media, core events,
projection/replay, drawer/timeline/app, private manifest and ASSETS/RECOVERY.
No Git mutation, parent process termination, preview port restart or full-suite
execution without central coordination. Fresh-read named files and preserve
concurrent item changes. Shared patches should change only spell entries, never
regenerate a catalog wholesale.

## Observable validation and completion

Read `HOW_TO_TEST.MD` before tests; scope command/state/event or replay/pixel
boundaries. Use existing native saved-event harness and renderer harness.

- Admission/output: real casts produce exact recipient/area/section ownership and
  outcomes. Failed/resisted/cancelled casts never leave persistent media owners.
- Lifecycle: two identical/different condition sources; independent clear;
  concentration loss/death/expiry; movement while held; reload/history/latest
  consistency. Maintain loops never replay application or create game ticks.
  Observer reacquisition of an already maintained effect enters quiet sustain;
  do not invent a witnessed cast, application or removal. Reuse existing owner
  ages and sustain origins in `ConditionLayerMedia`.
- Spatial:4camera actual pivots/scale, allnative headings, near/far actors,
  wall ends/apertures/real map boundaries, moving actor shadows, correctXYZ/Y,
  registered mechanical footprint and observer admission; no hidden-side disclosure.
  Approved cosmetic overhang and Hypnotic's decorative circle need not equal
  affected cells, but must never imply different damage/condition membership.
- Timing: simultaneous effects from one resolution are grouped; individual-turn
  hazards retain actual separate triggers. Cast formation/contact is visible
  before injury; no early blood, post-clear ghost or black-mask workaround.
- Outcomes: normal/countered Finger exclusivity; surviving/save/lethal/object
  Disintegrate branches only when their approved media are released; section vs
  whole-owner break and Ice breach-air expiry. Unapproved outcome studies stay
  unbound rather than being labelled completed.
- Packing: source-to-selected pixels and geometry registration remain equivalent,
  bank completeness, loop endpoint exclusion, bounded memory/cache and no runtime
  archive scan/install. Record space savings and retained source locations.

Run focused native/presentation checks and typing after each changed group.
At a stable combined checkpoint the parent/human coordinates the complete engine
and renderer suites. Record all failures/classification; never hide a backend
failure by changing a test expectation. Final evidence lists own/shared files,
release hashes, tests, standard review clips, remaining blocked21-row coverage.

## Review

Anti-slop reviewer `/root/spell_plan_antislop`: approved for preparation, not
installation. Applied its clarifications on cosmetic versus mechanical footprint,
grouped native-resolution contact, and manifest-specific release evidence.
ECS/anti-OOP reviewer `/root/spell_plan_ecs`: approved for preparation and
integration design, with no blockers. Applied its requirements for exact schemas/
patch receipts, quiet-sustain reacquisition and explicit geometry/disclosure
limitations. Neither review releases artwork or certifies the21backends.
The original preparation review preceded installation. The implementation
checkpoints below record subsequently released packets and bounded shared grants.
Private intake contract hashes are recorded
in `.runtime/spell-queue-20261002/intake-contract-receipt.json`; these snapshot
documents only and do not certify asset payload checksums.


## Staged release and implementation checkpoint

The human authorized starting completed spell packets, and the Godot producer
subsequently released the named accepted packets on October2. This supersedes
the historical UNSENT hold above for those packets; pending directed-source,
ground-fire and review-candidate supplements remain excluded.

Bestow Curse is installed:120 verified unchanged atlas pages,
1,882,300bytes, forty registered phase/layer views. Four source-owned native
conditions use the accepted warmup, two-second sustain with250ms overlap and
finite release. Successful native saves select finite resisted marks, positioned
above actual admitted actor pixels. No native curse mechanics changed. Private
source archive and production manifest installation are complete. Its 16 native saved-history clips (eight resisted, eight applied/cleared) are
complete on real wood. The runtime bounds correction passes76 focused checks.
Review runs: `20261002T171453Z-ddbc01` and `20261002T172119Z-e776e2` under
`.runtime/spell-queue-20261002/accepted-review/`.


Producer correction: the first Wind XYZ check was vacuous because its samples
were empty. The producer subsequently repaired and validated40 nonempty banks.
These remain optional authoring companions; no Wind XYZ is installed here.
Accepted RGBA intake remains independent of those maps.

User review fixture: use actual `terrain.wood` tiles and actor framing,640×440
per camera,32FPS. Rerender preserved public event histories; changing the fixture
floor does not alter native occupancy, gameplay material or the spell rules.


### Native allocation compatibility gaps found during divine intake

Beacon of Hope and Divine Word declare MULTI_ENTITY and return6 from the obsolete
`get_num_projectiles` hook. Current discovery reads `get_multi_target_count`, so
these actions disclose one allocation and reject a second selected recipient.
Mass Healing Word already uses the current hook and executes two recipients.
The proposed bounded repair migrates just those two hook methods while retaining
the existing six-target cap, costs and handlers. It is documented for human
discussion; no native patch is applied. Single-recipient art cases remain explicit
and do not certify full multi-target support.

The resisted mark actual-playback regression catches an empty-envelope bug when
choreography is rendered without bodies before the admitted body pass. The
approved fix forwards actual rendered bounds through playback/choreography/cast;
it is implemented after the coordinated run exited. Both reviewers approve;
76 focused checks pass, including actual-playback success/failure cue checks.
All16 saved-history Curse clips are complete on wood, retaining their original
native events.

### Holy integration checkpoint

The four Holy spells are bound through original native identities. Beacon uses
source-owned formation and hold; Daylight draws a compact clump at its disclosed
source, with existing native illumination. Mass Healing Word uses concurrent
actual recipients and the source contact peak; Divine Word follows HP-gated
conditions. Global Blind/Deaf glyphs use measured animated head sockets, separate
authored offsets and 600ms last-effective-owner fade. No new native mechanics.
Both independent reviewers approve the bounded mappings. The 56 original RGBA
pages add 6,696,513 bytes; no XYZ is installed. Private production installation preserves all prior manifest entries.
Seventy focused Holy/Curse/support checks passed before the stronger Daylight
owner regression; the final11 Holy checks and the native Daylight/Darkness check
also pass. The complete eight-view actual engine gallery uses real wood:
`.runtime/spell-queue-20261002/holy-production-review/runs/20261002T173738Z-4d61f0/`.

Lightning authoring is a later packet: the artist reported Chain Lightning
selecting secondaries within30ft of any selected position versus its description
within30ft of the primary. Record the actual event graph when this packet reaches
integration; no Lightning backend changes are included here.

Actual playback exposed Daylight's missing source disclosure: illumination
changed, but DaylightZone inherited `has_visible_presence=False`. The parent
granted the single existing metadata override to True. Both reviewers approve;
the observed-cell gate, native illumination, occupancy and concentration remain
unchanged. New paired native histories disclose the source and show the actual
orb in all four cameras. Only the Daylight inputs were recaptured; the other
three Holy histories are retained unchanged.


### Slow integration checkpoint

The accepted crimson revision `d0c688dbeb5b` is preserved privately in
`sources/control-slow-d0c688dbeb5b/`. Eight unchanged atlas pages total2,872,507
bytes; the public importer registers128 samples at32FPS, omitting the129th
verification endpoint. Native `condition.spell.slow` owns paired body layers,
150ms onset and550ms continuing removal. No actor-rate multiplier, recoloring,
XYZ or native rule change. Parent granted the exact two media entries, one
condition recipe, default bundle append and two native gallery selectors.
Both reviewers approve the mapping, including its actual harmful/Wisdom-save
catalog relationship. Eleven Slow/import checks pass; the combined Holy/Slow
selection passes28 checks. Scoped typing reports zero errors. Actual four-camera
paired playback compares actor pixels against the same native state with only
the optional Slow layers omitted. Failed saves draw both owners; successful
saves draw none; movement and concentration clear retain native facts. The
four real wooden-floor clips pass without presentation gaps:
`.runtime/spell-queue-20261002/slow-production-review/runs/20261002T174449Z-fcaba2/`.
Private production installation is complete: all8 pages are SHA-verified in
the installed and private copies, with6,718 prior manifest entries preserved.
Receipt: `.runtime/spell-queue-20261002/slow-private-install-receipt.json`.


### Continual Flame integration checkpoint

The approved fixed-origin v41 packet is preserved privately in
`sources/continual-flame-v41-7863efac984b/`, including both source variants
(16 original pages /1,040,464bytes). The selected v41_0 uses eight unchanged
PNG pages /540,600bytes and four phase/layer records at32FPS; application
frames0–47 and hold48–111 share pages, offsets and the exact source pivot.
Producer checksums match all retained files. Private production installation
is complete, preserving6,726 prior manifest entries and a source-local backup.
Receipt: `.runtime/spell-queue-20261002/continual-private-install-receipt.json`.

Real paired native history first reproduced missing disclosed flame owners.
The granted existing `has_visible_presence=True` flag fixes observation,
without changing light radius, permanence, concentration or damage. The
registered clump renderer now accepts a disclosed point anchor when no area
geometry exists, with existing visible-tile/support gates. Volume/wall paths
retain actual geometry requirements. No fabricated shape or lamp prop.
This supports the current native point/tile anchor; elevated object sockets
or attachment to selected movable equipment remain unsupported, not certified.

Both independent reviewers approve. Ninety focused paired replay/import/media
checks pass, the two existing native light/veto lifecycle checks pass, and
scoped typing reports zero errors. Normal paired wooden-floor clips are being
recorded under `.runtime/spell-queue-20261002/continual-production-review/`.
No item rules, cloud movement, wall composition or XYZ data changed.

Coordination update from the items chat: ordinary spell/VFX status and intake
requests now stay in this chat and go directly to Godot when needed. Spell
private-art manifest updates and minimal ASSETS notes are delegated to this
lane, serialized with its own jobs and preserving all other records/backups.
Contact the items chat only for an actual item-owned conflict requiring action.


### Holy recipient registration correction — October 2

Human reported misplaced Mass Healing Word effects and floating/flickering
Divine Word head conditions in the173738 gallery. The finite donor banks
were incorrectly registered to the torso at twice their native pixel scale.
Both recipient programs now use the actual selected ground anchor and scale.5
(the rig-to-world conversion produces pixel scale1 at zoom1). Proclamation
uses the same calibrated source scale. Original paired banks/pivots remain.

Blind/Deaf symbols keep their measured animated head sockets instead of
following the full actor/weapon/effect silhouette. Their offsets now retain
15source-pixel separation; previous0/-40 rig offsets floated them too far apart.
Godot confirms the core glyph is static; only sparse chips/material noise animate.
The64-frame banks and600ms last-effective-owner fade remain unchanged.
Enlarged actual-playback frames over4–6s show compact stable core symbols.

Regression evidence: native recipient origin test failed before correction
(projected groundY264 versus misplacedY223.5), then passes for two simultaneous
healing recipients and Divine Word in all4cameras. A pixel test checks that
changing the actor envelope cannot relocate a fixed measured head mark.
Holy/import20checks and condition-draw/point-clump/spatial75checks pass; scoped
typing0errors. Both anti-slop and ECS reviewers approve. Broader diagnostic
checks also pass22tests but expose existing incompatible legacy expectations:
`test_condition_transition_media.py::test_transition_only_recipe_plays_at_real_application_and_removal`
and `test_control_condition_sampling.py::test_senses_use_authored_intro_loop_and_finite_removal`
expect the old Blind/Deaf finite application/removal banks, which the earlier
approved shared gold-symbol binding replaced. These tests are not modified;
this is not a claim that the complete renderer suite is green.

Same saved events rerendered on real wood at32FPS, paired observers/all4cameras:
`.runtime/spell-queue-20261002/holy-production-review/runs/20261002T182929Z-8b2ccc/`.
All4clips pass with zero presentation gaps; HTTP200. No native rules, action
economy, recipient selection, event dates, cloud or wall code changed.

### Flame Strike integration checkpoint

Accepted v15 manifest6e290dcc4e50 is pinned and all496 original pages preserved
in `sources/flame-strike-v15-6e290dcc4e50/`. Lossless2048px packing retains all96
samples/32FPS, exact registration and656 addressed RGBA crops; selected168pages
use83,434,119bytes versus84,368,797bytes. Page count falls66.1%; bytes only1.1%.
NoXYZ or new gameplay. Private install preserves6,734 prior entries and original
manifest backup. Existing fire recipes/storage remain separate from atlas import.

Actual native10ft-radius/40ft-height cylinder targets two recipients; caster and
outside bystander remain unharmed. The granted generic Cylinder radius extraction
preserves native metadata instead of dropping it to zero. One paired ground
formation uses the exact source pivot at world pixel scale1; injury contact21/32s
matches first contact, not source peak53. Both independent reviewers approve.
Native timing regression samples the actual choreography immediately before/at
injury and draws fire before HP changes for both observers. Peak2.7s shows the
complete pillar registered around recipients in all4cameras. Final packed gallery
rerenders the same saved native events, realwood32FPS,2/2passed/zero gaps:
`.runtime/spell-queue-20261002/fire-production-review/runs/20261002T185234Z-653a20/`.

Continual Flame recording is complete:2/2passed, gallery181954Z-7fc939 under
continual-production-review. Sample5.5s shows the maintained fixed flame in all
four views; current tile-only anchor limitation remains explicit.

Next control shared-file edit grant: items parent confirmed condition schema,
media/sampling/lifetimes/drawing and scoped catalog are available for bounded
spell edits. Independent reviewers are implementing separate generic frozen
pose/alpha-contour and finite color-release crossfade pieces; recipes/imports
remain this lane's responsibility. No native rules or item-owned files change.


### Holds, Fear and Scorching checkpoint — October2

Holds original human source eefffc58e8c5 is preserved; lossless eight-page selection
503,957bytes retains768 exact crops, finite53-frame bind, one quiet frame96 and
87-frame release. Source-owned chains clear independently from ordinary Paralyzed.
Modular paralysis uses exact Idle3; shared amber outline uses body alpha and local
ownership clock, never shadow/weapon bounding box. The Ogre original is preserved
without claiming a calibrated Ogre profile. Hold casts use existing BodyActionCue,
with actual Special1/Magic3 sheet matching rather than the incompatible Attack5.
The final corrected twelve-clip rerender remains running; earlier interrupted
hot-schema run194948Z is superseded, not an acceptance receipt.

Fear source deb28a4f625f and diagonal v7 are preserved.46 production pages total
39,824,994bytes, with original144-frame finite cone and selected shared Frightened
application/64-frame sustain/500ms source overlap. Actual native cone headings and
source alpha centroids validate all4cameras. Native mixed saves, movement and clear
produce four passing saved-event clips on real wood in
`fear-production-review/runs/20261002T194406Z-a41a24/`. Hold/Fear focused18checks
pass. Native Fear's missing forced-Dash/disarm behavior and generic movement denial
remain disclosed rule gaps, not silently invented renderer behavior.

Scorching isolated v23 SHA16a3b4f1525d is preserved,16 original pages/1,246,355bytes
installed privately.14finite travel frames fit actual flight duration; source-root
camera tracking means no baked target displacement. Eight native headings retain
original pivots and pixel scale1.125.32 impact frames split behind/front actual
recipient body depth; public projectile three-tuple pixel API/world defaults remain.
Optional phase onMiss defaultsplay; Scorching opts intoomit for actual hitFalse.
Unknown disclosure does not infer a miss. Native repeated/split/miss allocation,
actual original-pixel direction and recipient painter-key checks:34passed. Shared
projectile/import11checks pass; scoped typing0. Both independent reviewers approve
the bounded runtime changes. Painter tests certify ordering, not full overlap pixels;
actual all4camera gameplay contact frames were visually inspected. Six saved-event
clips pass, no gaps, realwood32FPS:
`scorching-production-review/runs/20261002T200115Z-4ff4dd/`.

Hypnotic source589d88efa3e7 is preserved privately.24 packed rosette/spiral pages
retain748 exact crops and all native pivots; the approved reusable Incapacitated
head cue adds2 small pages. Total26 production payloads:4,097,739bytes. The native
cast now retains its already computed square area, while exact concentration slot
snapshots own the cosmetic spiral across root transfer, selective recovery and
source clear. Hidden/ambiguous ownership fails closed. Existing Charmed hearts
and approved pause bars follow each actual recipient; no new entrant hazard.

Both reviewers approve.62 focused checks pass, including multi-slot publication,
selective drop, veto preservation and paired cold replay. Scoped typing is clean.
Six final clips pass on wood,32FPS, all4cameras:
`hypnotic-production-review/runs/20261002T203310Z-8b6def/`.
Rare multiple same-spell casts in one lineage/nested reaction registration remain
explicitly unverified. Holds final corrected gallery also passes12/12:
`holds-final-review/runs/20261002T200420Z-185239/`.

Eyebite/Finger arbitrary delivery and modular Force sources are requested from
the artist; unapproved outcome packets remain unbound. Remaining walls use the
approved assembly amendment and existing native geometry. Original21 remain the
priority; portal camera0 acceptances do not establish complete view coverage.
