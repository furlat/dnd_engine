"""`creates` declarations: what an object's content can create in play is built when the object is created.

Conditions and actions defer their pydantic schema to first use. Creating an
object builds the closure of its class's `creates` (`build_creatable_models`),
so every model class a class's code can create must be in that closure, or a
gameplay operation builds its schema.

The source check reads each engine model class (and the module functions its
code calls) and collects the model classes it creates:

- a call `X(...)`, `module.X(...)` or `X.create(...)` / `X.model_validate(...)`;
- a class named as a value (a ClassVar, a mapping, a returned type, a local
  `kind = A if c else B`): a factory the code calls later;
- a call through a module mapping of classes (`TABLE[key](...)`).

A product counts when building it can matter: its schema is deferred or it
declares products of its own. Typing uses (`isinstance`, `cast`, annotations,
comparisons, `X.attribute`) are not creations.
"""

import ast
import importlib
import inspect
import pkgutil
import sys
from collections.abc import Mapping

import dnd
import server.worker  # noqa: F401  (imports every built-in content module)
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.content_system.creature_possessions import apply_creature_possessions
from dnd.monsters import srd_roster
from dnd.spells.summoning import SummonSpell
from dnd.summoning.forms import SUMMON_FORMS


# What the source check cannot see, each with the reason its declaration is by hand.
UNRESOLVED_CREATIONS = {
    "dnd.spatial.environmental_conditions.OilSurface": "ignition replaces it through a transition recipe that "
        "build_environmental_replacement maps to FireSurface",
}
# Registry lookups the check resolves itself:
# - a summon form's creature comes from its content recipe's factory (content registry);
# - an SRD creature's configurer is chosen by creature id (srd_roster._CONFIGURE_SRD_CREATURE_BY_ID),
#   so `construct_srd_creature(context, "dretch")` follows that one configurer, never the whole table;
# - a summon's possessions are its intrinsic weapons only, so the item builders that
#   apply_creature_possessions selects by item id are not part of a summon form's content.
SRD_CONFIGURERS = srd_roster._CONFIGURE_SRD_CREATURE_BY_ID
CONSTRUCTORS = frozenset({"create", "model_validate", "model_validate_json", "model_construct"})
TYPING_CALLS = frozenset({"isinstance", "issubclass", "cast", "type", "get_content_declaration"})


def _subclasses(root: type) -> list[type]:
    found, stack = [], [root]
    while stack:
        for subclass in stack.pop().__subclasses__():
            if subclass not in found:
                found.append(subclass)
                stack.append(subclass)
    return found


for _module in pkgutil.walk_packages(dnd.__path__, "dnd."):
    importlib.import_module(_module.name)
MODELS = frozenset((BaseObject, BaseBlock, *_subclasses(BaseObject), *_subclasses(BaseBlock)))
_TREES: dict[str, ast.Module] = {}


def _closure(model: type) -> set[type]:
    seen, pending = set(), list(model.creates)
    while pending:
        product = pending.pop()
        if product not in seen:
            seen.add(product)
            pending.extend(product.creates)
    return seen


def _counts(model: object) -> bool:
    return (inspect.isclass(model) and model in MODELS
            and (bool(model.model_config.get("defer_build")) or bool(model.creates)))


def _node(owner: object) -> ast.AST | None:
    module = owner.__module__
    if module not in _TREES:
        _TREES[module] = ast.parse(inspect.getsource(sys.modules[module]))
    node: ast.AST | None = _TREES[module]
    if inspect.isfunction(owner):
        # By its code's first line: factories may be closures renamed after their content.
        line = owner.__code__.co_firstlineno
        return next((child for child in ast.walk(node) if isinstance(child, ast.FunctionDef)
                     and min((child.lineno, *(decorator.lineno for decorator in child.decorator_list))) == line), None)
    for part in owner.__qualname__.split("."):
        node = next((child for child in ast.iter_child_nodes(node)
                     if isinstance(child, (ast.ClassDef, ast.FunctionDef)) and child.name == part), None)
        if node is None:
            return None
    return node


def _resolve(expression: ast.expr, namespace: Mapping[str, object]) -> object:
    if isinstance(expression, ast.Name):
        return namespace.get(expression.id)
    if isinstance(expression, ast.Attribute):
        base = _resolve(expression.value, namespace)
        if inspect.ismodule(base):
            return vars(base).get(expression.attr)
        if inspect.isclass(base) and base in MODELS and expression.attr in CONSTRUCTORS:
            return base
    return None


