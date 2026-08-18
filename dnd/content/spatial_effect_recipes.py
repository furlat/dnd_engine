"""Built-in authored definitions for persistent spatial phenomena."""

from __future__ import annotations

from collections.abc import Callable

from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclaration,
    get_content_declaration,
    spatial_effect_definition,
)
from dnd.core.content.spatial_effect_definitions import (
    SpatialEffectDefinition,
    SpatialEffectTransitionDefinition,
)
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectBlockingPolicy,
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
    SpatialEffectTransitionAction,
)


def _descriptor(
    *,
    display_name: str,
    content_id: str,
    layer: SpatialEffectLayer,
    tags: tuple[str, ...] | None = None,
) -> ContentDescriptorSpec:
    """Build one mechanics-free descriptor for an observed phenomenon."""
    return ContentDescriptorSpec(
        display_name=display_name,
        description=f"Persistent {display_name} spatial effect.",
        tags=(
            tags
            if tags is not None
            else ("spatial_effect", layer.value, "spell", "srd")
        ),
        visibility=ContentVisibility.OBSERVED,
        presentation=ContentPresentation(
            visual_variant_key=content_id,
            vfx_profile=content_id,
            ui_group=f"spatial_effects.{layer.value}",
        ),
        ordering=ContentOrdering(
            sort_group=f"spatial_effects.{layer.value}",
            sort_order=0,
        ),
    )


def _provenance(display_name: str) -> ContentProvenance:
    """Return the shared SRD provenance contract for one spell effect."""
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=f"SRD 5.1 (CC-BY-4.0), Spell: {display_name}",
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Independent encounter-local spatial owner; spell concentration "
            "is represented only by an explicit external lifetime link."
        ),
    )


def _environment_provenance(display_name: str) -> ContentProvenance:
    """Return reviewed provenance for an engine-owned material definition."""
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=f"Neurodragon environmental material: {display_name}",
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Persistent material state with transitions owned by the frozen "
            "spatial-effect content contract."
        ),
    )


def _feature_provenance(display_name: str) -> ContentProvenance:
    """Return reviewed SRD provenance for one feature-owned field."""
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=f"SRD 5.1 (CC-BY-4.0), Trait: {display_name}",
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Entity-anchored field owns membership while ordinary conditions "
            "own the resulting roll modifiers."
        ),
    )


def _definition(
    *,
    anchor_kind: SpatialEffectAnchorKind = (
        SpatialEffectAnchorKind.FIXED_POSITION
    ),
    layer: SpatialEffectLayer,
    occupancy_policy: SpatialEffectOccupancyPolicy,
    blocking_policy: SpatialEffectBlockingPolicy = (
        SpatialEffectBlockingPolicy.NONE
    ),
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset(),
    first_per_turn_trigger_kinds: frozenset[
        SpatialEffectTriggerKind
    ] = frozenset(),
) -> SpatialEffectDefinition:
    return SpatialEffectDefinition(
        anchor_kind=anchor_kind,
        layer=layer,
        occupancy_policy=occupancy_policy,
        blocking_policy=blocking_policy,
        trigger_kinds=trigger_kinds,
        first_per_turn_trigger_kinds=first_per_turn_trigger_kinds,
    )


_GROUND_DEFINITION = _definition(
    layer=SpatialEffectLayer.GROUND_SURFACE,
    occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
)
_CLOUD_DEFINITION = _definition(
    layer=SpatialEffectLayer.CLOUD,
    occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
)
_FIELD_DEFINITION = _definition(
    layer=SpatialEffectLayer.FIELD,
    occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
)
_WORLD_OBJECT_FIELD_DEFINITION = _definition(
    anchor_kind=SpatialEffectAnchorKind.WORLD_OBJECT,
    layer=SpatialEffectLayer.FIELD,
    occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
)


def _declaration_and_recipe(
    marker: Callable[[], None],
) -> tuple[ContentDeclaration, ContentRecipe]:
    declaration = get_content_declaration(marker)
    return declaration, ContentRecipe.create(
        ref=declaration.ref,
        parameters={},
    )


