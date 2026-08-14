"""SRD monster trait and factory parity tests."""

from collections.abc import Iterable
from uuid import uuid4

from dnd.actions import Attack, AttackEvent
from dnd.conditions import Incapacitated
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.base_actions import ActionEvent
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionApplicationEvent
from dnd.core.base_object import BaseObject
from dnd.core.condition_types import ConditionApplicationDisposition
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    D20RollResultEvent,
    DamageRollResultEvent,
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    RollModificationOperation,
    Trigger,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import AdvantageStatus
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.values import BaseValue
from dnd.entity import Entity
from dnd.monsters.traits import LeadershipAura, LeadershipMembership
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID,
)
from dnd.spatial_effects import FieldEffect, SpatialEffect


def reset_srd_trait_state(width: int = 12, height: int = 12) -> None:
    """Clear global engine registries for isolated SRD trait tests."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    SpatialEffect._effect_registry.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)


def registered_action_names(entity: Entity) -> set[str]:
    """Return registered action template names."""
    return {action.name or "" for action in entity.registered_actions}


def assert_conditions(entity: Entity, names: Iterable[str]) -> None:
    """Assert that feature-marker conditions are active on an entity."""
    for name in names:
        assert name in entity.active_conditions


def latest_damage_roll_result() -> DamageRollResultEvent:
    """Return the latest completed damage-roll event."""
    return next(
        event
        for event in reversed(
            EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
        )
        if (
            isinstance(event, DamageRollResultEvent)
            and event.phase is EventPhase.COMPLETION
        )
    )


def _materialize_srd_fixture(
    creature_id: str,
    *,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    declaration = SRD_CREATURE_DECLARATIONS_BY_ID[creature_id]
    role_suffix = f"{creature_id}_{position[0]}_{position[1]}"
    return materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=uuid4(),
        display_name=declaration.descriptor.display_name,
        faction=faction,
        position=position,
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.srd_traits.{role_suffix}",
        ),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )


def test_factory_trait_packages_are_installed() -> None:
    """Factories should install the trait package advertised by their SRD row."""
    expected_conditions = {
        "cultist": {"Dark Devotion"},
        "tribal_warrior": {"Pack Tactics"},
        "kobold": {"Pack Tactics", "Sunlight Sensitivity"},
        "zombie": {"Undead Fortitude"},
        "wolf": {"Keen Hearing and Smell", "Pack Tactics", "Bite Prone Rider"},
        "thug": {"Pack Tactics"},
        "hobgoblin": {"Martial Advantage"},
        "spy": {"Sneak Attack"},
        "bugbear": {"Brute", "Surprise Attack"},
        "dire_wolf": {"Keen Hearing and Smell", "Pack Tactics", "Bite Prone Rider"},
        "ghoul": {"Ghoul Claws Paralysis"},
        "gnoll": {"Rampage"},
        "bandit_captain": {"Parry"},
        "cult_fanatic": {"Dark Devotion"},
        "knight": {"Brave", "Parry"},
        "ogre_zombie": {"Undead Fortitude"},
    }
    expected_actions = {
        "scout": {"Scout Multiattack: Shortsword", "Scout Multiattack: Longbow"},
        "thug": {"Thug Multiattack"},
        "orc": {"Aggressive"},
        "gnoll": {"Bite"},
        "spy": {"Cunning Action: Dash", "Cunning Action: Disengage", "Cunning Action: Hide", "Spy Multiattack"},
        "berserker": {"Reckless"},
        "bandit_captain": {"Bandit Captain Multiattack: Melee", "Bandit Captain Multiattack: Ranged"},
        "cult_fanatic": {"Cult Fanatic Multiattack"},
        "priest": {"Divine Eminence"},
        "knight": {"Leadership", "Knight Multiattack"},
        "veteran": {"Veteran Multiattack: Melee", "Veteran Multiattack: Ranged"},
    }

    for monster_id, condition_names in expected_conditions.items():
        reset_srd_trait_state()
        monster = _materialize_srd_fixture(monster_id, position=(2, 2), faction="monsters")
        assert_conditions(monster, condition_names)

    for monster_id, action_names in expected_actions.items():
        reset_srd_trait_state()
        monster = _materialize_srd_fixture(monster_id, position=(2, 2), faction="monsters")
        assert action_names <= registered_action_names(monster)


def test_parry_does_not_spend_reaction_on_a_missed_attack() -> None:
    """Parry is a response to a hit, not a pre-roll AC modifier."""
    reset_srd_trait_state()
    defender = _materialize_srd_fixture(
        "bandit_captain",
        position=(2, 2),
        faction="monsters",
    )
    attacker = _materialize_srd_fixture(
        "commoner",
        position=(2, 3),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=30)

    with fixed_dice_faces(1):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=defender.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert isinstance(event, AttackEvent)
    assert event.attack_outcome is AttackOutcome.CRIT_MISS
    assert defender.action_economy.reactions.normalized_score == 1


def test_parry_spends_reaction_when_its_ac_bonus_blocks_a_hit() -> None:
    """A marginal melee hit is converted to a miss by the Parry reaction."""
    reset_srd_trait_state()
    defender = _materialize_srd_fixture(
        "bandit_captain",
        position=(2, 2),
        faction="monsters",
    )
    attacker = _materialize_srd_fixture(
        "commoner",
        position=(2, 3),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=30)
    attack_bonus = attacker.attack_bonus(
        WeaponSlot.MELEE_MAIN,
        defender.uuid,
    ).normalized_score
    armor_class = defender.ac_bonus(attacker.uuid).normalized_score
    marginal_face = armor_class - attack_bonus
    assert 2 <= marginal_face <= 19

    with fixed_dice_faces(marginal_face, 1):
        event = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=defender.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()

    assert isinstance(event, AttackEvent)
    assert event.attack_outcome is AttackOutcome.MISS
    assert defender.action_economy.reactions.normalized_score == 0


def test_gnoll_keeps_shield_and_gets_natural_bite_action() -> None:
    """Gnoll Bite should be a natural attack, not an off-hand weapon hack."""
    reset_srd_trait_state()
    gnoll = _materialize_srd_fixture("gnoll", position=(1, 1), faction="monsters")
    target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    offhand = gnoll.equipment._get_weapon_by_slot(WeaponSlot.MELEE_OFF)
    assert offhand is not None
    assert offhand.name == "Shield"
    assert "Bite" in registered_action_names(gnoll)

    bite = gnoll.get_action_template("Bite")
    assert bite is not None
    with fixed_dice_faces(15, 1):
        event = bite.instantiate(target_entity_uuid=target.uuid).apply()

    assert isinstance(event, AttackEvent)
    assert event.weapon_name == "Bite"
    assert event.damage_rolls is not None


def test_natural_bite_discloses_natural_attack_outcome_profile() -> None:
    """Natural attacks keep an outcome profile distinct from equipped weapons."""
    reset_srd_trait_state()
    gnoll = _materialize_srd_fixture("gnoll", position=(1, 1), faction="monsters")
    _target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    bite = gnoll.get_action_template("Bite")
    assert bite is not None
    profile = bite.get_outcome_profile(gnoll)

    assert profile is not None
    assert profile.effect_id == "natural_attack.bite"
    assert len(profile.damage_rolls) == 1
    assert profile.damage_rolls[0].dice_count == 1
    assert profile.damage_rolls[0].die_size == 4
    assert profile.damage_rolls[0].damage_type == DamageType.PIERCING.value
    assert gnoll.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN) is not None


def test_natural_bite_never_impersonates_the_equipped_weapon() -> None:
    """Natural attack handlers must always observe the real equipment state."""
    reset_srd_trait_state()
    gnoll = _materialize_srd_fixture(
        "gnoll",
        position=(1, 1),
        faction="monsters",
    )
    target = _materialize_srd_fixture(
        "commoner",
        position=(2, 1),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=30)
    equipped_weapon = gnoll.equipment.weapon_melee_main
    unarmed_facts = (
        gnoll.equipment.unarmed_damage_dice,
        gnoll.equipment.unarmed_dice_numbers,
        gnoll.equipment.unarmed_damage_type,
    )
    observed_states: list[tuple[object, tuple[object, ...]]] = []

    def observe_equipment(event: Event, _source_uuid):
        observed_states.append(
            (
                gnoll.equipment.weapon_melee_main,
                (
                    gnoll.equipment.unarmed_damage_dice,
                    gnoll.equipment.unarmed_dice_numbers,
                    gnoll.equipment.unarmed_damage_type,
                ),
            )
        )
        return event

    EventQueue.add_event_handler(
        EventHandler(
            name="Observe Natural Attack Equipment",
            source_entity_uuid=gnoll.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=gnoll.uuid,
                ),
            ],
            event_processor=observe_equipment,
        )
    )
    bite = gnoll.get_action_template("Bite")
    assert bite is not None
    with fixed_dice_faces(15, 1):
        result = bite.instantiate(target_entity_uuid=target.uuid).apply()

    assert isinstance(result, AttackEvent)
    assert observed_states
    assert all(
        weapon is equipped_weapon and facts == unarmed_facts
        for weapon, facts in observed_states
    )
    assert gnoll.equipment.weapon_melee_main is equipped_weapon


def test_pack_tactics_sunlight_and_keen_senses_use_contextual_values() -> None:
    """Contextual SRD advantage traits should participate in value evaluation."""
    reset_srd_trait_state()
    kobold = _materialize_srd_fixture("kobold", position=(1, 1), faction="monsters")
    ally = _materialize_srd_fixture("commoner", position=(2, 1), faction="monsters")
    target = _materialize_srd_fixture("commoner", position=(3, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    attack_bonus = kobold.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
    assert attack_bonus.advantage == AdvantageStatus.ADVANTAGE

    lonely_attack_bonus = ally.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
    lonely_attack_bonus.set_context({"sunlight": True})
    assert lonely_attack_bonus.advantage == AdvantageStatus.NONE

    kobold_sunlight_bonus = kobold.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
    kobold_sunlight_bonus.set_context({"sunlight": True})
    assert kobold_sunlight_bonus.advantage == AdvantageStatus.NONE

    wolf = _materialize_srd_fixture("wolf", position=(5, 5), faction="monsters")
    perception = wolf.skill_set.perception.skill_bonus.model_copy(deep=True)
    perception.set_context({"sense": "hearing"})
    assert perception.advantage == AdvantageStatus.ADVANTAGE


def test_uniform_multiattack_discloses_repeated_attack_profile() -> None:
    """Uniform Multiattack rows should advertise their repeated applications."""
    reset_srd_trait_state()
    scout = _materialize_srd_fixture("scout", position=(1, 1), faction="monsters")
    _target = _materialize_srd_fixture("commoner", position=(6, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=60)

    longbow = next(
        row
        for row in scout.get_available_actions().entity_actions
        if row.template_name == "Scout Multiattack: Longbow"
    )

    assert longbow.outcome_profile is not None
    assert longbow.outcome_profile.effect_id == "multiattack.scout_multiattack_longbow"
    assert longbow.outcome_profile.applications == 2
    assert longbow.outcome_profile.damage_rolls[0].die_size == 8
    assert longbow.outcome_profile.damage_rolls[0].damage_type == DamageType.PIERCING.value


def test_off_hand_multiattack_children_use_parent_cost_after_bonus_is_spent() -> None:
    """Stat-block off-hand attacks are not player two-weapon bonus actions."""
    for monster_id, action_name in (
        ("bandit_captain", "Bandit Captain Multiattack: Melee"),
        ("veteran", "Veteran Multiattack: Melee"),
    ):
        reset_srd_trait_state()
        actor = _materialize_srd_fixture(
            monster_id,
            position=(1, 1),
            faction="monsters",
        )
        target = _materialize_srd_fixture(
            "commoner",
            position=(2, 1),
            faction="heroes",
        )
        Entity.update_all_entities_senses(max_distance=30)
        actor.action_economy.consume(
            "bonus_actions",
            1,
            "Pre-spent bonus action",
        )
        bonus_actions_before = (
            actor.action_economy.bonus_actions.normalized_score
        )

        multiattack = actor.get_action_template(action_name)
        assert multiattack is not None
        with fixed_dice_faces(1, 1, 1):
            result = multiattack.instantiate(
                target_entity_uuid=target.uuid,
            ).apply()

        assert result is not None and not result.canceled
        completed_attacks = [
            event
            for event in EventQueue.get_events_by_type(EventType.ATTACK)
            if event.phase == EventPhase.COMPLETION
        ]
        assert len(completed_attacks) == 3
        assert [
            event.weapon_slot
            for event in completed_attacks
            if isinstance(event, AttackEvent)
        ] == [
            WeaponSlot.MELEE_MAIN,
            WeaponSlot.MELEE_MAIN,
            WeaponSlot.MELEE_OFF,
        ]
        assert (
            actor.action_economy.bonus_actions.normalized_score
            == bonus_actions_before
            == 0
        )


def test_actor_known_bonus_damage_reaches_attack_outcome_profiles() -> None:
    """Always-on or active actor-owned bonus dice should be visible to policy."""
    reset_srd_trait_state()
    bugbear = _materialize_srd_fixture("bugbear", position=(1, 1), faction="monsters")
    _target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    bugbear_attack = next(
        row
        for row in bugbear.get_available_actions().entity_actions
        if row.weapon_name == "Morningstar"
    )

    assert bugbear_attack.outcome_profile is not None
    assert [roll.die_size for roll in bugbear_attack.outcome_profile.damage_rolls].count(8) == 2
    assert bugbear_attack.outcome_profile.damage_rolls[-1].flat_bonus == 0
    assert bugbear_attack.outcome_profile.damage_rolls[-1].damage_type == DamageType.PIERCING.value

    reset_srd_trait_state()
    priest = _materialize_srd_fixture("priest", position=(1, 1), faction="monsters")
    _foe = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)
    divine = priest.get_action_template("Divine Eminence")
    assert divine is not None

    divine.instantiate().apply()
    priest_attack = next(
        row
        for row in priest.get_available_actions().entity_actions
        if row.weapon_name == "Mace"
    )

    assert priest_attack.outcome_profile is not None
    assert any(
        roll.dice_count == 3
        and roll.die_size == 6
        and roll.damage_type == DamageType.RADIANT.value
        for roll in priest_attack.outcome_profile.damage_rolls
    )


def test_undead_fortitude_survives_non_radiant_lethal_damage_only() -> None:
    """Undead Fortitude should cap qualifying lethal damage at 1 HP."""
    reset_srd_trait_state()
    zombie = _materialize_srd_fixture("zombie", position=(1, 1), faction="monsters")
    zombie._set_normal_hp(1)

    with fixed_dice_faces(20):
        dealt = zombie.receive_damage(1, DamageType.BLUDGEONING, source_entity_uuid=zombie.uuid)

    assert dealt == 0
    assert zombie.get_hp() == 1

    reset_srd_trait_state()
    radiant_zombie = _materialize_srd_fixture("zombie", position=(1, 1), faction="monsters")
    radiant_zombie._set_normal_hp(1)

    radiant_zombie.receive_damage(1, DamageType.RADIANT, source_entity_uuid=radiant_zombie.uuid)

    assert radiant_zombie.get_hp() <= 0


def test_wolf_bite_and_ghoul_claws_apply_failed_save_riders() -> None:
    """Named hit riders should fire through attack events and saving throws."""
    reset_srd_trait_state()
    wolf = _materialize_srd_fixture("wolf", position=(1, 1), faction="monsters")
    target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    wolf_bite = next(row for row in wolf.get_available_actions().entity_actions if row.weapon_name == "Bite")
    assert wolf_bite.target_effect_profile is not None
    assert wolf_bite.target_effect_profile.semantic_id == "attack.hit_rider.prone"
    assert wolf_bite.target_effect_profile.branches[0].save_dc == 11
    assert wolf_bite.target_effect_profile.branches[0].condition_semantic_keys == frozenset({"dnd.conditions.Prone"})

    with fixed_dice_faces(15, 1, 1, 1):
        Attack(source_entity_uuid=wolf.uuid, target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.MELEE_MAIN).apply()

    assert "Prone" in target.active_conditions

    reset_srd_trait_state()
    ghoul = _materialize_srd_fixture("ghoul", position=(1, 1), faction="monsters")
    victim = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    claws = next(row for row in ghoul.get_available_actions().entity_actions if row.weapon_name == "Claws")
    assert claws.target_effect_profile is not None
    assert claws.target_effect_profile.semantic_id == "attack.hit_rider.ghoul_paralysis"
    assert claws.target_effect_profile.branches[0].excluded_creature_types == frozenset({"undead"})
    assert claws.target_effect_profile.branches[0].condition_semantic_keys == frozenset({
        "dnd.monsters.traits.GhoulParalysisEffect",
        "dnd.conditions.Paralyzed",
    })

    with fixed_dice_faces(15, 1, 1, 1):
        Attack(source_entity_uuid=ghoul.uuid, target_entity_uuid=victim.uuid, weapon_slot=WeaponSlot.MELEE_MAIN).apply()

    assert "Ghoul Paralysis" in victim.active_conditions
    assert "Paralyzed" in victim.active_conditions


def test_large_srd_monster_size_damage_has_explicit_bonus() -> None:
    """Large SRD attackers should roll size damage without nullable bonuses."""
    reset_srd_trait_state()
    ogre_zombie = _materialize_srd_fixture("ogre_zombie", position=(1, 1), faction="monsters")
    target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)

    with fixed_dice_faces(15, 1, 1, 1):
        event = Attack(source_entity_uuid=ogre_zombie.uuid, target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.MELEE_MAIN).apply()

    assert event is not None
    assert event.damage_rolls is not None
    assert len(event.damage_rolls) == 2
    assert all(damage.damage_bonus is not None for damage in event.damages or [])


def test_brute_surprise_attack_and_martial_advantage_add_damage_dice() -> None:
    """Bonus-damage traits should inject extra damage rolls only when eligible."""
    reset_srd_trait_state()
    bugbear = _materialize_srd_fixture("bugbear", position=(1, 1), faction="monsters")
    target = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)
    target.senses.entities.pop(bugbear.uuid, None)

    with fixed_dice_faces(15, 1, 1, 1, 1):
        event = Attack(source_entity_uuid=bugbear.uuid, target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.MELEE_MAIN).apply()

    assert event is not None
    assert event.damage_rolls is not None
    assert len(event.damage_rolls) == 3
    assert all(damage.damage_bonus is not None for damage in event.damages or [])
    bugbear_damage = latest_damage_roll_result()
    assert len(bugbear_damage.damage_packets) == 3
    assert all(
        modification.operation is RollModificationOperation.APPEND
        for modification in bugbear_damage.roll_modifications
    )

    reset_srd_trait_state()
    hobgoblin = _materialize_srd_fixture("hobgoblin", position=(1, 1), faction="monsters")
    ally = _materialize_srd_fixture("commoner", position=(2, 2), faction="monsters")
    foe = _materialize_srd_fixture("commoner", position=(2, 1), faction="heroes")
    Entity.update_all_entities_senses(max_distance=30)
    assert ally.get_hp() > 0

    with fixed_dice_faces(15, 1, 1, 1):
        event = Attack(source_entity_uuid=hobgoblin.uuid, target_entity_uuid=foe.uuid, weapon_slot=WeaponSlot.MELEE_MAIN).apply()

    assert event is not None
    assert event.damage_rolls is not None
    assert len(event.damage_rolls) == 2
    assert all(damage.damage_bonus is not None for damage in event.damages or [])
    hobgoblin_damage = latest_damage_roll_result()
    assert len(hobgoblin_damage.damage_packets) == 2
    assert hobgoblin_damage.roll_modifications[-1].operation is (
        RollModificationOperation.APPEND
    )


def test_active_monster_actions_apply_their_marker_conditions() -> None:
    """Resource/actions traits should execute through normal action templates."""
    reset_srd_trait_state()
    priest = _materialize_srd_fixture("priest", position=(1, 1), faction="monsters")
    action = priest.get_action_template("Divine Eminence")
    assert action is not None
    setup = action.get_self_setup_profile(priest)
    assert setup is not None
    assert setup.semantic_id == "setup.divine_eminence"
    assert setup.increases_weapon_damage is True
    slot_level = priest.get_lowest_spell_slot(1)
    assert slot_level is not None
    slot_value = getattr(priest.action_economy, f"spell_slot_{slot_level}")
    slots_before = slot_value.normalized_score
    bonus_actions_before = priest.action_economy.bonus_actions.normalized_score

    event = action.instantiate().apply()

    assert isinstance(event, ActionEvent)
    assert [
        (cost.cost_type, cost.cost)
        for cost in event.costs
    ] == [
        ("bonus_actions", 1),
        (f"spell_slot_{slot_level}", 1),
    ]
    assert slot_value.normalized_score == slots_before - 1
    assert (
        priest.action_economy.bonus_actions.normalized_score
        == bonus_actions_before - 1
    )
    assert "Divine Eminence Active" in priest.active_conditions

    reset_srd_trait_state()
    knight = _materialize_srd_fixture("knight", position=(1, 1), faction="monsters")
    ally = _materialize_srd_fixture(
        "commoner",
        position=(2, 1),
        faction="monsters",
    )
    leadership = knight.get_action_template("Leadership")
    assert leadership is not None
    setup = leadership.get_self_setup_profile(knight)
    assert setup is not None
    assert setup.semantic_id == "support.leadership"
    assert setup.maximum_duration_rounds == 10

    event = leadership.instantiate().apply()

    assert event is not None
    assert "Leadership Used" in knight.active_conditions
    leadership_fields = [
        effect
        for effect in SpatialEffect.active_effects()
        if effect.anchor_uuid == knight.uuid
        and any(
            isinstance(condition, LeadershipAura)
            for condition in effect.active_conditions.values()
        )
    ]
    assert len(leadership_fields) == 1
    assert isinstance(leadership_fields[0], FieldEffect)
    assert isinstance(
        ally.active_conditions.get("Leadership"),
        LeadershipMembership,
    )
    assert "Leadership" not in knight.active_conditions

    knight.add_condition(
        Incapacitated(
            source_entity_uuid=ally.uuid,
            target_entity_uuid=knight.uuid,
        ),
    )
    assert SpatialEffect.get_effect(leadership_fields[0].uuid) is None
    assert "Leadership" not in ally.active_conditions
    assert "Leadership Used" in knight.active_conditions


def test_overlapping_leadership_fields_keep_one_source_and_promote_fallback() -> None:
    """Overlapping auras grant once and preserve the remaining source."""
    reset_srd_trait_state()
    first_leader = _materialize_srd_fixture(
        "knight",
        position=(1, 1),
        faction="monsters",
    )
    second_leader = _materialize_srd_fixture(
        "knight",
        position=(10, 1),
        faction="monsters",
    )
    ally = _materialize_srd_fixture(
        "commoner",
        position=(5, 1),
        faction="monsters",
    )
    enemy = _materialize_srd_fixture(
        "commoner",
        position=(5, 2),
        faction="heroes",
    )
    Entity.update_all_entities_senses(max_distance=60)

    for leader in (first_leader, second_leader):
        action = leader.get_action_template("Leadership")
        assert action is not None
        result = action.instantiate().apply()
        assert result is not None
        assert not result.canceled

    memberships = ally.get_condition_application_leases("Leadership")
    assert len(memberships) == 2
    assert all(
        isinstance(condition, LeadershipMembership)
        for condition in memberships
    )
    active = ally.active_conditions["Leadership"]
    assert active.source_entity_uuid == first_leader.uuid
    assert sum(condition.applied for condition in memberships) == 1

    with fixed_dice_faces(1, 1):
        Attack(
            source_entity_uuid=ally.uuid,
            target_entity_uuid=enemy.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    roll_event = next(
        event
        for event in reversed(
            EventQueue.get_events_by_type(
                EventType.ATTACK_D20_ROLL_RESULT,
            ),
        )
        if isinstance(event, D20RollResultEvent)
        and event.phase is EventPhase.COMPLETION
    )
    assert [
        modification.handler_name
        for modification in roll_event.roll_modifications
    ].count("Leadership") == 1

    Entity.update_entity_position(first_leader, (0, 11))

    remaining_memberships = ally.get_condition_application_leases(
        "Leadership",
    )
    assert len(remaining_memberships) == 1
    promoted = ally.active_conditions["Leadership"]
    assert promoted is remaining_memberships[0]
    assert promoted.applied
    assert promoted.source_entity_uuid == second_leader.uuid
    promotion_event = next(
        event
        for event in reversed(
            EventQueue.get_events_by_type(EventType.CONDITION_APPLICATION),
        )
        if isinstance(event, ConditionApplicationEvent)
        and event.phase is EventPhase.COMPLETION
        and event.condition.uuid == promoted.uuid
        and event.application_disposition
        is ConditionApplicationDisposition.PROMOTED
    )
    promotion_log = promotion_event.generate_combat_log()
    assert promotion_log is not None
    assert "another source" in promotion_log.compact

    second_field = next(
        effect
        for effect in SpatialEffect.active_effects()
        if effect.anchor_uuid == second_leader.uuid
    )
    for _ in range(9):
        assert not second_field.advance_duration("Leadership Aura")
    assert second_field.advance_duration("Leadership Aura")
    assert SpatialEffect.get_effect(second_field.uuid) is None
    assert "Leadership" not in ally.active_conditions
    assert ally.get_condition_application_leases("Leadership") == ()
