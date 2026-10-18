"""Architecture: one sheet publisher, one path (plan E5).

The sheet is evaluated in one place, by the one publisher, which the session calls at the end of its
composition and of every operation. The sheet and initiative events have one writer each, only the
publisher touches its kept sheets, and no publication module but the session imports the publisher.
The sheet fields that travel in their own events are written only where those events (or the birth)
carry the after-value.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def calls(name: str) -> list[str]:
    """Every call of `name` in dnd/, as 'file:function'."""
    found = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(function):
                if isinstance(node, ast.Call) and (
                        isinstance(node.func, ast.Name) and node.func.id == name
                        or isinstance(node.func, ast.Attribute) and node.func.attr == name):
                    found.append(f"{path.relative_to(ROOT)}:{function.name}")
    return sorted(set(found))


def test_the_sheet_is_evaluated_only_by_its_publisher():
    assert calls("evaluate_actor_sheet") == ["dnd/actor_sheets.py:publish_actor_sheets"]


def test_the_publisher_runs_at_session_start_and_at_every_operation_end():
    assert calls("publish_actor_sheets") == ["dnd/player/session.py:publish_sheets"]
    assert calls("publish_sheets") == ["dnd/player/session.py:_operation", "dnd/player/session.py:_start_session"]


def test_sheet_and_initiative_events_have_one_writer_each():
    assert calls("ActorSheetEvent") == ["dnd/actor_sheets.py:publish_actor_sheets"]
    assert calls("InitiativeOrderChangedEvent") == ["dnd/encounter.py:publish_initiative_order"]


def test_only_the_publisher_touches_its_kept_sheets():
    touching = set()
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr == "by_actor":
                touching.add(str(path.relative_to(ROOT)))
    assert touching == {"dnd/actor_sheets.py"}


def test_only_the_session_imports_the_publisher():
    importers = []
    for path in sorted((ROOT / "dnd" / "player").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "dnd.actor_sheets":
                importers.append(str(path.relative_to(ROOT)))
    assert importers == ["dnd/player/session.py"]


# Where the sheet fields that travel in their own events are written. Composition (builds, the class and
# origin grants, entity.py) writes them before the birth carries them; level changes publish
# EntityLevelAdded/RemovedEvent, which no session operation can carry (capture has no body for them);
# the others publish the after-value in a `dnd.player.sheet_facts` family. A new writer must do the same.
EVENTED_FIELD_WRITERS = {
    "dnd/characters/mastery.py": {"applied_class_levels"},
    "dnd/characters/spellbook.py": {"scribed_spell_ids"},
    "dnd/classes/divine_intervention.py": {"permanent_feature_uses"},
    "dnd/content/characters/barbarian_grants.py": {"applied_class_levels"},
    "dnd/content/characters/builds.py": {"permanent_feature_uses", "prepared_spell_selections", "scribed_spell_ids"},
    "dnd/content/characters/cleric_grants.py": {"applied_class_levels", "prepared_spell_selections"},
    "dnd/content/characters/fighter_grants.py": {"applied_class_levels"},
    "dnd/content/characters/origin_grants.py": {"applied_origin_state"},
    "dnd/content/characters/paladin_grants.py": {"applied_class_levels", "prepared_spell_selections"},
    "dnd/content/characters/progression.py": {"applied_class_levels", "applied_origin_state"},
    "dnd/content/characters/sorcerer_grants.py": {"applied_class_levels"},
    "dnd/content/characters/spellcasting_grants.py": {"prepared_spell_selections"},
    "dnd/content/characters/wizard_grants.py": {"applied_class_levels", "prepared_spell_selections"},
    "dnd/entity.py": {"character_background", "character_species", "character_species_variant"},
}


def test_evented_sheet_fields_are_written_only_by_their_event_owners():
    fields = set().union(*EVENTED_FIELD_WRITERS.values())
    found: dict[str, set[str]] = {}
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else [])
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in fields:
                    found.setdefault(str(path.relative_to(ROOT)), set()).add(target.attr)
    assert found == EVENTED_FIELD_WRITERS
