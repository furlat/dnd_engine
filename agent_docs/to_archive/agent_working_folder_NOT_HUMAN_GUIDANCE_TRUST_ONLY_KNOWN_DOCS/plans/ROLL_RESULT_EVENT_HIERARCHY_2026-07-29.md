# Roll Result Event Hierarchy

Date: 2026-07-29  
Status: COMPLETE  
Owner: backend engine

## Goal

Make dice interception a single official engine protocol rather than a set of
callback conventions.

The protocol must model the D&D rules seam after dice are rolled and before the
result is consumed. It must support:

- d20 replacement and additive bonuses for attacks, saving throws, and checks;
- selective damage rerolls;
- complete bonus-damage packets such as Divine Smite and monster traits;
- healing-die replacement or maximization;
- deterministic handler ordering and passive handler-effect evidence;
- immutable audit facts sufficient for analytics and debugging.

It must not retain legacy aliases, function-local imports, parallel event
families, or mutation-only handler behavior.

## Rules Meaning

There are three separate causal layers:

1. **Roll result**
   - The random faces and modifier total exist.
   - Lucky, Halfling Lucky, Bless, Bane, Guidance, Resistance, Leadership,
     Great Weapon Fighting, Divine Smite, bonus-damage traits, Unseen Strike,
     and Beacon of Hope act here.
2. **Outcome/application**
   - Attack hit/miss, save/check success, damage mitigation, temporary HP,
     normal HP, and applied healing are resolved here.
   - `TakeDamageEvent` and `HealEvent` handlers belong here when they alter the
     applied total rather than dice.
3. **Completed fact**
   - The accepted outcome is recorded for logs, presentation, replay, and
     analytics.
   - Completion is observational and does not dispatch handlers.

Mixing these layers makes rerolls indistinguishable from mitigation and causes
handler instrumentation to lie about what changed.

## Audit Inventory

### D20 result interceptors

- `LuckyFeature`
- Halfling Lucky
- Bless
- Bane
- Guidance
- Resistance
- Leadership

Concrete dispatch leaves:

- `D20RollResultEvent` for genuinely generic d20 rolls;
- `AttackD20RollResultEvent`;
- `SavingThrowD20RollResultEvent`;
- `SkillCheckD20RollResultEvent`.

Save/check category is authoritative even when optional ability/skill metadata
is absent. Death saves therefore remain save-result events rather than falling
back to a generic d20 category.

### Damage-roll interceptors

- Great Weapon Fighting;
- Divine Smite;
- `BonusDamageFeature` and its monster-trait subclasses;
- Unseen Strike.

### Healing-roll interceptors

- Beacon of Hope.

### Application interceptors reviewed separately

- Undead Fortitude;
- Relentless Rage;
- Relentless Endurance;
- Death Ward;
- Shield/Magic Missile prevention;
- Hellish Rebuke reaction triggering;
- ordinary `HealEvent` reduction/cancellation.

These are not dice-result transforms and must not be merged into the roll
hierarchy.

## Defects Found

1. `EventType.DICE_ROLL_RESULT` had no producer.
2. `DamageRolledEvent` / `EventType.DAMAGE_ROLLED` were dead predecessor
   contracts.
3. Trigger matching is exact, but stale documentation implied that a base d20
   trigger subscribed to attack/save/check leaves.
4. Result handlers mutated already-stored event objects.
5. Returning that same mutated object caused `HandlerDispatchEvidence` to
   classify real rule changes as `NO_EFFECT`.
6. Damage bonus producers updated different subsets of `damages`,
   `original_rolls`, and `final_rolls`.
7. Unseen Strike appended only a final roll, losing typed damage and original
   audit evidence.
8. Divine Smite omitted original-roll and typed modification evidence.
9. Save/check call sites could omit optional metadata and incorrectly fall
   back to the generic d20 event family.
10. D20 result events duplicated the same initial value in `roll` and
    `original_roll`.
