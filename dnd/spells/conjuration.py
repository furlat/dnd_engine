"""Conjuration spells - creating objects and summoning creatures.

Contains: CallLightning, PoisonSpray, AcidSplash, Grease, Web, Cloudkill,
          SpiritGuardians, FogCloud, Darkness, Daylight, InsectPlague, IncendiaryCloud
"""
from typing import Any, Dict, Literal, Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_runtime_materialization import (
    materialize_item_from_installed_runtime,
)
from dnd.core.base_actions import (
    ActionCategory,
    ActionEvent,
    ActionInformationOperation,
    ActionTargetEffectBranchProfile,
    ActionTargetEffectProfile,
    ActionTopologyOperation,
    ActionWorldEffectAnchor,
    ActionWorldEffectCertainty,
    ActionWorldEffectProfile,
    ActionWorldEffectScope,
    ActionWorldEffectShape,
    BaseAction,
    BaseCost,
    Cost,
    InformationEffectProfile,
    OutcomeResolution,
    PositionDiscoveryContract,
    TargetEffectDisposition,
    TargetType,
    TopologyEffectProfile,
)
from dnd.core.base_conditions import BaseCondition
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.materialization import ItemBuildContext
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclaration,
    behavior_identity,
    environment_object_factory,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.condition_types import (
    ConditionCategory,
    ConditionTag,
    DurationType,
    HazardFilter,
)
from dnd.blocks.base_item import BaseItem, UsableItem
import random
from dnd.core.dice import AttackOutcome
from dnd.core.values import ModifiableValue
from dnd.core.events import EventPhase, RangeType, Range, EventType, EventHandler, Trigger, Damage, Event, EventQueue, ExposedFlameEvent, FireExposureEvent, SkillCheckEvent, SpatialChangeEvent, WindExposureEvent
from dnd.core.modifiers import DamageType, NumericalModifier, AdvantageModifier, AdvantageStatus, ResistanceStatus
from dnd.core.base_block import BaseBlock, LightLevel
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.conditions import Concentrating, ConcentrationActionMarker, Prone, Restrained
from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator, entity_action_economy_cost_applier
from dnd.spells.content_metadata import srd_action_identity
from dnd.tile_conditions import ZoneControlCondition, parse_dice_string
from dnd.spells.spell_utils import validate_line_of_sight


@srd_action_identity(
    content_id="action.spell.call_lightning.strike",
    display_name="Call Lightning Strike",
    description="Call another bolt from an active Call Lightning spell.",
    parent_spell_name="Call Lightning",
    source_page=123,
    sort_order=570,
)
class CallLightningStrike(BaseAction):
    """Action granted by Call Lightning to strike with lightning each turn.

    This is NOT a spell - it's a special action granted while concentrating
    on Call Lightning. Uses an action, deals 3d10 lightning (DEX save).
    """
    name: str = Field(default="Call Lightning Strike", description="Display name for the call lightning strike action.")
    description: str = Field(default="Call down a bolt of lightning", description="Rules-facing summary for the call lightning strike action.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for call lightning strike.")
    costs: List[Cost] = Field(default_factory=lambda: [Cost(name="Strike Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)], description="Action economy costs paid to execute call lightning strike.")

    spell_dc: int = Field(default=10, description="Spell save DC used by call lightning strike saving throws.")
    damage_dice_count: int = Field(default=3, description="Number of d10 damage dice rolled by call lightning strike.")
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster UUID used for ownership and effect attribution by call lightning strike.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for call lightning strike.",
    )

    def _create_event(self) -> Event:
        """Create a generic action event."""
        return Event(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            event_type=EventType.CAST_SPELL,
            phase=EventPhase.DECLARATION
        )

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        """Validate target is in range and LOS."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if "Concentrating" not in caster.active_conditions:
            return declaration_event.cancel(status_message="Not concentrating on Call Lightning")

        conc = caster.active_conditions.get("Concentrating")
        if not isinstance(conc, Concentrating) or conc.get_slot_by_spell_name("Call Lightning") is None:
            return declaration_event.cancel(status_message="Not concentrating on Call Lightning")

        if target.uuid not in caster.senses.entities.keys():
            return declaration_event.cancel(status_message="Target not in line of sight")

        distance = caster.senses.get_feet_distance(target.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: Event) -> Optional[Event]:
        """Strike with lightning - DEX save for half damage."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=self.spell_dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"DEX save: {save_roll.total} vs DC {self.spell_dc} - {'Success' if success else 'Failure'}"
        )

        damage_bonus = caster.get_spell_damage_bonus()
        lightning_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=self.damage_dice_count,
            damage_bonus=damage_bonus,
            damage_type=DamageType.LIGHTNING
        )

        damage_dice = lightning_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        target.receive_damage(
            amount=final_damage,
            damage_type=DamageType.LIGHTNING,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        save_text = " (save for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[lightning_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} dealt {final_damage} lightning damage{save_text}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Spend the action declared by the granted strike."""
        return entity_action_economy_cost_applier(
            completion_event,
            self.source_entity_uuid,
        )


class CallLightning(SpellAction):
    """Call Lightning - 3rd level Conjuration (Concentration)

    A storm cloud appears. When you cast the spell, choose a point you can see
    under the cloud. Each creature within 5 feet of that point must make a DEX
    saving throw. A creature takes 3d10 lightning damage on a failed save, or
    half as much on a successful one.

    On each of your turns until the spell ends, you can use your action to call
    down lightning in this way again, targeting the same point or a different one.

    At Higher Levels: Damage increases by 1d10 for each slot level above 3rd.
    """
    name: str = Field(default="Call Lightning", description="Display name for the call lightning spell.")
    description: str = Field(default="Summon storm cloud, strike with lightning each turn", description="Rules-facing summary for the call lightning spell.")
    spell_level: int = Field(default=3, description="Spell slot level required to cast call lightning; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify call lightning.")
    concentration: bool = Field(default=True, description="Whether call lightning creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for call lightning.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for call lightning.",
    )
    projectile_type: Optional[str] = Field(default="bolt", description="Projectile visualization hint for call lightning.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.LIGHTNING, description="Primary damage type for VFX")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range and line of sight."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity or not target_entity:
            return declaration_event.cancel(status_message="Source or target entity not found")

        distance = source_entity.senses.get_feet_distance(target_entity.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
            )

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Call Lightning - initial strike + grant repeatable action."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        damage_dice_count = 3 + self.get_upcast_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=f"Storm cloud appears - requesting DEX save DC {dc}"
        )

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=effect_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = effect_event.post(
            save_success=success,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        damage_bonus = caster.get_spell_damage_bonus()
        lightning_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=10,
            dice_numbers=damage_dice_count,
            damage_bonus=damage_bonus,
            damage_type=DamageType.LIGHTNING
        )

        damage_dice = lightning_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        final_damage = damage_roll.total // 2 if success else damage_roll.total

        target.receive_damage(
            amount=final_damage,
            damage_type=DamageType.LIGHTNING,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        strike_action = CallLightningStrike(
            source_entity_uuid=caster.uuid,
            spell_dc=dc,
            damage_dice_count=damage_dice_count,
            caster_uuid=caster.uuid,
            template=True
        )
        caster.register_action(strike_action)

        concentration = self.ensure_concentration(effect_event)
        marker = ConcentrationActionMarker(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            action_name=strike_action.name
        )
        caster.add_condition(marker, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, marker.uuid)

        save_text = " (save for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[lightning_damage],
            damage_rolls=[damage_roll],
            status_message=f"{self.name} dealt {final_damage} lightning damage{save_text} - can strike again each turn"
        )

class PoisonSpray(SpellAction):
    """Poison Spray - Conjuration Cantrip

    Range 10ft, CON save or 1d12 poison damage.
    Scales: 2d12 at 5th, 3d12 at 11th, 4d12 at 17th.
    """
    name: str = Field(default="Poison Spray", description="Display name for the poison spray spell.")
    description: str = Field(default="CON save or 1d12 poison (10ft range)", description="Rules-facing summary for the poison spray spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast poison spray; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify poison spray.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Targeting mode used by action discovery and validation for poison spray.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=10), description="Range contract used when validating targets for poison spray.")
    projectile_type: Optional[str] = Field(default="spray", description="Projectile visualization hint for poison spray.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.POISON, description="Primary damage type for VFX")

    include_self: bool = Field(default=False, description="Whether poison spray can include the caster among valid targets.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter used when collecting valid targets for poison spray.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate LOS and 10ft range."""

        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return declaration_event.cancel(status_message="Entity not found")

        distance = source.senses.get_feet_distance(target.position)
        if distance > 10:
            return declaration_event.cancel(status_message=f"Out of range ({distance}ft > 10ft)")

        return los_event.phase_to(EventPhase.EXECUTION, status_message="Validated Poison Spray")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """CON save or poison damage."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Entity not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="constitution",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, _save_roll, success = target.saving_throw(save_request)

        if success:
            return execution_event.phase_to(
                EventPhase.COMPLETION,
                save_success=True,
                total_damage=0,
                status_message=f"{target.name} saves against Poison Spray"
            )

        num_dice = self._get_cantrip_dice_count(self.caster_level)
        damage_bonus = caster.get_spell_damage_bonus()

        poison_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=12,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.POISON
        )

        damage_dice = poison_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.POISON,
            source_entity_uuid=caster.uuid,
            parent_event=execution_event.uuid
        )

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            save_success=False,
            damages=[poison_damage],
            damage_rolls=[damage_roll],
            total_damage=damage_roll.total,
            status_message=f"Poison Spray: {damage_roll.total} poison to {target.name}"
        )


class AcidSplash(SpellAction):
    """Acid Splash - Conjuration cantrip

    You hurl a bubble of acid. Choose one or two creatures you can see
    within range. If you choose two, they must be within 5 feet of each other.
    A target must succeed on a DEX save or take 1d6 acid damage.

    Damage scales: 2d6 at 5th, 3d6 at 11th, 4d6 at 17th.
    """
    name: str = Field(default="Acid Splash", description="Display name for the acid splash spell.")
    description: str = Field(default="1-2 targets within 5ft of each other, DEX save or 1d6 acid", description="Rules-facing summary for the acid splash spell.")
    spell_level: int = Field(default=0, description="Spell slot level required to cast acid splash; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify acid splash.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Targeting mode used by action discovery and validation for acid splash.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60), description="Range contract used when validating targets for acid splash.")
    projectile_type: Optional[str] = Field(default="orb", description="Projectile visualization hint for acid splash.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.ACID, description="Primary damage type for VFX")

    allow_same_target: bool = Field(default=False, description="Whether acid splash may select the same entity more than once.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter used when collecting valid targets for acid splash.")

    include_self: bool = Field(default=False, description="Whether acid splash can include the caster among valid targets.")

    def get_num_projectiles(self) -> int:
        """1-2 targets (max 2)."""
        return min(2, 1 + len(self.extra_target_entity_uuids))

    def get_multi_target_count(self) -> Optional[int]:
        return 2

    def get_all_targets(self) -> List[UUID]:
        """Return all targets (1-2)."""
        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)
        return targets[:2]

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range, LOS, and 5ft proximity for 2-target case."""
        source = Entity.get(self.source_entity_uuid)
        if not source:
            return declaration_event.cancel(status_message="Caster not found")

        all_targets = self.get_all_targets()
        if not all_targets:
            return declaration_event.cancel(status_message="No targets specified")

        target_entities = []
        for target_uuid in all_targets:
            target = Entity.get(target_uuid)
            if not target:
                return declaration_event.cancel(status_message="Target not found")

            if target_uuid not in source.senses.entities.keys():
                return declaration_event.cancel(status_message=f"{target.name} not in line of sight")

            distance = source.senses.get_feet_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target.name} out of range ({distance}ft > {self.effective_range}ft)"
                )
            target_entities.append(target)

        if len(target_entities) == 2:
            t1, t2 = target_entities
            dx = abs(t1.position[0] - t2.position[0])
            dy = abs(t1.position[1] - t2.position[1])

            if dx > 1 or dy > 1:
                return declaration_event.cancel(
                    status_message=f"Targets must be within 5ft of each other (distance: {max(dx, dy) * 5}ft)"
                )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply acid splash damage to current target."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="dexterity",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "dexterity").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"DEX save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                total_damage=0,
                status_message=f"{target.name} avoids the acid"
            )

        num_dice = self._get_cantrip_dice_count(self.caster_level)
        damage_bonus = caster.get_spell_damage_bonus()

        acid_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=6,
            dice_numbers=num_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.ACID
        )

        damage_dice = acid_damage.get_dice(attack_outcome=AttackOutcome.HIT)
        damage_roll = damage_dice.roll

        target.receive_damage(
            amount=damage_roll.total,
            damage_type=DamageType.ACID,
            source_entity_uuid=caster.uuid,
            parent_event=effect_event.uuid
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[acid_damage],
            damage_rolls=[damage_roll],
            total_damage=damage_roll.total,
            status_message=f"Acid Splash: {damage_roll.total} acid to {target.name}"
        )


