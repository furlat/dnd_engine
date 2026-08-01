"""Tutorial tests for entity anatomy and actor-owned blocks."""

from uuid import uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig, RechargeType
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig
from dnd.blocks.skills import SkillConfig, SkillSetConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.base_object import BaseObject
from dnd.core.base_block import BaseBlock
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.values import BaseValue, ModifiableValue
from dnd.entity import Entity, EntityConfig


def reset_entity_anatomy_state() -> None:
    """Clear the global indexes touched by these actor-composition examples."""
    EventQueue.reset()
    GridMap.reset()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def create_tutorial_hero() -> Entity:
    """Create the complete Aria actor used by the anatomy examples."""
    hero_id = uuid4()

    return Entity.create(
        source_entity_uuid=hero_id,
        name="Aria",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=16),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=14),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=8),
            ),
            skill_set=SkillSetConfig(
                athletics=SkillConfig(proficiency=True),
                stealth=SkillConfig(proficiency=True, expertise=True),
                perception=SkillConfig(proficiency=True),
            ),
            saving_throws=SavingThrowSetConfig(
                dexterity_saving_throw=SavingThrowConfig(proficiency=True),
                constitution_saving_throw=SavingThrowConfig(proficiency=True),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=2,
                        mode="maximums",
                    )
                ],
            ),
            action_economy=ActionEconomyConfig(
                actions=1,
                bonus_actions=1,
                reactions=1,
                movement=30,
                spell_slots={1: 2},
            ),
            spellcasting=SpellcastingConfig(
                spellcasting_ability="wisdom",
                spell_attack_modifiers=[("Focus", 1)],
                spell_dc_modifiers=[("Moon Circlet", 2)],
            ),
            appearance=AppearanceConfig(
                body_category="NakedBody2",
                skin_tint=0x8A5A44,
                head_category="Head9",
                hair_tint=0x221811,
            ),
            proficiency_bonus=2,
            position=(1, 2),
            faction="heroes",
            weight=180,
        ),
    )


def test_first_actor_example_prints_runtime_shape(capsys) -> None:
    """The first actor example prints the runtime shape it creates."""
    reset_entity_anatomy_state()

    hero_id = uuid4()
    hero = Entity.create(
        source_entity_uuid=hero_id,
        name="Aria",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=16),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=14),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=2,
                        mode="maximums",
                    )
                ],
            ),
            position=(1, 2),
            faction="heroes",
            weight=180,
        ),
    )

    readout_lines = [
        f"created actor: {hero.name}",
        f"uuid matches source: {'yes' if hero.uuid == hero.source_entity_uuid else 'no'}",
        f"position: {hero.position}",
        f"hit points: {hero.get_hp()}",
        f"map lookup: {get_map().get_entity_position(hero.uuid)}",
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "created actor: Aria",
        "uuid matches source: yes",
        "position: (1, 2)",
        "hit points: 24",
        "map lookup: (1, 2)",
    ]
    assert readout_lines == expected_lines
    assert Entity.get(hero.uuid) is hero
    assert BaseBlock.get(hero.uuid) is hero
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_entity_config_prints_actor_shell_and_block_ownership(capsys) -> None:
    """Entity.create prints actor shell metadata and owned block shape."""
    reset_entity_anatomy_state()

    hero = create_tutorial_hero()

    actor_lines = [
        f"actor shell: name={hero.name}, faction={hero.faction}, weight={hero.weight}",
        f"identity: uuid_matches_source={hero.uuid == hero.source_entity_uuid}",
        f"position: {hero.position}",
    ]

    print("\n".join(actor_lines))

    expected_actor_lines = [
        "actor shell: name=Aria, faction=heroes, weight=180",
        "identity: uuid_matches_source=True",
        "position: (1, 2)",
    ]

    direct_block_names = {block.name for block in hero.get_blocks()}
    required_block_names = {
        "ability_scores",
        "skill_set",
        "SavingThrowSet",
        "Health",
        "Equipped",
        "ActionEconomy",
        "Senses",
        "Inventory",
        "Appearance",
        "Spellcasting",
        "Creature Proficiencies",
    }
    shared_source_count = sum(
        block.source_entity_uuid == hero.uuid
        for block in hero.get_blocks()
    )

    block_lines = [
        f"required blocks present: {required_block_names.issubset(direct_block_names)}",
        f"all direct blocks share source: {shared_source_count == len(hero.get_blocks())}",
    ]

    print("\n".join(block_lines))

    expected_block_lines = [
        "required blocks present: True",
        "all direct blocks share source: True",
    ]

    assert hero.name == "Aria"
    assert hero.uuid == hero.source_entity_uuid
    assert hero.position == (1, 2)
    assert hero.faction == "heroes"
    assert hero.weight == 180
    assert actor_lines == expected_actor_lines

    assert required_block_names.issubset(direct_block_names)

    for block in hero.get_blocks():
        assert block.source_entity_uuid == hero.uuid
    assert block_lines == expected_block_lines
    assert capsys.readouterr().out.splitlines() == (
        expected_actor_lines + expected_block_lines
    )


