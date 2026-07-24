"""Non-wrapping logical annotations for production policy methods."""

from __future__ import annotations

from collections.abc import Callable
from typing import ParamSpec, TypeVar, cast

from pydantic import Field

from ai.planning.contracts import PlanningModel
from server.agent_protocol.semantics import FactExpression, LogicalEffect


Parameters = ParamSpec("Parameters")
ReturnValue = TypeVar("ReturnValue")
_CONTRACT_ATTRIBUTE = "__logical_policy_method_contract__"


class PolicyMethodContract(PlanningModel):
    """Logical intention declared by one decision-producing policy method."""

    method_id: str = Field(description="Stable identity of the policy method.")
    preconditions: FactExpression = Field(description="Facts required to propose this method.")
    progress_effects: tuple[LogicalEffect, ...] = Field(
        default_factory=tuple,
        description="Logical progress intended by one accepted method step.",
    )
    completion: FactExpression = Field(description="Facts establishing method completion.")
    invalidation: FactExpression = Field(description="Facts requiring method abandonment.")
    creates_observation_barrier: bool = Field(
        default=False,
        description="Whether the method must reassess after real sensory feedback.",
    )


_METHOD_CONTRACTS: dict[str, PolicyMethodContract] = {}


def logical_policy_method(
    contract: PolicyMethodContract,
) -> Callable[
    [Callable[Parameters, ReturnValue]],
    Callable[Parameters, ReturnValue],
]:
    """Attach immutable logical metadata without wrapping method execution."""

    def decorate(
        function: Callable[Parameters, ReturnValue],
    ) -> Callable[Parameters, ReturnValue]:
        existing = _METHOD_CONTRACTS.get(contract.method_id)
        if existing is not None and existing != contract:
            raise ValueError(
                f"Logical policy method {contract.method_id} has conflicting contracts"
            )
        _METHOD_CONTRACTS[contract.method_id] = contract
        setattr(function, _CONTRACT_ATTRIBUTE, contract)
        return function

    return decorate


def contract_for_policy_method(
    function: Callable[..., object],
) -> PolicyMethodContract:
    """Return a method's contract or reject an unannotated production leaf."""
    contract = getattr(function, _CONTRACT_ATTRIBUTE, None)
    if not isinstance(contract, PolicyMethodContract):
        raise ValueError(f"Policy method {function.__qualname__} has no logical contract")
    return contract


def registered_policy_method_contracts() -> tuple[PolicyMethodContract, ...]:
    """Return registered contracts in stable identity order."""
    return tuple(_METHOD_CONTRACTS[key] for key in sorted(_METHOD_CONTRACTS))


def clear_policy_method_contract_registry() -> None:
    """Clear registrations for isolated test worlds."""
    _METHOD_CONTRACTS.clear()


def typed_policy_method(
    function: Callable[Parameters, ReturnValue],
) -> Callable[Parameters, ReturnValue]:
    """Retain a function's precise callable type for annotation helpers."""
    return cast(Callable[Parameters, ReturnValue], function)