class MistyStep(SpellAction):
    """Misty Step - 2nd level Conjuration

    Briefly surrounded by silvery mist, you teleport up to 30 feet to an
    unoccupied space that you can see.

    Casting Time: Bonus action.
    """
    name: str = Field(default="Misty Step", description="Display name for the misty step spell.")
    description: str = Field(default="Bonus action teleport up to 30ft to a visible space", description="Rules-facing summary for the misty step spell.")
    spell_level: int = Field(default=2, description="Spell slot level required to cast misty step; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify misty step.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for misty step.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF), description="Range contract used when validating targets for misty step.")

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Misty Step Cost", cost_type="bonus_actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute misty step.")

    teleport_range: int = Field(default=30, description="Maximum teleport distance in feet for misty step.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate destination is visible and within range."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No destination specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Destination {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.teleport_range:
            return declaration_event.cancel(
                status_message=f"Destination out of range ({distance}ft > {self.teleport_range}ft)"
            )

        grid = get_map()
        entities_at_dest = grid.get_entities_at(target_pos)
        if entities_at_dest:
            return declaration_event.cancel(status_message=f"Destination {target_pos} is occupied")

        if not grid.is_walkable_for(target_pos[0], target_pos[1], caster.uuid):
            return declaration_event.cancel(status_message=f"Destination {target_pos} is not accessible")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Teleport caster to destination."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No destination")

        start_pos = caster.senses.position

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} teleports from {start_pos} to {target_pos}"
        )

        Entity.update_entity_position(caster, target_pos)

        distance = abs(target_pos[0] - start_pos[0]) * 5 + abs(target_pos[1] - start_pos[1]) * 5

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            start_position=start_pos,
            end_position=target_pos,
            distance_feet=distance,
            status_message=f"{caster.name} teleports {distance}ft via Misty Step"
        )


class GreaseZone(ZoneControlCondition):
    """Zone control condition for Grease spell.

    Creates a 10ft square of difficult terrain. Creatures entering or
    starting their turn in the area must make a DEX save or fall prone.

    Applied to the caster, manages the zone via position-indexed handlers.
    """
    name: str = Field(default="Grease Zone", description="Display name for the grease zone zone condition.")
    description: str = Field(default="Slippery grease - DEX save or fall prone", description="Rules-facing summary for the grease zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the grease zone for cleanup and filtering.")

    zone_shape: str = Field(default="cube", description="Area shape used by grease zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=10, description="Zone radius in feet used by grease zone.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether grease zone makes affected tiles difficult terrain.")

    marker_name: Optional[str] = Field(default="Grease", description="Visible tile marker name created by grease zone.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for grease zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by grease zone saving throws.")

    def _has_entry_effect(self) -> bool:
        """Grease causes saves when entities enter."""
        return True

    def _has_turn_start_effect(self) -> bool:
        """Grease causes saves when entities start turn in zone."""
        return True

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - DEX save or fall prone."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:

                prone = Prone(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid,
                    tags={ConditionTag.MAGICAL}
                )
                entity.add_condition(prone, parent_event=event)

            return None

        return EventHandler(
            name="Grease Entry Save",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create handler for turn start in zone - DEX save or fall prone."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if event.event_type != EventType.TURN_START:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            if entity.senses.position not in zone_condition.affected_positions:
                return None

            if "Prone" in entity.active_conditions:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:

                prone = Prone(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid,
                    tags={ConditionTag.MAGICAL}
                )
                entity.add_condition(prone, parent_event=event)

            return None

        return EventHandler(
            name="Grease Turn Start Save",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EXECUTION
            )],
            event_processor=processor
        )


class Grease(SpellAction):
    """Grease - 1st level Conjuration

    Slick grease covers the ground in a 10-foot square centered on a point
    within range and turns it into difficult terrain for the duration.

    When the grease appears, each creature standing in its area must succeed
    on a Dexterity saving throw or fall prone. A creature that enters the
    area or ends its turn there must also succeed on a Dexterity saving
    throw or fall prone.

    Duration: 1 minute (non-concentration in SRD, but we treat as concentration
    for BG3-style cleanup convenience)
    """
    name: str = Field(default="Grease", description="Display name for the grease spell.")
    description: str = Field(default="10ft square difficult terrain, DEX save or prone", description="Rules-facing summary for the grease spell.")
    spell_level: int = Field(default=1, description="Spell slot level required to cast grease; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify grease.")
    concentration: bool = Field(default=True, description="Whether grease creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for grease.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for grease targeting.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for grease.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Grease Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute grease.")

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Grease's Dexterity-save prone branch."""
        if not isinstance(actor, Entity):
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.grease",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.grease.prone",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="dexterity",
                    condition_fact_ids=("selected_target.condition.prone",),
                    condition_semantic_keys=frozenset({"dnd.conditions.Prone"}),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in range and visible."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Position out of range ({distance}ft > {self.effective_range}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Grease - create zone, apply to creatures already there, concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=f"{caster.name} casts Grease at {target_pos}"
        )

        zone = GreaseZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)

        concentration.add_linked_condition(caster.uuid, zone.uuid)

        grid = get_map()
        prone_count = 0
        for pos in zone.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue
                if ent.uuid == caster.uuid:
                    continue

                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid,
                    ability_name="dexterity",
                    dc=dc,
                    parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)
                if not success:
                    prone = Prone(
                        source_entity_uuid=caster.uuid,
                        target_entity_uuid=ent.uuid,
                        tags={ConditionTag.MAGICAL}
                    )
                    ent.add_condition(prone, parent_event=effect_event)
                    prone_count += 1

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Grease active: 10ft square at {target_pos}, {prone_count} creatures fell prone"
        )


class WebRestrained(BaseCondition):
    """Restrained condition from Web spell.

    Has Restrained as sub-condition. Grants EscapeWebAction to escape.
    """
    name: str = Field(default="Web Restrained", description="Display name for the web restrained condition.")
    description: str = Field(default="Restrained by sticky web - can use action to escape", description="Rules-facing summary for the web restrained condition.")

    spell_dc: int = Field(default=10, description="Spell save DC used by web restrained saving throws.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []
        sub_conditions_uuids: List[UUID] = []

        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Target UUID not set")
        if self.source_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Source UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        restrained = Restrained(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(restrained, parent_event=declaration_event)
        sub_conditions_uuids.append(restrained.uuid)

        escape = EscapeWebAction(
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            restraining_condition_uuid=self.uuid,
            spell_dc=self.spell_dc,
            template=True
        )
        target.register_action(escape)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Web Restrained to {target.name}"
        )

        return outs, handler_uuids, sub_conditions_uuids, [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Remove granted escape action when this condition is removed."""
        if self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target:
                target.unregister_action("Escape Web")
        return super()._remove(event)


class EscapeWebAction(BaseAction):
    """Action to escape from Web spell's Restrained condition.

    Uses an action. Make STR check (Athletics) vs spell DC to escape.
    """
    name: str = Field(default="Escape Web", description="Display name for the escape web action action.")
    description: str = Field(default="Use action to attempt to escape the web", description="Rules-facing summary for the escape web action action.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode used by action discovery and validation for escape web action.")

    restraining_condition_uuid: Optional[UUID] = Field(default=None, description="Condition UUID removed when escape web action succeeds.")
    spell_dc: int = Field(default=10, description="Spell save DC used by escape web action saving throws.")

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Escape Web Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute escape web action.")

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        source_entity = Entity.get(self.source_entity_uuid)
        source_name = source_entity.name if source_entity else None

        return ActionEvent(
            name=self.name or "Escape Web",
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if "Web Restrained" not in entity.active_conditions:
            return declaration_event.cancel(status_message="Not restrained by web")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        check_event = SkillCheckEvent(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            skill_name="athletics",
            dc=self.spell_dc,
            source_entity_name=entity.name,
            parent_event=execution_event.uuid,
        )
        _, _, success = entity.skill_check(check_event)

        if success:

            entity.remove_condition("Web Restrained", parent_event=execution_event)
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{entity.name} breaks free from the web!"
            )
        else:
            return execution_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{entity.name} fails to escape the web"
            )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class WebZone(ZoneControlCondition):
    """Zone control condition for Web spell.

    Creates a 20ft cube of difficult terrain and light obscurement.
    Creatures entering or starting their turn inside must save or become
    restrained.

    Applied to the caster, manages the zone via position-indexed handlers.
    """
    name: str = Field(default="Web Zone", description="Display name for the web zone zone condition.")
    description: str = Field(default="Sticky webs - DEX save or restrained", description="Rules-facing summary for the web zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the web zone for cleanup and filtering.")

    zone_shape: str = Field(default="cube", description="Area shape used by web zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by web zone.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether web zone makes affected tiles difficult terrain.")
    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.DIM_LIGHT, description="Light level applied to affected tiles by web zone.")
    light_is_obscurement: bool = Field(default=True, description="Whether web zone lightly obscures affected tiles.")

    marker_name: Optional[str] = Field(default="Web", description="Visible tile marker name created by web zone.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for web zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by web zone saving throws.")
    anchored_or_layered: bool = Field(
        default=True,
        description="Whether the webs are anchored or layered across a surface and persist past the caster's next turn start.",
    )
    fire_damage_dice: str = Field(
        default="2d4",
        description="Fire damage dealt to creatures starting their turn in a burning web cube.",
    )

    _burning_positions: Set[Tuple[int, int]] = PrivateAttr(default_factory=set)
    _burning_fire_handler_uuid: Optional[UUID] = PrivateAttr(default=None)

    def _has_entry_effect(self) -> bool:
        """Web causes saves when entities enter."""
        return True

    def _has_turn_start_effect(self) -> bool:
        """Web causes saves when entities start their turn in the zone."""
        return True

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - DEX save or restrained."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            if "Web Restrained" in entity.active_conditions:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:

                web_restrained = WebRestrained(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid,
                    spell_dc=dc,
                    tags={ConditionTag.MAGICAL}
                )
                entity.add_condition(web_restrained, parent_event=event)

            return None

        return EventHandler(
            name="Web Entry Save",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create handler for turn start - DEX save or restrained."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            if entity.senses.position not in zone_condition.affected_positions:
                return None

            if "Web Restrained" in entity.active_conditions:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:
                web_restrained = WebRestrained(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid,
                    spell_dc=dc,
                    tags={ConditionTag.MAGICAL}
                )
                entity.add_condition(web_restrained, parent_event=event)

            return None

        return EventHandler(
            name="Web Turn Start Save",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_fire_exposure_handler(self) -> EventHandler:
        """Create a handler that burns away exposed Web cubes."""
        source_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, FireExposureEvent):
                return None
            if event.phase != EventPhase.EFFECT:
                return None

            zone_condition.expose_position_to_fire(
                event.position,
                fire_source_uuid=event.source_entity_uuid,
                parent_event=event,
            )
            return None

        return EventHandler(
            name="Web Fire Exposure",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.FIRE_EXPOSURE,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )

    def _create_burning_fire_handler(self) -> EventHandler:
        """Create a handler for lingering burning Web damage."""
        source_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            if not zone_condition._burning_positions:
                return None

            entity = Entity.get(event.source_entity_uuid)
            if entity is not None and entity.position in zone_condition._burning_positions:
                zone_condition._deal_burning_web_damage(entity, event)

            if event.source_entity_uuid == source_uuid:
                zone_condition._burning_positions.clear()
            return None

        return EventHandler(
            name="Web Burning Fire",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )

    def _ensure_burning_fire_handler(self) -> None:
        """Register and track the burning-fire handler once."""
        if self._burning_fire_handler_uuid is not None:
            return

        fire_handler = self._create_burning_fire_handler()
        EventQueue.add_event_handler(fire_handler)
        self._burning_fire_handler_uuid = fire_handler.uuid
        if fire_handler.uuid not in self.event_handlers_uuids:
            self.event_handlers_uuids.append(fire_handler.uuid)

    def _deal_burning_web_damage(self, entity: Entity, parent_event: Event) -> None:
        """Deal SRD burning Web damage to one entity.

        Args:
            entity: Entity that started its turn in a burning Web cube.
            parent_event: Turn-start event that triggered the damage.
        """
        source_uuid = self.source_entity_uuid
        if source_uuid is None:
            return

        count, value = parse_dice_string(self.fire_damage_dice)
        damage_bonus = ModifiableValue.create(
            source_entity_uuid=source_uuid,
            target_entity_uuid=entity.uuid,
            base_value=0,
            value_name="Web Fire Damage",
        )
        damage = Damage(
            source_entity_uuid=source_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=type_cast(Literal[4, 6, 8, 10, 12, 20], value),
            dice_numbers=count,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE,
        )
        damage_roll = damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        entity.receive_damage(
            damage_roll.total,
            DamageType.FIRE,
            source_uuid,
            damage_rolls=[damage_roll],
            damages=[damage],
            parent_event=parent_event.uuid,
        )

    def expose_position_to_fire(
        self,
        position: Tuple[int, int],
        fire_source_uuid: Optional[UUID] = None,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Burn away one Web cube and leave one round of fire damage.

        Args:
            position: Grid position exposed to fire.
            fire_source_uuid: Entity or object that exposed the cube to fire.
            parent_event: Event that triggered the exposure.

        Returns:
            True when the position was part of the Web zone and was burned.
        """
        if position not in self.affected_positions:
            return False

        removed = self._remove_position_effects(position, parent_event=parent_event)
        if not removed:
            return False

        grid = get_map()
        for entity_uuid in grid.get_entities_at(position):
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            web_restrained = entity.active_conditions.get("Web Restrained")
            if (
                web_restrained is not None
                and web_restrained.source_entity_uuid == self.source_entity_uuid
            ):
                entity.remove_condition("Web Restrained", parent_event=parent_event)

        self._burning_positions.add(position)
        self._ensure_burning_fire_handler()
        return True

    def _create_unanchored_collapse_handler(self) -> EventHandler:
        """Create a handler that ends unanchored webs on the caster's next turn."""
        source_uuid = self.source_entity_uuid
        condition_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            if event.source_entity_uuid != source_uuid:
                return None

            caster = Entity.get(source_uuid)
            if not caster:
                return None
            caster.remove_condition_by_uuid(condition_uuid, parent_event=event)
            return None

        return EventHandler(
            name="Web Unanchored Collapse",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=source_uuid,
            )],
            event_processor=processor,
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Web zone state and optional unanchored-collapse cleanup."""
        terrain_modifiers, handler_uuids, sub_condition_uuids, spatial_handler_uuids, effect_event = super()._apply(declaration_event)

        fire_handler = self._create_fire_exposure_handler()
        EventQueue.add_event_handler(fire_handler)
        handler_uuids.append(fire_handler.uuid)

        if not self.anchored_or_layered and self.source_entity_uuid is not None:
            collapse_handler = self._create_unanchored_collapse_handler()
            EventQueue.add_event_handler(collapse_handler)
            handler_uuids.append(collapse_handler.uuid)

        return terrain_modifiers, handler_uuids, sub_condition_uuids, spatial_handler_uuids, effect_event


class Web(SpellAction):
    """Web - 2nd level Conjuration (Concentration)

    You conjure a mass of thick, sticky webbing at a point of your choice
    within range. The webs fill a 20-foot cube from that point for the duration.
    The webs are difficult terrain and lightly obscure their area.

    If the webs aren't anchored between two solid masses (such as walls or trees)
    or layered across a floor, wall, or ceiling, the conjured web collapses on
    itself, and the spell ends at the start of your next turn.

    Each creature that starts its turn in the webs or that enters them during its
    turn must make a Dexterity saving throw. On a failed save, the creature is
    restrained as long as it remains in the webs or until it breaks free.

    A creature restrained by the webs can use its action to make a Strength check
    against your spell save DC. If it succeeds, it is no longer restrained.

    Web cubes exposed to fire burn away and deal 2d4 fire damage to creatures
    that start their turn in the burning cube before the fire expires.

    Duration: Concentration, up to 1 hour
    """
    name: str = Field(default="Web", description="Display name for the web spell.")
    description: str = Field(default="20ft cube of webs, DEX save or restrained, can escape with STR check", description="Rules-facing summary for the web spell.")
    spell_level: int = Field(default=2, description="Spell slot level required to cast web; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify web.")
    concentration: bool = Field(default=True, description="Whether web creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for web.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for web targeting.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for web.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Web Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute web.")
    anchored_or_layered: bool = Field(
        default=True,
        description="Whether the cast Web is anchored between solid masses or layered across a floor, wall, or ceiling.",
    )

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Declare Web's Dexterity-save restrained branch."""
        if not isinstance(actor, Entity):
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.web",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.web.restrained",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id),
                    save_ability="dexterity",
                    condition_fact_ids=("selected_target.condition.restrained",),
                    condition_semantic_keys=frozenset({
                        "dnd.spells.conjuration.WebRestrained",
                        "dnd.conditions.Restrained",
                    }),
                ),
            ),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in range and visible."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Position out of range ({distance}ft > {self.effective_range}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Web - create zone, restrain creatures already there, concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=f"{caster.name} casts Web at {target_pos}"
        )

        zone = WebZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc,
            anchored_or_layered=self.anchored_or_layered,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)

        concentration.add_linked_condition(caster.uuid, zone.uuid)

        grid = get_map()
        restrained_count = 0
        for pos in zone.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue
                if ent.uuid == caster.uuid:
                    continue

                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid,
                    ability_name="dexterity",
                    dc=dc,
                    parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)
                if not success:
                    web_restrained = WebRestrained(
                        source_entity_uuid=caster.uuid,
                        target_entity_uuid=ent.uuid,
                        spell_dc=dc,
                        tags={ConditionTag.MAGICAL}
                    )
                    ent.add_condition(web_restrained, parent_event=effect_event)
                    restrained_count += 1

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Web active: 20ft cube at {target_pos}, {restrained_count} creatures restrained"
        )


