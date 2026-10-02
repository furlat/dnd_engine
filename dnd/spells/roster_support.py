"""SRD 5.1 support spells selected by the complete roster disposition.

Effects own their normal modifiers, lights and granted actions. They do not
infer gameplay from artwork or install a second spell executor.
"""

from typing import Any, Literal, cast
from uuid import UUID, uuid4

from pydantic import Field

from dnd.actions import AttackEvent, Move, SpellAction, SpellEvent, entity_action_economy_cost_evaluator
from dnd.blocks.equipment import Weapon, WeaponUnequipEvent
from dnd.core.attack_types import WeaponAttackOverride
from dnd.core.equipment_types import WeaponSlot
from dnd.types.world import MovementMode
from dnd.types.abilities import AbilityName
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.events import Damage, Event, EventHandler, EventPhase, EventType, Range, RangeType, Trigger
from dnd.core.geometry import grid_distance_feet
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier, ResistanceModifier, ResistanceStatus
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.spells.content_metadata import srd_action_identity
from dnd.types.physical_access import PhysicalAccess


def _revoke_actions(actor_uuid: UUID | None, action_uuids: set[UUID]) -> None:
    actor = Entity.get(actor_uuid) if actor_uuid else None
    if actor is not None:
        for action_uuid in action_uuids:
            actor.unregister_action_by_uuid(action_uuid)
    action_uuids.clear()


def _rounds(count: int) -> Duration:
    return Duration(duration_type=DurationType.ROUNDS, duration=count)


def _install_spell_effect(spell: SpellAction, event: SpellEvent, effect: BaseCondition) -> SpellEvent:
    target = Entity.get(effect.target_entity_uuid) if effect.target_entity_uuid else None
    if target is None:
        return event.cancel(status_message="Spell recipient no longer exists")
    result = target.add_condition(effect, parent_event=event)
    if result is None or result.canceled or not effect.applied:
        return event.cancel(status_message="Spell effect was not admitted")
    if spell.concentration:
        spell.ensure_concentration(event).add_linked_condition(target.uuid, effect.uuid)
    return event


class LongstriderEffect(BaseCondition):
    description: str = "Speed increases by 10 feet until the effect ends."
    name: str = "Longstrider"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: _rounds(600))

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient missing")
        value = target.action_economy.movement
        modifier = NumericalModifier(name=self.name, value=10,
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid)
        value.self_static.add_value_modifier(modifier)
        return [(value.uuid, modifier.uuid)], [], [], [], event.phase_to(EventPhase.EFFECT)


class Longstrider(SpellAction):
    name: str = "Longstrider"
    description: str = "Touch: speed increases by 10 feet for one hour; additional recipients when upcast."
    spell_level: int = 1
    spell_school: str = "transmutation"
    target_type: TargetType = TargetType.MULTI_ENTITY
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))

    def get_multi_target_count(self) -> int:
        return self.alt_target_count or max(1, self.cast_at_level)

    def _apply(self, event: SpellEvent):
        effect_event = event.phase_to(EventPhase.EFFECT)
        return _install_spell_effect(self, effect_event, LongstriderEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid))


class BarkskinEffect(BaseCondition):
    description: str = "Armor Class cannot fall below 16."
    name: str = "Barkskin"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: _rounds(600))

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient missing")
        value = target.equipment.ac_bonus
        modifier = NumericalModifier(name=self.name, value=16,
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid)
        value.self_static.add_min_constraint(modifier)
        return [(value.uuid, modifier.uuid)], [], [], [], event.phase_to(EventPhase.EFFECT)


class Barkskin(SpellAction):
    name: str = "Barkskin"
    description: str = "Touch: Armor Class cannot be below 16; concentration up to one hour."
    spell_level: int = 2
    spell_school: str = "transmutation"
    concentration: bool = True
    target_type: TargetType = TargetType.ENTITY
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))

    def _apply(self, event: SpellEvent):
        return _install_spell_effect(self, event.phase_to(EventPhase.EFFECT), BarkskinEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid))


