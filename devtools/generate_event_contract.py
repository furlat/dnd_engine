"""Generate the exhaustive engine-event wire contract for Python and TypeScript."""

from __future__ import annotations

import argparse
import collections.abc
import hashlib
import importlib
import json
import pkgutil
import sys
import types
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Dict, ForwardRef, Literal, Set, Tuple, Union, cast, get_args, get_origin
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dnd
from pydantic import BaseModel, JsonValue
from pydantic_core import PydanticUndefined

from dnd.core.events import Event, EventType


SERVER_MANIFEST_PATH = ROOT / "server" / "event_contract.generated.json"


def import_dnd_modules() -> None:
    """Import every engine module so all concrete Event subclasses are known."""
    for module in pkgutil.walk_packages(dnd.__path__, f"{dnd.__name__}."):
        importlib.import_module(module.name)


def descendants(model: type[BaseModel]) -> Set[type[BaseModel]]:
    """Return all recursively declared Pydantic subclasses."""
    found: Set[type[BaseModel]] = set()
    pending = list(model.__subclasses__())
    while pending:
        child = pending.pop()
        if child in found:
            continue
        found.add(child)
        pending.extend(child.__subclasses__())
    return found


def qualified_name(value: type[Any]) -> str:
    """Return a stable Python class identifier for the wire discriminator."""
    return f"{value.__module__}.{value.__qualname__}"


def serialized_annotations(model: type[BaseModel]) -> Dict[str, Any]:
    """Return declared and computed fields included by a JSON-mode model dump."""
    annotations = {
        name: field.annotation
        for name, field in model.model_fields.items()
        if field.exclude is not True
    }
    annotations.update({
        name: field.return_type
        for name, field in model.model_computed_fields.items()
    })
    return annotations


def model_typescript_name(model: type[BaseModel]) -> str:
    """Return the generated TypeScript interface name for a Pydantic model."""
    return "EngineEvent" if model is Event else model.__name__


def literal_descriptor(value: Any) -> Dict[str, Any]:
    """Describe one JSON literal."""
    if isinstance(value, Enum):
        value = value.value
    return {"kind": "literal", "value": value}


class ContractBuilder:
    """Collect recursive wire models and emit runtime/type descriptors."""

    def __init__(self) -> None:
        self.models: Dict[type[BaseModel], Dict[str, Any]] = {}
        self.enums: Dict[type[Enum], Dict[str, Any]] = {}
        model_candidates = {BaseModel, *descendants(BaseModel)}
        self.models_by_name: Dict[str, type[BaseModel]] = {}
        duplicate_names: Set[str] = set()
        for model in model_candidates:
            if model.__name__ in self.models_by_name:
                duplicate_names.add(model.__name__)
            else:
                self.models_by_name[model.__name__] = model
        for name in duplicate_names:
            self.models_by_name.pop(name, None)

    def describe(self, annotation: Any) -> Dict[str, Any]:
        """Convert a resolved Python annotation into a JSON wire descriptor."""
        if annotation is Any or annotation is JsonValue:
            return {"kind": "json"}
        if annotation is None or annotation is type(None):
            return {"kind": "null"}
        if annotation is str or annotation is UUID or annotation is datetime or annotation is date:
            return {"kind": "string"}
        if annotation is bool:
            return {"kind": "boolean"}
        if annotation in {int, float}:
            return {"kind": "number"}
        if isinstance(annotation, ForwardRef):
            model = self.models_by_name.get(annotation.__forward_arg__)
            if model is not None:
                self.add_model(model)
                return {"kind": "model", "ref": qualified_name(model)}
            return {"kind": "json", "python": annotation.__forward_arg__}
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            self.enums.setdefault(annotation, {
                "python": qualified_name(annotation),
                "typescript": annotation.__name__,
                "values": [member.value for member in annotation],
            })
            return {"kind": "enum", "ref": qualified_name(annotation)}
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            self.add_model(annotation)
            return {"kind": "model", "ref": qualified_name(annotation)}

        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin is Annotated:
            return self.describe(args[0] if args else Any)
        if origin is Literal:
            return {"kind": "union", "items": [literal_descriptor(value) for value in args]}
        if origin in {Union, types.UnionType}:
            return {"kind": "union", "items": [self.describe(item) for item in args]}
        if origin in {list, set, frozenset, collections.abc.Sequence, collections.abc.Set}:
            return {"kind": "array", "items": self.describe(args[0] if args else Any)}
        if origin in {dict, Dict, collections.abc.Mapping}:
            return {"kind": "record", "values": self.describe(args[1] if len(args) > 1 else Any)}
        if origin in {tuple, Tuple}:
            if len(args) == 2 and args[1] is Ellipsis:
                return {"kind": "array", "items": self.describe(args[0])}
            return {"kind": "tuple", "items": [self.describe(item) for item in args]}
        if origin in {collections.abc.Callable}:
            return {"kind": "json", "python": repr(annotation)}
        return {"kind": "json", "python": repr(annotation)}

    def add_model(self, model: type[BaseModel]) -> None:
        """Add a model and recursively collect every referenced model and enum."""
        if model in self.models:
            return
        entry: Dict[str, Any] = {
            "python": qualified_name(model),
            "typescript": model_typescript_name(model),
            "fields": {},
        }
        self.models[model] = entry
        for name, annotation in serialized_annotations(model).items():
            entry["fields"][name] = self.describe(annotation)