class CloudkillZone(ZoneControlCondition):
    """Zone control condition for Cloudkill spell.

    Creates a 20ft radius sphere of heavily obscured poisonous fog.
    Creatures entering or starting their turn in the area take 5d8 poison
    (CON save for half).

    The cloud moves 10ft away from the caster at the start of each of the
    caster's turns.

    Applied to the caster, manages the zone via position-indexed handlers.
    """
    name: str = Field(default="Cloudkill Zone", description="Display name for the cloudkill zone zone condition.")
    description: str = Field(default="Poisonous fog - CON save or 5d8 poison, half on save", description="Rules-facing summary for the cloudkill zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the cloudkill zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by cloudkill zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by cloudkill zone.")
    adds_difficult_terrain: bool = Field(default=False, description="Whether cloudkill zone makes affected tiles difficult terrain.")

    marker_name: Optional[str] = Field(default="Cloudkill", description="Visible tile marker name created by cloudkill zone.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for cloudkill zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by cloudkill zone saving throws.")
    damage_dice: str = Field(default="5d8", description="Textual damage dice summary for cloudkill zone.")
    upcast_dice: int = Field(default=0, description="Additional damage dice contributed by upcasting cloudkill zone.")

    def _has_entry_effect(self) -> bool:
        """Cloudkill causes damage when entities enter."""
        return True

    def _has_turn_start_effect(self) -> bool:
        """Cloudkill causes damage when entities start turn in zone."""
        return True

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone and add auto-move handler."""

        outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event = super()._apply(declaration_event)

        auto_move_handler = self._create_auto_move_handler()
        EventQueue.add_event_handler(auto_move_handler)
        handler_uuids.append(auto_move_handler.uuid)

        return outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - CON save, poison damage."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        base_dice = 5 + self.upcast_dice

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=8, dice_numbers=base_dice, damage_bonus=dmg_bonus,
                damage_type=DamageType.POISON
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total

            entity.receive_damage(final_damage, DamageType.POISON, source_uuid, parent_event=event.uuid)

            return None

        return EventHandler(
            name="Cloudkill Entry Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create handler for turn start in zone - CON save, poison damage."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        base_dice = 5 + self.upcast_dice
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if event.event_type != EventType.TURN_START:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            if entity.senses.position not in zone_condition.affected_positions:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=8, dice_numbers=base_dice, damage_bonus=dmg_bonus,
                damage_type=DamageType.POISON
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total

            entity.receive_damage(final_damage, DamageType.POISON, source_uuid, parent_event=event.uuid)

            return None

        return EventHandler(
            name="Cloudkill Turn Start Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_auto_move_handler(self) -> EventHandler:
        """Create handler that moves zone 10ft away from caster at caster's turn start."""
        caster_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            if event.source_entity_uuid != caster_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                return None

            cx, cy = caster.senses.position
            zx, zy = zone_condition.zone_center

            dx = zx - cx
            dy = zy - cy

            if dx == 0 and dy == 0:

                dx = 1
                dy = 0

            length = max(abs(dx), abs(dy), 1)
            move_x = int(dx / length * 2) if dx != 0 else 0
            move_y = int(dy / length * 2) if dy != 0 else 0

            new_x = zx + move_x
            new_y = zy + move_y

            zone_condition.move_zone((new_x, new_y))

            return None

        return EventHandler(
            name="Cloudkill Auto-Move",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=caster_uuid
            )],
            event_processor=processor
        )


class Cloudkill(SpellAction):
    """Cloudkill - 5th level Conjuration (Concentration)

    You create a 20-foot-radius sphere of poisonous, yellow-green fog centered
    on a point you choose within range. The fog spreads around corners. It lasts
    for the duration or until strong wind disperses the fog, ending the spell.
    Its area is heavily obscured.

    When a creature enters the spell's area for the first time on a turn or starts
    its turn there, that creature must make a Constitution saving throw. The
    creature takes 5d8 poison damage on a failed save, or half as much damage on
    a successful one. Creatures are affected even if they hold their breath or
    don't need to breathe.

    The fog moves 10 feet away from you at the start of each of your turns,
    rolling along the surface of the ground.

    At Higher Levels: Damage increases by 1d8 for each slot level above 5th.

    Duration: Concentration, up to 10 minutes
    """
    name: str = Field(default="Cloudkill", description="Display name for the cloudkill spell.")
    description: str = Field(default="20ft sphere poison fog, 5d8 poison (CON half), moves away from caster", description="Rules-facing summary for the cloudkill spell.")
    spell_level: int = Field(default=5, description="Spell slot level required to cast cloudkill; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify cloudkill.")
    concentration: bool = Field(default=True, description="Whether cloudkill creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for cloudkill.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for cloudkill targeting.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for cloudkill.",
    )
    projectile_type: Optional[str] = Field(default="orb", description="Projectile visualization hint for cloudkill.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.POISON, description="Primary damage type for VFX")

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Cloudkill Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute cloudkill.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in range and visible."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Position out of range ({distance}ft > {self.effective_range}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Cloudkill - create zone, damage creatures already there, concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        upcast_bonus = self.get_upcast_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            status_message=f"{caster.name} casts Cloudkill at {target_pos}"
        )

        zone = CloudkillZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc,
            upcast_dice=upcast_bonus,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)

        concentration.add_linked_condition(caster.uuid, zone.uuid)

        grid = get_map()
        damage_count = 0
        base_dice = 5 + upcast_bonus

        for pos in zone.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue

                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid,
                    ability_name="constitution",
                    dc=dc,
                    parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)

                dmg_bonus = caster.get_spell_damage_bonus()
                damage_obj = Damage(
                    source_entity_uuid=caster.uuid, target_entity_uuid=ent.uuid,
                    damage_dice=8, dice_numbers=base_dice, damage_bonus=dmg_bonus,
                    damage_type=DamageType.POISON
                )
                damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
                final_damage = damage_roll.total // 2 if success else damage_roll.total

                ent.receive_damage(final_damage, DamageType.POISON, caster.uuid, parent_event=effect_event.uuid)
                damage_count += 1

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Cloudkill active: 20ft sphere at {target_pos}, {damage_count} creatures damaged"
        )