def test_ability_skill_and_save_blocks_print_character_sheet_terms(capsys) -> None:
    """Abilities, skills, and saves print D&D character sheet vocabulary."""
    reset_entity_anatomy_state()

    hero = create_tutorial_hero()

    strength = hero.ability_scores.get_ability("strength")
    dexterity = hero.ability_scores.get_ability("dexterity")
    athletics = hero.skill_set.get_skill("athletics")
    stealth = hero.skill_set.get_skill("stealth")
    dexterity_save = hero.saving_throws.get_saving_throw("dexterity")

    assert strength.ability_score.score == 16
    assert strength.ability_score.normalized_score == 3
    assert strength.modifier == 3
    assert dexterity.ability_score.score == 14
    assert dexterity.ability_score.normalized_score == 2
    assert dexterity.modifier == 2

    ability_lines = [
        f"strength: score={strength.ability_score.score}, modifier={strength.modifier}",
        f"dexterity: score={dexterity.ability_score.score}, modifier={dexterity.modifier}",
    ]

    print("\n".join(ability_lines))

    expected_ability_lines = [
        "strength: score=16, modifier=3",
        "dexterity: score=14, modifier=2",
    ]
    assert ability_lines == expected_ability_lines

    assert athletics.ability == "strength"
    assert athletics.proficiency is True
    assert athletics.expertise is False

    assert stealth.ability == "dexterity"
    assert stealth.proficiency is True
    assert stealth.expertise is True

    skill_lines = [
        (
            f"athletics: ability={athletics.ability}, "
            f"proficient={athletics.proficiency}, expert={athletics.expertise}"
        ),
        (
            f"stealth: ability={stealth.ability}, "
            f"proficient={stealth.proficiency}, expert={stealth.expertise}"
        ),
    ]

    print("\n".join(skill_lines))

    expected_skill_lines = [
        "athletics: ability=strength, proficient=True, expert=False",
        "stealth: ability=dexterity, proficient=True, expert=True",
    ]
    assert skill_lines == expected_skill_lines

    assert dexterity_save.ability == "dexterity"
    assert dexterity_save.proficiency is True

    save_lines = [
        f"dexterity save: ability={dexterity_save.ability}, proficient={dexterity_save.proficiency}",
    ]

    print("\n".join(save_lines))

    expected_save_lines = [
        "dexterity save: ability=dexterity, proficient=True",
    ]
    assert save_lines == expected_save_lines
    assert capsys.readouterr().out.splitlines() == (
        expected_ability_lines + expected_skill_lines + expected_save_lines
    )


