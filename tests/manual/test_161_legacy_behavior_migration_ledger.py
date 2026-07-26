"""Exact migration inventory for legacy actions, conditions, and handlers."""

from __future__ import annotations

import ast
import importlib
import os
import pkgutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import dnd
from dnd.core.base_actions import BaseAction
from dnd.core.base_conditions import BaseCondition
from dnd.core.content.inventory import (
    LegacyContentClassification,
    LegacyContentMigrationLedger,
    LegacyMigrationStatus,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.registration import get_content_declaration
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.spells import ALL_SPELLS


_ROOT = Path(__file__).resolve().parents[2]
_DND_ROOT = _ROOT / "dnd"
_LEDGER_PATH = _ROOT / "content_data" / "ledgers" / "legacy_behaviors.json"
_INVENTORY_TEST_NODEID = (
    "tests/manual/test_161_legacy_behavior_migration_ledger.py::"
    "test_every_current_behavior_definition_and_construction_site_is_accounted"
)
_EXPECTED_EXPLICIT_HANDLER_INVENTORY = {
    (
        "dnd/classes/barbarian.py:create_retaliation_handler"
        "#event_handler_construction.1"
    ): ("explicit:feature.barbarian.retaliation", "true"),
    (
        "dnd/classes/fighter.py:create_protection_handler"
        "#event_handler_construction.1"
    ): ("explicit:feature.fighter.protection", "true"),
    (
        "dnd/monsters/traits.py:ParryFeature._apply"
        "#event_handler_construction.1"
    ): ("explicit:trait.monster.parry", "false"),
    (
        "dnd/monsters/traits.py:UndeadFortitudeFeature._apply"
        "#event_handler_construction.1"
    ): ("explicit:trait.monster.undead_fortitude", "false"),
}
_EXPECTED_INTERNAL_CONDITION_LOCATORS = {
    "dnd/classes/fighter.py:ActionSurging",
    "dnd/classes/fighter.py:ExtraAttacksGranted",
    "dnd/conditions.py:ConcentrationActionMarker",
    "dnd/conditions.py:HasAttacked",
    "dnd/conditions.py:HasTakenDamage",
    "dnd/items/consumables.py:_WeaponCoatCondition",
    "dnd/monsters/skeleton_abilities.py:MarkCooldown",
    "dnd/monsters/traits.py:SimpleMarkerCondition",
    "dnd/spells/abjuration.py:AntimagicSuppression",
    "dnd/spells/conjuration.py:GuardianWarded",
    "dnd/spells/conjuration.py:SpiritGuardiansTriggered",
    "dnd/spells/necromancy.py:EyebiteCastingState",
}
_EXPECTED_ABSTRACT_CONDITION_LOCATORS = {
    "dnd/monsters/traits.py:BonusDamageFeature",
    "dnd/monsters/traits.py:ConditionalSaveAdvantageFeature",
    "dnd/monsters/traits.py:HitSaveRiderFeature",
    "dnd/monsters/traits.py:KeenPerceptionFeature",
    "dnd/spells/enchantment.py:CommandNextTurnEffect",
    "dnd/tile_conditions.py:TileEffectCondition",
    "dnd/tile_conditions.py:ZoneControlCondition",
}


@dataclass(frozen=True)
class _HandlerConstruction:
    locator: str
    semantic_identity: str
    player_toggleable: str


@dataclass(frozen=True)
class _ActionSource:
    inventory_kind: str
    locator: str


def _load_ledger() -> LegacyContentMigrationLedger:
    return LegacyContentMigrationLedger.model_validate_json(
        _LEDGER_PATH.read_text(encoding="utf-8"),
    )


def _module_names() -> tuple[str, ...]:
    return tuple(
        sorted(
            module.name
            for module in pkgutil.walk_packages(
                dnd.__path__,
                prefix="dnd.",
            )
        ),
    )


def _import_all_dnd_modules() -> None:
    for module_name in _module_names():
        importlib.import_module(module_name)


def _all_subclasses(root: type) -> set[type]:
    subclasses: set[type] = set()
    pending = list(root.__subclasses__())
    while pending:
        subclass = pending.pop()
        if subclass in subclasses:
            continue
        subclasses.add(subclass)
        pending.extend(subclass.__subclasses__())
    return subclasses


def _definition_locator(definition: type) -> str:
    return (
        f"{definition.__module__.replace('.', '/')}.py:"
        f"{definition.__qualname__}"
    )


def _runtime_definition_locators(root: type) -> set[str]:
    _import_all_dnd_modules()
    return {
        _definition_locator(definition)
        for definition in _all_subclasses(root)
        if definition.__module__.startswith("dnd.")
    }


def _terminal_name(expression: ast.expr) -> str:
    if isinstance(expression, ast.Name):
        return expression.id
    if isinstance(expression, ast.Attribute):
        return expression.attr
    return ""


def _literal_keyword(
    call: ast.Call,
    keyword_name: str,
) -> object | None:
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue
        if isinstance(keyword.value, ast.Constant):
            return keyword.value.value
        return None
    return None


class _BehaviorConstructionVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self.scope: list[str] = []
        self.ordinals: defaultdict[tuple[str, str], int] = defaultdict(int)
        self.handlers: list[_HandlerConstruction] = []
        self.action_sources: list[_ActionSource] = []

    @property
    def scope_name(self) -> str:
        return ".".join(self.scope) if self.scope else "<module>"

    def _next_locator(self, inventory_kind: str) -> str:
        key = (self.scope_name, inventory_kind)
        self.ordinals[key] += 1
        return (
            f"{self.relative_path}:{self.scope_name}"
            f"#{inventory_kind}.{self.ordinals[key]}"
        )

    def _visit_scoped(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_scoped(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == "get_use_actions":
            self.action_sources.append(
                _ActionSource(
                    inventory_kind="get_use_actions_source",
                    locator=f"{self.relative_path}:{self.scope_name}.{node.name}",
                ),
            )
        self._visit_scoped(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_scoped(node)

    def visit_Call(self, node: ast.Call) -> None:
        terminal_name = _terminal_name(node.func)
        if terminal_name in {"EventHandler", "SpatialHandler"}:
            semantic_key = _literal_keyword(node, "semantic_key")
            toggleable = _literal_keyword(node, "player_toggleable")
            self.handlers.append(
                _HandlerConstruction(
                    locator=self._next_locator(
                        "event_handler_construction",
                    ),
                    semantic_identity=(
                        f"explicit:{semantic_key}"
                        if isinstance(semantic_key, str) and semantic_key
                        else "fallback"
                    ),
                    player_toggleable=(
                        str(toggleable).lower()
                        if isinstance(toggleable, bool)
                        else "false"
                    ),
                ),
            )

        action_source_kind = {
            "register_spell": "register_spell_source",
            "register_spells_by_name": "register_spells_by_name_source",
        }.get(terminal_name)
        if action_source_kind is not None:
            self.action_sources.append(
                _ActionSource(
                    inventory_kind=action_source_kind,
                    locator=self._next_locator(action_source_kind),
                ),
            )
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "register_action"
        ):
            inventory_kind = "register_action_source"
            self.action_sources.append(
                _ActionSource(
                    inventory_kind=inventory_kind,
                    locator=self._next_locator(inventory_kind),
                ),
            )
        for keyword in node.keywords:
            if keyword.arg == "use_action_templates":
                inventory_kind = "use_action_templates_source"
                self.action_sources.append(
                    _ActionSource(
                        inventory_kind=inventory_kind,
                        locator=self._next_locator(inventory_kind),
                    ),
                )
        self.generic_visit(node)


def _construction_inventory() -> tuple[
    tuple[_HandlerConstruction, ...],
    tuple[_ActionSource, ...],
]:
    handlers: list[_HandlerConstruction] = []
    action_sources: list[_ActionSource] = []
    for path in sorted(_DND_ROOT.rglob("*.py")):
        relative_path = path.relative_to(_ROOT).as_posix()
        visitor = _BehaviorConstructionVisitor(relative_path)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
        handlers.extend(visitor.handlers)
        action_sources.extend(visitor.action_sources)
    return tuple(handlers), tuple(action_sources)


def _notes(row) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for fragment in row.notes.split(";"):
        if not fragment:
            continue
        key, separator, value = fragment.partition("=")
        assert separator, f"Malformed structured note on {row.legacy_id}: {fragment}"
        parsed[key] = value
    return parsed


def _rows_by_inventory_kind(ledger) -> dict[str, list]:
    grouped: defaultdict[str, list] = defaultdict(list)
    for row in ledger.rows:
        inventory_kind = _notes(row).get("inventory")
        assert inventory_kind, f"{row.legacy_id} has no inventory note"
        grouped[inventory_kind].append(row)
    return dict(grouped)


def _nodeid_target_exists(nodeid: str) -> bool:
    path_text, separator, target = nodeid.partition("::")
    if not separator:
        return False
    path = _ROOT / path_text
    if not path.is_file():
        return False
    target_name = target.partition("[")[0]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == target_name
        for node in tree.body
    )


def test_every_current_behavior_definition_and_construction_site_is_accounted(
) -> None:
    ledger = _load_ledger()
    grouped = _rows_by_inventory_kind(ledger)
    handlers, action_sources = _construction_inventory()
    expected: dict[str, set[str]] = {
        "action_definition": _runtime_definition_locators(BaseAction),
        "condition_definition": _runtime_definition_locators(BaseCondition),
        "event_handler_construction": {
            construction.locator for construction in handlers
        },
    }
    for source_kind in (
        "register_action_source",
        "register_spell_source",
        "register_spells_by_name_source",
        "use_action_templates_source",
        "get_use_actions_source",
    ):
        expected[source_kind] = {
            source.locator
            for source in action_sources
            if source.inventory_kind == source_kind
        }

    assert set(grouped) == set(expected)
    for inventory_kind, expected_locators in expected.items():
        actual_locators = {
            row.legacy_locators[0]
            for row in grouped[inventory_kind]
        }
        assert actual_locators == expected_locators
        assert len(grouped[inventory_kind]) == len(actual_locators)


def test_public_spell_inventory_and_levels_are_exact() -> None:
    _import_all_dnd_modules()

    ledger = _load_ledger()
    spell_rows = {
        _notes(row)["public_spell_name"]: row
        for row in ledger.rows
        if _notes(row).get("registry") == "ALL_SPELLS"
    }
    expected_levels = {
        spell_name: int(spell_type.model_fields["spell_level"].default)
        for spell_name, spell_type in ALL_SPELLS.items()
    }
    actual_levels = {
        spell_name: int(_notes(row)["spell_level"])
        for spell_name, row in spell_rows.items()
    }
    assert actual_levels == expected_levels
    assert {
        row.legacy_locators[0]
        for row in spell_rows.values()
    } == {
        _definition_locator(spell_type)
        for spell_type in ALL_SPELLS.values()
    }
    assert all(
        row.classification
        == LegacyContentClassification.INDEPENDENT_DEFINITION
        for row in spell_rows.values()
    )


def test_non_catalog_spell_behaviors_are_explicitly_classified() -> None:
    ledger = _load_ledger()
    by_locator = {
        row.legacy_locators[0]: row
        for row in ledger.rows
        if _notes(row).get("inventory") == "action_definition"
    }

    aegis = by_locator["dnd/extensions/aegis_spark.py:AegisSpark"]
    assert (
        aegis.classification
        == LegacyContentClassification.INDEPENDENT_DEFINITION
    )
    assert aegis.provisional_ref is not None
    assert aegis.provisional_ref.pack_id == "content.neurodragon"
    assert aegis.provisional_ref.content_id == "spell.aegis_spark"
    assert _notes(aegis)["spell_level"] == "0"

    acid = by_locator["dnd/items/spell_items.py:_AcidFlaskSpell"]
    assert (
        acid.classification
        == LegacyContentClassification.ROOT_OWNED_BEHAVIOR
    )
    assert acid.provisional_ref is not None
    assert acid.provisional_ref.content_id == "spell.acid_flask"
    assert acid.provided_by_ref is not None
    assert acid.provided_by_ref.content_id == "consumable.acid_flask"
    assert _notes(acid)["spell_level"] == "0"

    test_bless = by_locator["dnd/spells/enchantment.py:TestBless"]
    assert (
        test_bless.classification
        == LegacyContentClassification.FIXTURE_ONLY
    )
    assert test_bless.provisional_ref is not None
    assert test_bless.provisional_ref.pack_id == "content.neurodragon"
    assert test_bless.provisional_ref.content_id == "spell.fixture.test_bless"
    assert _notes(test_bless)["spell_level"] == "1"


def test_action_rows_match_exact_authored_refs_and_provider_closure() -> None:
    """The migration ledger cannot retain provisional Python-shaped identity."""
    _import_all_dnd_modules()
    action_types_by_locator = {
        _definition_locator(action_type): action_type
        for action_type in _all_subclasses(BaseAction)
        if action_type.__module__.startswith("dnd.")
    }
    loaded = bootstrap_content_system(pack_roots=())

    def is_reachable(
        source_ref: ContentRef,
        target_ref: ContentRef,
    ) -> bool:
        pending = [loaded.registry.resolve_definition(source_ref)]
        visited: set[str] = set()
        while pending:
            declaration = pending.pop()
            identity = declaration.ref.identity_key
            if identity in visited:
                continue
            visited.add(identity)
            if declaration.ref == target_ref:
                return True
            for dependency in declaration.dependencies:
                pending.append(
                    loaded.registry.resolve_definition(
                        dependency.target_ref,
                    ),
                )
        return False

    for row in _load_ledger().rows:
        if _notes(row).get("inventory") != "action_definition":
            continue
        action_type = action_types_by_locator[row.legacy_locators[0]]
        try:
            declaration = get_content_declaration(action_type)
        except ValueError:
            assert (
                row.classification
                == LegacyContentClassification.ABSTRACT_MECHANISM
            )
            continue

        assert row.provisional_ref == declaration.ref
        if (
            row.classification
            != LegacyContentClassification.ROOT_OWNED_BEHAVIOR
        ):
            continue
        assert row.provided_by_ref is not None
        assert is_reachable(row.provided_by_ref, declaration.ref)


def test_internal_condition_markers_are_not_public_definitions() -> None:
    ledger = _load_ledger()
    internal_locators = {
        row.legacy_locators[0]
        for row in ledger.rows
        if (
            _notes(row).get("inventory") == "condition_definition"
            and row.classification
            == LegacyContentClassification.INTERNAL_RUNTIME_MARKER
        )
    }
    assert internal_locators == _EXPECTED_INTERNAL_CONDITION_LOCATORS


def test_condition_rows_match_exact_authored_refs_and_provider_identity(
) -> None:
    """Condition inventory destinations cannot remain provisional aliases."""
    _import_all_dnd_modules()
    condition_types_by_locator = {
        _definition_locator(condition_type): condition_type
        for condition_type in _all_subclasses(BaseCondition)
        if condition_type.__module__.startswith("dnd.")
    }
    loaded = bootstrap_content_system(pack_roots=())
    abstract_locators: set[str] = set()

    for row in _load_ledger().rows:
        if _notes(row).get("inventory") != "condition_definition":
            continue
        locator = row.legacy_locators[0]
        condition_type = condition_types_by_locator[locator]
        try:
            declaration = get_content_declaration(condition_type)
        except ValueError:
            assert row.classification in {
                LegacyContentClassification.ABSTRACT_MECHANISM,
                LegacyContentClassification.INTERNAL_RUNTIME_MARKER,
            }
            assert row.provisional_ref is None
            if (
                row.classification
                == LegacyContentClassification.ABSTRACT_MECHANISM
            ):
                assert row.provided_by_ref is None
                abstract_locators.add(locator)
            elif row.provided_by_ref is not None:
                loaded.registry.resolve_definition(row.provided_by_ref)
            continue

        assert row.classification not in {
            LegacyContentClassification.ABSTRACT_MECHANISM,
            LegacyContentClassification.INTERNAL_RUNTIME_MARKER,
        }
        assert row.provisional_ref == declaration.ref
        if (
            row.classification
            == LegacyContentClassification.ROOT_OWNED_BEHAVIOR
        ):
            assert row.provided_by_ref is not None
            loaded.registry.resolve_definition(row.provided_by_ref)

    assert abstract_locators == _EXPECTED_ABSTRACT_CONDITION_LOCATORS


def test_handler_identity_and_toggleability_inventory_is_exact() -> None:
    ledger = _load_ledger()
    handlers, _ = _construction_inventory()
    expected = {
        construction.locator: (
            construction.semantic_identity,
            construction.player_toggleable,
        )
        for construction in handlers
    }
    actual = {
        row.legacy_locators[0]: (
            _notes(row)["identity"],
            _notes(row)["player_toggleable"],
        )
        for row in ledger.rows
        if _notes(row).get("inventory") == "event_handler_construction"
    }
    assert actual == expected
    assert {
        locator: identity
        for locator, identity in actual.items()
        if identity[0] != "fallback"
    } == _EXPECTED_EXPLICIT_HANDLER_INVENTORY


def test_migration_destinations_are_semantic_and_complete() -> None:
    ledger = _load_ledger()
    assert len(ledger.rows) == len(ledger.rows_by_id)
    assert tuple(row.legacy_id for row in ledger.rows) == tuple(
        sorted(row.legacy_id for row in ledger.rows),
    )
    assert all(
        row.migration_status == LegacyMigrationStatus.INVENTORIED
        for row in ledger.rows
    )
    assert all(
        row.classification
        != LegacyContentClassification.APPROVED_DELETION
        for row in ledger.rows
    )
    assert set(row.classification for row in ledger.rows) == {
        LegacyContentClassification.INDEPENDENT_DEFINITION,
        LegacyContentClassification.ROOT_OWNED_BEHAVIOR,
        LegacyContentClassification.INTERNAL_RUNTIME_MARKER,
        LegacyContentClassification.ABSTRACT_MECHANISM,
        LegacyContentClassification.FIXTURE_ONLY,
    }
    for row in ledger.rows:
        if (
            row.classification
            == LegacyContentClassification.INDEPENDENT_DEFINITION
        ):
            assert row.provisional_ref is not None
        if (
            row.classification
            == LegacyContentClassification.ROOT_OWNED_BEHAVIOR
        ):
            assert row.provided_by_ref is not None
        for reference in (
            row.provisional_ref,
            row.provided_by_ref,
            row.replacement_ref,
            *row.dependency_refs,
        ):
            if reference is None:
                continue
            assert "/" not in reference.content_id
            assert ".py" not in reference.content_id
            assert ":" not in reference.content_id
            assert not reference.content_id.startswith("dnd.")


def test_every_measuring_nodeid_exists() -> None:
    ledger = _load_ledger()
    cited_nodeids = {
        nodeid
        for row in ledger.rows
        for nodeid in row.measuring_test_nodeids
    }
    assert _INVENTORY_TEST_NODEID in cited_nodeids
    missing = sorted(
        nodeid
        for nodeid in cited_nodeids
        if not _nodeid_target_exists(nodeid)
    )
    assert missing == []


def test_ledger_is_import_order_invariant() -> None:
    script = """
import hashlib
import importlib
import pkgutil
from pathlib import Path
import dnd
from dnd.core.content.inventory import LegacyContentMigrationLedger
names = sorted(
    module.name
    for module in pkgutil.walk_packages(dnd.__path__, prefix="dnd.")
)
if __import__("os").environ["BEHAVIOR_IMPORT_ORDER"] == "reverse":
    names.reverse()
for name in names:
    importlib.import_module(name)
ledger = LegacyContentMigrationLedger.model_validate_json(
    Path("content_data/ledgers/legacy_behaviors.json").read_text(encoding="utf-8")
)
print(hashlib.sha256(ledger.model_dump_json().encode("utf-8")).hexdigest())
"""
    digests: list[str] = []
    for import_order in ("forward", "reverse"):
        environment = dict(os.environ)
        environment["BEHAVIOR_IMPORT_ORDER"] = import_order
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        digests.append(result.stdout.strip())
    assert len(set(digests)) == 1
