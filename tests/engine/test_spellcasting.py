"""Engine semantic tests for spellcasting core."""

from typing import Optional, cast
from uuid import uuid4

import pytest
from pydantic import Field

from dnd.actions import DropConcentration, SpellAction, SpellEvent
from dnd.actions_functional import (
    apply_action_overrides,
    clear_action_overrides,
    execute_by_index,
    get_available_actions,
    register_spell,
    setup_standard_actions,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingBlock, SpellcastingConfig
from dnd.conditions import Concentrating, Dashing
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_BY_CLASS,
)
from dnd.core.base_actions import TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.events import Damage, DeathEvent, EventPhase, EventQueue, Range, RangeType
from dnd.core.gridmap import get_map
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from tests.spell_test_exports import (
    ALL_SPELLS,
    CANTRIPS,
    LEVEL_1_SPELLS,
    LEVEL_2_SPELLS,
    LEVEL_3_SPELLS,
    LEVEL_4_SPELLS,
    LEVEL_5_SPELLS,
    LEVEL_6_SPELLS,
    LEVEL_7_SPELLS,
    LEVEL_8_SPELLS,
    LEVEL_9_SPELLS,
    FireBolt,
    MagicMissile,
    SPELL_CATALOG_METADATA_BY_NAME,
)
from tests.engine.support import get_hp, reset_combat_state, set_hp
from server.spell_catalog import build_spell_catalog_entry


def reset_spell_state(width: int = 8, height: int = 4) -> None:
    """Clear global state and create a rectangular spell test grid."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, width, height)


def create_spellcaster(
    name: str = "Wizard",
    position: tuple[int, int] = (0, 0),
    spell_slots: Optional[dict[int, int]] = None,
    spellcasting: Optional[SpellcastingConfig] = None,
    proficiency_bonus: int = 3,
) -> Entity:
    """Create a deterministic caster for spellcasting-core examples."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=12),
            constitution=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=18),
            wisdom=AbilityConfig(ability_score=14),
            charisma=AbilityConfig(ability_score=10),
        ),
        action_economy=ActionEconomyConfig(spell_slots=spell_slots or {}),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=3, mode="maximums")]
        ),
        proficiency_bonus=proficiency_bonus,
        spellcasting=spellcasting or SpellcastingConfig(spellcasting_ability="intelligence"),
        position=position,
        faction="casters",
    )
    return Entity.create(source_entity_uuid=uuid4(), name=name, config=config)


