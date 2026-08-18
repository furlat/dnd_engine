"""Focused contract tests for authoritative public condition presentation."""

from collections.abc import Iterator
from typing import Any, TypeVar
from uuid import UUID, uuid4

import pytest
from pydantic import Field, ValidationError

from devtools.generate_event_contract import import_dnd_modules
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.conditions import (
    Blinded,
    Charmed,
    ConcentrationActionMarker,
    Paralyzed,
    Stunned,
)
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.types.conditions import ConditionCategory, DurationType
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventType,
)
from dnd.core.gridmap import GridMap
from dnd.core.modifiers import ContextAwareCondition
from dnd.entities.entity import Entity, EntityConfig
from dnd.items.consumables import _WeaponCoatCondition
from dnd.monsters.traits import SimpleMarkerCondition
from dnd.player_character_body import PLAYER_CHARACTER_BODY_DECLARATION
from dnd.runtime_reset import reset_engine_runtime
from dnd.content.spatial_effect_recipes import GREASE_SURFACE_RECIPE
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spells.conjuration import GreaseZone
from server.player_replication.world_projection import (
    SubjectiveSpatialMemory,
    build_subjective_world,
)
from server.player_replication_contract import PerspectiveKind, SubjectivePerspective
from server.world_contracts import APIContentRefSnapshot
from server.world_projection import (
    project_condition_summary,
    project_entity_summary,
    project_grid,
    project_observed_tile,
)

ConditionT = TypeVar("ConditionT", bound=BaseCondition)


def _wire_content_ref(condition: BaseCondition) -> APIContentRefSnapshot:
    """Return the exact wire snapshot for one bound condition fixture."""
    assert condition.behavior_binding is not None
    return APIContentRefSnapshot.model_validate(
        condition.behavior_binding.definition_ref.model_dump(mode="python"),
    )


class AlphaPresentationCondition(BaseCondition):
    """Public fixture condition with exact backend-authored presentation."""

    name: str = Field(default="Alpha State")
    description: str = Field(default="Exact alpha rules text.")