@spatial_effect_definition(
    pack_id="content.srd_5_1_cc",
    content_id="spatial_effect.spell.grease",
    version=1,
    descriptor=_descriptor(
        display_name="Grease Surface",
        content_id="spatial_effect.spell.grease",
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ),
    provenance=_provenance("Grease"),
    spatial_effect_definition=_definition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_END,
        }),
    ),
)
def define_grease_surface() -> None:
    """Authored spatial metadata marker."""


(
    GREASE_SURFACE_DECLARATION,
    GREASE_SURFACE_RECIPE,
) = _declaration_and_recipe(define_grease_surface)


@spatial_effect_definition(
    pack_id="content.neurodragon",
    content_id="spatial_effect.material.fire",
    version=1,
    descriptor=_descriptor(
        display_name="Fire Surface",
        content_id="spatial_effect.material.fire",
        layer=SpatialEffectLayer.GROUND_SURFACE,
        tags=("spatial_effect", "ground_surface", "environmental_material"),
    ),
    provenance=_environment_provenance("Fire Surface"),
    spatial_effect_definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.DOUSE,
                action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
            ),
        ),
    ),
)
def define_fire_surface() -> None:
    """Authored spatial metadata marker."""


(
    FIRE_SURFACE_DECLARATION,
    FIRE_SURFACE_RECIPE,
) = _declaration_and_recipe(define_fire_surface)


@spatial_effect_definition(
    pack_id="content.neurodragon",
    content_id="spatial_effect.material.steam",
    version=1,
    descriptor=_descriptor(
        display_name="Steam Cloud",
        content_id="spatial_effect.material.steam",
        layer=SpatialEffectLayer.CLOUD,
        tags=("spatial_effect", "cloud", "environmental_material"),
    ),
    provenance=_environment_provenance("Steam Cloud"),
    spatial_effect_definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.CLOUD,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
        }),
    ),
)
def define_steam_cloud() -> None:
    """Authored spatial metadata marker."""


(
    STEAM_CLOUD_DECLARATION,
    STEAM_CLOUD_RECIPE,
) = _declaration_and_recipe(define_steam_cloud)


@spatial_effect_definition(
    pack_id="content.neurodragon",
    content_id="spatial_effect.material.ice",
    version=1,
    descriptor=_descriptor(
        display_name="Ice Surface",
        content_id="spatial_effect.material.ice",
        layer=SpatialEffectLayer.GROUND_SURFACE,
        tags=("spatial_effect", "ground_surface", "environmental_material"),
    ),
    provenance=_environment_provenance("Ice Surface"),
    spatial_effect_definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_END,
        }),
        first_per_turn_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_END,
        }),
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.VAPORIZE,
                action=(
                    SpatialEffectTransitionAction
                    .REMOVE_AFFECTED_AND_CREATE_SECONDARY
                ),
                replacement_recipe=STEAM_CLOUD_RECIPE,
            ),
        ),
    ),
    dependencies=(
        ContentDependency(
            relation=(
                ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT
            ),
            target_ref=STEAM_CLOUD_RECIPE.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Vaporized ice becomes the exact steam cloud material.",
        ),
    ),
)
def define_ice_surface() -> None:
    """Authored spatial metadata marker."""


(
    ICE_SURFACE_DECLARATION,
    ICE_SURFACE_RECIPE,
) = _declaration_and_recipe(define_ice_surface)


