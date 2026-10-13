"""Player aims stay exact while effects are computed only for a selected preview.

Boundary: native discovery/selection/command. Small placed caster scenes exercise
rich/deferred options, subjective previews and native execution without preview.
"""

import pytest
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import (
    execute_available_action, get_available_actions, preview_available_selection,
    register_spell, setup_standard_actions,
)
from dnd.core.aoe import (
    Cone, Cube, Cylinder, Line, Sphere, snapshot_aoe_aiming_geometry,
)
from dnd.content.items.environment_item_builders import build_spell_device
from dnd.core.base_actions import TargetType
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.items.spell_items import build_fireball_scroll
from dnd.items.consumables import build_healing_potion
from dnd.spells.conjuration import CallLightning
from dnd.spells.evocation import BurningHands, Fireball, IceStorm
from tests.manual.spell_regression_support import (
    create_spell_regression_actor, force_save_result, reset_spell_regression_arena,
)


@pytest.fixture
def scene():
    reset_spell_regression_arena(12, 10)
    caster = create_spell_regression_actor("Caster", (2, 4), "heroes",
        spell_slots={1: 3, 2: 2, 3: 2, 4: 2})
    enemy = create_spell_regression_actor("Enemy", (6, 4), "monsters")
    ally = create_spell_regression_actor("Ally", (6, 5), "heroes")
    yield caster, enemy, ally
    reset_engine_runtime()


def area_rows(result, name):
    return [row for row in result.position_actions
        if row.target_type is TargetType.POSITION_AOE
        and row.template_name.split("__slot_", 1)[0] == name]


def admission(rows):
    return [(row.template_name, row.availability_status, row.can_afford,
        tuple(cost.model_dump_json() for cost in row.costs),
        [(target.index, target.position, target.distance) for target in row.valid_targets])
        for row in rows]


@pytest.mark.parametrize("spell,name", [
    (Fireball, "Fireball"), (BurningHands, "Burning Hands"),
    (IceStorm, "Ice Storm"), (CallLightning, "Call Lightning"),
])
@pytest.mark.parametrize("deferred_first", [False, True])
def test_rich_and_deferred_discovery_keep_exact_aims_and_default_details(
    scene, spell, name, deferred_first,
):
    caster, _, _ = scene
    register_spell(caster, spell)
    Entity.update_all_entities_senses(max_distance=120)
    cursor = EventQueue.event_cursor()
    first = get_available_actions(caster, include_aoe_preview=not deferred_first)
    second = get_available_actions(caster, include_aoe_preview=deferred_first)
    rich, bare = (second, first) if deferred_first else (first, second)
    rich_rows, bare_rows = area_rows(rich, name), area_rows(bare, name)
    assert rich_rows and bare_rows
    assert admission(rich_rows) == admission(bare_rows)
    assert all(target.affected_positions is not None
        for row in rich_rows for target in row.valid_targets)
    assert all(target.affected_positions is None
        and target.affected_entity_uuids is None and target.affected_count is None
        for row in bare_rows for target in row.valid_targets)
    again = area_rows(get_available_actions(caster), name)
    assert [row.model_dump() for row in again] == [row.model_dump() for row in rich_rows]
    assert EventQueue.event_cursor() == cursor