class SpiritGuardiansTriggered(BaseCondition):
    """Marker condition to prevent multiple Spirit Guardians damage in one turn.

    Applied when an entity takes Spirit Guardians damage. Lasts 1 round
    (removed at the entity's next turn end).
    """
    name: str = Field(default="Spirit Guardians Triggered", description="Display name for the spirit guardians triggered condition.")
    description: str = Field(default="Already damaged by Spirit Guardians this turn", description="Rules-facing summary for the spirit guardians triggered condition.")
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        description="Internal once-per-turn marker category.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        handler = self._create_cleanup_handler()
        EventQueue.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Spirit Guardians damage marker applied"
        ) if declaration_event else None

        return [], [handler.uuid], [], [], effect_event

    def _create_cleanup_handler(self) -> EventHandler:
        """Remove this marker at the end of the target's turn."""
        target_uuid = self.target_entity_uuid
        if target_uuid is None:
            raise ValueError("Target UUID not set for Spirit Guardians Triggered")

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_END:
                return None
            if event.source_entity_uuid != target_uuid:
                return None

            entity = Entity.get(target_uuid)
            if entity and "Spirit Guardians Triggered" in entity.active_conditions:
                entity.remove_condition("Spirit Guardians Triggered", parent_event=event)

            return None

        return EventHandler(
            name="Spirit Guardians Triggered Cleanup",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


class SpiritGuardiansSlowed(BaseCondition):
    """Speed halving condition from Spirit Guardians.

    Applied to enemies within the Spirit Guardians zone.
    Removed when they leave the zone.
    """
    name: str = Field(default="Spirit Guardians Slowed", description="Display name for the spirit guardians slowed condition.")
    description: str = Field(default="Speed halved by Spirit Guardians", description="Rules-facing summary for the spirit guardians slowed condition.")
    tags: Set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.MAGICAL},
        description="Condition tags that classify the spirit guardians slow for cleanup and filtering.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        outs: List[Tuple[UUID, UUID]] = []

        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Target UUID not set")

        entity = Entity.get(self.target_entity_uuid)
        if not entity:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")
        if entity.ignore_magical_speed_reduction:
            return [], [], [], [], declaration_event.cancel(status_message=f"{entity.name} ignores magical speed reduction")

        current_speed = entity.action_economy.get_base_value("movement")
        half_speed = current_speed // 2

        mod = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            name="Spirit Guardians Slowed",
            value=-half_speed
        )
        mod_uuid = entity.action_economy.movement.self_static.add_value_modifier(mod)
        outs.append((entity.action_economy.movement.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{entity.name}'s speed halved by Spirit Guardians"
        ) if declaration_event else None

        return outs, [], [], [], effect_event


class SpiritGuardiansZone(ZoneControlCondition):
    """Zone control condition for Spirit Guardians spell.

    Creates a 15ft radius sphere centered on the caster. The zone follows
    the caster as they move. Enemies entering or starting turn in the zone
    must make WIS save or take 3d8 radiant damage (half on save).

    Only affects enemies. Allies are unaffected.
    """
    name: str = Field(default="Spirit Guardians Zone", description="Display name for the spirit guardians zone zone condition.")
    description: str = Field(default="Spectral warriors damage enemies entering the zone", description="Rules-facing summary for the spirit guardians zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the spirit guardians zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by spirit guardians zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=15, description="Zone radius in feet used by spirit guardians zone.")
    adds_difficult_terrain: bool = Field(default=False, description="Whether spirit guardians zone makes affected tiles difficult terrain.")

    marker_name: Optional[str] = Field(default="Spirit Guardians", description="Visible tile marker name created by spirit guardians zone.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ENEMIES, description="Creature relationship filter used for spirit guardians zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by spirit guardians zone saving throws.")
    damage_dice: str = Field(default="3d8", description="Textual damage dice summary for spirit guardians zone.")
    damage_type: DamageType = Field(default=DamageType.RADIANT, description="Damage type dealt by spirit guardians zone.")
    upcast_dice: int = Field(default=0, description="Additional damage dice contributed by upcasting spirit guardians zone.")

    def _has_entry_effect(self) -> bool:
        """Spirit Guardians damages enemies when they enter."""
        return True

    def _has_turn_start_effect(self) -> bool:
        """Spirit Guardians damages enemies when they start turn in zone."""
        return True

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply zone and add follow-caster handler."""

        outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event = super()._apply(declaration_event)

        follow_handler = self._create_follow_caster_handler()
        EventQueue.add_event_handler(follow_handler)
        handler_uuids.append(follow_handler.uuid)

        exit_handler = self._create_zone_exit_handler()
        EventQueue.add_spatial_handler(exit_handler, self.affected_positions, EventType.SPATIAL_ENTITY_LEFT, EventPhase.EFFECT)
        self._exit_handler_uuid = exit_handler.uuid
        external_uuids.append(exit_handler.uuid)

        return outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - WIS save, radiant damage (enemies only)."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        base_dice = 3 + self.upcast_dice
        dmg_type = self.damage_type

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            if entity.uuid == source_uuid:
                return None

            caster = Entity.get(source_uuid)
            if caster and entity.is_ally(caster):
                return None

            if "Spirit Guardians Triggered" in entity.active_conditions:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=8, dice_numbers=base_dice, damage_bonus=dmg_bonus,
                damage_type=dmg_type
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total

            entity.receive_damage(final_damage, dmg_type, source_uuid, parent_event=event.uuid)

            marker = SpiritGuardiansTriggered(
                source_entity_uuid=source_uuid,
                target_entity_uuid=entity.uuid
            )
            entity.add_condition(marker, parent_event=event)

            if "Spirit Guardians Slowed" not in entity.active_conditions:
                slowed = SpiritGuardiansSlowed(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid
                )
                entity.add_condition(slowed, parent_event=event)

            return None

        return EventHandler(
            name="Spirit Guardians Entry Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Create handler for turn start in zone - WIS save, radiant damage (enemies only)."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        base_dice = 3 + self.upcast_dice
        dmg_type = self.damage_type
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if event.event_type != EventType.TURN_START:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            if entity.senses.position not in zone_condition.affected_positions:
                return None

            if entity.uuid == source_uuid:
                return None

            caster = Entity.get(source_uuid)
            if caster and entity.is_ally(caster):
                return None

            if "Spirit Guardians Triggered" in entity.active_conditions:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=8, dice_numbers=base_dice, damage_bonus=dmg_bonus,
                damage_type=dmg_type
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total

            entity.receive_damage(final_damage, dmg_type, source_uuid, parent_event=event.uuid)

            marker = SpiritGuardiansTriggered(
                source_entity_uuid=source_uuid,
                target_entity_uuid=entity.uuid
            )
            entity.add_condition(marker, parent_event=event)

            return None

        return EventHandler(
            name="Spirit Guardians Turn Start Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_exit_handler(self) -> EventHandler:
        """Create handler for zone exit - remove speed debuff."""
        source_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            if event.old_position in zone_condition.affected_positions:
                return None

            if "Spirit Guardians Slowed" in entity.active_conditions:
                entity.remove_condition("Spirit Guardians Slowed", parent_event=event)

            return None

        return EventHandler(
            name="Spirit Guardians Exit Cleanup",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_follow_caster_handler(self) -> EventHandler:
        """Create handler that moves zone to follow caster."""
        caster_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if not isinstance(event, SpatialChangeEvent) or event.entity_uuid != caster_uuid:
                return None

            caster = Entity.get(caster_uuid)
            if caster:
                zone_condition.move_zone(caster.senses.position)

            return None

        return EventHandler(
            name="Spirit Guardians Follow",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )


class SpiritGuardians(SpellAction):
    """Spirit Guardians - 3rd level Conjuration (Concentration)

    You call forth spirits to protect you. They flit around you to a distance
    of 15 feet for the duration. If you are good or neutral, their spectral
    form appears angelic or fey (your choice). If you are evil, they appear
    fiendish.

    When you cast this spell, you can designate any number of creatures you
    can see to be unaffected by it. An affected creature's speed is halved in
    the area, and when the creature enters the area for the first time on a
    turn or starts its turn there, it must make a Wisdom saving throw. On a
    failed save, the creature takes 3d8 radiant damage (if you are good or
    neutral) or 3d8 necrotic damage (if you are evil). On a successful save,
    the creature takes half as much damage.

    At Higher Levels: Damage increases by 1d8 for each slot level above 3rd.

    Duration: Concentration, up to 10 minutes

    NOTE: This implementation only affects enemies (not neutral creatures).
    """
    name: str = Field(default="Spirit Guardians", description="Display name for the spirit guardians spell.")
    description: str = Field(default="15ft sphere around caster, enemies take 3d8 radiant (WIS half), speed halved", description="Rules-facing summary for the spirit guardians spell.")
    spell_level: int = Field(default=3, description="Spell slot level required to cast spirit guardians; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify spirit guardians.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")
    concentration: bool = Field(default=True, description="Whether spirit guardians creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode used by action discovery and validation for spirit guardians.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF),
        description="Range contract used when validating targets for spirit guardians.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Spirit Guardians Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute spirit guardians.")

    damage_type: DamageType = Field(default=DamageType.RADIANT, description="Damage type dealt by spirit guardians.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Spirit Guardians is self-targeted, minimal validation needed."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Spirit Guardians - create zone centered on caster."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        upcast_bonus = self.get_upcast_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="wisdom",
            save_dc=dc,
            status_message=f"{caster.name} casts Spirit Guardians"
        )

        zone = SpiritGuardiansZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=caster.senses.position,
            spell_dc=dc,
            damage_type=self.damage_type,
            upcast_dice=upcast_bonus,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)

        concentration.add_linked_condition(caster.uuid, zone.uuid)

        grid = get_map()
        damage_count = 0
        base_dice = 3 + upcast_bonus

        for pos in zone.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent:
                    continue
                if ent.uuid == caster.uuid:
                    continue
                if ent.is_ally(caster):
                    continue

                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid,
                    ability_name="wisdom",
                    dc=dc,
                    parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)

                dmg_bonus = caster.get_spell_damage_bonus()
                damage_obj = Damage(
                    source_entity_uuid=caster.uuid, target_entity_uuid=ent.uuid,
                    damage_dice=8, dice_numbers=base_dice, damage_bonus=dmg_bonus,
                    damage_type=self.damage_type
                )
                damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
                final_damage = damage_roll.total // 2 if success else damage_roll.total

                ent.receive_damage(final_damage, self.damage_type, caster.uuid, parent_event=effect_event.uuid)
                damage_count += 1

                marker = SpiritGuardiansTriggered(
                    source_entity_uuid=caster.uuid,
                    target_entity_uuid=ent.uuid
                )
                ent.add_condition(marker, parent_event=effect_event)

                if "Spirit Guardians Slowed" not in ent.active_conditions:
                    slowed = SpiritGuardiansSlowed(
                        source_entity_uuid=caster.uuid,
                        target_entity_uuid=ent.uuid
                    )
                    ent.add_condition(slowed, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Spirit Guardians active: 15ft sphere around {caster.name}, {damage_count} enemies damaged"
        )


class FogCloudZone(ZoneControlCondition):
    """Zone control condition for Fog Cloud spell.

    Creates a 20ft radius sphere of heavily obscured area (DARKNESS).
    Uses obscurement so darkvision cannot see through it.
    """
    name: str = Field(default="Fog Cloud Zone", description="Display name for the fog cloud zone zone condition.")
    description: str = Field(default="Heavily obscured fog — blocks vision including darkvision", description="Rules-facing summary for the fog cloud zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the fog cloud zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by fog cloud zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by fog cloud zone.")

    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.DARKNESS, description="Light level applied to affected tiles by fog cloud zone.")
    light_is_obscurement: bool = Field(default=True, description="Whether fog cloud zone blocks sight through its light level.")


class FogCloud(SpellAction):
    """Fog Cloud - 1st level Conjuration (Concentration)

    You create a 20-foot-radius sphere of fog centered on a point within range.
    The sphere spreads around corners, and its area is heavily obscured. It
    lasts for the duration or until a wind of moderate or greater speed (at
    least 10 miles per hour) disperses it.

    At Higher Levels: The radius increases by 20 feet for each slot level
    above 1st.

    Duration: Concentration, up to 1 hour
    """
    name: str = Field(default="Fog Cloud", description="Display name for the fog cloud spell.")
    description: str = Field(default="20ft sphere heavily obscured fog (blocks darkvision)", description="Rules-facing summary for the fog cloud spell.")
    spell_level: int = Field(default=1, description="Spell slot level required to cast fog cloud; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify fog cloud.")
    concentration: bool = Field(default=True, description="Whether fog cloud creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for fog cloud.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for fog cloud targeting.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=120),
        description="Range contract used when validating targets for fog cloud.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Fog Cloud Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute fog cloud.")

    def get_world_effect_profile(self, actor: Any) -> ActionWorldEffectProfile:
        """Declare Fog Cloud's slot-scaled concealment and vision blocker.

        Args:
            actor: Entity discovering the spell. The radius is determined by
                this action variant's cast slot rather than actor-private data.

        Returns:
            Typed information and topology effects matching the runtime zone.
        """
        radius = 20 + self.get_upcast_bonus() * 20
        return ActionWorldEffectProfile(
            semantic_id="control.fog_cloud",
            information_effects=(InformationEffectProfile(
                operation=ActionInformationOperation.CONCEAL_REGION,
                certainty=ActionWorldEffectCertainty.GUARANTEED,
                anchor=ActionWorldEffectAnchor.SELECTED_POSITION,
                scope=ActionWorldEffectScope.REGION,
                shape=ActionWorldEffectShape.SPHERE,
                radius_feet=radius,
            ),),
            topology_effects=(TopologyEffectProfile(
                operation=ActionTopologyOperation.CREATE_BLOCKER,
                certainty=ActionWorldEffectCertainty.GUARANTEED,
                anchor=ActionWorldEffectAnchor.SELECTED_POSITION,
                scope=ActionWorldEffectScope.REGION,
                shape=ActionWorldEffectShape.SPHERE,
                radius_feet=radius,
                affects_vision=True,
            ),),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Position out of range ({distance}ft > {self.effective_range}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        radius = 20 + self.get_upcast_bonus() * 20

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Fog Cloud at {target_pos}"
        )

        zone = FogCloudZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            zone_radius_feet=radius,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Fog Cloud active: {radius}ft radius sphere at {target_pos}"
        )


class DarknessZone(ZoneControlCondition):
    """Zone control condition for Darkness spell.

    Creates a 15ft radius sphere of magical darkness.
    Magical darkness blocks all vision including darkvision.
    Only Truesight and Devil's Sight can see through it.
    """
    name: str = Field(default="Darkness Zone", description="Display name for the darkness zone zone condition.")
    description: str = Field(default="Magical darkness — blocks all vision including darkvision", description="Rules-facing summary for the darkness zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the darkness zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by darkness zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=15, description="Zone radius in feet used by darkness zone.")

    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.MAGICAL_DARKNESS, description="Light level applied to affected tiles by darkness zone.")
    light_is_obscurement: bool = Field(default=True, description="Whether darkness zone blocks sight through its light level.")


class Darkness(SpellAction):
    """Darkness - 2nd level Evocation (Concentration)

    Magical darkness spreads from a point you choose within range to fill a
    15-foot-radius sphere for the duration. The darkness spreads around corners.
    A creature with darkvision can't see through this darkness, and nonmagical
    light can't illuminate it.

    If the point you choose is on an object you are holding or one that isn't
    being worn or carried, the darkness emanates from the object and moves with
    it. Completely covering the source of the darkness with an opaque object,
    such as a bowl or a helm, blocks the darkness.

    Duration: Concentration, up to 10 minutes
    """
    name: str = Field(default="Darkness", description="Display name for the darkness spell.")
    description: str = Field(default="15ft sphere magical darkness (blocks darkvision)", description="Rules-facing summary for the darkness spell.")
    spell_level: int = Field(default=2, description="Spell slot level required to cast darkness; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify darkness.")
    concentration: bool = Field(default=True, description="Whether darkness creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for darkness.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for darkness targeting.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for darkness.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Darkness Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute darkness.")

    def get_world_effect_profile(self, actor: Any) -> ActionWorldEffectProfile:
        """Declare Darkness's concealment and magical vision blocker.

        Args:
            actor: Entity discovering the spell. Darkness has fixed geometry.

        Returns:
            Typed information and topology effects matching the runtime zone.
        """
        return ActionWorldEffectProfile(
            semantic_id="control.darkness",
            information_effects=(InformationEffectProfile(
                operation=ActionInformationOperation.CONCEAL_REGION,
                certainty=ActionWorldEffectCertainty.GUARANTEED,
                anchor=ActionWorldEffectAnchor.SELECTED_POSITION,
                scope=ActionWorldEffectScope.REGION,
                shape=ActionWorldEffectShape.SPHERE,
                radius_feet=15,
            ),),
            topology_effects=(TopologyEffectProfile(
                operation=ActionTopologyOperation.CREATE_BLOCKER,
                certainty=ActionWorldEffectCertainty.GUARANTEED,
                anchor=ActionWorldEffectAnchor.SELECTED_POSITION,
                scope=ActionWorldEffectScope.MAGICAL_DARKNESS,
                shape=ActionWorldEffectShape.SPHERE,
                radius_feet=15,
                affects_vision=True,
            ),),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Position out of range ({distance}ft > {self.effective_range}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Darkness at {target_pos}"
        )

        zone = DarknessZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Darkness active: 15ft sphere at {target_pos}"
        )


class DaylightZone(ZoneControlCondition):
    """Zone control condition for Daylight spell.

    Creates a 60ft radius sphere of very bright light.
    Dispels any magical darkness in the area.
    Entities hidden in the zone are revealed.
    """
    name: str = Field(default="Daylight Zone", description="Display name for the daylight zone zone condition.")
    description: str = Field(default="Very bright light — reveals hidden creatures", description="Rules-facing summary for the daylight zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the daylight zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by daylight zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=60, description="Zone radius in feet used by daylight zone.")

    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.VERY_BRIGHT, description="Light level applied to affected tiles by daylight zone.")
    light_is_obscurement: bool = Field(default=False, description="Whether daylight zone blocks sight through its light level.")


def _is_daylight_targetable_darkness(position: Tuple[int, int]) -> bool:
    """Return whether Daylight may target a magical-darkness position."""
    tile = get_map().get_tile(*position)
    return tile is not None and tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS


def _remove_overlapping_darkness_zones(
    daylight_zone: DaylightZone,
    parent_event: Event,
) -> int:
    """Remove active Darkness zones overlapping a Daylight zone."""
    removed = 0
    for entity in list(Entity._entity_registry.values()):
        condition = entity.active_conditions.get("Darkness Zone")
        if not isinstance(condition, DarknessZone):
            continue
        if condition.affected_positions.isdisjoint(daylight_zone.affected_positions):
            continue
        entity.remove_condition("Darkness Zone", parent_event=parent_event)
        removed += 1
    return removed


class Daylight(SpellAction):
    """Daylight - 3rd level Evocation (not actually Concentration per SRD, but
    we use Concentration for cleanup convenience in our system)

    A 60-foot-radius sphere of light spreads out from a point you choose
    within range. The sphere is bright light and sheds dim light for an
    additional 60 feet.

    If you chose a point on an object you are holding or one that isn't being
    worn or carried, the light shines from the object with and moves with it.

    If any of this spell's area overlaps with an area of darkness created by a
    spell of 3rd level or lower, the spell that created the darkness is
    dispelled.

    Duration: 1 hour (using Concentration for cleanup)
    """
    name: str = Field(default="Daylight", description="Display name for the daylight spell.")
    description: str = Field(default="60ft sphere very bright light, reveals hidden, dispels darkness", description="Rules-facing summary for the daylight spell.")
    spell_level: int = Field(default=3, description="Spell slot level required to cast daylight; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify daylight.")
    concentration: bool = Field(default=True, description="Whether daylight creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for daylight.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range contract used when validating targets for daylight.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Daylight Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute daylight.")

    def get_world_effect_profile(self, actor: Any) -> ActionWorldEffectProfile:
        """Declare Daylight's illumination and Darkness-specific removal.

        Args:
            actor: Entity discovering the spell. Daylight has fixed geometry.

        Returns:
            Typed information and topology effects matching the runtime zone.
        """
        return ActionWorldEffectProfile(
            semantic_id="information.daylight",
            information_effects=(
                InformationEffectProfile(
                    operation=ActionInformationOperation.CHANGE_LIGHT,
                    certainty=ActionWorldEffectCertainty.GUARANTEED,
                    anchor=ActionWorldEffectAnchor.SELECTED_POSITION,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=60,
                ),
                InformationEffectProfile(
                    operation=ActionInformationOperation.REVEAL_REGION,
                    certainty=ActionWorldEffectCertainty.CONDITIONAL,
                    anchor=ActionWorldEffectAnchor.SELECTED_POSITION,
                    scope=ActionWorldEffectScope.REGION,
                    shape=ActionWorldEffectShape.SPHERE,
                    radius_feet=60,
                ),
            ),
            topology_effects=(TopologyEffectProfile(
                operation=ActionTopologyOperation.REMOVE_BLOCKER,
                certainty=ActionWorldEffectCertainty.CONDITIONAL,
                anchor=ActionWorldEffectAnchor.SELECTED_POSITION,
                scope=ActionWorldEffectScope.MAGICAL_DARKNESS,
                shape=ActionWorldEffectShape.SPHERE,
                radius_feet=60,
                affects_vision=True,
            ),),
        )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position specified")

        if (
            (target_pos not in caster.senses.visible or not caster.senses.visible[target_pos])
            and not _is_daylight_targetable_darkness(target_pos)
        ):
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Position out of range ({distance}ft > {self.effective_range}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Daylight at {target_pos}"
        )

        zone = DaylightZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)
        removed_darkness = _remove_overlapping_darkness_zones(zone, effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Daylight active: 60ft sphere at {target_pos}; dispelled {removed_darkness} darkness zone(s)"
        )


class InsectPlagueZone(ZoneControlCondition):
    """Zone for Insect Plague - swarming locusts deal piercing damage."""
    name: str = Field(default="Insect Plague Zone", description="Display name for the insect plague zone zone condition.")
    description: str = Field(default="Swarming biting locusts - CON save or 4d10 piercing", description="Rules-facing summary for the insect plague zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the insect plague zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by insect plague zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by insect plague zone.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether insect plague zone makes affected tiles difficult terrain.")
    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.DIM_LIGHT, description="Light level applied to affected tiles by insect plague zone.")
    light_is_obscurement: bool = Field(default=True, description="Whether insect plague zone lightly obscures affected tiles.")

    marker_name: Optional[str] = Field(default="Insect Plague", description="Visible tile marker name created by insect plague zone.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for insect plague zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by insect plague zone saving throws.")
    base_dice: int = Field(default=4, description="Base number of damage dice rolled by insect plague zone.")
    upcast_dice: int = Field(default=0, description="Additional damage dice contributed by upcasting insect plague zone.")

    def _has_entry_effect(self) -> bool:
        return True

    def _has_turn_start_effect(self) -> bool:
        return True

    def _create_zone_entry_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        num_dice = self.base_dice + self.upcast_dice

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            entity = Entity.get(event.entity_uuid)
            if not entity or not entity.has_hp:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=10, dice_numbers=num_dice, damage_bonus=dmg_bonus,
                damage_type=DamageType.PIERCING
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total
            entity.receive_damage(final_damage, DamageType.PIERCING, source_uuid, parent_event=event.uuid)
            return None

        return EventHandler(
            name="Insect Plague Entry Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        num_dice = self.base_dice + self.upcast_dice
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity or not entity.has_hp:
                return None
            if entity.senses.position not in zone_condition.affected_positions:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=10, dice_numbers=num_dice, damage_bonus=dmg_bonus,
                damage_type=DamageType.PIERCING
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total
            entity.receive_damage(final_damage, DamageType.PIERCING, source_uuid, parent_event=event.uuid)
            return None

        return EventHandler(
            name="Insect Plague Turn Start Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )


class InsectPlague(SpellAction):
    """Insect Plague - 5th level Conjuration (Concentration)

    Swarming locusts fill a 20ft sphere. CON save or 4d10 piercing (half on save).
    Damages on entry and turn start. At Higher Levels: +1d10 per level above 5th.
    """
    name: str = Field(default="Insect Plague", description="Display name for the insect plague spell.")
    description: str = Field(default="20ft sphere swarming locusts, 4d10 piercing (CON half)", description="Rules-facing summary for the insect plague spell.")
    spell_level: int = Field(default=5, description="Spell slot level required to cast insect plague; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify insect plague.")
    concentration: bool = Field(default=True, description="Whether insect plague creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for insect plague.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for insect plague targeting.",
    )
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60), description="Range contract used when validating targets for insect plague.")
    projectile_type: Optional[str] = Field(default="orb", description="Projectile visualization hint for insect plague.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.PIERCING, description="Primary damage type for VFX")

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Insect Plague Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute insect plague.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Out of range ({distance}ft)")

        return declaration_event.phase_to(EventPhase.EXECUTION, status_message=f"Validated {self.name}")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        upcast_bonus = self.get_upcast_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution", save_dc=dc,
            status_message=f"{caster.name} casts Insect Plague at {target_pos}"
        )

        zone = InsectPlagueZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc,
            upcast_dice=upcast_bonus,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        grid = get_map()
        base_dice = 4 + upcast_bonus
        for pos in zone.affected_positions:
            for ent_uuid in grid.get_entities_at(pos):
                ent = Entity.get(ent_uuid)
                if not ent or not ent.has_hp:
                    continue
                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid, ability_name="constitution",
                    dc=dc, parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)
                dmg_bonus = caster.get_spell_damage_bonus()
                damage_obj = Damage(
                    source_entity_uuid=caster.uuid, target_entity_uuid=ent.uuid,
                    damage_dice=10, dice_numbers=base_dice, damage_bonus=dmg_bonus,
                    damage_type=DamageType.PIERCING
                )
                damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
                final_damage = damage_roll.total // 2 if success else damage_roll.total
                ent.receive_damage(final_damage, DamageType.PIERCING, caster.uuid, parent_event=effect_event.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Insect Plague active: 20ft sphere at {target_pos}"
        )


class IncendiaryCloudZone(ZoneControlCondition):
    """Zone for Incendiary Cloud - roiling fire cloud deals fire damage."""
    name: str = Field(default="Incendiary Cloud Zone", description="Display name for the incendiary cloud zone zone condition.")
    description: str = Field(default="Roiling fire cloud - DEX save or 10d8 fire", description="Rules-facing summary for the incendiary cloud zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the incendiary cloud zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by incendiary cloud zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by incendiary cloud zone.")
    adds_difficult_terrain: bool = Field(default=False, description="Whether incendiary cloud zone makes affected tiles difficult terrain.")
    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.DARKNESS, description="Light level applied to affected tiles by incendiary cloud zone.")
    light_is_obscurement: bool = Field(default=True, description="Whether incendiary cloud zone blocks sight through its light level.")

    marker_name: Optional[str] = Field(default="Incendiary Cloud", description="Visible tile marker name created by incendiary cloud zone.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for incendiary cloud zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by incendiary cloud zone saving throws.")
    base_dice: int = Field(default=10, description="Base number of damage dice rolled by incendiary cloud zone.")

    def _has_entry_effect(self) -> bool:
        return True

    def _has_turn_start_effect(self) -> bool:
        return True

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event = super()._apply(declaration_event)
        auto_move_handler = self._create_auto_move_handler()
        EventQueue.add_event_handler(auto_move_handler)
        handler_uuids.append(auto_move_handler.uuid)
        return outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event

    def _create_zone_entry_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        num_dice = self.base_dice

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            entity = Entity.get(event.entity_uuid)
            if not entity or not entity.has_hp:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid, ability_name="dexterity",
                dc=dc, parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)
            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=8, dice_numbers=num_dice, damage_bonus=dmg_bonus,
                damage_type=DamageType.FIRE
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total
            entity.receive_damage(final_damage, DamageType.FIRE, source_uuid, parent_event=event.uuid)
            return None

        return EventHandler(
            name="Incendiary Cloud Entry Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        num_dice = self.base_dice
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity or not entity.has_hp:
                return None
            if entity.senses.position not in zone_condition.affected_positions:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid, ability_name="dexterity",
                dc=dc, parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)
            caster = Entity.get(source_uuid)
            dmg_bonus = caster.get_spell_damage_bonus() if caster else ModifiableValue.create(
                source_entity_uuid=source_uuid, base_value=0, value_name="Spell Damage"
            )
            damage_obj = Damage(
                source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid,
                damage_dice=8, dice_numbers=num_dice, damage_bonus=dmg_bonus,
                damage_type=DamageType.FIRE
            )
            damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
            final_damage = damage_roll.total // 2 if success else damage_roll.total
            entity.receive_damage(final_damage, DamageType.FIRE, source_uuid, parent_event=event.uuid)
            return None

        return EventHandler(
            name="Incendiary Cloud Turn Start Damage",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_auto_move_handler(self) -> EventHandler:
        """Move cloud 10ft away from caster at caster's turn start."""
        caster_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            if event.source_entity_uuid != caster_uuid:
                return None
            caster = Entity.get(caster_uuid)
            if not caster:
                return None

            cx, cy = caster.senses.position
            zx, zy = zone_condition.zone_center
            dx = zx - cx
            dy = zy - cy
            if dx == 0 and dy == 0:
                dx = 1
            length = max(abs(dx), abs(dy), 1)
            move_x = int(dx / length * 2) if dx != 0 else 0
            move_y = int(dy / length * 2) if dy != 0 else 0
            zone_condition.move_zone((zx + move_x, zy + move_y))
            return None

        return EventHandler(
            name="Incendiary Cloud Auto-Move",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=caster_uuid
            )],
            event_processor=processor
        )


class IncendiaryCloud(SpellAction):
    """Incendiary Cloud - 8th level Conjuration (Concentration)

    A cloud of roiling fire fills a 20ft sphere. DEX save or 10d8 fire (half on save).
    Damages on entry and turn start. Cloud moves 10ft away from caster each turn.
    Heavily obscured area.
    """
    name: str = Field(default="Incendiary Cloud", description="Display name for the incendiary cloud spell.")
    description: str = Field(default="20ft sphere fire cloud, 10d8 fire (DEX half), heavily obscured", description="Rules-facing summary for the incendiary cloud spell.")
    spell_level: int = Field(default=8, description="Spell slot level required to cast incendiary cloud; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify incendiary cloud.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.FIRE, description="Primary damage type for VFX")
    concentration: bool = Field(default=True, description="Whether incendiary cloud creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for incendiary cloud.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for incendiary cloud targeting.",
    )
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60), description="Range contract used when validating targets for incendiary cloud.")

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Incendiary Cloud Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute incendiary cloud.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Out of range ({distance}ft)")

        return declaration_event.phase_to(EventPhase.EXECUTION, status_message=f"Validated {self.name}")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity", save_dc=dc,
            status_message=f"{caster.name} casts Incendiary Cloud at {target_pos}"
        )

        zone = IncendiaryCloudZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        grid = get_map()
        for pos in zone.affected_positions:
            for ent_uuid in grid.get_entities_at(pos):
                ent = Entity.get(ent_uuid)
                if not ent or not ent.has_hp:
                    continue
                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid, ability_name="dexterity",
                    dc=dc, parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)
                dmg_bonus = caster.get_spell_damage_bonus()
                damage_obj = Damage(
                    source_entity_uuid=caster.uuid, target_entity_uuid=ent.uuid,
                    damage_dice=8, dice_numbers=10, damage_bonus=dmg_bonus,
                    damage_type=DamageType.FIRE
                )
                damage_roll = damage_obj.get_dice(attack_outcome=AttackOutcome.HIT).roll
                final_damage = damage_roll.total // 2 if success else damage_roll.total
                ent.receive_damage(final_damage, DamageType.FIRE, caster.uuid, parent_event=effect_event.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Incendiary Cloud active: 20ft sphere at {target_pos}"
        )


