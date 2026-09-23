# User complaints and contracts we must preserve

Recorded 2026-09-11 on `codex/recovery-design` during the event/archive audit.

This records the user's corrections from the conversation, including recurring
ones that explain the latest complaint. These are requirements and objections,
not evidence that an implementation satisfies them. Investigation findings belong
in a separate section with source evidence. Do not quietly weaken a requirement
to describe what the current implementation happens to support. This document
does not introduce new gameplay rules or authorize unrelated work.

## Immediate complaints: event recording and the client boundary

### September 23 — blocked attempts, expenditure and reaction ownership

Sanctuary review must distinguish a failed attacker save from a later successful
attack. Repair native targeting semantics; do not manufacture a block visually.
Canceled-action presentation must reflect cancellation phase **and whether the
actor actually spent action economy**. An unpaid preparation and a paid spell
interrupted in flight are different. Preserve completed child facts and original
lineages. Counterspell's source gesture and the incoming spell share presentation
time; this does not permit reparenting native events or rerunning rules in replay.

The user requested Counterspell artwork, later adding Globe of Invulnerability,
and explicitly excluded Dispel Magic. Globe's existing native area protection is
distinct from creature invulnerability/untargetability; check existing behavior
before proposing new mechanics. Art preparation is not production integration.

### September 21 — destruction is item state; cover the whole applicable catalog

Implementation was subsequently authorized. The user explicitly clarified:
**the transition must have a proper native event, which cascades the physical
change**. ItemDestructionEvent therefore owns geometry/cleanup consequences;
an ordinary spatial-change fact alone is insufficient as the semantic owner.
The specified art task received the missing-asset creation assignment.

The user selected an object becoming destroyed rather than requiring a separate
debris object for every item. Preserve the native identity, use existing damage
and destruction hooks, and drive remaining collision, description and visuals
from real state. Difficult terrain is an authored possibility for larger debris;
salvage/loot/repair is not automatically implied.

The requested dedicated plan must cover existing items and assets **and** new
delivered counterparts. Every applicable current door, trap/device and prop must
adopt the shared lifecycle with methods and meaningful behavioral tests. Do not
demonstrate a new furniture path while leaving existing doors inconsistent.
Record art that lacks native breakability, native breakables lacking media,
material/condition gaps and exact missing asset requests separately. An unbound
delivered bank is not missing artwork. See the
[destruction plan](DESTRUCTION_LIFECYCLE_PLAN_2026-09-21.md) and
[coverage ledger](DESTRUCTION_COVERAGE_2026-09-21.md). This request is for planning;
the existence of those documents does not mean the feature is implemented.

### September 21 — interiors, multi-Z reasoning and usable windows

Latest direction: prepare a **complete reviewed integration plan for all
handoff assets**, with native items and visibility/walkability/placement/height
and support data first. A demonstration room is only a proving step. The user
then explicitly said **ignore the Z discussion for this** and asked to recover
the separate XYZ task for a full scan of all affected rules/systems. That task
is active again. Do not re-open a multi-Z sequencing question here or omit
unused delivered props because they are absent from the first house.

First core now explicitly prioritized: multi-cell furniture, windows and
attacking/destruction must be understood and proved before bulk content work.
Attackable traps already use ordinary item damage/destruction/remnant ownership;
reuse it rather than designing a new destructible-object system. The broader
asset plan remains, with core mechanics first and content expansion afterward.

The consolidated interiors handoff contains new objects and concrete building
prefabs, including overlapping floors. The user requested careful backend map
design and proper content integration, then explicitly said to **reason first**
and delegate a multi-Z plan. The earlier single-storey-first proposal is now
superseded by the explicit separation above. Do not flatten supplied multistorey
houses or mistake their preserved source records for playable native layouts.

Windows must be usable gameplay features, not window pictures over solid-wall
mechanics. The design must consider actual openings, observation/targeting and
appropriate interaction/traversal; delivered fixed bars are not proof that
operable-window or broken-glass animation exists. Multi-Z design is not a new
authorization for flight, arbitrary falling or structural-collapse simulation.
The [interiors plan](INTERIORS_INTEGRATION_PLAN_2026-09-21.md) records the study
and independent reviews; the [multi-Z plan](MULTI_Z_MAP_PLAN_2026-09-21.md)
develops the spatial contract. These remain design work, not implemented claims.

### September 20 — trap artwork requires native gameplay and reusable triggers

The user requires new backend traps matching the recovered mechanisms, using
the existing condition/handler/event conventions. Pressure plates must support
both held controls (for example a door held open) and one trap activation per
new press, as explicitly selected in the follow-up. Delivered sprites do not
establish these rules. Trigger placement and the linked mechanism's affected
area are separate; preserved ground-contact and subjective replay rules still
apply. The [trap implementation plan](TRAPS_AND_TRIGGERS_PLAN_2026-09-20.md)
records code evidence and independent reviews; its existence is not evidence
of implementation.

September 21: the user proposes a portal beneath the hatch instead of adding
stacked-floor/falling mechanics, and explicitly requests bare portals sharing
that same native behavior. Portal appearance is authored presentation; reuse
the removed magical-hand portal component and existing portal library before
requesting more art. This does not authorize reverting the approved Chill Touch
effect to an older full hand/portal sequence.

