"""Closed migrations for retained direct-Codex artifact payloads."""

from __future__ import annotations


_LEGACY_INFORMATION_EFFECT_TYPES: dict[tuple[str, str], tuple[str, str]] = {
    (
        "reveal_frontier",
        "selected_target.observation_frontier",
    ): ("selected_target", "frontier"),
    (
        "reveal_frontier",
        "selected_object.far_side",
    ): ("selected_object", "frontier"),
}


_LEGACY_TOPOLOGY_EFFECT_TYPES: dict[tuple[str, str], tuple[str, str, str]] = {
    ("open", "selected_object"): ("guaranteed", "selected_object", "target"),
    ("close", "selected_object"): ("guaranteed", "selected_object", "target"),
    (
        "deactivate_hazard",
        "selected_object.linked_hazard_region",
    ): ("guaranteed", "selected_object", "hazard_region"),
}


def migrate_legacy_epoch_semantics(value: object) -> object:
    """Reconstruct typed locations for known pre-location artifact semantics."""
    if not isinstance(value, dict):
        return value
    affordances = value.get("affordances")
    if not isinstance(affordances, dict):
        return value
    semantic_catalog = affordances.get("semantic_catalog")
    if not isinstance(semantic_catalog, dict):
        return value

    migrated_catalog: dict[str, object] = {}
    catalog_changed = False
    for reference, raw_semantics in semantic_catalog.items():
        if not isinstance(raw_semantics, dict):
            migrated_catalog[reference] = raw_semantics
            continue
        migrated_semantics = raw_semantics
        raw_information_effects = raw_semantics.get("information_effects")
        if isinstance(raw_information_effects, list):
            migrated_information_effects: list[object] = []
            information_changed = False
            for raw_effect in raw_information_effects:
                if not isinstance(raw_effect, dict):
                    migrated_information_effects.append(raw_effect)
                    continue
                if "anchor" in raw_effect or "scope" in raw_effect:
                    migrated_information_effects.append(raw_effect)
                    continue
                effect_type = _LEGACY_INFORMATION_EFFECT_TYPES.get(
                    (
                        str(raw_effect.get("operation")),
                        str(raw_effect.get("scope_ref")),
                    )
                )
                if effect_type is None:
                    migrated_information_effects.append(raw_effect)
                    continue
                anchor, scope = effect_type
                migrated_information_effects.append({
                    **raw_effect,
                    "anchor": anchor,
                    "scope": scope,
                })
                information_changed = True
            if information_changed:
                migrated_semantics = {
                    **migrated_semantics,
                    "information_effects": migrated_information_effects,
                }

        raw_topology_effects = raw_semantics.get("topology_effects")
        if isinstance(raw_topology_effects, list):
            migrated_topology_effects: list[object] = []
            topology_changed = False
            for raw_effect in raw_topology_effects:
                if not isinstance(raw_effect, dict):
                    migrated_topology_effects.append(raw_effect)
                    continue
                if any(
                    field in raw_effect
                    for field in ("certainty", "anchor", "scope")
                ):
                    migrated_topology_effects.append(raw_effect)
                    continue
                effect_type = _LEGACY_TOPOLOGY_EFFECT_TYPES.get(
                    (
                        str(raw_effect.get("operation")),
                        str(raw_effect.get("subject_ref")),
                    )
                )
                if effect_type is None:
                    migrated_topology_effects.append(raw_effect)
                    continue
                certainty, anchor, scope = effect_type
                migrated_topology_effects.append({
                    **raw_effect,
                    "certainty": certainty,
                    "anchor": anchor,
                    "scope": scope,
                })
                topology_changed = True
            if topology_changed:
                migrated_semantics = {
                    **migrated_semantics,
                    "topology_effects": migrated_topology_effects,
                }

        migrated_catalog[reference] = migrated_semantics
        catalog_changed = catalog_changed or migrated_semantics is not raw_semantics

    if not catalog_changed:
        return value
    return {
        **value,
        "affordances": {
            **affordances,
            "semantic_catalog": migrated_catalog,
        },
    }


def migrate_legacy_snapshot_semantics(value: object) -> object:
    """Migrate a retained snapshot without mutating caller data."""
    if not isinstance(value, dict):
        return value
    current_epoch = value.get("current_epoch")
    migrated_epoch = migrate_legacy_epoch_semantics(current_epoch)
    if migrated_epoch is current_epoch:
        return value
    return {**value, "current_epoch": migrated_epoch}


def migrate_legacy_frame_semantics(value: object) -> object:
    """Migrate frame epochs at ordinary and replacement artifact boundaries."""
    if not isinstance(value, dict):
        return value
    migrated = value
    decision_epoch = value.get("decision_epoch")
    migrated_epoch = migrate_legacy_epoch_semantics(decision_epoch)
    if migrated_epoch is not decision_epoch:
        migrated = {**migrated, "decision_epoch": migrated_epoch}

    state_replacement = value.get("state_replacement")
    migrated_replacement = migrate_legacy_snapshot_semantics(state_replacement)
    if migrated_replacement is not state_replacement:
        migrated = {**migrated, "state_replacement": migrated_replacement}
    return migrated
