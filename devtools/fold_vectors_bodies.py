"""Golden vectors of the schema-16 bodies client fold (EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §3.3, §3.4, §3.5).

A vector is a seat's audience and a sequence of received records, each with the client bodies and items expected
after it. The expected states are written here by hand from the client's rules, never dumped from the fold:

- bodies and items are never pruned: leaving view changes nothing;
- a body's first record carries its birth (name, look, body id, size, manifestation), held from then on; every
  record replaces all of the body's changeable fields, and the last visual position stays what contacts made it;
- an item's first record carries its look (and, for its controller, its profile), held from then on; every record
  replaces its dynamic parts (effects, and the controller's state) whole;
- an actor change applies the items entering view first, then each actor's rows in order, with a dict's order:
  a set keeps its key's place or appends, an end removes its key, an end of an absent key changes nothing;
- a body whose lifetime ended ignores later records;
- a cell the seat sees shows what is there: a living body last seen on a visible cell that is no longer a contact
  loses its position there (its controlled bodies and the dead keep theirs).

Steps: `body` (a `BodyRecord`), `change` (an `ActorChangeFact`), `spatial` (a `SpatialFact`, for a lifetime's
end) and `seen` (the composed view after a sensory fold: its visible cells and contacts; a visual contact places
its body). The files are what Godot folds too (`sdk/protocol/fold-vectors/bodies/*.json`);
`tests/player/test_body_fold_vectors.py` folds them with the reference fold (`dnd.player.reduction`).

    PYTHONPATH=. python devtools/fold_vectors_bodies.py          # write the files
    PYTHONPATH=. python devtools/fold_vectors_bodies.py --check  # exit 1 when a file differs from this source
"""

import argparse
from dataclasses import dataclass, replace
from typing import Any
import json
from pathlib import Path
import sys
from uuid import UUID

from pydantic import TypeAdapter

from dnd.core.condition_types import (ConditionAgencyDenial, ConditionCategory, ConditionDurationSummary,
    DurationType)
from dnd.core.creature_types import Size
from dnd.core.equipment_types import WeaponSet
from dnd.core.item_types import (EquippedVisualPolicy, ItemEffectPresentationState, ItemIntegrity,
    ItemPresentationKind, ItemRarity)
from dnd.core.life_types import LifeState
from dnd.player.bodies import loadout_id
from dnd.player.facts import (ActorBirth, ActorChangeFact, ActorRows, BodyRecord, BodyState, ItemRecord, SpatialFact,
    VisualLoadout)
from dnd.types.actor import ConditionState, SpatialDisposition, TemporaryHitPointsGrant
from dnd.types.actor_facts import (ChangeField, ChangeRow, ConditionMember, ConditionRow, DispositionRow, DurationRow,
    GrantRow, InventoryRow, ItemEffectsRow, ItemStateRow, LayerRow, NumberRow, SizeRow, WeaponSetRow)
from dnd.types.appearance import AppearanceConfig
from dnd.types.event_facts import SpatialChangeType
from dnd.types.item_parts import ItemLook, ItemProfile, ItemState, VisualItem
from dnd.types.physical_access import ContactPassage

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "sdk" / "protocol" / "fold-vectors" / "bodies"
BODY, CHANGE, SPATIAL = TypeAdapter(BodyRecord), TypeAdapter(ActorChangeFact), TypeAdapter(SpatialFact)

Position = tuple[int, int]
# The seat controls A; B, C, D and E are other creatures.
A, B, C, D, E = (UUID(f"00000000-0000-4000-8000-00000000000{digit}") for digit in "abcde")
DAGGER, HELM, ROBE = (UUID(f"00000000-0000-4000-8000-00000000100{digit}") for digit in "123")
TORCH, POTION, ROPE = (UUID(f"00000000-0000-4000-8000-00000000200{digit}") for digit in "123")
POISON, BLESS, HASTE, CURSE = (UUID(f"00000000-0000-4000-8000-00000000300{digit}") for digit in "1234")
FLAME = UUID("00000000-0000-4000-8000-000000004001")
GRANT = UUID("00000000-0000-4000-8000-000000005001")


