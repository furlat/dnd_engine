"""Shared spell utility functions.

Contains helpers used across multiple spell school modules to avoid
cross-spell-file imports.
"""
from dnd.core.spell_damage import roll_spell_damage, finalize_spell_damage_roll
from dnd.core.events import SavingThrowEvent
from dnd.types.abilities import AbilityName
from dnd.core.values import ModifiableValue
from typing import Literal, cast
from dnd.core.creature_types import DamageType
from dnd.core.saving_throw_types import SavingThrowEffectTag

from typing import Optional, Callable
from dnd.core.base_conditions import BaseCondition
from dnd.core.life_types import LifeState
from dnd.core.events import EventHandler, EventType, Trigger
from uuid import UUID

from dnd.core.dice import DiceRoll
from dnd.core.events import EventPhase, Healing, HealRollResultEvent, Event
from dnd.entity import Entity
from dnd.actions import SpellEvent, PreparedSpellConcentration
from dnd.core.base_actions import BaseAction, ActionTargetEffectProfile, ActionTargetEffectBranchProfile, OutcomeResolution, TargetEffectDisposition
from dnd.core.content.registration import get_content_declaration
from dnd.core.gridmap import get_map
from dnd.blocks.base_item import BaseItem
from dnd.core.events import Damage, DamageRollPacket, DamageRollResultEvent
from dnd.core.dice import AttackOutcome
from dnd.core.base_block import BaseBlock
from dnd.core.damage import DamageResolution


def validate_line_of_sight(declaration_event: SpellEvent, source_entity_uuid: UUID) -> Optional[SpellEvent]:
    """Validate if the source entity and target entity are in line of sight."""
    source_entity = Entity.get(source_entity_uuid)
    if not source_entity:
        return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
    if not isinstance(source_entity, Entity):
        return declaration_event.cancel(status_message=f"Source entity not found for {declaration_event.name}")
    if not declaration_event.target_entity_uuid:
        return declaration_event.cancel(status_message=f"Target entity uuid not present for {declaration_event.name}")
    target_entity = Entity.get(declaration_event.target_entity_uuid)
    if not target_entity:
        return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")
    if not isinstance(target_entity, Entity):
        return declaration_event.cancel(status_message=f"Target entity not found for {declaration_event.name}")

    contact = source_entity.senses.entities.get(target_entity.uuid)
    if contact is None or not contact.visual:
        return declaration_event.cancel(status_message=f"Target entity not in line of sight for {declaration_event.name}")
    return declaration_event.phase_to(
        new_phase=EventPhase.EXECUTION,
        status_message=f"Validated line of sight for {declaration_event.name}"
    )


def fire_heal_roll_result(
    caster_uuid: UUID,
    target_uuid: UUID,
    healing: Healing,
    parent_event: Event,
    spell_name: str = "",
) -> DiceRoll:
    """Roll healing dice and fire HEAL_ROLL_RESULT event for handler interception.

    Mirrors the DAMAGE_ROLL_RESULT pattern. Handlers (e.g., Beacon of Hope)
    can maximize or replace healing dice via event.replace_roll().

    Returns the final_roll (possibly modified by handlers).
    """
    original_roll = healing.get_dice().roll
    caster = Entity.get(caster_uuid)
    target = Entity.get(target_uuid)

    heal_roll_event = HealRollResultEvent(
        source_entity_uuid=caster_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name=caster.name if isinstance(caster, Entity) else None,
        target_entity_name=target.name if isinstance(target, Entity) else None,
        spell_name=spell_name,
        effect_origin=parent_event.get_effect_origin(),
        original_roll=original_roll,
        final_roll=original_roll.model_copy(deep=True),
        parent_event=parent_event.uuid,
        phase=EventPhase.DECLARATION,
    )

    heal_roll_event = heal_roll_event.phase_to(
        EventPhase.EFFECT,
        status_message=f"Healing dice rolled for {spell_name}",
    )
    heal_roll_event = heal_roll_event.phase_to(
        EventPhase.COMPLETION,
        status_message=f"Healing dice finalized for {spell_name}",
    )

    return heal_roll_event.final_roll


