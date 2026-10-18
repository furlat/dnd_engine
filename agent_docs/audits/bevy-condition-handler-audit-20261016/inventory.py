"""Static source inventory for the condition/handler exposure audit.

This indexes declarations and call sites; it does not prove behavioral coverage.
Run from any directory. Outputs remain beside this script.
"""
from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[2]


def module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def partition(path: str) -> str:
    if path.startswith("dnd/spells/"):
        return "spells"
    if path in {"dnd/conditions.py", "dnd/tile_conditions.py"}:
        return "foundations"
    if path.startswith("dnd/core/"):
        return "core"
    if path in {"dnd/entity.py", "dnd/actions.py", "dnd/actions_functional.py",
                "dnd/action_dispatch.py", "dnd/encounter.py", "dnd/game.py"}:
        return "engine"
    return "features-world"


parsed = {}
imports = {}
classes = {}
failures = []
for path in sorted((ROOT / "dnd").rglob("*.py")):
    relative = str(path.relative_to(ROOT))
    try:
        tree = ast.parse(path.read_text(), filename=relative)
    except (SyntaxError, UnicodeError) as error:
        failures.append({"path": relative, "error": str(error)})
        continue
    module = module_name(path)
    parsed[module] = (relative, tree)
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            prefix = node.module or ""
            if node.level:
                package = module if path.stem == "__init__" else module.rsplit(".", 1)[0]
                prefix = ".".join(package.split(".")[:len(package.split(".")) - node.level + 1]
                                  + ([node.module] if node.module else []))
            for item in node.names:
                if item.name != "*":
                    aliases[item.asname or item.name] = f"{prefix}.{item.name}"
        elif isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = (
                    item.name if item.asname else item.name.split(".")[0])
    imports[module] = aliases
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes[f"{module}.{node.name}"] = {
                "path": relative, "module": module, "node": node,
                "bases": [ast.unparse(base) for base in node.bases],
            }


def resolve(module: str, spelling: str, seen: frozenset[str] = frozenset()) -> str:
    if "(" in spelling or "[" in spelling:
        return spelling
    first, dot, rest = spelling.partition(".")
    mapped = imports.get(module, {}).get(first)
    candidate = f"{mapped}{dot}{rest}" if mapped else f"{module}.{spelling}"
    if candidate in classes or candidate in seen:
        return candidate
    parent, _, leaf = candidate.rpartition(".")
    if leaf in imports.get(parent, {}):
        target = imports[parent][leaf]
        target_parent, _, target_leaf = target.rpartition(".")
        return resolve(target_parent, target_leaf, seen | {candidate})
    return candidate


families = {
    "condition": {"dnd.core.base_conditions.BaseCondition"},
    "handler": {"dnd.core.events.BaseHandler"},
    "contextual_modifier": {"dnd.core.modifiers.ContextualModifier"},
}
changed = True
while changed:
    changed = False
    for qualified, item in classes.items():
        bases = {resolve(item["module"], base) for base in item["bases"]}
        for members in families.values():
            if qualified not in members and bases & members:
                members.add(qualified)
                changed = True

registrations = {
    "add_event_handler", "add_spatial_handler", "remove_event_handler",
    "remove_spatial_handler", "add_pre_completion_callback",
    "add_pre_completion_system", "add_on_event_callback",
    "add_on_handler_dispatch_callback", "add_on_event_sequence_callback",
    "add_on_event_batch_callback", "invoke_admitted_system_effect",
    "register_condition_removal_participant", "register_condition_graph_settled_hook",
    "add_close_callback",
}
condition_operations = {
    "add_condition", "add_condition_with_event", "prepare_condition_application",
    "commit_prepared_condition_application", "remove_condition",
    "remove_condition_by_uuid", "prepare_condition_removal", "set_suppression",
    "activate", "move_to", "remove", "phase_to", "with_updates", "post",
}
rows = []


def add(kind: str, path: str, node: ast.AST, owner: str, expression: str, **extra) -> None:
    rows.append({"kind": kind, "partition": partition(path), "path": path,
                 "line": node.lineno, "end_line": node.end_lineno,
                 "owner": owner, "expression": expression, **extra})


class IndexVisitor(ast.NodeVisitor):
    def __init__(self, module: str, path: str):
        self.module = module
        self.path = path
        self.scope = []

    @property
    def owner(self):
        return ".".join([self.module] + self.scope)

    def visit_ClassDef(self, node):
        qualified = f"{self.module}.{node.name}"
        for family, members in families.items():
            if qualified in members:
                add(f"{family}_class", self.path, node, self.owner, qualified,
                    bases=[ast.unparse(base) for base in node.bases])
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        if self.scope and f"{self.module}.{self.scope[0]}" in families["condition"] and len(self.scope) == 1:
            add("condition_method", self.path, node, self.owner, node.name)
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        spelling = ast.unparse(node.func)
        qualified = resolve(self.module, spelling)
        constructor = qualified.removesuffix(".create")
        for family, members in families.items():
            if constructor in members:
                add(f"{family}_construction", self.path, node, self.owner, spelling,
                    keywords={item.arg: ast.unparse(item.value) for item in node.keywords
                              if item.arg is not None})
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in registrations:
                add("registration_or_direct_dispatch", self.path, node, self.owner, spelling,
                    arguments=[ast.unparse(value) for value in node.args],
                    keywords={item.arg: ast.unparse(item.value) for item in node.keywords
                              if item.arg is not None})
            if node.func.attr in condition_operations:
                add("interaction_call", self.path, node, self.owner, spelling)
        for keyword in node.keywords:
            if keyword.arg == "event_processor":
                add("processor_argument", self.path, node, self.owner, ast.unparse(keyword.value))
            elif keyword.arg == "callable":
                add("contextual_callable_argument", self.path, node, self.owner,
                    ast.unparse(keyword.value))
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Name) and node.target.id == "event_processor" and node.value:
            add("processor_field_declaration", self.path, node, self.owner, ast.unparse(node.value))
        self.generic_visit(node)

    def visit_Assign(self, node):
        if any(isinstance(target, ast.Attribute) and target.attr == "event_processor"
               or isinstance(target, ast.Name) and target.id == "event_processor"
               for target in node.targets):
            add("processor_reassignment", self.path, node, self.owner, ast.unparse(node.value))
        self.generic_visit(node)


for module, (path, tree) in parsed.items():
    IndexVisitor(module, path).visit(tree)

rows.sort(key=lambda row: (row["path"], row["line"], row["kind"]))
summary = {"parsed_files": len(parsed), "parse_failures": failures,
           "class_counts": {family: len(members) for family, members in families.items()},
           "rows_by_kind": {}, "rows_by_partition": {},
           "limits": ["Static declarations/call sites, not behavioral coverage.",
                      "Runtime-created definitions and reflective factories require manual review.",
                      "Interaction-call inventory intentionally includes unrelated same-name methods.",
                      "Aliases resolved from module-level imports; local/shadowed imports need review."]}
for row in rows:
    for dimension, key in [("rows_by_kind", row["kind"]),
                           ("rows_by_partition", row["partition"])]:
        summary[dimension][key] = summary[dimension].get(key, 0) + 1
OUTPUT.mkdir(parents=True, exist_ok=True)
(OUTPUT / "inventory.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
with (OUTPUT / "inventory.tsv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=["kind", "partition", "path", "line",
                                              "end_line", "owner", "expression"],
                            delimiter="\t", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
print(json.dumps(summary, indent=2))