### September 20 — consistent spell targets and integration ownership

The user rejected Poison's low body contact after the travelling-cloud repair.
Keep the intended anatomical target constant across spells; repeatedly lifting
individual recipes does not satisfy this. Check actual rendered contacts and
movement in every camera, rather than testing only the metadata we authored.
The main integration task owns this diagnosis and repair. Contact the artwork
task only when new renders are actually needed; do not pass responsibility for
placement bugs back to that task. Provide one preview covering all the new
spells, not another Poison-only gallery.

### C01 — Record once, serialize, and replay without rerunning mechanics

The user explicitly expects Python to process a premade event sequence. Generate
the native sequence once, retain its complete causal history, serialize it, and
use the saved input for repeated reduction, animation and visual validation.

> "no need to re-run everytime the game for the tests"

Holding Python objects after an engine reset does not establish this contract.
Neither does exporting diagnostic JSON while regenerating mechanics from a case
ID whenever the gallery is rerun. A replay must consume the saved sequence.
Native tests still exercise mechanics; presentation replay must not depend on
re-executing them. If additional runtime information is needed, identify precisely
which fact was omitted and where it should have been recorded.

### C02 — Lossy event serialization is an unacceptable gap

The user had already discussed event serialization extensively. Losing event
subclasses, consumed fields, identities or observation facts is not an optional
future networking enhancement. All facts required to process the recorded
sequence must survive writing and reading it. Receiving recorded events must
not execute their mechanics or register new backend events.

The user's immediate response to the serialization and actor-discovery findings
was that these were "absurdly bad defects". Audit the changes and existing
contracts before asserting that the engine lacked the capability. Distinguish
a native event regression from an incomplete capture/export/ingestion adapter.
Do not make the user carry that investigation or invent a second rules system
to compensate for dropped event facts.

### C03 — Actor discovery cannot depend on a fixed startup cast

The user rejects treating an initially known actor set as a sufficient general
game/client design. Birth, discovery and subsequent state must be supported by
received facts. An actor newly encountered during play must be introducible with
the appropriate appearance, equipment and state before its animation needs it.
Existing NeuroClient handling is a source to study; a fixed gallery roster is
not a substitute for that capability.

### C04 — Objective-to-subjective meaning was already solved

> "we had this solved from first principle already with the objective to subjective part"

Use the existing subjectivity rules and their event-time authority. Identify
where the current integration fails to apply or preserve them. Do not reopen
what observers should know, simplify events into invented messages such as
"B was hit", or add new withholding rules. An objective diagnostic capture and
a player's received stream have different audiences; correctly ignoring a
foreign observer's update in a reducer does not establish correct transmission.

### C05 — Active weapon sets are game state

> "we need clearly the weapon active sets as part of the game state"

The active set must be retained and recoverable with the rest of the state.
It cannot depend on a live equipment lookup during playback. The animation may
display a transition at its authored time; it must remain connected to the
actual state change. Test melee followed by ranged attack in the same turn,
and real equipment replacement, including the visible weapon/layer changes.

### C06 — The apparent starting world consists of recorded facts too

The user corrected the assistant's description of "retained starting world,
actors and sensory state": those have event origins. Explain which recorded
facts establish the initial reduced state. Do not quietly create an additional
source of authoritative game information or treat an unrecorded startup snapshot
as satisfying an events-only replay requirement.

## Earlier complaints that constrain this work

### C07 — Preserve the actual timeline and complete lineage design

- Event processing and rendering are independent processes, simulated with async
  work in the same Python thread. Event processing may advance while historical
  animation continues at the same speed or is paused.
- Render complete causal lineages, including parent/child and reaction
  relationships. An individual event's completion is not the presentation unit.
- Study handlers, conditions, event phases, interception and spatial events
  before proposing changes to their behavior. Do not mistake a child completing
  before later consequences for a broken action contract.
- Preserve native causality. Initial failed saves can apply conditions; actual
  later successful repeat saves can remove them according to their handlers.
  Videos must make their real turn sequence intelligible.
- Reaction attacks interrupt walking at the correct point; movement resumes only
  as permitted by native results. Death, paralysis and other stopping results
  must compose with the same historical playback.

### C08 — Recover the design; do not rebuild a special case for every spell

- This exercise is predominantly design. Hundreds of D&D spells cannot be
  implemented by writing a new animation/control path for each demonstration.
- Reuse NeuroStudio's existing JSON, typesystem and authored timeline meaning.
  Exporting existing TypeScript-authored data is acceptable; the running game is
  Python/Pygame. Portable data should remain usable by a future TypeScript client.
- Keep recipes, animation mappings and reduction responsibilities data-driven
  where their existing contracts call for it. Avoid accumulating ad hoc patches,
  invented matching systems, alternative queues and per-spell branches.
- Treat packaged sprite groups as rigs. Use the composable humanoid rig as the
  reference and map compatible animation names for other rigs. Different names
  are not a reason to recreate the animation system.