@spatial_effect_definition(
    pack_id="content.neurodragon",
    content_id="spatial_effect.material.electrified_water",
    version=1,
    descriptor=_descriptor(
        display_name="Electrified Water",
        content_id="spatial_effect.material.electrified_water",
        layer=SpatialEffectLayer.GROUND_SURFACE,
        tags=("spatial_effect", "ground_surface", "environmental_material"),
    ),
    provenance=_environment_provenance("Electrified Water"),
    spatial_effect_definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
            SpatialEffectTriggerKind.TURN_START,
        }),
        first_per_turn_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.FREEZE,
                action=SpatialEffectTransitionAction.REPLACE_AFFECTED,
                replacement_recipe=ICE_SURFACE_RECIPE,
            ),
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.VAPORIZE,
                action=(
                    SpatialEffectTransitionAction
                    .REMOVE_AFFECTED_AND_CREATE_SECONDARY
                ),
                replacement_recipe=STEAM_CLOUD_RECIPE,
            ),
        ),
    ),
    dependencies=(
        ContentDependency(
            relation=(
                ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT
            ),
            target_ref=ICE_SURFACE_RECIPE.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Frozen electrified water becomes exact ordinary ice.",
        ),
        ContentDependency(
            relation=(
                ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT
            ),
            target_ref=STEAM_CLOUD_RECIPE.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Vaporized electrified water becomes exact steam.",
        ),
    ),
)
def define_electrified_water() -> None:
    """Authored spatial metadata marker."""


(
    ELECTRIFIED_WATER_DECLARATION,
    ELECTRIFIED_WATER_RECIPE,
) = _declaration_and_recipe(define_electrified_water)


@spatial_effect_definition(
    pack_id="content.neurodragon",
    content_id="spatial_effect.material.water_surface",
    version=1,
    descriptor=_descriptor(
        display_name="Wet Surface",
        content_id="spatial_effect.material.water_surface",
        layer=SpatialEffectLayer.GROUND_SURFACE,
        tags=("spatial_effect", "ground_surface", "environmental_material"),
    ),
    provenance=_environment_provenance("Wet Surface"),
    spatial_effect_definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
        }),
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.FREEZE,
                action=SpatialEffectTransitionAction.REPLACE_AFFECTED,
                replacement_recipe=ICE_SURFACE_RECIPE,
            ),
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.ELECTRIFY,
                action=SpatialEffectTransitionAction.REPLACE_AFFECTED,
                replacement_recipe=ELECTRIFIED_WATER_RECIPE,
            ),
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.VAPORIZE,
                action=(
                    SpatialEffectTransitionAction
                    .REMOVE_AFFECTED_AND_CREATE_SECONDARY
                ),
                replacement_recipe=STEAM_CLOUD_RECIPE,
            ),
        ),
    ),
    dependencies=(
        ContentDependency(
            relation=(
                ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT
            ),
            target_ref=ICE_SURFACE_RECIPE.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Frozen wet surface becomes exact ice.",
        ),
        ContentDependency(
            relation=(
                ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT
            ),
            target_ref=ELECTRIFIED_WATER_RECIPE.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Electrified wet surface becomes exact energized water.",
        ),
        ContentDependency(
            relation=(
                ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT
            ),
            target_ref=STEAM_CLOUD_RECIPE.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Vaporized wet surface becomes exact steam.",
        ),
    ),
)
def define_water_surface() -> None:
    """Authored spatial metadata marker."""


(
    WATER_SURFACE_DECLARATION,
    WATER_SURFACE_RECIPE,
) = _declaration_and_recipe(define_water_surface)


@spatial_effect_definition(
    pack_id="content.srd_5_1_cc",
    content_id="spatial_effect.spell.web.burning",
    version=1,
    descriptor=_descriptor(
        display_name="Burning Web Fire",
        content_id="spatial_effect.spell.web.burning",
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ),
    provenance=_provenance("Web (Burning Cube)"),
    spatial_effect_definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.TURN_START,
        }),
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.DOUSE,
                action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
            ),
        ),
    ),
)
def define_burning_web_fire() -> None:
    """Authored spatial metadata marker."""


(
    BURNING_WEB_FIRE_DECLARATION,
    BURNING_WEB_FIRE_RECIPE,
) = _declaration_and_recipe(define_burning_web_fire)