11. Damage result events represented one logical packet with three parallel
    arrays.
12. Existing tuple audit entries had incompatible shapes across d20, damage,
    and healing.
13. `BaseAction` constructors auto-published declaration events from
    `Event.model_post_init()` but retained the pre-dispatch Python object.
    A functional declaration handler could return a canceled or modified
    event that the queue stored correctly while the action continued using
    the original declaration. Sanctuary demonstrated the defect: its failed
    Wisdom save produced an `AttackEvent` cancel fact, then the same attack
    still advanced through execution, damage, and completion.

## Target Contract

```text
Event
└── DiceRollResultEvent (abstract shared payload; never published)
    ├── D20RollResultEvent
    │   ├── AttackD20RollResultEvent
    │   ├── SavingThrowD20RollResultEvent
    │   └── SkillCheckD20RollResultEvent
    ├── DamageRollResultEvent
    └── HealRollResultEvent
```

### Shared audit fact

`RollModification` is a frozen, extra-forbidden fact:

- `operation`: `replace | append`;
- `handler_name`;
- optional `packet_index`;
- optional `previous_total`;
- `final_total`;
- rules-facing `reason`.

Shape validation makes replacement and append facts unambiguous.

### D20 and healing

- one `original_roll`;
- optional/effective replacement (`final_roll` for d20, effective final roll
  for healing);
- functional `replace_roll(...) -> Self`;
- no duplicated initial-roll field.

### Damage

`DamageRollPacket` is the indivisible record:

- typed `Damage`;
- `original_roll`;
- `final_roll`.

`DamageRollResultEvent` owns an ordered, non-empty list of packets.

- `replace_roll(packet_index, ...)` copies one packet with a new effective
  roll;
- `append_damage_roll(...)` appends a complete packet and typed append fact;
- no `damages`, `original_rolls`, or `final_rolls` compatibility properties.

## Handler Style

Every result interceptor follows the same rules:

1. Return `None` for an ineligible event.
2. Read the current effective roll/packet.
3. Use the event's functional helper.
4. Return the new event value.
5. Never assign to event fields or mutate result lists.
6. Consume resources only when the rule actually fires.
7. If a consumed resource keeps the original result, return an explicit
   modified event with a status fact so instrumentation does not report a
   no-op.

Application interceptors use `with_updates`, `cancel`, or an emitted child
event and do not edit dice audit facts.

Action execution likewise constructs its declaration without implicit
publication, explicitly publishes it once, and continues only from the exact
event returned by handler dispatch.

## Work Checklist

- [x] Remove dead generic dice-result and damage-rolled enum members/models.
- [x] Introduce typed `RollModification`.
- [x] Convert known d20/healing handlers to functional replacement.
- [x] Convert damage reroll and append handlers to functional transforms.
- [x] Make save/check subtype selection independent of optional metadata.
- [x] Add handler-evidence regression for `MODIFIED_EVENT`.
- [x] Add immutable audit-shape regressions.
- [x] Finish the hard cut from duplicated d20 `roll` to `original_roll`.
- [x] Finish the hard cut from parallel damage arrays to
  `DamageRollPacket`.
- [x] Audit all application interceptors for the same return/style rules
  without merging them into roll-result events.
- [x] Make action declaration publication retain the functional handler
  result and prove declaration cancellation stops execution.
- [x] Run focused consumer suites.
- [x] Regenerate the event contract and TypeScript SDK once.
- [x] Run generator `--check`, SDK build/tests, and event/player contract
  gates.
- [x] Update the codebase-audit closeout evidence.
- [x] Project actual roll changes into the causal combat-log tree.
- [x] Keep unmodified result events silent and prove subjective sanitization
  covers the new entry family.
- [x] Regenerate and re-freeze the event/SDK contracts after the combat-log
  addition.

## Combat-Log Projection Follow-up