- This is an ECS-adapted D&D codebase. Entities compose data and systems. Keep
  ownership and imports clear rather than growing controller hierarchies.
- Work within this recovery branch. Study the failed branch and experimental
  branch for intention and mistakes; do not import their dead infrastructure.
  Preserve the distinction between historical analysis and the forward plan.

### C09 — Build gameplay, not a VFX tutorial

- Individual spell art must not block the shared game work. Use the authored
  NeuroVFX/CodexFX assets where available; do not substitute an invented fallback
  and present it as the authored effect. VFX investigation is a separate bounded
  task when requested.
- Ranged attacks belong alongside melee and casting. Include equipment changes,
  demons/undead/animals, ordinary movement and turns, forced movement, and actual
  Haste/Dash behavior rather than demonstrating only spells.
- Reuse NeuroClient portraits, spell icons, layering identities and alignment
  data. Casting and impact anchors should use the available authored alignment.
- Respect the 2.5D height model throughout projection, movement and effects.
  Difficult stairs are useful cases, but also test flat ground, multiple
  positions, swapped caster/receiver and changed camera angles.

Asset references supplied by the user:

- `C:\Users\tommaso\Downloads\2D Orcs and Goblins - TopDown - V1.0.zip`
- `C:\Users\tommaso\Downloads\2D Demons - TopDown assetpack v1.1.zip`
- `C:\Users\tommaso\Documents\assets\smallscale`
- NeuroClient: modular humanoids, portraits, icons, alignment and Studio recipes.
- NeuroVFX/CodexFX: authored/generated effect assets, exported from Godot.

### C10 — Visual continuity and review must reflect real mechanics

- A lethal opportunity attack must leave the rendered body at its interrupted
  visual position. Keeping a different legal tile origin does not justify
  snapping the corpse to that tile's center. Study other interrupted states too.
- Paralysis presentation looked awkward; investigate the actual effect rather
  than assuming arbitrary recoloring or a shader is appropriate.
- Floating text must leave the action visible, with placement adjusted near the
  screen boundary.
- Jump reactions play while grounded before flight, not by freezing a character
  in midair. A jump body animation traverses exactly once over the flight time,
  including short, long, uphill and downhill cases. Avoid looping, fast resets
  and end-of-flight pose flips.
- Include flat-to-flat jumps over water, uphill/downhill jumps, movement around
  corners, Haste/Dash movement and native forced movement.
- Maintain an automatically generated array of labeled videos, with all four
  camera corners in one pass. The user must be able to inspect clips together,
  select faulty ones and export a trace/pinned moment for debugging.
- Recorded clips must preserve causal and turn relationships. Do not invent
  condition transitions just to show an animation capability.
- September 11: collect both entities' subjective viewpoints for every
  experiment, retaining four camera corners for each. Include many entering/
  leaving-sight walks, brief glimpses through open doorways and discovery caused
  by the observer walking. Both viewpoints must describe the same native
  experiment, with visibility changes during the complete movement lineage.
- September 12: exercise invisibility and stealth with and without truesight,
  adding a truesight spell/potion only where missing. Include allied versus
  opposing factions and both the concealed/casting actor and perceiver views.
  Use the established native distinctions; sharing a faction is not a renderer
  permission to reveal an otherwise undisclosed actor.

### C11 — Stop replacing understanding with speculative repair

- Investigate the status quo and original intention before patching. When in
  doubt, expand the source study rather than inventing a new system.
- Do not treat an artificially injected interception after a phase's effect as
  proof of a shipped mechanics defect. Find a real producer/handler and explain
  the native sequence before adding a repair or planning prerequisite.
- Keep speculative concerns out of the forward plan. Remove conclusions that
  depended on a corrected premise; merely apologizing does not do that work.
- Use the global `bug-fix` skill when investigating defects or revising work.
  Its reflection should improve judgment and initiative, not become an excuse
  to stop, seek constant supervision or avoid necessary implementation.
- Slow down routinely to review overall structure. Passing tests and reviewer
  agreement do not prove that the assumptions behind them match the user's goal.
- Explain what changed relative to the plan, what remains missing and what is
  next. The user should not have to reconstruct progress from gallery counts.
- Answer questions briefly during active work and keep working within the
  authorized scope. Do not make answering a question the entire work session.
- The September 11 request to write complaints down was explicitly side work
  while continuing the event/replay task. A follow-up clause or status question
  does not cancel the active implementation. The user had to correct another
  premature stop after the assistant finished only the audit/documents.
- Keep documentation accurate and useful. Large diffs need an honest distinction
  between source changes and imported assets; do not carry stale plans or skills
  forward as authority over the user's design.

## Investigation and implementation status

### September 12 — reviewed repair implementation authorized

The user approved proceeding after the whole-source audit, anti-slop/anti-OOP
review and plain timing baseline. That resumes performance implementation, not
new gameplay or VFX work. Preserve the distinction between native execution,
public event processing, asset preparation and drawing. Remove unnecessary
obligations at their owner; do not replace source audits with cached attestations
or let inherited tests make them requirements again.

