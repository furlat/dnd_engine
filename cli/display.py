"""
Display module for ASCII rendering with Rich.
"""

from typing import Dict, Any, List, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


console = Console()


def clear():
    """Clear the terminal."""
    console.clear()


def render_map(
    grid: Dict[str, Any],
    entities: List[Dict[str, Any]],
    current_entity_uuid: Optional[str] = None,
    valid_positions: Optional[List[Tuple[int, int]]] = None,
    visibility: Optional[Dict[str, Any]] = None,
    movement_path: Optional[List[Tuple[int, int]]] = None
) -> Text:
    """
    Render ASCII map with Rich formatting.

    Args:
        grid: Grid data from API
        entities: List of entities from API
        current_entity_uuid: UUID of current player (shown as @)
        valid_positions: Optional list of valid move positions (shown as *)
        visibility: Optional visibility data from API (uuid -> visible_cells)
        movement_path: Optional path to highlight (from last move)

    Returns:
        Rich Text object with colored map
    """
    # Build tile lookup
    tiles = {(t["x"], t["y"]): t for t in grid.get("tiles", [])}
    min_x, min_y = grid.get("min_x", 0), grid.get("min_y", 0)
    max_x, max_y = grid.get("max_x", 14), grid.get("max_y", 14)

    # Build entity lookup
    entity_at = {}
    for e in entities:
        pos = tuple(e["position"])
        entity_at[pos] = e

    # Valid positions set
    valid_set = set(tuple(p) for p in valid_positions) if valid_positions else set()

    # Movement path set
    path_set = set(tuple(p) for p in movement_path) if movement_path else set()

    # Build visibility sets: hero (green), enemy (red), both (yellow)
    hero_visible = set()
    enemy_visible = set()
    if visibility and current_entity_uuid:
        for uuid, data in visibility.items():
            cells = set(tuple(c) for c in data.get("visible_cells", []))
            if uuid == current_entity_uuid:
                hero_visible = cells
            else:
                enemy_visible.update(cells)

    # Build the map with Rich Text for coloring
    result = Text()

    # Header row with column numbers
    result.append("   ")
    for x in range(min_x, max_x + 1):
        result.append(f"{x % 10} ")
    result.append("\n")

    # Top border
    result.append("  +" + "-" * ((max_x - min_x + 1) * 2 + 1) + "+\n")

    for y in range(min_y, max_y + 1):
        result.append(f"{y:2}|")
        for x in range(min_x, max_x + 1):
            pos = (x, y)
            tile = tiles.get(pos)
            entity = entity_at.get(pos)

            # Determine cell character
            if entity:
                if entity["uuid"] == current_entity_uuid:
                    char = "@"  # Player
                    style = "bold green"
                elif entity.get("is_dead"):
                    char = "%"  # Corpse
                    style = "dim"
                else:
                    char = entity["name"][0].upper()  # First letter
                    style = "bold red"
            elif pos in path_set:
                char = "+"  # Movement path
                style = "bold magenta"
            elif pos in valid_set:
                char = "*"  # Valid move target
                style = "bold yellow"
            elif tile is None:
                char = " "
                style = ""
            elif not tile.get("walkable", True):
                char = "#"  # Wall
                style = "white"
            else:
                char = "."  # Floor
                # Determine visibility coloring
                in_hero = pos in hero_visible
                in_enemy = pos in enemy_visible
                if in_hero and in_enemy:
                    style = "yellow"  # Both see it
                elif in_hero:
                    style = "green"  # Only hero sees it
                elif in_enemy:
                    style = "red"  # Only enemy sees it
                else:
                    style = "dim"  # Neither sees it

            result.append(" ")
            result.append(char, style=style)
        result.append(" |\n")

    # Bottom border
    result.append("  +" + "-" * ((max_x - min_x + 1) * 2 + 1) + "+")

    return result


