"""Native generic actions play ordered child groups on the shared body clock."""

from dataclasses import replace
import json
from pathlib import Path
from types import MappingProxyType
from uuid import UUID, uuid4

import pytest

from dnd.actions_functional import execute_available_action, get_available_actions, setup_standard_actions
from dnd.blocks.health import HealthConfig
from dnd.conditions import Concentrating
from dnd.controller import HumanController
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue
from dnd.entity import Entity, EntityConfig
from dnd.encounter import Encounter
from dnd.game import Game
from dnd.monsters.beasts import BEAST_RECIPES_BY_ID
from dnd.monsters.fiends import FIEND_RECIPES_BY_ID
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.monsters.traits import MultiattackAction
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.animation import ActorContact
from game.animation_data import load_animation_data
from game.attack import BoundAttack
from game.body_presentation import sample_body_presentation
from game.choreography import bind_choreography, sample_choreography
from game.combat import actor_contact, actor_is_visible
from game.condition_types import ConditionRecipe
from dnd.player.facts import ActionFact
from dnd.player.reduction import reduce_lineage
from dnd.player.capture import capture_interval, capture_lineage, reduce_interval
from dnd.player.recorded import capture_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json"))))


@pytest.fixture(scope="module", params=tuple((form, second_misses)
    for form in ("brown_bear", "dretch", "huntsman_wing_devil") for second_misses in (False, True)))
def multiattack(request):
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        recipes = {**BEAST_RECIPES_BY_ID, **FIEND_RECIPES_BY_ID,
                   "dretch": SRD_CREATURE_RECIPES_BY_ID["dretch"]}
        form, second_misses = request.param
        owner = materialize_creature(recipes[form], runtime_entity_uuid=uuid4(),
            display_name=form, faction="creatures", position=(4, 3),
            deployment_role=CreatureDeploymentRole(role_id="test.multiattack"),
            possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS)
        victim = Entity.create(uuid4(), "Target", config=EntityConfig(position=(3, 3), faction="targets",
            health=HealthConfig(max_hit_points_bonus=500)))
        setup_standard_actions(victim)
        for actor, position in ((owner, (4, 3)), (victim, (3, 3))):
            actor.compose_entity()
            game.deploy_entity(actor, position)
        encounter = Encounter(name="Multiattack playback", source_entity_uuid=owner.uuid)
        for actor in (owner, victim):
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(15, 1):
            encounter.start_encounter()
        encounter.start_turn()
        if encounter.get_current_entity() is not owner:
            encounter.next_turn()
        applied = victim.add_condition(Concentrating(source_entity_uuid=victim.uuid,
            target_entity_uuid=victim.uuid, spell_name="Existing held spell"))
        assert applied is not None
        Entity.update_all_entities_senses()
        initialization = capture_interval(name="Before multiattack", start_cursor=0,
            end_cursor=EventQueue.event_cursor(), observer_uuid=owner.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initialization)
        row = next(row for row in get_available_actions(owner, legal_only=True).all_actions
                   if row.behavior_id == "action.monster.multiattack")
        choice = next(choice for choice in row.valid_targets if choice.target_uuid == victim.uuid)
        template = next(action for action in owner.registered_actions if isinstance(action, MultiattackAction))
        faces = []
        attack_number = 0
        for slot, repetitions in template.attack_sequence:
            weapon = owner.equipment.get_weapon(slot)
            assert weapon is not None
            for _ in range(repetitions):
                attack_number += 1
                if attack_number == 2 and second_misses:
                    faces.append(1)
                    continue
                faces.extend((15, *([1] * weapon.dice_numbers)))
                if attack_number == 1:
                    faces.append(1)  # The first hit fails the real concentration save.
        with fixed_dice_faces(*faces):
            result = execute_available_action(owner, row, choice)
        assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
        assert "Concentrating" not in victim.active_conditions
        captured = capture_history(before, (capture_lineage(result, observer_uuid=owner.uuid),))
        return player_history(captured)
    finally:
        game.close()
        reset_engine_runtime()


def test_native_multiattack_plays_each_body_once_and_keeps_historical_hp(multiattack, data):
    before, roots = multiattack
    root, = (row for row in roots if isinstance(row.root.fact, ActionFact)
             and row.root.fact.behavior_id == "action.monster.multiattack")
    # The ordinary scene supplies placed contacts from the head's entry state.
    # Child attacks must preserve their placement without restoring entry HP.
    contacts = {str(actor.uuid): actor_contact(before, actor, data)
                for actor in before.actors.values() if actor_is_visible(before, actor)}
    group = bind_choreography(before, root, data, contacts=contacts)
    first, second = group.nodes
    assert isinstance(first.bound, BoundAttack) and isinstance(second.bound, BoundAttack)
    assert first.start_ms == 0
    assert second.start_ms == pytest.approx(first.start_ms + first.bound.timeline.complete_ms)
    assert not group.gaps
    parent, = group.body_actions
    assert not parent.enabled  # Existing source multiattack has no extra gesture.
    assert group.after == reduce_lineage(before, root)
    source = first.bound.timeline.source.actor_uuid
    assert isinstance(first.bound.timeline.target, ActorContact)
    target = first.bound.timeline.target.actor_uuid
    for node in (first, second):
        assert isinstance(node.bound, BoundAttack)
        at = node.start_ms + 1
        shown = sample_body_presentation(before, group.after, data, at, at, {}, choreography=group)
        pose, = (row for row in shown.poses if row.actor.contact.actor_uuid == source)
        assert pose.body.clip == node.bound.timeline.clip and pose.body.frame == 0
    preceding = sample_choreography(group, second.start_ms - .01)
    assert next(value.hp for value in preceding.vitals if value.actor_uuid == target) == first.bound.timeline.resulting_hp
    next_start = sample_choreography(group, second.start_ms + .01)
    assert next(value.hp for value in next_start.vitals if value.actor_uuid == target) == first.bound.timeline.resulting_hp
    final = sample_choreography(group, group.complete_ms)
    assert next(value.hp for value in final.vitals if value.actor_uuid == target) == group.after.actors[UUID(target)].normal_hp
    assert final.complete
    assert sample_choreography(group, second.start_ms - .01) == preceding


def test_next_native_attack_waits_for_entire_condition_child(multiattack, data):
    before, roots = multiattack
    root, = (row for row in roots if isinstance(row.root.fact, ActionFact)
             and row.root.fact.behavior_id == "action.monster.multiattack")
    recipe = data.condition_recipes["condition.concentrating"].model_dump(mode="json")
    recipe["persistent"]["alphaMultiplier"] = .4
    recipe["removal"]["durationMs"] = 2500
    authored = replace(data, condition_recipes=MappingProxyType({**data.condition_recipes,
        "condition.concentrating": ConditionRecipe.model_validate_json(json.dumps(recipe))}))
    group = bind_choreography(before, root, authored)
    first, second = group.nodes
    transition, = group.conditions
    assert transition.complete_ms > first.bound.timeline.body_end_ms
    assert second.start_ms == pytest.approx(transition.complete_ms)
    assert first.bound.timeline.complete_ms == pytest.approx(transition.complete_ms)
    waiting = sample_choreography(group, transition.complete_ms - 1)
    assert len(waiting.clips) == 1 and not waiting.complete
    assert group.after == reduce_lineage(before, root)