class BetaPresentationCondition(BaseCondition):
    """Second public fixture condition used to prove stable ordering."""

    name: str = Field(default="Beta State")
    description: str = Field(default="Exact beta rules text.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.STATUS)


class SharedNameAlphaCondition(BaseCondition):
    """First mechanic using a deliberately shared display name."""

    name: str = Field(default="Shared Display Name")
    description: str = Field(default="First shared-name mechanic.")


class SharedNameBetaCondition(BaseCondition):
    """Second mechanic using the same display name."""

    name: str = Field(default="Shared Display Name")
    description: str = Field(default="Second shared-name mechanic.")


class InternalPresentationMarker(BaseCondition):
    """Private fixture marker that must never cross the public contract."""

    name: str = Field(default="Private Presentation Marker")
    description: str = Field(default="Private marker rules text.")
    condition_category: ConditionCategory = Field(default=ConditionCategory.INTERNAL)


_FIXTURE_DEFINITION_TYPES: dict[type[BaseCondition], type[BaseCondition]] = {
    AlphaPresentationCondition: Blinded,
    BetaPresentationCondition: Charmed,
    SharedNameAlphaCondition: Paralyzed,
    SharedNameBetaCondition: Stunned,
}


@pytest.fixture(scope="module", autouse=True)
def installed_content_system() -> None:
    """Install the exact declarations used by projected fixture bindings."""
    bootstrap_content_system()


@pytest.fixture
def presentation_grid() -> Iterator[GridMap]:
    """Provide an isolated runtime for entity, tile, and subjective projections."""
    grid = reset_engine_runtime(grid_size=(3, 1))
    try:
        yield grid
    finally:
        reset_engine_runtime()


def _duration(
    source_uuid: UUID,
    target_uuid: UUID,
    duration_type: DurationType,
    value: int | ContextAwareCondition | None,
) -> Duration:
    """Build one live duration without relying on condition application."""
    return Duration(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        duration_type=duration_type,
        duration=value,
    )


def _condition(
    condition_type: type[ConditionT],
    source_uuid: UUID,
    target_uuid: UUID,
    *,
    duration_type: DurationType = DurationType.PERMANENT,
    duration: int | ContextAwareCondition | None = None,
    **updates: Any,
) -> ConditionT:
    """Construct a presentation fixture condition with explicit duration state."""
    condition = condition_type(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        duration=_duration(source_uuid, target_uuid, duration_type, duration),
        **updates,
    )
    definition_type = _FIXTURE_DEFINITION_TYPES.get(condition_type)
    if definition_type is not None:
        declaration = get_content_declaration(definition_type)
        condition.behavior_binding = BehaviorBinding(
            definition_ref=declaration.ref,
            provided_by_ref=declaration.ref,
            runtime_owner_uuid=target_uuid,
        )
    return condition


def test_entity_projection_is_authoritative_filtered_and_deterministic(
    presentation_grid: GridMap,
) -> None:
    """Entity names are derived from sorted, complete public detail rows."""
    _ = presentation_grid
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Condition bearer",
        config=EntityConfig(position=(1, 0), faction="heroes"),
        content_ref=PLAYER_CHARACTER_BODY_DECLARATION.ref,
    )
    beta = _condition(
        BetaPresentationCondition,
        entity.uuid,
        entity.uuid,
        duration_type=DurationType.PERMANENT,
    )
    internal = _condition(
        InternalPresentationMarker,
        entity.uuid,
        entity.uuid,
        duration_type=DurationType.ROUNDS,
        duration=9,
    )
    alpha = _condition(
        AlphaPresentationCondition,
        entity.uuid,
        entity.uuid,
        duration_type=DurationType.ROUNDS,
        duration=3,
    )
    entity.active_conditions[beta.name] = beta
    entity.active_conditions[internal.name] = internal
    entity.active_conditions[alpha.name] = alpha

    summary = project_entity_summary(entity)

    assert summary.conditions == ["Alpha State", "Beta State"]
    assert summary.conditions == [detail.name for detail in summary.condition_details]
    assert [detail.semantic_key for detail in summary.condition_details] == [
        alpha.get_semantic_key(),
        beta.get_semantic_key(),
    ]
    assert alpha.behavior_binding is not None
    assert beta.behavior_binding is not None
    assert [detail.content_ref for detail in summary.condition_details] == [
        _wire_content_ref(alpha),
        _wire_content_ref(beta),
    ]
    assert summary.condition_details[0].description == "Exact alpha rules text."
    assert summary.condition_details[0].category == "condition"
    assert summary.condition_details[0].duration_type == "rounds"
    assert summary.condition_details[0].remaining_rounds == 3
    assert summary.condition_details[1].category == "status"
    assert summary.condition_details[1].duration_type == "permanent"
    assert summary.condition_details[1].remaining_rounds is None
    assert internal.name not in summary.model_dump_json()

    mismatched = summary.model_dump(mode="python")
    mismatched["conditions"] = ["Drifted legacy name"]
    with pytest.raises(ValidationError, match="condition detail names"):
        type(summary).model_validate(mismatched)


def test_non_round_durations_never_expose_remaining_rounds() -> None:
    """Only round-based duration state crosses the public DTO."""
    source_uuid = uuid4()
    target_uuid = uuid4()
    conditional = lambda *_args: False
    cases = (
        (DurationType.PERMANENT, None),
        (DurationType.ON_CONDITION, conditional),
        (DurationType.UNTIL_LONG_REST, None),
    )

    for duration_type, duration in cases:
        condition = _condition(
            AlphaPresentationCondition,
            source_uuid,
            target_uuid,
            duration_type=duration_type,
            duration=duration,
        )
        detail = project_condition_summary(condition)
        assert detail.duration_type == duration_type.value
        assert detail.remaining_rounds is None


