"""Conjuration spells - creating objects and summoning creatures.

Contains: CallLightning, PoisonSpray, AcidSplash, Grease, Web, Cloudkill,
          SpiritGuardians, FogCloud, Darkness, Daylight, InsectPlague, IncendiaryCloud
"""
from typing import Any, Dict, Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.core.base_actions import (
    ActionCategory,
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
    Cost,
    InformationEffectProfile,
    OutcomeResolution,
    PositionDiscoveryContract,
    TargetEffectDisposition,
    TargetType,
    TopologyEffectProfile,
)
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.base_conditions import BaseCondition, Duration, MostPotentCondition
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
from dnd.types.behaviors import RuntimeBehaviorKind
from dnd.types.conditions import (
    ConditionCategory,
    ConditionTag,
    DurationType,
    HazardFilter,
)
from dnd.blocks.base_item import (
    BaseItem,
    UsableItem,
)
import random
from dnd.types.rolls import AttackOutcome
from dnd.core.values import ModifiableValue
from dnd.types.abilities import AbilityName
from dnd.core.events.events_registry import (
    EventPhase,
    EventType,
    EventHandler,
    Trigger,
    Event,
    EventQueue,
)
from dnd.core.events.resolution_events import (
    RangeType,
    Range,
    Damage,
)
from dnd.core.events.world_events import (
    SpatialChangeEvent,
    SpatialEffectInteractionEvent,
)
from dnd.types.spatial_effects import (
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
    SpatialEffectLayer,
    SpatialEffectTriggerKind,
)
from dnd.types.damage import DamageType
from dnd.core.modifiers import NumericalModifier, AdvantageModifier
from dnd.types.rolls import AdvantageStatus
from dnd.types.damage import ResistanceStatus
from dnd.types.saving_throws import SavingThrowEffectTag
from dnd.types.senses import OpticalObscurement
from dnd.core.base_block import BaseBlock
from dnd.types.world import LightLevel
from dnd.core.gridmap import get_map
from dnd.types.items import ItemLocation
from dnd.entities.entity import Entity
from dnd.conditions import Concentrating, ConcentrationActionMarker, Prone
from dnd.actions.standard import (
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
)
from dnd.spells.content_metadata import srd_action_identity
from dnd.content.spatial_effect_recipes import (
    CLOUDKILL_CLOUD_RECIPE,
    DARKNESS_FIELD_RECIPE,
    DAYLIGHT_FIELD_RECIPE,
    ENTANGLE_FIELD_RECIPE,
    EVARDS_BLACK_TENTACLES_FIELD_RECIPE,
    FOG_CLOUD_RECIPE,
    GREASE_SURFACE_RECIPE,
    GUARDIAN_OF_FAITH_FIELD_RECIPE,
    INCENDIARY_CLOUD_RECIPE,
    INSECT_PLAGUE_FIELD_RECIPE,
    SLEET_STORM_FIELD_RECIPE,
    SPIRIT_GUARDIANS_FIELD_RECIPE,
    STINKING_CLOUD_RECIPE,
    WEB_SURFACE_RECIPE,
)
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.memberships import (
    SpatialConditionMembershipSource,
    MembershipAreaCondition,
)
from dnd.spatial.restraints import (
    EscapeSpatialRestraintAction,
    RestrainingAreaCondition,
    SpatialRestraintSource,
)


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

        contact = caster.senses.entities.get(target.uuid)
        if contact is None or not contact.visual:
            return declaration_event.cancel(status_message="Target not in line of sight")

        distance = caster.distance_to_entity(target)
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
            ability_name=AbilityName.DEXTERITY,
            dc=self.spell_dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"DEX save: {save_roll.total} vs DC {self.spell_dc} - {'Success' if success else 'Failure'}"
        )
        if effect_event.canceled:
            return effect_event

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
        return self._validate_entity_target_in_range_and_sight(
            declaration_event,
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
        if effect_event.canceled:
            return effect_event

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.DEXTERITY,
            dc=dc,
            parent_event=effect_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        effect_event = effect_event.with_updates(
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

        concentration = self.ensure_concentration(effect_event)
        marker = ConcentrationActionMarker(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            action_name=strike_action.name
        )
        caster.register_condition_action(marker, strike_action)
        caster.add_condition(marker, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, marker.uuid)

        self._close_concentration(effect_event)

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
    saving_throw_effect_tags: Tuple[SavingThrowEffectTag, ...] = Field(
        default=(SavingThrowEffectTag.POISON,),
        description="Exact origin-rule semantics carried by Poison Spray saves.",
    )

    include_self: bool = Field(default=False, description="Whether poison spray can include the caster among valid targets.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter used when collecting valid targets for poison spray.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate LOS and 10ft range."""
        return self._validate_entity_target_in_range_and_sight(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """CON save or poison damage."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Entity not found")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.CONSTITUTION,
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

            contact = source.senses.entities.get(target_uuid)
            if contact is None or not contact.visual:
                return declaration_event.cancel(status_message=f"{target.name} not in line of sight")

            distance = source.distance_to_entity(target)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"{target.name} out of range ({distance}ft > {self.effective_range}ft)"
                )
            target_entities.append(target)

        if len(target_entities) == 2:
            t1, t2 = target_entities
            target_distance = t1.distance_to_entity(t2)
            if target_distance > 5:
                return declaration_event.cancel(
                    status_message=(
                        "Targets must be within 5ft of each other "
                        f"(distance: {target_distance}ft)"
                    )
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
            ability_name=AbilityName.DEXTERITY,
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, AbilityName.DEXTERITY).normalized_score

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
        if effect_event.canceled:
            return effect_event

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
        if target_pos is None:
            return declaration_event.cancel(status_message="No destination specified")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Destination {target_pos} not visible")

        distance = caster.distance_to_position(target_pos)
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
        if target_pos is None:
            return execution_event.cancel(status_message="No destination")

        start_pos = caster.senses.position

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} teleports from {start_pos} to {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        Entity.update_entity_position(caster, target_pos)

        distance = abs(target_pos[0] - start_pos[0]) * 5 + abs(target_pos[1] - start_pos[1]) * 5

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            start_position=start_pos,
            end_position=target_pos,
            distance_feet=distance,
            status_message=f"{caster.name} teleports {distance}ft via Misty Step"
        )


class GreaseZone(AreaCondition):
    """Zone control condition for Grease spell.

    Creates a 10ft square of difficult terrain. Creatures entering or
    ending their turn in the area must make a DEX save or fall prone.

    Independently owns the zone through position-indexed handlers.
    """
    name: str = Field(default="Grease Zone", description="Display name for the grease zone zone condition.")
    description: str = Field(default="Slippery grease - DEX save or fall prone", description="Rules-facing summary for the grease zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the grease zone for cleanup and filtering.")

    zone_shape: str = Field(default="cube", description="Area shape used by grease zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=10, description="Zone radius in feet used by grease zone.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether grease zone makes affected tiles difficult terrain.")

    hazard_filter: Optional[HazardFilter] = Field(
        default=HazardFilter.ALL,
        description="Every creature treats an observed grease surface as hazardous.",
    )
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=10,
            duration_type=DurationType.ROUNDS,
        ),
        description="Grease persists independently for one minute.",
    )

    spell_dc: int = Field(default=10, description="Spell save DC used by grease zone saving throws.")

    def _apply_prone_save(
        self,
        entity: Entity,
        *,
        parent_event: Event,
        suppress_immediate_stand: bool = False,
    ) -> None:
        save_request = entity.create_saving_throw_request(
            target_entity_uuid=entity.uuid,
            ability_name=AbilityName.DEXTERITY,
            dc=self.spell_dc,
            parent_event=parent_event.uuid,
        )
        _, _, success = entity.saving_throw(save_request)
        if success:
            return
        prone = Prone(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            tags={ConditionTag.MAGICAL},
        )
        if suppress_immediate_stand:
            prone.suppress_immediate_stand_for_application()
        entity.add_condition(prone, parent_event=parent_event)

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Resolve Grease's explicit when-the-surface-appears save."""
        self._apply_prone_save(entity, parent_event=parent_event)

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - DEX save or fall prone."""
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            entity = Entity.get(event.entity_uuid)
            if entity is not None:
                condition._apply_prone_save(entity, parent_event=event)
            return None

        return EventHandler(
            name="Grease Entry Save",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_end_handler(self) -> EventHandler:
        """Create handler for turn end in zone - DEX save or fall prone."""
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:

            if event.event_type != EventType.TURN_END:
                return None

            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if not entity:
                return None

            if entity.senses.position not in condition.affected_positions:
                return None

            if "Prone" in entity.active_conditions:
                return None
            condition._apply_prone_save(
                entity,
                parent_event=event,
                suppress_immediate_stand=True,
            )
            return None

        return EventHandler(
            name="Grease Turn End Save",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
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

    Duration: 1 minute, independently timed.
    """
    name: str = Field(default="Grease", description="Display name for the grease spell.")
    description: str = Field(default="10ft square difficult terrain, DEX save or prone", description="Rules-facing summary for the grease spell.")
    spell_level: int = Field(default=1, description="Spell slot level required to cast grease; cantrips use 0.")
    spell_school: str = Field(default="conjuration", description="D&D school of magic used to classify grease.")
    concentration: bool = Field(default=False, description="Grease persists without concentration.")
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
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Grease and create an independently owned ground effect."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=f"{caster.name} casts Grease at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            GREASE_SURFACE_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=GreaseZone,
            condition_fields={
                "spell_dc": dc,
                "arbitration_potency": dc,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Grease field could not be established",
            )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Grease active: 10ft square at {target_pos}",
        )


class EscapeWebAction(EscapeSpatialRestraintAction):
    """Strength-check action against one exact Web restraint source."""

    name: str = Field(default="Escape Web")
    description: str = Field(
        default="Use an action to make a Strength check against the Web DC.",
    )
    ability_name: AbilityName = Field(default=AbilityName.STRENGTH, frozen=True)


class WebRestrained(SpatialRestraintSource):
    """Independent Web membership owning restraint and its escape option."""

    description: str = Field(
        default="Restrained by one exact Web effect until leaving or escaping.",
    )
    escape_action_types = (EscapeWebAction,)

class WebZone(RestrainingAreaCondition):
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

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for web zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by web zone saving throws.")
    anchored_or_layered: bool = Field(
        default=True,
        description="Whether the webs are anchored or layered across a surface and persist past the caster's next turn start.",
    )
    restraint_source_type = WebRestrained

    def restraint_check_dc(self) -> int:
        """Use the exact casting DC for Web escape checks."""
        return self.spell_dc

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

            if self.find_restraint(entity) is not None:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name=AbilityName.DEXTERITY,
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:

                self.apply_restraint(entity, parent_event=event)

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

    def _create_zone_exit_handler(self) -> EventHandler:
        """Release only this Web source when a creature leaves its footprint."""
        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            if event.entity_uuid is None:
                return None
            entity = Entity.get(event.entity_uuid)
            if entity is not None:
                self.remove_restraint(entity, parent_event=event)
            return None

        return EventHandler(
            name="Web Exit Release",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
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

            if self.find_restraint(entity) is not None:
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name=AbilityName.DEXTERITY,
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = entity.saving_throw(save_request)

            if not success:
                self.apply_restraint(entity, parent_event=event)

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

    def _remove_web_restrained_at(
        self,
        positions: Set[Tuple[int, int]],
        parent_event: Optional[Event],
    ) -> None:
        """Remove only this Web owner's restraints from removed cells."""
        grid = get_map()
        for position in positions:
            for entity_uuid in grid.get_entities_at(position):
                entity = Entity.get(entity_uuid)
                if entity is None:
                    continue
                membership = self.find_restraint(entity)
                if membership is not None:
                    self.remove_restraint(
                        entity,
                        parent_event=parent_event,
                    )

    def _release_positions(self, positions: Set[Tuple[int, int]]) -> None:
        """Release creatures in cubes removed by a material transition."""
        self._remove_web_restrained_at(positions, None)
        super()._release_positions(positions)

    def _create_unanchored_collapse_handler(self) -> EventHandler:
        """Create a handler that ends unanchored webs on the caster's next turn."""
        source_uuid = self.source_entity_uuid
        condition_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_START:
                return None
            if event.source_entity_uuid != source_uuid:
                return None

            condition = BaseCondition.get(condition_uuid)
            if isinstance(condition, WebZone):
                condition.deactivate(parent_event=event)
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
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Web and link its independently owned surface to concentration."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=f"{caster.name} casts Web at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            WEB_SURFACE_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=WebZone,
            condition_fields={
                "spell_dc": dc,
                "arbitration_potency": dc,
                "anchored_or_layered": self.anchored_or_layered,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Web field could not be established",
            )

        concentration = self.ensure_concentration(effect_event)

        concentration.add_linked_condition(zone.uuid, zone.uuid)

        self._close_concentration(effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Web active: 20ft cube at {target_pos}",
        )


class EscapeEntangleAction(EscapeSpatialRestraintAction):
    """Strength-check action against one exact Entangle source."""

    name: str = Field(default="Escape Entangle")
    description: str = Field(
        default="Use an action to make a Strength check against the Entangle DC.",
    )
    ability_name: AbilityName = Field(default=AbilityName.STRENGTH, frozen=True)


class EntangleRestrained(SpatialRestraintSource):
    """Independent Entangle restraint source."""

    description: str = Field(
        default="Restrained by one exact Entangle field until escaping.",
    )
    escape_action_types = (EscapeEntangleAction,)


class EntangleZone(RestrainingAreaCondition):
    """Fixed Entangle field with cast-time saves and difficult terrain."""

    name: str = Field(default="Entangle Zone")
    description: str = Field(
        default="Grasping plants create difficult terrain and restrain on a failed Strength save.",
    )
    zone_shape: str = Field(default="cube")
    zone_radius_feet: int = Field(default=20)
    adds_difficult_terrain: bool = Field(default=True)
    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL)
    spell_dc: int = Field(default=10, ge=0)
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=10,
            duration_type=DurationType.ROUNDS,
        ),
    )
    restraint_source_type = EntangleRestrained

    def restraint_check_dc(self) -> int:
        return self.spell_dc

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        save_request = entity.create_saving_throw_request(
            target_entity_uuid=entity.uuid,
            ability_name=AbilityName.STRENGTH,
            dc=self.spell_dc,
            parent_event=parent_event.uuid,
            saving_throw_context=self.saving_throw_context(
                effect_id="condition.spell.entangle.restrained",
            ),
        )
        _, _, success = entity.saving_throw(save_request)
        if not success:
            self.apply_restraint(entity, parent_event=parent_event)


class Entangle(SpellAction):
    """Entangle — 1st-level concentration field."""

    name: str = Field(default="Entangle")
    description: str = Field(
        default="Create a 20-foot square of difficult terrain; creatures there make a Strength save or become restrained.",
    )
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="conjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION)
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=90),
    )
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Entangle Cost",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            ),
        ],
    )

    def get_target_effect_profile(
        self,
        actor: Any,
    ) -> Optional[ActionTargetEffectProfile]:
        if not isinstance(actor, Entity):
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.entangle",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.entangle.restrained",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(
                        spellcasting_source_id=self.spellcasting_source_id,
                    ),
                    save_ability="strength",
                    condition_fact_ids=(
                        "affected_entity.condition.restrained",
                    ),
                    condition_semantic_keys=frozenset({
                        "dnd.conditions.Restrained",
                    }),
                ),
            ),
        )

    def _validate(
        self,
        declaration_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return execution_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")
        dc = caster.spell_save_dc(
            spellcasting_source_id=self.spellcasting_source_id,
        )
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            save_ability="strength",
            save_dc=dc,
            status_message=f"{caster.name} casts Entangle at {target_pos}",
        )
        if effect_event.canceled:
            return effect_event
        zone = materialize_spatial_condition(
            ENTANGLE_FIELD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=EntangleZone,
            condition_fields={
                "spell_dc": dc,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Entangle field could not be established",
            )
        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)
        self._close_concentration(effect_event)
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Entangle active at {target_pos}",
        )


