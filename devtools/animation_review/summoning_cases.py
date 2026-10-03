"""Representative native summon fights for the existing recorded review gallery.

All movement, attacks, concentration loss and dismissal use admitted native
actions. Fixed dice select reproducible outcomes; no retained fact, live HP,
position, allegiance or duration is edited to manufacture a visual result.
"""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import Shove
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.base_actions import TargetType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.summoning import ConjureAnimals, ConjureFey, ConjureFiend
from dnd.summoning.system import bind_summoning
from dnd.summoning.forms import selected_form
from dnd.types.summoning import SummonFamily, SummonSelection
from dnd.core.life_types import LifeState
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def summoning_history(
    *, form: str, family: Literal["animals", "fey", "fiend"], slot: int,
    flight: bool = False, release_control: bool = False,
    program: Literal["attacks", "injury", "ordinary_injury"] = "attacks",
) -> CapturedHistory:
    """Capture birth, travel, intrinsic attacks and one real lifecycle outcome.

    The released Fey keeps its full native duration and fights its former caster.
    Other cases end with controlled dismissal. Expiry is a separate lifecycle
    test; a shortened fake duration is not used to fit it into this recording.
    """
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors: dict[str, Entity] = {}
        for role, position in (("caster", (3, 6)), ("opponent", (8, 6))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "caster" else "opponents",
                ability_scores=AbilityScoresConfig(wisdom=AbilityConfig(ability_score=18),
                    strength=AbilityConfig(ability_score=18 if role == "opponent" and program != "attacks" else 10)),
                action_economy=ActionEconomyConfig(spell_slots={slot: 2}),
                spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
                health=HealthConfig(max_hit_points_bonus=500),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22")))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            if role == "opponent" and program != "attacks":
                actor.install_initial_items(((build_authored_item("weapon.longsword", actor.uuid), WeaponSlot.MELEE_MAIN),))
            setup_standard_actions(actor)
            if role == "opponent" and program != "attacks":
                actor.register_action(Shove(name="Knock Prone", source_entity_uuid=actor.uuid,
                    template=True, knock_prone=True))
            if role == "caster":
                register_spell(actor, {"animals": ConjureAnimals, "fey": ConjureFey,
                    "fiend": ConjureFiend}[family], caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, opponent = actors["caster"], actors["opponent"]
        encounter = Encounter(name=f"Native {family} {form} review", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        ordinary = None
        if program == "ordinary_injury":
            selected = selected_form(SummonSelection(family=SummonFamily(family),
                form_id=form, cast_at_level=slot, target_position=(5, 6)))
            ordinary = materialize_creature(selected.recipe, runtime_entity_uuid=uuid4(),
                display_name=selected.display_name, position=(5, 6), faction=caster.faction,
                deployment_role=CreatureDeploymentRole(role_id="review.ordinary_body"),
                possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS)
            ordinary.compose_entity()
            game.deploy_entity(ordinary, ordinary.position)
            encounter.add_combatant(ordinary, HumanController(source_entity_uuid=ordinary.uuid))
        with fixed_dice_faces(10, 10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        system = bind_summoning(game, encounter)
        Entity.update_all_entities_senses()

        def turn(actor: Entity, *, fresh: bool = False) -> None:
            with fixed_dice_faces(*([1] * 100)):
                if fresh:
                    encounter.next_turn()
                for _ in range(12):
                    if encounter.get_current_entity() is actor:
                        return
                    encounter.next_turn()
            raise AssertionError(f"No native turn reached for {actor.name}")

        def perform(actor: Entity, behavior: str, destination: tuple[int, int], *,
                    weapon_slot: WeaponSlot | None = None, template: str | None = None,
                    critical: bool = False, damage_face: int = 1) -> None:
            turn(actor)
            available = get_available_actions(actor, legal_only=True)
            choices = [(action, choice) for action in available.all_actions
                if action.behavior_id == behavior
                and (weapon_slot is None or action.weapon_slot == weapon_slot.value)
                and (template is None or action.template_name == template)
                for choice in action.valid_targets
                if choice.position == destination
                or action.target_type is TargetType.SELF and destination == actor.position]
            assert choices, (actor.name, behavior, destination, template,
                [(row.template_name, row.behavior_id, row.valid_targets)
                 for row in available.all_actions if row.behavior_id == behavior],
                tuple(actor.active_conditions), actor.action_economy.actions.normalized_score,
                [(item.item_id, item.uuid) for item in actor.equipment.get_all_equipped_items()])
            with fixed_dice_faces(20 if critical else 15, *([damage_face] * 100)):
                result = execute_available_action(actor, *choices[0])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION, result

        turn(caster)
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Before native summoning", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        if ordinary is None:
            available = get_available_actions(caster, legal_only=True)
            choices = [(action, choice) for action in available.all_actions
                if action.template_name.endswith(f"__summon_{form}")
                for choice in action.valid_targets if choice.position == (5, 6)]
            assert len(choices) == 1, [(row.template_name, selection.position) for row, selection in choices]
            result = execute_available_action(caster, *choices[0])
            assert result is not None and not result.canceled
            member, = system.memberships.values()
            summon = member.entity
            origin = member.existence.origin
        else:
            summon = ordinary
            member = None
            origin = None
        identity = summon.uuid
        assert summon.position == (5, 6) and summon.faction == caster.faction

        perform(summon, "action.move", (7, 6), template="Flying Movement" if flight else "Move")
        if program != "attacks":
            before_hit = summon.get_normal_hp()
            perform(opponent, "action.attack", summon.position, weapon_slot=WeaponSlot.MELEE_MAIN)
            assert 0 < summon.get_normal_hp() < before_hit
            perform(opponent, "action.shove", summon.position, template="Knock Prone", critical=True)
            assert "Prone" in summon.active_conditions
            # The standard native turn-start handler stands a prone creature
            # and spends half its speed; Stand Up is not a standard template.
            turn(summon)
            assert "Prone" not in summon.active_conditions
            assert summon.action_economy.movement_remaining() == summon.action_economy.get_base_value("movement") // 2
            for _ in range(20):
                if summon.get_normal_hp() <= 0:
                    break
                turn(opponent, fresh=True)
                perform(opponent, "action.attack", summon.position,
                    weapon_slot=WeaponSlot.MELEE_MAIN, critical=True, damage_face=6)
            assert summon.get_normal_hp() <= 0
            if ordinary is None:
                assert identity not in game.entities and identity not in encounter.combatants
                assert not system.memberships
            else:
                assert summon.health.life_state is LifeState.DEAD
                assert identity in game.entities and not system.memberships
        else:
            perform(summon, "action.attack", opponent.position, weapon_slot=WeaponSlot.MELEE_MAIN)
            if summon.equipment.get_weapon(WeaponSlot.MELEE_OFF) is not None:
                turn(summon, fresh=True)
                perform(summon, "action.attack", opponent.position, weapon_slot=WeaponSlot.MELEE_OFF, critical=True)
            turn(summon, fresh=True)
            multi = next((action for action in get_available_actions(summon, legal_only=True).all_actions
                if action.behavior_id == "action.monster.multiattack" and action.valid_targets), None)
            if multi is not None:
                perform(summon, multi.behavior_id, opponent.position, template=multi.template_name)
    
            if release_control:
                assert family == "fey" and member is not None
                hp = summon.get_normal_hp()
                caster_hp = caster.get_normal_hp()
                perform(caster, "action.drop_concentration", caster.position)
                assert summon.uuid == identity and summon.get_normal_hp() == hp
                assert summon.faction != caster.faction and member.existence.origin == origin
                assert summon.uuid in encounter.combatants
                turn(summon, fresh=True)
                perform(summon, "action.move", (4, 6), template="Move")
                perform(summon, "action.attack", caster.position, weapon_slot=WeaponSlot.MELEE_MAIN)
                assert caster.get_normal_hp() < caster_hp
            else:
                perform(caster, "action.summon.dismiss", summon.position)
                assert identity not in game.entities and identity not in encounter.combatants
                assert not system.memberships
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