def show_map(
    grid: Dict[str, Any],
    entities: List[Dict[str, Any]],
    current_entity_uuid: Optional[str] = None,
    valid_positions: Optional[List[Tuple[int, int]]] = None,
    visibility: Optional[Dict[str, Any]] = None,
    movement_path: Optional[List[Tuple[int, int]]] = None,
    title: str = "Battlefield"
):
    """Display the map in a panel."""
    map_text = render_map(grid, entities, current_entity_uuid, valid_positions, visibility, movement_path)

    # Legend with visibility colors
    legend = Text()
    legend.append("@ ", style="bold green")
    legend.append("= You  ")
    legend.append("X ", style="bold red")
    legend.append("= Enemy  ")
    legend.append("* ", style="bold yellow")
    legend.append("= Valid move  ")
    legend.append("+ ", style="bold magenta")
    legend.append("= Path\n")
    legend.append(". ", style="green")
    legend.append("= You see  ")
    legend.append(". ", style="red")
    legend.append("= Enemy sees  ")
    legend.append(". ", style="yellow")
    legend.append("= Both see  ")
    legend.append("# ", style="white")
    legend.append("= Wall")

    # Combine map and legend
    content = Text()
    content.append_text(map_text)
    content.append("\n\n")
    content.append_text(legend)

    console.print(Panel(content, title=title, box=box.ROUNDED))


def show_turn_info(turn: Dict[str, Any], entities: List[Dict[str, Any]]):
    """Display turn information and entity status."""
    # Find current entity
    current_uuid = turn.get("current_entity_uuid")
    current = next((e for e in entities if e["uuid"] == current_uuid), None)

    if not current:
        console.print("[red]No current entity[/red]")
        return

    # Turn header
    is_human = turn.get("is_human_turn", False)
    turn_text = "[bold green]YOUR TURN[/bold green]" if is_human else "[bold red]ENEMY TURN[/bold red]"

    console.print(Panel(
        f"Round [bold]{turn['round_number']}[/bold] - {current['name']} - {turn_text}",
        box=box.HEAVY
    ))

    # Entity status table
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("Entity", style="cyan")
    table.add_column("HP", justify="right")
    table.add_column("AC", justify="right")
    table.add_column("Position", justify="center")
    table.add_column("Conditions")

    for e in entities:
        is_current = e["uuid"] == current_uuid
        name = f"[bold]{e['name']}[/bold]" if is_current else e['name']
        if e["uuid"] == current_uuid and is_human:
            name = f"[green]{name}[/green]"
        elif e.get("is_dead"):
            name = f"[dim strikethrough]{e['name']}[/dim strikethrough]"

        hp_color = "green" if e["hp"] > e["max_hp"] // 2 else "yellow" if e["hp"] > 0 else "red"
        hp = f"[{hp_color}]{e['hp']}/{e['max_hp']}[/{hp_color}]"

        conditions = ", ".join(e.get("conditions", [])) or "-"

        table.add_row(
            name,
            hp,
            str(e.get("ac", "?")),
            f"({e['position'][0]}, {e['position'][1]})",
            conditions
        )

    console.print(table)

    # Action economy for current entity if human turn
    if is_human:
        console.print(
            f"\n[bold]Action Economy:[/bold] "
            f"Actions: [cyan]{turn['actions_remaining']}[/cyan]  "
            f"Bonus: [cyan]{turn['bonus_actions_remaining']}[/cyan]  "
            f"Movement: [cyan]{turn['movement_remaining']}ft[/cyan]  "
            f"Reaction: [cyan]{turn['reactions_remaining']}[/cyan]"
        )


def show_available_actions(actions: Dict[str, Any], entities: List[Dict[str, Any]]):
    """Display available actions."""
    console.print("\n[bold underline]Available Actions:[/bold underline]\n")

    # Entity lookup for names
    entity_lookup = {e["uuid"]: e for e in entities}

    # Attacks
    attacks = actions.get("attacks", [])
    if attacks:
        console.print("[bold cyan]ATTACKS[/bold cyan] (1 action):")
        for i, atk in enumerate(attacks, 1):
            targets = atk.get("valid_targets", [])
            can_afford = atk.get("can_afford", False)
            status = "[green]ready[/green]" if can_afford else "[red]no targets[/red]"

            target_names = []
            for t_uuid in targets[:3]:  # Show first 3
                t = entity_lookup.get(t_uuid, {})
                target_names.append(t.get("name", "Unknown"))
            targets_str = ", ".join(target_names) if target_names else "none in range"

            console.print(f"  [{i}] {atk['name']} - {status}")
            if targets:
                console.print(f"      Targets: {targets_str}")

    # Movement
    if actions.get("can_move"):
        console.print(f"\n[bold cyan]MOVEMENT[/bold cyan] ({actions['remaining_movement']}ft remaining):")
        console.print("  [m] move X Y - Move to position")
        console.print("  [m] move     - Show valid positions on map")

    # Other actions
    other = actions.get("other_actions", [])
    if other:
        console.print("\n[bold cyan]OTHER ACTIONS[/bold cyan] (1 action each):")
        for act in other:
            can = "[green]ready[/green]" if act.get("can_afford") else "[red]no action[/red]"
            console.print(f"  [{act['action_id'][0]}] {act['name']} - {act['description']} - {can}")

    # Free actions
    free = actions.get("free_actions", [])
    if free:
        console.print("\n[bold cyan]FREE ACTIONS[/bold cyan]:")
        for act in free:
            console.print(f"  [p] {act['name']} - {act['description']}")

    # Always available
    console.print("\n[bold cyan]OTHER[/bold cyan]:")
    console.print("  [e] end      - End your turn")
    console.print("  [s] status   - Show detailed status")
    console.print("  [?] help     - Show all commands")
    console.print("  [q] quit     - Exit game")


