# Spell presentation repair plan — 2026-10-04

This is the current, complete plan for the user's review of the 298-spell gallery.
It supersedes the scope list in `SPELL_SPATIAL_CORRECTION_2026-10-04.md`; that
document and its two reviews remain diagnostic evidence for the first four bugs.
This plan covers animation authoring, attachment, visual transitions and replay.
It does not authorize new spell rules, artwork, native events or a combat rewrite.

## October 5 implementation receipt

The historical statuses below record the investigation before implementation.
The current [repair report](audits/SPELL_PRESENTATION_REPAIR_ACCEPTANCE_2026-10-05.md)
and its24-issue gallery supersede those statuses and the instruction to keep
commit offsets disabled. Shared source blockers are closed; measured offsets are
enabled. Original failed recordings remain preserved as diagnostic evidence.

## Acceptance and current state

The approved main Godot VFX and original modular sheets remain the source art.
Use exact palette replacement and the existing delivered noise material; no RGB
multiplication. Keep the original 298 recordings and inputs immutable. Corrected
clips use the standard four-camera engine gallery, real floor tiles, and a feed
that reuses those videos. Do not require another review of all 298 clips.

Statuses below mean:

- **Diagnosed:** a cause is demonstrated, but the correction is not verified.
- **Patched:** candidate edits exist; visual acceptance and final review remain.
- **Investigate:** the symptom is recorded, without an invented cause or fix.
- **Question resolved:** existing rules were checked; no rule edit is needed.

There is no claim that the complete repair is finished. The 142 passing focused
tests in `.runtime/projectile-regression-20261004/current-focused.log` cover the
earlier geometry/delivery/nature/curse candidate. They precede the new formation
timing edits and cannot certify those edits or all reported visuals.

## 1. Complete issue ledger