@spatial_effect_definition(
    pack_id="content.neurodragon",
    content_id="spatial_effect.material.oil",
    version=1,
    descriptor=_descriptor(
        display_name="Oil Surface",
        content_id="spatial_effect.material.oil",
        layer=SpatialEffectLayer.GROUND_SURFACE,
        tags=("spatial_effect", "ground_surface", "environmental_material"),
    ),
    provenance=_environment_provenance("Oil Surface"),
    spatial_effect_definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.IGNITE,
                action=SpatialEffectTransitionAction.REPLACE_AFFECTED,
                replacement_recipe=FIRE_SURFACE_RECIPE,
            ),
        ),
    ),
    dependencies=(
        ContentDependency(
            relation=(
                ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT
            ),
            target_ref=FIRE_SURFACE_RECIPE.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Ignited oil transforms into the exact fire material.",
        ),
    ),
)
def define_oil_surface() -> None:
    """Authored spatial metadata marker."""


(
    OIL_SURFACE_DECLARATION,
    OIL_SURFACE_RECIPE,
) = _declaration_and_recipe(define_oil_surface)


@spatial_effect_definition(
    pack_id="content.neurodragon",
    content_id="spatial_effect.environment.spike_trap",
    version=1,
    descriptor=_descriptor(
        display_name="Spike Trap",
        content_id="spatial_effect.environment.spike_trap",
        layer=SpatialEffectLayer.GROUND_SURFACE,
        tags=("spatial_effect", "ground_surface", "environmental_hazard"),
    ),
    provenance=_environment_provenance("Spike Trap"),
    spatial_effect_definition=_definition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
        }),
    ),
)
def define_spike_trap_effect() -> None:
    """Authored spatial metadata marker."""


SPIKE_TRAP_EFFECT_DECLARATION = get_content_declaration(
    define_spike_trap_effect,
)
SPIKE_TRAP_EFFECT_RECIPE = ContentRecipe.create(
    ref=SPIKE_TRAP_EFFECT_DECLARATION.ref,
    parameters={},
)


@spatial_effect_definition(
    pack_id="content.srd_5_1_cc",
    content_id="spatial_effect.spell.web",
    version=1,
    descriptor=_descriptor(
        display_name="Web Surface",
        content_id="spatial_effect.spell.web",
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ),
    provenance=_provenance("Web"),
    spatial_effect_definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
            SpatialEffectTriggerKind.TURN_START,
        }),
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.IGNITE,
                action=SpatialEffectTransitionAction.REPLACE_AFFECTED,
                replacement_recipe=BURNING_WEB_FIRE_RECIPE,
            ),
        ),
    ),
    dependencies=(
        ContentDependency(
            relation=(
                ContentDependencyRelation.TRANSFORMS_TO_SPATIAL_EFFECT
            ),
            target_ref=BURNING_WEB_FIRE_RECIPE.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Each ignited Web cube becomes one round of burning fire.",
        ),
    ),
)
def define_web_surface() -> None:
    """Authored spatial metadata marker."""


(
    WEB_SURFACE_DECLARATION,
    WEB_SURFACE_RECIPE,
) = _declaration_and_recipe(define_web_surface)


@spatial_effect_definition(
    pack_id="content.srd_5_1_cc",
    content_id="spatial_effect.spell.spike_growth",
    version=1,
    descriptor=_descriptor(
        display_name="Spike Growth Surface",
        content_id="spatial_effect.spell.spike_growth",
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ),
    provenance=_provenance("Spike Growth"),
    spatial_effect_definition=_definition(
        layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
        }),
    ),
)
def define_spike_growth_surface() -> None:
    """Authored spatial metadata marker."""


@spatial_effect_definition(
    pack_id="content.srd_5_1_cc",
    content_id="spatial_effect.spell.ice_storm",
    version=1,
    descriptor=_descriptor(
        display_name="Ice Storm Surface",
        content_id="spatial_effect.spell.ice_storm",
        layer=SpatialEffectLayer.GROUND_SURFACE,
    ),
    provenance=_provenance("Ice Storm"),
    spatial_effect_definition=_GROUND_DEFINITION,
)
def define_ice_storm_surface() -> None:
    """Authored spatial metadata marker."""


