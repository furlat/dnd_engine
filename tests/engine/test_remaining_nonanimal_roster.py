"""Original source queue closes against registered recipes, including retained NPCs."""

import csv
from collections import Counter
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.monsters.demon_variants import CORROSIVE_DEMON_RECIPE, DREAD_DEMON_RECIPE
from dnd.monsters.fiends import FIEND_RECIPES_BY_ID
from dnd.monsters.goblins import GOBLIN_RECIPES_BY_ID
from dnd.monsters.remaining_fiends import REMAINING_FIEND_DEFINITIONS, REMAINING_FIEND_RECIPES_BY_ID
from dnd.monsters.roster_humanoids import HUMANOID_ROSTER_DEFINITIONS, HUMANOID_ROSTER_RECIPES_BY_ID
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.monsters.undead_roster import UNDEAD_DEFINITIONS, UNDEAD_ROSTER_RECIPES_BY_ID
from dnd.monsters.zombie_roster import ZOMBIE_DEFINITIONS, ZOMBIE_ROSTER_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime


AUDIT = Path(__file__).resolve().parents[2] / "agent_docs/audits/nonanimal-roster-20261018"
with (AUDIT / "roster_inventory.csv").open(newline="") as source:
    SOURCE_ROWS = tuple(csv.DictReader(source))
with (AUDIT / "native_authoring.csv").open(newline="") as source:
    COMPLETION_ROWS = tuple(csv.DictReader(source))
ADMITTED = tuple(row for row in COMPLETION_ROWS if row["selected_native_ref"])
RECIPES = {recipe.ref.identity_key: recipe for recipes in (
    BESTIARY_CREATURE_RECIPES_BY_ID, GOBLIN_RECIPES_BY_ID, FIEND_RECIPES_BY_ID,
    SRD_CREATURE_RECIPES_BY_ID, REMAINING_FIEND_RECIPES_BY_ID,
    HUMANOID_ROSTER_RECIPES_BY_ID, UNDEAD_ROSTER_RECIPES_BY_ID, ZOMBIE_ROSTER_RECIPES_BY_ID,
) for recipe in recipes.values()}
RECIPES.update({recipe.ref.identity_key: recipe for recipe in (CORROSIVE_DEMON_RECIPE, DREAD_DEMON_RECIPE)})


def test_original_180_source_rows_have_exact_native_dispositions():
    assert len(SOURCE_ROWS) == len(COMPLETION_ROWS) == 180
    for source, completed in zip(SOURCE_ROWS, COMPLETION_ROWS, strict=True):
        assert all(completed[key] == value for key, value in source.items())
        if source["existing_native_refs"]:
            assert completed["selected_native_ref"] == source["existing_native_refs"]
        elif source["planning_disposition"].startswith("candidate"):
            assert completed["native_status"] == "authored_new"
        else:
            assert not completed["selected_native_ref"]
    assert Counter(row["native_status"] for row in COMPLETION_ROWS) == {
        "authored_new": 123, "retained_existing": 20, "retained_existing_reconciled": 5,
        "hold_visual_decision": 8, "exclude_modern": 24,
    }
    assert len({row["selected_native_ref"] for row in ADMITTED}) == 148
    source_keys = [(row.pack, row.source_variant) for row in (*ZOMBIE_DEFINITIONS, *HUMANOID_ROSTER_DEFINITIONS)]
    source_keys += [("undead", row.source_variant) for row in UNDEAD_DEFINITIONS]
    source_keys += [("demons", row.source_variant) for row in REMAINING_FIEND_DEFINITIONS]
    expected = {(row["pack"], row["source_variant"]) for row in SOURCE_ROWS
                if row["planning_disposition"].startswith("candidate") and not row["existing_native_refs"]}
    assert len(source_keys) == len(set(source_keys)) == 123
    assert set(source_keys) == expected
    selected_refs = {}
    for definitions, recipes, pack in (
        (ZOMBIE_DEFINITIONS, ZOMBIE_ROSTER_RECIPES_BY_ID, None),
        (HUMANOID_ROSTER_DEFINITIONS, HUMANOID_ROSTER_RECIPES_BY_ID, None),
        (UNDEAD_DEFINITIONS, UNDEAD_ROSTER_RECIPES_BY_ID, "undead"),
        (REMAINING_FIEND_DEFINITIONS, REMAINING_FIEND_RECIPES_BY_ID, "demons"),
    ):
        for definition in definitions:
            source_pack = pack if pack is not None else definition.pack
            selected_refs[(source_pack, definition.source_variant)] = recipes[definition.key].ref.identity_key
    for row in COMPLETION_ROWS:
        if row["native_status"] == "authored_new":
            assert selected_refs[(row["pack"], row["source_variant"])] == row["selected_native_ref"]


@pytest.mark.parametrize("row", ADMITTED, ids=lambda row: f'{row["pack"]}/{row["source_variant"]}')
@pytest.mark.parametrize("mode", tuple(CreaturePossessionMode))
def test_every_admitted_source_materializes_its_selected_registered_recipe(row, mode):
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    try:
        recipe = RECIPES[row["selected_native_ref"]]
        actor = materialize_creature(recipe, runtime_entity_uuid=uuid4(),
            display_name=row["selected_name"] or row["source_variant"], faction="roster",
            position=(2, 2), deployment_role=CreatureDeploymentRole(role_id="tests.roster_closure"),
            possession_mode=mode)
        actor.compose_entity()
        game.deploy_entity(actor, actor.position)
        assert actor.content_ref == recipe.ref
        assert actor.get_hp() > 0
        assert actor.registered_actions
        assert not any(name.startswith("Summon") for name in actor.active_conditions)
        if mode is CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY:
            assert all(item.intrinsic_owner_uuid == actor.uuid for item in actor.equipment.get_all_equipped_items())
    finally:
        game.close()
        reset_engine_runtime()
