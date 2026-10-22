# Production fact repairs — backend handoff, 22 October 2026

These three repairs are in the local `feature/rules-checking` working tree on
top of `9ead58f825cc`. They are uncommitted alongside the earlier summon work.
No client files were changed. They use existing schema-18 fields; this repair
does not require a new protocol identity or generated SDK changes. The client
must run against this producer, not the older frozen recordings.

## Full Ice section destruction

A real full-section Disintegrate now emits exactly one ObjectDestroyedFact per
audience entitled to see the section at removal. It carries the actual object
UUID, previous item/placement and DISINTEGRATED disposition. Native removal and
Frigid Air remain unchanged. Sight lost before removal, including inside the
same cast, does not qualify. A hidden observer may retain last-seen memory.

## Earth Myrmidon Burrow Landing

The real child completion now carries `action.earth_myrmidon.landing`, under its
existing Burrow lineage. Per-target resolutions retain that identity too. No new
selectable action was granted; movement, bonus-action cost, saves and damage are
unchanged. Route from the authored identity and public causal structure.

## Arcane Sword

Render the independent blade from the actual spatial effect UUID with content
ID `spatial_effect.spell.arcane_sword`. Its observed sighting contains
`anchor_position` and `anchor_elevation_steps`. The point moves with that same
UUID, can leave/re-enter sight, survives reconnect and retires with its caster's
existing sword condition. Caster movement does not move it.

For the exact caster/blade association, match the visible blade's existing
`concentration_slot_uuid` to the actual slot in the observed caster's
Concentrating ConditionMember state (`concentration_slots[].slot_uuid`, with
`spell_id == spell.arcane_sword`). These are real native slot UUIDs, not condition
UUIDs or guessed positions. The visible blade's slot is a stable opaque
reference; it contains no caster UUID or coordinate. If only the blade is seen,
its point remains usable without inventing a caster association. Resolve the
slot only against independently disclosed actor/item state; a previously known
association can remain known when the caster leaves sight. Arcane Sword does
not fill `anchor_entity_uuid` or `sustainer_item_uuid` with a caster UUID.

Initial cast, Move and moving Strike produce native spatial creation/changes.
Move also supplies its existing ActionFact.target_position under ordinary
coordinate disclosure. A stationary Strike keeps the retained point and emits
no fake movement; its SpellFact.source_entity_uuid joins through the caster's
actual concentration slot, including after reconnect with two swords present.
SpellFact.source_position remains the caster position and attack_outcome remains
the actual outcome. Do not attach the blade to caster ground or guess from its
victim. The old `condition.spell.arcane_sword` remains the actor's lifetime owner;
its UUID is not the independent spatial UUID.

Owner/concentration rejection creates no blade. Blade admission rejection
retires the accepted owner through normal cleanup. Drop and expiry remove the
point and follow-up actions. The marker adds no blocking, terrain, hazard or
turn mechanics and declares empty crossing channels.

## Evidence and timings

The [implementation plan](plans/PRODUCTION_FACT_REPAIRS_2026-10-22.md) records
final validation and independent reviews. Native actions, detached JSON
publication/reduction, reconnect and existing worker paths are covered; no new
Godot rendering or live HTTP recording is claimed.
The final combined selected run passed 219 tests with 1 expected failure.

- [Ice evidence and control timings](audits/PRODUCTION_ICE_FACT_REPAIR_2026-10-22.md).
- [Landing evidence and timings](audits/PRODUCTION_FACT_REPAIRS_2026-10-22/landing_validation.md).
- [Arcane evidence and timings](audits/PRODUCTION_FACT_REPAIRS_2026-10-22/arcane_validation.md).

Ice and Landing show no meaningful regression in the bounded setups. Publishing
the sword adds real work: final native+capture/decode/fold medians are about
13.9 ms cast, 4.7 ms move, 4.9 ms stationary Strike and 7.4 ms moving Strike.
These measurements exclude startup, discovery and network latency.

One broader architecture check exposed an unrelated earlier summon declaration
omission: `_SPELL_CONSTRUCT_FORMS` does not declare InnateFlight used by the
shared summoned-construct factory. It is recorded separately and unchanged by
these three publication repairs.