The first checkpoint removes source/census audits and the pending duplicate
offline asset validator, gives body rows a session lifetime, separates native
demos from the painter, and removes native query/copy duplication. A following
bounded import repair separates passive records/public reduction from native
capture. Exact measurements and remaining limits belong to the fix plan/results.

### September 12 — fix plan and plain timing now requested

The user has authorized a fix plan and a current timing diagnostic so improvements
can be compared. The diagnostic must add no SHA/source verification, fingerprints,
frame hashing or asset audit. Use elapsed measurements of actual native and saved
playback work separately. This lifts the earlier measurement stop for this unit;
it does not mean the proposed implementation or pending edits are now complete.

The [reviewed fix plan](PERFORMANCE_FIX_PLAN_2026-09-12.md) and
[current baseline](PERFORMANCE_BASELINE_2026-09-12.md) record the result, actual
workloads, ranges, limitations and how to repeat the timings. No production edits
were made during this planning/measurement unit.

### September 12 — whole-codebase audit supersedes performance implementation

- The user explicitly calls this a **critical design/work problem**. Do not
  minimize it as a slip, isolated coding mistake, or small performance miss.
  The audit must address how inherited implementation became authority and how
  current review/testing let the same pattern return, including our own work.
- The user explicitly stopped all implementation until the whole codebase is
  scanned for unnecessary defensive machinery and repeated work.
- The problem is architectural recurrence: the recovery rolled back months of
  failed work, yet retained similar systems and accumulated more. Finding a
  smaller budget miss, optimizing a source audit, or accepting inherited tests
  as authority misses this framing.
- Scan all subsystems, including older server/AI/content machinery and newly
  written game/presentation code. Do not stop after removing one source hash.
- Establish purpose, actual callers, cadence and evidence before proposing what
  to retain or remove. Existing source and tests describe behavior; they do not
  independently justify it.
- Preserve the pending edits for review. During this stop, work is source study
  and documentation only; no further fixes, tests, benchmarks or rendering.

The completed [whole-codebase audit](audits/CODEBASE_MACHINERY_AUDIT_2026-09-12.md)
records the source findings and the recurring design/work failure. It covers all
1,031 Python/TS/JS files with explicit static-versus-semantic review limits.
Implementation remains paused; audit completion does not approve pending edits.

### September 12 — earlier performance unit, now paused

- Stop rendering feature work and fix measured slowness. A barely passing
  startup threshold does not establish acceptable game performance.
- Separate native imports, world construction and real turn execution from
  capture/projection/reduction, asset loading and drawing. Do not describe
  whole-process startup as the time to render a handful of frames.
- Investigate why earlier gameplay was fast. Compare compatible workloads and
  attribute inherited costs versus changes in the recovery branch honestly.
- Audit defensive copies, reserialization and repeated validation; do not
  assume their necessity merely because an earlier implementation added them.
- The user explicitly rejected built-in Python-source scanning/hashing on
  startup and requested its immediate removal. Do not replace it with a new
  verification/cache framework or hide it behind delayed imports.
- Bundled authored assets should load during play; exhaustive authoring checks
  should not delay every launch.
- Commit the checkpoint before changing implementation. Continue documenting
  findings and removals while doing the fixes; documentation is accompanying
  work, not a reason to stop implementation.

The pre-change checkpoint is `14b27f7`. The initial isolated native benchmark
imports no Pygame and revealed 10.79s of import work before a 0.30s four-actor
encounter setup. Its profiled import includes a 6.83s static source-closure walk;
that value includes profiler overhead. The old 64-by-64 diagnostic constructs
a different, much larger map and must not be presented as the same workload.

