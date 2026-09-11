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

C03/C04 remain **partial**: observer-movement discovery and later deployment are
covered, but the existing capture gate rejects an unseen actor moving into view.
The retained local archive also still contains objective diagnostic headers,
world data and foreign sensory rows. Actor admissions retain full item records;
the existing distinction between controlled inventory and other actors' visual
loadouts still needs applying at transmission. The archive must not be called a
player transmission payload. These limits do not justify inventing different
subjectivity rules.
The complaints above remain the acceptance requirements, independently of these
implementation notes.
