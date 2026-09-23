# Ten authored spells: implementation and validation

Status: implementation, independent review, regression verification and saved-event gallery complete. Human visual approval pending.
User authorized this work after the door/trap work, while AFK. That previous
unit is complete. This document is the active slice of RECOVERY_PLAN.md.

## Requested behavior and boundary

Integrate the delivered Inflict Wounds, Hellish Rebuke, Shatter, Misty Step,
Bless, Bane, False Life, Jump, Expeditious Retreat and Haste artwork. Real native
actions produce subjective serialized events. Playback consumes those saved
events independently of the engine and keeps authored media attached to the
correct participants, locations, conditions and motion. No artwork invents a
rule, damage recipient, movement distance or effect lifetime.

Source: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/recovered-pending-spells-2026-09-21/COMPLETE-SPELL-HANDOFF.md`.
All ten spells now have genuine eight-direction exports. The original Godot task
completed `delivery-buffs-directions-v1` and `delivery-movement-directions-v1`
during integration, preserving approved SE pixels. The importer copied 36 assets
(18 rear/front component pairs) into the ordinary paged media store.

## Findings and ownership

* Existing StudioMediaTrack plus paged projectile storage already represents
  finite ground-registered rear/front layers. Inflict and Hellish are recipient
  effects; Shatter is one area effect. No new per-spell drawing function.
* Hellish Rebuke is a native reaction ActionEvent inside the triggering damage
  lineage. Registered probes confirm its semantic identity already exists;
  adapt the existing delivery binding rather than create a second spell event.
* Shatter owns its ten-foot sphere and saves already. Its execution currently
  does not retain resolved area cells: use the existing area-target resolver so
  replay receives the actual footprint, as other area spells already do.
* Misty Step is an existing body-action relocation. Ordinary cast-media binding
  would currently bypass it. Keep that relocation clock and add registered
  finite endpoint tracks using independently disclosed departure/arrival facts.
  Never obtain an unseen endpoint from the native world or interpolate between
  the endpoints. One body, one committed relocation.
* Current condition layers execute static images only. Extend that existing
  composition to paged media and its already-authored activity selectors.
  Application and sustain are phases of the same retained condition membership;
  they must follow the actor and must not block subsequent action heads.
* Dash already has public condition.dashing membership. Reuse it. Native movement
  facts do not retain resolved numeric locomotion speed. Record that value at
  execution through the normal fact/projection path, keeping visibility rules.
* False Life temporary HP has no retained grant identity. Add passive grant
  ownership to the existing temporary-HP change/snapshot contract, so a replay
  can distinguish depletion, replacement and an unrelated grant. Do not invent
  a visual condition or bind the aura to ordinary HP or concentration.

## Implementation order and boundaries

1. Native facts and tests: complete the three missing data contracts above and
   preserve registered Hellish provenance. Exercise real casts/reactions, replacement,
   movement and projection. Repair the two retired Shatter wall test fixtures
   using the current wall-placement API; preserve their original expectations.
2. Package delivered media into the existing atlas storage, preserving original
   pixels, frame counts, fixed pivots, palettes, rear/front order and directions.
   Importers copy/describe media; independent authored recipe JSON owns behavior.
   No inherited spell settings, index-based socket copying, palette rewrite pass,
   runtime hashes or source-file audits. Never preload hundreds of frames into
   the body-row cache; use the existing bounded paged-media decoder.
3. Shared condition presentation: extend condition media records for application
   and loop banks, reuse condition composition/priority and absolute presentation
   time, and execute existing activity/ground-body attachment semantics. A stable
   membership retains its phase across action heads and refresh; removal ends
   only that membership, with the authored short fade. False Life uses the same
   presentation lifetime mechanism with its actual temporary-HP grant owner.
   All lifetime bookkeeping is local playback state derived from recorded facts.
4. Finite spell integration: authored recipes bind actual hit/reaction/area
   recipients; Inflict omits miss media, Hellish targets the triggering attacker,
   Shatter applies simultaneous native contact. Ground registration already
   contains torso height. Add Misty endpoint media without changing its native
   relocation/reduction path or duplicating its body.
5. Movement integration: sample existing resolved motion legs, contact and height.
   Quiet loops follow condition membership; takeoff/landing stay at actual ground
   endpoints, flight follows the airborne body, trail emissions remain at their
   historical path positions. Actual Dash membership selects the stronger trail.
   Native resolved speed informs the shared movement clock once. Preserve one
   jump animation cycle over airtime and pre-takeoff reaction behavior.
6. Haste action timing: an explicit authored presentation policy scales the actor
   body, hand preparation and release/contact together at binding. Spawned
   projectile travel retains its own clock. No global elapsed-time multiplier,
   synthetic extra attack or copied browser-preview speed constant.
7. Real saved-event clips and regression verification, then update this document
   with actual outcomes and remaining limitations. No declaration of completion
   while any delivered spell is still only an asset import.

## Data and rendering constraints

The same authored JSON must remain intelligible for a later TypeScript consumer.
Use existing NeuroStudio tracks and explicit, small extensions where an actual
capability is missing; document each extension in PRESENTATION_CONTRACT.md.
Keep original static condition images and Sleep/invisibility behavior working.
The independent presentation clock owns visual phase, never the event-ingestion
clock or wall time. Sampling/seeking does not mutate native mechanics.

Four-second buff applications must not freeze the actor or action queue. Their
application-to-loop transition is condition-owned, not an extra gameplay event.
Do not reset a sustain loop at every action head. Reapplication/replacement must
use the actual retained instance/source semantics, not spell-name guessing.

Use the authored palette on actual magic hand layers and ordinary damage flash.
Do not tint skin/equipment or turn Bane's decorative drops into blood mechanics.
Do not move the approved Fire Bolt sockets, normalize unrelated spell anchors,
or apply a second torso lift to ground-registered art. Preserve complete tails
and exclude duplicate seam observations from loops.
The new orbit exports have a fixed world-space basis. Select their view from
that authored basis and camera orientation, not the attacker's facing; existing
directional projectiles keep their present facing-driven registration.

## Observable acceptance cases

Tests follow HOW_TO_TEST.MD: native command -> authoritative events/state, then
serialized subjective packets -> presentation. No mocks of engine internals,
source-text assertions, giant pixel framework or invented event scripts.

* Inflict: successful melee contact and miss, stationary caster, correctly placed
  recipient effect and blood response from actual damage.
* Hellish: actual damaging attack triggers a legal reaction, correct attacker
  receives fire/save/damage, ancestry and visual timing retained.
* Shatter: simultaneous multi-recipient saves/damage, actual affected footprint,
  blocked/raised terrain, no visual propagation of native damage timing.
* Misty: source and destination witnesses, source-only and arrival-only observers,
  one relocation, preserved equipment/pose, independently stationary mist.
* Bless/Bane: multi-recipient application, Bane save success omitted, bystanders
  unaffected, actor movement during application/sustain, coexistence, refresh,
  removal/concentration loss without duplicate or restarted phase.
* False Life: self-only grant, partial absorption, depletion, replacement by
  another grant and another False Life cast. Aura follows exact source ownership.
* Jump: short/long/raised/blocked movement using actual native results, one body
  cycle, correctly anchored takeoff/flight/landing and existing reaction behavior.
* Expeditious Retreat: normal movement retains its native speed; actual bonus Dash
  enables the proper allowance and stronger trail; normal Dash also remains valid.
* Haste: native movement and actual Dash, attack and spell cast use one coherent
  action clock; projectile flight stays unchanged; removal follows native state.
* Media: all four cameras, relevant facings and actor perspectives, no direction
  substitution, alpha/depth/palette registration at normal speed and contact frames.
* Replay: recorded sequence is sufficient after engine reset, no foreign sensory
  leakage or objective lookup. Existing finite spells, Sleep, equipment, motion,
  portals and conditions retain their established contracts.

Produce a tagged gallery with paired observer clips and all four cameras per
clip; inspect representative motion and frames. Reuse the existing extractor.
Capture approval remains a human visual decision; report automated proof and
actual self-inspection separately.

## Required reviews

* Anti-slop reviewer: GO. Caller-owned immutable media lifetimes derive from
  bound condition contacts plus absolute presentation time. Existing membership
  starts in quiet sustain; no fabricated application when an actor is first seen.
* Anti-OOP/ECS reviewer: GO. Grant ownership changes only for an accepted
  replacement, survives partial absorption and is included in late observations.
  Step speed is captured before arrival hazards. Refresh preserves actual
  source/instance identity, without merging unrelated same-name grants.
* Media intake: complete. Fixed cells, pivots, native frame counts, loop seams,
  palettes and the distinction between camera views and actor facing confirmed.

Out of scope: upright portals, new spell/art concepts, flight/hover mechanics,
generic visual regression infrastructure, unrelated engine redesign or cleanup.

## Implemented result

* `pending_spells` owns ten independent Studio draft records. Packaging preserves
  these records; import does not borrow another spell's behavior. Registered
  native Hellish Rebuke reuses its spell draft through `actionDeliveries`.
* Native health retains accepted temporary-HP grant UUID/source. Native committed
  voluntary steps retain resolved speed. Shatter uses the existing area resolver
  and retains its affected cells. These facts survive subjective initialization,
  updates and serialization; presentation does not query the objective engine.
* Existing condition composition executes paged application/sustain art on actual
  membership dates and a 350 ms removal fade. False Life uses actual grant
  ownership through the same path. Motion tracks use disclosed legs, fixed
  historical trail positions and body/support attachment. All JSON extensions
  and their shared execution requirements are in `game/data/PRESENTATION_CONTRACT.md`.
* Haste uses recorded doubled locomotion speed once, with a separate authored
  1.25 actor action rate. Body, hand preparation and release stay together;
  projectile flight and target media retain their own clocks. Dash changes
  allowance/trail intensity, not locomotion speed. Jump remains one cycle over
  resolved airtime, with authored ground anticipation after preflight reactions.

## Review corrections and evidence

Independent actual-event presentation tests exposed two Hellish selection
errors: parent attacks included registered action children in their own damage
packet, and the old body-only reaction record intercepted the new selected
draft. Both now respect the same nested-action ownership as ordinary casts.
Hellish binds one incoming attack and one reaction cast for both save outcomes
and both observers. Its existing TakeDamage callback remains 166.67 ms after
injury in this rig; no timing is copied from the artwork browser.

Other review corrections preserve Haste's preparation duration, departure-only
Misty witness placement and the Jump takeoff's initial frames. Condition facts
now pass through their existing reducer at the compiled condition contact,
preserving recorded AC/max-HP changes as well as visible membership. Temporary-HP
changes likewise commit at their owning contact. Expired condition fade records
retire at subsequent head admission without mutating old seekable mappings.

The initialized coverage report now describes registered reaction delivery as
an action using its selected cast draft, rather than an unrelated spell entry
plus the retired body-only selection.

New real-event story/presentation/packaging selection: **60 passed** (35
presentation, 20 native story/replay, 5 packaging). The broader presentation
selection initially passed **239 tests**, and selected production modules pass
Pyright. Later condition-contact corrections and older contract tests receive
their own final verification below. Counts overlap; they are not a sum of
unique repository tests or a claim that the full repository suite was run.

Final combined selection after all corrections: **353 passed in 167.72 s**.
It includes the four `test_pending_*` modules plus teleport, movement routes/
interruptions, support replay, animation, spell body release/shared targets,
Sleep, Web, portals, condition media lifetime, attack animation, choreography
recovery, condition appearance/drawing/lifecycle, death playback, weapon motion
and presentation coverage. No failed or expected-failure result remains in this
selection. The two older recovery tests now select the actual concentration
removal among legitimate residue conditions; the lethal cast test preserves
release/contact/death/single-body assertions while allowing its already-existing
finite blood tail to extend the complete-lineage join.

Native/public-fact validation: **104 passed in 32.55 s** using:

```bash
uv run --no-sync python -m pytest -q \
  tests/game/test_pending_spell_facts.py tests/game/test_consumable_replay.py \
  tests/manual/test_126_shatter.py \
  tests/manual/test_135_cleric_batches_2_4_5_legacy_contract.py \
  tests/manual/test_remaining_spell_legacy_contract.py \
  tests/manual/test_125_haste_restricted_action.py tests/engine/test_misty_step.py
