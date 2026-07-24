"""Local interning for immutable semantic contracts received across epochs."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Optional

from server.agent_protocol.control import DecisionEpoch
from server.agent_protocol.semantics import (
    ActionSemantics,
    action_semantics_payload_ref,
    action_semantics_ref,
)


class SemanticContractPool:
    """Bounded content-addressed store for repeated action semantics."""

    def __init__(self, max_contracts: int = 2048) -> None:
        """Create an empty pool.

        Args:
            max_contracts: Maximum immutable contracts retained locally.
        """
        if max_contracts < 1:
            raise ValueError("max_contracts must be at least 1")
        self.max_contracts = max_contracts
        self._contracts: OrderedDict[str, ActionSemantics] = OrderedDict()

    def intern_catalog(self, catalog: object) -> dict[str, ActionSemantics]:
        """Return a catalog whose values reuse locally interned contracts."""
        if not isinstance(catalog, dict):
            return {}
        return {
            str(reference): self._intern(str(reference), payload)
            for reference, payload in catalog.items()
        }

    def prepare_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Prepare snapshot JSON for validation while preserving caller data."""
        current_epoch = payload.get("current_epoch")
        prepared_epoch = self.prepare_epoch(current_epoch)
        if prepared_epoch is current_epoch:
            return payload
        return {**payload, "current_epoch": prepared_epoch}

    def prepare_frame(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Prepare frame JSON for validation while preserving caller data."""
        decision_epoch = payload.get("decision_epoch")
        prepared_epoch = self.prepare_epoch(decision_epoch)
        if prepared_epoch is decision_epoch:
            return payload
        return {**payload, "decision_epoch": prepared_epoch}

    def prepare_epoch(self, payload: object) -> object:
        """Intern one typed or serialized decision epoch's semantic catalog."""
        if payload is None:
            return None
        if isinstance(payload, DecisionEpoch):
            catalog = self.intern_catalog(payload.affordances.semantic_catalog)
            if all(
                catalog[reference] is semantics
                for reference, semantics in payload.affordances.semantic_catalog.items()
            ):
                return payload
            affordances = payload.affordances.model_copy(update={"semantic_catalog": catalog})
            return payload.model_copy(update={"affordances": affordances})
        if not isinstance(payload, dict):
            return payload
        affordances = payload.get("affordances")
        if not isinstance(affordances, dict):
            return payload
        catalog = affordances.get("semantic_catalog")
        if not isinstance(catalog, dict):
            return payload
        prepared_affordances = {
            **affordances,
            "semantic_catalog": self.intern_catalog(catalog),
        }
        return {**payload, "affordances": prepared_affordances}

    def get(self, reference: str) -> Optional[ActionSemantics]:
        """Return one interned contract and mark it recently used."""
        semantics = self._contracts.get(reference)
        if semantics is not None:
            self._contracts.move_to_end(reference)
        return semantics

    def _intern(self, reference: str, payload: object) -> ActionSemantics:
        """Resolve one contract reference and enforce the pool bound."""
        existing = self.get(reference)
        if existing is not None:
            if isinstance(payload, ActionSemantics):
                actual_reference = action_semantics_ref(payload)
            elif isinstance(payload, dict):
                actual_reference = action_semantics_payload_ref(payload)
            else:
                actual_reference = action_semantics_ref(ActionSemantics.model_validate(payload))
            if actual_reference != reference:
                raise ValueError(
                    "Semantic contract reference does not match its content: "
                    f"expected {reference!r}, computed {actual_reference!r}."
                )
            return existing
        if isinstance(payload, ActionSemantics):
            semantics = payload
        else:
            semantics = ActionSemantics.model_validate(payload)
        actual_reference = action_semantics_ref(semantics)
        if actual_reference != reference:
            raise ValueError(
                "Semantic contract reference does not match its content: "
                f"expected {reference!r}, computed {actual_reference!r}."
            )
        self._contracts[reference] = semantics
        while len(self._contracts) > self.max_contracts:
            self._contracts.popitem(last=False)
        return semantics