class ProduceFlameEffect(BaseCondition):
    granted_action_uuids: set[UUID] = Field(default_factory=set)
    description: str = "Retained hand flame, anchored light and later hurl/dismiss actions."
    name: str = "Produce Flame"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: _rounds(100))
    caster_level: int = 1
    spellcasting_source_id: UUID | None = None
    light_source_uuid: UUID | None = None

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Caster missing")
        self.light_source_uuid = get_map().add_light_source(position=target.position,
            bright_radius_feet=10, dim_radius_feet=10, anchor_uuid=target.uuid, parent_event=event.uuid)
        actions = [HurlProduceFlame(source_entity_uuid=target.uuid, flame_uuid=self.uuid,
                    caster_level=self.caster_level, spellcasting_source_id=self.spellcasting_source_id, template=True),
                   DismissProduceFlame(source_entity_uuid=target.uuid, effect_uuid=self.uuid, template=True)]
        for action in actions:
            target.register_action(action)
        self.granted_action_uuids = {action.uuid for action in actions}
        return [], [], [], [], event.phase_to(EventPhase.EFFECT)

    def _remove(self, event: Event | None = None):
        _revoke_actions(self.target_entity_uuid, self.granted_action_uuids)
        if self.light_source_uuid is not None:
            get_map().remove_light_source(self.light_source_uuid, parent_event=event.uuid if event else None)
            self.light_source_uuid = None
        return super()._remove(event)


def _hurl_flame(spell: SpellAction, event: SpellEvent) -> SpellEvent:
    caster = Entity.get(spell.source_entity_uuid)
    target = Entity.get(spell.target_entity_uuid) if spell.target_entity_uuid else None
    if caster is None or target is None or target.uuid == caster.uuid:
        return event.cancel(status_message="Flame requires another creature")
    if (error := spell.physical_access_error()) is not None:
        return event.cancel(status_message=error)
    resolution = spell.resolve_spell_attack(caster, target, event.uuid)
    effect = event.phase_to(EventPhase.EFFECT, attack_bonus=resolution.attack_bonus,
        ac=resolution.target_ac, dice_roll=resolution.dice_roll, attack_outcome=resolution.outcome,
        is_threatened=resolution.is_threatened)
    if effect.canceled or resolution.outcome in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS):
        return effect
    damage = Damage(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        damage_dice=8, dice_numbers=spell._get_cantrip_dice_count(spell.caster_level),
        damage_bonus=caster.get_spell_damage_bonus(), damage_type=DamageType.FIRE)
    roll = damage.get_dice(resolution.outcome,
        crit_extra_dice=caster.get_spell_crit_extra_dice() if resolution.outcome == AttackOutcome.CRIT else 0).roll
    target.receive_damage(amount=roll.total, damage_type=DamageType.FIRE, source_entity_uuid=caster.uuid,
        parent_event=effect.uuid, damages=[damage], damage_rolls=[roll])
    return effect.with_updates(damages=[damage], damage_rolls=[roll])


