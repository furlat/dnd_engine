"""Golden vectors of the schema-16 sensory client fold (EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §3.1, §3.2).

A vector is a seat's audience and a sequence of received groups, each one composed `SensoryFact` with its group's
`SensoryRows`, together with the client state expected after each group. The expected states are written here by
hand from the client's rules, never dumped from the fold:

- the seat perceives exactly what the facts say: composed cells, contacts and effects with the members perceiving
  each row, light sources, and the anchor member's scalars (a scalar left out keeps its value);
- seen cells are every cell the seat has seen visible;
- an effect's cells that leave its visible part are remembered with the effect as last perceived. A remembered cell
  is forgotten when it is perceived again, when a member saw the effect leave it (retired cells), or, for an
  apparent effect, when the cell is seen without it. A concealed effect's cell seen by a member that never found it
  stays remembered;
- light sources and contacts are not remembered.

The files are what Godot folds too (`sdk/protocol/fold-vectors/sensory/*.json`); `tests/player/test_client_fold_vectors.py`
folds them with the reference fold (`dnd.player.reduction.fold_composed_sensory`).

    PYTHONPATH=. python devtools/fold_vectors_sensory.py   # write the files (the vector test checks they are current)
"""

import argparse
from dataclasses import dataclass, field
from typing import Any
import json
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter

from dnd.core.cells import (flag_bits, mask_from_positions, shared_cells, shared_values, values_from_items,
    zeros_left_out)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.player.facts import (LightChanges, LightPatch, LightRow, SensoryFact, SensoryRows, SpatialEffectContent,
    SpatialEffectPatch, SpatialEffectSighting)
from dnd.types.senses import SenseMode, SensesType
from dnd.types.traps import TrapState

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "sdk" / "protocol" / "fold-vectors" / "sensory"
ROWS = TypeAdapter(SensoryRows)
FACT = TypeAdapter(SensoryFact)

Position = tuple[int, int]
A, B = UUID("00000000-0000-4000-8000-00000000000a"), UUID("00000000-0000-4000-8000-00000000000b")
GOBLIN, CHEST = UUID("00000000-0000-4000-8000-000000001001"), UUID("00000000-0000-4000-8000-000000002001")
FOG, TRAP = UUID("00000000-0000-4000-8000-000000003001"), UUID("00000000-0000-4000-8000-000000003002")
TORCH = UUID("00000000-0000-4000-8000-000000004001")
DARKVISION = SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)


def _content(name: str) -> SpatialEffectContent:
    return SpatialEffectContent(content_ref=ContentRef(pack_id="test.fold_vectors",
        definition_kind=ContentDefinitionKind.CONDITION, content_id=f"condition.fold_vectors.{name}",
        content_version=1, definition_contract_hash="0" * 64), name=name.title(), description=f"A {name}.")


@dataclass(frozen=True)
class Contact:
    identity: UUID
    position: Position
    visual: bool = True
    members: int = 1
    is_object: bool = False


@dataclass(frozen=True)
class Light:
    identity: UUID
    position: Position
    bright: int = 20
    dim: int = 40
    anchor_entity: UUID | None = None


@dataclass
class Step:
    """One received group: its composed fact's values (by identity) and the client state expected after it."""

    expected: dict
    initial: bool = False
    position: Position | None = None
    added: tuple[Position, ...] = ()
    removed: tuple[Position, ...] = ()
    light: dict[Position, int] = field(default_factory=dict)
    hazard: dict[Position, int] = field(default_factory=dict)
    passive: int | None = None
    visual_access: int | None = None
    sense_modes: tuple[SenseMode, ...] | None = None
    paths_dirty: bool = False
    contacts: tuple[Contact, ...] = ()
    contacts_removed: tuple[tuple[UUID, bool], ...] = ()
    effects_added: tuple[tuple[UUID, SpatialEffectSighting, int], ...] = ()
    content: dict[UUID, SpatialEffectContent] = field(default_factory=dict)
    patches: tuple[tuple[UUID, SpatialEffectPatch], ...] = ()
    effects_removed: tuple[UUID, ...] = ()
    retired: tuple[tuple[UUID, tuple[Position, ...]], ...] = ()
    lights_added: tuple[Light, ...] = ()
    light_patches: tuple[tuple[UUID, dict], ...] = ()
    lights_removed: tuple[UUID, ...] = ()