def create_spell_target(
    name: str = "Target",
    position: tuple[int, int] = (1, 0),
    faction: str = "monsters",
) -> Entity:
    """Create a durable target entity."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")]
        ),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    return Entity.create(source_entity_uuid=uuid4(), name=name, config=config)


class BookLinkedConcentrationSpell(SpellAction):
    """Small test spell that links one condition to concentration."""

    name: str = Field(default="Book Linked Concentration", description="Book-only linked concentration spell name.")
    description: str = Field(default="Apply a linked Dashing condition", description="Book-only linked concentration spell summary.")
    spell_level: int = Field(default=0, description="Cantrip-level book spell.")
    concentration: bool = Field(default=True, description="Whether this book spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Book linked concentration spell targets self.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF, normal=0),
        description="Self range used by the book-only linked concentration spell.",
    )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Applying linked concentration example",
        )
        concentration = self.ensure_concentration(effect_event)
        linked = Dashing(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
        )
        caster.add_condition(linked, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, linked.uuid)

        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message="Linked concentration example complete",
        )


class BookEmptyConcentrationSpell(SpellAction):
    """Small test spell that starts concentration but links no effects."""

    name: str = Field(default="Book Empty Concentration", description="Book-only empty concentration spell name.")
    description: str = Field(default="Start concentration without linked effects", description="Book-only empty concentration spell summary.")
    spell_level: int = Field(default=0, description="Cantrip-level book spell.")
    concentration: bool = Field(default=True, description="Whether this book spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Book empty concentration spell targets self.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF, normal=0),
        description="Self range used by the book-only empty concentration spell.",
    )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Applying empty concentration example",
        )
        self.ensure_concentration(effect_event)
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message="Empty concentration example complete",
        )


class BookNamedConcentrationSpell(SpellAction):
    """Book-only spell that links a named no-op condition to concentration."""

    name: str = Field(default="Book Named Concentration", description="Book-only named concentration spell name.")
    description: str = Field(default="Apply a named linked condition", description="Book-only named concentration spell summary.")
    spell_level: int = Field(default=0, description="Cantrip-level book spell.")
    concentration: bool = Field(default=True, description="Whether this book spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.SELF, description="Book named concentration spell targets self.")
    linked_effect_name: str = Field(default="Book Linked Effect", description="Name of the linked no-op condition.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.SELF, normal=0),
        description="Self range used by the book-only named concentration spell.",
    )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if caster is None:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message="Applying named concentration example",
        )
        concentration = self.ensure_concentration(effect_event)
        linked = BaseCondition(
            name=self.linked_effect_name,
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
        )
        caster.add_condition(linked, parent_event=effect_event)
        concentration.add_linked_condition(caster.uuid, linked.uuid)

        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message="Named concentration example complete",
        )


class BookMultiTargetConcentrationSpell(SpellAction):
    """Book-only multi-target spell that links one condition per target."""

    name: str = Field(default="Book Multi Concentration", description="Book-only multi-target concentration spell name.")
    description: str = Field(default="Apply linked conditions to multiple targets", description="Book-only multi-target concentration spell summary.")
    spell_level: int = Field(default=0, description="Cantrip-level book spell.")
    concentration: bool = Field(default=True, description="Whether this book spell requires concentration.")
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY, description="Book spell targets multiple entities.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range used by the book-only multi-target concentration spell.",
    )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if caster is None:
            return execution_event.cancel(status_message="Caster not found")
        if target is None:
            return execution_event.cancel(status_message="Target not found")

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying multi-target concentration to {target.name}",
        )
        concentration = self.ensure_concentration(effect_event)
        linked = BaseCondition(
            name=f"Book Multi Effect {target.name}",
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        )
        target.add_condition(linked, parent_event=effect_event)
        concentration.add_linked_condition(target.uuid, linked.uuid)

        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Multi-target concentration applied to {target.name}",
        )


def test_eb_14_001_spell_slots_are_action_economy_values() -> None:
    """EB-14-001: spell slots are ModifiableValues consumed as action costs."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={1: 2, 2: 1})

    assert caster.action_economy.spell_slot_1.normalized_score == 2
    assert caster.action_economy.spell_slot_2.normalized_score == 1
    assert caster.has_spell_slot(1)
    assert caster.has_spell_slot(2)
    assert not caster.has_spell_slot(3)
    assert caster.get_lowest_spell_slot(1) == 1
    assert caster.get_lowest_spell_slot(3) is None

    caster.action_economy.consume("spell_slot_1", 1)

    assert caster.action_economy.spell_slot_1.normalized_score == 1

    caster.action_economy.reset_all_costs()

    assert caster.action_economy.spell_slot_1.normalized_score == 1

    caster.action_economy.reset_spell_slot_costs()

    assert caster.action_economy.spell_slot_1.normalized_score == 2


def test_eb_14_002_spellcasting_block_is_modifier_only() -> None:
    """EB-14-002: SpellcastingBlock stores spell modifiers, not known spells or slots."""
    reset_spell_state()
    block = SpellcastingBlock.create(
        source_entity_uuid=uuid4(),
        config=SpellcastingConfig(
            spellcasting_ability="wisdom",
            spell_attack_modifiers=[("Wand", 2)],
            spell_damage_modifiers=[("Elemental Affinity", 3)],
            spell_dc_modifiers=[("Focus", 1)],
            spell_crit_threshold_modifiers=[("Spell Sniper", 1)],
            spell_crit_extra_dice_modifiers=[("Arcane Surge", 2)],
            extra_spell_damage_dices=[6],
            extra_spell_damage_dices_numbers=[1],
            extra_spell_damage_bonus_modifiers=[[("Radiant Focus", 2)]],
            extra_spell_damage_types=["Radiant"],
        ),
    )

    assert block.spellcasting_ability == "wisdom"
    assert block.spell_attack_bonus.normalized_score == 2
    assert block.spell_damage_bonus.normalized_score == 3
    assert block.spell_dc_bonus.normalized_score == 1
    assert block.spell_crit_threshold.normalized_score == 1
    assert block.spell_crit_extra_dice.normalized_score == 2
    assert not hasattr(block, "spell_slot_1")
    assert not hasattr(block, "known_spells")

    extra_damage = block.get_extra_spell_damage()

    assert len(extra_damage) == 1
    assert extra_damage[0].damage_dice == 6
    assert extra_damage[0].dice_numbers == 1
    assert extra_damage[0].damage_bonus is not None
    assert extra_damage[0].damage_bonus.normalized_score == 2
    assert extra_damage[0].damage_type == DamageType.RADIANT


