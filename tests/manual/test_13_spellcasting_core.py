"""Manual Chapter 13 checks for spellcasting core."""

from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import (
    execute_by_index,
    get_available_actions,
    register_spell,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_actions import ActionCategory, AvailableActionInfo
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_object import BaseObject
from dnd.core.combat_log import CombatLogEntryType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.spells import FireBolt, Haste, MagicMissile


def reset_spell_tutorial_state(width: int = 10, height: int = 6) -> None:
    """Clear global state and create a small spell tutorial arena."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)


def create_spell_actor(
    name: str,
    position: tuple[int, int],
    faction: str,
    spell_slots: dict[int, int] | None = None,
    intelligence: int = 18,
    proficiency_bonus: int = 3,
    spellcasting: SpellcastingConfig | None = None,
) -> Entity:
    """Create an actor with spellcasting stats, HP, and optional spell slots."""
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=10),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=intelligence),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(spell_slots=spell_slots or {}),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=8,
                        hit_dice_count=3,
                        mode="maximums",
                    )
                ],
            ),
            proficiency_bonus=proficiency_bonus,
            spellcasting=spellcasting
            or SpellcastingConfig(spellcasting_ability="intelligence"),
            position=position,
            faction=faction,
        ),
    )


def find_action(actions, template_name: str) -> AvailableActionInfo:
    """Return the discovered action row with the requested template name."""
    for action_info in actions.all_actions:
        if action_info.template_name == template_name:
            return action_info
    raise AssertionError(f"{template_name} was not discovered")


def test_first_spell_example_prints_visible_discovery_and_cast(capsys) -> None:
    """The opening spellcasting example prints the full discovered-cast readout."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Pyromancer",
        (0, 0),
        "heroes",
        spell_slots={1: 1},
    )
    target = create_spell_actor("Training Target", (1, 0), "monsters")

    register_spell(caster, FireBolt, caster_level=5)
    register_spell(caster, MagicMissile, caster_level=5)
    Entity.update_all_entities_senses(max_distance=30)

    available = get_available_actions(caster)
    fire_bolt = find_action(available, "Fire Bolt")
    missile = find_action(available, "Magic Missile__slot_1")
    fire_target = fire_bolt.valid_targets[0]
    fire_target_entity = Entity.get(fire_target.target_uuid)
    assert fire_target_entity is not None

    target_hp_before = target.get_hp()
    actions_before = caster.action_economy.actions.normalized_score
    slot_before = caster.action_economy.spell_slot_1.normalized_score

    with fixed_dice_faces(12, 5, 6):
        event = execute_by_index(
            caster,
            fire_bolt.template_name,
            fire_target.index,
            available=available,
        )

    assert isinstance(event, SpellEvent)
    assert event.dice_roll is not None
    assert event.damage_rolls is not None
    assert event.combat_log is not None
    damage_roll = event.damage_rolls[0]

    readout_lines = [
        f"caster: {caster.name}",
        f"spell attack bonus: {caster.spell_attack_bonus().normalized_score}",
        f"spell save dc: {caster.spell_save_dc()}",
        f"discovered spells: {fire_bolt.display_name}, {missile.display_name}",
        (
            "fire bolt row: "
            f"level={fire_bolt.spell_level}, "
            f"cost={fire_bolt.cost_amount} {fire_bolt.cost_type}, "
            f"targets={len(fire_bolt.valid_targets)}"
        ),
        (
            "magic missile row: "
            f"cast_at={missile.cast_at_level}, "
            f"projectiles={missile.num_projectiles}, "
            f"slot before={slot_before}"
        ),
        (
            f"selected target: {fire_target_entity.name}, "
            f"distance={fire_target.distance}"
        ),
        (
            f"event: {event.spell_id}, "
            f"phase={event.phase.value}, "
            f"outcome={event.attack_outcome.value}"
        ),
        f"attack roll: {event.dice_roll.results} + 7 = {event.dice_roll.total}",
        f"damage roll: {damage_roll.results} = {damage_roll.total}",
        f"target hp: {target_hp_before} -> {target.get_hp()}",
        (
            "actions: "
            f"{actions_before} -> "
            f"{caster.action_economy.actions.normalized_score}"
        ),
        (
            "level 1 slots: "
            f"{slot_before} -> "
            f"{caster.action_economy.spell_slot_1.normalized_score}"
        ),
        f"combat log type: {event.combat_log.entry_type.value}",
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "caster: Pyromancer",
        "spell attack bonus: 7",
        "spell save dc: 15",
        "discovered spells: Fire Bolt, Magic Missile (Level 1)",
        "fire bolt row: level=0, cost=1 actions, targets=1",
        "magic missile row: cast_at=1, projectiles=3, slot before=1",
        "selected target: Training Target, distance=5",
        "event: fire_bolt, phase=completion, outcome=Hit",
        "attack roll: [12] + 7 = 19",
        "damage roll: [5, 6] = 11",
        "target hp: 27 -> 16",
        "actions: 1 -> 0",
        "level 1 slots: 1 -> 1",
        "combat log type: attack",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_spell_slots_are_action_economy_values_and_reset_separately(capsys) -> None:
    """Spell slots are spendable action-economy values, not spellcasting fields."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Slot Mage",
        (0, 0),
        "heroes",
        spell_slots={1: 2, 2: 1},
    )

    assert caster.action_economy.spell_slot_1.normalized_score == 2
    assert caster.action_economy.spell_slot_2.normalized_score == 1
    assert caster.has_spell_slot(1)
    assert caster.has_spell_slot(2)
    assert not caster.has_spell_slot(3)
    assert caster.get_lowest_spell_slot(1) == 1
    assert caster.get_lowest_spell_slot(3) is None
    assert not hasattr(caster.spellcasting, "spell_slot_1")
    initial_state = (
        caster.action_economy.spell_slot_1.normalized_score,
        caster.action_economy.spell_slot_2.normalized_score,
        caster.has_spell_slot(1),
        caster.has_spell_slot(2),
        caster.has_spell_slot(3),
        caster.get_lowest_spell_slot(1),
        caster.get_lowest_spell_slot(3),
        hasattr(caster.spellcasting, "spell_slot_1"),
    )

    caster.action_economy.consume("spell_slot_1", 1)

    assert caster.action_economy.spell_slot_1.normalized_score == 1
    after_consume = caster.action_economy.spell_slot_1.normalized_score

    caster.action_economy.reset_all_costs()

    assert caster.action_economy.spell_slot_1.normalized_score == 1
    after_turn_reset = caster.action_economy.spell_slot_1.normalized_score

    caster.action_economy.reset_spell_slot_costs()

    assert caster.action_economy.spell_slot_1.normalized_score == 2
    after_slot_reset = caster.action_economy.spell_slot_1.normalized_score

    slot_lines = [
        f"initial slots: level1={initial_state[0]}, level2={initial_state[1]}",
        (
            "has slots: "
            f"l1={initial_state[2]}, "
            f"l2={initial_state[3]}, "
            f"l3={initial_state[4]}"
        ),
        f"lowest slots: from1={initial_state[5]}, from3={initial_state[6]}",
        f"slots live on spellcasting block: {initial_state[7]}",
        f"level1 after consume: {after_consume}",
        f"level1 after turn reset: {after_turn_reset}",
        f"level1 after slot reset: {after_slot_reset}",
    ]

    print("\n".join(slot_lines))

    expected_slot_lines = [
        "initial slots: level1=2, level2=1",
        "has slots: l1=True, l2=True, l3=False",
        "lowest slots: from1=1, from3=None",
        "slots live on spellcasting block: False",
        "level1 after consume: 1",
        "level1 after turn reset: 1",
        "level1 after slot reset: 2",
    ]
    assert slot_lines == expected_slot_lines
    assert capsys.readouterr().out.splitlines() == expected_slot_lines


def test_spell_numbers_compose_from_ability_proficiency_and_modifiers(capsys) -> None:
    """Entity spell helpers combine ability, proficiency, and spell modifiers."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Focused Mage",
        (0, 0),
        "heroes",
        spellcasting=SpellcastingConfig(
            spellcasting_ability="intelligence",
            spell_attack_modifiers=[("Wand", 2)],
            spell_damage_modifiers=[("Elemental Affinity", 3)],
            spell_dc_modifiers=[("Arcane Focus", 1)],
            spell_crit_threshold_modifiers=[("Spell Sniper", 1)],
            spell_crit_extra_dice_modifiers=[("Arcane Surge", 2)],
        ),
    )

    assert caster.spell_attack_bonus().normalized_score == 9
    assert caster.spell_save_dc() == 16
    assert caster.get_spell_damage_bonus().normalized_score == 3
    assert caster.get_spell_crit_threshold() == 19
    assert caster.get_spell_crit_extra_dice() == 2
    number_lines = [
        f"spell ability: {caster.spellcasting.spellcasting_ability}",
        f"spell attack bonus: {caster.spell_attack_bonus().normalized_score}",
        f"spell save dc: {caster.spell_save_dc()}",
        f"spell damage bonus: {caster.get_spell_damage_bonus().normalized_score}",
        f"spell crit threshold: {caster.get_spell_crit_threshold()}",
        f"spell crit extra dice: {caster.get_spell_crit_extra_dice()}",
    ]

    print("\n".join(number_lines))

    expected_number_lines = [
        "spell ability: intelligence",
        "spell attack bonus: 9",
        "spell save dc: 16",
        "spell damage bonus: 3",
        "spell crit threshold: 19",
        "spell crit extra dice: 2",
    ]
    assert number_lines == expected_number_lines
    assert capsys.readouterr().out.splitlines() == expected_number_lines


