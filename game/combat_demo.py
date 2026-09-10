"""Finite public gameplay input for the integrated historical-cast scene.

The composition entry installs the existing content runtime before consuming
this iterator. The canonical creature materializer imports built-in content
definitions; the scenario does not install a separate content runtime.
The caller requests operations independently of visual playback. A cast yields
one complete lineage; optional equipment replacement yields its four separate
roots after the single public operation has completed and all are captured.
"""

from collections.abc import Generator
import random
from uuid import UUID, uuid4

from dnd.actions_functional import execute_by_index, get_available_actions, register_spell
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.controller import HumanController
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EntityCreatedEvent, EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.evocation import FireBolt, MagicMissile
from dnd.types.senses import SenseMode, SensesType
from game.presentation import (
    CompletedLineage, PresentationTarget, capture_interval, capture_lineage,
    reduce_interval, seed_actors,
)


BATTLEFIELD_ID = "battlefield.visual_vertical_seam"


def iter_combat_demo(
    *, caster_position: tuple[int, int] = (16, 25),
    second_attack_seed: int = 0,
    goblin_recipient: bool = False,
    replace_weapon: bool = False,
    magic_missile: bool = False,
) -> Generator[PresentationTarget | CompletedLineage, None, None]:
    """Yield the baseline and two legal casts, optionally replacing gear between.

    Magic Missile allocates A/B/A with damage seeds 0 and 1. The separate
    second_attack_seed selects the Fire Bolt demonstration's attack outcome.
    """
    SERVER_CONTENT_SYSTEM_RUNTIME.require()
    reset_engine_runtime()
    built = build_battlefield(BATTLEFIELD_ID)
    game = Game()
    actors: list[Entity] = []
    births: list[EntityCreatedEvent] = []
    replacement_item_uuid: UUID | None = None
    placements = (
        ("Caster", caster_position, "heroes"),
        ("Recipient", built.notable_positions["terrace"], "monsters"),
    ) + ((("Recipient B", (18, 20), "monsters"),) if magic_missile else ())
    for name, position, faction in placements:
        if name == "Recipient" and goblin_recipient:
            actor = materialize_creature(
                BESTIARY_CREATURE_RECIPES_BY_ID["goblin"],
                runtime_entity_uuid=uuid4(), display_name="Goblin recipient",
                faction=faction, position=position,
                deployment_role=CreatureDeploymentRole(role_id="scenario.terrace_recipient"),
                possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
            )
        else:
            actor = Entity.create(
                uuid4(), name,
                config=EntityConfig(
                    position=position, faction=faction,
                    action_economy=ActionEconomyConfig(
                        spell_slots={1: 2} if name == "Caster" and magic_missile else {},
                    ),
                    health=HealthConfig(hit_dices=[HitDiceConfig(
                        hit_dice_value=10, hit_dice_count=8, mode="maximums",
                    )]),
                    spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                    appearance=AppearanceConfig(
                        visual_scale=0.5, body_category="NakedBody", has_beard=False,
                    ),
                ),
            )
            # This authored battlefield is dark. The Goblin already owns its
            # authored darkvision; give the ordinary actors a real sense too.
            actor.senses.add_sense_mode_source(
                actor.uuid, SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
            )
        if name == "Caster":
            register_spell(actor, MagicMissile if magic_missile else FireBolt, caster_level=1)
            if replace_weapon:
                dagger = build_authored_item("weapon.dagger", actor.uuid)
                shortsword = build_authored_item("weapon.shortsword", actor.uuid)
                actor.install_initial_items(((dagger, WeaponSlot.MELEE_MAIN), (shortsword, None)))
                replacement_item_uuid = shortsword.uuid
        births.append(actor.compose_entity())
        actors.append(actor)
    caster, recipient = actors[:2]
    seed_cursor = EventQueue.event_cursor()
    initial_senses = capture_senses_snapshot(caster.senses)
    for actor in actors:
        game.deploy_entity(actor, actor.position)
    Entity.update_all_entities_senses()
    encounter = Encounter(name="Terrace spell practice", source_entity_uuid=uuid4())
    for actor in actors:
        encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
    random_state = random.getstate()
    try:
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
    finally:
        random.setstate(random_state)

    startup = capture_interval(
        name="combat startup", start_cursor=0, end_cursor=EventQueue.event_cursor(),
        observer_uuid=caster.uuid, battlefield_id=BATTLEFIELD_ID,
        door_uuid=built.object_uuids["door"],
        standing_torch_uuid=built.object_uuids["standing_torch"],
        seed_cursor=seed_cursor, seed_snapshot=initial_senses,
    )
    target, _ = reduce_interval(None, startup)
    yield seed_actors(
        target, tuple(births),
        active_weapon_sets={actor.uuid: actor.equipment.active_weapon_set for actor in actors},
    )

    for cast_number in (1, 2):
        random_state = random.getstate()
        try:
            if cast_number == 2:
                encounter.next_turn()
                while encounter.get_current_entity() is not caster:
                    encounter.next_turn()
            available = get_available_actions(caster)
            behavior_id = "spell.magic_missile" if magic_missile else "spell.fire_bolt"
            action = next(row for row in available.all_actions if row.behavior_id == behavior_id)
            target_option = next(
                row for row in action.valid_targets if row.target_uuid == recipient.uuid
            )
            if magic_missile:
                random.seed(cast_number - 1)
                terminal = execute_by_index(
                    caster, action.template_name, target_option.index,
                    extra_target_uuids=[str(actors[2].uuid), str(recipient.uuid)], available=available,
                )
            else:
                first_attack_seed = 17 if goblin_recipient else 0
                random.seed(first_attack_seed if cast_number == 1 else second_attack_seed)
                terminal = encounter.execute_action(caster.uuid, action.template_name, target_option.index)
            if terminal is None or terminal.canceled or terminal.phase is not EventPhase.COMPLETION:
                raise RuntimeError("scripted spell did not complete")
            lineage = capture_lineage(terminal, observer_uuid=caster.uuid)
        finally:
            random.setstate(random_state)
        yield lineage
        if cast_number == 1 and replacement_item_uuid is not None:
            random_state = random.getstate()
            try:
                start = EventQueue.event_cursor()
                if not caster.equip_item(replacement_item_uuid, WeaponSlot.MELEE_MAIN):
                    raise RuntimeError("scripted weapon replacement did not complete")
                roots = tuple(event for _, event in EventQueue.iter_events_since(start)
                              if event.phase is EventPhase.COMPLETION and event.parent_lineage is None)
                if len(roots) != 4:
                    raise RuntimeError("scripted weapon replacement requires its four independent roots")
                replacement = tuple(capture_lineage(root, observer_uuid=caster.uuid) for root in roots)
            finally:
                random.setstate(random_state)
            yield from replacement
