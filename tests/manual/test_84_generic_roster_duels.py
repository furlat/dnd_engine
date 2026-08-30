"""Canonical arbitrary-roster duel composition regressions."""

from __future__ import annotations

import random

from dnd.content_system.item_bindings import ITEM_RUNTIME_BINDINGS
from dnd.core.content.encounters import (
    EncounterRecipe,
    EncounterRosterSlot,
    FixedRosterOpeningPolicy,
    InitiativeOpeningPolicy,
    RosterControllerDefaults,
    RosterControllerKind,
)
from dnd.entity import Entity
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.items.apparel_presets import (
    DARK_CLOTH_SHOES_PRESET,
    HEDGE_WIZARD_ROBE_PRESET,
)
from dnd.scenarios.encounter_assembler import (
    AssembledEncounter,
    assemble_encounter_recipe,
)
from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS_BY_ID,
    roster_recipe,
)


def _assemble_duel(
    first_roster_id: str,
    second_roster_id: str,
    *,
    opening_roster_slot_id: str | None,
) -> AssembledEncounter:
    deployment = AUTHORED_DEPLOYMENTS_BY_ID[
        "neutral.battlefield.open_floor_bright"
    ]
    first = roster_recipe(first_roster_id)
    second = roster_recipe(second_roster_id)
    opening = (
        FixedRosterOpeningPolicy(
            roster_slot_id=opening_roster_slot_id,
        )
        if opening_roster_slot_id is not None
        else InitiativeOpeningPolicy()
    )
    reset_engine_runtime()
    return assemble_encounter_recipe(
        EncounterRecipe.create(
            encounter_id="encounter.test.generic_roster_duel",
            title="Generic Roster Duel",
            roster_slots=(
                EncounterRosterSlot(
                    roster_slot_id="roster_1",
                    roster=first,
                    faction_id="faction_1",
                    deployment_zone_id="zone_1",
                    controller_defaults=RosterControllerDefaults(
                        controller=RosterControllerKind.AI,
                        participant_name=first.title,
                        policy_id="builtin.basic",
                    ),
                ),
                EncounterRosterSlot(
                    roster_slot_id="roster_2",
                    roster=second,
                    faction_id="faction_2",
                    deployment_zone_id="zone_2",
                    controller_defaults=RosterControllerDefaults(
                        controller=RosterControllerKind.AI,
                        participant_name=second.title,
                        policy_id="builtin.basic",
                    ),
                ),
            ),
            battlefield_id=deployment.battlefield_id,
            deployment=deployment,
            opening_policy=opening,
            tags=("test",),
        ),
        game=Game(),
    )


def test_generic_duel_assembles_two_multi_actor_creature_rosters() -> None:
    random.seed(20260718)
    assembled = _assemble_duel(
        "monsters.skeleton_trio",
        "monsters.goblin_water_cell",
        opening_roster_slot_id="roster_2",
    )
    first = assembled.entities_by_roster_slot["roster_1"]
    second = assembled.entities_by_roster_slot["roster_2"]

    assert len(first) == 3
    assert len(second) == 3
    assert {actor.faction for actor in first} == {"faction_1"}
    assert {actor.faction for actor in second} == {"faction_2"}
    assert set(assembled.encounter.combatants) == {
        actor.uuid for actor in (*first, *second)
    }
    assert set(assembled.controllers) == set(assembled.encounter.combatants)
    current = assembled.encounter.get_current_entity()
    assert current is not None
    assert current.faction == "faction_2"
    assert all(actor.senses.visible for actor in (*first, *second))

    assert tuple(
        actor.content_ref.content_id
        for actor in second
        if actor.content_ref is not None
    ) == (
        "creature.goblin",
        "creature.goblin_archer",
        "creature.goblin_caster",
    )
    goblin_caster = second[2]
    assert goblin_caster.equipment.body_armor is not None
    assert ITEM_RUNTIME_BINDINGS.require(
        goblin_caster.equipment.body_armor.uuid,
    ).recipe == HEDGE_WIZARD_ROBE_PRESET.recipe
    assert goblin_caster.equipment.boots is not None
    assert ITEM_RUNTIME_BINDINGS.require(
        goblin_caster.equipment.boots.uuid,
    ).recipe == DARK_CLOTH_SHOES_PRESET.recipe


def test_mirrored_roster_keeps_runtime_identity_isolated_by_faction() -> None:
    assembled = _assemble_duel(
        "monsters.skeleton_trio",
        "monsters.skeleton_trio",
        opening_roster_slot_id=None,
    )
    first = assembled.entities_by_roster_slot["roster_1"]
    second = assembled.entities_by_roster_slot["roster_2"]

    assert first[0].name == second[0].name
    assert first[0].position != second[0].position
    assert first[0].uuid != second[0].uuid
    assert first[0].faction == "faction_1"
    assert second[0].faction == "faction_2"


def test_character_style_and_creature_rosters_share_one_assembler() -> None:
    assembled = _assemble_duel(
        "hero.sorcerer_l5_standard_torch",
        "monsters.skeleton_trio",
        opening_roster_slot_id=None,
    )
    first = assembled.entities_by_roster_slot["roster_1"]
    second = assembled.entities_by_roster_slot["roster_2"]

    assert len(first) == 1
    assert len(second) == 3
    assert all(
        Entity.get(actor.uuid) is actor for actor in (*first, *second)
    )