def format_attack_roll(d20, all_d20_rolls, advantage_status, attack_bonus, attack_total, target_ac):
    """Format attack roll display with advantage/disadvantage info."""
    bonus_str = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)

    if advantage_status == "advantage" and len(all_d20_rolls) >= 2:
        # Show both rolls, highlight the higher one (used)
        rolls_display = f"d20([green]{all_d20_rolls[0]}[/green], [green]{all_d20_rolls[1]}[/green] → [bold green]{d20}[/bold green])"
        adv_text = "[bold green]ADV[/bold green] "
    elif advantage_status == "disadvantage" and len(all_d20_rolls) >= 2:
        # Show both rolls, highlight the lower one (used)
        rolls_display = f"d20([red]{all_d20_rolls[0]}[/red], [red]{all_d20_rolls[1]}[/red] → [bold red]{d20}[/bold red])"
        adv_text = "[bold red]DIS[/bold red] "
    else:
        # Normal roll
        rolls_display = f"d20([cyan]{d20}[/cyan])"
        adv_text = ""

    return f"  {adv_text}Attack Roll: {rolls_display} {bonus_str} = [bold]{attack_total}[/bold] vs AC [bold]{target_ac}[/bold]"


def show_action_result(result: Dict[str, Any]):
    """Display the result of an action."""
    success = result.get("success", False)
    event_type = result.get("event_type", "")

    # Show attack details with full breakdown
    event_data = result.get("event_data")
    if event_data and event_type == "attack":
        attacker = event_data.get("attacker", "You")
        target_name = event_data.get("target", "Unknown")
        weapon = event_data.get("weapon", "weapon")
        d20 = event_data.get("d20")
        all_d20_rolls = event_data.get("all_d20_rolls", [])
        advantage_status = event_data.get("advantage_status", "none")
        attack_bonus = event_data.get("attack_bonus", 0)
        attack_total = event_data.get("attack_total")
        target_ac = event_data.get("target_ac")
        outcome = (event_data.get("outcome") or "").lower()
        total_damage = event_data.get("total_damage", 0)
        damage_rolls = event_data.get("damage_rolls", [])

        # Attack header
        console.print(f"\n[bold cyan]{attacker}[/bold cyan] attacks [bold yellow]{target_name}[/bold yellow] with [white]{weapon}[/white]")

        # Roll breakdown with advantage/disadvantage info
        console.print(format_attack_roll(d20, all_d20_rolls, advantage_status, attack_bonus, attack_total, target_ac))

        # Outcome
        if outcome == "crit":
            console.print(f"  Result: [bold yellow]*** CRITICAL HIT! ***[/bold yellow]")
        elif outcome == "hit":
            console.print(f"  Result: [bold green]HIT![/bold green]")
        elif outcome == "crit miss":
            console.print(f"  Result: [bold red]CRITICAL MISS![/bold red]")
        else:
            console.print(f"  Result: [dim]MISS[/dim]")

        # Damage breakdown if hit
        if outcome in ("hit", "crit") and total_damage > 0:
            damage_strs = []
            for dr in damage_rolls:
                dice = dr.get("dice", [])
                bonus = dr.get("bonus", 0)
                if isinstance(dice, list):
                    dice_str = "+".join(str(d) for d in dice)
                else:
                    dice_str = str(dice)
                if bonus != 0:
                    bonus_str = f"+{bonus}" if bonus > 0 else str(bonus)
                    damage_strs.append(f"({dice_str}){bonus_str}")
                else:
                    damage_strs.append(f"({dice_str})")
            console.print(f"  Damage: {' + '.join(damage_strs)} = [bold red]{total_damage}[/bold red]")

        # Target HP after attack
        target_hp = result.get("target_hp")
        if target_hp is not None:
            console.print(f"  {target_name} HP: [red]{target_hp}[/red]")

    elif event_type == "movement":
        # Movement result
        if event_data:
            start = event_data.get("start", [])
            end = event_data.get("end", [])
            console.print(f"[green]Moved from {tuple(start)} to {tuple(end)}[/green]")
        else:
            message = result.get("message", "Moved")
            console.print(f"[green]{message}[/green]")

        # Show any opportunity attacks triggered by movement
        triggered = result.get("triggered_reactions", [])
        for reaction in triggered:
            if reaction.get("type") == "opportunity_attack":
                show_opportunity_attack(reaction)

    else:
        # Generic action result
        message = result.get("message", "Action completed")
        if success:
            console.print(f"[green]{message}[/green]")
        else:
            console.print(f"[red]{message}[/red]")

    # Show deaths
    deaths = result.get("deaths", [])
    for name in deaths:
        console.print(f"\n[bold red]*** {name} has been slain! ***[/bold red]")

    # Show encounter end
    if result.get("encounter_ended"):
        console.print("\n[bold yellow]*** ENCOUNTER ENDED ***[/bold yellow]")