def _group(step: Step, several: bool) -> tuple[SensoryRows, SensoryFact]:
    """The group a projector would send for this step: its rows (each value once) and its one composed fact."""
    uuids: dict[UUID, int] = {}

    def uuid(identity: UUID) -> int:
        return uuids.setdefault(identity, len(uuids))

    added, removed = mask_from_positions(step.added), mask_from_positions(step.removed)
    cells, (added_bits, removed_bits) = shared_cells([added, removed])
    light_tables, (light_bits,) = shared_values([zeros_left_out(values_from_items(step.light), added)])
    hazard_tables, (hazard_bits,) = shared_values([zeros_left_out(values_from_items(step.hazard), added)])
    contact_index = [uuid(row.identity) for row in step.contacts]
    entity_removed = tuple(uuid(identity) for identity, is_object in step.contacts_removed if not is_object)
    object_removed = tuple(uuid(identity) for identity, is_object in step.contacts_removed if is_object)
    sightings = [uuid(identity) for identity, _, _ in step.effects_added]
    patches = [uuid(identity) for identity, _ in step.patches]
    effects_removed = tuple(uuid(identity) for identity in step.effects_removed)
    retired = [uuid(identity) for identity, _ in step.retired]

    def light_row(row: Light) -> LightRow:
        return LightRow(source=uuid(row.identity), position=row.position, very_bright_radius_feet=0,
            bright_radius_feet=row.bright, dim_radius_feet=row.dim, appearance="torch",
            anchor_entity=uuid(row.anchor_entity) if row.anchor_entity is not None else None)

    def light_patch(identity: UUID, changes: dict) -> LightPatch:
        resolved: LightChanges = {}
        if "position" in changes:
            resolved["position"] = changes["position"]
        if "anchor_entity" in changes:
            resolved["anchor_entity"] = uuid(changes["anchor_entity"]) if changes["anchor_entity"] is not None else None
        return LightPatch(source=uuid(identity), changes=resolved)
    lights = tuple(light_row(row) for row in step.lights_added)
    light_patches = tuple(light_patch(identity, changes) for identity, changes in step.light_patches)
    lights_removed = tuple(uuid(identity) for identity in step.lights_removed)
    rows = SensoryRows(uuids=tuple(uuids), contact_uuid_index=tuple(contact_index),
        contact_positions=tuple(row.position for row in step.contacts),
        contact_visual=flag_bits([row.visual for row in step.contacts]),
        contact_members=tuple(row.members for row in step.contacts) if several else (),
        sighting_uuid_index=tuple(sightings), sightings=tuple(sighting for _, sighting, _ in step.effects_added),
        sighting_members=tuple(members for _, _, members in step.effects_added) if several else (),
        patch_uuid_index=tuple(patches), sighting_patches=tuple(patch for _, patch in step.patches),
        retired_uuid_index=tuple(retired), retired_cells=tuple(mask_from_positions(cells) for _, cells in step.retired),
        light_sources=lights, light_patches=light_patches, cells=cells, light_levels=light_tables,
        hazards=hazard_tables)
    entities = tuple(index for index, row in enumerate(step.contacts) if not row.is_object)
    objects = tuple(index for index, row in enumerate(step.contacts) if row.is_object)
    fact = SensoryFact(initial=step.initial, observer_position=step.position,
        visible_cells_added=added_bits, visible_cells_removed=removed_bits,
        effective_light_levels_changed=light_bits, hazardous_cells_changed=hazard_bits,
        entity_contacts_changed=entities, entity_contacts_removed=entity_removed,
        object_contacts_changed=objects, object_contacts_removed=object_removed,
        sense_modes_changed=step.sense_modes is not None, sense_modes=step.sense_modes,
        passive_perception_changed=step.passive is not None, passive_perception=step.passive,
        visual_access_changed=step.visual_access is not None, visual_access=step.visual_access,
        paths_dirty=step.paths_dirty,
        spatial_effects_added=tuple(range(len(sightings))), spatial_effects_patched=tuple(range(len(patches))),
        spatial_effects_removed=effects_removed, spatial_effect_cells_retired=tuple(range(len(retired))),
        spatial_effect_content=step.content, light_sources_added=tuple(range(len(lights))),
        light_sources_patched=tuple(range(len(light_patches))), light_sources_removed=lights_removed)
    return rows, fact



