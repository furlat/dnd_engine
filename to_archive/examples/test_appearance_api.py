"""Focused checks for backend-authored appearance metadata."""

import sys
import traceback

sys.path.insert(0, ".")

from dnd.blocks.equipment import EquipmentEvent
from dnd.classes.barbarian_factory import BarbarianConfig, create_barbarian
from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.monsters.bestiary import create_caster, create_goblin, create_skeleton
from dnd.utils import reset_combat_state
from server.api_models import APIEntityFull, APIEntitySummary
from server.event_serialization import serialize_event


tests_passed = 0
tests_failed = 0


def run_test(name, func):
    global tests_passed, tests_failed
    reset_combat_state()
    get_map().create_rectangle(0, 0, 10, 10)
    try:
        func()
        print(f"  PASS: {name}")
        tests_passed += 1
    except Exception:
        print(f"  FAIL: {name}")
        traceback.print_exc()
        tests_failed += 1


def assert_appearance(summary, body, skin, head, hair, has_beard, beard):
    appearance = summary.appearance
    assert appearance.body_category == body
    assert appearance.skin_tint == skin
    assert appearance.head_category == head
    assert appearance.hair_tint == hair
    assert appearance.has_beard is has_beard
    assert appearance.beard_tint == beard


def test_class_factory_appearance_api():
    fighter = create_fighter(FighterConfig(level=1, name="Visual Fighter"))
    sorcerer = create_sorcerer(SorcererConfig(level=1, name="Visual Sorcerer"))
    barbarian = create_barbarian(BarbarianConfig(level=1, name="Visual Barbarian"))

    assert_appearance(APIEntitySummary.create(fighter), "NakedBody", 0xE6BC98, "Head9", 0x993F00, True, 0x993F00)
    assert_appearance(APIEntitySummary.create(sorcerer), "NakedBody", 0xE6BC98, "Head9", 0x993F00, False, 0)
    assert_appearance(APIEntitySummary.create(barbarian), "NakedBody", 0xD4AA78, "Head9", 0xD0BFA1, False, 0)

    full = APIEntityFull.create(fighter)
    assert full.appearance.body_category == "NakedBody"
    assert full.model_dump(mode="json")["appearance"]["head_category"] == "Head9"


def test_monster_factory_appearance_api():
    goblin = create_goblin(name="Goblin 1")
    skeleton = create_skeleton(name="Skeleton Warrior")
    caster = create_caster(name="Caster")

    assert_appearance(APIEntitySummary.create(goblin), "NakedBody", 0x7A9A3A, None, 0, False, 0)
    assert_appearance(APIEntitySummary.create(skeleton), "NakedBody2", 0xFFFFFF, None, 0, False, 0)
    assert_appearance(APIEntitySummary.create(caster), "NakedBody", 0xDDAA88, "Head9", 0x6C5231, False, 0)


def test_equipment_event_serializer_preserves_domain_event_only():
    sorcerer = create_sorcerer(SorcererConfig(level=1, name="Visual Sorcerer"))

    completions = [
        event for event in EventQueue._all_events
        if isinstance(event, EquipmentEvent) and event.phase == EventPhase.COMPLETION
    ]
    assert completions

    payload = serialize_event(completions[-1])
    assert payload["source_entity_uuid"] == str(sorcerer.uuid)
    assert payload["event_type"] in ("weapon_equip", "armor_equip", "shield_equip")
    assert "resulting_equipment" not in payload


run_test("class factory appearance API", test_class_factory_appearance_api)
run_test("monster factory appearance API", test_monster_factory_appearance_api)
run_test("equipment event serializer preserves domain event only", test_equipment_event_serializer_preserves_domain_event_only)

print(f"\nResults: {tests_passed} passed, {tests_failed} failed")
if tests_failed:
    sys.exit(1)