class ProduceFlame(SpellAction):
    name: str = "Produce Flame"
    description: str = "Create a hand flame and 10 feet bright/dim light, or hurl it up to 30 feet for 1d8 fire."
    spell_school: str = "conjuration"
    target_type: TargetType = TargetType.ENTITY
    include_self: bool = True
    valid_target_filter: str = "all"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))
    physical_access: PhysicalAccess | None = PhysicalAccess.PROJECTILE
    projectile_type: str | None = "bolt"
    spell_damage_type: DamageType | None = DamageType.FIRE

    @property
    def performs_attack(self) -> bool:
        return self.target_entity_uuid is not None and self.target_entity_uuid != self.source_entity_uuid

    def _apply(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return event.cancel(status_message="Caster missing")
        if self.target_entity_uuid is not None and self.target_entity_uuid != caster.uuid:
            old = caster.active_conditions.get("Produce Flame")
            if old is not None:
                removed = caster.remove_condition_by_uuid(old.uuid, parent_event=event)
                if not removed:
                    return event.cancel(status_message="Existing flame could not be released")
            return _hurl_flame(self, event)
        return _install_spell_effect(self, event.phase_to(EventPhase.EFFECT), ProduceFlameEffect(
            source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid,
            caster_level=self.caster_level, spellcasting_source_id=self.spellcasting_source_id))


@srd_action_identity(content_id="action.spell.produce_flame.hurl", display_name="Hurl Produce Flame",
    description="Hurl the retained hand flame.", parent_spell_name="Produce Flame", source_page=171, sort_order=1)
class HurlProduceFlame(SpellAction):
    name: str = "Hurl Produce Flame"
    spell_school: str = "conjuration"
    flame_uuid: UUID
    target_type: TargetType = TargetType.ENTITY
    valid_target_filter: str = "enemies"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))
    physical_access: PhysicalAccess | None = PhysicalAccess.PROJECTILE
    projectile_type: str | None = "bolt"
    spell_damage_type: DamageType | None = DamageType.FIRE

    @property
    def performs_attack(self) -> bool:
        return True

    def _validate(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None or not any(effect.uuid == self.flame_uuid for effect in caster.active_conditions.values()):
            return event.cancel(status_message="Hand flame is no longer retained")
        return super()._validate(event)

    def _apply(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return event.cancel(status_message="Caster missing")
        removed = caster.remove_condition_by_uuid(self.flame_uuid, parent_event=event)
        if not removed:
            return event.cancel(status_message="Hand flame could not be released")
        return _hurl_flame(self, event)


@srd_action_identity(content_id="action.spell.produce_flame.dismiss", display_name="Dismiss Produce Flame",
    description="Dismiss the retained hand flame.", parent_spell_name="Produce Flame", source_page=171, sort_order=2)
class DismissProduceFlame(BaseAction):
    name: str = "Dismiss Produce Flame"
    effect_uuid: UUID
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Dismiss Flame", cost_type="actions",
        cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def _apply(self, event):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return event.cancel(status_message="Caster missing")
        removed = caster.remove_condition_by_uuid(self.effect_uuid, parent_event=event)
        if not removed:
            return event.cancel(status_message="Flame could not be dismissed")
        return event.phase_to(EventPhase.EFFECT)


class FireShieldEffect(BaseCondition):
    granted_action_uuids: set[UUID] = Field(default_factory=set)
    description: str = "Warm/chill resistance and automatic retaliation against qualifying melee hits."
    name: str = "Fire Shield"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: _rounds(100))
    shield_kind: Literal["warm", "chill"] = "warm"
    light_source_uuid: UUID | None = None
    retaliated_lineages: set[UUID] = Field(default_factory=set, exclude=True)

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Caster missing")
        resisted = DamageType.COLD if self.shield_kind == "warm" else DamageType.FIRE
        damage_type = DamageType.FIRE if self.shield_kind == "warm" else DamageType.COLD
        value = target.health.damage_reduction
        modifier = ResistanceModifier(name=self.name, value=ResistanceStatus.RESISTANCE, damage_type=resisted,
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid)
        value.self_static.add_resistance_modifier(modifier)
        self.light_source_uuid = get_map().add_light_source(position=target.position,
            bright_radius_feet=10, dim_radius_feet=10, anchor_uuid=target.uuid, parent_event=event.uuid)

        def retaliate(attack: Event, owner_uuid: UUID):
            if attack.canceled or attack.lineage_uuid in self.retaliated_lineages:
                return None
            if attack.event_type == EventType.ATTACK:
                weapon_hit = cast(AttackEvent, attack)
                melee = weapon_hit.range is not None and weapon_hit.range.type == RangeType.REACH
                outcome = weapon_hit.attack_outcome
            elif attack.event_type == EventType.CAST_SPELL:
                spell_hit = cast(SpellEvent, attack)
                melee = spell_hit.range_type == "touch"
                outcome = spell_hit.attack_outcome
            else:
                return None
            if not melee or outcome not in (AttackOutcome.HIT, AttackOutcome.CRIT):
                return None
            attacker = Entity.get(attack.source_entity_uuid)
            owner = Entity.get(owner_uuid)
            if attacker is None or owner is None or grid_distance_feet(owner.position, attacker.position) > 5:
                return None
            self.retaliated_lineages.add(attack.lineage_uuid)
            damage = Damage(source_entity_uuid=owner.uuid, target_entity_uuid=attacker.uuid,
                damage_dice=8, dice_numbers=2, damage_type=damage_type,
                damage_bonus=ModifiableValue.create(source_entity_uuid=owner.uuid, base_value=0, value_name="Fire Shield damage"))
            roll = damage.get_dice(AttackOutcome.HIT).roll
            attacker.receive_damage(amount=roll.total, damage_type=damage_type, source_entity_uuid=owner.uuid,
                parent_event=attack.uuid, damages=[damage], damage_rolls=[roll], effect_origin=self.effect_origin)
            return None

        handler = EventHandler(name="Fire Shield retaliation", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target.uuid),
                Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target.uuid)], event_processor=retaliate)
        target.add_event_handler(handler)
        dismiss = DismissFireShield(source_entity_uuid=target.uuid, effect_uuid=self.uuid, template=True)
        target.register_action(dismiss)
        self.granted_action_uuids = {dismiss.uuid}
        return [(value.uuid, modifier.uuid)], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)

    def _remove(self, event: Event | None = None):
        _revoke_actions(self.target_entity_uuid, self.granted_action_uuids)
        if self.light_source_uuid is not None:
            get_map().remove_light_source(self.light_source_uuid, parent_event=event.uuid if event else None)
            self.light_source_uuid = None
        return super()._remove(event)