def test_eb_14_003_entity_spell_numbers_compose_from_multiple_blocks() -> None:
    """EB-14-003: spell attack, DC, crit, and damage combine entity blocks."""
    reset_spell_state()
    caster = create_spellcaster(
        spell_slots={1: 1},
        spellcasting=SpellcastingConfig(
            spellcasting_ability="intelligence",
            spell_attack_modifiers=[("Wand", 2)],
            spell_damage_modifiers=[("Elemental Affinity", 4)],
            spell_dc_modifiers=[("Focus", 1)],
            spell_crit_threshold_modifiers=[("Spell Sniper", 1)],
            spell_crit_extra_dice_modifiers=[("Arcane Surge", 2)],
        ),
        proficiency_bonus=3,
    )
    caster.equipment.attack_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=caster.uuid,
            name="Blessed Implement",
            value=1,
        )
    )
    caster.equipment.damage_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=caster.uuid,
            name="General Damage",
            value=2,
        )
    )
    caster.equipment.crit_threshold.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=caster.uuid,
            name="General Critical",
            value=1,
        )
    )
    caster.equipment.crit_extra_dice.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=caster.uuid,
            name="General Crit Dice",
            value=1,
        )
    )

    assert caster.spell_attack_bonus().normalized_score == 10
    assert caster.spell_save_dc() == 16
    assert caster.get_spell_crit_threshold() == 18
    assert caster.get_spell_crit_extra_dice() == 3
    assert caster.get_spell_damage_bonus().normalized_score == 6


def test_eb_14_004_spell_actions_create_spell_events_and_slot_costs() -> None:
    """EB-14-004: SpellAction metadata becomes SpellEvent declaration metadata."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={1: 1, 2: 1})
    target = create_spell_target()
    Entity.update_all_entities_senses()

    cantrip = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False,
    )
    missile = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    )

    assert [cost.cost_type for cost in cantrip.costs] == ["actions"]
    assert cantrip.cast_at_level == 0
    assert [cost.cost_type for cost in missile.costs] == ["actions", "spell_slot_1"]
    assert missile.cast_at_level == 1

    declaration = missile._create_declaration_event(use_register=False)

    assert isinstance(declaration, SpellEvent)
    assert declaration.spell_id == "magic_missile"
    assert declaration.spell_level == 1
    assert declaration.cast_at_level == 1
    assert declaration.spell_school == "evocation"
    assert declaration.range_ft == 120
    assert declaration.projectile_type == "dart"
    assert declaration.damage_types == [DamageType.FORCE]


def test_eb_14_005_cantrip_dice_scale_at_srd_thresholds() -> None:
    """EB-14-005: cantrip dice scale at levels 5, 11, and 17."""
    reset_spell_state()
    caster = create_spellcaster()
    cantrip = FireBolt(source_entity_uuid=caster.uuid)

    assert cantrip._get_cantrip_dice_count(1) == 1
    assert cantrip._get_cantrip_dice_count(4) == 1
    assert cantrip._get_cantrip_dice_count(5) == 2
    assert cantrip._get_cantrip_dice_count(10) == 2
    assert cantrip._get_cantrip_dice_count(11) == 3
    assert cantrip._get_cantrip_dice_count(16) == 3
    assert cantrip._get_cantrip_dice_count(17) == 4
    assert cantrip._get_cantrip_dice_count(20) == 4


def test_eb_14_006_generate_variants_uses_available_slots() -> None:
    """EB-14-006: explicit variant generation creates ephemeral cast choices."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={1: 2, 3: 1})
    cantrip_template = FireBolt(source_entity_uuid=caster.uuid, template=True)
    missile_template = MagicMissile(source_entity_uuid=caster.uuid, template=True)

    cantrip_variants = cantrip_template.generate_variants(caster)
    missile_variants = missile_template.generate_variants(caster)

    assert len(cantrip_variants) == 1
    assert cantrip_variants[0].cast_at_level == 0
    assert cantrip_variants[0].template is False
    assert cantrip_variants[0].use_register is False
    assert [cost.cost_type for cost in cantrip_variants[0].costs] == ["actions"]

    assert [variant.cast_at_level for variant in missile_variants] == [1, 3]
    assert all(variant.template is False for variant in missile_variants)
    assert all(variant.is_variant for variant in missile_variants)
    assert [cost.cost_type for cost in missile_variants[1].costs] == [
        "actions",
        "spell_slot_3",
    ]
    assert missile_variants[1].get_upcast_bonus() == 2
    assert missile_variants[1].get_multi_target_count() == 5


