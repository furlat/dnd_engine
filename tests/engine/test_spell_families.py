"""Engine semantic tests for spell families and implemented spells."""
from dnd.types.materials import Material, TileSurface

from typing import Optional, cast
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from pydantic import Field

from dnd.actions.standard import (
    Attack,
    AttackEvent,
    SpellEvent,
    Swim,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.equipment import (
    Weapon,
)
from dnd.blocks.base_item import BaseItem
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.conditions import Blinded, Concentrating, Exhaustion, Grappled, Paralyzed, Petrified, Poisoned, Restrained, Stunned, Underwater, Unconscious
from dnd.core.base_actions import (
    ActionAvailabilityStatus,
    TargetType,
)
from dnd.core.base_block import BaseBlock
from dnd.types.world import CardinalDirection, LightLevel
from dnd.types.senses import OpticalObscurement, SenseMode, SensesType
from dnd.core.base_conditions import BaseCondition
from dnd.types.conditions import ConditionTag, DurationType
from dnd.core.base_object import BaseObject
from dnd.core.base_tiles import water_factory
from dnd.core.aoe import Sphere
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.types.rolls import AttackOutcome, RollType
from dnd.types.equipment import WeaponSlot
from dnd.types.abilities import AbilityName
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.resolution_events import (
    RangeType,
)
from dnd.core.events.world_events import (
    SpatialEffectChangeEvent,
    SpatialEffectInteractionEvent,
)
from dnd.core.events.action_events import CounterspellReactionEvent
from dnd.core.events.item_events import ItemLocationStateEvent
from dnd.types.items import ItemLocation
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectChangeOperation,
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
)
from dnd.core.gridmap import get_map
from dnd.types.life import LifeState
from dnd.types.creatures import CreatureType
from dnd.types.damage import DamageType
from dnd.types.rolls import AdvantageStatus, AutoHitStatus
from dnd.core.modifiers import NumericalModifier, ResistanceModifier
from dnd.types.damage import ResistanceStatus
from dnd.core.values import BaseValue
from dnd.entities.entity import Entity, EntityConfig
from dnd.actions.operations import execute_by_index, setup_standard_actions
from dnd.items.torches import Torch, WallTorch, build_torch
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_wall_torch
from tests.spell_test_exports import (
    ALL_SPELLS,
    FireBolt,
    Fireball,
    MagicMissile,
    SacredFlame,
)
from dnd.spells.abjuration import (
    BeaconOfHope,
    DeathWard,
    FreedomOfMovement,
    FreedomOfMovementEffect,
    GreaterRestoration,
    LesserRestoration,
    MageArmor,
    ProtectionFromPoison,
    ProtectionFromEnergy,
    RemoveCurse,
    Stoneskin,
    register_counterspell_reaction,
    register_shield_reaction,
)
from dnd.spells.conjuration import (
    Cloudkill,
    Darkness,
    Daylight,
    FogCloud,
    Grease,
    IncendiaryCloud,
    InsectPlague,
    MistyStep,
    SleetStorm,
    SleetStormZone,
    SpiritGuardiansSlowed,
    SpiritGuardiansSlowSource,
    SpiritGuardians,
    StinkingCloud,
    StinkingCloudZone,
    Web,
    WebRestrained,
    WebZone,
    HeroesFeast,
)
from dnd.spells.divination import Guidance, SeeInvisibility
from dnd.spells.evocation import ContinualFlame, CureWounds, GustOfWind, GustOfWindZone, HealingWord, RayOfFrostEffect
from dnd.spells.illusion import ColorSpray, Invisibility, MirrorImage
from dnd.spells.illusion import MirrorImageEffect
from dnd.spells.necromancy import AbilityCurseEffect, BestowCurse, Eyebite, FalseLife, NecroticBless
from dnd.spells.transmutation import EnhanceAbility, EnlargeReduce, Haste, Slow, SlowedEffect, SpikeGrowth
from dnd.spells.enchantment import Bane, Bless, HoldMonster, HoldPerson, PowerWordKill, Sleep
from dnd.spatial.area_conditions import SpatialCondition
from dnd.content.spatial_effect_recipes import (
    BURNING_WEB_FIRE_RECIPE,
    GREASE_SURFACE_RECIPE,
    WEB_SURFACE_RECIPE,
)
from dnd.spatial.area_conditions import AreaCondition
from tests.engine.support import (
    create_test_entity,
    deal_damage_to,
    force_attack_hit,
    force_attack_miss,
    force_spell_attack_hit,
    get_hp,
    get_max_hp,
    remove_attack_modifier,
    reset_combat_state,
    set_hp,
)


def reset_spell_family_state(width: int = 12, height: int = 8) -> None:
    """Clear global state and create a rectangular spell-family test grid."""
    reset_combat_state()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, width, height, surface=TileSurface(base_material=Material.STONE))


def active_spatial_condition(
    condition_name: str,
) -> SpatialCondition:
    """Resolve the one active independent spatial condition by name."""
    matches = [
        condition
        for condition in get_map().get_spatial_conditions()
        if condition.name == condition_name
    ]
    assert len(matches) == 1
    return matches[0]


def create_family_caster(
    name: str = "Caster",
    position: tuple[int, int] = (1, 1),
    spell_slots: Optional[dict[int, int]] = None,
    faction: str = "heroes",
) -> Entity:
    """Create a deterministic caster for spell-family examples."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=18),
            wisdom=AbilityConfig(ability_score=16),
            charisma=AbilityConfig(ability_score=14),
        ),
        action_economy=ActionEconomyConfig(
            spell_slots=spell_slots or {1: 4, 2: 4, 3: 3}
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=6, mode="maximums")]
        ),
        proficiency_bonus=3,
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        position=position,
        faction=faction,
    )
    return create_test_entity(name=name, config=config)


def create_family_target(
    name: str = "Target",
    position: tuple[int, int] = (3, 1),
    faction: str = "monsters",
    hp_dice: int = 8,
    requires_breathing: bool = True,
) -> Entity:
    """Create a durable positioned target."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
            charisma=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=hp_dice, mode="maximums")]
        ),
        proficiency_bonus=2,
        position=position,
        faction=faction,
        requires_breathing=requires_breathing,
    )
    return create_test_entity(name=name, config=config)


def penalize_save(entity: Entity, ability_name: AbilityName, value: int = -100) -> None:
    """Make a save fail deterministically unless the engine applies an auto rule."""
    save = entity.saving_throws.get_saving_throw(ability_name)
    save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=f"Book {ability_name} save penalty",
            value=value,
        )
    )


def boost_save(entity: Entity, ability_name: AbilityName, value: int = 100) -> None:
    """Make a save succeed deterministically unless the engine applies an auto rule."""
    save = entity.saving_throws.get_saving_throw(ability_name)
    save.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=f"Book {ability_name} save boost",
            value=value,
        )
    )


def assert_completed_spell(event: Event | None) -> SpellEvent:
    """Assert a spell application produced an uncanceled completion event."""
    assert isinstance(event, SpellEvent)
    assert not event.canceled, event.status_message
    return event


class LingeringCurseEffect(BaseCondition):
    """Test-only curse condition with no additional gameplay payload."""

    name: str = Field(default="Lingering Curse", description="Condition name.")
    tags: set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.CURSE},
        description="Condition tags used by Remove Curse.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event | None]:
        """Apply the marker curse and return its effect event."""
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Applied Lingering Curse",
        )
        return [], [], [], [], effect_event


class LingeringDiseaseEffect(BaseCondition):
    """Test-only disease condition with no additional gameplay payload."""

    name: str = Field(default="Lingering Disease", description="Condition name.")
    tags: set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.DISEASE},
        description="Condition tags used by Lesser Restoration.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event | None]:
        """Apply the marker disease and return its effect event."""
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Applied Lingering Disease",
        )
        return [], [], [], [], effect_event


class BookPetrifyingEffect(BaseCondition):
    """Test-only petrification effect marker for Greater Restoration parity."""

    name: str = Field(default="Book Petrifying Effect", description="Condition name.")
    tags: set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.PETRIFICATION},
        description="Condition tags used by Greater Restoration.",
    )

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event | None]:
        """Apply the marker petrification effect and return its effect event."""
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Applied Book Petrifying Effect",
        )
        return [], [], [], [], effect_event


class BookAbilityScoreReduction(BaseCondition):
    """Test-only ability score reduction condition for restoration parity."""

    name: str = Field(default="Book Ability Score Reduction", description="Condition name.")
    tags: set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.ABILITY_SCORE_REDUCTION},
        description="Condition tags used by Greater Restoration.",
    )
    ability_name: AbilityName = Field(default="strength", description="Ability score reduced by this condition.")
    penalty: int = Field(default=-4, description="Raw ability score penalty applied by this condition.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event | None]:
        """Apply the ability score penalty and return its effect event."""
        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        ability = target.ability_scores.get_ability(self.ability_name)
        modifier_uuid = ability.ability_score.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid or self.target_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                name="Book ability score reduction",
                value=self.penalty,
            )
        )
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Book Ability Score Reduction to {self.ability_name}",
        )
        return [(ability.ability_score.uuid, modifier_uuid)], [], [], [], effect_event


class BookHitPointMaximumReduction(BaseCondition):
    """Test-only hit point maximum reduction condition for restoration parity."""

    name: str = Field(default="Book Hit Point Maximum Reduction", description="Condition name.")
    tags: set[ConditionTag] = Field(
        default_factory=lambda: {ConditionTag.HIT_POINT_MAXIMUM_REDUCTION},
        description="Condition tags used by Greater Restoration.",
    )
    penalty: int = Field(default=-5, description="Maximum hit point penalty applied by this condition.")

    def _apply(
        self,
        declaration_event: Event,
    ) -> tuple[list[tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event | None]:
        """Apply the hit point maximum penalty and return its effect event."""
        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        modifier_uuid = target.health.max_hit_points_bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid or self.target_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
                name="Book hit point maximum reduction",
                value=self.penalty,
            )
        )
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Applied Book Hit Point Maximum Reduction",
        )
        return [(target.health.max_hit_points_bonus.uuid, modifier_uuid)], [], [], [], effect_event


def run_shield_attack(attacker: Entity, shielded: Entity, d20_result: int) -> AttackEvent:
    """Attack a shielded target with a deterministic d20 roll."""
    with patch("dnd.core.dice.random.randint", return_value=d20_result):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=shielded.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    assert isinstance(event, AttackEvent)
    return event


def fixed_zone_randint(low: int, high: int) -> int:
    """Return deterministic d20 save and zone damage rolls."""
    if high == 20:
        return 10
    return min(max(3, low), high)


def test_eb_15_001_spell_catalog_groups_representative_families() -> None:
    """EB-15-001: the catalog maps implemented spell names to family classes."""
    reset_spell_family_state()

    representatives = {
        "Fire Bolt": (FireBolt, 0, "evocation", TargetType.ENTITY),
        "Magic Missile": (MagicMissile, 1, "evocation", TargetType.MULTI_ENTITY),
        "Fireball": (Fireball, 3, "evocation", TargetType.POSITION_AOE),
        "Mage Armor": (MageArmor, 1, "abjuration", TargetType.ENTITY),
        "Misty Step": (MistyStep, 2, "conjuration", TargetType.POSITION),
        "See Invisibility": (SeeInvisibility, 2, "divination", TargetType.SELF),
        "Bless": (Bless, 1, "enchantment", TargetType.MULTI_ENTITY),
        "Invisibility": (Invisibility, 2, "illusion", TargetType.ENTITY),
        "False Life": (FalseLife, 1, "necromancy", TargetType.SELF),
        "Spike Growth": (SpikeGrowth, 2, "transmutation", TargetType.POSITION),
    }

    for spell_name, (spell_cls, level, school, target_type) in representatives.items():
        spell = ALL_SPELLS[spell_name](source_entity_uuid=uuid4())
        assert ALL_SPELLS[spell_name] is spell_cls
        assert spell.spell_level == level
        assert spell.spell_school == school
        assert spell.target_type == target_type


def test_spell_validation_dispatches_execution_handlers_once() -> None:
    """Spell prerequisites must not repost the accepted execution phase."""
    reset_spell_family_state()
    caster = create_family_caster()
    target = create_family_target(position=(4, 1))
    Entity.materialize_all_navigation()
    execution_calls = 0

    def count_execution(event: Event, _: UUID) -> Event:
        nonlocal execution_calls
        execution_calls += 1
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=caster.uuid,
            name="Count spell execution dispatches",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=caster.uuid,
                )
            ],
            event_processor=count_execution,
        )
    )

    result = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert result.phase is EventPhase.COMPLETION
    assert execution_calls == 1


def test_position_spell_accepts_visible_map_origin() -> None:
    """The valid coordinate ``(0, 0)`` must not be mistaken for no target."""
    reset_spell_family_state()
    caster = create_family_caster(
        position=(1, 0),
        spell_slots={3: 1},
    )
    Entity.materialize_all_navigation()
    spell = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(0, 0),
        template=False,
    )
    declaration = spell._create_declaration_event(use_register=False)

    assert isinstance(declaration, SpellEvent)
    validated = spell._validate(declaration)

    assert isinstance(validated, SpellEvent)
    assert validated.canceled is False
    assert validated.phase is EventPhase.EXECUTION


def test_spell_save_updates_do_not_redispatch_effect_handlers() -> None:
    """Save results update the current spell effect without publishing it twice."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 1})
    target = create_family_target(position=(3, 1))
    Entity.materialize_all_navigation()
    penalize_save(target, "wisdom")
    effect_calls = 0

    def count_effect(event: Event, _: UUID) -> Event:
        nonlocal effect_calls
        effect_calls += 1
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=caster.uuid,
            name="Count spell effect dispatches",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster.uuid,
                )
            ],
            event_processor=count_effect,
        )
    )

    result = HoldPerson(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert result.phase is EventPhase.COMPLETION
    assert effect_calls == 1


def test_eb_15_002_evocation_attack_save_and_area_damage_patterns() -> None:
    """EB-15-002: evocation covers spell attacks, save cantrips, and AoE saves."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={3: 1})
    target = create_family_target(position=(4, 1))
    Entity.materialize_all_navigation()

    force_spell_attack_hit(caster)
    fire_bolt_hp = get_hp(target)
    fire_bolt_event = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False,
    ).apply()

    fire_bolt_event = assert_completed_spell(fire_bolt_event)
    assert DamageType.FIRE in fire_bolt_event.damage_types
    assert fire_bolt_event.damage_rolls is not None
    assert fire_bolt_event.damage_rolls[0].total > 0
    assert get_hp(target) == fire_bolt_hp - fire_bolt_event.damage_rolls[0].total

    caster.action_economy.reset_all_costs()
    penalize_save(target, "dexterity")
    sacred_hp = get_hp(target)
    sacred_event = SacredFlame(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False,
    ).apply()

    sacred_event = assert_completed_spell(sacred_event)
    assert sacred_event.save_ability == "dexterity"
    assert sacred_event.save_success is False
    assert DamageType.RADIANT in sacred_event.damage_types
    assert get_hp(target) == sacred_hp - sacred_event.total_damage

    caster.action_economy.reset_all_costs()
    area_target = create_family_target(name="Area Target", position=(7, 1))
    penalize_save(area_target, "dexterity")
    Entity.materialize_all_navigation()
    area_hp = get_hp(area_target)
    fireball_event = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=area_target.position,
        template=False,
    ).apply()

    fireball_event = assert_completed_spell(fireball_event)
    assert fireball_event.total_targets >= 1
    assert fireball_event.total_damage > 0
    assert get_hp(area_target) < area_hp
    assert caster.action_economy.spell_slot_3.normalized_score == 0


def test_eb_15_003_auto_hit_and_healing_spell_patterns() -> None:
    """EB-15-003: auto-hit damage and healing both use spell events."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 3})
    target = create_family_target(position=(3, 1))
    ally = create_family_target(
        name="Ally",
        position=(2, 1),
        faction="heroes",
        hp_dice=4,
    )
    Entity.materialize_all_navigation()

    missile_hp = get_hp(target)
    missile_event = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    missile_event = assert_completed_spell(missile_event)
    assert missile_event.total_targets == 3
    assert DamageType.FORCE in missile_event.damage_types
    assert get_hp(target) == missile_hp - missile_event.total_damage

    caster.action_economy.reset_all_costs()
    set_hp(ally, 1)
    wounded_hp = get_hp(ally)
    cure_event = CureWounds(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    cure_event = assert_completed_spell(cure_event)
    assert get_hp(ally) > wounded_hp
    assert caster.action_economy.actions.normalized_score == 0

    caster.action_economy.reset_all_costs()
    set_hp(ally, 1)
    low_hp = get_hp(ally)
    word_event = HealingWord(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    word_event = assert_completed_spell(word_event)
    assert get_hp(ally) > low_hp
    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0


def test_eb_15_004_abjuration_buffs_and_restoration_remove_conditions() -> None:
    """EB-15-004: abjuration includes protective buffs and condition removal."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 1, 2: 1})
    Entity.materialize_all_navigation()

    base_ac = caster.equipment.ac_bonus.normalized_score
    mage_armor_event = MageArmor(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    mage_armor_event = assert_completed_spell(mage_armor_event)
    assert "Mage Armor" in caster.active_conditions
    assert caster.equipment.ac_bonus.normalized_score >= base_ac

    caster.action_economy.reset_all_costs()
    poison = Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid)
    caster.add_condition(poison)
    assert "Poisoned" in caster.active_conditions

    restore_event = LesserRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    restore_event = assert_completed_spell(restore_event)
    assert "Poisoned" not in caster.active_conditions
    assert caster.action_economy.spell_slot_2.normalized_score == 0


def test_eb_15_023_restoration_spells_remove_supported_effects_only() -> None:
    """EB-15-023: restoration spells remove supported effects and preserve others."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 2, 3: 1, 5: 2})
    ally = create_family_target(name="Restoration Ally", position=(2, 1), faction="heroes")
    Entity.materialize_all_navigation()

    ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    ally.add_condition(LingeringDiseaseEffect(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    ally.add_condition(Stunned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))

    assert "Poisoned" in ally.active_conditions
    assert "Lingering Disease" in ally.active_conditions
    assert "Stunned" in ally.active_conditions
    assert "Incapacitated" not in ally.active_conditions
    assert ally.action_economy.action_permission.normalized_score == 0

    lesser_event = LesserRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    lesser_event = assert_completed_spell(lesser_event)
    assert "Poisoned" not in ally.active_conditions
    assert "Lingering Disease" in ally.active_conditions
    assert "Stunned" in ally.active_conditions
    assert "Incapacitated" not in ally.active_conditions
    assert ally.action_economy.action_permission.normalized_score == 0
    assert caster.action_economy.spell_slot_2.normalized_score == 1

    caster.action_economy.reset_all_costs()
    lesser_disease_event = LesserRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    lesser_disease_event = assert_completed_spell(lesser_disease_event)
    assert "Lingering Disease" not in ally.active_conditions
    assert "Stunned" in ally.active_conditions
    assert "Incapacitated" not in ally.active_conditions
    assert ally.action_economy.action_permission.normalized_score == 0
    assert caster.action_economy.spell_slot_2.normalized_score == 0

    caster.action_economy.reset_all_costs()
    greater_event = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    greater_event = assert_completed_spell(greater_event)
    assert "Stunned" not in ally.active_conditions
    assert "Incapacitated" not in ally.active_conditions
    assert ally.action_economy.action_permission.normalized_score == 1
    assert caster.action_economy.spell_slot_5.normalized_score == 1

    caster.action_economy.reset_all_costs()
    ally.add_condition(
        AbilityCurseEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            cursed_ability="strength",
        )
    )
    ally.add_condition(
        LingeringCurseEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
        )
    )

    assert "Bestow Curse" in ally.active_conditions
    assert "Lingering Curse" in ally.active_conditions

    greater_curse_event = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    greater_curse_event = assert_completed_spell(greater_curse_event)
    assert "Bestow Curse" not in ally.active_conditions
    assert "Lingering Curse" in ally.active_conditions
    assert caster.action_economy.spell_slot_5.normalized_score == 0

    caster.action_economy.reset_all_costs()
    ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    ally.add_condition(
        AbilityCurseEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            cursed_ability="strength",
        )
    )

    assert "Poisoned" in ally.active_conditions
    assert "Bestow Curse" in ally.active_conditions
    assert "Lingering Curse" in ally.active_conditions

    remove_curse_event = RemoveCurse(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    remove_curse_event = assert_completed_spell(remove_curse_event)
    assert "Bestow Curse" not in ally.active_conditions
    assert "Lingering Curse" not in ally.active_conditions
    assert "Poisoned" in ally.active_conditions
    assert caster.action_economy.spell_slot_3.normalized_score == 0


def test_eb_15_038_greater_restoration_removes_srd_tagged_effect_surfaces() -> None:
    """EB-15-038: Greater Restoration removes SRD-tagged effect surfaces."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={5: 3})
    ally = create_family_target(name="Restoration Ally", position=(2, 1), faction="heroes")
    Entity.materialize_all_navigation()

    base_strength_score = ally.ability_scores.strength.ability_score.score
    base_max_hp = get_max_hp(ally)
    ally.add_condition(
        BookPetrifyingEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
        )
    )
    ally.add_condition(
        BookAbilityScoreReduction(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            ability_name="strength",
            penalty=-4,
        )
    )
    ally.add_condition(
        BookHitPointMaximumReduction(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            penalty=-5,
        )
    )

    assert "Book Petrifying Effect" in ally.active_conditions
    assert "Book Ability Score Reduction" in ally.active_conditions
    assert "Book Hit Point Maximum Reduction" in ally.active_conditions
    assert ally.ability_scores.strength.ability_score.score == base_strength_score - 4
    assert get_max_hp(ally) == base_max_hp - 5

    petrification_event = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    petrification_event = assert_completed_spell(petrification_event)
    assert "Book Petrifying Effect" not in ally.active_conditions
    assert "Book Ability Score Reduction" in ally.active_conditions
    assert "Book Hit Point Maximum Reduction" in ally.active_conditions
    assert caster.action_economy.spell_slot_5.normalized_score == 2

    caster.action_economy.reset_all_costs()
    ability_event = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    ability_event = assert_completed_spell(ability_event)
    assert "Book Ability Score Reduction" not in ally.active_conditions
    assert "Book Hit Point Maximum Reduction" in ally.active_conditions
    assert ally.ability_scores.strength.ability_score.score == base_strength_score
    assert get_max_hp(ally) == base_max_hp - 5
    assert caster.action_economy.spell_slot_5.normalized_score == 1

    caster.action_economy.reset_all_costs()
    hp_max_event = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    hp_max_event = assert_completed_spell(hp_max_event)
    assert "Book Hit Point Maximum Reduction" not in ally.active_conditions
    assert get_max_hp(ally) == base_max_hp
    assert caster.action_economy.spell_slot_5.normalized_score == 0