def source_turn_expiry_handler(owner: BaseCondition, application: Event, *,
                                at_end: bool, expire: Callable[[Event], None]) -> EventHandler:
    """Source-turn deadlines, using native source turns and world rounds.

    A departed or dead source has no next turn; retain the effect until the
    next world round boundary instead of tying it to a recipient's initiative.
    """
    armed = False
    application_turn = application.turn_execution_id

    def processor(event: Event, _source_uuid: UUID) -> Optional[Event]:
        nonlocal armed
        if not owner.applied:
            return None
        if event.event_type is EventType.ROUND_END:
            source = Entity.get(owner.source_entity_uuid)
            if source is None or not source.is_deployed or source.health.life_state is LifeState.DEAD:
                expire(event)
        elif event.source_entity_uuid == owner.source_entity_uuid:
            if application_turn is not None and event.turn_execution_id == application_turn:
                return None
            if event.event_type is EventType.TURN_START:
                armed = True
                if not at_end:
                    expire(event)
            elif armed:
                expire(event)
        return None

    return EventHandler(name=f"{owner.name} source-turn expiry", source_entity_uuid=owner.source_entity_uuid,
        runs_while_suppressed=True,
        trigger_conditions=[
            Trigger(event_type=EventType.TURN_START, event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=owner.source_entity_uuid),
            Trigger(event_type=EventType.TURN_END, event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=owner.source_entity_uuid),
            Trigger(event_type=EventType.ROUND_END, event_phase=EventPhase.EFFECT),
        ], event_processor=processor)



def deliver_spell_damage(event: SpellEvent,target: BaseBlock,damage: Damage,roll: DiceRoll,
                         *,amount: int | None=None, on_resolved: Callable[[DamageResolution],None] | None=None) -> SpellEvent:
    """Deliver a native spell component with its retained origin and exact critical."""
    if event.canceled:
        return event
    total=roll.total if amount is None else amount
    damage.effect_origin=event.get_effect_origin()
    damages=[damage]
    rolls=[roll]
    outcome=event.attack_outcome
    if outcome is AttackOutcome.HIT or outcome is AttackOutcome.CRIT:
        finalized=DamageRollResultEvent(source_entity_uuid=event.source_entity_uuid,
            target_entity_uuid=target.uuid,attack_kind="spell",weapon_slot=None,
            attack_outcome=outcome,parent_event=event.uuid,
            damage_packets=[DamageRollPacket(damage=damage,original_roll=roll,final_roll=roll)])
        finalized=finalized.phase_to(EventPhase.EFFECT)
        if finalized.canceled:
            return event.cancel(status_message="Spell attack damage interrupted")
        finalized=finalized.phase_to(EventPhase.COMPLETION)
        damages=[packet.damage for packet in finalized.damage_packets]
        rolls=[packet.final_roll for packet in finalized.damage_packets]
        total=sum(packet.total for packet in rolls)
    if isinstance(target,BaseItem):
        target.receive_damage(total,damage.damage_type,damage.source_entity_uuid,
            parent_event=event,damages=damages,damage_rolls=rolls)
    elif isinstance(target,Entity):
        target.receive_damage(total,damage.damage_type,damage.source_entity_uuid,
            parent_event=event.uuid,damages=damages,damage_rolls=rolls,
            critical_hit=event.attack_outcome is AttackOutcome.CRIT,effect_origin=event.get_effect_origin(),
            on_resolved=on_resolved)
    return event.with_updates(damages=damages,damage_rolls=rolls,total_damage=total)


def spell_position_error(action: BaseAction) -> str | None:
    caster=Entity.get(action.source_entity_uuid)
    position=action.end_position
    if caster is None or position is None or not get_map().has_tile(*position):
        return "Choose an existing spell placement"
    if (error:=action.target_position_error(position)) is not None:
        return error
    if position!=caster.position and not caster.senses.visible.get(position,False):
        return "Choose a visible spell placement"
    return None


def spell_valid_positions(action: BaseAction):
    positions=BaseAction.get_valid_positions(action)
    caster=Entity.get(action.source_entity_uuid)
    if caster is not None and get_map().has_tile(*caster.position) and action.target_position_error(caster.position) is None:
        positions.append(caster.position)
    return positions


def target_turn_expiry_handler(owner: BaseCondition,*,turn_ends: int) -> EventHandler:
    """Short target-turn effects expire after actual completed recipient turns."""
    remaining=turn_ends
    if owner.target_entity_uuid is None:
        raise ValueError("A target-turn deadline requires a recipient")
    def expire(event: Event,_: UUID):
        nonlocal remaining
        remaining-=1
        target=BaseBlock.get(owner.target_entity_uuid) if owner.target_entity_uuid else None
        if remaining<=0 and target is not None:
            target.remove_condition_by_uuid(owner.uuid,parent_event=event)
        return None
    return EventHandler(name=f"{owner.get_display_name()} turn deadline",source_entity_uuid=owner.target_entity_uuid,
        runs_while_suppressed=True,trigger_conditions=[Trigger(event_type=EventType.TURN_END,event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=owner.target_entity_uuid)],event_processor=expire)


