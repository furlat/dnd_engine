"""Restored backend-authored appearance and equipment visual contracts."""

from dataclasses import dataclass
from typing import Literal

from dnd.blocks.equipment import EquipmentEvent
from dnd.classes.barbarian_factory import BarbarianConfig, create_barbarian
from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.monsters.bestiary import create_caster, create_goblin, create_skeleton
from server.event_contract import serialize_event
from server.world_projection import (
    project_entity_summary,
    project_equipment_overview,
)
from tests.manual.test_95_creature_presentation_contract import _reset_state


CoverageStatus = Literal["active", "strengthened", "stale"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived presentation case's maintained replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_146_appearance_visual_legacy_contract.py"
APPEARANCE_SELECTOR = (
    f"{THIS_FILE}::test_class_monster_appearance_and_equipment_event_boundaries"
)
SORCERER_SELECTOR = (
    f"{THIS_FILE}::test_sorcerer_visual_clothing_remains_swappable"
)
FIGHTER_SELECTOR = f"{THIS_FILE}::test_fighter_visual_boots_remain_swappable"


APPEARANCE_API_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_class_factory_appearance_api": LegacyCoverage(
        "strengthened",
        APPEARANCE_SELECTOR,
        "Canonical projected summaries retain exact factory-authored appearance; the removed broad APIEntityFull surface is not restored.",
    ),
    "test_monster_factory_appearance_api": LegacyCoverage(
        "active",
        APPEARANCE_SELECTOR,
        "Goblin, skeleton, and caster projections retain their exact layered appearance keys.",
    ),
    "test_equipment_event_serializer_preserves_domain_event_only": LegacyCoverage(
        "strengthened",
        APPEARANCE_SELECTOR,
        "The canonical event serializer preserves the domain fact without embedding a parallel equipment snapshot.",
    ),
}


EQUIPMENT_VISUAL_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_sorcerer_has_swappable_visual_clothing": LegacyCoverage(
        "active",
        SORCERER_SELECTOR,
        "Equipped and inventory visual variants remain explicit through swaps.",
    ),
    "test_fighter_has_swappable_visual_boots": LegacyCoverage(
        "active",
        FIGHTER_SELECTOR,
        "Boot and helmet presentation keys remain explicit through swaps.",
    ),
}


def _slot_item(entity, slot_name: str):
    overview = project_equipment_overview(entity)
    return next(slot.item for slot in overview.slots if slot.slot == slot_name)


def _inventory_item(entity, name: str, variant_id: str | None = None):
    return next(
        item
        for item in entity.inventory.items.values()
        if item.name == name
        and (variant_id is None or item.visual_variant_id == variant_id)
    )


def _assert_appearance(
    entity,
    *,
    body: str,
    skin: int,
    head: str | None,
    hair: int,
    has_beard: bool,
    beard: int,
) -> None:
    appearance = project_entity_summary(entity).appearance
    assert (
        appearance.body_category,
        appearance.skin_tint,
        appearance.head_category,
        appearance.hair_tint,
        appearance.has_beard,
        appearance.beard_tint,
    ) == (body, skin, head, hair, has_beard, beard)


def test_appearance_visual_manifests_account_for_all_5_cases() -> None:
    """Every archived appearance/visual case has an exact disposition."""
    assert len(APPEARANCE_API_LEGACY_CASES) == 3
    assert len(EQUIPMENT_VISUAL_LEGACY_CASES) == 2
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for ledger in (
            APPEARANCE_API_LEGACY_CASES,
            EQUIPMENT_VISUAL_LEGACY_CASES,
        )
        for case, row in ledger.items()
    )


def test_class_monster_appearance_and_equipment_event_boundaries() -> None:
    """Factories author exact cold visuals; events do not duplicate snapshots."""
    _reset_state()
    fighter = create_fighter(
        FighterConfig(level=1, name="Visual Fighter", position=(1, 1))
    )
    sorcerer = create_sorcerer(
        SorcererConfig(level=1, name="Visual Sorcerer", position=(3, 1))
    )
    barbarian = create_barbarian(
        BarbarianConfig(level=1, name="Visual Barbarian", position=(5, 1))
    )

    _assert_appearance(
        fighter,
        body="NakedBody",
        skin=0xE6BC98,
        head="Head9",
        hair=0x993F00,
        has_beard=True,
        beard=0x993F00,
    )
    _assert_appearance(
        sorcerer,
        body="NakedBody",
        skin=0xE6BC98,
        head="Head9",
        hair=0x993F00,
        has_beard=False,
        beard=0,
    )
    _assert_appearance(
        barbarian,
        body="NakedBody",
        skin=0xD4AA78,
        head="Head9",
        hair=0xD0BFA1,
        has_beard=False,
        beard=0,
    )

    completions = [
        event
        for event in EventQueue._all_events
        if isinstance(event, EquipmentEvent)
        and event.phase is EventPhase.COMPLETION
        and event.source_entity_uuid == sorcerer.uuid
    ]
    assert completions
    payload = serialize_event(completions[-1])
    assert payload["source_entity_uuid"] == str(sorcerer.uuid)
    assert payload["event_type"] in {
        "weapon_equip",
        "armor_equip",
        "shield_equip",
    }
    assert "resulting_equipment" not in payload

    _reset_state()
    goblin = create_goblin(name="Goblin", position=(1, 1))
    skeleton = create_skeleton(name="Skeleton", position=(3, 1))
    caster = create_caster(name="Caster", position=(5, 1))
    _assert_appearance(
        goblin,
        body="NakedBody",
        skin=0x7A9A3A,
        head=None,
        hair=0,
        has_beard=False,
        beard=0,
    )
    _assert_appearance(
        skeleton,
        body="NakedBody2",
        skin=0xFFFFFF,
        head=None,
        hair=0,
        has_beard=False,
        beard=0,
    )
    _assert_appearance(
        caster,
        body="NakedBody",
        skin=0xDDAA88,
        head="Head9",
        hair=0x6C5231,
        has_beard=False,
        beard=0,
    )