def test_eb_15_039_greater_restoration_removes_standard_petrified_condition() -> None:
    """EB-15-039: Greater Restoration removes standard Petrified state."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={5: 1})
    ally = create_family_target(name="Petrified Ally", position=(2, 1), faction="heroes")
    Entity.materialize_all_navigation()

    ally.add_condition(
        Petrified(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
        )
    )

    assert "Petrified" in ally.active_conditions
    assert "Incapacitated" not in ally.active_conditions
    assert ally.action_economy.action_permission.normalized_score == 0
    assert ally.check_condition_immunity("Poisoned")
    for damage_type in DamageType:
        assert ally.health.get_resistance(damage_type) == ResistanceStatus.RESISTANCE

    restoration_event = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    restoration_event = assert_completed_spell(restoration_event)
    assert "Petrified" not in ally.active_conditions
    assert "Incapacitated" not in ally.active_conditions
    assert ally.action_economy.action_permission.normalized_score == 1
    assert not ally.check_condition_immunity("Poisoned")
    for damage_type in DamageType:
        assert ally.health.get_resistance(damage_type) == ResistanceStatus.NONE
    assert caster.action_economy.spell_slot_5.normalized_score == 0


def test_eb_15_040_greater_restoration_reduces_exhaustion_one_level() -> None:
    """EB-15-040: Greater Restoration reduces Exhaustion by one level."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={5: 3})
    ally = create_family_target(name="Exhausted Ally", position=(2, 1), faction="heroes")
    Entity.materialize_all_navigation()
    base_movement = ally.action_economy.movement.normalized_score

    ally.add_condition(
        Exhaustion(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            level=3,
        )
    )

    active_exhaustion = ally.active_conditions["Exhaustion"]
    assert isinstance(active_exhaustion, Exhaustion)
    assert active_exhaustion.level == 3
    assert ally.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert ally.action_economy.movement.normalized_score == base_movement // 2
    assert ally.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert (
        ally.saving_throws.get_saving_throw("wisdom").bonus.advantage
        == AdvantageStatus.DISADVANTAGE
    )

    level_two_event = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    level_two_event = assert_completed_spell(level_two_event)
    active_exhaustion = ally.active_conditions["Exhaustion"]
    assert isinstance(active_exhaustion, Exhaustion)
    assert active_exhaustion.level == 2
    assert ally.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert ally.action_economy.movement.normalized_score == base_movement // 2
    assert ally.equipment.attack_bonus.advantage == AdvantageStatus.NONE
    assert ally.saving_throws.get_saving_throw("wisdom").bonus.advantage == AdvantageStatus.NONE
    assert caster.action_economy.spell_slot_5.normalized_score == 2

    caster.action_economy.reset_all_costs()
    level_one_event = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    level_one_event = assert_completed_spell(level_one_event)
    active_exhaustion = ally.active_conditions["Exhaustion"]
    assert isinstance(active_exhaustion, Exhaustion)
    assert active_exhaustion.level == 1
    assert ally.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert ally.action_economy.movement.normalized_score == base_movement
    assert caster.action_economy.spell_slot_5.normalized_score == 1

    caster.action_economy.reset_all_costs()
    removed_event = GreaterRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    removed_event = assert_completed_spell(removed_event)
    assert "Exhaustion" not in ally.active_conditions
    assert ally.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.NONE
    assert ally.action_economy.movement.normalized_score == base_movement
    assert caster.action_economy.spell_slot_5.normalized_score == 0


def test_eb_15_025_protective_abjurations_prevent_and_absorb_effects() -> None:
    """EB-15-025: protective abjurations prevent, absorb, and clean up effects."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 1, 4: 3, 9: 2})
    ally = create_family_target(name="Protected Ally", position=(2, 1), faction="heroes")
    doomed = create_family_target(name="Doomed Target", position=(3, 1), faction="monsters")
    setup_standard_actions(doomed)
    Entity.materialize_all_navigation()

    ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Poisoned" in ally.active_conditions

    poison_event = ProtectionFromPoison(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    poison_event = assert_completed_spell(poison_event)
    assert "Protection from Poison" in ally.active_conditions
    assert "Concentrating" not in caster.active_conditions
    assert caster.action_economy.spell_slot_2.normalized_score == 0
    assert "Poisoned" not in ally.active_conditions

    hp_before_poison = get_hp(ally)
    poison_damage = deal_damage_to(
        ally,
        20,
        damage_type=DamageType.POISON,
        source_uuid=caster.uuid,
    )
    assert poison_damage == 10
    assert get_hp(ally) == hp_before_poison - 10

    hp_before_slashing = get_hp(ally)
    slashing_damage = deal_damage_to(
        ally,
        20,
        damage_type=DamageType.SLASHING,
        source_uuid=caster.uuid,
    )
    assert slashing_damage == 20
    assert get_hp(ally) == hp_before_slashing - 20

    ordinary_save_request = caster.create_saving_throw_request(
        target_entity_uuid=ally.uuid,
        ability_name="constitution",
        dc=10,
    )
    _, ordinary_save_roll, _ = ally.saving_throw(ordinary_save_request)
    assert ordinary_save_roll.advantage_status == AdvantageStatus.NONE

    poison_save_request = caster.create_saving_throw_request(
        target_entity_uuid=ally.uuid,
        ability_name="constitution",
        dc=10,
        condition_context="Poisoned",
    )
    _, poison_save_roll, _ = ally.saving_throw(poison_save_request)
    assert poison_save_roll.advantage_status == AdvantageStatus.ADVANTAGE

    ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Poisoned" not in ally.active_conditions

    ally.remove_condition("Protection from Poison")
    ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Poisoned" in ally.active_conditions
    post_protection_save_request = caster.create_saving_throw_request(
        target_entity_uuid=ally.uuid,
        ability_name="constitution",
        dc=10,
        condition_context="Poisoned",
    )
    _, post_protection_save_roll, _ = ally.saving_throw(post_protection_save_request)
    assert post_protection_save_roll.advantage_status == AdvantageStatus.NONE
    ally.remove_condition("Poisoned")

    caster.action_economy.reset_all_costs()
    ward_event = DeathWard(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    ward_event = assert_completed_spell(ward_event)
    assert "Death Ward" in ally.active_conditions
    assert ally.get_event_handler_by_name("Death Ward") is not None
    assert caster.action_economy.spell_slot_4.normalized_score == 2

    set_hp(ally, 10)
    warded_damage = deal_damage_to(
        ally,
        50,
        damage_type=DamageType.SLASHING,
        source_uuid=caster.uuid,
    )
    assert warded_damage == 9
    assert get_hp(ally) == 1
    assert "Death Ward" not in ally.active_conditions
    assert ally.get_event_handler_by_name("Death Ward") is None

    caster.action_economy.reset_all_costs()
    set_hp(ally, 50)
    second_ward_event = DeathWard(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()
    second_ward_event = assert_completed_spell(second_ward_event)
    assert "Death Ward" in ally.active_conditions
    assert caster.action_economy.spell_slot_4.normalized_score == 1

    caster.action_economy.reset_all_costs()
    warded_kill_event = PowerWordKill(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()
    warded_kill_event = assert_completed_spell(warded_kill_event)
    assert "Death Ward" not in ally.active_conditions
    assert get_hp(ally) == 50
    assert ally.health.life_state is LifeState.ALIVE
    assert caster.action_economy.spell_slot_9.normalized_score == 1

    caster.action_economy.reset_all_costs()
    set_hp(doomed, 50)
    unwarded_kill_event = PowerWordKill(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=doomed.uuid,
        template=False,
    ).apply()
    unwarded_kill_event = assert_completed_spell(unwarded_kill_event)
    assert get_hp(doomed) == 0
    assert doomed.health.life_state is LifeState.DEAD
    assert caster.action_economy.spell_slot_9.normalized_score == 0

    caster.action_economy.reset_all_costs()
    ally.add_condition(Grappled(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    ally.add_condition(Restrained(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Grappled" in ally.active_conditions
    assert "Restrained" in ally.active_conditions
    assert ally.action_economy.movement.normalized_score == 0

    movement_event = FreedomOfMovement(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    movement_event = assert_completed_spell(movement_event)
    assert "Freedom of Movement" in ally.active_conditions
    assert ally.ignore_difficult_terrain
    assert ally.ignore_magical_speed_reduction
    assert caster.action_economy.spell_slot_4.normalized_score == 0
    assert "Grappled" in ally.active_conditions
    assert "Restrained" in ally.active_conditions

    first_mobility_source = ally.active_conditions["Freedom of Movement"]
    replacement_mobility_source = FreedomOfMovementEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    )
    ally.add_condition(replacement_mobility_source)
    assert (
        ally.active_conditions["Freedom of Movement"]
        is replacement_mobility_source
    )
    assert BaseCondition.get(first_mobility_source.uuid) is None
    assert ally.ignore_difficult_terrain
    assert ally.ignore_magical_speed_reduction
    assert ally.ignore_underwater_penalties

    available_escape_actions = ally.get_available_actions()
    escape_action_info = next(
        action for action in available_escape_actions.self_actions
        if action.template_name == "Freedom of Movement Escape"
    )
    assert escape_action_info.can_afford
    assert len(escape_action_info.valid_targets) == 1

    escape_event = execute_by_index(
        ally,
        "Freedom of Movement Escape",
        0,
        available=available_escape_actions,
    )
    assert escape_event is not None
    assert not escape_event.canceled
    assert escape_event.phase == EventPhase.COMPLETION
    assert "Grappled" not in ally.active_conditions
    assert "Restrained" not in ally.active_conditions
    assert ally.action_economy.movement.normalized_score == 25
    ally.action_economy.reset_all_costs()

    ally.equipment.equip(
        cast(Weapon, build_authored_item("weapon.longbow", ally.uuid)),
        WeaponSlot.RANGED_MAIN,
    )
    ally.add_condition(Underwater(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Underwater" in ally.active_conditions
    assert ally.ignore_underwater_penalties
    ranged_underwater_context = {
        "weapon_slot": WeaponSlot.RANGED_MAIN.value,
        "weapon_name": "Longbow",
        "range_type": RangeType.RANGE.value,
        "is_long_range": True,
    }
    protected_ranged_attack = ally.attack_bonus(WeaponSlot.RANGED_MAIN, caster.uuid)
    protected_ranged_attack.set_context(ranged_underwater_context)
    assert protected_ranged_attack.advantage == AdvantageStatus.NONE
    assert protected_ranged_attack.auto_hit == AutoHitStatus.NONE
    protected_ranged_attack.clear_context()

    water_lane = [(8, 1), (9, 1), (10, 1)]
    grid = get_map()
    for position in water_lane:
        grid.set_tile(position[0], position[1], tile=water_factory(position), fire_event=False)

    Entity.update_entity_position(ally, water_lane[0])
    ally.materialize_navigation(max_distance=20)
    swim_template = Swim(source_entity_uuid=ally.uuid, template=True)
    ally.register_action(swim_template)
    available_swims = ally.get_available_actions()
    swim_info = next(action for action in available_swims.position_actions if action.template_name == "Swim")
    assert any(target.position == water_lane[-1] and target.path_cost == 10 for target in swim_info.valid_targets)
    ally.unregister_action_by_uuid(swim_template.uuid)
    ally.action_economy.reset_all_costs()
    protected_swim = Swim(source_entity_uuid=ally.uuid, end_position=water_lane[-1]).apply()
    protected_swim = cast(Event, protected_swim)
    assert protected_swim.phase == EventPhase.COMPLETION
    assert not protected_swim.canceled
    assert ally.position == water_lane[-1]
    assert ally.action_economy.movement.normalized_score == 20
    Entity.update_entity_position(ally, water_lane[0])
    ally.action_economy.reset_all_costs()

    protected_speed = ally.action_economy.movement.normalized_score
    protected_ac = ally.ac_bonus().normalized_score
    ally.add_condition(SlowedEffect(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Slowed" in ally.active_conditions
    assert ally.action_economy.movement.normalized_score == protected_speed
    assert ally.ac_bonus().normalized_score == protected_ac - 2
    ally.remove_condition("Slowed")

    ally.add_condition(SpiritGuardiansSlowed(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Spirit Guardians Slowed" not in ally.active_conditions
    assert ally.action_economy.movement.normalized_score == protected_speed

    caster.add_condition(
        RayOfFrostEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            affected_target_uuid=ally.uuid,
        )
    )
    assert "Ray of Frost Effect" not in caster.active_conditions
    assert ally.action_economy.movement.normalized_score == protected_speed

    ally.add_condition(Grappled(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    ally.add_condition(Restrained(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Grappled" in ally.active_conditions
    assert "Restrained" in ally.active_conditions
    ally.remove_condition("Grappled")
    ally.remove_condition("Restrained")

    ally.add_condition(
        Grappled(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            tags={ConditionTag.MAGICAL},
        )
    )
    ally.add_condition(
        Restrained(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            tags={ConditionTag.MAGICAL},
        )
    )
    assert "Grappled" not in ally.active_conditions
    assert "Restrained" not in ally.active_conditions
    ally.add_condition(
        Paralyzed(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            tags={ConditionTag.MAGICAL},
        )
    )
    assert "Paralyzed" not in ally.active_conditions

    ally.add_condition(Paralyzed(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Paralyzed" in ally.active_conditions
    ally.remove_condition("Paralyzed")

    ally.remove_condition("Freedom of Movement")
    assert not ally.ignore_difficult_terrain
    assert not ally.ignore_magical_speed_reduction
    assert not ally.ignore_underwater_penalties
    assert ally.get_action_template("Freedom of Movement Escape") is None

    unprotected_ranged_attack = ally.attack_bonus(WeaponSlot.RANGED_MAIN, caster.uuid)
    unprotected_ranged_attack.set_context(ranged_underwater_context)
    assert unprotected_ranged_attack.advantage == AdvantageStatus.DISADVANTAGE
    assert unprotected_ranged_attack.auto_hit == AutoHitStatus.AUTOMISS
    unprotected_ranged_attack.clear_context()

    ally.equipment.equip(
        cast(Weapon, build_authored_item("weapon.club", ally.uuid)),
        WeaponSlot.MELEE_MAIN,
    )
    melee_underwater_context = {
        "weapon_slot": WeaponSlot.MELEE_MAIN.value,
        "weapon_name": "Club",
        "range_type": RangeType.REACH.value,
        "is_long_range": False,
    }
    unprotected_melee_attack = ally.attack_bonus(WeaponSlot.MELEE_MAIN, caster.uuid)
    unprotected_melee_attack.set_context(melee_underwater_context)
    assert unprotected_melee_attack.advantage == AdvantageStatus.DISADVANTAGE
    unprotected_melee_attack.clear_context()

    ally.swimming_speed = 30
    swimming_melee_attack = ally.attack_bonus(WeaponSlot.MELEE_MAIN, caster.uuid)
    swimming_melee_attack.set_context(melee_underwater_context)
    assert swimming_melee_attack.advantage == AdvantageStatus.NONE
    swimming_melee_attack.clear_context()
    ally.swimming_speed = 0

    unprotected_swim = Swim(source_entity_uuid=ally.uuid, end_position=water_lane[-1]).apply()
    unprotected_swim = cast(Event, unprotected_swim)
    assert unprotected_swim.phase == EventPhase.COMPLETION
    assert not unprotected_swim.canceled
    assert ally.position == water_lane[-1]
    assert ally.action_economy.movement.normalized_score == 10
    ally.action_economy.reset_all_costs()
    ally.remove_condition("Underwater")

    unprotected_speed = ally.action_economy.movement.normalized_score
    ally.add_condition(SlowedEffect(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Slowed" in ally.active_conditions
    assert ally.action_economy.movement.normalized_score == unprotected_speed // 2
    ally.remove_condition("Slowed")

    ally.add_condition(SpiritGuardiansSlowed(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Spirit Guardians Slowed" in ally.active_conditions
    assert ally.action_economy.movement.normalized_score == unprotected_speed // 2
    ally.remove_condition("Spirit Guardians Slowed")

    caster.add_condition(
        RayOfFrostEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            affected_target_uuid=ally.uuid,
        )
    )
    assert "Ray of Frost Effect" in caster.active_conditions
    assert ally.action_economy.movement.normalized_score == unprotected_speed - 10
    caster.remove_condition("Ray of Frost Effect")

    ally.add_condition(Grappled(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    ally.add_condition(Restrained(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
    assert "Grappled" in ally.active_conditions
    assert "Restrained" in ally.active_conditions
    ally.add_condition(
        Paralyzed(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
            tags={ConditionTag.MAGICAL},
        )
    )
    assert "Paralyzed" in ally.active_conditions


def test_eb_15_009_shield_reaction_converts_marginal_attack_hit_to_miss() -> None:
    """EB-15-009: Shield reacts after a hit roll only when +5 AC can stop it."""
    reset_spell_family_state()
    shielded = create_family_caster(
        name="Shielded Mage",
        position=(1, 1),
        spell_slots={1: 1},
        faction="heroes",
    )
    attacker = create_family_target(
        name="Attacker",
        position=(1, 2),
        faction="monsters",
    )
    register_shield_reaction(shielded)
    Entity.materialize_all_navigation()
    ac_before = shielded.ac_bonus().normalized_score

    attack_event = run_shield_attack(attacker, shielded, 10)

    assert attack_event.attack_outcome == AttackOutcome.MISS
    assert attack_event.dice_roll is not None
    assert attack_event.dice_roll.total == ac_before
    assert "Shield" in shielded.active_conditions
    assert shielded.equipment.ac_bonus.normalized_score == 5
    assert shielded.action_economy.reactions.normalized_score == 0
    assert shielded.action_economy.spell_slot_1.normalized_score == 0


def test_eb_15_010_shield_blocks_magic_missile_darts_against_its_target_only() -> None:
    """EB-15-010: Shield blocks Magic Missile damage on the shielded target."""
    reset_spell_family_state()
    shielded = create_family_caster(
        name="Shielded Mage",
        position=(1, 1),
        spell_slots={1: 1},
        faction="heroes",
    )
    ally = create_family_target(
        name="Ally",
        position=(2, 1),
        faction="heroes",
    )
    attacker = create_family_caster(
        name="Missile Caster",
        position=(1, 5),
        spell_slots={1: 1},
        faction="monsters",
    )
    register_shield_reaction(shielded)
    Entity.materialize_all_navigation(max_distance=20)
    shielded_hp = get_hp(shielded)
    ally_hp = get_hp(ally)

    event = MagicMissile(
        name="Opaque Force Darts",
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=shielded.uuid,
        extra_target_entity_uuids=[ally.uuid],
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    assert event.total_targets == 3
    assert event.total_damage > 0
    assert get_hp(shielded) == shielded_hp
    assert get_hp(ally) < ally_hp
    assert "Shield" in shielded.active_conditions
    assert shielded.action_economy.reactions.normalized_score == 0
    assert shielded.action_economy.spell_slot_1.normalized_score == 0
    assert attacker.action_economy.spell_slot_1.normalized_score == 0


def test_eb_15_020_shield_non_firing_persistence_and_turn_cleanup() -> None:
    """EB-15-020: Shield saves resources unless useful and cleans up at turn start."""

    def setup_pair(spell_slots: Optional[dict[int, int]] = None) -> tuple[Entity, Entity]:
        reset_spell_family_state()
        shielded = create_family_caster(
            name="Shielded Mage",
            position=(1, 1),
            spell_slots=spell_slots or {1: 1},
            faction="heroes",
        )
        attacker = create_family_target(
            name="Attacker",
            position=(1, 2),
            faction="monsters",
        )
        register_shield_reaction(shielded)
        Entity.materialize_all_navigation()
        return shielded, attacker

    for d20_result, expected_outcome in (
        (20, AttackOutcome.CRIT),
        (5, AttackOutcome.MISS),
        (15, AttackOutcome.HIT),
    ):
        shielded, attacker = setup_pair()
        base_ac_bonus = shielded.equipment.ac_bonus.normalized_score
        reactions_before = shielded.action_economy.reactions.normalized_score
        slots_before = shielded.action_economy.spell_slot_1.normalized_score

        event = run_shield_attack(attacker, shielded, d20_result)

        assert event.attack_outcome == expected_outcome
        assert "Shield" not in shielded.active_conditions
        assert shielded.equipment.ac_bonus.normalized_score == base_ac_bonus
        assert shielded.action_economy.reactions.normalized_score == reactions_before
        assert shielded.action_economy.spell_slot_1.normalized_score == slots_before

    shielded, attacker = setup_pair()
    shielded.action_economy.consume("reactions", 1)
    no_reaction_event = run_shield_attack(attacker, shielded, 10)
    assert no_reaction_event.attack_outcome == AttackOutcome.HIT
    assert "Shield" not in shielded.active_conditions
    assert shielded.action_economy.reactions.normalized_score == 0
    assert shielded.action_economy.spell_slot_1.normalized_score == 1

    shielded, attacker = setup_pair(spell_slots={1: 0})
    no_slot_event = run_shield_attack(attacker, shielded, 10)
    assert no_slot_event.attack_outcome == AttackOutcome.HIT
    assert "Shield" not in shielded.active_conditions
    assert shielded.action_economy.reactions.normalized_score == 1
    assert shielded.action_economy.spell_slot_1.normalized_score == 0

    shielded, attacker = setup_pair(spell_slots={1: 2})
    base_ac_bonus = shielded.equipment.ac_bonus.normalized_score
    first_event = run_shield_attack(attacker, shielded, 10)
    assert first_event.attack_outcome == AttackOutcome.MISS
    assert "Shield" in shielded.active_conditions
    assert shielded.equipment.ac_bonus.normalized_score == base_ac_bonus + 5
    assert shielded.action_economy.reactions.normalized_score == 0
    assert shielded.action_economy.spell_slot_1.normalized_score == 1
    assert shielded.get_event_handler_by_name("Shield: Magic Missile Block") is not None
    assert shielded.get_event_handler_by_name("Shield: Turn Start Removal") is not None

    attacker.action_economy.reset_all_costs()
    second_event = run_shield_attack(attacker, shielded, 10)
    assert second_event.attack_outcome == AttackOutcome.MISS
    assert "Shield" in shielded.active_conditions
    assert shielded.equipment.ac_bonus.normalized_score == base_ac_bonus + 5
    assert shielded.action_economy.reactions.normalized_score == 0
    assert shielded.action_economy.spell_slot_1.normalized_score == 1

    turn_start = shielded.on_turn_start(round_number=2, turn_index=0)
    assert turn_start.phase == EventPhase.COMPLETION
    assert "Shield" not in shielded.active_conditions
    assert shielded.equipment.ac_bonus.normalized_score == base_ac_bonus
    assert shielded.action_economy.reactions.normalized_score == 1
    assert shielded.action_economy.spell_slot_1.normalized_score == 1
    assert shielded.get_event_handler_by_name("Shield") is not None
    assert shielded.get_event_handler_by_name("Shield: Magic Missile Block") is None
    assert shielded.get_event_handler_by_name("Shield: Turn Start Removal") is None


def test_eb_15_022_shield_handler_toggle_gates_attack_and_missile_reactions() -> None:
    """EB-15-022: Shield's player-toggleable handler gates both trigger paths."""
    reset_spell_family_state()
    shielded = create_family_caster(
        name="Shielded Mage",
        position=(1, 1),
        spell_slots={1: 2},
        faction="heroes",
    )
    attacker = create_family_target(
        name="Attacker",
        position=(1, 2),
        faction="monsters",
    )
    register_shield_reaction(shielded)
    Entity.materialize_all_navigation()

    shield_handler = shielded.get_event_handler_by_name("Shield")
    assert shield_handler is not None and shield_handler.enabled
    assert shielded.set_handler_enabled_by_uuid(shield_handler.uuid, False)
    assert not shield_handler.enabled

    reactions_before = shielded.action_economy.reactions.normalized_score
    slots_before = shielded.action_economy.spell_slot_1.normalized_score

    disabled_attack = run_shield_attack(attacker, shielded, 10)

    assert disabled_attack.attack_outcome == AttackOutcome.HIT
    assert "Shield" not in shielded.active_conditions
    assert shielded.action_economy.reactions.normalized_score == reactions_before
    assert shielded.action_economy.spell_slot_1.normalized_score == slots_before

    attacker.action_economy.reset_all_costs()
    assert shielded.set_handler_enabled_by_uuid(shield_handler.uuid, True)
    assert shield_handler.enabled

    enabled_attack = run_shield_attack(attacker, shielded, 10)

    assert enabled_attack.attack_outcome == AttackOutcome.MISS
    assert "Shield" in shielded.active_conditions
    assert shielded.action_economy.reactions.normalized_score == reactions_before - 1
    assert shielded.action_economy.spell_slot_1.normalized_score == slots_before - 1

    reset_spell_family_state()
    shielded = create_family_caster(
        name="Shielded Mage",
        position=(1, 1),
        spell_slots={1: 1},
        faction="heroes",
    )
    missile_caster = create_family_caster(
        name="Missile Caster",
        position=(1, 5),
        spell_slots={1: 1},
        faction="monsters",
    )
    register_shield_reaction(shielded)
    Entity.materialize_all_navigation(max_distance=20)
    missile_shield_handler = shielded.get_event_handler_by_name("Shield")
    assert missile_shield_handler is not None
    assert shielded.set_handler_enabled_by_uuid(
        missile_shield_handler.uuid,
        False,
    )

    hp_before = get_hp(shielded)
    reactions_before = shielded.action_economy.reactions.normalized_score
    slots_before = shielded.action_economy.spell_slot_1.normalized_score

    missile_event = MagicMissile(
        source_entity_uuid=missile_caster.uuid,
        target_entity_uuid=shielded.uuid,
        template=False,
    ).apply()

    missile_event = assert_completed_spell(missile_event)
    assert get_hp(shielded) < hp_before
    assert "Shield" not in shielded.active_conditions
    assert shielded.action_economy.reactions.normalized_score == reactions_before
    assert shielded.action_economy.spell_slot_1.normalized_score == slots_before


