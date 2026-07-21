"""Contracts for typed and reproducible Codex representation profiles."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import Field, ValidationError
import pytest

from ai.codex_tools.representation.models import (
    ExposureTiming,
    InformationTransform,
    OmissionContract,
    Recoverability,
    RecoveryInstruction,
    RepresentationBlock,
    RepresentationComponentSelection,
    RepresentationComponentSpec,
    RepresentationInputDomain,
    RepresentationModel,
    RepresentationProfile,
    RepresentationRole,
    SemanticIntent,
    SubjectivityContract,
)
from ai.codex_tools.representation.profiles import (
    BALANCED_V2_PROFILE,
    BALANCED_V2_PROFILE_ID,
    BUILTIN_COMPONENT_SPECS,
    CURRENT_V1_PROFILE,
    CURRENT_V1_PROFILE_ID,
    build_builtin_representation_registry,
)
from ai.codex_tools.representation.registry import RepresentationRegistry


class ExamplePayload(RepresentationModel):
    """Small typed payload used to prove generic block validation."""

    actor_uuid: str = Field(description="Controlled actor represented by the example block.")


def test_component_spec_validates_exposure_transform_and_omission_contracts() -> None:
    """Component definitions reject incoherent semantic and recovery claims."""
    with pytest.raises(ValidationError, match="Default exposure must be supported"):
        _component_spec(
            default_exposure=ExposureTiming.DECISION_EPOCH,
            supported_exposures=(ExposureTiming.ON_DEMAND,),
        )

    with pytest.raises(ValidationError, match="Policy advice components must declare a rank transform"):
        _component_spec(
            role=RepresentationRole.POLICY_ADVICE,
            transform=InformationTransform.SELECT,
        )

    with pytest.raises(ValidationError, match="Canonical subjective omissions must remain locally recoverable"):
        _component_spec(
            omission_contract=OmissionContract(
                source_domains=(RepresentationInputDomain.KNOWN_ENTITIES,),
                omitted_paths=("world.known_entities.*.conditions",),
                recoverability=(Recoverability.NOT_RECOVERABLE,),
                rationale="Deliberately invalid canonical omission.",
            ),
        )


def test_registry_rejects_unknown_components_and_invalid_profile_parameters() -> None:
    """Profiles may select only registered components and declared parameters."""
    registry = RepresentationRegistry()
    profile = RepresentationProfile(
        profile_id="codex.invalid",
        version="1.0.0",
        description="Invalid profile used for registry validation.",
        component_selections=(
            RepresentationComponentSelection(
                component_id="missing.component",
                exposure=ExposureTiming.DECISION_EPOCH,
            ),
        ),
    )

    with pytest.raises(ValueError, match="Unknown representation component"):
        registry.register_profile(profile)

    registry.register_component(_component_spec())
    invalid_parameters = profile.model_copy(update={
        "component_selections": (
            RepresentationComponentSelection(
                component_id="test.component",
                exposure=ExposureTiming.DECISION_EPOCH,
                parameters={"made_up": True},
            ),
        ),
    })
    with pytest.raises(ValueError, match="unknown parameters"):
        registry.register_profile(invalid_parameters)


def test_manifest_order_and_digest_are_deterministic() -> None:
    """Registration order and audit timestamps do not change profile identity."""
    first_registry = build_builtin_representation_registry()
    second_registry = RepresentationRegistry()
    for spec in reversed(BUILTIN_COMPONENT_SPECS):
        second_registry.register_component(spec)
    second_registry.register_profile(BALANCED_V2_PROFILE)

    first = first_registry.resolve_profile(
        BALANCED_V2_PROFILE_ID,
        created_at=datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc),
    )
    second = second_registry.resolve_profile(
        BALANCED_V2_PROFILE_ID,
        created_at=datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
    )

    expected_order = tuple(
        selection.component_id
        for selection in BALANCED_V2_PROFILE.component_selections
    )
    assert first.component_order == expected_order
    assert second.component_order == expected_order
    assert first.manifest_digest == second.manifest_digest
    assert len(first.manifest_digest) == 64
    assert first.model_dump(mode="json")["manifest_digest"] == first.manifest_digest


def test_definition_and_profile_selection_remain_separate() -> None:
    """Ablation choices resolve without mutating shared component semantics."""
    registry = build_builtin_representation_registry()
    contact_spec = registry.component("contacts.partition")

    current = registry.resolve_profile(CURRENT_V1_PROFILE_ID)
    balanced = registry.resolve_profile(BALANCED_V2_PROFILE_ID)
    current_contact = next(
        component for component in current.components
        if component.spec.component_id == "contacts.partition"
    )
    balanced_contact = next(
        component for component in balanced.components
        if component.spec.component_id == "contacts.partition"
    )

    assert current_contact.spec is contact_spec
    assert balanced_contact.spec is contact_spec
    assert current_contact.parameters["include_remembered_allies"] is False
    assert balanced_contact.parameters["include_remembered_allies"] is True
    assert contact_spec.parameter_schema[0].default_value is False
    assert current.manifest_digest != balanced.manifest_digest


def test_builtin_profiles_capture_compatibility_and_neutral_oracle_semantics() -> None:
    """Current-v1 preserves eager advice while balanced-v2 makes it on demand."""
    current_oracle = _selection(CURRENT_V1_PROFILE, "oracle.policy")
    balanced_oracle = _selection(BALANCED_V2_PROFILE, "oracle.policy")
    balanced_telemetry = _selection(BALANCED_V2_PROFILE, "telemetry.runtime")

    assert current_oracle.exposure is ExposureTiming.DECISION_EPOCH
    assert current_oracle.parameters["advance_lifecycle_on_match"] is True
    assert CURRENT_V1_PROFILE.compatibility.preserves_eager_policy_lifecycle is True
    assert balanced_oracle.exposure is ExposureTiming.ON_DEMAND
    assert balanced_oracle.parameters["advance_lifecycle_on_match"] is False
    assert balanced_telemetry.exposure is ExposureTiming.NEVER
    assert "events.recent_logs" in {
        selection.component_id for selection in BALANCED_V2_PROFILE.component_selections
    }
    assert "events.decision_delta" in {
        selection.component_id for selection in BALANCED_V2_PROFILE.component_selections
    }
    balanced_actions = _selection(BALANCED_V2_PROFILE, "actions.index")
    balanced_presentation = _selection(BALANCED_V2_PROFILE, "presentation.typed_json")
    assert balanced_actions.parameters["family_limit"] == 24
    assert balanced_actions.parameters["capability_limit"] == 24
    assert balanced_presentation.parameters["include_command_follow_up"] is True


def test_action_and_command_ablation_settings_change_manifest_identity_independently() -> None:
    """Every model-facing limit and receipt choice participates in experiment identity."""
    registry = build_builtin_representation_registry()
    baseline = registry.resolve_profile(BALANCED_V2_PROFILE_ID)
    actions = next(
        component
        for component in baseline.components
        if component.spec.component_id == "actions.index"
    )
    presentation = next(
        component
        for component in baseline.components
        if component.spec.component_id == "presentation.typed_json"
    )
    action_variant = baseline.model_copy(update={
        "components": tuple(
            component.model_copy(update={
                "parameters": {**component.parameters, "family_limit": 12},
            })
            if component is actions
            else component
            for component in baseline.components
        ),
    })
    receipt_variant = baseline.model_copy(update={
        "components": tuple(
            component.model_copy(update={
                "parameters": {
                    **component.parameters,
                    "include_command_follow_up": False,
                },
            })
            if component is presentation
            else component
            for component in baseline.components
        ),
    })

    assert action_variant.manifest_digest != baseline.manifest_digest
    assert receipt_variant.manifest_digest != baseline.manifest_digest
    assert action_variant.manifest_digest != receipt_variant.manifest_digest


def test_representation_block_records_typed_provenance_and_costs() -> None:
    """Blocks retain typed payload, provenance, omissions, recovery, and timing."""
    block = RepresentationBlock[ExamplePayload](
        component_id="contacts.partition",
        component_version="1.0.0",
        role=RepresentationRole.DETERMINISTIC_DERIVATION,
        transform=InformationTransform.PARTITION,
        observation_cursor=42,
        epoch_id="epoch-7",
        generated_at=datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
        payload=ExamplePayload(actor_uuid="hero"),
        source_paths=("world.known_entities",),
        omitted_item_count=3,
        recovery_hints=(
            RecoveryInstruction(
                method=Recoverability.LOCAL_SELECT,
                endpoint="POST /v1/query",
                description="Select complete known entity facts.",
            ),
        ),
        timing_ms=0.125,
        payload_bytes=48,
        warnings=("Object state remains open JSON.",),
    )

    assert isinstance(block.payload, ExamplePayload)
    assert block.payload.actor_uuid == "hero"
    assert block.source_paths == ("world.known_entities",)
    assert block.omitted_item_count == 3
    assert block.recovery_hints[0].method is Recoverability.LOCAL_SELECT
    assert block.timing_ms == 0.125
    assert block.payload_bytes == 48


def test_public_representation_models_describe_every_pydantic_field() -> None:
    """Representation contracts remain self-documenting in generated schemas."""
    models = (
        SubjectivityContract,
        OmissionContract,
        RepresentationComponentSpec,
        RepresentationComponentSelection,
        RepresentationProfile,
        RecoveryInstruction,
        RepresentationBlock[ExamplePayload],
    )

    missing = {
        f"{model.__name__}.{name}"
        for model in models
        for name, field in model.model_fields.items()
        if not field.description
    }
    assert missing == set()


def _selection(
    profile: RepresentationProfile,
    component_id: str,
) -> RepresentationComponentSelection:
    """Return one selection from a built-in profile."""
    return next(
        selection for selection in profile.component_selections
        if selection.component_id == component_id
    )


def _component_spec(
    *,
    role: RepresentationRole = RepresentationRole.STATE_SELECTION,
    transform: InformationTransform = InformationTransform.SELECT,
    default_exposure: ExposureTiming = ExposureTiming.DECISION_EPOCH,
    supported_exposures: tuple[ExposureTiming, ...] = (ExposureTiming.DECISION_EPOCH,),
    omission_contract: OmissionContract | None = None,
) -> RepresentationComponentSpec:
    """Build a minimal valid component definition for registry tests."""
    return RepresentationComponentSpec(
        component_id="test.component",
        version="1.0.0",
        title="Test component",
        description="Small component definition used for isolated registry tests.",
        role=role,
        semantic_intent=SemanticIntent.PRESERVE_TURN_STATE,
        input_domains=(RepresentationInputDomain.KNOWN_ENTITIES,),
        output_model="tests.ExamplePayload",
        transform=transform,
        omission_contract=omission_contract or OmissionContract(
            source_domains=(RepresentationInputDomain.KNOWN_ENTITIES,),
            recoverability=(Recoverability.NOT_APPLICABLE,),
            rationale="The test component omits no source information.",
        ),
        subjectivity_contract=SubjectivityContract(
            description="The test component reads only session-subjective state."
        ),
        deterministic=True,
        default_exposure=default_exposure,
        supported_exposures=supported_exposures,
        implementation_ref="tests.TestComponent",
    )