class NauseatedCondition(BaseCondition):
    """Entity is nauseated and spends its action retching.

    Applied by Stinking Cloud when CON save fails at turn start.
    Duration: 1 round (auto-expires via advance_duration).
    """
    name: str = Field(default="Nauseated", description="Display name for the nauseated condition condition.")
    description: str = Field(default="Nauseated - spends action retching", description="Rules-facing summary for the nauseated condition condition.")

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        target_uuid = target.uuid

        actions_uuid = target.action_economy.actions.self_static.add_max_constraint(
            NumericalModifier(
                name="Nauseated",
                value=0,
                source_entity_uuid=target_uuid,
                target_entity_uuid=self.source_entity_uuid,
            )
        )
        outs.append((target.action_economy.actions.uuid, actions_uuid))

        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 1

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is nauseated"
        )
        return outs, [], [], [], effect_event


class StinkingCloudZone(ZoneControlCondition):
    """Zone control condition for Stinking Cloud.

    20ft radius sphere of heavily obscured noxious gas.
    Turn start: CON save or spend action retching.
    """
    name: str = Field(default="Stinking Cloud Zone", description="Display name for the stinking cloud zone zone condition.")
    description: str = Field(default="Nauseating gas - CON save or spend action", description="Rules-facing summary for the stinking cloud zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the stinking cloud zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by stinking cloud zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by stinking cloud zone.")
    adds_difficult_terrain: bool = Field(default=False, description="Whether stinking cloud zone makes affected tiles difficult terrain.")

    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.DARKNESS, description="Light level applied to affected tiles by stinking cloud zone.")
    light_is_obscurement: bool = Field(default=True, description="Whether stinking cloud zone blocks sight through its light level.")

    marker_name: Optional[str] = Field(default="Stinking Cloud", description="Visible tile marker name created by stinking cloud zone.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ENEMIES, description="Creature relationship filter used for stinking cloud zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by stinking cloud zone saving throws.")

    _wind_dispersal_rounds_remaining: Optional[int] = PrivateAttr(default=None)

    def _has_entry_effect(self) -> bool:
        return False

    def _has_turn_start_effect(self) -> bool:
        return True

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """CON save at turn start or become Nauseated."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            if entity.senses.position not in zone_condition.affected_positions:
                return None

            if "Nauseated" in entity.active_conditions:
                return None
            if not entity.requires_breathing:
                return None
            if entity.health.get_resistance(DamageType.POISON) == ResistanceStatus.IMMUNITY:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="constitution",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:
                nauseated = NauseatedCondition(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=entity.uuid,
                    tags={ConditionTag.MAGICAL}
                )
                entity.add_condition(nauseated, parent_event=event)

            return None

        return EventHandler(
            name="Stinking Cloud Turn Start",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_wind_exposure_handler(self) -> EventHandler:
        """Create handler that starts wind-based gas dispersal countdowns."""
        source_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, WindExposureEvent):
                return None
            dispersal_rounds = event.gas_dispersal_rounds()
            if dispersal_rounds is None:
                return None
            if not zone_condition.affected_positions.intersection(event.positions):
                return None

            current = zone_condition._wind_dispersal_rounds_remaining
            if current is None:
                zone_condition._wind_dispersal_rounds_remaining = dispersal_rounds
            else:
                zone_condition._wind_dispersal_rounds_remaining = min(current, dispersal_rounds)
            return None

        return EventHandler(
            name="Stinking Cloud Wind Exposure",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.WIND_EXPOSURE,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )

    def _create_wind_dispersal_countdown_handler(self) -> EventHandler:
        """Create handler that disperses the cloud after enough windy rounds."""
        source_uuid = self.source_entity_uuid
        condition_uuid = self.uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if source_uuid is None:
                return None
            if event.event_type != EventType.TURN_START:
                return None
            if event.source_entity_uuid != source_uuid:
                return None
            if zone_condition._wind_dispersal_rounds_remaining is None:
                return None

            zone_condition._wind_dispersal_rounds_remaining -= 1
            if zone_condition._wind_dispersal_rounds_remaining > 0:
                return None

            caster = Entity.get(source_uuid)
            if caster is not None:
                caster.remove_condition_by_uuid(condition_uuid, parent_event=event)
            return None

        return EventHandler(
            name="Stinking Cloud Wind Dispersal",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=source_uuid,
            )],
            event_processor=processor,
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Stinking Cloud and register wind dispersal handlers."""
        terrain_modifiers, handler_uuids, sub_condition_uuids, spatial_handler_uuids, effect_event = super()._apply(declaration_event)

        wind_handler = self._create_wind_exposure_handler()
        EventQueue.add_event_handler(wind_handler)
        handler_uuids.append(wind_handler.uuid)

        countdown_handler = self._create_wind_dispersal_countdown_handler()
        EventQueue.add_event_handler(countdown_handler)
        handler_uuids.append(countdown_handler.uuid)

        return terrain_modifiers, handler_uuids, sub_condition_uuids, spatial_handler_uuids, effect_event


class StinkingCloud(SpellAction):
    """Stinking Cloud - 3rd level Conjuration (Concentration)

    You create a 20-foot-radius sphere of yellow, nauseating gas.
    The cloud is heavily obscured. Each creature that starts its turn
    in the cloud must succeed on a CON save or spend its action retching.

    Duration: Concentration, up to 1 minute
    """
    name: str = Field(default="Stinking Cloud", description="Display name for the stinking cloud spell.")
    description: str = Field(default="20ft sphere nauseating fog, CON save or spend action", description="Rules-facing summary for the stinking cloud spell.")
    spell_level: int = Field(default=3, description="Spell slot level required to cast stinking cloud; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify stinking cloud.")
    concentration: bool = Field(default=True, description="Whether stinking cloud creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for stinking cloud.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for stinking cloud targeting.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=90),
        description="Range contract used when validating targets for stinking cloud.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Stinking Cloud Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute stinking cloud.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position")
        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")
        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Position out of range ({distance}ft)")
        return declaration_event.phase_to(new_phase=EventPhase.EXECUTION, status_message=f"Validated {self.name}")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution", save_dc=dc,
            status_message=f"{caster.name} casts Stinking Cloud at {target_pos}"
        )

        zone = StinkingCloudZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Stinking Cloud active: 20ft sphere at {target_pos}"
        )