def test_eb_15_036_shield_condition_log_nests_under_triggering_attack() -> None:
    """EB-15-036: Shield's condition application logs under its parent attack."""
    reset_spell_family_state()
    shielded = create_family_caster(
        name="Shielded Mage",
        position=(1, 1),
        spell_slots={1: 1},
        faction="heroes",
    )
    attacker = create_family_target(
        name="Attacker",
        position=(1, 2),
        faction="monsters",
    )
    register_shield_reaction(shielded)
    Entity.materialize_all_navigation()

    attack_event = run_shield_attack(attacker, shielded, 10)

    assert attack_event.attack_outcome == AttackOutcome.MISS
    assert attack_event.combat_log is not None
    assert attack_event.combat_log.entry_type == CombatLogEntryType.ATTACK
    assert [entry.entry_type for entry in [attack_event.combat_log]] == [
        CombatLogEntryType.ATTACK,
    ]

    shield_logs = [
        entry for entry in attack_event.combat_log.sub_entries
        if entry.entry_type == CombatLogEntryType.CONDITION_APPLIED
        and entry.target_uuid == str(shielded.uuid)
        and "Shield" in entry.compact
    ]
    assert len(shield_logs) == 1
    assert shield_logs[0].source_uuid == str(shielded.uuid)
    assert shield_logs[0].target_uuid == str(shielded.uuid)


def test_eb_15_005_multi_target_concentration_links_each_effect() -> None:
    """EB-15-005: multi-target concentration links every applied effect."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 1})
    ally_one = create_family_target(name="Ally One", position=(2, 1), faction="heroes")
    ally_two = create_family_target(name="Ally Two", position=(3, 1), faction="heroes")
    Entity.materialize_all_navigation()
    cursor = EventQueue.event_cursor()

    event = Bless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally_one.uuid,
        extra_target_entity_uuids=[ally_two.uuid],
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    root_index = EventQueue.get_event_index(event.uuid)
    assert root_index is not None
    condition_completions = [
        candidate
        for index, candidate in EventQueue.iter_events_since(cursor)
        if index < root_index
        and candidate.event_type is EventType.CONDITION_APPLICATION
        and candidate.phase is EventPhase.COMPLETION
        and candidate.target_entity_uuid in {ally_one.uuid, ally_two.uuid}
    ]
    assert len(condition_completions) == 2
    assert event.total_targets == 2
    assert "Bless" in ally_one.active_conditions
    assert "Bless" in ally_two.active_conditions
    assert "Concentrating" in caster.active_conditions
    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert len(concentration.linked_conditions) == 2

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Bless" not in ally_one.active_conditions
    assert "Bless" not in ally_two.active_conditions


@pytest.mark.parametrize(
    "spell_name",
    ("BeaconOfHope", "HoldMonster", "Bane", "Bless", "NecroticBless"),
)
def test_named_multi_target_concentration_closes_after_all_target_effects(
    spell_name: str,
) -> None:
    """Each named convolution keeps its links before the root terminal."""
    reset_spell_family_state(width=12, height=8)
    caster_slots = {6: 1} if spell_name == "HoldMonster" else (
        {3: 1} if spell_name == "BeaconOfHope" else (
            {2: 1} if spell_name == "NecroticBless" else {1: 1}
        )
    )
    caster = create_family_caster(spell_slots=caster_slots)
    first = create_family_target(
        name="First target",
        position=(2, 1),
        faction="heroes" if spell_name in {"BeaconOfHope", "Bless"} else "monsters",
    )
    second = create_family_target(
        name="Second target",
        position=(3, 1),
        faction="heroes" if spell_name in {"BeaconOfHope", "Bless"} else "monsters",
    )
    if spell_name == "HoldMonster":
        penalize_save(first, "wisdom")
        penalize_save(second, "wisdom")
    elif spell_name == "Bane":
        penalize_save(first, "charisma")
        penalize_save(second, "charisma")
    elif spell_name == "NecroticBless":
        first.creature_type = CreatureType.UNDEAD
        penalize_save(second, "charisma")
    Entity.materialize_all_navigation()
    spell_type = {
        "BeaconOfHope": BeaconOfHope,
        "HoldMonster": HoldMonster,
        "Bane": Bane,
        "Bless": Bless,
        "NecroticBless": NecroticBless,
    }[spell_name]
    spell_kwargs = {
        "source_entity_uuid": caster.uuid,
        "target_entity_uuid": first.uuid,
        "extra_target_entity_uuids": [second.uuid],
        "template": False,
    }
    if spell_name == "HoldMonster":
        spell_kwargs["cast_at_level"] = 6
    event = assert_completed_spell(spell_type(**spell_kwargs).apply())

    root_index = EventQueue.get_event_index(event.uuid)
    assert root_index is not None
    expected_condition_names = {
        "BeaconOfHope": {"Beacon of Hope"},
        "HoldMonster": {"Hold Monster"},
        "Bane": {"Bane"},
        "Bless": {"Bless"},
        "NecroticBless": {"Bless", "Bane"},
    }[spell_name]
    target_condition_completions = [
        candidate
        for index, candidate in EventQueue.iter_events_since(0)
        if index < root_index
        and candidate.event_type is EventType.CONDITION_APPLICATION
        and candidate.phase is EventPhase.COMPLETION
        and candidate.target_entity_uuid in {first.uuid, second.uuid}
        and getattr(candidate.condition, "name", None) in expected_condition_names
    ]
    assert len(target_condition_completions) == 2
    assert {
        candidate.target_entity_uuid for candidate in target_condition_completions
    } == {first.uuid, second.uuid}
    assert "Concentrating" in caster.active_conditions
    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert len(concentration.linked_conditions) == 2


def test_eb_15_015_bless_and_bane_rewrite_save_d20_results() -> None:
    """EB-15-015: Bless and Bane rewrite saving throw d20 result events."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 2})
    ally = create_family_target(name="Blessed Ally", position=(2, 1), faction="heroes")
    enemy = create_family_target(name="Baned Enemy", position=(3, 1), faction="monsters")
    penalize_save(enemy, "charisma")
    Entity.materialize_all_navigation()

    bless_event = Bless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    bless_event = assert_completed_spell(bless_event)
    assert "Bless" in ally.active_conditions

    bless_bonus = ally.saving_throw_bonus(caster.uuid, "wisdom")
    with patch("random.randint", side_effect=[10, 3]):
        blessed_roll, blessed_event = ally.roll_d20_event(
            bless_bonus,
            RollType.SAVE,
            ability_name="wisdom",
        )

    assert blessed_event.original_roll.results == [10]
    assert blessed_roll.total == blessed_event.original_roll.total + 3
    assert blessed_event.final_roll is not None
    assert blessed_event.roll_modifications[0].handler_name == "Bless"
    assert blessed_event.roll_modifications[0].reason.startswith("+3 (1d4)")
    blessed_event.phase_to(EventPhase.COMPLETION)

    caster.action_economy.reset_all_costs()
    bane_event = Bane(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemy.uuid,
        template=False,
    ).apply()

    bane_event = assert_completed_spell(bane_event)
    assert "Bane" in enemy.active_conditions

    bane_bonus = enemy.saving_throw_bonus(caster.uuid, "wisdom")
    with patch("random.randint", side_effect=[12, 2]):
        baned_roll, baned_event = enemy.roll_d20_event(
            bane_bonus,
            RollType.SAVE,
            ability_name="wisdom",
        )

    assert baned_event.original_roll.results == [12]
    assert baned_roll.total == baned_event.original_roll.total - 2
    assert baned_event.final_roll is not None
    assert baned_event.roll_modifications[0].handler_name == "Bane"
    assert baned_event.roll_modifications[0].reason.startswith("-2 (1d4)")
    baned_event.phase_to(EventPhase.COMPLETION)


def test_eb_15_016_guidance_rewrites_one_skill_check_then_cleans_up() -> None:
    """EB-15-016: Guidance rewrites one check d20 and removes its condition."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 1})
    Entity.materialize_all_navigation()

    event = Guidance(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    assert "Guidance" in caster.active_conditions
    assert "Concentrating" in caster.active_conditions

    skill_bonus = caster.skill_bonus(None, "perception")
    with patch("random.randint", side_effect=[9, 4]):
        guided_roll, guided_event = caster.roll_d20_event(
            skill_bonus,
            RollType.CHECK,
            skill_name="perception",
        )

    assert guided_event.original_roll.results == [9]
    assert guided_roll.total == guided_event.original_roll.total + 4
    assert guided_event.final_roll is not None
    assert guided_event.roll_modifications[0].handler_name == "Guidance"
    assert guided_event.roll_modifications[0].reason.startswith("+4 (1d4)")
    assert "Guidance" not in caster.active_conditions
    assert "Concentrating" not in caster.active_conditions
    guided_event.phase_to(EventPhase.COMPLETION)


def test_guidance_effect_cancellation_is_the_root_terminal_before_spell_state() -> None:
    """An EFFECT veto cancels Guidance before it creates its condition tree."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 1})
    before_cursor = EventQueue.event_cursor()

    def cancel_effect(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="Guidance effect canceled")

    handler = EventHandler(
        name="Cancel Guidance effect",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                name="Guidance effect",
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=caster.uuid,
            ),
        ],
        event_processor=cancel_effect,
    )
    EventQueue.add_event_handler(handler)
    try:
        result = Guidance(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            template=False,
        ).apply()
    finally:
        EventQueue.remove_event_handler(handler)

    assert isinstance(result, SpellEvent)
    assert result.phase is EventPhase.CANCEL
    assert result.is_last is True
    assert "Guidance" not in caster.active_conditions
    assert "Concentrating" not in caster.active_conditions
    root_events = [
        event
        for _, event in EventQueue.iter_events_since(before_cursor)
        if event.lineage_uuid == result.lineage_uuid
    ]
    assert root_events[-1].uuid == result.uuid
    assert root_events[-1].phase is EventPhase.CANCEL
    assert not any(event.phase is EventPhase.COMPLETION for event in root_events)
    terminal_index = EventQueue.get_event_index(result.uuid)
    assert terminal_index is not None
    assert list(EventQueue.iter_events_since(terminal_index + 1)) == []


@pytest.mark.parametrize(
    ("spell_type", "slot_level"),
    (
        (ProtectionFromEnergy, 3),
        (Stoneskin, 4),
        (BestowCurse, 3),
        (EnhanceAbility, 2),
        (EnlargeReduce, 2),
    ),
)
def test_single_target_concentration_begins_only_after_effect_admission(
    spell_type: type,
    slot_level: int,
) -> None:
    """An EFFECT veto cannot leave a slot or target condition behind."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={slot_level: 1})
    target = create_family_target(
        name="Concentration target",
        position=(2, 1),
        faction="heroes",
    )
    Entity.materialize_all_navigation()
    cursor = EventQueue.event_cursor()

    def cancel_effect(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="Single-target effect canceled")

    handler = EventHandler(
        name="Cancel single-target concentration effect",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.CAST_SPELL,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=caster.uuid,
        )],
        event_processor=cancel_effect,
    )
    EventQueue.add_event_handler(handler)
    try:
        result = spell_type(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            template=False,
        ).apply()
    finally:
        EventQueue.remove_event_handler(handler)

    assert isinstance(result, SpellEvent)
    assert result.phase is EventPhase.CANCEL
    assert result.is_last is True
    assert "Concentrating" not in caster.active_conditions
    emitted = [row for _, row in EventQueue.iter_events_since(cursor)]
    assert not any(
        row.event_type is EventType.CONDITION_APPLICATION
        for row in emitted
    )
    assert emitted[-1].uuid == result.uuid


@pytest.mark.parametrize(
    ("spell_type", "slot_level", "undead"),
    (
        (Bless, 1, False),
        (NecroticBless, 2, True),
    ),
)
def test_per_target_effect_veto_precedes_multi_target_concentration_state(
    spell_type: type,
    slot_level: int,
    undead: bool,
) -> None:
    """A canceled target application cannot install or link its condition."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={slot_level: 1})
    target = create_family_target(
        name="Vetoed target",
        position=(2, 1),
        faction="heroes",
    )
    if undead:
        target.creature_type = CreatureType.UNDEAD
    Entity.materialize_all_navigation()
    cursor = EventQueue.event_cursor()

    def cancel_target_effect(event: Event, _: UUID) -> Event | None:
        if isinstance(event, SpellEvent) and event.application_index == 0:
            return event.cancel(status_message="Target application canceled")
        return None

    handler = EventHandler(
        name="Cancel one target application",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.CAST_SPELL,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=caster.uuid,
        )],
        event_processor=cancel_target_effect,
    )
    EventQueue.add_event_handler(handler)
    try:
        result = spell_type(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            template=False,
        ).apply()
    finally:
        EventQueue.remove_event_handler(handler)

    result = assert_completed_spell(result)
    assert "Bless" not in target.active_conditions
    assert "Bane" not in target.active_conditions
    assert "Concentrating" not in caster.active_conditions
    emitted = [row for _, row in EventQueue.iter_events_since(cursor)]
    canceled_applications = [
        row
        for row in emitted
        if isinstance(row, SpellEvent)
        and row.application_index == 0
        and row.phase is EventPhase.CANCEL
    ]
    assert len(canceled_applications) == 1
    assert not any(
        row.event_type is EventType.CONDITION_APPLICATION
        for row in emitted
    )
    assert emitted[-1].uuid == result.uuid