def rounds(remaining: int) -> ConditionDurationSummary:
    return ConditionDurationSummary(duration_type=DurationType.ROUNDS, remaining_rounds=remaining)


def member(identity: UUID, name: str, remaining: int | None = None) -> ConditionMember:
    return ConditionMember(condition_uuid=identity, name=name, category=ConditionCategory.STATUS, behavior_id=None,
        state=ConditionState(condition_uuid=identity, name=name, category=ConditionCategory.STATUS,
            semantic_key=f"condition.fold_vectors.{name.lower()}", tags=(), removal_triggers=(),
            agency_denial=ConditionAgencyDenial.NONE, outcome_protections=(),
            duration=rounds(remaining) if remaining is not None else None))


def birth(name: str) -> ActorBirth:
    return ActorBirth(name=name, character_body_id=None, creature_content_ref=None, appearance=AppearanceConfig(),
        structural_base_size=Size.MEDIUM)


def layer(slot: str, item: UUID, item_id: str, lit: bool | None = None) -> VisualItem:
    return VisualItem(slot=slot, item_uuid=item, item_id=item_id, is_lit=lit)


def body(hp: int, *, conditions: tuple[ConditionMember, ...] = (), layers: tuple[VisualItem, ...] = (),
         inventory: tuple[UUID, ...] | None = None, weapon_set: WeaponSet = WeaponSet.MELEE,
         life: LifeState = LifeState.ALIVE) -> tuple[BodyState, VisualLoadout]:
    loadout = VisualLoadout(active_weapon_set=weapon_set, layers=layers)
    return BodyState(visual_loadout_id=loadout_id(loadout), normal_hp=hp, maximum_hp=10, temporary_hp=0,
        life_state=life, armor_class=12, conditions=conditions, controlled_items=inventory), loadout


def entered(*, occurrence: int, actor_uuid: UUID, birth: ActorBirth | None = None,
            body: tuple[BodyState, VisualLoadout], items: tuple[ItemRecord, ...] = (), by_id: bool = False
            ) -> BodyRecord:
    """A body record with its loadout's value, or (`by_id`) naming a loadout the seat holds by its id alone."""
    state, loadout = body
    return BodyRecord(occurrence=occurrence, actor_uuid=actor_uuid, birth=birth, body=state,
        loadout=None if by_id else loadout, items=items)


def look(item_id: str) -> ItemLook:
    return ItemLook(item_id=item_id, item_kind=ItemPresentationKind.ITEM, visual_item_name=item_id.split(".")[-1],
        visual_variant_id=None, equipped_visual_policy=EquippedVisualPolicy.VISIBLE,
        very_bright_radius_feet=None, bright_radius_feet=None, dim_radius_feet=None)


PROFILE = ItemProfile(name="Item", description=None, rarity=ItemRarity.COMMON, weight=1.0, value=0, tags=(),
    is_pickable=True, is_equippable=True, is_usable=False, is_targetable=False, door_mechanism=None, door_swing=None,
    stack_id=None, damage_dice=None, damage_type=None, weapon_properties=(), armor_type=None, armor_ac=None,
    shield_ac_bonus=None, max_charges=None, max_stack=1, is_consumable=False, map_char="i",
    include_in_senses_objects=True, include_in_adjacent_senses_objects=False,
    include_in_available_object_actions=True, maximum_hit_points=None, concentration_capacity=0,
    boundary_structure=None)
STATE = ItemState(stack_count=1, charges=None, integrity=ItemIntegrity.INTACT, destruction_outcome=None,
    remnant_state=None, current_hit_points=None, concentration_slots=(), construction_owner_uuid=None,
    construction_geometry=None, construction_suppressions=(), known_to_creator=False, supported_by_uuid=None,
    contact_passage=ContactPassage.STRUCTURAL, surface_residues=(), linked_spatial_condition_uuid=None, is_open=None,
    is_engaged=None, blocks_movement=False, blocks_optics=False, blocks_propagation=False, is_lit=None)