def test_eb_14_007_registered_spells_surface_executable_slot_variants() -> None:
    """EB-14-007: discovery exposes executable spell-slot variants."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={1: 1, 3: 1})
    target = create_spell_target(position=(1, 0))
    Entity.update_all_entities_senses()
    register_spell(caster, MagicMissile, caster_level=5)
    register_spell(caster, FireBolt, caster_level=5)

    available = get_available_actions(caster)
    missile_actions = [
        info for info in available.entity_actions if info.base_template_name == "Magic Missile"
    ]
    fire_bolt_actions = [
        info for info in available.entity_actions if info.template_name == "Fire Bolt"
    ]

    assert [info.template_name for info in missile_actions] == [
        "Magic Missile__slot_1",
        "Magic Missile__slot_3",
    ]
    assert [info.display_name for info in missile_actions] == [
        "Magic Missile (Level 1)",
        "Magic Missile (Level 3)",
    ]
    assert [info.cast_at_level for info in missile_actions] == [1, 3]
    assert [info.num_projectiles for info in missile_actions] == [3, 5]
    assert all(info.can_afford for info in missile_actions)
    assert all(info.is_spell_variant for info in missile_actions)
    assert all(target.uuid in [target_info.target_uuid for target_info in info.valid_targets] for info in missile_actions)
    assert len(fire_bolt_actions) == 1

    caster.action_economy.consume("spell_slot_1", 1)
    caster.action_economy.reset_all_costs()

    exhausted = get_available_actions(caster)
    remaining_missile_actions = [
        info for info in exhausted.entity_actions if info.base_template_name == "Magic Missile"
    ]

    assert [info.template_name for info in remaining_missile_actions] == ["Magic Missile__slot_3"]
    assert any(info.template_name == "Fire Bolt" for info in exhausted.all_actions)
    assert caster.has_spell_slot(3)

    target_hp_before = get_hp(target)
    result = execute_by_index(caster, "Magic Missile__slot_3", target_index=0, available=exhausted)

    assert isinstance(result, SpellEvent)
    assert not result.canceled
    assert result.cast_at_level == 3
    assert result.total_targets == 5
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    assert caster.action_economy.spell_slot_3.normalized_score == 0
    assert get_hp(target) < target_hp_before


def test_eb_14_019_generated_upcast_variant_executes_with_higher_slot() -> None:
    """EB-14-019: generated variants can execute at their upcast level."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={1: 1, 3: 1})
    target = create_spell_target(position=(1, 0))
    Entity.update_all_entities_senses()

    template = MagicMissile(source_entity_uuid=caster.uuid, template=True)
    variants = template.generate_variants(caster)
    level_three = next(variant for variant in variants if variant.cast_at_level == 3)
    level_three.target_entity_uuid = target.uuid

    hp_before = target.get_hp()
    result = level_three.apply()

    assert result is not None and not result.canceled
    spell_result = cast(SpellEvent, result)
    assert spell_result.cast_at_level == 3
    assert spell_result.total_targets == 5
    assert level_three.get_multi_target_count() == 5
    assert target.get_hp() < hp_before
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 1
    assert caster.action_economy.spell_slot_3.normalized_score == 0


def test_eb_14_008_magic_missile_convolution_aggregates_child_casts() -> None:
    """EB-14-008: multi-target spells aggregate per-target child applications."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={1: 1})
    target = create_spell_target(position=(1, 0))
    Entity.update_all_entities_senses()
    initial_hp = get_hp(target)

    event = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.total_targets == 3
    assert 6 <= event.total_damage <= 15
    assert get_hp(target) == initial_hp - event.total_damage
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    assert caster.action_economy.actions.normalized_score == 0


def test_eb_14_009_spell_event_damage_types_follow_damage_payloads() -> None:
    """EB-14-009: SpellEvent.phase_to derives damage type metadata from damages."""
    reset_spell_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    event = SpellEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        phase=EventPhase.EFFECT,
        use_register=False,
    )
    damages = [
        Damage(
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            damage_dice=6,
            dice_numbers=1,
            damage_type=DamageType.FIRE,
        ),
        Damage(
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            damage_dice=4,
            dice_numbers=1,
            damage_type=DamageType.FORCE,
        ),
        Damage(
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            damage_dice=8,
            dice_numbers=1,
            damage_type=DamageType.FIRE,
        ),
    ]

    updated = event.phase_to(EventPhase.COMPLETION, damages=damages)

    assert isinstance(updated, SpellEvent)
    assert updated.damage_types == [DamageType.FIRE, DamageType.FORCE]


def test_eb_14_010_concentration_links_cleanup_and_empty_casts() -> None:
    """EB-14-010: concentration owns linked effects and drops empty casts."""
    reset_spell_state()
    caster = create_spellcaster()

    linked_event = BookLinkedConcentrationSpell(
        source_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    assert isinstance(linked_event, SpellEvent)
    assert not linked_event.canceled
    assert "Concentrating" in caster.active_conditions
    assert "Dashing" in caster.active_conditions

    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert concentration.spell_name == "Book Linked Concentration"
    assert len(concentration.linked_conditions) == 1

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Dashing" not in caster.active_conditions

    caster.action_economy.reset_all_costs()
    empty_event = BookEmptyConcentrationSpell(
        source_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    assert isinstance(empty_event, SpellEvent)
    assert not empty_event.canceled
    assert "Concentrating" not in caster.active_conditions


def test_eb_14_011_spell_registration_uses_templates_and_setup_order_matters() -> None:
    """EB-14-011: spell registration uses exact action classes and templates."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={1: 1})

    register_spell(caster, FireBolt, caster_level=5)
    register_spell(caster, MagicMissile, caster_level=5)

    assert [action.name for action in caster.registered_actions] == [
        "Fire Bolt",
        "Magic Missile",
    ]
    assert all(action.template for action in caster.registered_actions)
    fire_bolt_template = caster.get_action_template("Fire Bolt")
    assert isinstance(fire_bolt_template, SpellAction)
    assert fire_bolt_template.caster_level == 5

    setup_standard_actions(caster)

    assert caster.get_action_template("Fire Bolt") is None
    assert caster.get_action_template("Magic Missile") is None
    assert caster.get_action_template("Drop Concentration") is not None

    register_spell(caster, FireBolt, caster_level=5)

    assert caster.get_action_template("Fire Bolt") is not None