def test_registered_spells_surface_cantrips_and_slot_variants(capsys) -> None:
    """Registered spell templates generate the rows a controller can select."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Menu Mage",
        (0, 0),
        "heroes",
        spell_slots={1: 1, 2: 1, 3: 1},
    )
    enemy = create_spell_actor("Training Target", (1, 0), "monsters")
    ally = create_spell_actor("Haste Ally", (0, 1), "heroes")
    register_spell(caster, FireBolt, caster_level=5)
    register_spell(caster, MagicMissile, caster_level=5)
    register_spell(caster, Haste, caster_level=5)
    Entity.update_all_entities_senses(max_distance=30)

    available = get_available_actions(caster)
    fire_bolt = find_action(available, "Fire Bolt")
    missile_1 = find_action(available, "Magic Missile__slot_1")
    missile_2 = find_action(available, "Magic Missile__slot_2")
    missile_3 = find_action(available, "Magic Missile__slot_3")
    haste = find_action(available, "Haste__slot_3")

    assert fire_bolt.action_category == ActionCategory.SPELL
    assert fire_bolt.spell_level == 0
    assert fire_bolt.cast_at_level == 0
    assert not fire_bolt.is_spell_variant
    assert [target.target_uuid for target in fire_bolt.valid_targets] == [
        enemy.uuid
    ]

    assert missile_1.base_template_name == "Magic Missile"
    assert missile_1.display_name == "Magic Missile (Level 1)"
    assert missile_1.cast_at_level == 1
    assert missile_1.num_projectiles == 3
    assert missile_1.allow_same_target is True
    assert missile_2.cast_at_level == 2
    assert missile_2.num_projectiles == 4
    assert missile_3.cast_at_level == 3
    assert missile_3.num_projectiles == 5

    assert haste.base_template_name == "Haste"
    assert haste.cast_at_level == 3
    assert {target.target_uuid for target in haste.valid_targets} == {
        enemy.uuid,
        ally.uuid,
    }
    fire_target_names = [
        Entity.get(target.target_uuid).name for target in fire_bolt.valid_targets
    ]
    haste_target_names = sorted(
        Entity.get(target.target_uuid).name for target in haste.valid_targets
    )
    discovery_lines = [
        (
            "fire bolt row: "
            f"category={fire_bolt.action_category.value}, "
            f"level={fire_bolt.spell_level}, "
            f"cast_at={fire_bolt.cast_at_level}, "
            f"variant={fire_bolt.is_spell_variant}, "
            f"targets={fire_target_names}"
        ),
        (
            "magic missile level 1: "
            f"base={missile_1.base_template_name}, "
            f"display={missile_1.display_name}, "
            f"cast_at={missile_1.cast_at_level}, "
            f"projectiles={missile_1.num_projectiles}, "
            f"same_target={missile_1.allow_same_target}"
        ),
        (
            "magic missile scaling: "
            f"level2={missile_2.num_projectiles}, "
            f"level3={missile_3.num_projectiles}"
        ),
        (
            "haste row: "
            f"base={haste.base_template_name}, "
            f"cast_at={haste.cast_at_level}, "
            f"targets={haste_target_names}"
        ),
    ]

    print("\n".join(discovery_lines))

    expected_discovery_lines = [
        "fire bolt row: category=spell, level=0, cast_at=0, variant=False, targets=['Training Target']",
        "magic missile level 1: base=Magic Missile, display=Magic Missile (Level 1), cast_at=1, projectiles=3, same_target=True",
        "magic missile scaling: level2=4, level3=5",
        "haste row: base=Haste, cast_at=3, targets=['Haste Ally', 'Training Target']",
    ]
    assert discovery_lines == expected_discovery_lines
    assert capsys.readouterr().out.splitlines() == expected_discovery_lines


def test_fire_bolt_uses_spell_attack_bonus_scaling_and_damage(capsys) -> None:
    """A cantrip spell attack rolls d20, scales damage dice, and costs an action."""
    reset_spell_tutorial_state()
    caster = create_spell_actor("Pyromancer", (0, 0), "heroes")
    enemy = create_spell_actor("Training Target", (1, 0), "monsters")
    Entity.update_all_entities_senses(max_distance=30)
    hp_before = enemy.get_hp()

    with fixed_dice_faces(12, 5, 6):
        event = FireBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=enemy.uuid,
            caster_level=5,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.attack_outcome == AttackOutcome.HIT
    assert event.dice_roll is not None
    assert event.dice_roll.results == [12]
    assert event.dice_roll.total == 19
    assert event.damage_rolls is not None
    assert event.damage_rolls[0].results == [5, 6]
    assert event.damage_rolls[0].total == 11
    assert enemy.get_hp() == hp_before - 11
    assert caster.action_economy.actions.normalized_score == 0
    assert event.combat_log is not None
    assert event.combat_log.entry_type == CombatLogEntryType.ATTACK
    assert event.combat_log.data["outcome"] == "hit"
    fire_lines = [
        (
            "event phase: "
            f"{event.phase.value}, canceled={event.canceled}, "
            f"outcome={event.attack_outcome.value}"
        ),
        f"attack roll: {event.dice_roll.results} -> {event.dice_roll.total}",
        f"damage roll: {event.damage_rolls[0].results} -> {event.damage_rolls[0].total}",
        f"target hp: {hp_before}->{enemy.get_hp()}",
        f"actions after cast: {caster.action_economy.actions.normalized_score}",
        (
            "combat log: "
            f"{event.combat_log.entry_type.value}, "
            f"outcome={event.combat_log.data['outcome']}"
        ),
    ]

    print("\n".join(fire_lines))

    expected_fire_lines = [
        "event phase: completion, canceled=False, outcome=Hit",
        "attack roll: [12] -> 19",
        "damage roll: [5, 6] -> 11",
        "target hp: 27->16",
        "actions after cast: 0",
        "combat log: attack, outcome=hit",
    ]
    assert fire_lines == expected_fire_lines
    assert capsys.readouterr().out.splitlines() == expected_fire_lines


def test_magic_missile_auto_hits_multiple_darts_and_spends_slot(capsys) -> None:
    """A leveled multi-target spell creates dart children and consumes its slot."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Missile Mage",
        (0, 0),
        "heroes",
        spell_slots={1: 1},
    )
    enemy = create_spell_actor("Training Target", (1, 0), "monsters")
    Entity.update_all_entities_senses(max_distance=30)
    hp_before = enemy.get_hp()

    with fixed_dice_faces(2, 3, 4):
        event = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=enemy.uuid,
        ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.total_targets == 3
    assert event.total_damage == 12
    assert enemy.get_hp() == hp_before - 12
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0
    assert event.combat_log is not None
    assert event.combat_log.entry_type == CombatLogEntryType.MULTI_ENTITY_ACTION
    assert len(event.combat_log.sub_entries) == 3
    missile_lines = [
        f"event phase: {event.phase.value}, canceled={event.canceled}",
        f"targets/projectiles: {event.total_targets}, damage={event.total_damage}",
        f"target hp: {hp_before}->{enemy.get_hp()}",
        f"actions after cast: {caster.action_economy.actions.normalized_score}",
        (
            "level 1 slots after cast: "
            f"{caster.action_economy.spell_slot_1.normalized_score}"
        ),
        (
            "combat log: "
            f"{event.combat_log.entry_type.value}, "
            f"sub_entries={len(event.combat_log.sub_entries)}"
        ),
    ]

    print("\n".join(missile_lines))

    expected_missile_lines = [
        "event phase: completion, canceled=False",
        "targets/projectiles: 3, damage=12",
        "target hp: 27->15",
        "actions after cast: 0",
        "level 1 slots after cast: 0",
        "combat log: multi_entity_action, sub_entries=3",
    ]
    assert missile_lines == expected_missile_lines
    assert capsys.readouterr().out.splitlines() == expected_missile_lines