(
    SPIKE_GROWTH_SURFACE_DECLARATION,
    SPIKE_GROWTH_SURFACE_RECIPE,
) = _declaration_and_recipe(define_spike_growth_surface)
(
    ICE_STORM_SURFACE_DECLARATION,
    ICE_STORM_SURFACE_RECIPE,
) = _declaration_and_recipe(define_ice_storm_surface)


def _cloud_definition(
    *,
    display_name: str,
    content_id: str,
    definition: SpatialEffectDefinition = _CLOUD_DEFINITION,
) -> Callable[[Callable[[], None]], Callable[[], None]]:
    return spatial_effect_definition(
        pack_id="content.srd_5_1_cc",
        content_id=content_id,
        version=1,
        descriptor=_descriptor(
            display_name=display_name,
            content_id=content_id,
            layer=SpatialEffectLayer.CLOUD,
        ),
        provenance=_provenance(display_name),
        spatial_effect_definition=definition,
    )


@_cloud_definition(
    display_name="Fog Cloud",
    content_id="spatial_effect.spell.fog_cloud",
    definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.CLOUD,
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.DISPERSE,
                minimum_intensity=(
                    SpatialEffectInteractionIntensity.MODERATE
                ),
                action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
            ),
        ),
    ),
)
def define_fog_cloud_effect() -> None:
    """Authored spatial metadata marker."""


@_cloud_definition(
    display_name="Cloudkill Cloud",
    content_id="spatial_effect.spell.cloudkill",
    definition=SpatialEffectDefinition(
        anchor_kind=SpatialEffectAnchorKind.INDEPENDENT_MOVABLE,
        layer=SpatialEffectLayer.CLOUD,
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
        first_per_turn_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.DISPERSE,
                minimum_intensity=SpatialEffectInteractionIntensity.STRONG,
                action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
            ),
        ),
    ),
)
def define_cloudkill_effect() -> None:
    """Authored spatial metadata marker."""


@_cloud_definition(
    display_name="Incendiary Cloud",
    content_id="spatial_effect.spell.incendiary_cloud",
    definition=_definition(
        anchor_kind=SpatialEffectAnchorKind.INDEPENDENT_MOVABLE,
        layer=SpatialEffectLayer.CLOUD,
        occupancy_policy=(
            SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING
        ),
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_END,
        }),
        first_per_turn_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_END,
        }),
    ),
)
def define_incendiary_cloud_effect() -> None:
    """Authored spatial metadata marker."""


@_cloud_definition(
    display_name="Stinking Cloud",
    content_id="spatial_effect.spell.stinking_cloud",
    definition=SpatialEffectDefinition(
        layer=SpatialEffectLayer.CLOUD,
        occupancy_policy=SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.TURN_START,
        }),
        transitions=(
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.DISPERSE,
                minimum_intensity=(
                    SpatialEffectInteractionIntensity.MODERATE
                ),
                action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
                delay_rounds=4,
            ),
            SpatialEffectTransitionDefinition(
                operation=SpatialEffectInteractionOperation.DISPERSE,
                minimum_intensity=SpatialEffectInteractionIntensity.STRONG,
                action=SpatialEffectTransitionAction.REMOVE_AFFECTED,
                delay_rounds=1,
            ),
        ),
    ),
)
def define_stinking_cloud_effect() -> None:
    """Authored spatial metadata marker."""


(
    FOG_CLOUD_DECLARATION,
    FOG_CLOUD_RECIPE,
) = _declaration_and_recipe(define_fog_cloud_effect)
(
    CLOUDKILL_CLOUD_DECLARATION,
    CLOUDKILL_CLOUD_RECIPE,
) = _declaration_and_recipe(define_cloudkill_effect)
(
    INCENDIARY_CLOUD_DECLARATION,
    INCENDIARY_CLOUD_RECIPE,
) = _declaration_and_recipe(define_incendiary_cloud_effect)
(
    STINKING_CLOUD_DECLARATION,
    STINKING_CLOUD_RECIPE,
) = _declaration_and_recipe(define_stinking_cloud_effect)


