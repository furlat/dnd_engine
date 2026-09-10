"""A public weapon replacement preserves separate roots and retained loadouts."""

from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.equipment import WeaponEquipEvent, WeaponUnequipEvent
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.core.item_types import ItemLocation
from dnd.core.life_types import LifeState
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.world_authoring import project_world_tile
from game.animation import sample_cast
from game.animation_data import load_animation_data, resolve_actor_layers
from game.combat import bind_cast
from game.combat_demo import iter_combat_demo
from game.presentation import CompletedLineage, PresentationTarget, capture_lineage, reduce_lineage, seed_actors


def test_public_weapon_replacement_retains_loadout_and_replays_after_reset() -> None:
    grid = reset_engine_runtime(grid_size=(3, 3))
    actor = Entity.create(uuid4(), "Modular caster", config=EntityConfig(
        position=(1, 1),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=8, mode="maximums",
        )]),
        appearance=AppearanceConfig(
            visual_scale=0.5, body_category="NakedBody", has_beard=False,
        ),
    ))
    dagger = build_authored_item("weapon.dagger", actor.uuid)
    shortsword = build_authored_item("weapon.shortsword", actor.uuid)
    actor.install_initial_items(((dagger, WeaponSlot.MELEE_MAIN), (shortsword, None)))
    birth = actor.compose_entity()
    Game().deploy_entity(actor, (1, 1))
    seed = seed_actors(
        PresentationTarget(
            generation=EventQueue.generation_id(), observer_uuid=actor.uuid,
            tiles={position: project_world_tile(tile) for position, tile in grid.get_all_tiles().items()},
            senses=capture_senses_snapshot(actor.senses),
            reducer_cursor=EventQueue.event_cursor(),
        ),
        (birth,), active_weapon_sets={actor.uuid: actor.equipment.active_weapon_set},
    )
    initial = seed.actors[actor.uuid]
    data = load_animation_data()
    original_layers = resolve_actor_layers(
        data, initial.appearance, initial.items, initial.equipment,
        initial.active_weapon_set, rig_id=data.root_rig,
    )
    assert dict(initial.equipment) == {WeaponSlot.MELEE_MAIN.value: dagger.uuid}
    assert next(layer.category for layer in original_layers if layer.slot == "weapon") == "Melee1"

    start = EventQueue.event_cursor()
    assert actor.equip_item(shortsword.uuid, WeaponSlot.MELEE_MAIN)
    roots = tuple(event for _, event in EventQueue.iter_events_since(start)
                  if event.phase is EventPhase.COMPLETION)
    assert tuple(type(event) for event in roots) == (
        WeaponUnequipEvent, WeaponEquipEvent, ItemLocationStateEvent, ItemLocationStateEvent,
    )
    histories = tuple(capture_lineage(root, observer_uuid=actor.uuid) for root in roots)
    for root, lineage in zip(roots, histories, strict=True):
        assert root.parent_event is None and root.parent_lineage is None
        assert not root.children_lineages
        assert lineage.root.uuid == root.uuid
        assert lineage.root.lineage_uuid == root.lineage_uuid
        assert lineage.root.parent_event is None and lineage.root.parent_lineage is None
        assert not lineage.root.children_lineages
        assert lineage.events == (lineage.root,)
        assert all(row.parent_event is None and row.parent_lineage is None
                   for row in lineage.objective_rows)

    # Independent roots overlap in declaration time but complete in this order.
    unequip, equip, incoming, displaced = histories
    assert unequip.start_cursor < equip.start_cursor < unequip.end_cursor < equip.end_cursor
    assert isinstance(unequip.root, WeaponUnequipEvent)
    assert isinstance(equip.root, WeaponEquipEvent)
    assert (unequip.root.item_uuid, unequip.root.slot) == (dagger.uuid, WeaponSlot.MELEE_MAIN)
    assert (equip.root.item_uuid, equip.root.slot) == (shortsword.uuid, WeaponSlot.MELEE_MAIN)
    incoming_fact, displaced_fact = incoming.root, displaced.root
    assert isinstance(incoming_fact, ItemLocationStateEvent)
    assert isinstance(displaced_fact, ItemLocationStateEvent)
    assert (incoming_fact.item_state.item_uuid, incoming_fact.location,
            incoming_fact.owner_uuid, incoming_fact.equipment_slot) == (
        shortsword.uuid, ItemLocation.EQUIPMENT, actor.uuid, WeaponSlot.MELEE_MAIN,
    )
    assert (displaced_fact.item_state.item_uuid, displaced_fact.location,
            displaced_fact.owner_uuid, displaced_fact.equipment_slot) == (
        dagger.uuid, ItemLocation.INVENTORY, actor.uuid, None,
    )
    states = [seed]
    for lineage in histories:
        states.append(reduce_lineage(states[-1], lineage))
    assert states[1].actors[actor.uuid] == initial
    assert states[2].actors[actor.uuid] == initial
    assert dict(states[3].actors[actor.uuid].equipment) == {
        WeaponSlot.MELEE_MAIN.value: shortsword.uuid,
    }
    latest = states[-1]
    after = latest.actors[actor.uuid]
    assert dict(after.equipment) == {WeaponSlot.MELEE_MAIN.value: shortsword.uuid}
    assert actor.equipment.get_weapon(WeaponSlot.MELEE_MAIN) is shortsword
    assert tuple(actor.inventory.items) == (dagger.uuid,)
    assert {item.item_uuid: item for item in after.items} == {
        item.uuid: item.to_item_presentation_state() for item in (dagger, shortsword)
    }
    assert (after.normal_hp, after.maximum_hp, after.temporary_hp, after.life_state) == (
        initial.normal_hp, initial.maximum_hp, initial.temporary_hp, initial.life_state,
    ) == (80, 80, 0, LifeState.ALIVE)
    assert after.active_weapon_set is initial.active_weapon_set is WeaponSet.MELEE
    assert after.active_weapon_set is actor.equipment.active_weapon_set
    assert seed.actors[actor.uuid] == initial
    assert dict(initial.equipment) == {WeaponSlot.MELEE_MAIN.value: dagger.uuid}
    updated_layers = resolve_actor_layers(
        data, after.appearance, after.items, after.equipment,
        after.active_weapon_set, rig_id=data.root_rig,
    )
    assert next(layer.category for layer in updated_layers if layer.slot == "weapon") == "Melee3"

    reset_engine_runtime()
    replay = seed
    for lineage in histories:
        replay = reduce_lineage(replay, lineage)
    assert replay == latest
    for retained, expected_layers in ((seed, original_layers), (replay, updated_layers)):
        retained_actor = retained.actors[actor.uuid]
        assert resolve_actor_layers(
            data, retained_actor.appearance, retained_actor.items, retained_actor.equipment,
            retained_actor.active_weapon_set, rig_id=data.root_rig,
        ) == expected_layers