def test_same_display_name_keeps_distinct_backend_semantic_keys() -> None:
    """Class identity, not display text, remains the authoritative mechanic key."""
    source_uuid = uuid4()
    target_uuid = uuid4()
    first = _condition(SharedNameAlphaCondition, source_uuid, target_uuid)
    second = _condition(SharedNameBetaCondition, source_uuid, target_uuid)

    first_detail = project_condition_summary(first)
    second_detail = project_condition_summary(second)

    assert first_detail.name == second_detail.name == "Shared Display Name"
    assert first_detail.content_ref != second_detail.content_ref
    assert first_detail.semantic_key != second_detail.semantic_key
    assert first_detail.semantic_key == first.get_semantic_key()
    assert second_detail.semantic_key == second.get_semantic_key()


def test_unbound_public_condition_cannot_enter_player_projection() -> None:
    """Projection never fabricates identity from a class path or display name."""
    condition = AlphaPresentationCondition(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
    )

    with pytest.raises(
        ValueError,
        match="no exact authored content binding",
    ):
        project_condition_summary(condition)


def test_tile_details_share_name_visibility_and_subjective_memory_policy(
    presentation_grid: GridMap,
) -> None:
    """Rich tile rows cannot reveal a condition hidden from the legacy name list."""
    grid = presentation_grid
    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Tile observer",
        config=EntityConfig(position=(0, 0), faction="heroes"),
        content_ref=PLAYER_CHARACTER_BODY_DECLARATION.ref,
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}
    observer.senses.entities = {}
    observer.senses.objects = {}
    tile = grid.get_tile(1, 0)
    assert tile is not None
    passive_perception = observer.get_passive_perception()

    visible = _condition(
        AlphaPresentationCondition,
        observer.uuid,
        tile.uuid,
        condition_stealth_dc=passive_perception - 1,
    )
    hidden = _condition(
        BetaPresentationCondition,
        observer.uuid,
        tile.uuid,
        condition_stealth_dc=passive_perception,
        description="SECRET HIDDEN TILE DESCRIPTION",
        semantic_key="secret.hidden.tile.semantic-key",
    )
    internal = _condition(
        InternalPresentationMarker,
        observer.uuid,
        tile.uuid,
    )
    tile.active_conditions[hidden.name] = hidden
    tile.active_conditions[internal.name] = internal
    tile.active_conditions[visible.name] = visible

    observed = project_observed_tile(grid, (1, 0), (observer.uuid,))
    objective_for_observer = next(
        row
        for row in project_grid(grid, observer.uuid).tiles
        if (row.x, row.y) == (1, 0)
    )

    assert observed.conditions == ["Alpha State"]
    assert observed.conditions == [detail.name for detail in observed.condition_details]
    assert observed.condition_details == objective_for_observer.condition_details
    assert "SECRET HIDDEN TILE DESCRIPTION" not in observed.model_dump_json()
    assert "secret.hidden.tile.semantic-key" not in observed.model_dump_json()
    assert internal.name not in observed.model_dump_json()

    perspective = SubjectivePerspective(
        perspective_epoch_id="condition-detail-epoch",
        kind=PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION,
        controlled_entity_uuids=(str(observer.uuid),),
        observer_entity_uuids=(str(observer.uuid),),
        active_observer_uuid=str(observer.uuid),
    )
    subjective = build_subjective_world(
        perspective=perspective,
        grid=grid,
        entities=(observer,),
        encounter=None,
        memory=SubjectiveSpatialMemory(
            perspective_epoch_id=perspective.perspective_epoch_id,
        ),
    )
    subjective_tile = next(
        row
        for row in subjective.state.grid.tiles
        if (row.x, row.y) == (1, 0)
    )

    assert subjective_tile.condition_details == observed.condition_details
    assert subjective_tile.conditions == observed.conditions
    assert "SECRET HIDDEN TILE DESCRIPTION" not in subjective.model_dump_json()
    assert "secret.hidden.tile.semantic-key" not in subjective.model_dump_json()

    mismatched = subjective_tile.model_dump(mode="python")
    mismatched["conditions"] = ["Drifted tile name"]
    with pytest.raises(ValidationError, match="condition detail names"):
        type(subjective_tile).model_validate(mismatched)


