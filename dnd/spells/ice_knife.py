"""Ice Knife's selected attack and subsequent unpaid area effect."""

from uuid import uuid5

from pydantic import Field

from dnd.actions import SpellAction, SpellEvent
from dnd.core.aoe import Sphere, snapshot_aoe_presentation_geometry
from dnd.core.base_actions import TargetType, target_resolution_sort_key
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentOrdering, ContentPresentation, ContentVisibility
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus
from dnd.core.content.registration import behavior_identity
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.events import Damage, EventPhase, Range, RangeType
from dnd.core.spell_execution import bind_spell_execution_lineage, spell_execution_scope
from dnd.entity import Entity
from dnd.spells.spell_utils import validate_line_of_sight


ICE_KNIFE_BURST = "spell.ice_knife.burst"


@behavior_identity(
    definition_kind=ContentDefinitionKind.SPELL,
    runtime_behavior_kind=RuntimeBehaviorKind.SPELL,
    pack_id="content.neurodragon", content_id="spell.ice_knife", version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Ice Knife",
        description="A piercing spell attack followed by a five-foot cold explosion, hit or miss.",
        tags=("level_1", "conjuration", "spell"), visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(icon_key="spell.ice_knife", visual_variant_key="ice_knife",
            vfx_profile="spell.ice_knife", ui_group="spells.conjuration"),
        ordering=ContentOrdering(sort_group="spells.level_1.conjuration", sort_order=335),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.ice_knife_legacy",
        source_anchor="Ice Knife, legacy 2014 rules: https://www.dndbeyond.com/spells/2384-ice-knife",
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL, review_status=ContentReviewStatus.REVIEWED,
        notes="New engine implementation of the legacy rule; not an SRD 5.1 spell or a 2024 rules migration.",
    ),
)
class IceKnife(SpellAction):
    """One paid cast; attack damage and cold saves retain separate causal branches."""

    name: str = "Ice Knife"
    description: str = "Ranged attack for 1d10 piercing; hit or miss, a 5ft burst deals 2d6 cold on a failed Dexterity save."
    spell_level: int = 1
    spell_school: str = "conjuration"
    verbal: bool = False
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    valid_target_filter: str = "all"
    include_self: bool = True
    spell_damage_type: DamageType | None = DamageType.PIERCING
    saving_throw_effect_id: str | None = ICE_KNIFE_BURST

    def _validate(self, declaration_event: SpellEvent) -> SpellEvent | None:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if caster is None or target is None:
            return declaration_event.cancel(status_message="Caster or target not found")
        if self.get_target_distance(target.position) > self.effective_range:
            return declaration_event.cancel(status_message="Target out of range")
        return validate_line_of_sight(declaration_event, self.source_entity_uuid)

    def _apply(self, execution_event: SpellEvent) -> SpellEvent | None:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if caster is None or target is None:
            return execution_event.cancel(status_message="Caster or target not found")
        center = target.position
        resolution = self.resolve_spell_attack(caster, target, execution_event.uuid)
        effect = execution_event.phase_to(EventPhase.EFFECT,
            attack_bonus=resolution.attack_bonus, ac=resolution.target_ac,
            dice_roll=resolution.dice_roll, attack_outcome=resolution.outcome,
            is_threatened=resolution.is_threatened,
        )
        if effect.canceled:
            return effect
        if resolution.outcome in (AttackOutcome.HIT, AttackOutcome.CRIT):
            critical = resolution.outcome is AttackOutcome.CRIT
            damage = Damage(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
                damage_type=DamageType.PIERCING, damage_dice=10, dice_numbers=1,
                damage_bonus=caster.get_spell_damage_bonus())
            roll = damage.get_dice(resolution.outcome,
                crit_extra_dice=caster.get_spell_crit_extra_dice() if critical else 0).roll
            dealt = target.receive_damage(roll.total, DamageType.PIERCING, caster.uuid,
                damages=[damage], damage_rolls=[roll], parent_event=effect.uuid,
                critical_hit=critical, effect_id="spell.ice_knife.piercing",
                impact_direction=(center[0] - caster.position[0], center[1] - caster.position[1]))
            effect = effect.with_updates(damages=[damage], damage_rolls=[roll], total_damage=dealt)
        # Damage contributors see the burst's actual type but retain the same
        # cast identity, so once-per-cast bonuses cannot become two spell casts.
        with spell_execution_scope(source_entity_uuid=caster.uuid, damage_type=DamageType.COLD,
                cause_id=effect.behavior_id, saving_throw_effect_id=ICE_KNIFE_BURST):
            bind_spell_execution_lineage(execution_event.lineage_uuid)
            self._burst(caster, center, effect)
        return effect

    def _burst(self, caster: Entity, center: tuple[int, int], parent: SpellEvent) -> None:
        """Resolve the admitted spell's burst, without declaring another cast.

        Counterspell intercepts CAST_SPELL at EXECUTION. These effect/application
        nodes start at EFFECT; their saves and damage still run ordinary native
        event progression, under the original spell's execution context.
        """
        shape = Sphere(source_entity_uuid=caster.uuid, target=center, radius_feet=5)
        shape.compute_objective(caster.position)
        recipients = [entity for identity in sorted(shape.affected_entity_uuids, key=target_resolution_sort_key)
                      if (entity := Entity.get(identity)) is not None and entity.is_active]
        burst = SpellEvent(name="Ice Knife burst", spell_id="ice_knife", effect_id=ICE_KNIFE_BURST,
            use_register=False,
            parent_event=parent.uuid, phase=EventPhase.EFFECT,
            source_entity_uuid=caster.uuid, source_entity_name=caster.name, source_position=parent.source_position,
            effect_source_position=parent.effect_source_position,
            behavior_id=parent.behavior_id, provided_by_id=parent.provided_by_id, origin_root_id=parent.origin_root_id,
            spell_level=self.spell_level, cast_at_level=self.cast_at_level, spell_school=self.spell_school,
            verbal=False, costs=[], aoe_position=center, aoe_shape_type="sphere", aoe_radius_ft=5,
            area_geometry=snapshot_aoe_presentation_geometry(shape, caster.position),
            area_propagation=shape.propagation,
            resolved_area_positions=tuple(sorted(shape.affected_positions)),
            declared_target_entity_uuids=[entity.uuid for entity in recipients], total_targets=len(recipients),
            damage_types=[DamageType.COLD],
        )
        burst = burst.post(use_register=True)
        if burst.canceled:
            return
        cold = Damage(source_entity_uuid=caster.uuid, damage_type=DamageType.COLD,
            damage_dice=6, dice_numbers=2 + self.get_upcast_bonus(), damage_bonus=caster.get_spell_damage_bonus())
        roll = cold.get_dice(AttackOutcome.HIT).roll
        total = 0
        for index, recipient in enumerate(recipients):
            application = SpellEvent(name="Ice Knife burst", spell_id="ice_knife", effect_id=ICE_KNIFE_BURST,
                use_register=False,
                parent_event=burst.uuid, phase=EventPhase.EFFECT,
                source_entity_uuid=caster.uuid, source_entity_name=caster.name, source_position=parent.source_position,
                effect_source_position=parent.effect_source_position,
                target_entity_uuid=recipient.uuid, target_entity_name=recipient.name,
                behavior_id=parent.behavior_id, provided_by_id=parent.provided_by_id, origin_root_id=parent.origin_root_id,
                spell_level=self.spell_level, cast_at_level=self.cast_at_level, spell_school=self.spell_school,
                verbal=False, costs=[], damage_types=[DamageType.COLD], application_index=index,
                application_id=uuid5(burst.lineage_uuid, f"target-application:{index}"),
            )
            application = application.post(use_register=True)
            if application.canceled:
                continue
            dc = caster.spell_save_dc(spellcasting_source_id=self.spellcasting_source_id)
            save = caster.create_saving_throw_request(target_entity_uuid=recipient.uuid,
                ability_name="dexterity", dc=dc, parent_event=application.uuid)
            _, saved_roll, success = recipient.saving_throw(save)
            dealt = 0 if success else recipient.receive_damage(roll.total, DamageType.COLD, caster.uuid,
                damages=[cold], damage_rolls=[roll], parent_event=application.uuid, effect_id=ICE_KNIFE_BURST)
            total += dealt
            application.phase_to(EventPhase.COMPLETION, save_ability="dexterity", save_dc=dc,
                save_roll=saved_roll, save_bonus=saved_roll.bonus, save_success=success,
                damages=[cold], damage_rolls=[roll], total_damage=dealt)
        burst.phase_to(EventPhase.COMPLETION, total_damage=total, damages=[cold], damage_rolls=[roll])