def flame(remaining: int | None = None) -> ItemEffectPresentationState:
    return ItemEffectPresentationState(effect_uuid=FLAME, behavior_id="condition.fold_vectors.flame",
        display_name="Flame", duration=rounds(remaining) if remaining is not None else None)


def rows(actor: UUID, *values: ChangeRow) -> ActorRows:
    return ActorRows(actor_uuid=actor, rows=values)


# The expected client view of one body and of one item.

def view(name: str, hp: int, *, conditions: tuple[tuple[UUID, str, int | None], ...] = (),
         layers: tuple[tuple[str, UUID, bool | None], ...] = (), inventory: tuple[UUID, ...] | None = None,
         position: Position | None = None, present: bool = True, life: str = "alive", maximum: int = 10,
         temporary: int = 0, grant: UUID | None = None, armor_class: int = 12, weapon_set: str = "melee",
         size: str | None = None, disposition: str = "present") -> dict[str, Any]:
    return {"name": name, "hp": [hp, maximum, temporary], "grant": str(grant) if grant is not None else None,
            "armor_class": armor_class, "life": life, "present": present,
            "position": list(position) if position is not None else None,
            "conditions": [[str(identity), label, remaining] for identity, label, remaining in conditions],
            "weapon_set": weapon_set, "layers": [[slot, str(item), lit] for slot, item, lit in layers],
            "inventory": [str(item) for item in inventory] if inventory is not None else None,
            "size": size, "disposition": disposition}


def item_view(item_id: str, *, profile: bool = False, state: tuple[int | None, int, bool | None] | None = None,
              effects: tuple[tuple[UUID, int | None], ...] = ()) -> dict[str, Any]:
    return {"item_id": item_id, "profile": profile,
            "state": {"charges": state[0], "stack_count": state[1], "is_lit": state[2]} if state is not None else None,
            "effects": [[str(identity), remaining] for identity, remaining in effects]}


@dataclass(frozen=True)
class Step:
    kind: str
    value: Any
    expected: dict[str, Any]