| ID | Category | Report and required result | Current status / next work |
|---|---|---|---|
| G1 | World projection | Magic Missile disappears in lower cameras or takes the wrong curve. All camera contacts must follow its actual XYZ curve. | Patched inverse camera displacement as a vector. Four-camera/raised-contact regression passes; inspect corrected native clip. |
| G2 | Area composition | Fireball has large triangular/tile cuts. Preserve rounded artwork and subjective grants. | Patched stable sphere edge ownership and restored continuous propagation. Inspect open field, hidden interior, barriers and staged breaches. |
| G3 | Area composition | Sleep's cloud bottom is sharply cut. Preserve its soft same-level fringe, while retaining real raised terrain clipping. | Patched explicit raised-support policy for that cloud. Check level/sloped/raised supports and incoming sight. |
| G4 | Area composition | Sunburst's dome has the same jagged cuts. | Investigate through G2's shared compositor using actual Sunburst frames; no assumption that a separate dome mask is necessary. |
| A1 | Emission / hands | Lightning Bolt and Chain Lightning move/jump between source positions. | Diagnosed: emitted arcs follow post-release hand/recovery frames. Patched release-source freeze; charge remains attached to pre-release hands. |
| A2 | Emission / hands | Sunbeam position and visible timing do not match the gesture. | Anchor is numerically stable in all cameras; this does not prove correct visible emission. Return to the proven Attack5 motion and inspect source frames/pivot/contact milestones. No guessed screen offset. |
| A3 | Emission / hands | Produce Flame loses its retained flame and only shows the projectile. | Diagnosed missing Idle/NE hand sockets. Candidate points measured from original Hands1 pixels; verify all directions, retained flame and hurl consumption. |
| P1 | Palette | Barkskin and warm Fire Shield cast white. Find every affected spell. | Ten all-white owners identified and candidate palettes authored. Validate each against its main material, not merely a nonwhite JSON value. |
| P2 | Palette variants | Warm/chill Fire Shield and radiant/necrotic Spirit Guardians need different casts. | Patched a typed palette selector based on this cast's own received energy evidence, shared by actor-only and delivered casts. Check both variants and reject conflicting evidence. |
| P3 | Palette | Shocking Grasp differs from Lightning Bolt; lightning's yellow/blue body accents mismatch the main blue VFX. | Candidate blue/cyan/white owner palettes and exact replacement for Shocking Grasp's baked yellow. Validate main effect and actor layers separately. |
| V1 | Authoring variety | Too many identical Special1 gestures and Effect4/5 accents. | Update motion/effect assignments according to measured motion and spell delivery. The initial pass's generic rationales are insufficient. |
| V2 | Ground casts | All walls and other ground-driven spells should strike the ground; stronger spells can use other accepted accents. | Six wall candidates now Attack4 with varied Effect1/2/3. Audit other genuinely ground-driven spells; do not force sky invocations into ground hits. |
| V3 | Signature restraint | The Attack5/Effect3 skeleton must be used only for Blight. | Candidate removes it from Harm. Other Effect3 motions are different artwork; they remain available after inspection. |
| C1 | Condition onset / attachment | Bestow Curse applies late and its circular cage sits too high. | Candidate finite touch attaches to ground and removes the extra contact delay. Validate touch, failed save, resisted cue and persistent ring together. Head marks retain their separate measured clearance. |
| C2 | Condition visibility | Fear/Frightened appears to lack the already available VFX. | Recipe and owned application tracks resolve. Inspect downstream pixels/visibility; do not duplicate Fear and Frightened ownership. |
| C3 | Condition connection / size | Hold Person chains connect too slowly; different creature sizes were not checked. | Candidate human formation shortened to 662.5ms. Human and scaled-body checks required. A distinct Ogre bank exists, but has no measured installed socket; do not silently stretch it or claim anatomy support. |
| C4 | Maintained condition | Hypnotic Pattern should remain on the ground and rotate. | Archived capture lacks cast-lineage ownership required by the current loop. Refresh only this native capture, retain the existing spiral/formation/removal, and verify actual rotation and concentration expiry. |
| C5 | Condition pose | Eyebite Asleep stands while ordinary Sleep falls and rests prone. | Candidate gives the exact Eyebite condition the shared existing Sleep override. Verify fall, persistent pose, wake, damage and death while asleep. No new sleep mechanic. |
| T1 | Delivery speed | Eyebite projectile/gaze is too slow. | Candidate uses existing contact speed 8 tiles/s instead of 2.65. Check onset and impact at short/long distances. |
| T2 | Injury continuity | Scorching Ray's repeated damage transition is awkward. | Diagnosed frame-7 HP delay and 150ms hit reentry. Candidate HP callback moved to frame0. Preserve established repeated-hit behavior until actual corrected frames prove a remaining problem. |
| T3 | Lethal feedback | Power Word appears to lack blood/impact. | Existing kill art draws. Native instant death has no damage/blood packet. Inspect timing/readability; if additional impact is needed, author finite cosmetic media conditional on the received lethal result, never fake damage or blood deposition. |
| T4 | Formation / state | Obscuration begins before the art visibly blocks; the same concern applies to movement, visibility and lighting transitions. | Two-date shared candidate is partially implemented with zero/default milestones; author/verify asset milestones before enabling it. Includes physical constructions, not only spatial fields. |
| T5 | Portal transfer | Dimension Door should begin emergence as soon as ingress finishes. | Reduce the existing DoorwayArt concealed transit interval; retain one native relocation and its source/destination contacts. |
| Q1 | Existing rules | Does Grease still knock people Prone? | Question resolved: cast/entry/end-turn saves still exist. Add a failed-save example to corrected evidence; do not change rules to force a fall in save-success clips. |

P1's exact all-white owner inventory: See Invisibility, True Seeing, Darkvision,
Shillelagh, Barkskin, Fire Shield, Produce Flame, Spirit Guardians, Guardian of
Faith, Heroes' Feast. Produce Flame's hurl alias inherits its owner. Neutral white
selectors on already colored condition media are not missing cast palettes.

## 2. Author a motion once, reuse its keypoints and sockets

