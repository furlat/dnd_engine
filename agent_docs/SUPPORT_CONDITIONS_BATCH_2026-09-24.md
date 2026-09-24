# Support conditions: production integration

Scope: the accepted support-batch handoff from the Godot workspace: Death Ward,
Stoneskin, Protection from Poison, six Enhance Ability presentations, Regenerate,
Remove Curse and Freedom of Movement. This is seven existing mechanical spells,
twelve visual presentations. It does not reopen the previous healing batch,
sensory backlog, barrel work or spell rules. The current renderer/private-art
cleanup contract remains authoritative. Historical Git removal is a separate,
concurrent user request and must preserve the working tree and these changes.

## What the study established

The original handoffs contain accepted q0 previews, not certified four-camera
production loops. The author is exporting real q1–q3 banks, periodic sustain
media and separate finite events. The preview clocks are not gameplay clocks.
The existing condition application/hold/removal sampler is sufficient for the
ordinary lifecycle: application can sequence or crossfade into sustain; removal
advances the existing phase while fading. Late observation starts with the
already-active hold. There is no new scheduler or condition engine to build.

Independent native review passed ten existing targeted tests. No rule defect
was demonstrated. Three missing recorded facts prevent honest presentation:
Enhance Ability loses its chosen ability, healing lacks a producing-condition
identity, and Ward consumption is not distinguishable in every public lineage
(instant death has no public fact). These are bounded event/state facts, not
renderer cues. Existing effective-handler evidence covers reactions and cannot
be used as ordinary condition ownership.

The application also lacks the exact five-band Stoneskin body material. Its
existing luminance-based spell palette is mathematically different from the
accepted maximum-RGB ramp. A distortion, equipment replacement or per-frame
uncached recolor would be the wrong owner.

## Ordered implementation

### 1. Preserve native facts at their current owners

* Add an optional typed ability choice to `ConditionState`. Enhance Ability
  snapshots it using the existing Protection from Energy precedent. Old unknown
  recordings remain unknown; never silently select Bull. The six child effect
  identities retain one paid spell and its existing concentration.
* Record condition consumption explicitly on the removal event and public
  condition-change fact. The existing Ward protection branches set consumption
  when they consume that instance. Ordinary removal, replacement and expiry do
  not. Atomic cleanup of linked descendants must not label them consumed too.
  Keep the current event parent/children and cancellation semantics intact.
* Add optional source-condition identity to the existing healing event/fact.
  Regenerate supplies its own instance identity for its real periodic healing;
  initial healing remains ordinary spell healing. Carry that provenance only
  through the existing permitted subjective fact, not through private handler
  diagnostics or live entity access. Native/archive/public JSON retain it.

Do not add new event kinds, an event bus, a rules adapter, a generic effect graph,
spell-name checks in drawing, or a new backend status solely for presentation.

### 2. Extend the existing authored presentation vocabulary narrowly

* Mirror `whenEnergyType` with an optional typed ability selector for condition
  layers. Use the existing child `effectDrafts` for selected casting palettes.
* Add authored finite condition responses for consumption and positive healing
  from that condition. Execute them at the recorded fact's choreography contact,
  with no native wait. Reuse `ConditionTransitionEffect` media and existing
  finite-effect sampling. Repeated heals create repeated finite responses;
  `owner_turn_start` remains its current one-time activation behavior.
  Bind each response once by triggering fact identity and condition owner; retain
  only unfinished tails. Attached response media follows the actor's current
  presented contact during movement. Finite tails participate in the existing
  presentation completion bound; maintained holds never block queue advancement.
  Neither changes native timing or the choreography contact.
* Bind responses from recorded condition identity/membership at the causal fact,
  not only the final state. In particular, Regenerate's tenth pulse survives the
  subsequent expiry; zero/blocked healing produces no successful-heal pulse.
* Permit a target-release media gate requiring actual completed, uncanceled
  condition removal with an authored tag. Remove Curse uses CURSE. Deduplicate
  per recipient and cast so several removals produce one release. A clean
  target can retain its casting gesture without pretending a curse was removed.