@pytest.mark.parametrize("spell,name", [(Fireball, "Fireball"), (IceStorm, "Ice Storm")])
def test_selected_subjective_preview_matches_rich_cells_and_recipients(scene, spell, name):
    caster, enemy, ally = scene
    hidden = create_spell_regression_actor("Hidden", (8, 4), "monsters")
    hidden.set_stealth_dc(100)
    get_map().set_tile(7, 4, blocks_optics=True, blocks_propagation=True)
    register_spell(caster, spell)
    Entity.update_all_entities_senses(max_distance=120)
    assert hidden.uuid not in caster.senses.entities
    rich = area_rows(get_available_actions(caster), name)[0]
    bare = area_rows(get_available_actions(caster, include_aoe_preview=False), name)[0]
    expected = next(target for target in rich.valid_targets if target.position == enemy.position)
    selected = next(target for target in bare.valid_targets if target.index == expected.index)
    cursor = EventQueue.event_cursor()
    status = preview_available_selection(caster, bare, (selected,), include_aoe_effects=False)
    assert status.can_confirm and status.area_preview == "deferred"
    assert status.affected_positions == () and status.affected_entity_uuids == ()
    preview = preview_available_selection(caster, bare, (selected,))
    assert preview.can_confirm and preview.area_preview == "computed"
    assert preview.affected_positions == tuple(expected.affected_positions)
    assert preview.affected_entity_uuids == tuple(expected.affected_entity_uuids)
    assert preview.affected_entity_names == tuple(expected.affected_entity_names)
    assert {enemy.uuid, ally.uuid} <= set(preview.affected_entity_uuids)
    assert hidden.uuid not in preview.affected_entity_uuids
    assert set(preview.affected_positions) <= {p for p, visible in caster.senses.visible.items() if visible}
    assert preview.geometry is not None
    assert selected.affected_positions is None
    assert (selected.index, selected.position, selected.distance) == (
        expected.index, expected.position, expected.distance)
    assert EventQueue.event_cursor() == cursor


def test_empty_selected_blast_is_computed_and_required_targets_still_gate_aims(scene):
    caster, _, _ = scene
    register_spell(caster, Fireball)
    Entity.update_all_entities_senses(max_distance=120)
    bare = area_rows(get_available_actions(caster, include_aoe_preview=False), "Fireball")[0]
    empty = next(target for target in bare.valid_targets if target.position == (11, 9))
    preview = preview_available_selection(caster, bare, (empty,))
    assert preview.can_confirm and preview.area_preview == "computed"
    assert preview.affected_entity_uuids == () and preview.affected_entity_names == ()
    template = caster.get_action_template("Fireball")
    assert template is not None
    template.aoe_require_targets = True
    rich = area_rows(get_available_actions(caster), "Fireball")
    required = area_rows(get_available_actions(caster, include_aoe_preview=False), "Fireball")
    assert [row.model_dump() for row in required] == [row.model_dump() for row in rich]
    assert not any(target.position == empty.position for row in required for target in row.valid_targets)


def test_item_area_aims_keep_details_optional_and_execute_without_preview(scene):
    caster, enemy, _ = scene
    scroll = build_fireball_scroll(caster.uuid)
    assert caster.loot_item(scroll)
    force_save_result(enemy, "dexterity", succeeds=False)
    Entity.update_all_entities_senses(max_distance=120)
    rich = next(row for row in get_available_actions(caster).position_actions
        if row.source_item_uuid == scroll.uuid)
    bare = next(row for row in get_available_actions(caster, include_aoe_preview=False).position_actions
        if row.source_item_uuid == scroll.uuid)
    assert admission([rich]) == admission([bare])
    target = next(target for target in bare.valid_targets if target.position == enemy.position)
    assert target.affected_positions is None
    hp = enemy.get_normal_hp()
    with fixed_dice_faces(*([2] * 100)):
        result = execute_available_action(caster, bare, target)
    assert isinstance(result, SpellEvent) and not result.canceled
    assert enemy.get_normal_hp() < hp


def test_item_area_range_origin_and_firing_sector_survive_deferred_discovery(scene):
    caster, _, _ = scene
    device = build_spell_device(item_id="environment.fireball_cannon", name="Short-range cannon",
        scroll_cast_level=3, spell_templates=[Fireball(source_entity_uuid=caster.uuid,
            template=True, cast_origin="source_item", alt_range=5, target_sector_degrees=45)])
    device.place_on_grid((3, 4))
    Entity.update_all_entities_senses(max_distance=120)
    rich = next(row for row in get_available_actions(caster).position_actions
        if row.source_item_uuid == device.uuid)
    bare = next(row for row in get_available_actions(caster, include_aoe_preview=False).position_actions
        if row.source_item_uuid == device.uuid)
    assert admission([rich]) == admission([bare])
    selected = next(target for target in bare.valid_targets if target.position == (4, 4))
    assert selected.distance == 5
    assert not any(target.position == (3, 5) for target in bare.valid_targets)
    assert bare.execution_template.get_target_origin() == device.position
    preview = preview_available_selection(caster, bare, (selected,))
    assert preview.can_confirm and preview.area_preview == "computed"
    assert preview.geometry.shape == "sphere" and preview.geometry.center == selected.position