def concrete_event_models() -> Set[type[Event]]:
    """Return every concrete Event wire model plus the generic Event model."""
    models: Set[type[Event]] = {Event}
    for model in descendants(Event):
        event_model = cast(type[Event], model)
        field = event_model.model_fields.get("event_type")
        if field is not None and field.default is not PydanticUndefined:
            models.add(event_model)
    return models


def allowed_event_types(model: type[Event]) -> list[str]:
    """Return semantic event categories accepted by one concrete wire model."""
    if model is Event:
        return [event_type.value for event_type in EventType]
    if qualified_name(model) == "dnd.core.events.SpatialChangeEvent":
        return [
            event_type.value
            for event_type in EventType
            if event_type.value.startswith("spatial_") or event_type.value == "movement_collision"
        ]
    default = model.model_fields["event_type"].default
    return [default.value if isinstance(default, Enum) else str(default)]


def build_manifest() -> Dict[str, Any]:
    """Build the canonical recursive event contract manifest."""
    import_dnd_modules()
    builder = ContractBuilder()
    event_models = sorted(concrete_event_models(), key=qualified_name)
    for model in event_models:
        builder.add_model(model)

    manifest: Dict[str, Any] = {
        "contract_version": 2,
        "event_types": [event_type.value for event_type in EventType],
        "event_classes": {
            qualified_name(model): {
                "model": qualified_name(model),
                "typescript": model_typescript_name(model),
                "event_types": allowed_event_types(model),
            }
            for model in event_models
        },
        "models": {
            qualified_name(model): builder.models[model]
            for model in sorted(builder.models, key=qualified_name)
        },
        "enums": {
            qualified_name(enum): builder.enums[enum]
            for enum in sorted(builder.enums, key=qualified_name)
        },
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["contract_hash"] = hashlib.sha256(canonical).hexdigest()
    return manifest


def typescript_literal(value: Any) -> str:
    """Render one JSON literal as TypeScript source."""
    return json.dumps(value, ensure_ascii=True)


def typescript_type(descriptor: Dict[str, Any], manifest: Dict[str, Any]) -> str:
    """Render a recursive contract descriptor as a TypeScript type."""
    kind = descriptor["kind"]
    if kind == "json":
        return "JsonValue"
    if kind == "null":
        return "null"
    if kind in {"string", "number", "boolean"}:
        return kind
    if kind == "literal":
        return typescript_literal(descriptor["value"])
    if kind == "enum":
        return manifest["enums"][descriptor["ref"]]["typescript"]
    if kind == "model":
        return manifest["models"][descriptor["ref"]]["typescript"]
    if kind == "array":
        return f"Array<{typescript_type(descriptor['items'], manifest)}>"
    if kind == "record":
        return f"Record<string, {typescript_type(descriptor['values'], manifest)}>"
    if kind == "tuple":
        return "[" + ", ".join(typescript_type(item, manifest) for item in descriptor["items"]) + "]"
    if kind == "union":
        rendered = list(dict.fromkeys(typescript_type(item, manifest) for item in descriptor["items"]))
        return " | ".join(rendered) if rendered else "never"
    raise ValueError(f"Unknown descriptor kind: {kind}")


def write_or_check(path: Path, content: str, check: bool) -> None:
    """Write one generated artifact or fail when its checked-in copy differs."""
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"Generated event contract is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    """Generate or verify the canonical backend event manifest."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    manifest = build_manifest()
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    write_or_check(SERVER_MANIFEST_PATH, manifest_text, args.check)


if __name__ == "__main__":
    main()