def expect(actors: dict[UUID, dict[str, Any]], items: dict[UUID, dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"actors": {str(identity): value for identity, value in actors.items()},
            "items": {str(identity): value for identity, value in (items or {}).items()}}


def seen(visible: tuple[Position, ...], contacts: dict[UUID, tuple[Position, bool]]) -> dict[str, Any]:
    return {"visible": [list(position) for position in visible],
            "contacts": {str(identity): {"position": list(position), "visual": visual}
                         for identity, (position, visual) in contacts.items()}}


def vectors() -> dict[str, tuple[str, list[Step]]]:
    goblin = birth("Goblin")
    dagger = layer("MELEE_MAIN", DAGGER, "weapon.dagger")
    helm, robe = layer("Head", HELM, "apparel.helm"), layer("Body", ROBE, "apparel.robe")
    first = entered(occurrence=0, actor_uuid=B, birth=goblin, body=body(7, conditions=(member(POISON, "Poisoned"),),
        layers=(dagger,)), items=(ItemRecord(item_uuid=DAGGER, look=look("weapon.dagger"), effects=(flame(),)),))
    seen_b = Step("seen", seen(((4, 5),), {B: ((4, 5), True)}), expect({B: view("Goblin", 7,
        conditions=((POISON, "Poisoned", None),), layers=(("MELEE_MAIN", DAGGER, None),), position=(4, 5))}))
    return {
        "v1_a_first_record_carries_the_birth_held_from_then_on": (
            "A body's first record carries its birth; a later record replaces every changeable field and keeps the "
            "birth. An item's first record carries its look; a later record replaces its effects and keeps the look.",
            [Step("body", first, expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),),
                                                 layers=(("MELEE_MAIN", DAGGER, None),))},
                                        {DAGGER: item_view("weapon.dagger", effects=((FLAME, None),))})),
             Step("body", entered(occurrence=4, actor_uuid=B, body=body(3, layers=(dagger,)),
                                     items=(ItemRecord(item_uuid=DAGGER),)),
                  expect({B: view("Goblin", 3, layers=(("MELEE_MAIN", DAGGER, None),))},
                         {DAGGER: item_view("weapon.dagger")}))]),
        "v2_a_record_keeps_the_position_contacts_gave": (
            "A record replaces the body's changeable fields but not its last visual position, which only contacts set.",
            [Step("body", first, expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),),
                                                 layers=(("MELEE_MAIN", DAGGER, None),))})),
             seen_b,
             Step("body", entered(occurrence=6, actor_uuid=B, body=body(5)),
                  expect({B: view("Goblin", 5, position=(4, 5))}))]),
        "v3_leaving_view_changes_nothing": (
            "Bodies and items are never pruned: a body that leaves view keeps its values and its last position.",
            [Step("body", first, expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),),
                                                 layers=(("MELEE_MAIN", DAGGER, None),))})),
             seen_b,
             Step("seen", seen(((8, 8),), {}), expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),),
                 layers=(("MELEE_MAIN", DAGGER, None),), position=(4, 5))},
                 {DAGGER: item_view("weapon.dagger", effects=((FLAME, None),))}))]),
        "v4_a_seen_cell_shows_what_is_there": (
            "A living body last seen on a visible cell that is no longer a contact loses its position; a controlled "
            "body, a dead body, a body still held as a contact and one on a cell not seen keep theirs.",
            [Step("body", entered(occurrence=0, actor_uuid=A, birth=birth("Hero"), body=body(10, inventory=())),
                  expect({A: view("Hero", 10, inventory=())})),
             *(Step("body", entered(occurrence=0, actor_uuid=identity, birth=birth(name),
                                       body=body(4, life=life)), expect({}))
               for identity, name, life in ((B, "Goblin", LifeState.ALIVE), (C, "Corpse", LifeState.DEAD),
                                            (D, "Far goblin", LifeState.ALIVE), (E, "Hidden goblin", LifeState.ALIVE))),
             Step("seen", seen(((4, 5), (4, 6), (4, 7), (4, 8), (9, 9)),
                               {A: ((4, 7), True), B: ((4, 5), True), C: ((4, 6), True), D: ((9, 9), True),
                                E: ((4, 8), True)}),
                  expect({A: view("Hero", 10, inventory=(), position=(4, 7)), B: view("Goblin", 4, position=(4, 5)),
                          C: view("Corpse", 4, position=(4, 6), life="dead"), D: view("Far goblin", 4, position=(9, 9)),
                          E: view("Hidden goblin", 4, position=(4, 8))})),
             Step("seen", seen(((4, 5), (4, 6), (4, 7), (4, 8)), {E: ((4, 8), False)}),
                  expect({A: view("Hero", 10, inventory=(), position=(4, 7)), B: view("Goblin", 4),
                          C: view("Corpse", 4, position=(4, 6), life="dead"), D: view("Far goblin", 4, position=(9, 9)),
                          E: view("Hidden goblin", 4, position=(4, 8))}))]),
        "v5_rows_apply_in_the_engines_dict_order": (
            "An actor change applies its entering items, then each actor's rows in order: a set keeps its key's place "
            "or appends, an end removes its key, the end of an absent key changes nothing; re-equipping a slot moves "
            "it last.",
            [Step("body", entered(occurrence=0, actor_uuid=A, birth=birth("Hero"),
                                     body=body(10, conditions=(member(POISON, "Poisoned"), member(BLESS, "Blessed", 3)),
                                               layers=(helm, robe), inventory=(HELM, ROBE)),
                                     items=(ItemRecord(item_uuid=HELM, look=look("apparel.helm"), profile=PROFILE,
                                                       state=STATE),
                                            ItemRecord(item_uuid=ROBE, look=look("apparel.robe"), profile=PROFILE,
                                                       state=STATE))),
                  expect({A: view("Hero", 10, conditions=((POISON, "Poisoned", None), (BLESS, "Blessed", 3)),
                                  layers=(("Head", HELM, None), ("Body", ROBE, None)), inventory=(HELM, ROBE))})),
             Step("change", ActorChangeFact(actors=(rows(A,
                     ConditionRow(condition_uuid=POISON, member=member(POISON, "Poisoned", 2)),
                     ConditionRow(condition_uuid=HASTE, member=member(HASTE, "Hasted", 10)),
                     ConditionRow(condition_uuid=CURSE),
                     LayerRow(slot="Head"), LayerRow(slot="Head", layer=helm),
                     InventoryRow(item_uuid=HELM, held=True), InventoryRow(item_uuid=TORCH, held=True)),),
                     items=(ItemRecord(item_uuid=TORCH, look=look("light.torch"), profile=PROFILE, state=STATE),)),
                  expect({A: view("Hero", 10, conditions=((POISON, "Poisoned", 2), (BLESS, "Blessed", 3),
                                                          (HASTE, "Hasted", 10)),
                                  layers=(("Body", ROBE, None), ("Head", HELM, None)), inventory=(HELM, ROBE, TORCH))},
                         {TORCH: item_view("light.torch", profile=True, state=(None, 1, None))})),
             Step("change", ActorChangeFact(actors=(rows(A, ConditionRow(condition_uuid=BLESS, consumed=True),
                     LayerRow(slot="Body"), InventoryRow(item_uuid=ROBE, held=False)),)),
                  expect({A: view("Hero", 10, conditions=((POISON, "Poisoned", 2), (HASTE, "Hasted", 10)),
                                  layers=(("Head", HELM, None),), inventory=(HELM, TORCH))},
                         {HELM: item_view("apparel.helm", profile=True, state=(None, 1, None)),
                          ROBE: item_view("apparel.robe", profile=True, state=(None, 1, None)),
                          TORCH: item_view("light.torch", profile=True, state=(None, 1, None))}))]),
        "v6_scalar_and_item_rows_replace_their_field": (
            "Scalar rows replace their field; item rows change the seat's record of that item: its state fields, "
            "its effects whole, an effect's or a condition's duration.",
            [Step("body", entered(occurrence=0, actor_uuid=A, birth=birth("Hero"),
                                     body=body(10, conditions=(member(BLESS, "Blessed", 3),),
                                               layers=(layer("MELEE_OFF", TORCH, "light.torch", False),),
                                               inventory=(TORCH,)),
                                     items=(ItemRecord(item_uuid=TORCH, look=look("light.torch"), profile=PROFILE,
                                                       state=replace(STATE, charges=5, is_lit=False)),)),
                  expect({A: view("Hero", 10, conditions=((BLESS, "Blessed", 3),),
                                  layers=(("MELEE_OFF", TORCH, False),), inventory=(TORCH,))},
                         {TORCH: item_view("light.torch", profile=True, state=(5, 1, False))})),
             Step("change", ActorChangeFact(actors=(rows(A,
                     NumberRow(field=ChangeField.NORMAL_HP, value=6), NumberRow(field=ChangeField.MAXIMUM_HP, value=12),
                     NumberRow(field=ChangeField.TEMPORARY_HP, value=4), GrantRow(value=TemporaryHitPointsGrant(
                         instance_uuid=GRANT, source_id="condition.fold_vectors.ward")),
                     NumberRow(field=ChangeField.ARMOR_CLASS, value=15), SizeRow(value=Size.LARGE),
                     DispositionRow(value=SpatialDisposition.ABSENT), WeaponSetRow(value=WeaponSet.RANGED),
                     DurationRow(field=ChangeField.CONDITION_DURATION, key=BLESS, duration=rounds(2)),
                     LayerRow(slot="MELEE_OFF", layer=layer("MELEE_OFF", TORCH, "light.torch", True)),
                     ItemStateRow(item_uuid=TORCH, changes={"charges": 4, "is_lit": True}),
                     ItemEffectsRow(item_uuid=TORCH, effects=(flame(5),)),
                     DurationRow(field=ChangeField.ITEM_EFFECT_DURATION, key=FLAME, item_uuid=TORCH,
                                 duration=rounds(4))),)),
                  expect({A: view("Hero", 6, maximum=12, temporary=4, grant=GRANT, armor_class=15, size="Large",
                                  disposition="absent", weapon_set="ranged", conditions=((BLESS, "Blessed", 2),),
                                  layers=(("MELEE_OFF", TORCH, True),), inventory=(TORCH,))},
                         {TORCH: item_view("light.torch", profile=True, state=(4, 1, True), effects=((FLAME, 4),))}))]),
        "v7_a_departed_body_ignores_later_records": (
            "A body whose lifetime ended ignores later records and rows.",
            [Step("body", first, expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),),
                                                 layers=(("MELEE_MAIN", DAGGER, None),))})),
             Step("spatial", SpatialFact(change_type=SpatialChangeType.ENTITY_LEFT, entity_uuid=B, position=(4, 5),
                                         terminal_departure=True),
                  expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),),
                                  layers=(("MELEE_MAIN", DAGGER, None),), present=False)})),
             Step("body", entered(occurrence=9, actor_uuid=B, body=body(1)), expect({B: view("Goblin", 7,
                 conditions=((POISON, "Poisoned", None),), layers=(("MELEE_MAIN", DAGGER, None),), present=False)})),
             Step("change", ActorChangeFact(actors=(rows(B, NumberRow(field=ChangeField.NORMAL_HP, value=1)),)),
                  expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),),
                                  layers=(("MELEE_MAIN", DAGGER, None),), present=False)}))]),
        "v8_a_reentering_body_names_its_loadout_by_id": (
            "A body record names its visual loadout by content id, with the value the first time; a later record "
            "naming a held id takes that value. Layer rows change the body's value, not the id's.",
            [Step("body", first, expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),),
                                                 layers=(("MELEE_MAIN", DAGGER, None),))})),
             Step("change", ActorChangeFact(actors=(rows(B, LayerRow(slot="MELEE_MAIN")),)),
                  expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),))})),
             Step("body", entered(occurrence=5, actor_uuid=B, body=body(6, layers=(dagger,)), by_id=True,
                                  items=(ItemRecord(item_uuid=DAGGER, effects=(flame(),)),)),
                  expect({B: view("Goblin", 6, layers=(("MELEE_MAIN", DAGGER, None),))},
                         {DAGGER: item_view("weapon.dagger", effects=((FLAME, None),))}))]),
        "v9_a_shown_item_without_a_record_has_no_effects": (
            "A body record leaves out the records of the items it shows that carry nothing (their look already "
            "sent, no state, no effects): such an item has no effects.",
            [Step("body", first, expect({B: view("Goblin", 7, conditions=((POISON, "Poisoned", None),),
                                                 layers=(("MELEE_MAIN", DAGGER, None),))},
                                        {DAGGER: item_view("weapon.dagger", effects=((FLAME, None),))})),
             Step("body", entered(occurrence=4, actor_uuid=B, body=body(7, layers=(dagger,)), by_id=True),
                  expect({B: view("Goblin", 7, layers=(("MELEE_MAIN", DAGGER, None),))},
                         {DAGGER: item_view("weapon.dagger")}))]),
    }


def _value(step: Step) -> Any:
    match step.kind:
        case "body":
            return BODY.dump_python(step.value, mode="json")
        case "change":
            return CHANGE.dump_python(step.value, mode="json")
        case "spatial":
            return SPATIAL.dump_python(step.value, mode="json")
    return step.value


def documents() -> dict[str, str]:
    """Each vector file's text."""
    return {f"{name}.json": json.dumps({"name": name, "rule": rule, "observers": [str(A)], "controlled": [str(A)],
                "steps": [{step.kind: _value(step), "expected": step.expected} for step in steps]}, indent=1) + "\n"
            for name, (rule, steps) in vectors().items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    wanted = documents()
    if args.check:
        held = {path.name: path.read_text() for path in DIRECTORY.glob("*.json")} if DIRECTORY.exists() else {}
        sys.exit(0 if held == wanted else 1)
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    for path in DIRECTORY.glob("*.json"):
        if path.name not in wanted:
            path.unlink()
    for name, text in wanted.items():
        (DIRECTORY / name).write_text(text)


if __name__ == "__main__":
    main()