def test_eb_14_012_spell_action_overrides_change_template_costs_not_slot_variant_discovery() -> None:
    """EB-14-012: temporary spell overrides affect templates, but variants still require slots."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={})
    target = create_spell_target(position=(1, 0))
    Entity.update_all_entities_senses()
    register_spell(caster, MagicMissile, caster_level=5)

    authored_template = caster.get_action_template("Magic Missile")
    assert isinstance(authored_template, SpellAction)
    assert authored_template.generate_variants(caster) == []
    assert not any(info.template_name == "Magic Missile" for info in get_available_actions(caster).all_actions)

    modified = apply_action_overrides(
        caster,
        lambda action: action.name == "Magic Missile",
        {"alt_skip_slot": True, "alt_cost_type": "bonus_actions"},
    )

    effective_template = caster.get_action_template("Magic Missile")
    assert isinstance(effective_template, SpellAction)
    assert tuple(modified) == (authored_template.uuid,)
    assert authored_template.alt_skip_slot is False
    assert authored_template.alt_cost_type is None
    assert [(cost.name, cost.cost_type, cost.cost) for cost in effective_template.effective_costs] == [
        ("Cast Spell", "bonus_actions", 1)
    ]

    available = get_available_actions(caster)
    overridden = [info for info in available.all_actions if info.template_name == "Magic Missile"]

    assert len(overridden) == 1
    assert overridden[0].cost_type == "bonus_actions"
    assert overridden[0].can_afford
    assert target.uuid in [target_info.target_uuid for target_info in overridden[0].valid_targets]
    assert effective_template.generate_variants(caster) == []

    clear_action_overrides(caster, modified)

    restored_template = caster.get_action_template("Magic Missile")
    assert isinstance(restored_template, SpellAction)
    assert restored_template is authored_template
    assert [(cost.name, cost.cost_type, cost.cost) for cost in restored_template.effective_costs] == [
        ("Cast Spell", "actions", 1),
        ("Spell Slot L1", "spell_slot_1", 1),
    ]


def test_eb_14_018_spell_range_overrides_affect_discovery_and_clear_cleanly() -> None:
    """EB-14-018: alt_range changes spell discovery and clear restores it."""
    reset_spell_state(width=32, height=2)
    caster = create_spellcaster(position=(0, 0), spell_slots={})
    far_target = create_spell_target(position=(26, 0))
    Entity.update_all_entities_senses(max_distance=32)
    register_spell(caster, FireBolt, caster_level=5)

    def has_fire_bolt_target() -> bool:
        available = get_available_actions(caster)
        return any(
            target_info.target_uuid == far_target.uuid
            for info in available.entity_actions
            if info.template_name == "Fire Bolt"
            for target_info in info.valid_targets
        )

    authored_template = caster.get_action_template("Fire Bolt")
    assert isinstance(authored_template, SpellAction)
    assert authored_template.effective_range == 120
    assert not has_fire_bolt_target()

    modified = apply_action_overrides(
        caster,
        lambda action: action.name == "Fire Bolt",
        {"alt_range": 300},
    )

    effective_template = caster.get_action_template("Fire Bolt")
    assert isinstance(effective_template, SpellAction)
    assert tuple(modified) == (authored_template.uuid,)
    assert authored_template.alt_range is None
    assert authored_template.effective_range == 120
    assert effective_template.effective_range == 300
    assert effective_template.get_range().normal == 300
    assert has_fire_bolt_target()

    clear_action_overrides(caster, modified)

    restored_template = caster.get_action_template("Fire Bolt")
    assert restored_template is authored_template
    assert authored_template.alt_range is None
    assert authored_template.effective_range == 120
    assert not has_fire_bolt_target()


def test_action_override_cleanup_preserves_authored_nondefault_fields() -> None:
    """Removing one overlay never resets unrelated authored template facts."""
    reset_spell_state(width=32, height=2)
    caster = create_spellcaster(position=(0, 0), spell_slots={})
    register_spell(caster, FireBolt, caster_level=5)

    authored_template = caster.get_action_template("Fire Bolt")
    assert isinstance(authored_template, SpellAction)
    authored_template.alt_skip_slot = True

    lease = apply_action_overrides(
        caster,
        lambda action: action.name == "Fire Bolt",
        {"alt_range": 300},
    )

    effective_template = caster.get_action_template("Fire Bolt")
    assert isinstance(effective_template, SpellAction)
    assert effective_template is not authored_template
    assert effective_template.alt_skip_slot is True
    assert effective_template.effective_range == 300
    assert authored_template.alt_skip_slot is True
    assert authored_template.alt_range is None

    clear_action_overrides(caster, lease)

    restored_template = caster.get_action_template("Fire Bolt")
    assert restored_template is authored_template
    assert authored_template.alt_skip_slot is True
    assert authored_template.alt_range is None


def test_action_override_leases_are_independently_removable() -> None:
    """Removing one temporary rule preserves every other active overlay."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={})
    register_spell(caster, FireBolt, caster_level=5)
    authored_template = caster.get_action_template("Fire Bolt")
    assert isinstance(authored_template, SpellAction)

    range_lease = apply_action_overrides(
        caster,
        lambda action: action.name == "Fire Bolt",
        {"alt_range": 300},
    )
    cost_lease = apply_action_overrides(
        caster,
        lambda action: action.name == "Fire Bolt",
        {"alt_cost_type": "bonus_actions"},
    )

    combined = caster.get_action_template("Fire Bolt")
    assert isinstance(combined, SpellAction)
    assert combined.effective_range == 300
    assert combined.alt_cost_type == "bonus_actions"

    clear_action_overrides(caster, range_lease)

    cost_only = caster.get_action_template("Fire Bolt")
    assert isinstance(cost_only, SpellAction)
    assert cost_only.effective_range == 120
    assert cost_only.alt_cost_type == "bonus_actions"

    clear_action_overrides(caster, cost_lease)

    assert caster.get_action_template("Fire Bolt") is authored_template
    assert authored_template.alt_range is None
    assert authored_template.alt_cost_type is None


