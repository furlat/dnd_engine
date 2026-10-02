"""Shared saved poison hit packet; coatings and single-release arrows use it."""
from typing import Literal

from dnd.core.events import Damage, DamageRollResultEvent
from dnd.core.dice import AttackOutcome
from dnd.core.creature_types import DamageType
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.core.values import ModifiableValue
from dnd.entity import Entity


def append_saved_poison(event: DamageRollResultEvent, *, dc: int,
        die: Literal[4,6,8,10,12,20], name: str, bonus: ModifiableValue,
        cause_id: str) -> DamageRollResultEvent:
    attacker = Entity.get(event.source_entity_uuid) if event.source_entity_uuid else None
    target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
    if attacker is None or target is None or event.canceled:
        return event
    request = attacker.create_saving_throw_request(target.uuid,"constitution",dc,parent_event=event.uuid,
        saving_throw_context=SavingThrowContext(cause_id=cause_id,effect_id="item.basic_poison.hit",
            is_magical=False,effect_tags=(SavingThrowEffectTag.POISON,)))
    _,_,saved = target.saving_throw(request)
    if saved:
        return event
    damage = Damage(name=name,source_entity_uuid=attacker.uuid,target_entity_uuid=target.uuid,
        damage_dice=die,dice_numbers=1,damage_type=DamageType.POISON,damage_bonus=bonus)
    return event.append_damage_roll(damage,damage.get_dice(AttackOutcome.HIT).roll,
        name,"Failed poison Constitution save")