Existing owners are `BodyClip`, `BodyContext`, `ActionFrameAnchor`, `BodyRig` and
`pose_sockets` in `game/animation_types.py`, loaded by `animation_data.py`.
`resolve_cast_recipe`, `context_anchor_ms`, the existing cast compiler and
`devtools/author_spell_casts.py` already connect them. Extend these owners rather
than adding a second animation registry, per-spell executor or client scheduler.

### Body motion record

For every selected casting motion, author once:

1. Its actual clip, frames, FPS, gesture description and supported accents.
2. Named preparation, release/contact and recovery keypoints measured against
   that clip. A motion can have both release and contact, with different meanings.
3. The per-frame hand/face/ground-depth socket paths for all eight directions,
   measured from that motion's original pixels, with explicit unavailable points.
4. Which frames expose a usable emitting hand and the motion's preparation,
   release and recovery sequence. The existing delivery record owns attachment
   lifetime: charge follows preparation; detached emission stays at release.
   That choice must not be a global property of the body motion, because the same
   gesture can also create a persistent hand-held effect.

Add optional named anchors to the existing `BodyClip` metadata, using the existing
`ActionFrameAnchor` value type. Put root motion anchors in the existing rig-table
document and materialize them into its clips in `_root_body_rig`. Fixed rigs
retain their existing body-context overrides and native release sockets; do not
replace their gestures with modular clips or borrow humanoid sockets.

Update the existing offline author command to resolve a selected motion's measured
preparation and release anchors. This is required work, not a description of its
current implementation: it presently requires a per-selection release integer
and derives preparation by subtracting three frames. Assignment rows choose a
motion and optional explicit
anchor override; they do not repeat arbitrary release integers for every spell.
The produced Studio recipes retain explicit source sockets and frame values, so
playback and a future TypeScript client consume the same concrete authored data.
Validate all chosen anchors against actual frame counts and every required socket.
An explicit override requires a reason and its own frame evidence. Authoring must
also retain intentional layer-palette overrides and variant selectors from the
reviewed assignment; rebuilding every layer with `source: auto` is insufficient.
A second dry run must produce no changes. Exercise canonical and derived owners,
and verify unrelated delivery, condition, injury and death fields remain intact.

Reuse the existing single `_point`/`directed_socket` projection path for each
delivery family. Camera conversion must treat offsets as vectors, include actor
scale and elevation once, and use the viewed direction's measured socket.
Charge samples current preparation frames; detached emission samples release.
Persistent hand attachments, such as Produce Flame, use the current resting pose.
The emission point, painter contact and main VFX must agree in all four cameras.

Keep Sunbeam/Lightning/Chain on their proven Attack5 registration. Use Attack6
elsewhere when the main VFX is compatible and measured; motion count diversity
alone is not a reason to break an existing delivery.

## 3. Author VFX transition keypoints once

Body release and VFX contact/formation are distinct. Do not use a body frame as a
universal indicator that a cloud, chain or physical wall is already visible.

On the existing `AuthoredProjectilePhase`, add optional named, phase-relative frame
anchors for the milestones needed here: visible onset, contact, formed and clear.
Use a media frame value with the actual phase's frame range, not the body's
14-frame maximum. Resolve anchors through the consuming track's actual FPS,
`timeMap`, facing map, fit/duration policy and playback rate. Raw source-frame/FPS
division is not sufficient. Held and reversed maps may give more than one
occurrence: require an explicitly selected occurrence or measured time override,
and reject an ambiguous required join. Keep body playback rate separate from the
independent world-media clock. Different original banks may have different
milestones; paired banks/directions must agree on the materialized join.

For procedural construction surfaces, the existing material binding owns its
application/removal durations and formation milestone once per material. It is
shared by panel/dome instances. No spell-specific wall timing branch is needed.

The existing authoring/materialization boundary writes concrete offsets to the
existing Studio tracks, condition layers and spatial/construction bindings:

- Contact/condition application waits for the matching visible contact anchor.
- A connection effect uses its application/hold crossfade consistently when sped up.
- Formation artwork starts at delivery. Its received spatial state commits at the
  authored formation milestone, not at an empty first frame and not automatically
  at the end of the full tail.