def test_eb_14_013_registered_cantrip_makes_entity_spellcaster() -> None:
    """EB-14-013: registered cantrip templates make is_spellcaster true."""
    reset_spell_state()
    caster = create_spellcaster(spell_slots={})
    target = create_spell_target(position=(1, 0))
    Entity.update_all_entities_senses()

    assert caster.is_spellcaster is False

    register_spell(caster, FireBolt, caster_level=5)

    available = get_available_actions(caster)
    cantrips = [info for info in available.entity_actions if info.template_name == "Fire Bolt"]

    assert len(cantrips) == 1
    assert target.uuid in [target_info.target_uuid for target_info in cantrips[0].valid_targets]
    assert caster.is_spellcaster is True


def test_eb_14_014_drop_concentration_can_target_one_multi_slot_spell() -> None:
    """EB-14-014: DropConcentration can remove one multi-slot concentration spell."""
    reset_spell_state()
    caster = create_spellcaster()
    caster.max_concentration_slots.self_static.add_value_modifier(
        NumericalModifier(
            name="Book Multi Concentration",
            value=1,
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
        )
    )

    first = BookNamedConcentrationSpell(
        source_entity_uuid=caster.uuid,
        name="Book First Concentration",
        linked_effect_name="Book First Effect",
        template=False,
    ).apply()
    caster.action_economy.reset_all_costs()
    second = BookNamedConcentrationSpell(
        source_entity_uuid=caster.uuid,
        name="Book Second Concentration",
        linked_effect_name="Book Second Effect",
        template=False,
    ).apply()

    assert isinstance(first, SpellEvent) and not first.canceled
    assert isinstance(second, SpellEvent) and not second.canceled
    assert "Concentrating" in caster.active_conditions
    assert "Book First Effect" in caster.active_conditions
    assert "Book Second Effect" in caster.active_conditions

    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert len(concentration.concentration_slots) == 2
    assert "Book First Concentration" in concentration.spell_name
    assert "Book Second Concentration" in concentration.spell_name
    actions_before_drop = caster.action_economy.actions.normalized_score

    drop_event = DropConcentration(
        source_entity_uuid=caster.uuid,
        target_spell="Book First Concentration",
        template=False,
    ).apply()

    assert drop_event is not None and not drop_event.canceled
    assert caster.action_economy.actions.normalized_score == actions_before_drop
    assert "Concentrating" in caster.active_conditions
    assert "Book First Effect" not in caster.active_conditions
    assert "Book Second Effect" in caster.active_conditions

    remaining = caster.active_conditions["Concentrating"]
    assert isinstance(remaining, Concentrating)
    assert len(remaining.concentration_slots) == 1
    assert "Book First Concentration" not in remaining.spell_name
    assert remaining.spell_name == "Book Second Concentration"