def test_public_mixed_history_keeps_first_cast_dagger_while_latest_reaches_shortsword_cast() -> None:
    data = load_animation_data()
    script = iter_combat_demo(replace_weapon=True)
    try:
        seed, first_lineage = next(script), next(script)
        assert isinstance(seed, PresentationTarget)
        assert isinstance(first_lineage, CompletedLineage)
        first = bind_cast(seed, first_lineage, data, travel_apex_steps=1.0)
        sample_times = (0, first.timeline.release_ms, first.timeline.complete_ms)
        original_samples = tuple(sample_cast(first.timeline, elapsed) for elapsed in sample_times)
        remaining: list[CompletedLineage] = []
        for lineage in script:
            assert isinstance(lineage, CompletedLineage)
            remaining.append(lineage)
    finally:
        script.close()

    assert tuple(type(lineage.root) for lineage in remaining) == (
        WeaponUnequipEvent, WeaponEquipEvent, ItemLocationStateEvent, ItemLocationStateEvent, SpellEvent,
    )
    equipment, second_lineage = remaining[:4], remaining[4]
    latest = reduce_lineage(seed, first_lineage)
    for lineage in remaining:
        latest = reduce_lineage(latest, lineage)
    caster_uuid = seed.observer_uuid
    first_actor, latest_actor = seed.actors[caster_uuid], latest.actors[caster_uuid]
    dagger = next(item for item in first_actor.items if item.item_id == "weapon.dagger")
    shortsword = next(item for item in first_actor.items if item.item_id == "weapon.shortsword")
    assert dict(first_actor.equipment) == {WeaponSlot.MELEE_MAIN.value: dagger.item_uuid}
    assert dict(latest_actor.equipment) == {WeaponSlot.MELEE_MAIN.value: shortsword.item_uuid}
    assert first_actor.active_weapon_set is latest_actor.active_weapon_set is WeaponSet.MELEE
    assert latest_actor.normal_hp == first_actor.normal_hp == 80
    assert tuple(sample_cast(first.timeline, elapsed) for elapsed in sample_times) == original_samples

    historical = first.after
    for lineage in equipment:
        historical = reduce_lineage(historical, lineage)
    second = bind_cast(historical, second_lineage, data, travel_apex_steps=1.0)
    assert (first.timeline.source.applications[0].target.hp, first.timeline.source.applications[0].resulting_hp,
            second.timeline.source.applications[0].target.hp, second.timeline.source.applications[0].resulting_hp) == (80, 73, 73, 66)
    assert second.after == latest
    assert tuple(next(layer.category for layer in cast.appearances[str(caster_uuid)]
                      if layer.slot == "weapon") for cast in (first, second)) == ("Melee1", "Melee3")

    reset_engine_runtime()
    replay_first = bind_cast(seed, first_lineage, data, travel_apex_steps=1.0)
    replay = replay_first.after
    for lineage in equipment:
        replay = reduce_lineage(replay, lineage)
    replay_second = bind_cast(replay, second_lineage, data, travel_apex_steps=1.0)
    assert replay_first == first
    assert replay_second == second
    assert tuple(sample_cast(replay_first.timeline, elapsed) for elapsed in sample_times) == original_samples