def test_health_resources_spellcasting_and_appearance_print_actor_regions(capsys) -> None:
    """Actor subsystems print HP, budgets, spell data, and renderer data."""
    reset_entity_anatomy_state()

    hero = create_tutorial_hero()

    health_lines = [
        f"hit dice count: {hero.health.total_hit_dices_number}",
        f"current hp: {hero.get_hp()}",
    ]

    print("\n".join(health_lines))

    expected_health_lines = [
        "hit dice count: 2",
        "current hp: 24",
    ]
    assert hero.get_hp() == 24
    assert hero.health.total_hit_dices_number == 2
    assert health_lines == expected_health_lines

    resource_lines = [
        f"actions: {hero.action_economy.actions.normalized_score}",
        f"bonus actions: {hero.action_economy.bonus_actions.normalized_score}",
        f"reactions: {hero.action_economy.reactions.normalized_score}",
        f"movement: {hero.action_economy.movement.normalized_score}",
        f"level 1 spell slots: {hero.action_economy.spell_slot_1.normalized_score}",
    ]

    print("\n".join(resource_lines))

    expected_resource_lines = [
        "actions: 1",
        "bonus actions: 1",
        "reactions: 1",
        "movement: 30",
        "level 1 spell slots: 2",
    ]

    assert hero.action_economy.actions.normalized_score == 1
    assert hero.action_economy.bonus_actions.normalized_score == 1
    assert hero.action_economy.reactions.normalized_score == 1
    assert hero.action_economy.movement.normalized_score == 30
    assert hero.action_economy.spell_slot_1.normalized_score == 2
    assert resource_lines == expected_resource_lines

    hero.action_economy.add_resource_contribution(
        name="Second Wind",
        source_id="fixture.second_wind",
        maximum=1,
        recharge_type=RechargeType.SHORT_REST,
    )
    assert hero.action_economy.consume_resource("Second Wind") is True
    after_consume = hero.action_economy.get_resource_current("Second Wind")
    assert hero.action_economy.get_resource_current("Second Wind") == 0
    hero.action_economy.on_short_rest()
    after_rest = hero.action_economy.get_resource_current("Second Wind")
    assert hero.action_economy.get_resource_current("Second Wind") == 1

    named_resource_lines = [
        f"Second Wind after consume: {after_consume}",
        f"Second Wind after short rest: {after_rest}",
    ]

    print("\n".join(named_resource_lines))

    expected_named_resource_lines = [
        "Second Wind after consume: 0",
        "Second Wind after short rest: 1",
    ]
    assert named_resource_lines == expected_named_resource_lines

    spellcasting_lines = [
        f"spellcasting ability: {hero.spellcasting.spellcasting_ability}",
        f"spell attack bonus: {hero.spellcasting.spell_attack_bonus.normalized_score}",
        f"spell dc bonus: {hero.spellcasting.spell_dc_bonus.normalized_score}",
    ]

    print("\n".join(spellcasting_lines))

    expected_spellcasting_lines = [
        "spellcasting ability: wisdom",
        "spell attack bonus: 1",
        "spell dc bonus: 2",
    ]

    assert hero.spellcasting.spellcasting_ability == "wisdom"
    assert hero.spellcasting.spell_attack_bonus.normalized_score == 1
    assert hero.spellcasting.spell_dc_bonus.normalized_score == 2
    assert spellcasting_lines == expected_spellcasting_lines

    appearance_lines = [
        f"body: {hero.appearance.body_category}",
        f"skin tint: {hex(hero.appearance.skin_tint)}",
        f"head: {hero.appearance.head_category}",
    ]

    print("\n".join(appearance_lines))

    expected_appearance_lines = [
        "body: NakedBody2",
        "skin tint: 0x8a5a44",
        "head: Head9",
    ]

    assert hero.appearance.body_category == "NakedBody2"
    assert hero.appearance.skin_tint == 0x8A5A44
    assert hero.appearance.head_category == "Head9"
    assert appearance_lines == expected_appearance_lines
    assert capsys.readouterr().out.splitlines() == (
        expected_health_lines
        + expected_resource_lines
        + expected_named_resource_lines
        + expected_spellcasting_lines
        + expected_appearance_lines
    )


def test_block_tree_discovery_prints_children_and_values(capsys) -> None:
    """BaseBlock discovery prints child block and value lookup results."""
    reset_entity_anatomy_state()

    hero = create_tutorial_hero()

    strength = hero.ability_scores.get_block_from_name("strength")
    assert strength is hero.ability_scores.strength

    strength_score = hero.ability_scores.strength.get_value_from_name(
        "strength Ability Score"
    )
    assert strength_score is hero.ability_scores.strength.ability_score

    tree_lookup_lines = [
        f"block lookup: {strength.name}",
        f"value lookup: {strength_score.name}",
    ]

    print("\n".join(tree_lookup_lines))

    expected_tree_lookup_lines = [
        "block lookup: strength",
        "value lookup: strength Ability Score",
    ]
    assert tree_lookup_lines == expected_tree_lookup_lines

    deep_values = hero.get_values(deep=True)
    deep_value_names = {value.name for value in deep_values}
    sample_value_names = sorted(
        name
        for name in deep_value_names
        if name in {"strength Ability Score", "Actions", "Spell Attack Bonus"}
    )

    deep_value_lines = [
        f"all values modifiable: {all(isinstance(value, ModifiableValue) for value in deep_values)}",
        f"sample values: {sample_value_names}",
    ]

    print("\n".join(deep_value_lines))

    expected_deep_value_lines = [
        "all values modifiable: True",
        "sample values: ['Actions', 'Spell Attack Bonus', 'strength Ability Score']",
    ]

    assert all(isinstance(value, ModifiableValue) for value in deep_values)
    assert "strength Ability Score" in deep_value_names
    assert "Actions" in deep_value_names
    assert "Spell Attack Bonus" in deep_value_names
    assert deep_value_lines == expected_deep_value_lines
    assert capsys.readouterr().out.splitlines() == (
        expected_tree_lookup_lines + expected_deep_value_lines
    )
