"""Architecture: handlers that act on others run after a simultaneous group (plan §5.3, index §7 "O").

Inside one area or multi-target effect every target takes the effect first;
reactions, concentration loss, aura refresh, summon and payload endings run in
phase B. Each such handler must declare it where it is constructed.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Handler names (or stable name fragments) of index §7's "acts on others" list.
AFTER_GROUP_HANDLERS = {
    "dnd/conditions.py": "Concentration Check",
    "dnd/spells/infernal.py": "Hellish Rebuke",
    "dnd/classes/barbarian.py": "Retaliation",
    "dnd/spells/evocation.py": "Fire Shield retaliation",
    "dnd/spells/abjuration.py": "Holy Aura melee-hit blindness",
    "dnd/classes/paladin.py": "Paladin aura deployment",
    "dnd/spatial/area_conditions.py": "Anchor Movement",
    "dnd/summoning/conditions.py": "Independent summon caster death",
    "dnd/items/spell_payloads.py": "Payload caster ending",
}


def _name_text(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str))
    return ""


def _is_handler_constructor(call: ast.Call) -> bool:
    function = call.func
    name = function.id if isinstance(function, ast.Name) else function.attr if isinstance(function, ast.Attribute) else ""
    return name.endswith("Handler")


def _declares_after_group(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg == "group_dispatch":
            value = keyword.value
            return isinstance(value, ast.Attribute) and value.attr == "AFTER_GROUP"
    return False


def test_handlers_acting_on_others_declare_after_group() -> None:
    missing = []
    for relative, fragment in AFTER_GROUP_HANDLERS.items():
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and _is_handler_constructor(node)
            and any(keyword.arg == "name" and fragment in _name_text(keyword.value) for keyword in node.keywords)]
        if not calls or not all(_declares_after_group(call) for call in calls):
            missing.append(f"{relative}: {fragment}")
    assert missing == []