class EscapeBlackTentaclesStrengthAction(EscapeSpatialRestraintAction):
    """Strength escape option against one Black Tentacles source."""

    name: str = Field(default="Escape Black Tentacles (Strength)")
    description: str = Field(
        default="Use an action to make a Strength check against the spell DC.",
    )
    ability_name: AbilityName = Field(default=AbilityName.STRENGTH, frozen=True)


class EscapeBlackTentaclesDexterityAction(EscapeSpatialRestraintAction):
    """Dexterity escape option against one Black Tentacles source."""

    name: str = Field(default="Escape Black Tentacles (Dexterity)")
    description: str = Field(
        default="Use an action to make a Dexterity check against the spell DC.",
    )
    ability_name: AbilityName = Field(default=AbilityName.DEXTERITY, frozen=True)


class BlackTentaclesRestrained(SpatialRestraintSource):
    """Independent Black Tentacles restraint source and both escape options."""

    description: str = Field(
        default="Restrained by one exact Evard's Black Tentacles field.",
    )
    escape_action_types = (
        EscapeBlackTentaclesStrengthAction,
        EscapeBlackTentaclesDexterityAction,
    )


class BlackTentaclesZone(RestrainingAreaCondition):
    """Damaging and restraining field for Evard's Black Tentacles."""

    name: str = Field(default="Evard's Black Tentacles Zone")
    description: str = Field(
        default="Writhing tentacles create difficult terrain, bludgeon, and restrain.",
    )
    zone_shape: str = Field(default="cube")
    zone_radius_feet: int = Field(default=20)
    adds_difficult_terrain: bool = Field(default=True)
    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL)
    spell_dc: int = Field(default=10, ge=0)
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=10,
            duration_type=DurationType.ROUNDS,
        ),
    )
    restraint_source_type = BlackTentaclesRestrained

    def restraint_check_dc(self) -> int:
        return self.spell_dc

    def _deal_tentacle_damage(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> int:
        caster = Entity.get(self.source_entity_uuid)
        damage_bonus = (
            caster.get_spell_damage_bonus()
            if caster is not None
            else ModifiableValue.create(
                source_entity_uuid=self.source_entity_uuid,
                base_value=0,
                value_name="Spell Damage",
            )
        )
        damage = Damage(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=6,
            dice_numbers=3,
            damage_bonus=damage_bonus,
            damage_type=DamageType.BLUDGEONING,
        )
        roll = damage.get_dice(attack_outcome=AttackOutcome.HIT).roll
        return entity.receive_damage(
            roll.total,
            DamageType.BLUDGEONING,
            self.source_entity_uuid,
            damage_rolls=[roll],
            damages=[damage],
            parent_event=parent_event.uuid,
            effect_id="spell.evards_black_tentacles.damage",
        )

    def _save_or_apply(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        request = entity.create_saving_throw_request(
            target_entity_uuid=entity.uuid,
            ability_name=AbilityName.DEXTERITY,
            dc=self.spell_dc,
            parent_event=parent_event.uuid,
            saving_throw_context=self.saving_throw_context(
                effect_id="spell.evards_black_tentacles.initial",
            ),
        )
        _, _, success = entity.saving_throw(request)
        if success:
            return
        self._deal_tentacle_damage(entity, parent_event=parent_event)
        self.apply_restraint(entity, parent_event=parent_event)

    def _create_zone_entry_handler(self) -> EventHandler:
        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            if event.entity_uuid is None:
                return None
            entity = Entity.get(event.entity_uuid)
            if entity is not None:
                self._save_or_apply(entity, parent_event=event)
            return None

        return EventHandler(
            name="Black Tentacles Entry",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )

    def _create_zone_turn_start_handler(self) -> EventHandler:
        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            entity = Entity.get(event.source_entity_uuid)
            if entity is None or entity.position not in self.affected_positions:
                return None
            if self.find_restraint(entity) is not None:
                self._deal_tentacle_damage(entity, parent_event=event)
            else:
                self._save_or_apply(entity, parent_event=event)
            return None

        return EventHandler(
            name="Black Tentacles Turn Start",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )


class EvardsBlackTentacles(SpellAction):
    """Evard's Black Tentacles — 4th-level concentration field."""

    name: str = Field(default="Evard's Black Tentacles")
    description: str = Field(
        default="Create a 20-foot square of difficult terrain that deals 3d6 bludgeoning damage and restrains on a failed Dexterity save.",
    )
    spell_level: int = Field(default=4)
    spell_school: str = Field(default="conjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.POSITION)
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default_factory=PositionDiscoveryContract,
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=90),
    )
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Evard's Black Tentacles Cost",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            ),
        ],
    )

    def get_target_effect_profile(
        self,
        actor: Any,
    ) -> Optional[ActionTargetEffectProfile]:
        if not isinstance(actor, Entity):
            return None
        return ActionTargetEffectProfile(
            semantic_id="control.evards_black_tentacles",
            branches=(
                ActionTargetEffectBranchProfile(
                    effect_id="control.evards_black_tentacles.failed_save",
                    disposition=TargetEffectDisposition.HARMFUL,
                    resolution=OutcomeResolution.SAVING_THROW,
                    save_dc=actor.spell_save_dc(
                        spellcasting_source_id=self.spellcasting_source_id,
                    ),
                    save_ability="dexterity",
                    condition_fact_ids=(
                        "affected_entity.condition.restrained",
                    ),
                    condition_semantic_keys=frozenset({
                        "dnd.conditions.Restrained",
                    }),
                ),
            ),
        )

    def _validate(
        self,
        declaration_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return execution_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")
        dc = caster.spell_save_dc(
            spellcasting_source_id=self.spellcasting_source_id,
        )
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=dc,
            status_message=(
                f"{caster.name} casts Evard's Black Tentacles at {target_pos}"
            ),
        )
        if effect_event.canceled:
            return effect_event
        zone = materialize_spatial_condition(
            EVARDS_BLACK_TENTACLES_FIELD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=BlackTentaclesZone,
            condition_fields={
                "spell_dc": dc,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Black Tentacles field could not be established",
            )
        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)
        self._close_concentration(effect_event)
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Evard's Black Tentacles active at {target_pos}",
        )