class FireShield(SpellAction):
    name: str = "Fire Shield"
    description: str = "Warm/cold ward: resistance, 10-foot light and 2d8 retaliation against melee hits within 5 feet."
    spell_level: int = 4
    spell_school: str = "evocation"
    target_type: TargetType = TargetType.SELF
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    shield_kind: Literal["warm", "chill"] = "warm"

    def get_discovery_variants(self, entity: Any) -> list[BaseAction]:
        return [variant.model_copy(deep=True, update={"uuid":uuid4(), "shield_kind":kind,
            "registered_template_uuid":self.registered_template_uuid or self.uuid})
            for variant in super().get_discovery_variants(entity) for kind in ("warm","chill")]

    def get_discovery_template_name(self) -> str:
        return f"{super().get_discovery_template_name()}__{self.shield_kind}"

    def get_discovery_display_name(self) -> str:
        return f"{super().get_discovery_display_name()} ({self.shield_kind})"

    def _apply(self, event: SpellEvent):
        return _install_spell_effect(self, event.phase_to(EventPhase.EFFECT), FireShieldEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.source_entity_uuid, shield_kind=self.shield_kind))


@srd_action_identity(content_id="action.spell.fire_shield.dismiss", display_name="Dismiss Fire Shield",
    description="Dismiss the retained fire or cold shield.", parent_spell_name="Fire Shield", source_page=144, sort_order=1)
class DismissFireShield(BaseAction):
    name: str = "Dismiss Fire Shield"
    effect_uuid: UUID
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Dismiss Shield", cost_type="actions",
        cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def _apply(self, event: Event):
        caster = Entity.get(self.source_entity_uuid)
        if caster is None or not caster.remove_condition_by_uuid(self.effect_uuid, parent_event=event):
            return event.cancel(status_message="Shield could not be dismissed")
        return event.phase_to(EventPhase.EFFECT)


@srd_action_identity(content_id="action.spell.fly.move", display_name="Flying Movement",
    description="Fly between supported positions using shared movement expenditure.", parent_spell_name="Fly", source_page=145, sort_order=1)
class FlyingMovement(Move):
    name: str = "Flying Movement"
    movement_mode: MovementMode = MovementMode.FLYING

    def _validate(self, event):
        # Every committed leg has support. Losing flight never leaves an
        # unsupported intermediate position or teleports to the destination.
        if any(get_map().get_tile(*position) is None for position in event.path or ()):
            return event.cancel(status_message="Flight requires supported positions")
        return super()._validate(event)


class FlyEffect(BaseCondition):
    granted_action_uuids: set[UUID] = Field(default_factory=set)
    description: str = "Source-owned flying speed and ground-to-ground movement."
    name: str = "Fly"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: _rounds(100))
    flying_speed: int = Field(default=60, gt=0)

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Recipient missing")
        target.action_economy.movement_speed_grants[self.uuid] = {MovementMode.FLYING: self.flying_speed}
        movement = FlyingMovement(source_entity_uuid=target.uuid, template=True)
        target.register_action(movement)
        self.granted_action_uuids = {movement.uuid}
        return [], [], [], [], event.phase_to(EventPhase.EFFECT)

    def _remove(self, event: Event | None = None):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            target.action_economy.movement_speed_grants.pop(self.uuid, None)
        _revoke_actions(self.target_entity_uuid, self.granted_action_uuids)
        return super()._remove(event)