def _cells(*positions: Position) -> list[list[int]]:
    return [list(position) for position in sorted(positions)]


def _lit(level: int, *positions: Position) -> dict[str, int]:
    return {f"{x},{y}": level for x, y in positions}


def expect(*, visible: tuple[Position, ...], seen: tuple[Position, ...], light: dict[str, int], position: Position,
           passive: int = 12, visual_access: int = 1, sense_modes: tuple[tuple[str, int], ...] = (("Darkvision", 60),),
           paths_dirty: bool = False, hazard: dict[str, int] | None = None, entities: dict | None = None,
           objects: dict | None = None, effects: dict | None = None, remembered: dict | None = None,
           lights: dict | None = None) -> dict:
    """The client state after a step, as the runner reads it (`client_sensory_view`)."""
    return {"visible": _cells(*visible), "seen": _cells(*seen), "light": light, "hazard": hazard or {},
            "position": list(position), "passive_perception": passive, "visual_access": visual_access,
            "sense_modes": [list(mode) for mode in sense_modes], "paths_dirty": paths_dirty,
            "entities": entities or {}, "objects": objects or {}, "effects": effects or {},
            "remembered": remembered or {}, "lights": lights or {}}


def contact(position: Position, *, visual: bool = True, members: int = 1) -> dict:
    return {"position": list(position), "visual": visual, "members": members}


def effect(name: str, *positions: Position, members: int, apparent: bool = True, anchor: Position | None = None,
           trap_state: str | None = None, volume: tuple[Position, ...] = ()) -> dict:
    return {"name": name, "positions": _cells(*positions), "volume": _cells(*volume), "apparent": apparent,
            "anchor_position": list(anchor) if anchor is not None else None, "trap_state": trap_state,
            "members": members}


def light(position: Position, *, bright: int = 20, dim: int = 40, anchor_entity: UUID | None = None) -> dict:
    return {"position": list(position), "bright": bright, "dim": dim,
            "anchor_entity": str(anchor_entity) if anchor_entity is not None else None}


def sighting(*positions: Position, apparent: bool = True, anchor: Position | None = None,
             trap_state: str | None = None) -> SpatialEffectSighting:
    return SpatialEffectSighting(positions=mask_from_positions(positions), apparent_presence=apparent,
        anchor_position=anchor, trap_state=TrapState(trap_state) if trap_state is not None else None)


def first(**values: Any) -> Step:
    """A seat's first group: its perception enters, with the position and every capability."""
    return Step(initial=True, passive=12, visual_access=1, sense_modes=(DARKVISION,), **values)


ROW = ((1, 1), (2, 1), (3, 1), (4, 1))


