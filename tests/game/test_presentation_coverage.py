"""Loaded bindings and received lineages produce honest developer coverage.

These assertions concern the report, not how its inventory is assembled. Native
scenario helpers supply real event histories; reporting never reruns gameplay.
"""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion
from game.player_facts import ActionFact
from game.player_reduction import reduce_lineage
from game.presentation_coverage import lineage_coverage, missing_observed_bindings, presentation_inventory
from tests.game.concealment_scenarios import concealment_history
from tests.game.player_helpers import player_history
from tests.game.scenarios import attack_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data(rig_files=(Path("game/data/rigs/goblin01.json"),))


def test_initialized_inventory_distinguishes_missing_casts_partial_tracks_and_accepted_omissions(data):
    rows = presentation_inventory(data, spell_ids=("spell.fire_bolt", "spell.new_registered_spell"))
    indexed = {(row["family"], row["identity"]): row for row in rows}
    assert indexed["spell", "spell.fire_bolt"]["status"] == "binding_selected"
    missing = indexed["spell", "spell.new_registered_spell"]
    assert missing["status"] == "missing_binding" and missing["binding"] is None
    assert "child outcomes" in missing["details"][0]
    potion = indexed["action", "action.item.potion_true_seeing.drink"]
    assert potion["binding"] == "action.item.potion_greater_invisibility.drink"
    assert potion["status"] == "binding_selected"
    assert indexed["action_source_media", potion["identity"]]["status"] == "accepted_omission"
    assert indexed["condition", "condition.consumable.weapon_coat.fire"]["status"] == "partial"
    assert indexed["fact", "turn"]["status"] == "state_only"
    assert all("observed" not in row for row in rows)
    json.dumps(rows)  # An ordinary TS/browser-consumable report, without Python-only values.


def test_future_authored_action_does_not_inherit_potion_media_approval(data):
    original = data.body_action_recipes["action.item.potion_healing.drink"]
    identity = "action.review_new_source_media"
    recipe = original.model_copy(update={"definitionRef": original.definitionRef.model_copy(update={"content_id": identity})})
    authored = replace(data, body_action_recipes={**data.body_action_recipes, identity: recipe})
    rows = presentation_inventory(authored)
    row, = (row for row in rows if row["family"] == "action_source_media" and row["identity"] == identity)
    assert row["status"] == "partial"


@pytest.mark.parametrize("opportunity", (False, True))
def test_bound_attack_and_parent_owned_damage_have_received_event_evidence(data, opportunity):
    before, lineages = player_history(attack_history("weapon.longsword", 17, opportunity=opportunity,
                                                    whole_movement=opportunity))
    initial = before
    evidence = []
    for lineage in lineages:
        motion = bind_motion(before, lineage, data)
        group = None if motion is not None else bind_choreography(before, lineage, data)
        rows = lineage_coverage(lineage, group=group, motion=motion)
        assert all(row["event_uuid"] is None or row["event_uuid"] in {str(node.uuid) for node in lineage.events}
                   for row in rows)
        evidence.extend(rows)
        before = reduce_lineage(before, lineage)
    attacks = [row for row in evidence if row["family"] == "fact" and row["identity"] == "attack"]
    assert attacks and all(row["observed"] == "bound" for row in attacks)
    damage = [row for row in evidence if row["family"] == "fact" and row["identity"] == "damage"]
    assert damage and all(row["observed"] == "parent_owned" for row in damage)
    assert not any(row["issues"] for row in damage)
    if not opportunity:
        without_attack = replace(data, attack_recipes={})
        group = bind_choreography(initial, lineages[0], without_attack)
        observed = lineage_coverage(lineages[0], group=group)
        missing = missing_observed_bindings(presentation_inventory(without_attack), observed)
        row, = (row for row in missing if row["family"] == "attack")
        assert row["identity"] == "action.attack" and row["status"] == "missing_binding"
        assert any(row["issues"] for row in observed if row["family"] == "attack")


def test_missing_selected_action_reports_gap_without_inventing_a_cue(data):
    history = concealment_history(sight_grant="potion", reveal="none")
    before, lineages = player_history(history, role="perceiver")
    for lineage in lineages:
        fact = lineage.root.fact
        if isinstance(fact, ActionFact) and fact.behavior_id == "action.item.potion_true_seeing.drink":
            break
        before = reduce_lineage(before, lineage)
    else:
        raise AssertionError("Native potion history did not contain its drink action")
    selected = data.body_action_bindings[fact.behavior_id].source_recipe
    missing = replace(data, body_action_recipes={identity: recipe for identity, recipe in data.body_action_recipes.items()
                                                if identity != selected})
    group = bind_choreography(before, lineage, missing)
    evidence = lineage_coverage(lineage, group=group)
    row, = (row for row in evidence if row["family"] == "action" and row["event_uuid"] == str(lineage.root.uuid))
    assert row["observed"] == "received" and not group.body_actions
    assert any(issue["code"] == "binding_gap" and "Missing body-action recipe" in issue["detail"]
               for issue in row["issues"])
    # The real child state still reduces when the actor presentation is missing.
    assert group.after == reduce_lineage(before, lineage)
