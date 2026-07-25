"""Brief renderers for subjective runtime state."""

from __future__ import annotations

from dnd.ai.contracts.observation import SubjectiveWorldState
from ai.subjective.models import AgentState


def render_epoch_brief(world: SubjectiveWorldState, agent_state: AgentState) -> str:
    """Render a compact decision-epoch brief."""
    epoch = world.current_epoch
    if epoch is None:
        return "No active decision epoch."
    actor = world.known_entities.get(epoch.actor_uuid)
    actor_name = getattr(actor, "name", epoch.actor_uuid)
    economy = epoch.economy
    visible_hostile_uuids = (
        agent_state.facts.contacts.visible_hostile_uuids
        if agent_state.facts is not None
        else tuple()
    )
    rows = epoch.affordances.all_rows
    row_lines = [
        f"- {row.row_id}: {row.display_name} [{row.action_category}]"
        for row in rows[:8]
    ]
    enemy_lines = []
    for entity_uuid in visible_hostile_uuids[:5]:
        enemy = world.known_entities.get(entity_uuid)
        if enemy is not None:
            enemy_lines.append(f"- {enemy.name} at {enemy.position} hp={enemy.hp}")
    return "\n".join([
        f"Actor: {actor_name}",
        f"Epoch: {epoch.epoch_id}",
        (
            "Economy: "
            f"actions={economy.actions}, bonus={economy.bonus_actions}, "
            f"movement={economy.movement_remaining}, reactions={economy.reactions}"
        ),
        "Visible enemies:",
        *(enemy_lines or ["- none"]),
        "Top rows:",
        *(row_lines or ["- none"]),
    ])
