"""Manual Chapter 15 checks for class features, factories, and feats."""

from typing import Any, cast
from uuid import uuid4

from dnd.actions import SpellAction
from dnd.actions_functional import get_available_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.classes.barbarian_factory import (
    BarbarianConfig,
    PrimalPathChoice,
    create_barbarian,
)
from dnd.classes.feats import LuckyFeature, lucky_processor
from dnd.classes.fighter import ActionSurge, SecondWind
from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.classes.rage import Frenzy
from dnd.classes.barbarian import RecklessAttack
from dnd.classes.sorcerer import QuickenedSpell
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer
from dnd.conditions import Paralyzed
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.dice import DiceRoll, RollType, fixed_dice_faces
from dnd.core.events import D20RollResultEvent, EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import DamageType
from dnd.core.values import (
    AdvantageStatus,
    AutoHitStatus,
    BaseValue,
    CriticalStatus,
    ModifiableValue,
)
from dnd.entity import Entity, EntityConfig


def reset_class_feature_state(width: int = 14, height: int = 8) -> None:
    """Clear global state and create a small class-feature arena."""
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


def create_feature_target(
    name: str = "Training Target",
    position: tuple[int, int] = (3, 1),
    faction: str = "monsters",
) -> Entity:
    """Create a durable target for class-feature examples."""
    target_id = uuid4()
    return Entity.create(
        source_entity_uuid=target_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=10),
                dexterity=AbilityConfig(ability_score=10),
                constitution=AbilityConfig(ability_score=10),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=10),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=6,
                        mode="maximums",
                    )
                ],
            ),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
    )


