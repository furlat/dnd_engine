"""Compact domains preserve native primary branches and ordered continuations."""

import pytest

from dnd.actions_functional import get_available_actions, preview_available_selection, register_spell
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.entity import Entity
from dnd.player.choice_projection import project_choices, project_selection_preview
from dnd.player.choices import PlayerChoices, PlayerSelectionPreview
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import ChainLightning, MagicMissile
from dnd.spells.transmutation import Telekinesis
from dnd.spells.walls import WallOfFire
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena
from tests.player.test_compact_choices import native_value


@pytest.fixture
def scene():
    reset_spell_regression_arena(40, 12)
    caster = create_spell_regression_actor('Caster', (2, 5), 'heroes', spell_slots={1: 2, 4: 2, 5: 2, 6: 2})
    recipients = [create_spell_regression_actor(name, pos, 'monsters') for name, pos in
        [('Near', (8, 5)), ('Far', (30, 5)), ('Beyond primary range', (35, 5))]]
    item = build_authored_item('environment.furniture.clay_stove', caster.uuid)
    item.place_on_grid((9, 7))
    yield caster, recipients, item
    reset_engine_runtime()


def discover(scene, spell, behavior):
    caster, _, _ = scene
    register_spell(caster, spell)
    Entity.update_all_entities_senses(max_distance=300)
    native = get_available_actions(caster, include_aoe_preview=False)
    compact = PlayerChoices.model_validate_json(project_choices(native, caster.position).model_dump_json())
    native_row = next(row for row in native.all_actions if row.behavior_id == behavior)
    compact_row = next(row for row in (*compact.entity_actions, *compact.position_actions)
        if row.template_name == native_row.template_name)
    assert [native_value(compact, binding) for binding in compact.target_sets[compact_row.target_set]] == [
        target.model_dump() for target in native_row.valid_targets]
    return native_row, compact_row, compact


def test_chain_primary_scoped_branch_keeps_distant_recipient_and_object_identity(scene):
    _, (_, far, beyond), item = scene
    native, row, compact = discover(scene, ChainLightning, 'spell.chain_lightning')
    primary = compact.target_sets[row.target_set]
    assert beyond.uuid not in {compact.subjects[binding.subject].uuid for binding in primary}
    far_binding = next(binding for binding in primary if compact.subjects[binding.subject].uuid == far.uuid)
    # Secondaries are picked on demand (plan §14.4): the selected primary's preview offers
    # the distant recipient the caster perceives, though it is no primary itself.
    object_binding = next(binding for binding in primary if compact.subjects[binding.subject].uuid == item.uuid)
    assert compact.subjects[object_binding.subject].kind == 'object'
    caster = scene[0]
    native_primary = next(target for target in native.valid_targets if target.index == far_binding.index)
    expected = preview_available_selection(caster, native, (native_primary,))
    preview = PlayerSelectionPreview.model_validate_json(project_selection_preview(expected).model_dump_json())
    assert [native_value(preview, target) for target in preview.target_sets[preview.next_target_set]] == [
        target.model_dump() for target in expected.next_targets]
    assert beyond.uuid in {target.target_uuid for target in expected.next_targets}


def test_repeated_missiles_preserve_fill_primary_and_ordered_preview(scene):
    caster, (near, _, _), _ = scene
    native, row, compact = discover(scene, MagicMissile, 'spell.magic_missile')
    selected = next(target for target in native.valid_targets if target.target_uuid == near.uuid)
    assert row.allocation_completion == 'fill_primary' and row.allow_same_target
    prefix = (selected, selected)
    expected = preview_available_selection(caster, native, prefix)
    preview = PlayerSelectionPreview.model_validate_json(project_selection_preview(expected).model_dump_json())
    assert preview.can_confirm
    assert preview.effective_target_uuids == expected.effective_target_uuids
    assert preview.effective_target_uuids.count(near.uuid) == row.num_projectiles


@pytest.mark.parametrize('spell,behavior', [(WallOfFire, 'spell.wall_of_fire'), (Telekinesis, 'spell.telekinesis')])
def test_ordered_position_preview_uses_its_own_coordinates(scene, spell, behavior):
    caster, (near, _, _), _ = scene
    near.faction = caster.faction
    native, row, compact = discover(scene, spell, behavior)
    selected = native.valid_targets[0]
    expected = preview_available_selection(caster, native, (selected,))
    assert expected.next_positions
    preview = PlayerSelectionPreview.model_validate_json(project_selection_preview(expected).model_dump_json())
    assert tuple(preview.positions[index] for index in preview.next_positions) == expected.next_positions
    assert preview.can_confirm == expected.can_confirm
    endpoint = expected.next_positions[0]
    complete = preview_available_selection(caster, native, (selected,), (endpoint,))
    wire_complete = project_selection_preview(complete)
    assert wire_complete.can_confirm == complete.can_confirm
    assert tuple(wire_complete.positions[index] for index in wire_complete.next_positions) == complete.next_positions