- Removal artwork starts at the removal event; physical/optical clearance joins
  the actual clear milestone. Audit existing clear behavior before changing it.

Do not create a generic effects graph, an untyped dictionary of callbacks or a new
event vocabulary. These are passive numbers/references in existing records.

### Two presentation dates for maintained fields and constructions

`SpatialMediaBinding` and `ConstructionMediaBinding` own the materialized
`formationCommitMs` value as a minimum offset. Native event order and independently reduced latest
state remain unchanged. `choreography.py` schedules the indivisible received
world/sensory changes and their related actor observations at that later date.
An update witnessing multiple sources waits for the latest relevant source date.
Earlier object placement must not admit a construction before its owner forms.
Seed every exact creation-source lineage's resolved milestone, including sources
with no retained state node, before propagating joins to observations. A related
update must not commit early merely because it does not repeat the changed owner.

Retain both witnessed artwork start and the resolved effective commit date in the
existing creation transitions and `SpatialMediaLifetime`/`ConstructionMediaLifetime`
after causal joins. Draw consumers use these dates; they must not reconstruct the
pending interval from `applied_ms + formationCommitMs`, because another source can
delay the whole update further and otherwise leave a gap in the artwork.

Before commit, retained records may draw independently witnessed formation shape
only through the current cell/surface disclosure grant. Filter each formation
sample through that grant before it reaches the existing field/construction
consumer. An any-visible-cell test must not admit the whole future field or
construction, nor borrow its future `visible_volume_positions` or
`upper_volume_surfaces`. If a partial formation has no supported current grant,
decline that part rather than guess permission. These records must
not insert future collision objects, light or obscuration into `PlayerState`,
contact tests, propagation inputs or creature disclosure. Future shape metadata
does not authorize revealing hidden occupants or hidden cells.
This is sample permission, not a screen-space tile-polygon mask. Keep the shared
continuous XYZ compositor and stable declared-shape fringe ownership; disclosure
correction must not reintroduce the Fireball/Sunburst triangles or Sleep's hard
bottom by clipping elevated artwork to ground-tile silhouettes.

The current partial candidate violates the admission boundary and reconstructs
nominal dates; its creation-source milestone propagation is also incomplete.
Keep all authored commit offsets disabled until these three source findings are
closed. Required regressions include a visible edge with a hidden interior,
unchanged pre-commit collision/light/actor disclosure, a source without a state
node, and a pending-art interval extended by another causal source.

Cold acquisition uses sustain, never guessed historical creation. Reacquisition
must not restart formation. Forward playback and backward seek reconstruct the
same state and art. Lifetime registration stays downstream of choreography;
never import the registrars back into the compositor and form an import cycle.
`WorldTransition.duration_ms` keeps its existing playback/intro-suppression meaning.

## 4. Correct palette and effect assignment through existing data

The spell's main VFX/material supplies its cast palette, unless explicitly
overridden. Check actual sampled pixels as well as recipe metadata. Keep the
three palette stops sensible for the material; no white placeholder or amber
stop in the blue lightning family. Exact swapping preserves geometry and alpha.

For variant spells, the passive `StudioCastPalette` record selects by a condition
or created-spatial owner and its received energy type. `received_cast_palette`
in `combat.py` serves both ordinary and actor-only binders before automatic layer
resolution. Use the cast's exact uncanceled owned branch, never spell names,
combat logs, unrelated active conditions or global latest state. Conflicting
palette evidence is invalid rather than an arbitrary first match.

The original gallery used 70 Special1 and 40 Attack5 casts, against 7 Attack4,
6 Attack6 and 2 Attack1. Effect2 was absent. Accepted but wholly unused combinations:

| Motion | Unused accents in the original gallery |
|---|---|
| Special1 | Effect1, Effect2 |
| Attack4 | Effect2, Effect3 |
| Attack5 | Effect2 |
| Attack6 | Effect2, Effect3 |

Effect1/Attack4 and Effect1/Attack6 appeared once each. Effect3/Special1 appeared
four times. Magic1/3 were unused because the chosen batch standardized Magic2;
they remain available hand styles, not mandatory power tiers. Attack3 is a bow
gesture and needs a genuine arrow/spectral-bow justification. Blank effect banks
on damage/death/ordinary movement cannot be made persistent auras.