def test_first_class_feature_example_prints_factory_actor_state(capsys) -> None:
    """The opening class-feature example prints factory-built actor state."""
    reset_class_feature_state()

    fighter = create_fighter(
        FighterConfig(
            level=5,
            name="Manual Fighter",
            position=(1, 1),
            faction="heroes",
            fighting_style="defense",
            asi_4=[("strength", 2)],
        )
    )
    barbarian = create_barbarian(
        BarbarianConfig(
            level=5,
            name="Manual Barbarian",
            position=(2, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
        )
    )
    sorcerer = create_sorcerer(
        SorcererConfig(
            level=5,
            name="Manual Sorcerer",
            position=(3, 1),
            faction="heroes",
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
            spell_names=["Fire Bolt", "Magic Missile", "Hold Person"],
        )
    )

    fighter_features = [
        name
        for name in [
            "Second Wind Feature",
            "Action Surge Feature",
            "Extra Attack",
        ]
        if name in fighter.active_conditions
    ]
    barbarian_features = [
        name
        for name in ["Rage Feature", "Frenzy Feature", "Fast Movement"]
        if name in barbarian.active_conditions
    ]
    sorcerer_features = [
        name
        for name in ["Draconic Resilience", "Sorcery Points Feature"]
        if name in sorcerer.active_conditions
    ]

    readout_lines = [
        f"fighter: hp={fighter.get_hp()}, features={', '.join(fighter_features)}",
        (
            "fighter resources: "
            f"second_wind={fighter.action_economy.resources['second_wind'].current}/"
            f"{fighter.action_economy.resources['second_wind'].maximum}, "
            f"action_surge={fighter.action_economy.resources['action_surge'].current}/"
            f"{fighter.action_economy.resources['action_surge'].maximum}, "
            f"extra_attacks={fighter.action_economy.resources['extra_attacks'].current}/"
            f"{fighter.action_economy.resources['extra_attacks'].maximum}"
        ),
        (
            "fighter buttons: "
            f"Second Wind={fighter.get_action_template('Second Wind') is not None}, "
            f"Action Surge={fighter.get_action_template('Action Surge') is not None}"
        ),
        (
            f"barbarian: hp={barbarian.get_hp()}, "
            f"features={', '.join(barbarian_features)}"
        ),
        (
            "barbarian resources: "
            f"rage={barbarian.action_economy.resources['rage'].current}/"
            f"{barbarian.action_economy.resources['rage'].maximum}"
        ),
        (
            "barbarian buttons: "
            f"Frenzy={barbarian.get_action_template('Frenzy') is not None}, "
            f"Reckless Attack="
            f"{barbarian.get_action_template('Reckless Attack') is not None}"
        ),
        (
            f"sorcerer: hp={sorcerer.get_hp()}, "
            f"features={', '.join(sorcerer_features)}"
        ),
        (
            "sorcerer resources: "
            f"sorcery_points="
            f"{sorcerer.action_economy.resources['sorcery_points'].current}/"
            f"{sorcerer.action_economy.resources['sorcery_points'].maximum}, "
            f"level3_slots={sorcerer.action_economy.spell_slot_3.normalized_score}"
        ),
        (
            "sorcerer buttons: "
            f"Quickened={sorcerer.get_action_template('Quickened Spell') is not None}, "
            f"Twinned={sorcerer.get_action_template('Twinned Spell') is not None}, "
            f"Fire Bolt={sorcerer.get_action_template('Fire Bolt') is not None}"
        ),
    ]

    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        (
            "fighter: hp=44, "
            "features=Second Wind Feature, Action Surge Feature, Extra Attack"
        ),
        (
            "fighter resources: second_wind=1/1, "
            "action_surge=1/1, extra_attacks=1/1"
        ),
        "fighter buttons: Second Wind=yes, Action Surge=yes",
        "barbarian: hp=50, features=Rage Feature, Frenzy Feature, Fast Movement",
        "barbarian resources: rage=3/3",
        "barbarian buttons: Frenzy=yes, Reckless Attack=yes",
        "sorcerer: hp=37, features=Draconic Resilience, Sorcery Points Feature",
        "sorcerer resources: sorcery_points=5/5, level3_slots=2",
        "sorcerer buttons: Quickened=yes, Twinned=yes, Fire Bolt=yes",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_factories_wire_level_gated_features_resources_actions_and_spells(capsys) -> None:
    """Class factories build playable actors from level and subclass choices."""
    reset_class_feature_state()

    fighter = create_fighter(
        FighterConfig(
            level=5,
            name="Manual Fighter",
            position=(1, 1),
            faction="heroes",
            fighting_style="defense",
            asi_4=[("strength", 2)],
        )
    )
    barbarian = create_barbarian(
        BarbarianConfig(
            level=5,
            name="Manual Barbarian",
            position=(2, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
        )
    )
    sorcerer = create_sorcerer(
        SorcererConfig(
            level=5,
            name="Manual Sorcerer",
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
    assert fighter.get_action_template("Second Wind") is not None

    assert "Rage Feature" in barbarian.active_conditions
    assert "Frenzy Feature" in barbarian.active_conditions
    assert "Fast Movement" in barbarian.active_conditions
    assert barbarian.action_economy.resources["rage"].maximum == 3
    assert barbarian.get_action_template("Frenzy") is not None

    assert "Draconic Resilience" in sorcerer.active_conditions
    assert "Sorcery Points Feature" in sorcerer.active_conditions
    assert sorcerer.action_economy.resources["sorcery_points"].maximum == 5
    assert sorcerer.action_economy.spell_slot_3.normalized_score == 2
    assert sorcerer.get_action_template("Quickened Spell") is not None
    assert sorcerer.get_action_template("Twinned Spell") is not None
    assert sorcerer.get_action_template("Fire Bolt") is not None

    readout_lines = [
        (
            f"fighter factory: hp={fighter.get_hp()}, "
            "features="
            f"{'Second Wind Feature' in fighter.active_conditions}/"
            f"{'Action Surge Feature' in fighter.active_conditions}/"
            f"{'Extra Attack' in fighter.active_conditions}, "
            f"extra_attacks={fighter.action_economy.resources['extra_attacks'].maximum}, "
            f"action_surge={fighter.action_economy.resources['action_surge'].maximum}, "
            f"second_wind_button={fighter.get_action_template('Second Wind') is not None}"
        ),
        (
            f"barbarian factory: hp={barbarian.get_hp()}, "
            "features="
            f"{'Rage Feature' in barbarian.active_conditions}/"
            f"{'Frenzy Feature' in barbarian.active_conditions}/"
            f"{'Fast Movement' in barbarian.active_conditions}, "
            f"rage={barbarian.action_economy.resources['rage'].maximum}, "
            f"frenzy_button={barbarian.get_action_template('Frenzy') is not None}"
        ),
        (
            f"sorcerer factory: hp={sorcerer.get_hp()}, "
            "features="
            f"{'Draconic Resilience' in sorcerer.active_conditions}/"
            f"{'Sorcery Points Feature' in sorcerer.active_conditions}, "
            "resources="
            f"sorcery_points={sorcerer.action_economy.resources['sorcery_points'].maximum}, "
            f"level3_slots={sorcerer.action_economy.spell_slot_3.normalized_score}, "
            "buttons="
            f"{sorcerer.get_action_template('Quickened Spell') is not None}/"
            f"{sorcerer.get_action_template('Twinned Spell') is not None}/"
            f"{sorcerer.get_action_template('Fire Bolt') is not None}"
        ),
    ]
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        (
            "fighter factory: hp=44, features=yes/yes/yes, "
            "extra_attacks=1, action_surge=1, second_wind_button=yes"
        ),
        (
            "barbarian factory: hp=50, features=yes/yes/yes, "
            "rage=3, frenzy_button=yes"
        ),
        (
            "sorcerer factory: hp=37, features=yes/yes, "
            "resources=sorcery_points=5, level3_slots=2, buttons=yes/yes/yes"
        ),
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_fighter_features_register_actions_spend_resources_and_short_rest(capsys) -> None:
    """Second Wind and Action Surge are feature-granted resource actions."""
    reset_class_feature_state()
    fighter = create_fighter(
        FighterConfig(
            level=2,
            name="Manual Fighter",
            position=(1, 1),
            faction="heroes",
        )
    )

    assert fighter.get_action_template("Second Wind") is not None
    assert fighter.get_action_template("Action Surge") is not None
    assert fighter.action_economy.resources["second_wind"].current == 1
    assert fighter.action_economy.resources["action_surge"].current == 1
    readout_lines = [
        (
            f"initial fighter: hp={fighter.get_hp()}, "
            f"second_wind={fighter.action_economy.resources['second_wind'].current}, "
            f"action_surge={fighter.action_economy.resources['action_surge'].current}, "
            f"buttons={fighter.get_action_template('Second Wind') is not None}/"
            f"{fighter.get_action_template('Action Surge') is not None}"
        )
    ]

    fighter.receive_damage(10, DamageType.FORCE, fighter.uuid)
    wounded_hp = fighter.get_hp()
    with fixed_dice_faces(6):
        second_wind_event = SecondWind(
            source_entity_uuid=fighter.uuid,
            fighter_level=2,
        ).apply()

    assert second_wind_event is not None
    assert not second_wind_event.canceled
    assert fighter.get_hp() == wounded_hp + 8
    assert fighter.action_economy.resources["second_wind"].current == 0
    assert fighter.action_economy.bonus_actions.normalized_score == 0
    readout_lines.append(
        (
            f"second wind: canceled={second_wind_event.canceled}, "
            f"hp={wounded_hp}->{fighter.get_hp()}, "
            f"resource={fighter.action_economy.resources['second_wind'].current}, "
            f"bonus={fighter.action_economy.bonus_actions.normalized_score}"
        )
    )

    fighter.action_economy.reset_all_costs()
    initial_actions = fighter.action_economy.actions.normalized_score
    action_surge_event = ActionSurge(source_entity_uuid=fighter.uuid).apply()

    assert action_surge_event is not None
    assert not action_surge_event.canceled
    assert "ActionSurging" in fighter.active_conditions
    assert fighter.action_economy.actions.normalized_score == initial_actions + 1
    assert fighter.action_economy.resources["action_surge"].current == 0
    readout_lines.append(
        (
            f"action surge: canceled={action_surge_event.canceled}, "
            f"actions={initial_actions}->{fighter.action_economy.actions.normalized_score}, "
            f"resource={fighter.action_economy.resources['action_surge'].current}, "
            f"condition={'ActionSurging' in fighter.active_conditions}"
        )
    )

    fighter.action_economy.on_short_rest()

    assert fighter.action_economy.resources["second_wind"].current == 1
    assert fighter.action_economy.resources["action_surge"].current == 1
    readout_lines.append(
        (
            f"short rest: second_wind="
            f"{fighter.action_economy.resources['second_wind'].current}, "
            f"action_surge={fighter.action_economy.resources['action_surge'].current}"
        )
    )
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "initial fighter: hp=20, second_wind=1, action_surge=1, buttons=yes/yes",
        "second wind: canceled=no, hp=10->18, resource=0, bonus=0",
        "action surge: canceled=no, actions=1->2, resource=0, condition=yes",
        "short rest: second_wind=1, action_surge=1",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_barbarian_frenzy_creates_and_cleans_condition_tree(capsys) -> None:
    """Berserker Frenzy creates Raging and Frenzied state owned by cleanup."""
    reset_class_feature_state()
    barbarian = create_barbarian(
        BarbarianConfig(
            level=3,
            name="Manual Berserker",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
        )
    )

    assert barbarian.get_action_template("Frenzy") is not None
    assert barbarian.action_economy.resources["rage"].current == 3
    readout_lines = [
        (
            f"initial berserker: rage={barbarian.action_economy.resources['rage'].current}, "
            f"frenzy_button={barbarian.get_action_template('Frenzy') is not None}"
        )
    ]

    frenzy_event = Frenzy(
        source_entity_uuid=barbarian.uuid,
        rage_damage=2,
    ).apply()

    assert frenzy_event is not None
    assert not frenzy_event.canceled
    assert "Raging" in barbarian.active_conditions
    assert "Frenzied" in barbarian.active_conditions
    assert barbarian.get_action_template("Frenzied Strike") is not None
    assert barbarian.action_economy.resources["rage"].current == 2

    raging = barbarian.active_conditions["Raging"]
    frenzied = barbarian.active_conditions["Frenzied"]
    assert frenzied.uuid in raging.sub_conditions
    readout_lines.append(
        (
            f"after frenzy: canceled={frenzy_event.canceled}, "
            f"rage={barbarian.action_economy.resources['rage'].current}, "
            f"raging={'Raging' in barbarian.active_conditions}, "
            f"frenzied={'Frenzied' in barbarian.active_conditions}, "
            f"strike={barbarian.get_action_template('Frenzied Strike') is not None}, "
            f"linked={frenzied.uuid in raging.sub_conditions}"
        )
    )

    barbarian.remove_condition("Raging")

    assert "Raging" not in barbarian.active_conditions
    assert "Frenzied" not in barbarian.active_conditions
    assert barbarian.get_action_template("Frenzied Strike") is None
    readout_lines.append(
        (
            f"after rage cleanup: raging={'Raging' in barbarian.active_conditions}, "
            f"frenzied={'Frenzied' in barbarian.active_conditions}, "
            f"strike={barbarian.get_action_template('Frenzied Strike') is not None}"
        )
    )
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "initial berserker: rage=3, frenzy_button=yes",
        (
            "after frenzy: canceled=no, rage=2, raging=yes, frenzied=yes, "
            "strike=yes, linked=yes"
        ),
        "after rage cleanup: raging=no, frenzied=no, strike=no",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_frenzied_strike_discovery_excludes_targets_outside_weapon_reach() -> None:
    """Frenzied Strike discovery only exposes targets the engine can execute."""
    reset_class_feature_state()
    barbarian = create_barbarian(
        BarbarianConfig(
            level=3,
            name="Reach Checked Berserker",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
        )
    )
    near_target = create_feature_target(name="Near Target", position=(2, 1), faction="monsters")
    far_target = create_feature_target(name="Far Target", position=(3, 1), faction="monsters")
    Entity.update_all_entities_senses(max_distance=20)

    frenzy_event = Frenzy(source_entity_uuid=barbarian.uuid, rage_damage=2).apply()
    assert frenzy_event is not None
    assert not frenzy_event.canceled
    barbarian.action_economy.reset_all_costs()

    available = get_available_actions(barbarian)
    strike = next(
        action for action in available.entity_actions
        if action.template_name == "Frenzied Strike"
    )

    target_uuids = {target.target_uuid for target in strike.valid_targets}
    assert near_target.uuid in target_uuids
    assert far_target.uuid not in target_uuids


def test_paralyzed_barbarian_cannot_use_zero_cost_reckless_attack() -> None:
    """Severe control blocks zero-cost class actions, not only costed actions."""
    reset_class_feature_state()
    barbarian = create_barbarian(
        BarbarianConfig(
            level=5,
            name="Held Berserker",
            position=(1, 1),
            faction="heroes",
            primal_path=PrimalPathChoice.BERSERKER,
            asi_4=[("strength", 2)],
        )
    )
    caster = create_feature_target(name="Manual Controller", position=(3, 1))

    paralyze_event = barbarian.add_condition(
        Paralyzed(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=barbarian.uuid,
        ),
        check_save_throw=False,
    )

    assert paralyze_event is not None
    assert not paralyze_event.canceled
    assert "Paralyzed" in barbarian.active_conditions
    assert "Incapacitated" in barbarian.active_conditions

    available = get_available_actions(barbarian)
    reckless = next(
        action for action in available.self_actions
        if action.template_name == "Reckless Attack"
    )

    assert reckless.can_afford is False
    assert reckless.valid_targets == []
    assert RecklessAttack(source_entity_uuid=barbarian.uuid).apply() is None


def test_sorcerer_quickened_spell_overrides_template_and_cleans_after_cast(capsys) -> None:
    """Quickened Spell mutates eligible spell templates until a spell is cast."""
    reset_class_feature_state()
    sorcerer = create_sorcerer(
        SorcererConfig(
            level=3,
            name="Manual Sorcerer",
            position=(1, 1),
            faction="heroes",
            metamagic_choices=["quickened", "twinned"],
            spell_names=["Fire Bolt", "Magic Missile"],
        )
    )
    target = create_feature_target(position=(3, 1))
    Entity.update_all_entities_senses(max_distance=30)

    fire_bolt_template = sorcerer.get_action_template("Fire Bolt")
    assert isinstance(fire_bolt_template, SpellAction)
    assert fire_bolt_template.alt_cost_type is None
    assert sorcerer.action_economy.resources["sorcery_points"].current == 3
    readout_lines = [
        (
            "before quickened: "
            f"sorcery_points={sorcerer.action_economy.resources['sorcery_points'].current}, "
            f"alt_cost={fire_bolt_template.alt_cost_type}, "
            f"cost={fire_bolt_template.effective_costs[0].cost_type}"
        )
    ]

    quickened_event = QuickenedSpell(source_entity_uuid=sorcerer.uuid).apply()

    assert quickened_event is not None
    assert not quickened_event.canceled
    assert "MetamagicActive" in sorcerer.active_conditions
    assert sorcerer.action_economy.resources["sorcery_points"].current == 1
    assert fire_bolt_template.alt_cost_type == "bonus_actions"
    assert fire_bolt_template.effective_costs[0].cost_type == "bonus_actions"
    readout_lines.append(
        (
            f"after quickened: canceled={quickened_event.canceled}, "
            f"sorcery_points={sorcerer.action_economy.resources['sorcery_points'].current}, "
            f"active={'MetamagicActive' in sorcerer.active_conditions}, "
            f"alt_cost={fire_bolt_template.alt_cost_type}, "
            f"cost={fire_bolt_template.effective_costs[0].cost_type}"
        )
    )

    spell_instance = fire_bolt_template.instantiate(target_entity_uuid=target.uuid)
    hp_before = target.get_hp()
    with fixed_dice_faces(12, 4):
        spell_event = spell_instance.apply()

    assert spell_event is not None
    assert not spell_event.canceled
    assert "MetamagicActive" not in sorcerer.active_conditions
    assert fire_bolt_template.alt_cost_type is None
    assert sorcerer.action_economy.bonus_actions.normalized_score == 0
    assert sorcerer.action_economy.actions.normalized_score == 1
    spell_attack_event = cast(Any, spell_event)
    readout_lines.append(
        (
            f"after fire bolt: canceled={spell_event.canceled}, "
            f"outcome={spell_attack_event.attack_outcome.value}, "
            f"hp={hp_before}->{target.get_hp()}, "
            f"actions={sorcerer.action_economy.actions.normalized_score}, "
            f"bonus={sorcerer.action_economy.bonus_actions.normalized_score}"
        )
    )
    readout_lines.append(
        (
            f"cleanup: active={'MetamagicActive' in sorcerer.active_conditions}, "
            f"alt_cost={fire_bolt_template.alt_cost_type}"
        )
    )
    readout_lines = [
        line.replace("True", "yes").replace("False", "no").replace("None", "none")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "before quickened: sorcery_points=3, alt_cost=none, cost=actions",
        (
            "after quickened: canceled=no, sorcery_points=1, active=yes, "
            "alt_cost=bonus_actions, cost=bonus_actions"
        ),
        "after fire bolt: canceled=no, outcome=Hit, hp=60->56, actions=1, bonus=0",
        "cleanup: active=no, alt_cost=none",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_lucky_feat_owns_resource_and_rewrites_low_own_d20_rolls(capsys) -> None:
    """Lucky is a feat-style condition with a resource and d20 processor."""
    reset_class_feature_state()
    hero = create_feature_target("Lucky Hero", (1, 1), "heroes")
    other = create_feature_target("Other Roller", (2, 1), "heroes")
    hero.add_condition(LuckyFeature(source_entity_uuid=hero.uuid, target_entity_uuid=hero.uuid))

    assert "Lucky" in hero.active_conditions
    assert hero.action_economy.resources["luck_points"].current == 3
    assert hero.get_event_handler_by_name("Lucky") is not None
    readout_lines = [
        (
            f"lucky attached: active={'Lucky' in hero.active_conditions}, "
            f"luck={hero.action_economy.resources['luck_points'].current}, "
            f"handler={hero.get_event_handler_by_name('Lucky') is not None}"
        )
    ]

    bonus = ModifiableValue.create(
        source_entity_uuid=hero.uuid,
        base_value=0,
        value_name="Lucky tutorial bonus",
    )
    other_bonus = ModifiableValue.create(
        source_entity_uuid=other.uuid,
        base_value=0,
        value_name="Other tutorial bonus",
    )

    def make_d20_event(source: Entity, total: int, event_bonus: ModifiableValue) -> D20RollResultEvent:
        roll = DiceRoll(
            dice_uuid=uuid4(),
            roll_type=RollType.CHECK,
            results=[total],
            total=total,
            bonus=0,
            advantage_status=AdvantageStatus.NONE,
            critical_status=CriticalStatus.NONE,
            auto_hit_status=AutoHitStatus.NONE,
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

    with fixed_dice_faces(20):
        modified = lucky_processor(make_d20_event(hero, 4, bonus), hero.uuid)

    assert modified is not None
    assert modified.modified
    assert modified.get_effective_roll().total == 20
    assert hero.action_economy.resources["luck_points"].current == 2
    readout_lines.append(
        (
            f"owner low roll: modified={modified.modified}, "
            f"original={modified.original_roll.total}, "
            f"effective={modified.get_effective_roll().total}, "
            f"luck={hero.action_economy.resources['luck_points'].current}"
        )
    )

    other_result = lucky_processor(make_d20_event(other, 4, other_bonus), hero.uuid)
    acceptable_result = lucky_processor(make_d20_event(hero, 12, bonus), hero.uuid)
    assert other_result is None
    assert acceptable_result is None
    assert hero.action_economy.resources["luck_points"].current == 2
    readout_lines.append(
        (
            f"ignored rolls: other={other_result is None}, "
            f"acceptable={acceptable_result is None}, "
            f"luck={hero.action_economy.resources['luck_points'].current}"
        )
    )

    hero.remove_condition("Lucky")

    assert "Lucky" not in hero.active_conditions
    assert hero.get_event_handler_by_name("Lucky") is None
    assert not hero.action_economy.has_resource("luck_points")
    readout_lines.append(
        (
            f"cleanup: active={'Lucky' in hero.active_conditions}, "
            f"handler={hero.get_event_handler_by_name('Lucky') is not None}, "
            f"resource={hero.action_economy.has_resource('luck_points')}"
        )
    )
    readout_lines = [
        line.replace("True", "yes").replace("False", "no")
        for line in readout_lines
    ]
    print("\n".join(readout_lines))

    expected_lines = [
        "lucky attached: active=yes, luck=3, handler=yes",
        "owner low roll: modified=yes, original=4, effective=20, luck=2",
        "ignored rolls: other=yes, acceptable=yes, luck=2",
        "cleanup: active=no, handler=no, resource=no",
    ]
    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
