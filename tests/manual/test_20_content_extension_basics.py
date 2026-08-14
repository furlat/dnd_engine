"""Manual Chapter 20 checks for content extension basics."""

from uuid import uuid4

from dnd.actions_functional import execute_by_index, get_available_actions
from dnd.blocks.base_item import UsableItem
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_actions import (
    ActionAvailabilityStatus,
    ActionEvent,
    TargetType,
)
from dnd.core.base_object import BaseObject
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.values import BaseValue
from dnd.entity import Entity
from dnd.extensions.field_focus import (
    DeployFieldFocus,
    FIELD_KIT_RECIPE,
    FieldFocus,
    field_kit_recipe,
)
from tests.manual.extension_scenario_support import (
    create_field_medic,
    create_field_training_scene,
    find_action_info,
    find_item_action,
    inventory_item_named,
)
from dnd.monsters.bestiary import create_goblin


def reset_content_extension_state(width: int = 8, height: int = 6) -> None:
    """Clear global state and create a small content-extension arena."""
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


def _materialize_field_kit(
    owner_uuid,
    *,
    charges: int = 1,
) -> UsableItem:
    return materialize_item(
        field_kit_recipe(charges=charges),
        owner_uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=UsableItem,
    )


def test_builtin_extension_module_exposes_expected_surfaces(capsys) -> None:
    """The extension module exposes behavior and canonical recipe surfaces."""
    source_uuid = uuid4()
    condition = FieldFocus(source_entity_uuid=source_uuid, target_entity_uuid=source_uuid)
    action = DeployFieldFocus(source_entity_uuid=source_uuid)

    assert condition.name == "Field Focus"
    assert condition.movement_bonus == 10
    assert condition.armor_bonus == 1
    assert FieldFocus.model_fields["movement_bonus"].description == "Bonus feet of movement while focused."
    assert action.name == "Deploy Field Focus"
    assert action.target_type == TargetType.SELF
    assert action.costs[0].cost_type == "bonus_actions"
    assert FIELD_KIT_RECIPE.ref.content_id == "gear.field_kit"
    assert callable(field_kit_recipe)
    assert callable(create_field_medic)
    assert callable(create_field_training_scene)

    readout_lines = [
        (
            "module surfaces: "
            f"condition={condition.name}, "
            f"action={action.name}, "
            f"target={action.target_type.value}, "
            f"cost={action.costs[0].cost_type}"
        ),
        (
            "condition defaults: "
            f"movement=+{condition.movement_bonus}, "
            f"armor=+{condition.armor_bonus}, "
            f"field={FieldFocus.model_fields['movement_bonus'].description}"
        ),
        (
            "composition: "
            f"kit_recipe={'yes' if callable(field_kit_recipe) else 'no'}, "
            f"medic={'yes' if callable(create_field_medic) else 'no'}, "
            f"scene={'yes' if callable(create_field_training_scene) else 'no'}"
        ),
    ]
    expected_lines = [
        "module surfaces: condition=Field Focus, action=Deploy Field Focus, target=self, cost=bonus_actions",
        "condition defaults: movement=+10, armor=+1, field=Bonus feet of movement while focused.",
        "composition: kit_recipe=yes, medic=yes, scene=yes",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_custom_condition_applies_and_cleans_up_owned_modifiers(capsys) -> None:
    """A custom condition can own value modifiers and clean them up."""
    reset_content_extension_state()
    hero = create_goblin(name="Focus Tester", position=(1, 1), faction="heroes")
    base_movement = hero.action_economy.movement.normalized_score
    base_ac = hero.ac_bonus().normalized_score

    condition = FieldFocus(source_entity_uuid=hero.uuid, target_entity_uuid=hero.uuid)
    event = hero.add_condition(condition)

    assert event is not None
    assert event.phase == EventPhase.COMPLETION
    assert "Field Focus" in hero.active_conditions
    assert hero.action_economy.movement.normalized_score == base_movement + 10
    assert hero.ac_bonus().normalized_score == base_ac + 1
    assert condition.modifers_uuids

    active_before_cleanup = "Field Focus" in hero.active_conditions
    active_movement = hero.action_economy.movement.normalized_score
    active_ac = hero.ac_bonus().normalized_score

    hero.remove_condition("Field Focus")

    assert "Field Focus" not in hero.active_conditions
    assert hero.action_economy.movement.normalized_score == base_movement
    assert hero.ac_bonus().normalized_score == base_ac

    readout_lines = [
        (
            "apply event: "
            f"phase={event.phase.value if event else 'none'}, "
            f"active={active_before_cleanup}, "
            f"modifiers={len(condition.modifers_uuids)}"
        ),
        f"bonuses active: movement={base_movement}->{active_movement}, ac={base_ac}->{active_ac}",
        (
            "after cleanup: "
            f"active={'Field Focus' in hero.active_conditions}, "
            f"movement={hero.action_economy.movement.normalized_score}, "
            f"ac={hero.ac_bonus().normalized_score}"
        ),
    ]
    expected_lines = [
        "apply event: phase=completion, active=True, modifiers=2",
        "bonuses active: movement=30->40, ac=15->16",
        "after cleanup: active=False, movement=30, ac=15",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_custom_action_registers_discovers_executes_and_spends_cost(capsys) -> None:
    """A custom action template can be registered, discovered, and executed."""
    reset_content_extension_state()
    hero = create_goblin(name="Focus Runner", position=(1, 1), faction="heroes")
    hero.register_action(DeployFieldFocus(source_entity_uuid=hero.uuid, template=True))

    actions = get_available_actions(hero)
    action_info = find_action_info(actions, "Deploy Field Focus")
    event = execute_by_index(hero, "Deploy Field Focus", 0, available=actions)

    assert action_info.target_type == TargetType.SELF
    assert action_info.availability_status is (
        ActionAvailabilityStatus.AVAILABLE
    )
    assert action_info.can_afford
    assert action_info.valid_targets[0].index == 0
    assert action_info.cost_type == "bonus_actions"
    assert event is not None
    assert event.phase == EventPhase.COMPLETION
    assert "Field Focus" in hero.active_conditions
    assert hero.action_economy.bonus_actions.normalized_score == 0

    condition_after_execution = "Field Focus" in hero.active_conditions
    bonus_actions_after_execution = hero.action_economy.bonus_actions.normalized_score
    hero.action_economy.reset_all_costs()
    refreshed = get_available_actions(hero)
    refreshed_action = find_action_info(refreshed, "Deploy Field Focus")

    assert refreshed_action.availability_status is (
        ActionAvailabilityStatus.REQUIREMENTS_UNMET
    )
    assert refreshed_action.can_afford
    assert refreshed_action.valid_targets == []

    readout_lines = [
        (
            "discovered action: "
            f"name={action_info.display_name}, "
            f"target={action_info.target_type.value}, "
            f"index={action_info.valid_targets[0].index}, "
            f"cost={action_info.cost_type}"
        ),
        (
            "execution: "
            f"phase={event.phase.value if event else 'none'}, "
            f"condition={condition_after_execution}, "
            f"bonus_actions={bonus_actions_after_execution}"
        ),
        (
            "after refresh: "
            f"action_status={refreshed_action.availability_status.value}, "
            f"executable={bool(refreshed_action.valid_targets)}, "
            f"bonus_actions={hero.action_economy.bonus_actions.normalized_score}"
        ),
    ]
    expected_lines = [
        "discovered action: name=Deploy Field Focus, target=self, index=0, cost=bonus_actions",
        "execution: phase=completion, condition=True, bonus_actions=0",
        "after refresh: action_status=requirements_unmet, executable=False, bonus_actions=1",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_usable_item_packages_the_same_action_template(capsys) -> None:
    """A usable item can expose the custom action through discovery."""
    reset_content_extension_state()
    hero = create_goblin(name="Kit Carrier", position=(1, 1), faction="heroes")
    kit = _materialize_field_kit(hero.uuid)
    loot_result = hero.loot_item(kit)
    assert loot_result

    actions = get_available_actions(hero)
    item_action = find_item_action(actions, "Deploy Field Focus", kit.uuid)
    actions_before = hero.action_economy.actions.normalized_score
    bonus_actions_before = hero.action_economy.bonus_actions.normalized_score
    event = execute_by_index(hero, item_action.template_name, 0, available=actions)

    assert item_action.is_item_use
    assert item_action.source_item_uuid == kit.uuid
    assert item_action.display_name == "Deploy Field Focus (Field Kit)"
    assert isinstance(event, ActionEvent)
    assert event.phase == EventPhase.COMPLETION
    assert event.source_item_uuid == kit.uuid
    assert event.source_item_presentation is not None
    assert event.source_item_presentation.item_uuid == kit.uuid
    assert event.item_charge_cost == 1
    assert kit.charges == 0
    assert hero.action_economy.actions.normalized_score == actions_before
    assert (
        hero.action_economy.bonus_actions.normalized_score
        == bonus_actions_before - 1
    )
    assert "Field Focus" in hero.active_conditions

    refreshed = get_available_actions(hero)

    assert all(info.source_item_uuid != kit.uuid for info in refreshed.self_actions)

    readout_lines = [
        f"carried kit: looted={'yes' if loot_result else 'no'}, item={kit.name}, charges_start=1",
        (
            "item action: "
            f"display={item_action.display_name}, "
            f"is_item={'yes' if item_action.is_item_use else 'no'}, "
            f"source_matches={'yes' if item_action.source_item_uuid == kit.uuid else 'no'}"
        ),
        (
            "after use: "
            f"phase={event.phase.value if event else 'none'}, "
            f"charges={kit.charges}, "
            f"condition={'Field Focus' in hero.active_conditions}"
        ),
        (
            "after refresh: "
            f"item_action_available={any(info.source_item_uuid == kit.uuid for info in refreshed.self_actions)}"
        ),
    ]
    expected_lines = [
        "carried kit: looted=yes, item=Field Kit, charges_start=1",
        "item action: display=Deploy Field Focus (Field Kit), is_item=yes, source_matches=yes",
        "after use: phase=completion, charges=0, condition=True",
        "after refresh: item_action_available=False",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_floor_object_use_action_comes_from_nearby_sensed_item(capsys) -> None:
    """A floor item can expose the custom use action when the actor is nearby."""
    reset_content_extension_state()
    hero = create_goblin(name="Floor Kit User", position=(1, 1), faction="heroes")
    kit = _materialize_field_kit(hero.uuid)
    kit.place_on_grid((1, 2))
    Entity.update_all_entities_senses(max_distance=20)

    actions = get_available_actions(hero)
    item_action = find_item_action(actions, "Deploy Field Focus", kit.uuid)
    actions_before = hero.action_economy.actions.normalized_score
    bonus_actions_before = hero.action_economy.bonus_actions.normalized_score
    event = execute_by_index(hero, item_action.template_name, 0, available=actions)

    assert kit.uuid in hero.senses.objects
    assert item_action.is_item_use
    assert item_action.source_item_uuid == kit.uuid
    assert isinstance(event, ActionEvent)
    assert event.phase == EventPhase.COMPLETION
    assert event.source_item_uuid == kit.uuid
    assert event.source_item_presentation is not None
    assert event.source_item_presentation.item_uuid == kit.uuid
    assert event.item_charge_cost == 1
    assert kit.charges == 0
    assert hero.action_economy.actions.normalized_score == actions_before
    assert (
        hero.action_economy.bonus_actions.normalized_score
        == bonus_actions_before - 1
    )
    assert "Field Focus" in hero.active_conditions

    readout_lines = [
        (
            "floor kit sensed: "
            f"position={kit.position}, "
            f"visible={'yes' if kit.uuid in hero.senses.objects else 'no'}"
        ),
        (
            "floor action: "
            f"display={item_action.display_name}, "
            f"is_item={'yes' if item_action.is_item_use else 'no'}, "
            f"source_matches={'yes' if item_action.source_item_uuid == kit.uuid else 'no'}"
        ),
        (
            "after use: "
            f"phase={event.phase.value if event else 'none'}, "
            f"charges={kit.charges}, "
            f"condition={'Field Focus' in hero.active_conditions}"
        ),
    ]
    expected_lines = [
        "floor kit sensed: position=(1, 2), visible=yes",
        "floor action: display=Deploy Field Focus (Field Kit), is_item=yes, source_matches=yes",
        "after use: phase=completion, charges=0, condition=True",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_actor_and_scene_factories_compose_the_builtin_extension(capsys) -> None:
    """Factory functions can assemble custom content into playable scenes."""
    reset_content_extension_state()
    medic, ally, floor_kit = create_field_training_scene()
    carried_kit = inventory_item_named(medic, "Field Kit")
    actions = get_available_actions(medic)
    actor_action = find_action_info(actions, "Deploy Field Focus")
    inventory_action = find_item_action(actions, "Deploy Field Focus", carried_kit.uuid)
    floor_action = find_item_action(actions, "Deploy Field Focus", floor_kit.uuid)

    assert medic.name == "Field Medic"
    assert ally.name == "Field Ally"
    assert actor_action.display_name == "Deploy Field Focus"
    assert inventory_action.display_name == "Deploy Field Focus (Field Kit)"
    assert floor_action.display_name == "Deploy Field Focus (Field Kit)"
    assert carried_kit.uuid in medic.inventory.items
    assert floor_kit.uuid in medic.senses.objects
    assert floor_kit.position == (1, 2)

    readout_lines = [
        (
            "scene actors: "
            f"medic={medic.name}, "
            f"ally={ally.name}, "
            f"medic_pos={medic.position}, "
            f"ally_pos={ally.position}"
        ),
        (
            "actions: "
            f"actor={actor_action.display_name}, "
            f"carried={inventory_action.display_name}, "
            f"floor={floor_action.display_name}"
        ),
        (
            "kits: "
            f"carried_in_inventory={'yes' if carried_kit.uuid in medic.inventory.items else 'no'}, "
            f"floor_visible={'yes' if floor_kit.uuid in medic.senses.objects else 'no'}, "
            f"floor_pos={floor_kit.position}"
        ),
    ]
    expected_lines = [
        "scene actors: medic=Field Medic, ally=Field Ally, medic_pos=(1, 1), ally_pos=(2, 1)",
        "actions: actor=Deploy Field Focus, carried=Deploy Field Focus (Field Kit), floor=Deploy Field Focus (Field Kit)",
        "kits: carried_in_inventory=yes, floor_visible=yes, floor_pos=(1, 2)",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