def show_error(message: str):
    """Display an error message."""
    console.print(f"[red]Error: {message}[/red]")


def show_info(message: str):
    """Display an info message."""
    console.print(f"[cyan]{message}[/cyan]")


def show_opportunity_attack(reaction: Dict[str, Any]):
    """Display an opportunity attack that was triggered."""
    attacker = reaction.get("attacker", "Unknown")
    target_name = reaction.get("target", "You")
    weapon = reaction.get("weapon", "weapon")
    d20 = reaction.get("d20")
    all_d20_rolls = reaction.get("all_d20_rolls", [])
    advantage_status = reaction.get("advantage_status", "none")
    attack_bonus = reaction.get("attack_bonus", 0)
    attack_total = reaction.get("attack_total")
    target_ac = reaction.get("target_ac")
    outcome = (reaction.get("outcome") or "").lower()
    total_damage = reaction.get("total_damage", 0)
    damage_rolls = reaction.get("damage_rolls", [])

    console.print(f"\n[bold magenta]*** OPPORTUNITY ATTACK! ***[/bold magenta]")
    console.print(f"[red]{attacker}[/red] attacks [cyan]{target_name}[/cyan] with [white]{weapon}[/white]")

    # Roll breakdown with advantage/disadvantage
    if d20 is not None and attack_total is not None and target_ac is not None:
        console.print(format_attack_roll(d20, all_d20_rolls, advantage_status, attack_bonus, attack_total, target_ac))

    # Outcome
    if outcome == "crit":
        console.print(f"  Result: [bold yellow]*** CRITICAL HIT! ***[/bold yellow]")
    elif outcome == "hit":
        console.print(f"  Result: [bold green]HIT![/bold green]")
    elif outcome == "crit miss":
        console.print(f"  Result: [bold red]CRITICAL MISS![/bold red]")
    else:
        console.print(f"  Result: [dim]MISS[/dim]")

    # Damage breakdown if hit
    if outcome in ("hit", "crit") and total_damage > 0:
        damage_strs = []
        for dr in damage_rolls:
            dice = dr.get("dice", [])
            bonus = dr.get("bonus", 0)
            if isinstance(dice, list):
                dice_str = "+".join(str(d) for d in dice)
            else:
                dice_str = str(dice)
            if bonus != 0:
                b_str = f"+{bonus}" if bonus > 0 else str(bonus)
                damage_strs.append(f"({dice_str}){b_str}")
            else:
                damage_strs.append(f"({dice_str})")
        console.print(f"  Damage: {' + '.join(damage_strs)} = [bold red]{total_damage}[/bold red]")


def show_combat_log(messages: List[str], max_lines: int = 5):
    """Display recent combat log messages."""
    if not messages:
        return
    console.print("\n[bold]Combat Log:[/bold]")
    for msg in messages[-max_lines:]:
        console.print(f"  [dim]{msg}[/dim]")


