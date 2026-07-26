"""Generate the standalone TypeScript SDK contract from backend Pydantic models."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any, Dict

from annotated_types import Ge, Gt, Le, Lt, MaxLen, MinLen
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from devtools.generate_event_contract import (
    SERVER_MANIFEST_PATH,
    ContractBuilder,
    build_manifest as build_event_manifest,
    concrete_event_models,
    import_dnd_modules,
    qualified_name,
    typescript_literal,
    typescript_type,
    write_or_check,
)
from dnd.core.events import Event
from dnd.core import combat_log
from server import (
    api_models,
    content_catalog,
    game_gateway_models,
    game_summary_store,
)
from server.game_directory import contracts as game_directory_contracts
from server.event_stream import EvictedPayload
from server.directory_event_stream import DirectoryStreamHeartbeat, DirectoryStreamSync
from server.agent_protocol.objective_diagnostics import (
    ObjectiveDiagnosticsBootstrap,
    ObjectiveDiagnosticsSync,
    SubjectiveRenderParityDiagnosticsResponse,
)
from server.objective_replay import (
    OBJECTIVE_REPLAY_CONTRACT_HASH,
    OBJECTIVE_REPLAY_CONTRACT_VERSION,
    ObjectiveReplayBundle,
)
from server import player_replication_contract
from server.player_replication_contract import (
    PLAYER_REPLICATION_CONTRACT_HASH,
    PLAYER_REPLICATION_CONTRACT_VERSION,
    SubjectiveCombatLogDelivery,
    SubjectiveCombatLogFramesResponse,
    SubjectiveFrameDelivery,
    SubjectiveFramesResponse,
    SubjectivePresentationCue,
    SubjectiveReplicationBootstrap,
    SubjectiveSyncDelivery,
    SubjectiveStreamDelivery,
    SubjectiveWorldPatch,
)
from server.player_replay import (
    PLAYER_REPLAY_CONTRACT_HASH,
    PLAYER_REPLAY_CONTRACT_VERSION,
    SubjectivePlayerReplayBundle,
    SubjectiveReplayDelivery,
)
from server.replicated_world import ReplicatedWorld
from server.timeline_contracts import (
    CombatLogFrame,
    CombatLogFramesResponse,
    GameEventFramesResponse,
    TIMELINE_CONTRACT_HASH,
    TIMELINE_CONTRACT_VERSION,
    WireEvent,
)


SDK_ROOT = ROOT / "sdk" / "typescript"
SDK_MANIFEST_PATH = SDK_ROOT / "src" / "generated" / "contract.generated.json"
SDK_TYPES_PATH = SDK_ROOT / "src" / "generated" / "contracts.generated.ts"
STREAM_MODELS = (
    EvictedPayload,
    DirectoryStreamSync,
    DirectoryStreamHeartbeat,
)
OBJECTIVE_DIAGNOSTICS_MODELS = (
    ObjectiveDiagnosticsBootstrap,
    ObjectiveDiagnosticsSync,
    SubjectiveRenderParityDiagnosticsResponse,
    GameEventFramesResponse,
    CombatLogFramesResponse,
    ReplicatedWorld,
)
PLAYER_REPLICATION_MODELS = (
    SubjectiveReplicationBootstrap,
    SubjectiveFramesResponse,
    SubjectiveCombatLogFramesResponse,
    SubjectiveSyncDelivery,
    SubjectiveFrameDelivery,
    SubjectiveCombatLogDelivery,
)
REPLAY_MODELS = (
    ObjectiveReplayBundle,
    SubjectivePlayerReplayBundle,
)
PLAYER_REPLICATION_ALIASES = {
    "SubjectiveWorldPatch": SubjectiveWorldPatch,
    "SubjectivePresentationCue": SubjectivePresentationCue,
    "SubjectiveStreamDelivery": SubjectiveStreamDelivery,
    "SubjectiveReplayDelivery": SubjectiveReplayDelivery,
}
TYPESCRIPT_NAME_OVERRIDES = {
    # Keep the cold objective snapshot unambiguously separate from the
    # canonical subjective world seed.
    qualified_name(ReplicatedWorld): "ObjectiveReplicatedWorld",
    # These broad timeline DTOs belong only to the separate objective
    # diagnostics surface.  Keep their generated names distinct from the
    # deliberately narrow player combat-log projection.
    qualified_name(CombatLogFrame): "TimelineCombatLogFrame",
    qualified_name(CombatLogFramesResponse): "TimelineCombatLogFramesResponse",
    qualified_name(player_replication_contract.AttackOutcome): "SubjectiveAttackOutcome",
}


class SdkContractBuilder(ContractBuilder):
    """SDK descriptor builder that preserves runtime-relevant field constraints."""

    def describe(self, annotation: Any) -> Dict[str, Any]:
        """Keep JSON integers distinct from unconstrained finite numbers."""
        if annotation is int:
            return {"kind": "integer"}
        return super().describe(annotation)

    def add_model(self, model: type[BaseModel]) -> None:
        """Collect a model, then attach its Pydantic field bounds to descriptors."""
        if model in self.models:
            return
        super().add_model(model)
        fields = self.models[model]["fields"]
        for name, field in model.model_fields.items():
            descriptor = fields.get(name)
            if descriptor is None or field.exclude is True:
                continue
            self._apply_field_constraints(descriptor, field.metadata)

    @staticmethod
    def _apply_field_constraints(
        descriptor: Dict[str, Any],
        metadata: list[Any],
    ) -> None:
        """Project the closed constraint vocabulary enforced by current SDK models."""
        if descriptor.get("kind") == "union":
            for member in descriptor["items"]:
                if member.get("kind") != "null":
                    SdkContractBuilder._apply_field_constraints(member, metadata)
            return

        kind = descriptor.get("kind")
        for constraint in metadata:
            if isinstance(constraint, Ge) and kind in {"integer", "number"}:
                descriptor["minimum"] = constraint.ge
            elif isinstance(constraint, Gt) and kind in {"integer", "number"}:
                descriptor["exclusive_minimum"] = constraint.gt
            elif isinstance(constraint, Le) and kind in {"integer", "number"}:
                descriptor["maximum"] = constraint.le
            elif isinstance(constraint, Lt) and kind in {"integer", "number"}:
                descriptor["exclusive_maximum"] = constraint.lt
            elif isinstance(constraint, MinLen) and kind in {"string", "array", "record"}:
                descriptor["min_length"] = constraint.min_length
            elif isinstance(constraint, MaxLen) and kind in {"string", "array", "record"}:
                descriptor["max_length"] = constraint.max_length

def api_model_roots() -> list[type[BaseModel]]:
    """Return every public model declared by `server.api_models`."""
    return sorted(
        (
            value
            for value in vars(api_models).values()
            if inspect.isclass(value)
            and issubclass(value, BaseModel)
            and value.__module__ == api_models.__name__
        ),
        key=qualified_name,
    )


def declared_model_roots(module: Any) -> list[type[BaseModel]]:
    """Return Pydantic models owned by one backend module."""
    return sorted(
        (
            value
            for value in vars(module).values()
            if inspect.isclass(value)
            and issubclass(value, BaseModel)
            and value.__module__ == module.__name__
        ),
        key=qualified_name,
    )


def build_sdk_manifest() -> Dict[str, Any]:
    """Build one recursive manifest for REST, SSE, logs, and engine events."""
    import_dnd_modules()
    event_manifest = build_event_manifest()
    builder = SdkContractBuilder()
    roots = [
        *api_model_roots(),
        *declared_model_roots(content_catalog),
        *declared_model_roots(game_gateway_models),
        *declared_model_roots(game_summary_store),
        *declared_model_roots(game_directory_contracts),
        *declared_model_roots(combat_log),
        *PLAYER_REPLICATION_MODELS,
        *REPLAY_MODELS,
        *STREAM_MODELS,
        *OBJECTIVE_DIAGNOSTICS_MODELS,
    ]
    for model in roots:
        builder.add_model(model)
    for model in concrete_event_models():
        builder.add_model(model)

    aliases = {
        name: builder.describe(annotation)
        for name, annotation in PLAYER_REPLICATION_ALIASES.items()
    }

    # Alias collection can discover additional transitive models and enums, so
    # overrides must be applied after every alias has been described.
    for model, descriptor in builder.models.items():
        override = TYPESCRIPT_NAME_OVERRIDES.get(qualified_name(model))
        if override is not None:
            descriptor["typescript"] = override
    for enum, descriptor in builder.enums.items():
        override = TYPESCRIPT_NAME_OVERRIDES.get(qualified_name(enum))
        if override is not None:
            descriptor["typescript"] = override

    type_names: Dict[str, str] = {}
    for model, descriptor in builder.models.items():
        name = descriptor["typescript"]
        previous = type_names.setdefault(name, qualified_name(model))
        if previous != qualified_name(model):
            raise RuntimeError(
                f"TypeScript model name {name!r} is ambiguous: "
                f"{previous!r} and {qualified_name(model)!r}."
            )
    for enum, descriptor in builder.enums.items():
        name = descriptor["typescript"]
        previous = type_names.setdefault(name, qualified_name(enum))
        if previous != qualified_name(enum):
            raise RuntimeError(
                f"TypeScript contract name {name!r} is ambiguous: "
                f"{previous!r} and {qualified_name(enum)!r}."
            )
    for name in aliases:
        previous = type_names.setdefault(name, f"alias:{name}")
        if previous != f"alias:{name}":
            raise RuntimeError(
                f"TypeScript alias name {name!r} conflicts with {previous!r}."
            )

    models: Dict[str, Any] = {}
    for model in sorted(builder.models, key=qualified_name):
        row = dict(builder.models[model])
        row["root_model"] = bool(getattr(model, "__pydantic_root_model__", False))
        models[qualified_name(model)] = row

    manifest: Dict[str, Any] = {
        "contract_version": 1,
        "player_replication_contract_version": PLAYER_REPLICATION_CONTRACT_VERSION,
        "player_replication_contract_hash": PLAYER_REPLICATION_CONTRACT_HASH,
        "objective_replay_contract_version": OBJECTIVE_REPLAY_CONTRACT_VERSION,
        "objective_replay_contract_hash": OBJECTIVE_REPLAY_CONTRACT_HASH,
        "player_replay_contract_version": PLAYER_REPLAY_CONTRACT_VERSION,
        "player_replay_contract_hash": PLAYER_REPLAY_CONTRACT_HASH,
        "event_contract_version": event_manifest["contract_version"],
        "event_contract_hash": event_manifest["contract_hash"],
        "event_classes": event_manifest["event_classes"],
        "models": models,
        "enums": {
            qualified_name(enum): builder.enums[enum]
            for enum in sorted(builder.enums, key=qualified_name)
        },
        "aliases": aliases,
        "roots": [qualified_name(model) for model in roots],
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["contract_hash"] = hashlib.sha256(canonical).hexdigest()
    return manifest


def sdk_typescript_type(descriptor: Dict[str, Any], manifest: Dict[str, Any]) -> str:
    """Render a descriptor, preserving concrete event polymorphism."""
    kind = descriptor.get("kind")
    if kind == "integer":
        return "number"
    if kind == "model" and descriptor.get("ref") in {
        qualified_name(Event),
        qualified_name(WireEvent),
    }:
        return "ServerEvent"
    if kind == "array":
        return f"Array<{sdk_typescript_type(descriptor['items'], manifest)}>"
    if kind == "record":
        return f"Record<string, {sdk_typescript_type(descriptor['values'], manifest)}>"
    if kind == "tuple":
        return "[" + ", ".join(
            sdk_typescript_type(item, manifest)
            for item in descriptor["items"]
        ) + "]"
    if kind == "union":
        rendered = list(dict.fromkeys(
            sdk_typescript_type(item, manifest)
            for item in descriptor["items"]
        ))
        return " | ".join(rendered) if rendered else "never"
    return typescript_type(descriptor, manifest)


def render_typescript(manifest: Dict[str, Any]) -> str:
    """Render exact SDK models and runtime descriptors as TypeScript."""
    lines = [
        "/* Generated by dnd_engine/devtools/generate_typescript_sdk.py. Do not edit. */",
        "",
        f"export const PLAYER_REPLICATION_CONTRACT_VERSION = {manifest['player_replication_contract_version']} as const;",
        f"export const PLAYER_REPLICATION_CONTRACT_HASH = {json.dumps(manifest['player_replication_contract_hash'])} as const;",
        f"export const OBJECTIVE_REPLAY_CONTRACT_VERSION = {manifest['objective_replay_contract_version']} as const;",
        f"export const OBJECTIVE_REPLAY_CONTRACT_HASH = {json.dumps(manifest['objective_replay_contract_hash'])} as const;",
        f"export const PLAYER_REPLAY_CONTRACT_VERSION = {manifest['player_replay_contract_version']} as const;",
        f"export const PLAYER_REPLAY_CONTRACT_HASH = {json.dumps(manifest['player_replay_contract_hash'])} as const;",
        f"export const TIMELINE_CONTRACT_VERSION = {TIMELINE_CONTRACT_VERSION} as const;",
        f"export const TIMELINE_CONTRACT_HASH = {json.dumps(TIMELINE_CONTRACT_HASH)} as const;",
        f"export const SDK_CONTRACT_VERSION = {manifest['contract_version']} as const;",
        f"export const SDK_CONTRACT_HASH = {json.dumps(manifest['contract_hash'])} as const;",
        f"export const EVENT_CONTRACT_VERSION = {manifest['event_contract_version']} as const;",
        f"export const EVENT_CONTRACT_HASH = {json.dumps(manifest['event_contract_hash'])} as const;",
        "",
        "export type JsonPrimitive = null | boolean | number | string;",
        "export type JsonValue = JsonPrimitive | ReadonlyArray<JsonValue> | { readonly [key: string]: JsonValue };",
        "export type ContractDescriptor =",
        "  | { readonly kind: 'json'; readonly python?: string }",
        "  | { readonly kind: 'null' | 'boolean' }",
        "  | { readonly kind: 'string'; readonly min_length?: number; readonly max_length?: number }",
        "  | { readonly kind: 'number' | 'integer'; readonly minimum?: number; readonly exclusive_minimum?: number; readonly maximum?: number; readonly exclusive_maximum?: number }",
        "  | { readonly kind: 'literal'; readonly value: JsonValue }",
        "  | { readonly kind: 'enum' | 'model'; readonly ref: string }",
        "  | { readonly kind: 'array'; readonly items: ContractDescriptor; readonly min_length?: number; readonly max_length?: number }",
        "  | { readonly kind: 'record'; readonly values: ContractDescriptor; readonly min_length?: number; readonly max_length?: number }",
        "  | { readonly kind: 'tuple' | 'union'; readonly items: ReadonlyArray<ContractDescriptor> };",
        "export interface ContractModelDescriptor {",
        "  readonly python: string;",
        "  readonly typescript: string;",
        "  readonly root_model: boolean;",
        "  readonly fields: Readonly<Record<string, ContractDescriptor>>;",
        "}",
        "export interface ContractEnumDescriptor {",
        "  readonly python: string;",
        "  readonly typescript: string;",
        "  readonly values: ReadonlyArray<JsonValue>;",
        "}",
        "",
    ]

    for enum in manifest["enums"].values():
        values = " | ".join(typescript_literal(value) for value in enum["values"])
        lines.append(f"export type {enum['typescript']} = {values or 'never'};")
    lines.append("")

    event_classes = manifest["event_classes"]
    for model_path, model in manifest["models"].items():
        fields = model["fields"]
        if model_path == qualified_name(WireEvent):
            lines.append(f"export type {model['typescript']} = ServerEvent;")
            lines.append("")
            continue
        if model["root_model"]:
            root = fields["root"]
            lines.append(
                f"export type {model['typescript']} = "
                f"{sdk_typescript_type(root, manifest)};"
            )
            lines.append("")
            continue

        is_event = model_path in event_classes
        lines.append(f"export interface {model['typescript']} {{")
        if is_event:
            lines.append(f"  readonly wire_type: {json.dumps(model_path)};")
        for name, descriptor in fields.items():
            if is_event and name == "event_type":
                values = event_classes[model_path]["event_types"]
                rendered = " | ".join(json.dumps(value) for value in values)
                lines.append(f"  readonly event_type: {rendered};")
                continue
            lines.append(
                f"  readonly {name}: {sdk_typescript_type(descriptor, manifest)};"
            )
        lines.append("}")
        lines.append("")

    for name, descriptor in manifest["aliases"].items():
        lines.append(
            f"export type {name} = {sdk_typescript_type(descriptor, manifest)};"
        )
    lines.append("")

    concrete_events = [
        row["typescript"]
        for path, row in event_classes.items()
        if path != qualified_name(Event)
    ]
    lines.append("export type ConcreteServerEvent =")
    for name in concrete_events:
        lines.append(f"  | {name}")
    lines[-1] = lines[-1] + ";"
    lines.append("export type ServerEvent = ConcreteServerEvent | EngineEvent;")
    lines.append("")
    lines.append("export interface EventByWireType {")
    for path, row in event_classes.items():
        lines.append(f"  readonly {json.dumps(path)}: {row['typescript']};")
    lines.append("}")
    lines.append("")

    lines.append("export interface SdkModelByName {")
    for model in manifest["models"].values():
        lines.append(f"  readonly {json.dumps(model['typescript'])}: {model['typescript']};")
    lines.append("}")
    lines.append("export type SdkModelName = keyof SdkModelByName;")
    lines.append("")
    lines.append("export interface SdkAliasByName {")
    for name in manifest["aliases"]:
        lines.append(f"  readonly {json.dumps(name)}: {name};")
    lines.append("}")
    lines.append("export type SdkAliasName = keyof SdkAliasByName;")
    lines.append("")
    lines.append(
        "export const SDK_MODEL_DESCRIPTORS: Readonly<Record<string, ContractModelDescriptor>> = "
        + json.dumps(manifest["models"], sort_keys=True, separators=(",", ":"))
        + ";"
    )
    lines.append(
        "export const SDK_ENUM_DESCRIPTORS: Readonly<Record<string, ContractEnumDescriptor>> = "
        + json.dumps(manifest["enums"], sort_keys=True, separators=(",", ":"))
        + ";"
    )
    lines.append(
        "export const SDK_ALIAS_DESCRIPTORS: Readonly<Record<SdkAliasName, ContractDescriptor>> = "
        + json.dumps(manifest["aliases"], sort_keys=True, separators=(",", ":"))
        + ";"
    )
    paths_by_name = {
        model["typescript"]: path
        for path, model in manifest["models"].items()
    }
    lines.append(
        "export const SDK_MODEL_PATHS_BY_NAME: Readonly<Record<SdkModelName, string>> = "
        + json.dumps(paths_by_name, sort_keys=True, separators=(",", ":"))
        + ";"
    )
    lines.append(
        "export const SDK_EVENT_CLASSES: Readonly<Record<string, { readonly model: string; readonly typescript: string; readonly event_types: ReadonlyArray<string> }>> = "
        + json.dumps(manifest["event_classes"], sort_keys=True, separators=(",", ":"))
        + ";"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Write or verify all generated backend and TypeScript contracts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    event_manifest = build_event_manifest()
    event_text = json.dumps(event_manifest, indent=2, sort_keys=True) + "\n"
    write_or_check(SERVER_MANIFEST_PATH, event_text, args.check)

    sdk_manifest = build_sdk_manifest()
    sdk_text = json.dumps(sdk_manifest, indent=2, sort_keys=True) + "\n"
    write_or_check(SDK_MANIFEST_PATH, sdk_text, args.check)
    write_or_check(SDK_TYPES_PATH, render_typescript(sdk_manifest), args.check)


if __name__ == "__main__":
    main()