class SleetStormZone(ZoneControlCondition):
    """Zone control for Sleet Storm.

    40ft radius cylinder: difficult terrain, heavily obscured.
    Entry + turn start: DEX save or Prone.
    Turn start: concentration disruption against spell save DC.
    """
    name: str = Field(default="Sleet Storm Zone", description="Display name for the sleet storm zone zone condition.")
    description: str = Field(default="Icy sleet - DEX save or prone, concentration disruption", description="Rules-facing summary for the sleet storm zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the sleet storm zone for cleanup and filtering.")

    zone_shape: str = Field(default="cylinder", description="Area shape used by sleet storm zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=40, description="Zone radius in feet used by sleet storm zone.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether sleet storm zone makes affected tiles difficult terrain.")

    sets_light_level: Optional[LightLevel] = Field(default=LightLevel.DARKNESS, description="Light level applied to affected tiles by sleet storm zone.")
    light_is_obscurement: bool = Field(default=True, description="Whether sleet storm zone blocks sight through its light level.")

    marker_name: Optional[str] = Field(default="Sleet Storm", description="Visible tile marker name created by sleet storm zone.")
    marker_hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ENEMIES, description="Creature relationship filter used for sleet storm zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by sleet storm zone saving throws.")

    def _has_entry_effect(self) -> bool:
        return True

    def _has_turn_start_effect(self) -> bool:
        return True

    def _douse_item_if_exposed(
        self,
        item: BaseItem,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Douse one exposed-flame item if it is burning.

        Args:
            item: Item to inspect.
            parent_event: Optional parent event for light-removal lineage.

        Returns:
            True when the item was an exposed flame and was doused.
        """
        parent_uuid = parent_event.uuid if parent_event is not None else None
        return item.douse_exposed_flame(parent_event=parent_uuid)

    def _entity_carried_items(self, entity: Entity) -> List[BaseItem]:
        """Return items carried or equipped by an entity."""
        items: List[BaseItem] = []
        items.extend(entity.inventory.items.values())
        items.extend(entity.equipment.get_all_equipped_items())
        return items

    def _douse_exposed_flames_at(
        self,
        position: Tuple[int, int],
        parent_event: Optional[Event] = None,
    ) -> int:
        """Douse exposed flames at one affected position.

        Args:
            position: Grid position to inspect.
            parent_event: Optional parent event for light-removal lineage.

        Returns:
            Number of exposed-flame items doused.
        """
        if position not in self.affected_positions:
            return 0

        grid = get_map()
        doused = 0
        for object_uuid in grid.get_objects_at(position):
            block = BaseBlock.get(object_uuid)
            if isinstance(block, BaseItem) and self._douse_item_if_exposed(block, parent_event):
                doused += 1

        for entity_uuid in grid.get_entities_at(position):
            entity = Entity.get(entity_uuid)
            if entity is None:
                continue
            for item in self._entity_carried_items(entity):
                if self._douse_item_if_exposed(item, parent_event):
                    doused += 1

        return doused

    def douse_exposed_flames(self, parent_event: Optional[Event] = None) -> int:
        """Douse all exposed flames currently inside the storm.

        Args:
            parent_event: Optional parent event for light-removal lineage.

        Returns:
            Number of exposed-flame items doused.
        """
        total = 0
        for position in list(self.affected_positions):
            total += self._douse_exposed_flames_at(position, parent_event)
        return total

    def _create_exposed_flame_handler(self) -> EventHandler:
        """Create a handler that douses flames ignited inside the storm."""
        source_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, ExposedFlameEvent):
                return None
            if event.position not in zone_condition.affected_positions:
                return None

            item = BaseBlock.get(event.item_uuid)
            if isinstance(item, BaseItem):
                zone_condition._douse_item_if_exposed(item, event)
            return None

        return EventHandler(
            name="Sleet Storm Douse Exposed Flame",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.EXPOSED_FLAME_IGNITED,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )

    def _create_zone_entry_handler(self) -> EventHandler:
        """DEX save or fall Prone on entry."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            zone_condition._douse_exposed_flames_at(event.position, event)
            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity", dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)
            if not success:
                prone = Prone(source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid, tags={ConditionTag.MAGICAL})
                entity.add_condition(prone, parent_event=event)
            return None

        return EventHandler(
            name="Sleet Storm Entry Save",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        """Turn start: DEX save or Prone + concentration disruption."""
        source_uuid = self.source_entity_uuid
        dc = self.spell_dc
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            if entity.senses.position not in zone_condition.affected_positions:
                return None

            zone_condition._douse_exposed_flames_at(entity.senses.position, event)

            if "Prone" not in entity.active_conditions:
                save_request = entity.create_saving_throw_request(
                    target_entity_uuid=entity.uuid,
                    ability_name="dexterity", dc=dc,
                    parent_event=event.uuid
                )
                _, _, success = entity.saving_throw(save_request)
                if not success:
                    prone = Prone(source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid, tags={ConditionTag.MAGICAL})
                    entity.add_condition(prone, parent_event=event)

            if "Concentrating" in entity.active_conditions:
                save_request = entity.create_saving_throw_request(
                    target_entity_uuid=entity.uuid,
                    ability_name="constitution", dc=dc,
                    parent_event=event.uuid
                )
                _, _, success = entity.saving_throw(save_request)
                if not success:
                    entity.remove_condition("Concentrating", parent_event=event)

            return None

        return EventHandler(
            name="Sleet Storm Turn Start",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EXECUTION
            )],
            event_processor=processor
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply Sleet Storm zone state and register exposed-flame dousing."""
        terrain_modifiers, handler_uuids, sub_condition_uuids, spatial_handler_uuids, effect_event = super()._apply(declaration_event)

        flame_handler = self._create_exposed_flame_handler()
        EventQueue.add_event_handler(flame_handler)
        handler_uuids.append(flame_handler.uuid)
        self.douse_exposed_flames(parent_event=effect_event)

        return terrain_modifiers, handler_uuids, sub_condition_uuids, spatial_handler_uuids, effect_event


class SleetStorm(SpellAction):
    """Sleet Storm - 3rd level Conjuration (Concentration)

    Until the spell ends, freezing rain and sleet fall in a 40-foot-radius,
    20-foot-high cylinder centered on a point you choose within range.
    The area is heavily obscured, difficult terrain, and creatures entering
    or starting turn there must DEX save or fall prone. Concentrating
    creatures must CON save or lose concentration. Exposed carried or placed
    flames in the area are doused.

    Duration: Concentration, up to 1 minute
    """
    name: str = Field(default="Sleet Storm", description="Display name for the sleet storm spell.")
    description: str = Field(default="40ft cylinder: difficult terrain, heavily obscured, DEX save/prone, conc disruption", description="Rules-facing summary for the sleet storm spell.")
    spell_level: int = Field(default=3, description="Spell slot level required to cast sleet storm; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify sleet storm.")
    concentration: bool = Field(default=True, description="Whether sleet storm creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for sleet storm.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
        description="Subjective visible-cell prerequisites for sleet storm targeting.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=150),
        description="Range contract used when validating targets for sleet storm.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Sleet Storm Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute sleet storm.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position")
        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")
        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Position out of range ({distance}ft)")
        return declaration_event.phase_to(new_phase=EventPhase.EXECUTION, status_message=f"Validated {self.name}")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity", save_dc=dc,
            status_message=f"{caster.name} casts Sleet Storm at {target_pos}"
        )

        zone = SleetStormZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=target_pos,
            spell_dc=dc,
            effect_origin=execution_event.to_effect_origin(),
        )
        caster.add_condition(zone, parent_event=effect_event)
        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        grid = get_map()
        for pos in zone.affected_positions:
            entity_uuids = grid.get_entities_at(pos)
            for ent_uuid in entity_uuids:
                ent = Entity.get(ent_uuid)
                if not ent or ent.uuid == caster.uuid:
                    continue
                save_request = caster.create_saving_throw_request(
                    target_entity_uuid=ent.uuid,
                    ability_name="dexterity", dc=dc,
                    parent_event=effect_event.uuid
                )
                _, _, success = ent.saving_throw(save_request)
                if not success:
                    prone = Prone(source_entity_uuid=caster.uuid, target_entity_uuid=ent.uuid, tags={ConditionTag.MAGICAL})
                    ent.add_condition(prone, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Sleet Storm active: 40ft cylinder at {target_pos}"
        )


class DimensionDoor(SpellAction):
    """Dimension Door - 4th level Conjuration

    You teleport yourself to any spot you can see within 500 feet.
    Simplified: direct teleport without portal objects.

    Duration: Instantaneous
    """
    name: str = Field(default="Dimension Door", description="Display name for the dimension door spell.")
    description: str = Field(default="Teleport to a visible position within 500ft", description="Rules-facing summary for the dimension door spell.")
    spell_level: int = Field(default=4, description="Spell slot level required to cast dimension door; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify dimension door.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for dimension door.")
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=lambda: PositionDiscoveryContract(
            requires_subjective_walkable=True,
            requires_subjective_unoccupied=True,
        ),
        description="Subjective destination prerequisites for dimension door.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=500),
        description="Range contract used when validating targets for dimension door.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Dimension Door Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute dimension door.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if not target_pos:
            return declaration_event.cancel(status_message="No target position")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.senses.get_feet_distance(target_pos)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Position out of range ({distance}ft)")

        grid = get_map()
        if not grid.is_walkable(target_pos[0], target_pos[1]):
            return declaration_event.cancel(status_message=f"Position {target_pos} not walkable")

        entities_at = grid.get_entities_at(target_pos)
        if entities_at and any(e != caster.uuid for e in entities_at):
            return declaration_event.cancel(status_message=f"Position {target_pos} is occupied")

        return declaration_event.phase_to(new_phase=EventPhase.EXECUTION, status_message=f"Validated {self.name}")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if not target_pos:
            return execution_event.cancel(status_message="No target position")

        old_pos = caster.senses.position

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} teleports from {old_pos} to {target_pos}"
        )

        Entity.update_entity_position(caster, target_pos)
        caster.update_entity_senses()

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} teleports to {target_pos}"
        )


class GuardianWarded(BaseCondition):
    """Marker condition — entity has already been affected by Guardian of Faith this turn.
    Removed at start of each turn.
    """
    name: str = Field(default="Guardian Warded", description="Display name for the guardian warded condition.")
    description: str = Field(default="Already triggered Guardian of Faith this turn", description="Rules-facing summary for the guardian warded condition.")
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        description="Internal once-per-turn marker category.",
    )
    guardian_uuid: Optional[UUID] = Field(default=None, description="Guardian object UUID associated with guardian warded.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="No target")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler = self._create_cleanup_handler()
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} is warded by Guardian of Faith"
        )
        return [], [handler.uuid], [], [], effect_event

    def _create_cleanup_handler(self) -> EventHandler:
        """Remove this marker at the start of the entity's turn."""
        assert self.target_entity_uuid is not None
        target_uuid = self.target_entity_uuid
        condition_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != target_uuid:
                return None
            target = Entity.get(target_uuid)
            if not target:
                return None
            if "Guardian Warded" in target.active_conditions:
                active = target.active_conditions.get("Guardian Warded")
                if active and active.uuid == condition_uuid:
                    target.remove_condition("Guardian Warded", parent_event=event)
            return None

        return EventHandler(
            name=f"Guardian Warded Cleanup ({target_uuid})",
            source_entity_uuid=target_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target_uuid
            )],
            event_processor=processor
        )