def test_sorcerer_visual_clothing_remains_swappable() -> None:
    """Sorcerer cold visual keys survive inventory/equipment transitions."""
    _reset_state()
    sorcerer = create_sorcerer(
        SorcererConfig(
            level=5,
            name="Visual Sorcerer",
            position=(2, 2),
            metamagic_choices=["quickened", "twinned"],
            asi_4=[("charisma", 2)],
        )
    )
    body = _slot_item(sorcerer, "body_armor")
    boots = _slot_item(sorcerer, "boots")
    assert body is not None and boots is not None
    assert (body.visual_item_name, body.visual_variant_id) == (
        "Robes",
        "81000005",
    )
    assert (boots.visual_item_name, boots.visual_variant_id) == (
        "Cloth Shoes",
        "b0000004",
    )
    assert sorcerer.ac_bonus().normalized_score == 15

    alternate_robes = _inventory_item(sorcerer, "Robes", "81000001")
    alternate_shoes = _inventory_item(sorcerer, "Cloth Shoes", "b0000005")
    wizard_hat = _inventory_item(sorcerer, "Wizard's Hat", "h0000011")
    equippable = sorcerer.get_equippable_items()
    assert any(
        row["item_uuid"] == str(alternate_robes.uuid)
        for row in equippable["body_armor"]
    )
    assert any(
        row["item_uuid"] == str(alternate_shoes.uuid)
        for row in equippable["boots"]
    )
    assert any(
        row["item_uuid"] == str(wizard_hat.uuid)
        for row in equippable["helmet"]
    )

    original_body = sorcerer.equipment.body_armor
    assert original_body is not None
    old_body_uuid = original_body.uuid
    assert sorcerer.equip_item(alternate_robes.uuid, BodyPart.BODY)
    swapped_body = _slot_item(sorcerer, "body_armor")
    assert swapped_body is not None
    assert swapped_body.visual_variant_id == "81000001"
    assert old_body_uuid in sorcerer.inventory.items
    assert sorcerer.ac_bonus().normalized_score == 15
    assert sorcerer.equip_item(wizard_hat.uuid, BodyPart.HEAD)
    helmet = _slot_item(sorcerer, "helmet")
    assert helmet is not None
    assert helmet.visual_variant_id == "h0000011"


def test_fighter_visual_boots_remain_swappable() -> None:
    """Fighter boots and helmet retain stable renderer keys after swapping."""
    _reset_state()
    fighter = create_fighter(
        FighterConfig(
            level=5,
            name="Visual Fighter",
            position=(2, 2),
            equipment_preset="archery",
            fighting_style="archery",
            asi_4=[("dexterity", 2)],
        )
    )
    boots = _slot_item(fighter, "boots")
    assert boots is not None
    assert (boots.visual_item_name, boots.visual_variant_id) == (
        "Leather Boots",
        "b0000009",
    )
    alternate_shoes = _inventory_item(fighter, "Cloth Shoes")
    helmet = _inventory_item(fighter, "Iron Helmet", "h0000008")
    equippable = fighter.get_equippable_items()
    assert any(
        row["item_uuid"] == str(alternate_shoes.uuid)
        for row in equippable["boots"]
    )
    assert any(
        row["item_uuid"] == str(helmet.uuid)
        for row in equippable["helmet"]
    )

    original_boots = fighter.equipment.boots
    assert original_boots is not None
    old_boots_uuid = original_boots.uuid
    assert fighter.equip_item(alternate_shoes.uuid, BodyPart.FEET)
    swapped_boots = _slot_item(fighter, "boots")
    assert swapped_boots is not None
    assert swapped_boots.name == "Cloth Shoes"
    assert swapped_boots.visual_variant_id is None
    assert old_boots_uuid in fighter.inventory.items
    assert fighter.equip_item(helmet.uuid, BodyPart.HEAD)
    equipped_helmet = _slot_item(fighter, "helmet")
    assert equipped_helmet is not None
    assert equipped_helmet.visual_variant_id == "h0000008"
