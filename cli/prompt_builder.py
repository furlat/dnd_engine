"""Build turn prompts for orchestrated Claude-vs-Claude PvP."""

import copy
from typing import List, Optional, Set

from cli.agent import format_map, format_entities, format_actions, format_combat_log_entry


def summarize_position_targets(actions: dict, max_spell_targets: int = 25) -> dict:
    """Trim AoE spell position_actions to top N by affected_count.

    Move/Jump targets are NOT trimmed (Claude needs full list to pick positions).
    Returns a deep copy — does not mutate the original.
    Claude can always run `actions` to get the full untruncated list per spell.
    """
    actions = copy.deepcopy(actions)
    position_actions = actions.get("position_actions", [])
    for pa in position_actions:
        if pa.get("action_category") == "spell" and len(pa.get("valid_targets", [])) > max_spell_targets:
            targets = pa["valid_targets"]
            targets.sort(key=lambda t: t.get("affected_count", 0), reverse=True)
            total = len(targets)
            pa["valid_targets"] = targets[:max_spell_targets]
            pa["_note"] = f"Showing top {max_spell_targets} of {total} positions. Run `actions` for full list."
    return actions


def build_turn_prompt(
    faction: str,
    entity_name: str,
    active_entity_uuid: str,
    controlled_uuids: List[str],
    state: dict,
    actions: dict,
    combat_log_entries: List[dict],
    round_number: int,
    notebook_content: str,
    visible_entity_uuids: Optional[Set[str]] = None,
) -> str:
    """Build a complete turn prompt for a Claude subprocess.

    Assembles: header, notebook, combat log, entity table, map, actions, instructions.
    """
    sections: List[str] = []

    # 1. Header
    sections.append(
        f"## {entity_name}'s Turn — Round {round_number}\n"
        f"You control the **{faction}** faction."
    )

    # 2. Notebook
    nb = notebook_content.strip() if notebook_content else ""
    if len(nb) > 2000:
        nb = "...(truncated)...\n" + nb[-1500:]
    sections.append(f"## Your Notebook\n{nb or '(empty — first turn)'}")

    # 3. Combat log
    if combat_log_entries:
        log_lines = ["## What Happened Since Your Last Turn"]
        for entry in combat_log_entries:
            log_lines.extend(format_combat_log_entry(entry))
        sections.append("\n".join(log_lines))

    # 4. Entity table
    entities = state.get("entities", [])
    entity_table = format_entities(
        entities,
        visible_entity_uuids=visible_entity_uuids,
        my_entity_uuid=active_entity_uuid,
        controlled_uuids=controlled_uuids,
    )
    sections.append(f"## Entities\n{entity_table}")

    # 5. ASCII map
    ascii_map = format_map(
        state,
        visible_entity_uuids=visible_entity_uuids,
        my_entity_uuid=active_entity_uuid,
    )
    sections.append(f"## Map\n{ascii_map}")

    # 6. Available actions (with AoE trimming)
    trimmed_actions = summarize_position_targets(actions)
    action_text = format_actions(trimmed_actions, entity_name)
    sections.append(f"## Actions\n{action_text}")

    # 7. Instructions
    sections.append(
        "## Reminders\n"
        "- Use commands with your token (see system prompt)\n"
        "- After Dash, run `actions` to see expanded movement targets\n"
        "- Write observations to your notebook before ending\n"
        "- **Always run `end` as your last command**"
    )

    return "\n\n".join(sections)