def _field_definition(
    *,
    display_name: str,
    content_id: str,
    definition: SpatialEffectDefinition = _FIELD_DEFINITION,
) -> Callable[[Callable[[], None]], Callable[[], None]]:
    return spatial_effect_definition(
        pack_id="content.srd_5_1_cc",
        content_id=content_id,
        version=1,
        descriptor=_descriptor(
            display_name=display_name,
            content_id=content_id,
            layer=SpatialEffectLayer.FIELD,
        ),
        provenance=_provenance(display_name),
        spatial_effect_definition=definition,
    )


@_field_definition(
    display_name="Entangle Field",
    content_id="spatial_effect.spell.entangle",
    definition=_definition(
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
        }),
    ),
)
def define_entangle_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Evard's Black Tentacles Field",
    content_id="spatial_effect.spell.evards_black_tentacles",
    definition=_definition(
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
        first_per_turn_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
    ),
)
def define_evards_black_tentacles_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Spirit Guardians Field",
    content_id="spatial_effect.spell.spirit_guardians",
    definition=_definition(
        anchor_kind=SpatialEffectAnchorKind.ENTITY,
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
            SpatialEffectTriggerKind.EFFECT_LEAVES_OCCUPANT,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
            SpatialEffectTriggerKind.TURN_START,
        }),
        first_per_turn_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
    ),
)
def define_spirit_guardians_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Guardian of Faith Field",
    content_id="spatial_effect.spell.guardian_of_faith",
    definition=_definition(
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        blocking_policy=SpatialEffectBlockingPolicy.ANCHOR,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
        }),
        first_per_turn_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
        }),
    ),
)
def define_guardian_of_faith_field() -> None:
    """Authored spatial metadata marker."""


@spatial_effect_definition(
    pack_id="content.srd_5_1_cc",
    content_id="spatial_effect.trait.leadership",
    version=1,
    descriptor=_descriptor(
        display_name="Leadership Field",
        content_id="spatial_effect.trait.leadership",
        layer=SpatialEffectLayer.FIELD,
        tags=("spatial_effect", "field", "trait", "srd"),
    ),
    provenance=_feature_provenance("Leadership"),
    spatial_effect_definition=_definition(
        anchor_kind=SpatialEffectAnchorKind.ENTITY,
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.EFFECT_ENTERS_OCCUPANT,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
        }),
    ),
)
def define_leadership_field() -> None:
    """Authored spatial metadata marker."""


@spatial_effect_definition(
    pack_id="content.srd_5_1_cc",
    content_id="spatial_effect.class_feature.draconic_presence",
    version=1,
    descriptor=_descriptor(
        display_name="Draconic Presence Field",
        content_id="spatial_effect.class_feature.draconic_presence",
        layer=SpatialEffectLayer.FIELD,
        tags=(
            "spatial_effect",
            "field",
            "class_feature",
            "sorcerer",
            "srd",
        ),
    ),
    provenance=_feature_provenance("Draconic Presence"),
    spatial_effect_definition=_definition(
        anchor_kind=SpatialEffectAnchorKind.ENTITY,
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.TURN_START,
        }),
    ),
)
def define_draconic_presence_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Darkness Field",
    content_id="spatial_effect.spell.darkness",
)
def define_darkness_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Daylight Field",
    content_id="spatial_effect.spell.daylight",
)
def define_daylight_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Insect Plague Field",
    content_id="spatial_effect.spell.insect_plague",
    definition=_definition(
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_END,
        }),
        first_per_turn_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.APPEAR,
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_END,
        }),
    ),
)
def define_insect_plague_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Sleet Storm Field",
    content_id="spatial_effect.spell.sleet_storm",
    definition=_definition(
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
        first_per_turn_trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
    ),
)
def define_sleet_storm_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Silence Field",
    content_id="spatial_effect.spell.silence",
    definition=_definition(
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.LEAVE,
        }),
    ),
)
def define_silence_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Gust of Wind Field",
    content_id="spatial_effect.spell.gust_of_wind",
    definition=_definition(
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        trigger_kinds=frozenset({
            SpatialEffectTriggerKind.ENTER,
            SpatialEffectTriggerKind.TURN_START,
        }),
    ),
)
def define_gust_of_wind_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Globe of Invulnerability Field",
    content_id="spatial_effect.spell.globe_of_invulnerability",
)
def define_globe_of_invulnerability_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Antimagic Field",
    content_id="spatial_effect.spell.antimagic_field",
    definition=_definition(
        anchor_kind=SpatialEffectAnchorKind.ENTITY,
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
    ),
)
def define_antimagic_field() -> None:
    """Authored spatial metadata marker."""