class GuardianOfFaithObject(BaseItem):
    """Spectral guardian placed on the grid. Blocks movement at its tile.

    Has a damage budget of 60. When total damage dealt reaches 60, the
    guardian vanishes (object is destroyed).
    """
    name: str = Field(default="Guardian of Faith", description="Display name for the guardian of faith object item.")
    description: str = Field(default="A large spectral guardian hovers in this space", description="Rules-facing summary for the guardian of faith object item.")
    blocks_movement: bool = Field(default=True, description="Whether guardian of faith object blocks creature movement on the grid.")
    is_pickable: bool = Field(default=False, description="Whether guardian of faith object can be picked up as an item.")

    caster_uuid: Optional[UUID] = Field(default=None, description="Caster UUID used for ownership and effect attribution by guardian of faith object.")
    spell_dc: int = Field(default=0, description="Spell save DC used by guardian of faith object saving throws.")
    damage_budget: int = Field(default=60, description="Total radiant damage guardian of faith object can deal before vanishing.")
    damage_dealt: int = Field(default=0, description="Radiant damage already dealt by guardian of faith object.")
    _aura_handler_uuid: Optional[UUID] = None

    def setup_aura(self, caster_uuid: UUID, spell_dc: int, position: Tuple[int, int]) -> None:
        """Place on grid and register the aura spatial handler."""
        self.caster_uuid = caster_uuid
        self.spell_dc = spell_dc

        self.place_on_grid(position)

        aura_positions: set[Tuple[int, int]] = set()
        for dx in range(-2, 3):
            for dy in range(-2, 3):

                if max(abs(dx), abs(dy)) <= 2:
                    aura_positions.add((position[0] + dx, position[1] + dy))

        handler = self._create_aura_handler(caster_uuid, spell_dc, position)
        EventQueue.add_spatial_handler(
            handler, aura_positions,
            EventType.SPATIAL_ENTITY_ENTERED, EventPhase.EFFECT
        )
        self._aura_handler_uuid = handler.uuid

    def _create_aura_handler(self, caster_uuid: UUID, spell_dc: int, _guardian_pos: Tuple[int, int]) -> EventHandler:
        """Create spatial handler for the guardian's damage aura."""
        guardian_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if not entity:
                return None

            guardian = BaseItem.get(guardian_uuid)
            if not guardian or not isinstance(guardian, GuardianOfFaithObject):
                return None

            caster = Entity.get(caster_uuid)
            if not caster:
                return None
            if entity.is_ally(caster) or entity.uuid == caster_uuid:
                return None

            if "Guardian Warded" in entity.active_conditions:
                return None

            save_request = caster.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name="dexterity",
                dc=spell_dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            damage = 10 if success else 20

            entity.receive_damage(
                amount=damage,
                damage_type=DamageType.RADIANT,
                source_entity_uuid=caster_uuid,
                parent_event=event.uuid
            )

            warded = GuardianWarded(
                source_entity_uuid=caster_uuid,
                target_entity_uuid=entity.uuid,
                guardian_uuid=guardian_uuid
            )
            entity.add_condition(warded, parent_event=event)

            guardian.damage_dealt += damage
            if guardian.damage_dealt >= guardian.damage_budget:
                guardian.destroy_guardian()

            return None

        return EventHandler(
            name=f"Guardian of Faith Aura ({guardian_uuid})",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def destroy_guardian(self) -> None:
        """Remove the guardian and clean up all its resources."""
        grid = get_map()

        if self._aura_handler_uuid:
            EventQueue.remove_spatial_handler(self._aura_handler_uuid)
            self._aura_handler_uuid = None

        grid.remove_object(self.uuid)


class GuardianOfFaith(SpellAction):
    """Guardian of Faith - 4th level Conjuration (NOT concentration)

    A Large spectral guardian appears and hovers for the duration in an
    unoccupied space of your choice that you can see within range. The
    guardian occupies that space and is indistinct except for a gleaming
    sword and shield emblazoned with the symbol of your deity.

    Any creature hostile to you that moves to a space within 10 feet of
    the guardian for the first time on a turn must succeed on a Dexterity
    saving throw. The creature takes 20 radiant damage on a failed save,
    or half as much damage on a successful one. The guardian vanishes when
    it has dealt a total of 60 damage.

    Duration: 8 hours (NOT concentration).
    """
    name: str = Field(default="Guardian of Faith", description="Display name for the guardian of faith spell.")
    description: str = Field(default="Summon spectral guardian: 20 radiant (DEX half), 60 damage budget", description="Rules-facing summary for the guardian of faith spell.")
    spell_level: int = Field(default=4, description="Spell slot level required to cast guardian of faith; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify guardian of faith.")
    spell_damage_type: Optional[DamageType] = Field(default=DamageType.RADIANT, description="Primary damage type for VFX")
    concentration: bool = Field(default=False, description="Whether guardian of faith creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for guardian of faith.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30), description="Range contract used when validating targets for guardian of faith.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not self.end_position:
            return declaration_event.cancel(status_message="No target position")

        grid = get_map()
        pos = self.end_position
        if not grid.is_walkable_for(pos[0], pos[1], caster.uuid):
            return declaration_event.cancel(status_message="Target position is not unoccupied")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        position = self.end_position
        if not position:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} summons a Guardian of Faith"
        )

        guardian = materialize_item_from_installed_runtime(
            GUARDIAN_OF_FAITH_OBJECT_RECIPE,
            caster.uuid,
            origin=ItemRuntimeOrigin.ENCOUNTER_ONLY,
            expected_type=GuardianOfFaithObject,
        )
        guardian.setup_aura(caster.uuid, dc, position)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"A spectral guardian appears at {position} (60 damage budget)"
        )