def vectors() -> dict[str, tuple[str, tuple[UUID, ...], list[Step]]]:
    """Each vector: the rule it pins, the seat's observers, its steps."""
    g, c, f, t, l = str(GOBLIN), str(CHEST), str(FOG), str(TRAP), str(TORCH)
    return {
        "v1_seen_cells_are_every_cell_seen_visible": (
            "The seen cells are not sent: every cell the seat has seen visible is seen; the composed view's cells, "
            "light and position change as the facts say.", (A,), [
            first(position=(2, 2), added=((1, 2), (2, 2), (3, 2)), light={(1, 2): 3, (2, 2): 3, (3, 2): 3},
                 expected=expect(visible=((1, 2), (2, 2), (3, 2)), seen=((1, 2), (2, 2), (3, 2)),
                                 light=_lit(3, (1, 2), (2, 2), (3, 2)), position=(2, 2))),
            Step(removed=((1, 2),), added=((4, 2),), light={(4, 2): 2},
                 expected=expect(visible=((2, 2), (3, 2), (4, 2)), seen=((1, 2), (2, 2), (3, 2), (4, 2)),
                                 light={**_lit(3, (2, 2), (3, 2)), **_lit(2, (4, 2))}, position=(2, 2))),
            Step(position=(9, 9), removed=((2, 2), (3, 2), (4, 2)), added=((9, 9),), light={(9, 9): 3},
                 expected=expect(visible=((9, 9),), seen=((1, 2), (2, 2), (3, 2), (4, 2), (9, 9)),
                                 light=_lit(3, (9, 9)), position=(9, 9))),
        ]),
        "v2_contacts_carry_their_members": (
            "Each contact row names the members perceiving it; a row whose members alone change is sent again; a "
            "removed contact is gone with its members.", (A, B), [
            first(position=(5, 4), added=((5, 5), (6, 5)), light={(5, 5): 3, (6, 5): 3},
                 contacts=(Contact(GOBLIN, (5, 5), members=1), Contact(CHEST, (6, 5), members=1, is_object=True)),
                 expected=expect(visible=((5, 5), (6, 5)), seen=((5, 5), (6, 5)), light=_lit(3, (5, 5), (6, 5)),
                                 position=(5, 4), entities={g: contact((5, 5), members=1)},
                                 objects={c: contact((6, 5), members=1)})),
            Step(contacts=(Contact(GOBLIN, (5, 5), members=3),),
                 expected=expect(visible=((5, 5), (6, 5)), seen=((5, 5), (6, 5)), light=_lit(3, (5, 5), (6, 5)),
                                 position=(5, 4), entities={g: contact((5, 5), members=3)},
                                 objects={c: contact((6, 5), members=1)})),
            Step(contacts=(Contact(GOBLIN, (6, 5), visual=False, members=2),
                           Contact(CHEST, (6, 5), members=3, is_object=True)),
                 expected=expect(visible=((5, 5), (6, 5)), seen=((5, 5), (6, 5)), light=_lit(3, (5, 5), (6, 5)),
                                 position=(5, 4), entities={g: contact((6, 5), visual=False, members=2)},
                                 objects={c: contact((6, 5), members=3)})),
            Step(contacts_removed=((GOBLIN, False),),
                 expected=expect(visible=((5, 5), (6, 5)), seen=((5, 5), (6, 5)), light=_lit(3, (5, 5), (6, 5)),
                                 position=(5, 4), objects={c: contact((6, 5), members=3)})),
        ]),
        "v3_a_walking_torch_is_patched_by_position": (
            "A light source enters whole, then travels as its changed fields only (a carried torch: its position, "
            "its anchor once undisclosed), and leaves by key; light sources carry no members.", (A, B), [
            first(position=(4, 5), added=((5, 5), (6, 5), (7, 5)), light={(5, 5): 3, (6, 5): 3, (7, 5): 3},
                 contacts=(Contact(GOBLIN, (5, 5), members=3),), lights_added=(Light(TORCH, (5, 5), anchor_entity=GOBLIN),),
                 expected=expect(visible=((5, 5), (6, 5), (7, 5)), seen=((5, 5), (6, 5), (7, 5)),
                                 light=_lit(3, (5, 5), (6, 5), (7, 5)), position=(4, 5),
                                 entities={g: contact((5, 5), members=3)},
                                 lights={l: light((5, 5), anchor_entity=GOBLIN)})),
            Step(contacts=(Contact(GOBLIN, (6, 5), members=3),), light_patches=((TORCH, {"position": (6, 5)}),),
                 expected=expect(visible=((5, 5), (6, 5), (7, 5)), seen=((5, 5), (6, 5), (7, 5)),
                                 light=_lit(3, (5, 5), (6, 5), (7, 5)), position=(4, 5),
                                 entities={g: contact((6, 5), members=3)},
                                 lights={l: light((6, 5), anchor_entity=GOBLIN)})),
            Step(contacts_removed=((GOBLIN, False),), light_patches=((TORCH, {"anchor_entity": None}),),
                 expected=expect(visible=((5, 5), (6, 5), (7, 5)), seen=((5, 5), (6, 5), (7, 5)),
                                 light=_lit(3, (5, 5), (6, 5), (7, 5)), position=(4, 5), lights={l: light((6, 5))})),
            Step(lights_removed=(TORCH,),
                 expected=expect(visible=((5, 5), (6, 5), (7, 5)), seen=((5, 5), (6, 5), (7, 5)),
                                 light=_lit(3, (5, 5), (6, 5), (7, 5)), position=(4, 5))),
        ]),
        "v4_an_apparent_effect_is_remembered_until_seen_without_it": (
            "An effect is perceived as its visible part; cells leaving it are remembered, and so is the whole effect "
            "when it leaves perception; an apparent effect's remembered cell seen without it is forgotten; a "
            "re-entering effect's perceived cells are no longer memory.", (A, B), [
            first(position=(1, 0), added=ROW, light={cell: 3 for cell in ROW},
                 effects_added=((FOG, sighting((2, 1), (3, 1), anchor=(2, 1)), 1),), content={FOG: _content("fog")},
                 expected=expect(visible=ROW, seen=ROW, light=_lit(3, *ROW), position=(1, 0),
                                 effects={f: effect("Fog", (2, 1), (3, 1), members=1, anchor=(2, 1))})),
            Step(patches=((FOG, SpatialEffectPatch(positions_added=mask_from_positions([(4, 1)]), members=3,
                                                   changes={"anchor_position": (3, 1)})),),
                 expected=expect(visible=ROW, seen=ROW, light=_lit(3, *ROW), position=(1, 0),
                                 effects={f: effect("Fog", (2, 1), (3, 1), (4, 1), members=3, anchor=(3, 1))})),
            Step(removed=((3, 1), (4, 1)),
                 patches=((FOG, SpatialEffectPatch(positions_removed=mask_from_positions([(3, 1), (4, 1)]),
                                                   members=1)),),
                 expected=expect(visible=((1, 1), (2, 1)), seen=ROW, light=_lit(3, (1, 1), (2, 1)), position=(1, 0),
                                 effects={f: effect("Fog", (2, 1), members=1, anchor=(3, 1))},
                                 remembered={f: _cells((3, 1), (4, 1))})),
            Step(removed=((2, 1),), effects_removed=(FOG,),
                 expected=expect(visible=((1, 1),), seen=ROW, light=_lit(3, (1, 1)), position=(1, 0),
                                 remembered={f: _cells((2, 1), (3, 1), (4, 1))})),
            Step(added=((3, 1),), light={(3, 1): 3},
                 expected=expect(visible=((1, 1), (3, 1)), seen=ROW, light=_lit(3, (1, 1), (3, 1)), position=(1, 0),
                                 remembered={f: _cells((2, 1), (4, 1))})),
            Step(added=((4, 1),), light={(4, 1): 3}, effects_added=((FOG, sighting((4, 1)), 2),),
                 expected=expect(visible=((1, 1), (3, 1), (4, 1)), seen=ROW, light=_lit(3, (1, 1), (3, 1), (4, 1)),
                                 position=(1, 0), effects={f: effect("Fog", (4, 1), members=2)},
                                 remembered={f: _cells((2, 1))})),
        ]),
        "v5_a_found_trap_is_forgotten_only_when_a_finder_sees_it_gone": (
            "A concealed effect's remembered cell seen by a member that never found it stays remembered; it is "
            "forgotten when the settlement retires it (a member that held it saw it gone).", (A, B), [
            first(position=(1, 0), added=((1, 1), (2, 1)), light={(1, 1): 3, (2, 1): 3},
                 effects_added=((TRAP, sighting((2, 1), apparent=False, trap_state="ready"), 1),),
                 content={TRAP: _content("trap")},
                 expected=expect(visible=((1, 1), (2, 1)), seen=((1, 1), (2, 1)), light=_lit(3, (1, 1), (2, 1)),
                                 position=(1, 0),
                                 effects={t: effect("Trap", (2, 1), members=1, apparent=False, trap_state="ready")})),
            Step(removed=((2, 1),), effects_removed=(TRAP,),
                 expected=expect(visible=((1, 1),), seen=((1, 1), (2, 1)), light=_lit(3, (1, 1)), position=(1, 0),
                                 remembered={t: _cells((2, 1))})),
            Step(added=((2, 1),), light={(2, 1): 3},
                 expected=expect(visible=((1, 1), (2, 1)), seen=((1, 1), (2, 1)), light=_lit(3, (1, 1), (2, 1)),
                                 position=(1, 0), remembered={t: _cells((2, 1))})),
            Step(retired=((TRAP, ((2, 1),)),),
                 expected=expect(visible=((1, 1), (2, 1)), seen=((1, 1), (2, 1)), light=_lit(3, (1, 1), (2, 1)),
                                 position=(1, 0))),
        ]),
        "v6_an_effect_that_ends_in_view_leaves_nothing": (
            "An effect that ends while its members see it leaves perception with all its cells retired: nothing "
            "is remembered.", (A, B), [
            first(position=(1, 0), added=((1, 1), (2, 1)), light={(1, 1): 3, (2, 1): 3},
                 effects_added=((FOG, sighting((1, 1), (2, 1)), 3),), content={FOG: _content("fog")},
                 expected=expect(visible=((1, 1), (2, 1)), seen=((1, 1), (2, 1)), light=_lit(3, (1, 1), (2, 1)),
                                 position=(1, 0), effects={f: effect("Fog", (1, 1), (2, 1), members=3)})),
            Step(effects_removed=(FOG,), retired=((FOG, ((1, 1), (2, 1))),),
                 expected=expect(visible=((1, 1), (2, 1)), seen=((1, 1), (2, 1)), light=_lit(3, (1, 1), (2, 1)),
                                 position=(1, 0))),
        ]),
        "v7_anchor_scalars_are_sent_when_they_change": (
            "The first fact carries the position and every capability; later facts carry a scalar only when it "
            "changed (the rest keep their values); paths stay dirty once dirty.", (A,), [
            Step(initial=True, position=(0, 0), passive=10, visual_access=2, sense_modes=(DARKVISION,),
                 added=((0, 0),), light={(0, 0): 3},
                 expected=expect(visible=((0, 0),), seen=((0, 0),), light=_lit(3, (0, 0)), position=(0, 0),
                                 passive=10, visual_access=2)),
            Step(passive=13,
                 expected=expect(visible=((0, 0),), seen=((0, 0),), light=_lit(3, (0, 0)), position=(0, 0),
                                 passive=13, visual_access=2)),
            Step(position=(1, 0), added=((1, 0),), light={(1, 0): 3}, visual_access=1, paths_dirty=True,
                 expected=expect(visible=((0, 0), (1, 0)), seen=((0, 0), (1, 0)), light=_lit(3, (0, 0), (1, 0)),
                                 position=(1, 0), passive=13, visual_access=1, paths_dirty=True)),
            Step(sense_modes=(),
                 expected=expect(visible=((0, 0), (1, 0)), seen=((0, 0), (1, 0)), light=_lit(3, (0, 0), (1, 0)),
                                 position=(1, 0), passive=13, visual_access=1, paths_dirty=True, sense_modes=())),
        ]),
        "v8_a_one_observer_seat_sends_no_member_columns": (
            "A seat with one observer leaves the member columns out: every contact and effect is that observer's.",
            (A,), [
            first(position=(1, 0), added=((1, 1), (2, 1)), light={(1, 1): 3, (2, 1): 3},
                 contacts=(Contact(GOBLIN, (1, 1)),), effects_added=((FOG, sighting((2, 1)), 1),),
                 content={FOG: _content("fog")},
                 expected=expect(visible=((1, 1), (2, 1)), seen=((1, 1), (2, 1)), light=_lit(3, (1, 1), (2, 1)),
                                 position=(1, 0), entities={g: contact((1, 1))},
                                 effects={f: effect("Fog", (2, 1), members=1)})),
        ]),
    }


def documents() -> dict[str, str]:
    """Each vector file's text."""
    result = {}
    for name, (rule, observers, steps) in vectors().items():
        several = len(observers) > 1
        rows = []
        for step in steps:
            group, fact = _group(step, several)
            rows.append({"sensory_rows": ROWS.dump_python(group, mode="json"),
                         "fact": FACT.dump_python(fact, mode="json"), "expected": step.expected})
        result[f"{name}.json"] = json.dumps({"name": name, "rule": rule,
            "observers": [str(observer) for observer in observers], "steps": rows}, indent=1) + "\n"
    return result


def main() -> None:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    wanted = documents()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    for path in DIRECTORY.glob("*.json"):
        if path.name not in wanted:
            path.unlink()
    for name, text in wanted.items():
        (DIRECTORY / name).write_text(text)


if __name__ == "__main__":
    main()
