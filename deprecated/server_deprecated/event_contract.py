"""Canonical serialization boundary for engine events sent to clients."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from dnd.core.events import Event


_CONTRACT_PATH = Path(__file__).with_name("event_contract.generated.json")


class EventContractError(RuntimeError):
    """Raised when a runtime event does not match the generated wire contract."""


def _load_contract() -> Dict[str, Any]:
    """Load and verify the checked-in generated event contract."""
    contract = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    expected_hash = contract.get("contract_hash")
    unhashed = {key: value for key, value in contract.items() if key != "contract_hash"}
    canonical = json.dumps(unhashed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    actual_hash = hashlib.sha256(canonical).hexdigest()
    if expected_hash != actual_hash:
        raise EventContractError(
            "Generated event contract hash mismatch; regenerate the contract before starting the server."
        )
    return contract


EVENT_CONTRACT = _load_contract()
EVENT_CONTRACT_VERSION = int(EVENT_CONTRACT["contract_version"])
EVENT_CONTRACT_HASH = str(EVENT_CONTRACT["contract_hash"])


def event_wire_type(event: Event) -> str:
    """Return the stable concrete event-class discriminator."""
    event_class = type(event)
    return f"{event_class.__module__}.{event_class.__qualname__}"


def serialize_event(event: Event) -> Dict[str, Any]:
    """Serialize one event and reject drift from the generated wire contract."""
    wire_type = event_wire_type(event)
    event_classes = EVENT_CONTRACT["event_classes"]
    event_contract = event_classes.get(wire_type)
    if event_contract is None:
        raise EventContractError(
            f"Event class {wire_type!r} is absent from the generated wire contract."
        )

    event_type = event.event_type.value
    if event_type not in event_contract["event_types"]:
        raise EventContractError(
            f"Event class {wire_type!r} cannot carry semantic type {event_type!r}."
        )

    payload = event.model_dump(mode="json")
    model_contract = EVENT_CONTRACT["models"][event_contract["model"]]
    expected_fields = set(model_contract["fields"])
    actual_fields = set(payload)
    if actual_fields != expected_fields:
        missing = sorted(expected_fields - actual_fields)
        unexpected = sorted(actual_fields - expected_fields)
        raise EventContractError(
            f"Event class {wire_type!r} drifted from the generated contract: "
            f"missing={missing}, unexpected={unexpected}."
        )

    return {"wire_type": wire_type, **payload}


def event_contract_summary() -> Dict[str, Any]:
    """Return the small contract identity payload used by clients at bootstrap."""
    return {
        "contract_version": EVENT_CONTRACT_VERSION,
        "contract_hash": EVENT_CONTRACT_HASH,
        "event_types": list(EVENT_CONTRACT["event_types"]),
        "wire_types": sorted(EVENT_CONTRACT["event_classes"]),
    }
