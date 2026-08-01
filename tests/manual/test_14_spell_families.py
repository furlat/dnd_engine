"""Manual Chapter 14 checks for spell families and implemented spells."""

from typing import cast
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.conditions import Concentrating, Poisoned
from dnd.core.base_actions import TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import (
    AbilityName,
    DamageAppliedEvent,
    EventPhase,
    EventQueue,
    EventType,
    TakeDamageEvent,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.modifiers import (
    AdvantageStatus,
    NumericalModifier,
    ResistanceStatus,
)
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from tests.spell_test_exports import (
    ALL_SPELLS,
    CANTRIPS,
    LEVEL_1_SPELLS,
    LEVEL_2_SPELLS,
    LEVEL_9_SPELLS,
    FireBolt,
    MagicMissile,
    PowerWordKill,
    SacredFlame,
)
from dnd.spells.abjuration import DeathWardEffect, LesserRestoration, MageArmor, ShieldBuff
from dnd.spells.conjuration import MistyStep
from dnd.spells.enchantment import Sleep
from dnd.spells.evocation import CureWounds, HealingWord
from dnd.spells.effect_ids import MAGIC_MISSILE_DAMAGE_EFFECT_ID
from dnd.spells.illusion import HypnoticPatternEffect, MirrorImage, MirrorImageEffect
from dnd.spells.necromancy import FalseLife
from dnd.spells.transmutation import SpikeGrowth
from dnd.spatial_effect_content import SPIKE_GROWTH_SURFACE_RECIPE
from dnd.spatial_effects import SpatialEffect
from dnd.spatial_effect_controllers import AreaSpatialEffectController


def reset_spell_family_state(width: int = 12, height: int = 8) -> None:
    """Clear global state and create a small spell-family arena."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)


def create_spell_family_actor(
    name: str,
    position: tuple[int, int],
    faction: str,
    spell_slots: dict[int, int] | None = None,
    hp_dice: int = 4,
    intelligence: int = 18,
    dexterity: int = 14,
) -> Entity:
    """Create a durable actor for spell family checks."""
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=dexterity),
                constitution=AbilityConfig(ability_score=10),
                intelligence=AbilityConfig(ability_score=intelligence),
                wisdom=AbilityConfig(ability_score=10),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(spell_slots=spell_slots or {}),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=hp_dice,
                        mode="maximums",
                    )
                ],
            ),
            proficiency_bonus=3,
            spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
            position=position,
            faction=faction,
        ),
    )


def penalize_saving_throw(
    entity: Entity,
    ability_name: AbilityName,
    value: int = -100,
) -> None:
    """Make one saving throw fail deterministically."""
    saving_throw = entity.saving_throws.get_saving_throw(ability_name)
    saving_throw.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=f"{ability_name.title()} tutorial penalty",
            value=value,
        )
    )


def set_current_normal_hp(entity: Entity, target_hp: int, source: Entity) -> None:
    """Move an actor's normal HP to a tutorial value through engine methods."""
    current_hp = entity.get_normal_hp()
    if target_hp < current_hp:
        entity.receive_damage(current_hp - target_hp, DamageType.FORCE, source.uuid)
    elif target_hp > current_hp:
        entity.receive_healing(target_hp - current_hp, source.uuid)


def assert_completed_spell(event: object) -> SpellEvent:
    """Assert a spell produced an uncanceled completion event."""
    assert isinstance(event, SpellEvent)
    assert not event.canceled
    return event


def test_ranged_spell_attacks_are_disadvantaged_while_threatened() -> None:
    """Adjacent hostiles affect spell attack models, rolls, and combat logs."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Threatened Mage", (2, 2), "heroes")
    target = create_spell_family_actor("Adjacent Warrior", (2, 3), "monsters")
    Entity.update_all_entities_senses(max_distance=30)

    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    profile = spell.get_outcome_profile(caster)

    assert caster.is_threatened() is True
    assert profile is not None
    assert profile.advantage is AdvantageStatus.DISADVANTAGE

    with fixed_dice_faces(12, 8, 5):
        event = assert_completed_spell(spell.apply())

    assert event.is_threatened is True
    assert event.dice_roll is not None
    assert event.dice_roll.results == [12, 8]
    assert event.dice_roll.advantage_status is AdvantageStatus.DISADVANTAGE

    combat_log = event.generate_combat_log()
    assert combat_log.data["is_threatened"] is True
    assert combat_log.data["advantage_breakdown"] == [
        {"name": "Threatened (Ranged)", "value": -1, "source": "self"}
    ]


def test_first_spell_family_example_prints_catalog_and_outcomes(capsys) -> None:
    """The opening spell-family example prints catalog shapes and cast results."""
    reset_spell_family_state()
    caster = create_spell_family_actor(
        "Battle Mage",
        (1, 1),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_family_actor("Target", (3, 1), "monsters")
    Entity.update_all_entities_senses(max_distance=30)

    families = [
        ("attack", ALL_SPELLS["Fire Bolt"]),
        ("save", ALL_SPELLS["Sacred Flame"]),
        ("auto-hit", ALL_SPELLS["Magic Missile"]),
    ]
    readout_lines = []
    for family_name, spell_cls in families:
        preview = spell_cls(source_entity_uuid=caster.uuid)
        readout_lines.append(
            (
                f"catalog: {preview.name} -> {family_name}, "
                f"level={preview.spell_level}, "
                f"school={preview.spell_school}, "
                f"target={preview.target_type.value}"
            )
        )

    hp_before = target.get_hp()
    with fixed_dice_faces(12, 5, 6):
        fire_event = FireBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_level=5,
        ).apply()

    fire_event = assert_completed_spell(fire_event)
    assert fire_event.attack_outcome is not None
    assert fire_event.damage_rolls is not None
    assert fire_event.dice_roll is not None
    fire_damage = fire_event.damage_rolls[0]
    readout_lines.append(
        (
            f"fire bolt: outcome={fire_event.attack_outcome.value}, "
            f"roll={fire_event.dice_roll.results}+7={fire_event.dice_roll.total}, "
            f"damage={fire_damage.results}->{fire_damage.total}, "
            f"hp={hp_before}->{target.get_hp()}"
        )
    )

    caster.action_economy.reset_all_costs()
    penalize_saving_throw(target, "dexterity")
    hp_before = target.get_hp()
    with fixed_dice_faces(10, 4, 5):
        sacred_event = SacredFlame(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_level=5,
        ).apply()

    sacred_event = assert_completed_spell(sacred_event)
    assert sacred_event.damage_rolls is not None
    sacred_damage = sacred_event.damage_rolls[0]
    readout_lines.append(
        (
            f"sacred flame: save={sacred_event.save_ability}, "
            f"success={sacred_event.save_success}, "
            f"damage={sacred_damage.results}->{sacred_damage.total}, "
            f"hp={hp_before}->{target.get_hp()}"
        )
    )

    caster.action_economy.reset_all_costs()
    hp_before = target.get_hp()
    slot_before = caster.action_economy.spell_slot_1.normalized_score
    with fixed_dice_faces(2, 3, 4):
        missile_event = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        ).apply()

    missile_event = assert_completed_spell(missile_event)
    readout_lines.append(
        (
            f"magic missile: targets={missile_event.total_targets}, "
            f"total_damage={missile_event.total_damage}, "
            f"hp={hp_before}->{target.get_hp()}, "
            f"slot={slot_before}->"
            f"{caster.action_economy.spell_slot_1.normalized_score}"
        )
    )
    print("\n".join(readout_lines))

    expected_lines = [
        "catalog: Fire Bolt -> attack, level=0, school=evocation, target=entity",
        "catalog: Sacred Flame -> save, level=0, school=evocation, target=entity",
        (
            "catalog: Magic Missile -> auto-hit, "
            "level=1, school=evocation, target=multi_entity"
        ),
        "fire bolt: outcome=Hit, roll=[12]+7=19, damage=[5, 6]->11, hp=40->29",
        (
            "sacred flame: save=dexterity, success=False, "
            "damage=[4, 5]->9, hp=29->20"
        ),
        "magic missile: targets=3, total_damage=12, hp=20->8, slot=1->0",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_spell_catalog_groups_representative_runtime_families() -> None:
    """The catalog maps public spell names to classes with runtime metadata."""
    representatives = {
        "Fire Bolt": (FireBolt, 0, "evocation", TargetType.ENTITY),
        "Magic Missile": (MagicMissile, 1, "evocation", TargetType.MULTI_ENTITY),
        "Mage Armor": (MageArmor, 1, "abjuration", TargetType.ENTITY),
        "Misty Step": (MistyStep, 2, "conjuration", TargetType.POSITION),
        "Spike Growth": (SpikeGrowth, 2, "transmutation", TargetType.POSITION),
        "Mirror Image": (MirrorImage, 2, "illusion", TargetType.SELF),
        "Power Word Kill": (PowerWordKill, 9, "enchantment", TargetType.ENTITY),
    }

    assert CANTRIPS["Fire Bolt"] is FireBolt
    assert LEVEL_1_SPELLS["Magic Missile"] is MagicMissile
    assert LEVEL_2_SPELLS["Misty Step"] is MistyStep
    assert LEVEL_9_SPELLS["Power Word Kill"] is PowerWordKill
    assert len(ALL_SPELLS) >= 100

    for spell_name, (spell_cls, level, school, target_type) in representatives.items():
        spell = ALL_SPELLS[spell_name](source_entity_uuid=uuid4())

        assert ALL_SPELLS[spell_name] is spell_cls
        assert spell.name == spell_name
        assert spell.spell_level == level
        assert spell.spell_school == school
        assert spell.target_type == target_type


def test_offensive_spell_families_cover_attack_save_and_auto_hit_damage(capsys) -> None:
    """Offensive spells use attack rolls, saving throws, or auto-hit darts."""
    reset_spell_family_state()
    caster = create_spell_family_actor(
        "Battle Mage",
        (1, 1),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_family_actor("Target", (3, 1), "monsters")
    Entity.update_all_entities_senses(max_distance=30)

    hp_before = target.get_hp()
    with fixed_dice_faces(12, 5, 6):
        fire_event = FireBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_level=5,
        ).apply()

    fire_event = assert_completed_spell(fire_event)
    assert fire_event.attack_outcome is not None
    assert fire_event.dice_roll is not None
    assert fire_event.damage_rolls is not None
    assert fire_event.damage_rolls[0].results == [5, 6]
    assert target.get_hp() == hp_before - 11
    fire_damage = fire_event.damage_rolls[0]
    readout_lines = [
        (
            f"fire bolt: outcome={fire_event.attack_outcome.value}, "
            f"roll={fire_event.dice_roll.results}+7={fire_event.dice_roll.total}, "
            f"damage={fire_damage.results}->{fire_damage.total}, "
            f"hp={hp_before}->{target.get_hp()}"
        )
    ]

    caster.action_economy.reset_all_costs()
    penalize_saving_throw(target, "dexterity")
    hp_before = target.get_hp()
    with fixed_dice_faces(10, 4, 5):
        sacred_event = SacredFlame(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_level=5,
        ).apply()

    sacred_event = assert_completed_spell(sacred_event)
    assert sacred_event.save_ability == "dexterity"
    assert sacred_event.save_success is False
    assert sacred_event.damage_rolls is not None
    assert sacred_event.damage_rolls[0].results == [4, 5]
    assert target.get_hp() == hp_before - 9
    sacred_damage = sacred_event.damage_rolls[0]
    readout_lines.append(
        (
            f"sacred flame: save={sacred_event.save_ability}, "
            f"success={sacred_event.save_success}, "
            f"damage={sacred_damage.results}->{sacred_damage.total}, "
            f"hp={hp_before}->{target.get_hp()}"
        )
    )

    caster.action_economy.reset_all_costs()
    hp_before = target.get_hp()
    slot_before = caster.action_economy.spell_slot_1.normalized_score
    with fixed_dice_faces(2, 3, 4):
        missile_event = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
        ).apply()

    missile_event = assert_completed_spell(missile_event)
    assert missile_event.total_targets == 3
    assert missile_event.total_damage == 12
    assert target.get_hp() == hp_before - 12
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    readout_lines.append(
        (
            f"magic missile: targets={missile_event.total_targets}, "
            f"total_damage={missile_event.total_damage}, "
            f"hp={hp_before}->{target.get_hp()}, "
            f"slot={slot_before}->"
            f"{caster.action_economy.spell_slot_1.normalized_score}"
        )
    )

    print("\n".join(readout_lines))

    expected_lines = [
        "fire bolt: outcome=Hit, roll=[12]+7=19, damage=[5, 6]->11, hp=40->29",
        (
            "sacred flame: save=dexterity, success=False, "
            "damage=[4, 5]->9, hp=29->20"
        ),
        "magic missile: targets=3, total_damage=12, hp=20->8, slot=1->0",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_recovery_protection_and_restoration_families_change_owned_state(capsys) -> None:
    """Healing, armor, and restoration spells update the target they touch."""
    reset_spell_family_state()
    caster = create_spell_family_actor(
        "Ward Mage",
        (1, 1),
        "heroes",
        spell_slots={1: 3, 2: 1},
    )
    ally = create_spell_family_actor("Ally", (2, 1), "heroes")
    Entity.update_all_entities_senses(max_distance=30)

    set_current_normal_hp(ally, 5, caster)
    hp_before = ally.get_normal_hp()
    actions_before = caster.action_economy.actions.normalized_score
    with fixed_dice_faces(6):
        cure_event = CureWounds(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
        ).apply()

    cure_event = assert_completed_spell(cure_event)
    assert cure_event.name == "Cure Wounds"
    assert ally.get_normal_hp() == 15
    assert caster.action_economy.actions.normalized_score == 0
    readout_lines = [
        (
            f"cure wounds: hp={hp_before}->{ally.get_normal_hp()}, "
            f"action={actions_before}->{caster.action_economy.actions.normalized_score}, "
            f"slot1={caster.action_economy.spell_slot_1.normalized_score}"
        )
    ]

    caster.action_economy.reset_all_costs()
    set_current_normal_hp(ally, 5, caster)
    hp_before = ally.get_normal_hp()
    bonus_before = caster.action_economy.bonus_actions.normalized_score
    with fixed_dice_faces(3):
        word_event = HealingWord(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=ally.uuid,
        ).apply()

    word_event = assert_completed_spell(word_event)
    assert word_event.name == "Healing Word"
    assert ally.get_normal_hp() == 12
    assert caster.action_economy.bonus_actions.normalized_score == 0
    readout_lines.append(
        (
            f"healing word: hp={hp_before}->{ally.get_normal_hp()}, "
            f"bonus={bonus_before}->"
            f"{caster.action_economy.bonus_actions.normalized_score}, "
            f"slot1={caster.action_economy.spell_slot_1.normalized_score}"
        )
    )

    caster.action_economy.reset_all_costs()
    base_ac = caster.ac_bonus().normalized_score
    armor_event = MageArmor(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
    ).apply()

    armor_event = assert_completed_spell(armor_event)
    assert "Mage Armor" in caster.active_conditions
    assert caster.ac_bonus().normalized_score == max(base_ac, 15)
    readout_lines.append(
        (
            f"mage armor: ac={base_ac}->{caster.ac_bonus().normalized_score}, "
            f"condition={'Mage Armor' in caster.active_conditions}, "
            f"slot1={caster.action_economy.spell_slot_1.normalized_score}"
        )
    )

    caster.action_economy.reset_all_costs()
    poison = Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid)
    caster.add_condition(poison)
    before_poison = "Poisoned" in caster.active_conditions

    restore_event = LesserRestoration(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
    ).apply()

    restore_event = assert_completed_spell(restore_event)
    assert "Poisoned" not in caster.active_conditions
    assert caster.action_economy.spell_slot_2.normalized_score == 0
    readout_lines.append(
        (
            f"lesser restoration: poisoned={before_poison}->"
            f"{'Poisoned' in caster.active_conditions}, "
            f"slot2={caster.action_economy.spell_slot_2.normalized_score}"
        )
    )

    print("\n".join(readout_lines))

    expected_lines = [
        "cure wounds: hp=5->15, action=1->0, slot1=2",
        "healing word: hp=5->12, bonus=1->0, slot1=1",
        "mage armor: ac=12->15, condition=True, slot1=0",
        "lesser restoration: poisoned=True->False, slot2=0",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_mobility_and_temporary_hit_point_families_update_position_and_hp_pool(
    capsys,
) -> None:
    """Misty Step moves without walking, and False Life grants temporary HP."""
    reset_spell_family_state()
    caster = create_spell_family_actor(
        "Mist Mage",
        (1, 1),
        "heroes",
        spell_slots={1: 1, 2: 1},
    )
    Entity.update_all_entities_senses(max_distance=30)

    position_before = caster.position
    bonus_before = caster.action_economy.bonus_actions.normalized_score
    slot2_before = caster.action_economy.spell_slot_2.normalized_score
    misty_event = MistyStep(
        source_entity_uuid=caster.uuid,
        end_position=(4, 1),
    ).apply()

    misty_event = assert_completed_spell(misty_event)
    assert misty_event.name == "Misty Step"
    assert caster.position == (4, 1)
    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert caster.action_economy.spell_slot_2.normalized_score == 0
    readout_lines = [
        (
            f"misty step: position={position_before}->{caster.position}, "
            f"bonus={bonus_before}->"
            f"{caster.action_economy.bonus_actions.normalized_score}, "
            f"slot2={slot2_before}->"
            f"{caster.action_economy.spell_slot_2.normalized_score}"
        )
    ]

    caster.action_economy.reset_all_costs()
    temp_before = caster.health.temporary_hit_points.normalized_score
    slot1_before = caster.action_economy.spell_slot_1.normalized_score
    with fixed_dice_faces(3):
        false_life_event = FalseLife(source_entity_uuid=caster.uuid).apply()

    false_life_event = assert_completed_spell(false_life_event)
    assert false_life_event.name == "False Life"
    assert caster.health.temporary_hit_points.normalized_score == 7
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    readout_lines.append(
        (
            f"false life: temp_hp={temp_before}->"
            f"{caster.health.temporary_hit_points.normalized_score}, "
            f"slot1={slot1_before}->"
            f"{caster.action_economy.spell_slot_1.normalized_score}"
        )
    )

    print("\n".join(readout_lines))

    expected_lines = [
        "misty step: position=(1, 1)->(4, 1), bonus=1->0, slot2=1->0",
        "false life: temp_hp=0->7, slot1=1->0",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_zone_spell_family_owns_spatial_handlers_and_concentration_cleanup(
    capsys,
) -> None:
    """Zone spells own map-clipped effects and clean up through links."""
    reset_spell_family_state()
    caster = create_spell_family_actor(
        "Thorn Mage",
        (1, 1),
        "heroes",
        spell_slots={2: 1},
    )
    target = create_spell_family_actor("Raider", (10, 1), "monsters")
    Entity.update_all_entities_senses(max_distance=30)

    event = SpikeGrowth(
        source_entity_uuid=caster.uuid,
        end_position=(5, 3),
    ).apply()

    event = assert_completed_spell(event)
    assert "Concentrating" in caster.active_conditions

    surface = next(
        effect
        for effect in SpatialEffect.active_effects()
        if effect.content_ref == SPIKE_GROWTH_SURFACE_RECIPE.ref
    )
    zone = cast(
        AreaSpatialEffectController,
        surface.active_conditions["Spike Growth Zone"],
    )
    concentration = cast(Concentrating, caster.active_conditions["Concentrating"])
    assert len(zone.affected_positions) > 0
    assert len(zone.spatial_handler_uuids) > 0
    assert (surface.uuid, zone.uuid) in concentration.linked_conditions
    readout_lines = [
        (
            f"spike growth: effect={SpatialEffect.get_effect(surface.uuid) is surface}, "
            f"concentrating={'Concentrating' in caster.active_conditions}, "
            f"positions={len(zone.affected_positions)}, "
            f"handlers={len(zone.spatial_handler_uuids)}, "
            f"linked={(surface.uuid, zone.uuid) in concentration.linked_conditions}"
        )
    ]

    hp_before = target.get_hp()
    with fixed_dice_faces(3, 4):
        Entity.update_entity_position(target, (5, 3))

    assert target.get_hp() == hp_before - 7
    readout_lines.append(
        (
            f"zone entry: position={target.position}, damage=7, "
            f"hp={hp_before}->{target.get_hp()}"
        )
    )

    caster.remove_condition("Concentrating")

    assert SpatialEffect.get_effect(surface.uuid) is None
    assert "Concentrating" not in caster.active_conditions
    readout_lines.append(
        (
            f"cleanup: effect={SpatialEffect.get_effect(surface.uuid) is not None}, "
            f"concentrating={'Concentrating' in caster.active_conditions}"
        )
    )

    print("\n".join(readout_lines))

    expected_lines = [
        (
            "spike growth: effect=True, concentrating=True, "
            "positions=48, handlers=1, linked=True"
        ),
        "zone entry: position=(5, 3), damage=7, hp=40->33",
        "cleanup: effect=False, concentrating=False",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_illusion_and_enchantment_families_create_conditions(capsys) -> None:
    """Mirror Image and Sleep turn spell effects into condition state."""
    reset_spell_family_state()
    caster = create_spell_family_actor(
        "Dream Mage",
        (1, 1),
        "heroes",
        spell_slots={1: 2, 2: 1},
    )
    low = create_spell_family_actor("Low HP Goblin", (5, 3), "monsters", hp_dice=1)
    mid = create_spell_family_actor("Mid HP Goblin", (6, 3), "monsters", hp_dice=1)
    high = create_spell_family_actor("High HP Bugbear", (7, 3), "monsters", hp_dice=3)
    undead = create_spell_family_actor("Skeleton", (5, 4), "monsters", hp_dice=1)
    set_current_normal_hp(low, 5, caster)
    set_current_normal_hp(mid, 10, caster)
    set_current_normal_hp(high, 20, caster)
    set_current_normal_hp(undead, 1, caster)
    undead.creature_type = CreatureType.UNDEAD
    Entity.update_all_entities_senses(max_distance=30)

    base_ac = caster.ac_bonus().normalized_score
    mirror_event = MirrorImage(source_entity_uuid=caster.uuid).apply()

    mirror_event = assert_completed_spell(mirror_event)
    mirror = cast(MirrorImageEffect, caster.active_conditions["Mirror Image"])
    assert mirror.duplicates == 3
    assert "Concentrating" not in caster.active_conditions
    assert caster.ac_bonus().normalized_score == base_ac + 9
    readout_lines = [
        (
            f"mirror image: duplicates={mirror.duplicates}, "
            f"ac={base_ac}->{caster.ac_bonus().normalized_score}, "
            f"concentrating={'Concentrating' in caster.active_conditions}"
        )
    ]

    caster.action_economy.reset_all_costs()
    selector = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(5, 3),
    )
    selector.hp_pool_rolled = 16
    selector.hp_pool_remaining = 16

    selected_targets = selector.get_all_targets()

    assert low.uuid in selected_targets
    assert mid.uuid in selected_targets
    assert high.uuid not in selected_targets
    assert undead.uuid not in selected_targets
    assert selector.hp_pool_remaining == 1
    selected_names: list[str] = []
    for entity_uuid in selected_targets:
        selected_entity = Entity.get(entity_uuid)
        assert selected_entity is not None
        selected_names.append(selected_entity.name)
    readout_lines.append(
        (
            f"sleep selection: selected={selected_names}, "
            f"remaining_pool={selector.hp_pool_remaining}, "
            f"undead_selected={undead.uuid in selected_targets}"
        )
    )

    sleep = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(5, 3),
    )
    sleep.hp_pool_rolled = 5
    sleep.hp_pool_remaining = 5

    sleep_event = sleep.apply()

    sleep_event = assert_completed_spell(sleep_event)
    assert "Sleep" in low.active_conditions
    assert "Unconscious" not in low.active_conditions
    assert low.action_economy.action_permission.normalized_score == 0
    assert low.senses.visual_access.normalized_score == 0
    assert "Sleep" not in mid.active_conditions
    assert sleep.hp_pool_remaining == 0
    readout_lines.append(
        (
            f"sleep apply: low_sleep={'Sleep' in low.active_conditions}, "
            f"low_action_denied={low.action_economy.action_permission.normalized_score == 0}, "
            f"mid_sleep={'Sleep' in mid.active_conditions}, "
            f"remaining_pool={sleep.hp_pool_remaining}"
        )
    )

    low.receive_damage(1, DamageType.FORCE, caster.uuid)

    assert "Sleep" not in low.active_conditions
    assert "Unconscious" not in low.active_conditions
    assert low.action_economy.action_permission.normalized_score == 1
    assert low.senses.visual_access.normalized_score == 1
    readout_lines.append(
        (
            f"wakeup: low_sleep={'Sleep' in low.active_conditions}, "
            f"low_action_allowed={low.action_economy.action_permission.normalized_score == 1}"
        )
    )

    print("\n".join(readout_lines))

    expected_lines = [
        "mirror image: duplicates=3, ac=12->21, concentrating=False",
        (
            "sleep selection: selected=['Low HP Goblin', 'Mid HP Goblin'], "
            "remaining_pool=1, undead_selected=False"
        ),
        (
            "sleep apply: low_sleep=True, low_action_denied=True, "
            "mid_sleep=False, remaining_pool=0"
        ),
        "wakeup: low_sleep=False, low_action_allowed=True",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_blocked_damage_does_not_break_hypnotic_pattern() -> None:
    """A canceled damage packet cannot satisfy a takes-damage trigger."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Pattern Caster", (1, 1), "heroes")
    target = create_spell_family_actor("Shielded Target", (3, 1), "monsters")
    hypnotic = HypnoticPatternEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    )
    shield = ShieldBuff(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(hypnotic)
    target.add_condition(shield)

    actual_damage = target.receive_damage(
        5,
        DamageType.FORCE,
        caster.uuid,
        effect_id=MAGIC_MISSILE_DAMAGE_EFFECT_ID,
    )

    assert actual_damage == 0
    assert "Shield" in target.active_conditions
    assert "Hypnotic Pattern" in target.active_conditions

    target.remove_condition("Shield")
    actual_damage = target.receive_damage(1, DamageType.FORCE, caster.uuid)

    assert actual_damage == 1
    assert "Hypnotic Pattern" not in target.active_conditions


def test_damage_applied_event_is_post_mitigation_and_drives_damage_consequences() -> None:
    """Only positive post-mitigation damage satisfies takes-damage rules."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Pattern Caster", (1, 1), "heroes")
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Force-Immune Target",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(),
            action_economy=ActionEconomyConfig(),
            health=HealthConfig(
                hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")],
                immunities=[DamageType.FORCE],
            ),
            position=(3, 1),
            faction="monsters",
        ),
    )
    target.add_condition(HypnoticPatternEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    ))

    force_damage = target.receive_damage(5, DamageType.FORCE, caster.uuid)

    assert force_damage == 0
    assert "Hypnotic Pattern" in target.active_conditions
    assert EventQueue.get_events_by_type(EventType.DAMAGE_APPLIED) == []
    force_completion = [
        event
        for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if event.phase == EventPhase.COMPLETION
    ][-1]
    assert isinstance(force_completion, TakeDamageEvent)
    assert force_completion.resolution is not None
    assert force_completion.resolution.incoming_damage == 5
    assert force_completion.resolution.affinity_prevented_damage == 5
    assert force_completion.resolution.components[0].resistance_status == ResistanceStatus.IMMUNITY
    assert force_completion.resolution.components[0].affinity_prevented_damage == 5
    assert force_completion.resolution.applied_damage == 0

    slashing_damage = target.receive_damage(3, DamageType.SLASHING, caster.uuid)

    assert slashing_damage == 3
    assert "Hypnotic Pattern" not in target.active_conditions
    completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.DAMAGE_APPLIED)
        if event.phase == EventPhase.COMPLETION
    ]
    assert len(completions) == 1
    applied = completions[0]
    assert isinstance(applied, DamageAppliedEvent)
    assert applied.applied_damage == 3
    assert applied.normal_hit_point_damage == 3
    assert applied.temporary_hit_point_damage == 0
    assert applied.resulting_normal_hp == target.get_normal_hp()
    assert applied.resulting_temporary_hp == 0
    assert applied.resolution is not None
    assert applied.resolution.incoming_damage == 3
    assert applied.resolution.applied_damage == 3
    assert applied.resolution.effective_normal_hit_point_damage == 3
    assert applied.resolution.overkill_damage == 0
    parent = applied.get_parent_event()
    assert parent is not None
    assert parent.event_type == EventType.TAKE_DAMAGE
    damage_completion = [
        event
        for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if event.phase == EventPhase.COMPLETION
    ][-1]
    assert damage_completion.combat_log is not None

    def iter_log_tree(entry):
        yield entry
        for child in entry.sub_entries:
            yield from iter_log_tree(child)

    assert any(
        entry.data.get("condition_name") == "Hypnotic Pattern"
        for entry in iter_log_tree(damage_completion.combat_log)
    )


def test_temporary_hit_point_loss_is_positive_applied_damage() -> None:
    """Temporary hit points absorb damage without suppressing takes-damage rules."""
    reset_spell_family_state()
    caster = create_spell_family_actor("Pattern Caster", (1, 1), "heroes")
    target = create_spell_family_actor("Ward Target", (3, 1), "monsters")
    target.grant_temporary_hit_points(5, target.uuid)
    target.add_condition(HypnoticPatternEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
    ))

    normal_hit_point_damage = target.receive_damage(3, DamageType.FORCE, caster.uuid)

    assert normal_hit_point_damage == 0
    assert target.health.temporary_hit_points.normalized_score == 2
    assert "Hypnotic Pattern" not in target.active_conditions
    completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.DAMAGE_APPLIED)
        if event.phase == EventPhase.COMPLETION
    ]
    assert len(completions) == 1
    applied = completions[0]
    assert isinstance(applied, DamageAppliedEvent)
    assert applied.applied_damage == 3
    assert applied.normal_hit_point_damage == 0
    assert applied.temporary_hit_point_damage == 3
    assert applied.resulting_temporary_hp == 2
    assert applied.resolution is not None
    assert applied.resolution.temporary_hit_point_damage == 3
    assert applied.resolution.normal_hit_point_damage == 0


def test_concentration_check_uses_applied_damage_not_incoming_damage() -> None:
    """Mitigated packets do not roll concentration saves; applied damage does."""
    reset_spell_family_state()
    attacker = create_spell_family_actor("Attacker", (1, 1), "heroes")
    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name="Concentrating Caster",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(),
            action_economy=ActionEconomyConfig(),
            health=HealthConfig(
                hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=4, mode="maximums")],
                immunities=[DamageType.FORCE],
            ),
            position=(3, 1),
            faction="monsters",
        ),
    )
    caster.add_condition(Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Probe",
    ))

    caster.receive_damage(8, DamageType.FORCE, attacker.uuid)

    assert "Concentrating" in caster.active_conditions
    assert EventQueue.get_events_by_type(EventType.SAVING_THROW) == []

    with fixed_dice_faces(1):
        caster.receive_damage(2, DamageType.SLASHING, attacker.uuid)

    assert "Concentrating" not in caster.active_conditions
    save_completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SAVING_THROW)
        if event.phase == EventPhase.COMPLETION
    ]
    assert len(save_completions) == 1


def test_damage_reducing_a_death_save_actor_to_zero_ends_concentration_without_save() -> None:
    """A caster at zero normal HP cannot preserve concentration with a damage save."""
    reset_spell_family_state()
    attacker = create_spell_family_actor("Attacker", (1, 1), "heroes")
    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name="Dying Caster",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(),
            action_economy=ActionEconomyConfig(),
            health=HealthConfig(
                hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=2, mode="maximums")],
            ),
            position=(3, 1),
            faction="monsters",
            uses_death_saves=True,
        ),
    )
    set_current_normal_hp(caster, 2, attacker)
    EventQueue.reset()
    caster.add_condition(Concentrating(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        spell_name="Probe",
    ))

    with fixed_dice_faces(20):
        caster.receive_damage(3, DamageType.SLASHING, attacker.uuid)

    assert caster.get_normal_hp() == 0
    assert caster.is_dying
    assert "Concentrating" not in caster.active_conditions
    assert EventQueue.get_events_by_type(EventType.SAVING_THROW) == []


def test_death_ward_uses_post_mitigation_lethality_and_leaves_one_normal_hp() -> None:
    """Death Ward previews defenses and caps normal-HP loss compositionally."""
    reset_spell_family_state()
    attacker = create_spell_family_actor("Attacker", (1, 1), "heroes")

    def create_warded_target(name: str) -> Entity:
        target = Entity.create(
            source_entity_uuid=uuid4(),
            name=name,
            config=EntityConfig(
                ability_scores=AbilityScoresConfig(),
                action_economy=ActionEconomyConfig(),
                health=HealthConfig(
                    hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=2, mode="maximums")],
                    resistances=[DamageType.FIRE],
                ),
                position=(3, 1),
                faction="monsters",
            ),
        )
        set_current_normal_hp(target, 10, attacker)
        target.add_condition(DeathWardEffect(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
        ))
        return target

    nonlethal = create_warded_target("Nonlethal Ward")
    nonlethal_damage = nonlethal.receive_damage(15, DamageType.FIRE, attacker.uuid)

    assert nonlethal_damage == 7
    assert nonlethal.get_normal_hp() == 3
    assert "Death Ward" in nonlethal.active_conditions

    lethal = create_warded_target("Lethal Ward")
    lethal_damage = lethal.receive_damage(25, DamageType.FIRE, attacker.uuid)

    assert lethal_damage == 9
    assert lethal.get_normal_hp() == 1
    assert "Death Ward" not in lethal.active_conditions
