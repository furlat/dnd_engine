"""Real Fear cone casts: failed/successful saves, an outside actor and native clear."""

import random
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.catalog_content import SPELL_CONTENT_IDENTITY_BY_NAME
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def fear_history(*, direction: tuple[int, int] = (0, 1)) -> CapturedHistory:
    assert direction in ((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))
    dx,dy = direction
    positions = (("caster", (7,7)), ("recipient", (7+2*dx,7+2*dy)),
                 ("second", (7+3*dx,7+3*dy)), ("bystander", (7-3*dy,7+3*dx)))
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        for role, position in positions:
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction="heroes" if role == "caster" else "monsters",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    wisdom=AbilityConfig(ability_score=1 if role == "recipient" else 30 if role == "second" else 10)),
                action_economy=ActionEconomyConfig(spell_slots={3: 3}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10,
                    hit_dice_count=12, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22")))
            actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, SPELL_CONTENT_IDENTITY_BY_NAME['Fear'].spell_type, caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["recipient"]
        encounter = Encounter(name="Fear native cone and real source clear", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10, 10, 10):
            encounter.start_encounter()
        encounter.start_turn()

        def perform(actor: Entity, behavior: str, destination: tuple[int, int]) -> None:
            while encounter.get_current_entity() is not actor:
                with fixed_dice_faces(*([1] * 40)):
                    encounter.next_turn()
            choices = [(action, selection) for action in get_available_actions(actor).all_actions
                if action.behavior_id == behavior for selection in action.valid_targets
                if selection.position is not None and (
                    selection.position == destination if behavior != 'spell.fear' else
                    (selection.position[0]-7)*dy == (selection.position[1]-7)*dx
                    and (selection.position[0]-7)*dx + (selection.position[1]-7)*dy > 0)]
            assert choices, (behavior, destination)
            with fixed_dice_faces(*([10] * 40)):
                result = execute_available_action(actor, *choices[0])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION

        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Fear initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        perform(caster, 'spell.fear', (7+dx,7+dy))
        assert {'Fear', 'Frightened'} <= set(recipient.active_conditions)
        assert 'Fear' not in actors['second'].active_conditions
        assert 'Frightened' not in actors['second'].active_conditions
        assert 'Fear' not in actors['bystander'].active_conditions
        assert 'Frightened' not in caster.active_conditions
        # Record today's rules without inventing animation-driven fleeing.
        assert recipient.position == positions[1][1]
        perform(caster, 'action.move', (7-dy,7+dx))
        caster.remove_condition('Concentrating')
        assert 'Fear' not in recipient.active_conditions
        assert 'Frightened' not in recipient.active_conditions
        perform(recipient, 'action.move', (positions[1][1][0]+dy,positions[1][1][1]-dx))
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "recipient")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