def spell_condition_profile(action,caster: Entity,*,key: str,condition_type: type[BaseCondition],
        beneficial: bool=False,save_ability: str | None=None,fact: str | None=None,
        included: frozenset[str]=frozenset(),excluded: frozenset[str]=frozenset()):
    resolution=OutcomeResolution.SAVING_THROW if save_ability else OutcomeResolution.AUTOMATIC
    return ActionTargetEffectProfile(semantic_id=f"spell.{key}",branches=(ActionTargetEffectBranchProfile(
        effect_id=f"spell.{key}.condition",disposition=TargetEffectDisposition.BENEFICIAL if beneficial else TargetEffectDisposition.HARMFUL,
        resolution=resolution,save_dc=caster.spell_save_dc(spellcasting_source_id=action.spellcasting_source_id) if save_ability else None,
        save_ability=save_ability,included_creature_types=included,excluded_creature_types=excluded,
        condition_fact_ids=(fact or f"selected_target.condition.{key}",),
        condition_semantic_keys=frozenset({get_content_declaration(condition_type).ref.content_id})),))


def condition_save(owner: BaseCondition, target: Entity, boundary: Event,
                   ability: AbilityName, dc: int, effect_id: str,
                   effect_tags: tuple[SavingThrowEffectTag, ...] = ()) -> bool:
    """Roll a retained condition save without requiring its caster to survive."""
    request = SavingThrowEvent(source_entity_uuid=owner.source_entity_uuid or target.uuid,
        target_entity_uuid=target.uuid, ability_name=ability, dc=dc, parent_event=boundary.uuid,
        saving_throw_context=owner.saving_throw_context(effect_id=effect_id, effect_tags=effect_tags))
    return target.saving_throw(request)[2]


def condition_damage(owner: BaseCondition, target: Entity, boundary: Event, *,
                     count: int, die: Literal[4,6,8,10,12,20], damage_type: DamageType) -> None:
    """Deliver one source-owned periodic packet through native damage resolution."""
    source = owner.source_entity_uuid or target.uuid
    damage = Damage(name=owner.get_display_name(), source_entity_uuid=source,
        target_entity_uuid=target.uuid, dice_numbers=count, damage_dice=die, damage_type=damage_type,
        damage_bonus=ModifiableValue.create(source_entity_uuid=source, base_value=0),
        effect_origin=owner.effect_origin)
    roll = roll_spell_damage(damage, parent_event=boundary, effect_origin=owner.effect_origin, attack_outcome=AttackOutcome.HIT, crit_extra_dice=0)
    target.receive_damage(roll.total, damage_type, source, damages=[damage], damage_rolls=[roll],
        parent_event=boundary.uuid, effect_origin=owner.effect_origin,
        independent_resolution=True, source_condition_uuid=owner.uuid)


def validate_spell_recipients(action: BaseAction, declaration: SpellEvent) -> SpellEvent | None:
    """Validate the selected recipients before payment, using native targeting."""
    caster = Entity.get(action.source_entity_uuid)
    if caster is None: return declaration.cancel(status_message="Caster absent")
    targets = action.get_all_targets()
    if not targets: return declaration.cancel(status_message="Recipient absent")
    error = action._validate_target_filter(targets)
    if error is not None: return declaration.cancel(status_message=error)
    for identity in targets:
        target = Entity.get(identity)
        if target is None or target.health.life_state is LifeState.DEAD:
            return declaration.cancel(status_message="Living recipient required")
        if target.uuid == caster.uuid:
            if not action.include_self: return declaration.cancel(status_message="Self targeting is not allowed")
        else:
            contact = caster.senses.entities.get(target.uuid)
            if contact is None or not contact.visual: return declaration.cancel(status_message="Recipient must be visible")
        if (error := action.target_position_error(target.position)) is not None:
            return declaration.cancel(status_message=error)
    return cast(SpellEvent | None, BaseAction._validate(action, declaration))


def apply_concentrating_zone(action, event: SpellEvent, zone) -> SpellEvent:
    """Admit concentration replacement before publishing a new spatial owner."""
    if event.canceled:
        zone.discard_from_runtime_owner()
        return event
    with BaseBlock.condition_removal_scope():
        prepared=action.prepare_concentration(event)
        if not isinstance(prepared,PreparedSpellConcentration):
            zone.discard_from_runtime_owner()
            return event.cancel(status_message="Concentration was not admitted")
        try:
            result=zone.activate(parent_event=event)
            if result is None or result.canceled or not zone.applied:
                return event.cancel(status_message="Spatial effect was not admitted")
            action.commit_prepared_concentration(prepared,zone,zone)
            action.publish_prepared_concentration(prepared)
            return event
        finally:
            if prepared.application is not None and not prepared.application.committed:
                prepared.owner.cancel_condition_application(prepared.application,"Spatial cast was rejected")