* Add a palette-only body ramp record with explicit colors, maximum-RGB mapping,
  gain and application/removal blending. Stoneskin uses the author's five colors
  and gain 1.35. Map the current body/equipment row through the existing bounded
  palette cache; preserve alpha and animation, exclude shadows/independent VFX,
  retain hit-flash priority. Blend strength must not create timestamp cache keys.

All extensions are strict passive typed records, documented in the public
presentation contract. Keep one sampler per behavior. Legacy documents remain
readable with absent fields and unchanged output. No runtime source audit,
library hashing, image scanning or per-frame validation is introduced.

### 3. Import accepted media and author the seven spells explicitly

Preserve the full delivery under the private source archive before copying its
selected production media. Follow `devtools/import_healing_media.py`: importer
converts storage/registration only and never synthesizes or rewrites recipes.
Use packed pages/frame tables; preserve original canvas, pivots, crop offsets,
alpha, palette, frame rate and front/back ordering. Four actual camera exports
are required. Do not mirror q0 as fictitious camera coverage.

One explicit selected support bundle owns these spells and their child effects.
Register its binding/asset files through current loaders. Copy only approved
media selections, including the six-entry Enhance allowlist and separate poison
v3 approval. Cast glows use isolated hand sheets, never an actor composite.
Protection from Poison and Freedom of Movement require only existing lifecycle
data. Ward uses cast/hold/consumed; Stoneskin uses cast/hold/body ramp; Regenerate
uses quiet hold and separately delivered real-heal response; Remove Curse is
finite. No preview clear time becomes a native duration.

Store pixels/geometry privately; keep recipes, binding metadata and schemas in
the code repository. Update the production release/manifest by explicit tooling,
with originals retained. No automatic install on startup.

### 4. Validate native causality, saved replay and media together

Read HOW_TO_TEST.MD and reuse current fixture/action/capture helpers. Tests must
exercise actual native actions and serialize once; clip replay must work after
engine teardown. Cover self/touch, movement, removal, canceled/out-of-range
attempts, cold observation and four-camera registration without changing any
previous spell targeting or trajectory.

| Spell | Required distinct behavior |
| --- | --- |
| Ward | Nonlethal hit retains hold; lethal prevention consumes once at 1 HP; second lethal hit kills; instant-death prevention consumes; ordinary removal/replacement never plays the consumption burst. |
| Stoneskin | Current B/P/S resistance and other damage unchanged; concentration removal restores ordinary damage; body/equipment alpha and actual frames survive the ramp across facings. No magical-weapon provenance expansion. |
| Poison protection | Poisoned and clean recipients gain the actual buff; only actual Poisoned condition is cleared; native resistance/immunity and removal remain correct. |
| Enhance Ability | Six real registered action choices survive native/public JSON and late observation, with six matching palettes; only Bear grants temporary HP; concentration removes the exact instance. |
| Regenerate | Initial burst plus actual turn-owned heals; repeated/final pulse; no positive-heal pulse at full HP or when blocked; unrelated healing never borrows this condition's identity. |
| Remove Curse | Actual CURSE-tagged removals produce one release per target; clean target and untagged conditions do not. |
| Freedom of Movement | Existing difficult-terrain/mundane restraint escape behavior, no fabricated speed boost; appearance follows movement and actual removal. |

Generate paired caster/recipient videos in all four cameras using real saved
subjective lineages and retain those inputs. Include enough ordinary standing
and movement to inspect pivot and hold seams. Report review captures as captures,
not as human-approved visuals. Run meaningful affected tests and scoped typing;
fix failures rather than leaving them labeled preexisting.

### 5. Independent review and completion

Before code changes, anti-slop reviewer checks scope/causal truth and anti-OOP/ECS
reviewer checks ownership, passive data and existing-system reuse. Both reread
the complete plan after corrections. After implementation, both inspect the
actual diff and evidence. Record exact test/clip results, asset revision and any
honest delivery limitation below, then update RECOVERY_PLAN.md's current unit.

## Review and implementation record

Initial source study: anti-slop and anti-OOP/ECS completed independently; full
plan review pending. Godot delivered isolated hand media for all twelve variants;
condition camera and loop deliveries are in progress. No runtime changes yet.
