"""Project one native admission into its public lookup domains."""

from dataclasses import dataclass, field

from dnd.core.aoe import snapshot_aoe_aiming_geometry
from dnd.core.base_actions import (
    AvailableActionInfo, AvailableActionsResult, AvailableSelectionPreview,
    AvailableTarget, OpportunityAttackExposure, TargetType,
)
from dnd.player.choices import (
    ChoiceBinding, ChoiceExposure, ChoiceSubject, PlayerAction, PlayerChoices,
    PlayerSelectionPreview, PositionBinding, SelfBinding, SubjectBinding,
)


@dataclass(slots=True)
class ChoiceTables:
    subjects: list[ChoiceSubject] = field(default_factory=list)
    positions: list[tuple[int, int]] = field(default_factory=list)
    target_sets: list[tuple[ChoiceBinding, ...]] = field(default_factory=list)
    subject_refs: dict[ChoiceSubject, int] = field(default_factory=dict)
    position_refs: dict[tuple[int, int], int] = field(default_factory=dict)
    set_refs: dict[tuple[ChoiceBinding, ...], int] = field(default_factory=dict)
    # Native variants can already share target objects; visit each only once.
    binding_refs: dict[int, ChoiceBinding] = field(default_factory=dict)


def position_reference(tables: ChoiceTables, position: tuple[int, int]) -> int:
    reference = tables.position_refs.get(position)
    if reference is None:
        reference = len(tables.positions)
        tables.position_refs[position] = reference
        tables.positions.append(position)
    return reference


def exposure_binding(tables: ChoiceTables, exposure: OpportunityAttackExposure) -> ChoiceExposure:
    return ChoiceExposure(reactor_uuid=exposure.reactor_uuid, reactor_name=exposure.reactor_name,
        from_position=position_reference(tables, exposure.from_position),
        to_position=position_reference(tables, exposure.to_position))


def target_binding(tables: ChoiceTables, target: AvailableTarget) -> ChoiceBinding:
    existing = tables.binding_refs.get(id(target))
    if existing is not None:
        return existing
    values = dict(index=target.index, distance=target.distance, path_cost=target.path_cost,
        extra_target_uuids=None if target.extra_target_uuids is None else tuple(target.extra_target_uuids),
        secondary_set=None if target.secondary_targets is None else target_set(tables, target.secondary_targets),
        is_path_hazardous=target.is_path_hazardous, safe_path_cost=target.safe_path_cost,
        path=None if target.path is None else tuple(position_reference(tables, cell) for cell in target.path),
        safe_path=None if target.safe_path is None else tuple(position_reference(tables, cell) for cell in target.safe_path),
        opportunity_attack_exposures=tuple(exposure_binding(tables, value) for value in target.opportunity_attack_exposures),
        safe_path_opportunity_attack_exposures=tuple(exposure_binding(tables, value) for value in target.safe_path_opportunity_attack_exposures))
    if target.target_uuid is not None:
        subject = ChoiceSubject(uuid=target.target_uuid, kind=target.target_kind, name=target.target_name)
        reference = tables.subject_refs.get(subject)
        if reference is None:
            reference = len(tables.subjects)
            tables.subject_refs[subject] = reference
            tables.subjects.append(subject)
        binding = SubjectBinding(kind='subject', subject=reference,
            position=None if target.position is None else position_reference(tables, target.position), **values)
    elif target.position is not None:
        binding = PositionBinding(kind='position', position=position_reference(tables, target.position), **values)
    else:
        binding = SelfBinding(kind='self', **values)
    tables.binding_refs[id(target)] = binding
    return binding


def target_set(tables: ChoiceTables, targets: list[AvailableTarget] | tuple[AvailableTarget, ...]) -> int:
    bindings = tuple(target_binding(tables, target) for target in targets)
    reference = tables.set_refs.get(bindings)
    if reference is None:
        reference = len(tables.target_sets)
        tables.set_refs[bindings] = reference
        tables.target_sets.append(bindings)
    return reference


def project_choices(original: AvailableActionsResult, actor_position: tuple[int, int]) -> PlayerChoices:
    """Project one native discovery into its compact wire domains; templates are never serialized.

    The session retains `original` itself: its rows are fresh per discovery
    call and no reader mutates a row's targets after discovery (execution binds
    a deep copy, rich callers receive a validated copy), so nothing is detached
    here. Rows are read through their field values, never dumped and validated.
    """
    tables = ChoiceTables()

    def project_rows(rows: list[AvailableActionInfo]) -> tuple[PlayerAction, ...]:
        projected = []
        for row in rows:
            metadata = dict(row)
            del metadata['valid_targets']
            template = row.execution_template
            area = row.target_type == TargetType.POSITION_AOE
            projected.append(PlayerAction(**metadata, target_set=target_set(tables, row.valid_targets),
                area_preview='deferred' if area else 'not_applicable',
                aiming=(snapshot_aoe_aiming_geometry(template.aoe_shape, actor_position)
                    if area and template is not None and template.aoe_shape is not None else None),
                range_origin=template.get_target_origin() if area and template is not None else None,
                area_include_self=template.include_self if area and template is not None else None,
                area_target_filter=template.valid_target_filter if area and template is not None else None,
                area_include_dead=(template.include_dead or row._aoe_include_dead) if area and template is not None else None))
        return tuple(projected)

    entity_rows = project_rows(original.entity_actions)
    position_rows = project_rows(original.position_actions)
    self_rows = project_rows(original.self_actions)
    object_rows = project_rows(original.object_actions)
    return PlayerChoices(discovery_generation=original.discovery_generation, entity_uuid=original.entity_uuid,
        subjects=tuple(tables.subjects), positions=tuple(tables.positions), target_sets=tuple(tables.target_sets),
        entity_actions=entity_rows, position_actions=position_rows, self_actions=self_rows, object_actions=object_rows,
        remaining_movement=original.remaining_movement, handler_details=original.handler_details,
        world_interactions=original.world_interactions)


def project_selection_preview(preview: AvailableSelectionPreview) -> PlayerSelectionPreview:
    """Preview references belong to this response, including new destinations."""
    tables = ChoiceTables()
    next_set = target_set(tables, preview.next_targets)
    next_positions = tuple(position_reference(tables, cell) for cell in preview.next_positions)
    affected = tuple(position_reference(tables, cell) for cell in preview.affected_positions)
    return PlayerSelectionPreview(subjects=tuple(tables.subjects), positions=tuple(tables.positions),
        target_sets=tuple(tables.target_sets), next_target_set=next_set,
        can_confirm=preview.can_confirm, reason=preview.reason,
        effective_target_uuids=preview.effective_target_uuids, next_positions=next_positions,
        geometry=preview.geometry, area_preview=preview.area_preview, affected_positions=affected,
        affected_entity_uuids=preview.affected_entity_uuids, affected_entity_names=preview.affected_entity_names,
        selected_route=preview.selected_route)