@pytest.mark.parametrize("item_use", [False, True])
@pytest.mark.parametrize("include_dead", [False, True])
def test_selected_area_preserves_zero_hp_query_policy(scene, item_use, include_dead):
    caster, enemy, _ = scene
    enemy.uses_death_saves = True
    enemy.receive_damage(enemy.get_normal_hp(), DamageType.FORCE, caster.uuid)
    assert enemy.get_normal_hp() == 0
    if item_use:
        scroll = build_fireball_scroll(caster.uuid)
        assert caster.loot_item(scroll)
        source_item_uuid = scroll.uuid
    else:
        register_spell(caster, Fireball)
        source_item_uuid = None
    Entity.update_all_entities_senses(max_distance=120)
    assert enemy.uuid in caster.senses.entities
    rich = next(row for row in caster.get_available_actions(
        include_dead=include_dead).position_actions
        if row.target_type is TargetType.POSITION_AOE and row.source_item_uuid == source_item_uuid)
    bare = next(row for row in caster.get_available_actions(
        include_dead=include_dead, include_aoe_preview=False).position_actions
        if row.target_type is TargetType.POSITION_AOE and row.source_item_uuid == source_item_uuid)
    expected = next(target for target in rich.valid_targets if target.position == enemy.position)
    # A detached row retains its own query policy after a later, opposite query.
    retained = bare.model_copy(update={"valid_targets": [
        target.model_copy(deep=True) for target in bare.valid_targets]})
    caster.get_available_actions(include_dead=not include_dead, include_aoe_preview=False)
    selected = next(target for target in retained.valid_targets if target.index == expected.index)
    cursor = EventQueue.event_cursor()
    preview = preview_available_selection(caster, retained, (selected,))
    assert preview.can_confirm and preview.area_preview == "computed"
    assert preview.affected_positions == tuple(expected.affected_positions)
    assert preview.affected_entity_uuids == tuple(expected.affected_entity_uuids)
    assert preview.affected_entity_names == tuple(expected.affected_entity_names)
    assert (enemy.uuid in preview.affected_entity_uuids) is include_dead
    assert EventQueue.event_cursor() == cursor


def test_native_object_choices_identify_the_item_as_an_object(scene):
    caster, _, _ = scene
    setup_standard_actions(caster)
    potion = build_healing_potion(caster.uuid)
    potion.place_on_grid((3, 4))
    Entity.update_all_entities_senses(max_distance=120)
    offered = [target for action in get_available_actions(caster, include_aoe_preview=False).object_actions
        for target in action.valid_targets if target.target_uuid == potion.uuid]
    assert offered and all(target.target_kind == "object" for target in offered)


@pytest.mark.parametrize("shape,mode", [
    (Sphere(source_entity_uuid=uuid4(), target=(6, 4)), "aim"),
    (Cylinder(source_entity_uuid=uuid4(), target=(6, 4)), "aim"),
    (Cube(source_entity_uuid=uuid4(), target=(6, 4), centered=True), "aim"),
    (Cone(source_entity_uuid=uuid4(), target=(6, 4)), "fixed"),
    (Line(source_entity_uuid=uuid4(), target=(6, 4)), "fixed"),
    (Cube(source_entity_uuid=uuid4(), target=(6, 4), centered=False), "fixed"),
    (Sphere(source_entity_uuid=uuid4(), target=(6, 4), origin_override=(3, 4), propagation="connected"), "fixed"),
])
def test_native_aiming_descriptor_preserves_shape_origin_and_propagation(shape, mode):
    descriptor = snapshot_aoe_aiming_geometry(shape, (2, 4))
    assert descriptor is not None
    assert descriptor.reference_target == shape.target and descriptor.origin_mode == mode
    assert descriptor.propagation == shape.propagation
    assert shape.computed_origin is None and not shape.affected_positions
