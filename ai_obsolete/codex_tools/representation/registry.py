"""Closed registries for Codex representation components and profiles."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import JsonValue

from ai.codex_tools.representation.models import (
    RepresentationComponentSelection,
    RepresentationComponentSpec,
    RepresentationProfile,
    ResolvedRepresentationComponent,
    ResolvedRepresentationManifest,
)


class RepresentationRegistry:
    """Register semantic definitions and resolve reproducible profile manifests."""

    def __init__(self) -> None:
        """Create an empty component and profile registry."""
        self._components: dict[str, RepresentationComponentSpec] = {}
        self._profiles: dict[str, RepresentationProfile] = {}

    def register_component(self, spec: RepresentationComponentSpec) -> None:
        """Register one uniquely identified component definition.

        Args:
            spec: Validated semantic component definition.

        Raises:
            ValueError: If the component identity is already registered.
        """
        if spec.component_id in self._components:
            raise ValueError(f"Representation component already registered: {spec.component_id}")
        self._components[spec.component_id] = spec

    def register_profile(self, profile: RepresentationProfile) -> None:
        """Register a profile after validating every component choice.

        Args:
            profile: Ordered representation profile definition.

        Raises:
            ValueError: If the profile is duplicated or references an invalid choice.
        """
        if profile.profile_id in self._profiles:
            raise ValueError(f"Representation profile already registered: {profile.profile_id}")
        for selection in profile.component_selections:
            self._validate_selection(selection)
        active_component_ids = {
            selection.component_id
            for selection in profile.component_selections
            if selection.enabled
        }
        missing_required = sorted(
            component_id
            for component_id, spec in self._components.items()
            if spec.required and component_id not in active_component_ids
        )
        if missing_required:
            raise ValueError(
                "Representation profile is missing required components: "
                + ", ".join(missing_required)
            )
        self._profiles[profile.profile_id] = profile

    def component(self, component_id: str) -> RepresentationComponentSpec:
        """Return a registered component definition.

        Args:
            component_id: Stable component identity.

        Returns:
            Registered component specification.

        Raises:
            ValueError: If the component is unknown.
        """
        try:
            return self._components[component_id]
        except KeyError as exc:
            raise ValueError(f"Unknown representation component: {component_id}") from exc

    def profile(self, profile_id: str) -> RepresentationProfile:
        """Return a registered profile definition.

        Args:
            profile_id: Stable profile identity.

        Returns:
            Registered profile definition.

        Raises:
            ValueError: If the profile is unknown.
        """
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise ValueError(f"Unknown representation profile: {profile_id}") from exc

    def components(self) -> tuple[RepresentationComponentSpec, ...]:
        """Return component definitions in stable identity order."""
        return tuple(self._components[key] for key in sorted(self._components))

    def profiles(self) -> tuple[RepresentationProfile, ...]:
        """Return profile definitions in stable identity order."""
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def resolve_profile(
        self,
        profile_id: str,
        *,
        created_at: datetime | None = None,
    ) -> ResolvedRepresentationManifest:
        """Resolve defaults and definitions into one immutable manifest.

        Args:
            profile_id: Registered profile identity.
            created_at: Optional offset-aware audit timestamp.

        Returns:
            Fully resolved manifest with a deterministic content digest.
        """
        profile = self.profile(profile_id)
        components = tuple(
            self._resolve_component(order, selection)
            for order, selection in enumerate(profile.component_selections)
        )
        return ResolvedRepresentationManifest(
            profile_id=profile.profile_id,
            profile_version=profile.version,
            profile_description=profile.description,
            components=components,
            created_at=created_at or datetime.now(timezone.utc),
            compatibility=profile.compatibility,
        )

    def _resolve_component(
        self,
        order: int,
        selection: RepresentationComponentSelection,
    ) -> ResolvedRepresentationComponent:
        """Resolve one profile choice against its registered definition."""
        spec = self._validate_selection(selection)
        provided = dict(selection.parameters)
        resolved: dict[str, JsonValue] = {}
        for parameter in spec.parameter_schema:
            if parameter.parameter_id in provided:
                value = provided.pop(parameter.parameter_id)
                parameter.validate_value(value)
                resolved[parameter.parameter_id] = value
            elif parameter.has_default:
                resolved[parameter.parameter_id] = parameter.default_value
            elif parameter.required:
                raise ValueError(
                    f"Component {spec.component_id} requires parameter {parameter.parameter_id}"
                )
        if provided:
            unknown = ", ".join(sorted(provided))
            raise ValueError(f"Component {spec.component_id} received unknown parameters: {unknown}")
        return ResolvedRepresentationComponent(
            order=order,
            spec=spec,
            enabled=selection.enabled,
            exposure=selection.exposure,
            parameters={key: resolved[key] for key in sorted(resolved)},
        )

    def _validate_selection(
        self,
        selection: RepresentationComponentSelection,
    ) -> RepresentationComponentSpec:
        """Validate a profile choice without mutating either definition."""
        spec = self.component(selection.component_id)
        if selection.exposure not in spec.supported_exposures:
            raise ValueError(
                f"Component {spec.component_id} does not support {selection.exposure.value} exposure"
            )
        parameter_specs = {
            parameter.parameter_id: parameter
            for parameter in spec.parameter_schema
        }
        unknown_parameters = set(selection.parameters) - set(parameter_specs)
        if unknown_parameters:
            unknown = ", ".join(sorted(unknown_parameters))
            raise ValueError(f"Component {spec.component_id} received unknown parameters: {unknown}")
        for parameter_id, value in selection.parameters.items():
            parameter_specs[parameter_id].validate_value(value)
        missing = [
            parameter.parameter_id
            for parameter in spec.parameter_schema
            if parameter.required and parameter.parameter_id not in selection.parameters
        ]
        if missing:
            raise ValueError(
                f"Component {spec.component_id} is missing required parameters: {', '.join(missing)}"
            )
        return spec