Review assignments against `MODULAR_CASTING_CATALOG_2026-10-04.json` and its
contact sheets, including the original labels, user observations and separate
per-motion effect descriptions. Selection is semantic authoring, not combinatorial
coverage. Each assignment must state:

1. The spell's actual manifestation and delivery: invoked from above, driven into
   ground, directed bolt/beam, touch, weapon/arrow release, self transformation,
   gathering, summons, etc. Use existing spell behavior/media, not a guessed label.
2. Why the chosen body's measured gesture expresses that manifestation. A bow
   pose needs an arrow/bow delivery; an earth strike needs a ground-driven act.
3. What that motion's specific effect depicts and why it belongs here: a hand
   flare, ground ring, upward spikes, orbiting bodies, vertical cage or skeleton.
   "Effect3" alone is not a semantic description: its shape changes with motion.
4. Whether the accent competes with the main VFX or implies an extra impact,
   affected area, restraint or projectile that the spell does not have.
5. Why its visual intensity and repetition rate fit this spell's level and use.

Reviewers reject generic repeated rationales such as "this is a high-level spell"
or "gather/open suits magic" where the manifestation/effect relationship is
unexplained. Allowed-but-unused combinations are available choices, not quotas.
Prefer reuse of a semantically correct, registered motion over forced variety.
Audit the complete loaded spell assignment inventory, including derived aliases
and real weapon-cast exceptions. Record each changed selection and its rationale;
representative examples cannot certify all remaining assignments. Compare each
affected combination beside its main Godot media, not only in the isolated catalog.

Select by meaning, gesture, delivery and visual footprint first, level second.
Keep ordinary casts restrained; add one deliberate accent for stronger
casts, with limited layering. Use Attack4 for all six walls and genuine ground
invocations. Reserve Attack5/Effect3's skeleton for Blight. Special1/Effect3's
column and Attack4/Effect3's radial burst are separate allowed geometries.
Use the accepted Effect2 combinations where their larger spikes/orbits suit the
spell and do not obscure the main VFX. Do not assign them merely to fill a quota.

## 5. Shared condition and damage presentation

Conditions keep their existing identities and ownership. Eyebite Asleep uses the
same fall/rest/rise body profile as Sleep via the existing overrides. Frightened
remains the one Fear visual owner. Hold Person/Monster reuse their registered
connection media; anatomy-specific media needs a measured rig attachment.
Use current render scale for size checks, not an invented creature-size rule.

Hypnotic Pattern's native concentration slot must carry the current cast-lineage
UUID. Refresh that bounded native capture; do not guess ownership from spell ID or
loop the finite rosette forever. Validate sustained spiral rotation, removal and
cold/seek behavior through its existing concentration-media path.

Scorching Ray's HP/number callback joins actual impact. Existing repeated-hit
reentry is an established shared contract: changing it globally would be a new
regression. If corrected pixels still show unacceptable resets, add a narrowly
authored continuity option on the existing damage presentation, exercise repeated
hits and preserve defaults. Do not change projectile speed to hide injury timing.

Power Word Kill is instant death, not ordinary damage. Keep existing lethal art,
death state and actual event sequence. Assess visible impact first. Any extra
cosmetic impact uses an existing finite, outcome-filtered media track; it must
not manufacture HP changes, blood-release facts or ground blood residue.

Dimension Door uses the existing DoorwayArt ingress/transit/egress dates. Set the
concealed transit interval to zero for that binding, so emergence starts as entry
finishes. Check caster and recipient views; do not add movement steps or a second
teleport. This does not change persistent portal timing globally.

## 6. Ordered delivery and evidence

1. **Freeze the issue inventory and review this plan.** Independent anti-slop
   and anti-OOP/ECS reviewers check source ownership, import DAG, scope, evidence
   and exact user requirements. Existing early spatial approvals do not certify
   this larger plan. Write their findings next to this document.
