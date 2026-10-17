"""Architecture: a value read takes its situation as one frozen argument (plan §6b PR).

Values hold no read state. Who reads a value, against whom, in which context
and with which opponent rows is the `ValueRead` passed to the read; the
evaluated result is a frozen `ValueReading`. The stateful forms are gone: no
target or context set and cleared on value or block trees, no imported opponent
channels stored on a value, no lineage-keyed breakdown cache.

Blocks still declare target and context fields because the sensory blocks are
constructed with them (outside this change); no setter writes them on a read.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Names of the removed stateful mechanism; none may be defined, called or read anywhere in dnd/.
REMOVED_NAMES = {
    "_temporary_target",
    "get_target_entity",
    "clear_target_entity",
    "set_from_target",
    "set_from_target_static",
    "set_from_target_contextual",
    "reset_from_target",
    "from_target_static",
    "from_target_contextual",
    "set_event_lineage",
    "clear_event_lineage",
    "event_lineage_uuid",
    "breakdown_result",
    "_latest_evaluation",
    "get_typed_modifiers",
    "get_full_breakdown",
    "get_full_advantage_breakdown",
    "get_advantage_breakdown",
    # PH-2: values are records with modifier rows; composed reads are parts, never a new value graph.
    "self_static",
    "to_target_static",
    "self_contextual",
    "to_target_contextual",
    "StaticValue",
    "ContextualValue",
    "BaseValue",
    "combine_values",
    "get_base_modifier",
    "renormalized",
    "composed_passive_score",
    "retire_owned_state",
    "get_all_modifier_uuids",
    "normalized_score_excluding_static_modifiers",
    "update_normalizers",
    "get_combined_values",
    "add_fixed_score",
}

# Values, blocks and entities may not define target or context setters on their models.
STATE_SETTERS = {"set_target_entity", "clear_target_entity", "set_context", "clear_context"}
VALUE_AND_BLOCK_MODULES = ("dnd/core/values.py", "dnd/core/base_block.py", "dnd/core/base_tiles.py", "dnd/entity.py")
VALUE_AND_BLOCK_PACKAGES = ("dnd/blocks/",)

# Records that keep a read keep its evaluated result. Damage and healing packets keep the parts of their
# bonus (a ComposedValue), which they read in their own situation (source, target, attack context).
READ_RECORD_MODULES = ("dnd/core/events.py", "dnd/core/dice.py", "dnd/actions.py")


def _names(tree: ast.AST) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg is not None:
            found.add(node.arg)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.add(node.target.id)
    return found


def test_the_stateful_value_read_mechanism_is_gone() -> None:
    uses = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        names = _names(ast.parse(path.read_text(encoding="utf-8")))
        uses.extend(f"{path.relative_to(ROOT)}: {name}" for name in sorted(names & REMOVED_NAMES))
    assert uses == []


def test_values_and_blocks_define_no_read_state_setters() -> None:
    definers = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative not in VALUE_AND_BLOCK_MODULES and not relative.startswith(VALUE_AND_BLOCK_PACKAGES):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef):
                definers.extend(f"{relative}:{item.lineno} {node.name}.{item.name}" for item in node.body
                                if isinstance(item, ast.FunctionDef) and (item.name in STATE_SETTERS
                                    or (node.name == "BaseBlock" and item.name == "clear")))
    assert definers == []


def test_read_records_hold_evaluated_readings_not_values() -> None:
    """Dice, d20 events and attack records keep the ValueReading of their read, never a live ModifiableValue."""
    fields = []
    for relative in READ_RECORD_MODULES:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if (isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
                        and "ModifiableValue" in ast.unparse(item.annotation)):
                    fields.append(f"{relative}:{item.lineno} {node.name}.{item.target.id}")
    assert fields == []


def test_values_declare_no_target_or_context_fields() -> None:
    """A value is its rows, owner and normalizer; the read situation is never a field of it."""
    fields = []
    tree = ast.parse((ROOT / "dnd/core/values.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ModifiableValue":
            fields.extend(f"{node.name}.{item.target.id}" for item in node.body
                          if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
                          and item.target.id in {"target_entity_uuid", "target_entity_name", "context"})
            bases = {base.id for base in node.bases if isinstance(base, ast.Name)}
            if "BaseObject" in bases:
                fields.append(f"{node.name} inherits BaseObject's target and context fields")
    assert fields == []
