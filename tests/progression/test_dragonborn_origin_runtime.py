"""Direct Dragonborn Breath Weapon and reversible origin regressions."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.abilities import AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.characters.character_builds import create_character
from dnd.content.characters.dragonborn_definitions import DRAGONBORN_ANCESTRY_DEFINITIONS
from dnd.content.characters.origin_content import resolve_origin_transforms
from dnd.content.characters.player_body import create_player_body
from dnd.core.aoe import Cone, Line
from dnd.core.dice import fixed_dice_faces
from dnd.core.events.action_events import DragonbornBreathWeaponEvent
from dnd.core.events.events_registry import EventPhase, EventQueue, EventType
from dnd.core.modifiers import NumericalModifier
from dnd.entities.creature_transforms import apply_entity_transforms, rollback_entity_transforms
from dnd.entities.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.origins.dragonborn import DRAGONBORN_BREATH_RESOURCE, DragonbornBreathWeapon
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.abilities import AbilityName
from dnd.types.creatures import Background, Species
from dnd.types.damage import DamageType, ResistanceStatus
from dnd.types.dragonborn import DragonbornAncestry, DragonbornBreathGeometry
from dnd.types.progression import AppliedOriginState, OriginChoiceSelection
from tests.engine.support import create_test_entity


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(20, 12))
    yield
    reset_engine_runtime()


def _state(
    ancestry: DragonbornAncestry,
    *,
    constitution: int = 10,
) -> AppliedOriginState:
    base = {
        ability: constitution if ability is AbilityName.CONSTITUTION else 10
        for ability in AbilityName
    }
    return AppliedOriginState(
        base_ability_scores=tuple((ability, base[ability]) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.STRENGTH, 1),
            (AbilityName.CONSTITUTION, 2),
        ),
        choices=(OriginChoiceSelection(
            "species.dragonborn.draconic_ancestry",
            (ancestry.value,),
        ),),
    )


def _dragonborn(
    ancestry: DragonbornAncestry,
    position: tuple[int, int],
    *,
    constitution: int = 10,
) -> Entity:
    entity = create_character(
        uuid4(),
        name=f"{ancestry.value.title()} Dragonborn",
        species=Species.DRAGONBORN,
        background=Background.ADVENTURER,
        origin_state=_state(ancestry, constitution=constitution),
        faction="heroes",
    )
    Game().deploy_entity(entity, position)
    return entity


def _target(position: tuple[int, int]) -> Entity:
    return create_test_entity(
        name="Breath Target",
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(),
            health=HealthConfig(hit_dices=[HitDiceConfig(
                hit_dice_value=12,
                hit_dice_count=10,
                mode="maximums",
            )]),
            position=position,
            faction="monsters",
            proficiency_bonus=2,
        ),
    )


def _force_save(entity: Entity, ability: AbilityName, *, succeeds: bool) -> None:
    saving_throw = entity.saving_throws.get_saving_throw(ability)
    saving_throw.bonus.self_static.add_value_modifier(NumericalModifier.create(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        name=f"Dragonborn regression {ability.value} save",
        value=100 if succeeds else -100,
    ))


def _breath(entity: Entity) -> DragonbornBreathWeapon:
    action = entity.get_action_template("Breath Weapon")
    assert isinstance(action, DragonbornBreathWeapon)
    return action


@pytest.mark.parametrize(
    ("character_level", "expected_dice"),
    ((1, 2), (5, 2), (6, 3), (10, 3), (11, 4), (15, 4), (16, 5), (20, 5)),
)
def test_breath_weapon_damage_scales_at_exact_character_level_thresholds(
    character_level: int,
    expected_dice: int,
) -> None:
    action = _breath(_dragonborn(DragonbornAncestry.RED, (2, 2)))
    action.character_level = character_level
    assert action.damage_dice_count == expected_dice


@pytest.mark.parametrize(
    ("ancestry", "shape_type", "length_feet", "width_feet"),
    (
        (DragonbornAncestry.BLACK, Line, 30, 5),
        (DragonbornAncestry.GOLD, Cone, 15, None),
    ),
)
def test_breath_weapon_uses_ancestry_authored_geometry(
    ancestry: DragonbornAncestry,
    shape_type: type[Line] | type[Cone],
    length_feet: int,
    width_feet: int | None,
) -> None:
    action = _breath(_dragonborn(ancestry, (2, 2)))
    assert isinstance(action.aoe_shape, shape_type)
    assert action.aoe_shape.length_feet == length_feet
    if isinstance(action.aoe_shape, Line):
        assert action.aoe_shape.width_feet == width_feet


def test_breath_weapon_uses_constitution_dc_damage_and_one_rest_use() -> None:
    caster = _dragonborn(DragonbornAncestry.BLACK, (2, 5), constitution=14)
    target = _target((6, 5))
    _force_save(target, AbilityName.DEXTERITY, succeeds=False)
    template = _breath(caster)
    template.character_level = 6

    hp_before = target.get_hp()
    with fixed_dice_faces(10, 4, 4, 4):
        result = template.instantiate(end_position=(3, 5)).apply()

    assert isinstance(result, DragonbornBreathWeaponEvent)
    assert result.phase is EventPhase.COMPLETION
    assert not result.canceled
    # An unlevelled direct body has no class proficiency contribution yet.
    assert result.save_dc == 11
    assert result.save_ability is AbilityName.DEXTERITY
    assert result.total_damage == 12
    assert hp_before - target.get_hp() == 12
    assert caster.action_economy.get_resource_current(DRAGONBORN_BREATH_RESOURCE) == 0
    assert not template.check_costs()
    caster.on_short_rest()
    assert caster.action_economy.get_resource_current(DRAGONBORN_BREATH_RESOURCE) == 1
    caster.on_turn_start()
    assert template.check_costs()


def test_successful_constitution_save_halves_cone_damage() -> None:
    caster = _dragonborn(DragonbornAncestry.GREEN, (3, 5))
    target = _target((5, 5))
    _force_save(target, AbilityName.CONSTITUTION, succeeds=True)
    hp_before = target.get_hp()
    with fixed_dice_faces(10, 5, 5):
        result = _breath(caster).instantiate(end_position=(4, 5)).apply()

    assert isinstance(result, DragonbornBreathWeaponEvent)
    assert result.save_ability is AbilityName.CONSTITUTION
    assert result.total_damage == 5
    assert hp_before - target.get_hp() == 5


def test_breath_event_is_the_replay_and_presentation_fact() -> None:
    caster = _dragonborn(DragonbornAncestry.RED, (3, 5))
    target = _target((5, 5))
    _force_save(target, AbilityName.DEXTERITY, succeeds=False)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(10, 4, 4):
        result = _breath(caster).instantiate(end_position=(4, 5)).apply()

    emitted = tuple(EventQueue.iter_events_since(cursor))
    assert result in tuple(event for _, event in emitted)
    assert result.event_type is EventType.BASE_ACTION
    assert result.ancestry is DragonbornAncestry.RED
    assert result.damage_type is DamageType.FIRE
    assert result.breath_geometry is DragonbornBreathGeometry.CONE
    assert result.declared_target_entity_uuids == [target.uuid]
    assert result.total_damage == 8
    damage_facts = tuple(
        event
        for _, event in emitted
        if event.event_type is EventType.TAKE_DAMAGE
        and event.phase is EventPhase.COMPLETION
    )
    assert len(damage_facts) == 1
    assert damage_facts[0].target_entity_uuid == target.uuid
    assert damage_facts[0].total_damage == 8


def test_origin_transform_rolls_back_resistance_action_and_resource() -> None:
    entity = create_player_body(uuid4(), name="Silver Dragonborn")
    transforms = resolve_origin_transforms(
        species=Species.DRAGONBORN,
        species_variant=None,
        background=Background.ADVENTURER,
        state=_state(DragonbornAncestry.SILVER),
    )
    receipts = apply_entity_transforms(entity, transforms)
    try:
        definition = DRAGONBORN_ANCESTRY_DEFINITIONS[DragonbornAncestry.SILVER]
        assert entity.health.get_resistance(definition.damage_type) is ResistanceStatus.RESISTANCE
        assert isinstance(entity.get_action_template("Breath Weapon"), DragonbornBreathWeapon)
        assert entity.action_economy.get_resource_current(DRAGONBORN_BREATH_RESOURCE) == 1
        rollback_entity_transforms(receipts)
        assert entity.health.get_resistance(definition.damage_type) is ResistanceStatus.NONE
        assert entity.get_action_template("Breath Weapon") is None
        assert not entity.action_economy.has_resource(DRAGONBORN_BREATH_RESOURCE)
    finally:
        entity.discard_unpublished_runtime()