class CloudkillZone(AreaCondition):
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

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for cloudkill zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by cloudkill zone saving throws.")
    damage_dice: str = Field(default="5d8", description="Textual damage dice summary for cloudkill zone.")
    upcast_dice: int = Field(default=0, description="Additional damage dice contributed by upcasting cloudkill zone.")

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
                ability_name=AbilityName.CONSTITUTION,
                dc=dc,
                parent_event=event.uuid,
                saving_throw_context=self.saving_throw_context(
                    effect_id="condition.spell.cloudkill.zone.poison_save",
                    effect_tags=(SavingThrowEffectTag.POISON,),
                ),
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
                ability_name=AbilityName.CONSTITUTION,
                dc=dc,
                parent_event=event.uuid,
                saving_throw_context=zone_condition.saving_throw_context(
                    effect_id=(
                        "condition.spell.stinking_cloud.zone.poison_save"
                    ),
                    effect_tags=(SavingThrowEffectTag.POISON,),
                ),
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
            zx, zy = zone_condition.position

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

            zone_condition.move_zone(
                (new_x, new_y),
                parent_event=event,
            )

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
    saving_throw_effect_tags: Tuple[SavingThrowEffectTag, ...] = Field(
        default=(SavingThrowEffectTag.POISON,),
        description="Exact origin-rule semantics carried by Cloudkill saves.",
    )

    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Cloudkill Cost", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)
    ], description="Action economy costs paid to execute cloudkill.")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target position is in range and visible."""
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Cast Cloudkill; occupants are affected only on entry or turn start."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        upcast_bonus = self.get_upcast_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution",
            save_dc=dc,
            status_message=f"{caster.name} casts Cloudkill at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            CLOUDKILL_CLOUD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=CloudkillZone,
            condition_fields={
                "spell_dc": dc,
                "arbitration_potency": dc,
                "upcast_dice": upcast_bonus,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Cloudkill field could not be established",
            )

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        self._close_concentration(effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Cloudkill active: 20ft sphere at {target_pos}",
        )


class SpiritGuardiansSlowed(MostPotentCondition):
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
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        frozen=True,
    )
    potency_rank: Tuple[int, ...] = Field(
        default=(0,),
        min_length=1,
        description="Every live Spirit Guardians source manifests the same halving.",
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


class SpiritGuardiansSlowSource(SpatialConditionMembershipSource):
    """Internal exact aura membership owning the public speed-halving lease."""

    description: str = Field(
        default="Tracks one exact Spirit Guardians aura covering this creature.",
    )

    def create_manifestation(self, target: Entity) -> BaseCondition:
        return SpiritGuardiansSlowed(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            parent_condition=self.uuid,
            potency_rank=(0,),
            tags={ConditionTag.MAGICAL},
        )


class SpiritGuardiansZone(MembershipAreaCondition):
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

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ENEMIES, description="Creature relationship filter used for spirit guardians zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by spirit guardians zone saving throws.")
    damage_dice: str = Field(default="3d8", description="Textual damage dice summary for spirit guardians zone.")
    damage_type: DamageType = Field(default=DamageType.RADIANT, description="Damage type dealt by spirit guardians zone.")
    upcast_dice: int = Field(default=0, description="Additional damage dice contributed by upcasting spirit guardians zone.")

    membership_trigger_kinds: frozenset[
        SpatialEffectTriggerKind
    ] = frozenset({
        SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
        SpatialEffectTriggerKind.ENTER,
        SpatialEffectTriggerKind.TURN_START,
    })

    def membership_source_class(
        self,
    ) -> type[SpatialConditionMembershipSource]:
        return SpiritGuardiansSlowSource

    def membership_applies_to(self, entity: Entity) -> bool:
        """Manifest the slow only on enemies of the aura's source."""
        if entity.uuid == self.source_entity_uuid:
            return False
        caster = Entity.get(self.source_entity_uuid)
        return caster is None or not entity.is_ally(caster)

    def _affect_enemy(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> bool:
        """Resolve one admitted Spirit Guardians save, damage, and slow."""
        source_uuid = self.source_entity_uuid
        if entity.uuid == source_uuid:
            return False
        caster = Entity.get(source_uuid)
        if caster is not None and entity.is_ally(caster):
            return False

        save_request = entity.create_saving_throw_request(
            target_entity_uuid=entity.uuid,
            ability_name=AbilityName.WISDOM,
            dc=self.spell_dc,
            parent_event=parent_event.uuid,
        )
        _, _, success = entity.saving_throw(save_request)
        damage_bonus = (
            caster.get_spell_damage_bonus()
            if caster is not None
            else ModifiableValue.create(
                source_entity_uuid=source_uuid,
                base_value=0,
                value_name="Spell Damage",
            )
        )
        damage = Damage(
            source_entity_uuid=source_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=8,
            dice_numbers=3 + self.upcast_dice,
            damage_bonus=damage_bonus,
            damage_type=self.damage_type,
        )
        rolled = damage.get_dice(
            attack_outcome=AttackOutcome.HIT,
        ).roll.total
        entity.receive_damage(
            rolled // 2 if success else rolled,
            self.damage_type,
            source_uuid,
            parent_event=parent_event.uuid,
        )

        return True

    def _apply_effect_entry_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Apply BG3-style damage when the moving aura reaches a creature."""
        self._affect_enemy(entity, parent_event=parent_event)

    def _apply_effect_exit_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Release only this aura's slow source when it moves away."""
        self.remove_membership(entity, parent_event=parent_event)

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create handler for entry - WIS save, radiant damage (enemies only)."""
        source_uuid = self.source_entity_uuid
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None

            entity = Entity.get(event.entity_uuid)
            if entity is not None:
                condition._affect_enemy(entity, parent_event=event)
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

            zone_condition._affect_enemy(entity, parent_event=event)
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

            self.remove_membership(entity, parent_event=event)

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
        return self._validate_self_cast(declaration_event)

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
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            SPIRIT_GUARDIANS_FIELD_RECIPE,
            caster.uuid,
            position=caster.senses.position,
            faction=caster.faction,
            condition_type=SpiritGuardiansZone,
            condition_fields={
                "spell_dc": dc,
                "damage_type": self.damage_type,
                "upcast_dice": upcast_bonus,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Spirit Guardians field could not be established",
            )

        concentration = self.ensure_concentration(effect_event)

        concentration.add_linked_condition(zone.uuid, zone.uuid)

        self._close_concentration(effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Spirit Guardians active: 15ft sphere around {caster.name}",
        )


class FogCloudZone(AreaCondition):
    """Zone control condition for Fog Cloud spell.

    Creates a 20ft radius sphere of heavily obscured area (DARKNESS).
    Uses obscurement so darkvision cannot see through it.
    """
    name: str = Field(default="Fog Cloud Zone", description="Display name for the fog cloud zone zone condition.")
    description: str = Field(default="Heavily obscured fog — blocks vision including darkvision", description="Rules-facing summary for the fog cloud zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the fog cloud zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by fog cloud zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by fog cloud zone.")

    optical_obscurement: Optional[OpticalObscurement] = Field(
        default=OpticalObscurement.HEAVY,
        description="Fog blocks visual routes without changing objective illumination.",
    )


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
        """Validate target position is in range and visible."""
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        radius = 20 + self.get_upcast_bonus() * 20

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Fog Cloud at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            FOG_CLOUD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=FogCloudZone,
            condition_fields={
                "zone_radius_feet": radius,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Fog Cloud field could not be established",
            )

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        self._close_concentration(effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Fog Cloud active: {radius}ft radius sphere at {target_pos}"
        )


class DarknessZone(AreaCondition):
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

    sets_light_level: Optional[LightLevel] = Field(
        default=LightLevel.DARKNESS,
        description="Darkness caps objective illumination in affected cells.",
    )
    light_is_cap: bool = Field(default=True, description="Darkness caps rather than adds illumination.")
    optical_obscurement: Optional[OpticalObscurement] = Field(
        default=OpticalObscurement.MAGICAL_DARKNESS,
        description="Conditional optical obscurement bypassed only by exact senses.",
    )


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
        """Validate target position is in range and visible."""
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Darkness at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            DARKNESS_FIELD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=DarknessZone,
            condition_fields={
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Darkness field could not be established",
            )

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        self._close_concentration(effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Darkness active: 15ft sphere at {target_pos}"
        )


class DaylightZone(AreaCondition):
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
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=600,
            duration_type=DurationType.ROUNDS,
        ),
        description="Daylight persists independently for one hour.",
    )


def _is_daylight_targetable_darkness(position: Tuple[int, int]) -> bool:
    """Return whether Daylight may target a magical-darkness position."""
    return OpticalObscurement.MAGICAL_DARKNESS in get_map().get_optical_obscurements_at(position)


def _remove_overlapping_darkness_zones(
    daylight_zone: DaylightZone,
    parent_event: Event,
) -> int:
    """Retire exact indexed Darkness fields overlapping a Daylight field."""
    conditions: dict[UUID, AreaCondition] = {}
    grid = get_map()
    for position in daylight_zone.affected_positions:
        for condition in grid.get_spatial_conditions_at(
                position,
                layer=SpatialEffectLayer.FIELD,
        ):
            if isinstance(condition, AreaCondition):
                conditions[condition.uuid] = condition
    removed = 0
    for condition_uuid in sorted(conditions, key=str):
        condition = conditions[condition_uuid]
        if condition.content_ref != DARKNESS_FIELD_RECIPE.ref:
            continue
        condition.deactivate(parent_event=parent_event)
        removed += 1
    return removed


class Daylight(SpellAction):
    """Daylight - 3rd level Evocation.

    A 60-foot-radius sphere of light spreads out from a point you choose
    within range. The sphere is bright light and sheds dim light for an
    additional 60 feet.

    If you chose a point on an object you are holding or one that isn't being
    worn or carried, the light shines from the object with and moves with it.

    If any of this spell's area overlaps with an area of darkness created by a
    spell of 3rd level or lower, the spell that created the darkness is
    dispelled.

    Duration: 1 hour, independently timed.
    """
    name: str = Field(default="Daylight", description="Display name for the daylight spell.")
    description: str = Field(default="60ft sphere very bright light, reveals hidden, dispels darkness", description="Rules-facing summary for the daylight spell.")
    spell_level: int = Field(default=3, description="Spell slot level required to cast daylight; cantrips use 0.")
    spell_school: str = Field(default="evocation", description="D&D school of magic used to classify daylight.")
    concentration: bool = Field(default=False, description="Daylight persists without concentration.")
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
        if target_pos is None:
            return declaration_event.cancel(status_message="No target position specified")

        if (
            (target_pos not in caster.senses.visible or not caster.senses.visible[target_pos])
            and not _is_daylight_targetable_darkness(target_pos)
        ):
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.distance_to_position(target_pos)
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
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Daylight at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            DAYLIGHT_FIELD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=DaylightZone,
            condition_fields={
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Daylight field could not be established",
            )
        removed_darkness = _remove_overlapping_darkness_zones(zone, effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Daylight active: 60ft sphere at {target_pos}; dispelled {removed_darkness} darkness zone(s)"
        )


class InsectPlagueZone(AreaCondition):
    """Zone for Insect Plague - swarming locusts deal piercing damage."""
    name: str = Field(default="Insect Plague Zone", description="Display name for the insect plague zone zone condition.")
    description: str = Field(default="Swarming biting locusts - CON save or 4d10 piercing", description="Rules-facing summary for the insect plague zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the insect plague zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by insect plague zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by insect plague zone.")
    adds_difficult_terrain: bool = Field(default=True, description="Whether insect plague zone makes affected tiles difficult terrain.")

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for insect plague zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by insect plague zone saving throws.")
    base_dice: int = Field(default=4, description="Base number of damage dice rolled by insect plague zone.")
    upcast_dice: int = Field(default=0, description="Additional damage dice contributed by upcasting insect plague zone.")

    def _damage_entity(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        if not entity.has_hp:
            return
        save_request = entity.create_saving_throw_request(
            target_entity_uuid=entity.uuid,
            ability_name=AbilityName.CONSTITUTION,
            dc=self.spell_dc,
            parent_event=parent_event.uuid,
        )
        _, _, success = entity.saving_throw(save_request)
        caster = Entity.get(self.source_entity_uuid)
        damage_bonus = (
            caster.get_spell_damage_bonus()
            if caster is not None
            else ModifiableValue.create(
                source_entity_uuid=self.source_entity_uuid,
                base_value=0,
                value_name="Spell Damage",
            )
        )
        damage = Damage(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=10,
            dice_numbers=self.base_dice + self.upcast_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.PIERCING,
        )
        damage_roll = damage.get_dice(
            attack_outcome=AttackOutcome.HIT,
        ).roll
        amount = damage_roll.total // 2 if success else damage_roll.total
        entity.receive_damage(
            amount,
            DamageType.PIERCING,
            self.source_entity_uuid,
            parent_event=parent_event.uuid,
        )

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Resolve Insect Plague's explicit when-the-area-appears save."""
        self._damage_entity(entity, parent_event=parent_event)

    def _create_zone_entry_handler(self) -> EventHandler:
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            entity = Entity.get(event.entity_uuid)
            if entity is not None:
                condition._damage_entity(entity, parent_event=event)
            return None

        return EventHandler(
            name="Insect Plague Entry Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_end_handler(self) -> EventHandler:
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_END:
                return None
            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if entity is None:
                return None
            if entity.senses.position not in condition.affected_positions:
                return None
            condition._damage_entity(entity, parent_event=event)
            return None

        return EventHandler(
            name="Insect Plague Turn End Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )


class InsectPlague(SpellAction):
    """Insect Plague - 5th level Conjuration (Concentration)

    Swarming locusts fill a 20ft sphere. CON save or 4d10 piercing (half on save).
    Damages when the area appears, on entry, and at turn end. At Higher
    Levels: +1d10 per level above 5th.
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
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
        upcast_bonus = self.get_upcast_bonus()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution", save_dc=dc,
            status_message=f"{caster.name} casts Insect Plague at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            INSECT_PLAGUE_FIELD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=InsectPlagueZone,
            condition_fields={
                "spell_dc": dc,
                "upcast_dice": upcast_bonus,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Insect Plague field could not be established",
            )

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        self._close_concentration(effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Insect Plague active: 20ft sphere at {target_pos}"
        )


class IncendiaryCloudZone(AreaCondition):
    """Zone for Incendiary Cloud - roiling fire cloud deals fire damage."""
    name: str = Field(default="Incendiary Cloud Zone", description="Display name for the incendiary cloud zone zone condition.")
    description: str = Field(default="Roiling fire cloud - DEX save or 10d8 fire", description="Rules-facing summary for the incendiary cloud zone zone condition.")
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL}, description="Condition tags that classify the incendiary cloud zone for cleanup and filtering.")

    zone_shape: str = Field(default="sphere", description="Area shape used by incendiary cloud zone to compute affected grid positions.")
    zone_radius_feet: int = Field(default=20, description="Zone radius in feet used by incendiary cloud zone.")
    adds_difficult_terrain: bool = Field(default=False, description="Whether incendiary cloud zone makes affected tiles difficult terrain.")
    optical_obscurement: Optional[OpticalObscurement] = Field(
        default=OpticalObscurement.HEAVY,
        description="The cloud blocks visual routes without changing illumination.",
    )

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ALL, description="Creature relationship filter used for incendiary cloud zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by incendiary cloud zone saving throws.")
    base_dice: int = Field(default=10, description="Base number of damage dice rolled by incendiary cloud zone.")

    def _damage_entity(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        if not entity.has_hp:
            return
        save_request = entity.create_saving_throw_request(
            target_entity_uuid=entity.uuid,
            ability_name=AbilityName.DEXTERITY,
            dc=self.spell_dc,
            parent_event=parent_event.uuid,
        )
        _, _, success = entity.saving_throw(save_request)
        caster = Entity.get(self.source_entity_uuid)
        damage_bonus = (
            caster.get_spell_damage_bonus()
            if caster is not None
            else ModifiableValue.create(
                source_entity_uuid=self.source_entity_uuid,
                base_value=0,
                value_name="Spell Damage",
            )
        )
        damage = Damage(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=8,
            dice_numbers=self.base_dice,
            damage_bonus=damage_bonus,
            damage_type=DamageType.FIRE,
        )
        damage_roll = damage.get_dice(
            attack_outcome=AttackOutcome.HIT,
        ).roll
        amount = damage_roll.total // 2 if success else damage_roll.total
        entity.receive_damage(
            amount,
            DamageType.FIRE,
            self.source_entity_uuid,
            parent_event=parent_event.uuid,
        )

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Resolve Incendiary Cloud's explicit appearance damage."""
        self._damage_entity(entity, parent_event=parent_event)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event = super()._apply(declaration_event)
        auto_move_handler = self._create_auto_move_handler()
        EventQueue.add_event_handler(auto_move_handler)
        handler_uuids.append(auto_move_handler.uuid)
        return outs, handler_uuids, sub_conditions_uuids, external_uuids, effect_event

    def _create_zone_entry_handler(self) -> EventHandler:
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            entity = Entity.get(event.entity_uuid)
            if entity is not None:
                condition._damage_entity(entity, parent_event=event)
            return None

        return EventHandler(
            name="Incendiary Cloud Entry Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_zone_turn_end_handler(self) -> EventHandler:
        condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.TURN_END:
                return None
            entity_uuid = event.source_entity_uuid
            entity = Entity.get(entity_uuid)
            if entity is None:
                return None
            if entity.senses.position not in condition.affected_positions:
                return None
            condition._damage_entity(entity, parent_event=event)
            return None

        return EventHandler(
            name="Incendiary Cloud Turn End Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.TURN_END,
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
            zx, zy = zone_condition.position
            dx = zx - cx
            dy = zy - cy
            if dx == 0 and dy == 0:
                dx = 1
            length = max(abs(dx), abs(dy), 1)
            move_x = int(dx / length * 2) if dx != 0 else 0
            move_y = int(dy / length * 2) if dy != 0 else 0
            zone_condition.move_zone(
                (zx + move_x, zy + move_y),
                parent_event=event,
            )
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
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity", save_dc=dc,
            status_message=f"{caster.name} casts Incendiary Cloud at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            INCENDIARY_CLOUD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=IncendiaryCloudZone,
            condition_fields={
                "spell_dc": dc,
                "arbitration_potency": dc,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Incendiary Cloud field could not be established",
            )

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        self._close_concentration(effect_event)

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


class StinkingCloudZone(AreaCondition):
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

    optical_obscurement: Optional[OpticalObscurement] = Field(
        default=OpticalObscurement.HEAVY,
        description="The cloud blocks visual routes without changing illumination.",
    )

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ENEMIES, description="Creature relationship filter used for stinking cloud zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by stinking cloud zone saving throws.")

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
                ability_name=AbilityName.CONSTITUTION,
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
    saving_throw_effect_tags: Tuple[SavingThrowEffectTag, ...] = Field(
        default=(SavingThrowEffectTag.POISON,),
        description="Exact origin-rule semantics carried by Stinking Cloud saves.",
    )
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
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="constitution", save_dc=dc,
            status_message=f"{caster.name} casts Stinking Cloud at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            STINKING_CLOUD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=StinkingCloudZone,
            condition_fields={
                "spell_dc": dc,
                "arbitration_potency": dc,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Stinking Cloud field could not be established",
            )

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        self._close_concentration(effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Stinking Cloud active: 20ft sphere at {target_pos}"
        )


class SleetStormZone(AreaCondition):
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

    optical_obscurement: Optional[OpticalObscurement] = Field(
        default=OpticalObscurement.HEAVY,
        description="The storm blocks visual routes without changing illumination.",
    )

    hazard_filter: Optional[HazardFilter] = Field(default=HazardFilter.ENEMIES, description="Creature relationship filter used for sleet storm zone hazard markers.")

    spell_dc: int = Field(default=10, description="Spell save DC used by sleet storm zone saving throws.")

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

    def _emit_dousing_interaction(
        self,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Emit the typed dousing operation consumed by material transitions."""
        if not self.affected_positions:
            return
        douse_event = SpatialEffectInteractionEvent(
            source_entity_uuid=self.source_entity_uuid,
            operation=SpatialEffectInteractionOperation.DOUSE,
            positions=tuple(sorted(self.affected_positions)),
            intensity=SpatialEffectInteractionIntensity.STRONG,
            parent_event=parent_event.uuid if parent_event is not None else None,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
        EventQueue.publish_lifecycle(douse_event)

    def _create_exposed_flame_handler(self) -> EventHandler:
        """Create a handler that douses flames ignited inside the storm."""
        source_uuid = self.source_entity_uuid
        zone_condition = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialEffectInteractionEvent):
                return None
            if event.operation is not SpatialEffectInteractionOperation.IGNITE:
                return None
            if not set(event.positions).intersection(
                zone_condition.affected_positions,
            ):
                return None
            if event.source_object_uuid is None:
                return None
            item = BaseBlock.get(event.source_object_uuid)
            if isinstance(item, BaseItem):
                zone_condition._douse_item_if_exposed(item, event)
            return None

        return EventHandler(
            name="Sleet Storm Douse Exposed Flame",
            source_entity_uuid=source_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_EFFECT_INTERACTION,
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
                ability_name=AbilityName.DEXTERITY, dc=dc,
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
                    ability_name=AbilityName.DEXTERITY, dc=dc,
                    parent_event=event.uuid
                )
                _, _, success = entity.saving_throw(save_request)
                if not success:
                    prone = Prone(source_entity_uuid=source_uuid, target_entity_uuid=entity.uuid, tags={ConditionTag.MAGICAL})
                    entity.add_condition(prone, parent_event=event)

            if "Concentrating" in entity.active_conditions:
                save_request = entity.create_saving_throw_request(
                    target_entity_uuid=entity.uuid,
                    ability_name=AbilityName.CONSTITUTION, dc=dc,
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
        self._emit_dousing_interaction(effect_event)
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
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")
        target_pos = self.end_position
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity", save_dc=dc,
            status_message=f"{caster.name} casts Sleet Storm at {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        zone = materialize_spatial_condition(
            SLEET_STORM_FIELD_RECIPE,
            caster.uuid,
            position=target_pos,
            faction=caster.faction,
            condition_type=SleetStormZone,
            condition_fields={
                "spell_dc": dc,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        activation = zone.activate(parent_event=effect_event)
        if activation is None or activation.canceled or not zone.applied:
            return effect_event.cancel(
                status_message="Sleet Storm field could not be established",
            )
        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(zone.uuid, zone.uuid)

        self._close_concentration(effect_event)

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
        if target_pos is None:
            return declaration_event.cancel(status_message="No target position")

        if target_pos not in caster.senses.visible or not caster.senses.visible[target_pos]:
            return declaration_event.cancel(status_message=f"Position {target_pos} not visible")

        distance = caster.distance_to_position(target_pos)
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
        if target_pos is None:
            return execution_event.cancel(status_message="No target position")

        old_pos = caster.senses.position

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} teleports from {old_pos} to {target_pos}"
        )
        if effect_event.canceled:
            return effect_event

        Entity.update_entity_position(caster, target_pos)
        caster.materialize_navigation()

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} teleports to {target_pos}"
        )


class GuardianOfFaithCondition(AreaCondition):
    """Fixed spectral guardian with one shared per-target turn admission fence."""

    name: str = Field(default="Guardian of Faith")
    description: str = Field(
        default=(
            "A spectral guardian blocks its space and damages hostile "
            "creatures entering within 10 feet."
        ),
    )
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    duration: Duration = Field(
        default_factory=lambda: Duration(
            duration=4800,
            duration_type=DurationType.ROUNDS,
        ),
    )
    spell_dc: int = Field(default=0, ge=0)
    damage_budget: int = Field(default=60, ge=1)
    damage_dealt: int = Field(default=0, ge=0)
    hazard_filter: Optional[HazardFilter] = HazardFilter.ENEMIES
    def _compute_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return the guardian's own space plus every cell within 10 feet."""
        center_x, center_y = self.position
        return {
            (center_x + dx, center_y + dy)
            for dx in range(-2, 3)
            for dy in range(-2, 3)
        }

    def _create_zone_entry_handler(self) -> EventHandler:
        """Create the indexed hostile-entry save and damage handler."""
        condition = self

        def processor(
            event: Event,
            _source_entity_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            entity = (
                Entity.get(event.entity_uuid)
                if event.entity_uuid is not None
                else None
            )
            caster = Entity.get(condition.source_entity_uuid)
            if entity is None or caster is None:
                return None
            if entity.uuid == caster.uuid or entity.is_ally(caster):
                return None

            save_request = entity.create_saving_throw_request(
                target_entity_uuid=entity.uuid,
                ability_name=AbilityName.DEXTERITY,
                dc=condition.spell_dc,
                parent_event=event.uuid,
            )
            _, _, success = entity.saving_throw(save_request)
            damage = 10 if success else 20
            hp_before = entity.get_hp()
            entity.receive_damage(
                amount=damage,
                damage_type=DamageType.RADIANT,
                source_entity_uuid=caster.uuid,
                parent_event=event.uuid,
            )
            condition.damage_dealt += max(0, hp_before - entity.get_hp())
            if condition.damage_dealt >= condition.damage_budget:
                condition.deactivate(parent_event=event)
            return None

        return EventHandler(
            name="Guardian of Faith Entry Damage",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
            )],
            event_processor=processor,
        )


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
        if self.end_position is None:
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
        if position is None:
            return execution_event.cancel(status_message="No target position")

        dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} summons a Guardian of Faith"
        )
        if effect_event.canceled:
            return effect_event

        guardian = materialize_spatial_condition(
            GUARDIAN_OF_FAITH_FIELD_RECIPE,
            caster.uuid,
            position=position,
            faction=caster.faction,
            condition_type=GuardianOfFaithCondition,
            condition_fields={
                "spell_dc": dc,
                "effect_origin": execution_event.to_effect_origin(),
            },
        )
        result = guardian.activate(parent_event=effect_event)
        if result is None or result.canceled or not guardian.applied:
            return execution_event.cancel(
                status_message="Guardian of Faith field could not be installed",
            )

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

        wis_save = target.saving_throws.get_saving_throw(AbilityName.WISDOM)
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

        con_mod = target.ability_scores.get_ability(AbilityName.CONSTITUTION).get_combined_values().normalized_score
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
            con_mod = target.ability_scores.get_ability(AbilityName.CONSTITUTION).get_combined_values().normalized_score
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
        if effect_event.canceled:
            return effect_event

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
                    semantic_key="action.environment.heroes_feast.eat",
                    behavior_id="action.environment.heroes_feast.eat",
                ),
            )
        ]


