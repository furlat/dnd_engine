"""Export the complete authoring view, not a private gameplay recording.

Uses existing player values for Studio input. The single initial sensory row
explicitly exposes the whole authored map; it is never served to a player seat.
"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

from dnd.core.gridmap import get_map
from dnd.scenarios.battlefield_catalog import build_battlefield, _world_initialized_event
from dnd.player.audience import PlayerAudience
from dnd.player.facts import (
    PlayerInitialization, PlayerNode, PlayerObject, PlayerSequence, PlayerWorld,
    SensoryFact, VersionRow, WorldUpdate,
)
from dnd.player.projection import _floor_item
from dnd.player.reduction import encode_player_sequence
from dnd.types.event_facts import EventPhase
from dnd.types.senses import PerceivedContact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--battlefield", default="battlefield.lantern_crypt")
    args = parser.parse_args()
    built = build_battlefield(args.battlefield)
    grid = get_map()
    world = _world_initialized_event(built, grid)
    tiles = world.tiles
    objects = tuple(PlayerObject(placement=o.placement, item=_floor_item(o.item, ())) for o in world.objects)
    observer, event, lineage, generation = uuid4(), uuid4(), uuid4(), uuid4()
    positions = tuple(t.position for t in tiles)
    sensory = SensoryFact(observer_uuid=observer, initial=True, observer_position=positions[0],
        observer_position_changed=True, effective_light_levels_changed={f"{x},{y}": 3 for x, y in positions},
        cause_event_uuid=None, visible_cells_added=positions, visible_cells_removed=(), seen_cells_added=positions,
        entity_contacts_changed={}, entity_contacts_removed=frozenset(),
        object_contacts_changed={o.item.item_uuid: PerceivedContact(position=o.placement.position, visual=True) for o in objects},
        object_contacts_removed=frozenset(), sense_modes_changed=True, sense_modes=(),
        passive_perception_changed=True, passive_perception=0, visual_access_changed=True, visual_access=1, paths_dirty=False)
    sequence = PlayerSequence(initialization=PlayerInitialization(generation=generation, observer_uuid=observer,
        world=PlayerWorld(battlefield_id=world.battlefield_id, battlefield_name=world.battlefield_name,
                          bounds=world.bounds, width=world.width, height=world.height),
        nodes=(PlayerNode(uuid=event, lineage_uuid=lineage, parent_event=None, parent_lineage=None,
                          children_lineages=(), phase=EventPhase.COMPLETION, canceled=False, fact=sensory),),
        version_rows=(VersionRow(source_index=0, event_uuid=event, lineage_uuid=lineage),), end_cursor=0,
        observations=(), world_updates=(WorldUpdate(event_uuid=event, tiles=tiles, objects=objects,
                                                   objects_removed=(), connectors=world.connectors),),
        audience=PlayerAudience(controlled=(), observers=(observer,), revision=0)), lineages=())
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
