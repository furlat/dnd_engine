"""Native barrel stories survive a public-only save and replay."""

import pytest

from dnd.core.creature_types import DamageType
from dnd.core.events import EventQueue
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity
from game.player_facts import ConditionChangeFact, DamageFact, ObjectDestroyedFact, SavingThrowFact
from game.player_reduction import reduce_lineage
from tests.game.liquid_barrel_scenarios import liquid_barrel_history
from tests.game.test_environment_presentation import _saved


LIQUIDS = ("oil", "water", "grease", "poison", "blood", "dread_blood")
SURFACE_IDS = {"oil": "spatial_effect.material.oil", "water": "spatial_effect.material.water_surface",
               "grease": "spatial_effect.spell.grease"}
RESIDUE_IDS = {"poison": "residue.poison", "blood": "residue.blood", "dread_blood": "residue.dread_blood"}
SPILL_CELLS = {(x, y) for x in range(4, 7) for y in range(3, 6)}


def check_floor(state, liquid):
    assert state.senses is not None
    if liquid in SURFACE_IDS:
        surface, = (effect for effect in state.senses.spatial_effects.values()
                    if effect.content_ref.content_id == SURFACE_IDS[liquid])
        assert set(surface.positions) == SPILL_CELLS
    else:
        assert {position for position, tile in state.tiles.items()
                if any(row.residue_id == RESIDUE_IDS[liquid] for row in tile.residues)} == SPILL_CELLS
        for position in SPILL_CELLS:
            residue, = (row for row in state.tiles[position].residues
                        if row.residue_id == RESIDUE_IDS[liquid])
            assert residue.amount == (5 if liquid == "blood" else 1)


@pytest.mark.parametrize("liquid,saved,jump", [(liquid, True, False) for liquid in LIQUIDS]
    + [("grease", False, False), ("dread_blood", False, False),
       ("poison", True, True), ("water", True, True), ("grease", False, True)])
def test_two_observers_replay_breakage_and_actual_liquid_contact(liquid, saved, jump):
    history = liquid_barrel_history(liquid=liquid, saved=saved, jump=jump)
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0
    assert set(history.views) == {"traveler", "witness"}
    for role, native in history.views.items():
        state, roots = _saved(native)
        barrel, = (obj for obj in state.objects.values()
                   if obj.item.item_id == f"environment.blocker.{liquid}_barrel")
        traveler, = (actor for actor in state.actors.values() if actor.name == "Traveler")
        initial_hp = traveler.normal_hp
        facts = []
        for root in roots:
            facts.extend(node.fact for node in root.events)
            state = reduce_lineage(state, root)
        breaks = [fact for fact in facts if isinstance(fact, ObjectDestroyedFact)
                  and fact.object_uuid == barrel.item.item_uuid]
        assert len(breaks) == 1, role
        assert state.objects[barrel.item.item_uuid].item.integrity is ItemIntegrity.DESTROYED
        check_floor(state, liquid)
        actor = state.actors[traveler.uuid]
        assert actor.normal_hp == initial_hp - (4 if liquid == "poison" else 0)
        conditions = [fact for fact in facts if isinstance(fact, ConditionChangeFact)
                      and fact.target_entity_uuid == traveler.uuid]
        if liquid == "water":
            assert any(fact.condition.name == "Wet" for fact in conditions)
        if liquid in ("grease", "dread_blood"):
            saves = [fact for fact in facts if isinstance(fact, SavingThrowFact)
                     and fact.target_entity_uuid == traveler.uuid]
            # Grease also saves on appearance around the adjacent attacker.
            assert saves and (all(fact.succeeded for fact in saves) if saved
                              else any(not fact.succeeded for fact in saves))
            if not saved:
                assert any(fact.condition.name == ("Prone" if liquid == "grease" else "Frightened")
                           for fact in conditions)
        if liquid == "poison":
            damages = [fact for fact in facts if isinstance(fact, DamageFact)
                       and fact.target_entity_uuid == traveler.uuid and fact.stage == "applied"]
            assert len(damages) == 2 and all(fact.damage_type is DamageType.POISON for fact in damages)
        assert not {"Wet", "Prone", "Frightened"}.intersection(row.name for row in actor.conditions)
    assert not Entity.get_all_entities() and EventQueue.event_cursor() == 0


@pytest.mark.parametrize("liquid", LIQUIDS)
def test_late_observation_contains_wreck_and_liquid_without_replaying_breakage(liquid):
    history = liquid_barrel_history(liquid=liquid, late_snapshot=True)
    for native in history.views.values():
        state, roots = _saved(native)
        assert not roots
        wreck, = (obj for obj in state.objects.values()
                  if obj.item.item_id == f"environment.blocker.{liquid}_barrel")
        assert wreck.item.integrity is ItemIntegrity.DESTROYED
        check_floor(state, liquid)


@pytest.mark.parametrize("layout", ("door-closed", "door-open"))
def test_saved_spill_observations_respect_door_boundary(layout):
    history = liquid_barrel_history(liquid="oil", layout=layout)
    for role, native in history.views.items():
        state, roots = _saved(native)
        for root in roots:
            state = reduce_lineage(state, root)
        assert state.senses is not None
        surface, = (effect for effect in state.senses.spatial_effects.values()
                    if effect.content_ref.content_id == SURFACE_IDS["oil"])
        positions = set(surface.positions)
        assert positions and positions <= SPILL_CELLS
        if role == "traveler":
            assert ((6, 4) in positions) is (layout == "door-open")
        if layout == "door-closed":
            assert all(x <= 5 for x, _ in positions)


def test_saved_center_landing_retains_fear_until_manual_pool_exit():
    history = liquid_barrel_history(liquid="dread_blood", saved=False, jump=True, landing="center")
    for native in history.views.values():
        state, roots = _saved(native)
        traveler, = (actor for actor in state.actors.values() if actor.name == "Traveler")
        saves = []
        feared_positions = set()
        for root in roots:
            saves.extend(node.fact for node in root.events if isinstance(node.fact, SavingThrowFact)
                         and node.fact.target_entity_uuid == traveler.uuid)
            state = reduce_lineage(state, root)
            actor = state.actors[traveler.uuid]
            if any(row.name == "Frightened" for row in actor.conditions):
                feared_positions.add(actor.last_visual_position)
        assert len(saves) == 1 and not saves[0].succeeded
        assert (6, 4) in feared_positions
        actor = state.actors[traveler.uuid]
        assert actor.last_visual_position == (7, 4)
        assert not any(row.name == "Frightened" for row in actor.conditions)
        check_floor(state, "dread_blood")