2. **Consolidate motion/keypoint authoring.** Validate core motion anchors,
   missing sockets, pre-release tracking and detached release contacts. Apply
   G1/A1–A3/T1 and retain proven beam gestures. Inspect four cameras before moving on.
3. **Consolidate VFX milestones and staged state.** Finish T4 for cloud, light
   and physical construction. Prove pre-commit artwork without early state,
   correct commit, removal clearance, cold acquisition, multi-source updates and
   backward seek. Review this independent shared-core step before broad authoring.
4. **Apply palette/effect assignments and condition timing.** Finish P1–P3,
   V1–V3, C1–C5, T2/T3/T5 through the established owners. Inspect main VFX and
   actor layers together; do not rely on passing loader/schema tests.
5. **Verify area composition.** Finish G2–G4 using actual media and preserved
   subjective grants, real supports, wall/window/door openings, Globe exclusions
   and staged breach pixels. Include Fireball, Sleep and Sunburst.
6. **Export and inspect the issue-indexed correction gallery defined below.** Reuse unchanged saved
   inputs except clearly labeled fresh native captures for stale ownership data
   and the failed Grease/different-size examples. Include all reported cases,
   variants and relevant cameras; do not silently replace archival inputs.
7. **Final independent source/evidence review.** Review changed source, authored
   assignments, pixel evidence and test limits. Update the ledger with fixes,
   genuinely unresolved asset registration and any remaining blocker. Completion
   requires those reviews and visible evidence, not a schema check or clip count.

Run feature tests at the binding/sample/draw boundary, following `HOW_TO_TEST.md`.
Existing targeted projection, area, native condition, directed media, maintained
media, construction, portal and damage suites cover the affected paths. Add only
the missing public-boundary regressions. Run architecture and changed-file typing
for schema/shared-core edits; broaden tests when a shared change warrants it.
Record exact commands/results and keep old test counts distinct from new evidence.

## 7. Gallery contract — every reported issue must be inspectable

Use the existing standard engine gallery and one-player scroll feed. Add a plain
issue index over its existing recordings, with all 24 ledger IDs in report order.
Every entry states the reported defect, expected result, candidate/verified/open
status, motion and layer semantics, palette source, and relevant camera. Link to
the exact clip and seek time/frame; include a still when a fast join is difficult
to inspect. The user must be able to follow the issues without searching another
298-clip collection. One recording can prove several issues, but each issue keeps
its own entry and explicit inspection moment. Playback navigation reuses videos;
it does not cause rendering.

Preserve links to original evidence beside corrected evidence. Label whether an
input was reused or freshly recorded and why. Old media is a before-reference,
not proof of a current fix. Before/after clips need comparable moments; do not
imply synchronization when action timing changed. Missing evidence leaves an
entry visibly open. A limitation such as unregistered Hold anatomy cannot be
hidden by omitting that entry or substituting a scaled human.