The functional interceptor refactor preserves an ordered
`roll_modifications` ledger on every result event, but the completed first
pass did not project that ledger into `CombatLogEntry`. The mechanical result
was correct and the objective event history was auditable, while the normal
combat-log consumer could not see why a roll changed.

The single-path correction is:

- a `roll_modification` combat-log entry is generated only when the result
  event contains one or more actual changes;
- it remains a child of the attack, save, check, or healing event that owns
  the result, using the existing event lineage rather than a standalone log
  callback or client reconstruction;
- its structured payload is a combat-log-owned projection of the event audit
  facts, so `combat_log.py` does not import upward from `events.py`;
- damage-packet changes additionally identify the affected packet's damage
  type and dice expression;
- unmodified dice results generate no entry;
- the subjective projector explicitly reviews and sanitizes the new entry
  family under the same event-time evidence rules as its parent.

## Final Evidence

Frozen generated identities:

- event contract:
  `9aee4d4913a2121033f6bfbb9afea4efa6d88b8f9bdd3e6b01f8346921805e82`;
- SDK contract:
  `da4bd3626e65d728fc9469cdd4a3350eaf914eeac1221af9871f019ba75aac0d`;
- player replication contract:
  `0bdba516d5c20f2c711c0621f63aab363e1dcf6f62246545980e06db2740de91`;
- generated TypeScript source:
  `e85f34dff3eb16124c8820b3589ced3e5aef6c4f5853d1de749abf05af60aa06`.

Focused green gates:

- roll semantics 23/23;
- manual dice results 5/5;
- reaction events 7/7;
- spell families 47/47;
- Halfling origin 5/5;
- Half-Orc origin 4/4;
- Barbarian grants 14/14;
- monster traits 12/12;
- canonical presentation mapper 41/41;
- stealth and Unseen Strike 17/17;
- cleric spell batches 24/24;
- Protection reaction 6/6;
- combat actions 28/28;
- engine event lifecycle 13/13;
- event-before-handler ordering 5/5;
- movement 6/6;
- Haste restrictions 25/25;
- action overrides 26/26;
- action semantics 42/42;
- Counterspell 11/11;
- event wire contract 7/7;
- Python SDK generation contract 9/9;
- subjective combat-log projection 29/29;
- subjective replication contract 9/9;
- player replication contract 27/27;
- player journal 15/15;
- subjective replay 7/7;
- timeline contract 13/13;
- objective timeline 6/6;
- objective/subjective render parity 8/8;
- source-model hygiene 15/15;
- TypeScript SDK 81/81.

Additional validation:

- focused Pyright: zero errors;
- generated contract `--check`: green;
- TypeScript SDK build: green;
- stale predecessor-field/generated-symbol scans: empty;
- touched-file `git diff --check`: green.

## Focused Gates

Run files individually:

- `tests/engine/test_dice_event_semantics.py`
- `tests/engine/test_manual_06_dice_and_roll_result_events.py`
- `tests/manual/test_06_reactions_to_events.py`
- `tests/engine/test_spell_families.py`
- `tests/progression/test_halfling_origin_runtime.py`
- `tests/manual/test_53_srd_monster_traits.py`
- `tests/manual/test_121_canonical_presentation_mapper.py`
- `tests/manual/test_135_stealth_lighting_legacy_contract.py`
- the focused cleric Resistance/Beacon suite;
- the event contract/generator/SDK suites after regeneration.

## Completion Criteria

- Every registered dice-result interceptor uses the functional protocol.
- No production reference remains to the dead predecessor events.
- No d20 initial-roll duplication or damage parallel-array representation
  remains.
- Every bonus-damage producer emits complete typed packets.
- Handler dispatch evidence reports actual replacements/appends as modified.
- Every actual roll change has one typed combat-log entry under its causal
  result-event parent; unmodified result events stay silent.
- Application-level rules remain distinct and their focused tests stay green.
- Generated Python/TypeScript contracts match source exactly.
- No compatibility aliases or alternate route/event paths are added.
