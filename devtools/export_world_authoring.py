"""Export the complete authoring view, not a private gameplay recording.

Uses existing player values for Studio input. The single initial sensory row
explicitly exposes the whole authored map; it is never served to a player seat.
"""
import argparse
import json
from dnd.core.cells import flag_bits, mask_from_positions, shared_cells, shared_values, values_from_items
from pathlib import Path
from uuid import uuid4

from dnd.core.gridmap import get_map
from dnd.scenarios.battlefield_catalog import build_battlefield, _world_initialized_event
from dnd.player.audience import AudiencePerception, PlayerAudience
from dnd.player.facts import (
    PlayerInitialization, PlayerNode, PlayerSequence, PlayerWorld,
    SensoryFact, SensoryRows, VersionRows,
)
from dnd.player.reduction import encode_player_sequence
from dnd.player.world_stamps import SeatStamps, WorldDigests, WorldStamps
from dnd.player.static_sent import StaticSent
from dnd.player.world_publication import seat_world_update
from dnd.types.cells import EMPTY_CELLS
from dnd.types.event_facts import EventPhase
from dnd.types.senses import PerceivedContact, SensesSnapshot
from dnd.world_facts import WorldFacts, apply_world_fact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--battlefield", default="battlefield.lantern_crypt")
    args = parser.parse_args()
    built = build_battlefield(args.battlefield)
    grid = get_map()
    world = _world_initialized_event(built, grid)
    tiles = world.tiles
    objects = world.objects
    observer, generation = uuid4(), uuid4()
    positions = tuple(t.position for t in tiles)
    audience = PlayerAudience(controlled=(), observers=(observer,), revision=0)
    # The authored world entering a view of every cell, with every object in contact: the seats' one path.
    authored = WorldFacts()
    apply_world_fact(authored, world)
    view = SensesSnapshot(position=positions[0], visible=mask_from_positions(positions),
        seen=mask_from_positions(positions), entities={},
        objects={o.item.item_uuid: PerceivedContact(position=o.placement.position, visual=True) for o in objects},
        effective_light_levels=values_from_items({position: 3 for position in positions}), paths_dirty=False,
        passive_perception=0, sense_modes_hash=0, sense_modes=(), visual_access=1)
    update = seat_world_update(authored, 0, (), EMPTY_CELLS, view, AudiencePerception(members={observer: view}),
        audience, None, observed=set(), granted=set(), sent=StaticSent(), pending=StaticSent(),
        digests=WorldDigests(), stamps=SeatStamps(WorldStamps()))
    cells, (visible, seen) = shared_cells((mask_from_positions(positions), mask_from_positions(positions)))
    light_levels, (light,) = shared_values((values_from_items({position: 3 for position in positions}),))
    rows = SensoryRows(uuids=(observer, *(o.item.item_uuid for o in objects)),
        contact_uuid_index=tuple(range(1, len(objects) + 1)),
        contact_positions=tuple(o.placement.position for o in objects), contact_visual=flag_bits([True] * len(objects)),
        cells=cells, light_levels=light_levels)
    sensory = SensoryFact(observer=0, initial=True, observer_position=positions[0],
        observer_position_changed=True, effective_light_levels_changed=light,
        cause_occurrence=None, visible_cells_added=visible, seen_cells_added=seen,
        object_contacts_changed=tuple(range(len(objects))), sense_modes_changed=True, sense_modes=(),
        passive_perception_changed=True, passive_perception=0, visual_access_changed=True, visual_access=1, paths_dirty=False)
    sequence = PlayerSequence(initialization=PlayerInitialization(generation=generation, observer_uuid=observer,
        world=PlayerWorld(battlefield_id=world.battlefield_id, battlefield_name=world.battlefield_name,
                          bounds=world.bounds, width=world.width, height=world.height),
        nodes=(PlayerNode(occurrence=0, lineage=0, parent_event=None, parent_lineage=None,
                          children_lineages=(), phase=EventPhase.COMPLETION, canceled=False, fact=sensory),),
        version_rows=VersionRows(occurrences=(0,), lineages=(0,)), end_cursor=0,
        observations=(), world_updates=(update,) if update is not None else (),
        audience=audience, sensory_rows=rows), lineages=())
    args.output.mkdir(parents=True, exist_ok=True)
    name = args.battlefield.removeprefix("battlefield.").replace("_", "-") + "-authoring"
    (args.output / f"{name}.json").write_bytes(encode_player_sequence(sequence))
    index = args.output / "index.json"
    entries = json.loads(index.read_text()) if index.exists() else []
    entries = [e for e in entries if e["id"] != name]
    entries.insert(0, dict(id=name, title=f"{world.battlefield_name} · complete authoring view", path=f"{name}.json", tags=["authoring"]))
    index.write_text(json.dumps(entries, indent=2) + "\n")
    print(f"{world.battlefield_name}: {len(tiles)} native supports, {len(objects)} native objects; complete authoring view.")


if __name__ == "__main__":
    main()
