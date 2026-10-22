# Death, invisibility and encounter-ending investigation

Status: all three authorized repairs implemented and regression-tested in the
repair commit on feature/rules-checking, based on bedc3d92dc. The human authorized
"fix this shit" and making creature zero-HP handling configurable. Preserve
the separate selected-AoE plan and its settled connected-reach rule.

## Scope and observable questions

- Ordinary invisibility broken by casting: trace native cast, condition removal,
  sensory reveal, spell publication, damage and death in their recorded order.
  Compare visible and invisible casters using the same spell and damage outcome.
- Zero HP: explain dying versus immediate death, including massive damage and
  the source of enemy death-save policy. The human wants enemies to die at zero
  HP, rather than remain downed; identify the existing owner of that policy.
- Encounter completion: verify the previously requested rule ending combat when
  a side has no conscious combatants, and distinguish zero-HP/unconsciousness
  from temporary conscious action denial. Trace the public terminal boundary.
- Inspect available client handoff/code/recordings only to establish what the
  backend sent and which backend is running. Do not read other chat threads or
  edit the client. Exact reported encounter/spell is requested asynchronously.

## Execution

1. Inspect code owners and existing regressions before drawing conclusions.
2. Reproduce through native events and actual player projection/worker where
   needed, using existing creator-backed fixtures. Read HOW_TO_TEST.md first.
3. Record confirmed causes separately from hypotheses and missing reproduction
   information. Explain existing test gaps and propose the smallest repair.
4. If a repair is undertaken, record its exact boundary before editing, keep an
   adherence reviewer active, and validate event order plus relevant gameplay
   timing. No general sensory redesign or new life-state framework.

## Independent reviewers

- Antislop/scope and plan adherence: free_aim_scope, reviewing defeat/end policy.
- AntiOOP/ECS and event ownership: free_aim_ecs, reviewing invisibility/reveal order.

## Findings

- Both actual Gallery recordings end with the player DYING, reason DAMAGE:
  `20261022T134835.665203Z/journal/0000000000000014.json` records 28 Lightning
  damage; `20261022T151105.771533Z/restart-50eeba43-4ccc-442f-a910-8ab13152d639/
  journal/0000000000000039.json` records the fighter's finishing blow. Both
  publish `outside_encounter`. The lightning record contains no spell fact and
  its damage source is undisclosed. These are client-repository player-run paths.
- Native conscious-ending regressions pass (21 selected tests). The current
  client launch pin is bedc3d92dc and contains that native fix. Worker boundary
  currently returns outside_encounter for every ended encounter, including loss.
- Character creation hardcodes uses_death_saves=True; the Gallery fighter
  sentries inherit it. The authored arcanist defaults False. Existing entity
  damage already supports both policies; no new death subsystem is needed.
- Massive-damage behavior predates this work (blame da5d224de1, July 1). It did
  not cause either recorded Gallery outcome and is not changed by these repairs.
- Ordinary spell-invisibility reveal occurs at spell EFFECT. The simultaneous
  area group deferred sensory settlement until after the target lost consciousness.
  Native/public reproduction confirmed both late reveal and missing lethal SpellFact.

## Authorized repair boundaries

1. Expose an optional `uses_death_saves` override on each EncounterRosterMember:
   False means ordinary death at zero HP; True enables existing death-save rules;
   omitted/None preserves the source's default. Apply before composition and
   starting damage. Omit None from serialized members so legacy recipe digests
   remain valid. Explicit True/False participate in the existing digest.
   Set the blue combat-scenario template explicitly False; the Gallery client
   copies these members when substituting fighter premades, so it inherits the
   authored enemy policy. No inference from AI/human controller or faction name
   inside damage resolution. Tests exercise both source types and both choices.
2. At an ended encounter, publish terminal for a defeated seat, preserving
   outside_encounter for surviving parties and existing post-victory actions.
   Base defeat on native consciousness and the seat's faction/party, not temporary
   inability to act or an opposing controlled survivor. Keep direct worker
   authorization consistent with the public boundary. Test real publication and
   HTTP admission for losing and surviving seats, including a conscious ally.
3. Reproduce and fix only the confirmed ordinary-invisibility cast/reveal
   settlement ordering. Preserve simultaneous target damage, unseen attack
   semantics and Greater Invisibility behavior. Test native and serialized player
   occurrence order for surviving and downed/dead recipients; keep true hidden
   sources hidden. Measure the affected cast and ordinary visible control before
   and after; do not add global sensory work or per-recipient settlement.