@_field_definition(
    display_name="Continual Flame Field",
    content_id="spatial_effect.spell.continual_flame",
    definition=_WORLD_OBJECT_FIELD_DEFINITION,
)
def define_continual_flame_field() -> None:
    """Authored spatial metadata marker."""


(
    ENTANGLE_FIELD_DECLARATION,
    ENTANGLE_FIELD_RECIPE,
) = _declaration_and_recipe(define_entangle_field)
(
    EVARDS_BLACK_TENTACLES_FIELD_DECLARATION,
    EVARDS_BLACK_TENTACLES_FIELD_RECIPE,
) = _declaration_and_recipe(define_evards_black_tentacles_field)
(
    SPIRIT_GUARDIANS_FIELD_DECLARATION,
    SPIRIT_GUARDIANS_FIELD_RECIPE,
) = _declaration_and_recipe(define_spirit_guardians_field)
(
    GUARDIAN_OF_FAITH_FIELD_DECLARATION,
    GUARDIAN_OF_FAITH_FIELD_RECIPE,
) = _declaration_and_recipe(define_guardian_of_faith_field)
(
    DRACONIC_PRESENCE_FIELD_DECLARATION,
    DRACONIC_PRESENCE_FIELD_RECIPE,
) = _declaration_and_recipe(define_draconic_presence_field)
(
    LEADERSHIP_FIELD_DECLARATION,
    LEADERSHIP_FIELD_RECIPE,
) = _declaration_and_recipe(define_leadership_field)
(
    DARKNESS_FIELD_DECLARATION,
    DARKNESS_FIELD_RECIPE,
) = _declaration_and_recipe(define_darkness_field)
(
    DAYLIGHT_FIELD_DECLARATION,
    DAYLIGHT_FIELD_RECIPE,
) = _declaration_and_recipe(define_daylight_field)
(
    INSECT_PLAGUE_FIELD_DECLARATION,
    INSECT_PLAGUE_FIELD_RECIPE,
) = _declaration_and_recipe(define_insect_plague_field)
(
    SLEET_STORM_FIELD_DECLARATION,
    SLEET_STORM_FIELD_RECIPE,
) = _declaration_and_recipe(define_sleet_storm_field)
(
    SILENCE_FIELD_DECLARATION,
    SILENCE_FIELD_RECIPE,
) = _declaration_and_recipe(define_silence_field)
(
    GUST_OF_WIND_FIELD_DECLARATION,
    GUST_OF_WIND_FIELD_RECIPE,
) = _declaration_and_recipe(define_gust_of_wind_field)
(
    GLOBE_OF_INVULNERABILITY_FIELD_DECLARATION,
    GLOBE_OF_INVULNERABILITY_FIELD_RECIPE,
) = _declaration_and_recipe(define_globe_of_invulnerability_field)
(
    ANTIMAGIC_FIELD_DECLARATION,
    ANTIMAGIC_FIELD_RECIPE,
) = _declaration_and_recipe(define_antimagic_field)
(
    CONTINUAL_FLAME_FIELD_DECLARATION,
    CONTINUAL_FLAME_FIELD_RECIPE,
) = _declaration_and_recipe(define_continual_flame_field)