class HeroesFeastBuff(BaseCondition):
    """Heroes' Feast buff — immunity to poison/frightened, advantage on WIS saves,
    increased max HP.
    """
    name: str = Field(default="Heroes' Feast", description="Display name for the heroes feast buff condition.")
    description: str = Field(default="Immune to poison/frightened, advantage WIS saves, +max HP", description="Rules-facing summary for the heroes feast buff condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the heroes feast buff for cleanup and filtering.")
    hp_bonus: int = Field(default=0, description="Maximum hit point bonus granted by heroes feast buff.")

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        assert self.target_entity_uuid is not None
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        if "Poisoned" in target.active_conditions:
            target.remove_condition("Poisoned", parent_event=declaration_event)
        if "Frightened" in target.active_conditions:
            target.remove_condition("Frightened", parent_event=declaration_event)

        target.add_condition_immunity("Poisoned", immunity_name="Heroes' Feast")
        target.add_condition_immunity("Frightened", immunity_name="Heroes' Feast")

        wis_save = target.saving_throws.get_saving_throw("wisdom")
        wis_adv_uuid = wis_save.bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="Heroes' Feast",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
        )
        outs.append((wis_save.bonus.uuid, wis_adv_uuid))

        if self.hp_bonus > 0:
            hp_mod_uuid = target.health.max_hit_points_bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Heroes' Feast",
                    value=self.hp_bonus,
                    source_entity_uuid=self.source_entity_uuid,
                    target_entity_uuid=self.target_entity_uuid,
                )
            )
            outs.append((target.health.max_hit_points_bonus.uuid, hp_mod_uuid))

        con_mod = target.ability_scores.get_ability("constitution").get_combined_values().normalized_score
        max_hp = target.health.get_max_hit_dices_points(con_mod) + target.health.max_hit_points_bonus.score
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Heroes' Feast buff on {target.name} (+{self.hp_bonus} max HP)",
            resulting_max_hp=max_hp
        )
        return outs, [], [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            con_mod = target.ability_scores.get_ability("constitution").get_combined_values().normalized_score
            max_hp = target.health.get_max_hit_dices_points(con_mod) + target.health.max_hit_points_bonus.score
            return {"resulting_max_hp": max_hp}
        return {}

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up condition immunities."""
        if not self.target_entity_uuid:
            return super()._remove(event)
        target = Entity.get(self.target_entity_uuid)
        if target:
            target._remove_static_condition_immunity("Poisoned", "Heroes' Feast")
            target._remove_static_condition_immunity("Frightened", "Heroes' Feast")
        return super()._remove(event)


@behavior_identity(
    definition_kind=ContentDefinitionKind.ACTION,
    runtime_behavior_kind=RuntimeBehaviorKind.ACTION,
    pack_id="content.srd_5_1_cc",
    content_id="action.environment.heroes_feast.eat",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Eat from Feast",
        description="Consume one serving from a Heroes' Feast.",
        tags=("action", "environment", "spell", "srd"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key="action.environment.heroes_feast.eat",
            visual_variant_key="eat_from_feast",
            vfx_profile="eat_from_feast",
            ui_group="actions.action",
        ),
        ordering=ContentOrdering(
            sort_group="actions.action",
            sort_order=990,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), p. 154, "
            "Spell Descriptions: Heroes' Feast"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Item-bound feast interaction preserved exactly.",
    ),
)
class EatFromFeast(BaseAction):
    """Action to eat from the Heroes' Feast and gain the buff."""
    name: str = Field(default="Eat from Feast", description="Display name for the eat from feast action.")
    description: str = Field(default="Eat from the Heroes' Feast to gain its buff", description="Rules-facing summary for the eat from feast action.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Targeting mode used by action discovery and validation for eat from feast.")
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Action category used when discovering and executing eat from feast.")
    feast_uuid: UUID = Field(description="UUID of the HeroesFeastObject")
    caster_uuid: UUID = Field(description="UUID of the caster who created the feast")
    is_item_use: bool = Field(default=True, description="Whether eat from feast is routed through item-use execution.")

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        feast = BaseItem.get(self.feast_uuid)
        if not feast or not isinstance(feast, HeroesFeastObject):
            return declaration_event.cancel(status_message="Feast no longer available")

        if entity.uuid in feast.consumed_by:
            return declaration_event.cancel(status_message=f"{entity.name} has already eaten from this feast")

        if "Heroes' Feast" in entity.active_conditions:
            return declaration_event.cancel(status_message=f"{entity.name} already has Heroes' Feast buff")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[ActionEvent], parent_result)

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        feast = BaseItem.get(self.feast_uuid)
        if not entity or not feast or not isinstance(feast, HeroesFeastObject):
            return execution_event.cancel(status_message="Entity or feast not found")

        hp_bonus = random.randint(1, 10) + random.randint(1, 10)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{entity.name} eats from the Heroes' Feast"
        )

        buff = HeroesFeastBuff(
            source_entity_uuid=self.caster_uuid,
            target_entity_uuid=entity.uuid,
            hp_bonus=hp_bonus,
        )
        entity.add_condition(buff, parent_event=effect_event)

        feast.consumed_by.add(entity.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{entity.name} gains Heroes' Feast buff (+{hp_bonus} max HP)"
        )


class HeroesFeastObject(UsableItem):
    """A magnificent feast that appears on the ground.
    Creatures can eat from it to gain the Heroes' Feast buff.
    """
    name: str = Field(default="Heroes' Feast", description="Display name for the heroes feast object item.")
    description: str = Field(default="A magnificent feast — eat to gain immunity to poison/frightened and +HP", description="Rules-facing summary for the heroes feast object item.")
    is_pickable: bool = Field(default=False, description="Whether heroes feast object can be picked up as an item.")
    map_char: str = Field(default="F", description="Single-character map glyph used for heroes feast object.")
    consumed_by: Set[UUID] = Field(default_factory=set, description="Entity UUIDs that have already used heroes feast object.")
    caster_uuid: Optional[UUID] = Field(default=None, description="Caster UUID used for ownership and effect attribution by heroes feast object.")

    def get_use_actions(self, user_entity_uuid: UUID) -> List[BaseAction]:
        """Return the EatFromFeast action if the user hasn't eaten yet."""
        if user_entity_uuid in self.consumed_by:
            return []
        if not self.caster_uuid:
            return []
        return [
            self.bind_dynamic_use_action(
                EatFromFeast(
                    source_entity_uuid=user_entity_uuid,
                    feast_uuid=self.uuid,
                    caster_uuid=self.caster_uuid,
                    source_item_uuid=self.uuid,
                ),
            )
        ]


class HeroesFeast(SpellAction):
    """Heroes' Feast — 6th-level conjuration.

    You bring forth a great feast. A feast object appears at the target position.
    Creatures within 5 feet can use an action to eat from it, gaining:
    - Immunity to poison and being frightened
    - Advantage on WIS saves
    - +2d10 max HP
    """
    name: str = Field(default="Heroes' Feast", description="Display name for the heroes feast spell.")
    description: str = Field(default="Summon feast: eat for poison/fear immunity, WIS save advantage, +HP", description="Rules-facing summary for the heroes feast spell.")
    spell_level: int = Field(default=6, description="Spell slot level required to cast heroes feast; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify heroes feast.")
    concentration: bool = Field(default=False, description="Whether heroes feast creates and maintains a concentration condition.")
    target_type: TargetType = Field(default=TargetType.POSITION, description="Targeting mode used by action discovery and validation for heroes feast.")
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30), description="Range contract used when validating targets for heroes feast.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not self.end_position:
            return declaration_event.cancel(status_message="No target position")

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")
        position = self.end_position
        if not position:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} conjures a Heroes' Feast"
        )

        feast = materialize_item_from_installed_runtime(
            HEROES_FEAST_OBJECT_RECIPE,
            caster.uuid,
            origin=ItemRuntimeOrigin.ENCOUNTER_ONLY,
            expected_type=HeroesFeastObject,
        )
        feast.place_on_grid(position)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"A magnificent feast appears at {position}"
        )


class SpellEnvironmentObjectParameters(BaseModel):
    """Spell-created floor objects have no durable construction variants."""

    model_config = ConfigDict(extra="forbid", frozen=True)


_SPELL_ENVIRONMENT_OBJECT_DEFINITION = ItemDefinition(
    persistence_policy=ItemPersistencePolicy.ENCOUNTER_ONLY,
)


def _spell_environment_descriptor(
    *,
    content_id: str,
    display_name: str,
    description: str,
    visual_variant_key: str,
    sort_order: int,
) -> ContentDescriptorSpec:
    """Build public, mechanics-free presentation for a spell-created object."""
    return ContentDescriptorSpec(
        display_name=display_name,
        description=description,
        tags=("environment", "spell", "srd", "summoned"),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=content_id,
            sprite_key=visual_variant_key,
            visual_variant_key=visual_variant_key,
            vfx_profile=content_id,
            ui_group="environment.spell_objects",
        ),
        ordering=ContentOrdering(
            sort_group="environment.spell_objects",
            sort_order=sort_order,
        ),
    )


def _spell_environment_provenance(
    *,
    display_name: str,
    source_page: int,
) -> ContentProvenance:
    """Return reviewed SRD provenance for a spell-created floor object."""
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            f"SRD 5.1 (CC-BY-4.0), p. {source_page}, "
            f"Spell Descriptions: {display_name}"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Encounter-only floor object created by the owning spell; "
            "existing mechanics preserved."
        ),
    )


@environment_object_factory(
    pack_id="content.srd_5_1_cc",
    content_id="environment.spell_object.guardian_of_faith",
    version=1,
    parameters=SpellEnvironmentObjectParameters,
    descriptor=_spell_environment_descriptor(
        content_id="environment.spell_object.guardian_of_faith",
        display_name="Guardian of Faith",
        description="The spectral guardian created by Guardian of Faith.",
        visual_variant_key="guardian_of_faith",
        sort_order=10,
    ),
    provenance=_spell_environment_provenance(
        display_name="Guardian of Faith",
        source_page=150,
    ),
    item_definition=_SPELL_ENVIRONMENT_OBJECT_DEFINITION,
)
def _build_guardian_of_faith_object(
    raw_context: object,
    parameters: SpellEnvironmentObjectParameters,
) -> GuardianOfFaithObject:
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return GuardianOfFaithObject(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
    )


@environment_object_factory(
    pack_id="content.srd_5_1_cc",
    content_id="environment.spell_object.heroes_feast",
    version=1,
    parameters=SpellEnvironmentObjectParameters,
    descriptor=_spell_environment_descriptor(
        content_id="environment.spell_object.heroes_feast",
        display_name="Heroes' Feast",
        description="The magnificent feast created by Heroes' Feast.",
        visual_variant_key="heroes_feast",
        sort_order=20,
    ),
    provenance=_spell_environment_provenance(
        display_name="Heroes' Feast",
        source_page=154,
    ),
    item_definition=_SPELL_ENVIRONMENT_OBJECT_DEFINITION,
    dependencies=(
        ContentDependency(
            relation=ContentDependencyRelation.GRANTS_ACTION,
            target_ref=get_content_declaration(EatFromFeast).ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        ),
    ),
)
def _build_heroes_feast_object(
    raw_context: object,
    parameters: SpellEnvironmentObjectParameters,
) -> HeroesFeastObject:
    _ = parameters
    context = ItemBuildContext.model_validate(raw_context)
    return HeroesFeastObject(
        source_entity_uuid=context.source_entity_uuid,
        content_ref=context.requested_ref,
        caster_uuid=context.source_entity_uuid,
    )


GUARDIAN_OF_FAITH_OBJECT_DECLARATION = get_content_declaration(
    _build_guardian_of_faith_object,
)
HEROES_FEAST_OBJECT_DECLARATION = get_content_declaration(
    _build_heroes_feast_object,
)
GUARDIAN_OF_FAITH_OBJECT_REF = GUARDIAN_OF_FAITH_OBJECT_DECLARATION.ref
HEROES_FEAST_OBJECT_REF = HEROES_FEAST_OBJECT_DECLARATION.ref
GUARDIAN_OF_FAITH_OBJECT_RECIPE = ContentRecipe.create(
    ref=GUARDIAN_OF_FAITH_OBJECT_REF,
    parameters={},
)
HEROES_FEAST_OBJECT_RECIPE = ContentRecipe.create(
    ref=HEROES_FEAST_OBJECT_REF,
    parameters={},
)
SRD_SPELL_ENVIRONMENT_OBJECT_DECLARATIONS: tuple[
    ContentDeclaration,
    ...,
] = (
    GUARDIAN_OF_FAITH_OBJECT_DECLARATION,
    HEROES_FEAST_OBJECT_DECLARATION,
)