class Fly(SpellAction):
    name: str = "Fly"
    description: str = "Touch: 60-foot flying speed, concentration for 10 minutes; supported endpoints only."
    spell_level: int = 3
    spell_school: str = "transmutation"
    concentration: bool = True
    target_type: TargetType = TargetType.MULTI_ENTITY
    include_self: bool = True
    valid_target_filter: str = "self_or_allies"
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))

    def get_multi_target_count(self) -> int:
        return self.alt_target_count or max(1, self.cast_at_level - 2)

    def _apply(self, event: SpellEvent):
        return _install_spell_effect(self, event.phase_to(EventPhase.EFFECT), FlyEffect(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.target_entity_uuid))


class ShillelaghEffect(BaseCondition):
    description: str = "Exact held weapon becomes magical, d8 with optional casting ability."
    name: str = "Shillelagh"
    tags: set[ConditionTag] = {ConditionTag.MAGICAL}
    duration: Duration = Field(default_factory=lambda: _rounds(10))
    weapon_uuid: UUID
    casting_ability: AbilityName

    def _apply(self, event: Event):
        caster = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        weapon = cast(Weapon | None, Weapon.get(self.weapon_uuid))
        if caster is None or weapon is None:
            return [], [], [], [], event.cancel(status_message="Held weapon missing")
        weapon.attack_overrides[self.uuid] = WeaponAttackOverride(wielder_uuid=caster.uuid,
            damage_die=8, optional_ability=self.casting_ability)

        def released(transition: Event, actor_uuid: UUID):
            if isinstance(transition, WeaponUnequipEvent) and transition.item_uuid == self.weapon_uuid:
                actor = Entity.get(actor_uuid)
                if actor is not None:
                    actor.remove_condition_by_uuid(self.uuid, parent_event=transition)
            return None

        handler = EventHandler(name="Shillelagh release", source_entity_uuid=caster.uuid,
            trigger_conditions=[Trigger(event_type=EventType.WEAPON_UNEQUIP, event_phase=EventPhase.EFFECT)],
            event_processor=released)
        caster.add_event_handler(handler)
        return [], [handler.uuid], [], [], event.phase_to(EventPhase.EFFECT)

    def _remove(self, event: Event | None = None):
        weapon = cast(Weapon | None, Weapon.get(self.weapon_uuid))
        if weapon is not None:
            weapon.attack_overrides.pop(self.uuid, None)
        return super()._remove(event)


class Shillelagh(SpellAction):
    name: str = "Shillelagh"
    description: str = "Held wooden club/staff: magical, d8; optionally use spellcasting ability for one minute."
    spell_school: str = "transmutation"
    target_type: TargetType = TargetType.SELF
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN
    selected_weapon_uuid: UUID | None = None

    def _create_declaration_event(self, parent_event: Event | None = None, use_register: bool = True):
        caster = Entity.get(self.source_entity_uuid)
        weapon = caster.equipment.get_weapon(self.weapon_slot) if caster else None
        self.selected_weapon_uuid = weapon.uuid if weapon else None
        declaration = super()._create_declaration_event(parent_event, use_register=use_register)
        return declaration.model_copy(update={"source_item_uuid":self.selected_weapon_uuid}) if declaration else None

    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Shillelagh", cost_type="bonus_actions",
        cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def _validate(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        weapon = caster.equipment.get_weapon(self.weapon_slot) if caster else None
        if weapon is None or weapon.item_id not in {"weapon.club", "weapon.quarterstaff"}:
            return event.cancel(status_message="Shillelagh requires a held wooden club or quarterstaff")
        return super()._validate(event)

    def _apply(self, event: SpellEvent):
        caster = Entity.get(self.source_entity_uuid)
        weapon = caster.equipment.get_weapon(self.weapon_slot) if caster else None
        if (caster is None or weapon is None or weapon.uuid != self.selected_weapon_uuid
                or weapon.item_id not in {"weapon.club", "weapon.quarterstaff"}):
            return event.cancel(status_message="Exact eligible held weapon was lost")
        return _install_spell_effect(self, event.phase_to(EventPhase.EFFECT), ShillelaghEffect(
            source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, weapon_uuid=weapon.uuid,
            casting_ability=caster.spellcasting.resolve_spellcasting_ability(self.spellcasting_source_id)))