def test_haste_links_spell_effect_to_concentration_and_cleans_up(capsys) -> None:
    """A concentration spell links target effects to the caster's condition."""
    reset_spell_tutorial_state()
    caster = create_spell_actor(
        "Time Mage",
        (0, 0),
        "heroes",
        spell_slots={3: 1},
    )
    ally = create_spell_actor("Haste Ally", (1, 0), "heroes")
    Entity.update_all_entities_senses(max_distance=30)
    movement_before = ally.action_economy.movement.normalized_score
    actions_before = ally.action_economy.actions.normalized_score
    ac_before = ally.ac_bonus().normalized_score

    event = Haste(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    ).apply()

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert "Concentrating" in caster.active_conditions
    assert "Haste" in ally.active_conditions
    assert ally.action_economy.movement.normalized_score == movement_before * 2
    assert ally.action_economy.actions.normalized_score == actions_before + 1
    assert ally.ac_bonus().normalized_score == ac_before + 2
    assert caster.action_economy.spell_slot_3.normalized_score == 0

    concentrating = caster.active_conditions["Concentrating"]
    assert concentrating.linked_conditions == [
        (ally.uuid, ally.active_conditions["Haste"].uuid)
    ]
    after_apply = (
        event.phase.value,
        event.canceled,
        "Concentrating" in caster.active_conditions,
        "Haste" in ally.active_conditions,
        ally.action_economy.movement.normalized_score,
        ally.action_economy.actions.normalized_score,
        ally.ac_bonus().normalized_score,
        caster.action_economy.spell_slot_3.normalized_score,
        concentrating.linked_conditions
        == [(ally.uuid, ally.active_conditions["Haste"].uuid)],
    )

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert "Haste" not in ally.active_conditions
    assert "Incapacitated" in ally.active_conditions
    assert ally.ac_bonus().normalized_score == ac_before
    after_cleanup = (
        "Concentrating" in caster.active_conditions,
        "Haste" in ally.active_conditions,
        "Incapacitated" in ally.active_conditions,
        ally.ac_bonus().normalized_score,
    )

    haste_lines = [
        f"event phase: {after_apply[0]}, canceled={after_apply[1]}",
        (
            "conditions after cast: "
            f"caster_concentrating={after_apply[2]}, "
            f"ally_haste={after_apply[3]}"
        ),
        (
            "ally movement/actions/ac: "
            f"{movement_before}->{after_apply[4]}, "
            f"{actions_before}->{after_apply[5]}, "
            f"{ac_before}->{after_apply[6]}"
        ),
        f"level 3 slots after cast: {after_apply[7]}",
        f"concentration linked to haste: {after_apply[8]}",
        (
            "after concentration cleanup: "
            f"caster_concentrating={after_cleanup[0]}, "
            f"ally_haste={after_cleanup[1]}, "
            f"ally_incapacitated={after_cleanup[2]}, "
            f"ally_ac={after_cleanup[3]}"
        ),
    ]

    print("\n".join(haste_lines))

    expected_haste_lines = [
        "event phase: completion, canceled=False",
        "conditions after cast: caster_concentrating=True, ally_haste=True",
        "ally movement/actions/ac: 30->60, 1->2, 10->12",
        "level 3 slots after cast: 0",
        "concentration linked to haste: True",
        "after concentration cleanup: caster_concentrating=False, ally_haste=False, ally_incapacitated=True, ally_ac=10",
    ]
    assert haste_lines == expected_haste_lines
    assert capsys.readouterr().out.splitlines() == expected_haste_lines
