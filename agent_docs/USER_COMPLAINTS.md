# User complaints and contracts we must preserve

Recorded 2026-09-11 on `codex/recovery-design` during the event/archive audit.

This records the user's corrections from the conversation, including recurring
ones that explain the latest complaint. These are requirements and objections,
not evidence that an implementation satisfies them. Investigation findings belong
in a separate section with source evidence. Do not quietly weaken a requirement
to describe what the current implementation happens to support. This document
does not introduce new gameplay rules or authorize unrelated work.

## Immediate complaints: event recording and the client boundary

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
