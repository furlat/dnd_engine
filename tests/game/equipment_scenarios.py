"""Native same-turn equipment histories for gameplay tests and clip review."""

from dataclasses import replace
import random
from typing import Literal
from uuid import uuid4

from dnd.actions import AttackEvent
from dnd.actions_functional import execute_by_index, get_available_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.content.characters.builds import create_character
from dnd.content.characters.premades import FIGHTER_PREMADE_ID, PREMADE_CHARACTER_BUILDS
from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.equipment_types import BodyPart, WeaponSet, WeaponSlot
from dnd.core.events import EntityCreatedEvent, EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from game.presentation import (
    CompletedLineage, PresentationTarget, capture_interval, capture_lineage,
    reduce_interval, reduce_lineage, seed_actors,
)


def equipment_sequence_history(
    *, replacement: Literal["weapon", "wardrobe"] = "weapon", attacks: bool = True,
) -> tuple[PresentationTarget, tuple[CompletedLineage, ...]]:
    """Melee, a public item replacement and ranged Extra Attack in one turn.

    Attack owns weapon-set activation. The replacement changes item membership;
    it does not manufacture an independent draw-weapon action or debit.
    """
    previous = random.getstate()
    reset_engine_runtime()
    battlefield = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        build = PREMADE_CHARACTER_BUILDS[FIGHTER_PREMADE_ID]
        build = replace(build, item_loadout=(*build.item_loadout,
            ItemLoadoutEntry("apparel.robes.red_mage")))
        fighter = create_character(build, faction="heroes", position=(3, 3))
        targets = tuple(Entity.create(uuid4(), name, config=EntityConfig(
            position=position, faction="enemies",
            appearance=AppearanceConfig(body_category="NakedBody", head_category="Head22", has_beard=False),
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
        )) for name, position in (("Near target", (4, 3)), ("Far target", (8, 3))))
        for target in targets:
            target.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", target.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", target.uuid), BodyPart.FEET),
            ))
            target.compose_entity()
        actors = (fighter, *targets)
        for actor in actors:
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Equipment in one turn", source_entity_uuid=fighter.uuid)
        for actor in actors:
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not fighter:
            encounter.next_turn()
        cursor = EventQueue.event_cursor()
        startup = capture_interval(name="equipment turn", start_cursor=0, end_cursor=cursor,
            observer_uuid=fighter.uuid, battlefield_id=battlefield.definition.battlefield_id,
            seed_cursor=cursor, seed_snapshot=capture_senses_snapshot(fighter.senses))
        baseline, _ = reduce_interval(None, startup)
        actor_ids = {actor.uuid for actor in actors}
        births = tuple(event for _, event in EventQueue.iter_events_since(0)
                       if isinstance(event, EntityCreatedEvent) and event.entity_uuid in actor_ids)
        before = seed_actors(baseline, births,
            active_weapon_sets={actor.uuid: actor.equipment.active_weapon_set for actor in actors})
        latest = before
        history: list[CompletedLineage] = []

        def retain(start: int) -> None:
            nonlocal latest
            roots = tuple(event for _, event in EventQueue.iter_events_since(start)
                          if event.parent_lineage is None
                          and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
            for root in roots:
                lineage = capture_lineage(root, observer_uuid=fighter.uuid)
                latest = reduce_lineage(latest, lineage)
                history.append(lineage)
            assert latest.actors[fighter.uuid].armor_class == fighter.ac_bonus().normalized_score
            assert dict(latest.actors[fighter.uuid].equipment) == {
                slot.value: item.uuid for slot in (*WeaponSlot, *BodyPart)
                if (item := fighter.equipment.get_item_by_slot(slot)) is not None}

        def attack(behavior: str, slot: WeaponSlot, position: tuple[int, int]) -> AttackEvent:
            available = get_available_actions(fighter)
            row = next(row for row in available.all_actions
                       if row.behavior_id == behavior and row.weapon_slot == slot.value and row.valid_targets)
            target = next(target for target in row.valid_targets if target.position == position)
            start = EventQueue.event_cursor()
            random.seed(0)
            event = execute_by_index(fighter, row.template_name, target.index, available=available)
            assert isinstance(event, AttackEvent) and not event.canceled and event.phase is EventPhase.COMPLETION
            retain(start)
            return event

        assert fighter.action_economy.actions.normalized_score == 1
        first = attack("action.attack", WeaponSlot.MELEE_MAIN, (4, 3)) if attacks else None
        if attacks:
            assert fighter.action_economy.actions.normalized_score == 0
            assert fighter.action_economy.resources["extra_attacks"].current == 1
        item_id = "weapon.dagger" if replacement == "weapon" else "apparel.robes.red_mage"
        item = next(item for item in fighter.inventory.items.values() if item.item_id == item_id)
        start = EventQueue.event_cursor()
        assert fighter.equip_item(item.uuid, WeaponSlot.MELEE_MAIN if replacement == "weapon" else BodyPart.BODY)
        retain(start)
        assert fighter.equipment.active_weapon_set is WeaponSet.MELEE
        if attacks:
            second = attack("action.feature.extra_attack", WeaponSlot.RANGED_MAIN, (8, 3))
            assert first is not None and first.turn_execution_id == second.turn_execution_id
            assert fighter.action_economy.actions.normalized_score == 0
            assert fighter.action_economy.resources["extra_attacks"].current == 0
            assert fighter.equipment.active_weapon_set is WeaponSet.RANGED
        assert encounter.get_current_entity() is fighter
        return before, tuple(history)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous)
