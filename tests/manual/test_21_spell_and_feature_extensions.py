"""Manual Chapter 21 checks for spell and feature extensions."""

from dnd.actions.standard import (
    SpellEvent,
)
from dnd.actions.operations import execute_by_index, get_available_actions
from dnd.core.base_actions import (
    TargetType,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.events.events_registry import (
    EventPhase,
    EventQueue,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.core.values import BaseValue
from dnd.entity import Entity
from dnd.extensions.aegis_spark import (
    AegisSpark,
    AegisSparkEffect,
)
from tests.manual.extension_scenario_support import (
    create_aegis_scene,
    create_spell_feature_actor,
    find_action_info,
)


def reset_spell_feature_state(width: int = 8, height: int = 6) -> None:
    """Clear global state and create a small spell-feature arena."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, width, height)


def test_aegis_module_exposes_spell_effect_and_factories(capsys) -> None:
    """The extension module exposes the spell, effect, and scene factory."""
    reset_spell_feature_state()
    caster = create_spell_feature_actor("Aegis Student", (1, 1), "heroes")
    spark = AegisSpark(source_entity_uuid=caster.uuid, caster_level=5, template=True)
    effect = AegisSparkEffect(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid)

    assert spark.name == "Aegis Spark"
    assert spark.spell_level == 0
    assert spark.spell_school == "abjuration"
    assert spark.target_type == TargetType.ENTITY
    assert spark.include_self
    assert spark.valid_target_filter == "self_or_allies"
    assert spark.effective_range == 30
    assert effect.armor_bonus == 2
    assert callable(create_aegis_scene)

    readout_lines = [
        (
            "module surfaces: "
            f"spell={spark.name}, "
            f"level={spark.spell_level}, "
            f"school={spark.spell_school}, "
            f"target={spark.target_type.value}"
        ),
        (
            "target policy: "
            f"include_self={'yes' if spark.include_self else 'no'}, "
            f"filter={spark.valid_target_filter}, "
            f"range={spark.effective_range}"
        ),
        (
            "owners: "
            f"effect_ac=+{effect.armor_bonus}, "
            f"scene_factory={'yes' if callable(create_aegis_scene) else 'no'}"
        ),
    ]
    expected_lines = [
        "module surfaces: spell=Aegis Spark, level=0, school=abjuration, target=entity",
        "target policy: include_self=yes, filter=self_or_allies, range=30",
        "owners: effect_ac=+2, scene_factory=yes",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_spell_extension_discovers_self_and_allies_not_enemies(capsys) -> None:
    """The custom spell uses engine target filters and discovery metadata."""
    reset_spell_feature_state()
    caster, ally, enemy = create_aegis_scene()
    actions = get_available_actions(caster)
    aegis = find_action_info(actions, "Aegis Spark")

    assert aegis.target_type == TargetType.ENTITY
    assert aegis.action_category.value == "spell"
    assert aegis.spell_level == 0
    assert aegis.cast_at_level == 0
    assert aegis.cost_type == "actions"
    assert [target.target_name for target in aegis.valid_targets] == [
        "Shield Ally",
        "Aegis Warden",
    ]
    valid_target_uuids = {target.target_uuid for target in aegis.valid_targets}
    assert enemy.uuid not in valid_target_uuids
    assert ally.uuid in valid_target_uuids
    assert caster.uuid in valid_target_uuids

    readout_lines = [
        (
            "spell row: "
            f"target={aegis.target_type.value}, "
            f"category={aegis.action_category.value}, "
            f"level={aegis.spell_level}, "
            f"cast={aegis.cast_at_level}, "
            f"cost={aegis.cost_type}"
        ),
        f"valid targets: {[target.target_name for target in aegis.valid_targets]}",
        (
            "target filter: "
            f"ally={'yes' if ally.uuid in valid_target_uuids else 'no'}, "
            f"caster={'yes' if caster.uuid in valid_target_uuids else 'no'}, "
            f"enemy={'yes' if enemy.uuid in valid_target_uuids else 'no'}"
        ),
    ]
    expected_lines = [
        "spell row: target=entity, category=spell, level=0, cast=0, cost=actions",
        "valid targets: ['Shield Ally', 'Aegis Warden']",
        "target filter: ally=yes, caster=yes, enemy=no",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_spell_extension_executes_event_condition_cost_and_cleanup(capsys) -> None:
    """The custom spell creates a SpellEvent, applies state, spends cost, and cleans up."""
    reset_spell_feature_state()
    caster, ally, _enemy = create_aegis_scene()
    actions = get_available_actions(caster)
    aegis = find_action_info(actions, "Aegis Spark")
    ally_index = next(
        target.index
        for target in aegis.valid_targets
        if target.target_uuid == ally.uuid
    )
    ally_ac_before = ally.ac_bonus().normalized_score

    event = execute_by_index(caster, "Aegis Spark", ally_index, available=actions)

    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.phase == EventPhase.COMPLETION
    assert event.spell_id == "aegis_spark"
    assert event.spell_level == 0
    assert event.cast_at_level == 0
    assert "Aegis Spark" in ally.active_conditions
    assert ally.ac_bonus().normalized_score == ally_ac_before + 2
    assert caster.action_economy.actions.normalized_score == 0
    ally_ac_active = ally.ac_bonus().normalized_score
    actions_after_cast = caster.action_economy.actions.normalized_score
    condition_after_cast = "Aegis Spark" in ally.active_conditions

    ally.remove_condition("Aegis Spark")

    assert "Aegis Spark" not in ally.active_conditions
    assert ally.ac_bonus().normalized_score == ally_ac_before

    readout_lines = [
        (
            "spell event: "
            f"type={type(event).__name__}, "
            f"phase={event.phase.value if event else 'none'}, "
            f"canceled={'yes' if event and event.canceled else 'no'}, "
            f"spell={event.spell_id if event else 'none'}"
        ),
        (
            "spell levels: "
            f"base={event.spell_level if event else 'none'}, "
            f"cast={event.cast_at_level if event else 'none'}, "
            f"target_index={ally_index}"
        ),
        (
            "ward active: "
            f"condition={condition_after_cast}, "
            f"ac={ally_ac_before}->{ally_ac_active}, "
            f"caster_actions={actions_after_cast}"
        ),
        (
            "after cleanup: "
            f"condition={'Aegis Spark' in ally.active_conditions}, "
            f"ac={ally.ac_bonus().normalized_score}"
        ),
    ]
    expected_lines = [
        "spell event: type=SpellEvent, phase=completion, canceled=no, spell=aegis_spark",
        "spell levels: base=0, cast=0, target_index=0",
        "ward active: condition=True, ac=11->13, caster_actions=0",
        "after cleanup: condition=False, ac=11",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_extension_scene_composes_actor_ally_enemy_and_template(capsys) -> None:
    """The test scene explicitly installs the authored extension spell."""
    reset_spell_feature_state()
    caster, ally, enemy = create_aegis_scene()
    actions = get_available_actions(caster)
    aegis = find_action_info(actions, "Aegis Spark")

    assert caster.name == "Aegis Warden"
    assert ally.name == "Shield Ally"
    assert enemy.name == "Training Dummy"
    assert caster.get_action_template("Aegis Spark") is not None
    assert [target.target_name for target in aegis.valid_targets] == [
        "Shield Ally",
        "Aegis Warden",
    ]
    target_names = [target.target_name for target in aegis.valid_targets]
    template_present = caster.get_action_template("Aegis Spark") is not None

    readout_lines = [
        f"scene actors: caster={caster.name}, ally={ally.name}, enemy={enemy.name}",
        (
            "extension state: "
            f"template={'yes' if template_present else 'no'}"
        ),
        f"spell targets: {target_names}",
    ]
    expected_lines = [
        "scene actors: caster=Aegis Warden, ally=Shield Ally, enemy=Training Dummy",
        "extension state: template=yes",
        "spell targets: ['Shield Ally', 'Aegis Warden']",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
