"""Focused Halfling origin runtime regressions."""

from collections.abc import Iterator
from unittest.mock import patch
from uuid import uuid4

import pytest

from dnd.actions.standard import (
    Hide,
)
from dnd.content.characters.origin_content import resolve_origin_transforms
from dnd.content.characters.player_body import create_player_body
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.entities.creature_transforms import apply_entity_transforms, rollback_entity_transforms
from dnd.types.rolls import RollType
from dnd.core.events.events_registry import (
    EventPhase,
)
from dnd.core.gridmap import get_map
from dnd.types.abilities import AbilityName
from dnd.types.creatures import Background, OriginCapability, Size, Species
from dnd.types.progression import AppliedOriginState
from dnd.entities.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from tests.engine.support import create_test_entity


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _state() -> AppliedOriginState:
    return AppliedOriginState(
        base_ability_scores=tuple((ability, 10) for ability in AbilityName),
        flexible_ability_bonuses=(
            (AbilityName.DEXTERITY, 2),
            (AbilityName.CHARISMA, 1),
        ),
    )


def test_halfling_lucky_rerolls_natural_one_and_must_use_replacement() -> None:
    entity = create_player_body(uuid4(), name="Halfling")
    receipts = apply_entity_transforms(
        entity,
        resolve_origin_transforms(
            species=Species.HALFLING,
            species_variant=None,
            background=Background.ADVENTURER,
            state=_state(),
        ),
    )

    with patch("dnd.core.dice._randint", side_effect=(1, 7)):
        roll, event = entity.roll_d20_event(
            entity.ability_scores.dexterity.ability_score,
            RollType.CHECK,
            skill_name="stealth",
        )

    assert event.original_roll.results == [1]
    assert event.final_roll is not None
    assert event.final_roll.results == [7]
    assert roll.results == [7]
    assert event.roll_modifications[0].handler_name == "Halfling Lucky"

    with patch("dnd.core.dice._randint", side_effect=(1, 1)):
        replacement_one, _ = entity.roll_d20_event(
            entity.ability_scores.dexterity.ability_score,
            RollType.SAVE,
            ability_name="dexterity",
        )

    assert replacement_one.results == [1]

    rollback_entity_transforms(receipts)

    with patch("dnd.core.dice._randint", return_value=1):
        unmodified, event = entity.roll_d20_event(
            entity.ability_scores.dexterity.ability_score,
            RollType.ATTACK,
        )

    assert unmodified.results == [1]
    assert event.final_roll is None


def test_halfling_nimbleness_allows_traversal_but_not_ending_in_larger_space() -> None:
    reset_engine_runtime(grid_size=(5, 1))
    halfling = create_test_entity(
        name="Halfling",
        config=EntityConfig(
            position=(1, 0),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    larger = create_test_entity(
        name="Larger creature",
        config=EntityConfig(
            position=(2, 0),
            faction="monsters",
            size=Size.MEDIUM,
        ),
    )
    source_id = uuid4()
    halfling.add_origin_capability_source(
        OriginCapability.HALFLING_NIMBLENESS,
        source_id,
    )

    halfling.update_entity_senses(max_distance=20)

    assert not larger.blocks_walking(halfling.uuid)
    assert (2, 0) not in halfling.senses.paths
    assert halfling.senses.paths[(3, 0)] == [
        (1, 0),
        (2, 0),
        (3, 0),
    ]

    halfling.remove_origin_capability_source(
        OriginCapability.HALFLING_NIMBLENESS,
        source_id,
    )
    halfling.update_entity_senses(max_distance=20)

    assert larger.blocks_walking(halfling.uuid)
    assert (3, 0) not in halfling.senses.paths
    assert not get_map().is_walkable_for(2, 0, halfling.uuid)


def test_halfling_nimbleness_does_not_bypass_same_size_creatures() -> None:
    reset_engine_runtime(grid_size=(5, 1))
    halfling = create_test_entity(
        name="Halfling",
        config=EntityConfig(
            position=(1, 0),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    same_size = create_test_entity(
        name="Same-size creature",
        config=EntityConfig(
            position=(2, 0),
            faction="monsters",
            size=Size.SMALL,
        ),
    )
    halfling.add_origin_capability_source(
        OriginCapability.HALFLING_NIMBLENESS,
        uuid4(),
    )

    halfling.update_entity_senses(max_distance=20)

    assert same_size.blocks_walking(halfling.uuid)
    assert (2, 0) not in halfling.senses.paths
    assert (3, 0) not in halfling.senses.paths


def test_naturally_stealthy_allows_hide_behind_one_larger_creature() -> None:
    reset_engine_runtime(grid_size=(6, 3))
    hider = create_test_entity(
        name="Lightfoot",
        config=EntityConfig(
            position=(4, 1),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    create_test_entity(
        name="Larger cover",
        config=EntityConfig(
            position=(2, 1),
            faction="heroes",
            size=Size.MEDIUM,
        ),
    )
    observer = create_test_entity(
        name="Observer",
        config=EntityConfig(
            position=(0, 1),
            faction="monsters",
            size=Size.MEDIUM,
        ),
    )
    Entity.update_all_entities_senses(max_distance=20)
    assert hider.uuid in observer.senses.entities

    denied = Hide(source_entity_uuid=hider.uuid).apply()
    assert denied is not None and denied.canceled

    hider.add_origin_capability_source(
        OriginCapability.NATURALLY_STEALTHY,
        uuid4(),
    )
    hide = Hide(source_entity_uuid=hider.uuid)
    declaration = hide._create_declaration_event()
    assert isinstance(declaration, ActionEvent)
    validated = hide._validate(declaration)

    assert validated.phase is EventPhase.EXECUTION
    assert not validated.canceled


def test_naturally_stealthy_requires_intervening_creature_to_be_larger() -> None:
    reset_engine_runtime(grid_size=(6, 3))
    hider = create_test_entity(
        name="Lightfoot",
        config=EntityConfig(
            position=(4, 1),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    create_test_entity(
        name="Same-size cover",
        config=EntityConfig(
            position=(2, 1),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    observer = create_test_entity(
        name="Observer",
        config=EntityConfig(
            position=(0, 1),
            faction="monsters",
            size=Size.MEDIUM,
        ),
    )
    hider.add_origin_capability_source(
        OriginCapability.NATURALLY_STEALTHY,
        uuid4(),
    )
    Entity.update_all_entities_senses(max_distance=20)

    assert hider.uuid in observer.senses.entities
    denied = Hide(source_entity_uuid=hider.uuid).apply()

    assert denied is not None and denied.canceled
    assert "Hidden" not in hider.active_conditions