def test_eb_14_015_damage_and_death_break_concentration_deterministically() -> None:
    """EB-14-015: damage and death events break concentration without randomness."""
    reset_spell_state()
    caster = create_spellcaster()
    set_hp(caster, 100)
    cast_event = BookNamedConcentrationSpell(
        source_entity_uuid=caster.uuid,
        name="Book Fragile Concentration",
        linked_effect_name="Book Fragile Effect",
        template=False,
    ).apply()

    assert isinstance(cast_event, SpellEvent) and not cast_event.canceled
    assert "Concentrating" in caster.active_conditions
    assert "Book Fragile Effect" in caster.active_conditions

    starting_hp = get_hp(caster)
    actual_damage = caster.receive_damage(60, DamageType.FIRE, caster.uuid)

    assert actual_damage == 60
    assert get_hp(caster) == starting_hp - 60
    assert "Concentrating" not in caster.active_conditions
    assert "Book Fragile Effect" not in caster.active_conditions

    dying_caster = create_spellcaster(name="Death-Test Wizard", position=(2, 0))
    death_cast = BookNamedConcentrationSpell(
        source_entity_uuid=dying_caster.uuid,
        name="Book Death Concentration",
        linked_effect_name="Book Death Effect",
        template=False,
    ).apply()

    assert isinstance(death_cast, SpellEvent) and not death_cast.canceled
    assert "Concentrating" in dying_caster.active_conditions
    assert "Book Death Effect" in dying_caster.active_conditions

    death_event = DeathEvent(
        source_entity_uuid=dying_caster.uuid,
        target_entity_uuid=dying_caster.uuid,
        entity_uuid=dying_caster.uuid,
        entity_name=dying_caster.name,
        killer_uuid=dying_caster.uuid,
        killer_name=dying_caster.name,
        final_hp=0,
    )
    death_event = death_event.phase_to(EventPhase.EXECUTION)
    death_event = death_event.phase_to(EventPhase.EFFECT)

    assert not death_event.canceled
    assert "Concentrating" not in dying_caster.active_conditions
    assert "Book Death Effect" not in dying_caster.active_conditions


def test_eb_14_016_multi_target_concentration_reuses_one_slot() -> None:
    """EB-14-016: one multi-target concentration cast reuses one slot."""
    reset_spell_state()
    caster = create_spellcaster()
    first_target = create_spell_target(name="First Target", position=(1, 0))
    second_target = create_spell_target(name="Second Target", position=(2, 0))
    Entity.update_all_entities_senses()

    spell = BookMultiTargetConcentrationSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=first_target.uuid,
        extra_target_entity_uuids=[second_target.uuid],
        template=False,
    )
    event = spell.apply()

    assert event is not None and not event.canceled
    assert "Book Multi Effect First Target" in first_target.active_conditions
    assert "Book Multi Effect Second Target" in second_target.active_conditions
    assert "Concentrating" in caster.active_conditions

    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert spell.cast_concentrating_uuid == concentration.uuid
    assert len(concentration.concentration_slots) == 1
    slot = next(iter(concentration.concentration_slots.values()))
    assert slot.spell_name == "Book Multi Concentration"
    assert set(slot.linked_entries) == {
        (first_target.uuid, first_target.active_conditions["Book Multi Effect First Target"].uuid),
        (second_target.uuid, second_target.active_conditions["Book Multi Effect Second Target"].uuid),
    }
    assert len(concentration.linked_conditions) == 2

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Book Multi Effect First Target" not in first_target.active_conditions
    assert "Book Multi Effect Second Target" not in second_target.active_conditions


