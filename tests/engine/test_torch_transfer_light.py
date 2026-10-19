"""Accepted torch transfers move illumination; refused transfers preserve it."""

import pytest

from dnd.actions_functional import execute_use_action
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_storage_chest
from dnd.core.events import EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.types.world import LightLevel
from tests.engine.test_global_native_audit_regressions import combatant
from tests.engine.test_roster_support_spells import game as game


@pytest.mark.parametrize("via_inventory", (False, True))
def test_transferred_torch_light_follows_only_the_accepted_carrier(game, via_inventory):
    grid = get_map()
    grid.create_rectangle(0, 0, 40, 5, default_light=LightLevel.DARKNESS)
    first = combatant(game)
    second = combatant(game, "New holder", (15, 2))
    torch = build_authored_item("equipment.portable_torch", first.uuid)
    assert first.loot_item(torch)
    use_name = torch.get_use_actions(first.uuid)[0].get_discovery_template_name()
    result = execute_use_action(first, torch.uuid, use_name)
    assert result is not None and not result.canceled
    flames_before = len(EventQueue.get_events_by_type(EventType.EXPOSED_FLAME_IGNITED))

    second.inventory.max_slots = 0
    accepted = (first.inventory.transfer_to(torch.uuid, second.inventory) if via_inventory
                else second.loot_item(torch))
    assert not accepted and torch.owner_uuid == first.uuid
    assert grid.get_tile(2, 2).resolved_light_level is LightLevel.VERY_BRIGHT
    assert grid.get_tile(15, 2).resolved_light_level is LightLevel.DARKNESS

    second.inventory.max_slots = None
    accepted = (first.inventory.transfer_to(torch.uuid, second.inventory) if via_inventory
                else second.loot_item(torch))
    assert accepted and torch.owner_uuid == second.uuid and torch.is_lit
    assert grid.get_tile(2, 2).resolved_light_level is LightLevel.DARKNESS
    assert grid.get_tile(15, 2).resolved_light_level is LightLevel.VERY_BRIGHT
    assert len(EventQueue.get_events_by_type(EventType.EXPOSED_FLAME_IGNITED)) == flames_before

    Entity.update_entity_position(first, (3, 2))
    Entity.update_entity_position(second, (35, 2))
    assert grid.get_tile(3, 2).resolved_light_level is LightLevel.DARKNESS
    assert grid.get_tile(15, 2).resolved_light_level is LightLevel.DARKNESS
    assert grid.get_tile(35, 2).resolved_light_level is LightLevel.VERY_BRIGHT


def test_storing_a_lit_torch_releases_the_old_carrier_light(game):
    grid = get_map()
    grid.create_rectangle(0, 0, 20, 5, default_light=LightLevel.DARKNESS)
    actor = combatant(game)
    chest = build_storage_chest("Torch storage", include_loot_all_action=False)
    chest.chest_inventory.source_entity_uuid = chest.uuid
    chest.place_on_grid((3, 2))
    torch = build_authored_item("equipment.portable_torch", actor.uuid)
    assert actor.loot_item(torch)
    use_name = torch.get_use_actions(actor.uuid)[0].get_discovery_template_name()
    result = execute_use_action(actor, torch.uuid, use_name)
    assert result is not None and not result.canceled
    assert grid.get_tile(2, 2).resolved_light_level is LightLevel.VERY_BRIGHT

    assert actor.inventory.transfer_to(torch.uuid, chest.chest_inventory)
    assert torch.owner_uuid == chest.uuid
    assert grid.get_tile(2, 2).resolved_light_level is LightLevel.DARKNESS
    assert not torch.is_lit