Implementation adherence remains assigned to free_aim_scope. A dedicated
zero_hp_policy implementer may own the bounded roster fields/assembly/fixture
and their tests; free_aim_ecs owns the reveal reproduction and repair review.
The parent owns public defeat publication, integration and final checks. Record
a backend handoff for client adoption; no client edits or chat messages.

## Completion and validation

All three repair boundaries above are implemented. The ordinary invisible spell
now records its post-reveal EFFECT version through the existing handler-result
path. This retains identity grants before damage removes the observer's sight.
Target applications and area finalization remain one simultaneous group; the
spell completion still follows its results. No public schema or SDK changes.

Pre-fix regressions reproduced rejected roster policy, defeated
outside_encounter publication, and three invisible Lightning Bolt delivery
failures (surviving, dying, dead victims). The corresponding controls passed.

Combined run: **102 passed in 37.23 seconds**, using
`UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run --no-sync python -m pytest`
with these files:

- tests/player/test_defeated_boundary.py
- tests/player/test_spell_invisibility_delivery.py
- tests/player/test_prepared_classes_http.py
- tests/player/test_summon_caster_defeat.py
- tests/engine/test_roster_zero_hp_policy.py
- tests/engine/test_encounter_conscious_end.py
- tests/engine/test_simultaneous_area_resolution.py
- tests/engine/test_simultaneous_rule_fixes.py
- tests/engine/test_simultaneous_groups.py
- tests/engine/test_ice_knife.py
- tests/engine/test_summon_caster_defeat.py
- tests/manual/test_50_counterspell_engine_contract.py
- tests/manual/test_190_encounter_recipe_foundation.py

The reveal owner's separate focused batch passed **86 tests in 23.85 seconds**,
also including standard conditions and fire surface contacts. These counts
overlap; they are not additive. Native consciousness plus the new worker/HTTP
defeat cases separately passed 23 tests. No full-suite or Godot visual run is
claimed. The HTTP regression starts the actual native worker, delivers SSE,
checks the defeat final cursor, acknowledges delivery, and rejects further
choices with game_terminal. Existing post-victory preparation remains usable.
Strengthened public geometry/resolution assertions passed all 12 reveal tests.
Reveal qualification covers ordinary top-level casts. Casting inside an already
open outer simultaneous group retains that outer settlement boundary; this is
not a general redesign of nested-event settlement.

### Why older tests missed this

- Native encounter-ending tests checked EncounterState.ENDED, while public
  outside-encounter tests covered victory/recovery; neither checked a losing seat.
- Existing invisibility checks did not combine a real revealing AoE with a victim
  losing consciousness and then inspect that victim's serialized spell/damage.
- Creature defaults were source-dependent. Replacing a monster with a creator
  premade silently enabled death saves because there was no roster-level override.

### Timing and review

Four 30-target Fireball samples per visible/invisible condition, before and after,
measure native cast including sensory work. Source is on /mnt/c; the Python
environment is under /home/tommaso/.cache. Setup, discovery, serialization,
transport and UI are excluded. Visible ranges were 141–201 ms before and
139–157 ms after; invisible ranges were 183–743 ms before and 138–525 ms after.
Busy-machine/GC variance prevents a speedup claim. Visible casts retain 34 sensory
events in one settlement. Invisible casts now emit 67 in two settlements: reveal,
then shared damage. There is no per-target settlement or new sensory subsystem.
The roster override runs during setup; defeat faction scanning runs after ENDED.

Raw samples, probe and reproducible timing setup are in the local ignored
[audit directory](../audits/DEATH_INVISIBILITY_2026-10-22/). Important results are
recorded here so this plan does not depend on the ignored artifacts being shipped.
Plan adherence/antislop reviewer free_aim_scope approved the complete diff and
validation with no blocking findings. Independent antiOOP/ECS reviewer
zero_hp_policy approved the reveal/defeat changes with no actionable findings
and independently ran 35 defeat/reveal/consciousness cases successfully in
12.74 seconds. That agent's policy implementation was independently reviewed by
free_aim_scope. No new runtime framework or per-target sensory settlement was
introduced.

Client adoption and exact field semantics are in the
[backend handoff](../DEATH_INVISIBILITY_CLIENT_HANDOFF_2026-10-22.md).
