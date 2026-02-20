"""Build turn prompts for orchestrated Claude-vs-Claude PvP.

Pure assembler: accepts pre-formatted strings and assembles sections.
Filtering logic lives in cli/log_filter.py.
"""

from typing import List


def build_turn_prompt(
    entity_name: str,
    faction: str,
    round_number: int,
    notebook_content: str,
    combat_log_text: str,
    entity_table_text: str,
    map_text: str,
    action_text: str,
    series_info: str = "",
) -> str:
    """Build a complete turn prompt for a Claude subprocess.

    Assembles: header, notebook, combat log, entity table, map, actions, instructions.
    All sections are pre-formatted strings — this function only assembles.
    """
    sections: List[str] = []

    # 1. Header
    header = (
        f"## {entity_name}'s Turn — Round {round_number}\n"
        f"You control the **{faction}** faction."
    )
    if series_info:
        header += f"\n{series_info}"
    sections.append(header)

    # 2. Notebook
    nb = notebook_content.strip() if notebook_content else ""
    if len(nb) > 2000:
        nb = "...(truncated)...\n" + nb[-1500:]
    sections.append(f"## Your Notebook\n{nb or '(empty — first turn)'}")

    # 3. Combat log
    if combat_log_text:
        sections.append(f"## What Happened Since Your Last Turn\n{combat_log_text}")

    # 4. Entity table
    sections.append(f"## Entities\n{entity_table_text}")

    # 5. Map
    sections.append(f"## Map\n{map_text}")

    # 6. Available actions
    sections.append(f"## Actions\n{action_text}")

    # 7. Instructions
    sections.append(
        "## Reminders\n"
        "- Use commands with your token (see system prompt)\n"
        "- After Dash, run `actions` to see expanded movement targets\n"
        "- **Always run `end` as your last action**"
    )

    return "\n\n".join(sections)