BUILT_IN_SPATIAL_EFFECT_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    GREASE_SURFACE_DECLARATION,
    OIL_SURFACE_DECLARATION,
    FIRE_SURFACE_DECLARATION,
    WATER_SURFACE_DECLARATION,
    ICE_SURFACE_DECLARATION,
    ELECTRIFIED_WATER_DECLARATION,
    STEAM_CLOUD_DECLARATION,
    SPIKE_TRAP_EFFECT_DECLARATION,
    BURNING_WEB_FIRE_DECLARATION,
    WEB_SURFACE_DECLARATION,
    SPIKE_GROWTH_SURFACE_DECLARATION,
    ICE_STORM_SURFACE_DECLARATION,
    FOG_CLOUD_DECLARATION,
    CLOUDKILL_CLOUD_DECLARATION,
    INCENDIARY_CLOUD_DECLARATION,
    STINKING_CLOUD_DECLARATION,
    ENTANGLE_FIELD_DECLARATION,
    EVARDS_BLACK_TENTACLES_FIELD_DECLARATION,
    SPIRIT_GUARDIANS_FIELD_DECLARATION,
    GUARDIAN_OF_FAITH_FIELD_DECLARATION,
    DRACONIC_PRESENCE_FIELD_DECLARATION,
    LEADERSHIP_FIELD_DECLARATION,
    DARKNESS_FIELD_DECLARATION,
    DAYLIGHT_FIELD_DECLARATION,
    INSECT_PLAGUE_FIELD_DECLARATION,
    SLEET_STORM_FIELD_DECLARATION,
    SILENCE_FIELD_DECLARATION,
    GUST_OF_WIND_FIELD_DECLARATION,
    GLOBE_OF_INVULNERABILITY_FIELD_DECLARATION,
    ANTIMAGIC_FIELD_DECLARATION,
    CONTINUAL_FLAME_FIELD_DECLARATION,
)


__all__ = [
    "ANTIMAGIC_FIELD_RECIPE",
    "BURNING_WEB_FIRE_RECIPE",
    "CONTINUAL_FLAME_FIELD_RECIPE",
    "DARKNESS_FIELD_RECIPE",
    "DAYLIGHT_FIELD_RECIPE",
    "DRACONIC_PRESENCE_FIELD_RECIPE",
    "ENTANGLE_FIELD_RECIPE",
    "EVARDS_BLACK_TENTACLES_FIELD_RECIPE",
    "CLOUDKILL_CLOUD_RECIPE",
    "ELECTRIFIED_WATER_RECIPE",
    "FIRE_SURFACE_RECIPE",
    "FOG_CLOUD_RECIPE",
    "GLOBE_OF_INVULNERABILITY_FIELD_RECIPE",
    "GREASE_SURFACE_RECIPE",
    "GUST_OF_WIND_FIELD_RECIPE",
    "GUARDIAN_OF_FAITH_FIELD_RECIPE",
    "ICE_STORM_SURFACE_RECIPE",
    "ICE_SURFACE_RECIPE",
    "INSECT_PLAGUE_FIELD_RECIPE",
    "INCENDIARY_CLOUD_RECIPE",
    "LEADERSHIP_FIELD_RECIPE",
    "OIL_SURFACE_RECIPE",
    "SILENCE_FIELD_RECIPE",
    "SLEET_STORM_FIELD_RECIPE",
    "SPIRIT_GUARDIANS_FIELD_RECIPE",
    "SPIKE_GROWTH_SURFACE_RECIPE",
    "SPIKE_TRAP_EFFECT_DECLARATION",
    "STINKING_CLOUD_RECIPE",
    "STEAM_CLOUD_RECIPE",
    "WATER_SURFACE_RECIPE",
    "WEB_SURFACE_RECIPE",
    "BUILT_IN_SPATIAL_EFFECT_DECLARATIONS",
    "SPIKE_TRAP_EFFECT_RECIPE",
]