The [September 11 source audit](ANIMATION_COMPOSITION_AUDIT.md#event-recording-contract-correction--september-11)
records C01–C06 findings against native history and the current capture/export
path. It attributes the serialization failures to the new recording/consumer
boundary rather than the Event registry separation, identifies the omitted
actor-admission connection, and records a native unequip operation whose active
weapon after-value is lost in presentation. Existing subjectivity authority
remains intact. The user then explicitly corrected the premature stop after
documentation; implementation continued in the same work unit.

The working tree now implements passive concrete event decoding, native active
weapon after-values, initial sensory events, event-based initialization, and
saved-input gallery replay. New actor admissions use private recorded history
at actual observation; hidden births and their private state mutations are not
added as retained initialization event payloads merely because they exist.
Objective diagnostic headers remain in the local archive. Sword removal
selects the surviving bow at the original Studio commit frame before the next
ranged attack. All 72 saved-input clips replay with identical video and input
bytes and matching gameplay state. See [RECOVERY_PLAN](../RECOVERY_PLAN.md) for
measured checks, the diagnostic cache-hash exception and the final gallery.

C01/C02/C05/C06 are implemented for the current retained event families. This
does not claim archival of arbitrary executable engine object graphs or complete
inventory/drop/destruction presentation.

C03/C04 were **partial at `12ae1eb`**: observer-movement discovery and later deployment were
covered, but the existing capture gate rejects an unseen actor moving into view.
The retained local archive also still contains objective diagnostic headers,
world data and foreign sensory rows. Actor admissions retain full item records;
the existing distinction between controlled inventory and other actors' visual
loadouts still needs applying at transmission. The archive must not be called a
player transmission payload. These limits do not justify inventing different
subjectivity rules.
The complaints above remain the acceptance requirements, independently of these
implementation notes.

**Visibility unit implemented:** unseen entry, timed contact loss
and reacquisition now cross serialized public player events. Private native
archives are separate. Equipped visual layers/active set, own sensory deltas,
observed world memory and causal structure reach playback; foreign inventory
and objective diagnostic rows do not. Fifteen native experiments are recorded
from both participants, with all four corners per viewpoint. All 30 clips replay
from public bytes with native generation disabled and reproduce their capture
videos exactly. Six paired lethal-reaction/forced-movement clips pass the same
boundary; the controlled mover retains its interrupted corpse position.

C03/C04 and the paired-view requirement C10 are implemented for the connected
event families. Other actors' equipped appearance is public; their full item
records are not. The native archive remains a separate local diagnostic artifact.
These results do not claim full inventory/drop/destruction presentation or all
Studio animation primitives. RECOVERY_PLAN links the review galleries and records
the final checks and remaining broader gameplay work.

## September 18 — environment work must go beyond known assets

- The first asset study overfocused on familiar doors and chests. The user
  explicitly asked for levers, switching off placed lights, and broader
  environmental interactions.
- Study the meaningful gameplay and state changes each prop supports, rather
  than treating the presence of a sprite as the outcome.
- The user then clarified that new backend behavior is part of this work.
  Existing native actions are a starting point, not a limit. Author missing
  states/actions/events where the selected interaction requires them; presentation
  still consumes recorded subjective facts.
- The first connected examples exercise real light-control consequences and
  linked trap deactivation. The next backend design covers controls linked to
  doors/lights and real container open/closed state. Do not claim those new
  mechanics are complete merely because suitable art already exists.
- Reviewing the torch videos, the user identified missing physical interaction:
  previously inspected arm-extension animations were not playing. Environment
  actions must play an appropriate gesture, and their object effect must appear
  at hand contact, like an attack. Imported disabled/instant environment recipes
  do not satisfy this. Connect the shared gesture and causal effect anchor while
  continuing the authorized backend unit; do not turn this correction into a
  separate VFX project or delay native event processing for rendering.

## September 19 — trap mechanics precede trap presentation

- Concealed spikes are down and are not drawn for an unaware observer. Detected
  spikes are visible while down. Activation raises them until deactivation;
  reactivation raises them again. Deactivation must not erase prior discovery.
- These are backend gameplay states governed by handlers. Descriptions must
  reflect the state the observer knows. Do not place animation cues in backend
  state or infer gameplay from sprite frames.
- Plan this small feature before resuming the paused art integration. Explore
  content reuse beyond spikes, starting with variants such as poisoned spikes;
  a dozen proposals are a study, not twelve new mechanisms or implementations.
- The [trap plan](TRAP_STATE_PLAN_2026-09-19.md) records the shared first unit;
  the [variant study](GROUND_TRAP_VARIANTS_2026-09-19.md) distinguishes existing
  native capabilities from missing connections and proposed art.
- Acceptance tests must follow the same complete narrative as the videos:
  enter, exit and re-enter raised spikes; lower them with a real lever; cross
  safely and remain inside; have the other character raise them and damage the
  stationary occupant. Record detected/undetected cases through real actions,
  both subjective viewpoints and all four camera corners.
- The delivered poisoned art should use authored content identity. The new
  bloodied artwork suggests a reusable condition, independent of a trap's
  mechanical state and potentially applicable to other tiles. Study the existing
  condition owners before deciding its application/persistence semantics;
  do not quietly turn every damage event into a universal bleeding rule.
- The review UI must make saved runs accessible; an older focused gallery is
  not an all-catalog browser. The user also proposed video pixel differences
  as regression evidence and explicitly requested documentation only for now.
  See the future comparison note in `devtools/animation_review/README.md`;
  do not turn it into runtime hashing or an unrequested testing framework.
- Bloodied belongs to the tile, initially inert but available for later
  elemental/magic interactions. The user proposed one map-wide damage handler
  conditioned on the damaged creature having blood, superseding the assistant's
  spike-only trigger proposal. The user explicitly requested further study before
  implementation and questioned adding a dedicated boolean to entities. Study
  existing reusable body/feature data; do not replace that question with a new
  physiology framework or silently choose biology and damage-type policies.
- The user refined that proposal to a handler on each creature, releasing blood
  or other authored substances when damaged: poisonous fluid, bone fragments and
  smoke can select different effects. Share one processor configured by body data.
  Blood splatter leaves authoritative tile residue; a known spike trap on that
  tile uses its bloodied variant. Keep repeatable release events separate from
  persistent tile state, and keep particle simulation out of native state changes.
- The full plan must include skeleton bone bursts and potential ground fragments,
  plus demon-package variants whose residue can damage or provoke a low-DC fear
  save on entry. Preserve the existing modular skeleton Body 2 route as well as
  the dedicated `Documents/assets/smallscale/2D HD Undead pack 1.zip` art path.
  These are shared native capabilities with authored content, not independent
  VFX demos or grounds for replacing the existing rigs/creature mechanics.
- Jumping or flying over a floor trap must not activate it; native regression
  tests for this are mandatory. Landing/contact is distinct from crossing its
  horizontal cell, including a flying movement endpoint. Misty Step arrival on
  the trap is ground contact, while intermediate tiles are not visited. Actual
  flight touchdown must be exercised through native state/actions once connected,
  not manufactured by direct position writes or inferred from rendered height.
- The user explicitly prioritizes repairing the demonstrated jump/floor-trap
  defect before adding blood, bone and demonic residue features. Do not carry
  the known failing contact contract forward as an accepted limitation or bury
  its repair behind art work or a broader flight-system redesign.
- The user proposed ground/air/underground movement facts and air-only spells or
  storms that strike flyers. Retain the native location layer between actions,
  including hovering, and carry it through recorded events. Effects declare
  which layers they affect; reuse spatial handlers instead of globally ignoring
  airborne entries or deriving rules from animation height.
- Dread blood fear must compel retreat toward the actual previous cell and charge
  movement for it. Exiting the pool in that direction removes the fear; inability
  to retreat/pay leaves the creature there frightened, with escape still possible
  when movement becomes available. Do not substitute generic Frightened's zero-
  movement cap, a free shove, a one-round timer or an animation-only recoil.
- Do not turn the jump/floor-trap repair into a flight feature. The user clarified
  that movements land, then explicitly corrected the expansion into hovering,
  dedicated landing controls and wing-dismissal rules. Keep jump takeoff, airborne
  crossings and actual ground contact; remove the invented flight prerequisite
  from both implementation and plan. Shared layer data is not authorization to
  build every movement mode now.
- For Misty Step into dread blood, the user approved one paid adjacent retreat
  toward the departure point. Teleport does not invent an adjacent previous cell.
- Ordinary humanoid blood should have amounts ranging from a small splat to an
  almost-full pool. Carry this forward without interrupting the active unit;
  recorded tile state must select the amount. Injury thresholds/accumulation
  have not been chosen, and the requirement does not automatically expand bone
  or demon residue profiles.
- Artwork handoff files are a queue, not instructions to switch tasks. Complete
  the approved mechanics/replay unit before pursuing unrelated spells or VFX.
- Projectile art must retain NeuroClient's small residual rotation between the
  eight authored directions. The user noticed Eldritch lacking this in the new
  clips. Selecting a real direction row and aligning it to the actual trajectory
  are both required; a limited handoff preview must not disable the original
  recipe's behavior. Keep the correction in shared presentation/data ownership.
- Ashen must appear with Fireball contact and can expand outward with the blast;
  waiting until the whole animation finishes is incorrect. The user also found
  Fireball travel too slow and requested a roughly 20% larger projectile. Keep
  travel tuning separate from the calibrated explosion size, and keep contact/
  reveal timing in presentation while native conditions remain authoritative.
# 2026-09-19 — Fireball leaking over foreground boundaries

User identified fire leaking from behind the wall/door in “Fireball · east
boundary · caster”, camera 0, run `20260919T162630Z-c573f3`, and requested a
first-principles correction. The complete area image and individual boundary
segments cannot be ordered correctly by their separate center-Y keys. Prior
ground-mask tests were insufficient evidence for final scene occlusion. Fix shared
composition using physical boundary geometry and actual sprite silhouettes;
preserve native mechanics and the already corrected timing/size.

### September 20 — weapon motion must agree with the represented attack

The user caught a piercing critical rendered as a broad slash in the release
gallery. The imported global critical/elemental profiles were overriding the
weapon family; passing replay checks did not establish visual correctness.
Use authored weapon-specific choices first, with damage type as fallback. The
user suggested an overhead dagger critical. Keep clip, contact and effects in
recipe data; do not create weapon conditionals in playback. Face participants
toward each other in ordinary review examples and include deliberate backstab
examples. Rear facing itself does not authorize new combat bonus rules.

### September 20 — blood volume and repeated-hit coverage

The user approved the weapon-motion correction but found gore too restrained
and too few tiles affected. They asked whether the gallery used current blood
work and requested comparison with the art task's repeated blood/poison/bone
examples. The current game uses the compact normalized region candidate, not
the approved wide 96-particle blood reference. Its dagger accumulation case
contains seven real hits, caps at five units, and retains the same two receiving
tiles. Bones/corrosive/dread currently cap at one; poison has art only. Art
previews show five amount stages for every material and wider proposed layouts.
Those preview controls are not implemented native gameplay. The compact
artifact's imported particle fields match the current handoff. Do not call
this full parity with the heavier or wider art demonstrations.

### September 20 — the compact correction still missed the inspected reference

The user rejected `20260919T235102Z-e50471`: the two-goblin reference had much
more blood, spread across neighboring tiles, and more dynamic spray. The art
task relayed clarification that this reference is the high end, while the game
should be moderately high. Increasing tiny ellipses while preserving the wrong
compact replacement did not address that request. Compare the actual approved
`blood-fluid` source and in-game first/repeated hits; do not treat asset parity,
passing replay tests or reviewers accepting that narrow framing as visual
acceptance. See `BLOOD_REFERENCE_CORRECTION_2026-09-20.md` for the correction.

### September 20 — use the intended creatures in material examples

Bone demonstrations must use skeletons, preferably the premade Undead pack.
Toxic demonstrations can use orcs for now. Correct the main and repeated-hit
catalog entries, including the mixed scene's separate bone donor; an isolated
premade-skeleton card does not fulfill the request while other bone cards still
show a modular clothed body. The Orc example is an explicitly configured
corrosive review creature, not a change to every Orc's biology.

### September 20 — review graphics ownership and actual NeuroClient portability

After the Ray/Ice Knife contact-height correction, the user challenged the
accumulation of manual placement and tuning. Review the graphics pipeline as a
whole: distinguish authored reusable data from ad hoc compensation, and verify
what the TypeScript client/editor can actually consume with minimal adaptation.
Putting a correction in JSON does not establish a coherent shared contract.
Measured media pivots and rig/clip sockets remain legitimate authored data;
per-spell repairs must not conceal conflicting coordinate ownership. See
`GRAPHICS_PORTABILITY_REVIEW_2026-09-20.md` and its independent format/ECS reviews.
This request is for review before further graphics refactoring.

Follow-up: rejection by the old TS schema is not itself a design defect; extending
an overly restrictive schema is acceptable when justified by real behavior.
Properly tuned, stable numerical positions are acceptable, and a comprehensive
keypoint system would be excessive. The user specifically identifies scattered
importer authoring/inheritance as a serious problem. Distinguish genuine missing
presentation support from the potion VFX strip they had explicitly deferred;
drinking animation and native effect timing already work.

Further clarification: omitted VFX strips are acceptable, with the current focus
on target-side spell presentation; leave potions as they are. Proper jumping is
already implemented. Empty optional walk/jump effect tracks and disabled extra
recovery clips are not missing movement/landing and must not become new work
merely because their legacy fields are retained.

### September 20 — cleanup coverage must be lean; preserve rendered approval

The user requests an organized data-driven cleanup plan and an inventory of
digestible events and missing presentation. Derive that inventory from existing
initialization/registries and bindings; no SHA, source audits, asset-folder
validation or other slow bookkeeping. Event-family ingestion, content bindings
and observed playback are different coverage questions.

The user explicitly approved **final rendered results, not JSON values**. Current
code applies transformations and post-processing after those values are read.
Preserving raw values while changing their consumer can cause regressions.
Establish the effective visual baseline from code, data and selected media;
compare the same recorded inputs before/after cleanup. Values may change to
preserve appearance and timing. Distinguish user-approved outputs, current
captures and known defects instead of labeling every present value approved.

### September 20 — Web pacing and oversized Poison Spray

The user found the pause/slow buildup between Web's projectile and deployment
unacceptable. Inspection separated correct contact/event timing from slow source
growth. The existing field binding now plays the expansion faster and omits its
redundant static tail, preserving the resting field.

The user then found Poison Spray enlarged and visibly coarser than its export.
The renderer had overridden authored scale to make the whole cloud span the
target distance. This is not an approved interpretation of the asset: preserve
its particle size and authored scale. An endpoint-equality test had reinforced
the wrong premise. It now checks scale, hand anchoring and aim independently.
Any remaining range/contact mismatch must be addressed explicitly, not concealed
by enlarging the raster. See `SPELL_BATCH_RESULT_2026-09-20.md` for the observed
maximum-range arrival limitation and queued source/contact handoff.

The user then rejected the range-v3 gallery's direction, apparent backside
emission and cloud travelling beyond its recipient. Poison Spray is a single
target spell in this engine; its appearance must not imply an unrecorded area
or lingering hazard. Checking one contact frame was insufficient. The long
baked source trajectory and large rotations at overlapping projected contacts
are reproduced in `POISON_DELIVERY_CORRECTION_2026-09-20.md`; that correction
must inspect onset, the entire journey and dissipation in all four cameras.

### September 20 — preserve approved Fire Bolt; animate Sleep poses

- Fire Bolt’s previously authored placement was changed without a demonstrated user problem. Restore its original registration/offsets; “shared target” tests cannot overrule approved pixels.
- Sleep must play the fall, hold the sleeping body, receive hits at that body, and reverse the fall to rise after actual wake-up when alive. Keep native damage/state timing.


## 2026-09-20 — spell injuries must release the creature’s material

The user noticed missing blood with spell damage and asked whether it had been
bound to weapon types. The cause was a physical-damage-only native filter plus
missing body traits on newer review actors. Spells must use the existing injury
and residue path. Any spell coloration must be **very light**: blood stays blood,
bones stay bones, and deposited material keeps its palette and native properties.
No spell targeting or authored registration change is part of this correction.


## 2026-09-20 — restored spell releases are too uniform

A shared blunt burst plus a subtle tint is not the final injury presentation.
The user requests distinct responses for every spell damage type, explicitly
all thirteen engine DamageTypes, with examples of frozen fragments/cold vapor,
fire steam and stronger force splats. Material identity remains primary. The
reviewed response plan and queued art brief cover these variations without
per-spell executors or renderer-invented receiving tiles.

## 2026-09-21 — portals share gameplay; backend first

The user requests bare portals and a trap hatch opening over a portal to share
one native behavior. A physical pit is unsuitable for the current one-support-
per-X/Y world. Existing portal donors should be reused; the Godot task may
prepare the hatch/portal composition, while implementation and necessary game
fixes proceed independently. Do not make mechanics depend on art availability
or invent a separate gameplay implementation for each appearance.

### September 21 — trap work was narrowed incorrectly to portals

The user asked "what about the traps" and then objected that the portal was the
one mechanism without delivered assets. The broader reviewed trap plan remained
authorized. A recent design conversation about portals did not replace that plan
or justify returning after only that slice. Resume plates and delivered mechanisms,
validate real native events and produce paired four-camera clips. Keep portal art
separate until its delivery is ready.


## September 21 — portal passage and trap avoidance corrections

- A successful ground-trap reflex save must relocate the creature back to the
  actual previous cell; never animate a hop that settles back inside the trap.
  Reuse that behavior for appropriate plate-triggered ground mechanisms.
- Open hatches must start the fall immediately, including at the end of an
  incoming jump. Opening hatches need only a short contact delay and an
  accelerating fall, not a mid-air pause.
- Include walking into visible closed/open hatches and jumping into open ones,
  from traveler and both endpoint witnesses, using actual saved native events.
- Bare portals must clip the descending body at their own floor opening. Hatch
  hardware is optional; its larger aperture cannot stand in for the bare ring.
- Exiting a portal also needs motion: emerge through the opening and settle.
  Upright, wall-like portal entrances/exits should eventually use horizontal
  passage, but the user explicitly deferred them to another day. Keep the
  current work limited to ground portals and hatches.
- Damage inside blade/crusher doorway frames must respect physical occlusion;
  UUID ordering must not decide whether the character paints over the frame.
- Traps injure the creature's configured material through ordinary damage types.
  The blood-only material handoff is authorized; its lab spell scaffolding is not.

## September 21 — projectile orientation and lever use

- Fireball's travelling projectile must follow its flight direction; the ground
  explosion must keep its floor orientation. Use separate existing phase settings.
- The authored lever motion must actually play when the lever is successfully
  used, including resetting sprung traps. A working linked trap effect alone is
  insufficient: retain the physical handle change in native events and replay it
  at the user's hand contact.

## September 21 — lethal opportunity attack missing blood

The walk → opportunity hit → downing video had no visible blood. Damage must
still release the creature's configured material when its consequence is DYING
or death; a severe injury should not visually lose its blood because of that
transition. The diagnosed case omitted its existing blood-response fixture
option, so its saved damage carried no release. Correct the real experiment,
preserve both subjective recordings, and verify the spray and ground residue
alongside the interrupted fall. Existing critical amplification remains intact;
a separate lethal-hit multiplier has not been authored.

## September 22 — liquid barrels need real areas and coherent spilling

- All six liquid barrels must spill over surrounding ground (up to 3×3), with
  actual native effects across that area; a larger picture on one cell is wrong.
- Water currently pops into existence. A visible liquid-spilling animation is a
  necessary result; the user permits queuing it but not calling it completed.
- The static output is also inadequate: use material tile-map-like artwork
  whose interiors, borders and corners follow the desired pool pattern. Favor
  rounded/circular outlines over a square patch or separate repeated splats.
- Grease art remains deferred to its accepted spell handoff. Keep gameplay
  ownership separate from authored media and preserve accepted injury output.

Later approval supersedes that Grease-media deferral for this liquid unit:
Godot supplied all six materials × three approved irregular variants, including
Grease. All 18 are now integrated through the shared deposition path; see the
[result](LIQUID_MEDIA_INTEGRATION_RESULT_2026-09-22.md). This does not authorize
unrelated spell behavior or imply the separate Grease spell integration is done.

## September 22 — latest spell review omitted blood; limit review scope

The new spell clips again created humanoid fixtures without their existing
blood-response behavior. Damage alone is not a complete demonstration: ordinary
injury must retain real material-release events and persistent floor residue,
including damage received while exercising protection/transformation spells.
Correct the creature composition and recapture affected real gameplay inputs;
do not invent blood in presentation or edit recorded events after the fact.

The next feedback gallery must include **only the latest fourteen-spell batch
and barrels**, not all 59 historical spell presentations. Preserve the existing
four-camera and paired-perspective review workflow within that smaller scope.

### September 23 — interruption timing and Counterspell expression

- Sanctuary and Counterspell cut off direct/non-projectile attempts too early;
  give their casting body several more visible frames without accelerating it.
- Counterspell should visibly express one mage anticipating and breaking another's
  magic, including dispersal of an emitted projectile, rather than an abrupt cut.
- Preserve actual recorded outcomes and ordinary approved spell behavior while
  adjusting these shared presentation rules; review the same saved input sequences.
