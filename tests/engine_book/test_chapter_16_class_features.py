"""Engine book parity tests for class features, factories, and feats."""

from typing import Optional
from unittest.mock import patch
from uuid import UUID, uuid4

from pydantic import ValidationError

from dnd.actions import Attack, SpellAction
from dnd.actions_functional import execute_action, get_available_actions, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.base_actions import TargetType, spell_slot_cost_type
from dnd.classes.barbarian_factory import (
    BarbarianConfig,
    PrimalPathChoice,
    create_barbarian,
)
from dnd.classes.feats import LuckyFeature, lucky_processor
from dnd.classes.fighter import ActionSurge, ExtraAttack, ExtraAttackFeature, SecondWind
from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.classes.paladin import register_divine_smite
from dnd.classes.rage import Frenzy, RageFeature, Raging
from dnd.classes.sorcerer import QuickenedSpell
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer
from dnd.conditions import Blinded, Charmed, Frightened, Poisoned
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.dice import AttackOutcome, DiceRoll, RollType
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import D20RollResultEvent, DamageRollResultEvent, EventPhase, EventQueue, EventType, SkillCheckEvent
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.core.modifiers import CreatureType, DamageType, ResistanceStatus
from dnd.core.values import AdvantageStatus, AutoHitStatus, BaseValue, CriticalStatus, ModifiableValue
from dnd.entity import Entity, EntityConfig, determine_attack_outcome
from dnd.items import create_leather_armor, create_longsword, create_shortbow
from dnd.monsters.bestiary import create_skeleton
from dnd.utils import deal_damage_to, force_attack_crit, force_attack_hit, get_hp, reset_combat_state, set_hp
from dnd.utils import force_attack_miss


def reset_class_feature_state(width: int = 14, height: int = 8) -> None:
    """Clear global state and create a rectangular class-feature test grid."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, width, height)


def create_book_target(
    name: str = "Target",
    position: tuple[int, int] = (3, 1),
    creature_type: CreatureType = CreatureType.HUMANOID,
) -> Entity:
    """Create a durable target for class feature examples."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=10),
        ),
        action_economy=ActionEconomyConfig(),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")]
        ),
        proficiency_bonus=2,
        position=position,
        faction="monsters",
        creature_type=creature_type,
    )
    entity = Entity.create(source_entity_uuid=UUID(int=position[0] + position[1] + 1), name=name, config=config)
    setup_standard_actions(entity)
    return entity


