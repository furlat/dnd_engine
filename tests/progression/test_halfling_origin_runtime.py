"""Focused Halfling origin runtime regressions."""

from collections.abc import Iterator
from unittest.mock import patch
from uuid import uuid4

import pytest

from dnd.actions import Hide
from dnd.content_system.character_build_validation import (
    CharacterBuildPreview,
    CharacterGrantProvenance,
    CharacterGrantScheduleEntry,
    CharacterGrantScheduleKind,
    CharacterGrantSourceKind,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_materialization import (
    CharacterCompositionReceipt,
    remove_character_composition,
)
from dnd.content_system.origin_runtime_character_grant_appliers import (
    ORIGIN_RUNTIME_CHARACTER_GRANT_APPLIERS,
)
from dnd.content_system.pack_loader import LoadedContentSystem
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.core.base_actions import ActionEvent
from dnd.core.content.origin_features import OriginCapability
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.dice import RollType
from dnd.core.events import EventPhase
from dnd.core.gridmap import get_map
from dnd.core.creature_types import Size
from dnd.entity import Entity, EntityConfig
from dnd.origins.halfling import (
    HALFLING_LUCKY_DECLARATION,
    HALFLING_LUCKY_REF,
)
from dnd.runtime_reset import reset_engine_runtime
from tests.engine.support import create_test_entity


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _runtime() -> ContentSystemRuntime:
    runtime = ContentSystemRuntime()
    runtime.install(
        LoadedContentSystem(
            registry=FrozenContentRegistry(
                declarations={
                    HALFLING_LUCKY_REF.identity_key: (
                        HALFLING_LUCKY_DECLARATION
                    ),
                },
                recipe_presets={},
                sources={},
            ),
            packs=(),
            built_in_artifact_digest="a" * 64,
            content_set_digest="b" * 64,
            provider_only_behavior_ids=frozenset({
                HALFLING_LUCKY_REF.content_id,
            }),
        ),
    )
    return runtime


def test_halfling_lucky_rerolls_natural_one_and_must_use_replacement() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    entry = CharacterGrantScheduleEntry(
        kind=CharacterGrantScheduleKind.AUTOMATIC_CONTENT,
        provenance=CharacterGrantProvenance(
            source_kind=CharacterGrantSourceKind.SPECIES,
            source_ref=HALFLING_LUCKY_REF,
            character_level=1,
            class_level_id=None,
            class_level=None,
            choice_id=None,
            ordinal_path=(0,),
        ),
        grant_token="species.halfling.lucky",
        content_ref=HALFLING_LUCKY_REF,
    )
    context = BuiltinCharacterGrantContext(
        entity=entity,
        character_id=uuid4(),
        preview=CharacterBuildPreview(
            class_level_counts=(),
            automatic_grant_refs=(HALFLING_LUCKY_REF,),
            grant_schedule=(entry,),
            final_known_spell_refs=(),
            caster_contributions=(),
            effective_spellcaster_level=0,
            normal_spell_slots=(),
        ),
        runtime=_runtime(),
    )
    receipt = ORIGIN_RUNTIME_CHARACTER_GRANT_APPLIERS[
        HALFLING_LUCKY_REF.identity_key
    ](context, entry)

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

    remove_character_composition(
        entity,
        CharacterCompositionReceipt(
            runtime_entity_uuid=entity.uuid,
            character_id=context.character_id,
            grants=(receipt,),
            automatic_grant_refs=(HALFLING_LUCKY_REF,),
        ),
    )

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
        source_id=uuid4(),
        name="Halfling",
        config=EntityConfig(
            position=(1, 0),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    larger = create_test_entity(
        source_id=uuid4(),
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
        source_id=uuid4(),
        name="Halfling",
        config=EntityConfig(
            position=(1, 0),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    same_size = create_test_entity(
        source_id=uuid4(),
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
        source_id=uuid4(),
        name="Lightfoot",
        config=EntityConfig(
            position=(4, 1),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    create_test_entity(
        source_id=uuid4(),
        name="Larger cover",
        config=EntityConfig(
            position=(2, 1),
            faction="heroes",
            size=Size.MEDIUM,
        ),
    )
    observer = create_test_entity(
        source_id=uuid4(),
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
        source_id=uuid4(),
        name="Lightfoot",
        config=EntityConfig(
            position=(4, 1),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    create_test_entity(
        source_id=uuid4(),
        name="Same-size cover",
        config=EntityConfig(
            position=(2, 1),
            faction="heroes",
            size=Size.SMALL,
        ),
    )
    observer = create_test_entity(
        source_id=uuid4(),
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