| Issue | Required corrected evidence / inspection moments |
|---|---|
| G1 | Magic Missile A/B/A with both releases, every target arrival and all four cameras; level and raised contacts. No missing lower-camera projectile or camera-dependent curve. |
| G2 | Fireball's rounded formation/contact/tail in open terrain and its actual barrier/subjective edge cases. Inspect formerly triangular cuts and hidden-interior admission independently. |
| G3 | Sleep's front/bottom fringe at the reported moment, level floor and actual raised/sloped supports in four cameras. Soft same-level fringe must not bypass real higher supports. |
| G4 | Sunburst's dome onset/peak/clear in all cameras, with the formerly jagged edge plainly visible. |
| A1 | Lightning Bolt and Chain Lightning preparation, release, sustained emission and recovery. The charge follows hands; the detached source does not jump as hands recover. |
| A2 | Sunbeam's actual hand join at visible onset and the full beam contact, using the registered motion in every camera. |
| A3 | Produce Flame creation, retained idle hand in all eight facings, and hurl/consumption. Separate a retained flame from the outgoing projectile. |
| P1 | All ten named white owners, each with its own cast-layer/main-material comparison and palette provenance. No representative-only palette claim. |
| P2 | Warm/chill Fire Shield and radiant/necrotic Spirit Guardians; ordinary and actor-only paths where used, with actual received variant evidence. |
| P3 | Shocking Grasp, Lightning Bolt and Chain Lightning side by side in the chosen blue family; inspect actor accents and baked main effect separately. |
| V1 | Reviewed changes across delivery roles and levels, showing every newly assigned motion/effect pairing with its main VFX and semantic rationale. Include repeated casts to judge visual density. Link the complete assignment audit. |
| V2 | All six wall spells using the ground-strike gesture, plus changed genuine ground invocations. Show contact/formation and the chosen distinct accent; do not demonstrate only Ice. |
| V3 | Blight's unique Attack5/Effect3 skeleton, corrected Harm, and any retained Effect3 examples with their different motion-specific geometry. |
| C1 | Bestow Curse touch, condition onset and body-centered cage/ring; failed and successful saves, with no inappropriate persistent cue on a resisted result. |
| C2 | Fear's actual Frightened condition onset, sustain and clear on screen; verify the existing visual owner rather than merely a loaded recipe. |
| C3 | Hold connection and release for both spells, supported body scales and each supported anatomy registration. Show the connection moment; explicitly mark unsupported Ogre registration if it remains. |
| C4 | Fresh Hypnotic Pattern formation, visible ground-spiral rotation/sustain and concentration clear. Label the stale archived ownership versus fresh native input. |
| C5 | Ordinary Sleep and Eyebite Asleep fall/rest/wake side by side, including damage wake and death while asleep. No standing asleep or standing up solely to die. |
| T1 | Eyebite delivery at short and long distances; arrival and condition onset must be fast and joined. |
| T2 | Scorching Ray successive arrivals, visible injury and HP/number joins, at a frame-step-able moment. Preserve the shared established repeated-hit contract. |
| T3 | Power Word Kill's lethal contact/main art/death, and any separately diagnosed Power Word feedback case. Show actual result and cosmetic impact without fabricated damage or blood facts. |
| T4 | Cloud obscuration, lighting change and physical wall formation: initial visible art, actual state commit and removal clearance. Include partial disclosure, caster/recipient views and a multi-source delayed update; attach forward/seek evidence. |
| T5 | Dimension Door's final ingress frame followed immediately by first emergence, in caster/recipient views. One native relocation. |
| Q1 | Grease with a real failed-save fall and a successful-save comparison, including relevant cast/entry/end-turn triggers. Record native save results. |

The coverage receipt maps every row to artifact paths, frames/times, inspected
pixels and any numerical/test evidence. No clip total is an acceptance threshold.
Final reviews check this map and the actual visuals against the original comments;
they must not close an issue merely because a recorder reports “checks pass.”

## Review handoff

Review code and user requirements only. Do not read or message other chats.
Check especially: no new renderer spell-name switches, duplicated animation
timers, guessed hand offsets, future visibility leaks, early collision, global
damage-policy changes, fake native blood/damage, artwork tinting or stale captures
presented as current proof. Verify per-motion effect semantics and original labels
against each spell, rather than approving the number of distinct combinations.
Each accepted fix must identify the shared owner and
its actual visual acceptance boundary. Required receipts: anti-slop and anti-OOP/ECS.

Independent plan reviews are saved alongside this document:

- [Anti-slop review](audits/SPELL_PRESENTATION_REPAIR_PLAN_ANTISLOP_2026-10-04.md).
- [ECS/DAG review](audits/SPELL_PRESENTATION_REPAIR_PLAN_ECS_2026-10-04.md).

Both approve the existing-record architecture. Their required clarifications are
incorporated above: mapped media clocks, reproducible motion/palette authoring,
current formation disclosure, resolved retained dates and creation-source joins.
Both reviewers subsequently confirmed these plan clarifications are closed and
approved the semantic assignment requirements and all 24 gallery entries. There
is no remaining plan-review blocker. This approval does not accept the partial
implementation or replace final pixel review. The semantic assignment and
complete gallery requirements remain implementation acceptance gates.
