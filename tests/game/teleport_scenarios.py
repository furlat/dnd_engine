"""One discovered Misty Step, saved from caster and witness viewpoints."""

import random
from uuid import uuid4

from dnd.actions import AttackEvent, SpellEvent
from dnd.actions_functional import execute_by_index, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue, SpatialChangeEvent, SpatialChangeType, StepMovementEvent
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import MistyStep
from dnd.types.senses import SenseMode, SensesType
from dnd.types.world import OccupancyLayer
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def teleport_history(
    *, battlefield_id: str = "battlefield.open_floor_bright",
    caster_position: tuple[int, int] = (3, 3),
    witness_position: tuple[int, int] = (4, 3),
    destination: tuple[int, int] = (7, 3),
    caster_layer: OccupancyLayer = OccupancyLayer.GROUND,
) -> CapturedHistory:
    """Capture a legal native cast without movement paths or presentation delays.

    Dark proving maps use actors with native, recorded Darkvision; bright-map
    experiments retain ordinary vision, including both doorway viewpoints.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    built = build_battlefield(battlefield_id)
    game = Game()
    try:
        actors: dict[str, Entity] = {}
        for role, position in (("caster", caster_position), ("witness", witness_position)):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "caster" else "enemies",
                occupancy_layer=caster_layer if role == "caster" else OccupancyLayer.GROUND,
                health=HealthConfig(hit_dices=[HitDiceConfig(
                    hit_dice_value=10, hit_dice_count=8, mode="maximums",
                )]),
                action_economy=ActionEconomyConfig(spell_slots={2: 2} if role == "caster" else {}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            if built.definition.light_level == "darkness":
                actor.senses.add_sense_mode_source(actor.uuid,
                    SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, MistyStep, caster_level=3)
            actor.compose_entity()
            actors[role] = actor
        caster, witness = actors["caster"], actors["witness"]
        add_opportunity_attack_handler(witness)
        for actor in actors.values():
            game.deploy_entity(actor, actor.position)
        encounter = Encounter(name="Paired Misty Step experiment", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()

        available = get_available_actions(caster)
        choices = [
            (row, target) for row in available.all_actions if row.behavior_id == "spell.misty_step"
            for target in row.valid_targets if target.position == destination
        ]
        if not choices:
            raise ValueError(f"No discovered Misty Step from {caster_position} to {destination} in {battlefield_id}")
        row, target = choices[0]
        assert target.path is None and not target.opportunity_attack_exposures
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="teleport initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        resources = (caster.action_economy.bonus_actions.normalized_score,
                     caster.action_economy.spell_slot_2.normalized_score,
                     caster.action_economy.movement.normalized_score,
                     witness.action_economy.reactions.normalized_score)
        root = execute_by_index(caster, row.template_name, target.index, available=available)
        assert isinstance(root, SpellEvent) and not root.canceled and root.phase is EventPhase.COMPLETION
        assert caster.position == destination
        assert (caster.action_economy.bonus_actions.normalized_score,
                caster.action_economy.spell_slot_2.normalized_score,
                caster.action_economy.movement.normalized_score,
                witness.action_economy.reactions.normalized_score) == (
                    resources[0] - 1, resources[1] - 1, resources[2], resources[3],
                )
        completed = [event for _, event in EventQueue.iter_events_since(baseline)
                     if event.phase is EventPhase.COMPLETION]
        assert not any(isinstance(event, (StepMovementEvent, AttackEvent)) for event in completed)
        positions = [event for event in completed if isinstance(event, SpatialChangeEvent)
                     and event.entity_uuid == caster.uuid
                     and event.change_type in (SpatialChangeType.ENTITY_LEFT, SpatialChangeType.ENTITY_ENTERED)]
        assert [(event.change_type, event.position) for event in positions] == [
            (SpatialChangeType.ENTITY_LEFT, caster_position), (SpatialChangeType.ENTITY_ENTERED, destination),
        ]
        assert all(event.parent_lineage == root.lineage_uuid for event in positions)
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