def test_multi_target_effect_cancellation_precedes_aoe_children_and_state() -> None:
    """An AOE EFFECT veto produces no per-target effects or concentration cleanup."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={3: 1})
    first_target = create_family_target(name="First target", position=(2, 1))
    second_target = create_family_target(name="Second target", position=(3, 1))
    first_hp = get_hp(first_target)
    second_hp = get_hp(second_target)
    Entity.materialize_all_navigation()
    before_cursor = EventQueue.event_cursor()

    def cancel_effect(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="AOE effect canceled")

    handler = EventHandler(
        name="Cancel AOE effect",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                name="AOE effect",
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=caster.uuid,
            ),
        ],
        event_processor=cancel_effect,
    )
    EventQueue.add_event_handler(handler)
    try:
        result = Fireball(
            source_entity_uuid=caster.uuid,
            end_position=(2, 1),
            template=False,
        ).apply()
    finally:
        EventQueue.remove_event_handler(handler)

    assert isinstance(result, SpellEvent)
    assert result.phase is EventPhase.CANCEL
    assert result.is_last is True
    assert get_hp(first_target) == first_hp
    assert get_hp(second_target) == second_hp
    assert "Concentrating" not in caster.active_conditions
    root_events = [
        event
        for _, event in EventQueue.iter_events_since(before_cursor)
        if event.lineage_uuid == result.lineage_uuid
    ]
    assert root_events[-1].uuid == result.uuid
    assert root_events[-1].phase is EventPhase.CANCEL
    assert not any(event.phase is EventPhase.COMPLETION for event in root_events)
    assert not any(
        event.parent_event in {root.uuid for root in root_events}
        and event.lineage_uuid != result.lineage_uuid
        for _, event in EventQueue.iter_events_since(before_cursor)
    )


def test_counterspell_is_a_parented_child_of_the_canceled_spell_log() -> None:
    """Counterspell remains a child fact when it interrupts a spell root."""
    reset_spell_family_state(width=12, height=8)
    caster = create_family_caster(
        name="Incoming Caster",
        position=(1, 1),
        spell_slots={1: 1},
        faction="heroes",
    )
    counterspeller = create_family_caster(
        name="Counterspeller",
        position=(5, 1),
        spell_slots={3: 1},
        faction="monsters",
    )
    register_counterspell_reaction(counterspeller)
    Entity.materialize_all_navigation()
    cursor = EventQueue.event_cursor()

    result = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=counterspeller.uuid,
        template=False,
    ).apply()

    assert isinstance(result, SpellEvent)
    assert result.canceled
    reaction_rows = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, CounterspellReactionEvent)
    ]
    assert reaction_rows
    assert all(event.parent_event is not None for event in reaction_rows)
    assert all(
        EventQueue.get_event_by_uuid(event.parent_event).lineage_uuid == result.lineage_uuid
        for event in reaction_rows
        if event.parent_event is not None
        and EventQueue.get_event_by_uuid(event.parent_event) is not None
    )
    assert reaction_rows[-1].parent_lineage == result.lineage_uuid
    assert reaction_rows[-1].lineage_uuid in result.children_lineages
    assert result.combat_log is not None
    interruption_logs = [
        entry
        for entry in result.combat_log.sub_entries
        if entry.entry_type is CombatLogEntryType.SPELL_INTERRUPTION
    ]
    assert len(interruption_logs) == 1
    assert interruption_logs[0].source_uuid == str(counterspeller.uuid)
    assert not any(
        isinstance(event, CounterspellReactionEvent) and event.parent_event is None
        for _, event in EventQueue.iter_events_since(cursor)
    )


def test_eb_15_024_d20_mutation_handlers_are_roll_type_scoped() -> None:
    """EB-15-024: Bless, Bane, and Guidance mutate only their roll types."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 1})
    ally = create_family_target(name="Blessed Ally", position=(2, 1), faction="heroes")
    target = create_family_target(name="Attack Target", position=(3, 1), faction="monsters")
    Entity.materialize_all_navigation()

    bless_event = Bless(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        template=False,
    ).apply()

    bless_event = assert_completed_spell(bless_event)
    assert "Bless" in ally.active_conditions

    bless_attack_bonus = ally.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
    with patch("random.randint", side_effect=[8, 4]):
        blessed_attack_roll, blessed_attack_event = ally.roll_d20_event(
            bless_attack_bonus,
            RollType.ATTACK,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        )

    assert blessed_attack_event.original_roll.results == [8]
    assert blessed_attack_roll.total == blessed_attack_event.original_roll.total + 4
    assert blessed_attack_event.roll_modifications[0].handler_name == "Bless"
    blessed_attack_event.phase_to(EventPhase.COMPLETION)

    bless_check_bonus = ally.skill_bonus(None, "athletics")
    with patch("random.randint", side_effect=[9]):
        blessed_check_roll, blessed_check_event = ally.roll_d20_event(
            bless_check_bonus,
            RollType.CHECK,
            skill_name="athletics",
        )

    assert blessed_check_event.original_roll.results == [9]
    assert blessed_check_roll.total == blessed_check_event.original_roll.total
    assert blessed_check_event.roll_modifications == []
    assert "Bless" in ally.active_conditions
    blessed_check_event.phase_to(EventPhase.COMPLETION)

    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 1})
    enemy = create_family_target(name="Baned Enemy", position=(2, 1), faction="monsters")
    target = create_family_target(name="Attack Target", position=(3, 1), faction="heroes")
    penalize_save(enemy, "charisma")
    Entity.materialize_all_navigation()

    bane_event = Bane(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=enemy.uuid,
        template=False,
    ).apply()

    bane_event = assert_completed_spell(bane_event)
    assert "Bane" in enemy.active_conditions

    bane_attack_bonus = enemy.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
    with patch("random.randint", side_effect=[13, 2]):
        baned_attack_roll, baned_attack_event = enemy.roll_d20_event(
            bane_attack_bonus,
            RollType.ATTACK,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        )

    assert baned_attack_event.original_roll.results == [13]
    assert baned_attack_roll.total == baned_attack_event.original_roll.total - 2
    assert baned_attack_event.roll_modifications[0].handler_name == "Bane"
    baned_attack_event.phase_to(EventPhase.COMPLETION)

    bane_check_bonus = enemy.skill_bonus(None, "athletics")
    with patch("random.randint", side_effect=[7]):
        baned_check_roll, baned_check_event = enemy.roll_d20_event(
            bane_check_bonus,
            RollType.CHECK,
            skill_name="athletics",
        )

    assert baned_check_event.original_roll.results == [7]
    assert baned_check_roll.total == baned_check_event.original_roll.total
    assert baned_check_event.roll_modifications == []
    assert "Bane" in enemy.active_conditions
    baned_check_event.phase_to(EventPhase.COMPLETION)

    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 1})
    Entity.materialize_all_navigation()

    guidance_event = Guidance(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    guidance_event = assert_completed_spell(guidance_event)
    assert "Guidance" in caster.active_conditions
    assert "Concentrating" in caster.active_conditions

    guidance_attack_bonus = caster.attack_bonus(WeaponSlot.MELEE_MAIN)
    with patch("random.randint", side_effect=[12]):
        guidance_attack_roll, guidance_attack_event = caster.roll_d20_event(
            guidance_attack_bonus,
            RollType.ATTACK,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        )

    assert guidance_attack_event.original_roll.results == [12]
    assert guidance_attack_roll.total == guidance_attack_event.original_roll.total
    assert guidance_attack_event.roll_modifications == []
    assert "Guidance" in caster.active_conditions
    guidance_attack_event.phase_to(EventPhase.COMPLETION)

    guidance_save_bonus = caster.saving_throw_bonus(None, "wisdom")
    with patch("random.randint", side_effect=[14]):
        guidance_save_roll, guidance_save_event = caster.roll_d20_event(
            guidance_save_bonus,
            RollType.SAVE,
            ability_name="wisdom",
        )

    assert guidance_save_event.original_roll.results == [14]
    assert guidance_save_roll.total == guidance_save_event.original_roll.total
    assert guidance_save_event.roll_modifications == []
    assert "Guidance" in caster.active_conditions
    guidance_save_event.phase_to(EventPhase.COMPLETION)

    guidance_check_bonus = caster.skill_bonus(None, "perception")
    with patch("random.randint", side_effect=[9, 3]):
        guidance_check_roll, guidance_check_event = caster.roll_d20_event(
            guidance_check_bonus,
            RollType.CHECK,
            skill_name="perception",
        )

    assert guidance_check_event.original_roll.results == [9]
    assert guidance_check_roll.total == guidance_check_event.original_roll.total + 3
    assert guidance_check_event.roll_modifications[0].handler_name == "Guidance"
    assert "Guidance" not in caster.active_conditions
    assert "Concentrating" not in caster.active_conditions
    guidance_check_event.phase_to(EventPhase.COMPLETION)


def test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup() -> None:
    """EB-15-017: Hold Person applies Paralyzed and repeat-save cleanup."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 1})
    target = create_family_target(name="Held Humanoid", position=(3, 1))
    penalize_save(target, "wisdom")
    Entity.materialize_all_navigation()

    event = HoldPerson(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    assert "Hold Person" in target.active_conditions
    assert "Paralyzed" in target.active_conditions
    hold_effect = target.active_conditions["Hold Person"]
    paralyzed = target.active_conditions["Paralyzed"]
    assert paralyzed.parent_condition == hold_effect.uuid
    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert (target.uuid, hold_effect.uuid) in concentration.linked_conditions
    assert caster.action_economy.spell_slot_2.normalized_score == 0

    boost_save(target, "wisdom", value=200)
    turn_end = target.on_turn_end(round_number=1, turn_index=0)

    assert turn_end.phase == EventPhase.COMPLETION
    assert "Hold Person" not in target.active_conditions
    assert "Paralyzed" not in target.active_conditions
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 1
    assert "Concentrating" not in caster.active_conditions


def test_eb_15_017_hold_person_successful_initial_save_has_truthful_synced_log() -> None:
    """Hold Person reports the resolved save and cleans empty concentration."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 1})
    target = create_family_target(name="Resisting Humanoid", position=(3, 1))
    boost_save(target, "wisdom")
    Entity.materialize_all_navigation()
    cursor = EventQueue.event_cursor()

    event = HoldPerson(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    root_index = EventQueue.get_event_index(event.uuid)
    assert root_index is not None
    concentration_removals = [
        candidate
        for index, candidate in EventQueue.iter_events_since(cursor)
        if index < root_index
        and candidate.event_type is EventType.CONDITION_REMOVAL
        and candidate.phase is EventPhase.COMPLETION
        and candidate.target_entity_uuid == caster.uuid
        and getattr(candidate.condition, "name", None) == "Concentrating"
    ]
    assert len(concentration_removals) == 1
    assert event.save_success is True
    assert event.save_roll is not None
    assert event.save_bonus == event.save_roll.bonus
    assert "Hold Person" not in target.active_conditions
    assert "Paralyzed" not in target.active_conditions
    assert "Concentrating" not in caster.active_conditions
    assert event.status_message is not None
    assert "saved" in event.status_message.lower()
    assert "concentrat" not in event.status_message.lower()

    assert event.combat_log is not None
    assert event.combat_log.entry_type == CombatLogEntryType.SPELL_SAVE
    saving_throw_logs = [
        entry for entry in event.combat_log.sub_entries
        if entry.entry_type == CombatLogEntryType.SAVING_THROW
    ]
    assert len(saving_throw_logs) == 1
    nested_save_log = saving_throw_logs[0]
    assert nested_save_log.data["save_kind"] == "ability"
    parent_roll = event.combat_log.data["save_roll"]
    nested_roll = nested_save_log.data["roll"]
    assert parent_roll["results"] == nested_roll["results"]
    assert parent_roll["bonus"] == nested_roll["bonus"]
    assert parent_roll["total"] == nested_roll["total"]
    assert event.combat_log.data["save_success"] == nested_save_log.data["success"]


def test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup() -> None:
    """EB-15-018: Hold Monster rejects undead and cleans up on repeat save."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={5: 1})
    undead = create_family_target(name="Skeleton", position=(3, 1))
    undead.creature_type = CreatureType.UNDEAD
    target = create_family_target(name="Living Monster", position=(4, 1))
    target.creature_type = CreatureType.MONSTROSITY
    penalize_save(target, "wisdom")
    Entity.materialize_all_navigation()

    undead_event = HoldMonster(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=undead.uuid,
        template=False,
    ).apply()

    assert undead_event is not None
    assert undead_event.canceled
    assert "Hold Monster" not in undead.active_conditions
    assert caster.action_economy.spell_slot_5.normalized_score == 1

    event = HoldMonster(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    assert "Hold Monster" in target.active_conditions
    assert "Paralyzed" in target.active_conditions
    hold_effect = target.active_conditions["Hold Monster"]
    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert (target.uuid, hold_effect.uuid) in concentration.linked_conditions
    assert caster.action_economy.spell_slot_5.normalized_score == 0

    boost_save(target, "wisdom", value=200)
    turn_end = target.on_turn_end(round_number=1, turn_index=0)

    assert turn_end.phase == EventPhase.COMPLETION
    assert "Hold Monster" not in target.active_conditions
    assert "Paralyzed" not in target.active_conditions
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 1
    assert "Concentrating" not in caster.active_conditions


def test_eb_15_018_hold_monster_successful_initial_save_has_synced_log() -> None:
    """Hold Monster keeps its per-target spell log aligned with the child save."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={5: 1})
    target = create_family_target(name="Resisting Monster", position=(3, 1))
    target.creature_type = CreatureType.MONSTROSITY
    boost_save(target, "wisdom")
    Entity.materialize_all_navigation()

    event = HoldMonster(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    assert "Hold Monster" not in target.active_conditions
    assert "Paralyzed" not in target.active_conditions
    assert "Concentrating" not in caster.active_conditions

    assert event.combat_log is not None
    spell_save_logs = [
        entry for entry in event.combat_log.sub_entries
        if entry.entry_type == CombatLogEntryType.SPELL_SAVE
    ]
    assert len(spell_save_logs) == 1
    spell_save_log = spell_save_logs[0]
    saving_throw_logs = [
        entry for entry in spell_save_log.sub_entries
        if entry.entry_type == CombatLogEntryType.SAVING_THROW
    ]
    assert len(saving_throw_logs) == 1
    nested_save_log = saving_throw_logs[0]
    assert nested_save_log.data["save_kind"] == "ability"
    parent_roll = spell_save_log.data["save_roll"]
    nested_roll = nested_save_log.data["roll"]
    assert parent_roll["results"] == nested_roll["results"]
    assert parent_roll["bonus"] == nested_roll["bonus"]
    assert parent_roll["total"] == nested_roll["total"]
    assert spell_save_log.data["save_success"] == nested_save_log.data["success"]


def test_eb_15_019_mirror_image_duplicates_absorb_missed_attacks() -> None:
    """EB-15-019: Mirror Image adds AC and consumes duplicates on misses."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 2})
    attacker = create_family_target(name="Attacker", position=(2, 1), faction="monsters")
    Entity.materialize_all_navigation()
    base_ac_bonus = caster.equipment.ac_bonus.normalized_score

    event = MirrorImage(
        source_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    assert "Mirror Image" in caster.active_conditions
    assert "Concentrating" not in caster.active_conditions
    mirror = cast(MirrorImageEffect, caster.active_conditions["Mirror Image"])
    assert mirror.duplicates == 3
    assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 9
    assert caster.action_economy.spell_slot_2.normalized_score == 1

    miss_mod = force_attack_miss(attacker)
    for expected_duplicates in (2, 1, 0):
        attacker.action_economy.reset_all_costs()
        attack_event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=caster.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

        assert isinstance(attack_event, AttackEvent)
        assert attack_event.attack_outcome in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS)
        if expected_duplicates > 0:
            mirror = cast(MirrorImageEffect, caster.active_conditions["Mirror Image"])
            assert mirror.duplicates == expected_duplicates
            assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + expected_duplicates * 3
        else:
            assert "Mirror Image" not in caster.active_conditions
            assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus

    remove_attack_modifier(attacker, miss_mod)

    caster.action_economy.reset_all_costs()
    event = MirrorImage(
        source_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    hit_mod = force_attack_hit(attacker)
    hp_before = get_hp(caster)
    attacker.action_economy.reset_all_costs()
    hit_event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()

    assert isinstance(hit_event, AttackEvent)
    assert hit_event.attack_outcome not in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS)
    assert get_hp(caster) < hp_before
    mirror = cast(MirrorImageEffect, caster.active_conditions["Mirror Image"])
    assert mirror.duplicates == 3
    assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 9
    assert caster.action_economy.spell_slot_2.normalized_score == 0
    remove_attack_modifier(attacker, hit_mod)


def test_eb_15_035_mirror_image_recast_replaces_and_duration_expires() -> None:
    """EB-15-035: Mirror Image recasts replace state and duration expires."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 3})
    attacker = create_family_target(name="Mirror Attacker", position=(2, 1), faction="monsters")
    Entity.materialize_all_navigation()
    base_ac_bonus = caster.equipment.ac_bonus.normalized_score

    first_event = MirrorImage(
        source_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    first_event = assert_completed_spell(first_event)
    assert first_event is not None
    mirror = cast(MirrorImageEffect, caster.active_conditions["Mirror Image"])
    assert mirror.duplicates == 3
    assert mirror.duration.duration_type == DurationType.ROUNDS
    assert mirror.duration.duration == 10
    assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 9
    assert len(caster.get_event_handlers_by_name("Mirror Image: Evade")) == 1
    assert caster.action_economy.spell_slot_2.normalized_score == 2

    miss_mod = force_attack_miss(attacker)
    attacker.action_economy.reset_all_costs()
    miss_event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()

    assert isinstance(miss_event, AttackEvent)
    assert miss_event.attack_outcome in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS)
    mirror = cast(MirrorImageEffect, caster.active_conditions["Mirror Image"])
    assert mirror.duplicates == 2
    assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 6

    caster.action_economy.reset_all_costs()
    second_event = MirrorImage(
        source_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    second_event = assert_completed_spell(second_event)
    assert second_event is not None
    mirror = cast(MirrorImageEffect, caster.active_conditions["Mirror Image"])
    assert mirror.duplicates == 3
    assert mirror.duration.duration == 10
    assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 9
    assert len(caster.get_event_handlers_by_name("Mirror Image: Evade")) == 1
    assert caster.action_economy.spell_slot_2.normalized_score == 1

    attacker.action_economy.reset_all_costs()
    recast_miss_event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()

    assert isinstance(recast_miss_event, AttackEvent)
    assert recast_miss_event.attack_outcome in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS)
    mirror = cast(MirrorImageEffect, caster.active_conditions["Mirror Image"])
    assert mirror.duplicates == 2
    assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 6
    assert len(caster.get_event_handlers_by_name("Mirror Image: Evade")) == 1
    remove_attack_modifier(attacker, miss_mod)

    for _ in range(9):
        assert not caster.advance_duration("Mirror Image")
        assert "Mirror Image" in caster.active_conditions

    assert caster.advance_duration("Mirror Image")
    assert "Mirror Image" not in caster.active_conditions
    assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus
    assert len(caster.get_event_handlers_by_name("Mirror Image: Evade")) == 0


def test_eb_15_006_zone_spells_create_spatial_handlers_and_cleanup_links() -> None:
    """EB-15-006: zone spells create spatial handlers and concentration cleanup."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 1})
    Entity.materialize_all_navigation()

    event = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=(5, 3),
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    effect = active_spatial_condition("Spike Growth Zone")
    assert isinstance(effect, SpatialCondition)
    assert "Spike Growth Zone" not in caster.active_conditions
    assert "Concentrating" in caster.active_conditions

    zone = cast(AreaCondition, effect)
    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert len(zone.affected_positions) > 0
    assert len(zone.spatial_handler_uuids) > 0
    assert (effect.uuid, zone.uuid) in concentration.linked_conditions

    caster.remove_condition("Concentrating")

    assert "Spike Growth Zone" not in caster.active_conditions
    assert BaseCondition.get(effect.uuid) is None
    assert "Concentrating" not in caster.active_conditions


def test_eb_15_021_zone_spell_family_entry_turn_start_and_cleanup_edges() -> None:
    """EB-15-021: zone spell families use entry, turn-start, and cleanup handlers."""
    reset_spell_family_state(width=18, height=18)
    caster = create_family_caster(position=(1, 1), spell_slots={1: 1})
    target = create_family_target(name="Grease Target", position=(8, 5))
    setup_standard_actions(target)
    penalize_save(target, "dexterity")
    Entity.materialize_all_navigation(max_distance=30)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        grease_event = Grease(
            source_entity_uuid=caster.uuid,
            end_position=(5, 5),
            template=False,
    ).apply()

    grease_event = assert_completed_spell(grease_event)
    grease_effect_uuids = get_map().get_spatial_condition_uuids_at((5, 5))
    assert len(grease_effect_uuids) == 1
    grease_effect = BaseCondition.get(next(iter(grease_effect_uuids)))
    assert isinstance(grease_effect, SpatialCondition)
    grease_tile = get_map().get_tile(5, 5)
    assert grease_tile is not None
    assert grease_tile.get_conditions()[grease_effect.uuid] is grease_effect
    grease_zone = cast(
        AreaCondition,
        grease_effect,
    )
    assert grease_zone.adds_difficult_terrain
    assert len(grease_zone.spatial_handler_uuids) == 1
    assert len(grease_zone.event_handlers_uuids) == 1

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        Entity.update_entity_position(target, (5, 5))
    assert "Prone" in target.active_conditions

    target.remove_condition("Prone")
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        target.on_turn_start(round_number=1, turn_index=0)
    assert "Prone" not in target.active_conditions
    assert target.action_economy.movement.normalized_score == 30

    reset_spell_family_state(width=18, height=18)
    caster = create_family_caster(position=(1, 1), spell_slots={2: 1})
    target = create_family_target(name="Web Target", position=(8, 5))
    penalize_save(target, "dexterity")
    Entity.materialize_all_navigation(max_distance=30)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        web_event = Web(
            source_entity_uuid=caster.uuid,
            end_position=(5, 5),
            template=False,
        ).apply()

    web_event = assert_completed_spell(web_event)
    web_effect = active_spatial_condition("Web Zone")
    assert isinstance(web_effect, SpatialCondition)
    assert web_effect.content_ref == WEB_SURFACE_RECIPE.ref
    web_zone = cast(WebZone, web_effect)
    assert web_zone.adds_difficult_terrain
    assert len(web_zone.spatial_handler_uuids) == 3
    assert {
        EventQueue._event_handlers[handler_uuid].name
        for handler_uuid in web_zone.event_handlers_uuids
    } == {"Web Turn Start Save"}

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        Entity.update_entity_position(target, (5, 5))
    web_membership = next(
        condition
        for condition in target.active_conditions_by_uuid.values()
        if isinstance(condition, WebRestrained)
    )
    assert "Restrained" in target.active_conditions
    assert any(action.name == "Escape Web" for action in target.registered_actions)

    target.remove_condition_by_uuid(web_membership.uuid)
    assert "Restrained" not in target.active_conditions
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        target.on_turn_start(round_number=1, turn_index=0)
    assert any(
        isinstance(condition, WebRestrained)
        for condition in target.active_conditions_by_uuid.values()
    )
    assert "Restrained" in target.active_conditions

    reset_spell_family_state(width=24, height=24)
    caster = create_family_caster(position=(1, 1), spell_slots={5: 1})
    target = create_family_target(name="Cloudkill Target", position=(15, 10), hp_dice=10)
    penalize_save(target, "constitution")
    Entity.materialize_all_navigation(max_distance=40)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        cloudkill_event = Cloudkill(
            source_entity_uuid=caster.uuid,
            end_position=(10, 10),
            template=False,
        ).apply()

    cloudkill_event = assert_completed_spell(cloudkill_event)
    cloudkill_effect = active_spatial_condition(
        "Cloudkill Zone",
    )
    assert isinstance(cloudkill_effect, SpatialCondition)
    cloudkill_zone = cast(AreaCondition, cloudkill_effect)
    assert not cloudkill_zone.adds_difficult_terrain
    assert len(cloudkill_zone.spatial_handler_uuids) == 2
    assert len(cloudkill_zone.event_handlers_uuids) == 2

    hp_before_entry = get_hp(target)
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        Entity.update_entity_position(target, (10, 10))
    assert hp_before_entry - get_hp(target) == 15

    hp_before_start = get_hp(target)
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        target.on_turn_start(round_number=1, turn_index=0)
    assert hp_before_start - get_hp(target) == 15

    old_center = cloudkill_zone.position
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        caster.on_turn_start(round_number=1, turn_index=0)
    assert cloudkill_zone.position != old_center

    reset_spell_family_state(width=18, height=18)
    caster = create_family_caster(position=(5, 5), spell_slots={3: 1}, faction="heroes")
    enemy = create_family_target(
        name="Spirit Enemy",
        position=(10, 5),
        faction="monsters",
        hp_dice=10,
    )
    ally = create_family_target(
        name="Spirit Ally",
        position=(10, 6),
        faction="heroes",
        hp_dice=10,
    )
    penalize_save(enemy, "wisdom")
    Entity.materialize_all_navigation(max_distance=30)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        spirit_event = SpiritGuardians(
            source_entity_uuid=caster.uuid,
            template=False,
        ).apply()

    spirit_event = assert_completed_spell(spirit_event)
    spirit_effect = active_spatial_condition(
        "Spirit Guardians Zone",
    )
    assert isinstance(spirit_effect, SpatialCondition)
    assert spirit_effect.anchor_kind is SpatialEffectAnchorKind.ENTITY
    assert spirit_effect.anchor_uuid == caster.uuid
    spirit_zone = cast(AreaCondition, spirit_effect)
    assert spirit_zone.position == caster.position
    assert len(spirit_zone.spatial_handler_uuids) == 2
    assert len(spirit_zone.event_handlers_uuids) == 2

    enemy_hp_before = get_hp(enemy)
    ally_hp_before = get_hp(ally)
    movement_turn = EventQueue.begin_turn_execution()
    try:
        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            Entity.update_entity_position(enemy, (6, 5))
            Entity.update_entity_position(ally, (6, 6))
        assert enemy_hp_before - get_hp(enemy) == 9
        assert get_hp(ally) == ally_hp_before
        assert "Spirit Guardians Slowed" in enemy.active_conditions

        hp_after_entry = get_hp(enemy)
        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            Entity.update_entity_position(enemy, (7, 5))
        assert get_hp(enemy) == hp_after_entry
        assert "Spirit Guardians Slowed" in enemy.active_conditions
    finally:
        EventQueue.end_turn_execution(movement_turn)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        Entity.update_entity_position(enemy, (12, 12))
    assert "Spirit Guardians Slowed" not in enemy.active_conditions

    caster.remove_condition("Concentrating")
    assert "Spirit Guardians Zone" not in caster.active_conditions
    assert BaseCondition.get(spirit_effect.uuid) is None
    assert all(
        handler_uuid not in EventQueue._handler_positions
        for handler_uuid in spirit_zone.spatial_handler_uuids
    )


def test_spirit_guardians_uses_one_effect_target_turn_admission_fence() -> None:
    """Entry and turn-start triggers share one exact per-turn admission token."""
    reset_spell_family_state(width=18, height=18)
    caster = create_family_caster(
        position=(5, 5),
        spell_slots={3: 1},
        faction="heroes",
    )
    enemy = create_family_target(
        name="Admission Enemy",
        position=(12, 12),
        faction="monsters",
        hp_dice=20,
    )
    set_hp(enemy, 300)
    penalize_save(enemy, "wisdom")
    Entity.materialize_all_navigation(max_distance=30)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        assert_completed_spell(
            SpiritGuardians(
                source_entity_uuid=caster.uuid,
                template=False,
            ).apply(),
        )

    first_turn = EventQueue.begin_turn_execution()
    try:
        hp_before_entry = get_hp(enemy)
        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            Entity.update_entity_position(enemy, (6, 5))
        hp_after_entry = get_hp(enemy)
        assert hp_after_entry < hp_before_entry

        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            enemy.on_turn_start(
                encounter_uuid=uuid4(),
                round_number=1,
                turn_index=0,
            )
        assert get_hp(enemy) == hp_after_entry
    finally:
        EventQueue.end_turn_execution(first_turn)

    second_turn = EventQueue.begin_turn_execution()
    try:
        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            enemy.on_turn_start(
                encounter_uuid=uuid4(),
                round_number=2,
                turn_index=0,
            )
        assert get_hp(enemy) < hp_after_entry
    finally:
        EventQueue.end_turn_execution(second_turn)


def test_spirit_guardians_moving_aura_hits_each_target_once_per_turn() -> None:
    """BG3-style aura movement admits many targets but never repeats one target."""
    reset_spell_family_state(width=24, height=12)
    caster = create_family_caster(
        position=(1, 5),
        spell_slots={3: 1},
        faction="heroes",
    )
    first_enemy = create_family_target(
        name="First Aura Target",
        position=(5, 5),
        faction="monsters",
        hp_dice=20,
    )
    second_enemy = create_family_target(
        name="Second Aura Target",
        position=(10, 5),
        faction="monsters",
        hp_dice=20,
    )
    for enemy in (first_enemy, second_enemy):
        set_hp(enemy, 300)
        penalize_save(enemy, "wisdom")
    Entity.materialize_all_navigation(max_distance=30)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        assert_completed_spell(
            SpiritGuardians(
                source_entity_uuid=caster.uuid,
                template=False,
            ).apply(),
        )

    movement_turn = EventQueue.begin_turn_execution()
    try:
        first_hp = get_hp(first_enemy)
        second_hp = get_hp(second_enemy)
        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            Entity.update_entity_position(caster, (2, 5))
        assert get_hp(first_enemy) < first_hp
        first_after_hit = get_hp(first_enemy)
        assert "Spirit Guardians Slowed" in first_enemy.active_conditions
        assert get_hp(second_enemy) == second_hp

        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            Entity.update_entity_position(caster, (7, 5))
        assert get_hp(second_enemy) < second_hp
        assert "Spirit Guardians Slowed" in first_enemy.active_conditions
        assert "Spirit Guardians Slowed" in second_enemy.active_conditions

        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            Entity.update_entity_position(caster, (14, 5))
        assert "Spirit Guardians Slowed" not in first_enemy.active_conditions
        assert "Spirit Guardians Slowed" not in second_enemy.active_conditions
        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            Entity.update_entity_position(caster, (2, 5))
        assert get_hp(first_enemy) == first_after_hit
        assert "Spirit Guardians Slowed" in first_enemy.active_conditions
    finally:
        EventQueue.end_turn_execution(movement_turn)

    next_turn = EventQueue.begin_turn_execution()
    try:
        first_before_next_turn = get_hp(first_enemy)
        with patch(
            "dnd.core.dice.random.randint",
            side_effect=fixed_zone_randint,
        ):
            Entity.update_entity_position(caster, (14, 5))
            Entity.update_entity_position(caster, (2, 5))
        assert get_hp(first_enemy) < first_before_next_turn
    finally:
        EventQueue.end_turn_execution(next_turn)


def test_overlapping_spirit_guardians_keep_each_exact_slow_source() -> None:
    """One aura ending cannot erase another aura's still-live speed halving."""
    reset_spell_family_state(width=20, height=12)
    first_caster = create_family_caster(
        name="First Guardian",
        position=(5, 5),
        spell_slots={3: 1},
        faction="heroes",
    )
    second_caster = create_family_caster(
        name="Second Guardian",
        position=(7, 5),
        spell_slots={3: 1},
        faction="heroes",
    )
    enemy = create_family_target(
        name="Overlapping Aura Target",
        position=(15, 5),
        faction="monsters",
        hp_dice=30,
    )
    set_hp(enemy, 500)
    penalize_save(enemy, "wisdom")
    Entity.materialize_all_navigation(max_distance=30)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        assert_completed_spell(
            SpiritGuardians(
                source_entity_uuid=first_caster.uuid,
                template=False,
            ).apply(),
        )
        assert_completed_spell(
            SpiritGuardians(
                source_entity_uuid=second_caster.uuid,
                template=False,
            ).apply(),
        )
        Entity.update_entity_position(enemy, (6, 5))

    sources = [
        condition
        for condition in enemy.active_conditions_by_uuid.values()
        if isinstance(condition, SpiritGuardiansSlowSource)
    ]
    assert len(sources) == 2
    assert len(
        enemy.get_condition_application_leases("Spirit Guardians Slowed"),
    ) == 2
    assert "Spirit Guardians Slowed" in enemy.active_conditions

    first_caster.remove_condition("Concentrating")
    assert "Spirit Guardians Slowed" in enemy.active_conditions
    assert len(
        enemy.get_condition_application_leases("Spirit Guardians Slowed"),
    ) == 1

    second_caster.remove_condition("Concentrating")
    assert "Spirit Guardians Slowed" not in enemy.active_conditions
    assert (
        enemy.get_condition_application_leases("Spirit Guardians Slowed")
        == ()
    )


def test_grease_has_an_independent_lifetime_and_checks_occupants_at_turn_end() -> None:
    """Grease is a timed world effect, not a caster concentration condition."""
    reset_spell_family_state(width=24, height=24)
    caster = create_family_caster(
        position=(2, 2),
        spell_slots={1: 2, 2: 1},
    )
    target = create_family_target(position=(10, 10))
    penalize_save(target, "dexterity")
    Entity.materialize_all_navigation(max_distance=120)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        grease_event = Grease(
            source_entity_uuid=caster.uuid,
            end_position=(10, 10),
            template=False,
        ).apply()
    grease_event = assert_completed_spell(grease_event)
    assert "Concentrating" not in caster.active_conditions
    assert "Grease Zone" not in caster.active_conditions
    grease_effect_uuids = get_map().get_spatial_condition_uuids_at((10, 10))
    assert len(grease_effect_uuids) == 1
    grease_effect = BaseCondition.get(next(iter(grease_effect_uuids)))
    assert isinstance(grease_effect, SpatialCondition)
    grease_zone = cast(
        AreaCondition,
        grease_effect,
    )
    assert grease_zone.duration.duration_type is DurationType.ROUNDS
    assert grease_zone.duration.duration == 10
    created_events = [
        event
        for event in EventQueue.get_events_by_type(
            EventType.SPATIAL_EFFECT_CHANGED,
        )
        if isinstance(event, SpatialEffectChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.operation is SpatialEffectChangeOperation.CREATED
    ]
    assert len(created_events) == 1
    assert created_events[0].parent_lineage == grease_event.lineage_uuid
    assert created_events[0].spatial_effect_uuid == grease_effect.uuid
    assert created_events[0].combat_log is not None
    assert (
        created_events[0].combat_log.entry_type
        is CombatLogEntryType.SPATIAL_EFFECT
    )

    target.remove_condition("Prone")
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        target.on_turn_start(round_number=1, turn_index=0)
    assert "Prone" not in target.active_conditions

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        target.on_turn_end(round_number=1, turn_index=0)
    assert "Prone" in target.active_conditions

    caster.on_turn_start(round_number=2, turn_index=0)
    fog_event = FogCloud(
        source_entity_uuid=caster.uuid,
        end_position=(15, 15),
        template=False,
    ).apply()
    assert_completed_spell(fog_event)
    assert "Concentrating" in caster.active_conditions
    caster.remove_condition("Concentrating")

    grease_tile = get_map().get_tile(10, 10)
    assert grease_tile is not None
    assert grease_tile.walking_cost.normalized_score == 2
    for _ in range(9):
        assert not grease_effect.progress_spatial_duration()
    assert grease_zone.duration.duration == 1
    assert grease_effect.progress_spatial_duration()
    assert BaseCondition.get(grease_effect.uuid) is None
    assert get_map().get_spatial_condition_uuids_at((10, 10)) == set()
    assert grease_tile.walking_cost.normalized_score == 1
    removed_events = [
        event
        for event in EventQueue.get_events_by_type(
            EventType.SPATIAL_EFFECT_CHANGED,
        )
        if isinstance(event, SpatialEffectChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.operation is SpatialEffectChangeOperation.REMOVED
        and event.spatial_effect_uuid == grease_effect.uuid
    ]
    assert len(removed_events) == 1
    assert removed_events[0].spatial_effect_uuid == grease_effect.uuid
    assert removed_events[0].previous_positions


def test_second_overlapping_grease_replaces_exact_material_without_raw_error() -> None:
    """Two ordinary casts share one material layer without stacked terrain."""
    reset_spell_family_state(width=24, height=24)
    first_caster = create_family_caster(
        name="First Grease Caster",
        position=(2, 2),
        spell_slots={1: 1},
    )
    second_caster = create_family_caster(
        name="Second Grease Caster",
        position=(2, 3),
        spell_slots={1: 1},
    )
    Entity.materialize_all_navigation(max_distance=120)

    first_event = Grease(
        source_entity_uuid=first_caster.uuid,
        end_position=(10, 10),
        template=False,
    ).apply()
    second_event = Grease(
        source_entity_uuid=second_caster.uuid,
        end_position=(10, 10),
        template=False,
    ).apply()

    assert_completed_spell(first_event)
    assert_completed_spell(second_event)
    active = [
        effect
        for effect in get_map().get_spatial_conditions()
        if effect.content_ref == GREASE_SURFACE_RECIPE.ref
    ]
    assert len(active) == 1
    assert active[0].source_entity_uuid == second_caster.uuid
    center = get_map().get_tile(10, 10)
    assert center is not None
    assert center.walking_cost.normalized_score == 2


def test_daylight_has_an_independent_lifetime_from_caster_concentration() -> None:
    """Daylight persists when its caster starts and drops another concentration."""
    reset_spell_family_state(width=40, height=40)
    caster = create_family_caster(
        position=(3, 3),
        spell_slots={2: 1, 3: 1},
    )
    Entity.materialize_all_navigation(max_distance=200)

    daylight_event = Daylight(
        source_entity_uuid=caster.uuid,
        end_position=(12, 12),
        template=False,
    ).apply()
    assert_completed_spell(daylight_event)
    assert "Concentrating" not in caster.active_conditions
    assert "Daylight Zone" not in caster.active_conditions
    daylight_effect_uuids = get_map().get_spatial_condition_uuids_at((12, 12))
    assert len(daylight_effect_uuids) == 1
    daylight_effect = BaseCondition.get(next(iter(daylight_effect_uuids)))
    assert isinstance(daylight_effect, SpatialCondition)
    daylight_zone = cast(
        AreaCondition,
        daylight_effect,
    )
    assert daylight_zone.duration.duration_type is DurationType.ROUNDS
    assert daylight_zone.duration.duration == 600

    center_tile = get_map().get_tile(12, 12)
    assert center_tile is not None
    assert center_tile.resolved_light_level == LightLevel.VERY_BRIGHT

    caster.on_turn_start(round_number=2, turn_index=0)
    fog_event = FogCloud(
        source_entity_uuid=caster.uuid,
        end_position=(3, 14),
        cast_at_level=2,
        template=False,
    ).apply()
    assert_completed_spell(fog_event)
    assert "Concentrating" in caster.active_conditions
    caster.remove_condition("Concentrating")

    assert center_tile.resolved_light_level == LightLevel.VERY_BRIGHT
    for _ in range(599):
        assert not daylight_effect.progress_spatial_duration()
    assert daylight_effect.progress_spatial_duration()
    assert BaseCondition.get(daylight_effect.uuid) is None
    assert get_map().get_spatial_condition_uuids_at((12, 12)) == set()
    assert center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT


def test_eb_15_026_light_zone_spells_apply_obscurement_and_dispel_darkness() -> None:
    """EB-15-026: light-zone spells alter tiles and Daylight dispels Darkness."""
    reset_spell_family_state(width=36, height=36)
    caster = create_family_caster(position=(8, 8), spell_slots={2: 1})
    Entity.materialize_all_navigation(max_distance=160)

    fog_event = FogCloud(
        source_entity_uuid=caster.uuid,
        end_position=(16, 16),
        cast_at_level=2,
        template=False,
    ).apply()

    fog_event = assert_completed_spell(fog_event)
    fog_effect = active_spatial_condition("Fog Cloud Zone")
    assert isinstance(fog_effect, SpatialCondition)
    fog_zone = cast(AreaCondition, fog_effect)
    fog_center_tile = get_map().get_tile(16, 16)
    fog_edge_tile = get_map().get_tile(24, 16)
    fog_outside_tile = get_map().get_tile(25, 16)
    assert fog_center_tile is not None
    assert fog_edge_tile is not None
    assert fog_outside_tile is not None
    assert fog_zone.zone_radius_feet == 40
    assert (24, 16) in fog_zone.affected_positions
    assert fog_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert fog_edge_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert fog_outside_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert get_map().get_optical_obscurements_at((16, 16)) == (
        OpticalObscurement.HEAVY,
    )
    assert get_map().get_optical_obscurements_at((24, 16)) == (
        OpticalObscurement.HEAVY,
    )
    assert "Concentrating" in caster.active_conditions

    caster.remove_condition("Concentrating")
    assert "Fog Cloud Zone" not in caster.active_conditions
    assert BaseCondition.get(fog_effect.uuid) is None
    assert fog_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT

    reset_spell_family_state(width=24, height=24)
    dark_caster = create_family_caster(
        name="Dark Caster",
        position=(6, 6),
        spell_slots={2: 1},
        faction="monsters",
    )
    light_caster = create_family_caster(
        name="Light Caster",
        position=(6, 7),
        spell_slots={3: 1},
        faction="heroes",
    )
    darkvision_observer = create_family_target(
        name="Darkvision Observer",
        position=(10, 10),
        faction="heroes",
    )
    darkvision_observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
    ]
    Entity.materialize_all_navigation(max_distance=120)

    darkness_event = Darkness(
        source_entity_uuid=dark_caster.uuid,
        end_position=(11, 10),
        template=False,
    ).apply()

    darkness_event = assert_completed_spell(darkness_event)
    darkness_effect = active_spatial_condition(
        "Darkness Zone",
    )
    assert isinstance(darkness_effect, SpatialCondition)
    darkness_zone = cast(AreaCondition, darkness_effect)
    center_tile = get_map().get_tile(11, 10)
    assert center_tile is not None
    assert center_tile.resolved_light_level == LightLevel.DARKNESS
    assert get_map().get_optical_obscurements_at((11, 10)) == (
        OpticalObscurement.MAGICAL_DARKNESS,
    )
    assert (11, 10) not in light_caster.senses.visible
    assert (11, 10) not in darkvision_observer.senses.visible
    assert "Concentrating" in dark_caster.active_conditions

    daylight_event = Daylight(
        source_entity_uuid=light_caster.uuid,
        end_position=(11, 10),
        template=False,
    ).apply()

    daylight_event = assert_completed_spell(daylight_event)
    daylight_effect_uuids = get_map().get_spatial_condition_uuids_at((11, 10))
    assert len(daylight_effect_uuids) == 1
    daylight_effect = BaseCondition.get(next(iter(daylight_effect_uuids)))
    assert isinstance(daylight_effect, SpatialCondition)
    daylight_zone = cast(
        AreaCondition,
        daylight_effect,
    )
    assert darkness_zone.uuid not in dark_caster.active_conditions_by_uuid
    assert "Darkness Zone" not in dark_caster.active_conditions
    assert BaseCondition.get(darkness_effect.uuid) is None
    assert "Concentrating" not in dark_caster.active_conditions
    assert center_tile.resolved_light_level == LightLevel.VERY_BRIGHT
    assert (11, 10) in daylight_zone.affected_positions
    assert "Concentrating" not in light_caster.active_conditions


def test_eb_15_027_damage_zones_cover_upcast_obscurement_and_movement() -> None:
    """EB-15-027: damage zones cover upcast dice, obscurement, and movement."""
    reset_spell_family_state(width=24, height=24)
    caster = create_family_caster(position=(5, 5), spell_slots={7: 1})
    target = create_family_target(name="Insect Target", position=(10, 5), hp_dice=20)
    penalize_save(target, "constitution")
    set_hp(target, 300)
    Entity.materialize_all_navigation(max_distance=120)

    target_hp_before = get_hp(target)
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        plague_event = InsectPlague(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            cast_at_level=7,
            template=False,
        ).apply()

    plague_event = assert_completed_spell(plague_event)
    plague_effect = active_spatial_condition(
        "Insect Plague Zone",
    )
    assert isinstance(plague_effect, SpatialCondition)
    plague_zone = cast(AreaCondition, plague_effect)
    plague_center_tile = get_map().get_tile(10, 5)
    assert plague_center_tile is not None
    assert plague_zone.adds_difficult_terrain
    assert plague_zone.sets_light_level is None
    assert plague_center_tile.walking_cost.normalized_score == 2
    assert plague_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert target_hp_before - get_hp(target) == 18
    assert caster.action_economy.spell_slot_7.normalized_score == 0

    caster.remove_condition("Concentrating")
    assert "Insect Plague Zone" not in caster.active_conditions
    assert BaseCondition.get(plague_effect.uuid) is None
    assert plague_center_tile.walking_cost.normalized_score == 1
    assert plague_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT

    reset_spell_family_state(width=30, height=30)
    caster = create_family_caster(position=(5, 10), spell_slots={8: 1})
    target = create_family_target(name="Cloud Target", position=(10, 10), hp_dice=20)
    penalize_save(target, "dexterity")
    set_hp(target, 300)
    Entity.materialize_all_navigation(max_distance=120)

    target_hp_before = get_hp(target)
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        cloud_event = IncendiaryCloud(
            source_entity_uuid=caster.uuid,
            end_position=(10, 10),
            template=False,
        ).apply()

    cloud_event = assert_completed_spell(cloud_event)
    cloud_effect = active_spatial_condition(
        "Incendiary Cloud Zone",
    )
    assert isinstance(cloud_effect, SpatialCondition)
    cloud_zone = cast(AreaCondition, cloud_effect)
    old_center = cloud_zone.position
    old_center_tile = get_map().get_tile(*old_center)
    old_trailing_tile = get_map().get_tile(6, 10)
    assert old_center_tile is not None
    assert old_trailing_tile is not None
    assert not cloud_zone.adds_difficult_terrain
    assert cloud_zone.sets_light_level is None
    assert get_map().get_optical_obscurements_at(old_center) == (
        OpticalObscurement.HEAVY,
    )
    assert old_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert old_trailing_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert target_hp_before - get_hp(target) == 30
    assert caster.action_economy.spell_slot_8.normalized_score == 0

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        caster.on_turn_start(round_number=1, turn_index=0)

    new_center = cloud_zone.position
    new_center_tile = get_map().get_tile(*new_center)
    new_leading_tile = get_map().get_tile(16, 10)
    assert new_center != old_center
    assert new_center_tile is not None
    assert new_leading_tile is not None
    assert old_trailing_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert get_map().get_optical_obscurements_at(new_center) == (
        OpticalObscurement.HEAVY,
    )
    assert new_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert new_leading_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT


def test_eb_15_028_gas_and_ice_zones_match_srd_turn_start_edges() -> None:
    """EB-15-028: Stinking Cloud and Sleet Storm preserve SRD zone edges."""
    reset_spell_family_state(width=24, height=18)
    caster = create_family_caster(position=(5, 5), spell_slots={3: 2})
    retching_target = create_family_target(name="Retching Target", position=(10, 5), hp_dice=8)
    immune_target = create_family_target(name="Poison Immune Target", position=(10, 6), hp_dice=8)
    penalize_save(retching_target, "constitution")
    penalize_save(immune_target, "constitution")
    immune_target.health.damage_reduction.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=immune_target.uuid,
            target_entity_uuid=immune_target.uuid,
            value=ResistanceStatus.IMMUNITY,
            damage_type=DamageType.POISON,
            name="Book poison immunity",
        )
    )
    Entity.materialize_all_navigation(max_distance=120)

    with patch("dnd.core.dice.random.randint", return_value=10):
        cloud_event = StinkingCloud(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            template=False,
        ).apply()

    cloud_event = assert_completed_spell(cloud_event)
    cloud_effect = active_spatial_condition(
        "Stinking Cloud Zone",
    )
    assert isinstance(cloud_effect, SpatialCondition)
    cloud_zone = cast(AreaCondition, cloud_effect)
    cloud_center_tile = get_map().get_tile(10, 5)
    assert cloud_center_tile is not None
    assert not cloud_zone.adds_difficult_terrain
    assert cloud_zone.sets_light_level is None
    assert get_map().get_optical_obscurements_at((10, 5)) == (
        OpticalObscurement.HEAVY,
    )
    assert cloud_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert "Nauseated" not in retching_target.active_conditions

    with patch("dnd.core.dice.random.randint", return_value=10):
        retching_target.on_turn_start(round_number=1, turn_index=0)

    assert "Nauseated" in retching_target.active_conditions
    assert retching_target.action_economy.actions.normalized_score == 0
    assert retching_target.action_economy.bonus_actions.normalized_score == 1
    assert retching_target.action_economy.reactions.normalized_score == 1
    assert retching_target.action_economy.movement.normalized_score > 0

    with patch("dnd.core.dice.random.randint", return_value=10):
        immune_target.on_turn_start(round_number=1, turn_index=1)

    assert "Nauseated" not in immune_target.active_conditions
    caster.remove_condition("Concentrating")
    assert "Stinking Cloud Zone" not in caster.active_conditions
    assert BaseCondition.get(cloud_effect.uuid) is None
    assert cloud_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT

    reset_spell_family_state(width=24, height=18)
    grid = get_map()
    grid.set_tile(
        11,
        10,
        surface=TileSurface(base_material=Material.STONE),
            walking_cost=0,
        blocks_optics=True,
        blocks_propagation=True,
        name="Wall",
    )
    caster = create_family_caster(position=(10, 5), spell_slots={3: 1})
    concentrating_target = create_family_target(
        name="Concentrating Target",
        position=(12, 10),
        hp_dice=8,
    )
    penalize_save(concentrating_target, "dexterity")
    Entity.materialize_all_navigation(max_distance=120)

    with patch("dnd.core.dice.random.randint", return_value=10):
        storm_event = SleetStorm(
            source_entity_uuid=caster.uuid,
            end_position=(10, 10),
            template=False,
        ).apply()

    storm_event = assert_completed_spell(storm_event)
    storm_effect = active_spatial_condition(
        "Sleet Storm Zone",
    )
    assert isinstance(storm_effect, SpatialCondition)
    storm_zone = cast(AreaCondition, storm_effect)
    storm_center_tile = get_map().get_tile(10, 10)
    assert storm_center_tile is not None
    assert storm_zone.zone_shape == "cylinder"
    assert concentrating_target.position in storm_zone.affected_positions
    assert "Prone" not in concentrating_target.active_conditions
    assert storm_center_tile.walking_cost.normalized_score == 2
    assert get_map().get_optical_obscurements_at((10, 10)) == (
        OpticalObscurement.HEAVY,
    )
    assert storm_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT

    concentrating_target.add_condition(
        Concentrating(
            source_entity_uuid=concentrating_target.uuid,
            target_entity_uuid=concentrating_target.uuid,
            spell_name="Book Probe",
        )
    )
    assert "Concentrating" in concentrating_target.active_conditions

    with patch("dnd.core.dice.random.randint", return_value=12):
        concentrating_target.on_turn_start(round_number=1, turn_index=0)

    assert "Prone" in concentrating_target.active_conditions
    assert "Concentrating" not in concentrating_target.active_conditions
    caster.remove_condition("Concentrating")
    assert "Sleet Storm Zone" not in caster.active_conditions
    assert BaseCondition.get(storm_effect.uuid) is None
    assert storm_center_tile.walking_cost.normalized_score == 1
    assert storm_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT


def test_eb_15_041_stinking_cloud_skips_breathless_creatures() -> None:
    """EB-15-041: Stinking Cloud skips creatures that do not breathe."""
    reset_spell_family_state(width=24, height=18)
    caster = create_family_caster(position=(5, 5), spell_slots={3: 1})
    breathing_target = create_family_target(
        name="Breathing Target",
        position=(10, 5),
        hp_dice=8,
    )
    breathless_target = create_family_target(
        name="Breathless Target",
        position=(10, 6),
        hp_dice=8,
        requires_breathing=False,
    )
    penalize_save(breathing_target, "constitution")
    penalize_save(breathless_target, "constitution")
    Entity.materialize_all_navigation(max_distance=120)

    with patch("dnd.core.dice.random.randint", return_value=10):
        cloud_event = StinkingCloud(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            template=False,
        ).apply()

    cloud_event = assert_completed_spell(cloud_event)
    cloud_effect = active_spatial_condition(
        "Stinking Cloud Zone",
    )
    assert isinstance(cloud_effect, SpatialCondition)
    cloud_zone = cast(AreaCondition, cloud_effect)
    assert breathing_target.position in cloud_zone.affected_positions
    assert breathless_target.position in cloud_zone.affected_positions
    assert breathing_target.requires_breathing is True
    assert breathless_target.requires_breathing is False

    with patch("dnd.core.dice.random.randint", return_value=10):
        breathing_target.on_turn_start(round_number=1, turn_index=0)

    assert "Nauseated" in breathing_target.active_conditions

    saving_throw_count = len(EventQueue.get_events_by_type(EventType.SAVING_THROW))
    with patch("dnd.core.dice.random.randint", return_value=1):
        breathless_target.on_turn_start(round_number=1, turn_index=1)

    assert "Nauseated" not in breathless_target.active_conditions
    assert breathless_target.action_economy.actions.normalized_score == 1
    assert len(EventQueue.get_events_by_type(EventType.SAVING_THROW)) == saving_throw_count


def test_gust_wind_exposure_uses_the_complete_child_lifecycle() -> None:
    """Persistent wind is a typed child fact, not an effect-only shortcut."""
    reset_spell_family_state(width=24, height=18)
    caster = create_family_caster(position=(2, 2), spell_slots={2: 1})
    Entity.materialize_all_navigation(max_distance=120)

    gust_event = GustOfWind(
        source_entity_uuid=caster.uuid,
        end_position=(10, 2),
        template=False,
    ).apply()

    gust_event = assert_completed_spell(gust_event)
    wind_events = [
        event
        for event in EventQueue.get_events_by_type(
            EventType.SPATIAL_EFFECT_INTERACTION
        )
        if isinstance(event, SpatialEffectInteractionEvent)
        and event.operation is SpatialEffectInteractionOperation.DISPERSE
        and event.parent_event is not None
    ]
    assert [event.phase for event in wind_events] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    parent_ids = {event.parent_event for event in wind_events}
    assert len(parent_ids) == 1
    parent_id = next(iter(parent_ids))
    assert parent_id is not None
    wind_parent = EventQueue.get_event_by_uuid(parent_id)
    assert wind_parent is not None
    assert wind_parent.event_type is EventType.CONDITION_APPLICATION
    assert wind_parent.parent_event is not None
    spell_parent = EventQueue.get_event_by_uuid(wind_parent.parent_event)
    assert spell_parent is not None
    assert spell_parent.lineage_uuid == gust_event.lineage_uuid


def test_object_spell_shared_validator_rejects_out_of_reach_target() -> None:
    """Object spells cannot bypass their authored reach with a custom target."""
    reset_spell_family_state(width=12, height=8)
    caster = create_family_caster(
        position=(1, 1),
        spell_slots={2: 1},
    )
    focus = BaseItem(
        source_entity_uuid=caster.uuid,
        semantic_key="environment.blocker.oil_barrel",
        name="Oil Barrel",
        is_pickable=False,
        is_targetable=True,
    )
    focus.place_on_grid((4, 1))
    Entity.materialize_all_navigation(max_distance=120)

    event = ContinualFlame(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=focus.uuid,
        template=False,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert event.canceled
    assert event.status_message == "Target object is out of reach"


def test_heroes_feast_publishes_exactly_one_floor_fact() -> None:
    """Spell-created floor objects have one exact committed placement fact."""
    reset_spell_family_state()
    caster = create_family_caster(position=(1, 1), spell_slots={6: 1})
    cursor = EventQueue.event_cursor()

    assert_completed_spell(
        HeroesFeast(
            source_entity_uuid=caster.uuid,
            end_position=(2, 1),
            template=False,
        ).apply()
    )
    feast_uuid = next(iter(get_map().get_objects_at((2, 1))))
    floor_facts = [
        candidate
        for _index, candidate in EventQueue.iter_events_since(cursor)
        if isinstance(candidate, ItemLocationStateEvent)
        and candidate.item_state.item_uuid == feast_uuid
        and candidate.location is ItemLocation.FLOOR
    ]
    assert len(floor_facts) == 1
    assert floor_facts[0].world_placement == get_map().get_object_placement(feast_uuid)
    assert floor_facts[0].world_placement is not None
    assert floor_facts[0].world_placement.object_uuid == feast_uuid


def test_continual_flame_relocates_and_cleans_up_with_its_anchor() -> None:
    """An anchored permanent flame follows relocation and terminal removal."""
    reset_spell_family_state(width=8, height=3)
    caster = create_family_caster(position=(0, 1), spell_slots={2: 1})
    focus = BaseItem(source_entity_uuid=caster.uuid, name="Flame focus")
    focus.place_on_grid((1, 1))
    Entity.materialize_all_navigation(max_distance=40)

    assert_completed_spell(
        ContinualFlame(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=focus.uuid,
            template=False,
        ).apply()
    )
    condition = next(
        candidate
        for candidate in get_map().get_spatial_conditions()
        if candidate.anchor_uuid == focus.uuid
    )
    assert condition.position == (1, 1)
    assert get_map().get_tile(1, 1).resolved_light_level is LightLevel.BRIGHT_LIGHT

    grid = get_map()
    grid.move_object(focus.uuid, (3, 1))

    assert condition.position == (3, 1)
    assert condition.affected_positions == {(3, 1)}
    assert get_map().get_tile(3, 1).resolved_light_level is LightLevel.BRIGHT_LIGHT
    grid.remove_object(focus.uuid)
    assert condition.uuid not in {candidate.uuid for candidate in grid.get_spatial_conditions()}
    assert get_map().get_tile(3, 1).resolved_light_level is LightLevel.BRIGHT_LIGHT


def test_entity_spell_shared_validator_rejects_unseen_target() -> None:
    """Single-target spells cannot bypass line of sight with a custom validator."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 1})
    target = create_family_target(
        name="Unseen Ally",
        position=(2, 1),
        faction="heroes",
    )
    Entity.materialize_all_navigation()
    caster.senses.entities.pop(target.uuid, None)

    event = Invisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert event.canceled
    assert event.status_message == "Unseen Ally not in line of sight"
    assert "Invisibility" not in target.active_conditions


def test_aoe_candidate_compaction_never_mutates_shared_shape() -> None:
    """AoE discovery evaluates immutable candidates, not a shared fake target."""
    reset_spell_family_state()
    caster = create_family_caster()
    shape = Sphere(
        source_entity_uuid=caster.uuid,
        target=(2, 2),
        radius_feet=10,
    )
    original_target = shape.target
    observed_original_targets = []
    footprint_target_key = Sphere.footprint_target_key

    def observe_candidate(
        candidate: Sphere,
        caster_position: tuple[int, int],
        *,
        target_override: tuple[int, int] | None = None,
    ) -> tuple[object, ...]:
        observed_original_targets.append(shape.target)
        return footprint_target_key(
            candidate,
            caster_position,
            target_override=target_override,
        )

    with patch.object(Sphere, "footprint_target_key", observe_candidate):
        caster._compact_aoe_candidate_positions(
            shape,
            [(3, 2), (4, 2), (5, 2)],
        )

    assert observed_original_targets == [original_target] * 3
    assert shape.target == original_target


def test_eb_15_044_stinking_cloud_wind_dispersal_uses_srd_rounds() -> None:
    """EB-15-044: Stinking Cloud disperses after SRD wind exposure rounds."""
    reset_spell_family_state(width=24, height=18)
    caster = create_family_caster(position=(2, 2), spell_slots={3: 1})
    Entity.materialize_all_navigation(max_distance=120)

    cloud_event = StinkingCloud(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        template=False,
    ).apply()

    cloud_event = assert_completed_spell(cloud_event)
    cloud_effect = active_spatial_condition(
        "Stinking Cloud Zone",
    )
    assert isinstance(cloud_effect, SpatialCondition)
    cloud_zone = cast(StinkingCloudZone, cloud_effect)
    assert (10, 5) in cloud_zone.affected_positions
    assert len(cloud_zone.event_handlers_uuids) == 1

    moderate_wind = SpatialEffectInteractionEvent(
        source_entity_uuid=caster.uuid,
        operation=SpatialEffectInteractionOperation.DISPERSE,
        positions=((10, 5),),
        intensity=SpatialEffectInteractionIntensity.MODERATE,
        phase=EventPhase.DECLARATION,
    )
    moderate_wind = moderate_wind.phase_to(EventPhase.EFFECT)
    moderate_wind = moderate_wind.phase_to(EventPhase.COMPLETION)

    assert moderate_wind.phase == EventPhase.COMPLETION
    assert BaseCondition.get(cloud_effect.uuid) is cloud_effect
    for _ in range(1, 4):
        assert not cloud_effect.progress_spatial_duration()
        assert BaseCondition.get(cloud_effect.uuid) is cloud_effect

    assert cloud_effect.progress_spatial_duration()
    assert "Stinking Cloud Zone" not in caster.active_conditions
    assert BaseCondition.get(cloud_effect.uuid) is None
    assert "Concentrating" not in caster.active_conditions
    assert cloud_zone.event_handlers_uuids == []

    reset_spell_family_state(width=24, height=18)
    cloud_caster = create_family_caster(name="Cloud Caster", position=(1, 1), spell_slots={3: 1})
    wind_caster = create_family_caster(name="Wind Caster", position=(2, 5), spell_slots={2: 1})
    Entity.materialize_all_navigation(max_distance=120)

    cloud_event = StinkingCloud(
        source_entity_uuid=cloud_caster.uuid,
        end_position=(8, 5),
        template=False,
    ).apply()

    cloud_event = assert_completed_spell(cloud_event)
    cloud_effect = active_spatial_condition(
        "Stinking Cloud Zone",
    )
    assert isinstance(cloud_effect, SpatialCondition)
    cloud_zone = cast(StinkingCloudZone, cloud_effect)
    wind_event = GustOfWind(
        source_entity_uuid=wind_caster.uuid,
        end_position=(12, 5),
        template=False,
    ).apply()
    assert_completed_spell(wind_event)
    gust_zone = cast(
        GustOfWindZone,
        active_spatial_condition("Gust of Wind Zone"),
    )

    assert (8, 5) in gust_zone.affected_positions
    assert BaseCondition.get(cloud_effect.uuid) is cloud_effect

    assert cloud_effect.progress_spatial_duration()

    assert "Stinking Cloud Zone" not in cloud_caster.active_conditions
    assert BaseCondition.get(cloud_effect.uuid) is None
    assert "Concentrating" not in cloud_caster.active_conditions
    assert cloud_zone.event_handlers_uuids == []


def test_eb_15_045_gust_terrain_removal_restores_cached_move_targets() -> None:
    """EB-15-045: ending Gust invalidates paths cached with difficult terrain."""
    reset_spell_family_state(width=25, height=21)
    grid = get_map()
    for x in range(25):
        grid.set_tile(
            x,
            9,
            surface=TileSurface(base_material=Material.STONE),
            walking_cost=0,
            blocks_optics=True,
            blocks_propagation=True,
            name="Wall",
        )
        grid.set_tile(
            x,
            11,
            surface=TileSurface(base_material=Material.STONE),
            walking_cost=0,
            blocks_optics=True,
            blocks_propagation=True,
            name="Wall",
        )

    caster = create_family_caster(
        position=(1, 10),
        spell_slots={2: 1},
    )
    mover = create_family_target(
        name="Mover",
        position=(5, 10),
    )
    setup_standard_actions(mover)
    boost_save(mover, "strength")
    Entity.materialize_all_navigation(max_distance=20)
    mover.materialize_navigation(max_distance=20, path_max_distance=6)

    def move_targets() -> set[tuple[int, int]]:
        move = next(
            action
            for action in mover.get_available_actions().position_actions
            if action.template_name == "Move"
        )
        return {
            target.position
            for target in move.valid_targets
            if target.position is not None
        }

    targets_before = move_targets()
    revision_before = grid.movement_revision
    cast_event = GustOfWind(
        source_entity_uuid=caster.uuid,
        end_position=(20, 10),
        cast_at_level=2,
        template=False,
    ).apply()

    assert_completed_spell(cast_event)
    assert mover.position == (5, 10)
    assert grid.movement_revision > revision_before

    targets_during = move_targets()
    assert len(targets_during) < len(targets_before)
    revision_during = grid.movement_revision

    caster.remove_condition("Concentrating")

    assert grid.movement_revision > revision_during
    targets_restored = move_targets()
    assert targets_restored == targets_before


def test_eb_15_043_sleet_storm_douses_exposed_flames() -> None:
    """EB-15-043: Sleet Storm douses exposed carried and placed flames."""
    reset_spell_family_state(width=24, height=18)
    grid = get_map()
    caster = create_family_caster(position=(5, 5), spell_slots={3: 1})
    torchbearer = create_family_target(name="Torchbearer", position=(10, 5), hp_dice=8)
    penalize_save(torchbearer, "dexterity")
    carried_torch = build_torch(torchbearer.uuid)
    torchbearer.loot_item(carried_torch)
    carried_torch.ignite(torchbearer.uuid)
    wall_torch = build_wall_torch()
    wall_torch.mount(
        (10, 6),
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=1,
        orientation=CardinalDirection.WEST,
        lit=True,
    )
    outside_torch = build_wall_torch()
    outside_torch.mount(
        (1, 1),
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=1,
        orientation=CardinalDirection.WEST,
        lit=True,
    )
    carried_light_uuid = carried_torch._light_source_uuid
    wall_light_uuid = wall_torch._light_source_uuid
    outside_light_uuid = outside_torch._light_source_uuid
    assert carried_torch.is_lit and carried_light_uuid in grid._light_sources
    assert wall_torch.is_lit and wall_light_uuid in grid._light_sources
    assert outside_torch.is_lit and outside_light_uuid in grid._light_sources
    Entity.materialize_all_navigation(max_distance=120)

    with patch("dnd.core.dice.random.randint", return_value=10):
        storm_event = SleetStorm(
            source_entity_uuid=caster.uuid,
            end_position=(10, 5),
            template=False,
        ).apply()

    storm_event = assert_completed_spell(storm_event)
    storm_effect = active_spatial_condition(
        "Sleet Storm Zone",
    )
    assert isinstance(storm_effect, SpatialCondition)
    storm_zone = cast(SleetStormZone, storm_effect)
    storm_center_tile = get_map().get_tile(10, 5)
    assert storm_center_tile is not None
    assert torchbearer.position in storm_zone.affected_positions
    assert (10, 6) in storm_zone.affected_positions
    assert len(storm_zone.event_handlers_uuids) == 2
    assert carried_torch.is_lit is False
    assert carried_torch._light_source_uuid is None
    assert carried_light_uuid not in grid._light_sources
    assert wall_torch.is_lit is False
    assert wall_torch._light_source_uuid is None
    assert wall_light_uuid not in grid._light_sources
    assert outside_torch.is_lit is True
    assert outside_torch._light_source_uuid == outside_light_uuid
    assert outside_light_uuid in grid._light_sources
    assert "Prone" not in torchbearer.active_conditions

    with patch("dnd.core.dice.random.randint", return_value=10):
        torchbearer.on_turn_start(round_number=1, turn_index=0)
    assert "Prone" in torchbearer.active_conditions

    carried_torch.ignite(torchbearer.uuid)
    assert carried_torch.is_lit is False
    assert carried_torch._light_source_uuid is None

    wall_torch.light()
    assert wall_torch.is_lit is False
    assert wall_torch._light_source_uuid is None

    caster.remove_condition("Concentrating")
    assert "Sleet Storm Zone" not in caster.active_conditions
    assert BaseCondition.get(storm_effect.uuid) is None
    assert storm_zone.event_handlers_uuids == []
    assert outside_torch.is_lit is True
    assert outside_torch._light_source_uuid in grid._light_sources
    assert storm_center_tile.walking_cost.normalized_score == 1
    assert storm_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT


def test_eb_15_029_web_models_obscurement_grounding_and_escape_cleanup() -> None:
    """EB-15-029: Web models obscurement, grounded persistence, and escape cleanup."""
    reset_spell_family_state(width=18, height=18)
    caster = create_family_caster(position=(1, 1), spell_slots={2: 1})
    target = create_family_target(name="Web Target", position=(5, 5), hp_dice=8)
    penalize_save(target, "dexterity")
    target.ability_scores.strength.modifier_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            name="Deterministic raw Strength escape boost",
            value=100,
        )
    )
    Entity.materialize_all_navigation(max_distance=60)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        web_event = Web(
            source_entity_uuid=caster.uuid,
            end_position=(5, 5),
            template=False,
        ).apply()

    web_event = assert_completed_spell(web_event)
    web_effect = active_spatial_condition("Web Zone")
    assert isinstance(web_effect, SpatialCondition)
    assert web_effect.content_ref == WEB_SURFACE_RECIPE.ref
    web_zone = cast(AreaCondition, web_effect)
    web_center_tile = get_map().get_tile(5, 5)
    assert web_center_tile is not None
    assert web_zone.zone_shape == "cube"
    assert web_zone.adds_difficult_terrain
    assert web_zone.sets_light_level is None
    assert web_center_tile.walking_cost.normalized_score == 2
    assert web_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert "Web Restrained" not in target.active_conditions
    assert "Restrained" not in target.active_conditions

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        target.on_turn_start(round_number=1, turn_index=0)

    assert any(
        isinstance(condition, WebRestrained)
        for condition in target.active_conditions_by_uuid.values()
    )
    assert "Restrained" in target.active_conditions
    assert BaseCondition.get(web_effect.uuid) is web_effect
    escape = next(
        action for action in target.registered_actions if action.name == "Escape Web"
    ).instantiate()
    with patch("dnd.core.dice.random.randint", return_value=10):
        escape_event = escape.apply()

    assert escape_event is not None
    assert not escape_event.canceled
    assert not any(
        isinstance(condition, WebRestrained)
        for condition in target.active_conditions_by_uuid.values()
    )
    assert "Restrained" not in target.active_conditions
    assert all(action.name != "Escape Web" for action in target.registered_actions)

    caster.remove_condition("Concentrating")
    assert "Web Zone" not in caster.active_conditions
    assert BaseCondition.get(web_effect.uuid) is None
    assert web_center_tile.walking_cost.normalized_score == 1
    assert web_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT


def test_eb_15_037_web_unanchored_cast_collapses_on_caster_turn_start() -> None:
    """EB-15-037: unanchored Web ends at the caster's next turn start."""
    reset_spell_family_state(width=18, height=18)
    caster = create_family_caster(position=(1, 1), spell_slots={2: 1})
    Entity.materialize_all_navigation(max_distance=60)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        web_event = Web(
            source_entity_uuid=caster.uuid,
            end_position=(5, 5),
            anchored_or_layered=False,
            template=False,
        ).apply()

    web_event = assert_completed_spell(web_event)
    web_effect = active_spatial_condition("Web Zone")
    web_zone = cast(WebZone, web_effect)
    web_center_tile = get_map().get_tile(5, 5)
    assert web_center_tile is not None
    assert not web_zone.anchored_or_layered
    assert {
        EventQueue._event_handlers[handler_uuid].name
        for handler_uuid in web_zone.event_handlers_uuids
    } == {"Web Turn Start Save", "Web Unanchored Collapse"}
    assert "Concentrating" in caster.active_conditions
    assert web_center_tile.walking_cost.normalized_score == 2
    assert web_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT

    turn_start = caster.on_turn_start(round_number=2, turn_index=0)

    assert turn_start.phase == EventPhase.COMPLETION
    assert "Web Zone" not in caster.active_conditions
    assert "Concentrating" not in caster.active_conditions
    assert BaseCondition.get(web_effect.uuid) is None
    assert web_zone.event_handlers_uuids == []
    assert web_center_tile.walking_cost.normalized_score == 1
    assert web_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT


def test_eb_15_042_web_fire_exposure_burns_one_cube_for_one_round() -> None:
    """EB-15-042: Web fire exposure burns one cube and deals one-round fire."""
    reset_spell_family_state(width=18, height=18)
    caster = create_family_caster(position=(1, 1), spell_slots={2: 1})
    target = create_family_target(name="Web Fire Target", position=(5, 5), hp_dice=8)
    penalize_save(target, "dexterity")
    Entity.materialize_all_navigation(max_distance=60)

    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        web_event = Web(
            source_entity_uuid=caster.uuid,
            end_position=(5, 5),
            template=False,
        ).apply()

    web_event = assert_completed_spell(web_event)
    web_effect = active_spatial_condition("Web Zone")
    web_zone = cast(WebZone, web_effect)
    web_center_tile = get_map().get_tile(5, 5)
    adjacent_web_tile = get_map().get_tile(6, 5)
    assert web_center_tile is not None
    assert adjacent_web_tile is not None
    assert (5, 5) in web_zone.affected_positions
    assert (6, 5) in web_zone.affected_positions
    assert web_center_tile.walking_cost.normalized_score == 2
    assert web_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert "Web Restrained" not in target.active_conditions
    web_handlers = [
        EventQueue._event_handlers[handler_uuid]
        for handler_uuid in web_zone.event_handlers_uuids
    ]
    assert {handler.name for handler in web_handlers} == {"Web Turn Start Save"}
    assert all(
        handler.behavior_id == web_zone.behavior_id
        and handler.provided_by_id == web_zone.behavior_id
        for handler in web_handlers
    )

    fire_event = SpatialEffectInteractionEvent(
        source_entity_uuid=caster.uuid,
        operation=SpatialEffectInteractionOperation.IGNITE,
        positions=((5, 5),),
        intensity=SpatialEffectInteractionIntensity.STRONG,
        damage_type=DamageType.FIRE,
        phase=EventPhase.DECLARATION,
    )
    fire_event = fire_event.phase_to(EventPhase.EFFECT)
    fire_event = fire_event.phase_to(EventPhase.COMPLETION)

    assert fire_event.phase == EventPhase.COMPLETION
    assert (5, 5) not in web_zone.affected_positions
    assert (6, 5) in web_zone.affected_positions
    assert len(web_zone.event_handlers_uuids) == 1
    assert web_center_tile.walking_cost.normalized_score == 1
    assert web_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert adjacent_web_tile.walking_cost.normalized_score == 2
    assert adjacent_web_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
    assert "Web Restrained" not in target.active_conditions
    assert "Restrained" not in target.active_conditions
    assert all(action.name != "Escape Web" for action in target.registered_actions)

    burning_effects = [
        effect
        for effect in get_map().get_spatial_conditions()
        if effect.content_ref == BURNING_WEB_FIRE_RECIPE.ref
    ]
    assert len(burning_effects) == 1
    burning_effect = burning_effects[0]
    assert burning_effect.affected_positions == {(5, 5)}

    hp_before_fire = get_hp(target)
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        target.on_turn_start(round_number=1, turn_index=0)

    hp_after_fire = get_hp(target)
    assert hp_before_fire - hp_after_fire == 6
    assert "Web Restrained" not in target.active_conditions

    assert burning_effect.progress_spatial_duration()
    assert BaseCondition.get(burning_effect.uuid) is None
    with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
        target.on_turn_start(round_number=2, turn_index=0)

    assert get_hp(target) == hp_after_fire
    assert BaseCondition.get(web_effect.uuid) is web_effect
    assert "Concentrating" in caster.active_conditions

    caster.remove_condition("Concentrating")
    assert "Web Zone" not in caster.active_conditions
    assert BaseCondition.get(web_effect.uuid) is None
    assert web_zone.event_handlers_uuids == []
    assert adjacent_web_tile.walking_cost.normalized_score == 1
    assert adjacent_web_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT


def test_eb_15_011_haste_modifier_bundle_and_lethargy_cleanup() -> None:
    """EB-15-011: Haste applies a modifier bundle and lethargy on cleanup."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={3: 1})
    target = create_family_target(name="Hasted Ally", position=(3, 1), faction="heroes")
    Entity.materialize_all_navigation()
    base_speed = target.action_economy.movement.normalized_score
    base_ac_bonus = target.equipment.ac_bonus.normalized_score
    base_actions = target.action_economy.actions.normalized_score

    event = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    assert "Haste" in target.active_conditions
    assert "Concentrating" in caster.active_conditions
    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert (target.uuid, target.active_conditions["Haste"].uuid) in concentration.linked_conditions
    assert target.action_economy.movement.normalized_score == base_speed * 2
    assert target.equipment.ac_bonus.normalized_score == base_ac_bonus + 2
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.advantage
        == AdvantageStatus.ADVANTAGE
    )
    assert target.action_economy.actions.normalized_score == base_actions
    assert target.action_economy.resources["haste_action"].current == 1
    assert caster.action_economy.spell_slot_3.normalized_score == 0

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Haste" not in target.active_conditions
    assert "haste_action" not in target.action_economy.resources
    assert "Haste Lethargy" in target.active_conditions
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0


def test_eb_15_012_slow_multi_target_modifier_bundle_and_cleanup() -> None:
    """EB-15-012: Slow applies failed-save debuffs to each linked target."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={3: 1})
    target_one = create_family_target(name="Slowed One", position=(3, 1), faction="monsters")
    target_two = create_family_target(name="Slowed Two", position=(4, 1), faction="monsters")
    Entity.materialize_all_navigation()
    base_speed = target_one.action_economy.movement.normalized_score
    base_ac_bonus = target_one.equipment.ac_bonus.normalized_score
    base_dex_save = target_one.saving_throws.get_saving_throw("dexterity").bonus.normalized_score
    penalize_save(target_one, "wisdom")
    penalize_save(target_two, "wisdom")

    event = Slow(
        source_entity_uuid=caster.uuid,
        end_position=(3, 1),
        template=False,
    ).apply()

    event = assert_completed_spell(event)
    assert event.total_targets >= 2
    assert "Slowed" in target_one.active_conditions
    assert "Slowed" in target_two.active_conditions
    assert target_one.action_economy.movement.normalized_score == base_speed // 2
    assert target_one.equipment.ac_bonus.normalized_score == base_ac_bonus - 2
    assert (
        target_one.saving_throws.get_saving_throw("dexterity").bonus.normalized_score
        == base_dex_save - 2
    )
    assert target_one.action_economy.reactions.normalized_score == 0
    concentration = caster.active_conditions["Concentrating"]
    assert isinstance(concentration, Concentrating)
    assert len(concentration.linked_conditions) >= 2
    assert caster.action_economy.spell_slot_3.normalized_score == 0

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Slowed" not in target_one.active_conditions
    assert "Slowed" not in target_two.active_conditions
    assert target_one.action_economy.movement.normalized_score == base_speed
    assert target_one.equipment.ac_bonus.normalized_score == base_ac_bonus


def test_eb_15_013_sleep_hp_pool_selection_immunity_and_wake_on_damage() -> None:
    """EB-15-013: Sleep spends a lowest-HP pool and wakes targets on damage."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 2})
    low = create_family_target(name="Low HP Goblin", position=(5, 3), hp_dice=1)
    mid = create_family_target(name="Mid HP Goblin", position=(6, 3), hp_dice=1)
    high = create_family_target(name="High HP Bugbear", position=(7, 3), hp_dice=2)
    undead = create_family_target(name="Skeleton", position=(5, 4), hp_dice=1)
    set_hp(low, 5)
    set_hp(mid, 10)
    set_hp(high, 20)
    set_hp(undead, 1)
    undead.creature_type = CreatureType.UNDEAD
    Entity.materialize_all_navigation()

    selector = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(5, 3),
        template=False,
    )
    selector.hp_pool_rolled = 16
    selector.hp_pool_remaining = 16

    targets = selector.get_all_targets()
    repeated_targets = selector.get_all_targets()

    assert low.uuid in targets
    assert mid.uuid in targets
    assert high.uuid not in targets
    assert undead.uuid not in targets
    assert selector.hp_pool_remaining == 1
    assert repeated_targets == targets
    assert selector.hp_pool_remaining == 1

    sleep = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(5, 3),
        template=False,
    )
    sleep.hp_pool_rolled = 5
    sleep.hp_pool_remaining = 5

    event = sleep.apply()

    event = assert_completed_spell(event)
    assert "Sleep" in low.active_conditions
    assert "Unconscious" not in low.active_conditions
    assert low.action_economy.action_permission.normalized_score == 0
    assert low.senses.visual_access.normalized_score == 0
    assert "Sleep" not in mid.active_conditions
    assert sleep.hp_pool_remaining == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 1

    deal_damage_to(low, 1, source_uuid=caster.uuid)

    assert "Sleep" not in low.active_conditions
    assert "Unconscious" not in low.active_conditions
    assert low.action_economy.action_permission.normalized_score == 1
    assert low.senses.visual_access.normalized_score == 1


def test_eb_15_014_color_spray_hp_pool_skips_and_blinded_cleanup() -> None:
    """EB-15-014: Color Spray spends an HP pool over valid cone targets."""
    reset_spell_family_state(width=12, height=10)
    caster = create_family_caster(position=(5, 5), spell_slots={1: 2})
    already_blinded = create_family_target(name="Already Blinded", position=(6, 5), hp_dice=1)
    low = create_family_target(name="Low HP Goblin", position=(7, 5), hp_dice=1)
    high = create_family_target(name="High HP Ogre", position=(8, 5), hp_dice=2)
    set_hp(already_blinded, 3)
    set_hp(low, 8)
    set_hp(high, 15)
    already_blinded.add_condition(
        Blinded(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=already_blinded.uuid,
        )
    )
    Entity.materialize_all_navigation()

    selector = ColorSpray(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        template=False,
    )
    selector.hp_pool_rolled = 10
    selector.hp_pool_remaining = 10

    targets = selector.get_all_targets()
    repeated_targets = selector.get_all_targets()

    assert already_blinded.uuid not in targets
    assert low.uuid in targets
    assert high.uuid not in targets
    assert selector.hp_pool_remaining == 2
    assert repeated_targets == targets
    assert selector.hp_pool_remaining == 2

    color_spray = ColorSpray(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        template=False,
    )
    color_spray.hp_pool_rolled = 8
    color_spray.hp_pool_remaining = 8

    event = color_spray.apply()

    event = assert_completed_spell(event)
    assert "Color Spray" in low.active_conditions
    assert "Blinded" in low.active_conditions
    assert "Color Spray" not in already_blinded.active_conditions
    assert "Color Spray" not in high.active_conditions
    assert color_spray.hp_pool_remaining == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 1

    low.remove_condition("Color Spray")

    assert "Color Spray" not in low.active_conditions
    assert "Blinded" not in low.active_conditions


def test_eb_15_030_hp_pool_spells_cover_upcast_and_immunity_edges() -> None:
    """EB-15-030: HP-pool spells cover upcast dice and skip invalid targets."""
    reset_spell_family_state(width=14, height=10)
    caster = create_family_caster(position=(5, 5), spell_slots={3: 2})
    unconscious = create_family_target(name="Unconscious Goblin", position=(5, 3), hp_dice=1)
    undead = create_family_target(name="Undead Goblin", position=(6, 3), hp_dice=1)
    charmed_immune = create_family_target(name="Charmless Goblin", position=(7, 3), hp_dice=1)
    valid_sleep = create_family_target(name="Sleepable Goblin", position=(8, 3), hp_dice=1)
    set_hp(unconscious, 2)
    set_hp(undead, 3)
    set_hp(charmed_immune, 4)
    set_hp(valid_sleep, 5)
    unconscious.add_condition(
        Unconscious(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=unconscious.uuid,
        )
    )
    undead.creature_type = CreatureType.UNDEAD
    charmed_immune.add_condition_immunity("Charmed", immunity_name="Book charm immunity")
    Entity.materialize_all_navigation(max_distance=80)

    sleep_selector = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(5, 3),
        cast_at_level=3,
        template=False,
    )
    assert sleep_selector.get_hp_pool_dice() == (9, 8)
    sleep_selector.hp_pool_rolled = 20
    sleep_selector.hp_pool_remaining = 20

    sleep_targets = sleep_selector.get_all_targets()

    assert unconscious.uuid not in sleep_targets
    assert undead.uuid not in sleep_targets
    assert charmed_immune.uuid not in sleep_targets
    assert valid_sleep.uuid in sleep_targets
    assert sleep_selector.hp_pool_remaining == 15

    spray_unconscious = create_family_target(name="Spray Unconscious", position=(6, 5), hp_dice=1)
    spray_blinded = create_family_target(name="Spray Blinded", position=(6, 6), hp_dice=1)
    spray_immune = create_family_target(name="Spray Immune", position=(7, 5), hp_dice=1)
    spray_sightless = create_family_target(name="Spray Sightless", position=(8, 5), hp_dice=1)
    spray_valid = create_family_target(name="Spray Valid", position=(7, 6), hp_dice=1)
    set_hp(spray_unconscious, 2)
    set_hp(spray_blinded, 3)
    set_hp(spray_immune, 4)
    set_hp(spray_sightless, 1)
    set_hp(spray_valid, 5)
    spray_unconscious.add_condition(
        Unconscious(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=spray_unconscious.uuid,
        )
    )
    spray_blinded.add_condition(
        Blinded(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=spray_blinded.uuid,
        )
    )
    spray_immune.add_condition_immunity("Blinded", immunity_name="Book blind immunity")
    spray_sightless.has_ordinary_sight = False
    Entity.materialize_all_navigation(max_distance=80)

    color_selector = ColorSpray(
        source_entity_uuid=caster.uuid,
        end_position=(10, 7),
        cast_at_level=3,
        template=False,
    )
    assert color_selector.get_hp_pool_dice() == (10, 10)
    color_selector.hp_pool_rolled = 20
    color_selector.hp_pool_remaining = 20

    color_targets = color_selector.get_all_targets()

    assert spray_unconscious.uuid not in color_targets
    assert spray_blinded.uuid not in color_targets
    assert spray_immune.uuid not in color_targets
    assert spray_sightless.uuid not in color_targets
    assert spray_valid.uuid in color_targets
    assert color_selector.hp_pool_remaining == 15


def test_eb_15_031_eyebite_granted_action_lifecycle_and_repeat_save() -> None:
    """EB-15-031: Eyebite links first and repeat strikes to concentration."""
    reset_spell_family_state(width=12, height=8)
    caster = create_family_caster(position=(1, 1), spell_slots={6: 1})
    first = create_family_target(name="First Gaze Target", position=(4, 1))
    second = create_family_target(name="Second Gaze Target", position=(5, 1))
    penalize_save(first, "wisdom")
    penalize_save(second, "wisdom")
    Entity.materialize_all_navigation(max_distance=80)

    event = Eyebite(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=first.uuid,
        effect_choice="sickened",
        template=False,
        costs=[],
    ).apply()

    event = assert_completed_spell(event)
    assert "Concentrating" in caster.active_conditions
    assert "Sickened" in first.active_conditions
    assert caster.action_economy.spell_slot_6.normalized_score == 0

    strike_template = caster.get_action_template("Eyebite Strike")
    assert strike_template is not None
    strike_template_uuid = strike_template.uuid

    repeat_event = strike_template.instantiate(target_entity_uuid=second.uuid).apply()

    assert repeat_event is not None
    assert not repeat_event.canceled
    assert "Sickened" in second.active_conditions
    assert caster.action_economy.actions.normalized_score == 0

    boost_save(second, "wisdom", value=200)
    penalize_save(second, "constitution", value=-200)
    second.on_turn_end()

    assert "Sickened" not in second.active_conditions
    assert "Concentrating" in caster.active_conditions
    assert "Eyebite Strike" in [action.name for action in caster.registered_actions]

    caster.remove_condition("Concentrating")

    assert "Sickened" not in first.active_conditions
    assert "Concentrating" not in caster.active_conditions
    assert caster.get_action_template("Eyebite Strike") is None
    assert BaseObject.get(strike_template_uuid) is None


def test_eb_15_032_eyebite_blocks_successful_retargets_and_unseen_targets() -> None:
    """EB-15-032: Eyebite enforces save memory and visible targets."""
    reset_spell_family_state(width=12, height=8)
    caster = create_family_caster(position=(1, 1), spell_slots={6: 1})
    saved = create_family_target(name="Resolved Target", position=(4, 1))
    vulnerable = create_family_target(name="Fresh Target", position=(5, 1))
    boost_save(saved, "wisdom", value=200)
    penalize_save(vulnerable, "wisdom")
    Entity.materialize_all_navigation(max_distance=80)

    event = Eyebite(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=saved.uuid,
        effect_choice="sickened",
        template=False,
        costs=[],
    ).apply()

    event = assert_completed_spell(event)
    assert "Sickened" not in saved.active_conditions

    strike_template = caster.get_action_template("Eyebite Strike")
    assert strike_template is not None

    retarget_event = strike_template.instantiate(target_entity_uuid=saved.uuid).apply()

    assert retarget_event is not None
    assert retarget_event.canceled
    assert caster.action_economy.actions.normalized_score == 1

    fresh_event = strike_template.instantiate(target_entity_uuid=vulnerable.uuid).apply()

    assert fresh_event is not None
    assert not fresh_event.canceled
    assert "Sickened" in vulnerable.active_conditions
    assert caster.action_economy.actions.normalized_score == 0

    reset_spell_family_state(width=12, height=8)
    caster = create_family_caster(position=(1, 1), spell_slots={6: 1})
    unseen = create_family_target(name="Unseen Target", position=(4, 1))
    unseen.set_invisible(True)
    penalize_save(unseen, "wisdom")
    Entity.materialize_all_navigation(max_distance=80)
    assert unseen.uuid not in caster.senses.entities

    channel_event = Eyebite(
        source_entity_uuid=caster.uuid,
        effect_choice="sickened",
        template=False,
        costs=[],
    ).apply()

    channel_event = assert_completed_spell(channel_event)
    unseen_strike = caster.get_action_template("Eyebite Strike")
    assert unseen_strike is not None

    unseen_event = unseen_strike.instantiate(target_entity_uuid=unseen.uuid).apply()

    assert unseen_event is not None
    assert unseen_event.canceled
    assert "Sickened" not in unseen.active_conditions
    assert caster.action_economy.actions.normalized_score == 1


def test_eb_15_033_shake_awake_action_ends_sleep_and_eyebite_asleep() -> None:
    """EB-15-033: Shake Awake spends an action to wake magical sleepers."""
    reset_spell_family_state(width=12, height=8)
    caster = create_family_caster(position=(1, 1), spell_slots={1: 1})
    helper = create_family_target(name="Helper", position=(4, 2), faction="heroes")
    sleeper = create_family_target(name="Sleep Target", position=(4, 1), hp_dice=1)
    set_hp(sleeper, 5)
    setup_standard_actions(helper)
    Entity.materialize_all_navigation(max_distance=80)

    sleep = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=sleeper.position,
        template=False,
        costs=[],
    )
    sleep.hp_pool_rolled = 5
    sleep.hp_pool_remaining = 5

    sleep_event = sleep.apply()

    sleep_event = assert_completed_spell(sleep_event)
    assert "Sleep" in sleeper.active_conditions
    assert "Unconscious" not in sleeper.active_conditions
    assert sleeper.action_economy.action_permission.normalized_score == 0
    assert sleeper.senses.visual_access.normalized_score == 0

    sleep_actions = [
        action for action in helper.get_available_actions().entity_actions
        if action.template_name == "Shake Awake"
    ]
    assert len(sleep_actions) == 1
    assert [target.target_uuid for target in sleep_actions[0].valid_targets] == [sleeper.uuid]

    shake_template = helper.get_action_template("Shake Awake")
    assert shake_template is not None
    wake_event = shake_template.instantiate(target_entity_uuid=sleeper.uuid).apply()

    assert wake_event is not None
    assert not wake_event.canceled
    assert "Sleep" not in sleeper.active_conditions
    assert "Unconscious" not in sleeper.active_conditions
    assert sleeper.action_economy.action_permission.normalized_score == 1
    assert sleeper.senses.visual_access.normalized_score == 1
    assert helper.action_economy.actions.normalized_score == 0
    helper.action_economy.reset_all_costs()
    inactive_shake_action = next(
        action
        for action in helper.get_available_actions().entity_actions
        if action.template_name == "Shake Awake"
    )
    assert inactive_shake_action.availability_status is (
        ActionAvailabilityStatus.NO_VALID_TARGETS
    )
    assert inactive_shake_action.valid_targets == []

    reset_spell_family_state(width=12, height=8)
    caster = create_family_caster(position=(1, 1), spell_slots={6: 1})
    helper = create_family_target(name="Helper", position=(4, 2), faction="heroes")
    sleeper = create_family_target(name="Eyebite Sleeper", position=(4, 1), hp_dice=1)
    setup_standard_actions(helper)
    penalize_save(sleeper, "wisdom")
    Entity.materialize_all_navigation(max_distance=80)

    eyebite_event = Eyebite(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=sleeper.uuid,
        effect_choice="asleep",
        template=False,
        costs=[],
    ).apply()

    eyebite_event = assert_completed_spell(eyebite_event)
    assert "Eyebite Asleep" in sleeper.active_conditions
    assert "Unconscious" not in sleeper.active_conditions
    assert sleeper.action_economy.action_permission.normalized_score == 0
    assert sleeper.senses.visual_access.normalized_score == 0

    helper.action_economy.reset_all_costs()
    eyebite_actions = [
        action for action in helper.get_available_actions().entity_actions
        if action.template_name == "Shake Awake"
    ]
    assert len(eyebite_actions) == 1
    assert [target.target_uuid for target in eyebite_actions[0].valid_targets] == [sleeper.uuid]

    eyebite_shake_template = helper.get_action_template("Shake Awake")
    assert eyebite_shake_template is not None
    wake_eyebite_event = eyebite_shake_template.instantiate(target_entity_uuid=sleeper.uuid).apply()

    assert wake_eyebite_event is not None
    assert not wake_eyebite_event.canceled
    assert "Eyebite Asleep" not in sleeper.active_conditions
    assert "Unconscious" not in sleeper.active_conditions
    assert sleeper.action_economy.action_permission.normalized_score == 1
    assert sleeper.senses.visual_access.normalized_score == 1
    assert helper.action_economy.actions.normalized_score == 0


def test_eb_15_034_eyebite_panicked_forces_dash_movement_and_distance_cleanup() -> None:
    """EB-15-034: Panicked forces Dash movement and ends by distance plus sight."""
    reset_spell_family_state(width=24, height=5)
    caster = create_family_caster(position=(1, 2), spell_slots={6: 1})
    target = create_family_target(name="Panicked Target", position=(4, 2), hp_dice=4)
    penalize_save(target, "wisdom")
    Entity.materialize_all_navigation(max_distance=80)

    event = Eyebite(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        effect_choice="panicked",
        template=False,
        costs=[],
    ).apply()

    event = assert_completed_spell(event)
    assert "Eyebite Panicked" in target.active_conditions
    assert "Frightened" in target.active_conditions

    boost_save(target, "wisdom", value=200)
    target.on_turn_end()

    assert "Eyebite Panicked" in target.active_conditions

    start_distance = caster.senses.get_feet_distance(target.position)
    target.on_turn_start(round_number=1, turn_index=0)
    Entity.materialize_all_navigation(max_distance=80)
    moved_distance = caster.senses.get_feet_distance(target.position)

    assert moved_distance > start_distance
    assert moved_distance >= 60
    assert target.action_economy.actions.normalized_score == 0
    assert "Dashing" in target.active_conditions
    assert caster.uuid in target.senses.entities
    assert "Eyebite Panicked" in target.active_conditions

    caster.set_invisible(True)
    target.on_turn_start(round_number=2, turn_index=0)
    Entity.materialize_all_navigation(max_distance=80)

    assert caster.uuid not in target.senses.entities
    assert caster.senses.get_feet_distance(target.position) >= 60
    assert "Eyebite Panicked" not in target.active_conditions
    assert "Frightened" not in target.active_conditions


def test_eb_15_007_mobility_and_sense_utility_spells_change_state() -> None:
    """EB-15-007: utility spells modify position and sense modes."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={2: 2})
    Entity.materialize_all_navigation()

    see_event = SeeInvisibility(
        source_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    see_event = assert_completed_spell(see_event)
    assert "See Invisibility" in caster.active_conditions
    assert any(
        mode.sense_type == SensesType.SEE_INVISIBLE
        for mode in caster.senses.get_sense_modes()
    )
    assert "Concentrating" not in caster.active_conditions

    caster.action_economy.reset_all_costs()
    start_position = caster.position
    misty_event = MistyStep(
        source_entity_uuid=caster.uuid,
        end_position=(4, 1),
        template=False,
    ).apply()

    misty_event = assert_completed_spell(misty_event)
    assert start_position != caster.position
    assert caster.position == (4, 1)
    assert caster.action_economy.bonus_actions.normalized_score == 0


def test_eb_15_008_illusion_and_necromancy_self_effects() -> None:
    """EB-15-008: illusion and necromancy self spells alter entity state."""
    reset_spell_family_state()
    caster = create_family_caster(spell_slots={1: 1, 2: 1})
    Entity.materialize_all_navigation()

    false_life_event = FalseLife(
        source_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    false_life_event = assert_completed_spell(false_life_event)
    assert caster.health.temporary_hit_points.normalized_score > 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0

    caster.action_economy.reset_all_costs()
    invisible_event = Invisibility(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        template=False,
    ).apply()

    invisible_event = assert_completed_spell(invisible_event)
    assert "Invisible" in caster.active_conditions
    assert caster.is_invisible
    assert "Concentrating" in caster.active_conditions


def run_all_tests() -> None:
    """Run all Chapter 15 parity examples as a script."""
    tests = [
        test_eb_15_001_spell_catalog_groups_representative_families,
        test_eb_15_002_evocation_attack_save_and_area_damage_patterns,
        test_eb_15_003_auto_hit_and_healing_spell_patterns,
        test_eb_15_004_abjuration_buffs_and_restoration_remove_conditions,
        test_eb_15_023_restoration_spells_remove_supported_effects_only,
        test_eb_15_038_greater_restoration_removes_srd_tagged_effect_surfaces,
        test_eb_15_039_greater_restoration_removes_standard_petrified_condition,
        test_eb_15_040_greater_restoration_reduces_exhaustion_one_level,
        test_eb_15_025_protective_abjurations_prevent_and_absorb_effects,
        test_eb_15_009_shield_reaction_converts_marginal_attack_hit_to_miss,
        test_eb_15_010_shield_blocks_magic_missile_darts_against_its_target_only,
        test_eb_15_020_shield_non_firing_persistence_and_turn_cleanup,
        test_eb_15_022_shield_handler_toggle_gates_attack_and_missile_reactions,
        test_eb_15_036_shield_condition_log_nests_under_triggering_attack,
        test_eb_15_005_multi_target_concentration_links_each_effect,
        test_eb_15_015_bless_and_bane_rewrite_save_d20_results,
        test_eb_15_016_guidance_rewrites_one_skill_check_then_cleans_up,
        test_eb_15_024_d20_mutation_handlers_are_roll_type_scoped,
        test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup,
        test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup,
        test_eb_15_019_mirror_image_duplicates_absorb_missed_attacks,
        test_eb_15_035_mirror_image_recast_replaces_and_duration_expires,
        test_eb_15_006_zone_spells_create_spatial_handlers_and_cleanup_links,
        test_eb_15_021_zone_spell_family_entry_turn_start_and_cleanup_edges,
        test_eb_15_026_light_zone_spells_apply_obscurement_and_dispel_darkness,
        test_eb_15_027_damage_zones_cover_upcast_obscurement_and_movement,
        test_eb_15_028_gas_and_ice_zones_match_srd_turn_start_edges,
        test_eb_15_041_stinking_cloud_skips_breathless_creatures,
        test_eb_15_044_stinking_cloud_wind_dispersal_uses_srd_rounds,
        test_eb_15_043_sleet_storm_douses_exposed_flames,
        test_eb_15_029_web_models_obscurement_grounding_and_escape_cleanup,
        test_eb_15_037_web_unanchored_cast_collapses_on_caster_turn_start,
        test_eb_15_042_web_fire_exposure_burns_one_cube_for_one_round,
        test_eb_15_011_haste_modifier_bundle_and_lethargy_cleanup,
        test_eb_15_012_slow_multi_target_modifier_bundle_and_cleanup,
        test_eb_15_013_sleep_hp_pool_selection_immunity_and_wake_on_damage,
        test_eb_15_014_color_spray_hp_pool_skips_and_blinded_cleanup,
        test_eb_15_030_hp_pool_spells_cover_upcast_and_immunity_edges,
        test_eb_15_031_eyebite_granted_action_lifecycle_and_repeat_save,
        test_eb_15_032_eyebite_blocks_successful_retargets_and_unseen_targets,
        test_eb_15_033_shake_awake_action_ends_sleep_and_eyebite_asleep,
        test_eb_15_034_eyebite_panicked_forces_dash_movement_and_distance_cleanup,
        test_eb_15_007_mobility_and_sense_utility_spells_change_state,
        test_eb_15_008_illusion_and_necromancy_self_effects,
    ]
    for test in tests:
        test()
    print("Chapter 15 spell-family engine book examples passed.")


if __name__ == "__main__":
    run_all_tests()