def _created(owner: object, visited: set[object]) -> set[type]:
    """Model classes `owner`'s code creates, following the dnd module functions it calls."""
    if owner in visited:
        return set()
    visited.add(owner)
    node = _node(owner)
    if node is None:
        return set()
    namespace = vars(sys.modules[owner.__module__])
    typing_nodes: set[int] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id in TYPING_CALLS:
            typing_nodes.update(id(part) for argument in child.args for part in ast.walk(argument))
        for annotation in (getattr(child, "annotation", None), getattr(child, "returns", None)):
            if isinstance(annotation, ast.expr):
                typing_nodes.update(id(part) for part in ast.walk(annotation))
        if isinstance(child, ast.Compare):
            typing_nodes.update(id(part) for part in ast.walk(child))
        if isinstance(child, ast.ClassDef):
            typing_nodes.update(id(part) for base in (*child.bases, *child.keywords, *child.decorator_list)
                                for part in ast.walk(base))
        for parameter in getattr(child, "type_params", ()):
            typing_nodes.update(id(part) for part in ast.walk(parameter))
        if isinstance(child, ast.Attribute) and child.attr not in CONSTRUCTORS:
            typing_nodes.add(id(child.value))
    created: set[type] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            target = _resolve(child.func, namespace)
            if target is srd_roster.construct_srd_creature:
                creature = child.args[1] if len(child.args) > 1 else None
                if isinstance(creature, ast.Constant):
                    created |= _created(SRD_CONFIGURERS[creature.value], visited)
                continue
            if _counts(target):
                created.add(target)
            elif (inspect.isfunction(target) and target.__module__.startswith("dnd.")
                    and target.__module__ in sys.modules):
                created |= _created(target, visited)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            value = namespace.get(child.id)
            if _counts(value) and id(child) not in typing_nodes:
                created.add(value)
            elif isinstance(value, Mapping):
                # A dispatch table (`TABLE[key](...)`, `TABLE.get(key)`): any of its entries may run.
                for entry in tuple(value.values()):
                    if _counts(entry):
                        created.add(entry)
                    elif inspect.isfunction(entry) and entry.__module__.startswith("dnd."):
                        created |= _created(entry, visited)
    return created


def test_every_creatable_model_is_built_at_creation():
    missing = {}
    for model in sorted(MODELS, key=lambda model: (model.__module__, model.__qualname__)):
        if not model.__module__.startswith("dnd.") or _node(model) is None:
            continue
        lacking = {product for product in _created(model, set())
                   if product is not model} - _closure(model)
        if lacking:
            missing[f"{model.__module__}.{model.__qualname__}"] = sorted(product.__qualname__ for product in lacking)
    assert missing == {}


def test_a_summon_spell_builds_its_forms_content():
    """A summoned creature is created in the cast; its form's content is built with the summoner's spell."""
    registry = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry
    by_family: dict[object, set[type]] = {}
    for form in SUMMON_FORMS:
        factory = registry.resolve_factory(form.recipe.ref).construction.factory
        products = _created(factory, {apply_creature_possessions})
        if factory.__module__ == srd_roster.__name__:
            products |= _created(SRD_CONFIGURERS[form.recipe.ref.content_id.removeprefix("creature.")],
                {apply_creature_possessions})
        by_family.setdefault(form.family, set()).update(products)
    missing = {}
    for spell in MODELS:
        if issubclass(spell, SummonSpell) and spell is not SummonSpell:
            lacking = by_family[spell.model_fields["family"].default] - _closure(spell)
            if lacking:
                missing[spell.__qualname__] = sorted(product.__qualname__ for product in lacking)
    assert missing == {}


def test_unresolved_creations_are_still_declared():
    """Each by-hand entry names a live class that declares products."""
    declared = {f"{model.__module__}.{model.__qualname__}": model for model in MODELS}
    assert {name: bool(declared[name].creates) for name in UNRESOLVED_CREATIONS if name in declared} == {
        name: True for name in UNRESOLVED_CREATIONS}


def test_a_subclass_creates_everything_its_parents_create():
    dropped = []
    for model in MODELS:
        for base in model.__bases__:
            if base in MODELS:
                lost = set(base.creates) - set(model.creates)
                if lost:
                    dropped.append((f"{model.__module__}.{model.__qualname__}", base.__qualname__,
                        sorted(product.__qualname__ for product in lost)))
    assert dropped == []
