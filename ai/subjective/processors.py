"""Built-in post-processors for the subjective runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ai.knowledge.deriver import derive_agent_facts
from ai.subjective.hooks import HookContext, HookPoint, ProcessorOutput
from ai.subjective.models import BriefEmission, TraceEmission
from ai.subjective.printers import render_epoch_brief


@dataclass
class AgentFactsProcessor:
    """Derive the shared typed policy facts before presentation processors run."""

    name: str = "agent_facts"
    order: int = 5
    state_changing_hook_points: ClassVar[frozenset[HookPoint]] = frozenset({
        HookPoint.SNAPSHOT_LOADED,
        HookPoint.FRAME_APPLIED,
        HookPoint.RESYNC_COMPLETED,
    })

    def should_run(self, context: HookContext) -> bool:
        """Derive after state changes or when no typed facts exist yet."""
        return context.hook in self.state_changing_hook_points or context.agent_state.facts is None

    def run(self, context: HookContext) -> list[ProcessorOutput]:
        """Update typed facts with immutable section reuse where possible."""
        derivation = derive_agent_facts(
            context.world,
            previous_world=context.previous_world,
            previous_facts=context.agent_state.facts,
        )
        return [
            ProcessorOutput(facts_update=derivation.facts),
            ProcessorOutput(
                trace=TraceEmission(
                    event="processor.agent_facts",
                    data={
                        "invalidated_sections": list(derivation.invalidated_sections),
                        "metrics": [metric.model_dump(mode="json") for metric in derivation.metrics],
                    },
                )
            ),
        ]


@dataclass
class TurnBriefProcessor:
    """Emit a compact brief for the current decision epoch."""

    name: str = "turn_brief"
    order: int = 90
    hook_points: ClassVar[frozenset[HookPoint]] = frozenset({
        HookPoint.SNAPSHOT_LOADED,
        HookPoint.EPOCH_STARTED,
        HookPoint.RESYNC_COMPLETED,
    })

    def run(self, context: HookContext) -> list[ProcessorOutput]:
        """Render a turn brief."""
        if context.world.current_epoch is None:
            return []
        text = render_epoch_brief(context.world, context.agent_state)
        return [ProcessorOutput(brief=BriefEmission(title="Decision Epoch", text=text, data={"epoch_id": context.world.current_epoch.epoch_id}))]


def default_processors() -> list:
    """Return the default subjective runtime post-processors."""
    return [
        AgentFactsProcessor(),
        TurnBriefProcessor(),
    ]
