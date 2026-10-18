"""Explicit factual spell packet interception, independent of feature owners."""

from dnd.core.dice import AttackOutcome, DiceRoll
from dnd.core.effect_types import EffectOrigin, EffectOriginKind
from dnd.core.events import Damage, Event, EventPhase, SpellDamageRollResultEvent


def finalize_spell_damage_roll(
    damage: Damage,
    roll: DiceRoll,
    *,
    parent_event: Event,
    effect_origin: EffectOrigin | None = None,
) -> DiceRoll:
    origin = effect_origin or damage.effect_origin or parent_event.get_effect_origin()
    if origin is None or origin.kind is not EffectOriginKind.SPELL:
        return roll
    damage.effect_origin = origin
    result = SpellDamageRollResultEvent(
        source_entity_uuid=damage.source_entity_uuid,
        target_entity_uuid=damage.target_entity_uuid,
        parent_event=parent_event.uuid,
        effect_origin=origin,
        damage=damage,
        original_roll=roll,
        final_roll=roll,
    )
    result = result.phase_to(EventPhase.EFFECT)
    if result.canceled:
        return roll.model_copy(update={"total": 0})
    return result.phase_to(EventPhase.COMPLETION).final_roll


def roll_spell_damage(
    damage: Damage,
    *,
    parent_event: Event,
    attack_outcome: AttackOutcome,
    crit_extra_dice: int = 0,
    effect_origin: EffectOrigin | None = None,
) -> DiceRoll:
    roll = damage.get_dice(
        attack_outcome=attack_outcome, crit_extra_dice=crit_extra_dice
    ).roll
    return finalize_spell_damage_roll(
        damage, roll, parent_event=parent_event, effect_origin=effect_origin
    )


def resolve_saved_spell_damage(
    damage: Damage,
    *,
    parent_event: Event,
    saved: bool,
    success_fraction: float,
    effect_origin: EffectOrigin | None = None,
) -> SpellDamageRollResultEvent:
    origin = effect_origin or damage.effect_origin or parent_event.get_effect_origin()
    if origin is None or origin.kind is not EffectOriginKind.SPELL:
        raise ValueError("A saved spell packet requires explicit spell origin")
    damage.effect_origin = origin
    roll = damage.get_dice(AttackOutcome.HIT).roll
    result = SpellDamageRollResultEvent(
        source_entity_uuid=damage.source_entity_uuid,
        target_entity_uuid=damage.target_entity_uuid,
        parent_event=parent_event.uuid,
        effect_origin=origin,
        damage=damage,
        original_roll=roll,
        final_roll=roll,
        save_success=saved,
        success_damage_fraction=success_fraction,
    )
    result = result.phase_to(EventPhase.EFFECT)
    return result if result.canceled else result.phase_to(EventPhase.COMPLETION)