def test_spatial_condition_footprint_projects_without_tile_marker_conditions(
    presentation_grid: GridMap,
) -> None:
    """An indexed ground effect is visible without duplicating its lifetime per tile."""
    source_uuid = uuid4()
    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Surface observer",
        config=EntityConfig(position=(0, 0), faction="heroes"),
        content_ref=PLAYER_CHARACTER_BODY_DECLARATION.ref,
    )
    observer.senses.visible = {(0, 0): True, (1, 0): True}
    observer.senses.seen = {(0, 0), (1, 0)}

    surface = materialize_spatial_condition(
        GREASE_SURFACE_RECIPE,
        source_uuid,
        position=(1, 0),
        faction=None,
        condition_type=GreaseZone,
    )
    parent = Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.CONDITION_APPLICATION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    result = surface.activate(parent_event=parent)
    assert result is not None
    assert not result.canceled

    tile = presentation_grid.get_tile(1, 0)
    assert tile is not None
    assert "Grease" not in tile.active_conditions
    assert "Grease Zone" not in tile.active_conditions
    assert presentation_grid.get_spatial_condition_uuids_at((1, 0)) == {
        surface.uuid,
    }

    observed = project_observed_tile(
        presentation_grid,
        (1, 0),
        (observer.uuid,),
    )
    assert observed.conditions == []
    assert observed.condition_details == []
    assert observed.is_hazardous
    assert observed.walking_cost == 2
    assert len(observed.spatial_effects) == 1
    assert observed.spatial_effects[0].uuid == str(surface.uuid)
    assert observed.spatial_effects[0].layer == "ground_surface"
    assert observed.spatial_effects[0].content_ref == (
        APIContentRefSnapshot.model_validate(
            GREASE_SURFACE_RECIPE.ref.model_dump(mode="python"),
        )
    )

    surface.deactivate()
    assert BaseCondition.get(surface.uuid) is None
    assert presentation_grid.get_spatial_condition_uuids_at((1, 0)) == set()
    assert tile.walking_cost.normalized_score == 1


@pytest.mark.parametrize(
    "condition_type",
    (
        SimpleMarkerCondition,
        ConcentrationActionMarker,
        _WeaponCoatCondition,
    ),
)
def test_tracking_only_conditions_are_internal(
    condition_type: type[BaseCondition],
) -> None:
    """Lifecycle and already-triggered markers cannot become public tooltips."""
    category = condition_type.model_fields["condition_category"].get_default(
        call_default_factory=True,
    )
    assert category is ConditionCategory.INTERNAL


def test_every_public_condition_class_declares_name_and_description() -> None:
    """Reachable public condition types cannot fall back to missing tooltip text."""
    import_dnd_modules()
    seen: set[type[BaseCondition]] = set()
    pending = list(BaseCondition.__subclasses__())
    failures: list[str] = []

    while pending:
        condition_type = pending.pop()
        pending.extend(condition_type.__subclasses__())
        if condition_type in seen:
            continue
        seen.add(condition_type)
        if not condition_type.__module__.startswith("dnd."):
            continue
        fields = condition_type.model_fields
        category = fields["condition_category"].get_default(
            call_default_factory=True,
        )
        if category is ConditionCategory.INTERNAL:
            continue
        name = fields["name"].get_default(call_default_factory=True)
        description = fields["description"].get_default(
            call_default_factory=True,
        )
        if not isinstance(name, str) or not name.strip():
            failures.append(f"{condition_type.__module__}.{condition_type.__name__}: name")
        if not isinstance(description, str) or not description.strip():
            failures.append(
                f"{condition_type.__module__}.{condition_type.__name__}: description"
            )

    assert failures == []