def build_heroes_feast_object(
    source_entity_uuid: UUID,
) -> HeroesFeastObject:
    """Construct the spell-created feast with direct semantic identity."""
    return HeroesFeastObject(
        source_entity_uuid=source_entity_uuid,
        semantic_key="environment.spell_object.heroes_feast",
        caster_uuid=source_entity_uuid,
    )


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
        return self._validate_visible_position_in_range(declaration_event)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")
        position = self.end_position
        if position is None:
            return execution_event.cancel(status_message="No target position")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} conjures a Heroes' Feast"
        )
        if effect_event.canceled:
            return effect_event

        feast = build_heroes_feast_object(caster.uuid)
        feast.place_on_grid(position)
        feast.publish_location_state(
            ItemLocation.FLOOR,
            world_placement=get_map().get_object_placement(feast.uuid),
            source_entity_uuid=caster.uuid,
            parent_event=effect_event,
        )

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


HEROES_FEAST_OBJECT_DECLARATION = get_content_declaration(
    _build_heroes_feast_object,
)
HEROES_FEAST_OBJECT_REF = HEROES_FEAST_OBJECT_DECLARATION.ref
HEROES_FEAST_OBJECT_RECIPE = ContentRecipe.create(
    ref=HEROES_FEAST_OBJECT_REF,
    parameters={},
)
SRD_SPELL_ENVIRONMENT_OBJECT_DECLARATIONS: tuple[
    ContentDeclaration,
    ...,
] = (
    HEROES_FEAST_OBJECT_DECLARATION,
)