def show_ai_actions(actions: List[Dict[str, Any]]):
    """Display AI actions that occurred during AI turn."""
    if not actions:
        return

    console.print("\n[bold red]━━━ AI TURN ━━━[/bold red]")
    for action in actions:
        action_type = action.get("type", "")

        if action_type == "turn_start":
            entity_name = action.get("entity", "Unknown")
            console.print(f"\n[bold yellow]{entity_name}'s turn[/bold yellow]")

        elif action_type == "attack":
            attacker = action.get("attacker", "Unknown")
            target_name = action.get("target", "Unknown")
            weapon = action.get("weapon", "weapon")
            d20 = action.get("d20")
            all_d20_rolls = action.get("all_d20_rolls", [])
            advantage_status = action.get("advantage_status", "none")
            attack_bonus = action.get("attack_bonus", 0)
            attack_total = action.get("attack_total")
            target_ac = action.get("target_ac")
            outcome = (action.get("outcome") or "").lower()
            total_damage = action.get("total_damage", 0)
            damage_rolls = action.get("damage_rolls", [])
            is_opp_attack = action.get("is_opportunity_attack", False)

            # Attack header
            opp_text = "[bold magenta](OPPORTUNITY ATTACK)[/bold magenta] " if is_opp_attack else ""
            console.print(f"\n  {opp_text}[red]{attacker}[/red] attacks [cyan]{target_name}[/cyan] with [white]{weapon}[/white]")

            # Roll breakdown with advantage/disadvantage
            if d20 is not None and attack_total is not None and target_ac is not None:
                roll_line = format_attack_roll(d20, all_d20_rolls, advantage_status, attack_bonus, attack_total, target_ac)
                # Add extra indent for AI actions
                console.print(f"  {roll_line}")

            # Outcome
            if outcome == "crit":
                console.print(f"    Result: [bold yellow]*** CRITICAL HIT! ***[/bold yellow]")
            elif outcome == "hit":
                console.print(f"    Result: [bold green]HIT![/bold green]")
            elif outcome == "crit miss":
                console.print(f"    Result: [bold red]CRITICAL MISS![/bold red]")
            else:
                console.print(f"    Result: [dim]MISS[/dim]")

            # Damage breakdown if hit
            if outcome in ("hit", "crit") and total_damage > 0:
                damage_strs = []
                for dr in damage_rolls:
                    dice = dr.get("dice", [])
                    bonus = dr.get("bonus", 0)
                    if isinstance(dice, list):
                        dice_str = "+".join(str(d) for d in dice)
                    else:
                        dice_str = str(dice)
                    if bonus != 0:
                        b_str = f"+{bonus}" if bonus > 0 else str(bonus)
                        damage_strs.append(f"({dice_str}){b_str}")
                    else:
                        damage_strs.append(f"({dice_str})")
                console.print(f"    Damage: {' + '.join(damage_strs)} = [bold red]{total_damage}[/bold red]")

        elif action_type == "move":
            entity = action.get("entity", "Unknown")
            from_pos = action.get("from", [0, 0])
            to_pos = action.get("to", [0, 0])
            console.print(f"  [red]{entity}[/red] moves {tuple(from_pos)} → {tuple(to_pos)}")

    console.print("[bold red]━━━ END AI TURN ━━━[/bold red]\n")


def prompt_command() -> str:
    """Prompt for a command."""
    console.print()
    return console.input("[bold yellow]>[/bold yellow] ").strip().lower()


def show_help():
    """Display help information."""
    help_text = """
[bold underline]Commands:[/bold underline]

[bold cyan]Movement:[/bold cyan]
  move X Y      Move to position (X, Y)
  move          Show valid move positions on map
  m X Y         Short form of move

[bold cyan]Combat:[/bold cyan]
  attack N      Attack target number N from the list
  a N           Short form of attack

[bold cyan]Actions:[/bold cyan]
  dash          Take the Dash action (double movement)
  dodge         Take the Dodge action (disadvantage on attacks)
  disengage     Take the Disengage action (no opportunity attacks)
  d/o/i         Short forms

[bold cyan]Turn:[/bold cyan]
  end           End your turn
  e             Short form of end

[bold cyan]Info:[/bold cyan]
  status        Show detailed entity status
  actions       List all available actions
  map           Redraw the map
  help / ?      Show this help

[bold cyan]Game:[/bold cyan]
  quit / q      Exit the game
"""
    console.print(Panel(help_text, title="Help", box=box.ROUNDED))
