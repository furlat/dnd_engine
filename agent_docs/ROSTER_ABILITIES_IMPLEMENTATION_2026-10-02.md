# Roster ability batch: native implementation

October 2, 2026. Implements the native portion of the approved
[plan](ROSTER_ABILITIES_AND_SIMPLE_SPELLS_PLAN_2026-10-02.md).
The [150-row disposition](ROSTER_ABILITY_DISPOSITIONS_2026-10-02.md) remains the
complete character-authoring input. This checkpoint does not register those
characters or certify their source clips. Scenarios and multi-Z remain deferred.

## Implemented

| Capability | Native owner and result |
| --- | --- |
| Six support spells | `dnd/spells/roster_support.py`: Produce Flame, Shillelagh, Longstrider, Barkskin, Fly and warm/chill Fire Shield. Canonical spell identities, SRD5.1 provenance and granted actions are registered through the existing content owners. |
| Selected creature effects | `dnd/monsters/roster_abilities.py`: contextual Magic Resistance, indefinite concentration-based innate Invisibility, authored innate flight and Wight Life Drain with cumulative maximum-HP loss until long rest. Its melee Multiattack may replace one Longsword only. |
| Natural attack identity | Existing attack-source facts now carry intrinsic magical status and optional fixed source bonuses. Fixed attack/damage baselines preserve independent buffs; no inventory teeth/claws or actor-wide weapon bonus. |
| Four arrows | `dnd/items/roster_carried_powers.py`: Ember/Frost/Storm add 1d6 typed damage on hit; Venom reuses the DC10 CON/1d4 poison packet without Poisoned or critical doubling. All are inventory stacks used through ordinary bow/crossbow attacks and selected ranged Multiattack. |
| Three backpacks | Ember Quiver coats the exact declared bow/crossbow for ten rounds; Wayfarer's Pack casts self Longstrider; Warden's Pack casts self Resistance. Each requires the real BACKPACK slot and one item-owned use per long rest. Transfer preserves depleted charges. |

Spell modifiers, lights, granted actions and concentration links belong to the
actual effect UUID. Shillelagh modifies the exact held possession and ends on
release; ordinary coatings retain their already accepted transfer lifetime.
Life Drain survives the attacker's removal, preserves current HP correctly and
publishes changed condition/stats facts when further hits increase the reduction.
Fire Shield retaliation is automatic native damage, with no reaction debit and
no recursive shield hit. Innate Invisibility remains an ability rather than a
counterspellable cast; ordinary nonconcentration casting does not reveal it.

## Shared contracts

Movement has one expenditure history across modes. Mode grants do not raise
walking speed. Haste/Slow factors compose before integer rounding.
Move, Jump, Command and prone standing
read the same remaining-movement ledger. Flight ends on supported positions;
losing the grant during a step cannot teleport or spend an uncommitted step.

The human deferred ordinary Grapple. Its new action, registrations, dragging,
hand reservations and speed caps are removed. Pre-removal sources are preserved
privately in `.runtime/deferred-grapple-20261002/`; this is not a release dependency.
The pre-existing Grappled condition is unchanged.

Finite item costs are admitted through cancellable child events before ordinary
action-cost commitment. Charges/arrow copies commit at release after execution
and physical/source revalidation. A miss spends one arrow; an interrupted release
does not. Prepared child events have registered declaration ancestry. Arrow
discovery preserves normal, Extra Attack and restricted Haste variants, exposing
typed selected possession/payload facts without a second combat executor.

Canonical `build_authored_item` constructs all seven new items. No additional
item registry, slot system, effect scripting language or per-NPC executor exists.

## Validation

Before the Grapple scope reduction, the full engine and existing attack-budget
suite passed **2,431 cases in 310.09 seconds**. The remaining ability module has
67 cases, including the complete 48-combination Haste × Extra Attack × Action
Surge × Slow arrow grid, native index-based selection, ranged Multiattack,
failed releases and transfer/recharge. The support-spell module has 16 cases.
Post-removal verification is recorded below when complete.

Architecture checks exposed a redundant flying-speed affordability read in
Flying Movement validation. It was removed; the shared typed movement cost
already owns that check. Its native/architecture rerun passes. The separate
server cold-start check still imports removed `dnd.core.senses` from the paused
server. It is documented rather than repaired in this native lane.

Both independent anti-slop and ECS/anti-OOP reviewers approve the bounded native
implementation. Their approval excludes full roster and visual integration.

## Remaining visual and character work

The [visual handoff](ROSTER_ABILITIES_VISUAL_HANDOFF_2026-10-02.md) records exact
owners, contact/lifetime rules and missing registrations. Accepted item palettes,
bloom, geometry and shadows remain unchanged. Backpack geometry uses existing
Bag2 appearances; new spell/arrow effects are not certified as rendered here.

Existing Stoneskin still has its previously authored all-physical-damage
adaptation. This batch adds exact magical natural-source facts, not a rewrite of
that resistance rule. Do not claim a new magical-resistance bypass implementation.
Wight zombie creation, unsupported source spells and optional custom signatures
remain the explicit omissions in the complete disposition table.