def create_book_paladin(
    name: str = "Book Paladin",
    position: tuple[int, int] = (1, 1),
    spell_slots: Optional[dict[int, int]] = None,
) -> Entity:
    """Create a minimal paladin-like entity for Divine Smite examples."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=14),
        ),
        action_economy=ActionEconomyConfig(spell_slots=spell_slots or {1: 1}),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="maximums")]
        ),
        proficiency_bonus=3,
        position=position,
        faction="heroes",
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    entity.equipment.equip(create_longsword(entity.uuid), WeaponSlot.MELEE_MAIN)
    setup_standard_actions(entity)
    return entity


def get_smite_event(entity_uuid: UUID) -> Optional[DamageRollResultEvent]:
    """Return the latest Divine Smite damage-roll result event for an entity."""
    for obj in reversed(tuple(BaseObject._registry.values())):
        if (
            isinstance(obj, DamageRollResultEvent)
            and obj.source_entity_uuid == entity_uuid
            and obj.context.get("divine_smite_applied")
        ):
            return obj
    return None


def get_smite_context(entity_uuid: UUID) -> Optional[dict]:
    """Return Divine Smite metadata from the latest damage-roll result event."""
    event = get_smite_event(entity_uuid)
    return event.context if event else None


def get_latest_skill_check_event(entity_uuid: UUID, skill_name: str) -> Optional[SkillCheckEvent]:
    """Return the latest completed skill-check event for an entity and skill."""
    for event in reversed(EventQueue._all_events):
        if (
            isinstance(event, SkillCheckEvent)
            and event.source_entity_uuid == entity_uuid
            and event.skill_name == skill_name
            and event.phase == EventPhase.COMPLETION
        ):
            return event
    return None


def prove_extra_attack_count(fighter: Entity, target: Entity, expected_extra_attacks: int) -> None:
    """Assert one Attack action grants exactly the expected number of extras."""
    force_attack_miss(fighter)
    fighter.action_economy.reset_all_costs()
    fighter.action_economy.on_turn_start()

    feature = fighter.active_conditions["Extra Attack"]
    resource = fighter.action_economy.resources["extra_attacks"]

    assert isinstance(feature, ExtraAttackFeature)
    assert feature.extra_attacks == expected_extra_attacks
    assert resource.maximum == expected_extra_attacks

    resource.current = 0
    attack_event = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert attack_event is not None
    assert not attack_event.canceled
    assert resource.current == expected_extra_attacks

    for remaining in range(expected_extra_attacks - 1, -1, -1):
        extra_event = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            template=False,
        ).apply()

        assert extra_event is not None
        assert not extra_event.canceled
        assert resource.current == remaining

    exhausted_event = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert exhausted_event is None or exhausted_event.canceled
    assert resource.current == 0


def spend_attack_batch(fighter: Entity, target: Entity, expected_extra_attacks: int) -> None:
    """Spend one action-cost Attack plus its full Extra Attack batch."""
    resource = fighter.action_economy.resources["extra_attacks"]

    attack_event = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert attack_event is not None
    assert not attack_event.canceled
    assert resource.current == expected_extra_attacks

    for remaining in range(expected_extra_attacks - 1, -1, -1):
        extra_event = ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            template=False,
        ).apply()

        assert extra_event is not None
        assert not extra_event.canceled
        assert resource.current == remaining

    exhausted_event = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert exhausted_event is None or exhausted_event.canceled
    assert resource.current == 0


def create_attack_roll(entity: Entity, natural_roll: int, bonus: int = 5) -> DiceRoll:
    """Create a deterministic attack roll result for outcome-threshold checks."""
    return DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.ATTACK,
        results=[natural_roll],
        total=natural_roll + bonus,
        bonus=bonus,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NONE,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=entity.uuid,
    )


def test_eb_16_001_factories_apply_level_gated_features_and_resources() -> None:
    """EB-16-001: factories wire level-gated class features and resources."""
    reset_class_feature_state()

    fighter = create_fighter(
        FighterConfig(
            level=5,
            name="Book Fighter",
            position=(1, 1),
            faction="heroes",
            fighting_style="defense",
            asi_4=[("strength", 2)],
        )
    )
    barbarian = create_barbarian(
        BarbarianConfig(
            level=5,
            name="Book Barbarian",
            position=(2, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
        )
    )
    sorcerer = create_sorcerer(
        SorcererConfig(
            level=5,
            name="Book Sorcerer",
            position=(3, 1),
            faction="heroes",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            spell_names=["Fire Bolt", "Magic Missile", "Hold Person"],
        )
    )

    assert "Second Wind Feature" in fighter.active_conditions
    assert "Action Surge Feature" in fighter.active_conditions
    assert "Extra Attack" in fighter.active_conditions
    assert fighter.action_economy.resources["extra_attacks"].maximum == 1
    assert fighter.action_economy.resources["action_surge"].maximum == 1

    assert "Rage Feature" in barbarian.active_conditions
    assert "Frenzy Feature" in barbarian.active_conditions
    assert "Fast Movement" in barbarian.active_conditions
    assert barbarian.action_economy.resources["rage"].maximum == 3

    assert "Draconic Resilience" in sorcerer.active_conditions
    assert "Sorcery Points Feature" in sorcerer.active_conditions
    assert sorcerer.action_economy.resources["sorcery_points"].maximum == 5
    assert sorcerer.action_economy.spell_slot_3.normalized_score == 2
    assert sorcerer.get_action_template("Quickened Spell") is not None
    assert sorcerer.get_action_template("Twinned Spell") is not None
    assert sorcerer.get_action_template("Fire Bolt") is not None


def test_eb_16_002_fighter_resources_actions_and_short_rest_recharge() -> None:
    """EB-16-002: fighter features register actions and spend rechargeable resources."""
    reset_class_feature_state()
    fighter = create_fighter(
        FighterConfig(level=2, name="Book Fighter", position=(1, 1), faction="heroes")
    )

    assert fighter.get_action_template("Second Wind") is not None
    assert fighter.get_action_template("Action Surge") is not None
    assert fighter.action_economy.resources["second_wind"].current == 1
    assert fighter.action_economy.resources["action_surge"].current == 1

    set_hp(fighter, get_hp(fighter) - 5)
    wounded_hp = get_hp(fighter)
    second_wind = SecondWind(source_entity_uuid=fighter.uuid, fighter_level=2, template=False)
    second_wind_event = second_wind.apply()

    assert second_wind_event is not None
    assert not second_wind_event.canceled
    assert get_hp(fighter) > wounded_hp
    assert fighter.action_economy.resources["second_wind"].current == 0
    assert fighter.action_economy.bonus_actions.normalized_score == 0

    fighter.action_economy.reset_all_costs()
    initial_actions = fighter.action_economy.actions.normalized_score
    action_surge = ActionSurge(source_entity_uuid=fighter.uuid, template=False)
    action_surge_event = action_surge.apply()

    assert action_surge_event is not None
    assert not action_surge_event.canceled
    assert "ActionSurging" in fighter.active_conditions
    assert fighter.action_economy.actions.normalized_score == initial_actions + 1
    assert fighter.action_economy.resources["action_surge"].current == 0

    fighter.action_economy.on_short_rest()

    assert fighter.action_economy.resources["second_wind"].current == 1
    assert fighter.action_economy.resources["action_surge"].current == 1


def test_eb_16_007_fighter_level_ten_champion_adds_distinct_second_fighting_style() -> None:
    """EB-16-007: level 10 Champion adds a distinct second Fighting Style."""
    reset_class_feature_state()

    fighter = create_fighter(
        FighterConfig(
            level=10,
            name="Book Champion",
            position=(1, 1),
            faction="heroes",
            fighting_style="defense",
            second_fighting_style="protection",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
        )
    )
    extra_attack = fighter.active_conditions["Extra Attack"]

    assert "Fighting Style: Defense" in fighter.active_conditions
    assert "Fighting Style: Protection" in fighter.active_conditions
    assert fighter.get_event_handler_by_name("Protection") is not None
    assert "Indomitable" in fighter.active_conditions
    assert "Improved Critical" in fighter.active_conditions
    assert isinstance(extra_attack, ExtraAttackFeature)
    assert extra_attack.extra_attacks == 1

    assert fighter.proficiency_bonus.normalized_score == 4
    assert fighter.ability_scores.strength.ability_score.score == 20
    assert fighter.ability_scores.constitution.ability_score.score == 17
    assert fighter.ac_bonus().normalized_score == 19
    assert fighter.action_economy.resources["indomitable"].maximum == 1
    assert fighter.action_economy.resources["extra_attacks"].maximum == 1
    assert fighter.get_action_template("Extra Attack_MELEE_MAIN") is not None

    duplicate_style_error = None
    early_style_error = None
    try:
        FighterConfig(
            level=10,
            fighting_style="defense",
            second_fighting_style="defense",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
        )
    except ValidationError as exc:
        duplicate_style_error = exc

    try:
        FighterConfig(
            level=9,
            fighting_style="defense",
            second_fighting_style="protection",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
        )
    except ValidationError as exc:
        early_style_error = exc

    assert duplicate_style_error is not None
    assert "Cannot take same fighting style twice" in str(duplicate_style_error)
    assert early_style_error is not None
    assert "Second fighting style requires level 10+" in str(early_style_error)


def test_eb_16_008_extra_attack_recharges_for_action_surge_attack_action() -> None:
    """EB-16-008: Extra Attack refreshes for the action granted by Action Surge."""
    reset_class_feature_state()

    fighter = create_fighter(
        FighterConfig(
            level=5,
            name="Book Fighter",
            position=(1, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
        )
    )
    target = create_book_target(position=(2, 1))
    Entity.update_all_entities_senses()
    force_attack_miss(fighter)
    fighter.action_economy.reset_all_costs()
    fighter.action_economy.on_turn_start()

    assert fighter.action_economy.actions.normalized_score == 1
    assert fighter.action_economy.resources["extra_attacks"].current == 1
    assert "ExtraAttacksGranted" not in fighter.active_conditions

    first_attack_event = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert first_attack_event is not None
    assert not first_attack_event.canceled
    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources["extra_attacks"].current == 1
    assert "ExtraAttacksGranted" in fighter.active_conditions

    first_extra_event = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert first_extra_event is not None
    assert not first_extra_event.canceled
    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources["extra_attacks"].current == 0

    surge_event = ActionSurge(source_entity_uuid=fighter.uuid, template=False).apply()

    assert surge_event is not None
    assert not surge_event.canceled
    assert "ActionSurging" in fighter.active_conditions
    assert fighter.action_economy.actions.normalized_score == 1
    assert fighter.action_economy.resources["action_surge"].current == 0

    second_attack_event = Attack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert second_attack_event is not None
    assert not second_attack_event.canceled
    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources["extra_attacks"].current == 1

    second_extra_event = ExtraAttack(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert second_extra_event is not None
    assert not second_extra_event.canceled
    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources["extra_attacks"].current == 0


def test_eb_16_009_extra_attack_counts_scale_at_fighter_levels_eleven_and_twenty() -> None:
    """EB-16-009: Extra Attack grants two extras at L11 and three at L20."""
    reset_class_feature_state()

    level_eleven = create_fighter(
        FighterConfig(
            level=11,
            name="Book Veteran",
            position=(1, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
        )
    )
    level_twenty = create_fighter(
        FighterConfig(
            level=20,
            name="Book Legend",
            position=(4, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("dexterity", 2)],
            asi_12=[("wisdom", 2)],
            asi_14=[("constitution", 2)],
            asi_16=[("strength", 1), ("wisdom", 1)],
            asi_19=[("dexterity", 1), ("constitution", 1)],
        )
    )
    target_eleven = create_book_target(name="Veteran Target", position=(2, 1))
    target_twenty = create_book_target(name="Legend Target", position=(5, 1))
    Entity.update_all_entities_senses()

    prove_extra_attack_count(level_eleven, target_eleven, expected_extra_attacks=2)
    prove_extra_attack_count(level_twenty, target_twenty, expected_extra_attacks=3)


def test_eb_16_014_higher_level_extra_attack_refreshes_after_action_surge() -> None:
    """EB-16-014: Action Surge grants a full new Extra Attack batch at L11/L20."""
    reset_class_feature_state()

    level_eleven = create_fighter(
        FighterConfig(
            level=11,
            name="Book Action Surge Veteran",
            position=(1, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
        )
    )
    level_twenty = create_fighter(
        FighterConfig(
            level=20,
            name="Book Action Surge Legend",
            position=(4, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("dexterity", 2)],
            asi_12=[("wisdom", 2)],
            asi_14=[("constitution", 2)],
            asi_16=[("strength", 1), ("wisdom", 1)],
            asi_19=[("dexterity", 1), ("constitution", 1)],
        )
    )
    target_eleven = create_book_target(name="Veteran Surge Target", position=(2, 1))
    target_twenty = create_book_target(name="Legend Surge Target", position=(5, 1))
    Entity.update_all_entities_senses()

    for fighter, target, expected_extra_attacks, expected_action_surge_uses in [
        (level_eleven, target_eleven, 2, 1),
        (level_twenty, target_twenty, 3, 2),
    ]:
        force_attack_miss(fighter)
        fighter.action_economy.reset_all_costs()
        fighter.action_economy.on_turn_start()

        resource = fighter.action_economy.resources["extra_attacks"]
        action_surge_resource = fighter.action_economy.resources["action_surge"]
        feature = fighter.active_conditions["Extra Attack"]

        assert isinstance(feature, ExtraAttackFeature)
        assert feature.extra_attacks == expected_extra_attacks
        assert resource.maximum == expected_extra_attacks
        assert resource.current == expected_extra_attacks
        assert action_surge_resource.current == expected_action_surge_uses
        assert fighter.action_economy.actions.normalized_score == 1

        resource.current = 0
        spend_attack_batch(fighter, target, expected_extra_attacks)

        assert fighter.action_economy.actions.normalized_score == 0

        surge_event = ActionSurge(source_entity_uuid=fighter.uuid, template=False).apply()

        assert surge_event is not None
        assert not surge_event.canceled
        assert fighter.action_economy.actions.normalized_score == 1
        assert action_surge_resource.current == expected_action_surge_uses - 1

        spend_attack_batch(fighter, target, expected_extra_attacks)

        assert fighter.action_economy.actions.normalized_score == 0
        assert resource.current == 0


def test_eb_16_010_indomitable_rerolls_failed_saves_and_recharges_on_long_rest() -> None:
    """EB-16-010: Indomitable rerolls a failed save and recharges on long rest."""
    reset_class_feature_state()

    fighter = create_fighter(
        FighterConfig(
            level=9,
            name="Book Indomitable Fighter",
            position=(1, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
        )
    )
    caster = create_book_target(name="Book Caster", position=(2, 1))
    Entity.update_all_entities_senses()

    handler = fighter.get_event_handler_by_name("Indomitable")
    resource = fighter.action_economy.resources["indomitable"]

    assert "Indomitable" in fighter.active_conditions
    assert handler is not None
    assert handler.player_toggleable
    assert resource.current == 1
    assert resource.maximum == 1

    easy_request = caster.create_saving_throw_request(
        target_entity_uuid=fighter.uuid,
        ability_name="wisdom",
        dc=1,
    )
    with patch("dnd.core.dice.random.randint", return_value=10):
        easy_outcome, easy_roll, easy_success = fighter.saving_throw(easy_request)

    assert easy_outcome == AttackOutcome.HIT
    assert easy_success
    assert easy_roll.total == 11
    assert resource.current == 1

    hard_roll_values = iter([2])

    def hard_save_randint(minimum: int, maximum: int) -> int:
        """Return 2 for the original save, then 18 for the reroll."""
        return next(hard_roll_values, 18)

    hard_request = caster.create_saving_throw_request(
        target_entity_uuid=fighter.uuid,
        ability_name="wisdom",
        dc=15,
    )
    with patch("dnd.core.dice.random.randint", side_effect=hard_save_randint):
        hard_outcome, hard_roll, hard_success = fighter.saving_throw(hard_request)

    assert hard_outcome == AttackOutcome.HIT
    assert hard_success
    assert hard_roll.results == [18]
    assert hard_roll.total == 19
    assert resource.current == 0

    fighter.action_economy.on_long_rest()

    assert resource.current == 1


def test_eb_16_011_champion_critical_thresholds_upgrade_without_stacking() -> None:
    """EB-16-011: Champion crit thresholds upgrade from Improved to Superior."""
    reset_class_feature_state()

    level_fourteen = create_fighter(
        FighterConfig(
            level=14,
            name="Book Improved Champion",
            position=(1, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
            asi_12=[("wisdom", 2)],
            asi_14=[("dexterity", 2)],
        )
    )
    level_fifteen = create_fighter(
        FighterConfig(
            level=15,
            name="Book Superior Champion",
            position=(3, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
            asi_12=[("wisdom", 2)],
            asi_14=[("dexterity", 2)],
        )
    )

    assert "Improved Critical" in level_fourteen.active_conditions
    assert "Superior Critical" not in level_fourteen.active_conditions
    assert level_fourteen.get_crit_threshold(WeaponSlot.MELEE_MAIN) == 19
    assert level_fourteen.get_crit_threshold(WeaponSlot.RANGED_MAIN) == 19

    improved_18 = create_attack_roll(level_fourteen, 18)
    improved_19 = create_attack_roll(level_fourteen, 19)

    assert determine_attack_outcome(
        improved_18,
        10,
        crit_threshold=level_fourteen.get_crit_threshold(),
    ) == AttackOutcome.HIT
    assert determine_attack_outcome(
        improved_19,
        10,
        crit_threshold=level_fourteen.get_crit_threshold(),
    ) == AttackOutcome.CRIT

    assert "Improved Critical" not in level_fifteen.active_conditions
    assert "Superior Critical" in level_fifteen.active_conditions
    assert level_fifteen.get_crit_threshold(WeaponSlot.MELEE_MAIN) == 18
    assert level_fifteen.get_crit_threshold(WeaponSlot.RANGED_MAIN) == 18

    superior_17 = create_attack_roll(level_fifteen, 17)
    superior_18 = create_attack_roll(level_fifteen, 18)

    assert determine_attack_outcome(
        superior_17,
        10,
        crit_threshold=level_fifteen.get_crit_threshold(),
    ) == AttackOutcome.HIT
    assert determine_attack_outcome(
        superior_18,
        10,
        crit_threshold=level_fifteen.get_crit_threshold(),
    ) == AttackOutcome.CRIT

    level_fifteen.remove_condition("Superior Critical")

    assert level_fifteen.get_crit_threshold(WeaponSlot.MELEE_MAIN) == 20
    assert level_fifteen.get_crit_threshold(WeaponSlot.RANGED_MAIN) == 20


def test_eb_16_012_survivor_heals_only_at_valid_turn_start_thresholds() -> None:
    """EB-16-012: Survivor heals at turn start only when its gates pass."""
    reset_class_feature_state()

    fighter = create_fighter(
        FighterConfig(
            level=18,
            name="Book Survivor Champion",
            position=(1, 1),
            faction="heroes",
            asi_4=[("strength", 2)],
            asi_6=[("constitution", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
            asi_12=[("wisdom", 2)],
            asi_14=[("constitution", 2)],
            asi_16=[("dexterity", 2)],
        )
    )
    survivor_handler = fighter.get_event_handler_by_name("Survivor")
    max_hp = get_hp(fighter)
    con_mod = fighter.ability_scores.constitution.modifier
    expected_healing = 5 + con_mod

    assert "Survivor" in fighter.active_conditions
    assert survivor_handler is not None
    assert "Superior Critical" in fighter.active_conditions

    set_hp(fighter, max_hp // 2)
    wounded_hp = get_hp(fighter)
    healing_event = fighter.on_turn_start()

    assert get_hp(fighter) == wounded_hp + expected_healing
    assert "Survivor heals" in (healing_event.status_message or "")

    set_hp(fighter, max_hp // 2 + 1)
    above_half_hp = get_hp(fighter)
    fighter.on_turn_start()

    assert get_hp(fighter) == above_half_hp

    set_hp(fighter, 0)
    fighter.on_turn_start()

    assert get_hp(fighter) == 0

    fighter.remove_condition("Survivor")
    assert fighter.get_event_handler_by_name("Survivor") is None

    set_hp(fighter, max_hp // 2)
    after_removal_hp = get_hp(fighter)
    fighter.on_turn_start()

    assert get_hp(fighter) == after_removal_hp


def test_eb_16_013_fighting_styles_place_expected_modifiers_and_handlers() -> None:
    """EB-16-013: Fighter fighting styles wire their concrete engine hooks."""
    reset_class_feature_state(width=18, height=8)

    archer = create_fighter(
        FighterConfig(
            level=1,
            name="Book Archer",
            position=(1, 1),
            faction="heroes",
            fighting_style="archery",
            equipment_preset="archery",
        )
    )
    defender = create_fighter(
        FighterConfig(
            level=1,
            name="Book Defender",
            position=(3, 1),
            faction="heroes",
            fighting_style="defense",
        )
    )
    duelist = create_fighter(
        FighterConfig(
            level=1,
            name="Book Duelist",
            position=(5, 1),
            faction="heroes",
            fighting_style="dueling",
        )
    )
    great_weapon = create_fighter(
        FighterConfig(
            level=1,
            name="Book Great Weapon",
            position=(7, 1),
            faction="heroes",
            fighting_style="great_weapon",
            equipment_preset="greatsword",
        )
    )
    protector = create_fighter(
        FighterConfig(
            level=1,
            name="Book Protector",
            position=(9, 1),
            faction="heroes",
            fighting_style="protection",
        )
    )
    two_weapon = create_fighter(
        FighterConfig(
            level=1,
            name="Book Two Weapon",
            position=(13, 1),
            faction="heroes",
            fighting_style="two_weapon",
            equipment_preset="dual_wield",
        )
    )

    assert archer.equipment.ranged_attack_bonus.normalized_score == 2
    archer.remove_condition("Fighting Style: Archery")
    assert archer.equipment.ranged_attack_bonus.normalized_score == 0

    assert defender.ac_bonus().normalized_score == 19
    defender.remove_condition("Fighting Style: Defense")
    assert defender.ac_bonus().normalized_score == 18

    assert duelist.equipment.melee_damage_bonus.normalized_score == 2
    duelist.remove_condition("Fighting Style: Dueling")
    assert duelist.equipment.melee_damage_bonus.normalized_score == 0

    gwf_handler = great_weapon.get_event_handler_by_name("Great Weapon Fighting")
    assert gwf_handler is not None
    assert gwf_handler.player_toggleable
    great_weapon.remove_condition("Fighting Style: Great Weapon Fighting")
    assert great_weapon.get_event_handler_by_name("Great Weapon Fighting") is None

    expected_off_hand_bonus = max(
        two_weapon.ability_scores.strength.modifier,
        two_weapon.ability_scores.dexterity.modifier,
    )
    assert two_weapon.equipment.off_hand_melee_ability_bonus.normalized_score == expected_off_hand_bonus
    two_weapon.remove_condition("Fighting Style: Two-Weapon Fighting")
    assert two_weapon.equipment.off_hand_melee_ability_bonus.normalized_score == 0

    ally = create_book_target(name="Protected Ally", position=(10, 1))
    enemy = create_skeleton(name="Book Enemy", position=(11, 1))
    setup_standard_actions(enemy)
    Entity.update_all_entities_senses(max_distance=20)
    force_attack_miss(enemy)

    protection_event = Attack(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=ally.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    assert protection_event is not None
    assert protection_event.attack_bonus is not None
    assert protection_event.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert protector.action_economy.reactions.normalized_score == 0


def test_eb_16_003_barbarian_rage_and_frenzy_cleanup_cascade() -> None:
    """EB-16-003: Berserker Frenzy creates and cleans a Raging child tree."""
    reset_class_feature_state()
    barbarian = create_barbarian(
        BarbarianConfig(
            level=3,
            name="Book Berserker",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
        )
    )

    assert barbarian.get_action_template("Frenzy") is not None
    assert barbarian.action_economy.resources["rage"].current == 3

    frenzy = Frenzy(source_entity_uuid=barbarian.uuid, rage_damage=2, template=False)
    frenzy_event = frenzy.apply()

    assert frenzy_event is not None
    assert not frenzy_event.canceled
    assert "Raging" in barbarian.active_conditions
    assert "Frenzied" in barbarian.active_conditions
    assert barbarian.get_action_template("Frenzied Strike") is not None
    assert barbarian.action_economy.resources["rage"].current == 2

    raging = barbarian.active_conditions["Raging"]
    frenzied = barbarian.active_conditions["Frenzied"]
    assert frenzied.uuid in raging.sub_conditions

    barbarian.remove_condition("Raging")

    assert "Raging" not in barbarian.active_conditions
    assert "Frenzied" not in barbarian.active_conditions
    assert barbarian.get_action_template("Frenzied Strike") is None


def test_eb_16_015_barbarian_factory_scales_rage_brutal_critical_and_capstone() -> None:
    """EB-16-015: Barbarian factory scales rage, Brutal Critical, and capstone."""
    reset_class_feature_state()

    level_one = create_barbarian(
        BarbarianConfig(
            level=1,
            name="Book Young Barbarian",
            position=(1, 1),
            faction="heroes",
        )
    )
    level_nine = create_barbarian(
        BarbarianConfig(
            level=9,
            name="Book Brutal Barbarian",
            position=(3, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
            asi_8=[("constitution", 2)],
        )
    )
    level_seventeen = create_barbarian(
        BarbarianConfig(
            level=17,
            name="Book Persistent Barbarian",
            position=(5, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
            asi_12=[("constitution", 2)],
            asi_16=[("dexterity", 2)],
        )
    )
    level_twenty = create_barbarian(
        BarbarianConfig(
            level=20,
            name="Book Primal Champion",
            position=(7, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
            asi_12=[("constitution", 2)],
            asi_16=[("constitution", 2)],
            asi_19=[("dexterity", 2)],
        )
    )

    level_one_rage = level_one.active_conditions["Rage Feature"]
    level_nine_rage = level_nine.active_conditions["Rage Feature"]
    level_seventeen_rage = level_seventeen.active_conditions["Rage Feature"]
    level_twenty_rage = level_twenty.active_conditions["Rage Feature"]

    assert isinstance(level_one_rage, RageFeature)
    assert isinstance(level_nine_rage, RageFeature)
    assert isinstance(level_seventeen_rage, RageFeature)
    assert isinstance(level_twenty_rage, RageFeature)

    assert level_one.action_economy.resources["rage"].maximum == 2
    assert level_one_rage.rage_damage == 2
    assert "Brutal Critical" not in level_one.active_conditions
    assert "Fast Movement" not in level_one.active_conditions

    assert level_nine.action_economy.resources["rage"].maximum == 4
    assert level_nine_rage.rage_damage == 3
    assert "Fast Movement" in level_nine.active_conditions
    assert level_nine.action_economy.movement.normalized_score == 40
    assert "Feral Instinct" in level_nine.active_conditions
    assert level_nine.initiative.advantage == AdvantageStatus.ADVANTAGE
    assert level_nine.get_crit_extra_dice(WeaponSlot.MELEE_MAIN) == 1
    assert level_nine.get_crit_extra_dice(WeaponSlot.RANGED_MAIN) == 0

    assert level_seventeen.action_economy.resources["rage"].maximum == 6
    assert level_seventeen_rage.rage_damage == 4
    assert level_seventeen.get_crit_extra_dice(WeaponSlot.MELEE_MAIN) == 3
    assert "Relentless Rage" in level_seventeen.active_conditions
    assert level_seventeen.action_economy.resources["relentless_rage"].maximum == 5
    assert level_seventeen.get_event_handler_by_name("Relentless Rage") is not None
    assert "PersistentRage" in level_seventeen.active_conditions
    assert "Indomitable Might" not in level_seventeen.active_conditions

    assert level_twenty.action_economy.resources["rage"].maximum == 999
    assert level_twenty_rage.rage_damage == 4
    assert level_twenty.get_crit_extra_dice(WeaponSlot.MELEE_MAIN) == 3
    assert "Indomitable Might" in level_twenty.active_conditions
    assert level_twenty.get_event_handler_by_name("Indomitable Might") is not None
    assert "Primal Champion" in level_twenty.active_conditions
    assert level_twenty.ability_scores.strength.ability_score.score == 24
    assert level_twenty.ability_scores.constitution.ability_score.score == 24

    level_twenty.remove_condition("Primal Champion")

    assert level_twenty.ability_scores.strength.ability_score.score == 20
    assert level_twenty.ability_scores.constitution.ability_score.score == 20


def test_eb_16_023_barbarian_primal_champion_updates_derived_combat_surfaces() -> None:
    """EB-16-023: Primal Champion flows through derived STR/CON surfaces."""
    reset_class_feature_state(width=20, height=8)

    barbarian = create_barbarian(
        BarbarianConfig(
            level=20,
            name="Book Primal Combatant",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
            asi_12=[("constitution", 2)],
            asi_16=[("constitution", 2)],
            asi_19=[("dexterity", 2)],
        )
    )
    target = create_book_target(name="Primal Target", position=(2, 1))
    Entity.update_all_entities_senses(max_distance=30)

    def snapshot() -> dict[str, int]:
        damages = barbarian.get_damages(WeaponSlot.MELEE_MAIN, target.uuid)
        assert damages
        assert damages[0].damage_bonus is not None

        return {
            "strength_score": barbarian.ability_scores.strength.ability_score.score,
            "constitution_score": barbarian.ability_scores.constitution.ability_score.score,
            "strength_modifier": barbarian.ability_scores.strength.get_combined_values().normalized_score,
            "constitution_modifier": barbarian.ability_scores.constitution.get_combined_values().normalized_score,
            "melee_attack": barbarian.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid).normalized_score,
            "melee_damage": damages[0].damage_bonus.normalized_score,
            "athletics": barbarian.skill_bonus(target.uuid, "athletics").normalized_score,
            "strength_save": barbarian.saving_throw_bonus(target.uuid, "strength").normalized_score,
            "constitution_save": barbarian.saving_throw_bonus(target.uuid, "constitution").normalized_score,
            "unarmored_ac": barbarian.ac_bonus(target.uuid).normalized_score,
            "hp": barbarian.get_hp(),
        }

    assert "Primal Champion" in barbarian.active_conditions

    boosted = snapshot()

    assert boosted["strength_score"] == 24
    assert boosted["constitution_score"] == 24
    assert boosted["strength_modifier"] == 7
    assert boosted["constitution_modifier"] == 7

    barbarian.remove_condition("Primal Champion")
    unboosted = snapshot()

    assert unboosted["strength_score"] == 20
    assert unboosted["constitution_score"] == 20
    assert "Primal Champion" not in barbarian.active_conditions

    ability_delta = 2
    hit_point_delta = ability_delta * barbarian.health.total_hit_dices_number

    for key in [
        "strength_modifier",
        "constitution_modifier",
        "melee_attack",
        "melee_damage",
        "athletics",
        "strength_save",
        "constitution_save",
        "unarmored_ac",
    ]:
        assert boosted[key] == unboosted[key] + ability_delta

    assert boosted["hp"] == unboosted["hp"] + hit_point_delta


def test_eb_16_019_barbarian_reckless_danger_sense_and_mindless_rage_edges() -> None:
    """EB-16-019: early Barbarian tactical features mutate live roll surfaces."""
    reset_class_feature_state(width=20, height=8)

    barbarian = create_barbarian(
        BarbarianConfig(
            level=6,
            name="Book Tactical Berserker",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
        )
    )
    visible_source = create_book_target(name="Visible Hazard Source", position=(3, 1))
    Entity.update_all_entities_senses(max_distance=30)

    assert "Reckless Attack Feature" in barbarian.active_conditions
    assert "Danger Sense" in barbarian.active_conditions
    assert "Mindless Rage" in barbarian.active_conditions

    available = get_available_actions(barbarian)
    reckless_info = next(
        action for action in available.self_actions if action.template_name == "Reckless Attack"
    )

    assert barbarian.equipment.melee_attack_bonus.advantage == AdvantageStatus.NONE
    reckless_event = execute_action(barbarian, "Reckless Attack", reckless_info.valid_targets[0])

    assert reckless_event is not None
    assert not reckless_event.canceled
    assert "Reckless Attacking" in barbarian.active_conditions
    assert barbarian.equipment.melee_attack_bonus.advantage == AdvantageStatus.ADVANTAGE
    assert barbarian.equipment.ac_bonus.to_target_static.advantage_sum > 0

    repeated_reckless_event = execute_action(barbarian, "Reckless Attack", reckless_info.valid_targets[0])

    assert repeated_reckless_event is not None
    assert repeated_reckless_event.canceled
    assert repeated_reckless_event.status_message == "Already attacking recklessly"

    dex_save_bonus = barbarian.saving_throws.get_saving_throw("dexterity").bonus
    dex_save_bonus.set_target_entity(visible_source.uuid)

    assert dex_save_bonus.advantage == AdvantageStatus.ADVANTAGE

    blinded_event = barbarian.add_condition(
        Blinded(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
    )

    assert blinded_event is not None
    assert not blinded_event.canceled
    assert dex_save_bonus.advantage == AdvantageStatus.NONE

    barbarian.remove_condition("Blinded")

    assert dex_save_bonus.advantage == AdvantageStatus.ADVANTAGE

    dex_save_bonus.set_target_entity(uuid4())

    assert dex_save_bonus.advantage == AdvantageStatus.NONE

    charm_event = barbarian.add_condition(
        Charmed(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
    )
    fear_event = barbarian.add_condition(
        Frightened(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
    )

    assert charm_event is not None
    assert not charm_event.canceled
    assert fear_event is not None
    assert not fear_event.canceled
    assert "Charmed" in barbarian.active_conditions
    assert "Frightened" in barbarian.active_conditions

    rage_event = barbarian.add_condition(
        Raging(
            source_entity_uuid=barbarian.uuid,
            target_entity_uuid=barbarian.uuid,
            rage_damage=2,
        )
    )

    assert rage_event is not None
    assert not rage_event.canceled
    assert "Raging" in barbarian.active_conditions
    assert "Charmed" not in barbarian.active_conditions
    assert "Frightened" not in barbarian.active_conditions

    blocked_charm_event = barbarian.add_condition(
        Charmed(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
    )
    blocked_fear_event = barbarian.add_condition(
        Frightened(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
    )
    poison_event = barbarian.add_condition(
        Poisoned(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
    )

    assert blocked_charm_event is not None
    assert blocked_charm_event.canceled
    assert blocked_fear_event is not None
    assert blocked_fear_event.canceled
    assert poison_event is not None
    assert not poison_event.canceled
    assert "Charmed" not in barbarian.active_conditions
    assert "Frightened" not in barbarian.active_conditions
    assert "Poisoned" in barbarian.active_conditions

    barbarian.remove_condition("Raging")
    post_rage_charm_event = barbarian.add_condition(
        Charmed(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
    )

    assert post_rage_charm_event is not None
    assert not post_rage_charm_event.canceled
    assert "Charmed" in barbarian.active_conditions


def test_eb_16_020_barbarian_relentless_and_persistent_rage_events() -> None:
    """EB-16-020: higher-level Barbarian rage features use event handlers."""
    reset_class_feature_state(width=20, height=8)

    relentless = create_barbarian(
        BarbarianConfig(
            level=11,
            name="Book Relentless Berserker",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
            asi_8=[("constitution", 2)],
        )
    )
    damage_source = create_book_target(name="Fire Hazard", position=(3, 1))
    rage_event = relentless.add_condition(
        Raging(
            source_entity_uuid=relentless.uuid,
            target_entity_uuid=relentless.uuid,
            rage_damage=3,
        )
    )
    relentless_resource = relentless.action_economy.resources.get("relentless_rage")

    assert rage_event is not None
    assert not rage_event.canceled
    assert relentless_resource is not None
    assert relentless_resource.current == 5
    assert relentless.get_event_handler_by_name("Relentless Rage") is not None

    set_hp(relentless, 5)

    with patch("dnd.core.dice.random.randint", return_value=20):
        survival_damage = deal_damage_to(
            relentless,
            20,
            DamageType.FIRE,
            source_uuid=damage_source.uuid,
        )

    assert survival_damage == 4
    assert get_hp(relentless) == 1
    assert relentless_resource.current == 4
    assert relentless.health.life_state is LifeState.ALIVE

    set_hp(relentless, 5)

    with patch("dnd.core.dice.random.randint", return_value=1):
        failed_save_damage = deal_damage_to(
            relentless,
            20,
            DamageType.FIRE,
            source_uuid=damage_source.uuid,
    )

    assert failed_save_damage == 20
    assert get_hp(relentless) <= 0
    assert relentless_resource.current == 4
    assert relentless.health.life_state is LifeState.DEAD

    reset_class_feature_state(width=20, height=8)

    persistent = create_barbarian(
        BarbarianConfig(
            level=15,
            name="Book Persistent Berserker",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
            asi_12=[("constitution", 2)],
        )
    )
    persistent_rage_event = persistent.add_condition(
        Raging(
            source_entity_uuid=persistent.uuid,
            target_entity_uuid=persistent.uuid,
            rage_damage=3,
        )
    )

    assert persistent_rage_event is not None
    assert not persistent_rage_event.canceled
    assert "PersistentRage" in persistent.active_conditions
    assert "Raging" in persistent.active_conditions
    assert "HasAttacked" not in persistent.active_conditions
    assert "HasTakenDamage" not in persistent.active_conditions

    persistent.on_turn_start()

    assert "Raging" in persistent.active_conditions

    persistent.remove_condition("PersistentRage")
    persistent.on_turn_start()

    assert "PersistentRage" not in persistent.active_conditions
    assert "Raging" not in persistent.active_conditions


def test_eb_16_021_barbarian_indomitable_might_recomputes_skill_check_result() -> None:
    """EB-16-021: Indomitable Might updates skill-check rolls and outcomes."""
    reset_class_feature_state(width=20, height=8)

    barbarian = create_barbarian(
        BarbarianConfig(
            level=18,
            name="Book Indomitable Berserker",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
            asi_8=[("strength", 1), ("constitution", 1)],
            asi_12=[("constitution", 2)],
            asi_16=[("dexterity", 2)],
        )
    )
    strength_score = barbarian.ability_scores.strength.ability_score.score

    assert strength_score == 20
    assert "Indomitable Might" in barbarian.active_conditions
    assert barbarian.get_event_handler_by_name("Indomitable Might") is not None

    athletics_request = SkillCheckEvent(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        skill_name="athletics",
        dc=18,
    )
    with patch("dnd.core.dice.random.randint", return_value=1):
        athletics_outcome, athletics_roll, athletics_success = barbarian.skill_check(athletics_request)
    athletics_completion = get_latest_skill_check_event(barbarian.uuid, "athletics")

    assert athletics_outcome == AttackOutcome.HIT
    assert athletics_roll.total == strength_score
    assert athletics_success is True
    assert athletics_completion is not None
    assert athletics_completion.dice_roll is not None
    assert athletics_completion.dice_roll.total == strength_score
    assert athletics_completion.result is True

    perception_request = SkillCheckEvent(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        skill_name="perception",
        dc=18,
    )
    with patch("dnd.core.dice.random.randint", return_value=1):
        perception_outcome, perception_roll, perception_success = barbarian.skill_check(perception_request)
    perception_completion = get_latest_skill_check_event(barbarian.uuid, "perception")

    assert perception_outcome == AttackOutcome.MISS
    assert perception_roll.total < strength_score
    assert perception_success is False
    assert perception_completion is not None
    assert perception_completion.dice_roll is not None
    assert perception_completion.dice_roll.total == perception_roll.total
    assert perception_completion.result is False

    barbarian.remove_condition("Indomitable Might")

    assert barbarian.get_event_handler_by_name("Indomitable Might") is None

    without_feature_request = SkillCheckEvent(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        skill_name="athletics",
        dc=18,
    )
    with patch("dnd.core.dice.random.randint", return_value=1):
        removed_outcome, removed_roll, removed_success = barbarian.skill_check(without_feature_request)

    assert removed_outcome == AttackOutcome.MISS
    assert removed_roll.total < strength_score
    assert removed_success is False


def test_eb_16_022_barbarian_retaliation_reaction_attack_gates() -> None:
    """EB-16-022: Retaliation uses a reaction attack with explicit gates."""

    def create_retaliator(position: tuple[int, int] = (1, 1)) -> Entity:
        return create_barbarian(
            BarbarianConfig(
                level=14,
                name="Book Retaliating Berserker",
                position=position,
                faction="heroes",
                primal_path=PrimalPathChoice.BERSERKER,
                asi_4=[("strength", 2)],
                asi_8=[("strength", 1), ("constitution", 1)],
                asi_12=[("constitution", 2)],
            )
        )

    reset_class_feature_state(width=20, height=8)
    barbarian = create_retaliator()
    attacker = create_book_target(name="Adjacent Attacker", position=(2, 1))
    Entity.update_all_entities_senses(max_distance=30)

    assert "Retaliation" in barbarian.active_conditions
    assert barbarian.get_event_handler_by_name("Retaliation") is not None

    attacker_hp_before = get_hp(attacker)
    actions_before = barbarian.action_economy.actions.normalized_score
    reactions_before = barbarian.action_economy.reactions.normalized_score

    force_attack_hit(barbarian)
    incoming_damage = deal_damage_to(
        barbarian,
        1,
        DamageType.FIRE,
        source_uuid=attacker.uuid,
    )

    assert incoming_damage == 1
    assert get_hp(attacker) < attacker_hp_before
    assert barbarian.action_economy.actions.normalized_score == actions_before
    assert barbarian.action_economy.reactions.normalized_score == reactions_before - 1

    attacker_hp_after_first = get_hp(attacker)
    force_attack_hit(barbarian)
    deal_damage_to(barbarian, 1, DamageType.FIRE, source_uuid=attacker.uuid)

    assert get_hp(attacker) == attacker_hp_after_first
    assert barbarian.action_economy.actions.normalized_score == actions_before
    assert barbarian.action_economy.reactions.normalized_score == 0

    reset_class_feature_state(width=20, height=8)
    distant_barbarian = create_retaliator()
    distant_attacker = create_book_target(name="Distant Attacker", position=(4, 1))
    Entity.update_all_entities_senses(max_distance=30)
    distant_attacker_hp = get_hp(distant_attacker)

    force_attack_hit(distant_barbarian)
    deal_damage_to(distant_barbarian, 1, DamageType.FIRE, source_uuid=distant_attacker.uuid)

    assert get_hp(distant_attacker) == distant_attacker_hp
    assert distant_barbarian.action_economy.reactions.normalized_score == 1

    reset_class_feature_state(width=20, height=8)
    unarmed_barbarian = create_retaliator()
    unarmed_attacker = create_book_target(name="Unarmed Gate Attacker", position=(2, 1))
    unarmed_barbarian.equipment.unequip(WeaponSlot.MELEE_MAIN)
    Entity.update_all_entities_senses(max_distance=30)
    unarmed_attacker_hp = get_hp(unarmed_attacker)

    force_attack_hit(unarmed_barbarian)
    deal_damage_to(unarmed_barbarian, 1, DamageType.FIRE, source_uuid=unarmed_attacker.uuid)

    assert get_hp(unarmed_attacker) == unarmed_attacker_hp
    assert unarmed_barbarian.action_economy.reactions.normalized_score == 1

    unarmed_barbarian.remove_condition("Retaliation")

    assert unarmed_barbarian.get_event_handler_by_name("Retaliation") is None


def test_eb_16_004_sorcerer_quickened_spell_overrides_and_cleanup() -> None:
    """EB-16-004: Quickened Spell mutates templates and cleans after casting."""
    reset_class_feature_state()
    sorcerer = create_sorcerer(
        SorcererConfig(
            level=3,
            name="Book Sorcerer",
            position=(1, 1),
            faction="heroes",
            metamagic_choices=["quickened", "twinned"],
            spell_names=["Fire Bolt", "Magic Missile"],
        )
    )
    target = create_book_target(position=(3, 1))
    Entity.update_all_entities_senses()

    fire_bolt_template = sorcerer.get_action_template("Fire Bolt")
    assert fire_bolt_template is not None
    assert fire_bolt_template.alt_cost_type is None
    assert sorcerer.action_economy.resources["sorcery_points"].current == 3

    quickened_event = QuickenedSpell(source_entity_uuid=sorcerer.uuid, template=False).apply()

    assert quickened_event is not None
    assert not quickened_event.canceled
    assert "MetamagicActive" in sorcerer.active_conditions
    assert sorcerer.action_economy.resources["sorcery_points"].current == 1
    assert fire_bolt_template.alt_cost_type == "bonus_actions"
    assert fire_bolt_template.effective_costs[0].cost_type == "bonus_actions"

    spell_instance = fire_bolt_template.instantiate(target_entity_uuid=target.uuid)
    spell_event = spell_instance.apply()

    assert spell_event is not None
    assert not spell_event.canceled
    assert "MetamagicActive" not in sorcerer.active_conditions
    assert fire_bolt_template.alt_cost_type is None
    assert sorcerer.action_economy.bonus_actions.normalized_score == 0
    assert sorcerer.action_economy.actions.normalized_score == 1


def test_eb_16_016_sorcerer_font_of_magic_twinned_and_distant_overrides() -> None:
    """EB-16-016: Font of Magic plus Twinned and Distant metamagic hooks."""
    reset_class_feature_state(width=30, height=10)

    font_sorcerer = create_sorcerer(
        SorcererConfig(
            level=10,
            name="Book Font Sorcerer",
            position=(1, 1),
            faction="heroes",
            metamagic_choices=["quickened", "twinned", "distant"],
            asi_4=[("charisma", 2)],
            asi_8=[("charisma", 1), ("constitution", 1)],
            spell_names=["Fire Bolt", "Ray of Frost", "Shocking Grasp", "Magic Missile", "Hold Person", "Fireball"],
        )
    )

    assert font_sorcerer.action_economy.resources["sorcery_points"].current == 10
    assert font_sorcerer.action_economy.resources["sorcery_points"].maximum == 10
    assert font_sorcerer.get_action_template("Twinned Spell") is not None
    assert font_sorcerer.get_action_template("Distant Spell") is not None

    for slot_level, sp_cost in [(1, 2), (2, 3), (3, 5), (4, 6), (5, 7)]:
        assert font_sorcerer.get_action_template(f"Slot\u2192SP L{slot_level}") is not None
        assert font_sorcerer.get_action_template(f"{sp_cost}SP\u2192Slot L{slot_level}") is not None
    assert font_sorcerer.get_action_template("Slot\u2192SP L6") is None

    font_sorcerer.action_economy.consume_resource("sorcery_points", 8)
    assert font_sorcerer.action_economy.get_resource_current("sorcery_points") == 2

    slot_to_sp = font_sorcerer.get_action_template("Slot\u2192SP L3")
    assert slot_to_sp is not None
    slot_to_sp.instantiate().apply()

    assert font_sorcerer.action_economy.get_resource_current("sorcery_points") == 5
    assert font_sorcerer.action_economy.spell_slot_3.normalized_score == 2
    assert font_sorcerer.action_economy.bonus_actions.normalized_score == 0

    font_sorcerer.action_economy.reset_all_costs()
    font_sorcerer.action_economy.consume("spell_slot_2", 1, "book_slot_use")
    assert font_sorcerer.action_economy.spell_slot_2.normalized_score == 2

    sp_to_slot = font_sorcerer.get_action_template("3SP\u2192Slot L2")
    assert sp_to_slot is not None
    sp_to_slot.instantiate().apply()

    assert font_sorcerer.action_economy.get_resource_current("sorcery_points") == 2
    assert font_sorcerer.action_economy.spell_slot_2.normalized_score == 3

    twinned_sorcerer = create_sorcerer(
        SorcererConfig(
            level=10,
            name="Book Twinned Sorcerer",
            position=(6, 1),
            faction="heroes",
            metamagic_choices=["quickened", "twinned", "distant"],
            asi_4=[("charisma", 2)],
            asi_8=[("charisma", 1), ("constitution", 1)],
            spell_names=["Fire Bolt", "Magic Missile", "Hold Person", "Fireball"],
        )
    )
    twinned_action = twinned_sorcerer.get_action_template("Twinned Spell")
    assert twinned_action is not None
    twinned_action.instantiate().apply()

    fire_bolt = twinned_sorcerer.get_action_template("Fire Bolt")
    hold_person = twinned_sorcerer.get_action_template("Hold Person")
    magic_missile = twinned_sorcerer.get_action_template("Magic Missile")
    fireball = twinned_sorcerer.get_action_template("Fireball")

    assert isinstance(fire_bolt, SpellAction)
    assert isinstance(hold_person, SpellAction)
    assert isinstance(magic_missile, SpellAction)
    assert isinstance(fireball, SpellAction)
    assert fire_bolt.alt_target_type == TargetType.MULTI_ENTITY
    assert fire_bolt.alt_target_count == 2
    assert fire_bolt.alt_extra_costs == []
    assert hold_person.alt_target_type == TargetType.MULTI_ENTITY
    assert hold_person.alt_target_count == 2
    assert hold_person.alt_extra_costs[0].resource_cost == 1
    assert magic_missile.alt_target_type is None
    assert fireball.alt_target_type is None
    assert twinned_sorcerer.action_economy.get_resource_current("sorcery_points") == 9

    twinned_sorcerer.remove_condition("Sorcery Points Feature")

    assert "MetamagicActive" not in twinned_sorcerer.active_conditions
    assert twinned_sorcerer.get_action_template("Twinned Spell") is None
    assert twinned_sorcerer.get_action_template("Slot\u2192SP L1") is None
    assert fire_bolt.alt_target_type is None
    assert hold_person.alt_target_type is None

    distant_sorcerer = create_sorcerer(
        SorcererConfig(
            level=10,
            name="Book Distant Sorcerer",
            position=(12, 1),
            faction="heroes",
            metamagic_choices=["quickened", "twinned", "distant"],
            asi_4=[("charisma", 2)],
            asi_8=[("charisma", 1), ("constitution", 1)],
            spell_names=["Fire Bolt", "Ray of Frost", "Shocking Grasp", "Magic Missile"],
        )
    )
    distant_action = distant_sorcerer.get_action_template("Distant Spell")
    assert distant_action is not None
    distant_action.instantiate().apply()

    distant_fire_bolt = distant_sorcerer.get_action_template("Fire Bolt")
    ray_of_frost = distant_sorcerer.get_action_template("Ray of Frost")
    shocking_grasp = distant_sorcerer.get_action_template("Shocking Grasp")
    distant_magic_missile = distant_sorcerer.get_action_template("Magic Missile")

    assert isinstance(distant_fire_bolt, SpellAction)
    assert isinstance(ray_of_frost, SpellAction)
    assert isinstance(shocking_grasp, SpellAction)
    assert isinstance(distant_magic_missile, SpellAction)
    assert distant_fire_bolt.spell_range.normal == 120
    assert distant_fire_bolt.alt_range == 240
    assert distant_fire_bolt.effective_range == 240
    assert ray_of_frost.spell_range.normal == 60
    assert ray_of_frost.alt_range == 120
    assert shocking_grasp.alt_range == 30
    assert distant_magic_missile.alt_range == 240
    assert distant_sorcerer.action_economy.get_resource_current("sorcery_points") == 9

    distant_sorcerer.remove_condition("Sorcery Points Feature")

    assert "MetamagicActive" not in distant_sorcerer.active_conditions
    assert distant_sorcerer.get_action_template("Distant Spell") is None
    assert distant_fire_bolt.alt_range is None
    assert ray_of_frost.alt_range is None
    assert shocking_grasp.alt_range is None


def test_eb_16_017_sorcerer_draconic_resilience_and_elemental_affinity() -> None:
    """EB-16-017: Draconic origin wires HP, unarmored AC, and resistance."""
    reset_class_feature_state()

    level_one = create_sorcerer(
        SorcererConfig(
            level=1,
            name="Book Draconic Initiate",
            position=(1, 1),
            faction="heroes",
        )
    )

    assert "Draconic Resilience" in level_one.active_conditions
    assert level_one.health.max_hit_points_bonus.normalized_score == 1
    assert get_hp(level_one) == 9
    assert level_one.ac_bonus().normalized_score == 15

    level_one.equipment.equip(create_leather_armor(level_one.uuid), BodyPart.BODY)

    assert level_one.ac_bonus().normalized_score == 13

    level_one.remove_condition("Draconic Resilience")

    assert "Draconic Resilience" not in level_one.active_conditions
    assert level_one.health.max_hit_points_bonus.normalized_score == 0
    assert get_hp(level_one) == 8

    fire_sorcerer = create_sorcerer(
        SorcererConfig(
            level=6,
            name="Book Fire Dragon Sorcerer",
            position=(3, 1),
            faction="heroes",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            draconic_damage_type="Fire",
        )
    )

    assert "Elemental Affinity" in fire_sorcerer.active_conditions
    assert fire_sorcerer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.RESISTANCE
    assert fire_sorcerer.health.get_resistance(DamageType.COLD) == ResistanceStatus.NONE

    hp_before = get_hp(fire_sorcerer)
    actual_fire_damage = deal_damage_to(fire_sorcerer, 20, DamageType.FIRE)

    assert actual_fire_damage == 10
    assert get_hp(fire_sorcerer) == hp_before - 10

    fire_sorcerer.remove_condition("Elemental Affinity")

    assert fire_sorcerer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.NONE
    assert deal_damage_to(fire_sorcerer, 10, DamageType.FIRE) == 10

    cold_sorcerer = create_sorcerer(
        SorcererConfig(
            level=6,
            name="Book Cold Dragon Sorcerer",
            position=(5, 1),
            faction="heroes",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            draconic_damage_type="Cold",
        )
    )

    assert cold_sorcerer.health.get_resistance(DamageType.COLD) == ResistanceStatus.RESISTANCE
    assert cold_sorcerer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.NONE


def test_eb_16_005_lucky_feat_resource_and_d20_processor() -> None:
    """EB-16-005: Lucky grants a resource and rewrites low own d20 rolls."""
    reset_class_feature_state()
    entity = create_skeleton(name="Lucky Hero", position=(1, 1))
    lucky = LuckyFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
    entity.add_condition(lucky)

    assert "Lucky" in entity.active_conditions
    assert entity.action_economy.resources["luck_points"].current == 3
    assert entity.get_event_handler_by_name("Lucky") is not None

    bonus = ModifiableValue.create(
        source_entity_uuid=entity.uuid,
        base_value=0,
        value_name="Lucky test bonus",
    )
    low_roll = DiceRoll(
        dice_uuid=UUID(int=101),
        roll_type=RollType.CHECK,
        results=[4],
        total=4,
        bonus=0,
        advantage_status=bonus.advantage,
        critical_status=bonus.critical,
        auto_hit_status=bonus.auto_hit,
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    low_event = D20RollResultEvent(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        roll_type=RollType.CHECK,
        roll=low_roll,
        original_roll=low_roll,
        bonus=bonus,
        use_register=False,
    )

    with patch("dnd.core.dice.random.randint", return_value=20):
        modified = lucky_processor(low_event, entity.uuid)

    assert modified is not None
    assert modified.modified
    assert modified.get_effective_roll().total == 20
    assert entity.action_economy.resources["luck_points"].current == 2
    assert modified.roll_modifications

    good_roll = low_roll.model_copy(update={"total": 12, "results": [12]})
    good_event = low_event.model_copy(update={"roll": good_roll, "original_roll": good_roll})

    assert lucky_processor(good_event, entity.uuid) is None
    assert entity.action_economy.resources["luck_points"].current == 2


def test_eb_16_025_lucky_policy_lifecycle_and_cleanup_contract() -> None:
    """EB-16-025: Lucky is an automatic low-roll policy with cleanup."""
    reset_class_feature_state()
    entity = create_skeleton(name="Lucky Policy Hero", position=(1, 1))
    other = create_skeleton(name="Other Roller", position=(2, 1))
    entity.add_condition(LuckyFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid))

    handler = entity.get_event_handler_by_name("Lucky")
    resource = entity.action_economy.resources["luck_points"]

    assert handler is not None
    assert handler.player_toggleable
    assert len(handler.trigger_conditions) == 3
    assert {trigger.event_type for trigger in handler.trigger_conditions} == {
        EventType.ATTACK_D20_ROLL_RESULT,
        EventType.SAVE_D20_ROLL_RESULT,
        EventType.CHECK_D20_ROLL_RESULT,
    }
    assert resource.maximum == 3

    bonus = ModifiableValue.create(
        source_entity_uuid=entity.uuid,
        base_value=0,
        value_name="Lucky policy bonus",
    )
    other_bonus = ModifiableValue.create(
        source_entity_uuid=other.uuid,
        base_value=0,
        value_name="Other lucky policy bonus",
    )

    def make_event(source: Entity, total: int, event_bonus: ModifiableValue) -> D20RollResultEvent:
        roll = DiceRoll(
            dice_uuid=uuid4(),
            roll_type=RollType.CHECK,
            results=[total],
            total=total,
            bonus=0,
            advantage_status=event_bonus.advantage,
            critical_status=event_bonus.critical,
            auto_hit_status=event_bonus.auto_hit,
            source_entity_uuid=source.uuid,
            target_entity_uuid=source.uuid,
        )
        return D20RollResultEvent(
            source_entity_uuid=source.uuid,
            target_entity_uuid=source.uuid,
            roll_type=RollType.CHECK,
            roll=roll,
            original_roll=roll,
            bonus=event_bonus,
            use_register=False,
        )

    with patch("dnd.core.dice.random.randint", return_value=20):
        own_low = lucky_processor(make_event(entity, 4, bonus), entity.uuid)

    assert own_low is not None
    assert own_low.get_effective_roll().total == 20
    assert resource.current == 2

    assert lucky_processor(make_event(other, 4, other_bonus), entity.uuid) is None
    assert resource.current == 2

    assert lucky_processor(make_event(entity, 10, bonus), entity.uuid) is None
    assert resource.current == 2

    resource.current = 0
    assert lucky_processor(make_event(entity, 4, bonus), entity.uuid) is None
    assert resource.current == 0

    entity.action_economy.on_long_rest()
    assert resource.current == 3

    entity.remove_condition("Lucky")

    assert "Lucky" not in entity.active_conditions
    assert entity.get_event_handler_by_name("Lucky") is None
    assert not entity.action_economy.has_resource("luck_points")


def test_eb_16_006_divine_smite_handlers_use_highest_melee_hit_slot_once() -> None:
    """EB-16-006: Divine Smite handlers add one radiant payload on melee hit."""
    reset_class_feature_state()
    paladin_config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=14),
        ),
        action_economy=ActionEconomyConfig(spell_slots={1: 1, 2: 1}),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=5, mode="maximums")]
        ),
        proficiency_bonus=3,
        position=(1, 1),
        faction="heroes",
    )
    paladin = Entity.create(source_entity_uuid=UUID(int=201), name="Book Paladin", config=paladin_config)
    paladin.equipment.equip(create_longsword(paladin.uuid), WeaponSlot.MELEE_MAIN)
    setup_standard_actions(paladin)
    register_divine_smite(paladin, max_slot_level=2)

    target = create_book_target(position=(2, 1))
    Entity.update_all_entities_senses()

    force_attack_hit(paladin)
    attack_event = Attack(
        source_entity_uuid=paladin.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        template=False,
    ).apply()

    context = get_smite_context(paladin.uuid)

    assert attack_event is not None
    assert not attack_event.canceled
    assert context is not None
    assert context["divine_smite_slot_level"] == 2
    assert context["divine_smite_dice_count"] == 3
    assert paladin.action_economy.spell_slot_2.normalized_score == 0
    assert paladin.action_economy.spell_slot_1.normalized_score == 1

    for obj in BaseObject._registry.values():
        if isinstance(obj, DamageRollResultEvent) and obj.source_entity_uuid == paladin.uuid:
            smite_damage = [damage for damage in obj.damages if damage.name == "Divine Smite"]
            assert len(smite_damage) == 1
            assert smite_damage[0].damage_type == DamageType.RADIANT
            break
    else:
        raise AssertionError("No paladin damage-roll result event found")


def test_eb_16_018_divine_smite_handler_gates_fallthrough_and_critical_dice() -> None:
    """EB-16-018: Divine Smite gates no-op safely and crits double smite dice."""

    def setup_case(
        spell_slots: dict[int, int],
        max_slot_level: int,
        target_position: tuple[int, int] = (2, 1),
    ) -> tuple[Entity, Entity]:
        reset_class_feature_state(width=20, height=8)
        paladin = create_book_paladin(spell_slots=spell_slots)
        register_divine_smite(paladin, max_slot_level=max_slot_level)
        target = create_book_target(position=target_position)
        Entity.update_all_entities_senses(max_distance=30)
        return paladin, target

    def apply_attack(attacker: Entity, target: Entity, weapon_slot: WeaponSlot) -> None:
        attack_event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=weapon_slot,
            template=False,
        ).apply()
        assert attack_event is not None
        assert not attack_event.canceled

    fallthrough_paladin, fallthrough_target = setup_case({1: 1, 2: 1, 3: 1}, 3)
    assert fallthrough_paladin.set_handler_enabled("Divine Smite (L3)", False)
    force_attack_hit(fallthrough_paladin)
    apply_attack(fallthrough_paladin, fallthrough_target, WeaponSlot.MELEE_MAIN)
    fallthrough_context = get_smite_context(fallthrough_paladin.uuid)

    assert fallthrough_context is not None
    assert fallthrough_context["divine_smite_slot_level"] == 2
    assert fallthrough_context["divine_smite_dice_count"] == 3
    assert fallthrough_paladin.action_economy.spell_slot_3.normalized_score == 1
    assert fallthrough_paladin.action_economy.spell_slot_2.normalized_score == 0
    assert fallthrough_paladin.action_economy.spell_slot_1.normalized_score == 1

    disabled_paladin, disabled_target = setup_case({1: 1, 2: 1, 3: 1}, 3)
    for level in range(1, 4):
        assert disabled_paladin.set_handler_enabled(f"Divine Smite (L{level})", False)
    force_attack_hit(disabled_paladin)
    apply_attack(disabled_paladin, disabled_target, WeaponSlot.MELEE_MAIN)

    assert get_smite_context(disabled_paladin.uuid) is None
    assert disabled_paladin.action_economy.spell_slot_3.normalized_score == 1
    assert disabled_paladin.action_economy.spell_slot_2.normalized_score == 1
    assert disabled_paladin.action_economy.spell_slot_1.normalized_score == 1

    miss_paladin, miss_target = setup_case({1: 1}, 1)
    force_attack_miss(miss_paladin)
    apply_attack(miss_paladin, miss_target, WeaponSlot.MELEE_MAIN)

    assert get_smite_context(miss_paladin.uuid) is None
    assert miss_paladin.action_economy.spell_slot_1.normalized_score == 1

    ranged_paladin, ranged_target = setup_case({1: 1}, 1, target_position=(6, 1))
    ranged_paladin.equipment.equip(create_shortbow(ranged_paladin.uuid), WeaponSlot.RANGED_MAIN)
    force_attack_hit(ranged_paladin)
    apply_attack(ranged_paladin, ranged_target, WeaponSlot.RANGED_MAIN)

    assert get_smite_context(ranged_paladin.uuid) is None
    assert ranged_paladin.action_economy.spell_slot_1.normalized_score == 1

    empty_slot_paladin, empty_slot_target = setup_case({1: 0}, 1)
    assert not empty_slot_paladin.action_economy.can_afford(spell_slot_cost_type(1), 1)
    force_attack_hit(empty_slot_paladin)
    apply_attack(empty_slot_paladin, empty_slot_target, WeaponSlot.MELEE_MAIN)

    assert get_smite_context(empty_slot_paladin.uuid) is None
    assert empty_slot_paladin.action_economy.spell_slot_1.normalized_score == 0

    crit_paladin, crit_target = setup_case({1: 1}, 1)
    force_attack_hit(crit_paladin)
    force_attack_crit(crit_paladin)
    apply_attack(crit_paladin, crit_target, WeaponSlot.MELEE_MAIN)
    crit_smite_event = get_smite_event(crit_paladin.uuid)

    assert crit_smite_event is not None
    assert crit_smite_event.attack_outcome == AttackOutcome.CRIT
    assert crit_smite_event.context["divine_smite_slot_level"] == 1
    assert crit_smite_event.context["divine_smite_dice_count"] == 2
    crit_smite_results = crit_smite_event.final_rolls[-1].results
    assert isinstance(crit_smite_results, list)
    assert len(crit_smite_results) == 4
    assert crit_paladin.action_economy.spell_slot_1.normalized_score == 0


def test_eb_16_024_divine_smite_creature_type_bonus_dice_and_cap() -> None:
    """EB-16-024: Divine Smite adds SRD bonus dice against undead and fiends."""

    def smite_case(creature_type: CreatureType, slot_level: int) -> tuple[DamageRollResultEvent, Entity]:
        reset_class_feature_state(width=20, height=8)
        paladin = create_book_paladin(spell_slots={slot_level: 1})
        register_divine_smite(paladin, max_slot_level=slot_level)
        target = create_book_target(
            name=f"Book {creature_type.value.title()} Target",
            position=(2, 1),
            creature_type=creature_type,
        )
        Entity.update_all_entities_senses(max_distance=30)

        force_attack_hit(paladin)
        with patch("dnd.core.dice.random.randint", side_effect=lambda _low, high: 10 if high == 20 else 4):
            attack_event = Attack(
                source_entity_uuid=paladin.uuid,
                target_entity_uuid=target.uuid,
                weapon_slot=WeaponSlot.MELEE_MAIN,
                template=False,
            ).apply()
        smite_event = get_smite_event(paladin.uuid)

        assert attack_event is not None
        assert not attack_event.canceled
        assert smite_event is not None
        assert smite_event.target_entity_uuid == target.uuid
        assert paladin.action_economy.can_afford(spell_slot_cost_type(slot_level), 1) is False
        return smite_event, paladin

    humanoid_event, _ = smite_case(CreatureType.HUMANOID, 5)
    humanoid_results = humanoid_event.final_rolls[-1].results

    assert humanoid_event.context["divine_smite_slot_level"] == 5
    assert humanoid_event.context["divine_smite_dice_count"] == 5
    assert humanoid_event.context["divine_smite_creature_type_bonus"] == 0
    assert isinstance(humanoid_results, list)
    assert len(humanoid_results) == 5

    undead_event, _ = smite_case(CreatureType.UNDEAD, 1)
    undead_results = undead_event.final_rolls[-1].results

    assert undead_event.context["divine_smite_slot_level"] == 1
    assert undead_event.context["divine_smite_dice_count"] == 3
    assert undead_event.context["divine_smite_creature_type_bonus"] == 1
    assert isinstance(undead_results, list)
    assert len(undead_results) == 3

    fiend_event, _ = smite_case(CreatureType.FIEND, 5)
    fiend_results = fiend_event.final_rolls[-1].results

    assert fiend_event.context["divine_smite_slot_level"] == 5
    assert fiend_event.context["divine_smite_dice_count"] == 6
    assert fiend_event.context["divine_smite_creature_type_bonus"] == 1
    assert isinstance(fiend_results, list)
    assert len(fiend_results) == 6


def run_all_tests() -> None:
    """Run all Chapter 16 parity examples as a script."""
    tests = [
        test_eb_16_001_factories_apply_level_gated_features_and_resources,
        test_eb_16_002_fighter_resources_actions_and_short_rest_recharge,
        test_eb_16_007_fighter_level_ten_champion_adds_distinct_second_fighting_style,
        test_eb_16_008_extra_attack_recharges_for_action_surge_attack_action,
        test_eb_16_009_extra_attack_counts_scale_at_fighter_levels_eleven_and_twenty,
        test_eb_16_014_higher_level_extra_attack_refreshes_after_action_surge,
        test_eb_16_010_indomitable_rerolls_failed_saves_and_recharges_on_long_rest,
        test_eb_16_011_champion_critical_thresholds_upgrade_without_stacking,
        test_eb_16_012_survivor_heals_only_at_valid_turn_start_thresholds,
        test_eb_16_013_fighting_styles_place_expected_modifiers_and_handlers,
        test_eb_16_003_barbarian_rage_and_frenzy_cleanup_cascade,
        test_eb_16_015_barbarian_factory_scales_rage_brutal_critical_and_capstone,
        test_eb_16_023_barbarian_primal_champion_updates_derived_combat_surfaces,
        test_eb_16_019_barbarian_reckless_danger_sense_and_mindless_rage_edges,
        test_eb_16_020_barbarian_relentless_and_persistent_rage_events,
        test_eb_16_021_barbarian_indomitable_might_recomputes_skill_check_result,
        test_eb_16_022_barbarian_retaliation_reaction_attack_gates,
        test_eb_16_004_sorcerer_quickened_spell_overrides_and_cleanup,
        test_eb_16_016_sorcerer_font_of_magic_twinned_and_distant_overrides,
        test_eb_16_017_sorcerer_draconic_resilience_and_elemental_affinity,
        test_eb_16_005_lucky_feat_resource_and_d20_processor,
        test_eb_16_025_lucky_policy_lifecycle_and_cleanup_contract,
        test_eb_16_006_divine_smite_handlers_use_highest_melee_hit_slot_once,
        test_eb_16_018_divine_smite_handler_gates_fallthrough_and_critical_dice,
        test_eb_16_024_divine_smite_creature_type_bonus_dice_and_cap,
    ]
    for test in tests:
        test()
    print("Chapter 16 class-feature engine book examples passed.")


if __name__ == "__main__":
    run_all_tests()
