"""Real commands for the ten delivered spell and condition presentations."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.body_responses import BLOOD_BODY_RESPONSE, install_body_response
from dnd.content.characters.origin_definitions import ABILITY_ORDER, resolve_origin
from dnd.content.characters.origin_grants import apply_origin
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.enchantment import Bane, Bless
from dnd.spells.evocation import FireBolt, Shatter
from dnd.spells.necromancy import FalseLife, InflictWounds
from dnd.spells.transmutation import EnhanceAbility, ExpeditiousRetreat, Haste, JumpSpell
from dnd.types.character_progression import AppliedOriginState, Background, Species
from dnd.types.world import CardinalDirection
from dnd.world_authoring import set_world_tile_elevation
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history
from tests.game.teleport_scenarios import teleport_history


PendingProgram = Literal["inflict_wounds", "hellish_rebuke", "shatter", "misty_step", "bless", "bane",
                         "false_life", "jump", "expeditious_retreat", "haste"]
SPELLS = {"inflict_wounds": InflictWounds, "shatter": Shatter, "bless": Bless, "bane": Bane,
          "false_life": FalseLife, "jump": JumpSpell, "expeditious_retreat": ExpeditiousRetreat, "haste": Haste}


def pending_spell_history(*, program: PendingProgram, miss: bool = False, saved: bool = False,
                          blocked: bool = False, raised: bool = False, long_jump: bool = False,
                          replace_grant: bool = False, unrelated_grant: bool = False,
                          perspective: Literal["both", "departure", "arrival"] = "both") -> CapturedHistory:
    """Capture native outcomes and both players before resetting the engine."""
    if program == "misty_step":
        if perspective != "both":
            return teleport_history(battlefield_id="battlefield.visibility_doorway_open",
                witness_position=(5, 7), caster_position=(8, 7) if perspective == "departure" else (8, 10),
                destination=(8, 10) if perspective == "departure" else (8, 7))
        return teleport_history()
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        positions = {"caster": (3, 6), "target": (4, 6)}
        if program in ("bless", "bane"):
            positions.update(second=(5, 6), saved=(5, 7), outside=(3, 8))
        if program == "shatter":
            positions = {"caster": (3, 6), "target": (6, 6), "saved": (6, 5),
                         "outside": (3, 9), "behind": (8, 6)}
            if blocked:
                for y in range(3, 10):
                    build_directional_wall().place_on_grid((7, y), boundary_direction=CardinalDirection.EAST)
        if program == "expeditious_retreat":
            positions["target"] = (7, 6)
        if program == "haste":
            positions["enemy"] = (7, 6)
        if raised:
            author = uuid4()
            for x in range(5, 9):
                for y in range(4, 9):
                    set_world_tile_elevation((x, y), author_uuid=author, height=2,
                        surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
        actors: dict[str, Entity] = {}
        for role, position in positions.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if (role == "caster" or program == "bless"
                    or program in ("jump", "haste") and role == "target") else "enemies",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    dexterity=AbilityConfig(ability_score=10),
                    constitution=AbilityConfig(ability_score=20 if role == "saved" else 10),
                    charisma=AbilityConfig(ability_score=20 if role == "saved" else 10)),
                action_economy=ActionEconomyConfig(spell_slots={1: 8, 2: 4, 3: 4}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=12, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            setup_standard_actions(actor)
            if role == "caster":
                if program == "hellish_rebuke":
                    origin = resolve_origin(species=Species.TIEFLING, species_variant=None,
                        background=Background.ADVENTURER, state=AppliedOriginState(
                            base_ability_scores=tuple((ability, 18 if ability == "intelligence" else 10)
                                                      for ability in ABILITY_ORDER),
                            flexible_ability_bonuses=(("constitution", 1), ("charisma", 2)), choices=()))
                    apply_origin(actor, origin, character_level=3)
                else:
                    register_spell(actor, SPELLS[program], caster_level=5)
                if unrelated_grant:
                    actor.register_action(EnhanceAbility(source_entity_uuid=actor.uuid, template=True,
                        caster_level=5, enhance_ability_type="constitution"))
            if program == "haste" and role == "target":
                register_spell(actor, FireBolt, caster_level=5)
            install_body_response(actor, BLOOD_BODY_RESPONSE)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, target = actors["caster"], actors["target"]
        encounter = Encounter(name="Pending spell gameplay", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10] * len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Pending spell initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)

        def perform(actor: Entity, behavior: str, *, recipient: Entity | None = None,
                    position: tuple[int, int] | None = None, extras: tuple[Entity, ...] = (),
                    dice: tuple[int, ...] = (4,) * 40, fresh: bool = False,
                    cost_type: str | None = None, resource: str | None = None) -> Event:
            if fresh:
                encounter.next_turn()
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()
            available = get_available_actions(actor)
            choices = [(action, choice) for action in available.all_actions
                       if action.behavior_id == behavior and (cost_type is None or action.cost_type == cost_type)
                       and (resource is None or any(cost.resource_name == resource for cost in action.costs))
                       for choice in action.valid_targets
                       if (recipient is None or choice.target_uuid == recipient.uuid)
                       and (position is None or choice.position == position)]
            assert choices, (program, actor.name, behavior, position, cost_type,
                [(row.template_name, row.behavior_id, row.cost_type) for row in available.all_actions])
            with fixed_dice_faces(*dice):
                result = execute_available_action(actor, *choices[0],
                    extra_target_uuids=[str(other.uuid) for other in extras])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION, (behavior, result)
            return result

        if program == "inflict_wounds":
            perform(caster, "spell.inflict_wounds", recipient=target, dice=(1,) if miss else (15, 4, 4, 4))
            assert target.get_hp() == (120 if miss else 108)
        elif program == "hellish_rebuke":
            perform(target, "action.attack", recipient=caster, dice=(15, 3, 20 if saved else 4, 4, 4, 4))
            assert caster.get_normal_hp() == 117
            assert target.get_normal_hp() == (114 if saved else 108)
        elif program == "shatter":
            cast = perform(caster, "spell.shatter", position=(6, 6), dice=(10, 4, 4, 4) * 8)
            assert isinstance(cast, SpellEvent) and cast.resolved_area_positions
            assert ((8, 6) in cast.resolved_area_positions) is not blocked
            assert actors["outside"].get_hp() == before.actors[actors["outside"].uuid].normal_hp
        elif program in ("bless", "bane"):
            name = "Bless" if program == "bless" else "Bane"
            extras = (actors["second"], actors["saved"])
            perform(caster, "spell." + program, recipient=target, extras=extras, dice=(10,) * 20)
            assert name in target.active_conditions and name in actors["second"].active_conditions
            assert (name in actors["saved"].active_conditions) is (program == "bless")
            assert name not in actors["outside"].active_conditions
            perform(target, "action.move", position=(4, 8))
            perform(actors["second"], "action.move", position=(6, 7))
            perform(caster, "action.drop_concentration")
            assert all(name not in actor.active_conditions for actor in actors.values())
        elif program == "false_life":
            perform(caster, "spell.false_life", dice=(2,))
            assert caster.health.temporary_hit_points.normalized_score == 6
            first_grant = caster.health.temporary_hit_points_grant
            perform(target, "action.attack", recipient=caster, dice=(15, 3))
            assert caster.health.temporary_hit_points.normalized_score == 3
            assert caster.health.temporary_hit_points_grant == first_grant
            if unrelated_grant:
                perform(caster, "spell.enhance_ability", recipient=caster, dice=(6, 6))
                assert caster.health.temporary_hit_points.normalized_score == 12
                assert caster.health.temporary_hit_points_grant is not None
                assert caster.health.temporary_hit_points_grant.source_id is None
            elif replace_grant:
                perform(caster, "spell.false_life", dice=(4,))
                assert caster.health.temporary_hit_points.normalized_score == 8
                assert caster.health.temporary_hit_points_grant != first_grant
                perform(caster, "action.move", position=(3, 8))
            else:
                perform(target, "action.attack", recipient=caster, dice=(15, 5), fresh=True)
                assert caster.health.temporary_hit_points.normalized_score == 0
                assert caster.health.temporary_hit_points_grant is None and caster.get_normal_hp() == 118
        elif program == "jump":
            perform(caster, "spell.jump", recipient=target)
            destination = (8, 6) if long_jump else (6, 6)
            perform(target, "action.jump", position=destination)
            assert target.position == destination
        elif program == "expeditious_retreat":
            base_speed = caster.action_economy.current_speed()
            perform(caster, "spell.expeditious_retreat")
            assert caster.action_economy.current_speed() == base_speed
            perform(caster, "action.move", position=(4, 6))
            perform(caster, "action.spell.expeditious_retreat.dash", fresh=True, cost_type="bonus_actions")
            perform(caster, "action.move", position=(6, 6))
            perform(caster, "action.move", position=(6, 8))
            perform(caster, "action.drop_concentration")
        else:
            base_speed = target.action_economy.current_speed()
            perform(caster, "spell.haste", recipient=target)
            assert target.action_economy.current_speed() == 2 * base_speed
            perform(target, "action.move", position=(6, 6))
            perform(target, "action.attack", recipient=actors["enemy"], dice=(15, 4), resource="haste_action")
            perform(target, "action.move", position=(5, 5), fresh=True)
            perform(target, "spell.fire_bolt", recipient=actors["enemy"], dice=(15, 4, 4))
            perform(target, "action.dash", resource="haste_action")
            perform(target, "action.move", position=(3, 5))
            perform(caster, "action.drop_concentration")
            assert "Haste" not in target.active_conditions and "Haste Lethargy" in target.active_conditions
        history = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "target")))
        primary = history.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, history.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
