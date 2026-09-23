"""Genuine projectile life transitions shared by tests and the clip extractor."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_by_index, register_spell
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import FireBolt, MagicMissile
from game.presentation import capture_interval, capture_lineage, reduce_interval, reduce_lineage
from game.replay import CapturedHistory, ObserverCapture, capture_history


def projectile_life_history(initial: LifeState = LifeState.ALIVE, *, repeated: bool = False,
                            maximum_hp: Literal[4, 20] = 4) -> CapturedHistory:
    """One native generation, both views; optional repeated Magic Missile delivery."""
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = build_battlefield("battlefield.open_floor_bright")
    game = Game()
    try:
        caster = Entity.create(uuid4(), "Caster", config=EntityConfig(position=(3, 3), faction="caster",
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=4, hit_dice_count=5, mode="maximums")]),
            spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
            action_economy=ActionEconomyConfig(spell_slots={1: 1} if repeated else {})))
        target = Entity.create(uuid4(), "Death-save recipient", config=EntityConfig(
            position=(5, 3), faction="target", uses_death_saves=True,
            health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=4, hit_dice_count=maximum_hp // 4, mode="maximums")])))
        register_spell(caster, MagicMissile if repeated else FireBolt, caster_level=1)
        for actor in (caster, target):
            actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),))
            actor.compose_entity()
            game.deploy_entity(actor, actor.position)
        Entity.update_all_entities_senses()
        encounter = Encounter(name="Native projectile life states", source_entity_uuid=uuid4())
        for actor in (caster, target):
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        if initial is not LifeState.ALIVE:
            target.enter_dying_state()
            if initial is LifeState.STABLE:
                assert target.stabilize()
        initialization = capture_interval(name="Projectile life initialization", start_cursor=0,
            end_cursor=EventQueue.event_cursor(), observer_uuid=caster.uuid,
            battlefield_id=battlefield.definition.battlefield_id)
        before, _ = reduce_interval(None, initialization)
        available = caster.get_available_actions(include_dead=True)
        action = next(row for row in available.all_actions if row.behavior_id == ("spell.magic_missile" if repeated else "spell.fire_bolt"))
        option = next(row for row in action.valid_targets if row.target_uuid == target.uuid)
        random.seed(17)
        if repeated:
            with fixed_dice_faces(4, 4, 4):
                event = execute_by_index(caster, action.template_name, option.index, available=available)
        else:
            event = execute_by_index(caster, action.template_name, option.index, available=available)
        assert event is not None and event.phase is EventPhase.COMPLETION and not event.canceled
        lineage = capture_lineage(event, observer_uuid=caster.uuid)
        recorded = reduce_lineage(before, lineage).actors[target.uuid]
        assert (recorded.normal_hp, recorded.life_state) == (target.get_normal_hp(), target.health.life_state)
        return capture_history(before, (lineage,), observers=(
            ObserverCapture("caster", caster.uuid, before.reducer_cursor),
            ObserverCapture("recipient", target.uuid, before.reducer_cursor),
        ))
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