```

All commands use the existing WSL uv environment at
`/home/tommaso/.cache/dnd-engine/venv`, with dummy SDL video/audio for rendering.
The working source remains this `/mnt/c` checkout. Independent final ECS and
anti-slop reviews report GO for the native ownership, reaction binding, condition
contact reduction and shared lifetime path.

Selected production/test modules pass Pyright with **zero errors**. Visual
inspection used representative contact, peak, decay and movement frames from the
four-camera renders: Inflict/Hellish recipient placement, Shatter at a wall,
Misty endpoints, Bless/Bane/False Life wraps and Jump progression. The imported
movement/mist artwork retains its delivered subtle alpha; no unrequested
opacity or anchor retuning was applied. This inspection is not human approval
or a pixel-regression guarantee.

## Final review gallery

[Open all 38 observer clips](http://127.0.0.1:8767/runs/20260921T021359Z-99af54/index.html).
The 19 native stories are paired by observer; each video contains all four
camera corners. The final run replays the original saved public packets, without
rerunning mechanics: **38/38 passed, 4,394 encoded frames, zero presentation gaps**.
It includes the final reaction, condition-contact and coverage corrections.

Files are retained under
`.runtime/animation-review/runs/20260921T021359Z-99af54/`; original inputs remain
under `.runtime/animation-review/inputs/pending-*/input.json`. The local review
server is serving port 8767. Earlier same-tag runs are intermediate captures;
this linked run is the completed implementation review. There is no outstanding
artwork delivery or known failed check in this unit; visual acceptance remains
with the user. Upright portals and generic pixel regression infrastructure remain
outside this unit.