def test_multi_target_action_restores_primary_target_after_application_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed target application cannot leak its target into the action."""
    reset_spell_state()
    caster = create_spellcaster()
    first_target = create_spell_target(name="First Target", position=(1, 0))
    second_target = create_spell_target(name="Second Target", position=(2, 0))
    Entity.update_all_entities_senses()
    spell = BookMultiTargetConcentrationSpell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=first_target.uuid,
        extra_target_entity_uuids=[second_target.uuid],
        template=False,
    )

    def fail_on_second_target(
        action: BookMultiTargetConcentrationSpell,
        execution_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        if action.target_entity_uuid == second_target.uuid:
            raise RuntimeError("deterministic target application failure")
        effect_event = execution_event.phase_to(EventPhase.EFFECT)
        return effect_event.phase_to(EventPhase.COMPLETION)

    monkeypatch.setattr(
        BookMultiTargetConcentrationSpell,
        "_apply",
        fail_on_second_target,
    )

    with pytest.raises(
        RuntimeError,
        match="deterministic target application failure",
    ):
        spell.apply()

    assert spell.target_entity_uuid == first_target.uuid


def test_eb_14_017_spell_catalog_identity_matches_spell_events() -> None:
    """EB-14-017: explicit catalog IDs agree with emitted public spell IDs."""
    reset_spell_state()
    level_buckets = {
        0: CANTRIPS,
        1: LEVEL_1_SPELLS,
        2: LEVEL_2_SPELLS,
        3: LEVEL_3_SPELLS,
        4: LEVEL_4_SPELLS,
        5: LEVEL_5_SPELLS,
        6: LEVEL_6_SPELLS,
        7: LEVEL_7_SPELLS,
        8: LEVEL_8_SPELLS,
        9: LEVEL_9_SPELLS,
    }
    bucketed_names = [name for spells in level_buckets.values() for name in spells]

    assert len(bucketed_names) == len(set(bucketed_names))
    assert set(bucketed_names) == set(ALL_SPELLS)

    before_registry_count = len(BaseObject._registry)
    entries = {
        SPELL_CATALOG_METADATA_BY_NAME[display_name].catalog_id:
            build_spell_catalog_entry(
                SPELL_CATALOG_COMPOSITION_BY_CLASS[spell_cls],
            )
        for display_name, spell_cls in ALL_SPELLS.items()
    }
    after_registry_count = len(BaseObject._registry)

    assert after_registry_count == before_registry_count
    assert len(entries) == len(ALL_SPELLS)
    assert set(entries) == {
        metadata.catalog_id
        for metadata in SPELL_CATALOG_METADATA_BY_NAME.values()
    }

    for expected_level, spells in level_buckets.items():
        for display_name in spells:
            catalog_id = SPELL_CATALOG_METADATA_BY_NAME[
                display_name
            ].catalog_id
            entry = entries[catalog_id]
            assert entry.name == display_name
            assert entry.level == expected_level

    for display_name in ("Fire Bolt", "Magic Missile", "Fireball"):
        spell_cls = ALL_SPELLS[display_name]
        spell = spell_cls(
            source_entity_uuid=uuid4(),
            target_entity_uuid=uuid4(),
            use_register=False,
        )
        event = spell._create_declaration_event(use_register=False)

        assert isinstance(event, SpellEvent)
        catalog_id = SPELL_CATALOG_METADATA_BY_NAME[display_name].catalog_id
        assert event.spell_id == entries[catalog_id].id
        assert event.spell_level == entries[catalog_id].level

    magic_missile = entries["magic_missile"]
    fireball = entries["fireball"]

    assert magic_missile.multi_target is not None
    assert magic_missile.multi_target.projectiles_per_cast == 3
    assert magic_missile.vfx is not None
    assert magic_missile.vfx.route_hint == "missile_volley"
    assert tuple(save.ability for save in fireball.saving_throws) == (
        "dexterity",
    )


if __name__ == "__main__":
    tests = [
        test_eb_14_001_spell_slots_are_action_economy_values,
        test_eb_14_002_spellcasting_block_is_modifier_only,
        test_eb_14_003_entity_spell_numbers_compose_from_multiple_blocks,
        test_eb_14_004_spell_actions_create_spell_events_and_slot_costs,
        test_eb_14_005_cantrip_dice_scale_at_srd_thresholds,
        test_eb_14_006_generate_variants_uses_available_slots,
        test_eb_14_007_registered_spells_surface_executable_slot_variants,
        test_eb_14_019_generated_upcast_variant_executes_with_higher_slot,
        test_eb_14_008_magic_missile_convolution_aggregates_child_casts,
        test_eb_14_009_spell_event_damage_types_follow_damage_payloads,
        test_eb_14_010_concentration_links_cleanup_and_empty_casts,
        test_eb_14_011_spell_registration_uses_templates_and_setup_order_matters,
        test_eb_14_012_spell_action_overrides_change_template_costs_not_slot_variant_discovery,
        test_eb_14_013_registered_cantrip_makes_entity_spellcaster,
        test_eb_14_014_drop_concentration_can_target_one_multi_slot_spell,
        test_eb_14_015_damage_and_death_break_concentration_deterministically,
        test_eb_14_016_multi_target_concentration_reuses_one_slot,
        test_eb_14_017_spell_catalog_identity_matches_spell_events,
        test_eb_14_018_spell_range_overrides_affect_discovery_and_clear_cleanly,
    ]

    for test in tests:
        test()
        print(f"{test.__name__}: PASS")
