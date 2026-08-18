#!/usr/bin/env python3
"""Audit the gameplay-event -> NeuroClient presentation bridge.

This is a standalone developer tool, not an application package entry point.
It deliberately ignores sprite quality, bespoke art, and optional media.  Its
question is narrower: can every authored gameplay identity and every legal
transport variant reach a frontend intent/executor, or is the bridge broken?

Statuses have literal meanings:

* CONNECTED: the inspected bridge exists.
* INTENTIONAL_STATE_ONLY: the reducer/replica intentionally owns the result.
* BROKEN: a concrete current product path loses identity/data or rejects a
  legal transport value.
* NOT_SCANNED: source changed beyond a maintained check; this is a scanner
  limitation, never a claim that the product is broken.

The default exit is non-zero while BROKEN or NOT_SCANNED rows exist.  Use
--allow-broken to generate a report while known defects remain.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence


ENGINE_ROOT = Path(__file__).resolve().parents[1]
CLIENT_ROOT = Path("/home/tommaso/Dev/NeuroClient")
TOOLS_ROOT = Path(__file__).resolve().parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

CONNECTED = "CONNECTED"
STATE_ONLY = "INTENTIONAL_STATE_ONLY"
BROKEN = "BROKEN"
NOT_SCANNED = "NOT_SCANNED"


@dataclass(frozen=True)
class Evidence:
    file: str
    line: int
    detail: str


@dataclass
class Finding:
    id: str
    category: str
    status: str
    impact: str
    detail: str
    affected_ids: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Inventory:
    category: str
    total: int
    counts: dict[str, int]
    members: dict[str, str]


@dataclass
class Report:
    engine_root: str
    client_root: str
    inventories: list[Inventory]
    findings: list[Finding]
    facts: dict[str, int]
    audit_gaps: list[str]
    scanner_errors: list[str]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(text(path))


def line_of(path: Path, needle: str) -> int:
    source = text(path)
    offset = source.find(needle)
    return source.count("\n", 0, max(offset, 0)) + 1 if offset >= 0 else 0


def ev(path: Path, needle: str, detail: str) -> Evidence:
    return Evidence(str(path), line_of(path, needle), detail)


def has_throwing_guard(source: str, identifier: str) -> bool:
    """Return whether a TypeScript `if` guard on identifier throws."""
    def matching(start: int, opening: str, closing: str) -> int:
        depth = 0
        for offset in range(start, len(source)):
            if source[offset] == opening:
                depth += 1
            elif source[offset] == closing:
                depth -= 1
                if depth == 0:
                    return offset
        return -1

    for occurrence in re.finditer(rf"\b{re.escape(identifier)}\b", source):
        if_start = source.rfind("if", max(0, occurrence.start() - 500), occurrence.start())
        if if_start < 0 or not re.match(r"if\s*\(", source[if_start:]):
            continue
        condition_start = source.find("(", if_start, occurrence.start())
        condition_end = matching(condition_start, "(", ")")
        if condition_end < occurrence.end():
            continue
        block_start = source.find("{", condition_end, condition_end + 40)
        if block_start < 0:
            continue
        block_end = matching(block_start, "{", "}")
        if block_end > block_start and "throw " in source[block_start:block_end]:
            return True
    return False


def ref_key(ref: Any) -> tuple[str, str, str, int, str]:
    if hasattr(ref, "model_dump"):
        ref = ref.model_dump(mode="json")
    return (
        str(ref["pack_id"]),
        str(ref["definition_kind"]),
        str(ref["content_id"]),
        int(ref["content_version"]),
        str(ref["definition_contract_hash"]),
    )


def key_label(key: tuple[str, str, str, int, str]) -> str:
    pack, kind, content_id, version, contract = key
    return f"{pack}:{kind}:{content_id}@{version}#{contract[:12]}"


def identity_label(key: tuple[str, str, str, int, str]) -> str:
    """Human ContentRef identity without its separately validated contract hash."""
    pack, kind, content_id, version, _contract = key
    return f"{pack}:{kind}:{content_id}@{version}"


def inventory(category: str, members: dict[str, str]) -> Inventory:
    return Inventory(
        category=category,
        total=len(members),
        counts=dict(sorted(Counter(members.values()).items())),
        members=dict(sorted(members.items())),
    )


def extract_server_cues(path: Path) -> dict[str, str]:
    tree = ast.parse(text(path), filename=str(path))
    class_kinds: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            if not isinstance(statement.target, ast.Name) or statement.target.id != "kind":
                continue
            values = [
                child.value
                for child in ast.walk(statement.annotation)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            ]
            if values:
                class_kinds[node.name] = values[0]
    union_names: set[str] = set()
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.Assign):
            if any(isinstance(item, ast.Name) and item.id == "SubjectivePresentationCue" for item in node.targets):
                target, value = "SubjectivePresentationCue", node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "SubjectivePresentationCue":
                target, value = node.target.id, node.value or node.annotation
        if target and value is not None:
            union_names.update(item.id for item in ast.walk(value) if isinstance(item, ast.Name))
    return {
        kind: name
        for name, kind in class_kinds.items()
        if name in union_names
    }


def extract_registry_cues(path: Path) -> set[str]:
    source = text(path)
    start = source.find("PRESENTATION_CUE_CHANNELS")
    opening = source.find("{", start)
    if start < 0 or opening < 0:
        return set()
    depth = 0
    closing = -1
    for offset, char in enumerate(source[opening:], start=opening):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                closing = offset
                break
    if closing < 0:
        return set()
    return set(re.findall(
        r"(?m)^\s{2}([a-z][a-z0-9_]*):\s*\[",
        source[opening:closing],
    ))


def declaration(source: str, name: str) -> str:
    match = re.search(rf"(?:export\s+)?(?:interface|type)\s+{re.escape(name)}\b", source)
    if match is None:
        return ""
    nxt = re.search(r"(?m)^(?:export\s+)?(?:interface|type)\s+", source[match.end():])
    end = match.end() + nxt.start() if nxt else len(source)
    return source[match.start():end]


def intent_types(path: Path) -> set[str]:
    source = text(path)
    alias = re.search(r"export\s+type\s+ClipIntent\s*=([\s\S]*?);", source)
    if alias is None:
        return set()
    members = re.findall(r"\b([A-Z][A-Za-z0-9]*Intent)\b", alias.group(1))

    def resolve(name: str, seen: set[str]) -> set[str]:
        if name in seen:
            return set()
        block = declaration(source, name)
        direct = set(re.findall(r'\btype\s*:\s*"([A-Za-z0-9_]+)"', block))
        if direct:
            return direct
        refs = set(re.findall(r"\b([A-Z][A-Za-z0-9]*(?:Intent|IntentBase))\b", block))
        result: set[str] = set()
        for ref in refs - {name}:
            result.update(resolve(ref, seen | {name}))
        if not result and name.endswith("Intent"):
            result.update(resolve(name + "Base", seen | {name}))
        return result

    result: set[str] = set()
    for member in members:
        result.update(resolve(member, set()))
    return result


def dispatch_cases(path: Path) -> set[str]:
    source = text(path)
    start = source.find("async function dispatchIntent")
    end = source.find("\nfunction assertRequiredEntities", start)
    block = source[start:end if end >= 0 else len(source)]
    return set(re.findall(r'\bcase\s+"([A-Za-z0-9_]+)"\s*:', block))


def action_category(content_id: str) -> str:
    movement = {
        "action.move", "action.swim", "action.jump", "action.traverse_connector",
    }
    if content_id in movement:
        return "movement"
    if content_id.startswith("action.class.") or content_id.startswith("action.feature."):
        return "class_and_subclass_actions"
    if content_id.startswith("action.spell."):
        return "spell_followup_actions"
    if content_id.startswith("action.item."):
        return "item_actions"
    if content_id.startswith("action.environment."):
        return "environment_actions"
    if content_id.startswith(("action.monster.", "action.creature.", "action.trait.")):
        return "monster_trait_and_configured_actions"
    if content_id.startswith("action.origin."):
        return "origin_actions"
    return "universal_and_base_actions"


def execute_zero_application_spell_probe() -> dict[str, list[tuple[str, int]]]:
    """Execute the four known non-entity routes through canonical projection."""
    from dnd.content_system.bootstrap import bootstrap_content_system
    from dnd.content_system.item_bindings import ItemRuntimeOrigin
    from dnd.content_system.item_materialization import materialize_item
    from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
    from dnd.core.events import EventQueue
    from dnd.entities.entity import Entity
    from dnd.items.environment_content import OIL_BARREL_RECIPE, OilBarrel
    from dnd.spells.conjuration import DimensionDoor, HeroesFeast
    from dnd.spells.evocation import ContinualFlame
    from dnd.spells.infernal import Thaumaturgy
    from tests.engine.test_spell_families import (
        create_family_caster,
        reset_spell_family_state,
    )
    from tests.manual.test_121_canonical_presentation_mapper import (
        _perspective,
        _project_event_queue_since,
    )

    result: dict[str, list[tuple[str, int]]] = {}
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())

    def project(content_id: str, action: Any, caster: Any) -> None:
        Entity.update_all_entities_senses(max_distance=1000)
        cursor = EventQueue.event_cursor()
        terminal = action.apply()
        if terminal is None or terminal.canceled:
            raise RuntimeError(f"{content_id} did not complete successfully")
        frame, _slots = _project_event_queue_since(cursor, _perspective(caster.uuid))
        result[content_id] = [
            (cue.delivery.value, len(cue.targets))
            for cue in frame.presentation
            if cue.kind == "spell"
        ]

    reset_spell_family_state(width=20, height=20)
    caster = create_family_caster()
    project(
        "spell.thaumaturgy",
        Thaumaturgy(source_entity_uuid=caster.uuid, template=False),
        caster,
    )

    reset_spell_family_state(width=20, height=20)
    caster = create_family_caster(spell_slots={2: 1})
    target = materialize_item(
        OIL_BARREL_RECIPE,
        caster.uuid,
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=OilBarrel,
    )
    target.place_on_grid((2, 1))
    project(
        "spell.continual_flame",
        ContinualFlame(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            template=False,
        ),
        caster,
    )

    reset_spell_family_state(width=20, height=20)
    caster = create_family_caster(spell_slots={4: 1})
    project(
        "spell.dimension_door",
        DimensionDoor(
            source_entity_uuid=caster.uuid,
            end_position=(4, 4),
            template=False,
        ),
        caster,
    )

    reset_spell_family_state(width=20, height=20)
    caster = create_family_caster(spell_slots={6: 1})
    project(
        "spell.heroes_feast",
        HeroesFeast(
            source_entity_uuid=caster.uuid,
            end_position=(4, 4),
            template=False,
        ),
        caster,
    )
    return result


def validate_client_spell_materialization(
    spell_catalog: Sequence[Any],
    content_catalog: Any,
    client: Path,
) -> dict[str, Any]:
    """Run NeuroClient's real TS generator/validator over every backend row."""
    payload = {
        "catalog": [row.model_dump(mode="json") for row in spell_catalog],
        "contentCatalog": content_catalog.model_dump(mode="json"),
        "assets": load_json(client / "app/public/studio/spell-projectile-assets.json"),
        "drafts": load_json(client / "app/public/studio/spell-studio-drafts.json"),
    }
    source = """
      import { createServer } from "vite";
      let raw = "";
      for await (const chunk of process.stdin) raw += chunk;
      const input = JSON.parse(raw);
      const vite = await createServer({
        server: { middlewareMode: true },
        appType: "custom",
        logLevel: "silent",
      });
      try {
        const [
          mod,
          catalogMod,
          bundleMod,
          recipeMod,
          dispositionMod,
          contextMod,
          conditionMod,
          mediaMod,
          mapperMod,
          resolverMod,
          semanticsMod,
        ] = await Promise.all([
          vite.ssrLoadModule("/src/render/spellAuthoring/validation.ts"),
          vite.ssrLoadModule("/src/render/contentPresentationCatalog.ts"),
          vite.ssrLoadModule("/src/render/presentationBundle.ts"),
          vite.ssrLoadModule("/src/render/actionPresentationRecipes.ts"),
          vite.ssrLoadModule("/src/render/actionPresentationDispositions.ts"),
          vite.ssrLoadModule("/src/render/actionContextPresentation.ts"),
          vite.ssrLoadModule("/src/render/conditionPresentation.ts"),
          vite.ssrLoadModule("/src/render/actionMediaAssets.ts"),
          vite.ssrLoadModule("/src/render/subjectivePresentationMapper.ts"),
          vite.ssrLoadModule("/src/render/spellAuthoring/runtimeResolver.ts"),
          vite.ssrLoadModule("/src/render/subjectivePresentationSemantics.ts"),
        ]);
        const catalog = input.catalog.map(mod.backendSpellToCatalogEntry);
        const result = mod.buildLoadedSpellAuthoringData({
          catalog,
          projectileAssets: input.assets,
          studioDrafts: input.drafts,
        });
        const contentCatalog = catalogMod.createContentPresentationCatalogIndex(
          input.contentCatalog,
        );
        const bundle = bundleMod.compilePresentationBundle({
          actionRecipes: recipeMod.getContentActionPresentationRecipeFile(),
          actionDispositions:
            dispositionMod.getActionPresentationDispositionFile(),
          actionContexts: contextMod.getActionContextPresentationFile(),
          conditionRecipes: conditionMod.getConditionPresentationFile(),
          mediaAssets: mediaMod.getActionMediaAssetFile(),
          spellAuthoring: result,
        }, contentCatalog, 1);
        const entities = new Map([
          ["hero", {
            uuid: "hero", name: "Hero", position: [0, 0],
            conditions: [], condition_details: [],
          }],
          ["enemy", {
            uuid: "enemy", name: "Enemy", position: [2, 0],
            conditions: [], condition_details: [],
          }],
        ]);
        const mapContext = {
          entitiesById: entities,
          contentCatalog,
          presentationBundle: bundle,
          eventTypeDesigns: {},
          resolveAuthoredSpellPresentation(request) {
            return resolverMod.resolveAuthoredSpellPresentation(
              bundle.spellAuthoring,
              {
                entitiesById: entities,
                entitiesEquipmentById: new Map(),
                visualLoadoutByEntity: new Map(),
              },
              request,
            );
          },
          getEntityPosition(uuid) {
            return entities.get(uuid)?.position ?? null;
          },
          getEntityConditions(uuid) {
            return entities.get(uuid)?.conditions ?? [];
          },
        };
        const spellById = new Map(result.catalog.map((row) => [row.id, row]));
        function cueBase(id) {
          return {
            presentation_cursor: 1,
            presentation_id: id,
            parent_presentation_id: null,
            child_presentation_ids: [],
            source_event_cursor: 1,
            source_event_uuid: `event:${id}`,
            content_attributions: [],
          };
        }
        function behaviorAttribution(ref) {
          return {
            kind: "unrooted_behavior",
            role: "behavior",
            definition_ref: ref,
            provided_by_ref: ref,
          };
        }
        function spellCue(id, delivery, targets) {
          const row = spellById.get(id);
          if (!row) throw new Error(`missing spell fixture ${id}`);
          return {
            ...cueBase(`probe:${delivery}:${id}`),
            content_attributions: [behaviorAttribution(row.contentRef)],
            kind: "spell",
            actor_uuid: "hero",
            spell_id: id,
            spell_name: row.name,
            spell_school: row.school,
            spell_level: row.level,
            delivery,
            targets: targets.map((target, index) => ({
              application_index: index,
              application_id: `probe:${delivery}:${id}:${index}`,
              outcome: "automatic",
              target_uuid: target.target_uuid,
              position: target.position,
              effect_presentation_ids: [],
            })),
            projectile_type: row.projectileType,
            area: null,
          };
        }
        function probe(id, delivery, targets) {
          try {
            const groups = mapperMod.mapSubjectivePresentationCuesToClipGroups(
              [spellCue(id, delivery, targets)],
              mapContext,
            );
            return {
              accepted: true,
              intentTypes: groups.flatMap(
                (group) => group.intents.map((intent) => intent.type),
              ),
              deliveries: groups.flatMap(
                (group) => group.intents
                  .filter((intent) => intent.type === "cast")
                  .map((intent) => intent.delivery),
              ),
            };
          } catch (error) {
            return {
              accepted: false,
              error: error instanceof Error ? error.message : String(error),
            };
          }
        }
        const position = { target_uuid: null, position: [2, 0] };
        const entity = { target_uuid: "enemy", position: [2, 0] };
        const mappingProbes = {
          projectile_zero: probe("fire_bolt", "projectile", []),
          touch_zero: probe("cure_wounds", "touch", []),
          direct_zero: probe("healing_word", "direct", []),
          projectile_position:
            probe("fire_bolt", "projectile", [position]),
          missile_position:
            probe("magic_missile", "missile_volley", [position, entity]),
          touch_position: probe("cure_wounds", "touch", [position]),
          direct_position: probe("healing_word", "direct", [position]),
        };
        const definitionFamilies = {};
        const definitionRefs = {};
        for (const binding of bundle.bindings) {
          if (binding.identity.kind !== "definition") continue;
          definitionFamilies[binding.family] =
            (definitionFamilies[binding.family] ?? 0) + 1;
          (definitionRefs[binding.family] ??= []).push(binding.identity.ref);
        }
        const stateOnlyProbes = {
          door: semanticsMod.subjectiveStateOnlyReason({ kind: "door" }),
          light: semanticsMod.subjectiveStateOnlyReason({ kind: "light" }),
          spatial_effect:
            semanticsMod.subjectiveStateOnlyReason({ kind: "spatial_effect" }),
          equipment_none: semanticsMod.subjectiveStateOnlyReason({
            kind: "equipment",
            visual_loadout: { active_weapon_set: "none" },
          }),
          encounter_start: semanticsMod.subjectiveStateOnlyReason({
            kind: "encounter", transition: "start",
          }),
          encounter_turn_start: semanticsMod.subjectiveStateOnlyReason({
            kind: "encounter", transition: "turn_start",
          }),
        };
        process.stdout.write(JSON.stringify({
          catalog: result.catalog.length,
          drafts: result.studioDrafts.spells.length,
          warnings: result.warnings,
          statuses: Object.fromEntries(result.statusByContentRefKey),
          mappingProbes,
          bundleCoverage: bundle.coverage,
          definitionFamilies,
          definitionRefs,
          stateOnlyProbes,
        }));
      } finally {
        await vite.close();
      }
    """
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=client / "app",
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "NeuroClient spell materialization failed: "
            + (completed.stderr.strip() or completed.stdout.strip())
        )
    return json.loads(completed.stdout)


def build_report(engine: Path, client: Path) -> Report:
    from dnd.content_system.bootstrap import bootstrap_content_system
    from presentation_bridge_action_sites import (
        build_report as build_action_site_report,
    )
    from server.content_catalog import build_public_content_catalog
    from server.spell_catalog import build_spell_catalog

    errors: list[str] = []
    audit_gaps: list[str] = []
    findings: list[Finding] = []
    contract = engine / "server/player_replication_contract.py"
    server_mapper = engine / "server/player_replication/mapper.py"
    base_actions = engine / "dnd/core/base_actions.py"
    monster_traits = engine / "dnd/monsters/traits.py"
    evocation = engine / "dnd/spells/evocation.py"
    spell_items = engine / "dnd/items/spell_items.py"
    registry = client / "app/src/render/presentationChannelRegistry.ts"
    mapper = client / "app/src/render/subjectivePresentationMapper.ts"
    types = client / "app/src/render/types.ts"
    dispatcher = client / "app/src/render/dispatcher.ts"
    bundle = client / "app/src/render/presentationBundle.ts"
    context_source = client / "app/src/render/actionContextPresentation.ts"
    generated = client / "app/src/render/spellAuthoring/generatedBaseline.ts"
    resolver = client / "app/src/render/spellAuthoring/runtimeResolver.ts"
    event_ingestion = client / "app/src/engine/eventIngestion.ts"
    locomotion_owner = client / "app/src/render/LocomotionSessionExecutor.ts"
    move_clip = client / "app/src/render/clips/MoveClip.ts"

    loaded = bootstrap_content_system()
    action_site_report = build_action_site_report(engine)
    public_catalog = build_public_content_catalog(loaded)
    spell_catalog = build_spell_catalog().spells
    public_entries = list(public_catalog.entries)
    registry_declarations = {
        ref_key(row.ref): row for row in loaded.registry.declarations.values()
    }

    action_recipes_doc = load_json(client / "app/src/render/data/animation/contentActionPresentationRecipes.json")
    dispositions_doc = load_json(client / "app/src/render/data/animation/actionPresentationDispositions.json")
    condition_doc = load_json(client / "app/src/render/data/animation/conditionPresentation.json")
    client_action_rows = [
        *action_recipes_doc["recipes"], *dispositions_doc["entries"]
    ]
    client_action_key_rows = [
        ref_key(row["definitionRef"]) for row in client_action_rows
    ]
    client_action_keys = set(client_action_key_rows)
    client_condition_rows = condition_doc["recipes"]
    client_condition_key_rows = [
        ref_key(row["definitionRef"]) for row in client_condition_rows
    ]
    client_condition_keys = set(client_condition_key_rows)

    action_entries = [
        row for row in public_entries
        if row.ref.definition_kind.value in {"action", "reaction"}
    ]
    condition_entries = [
        row for row in public_entries
        if row.runtime_behavior_kind is not None
        and row.runtime_behavior_kind.value == "condition"
    ]
    public_spell_entries = [
        row for row in public_entries if row.ref.definition_kind.value == "spell"
    ]
    action_recipe_kinds = {
        ref_key(row["definitionRef"]): tuple(row.get("compatibleCueKinds", ()))
        for row in action_recipes_doc["recipes"]
    }
    public_action_keys = {ref_key(row.ref) for row in action_entries}
    public_condition_keys = {ref_key(row.ref) for row in condition_entries}
    missing_actions = sorted(
        key_label(ref_key(row.ref)) for row in action_entries
        if ref_key(row.ref) not in client_action_keys
    )
    extra_actions = sorted(
        key_label(key) for key in client_action_keys - public_action_keys
    )
    duplicate_actions = sorted(
        key_label(key) for key, count in Counter(client_action_key_rows).items()
        if count > 1
    )
    wrong_route_actions = sorted(
        key_label(key)
        for key in public_action_keys
        if key in action_recipe_kinds
        and registry_declarations.get(key) is not None
        and registry_declarations[key].runtime_behavior_kind is not None
        and registry_declarations[key].runtime_behavior_kind.value == "reaction"
        and not set(action_recipe_kinds[key])
        & {"action", "attack", "counterspell"}
    )
    missing_conditions = sorted(
        key_label(ref_key(row.ref)) for row in condition_entries
        if ref_key(row.ref) not in client_condition_keys
    )
    extra_conditions = sorted(
        key_label(key) for key in client_condition_keys - public_condition_keys
    )
    duplicate_conditions = sorted(
        key_label(key) for key, count in Counter(client_condition_key_rows).items()
        if count > 1
    )
    spell_catalog_keys = {ref_key(row.content_ref) for row in spell_catalog}
    public_spell_keys = {ref_key(row.ref) for row in public_spell_entries}

    public_seed_keys = {
        key for key, row in registry_declarations.items()
        if row.descriptor.visibility.value == "public"
    }
    reachable_keys = set(public_seed_keys)
    frontier = list(sorted(public_seed_keys))
    while frontier:
        current = frontier.pop()
        for dependency in registry_declarations[current].dependencies:
            target = ref_key(dependency.target_ref)
            if target not in registry_declarations:
                errors.append(
                    "Content dependency target is absent from the installed registry: "
                    + key_label(target)
                )
                continue
            if target not in reachable_keys:
                reachable_keys.add(target)
                frontier.append(target)
    presentation_runtime_kinds = {"action", "reaction", "spell", "condition"}
    reachable_runtime_keys = {
        key for key in reachable_keys
        if registry_declarations[key].runtime_behavior_kind is not None
        and registry_declarations[key].runtime_behavior_kind.value
        in presentation_runtime_kinds
    }
    exact_client_runtime_keys = (
        client_action_keys | client_condition_keys | spell_catalog_keys
    )
    missing_reachable_runtime_keys = sorted(
        reachable_runtime_keys - exact_client_runtime_keys
    )
    missing_reachable_runtime_labels = [
        key_label(key) for key in missing_reachable_runtime_keys
    ]

    server_cues = extract_server_cues(contract)
    registry_cues = extract_registry_cues(registry)
    mapper_source = text(mapper)
    map_cue_start = mapper_source.find("function mapCueUnchecked")
    map_cue_end = mapper_source.find("\nfunction mapAction", map_cue_start)
    map_cue_block = mapper_source[
        map_cue_start:map_cue_end if map_cue_end >= 0 else len(mapper_source)
    ]
    mapper_cases = set(re.findall(
        r'\bcase\s+"([a-z][a-z0-9_]*)"\s*:',
        map_cue_block,
    ))
    runtime_intents = intent_types(types)
    executor_cases = dispatch_cases(dispatcher)
    server_cue_set = set(server_cues)
    cue_extraction_ready = bool(
        server_cue_set
        and registry_cues
        and mapper_cases
        and map_cue_start >= 0
        and map_cue_end > map_cue_start
    )
    missing_registry_cues = sorted(server_cue_set - registry_cues)
    extra_registry_cues = sorted(registry_cues - server_cue_set)
    missing_mapper_cues = sorted(server_cue_set - mapper_cases)
    extra_mapper_cues = sorted(mapper_cases - server_cue_set)
    cue_gap = sorted(set(
        missing_registry_cues
        + extra_registry_cues
        + missing_mapper_cues
        + extra_mapper_cues
    ))
    intent_extraction_ready = bool(runtime_intents and executor_cases)
    missing_executor_intents = sorted(runtime_intents - executor_cases)
    extra_executor_intents = sorted(executor_cases - runtime_intents)
    intent_gap = sorted(set(missing_executor_intents + extra_executor_intents))
    findings.append(Finding(
        "structure.cue_to_mapper", "systemic",
        (
            NOT_SCANNED if not cue_extraction_ready
            else CONNECTED if not cue_gap
            else BROKEN
        ),
        "structural", (
            f"{len(server_cues)} canonical cue kinds; registry missing/extra="
            f"{missing_registry_cues}/{extra_registry_cues}; mapper missing/extra="
            f"{missing_mapper_cues}/{extra_mapper_cues}; extraction_ready="
            f"{cue_extraction_ready}"
        ),
        evidence=[ev(contract, "SubjectivePresentationCue", "canonical cue union"), ev(mapper, "function mapCueUnchecked", "exhaustive client mapper")],
    ))
    findings.append(Finding(
        "structure.intent_to_executor", "systemic",
        (
            NOT_SCANNED if not intent_extraction_ready
            else CONNECTED if not intent_gap
            else BROKEN
        ),
        "structural", f"{len(runtime_intents)} ClipIntent discriminants; "
        f"executor missing/extra={missing_executor_intents}/"
        f"{extra_executor_intents}; extraction_ready={intent_extraction_ready}",
        evidence=[ev(types, "export type ClipIntent", "runtime intent union"), ev(dispatcher, "async function dispatchIntent", "intent executor switch")],
    ))

    materialization: dict[str, Any] | None = None
    materialization_error: str | None = None
    try:
        materialization = validate_client_spell_materialization(
            spell_catalog,
            public_catalog,
            client,
        )
    except Exception as exc:  # scanner/tool failure, not a product verdict
        materialization_error = str(exc)
        errors.append(materialization_error)
    bundle_coverage = (
        materialization.get("bundleCoverage", {})
        if materialization is not None else {}
    )
    definition_families = (
        materialization.get("definitionFamilies", {})
        if materialization is not None else {}
    )
    compiled_definition_refs = (
        materialization.get("definitionRefs", {})
        if materialization is not None else {}
    )
    if materialization is not None:
        exact_client_runtime_keys = {
            ref_key(ref)
            for refs in compiled_definition_refs.values()
            for ref in refs
        }
        missing_reachable_runtime_keys = sorted(
            reachable_runtime_keys - exact_client_runtime_keys
        )
        missing_reachable_runtime_labels = [
            key_label(key) for key in missing_reachable_runtime_keys
        ]
    spell_materialization_exact = bool(
        materialization is not None
        and materialization.get("catalog") == len(spell_catalog)
        and materialization.get("drafts") == len(spell_catalog)
        and materialization.get("warnings") == []
        and len(materialization.get("statuses", {})) == len(spell_catalog)
    )
    bundle_definition_exact = bool(
        materialization is not None
        and bundle_coverage.get("missingDefinitionCount") == 0
        and definition_families.get("action") == len(client_action_keys)
        and definition_families.get("condition") == len(client_condition_keys)
        and definition_families.get("spell") == len(spell_catalog)
    )
    action_bundle_exact = bool(
        bundle_definition_exact
        and definition_families.get("action") == len(action_entries)
    )
    condition_bundle_exact = bool(
        bundle_definition_exact
        and definition_families.get("condition") == len(condition_entries)
    )

    action_definition_issues = [
        *(f"missing:{item}" for item in missing_actions),
        *(f"extra:{item}" for item in extra_actions),
        *(f"duplicate:{item}" for item in duplicate_actions),
        *(f"wrong_route:{item}" for item in wrong_route_actions),
    ]
    if action_definition_issues or (
        materialization is not None and not action_bundle_exact
    ):
        findings.append(Finding(
            "definitions.action_binding_gap", "systemic", BROKEN,
            "frame_blocking",
            "Public action/reaction definitions are not an exact validated "
            "one-to-one compiled bundle set.",
            action_definition_issues or [
                f"compiled_action_bindings="
                f"{definition_families.get('action')!r}; expected="
                f"{len(action_entries)}"
            ],
        ))
    elif materialization_error is not None:
        findings.append(Finding(
            "definitions.action_recipe_closure", "systemic", NOT_SCANNED,
            "scanner_failure",
            "The real presentation bundle compiler did not execute, so raw JSON "
            "set equality is not reported as compiled action closure.",
        ))
    else:
        findings.append(Finding(
            "definitions.action_recipe_closure", "systemic", CONNECTED,
            "structural",
            f"The real bundle compiler validated all {len(action_entries)} exact "
            "public action/reaction definitions with one recipe or explicit "
            "movement disposition. Runtime identity propagation is audited "
            "separately.",
            evidence=[ev(client / "app/src/render/data/animation/contentActionPresentationRecipes.json", '"recipes"', "exact action recipes"), ev(client / "app/src/render/data/animation/actionPresentationDispositions.json", '"entries"', "explicit movement dispositions")],
        ))
    condition_definition_issues = [
        *(f"missing:{item}" for item in missing_conditions),
        *(f"extra:{item}" for item in extra_conditions),
        *(f"duplicate:{item}" for item in duplicate_conditions),
    ]
    if condition_definition_issues or (
        materialization is not None and not condition_bundle_exact
    ):
        findings.append(Finding(
            "definitions.condition_binding_gap", "conditions", BROKEN,
            "frame_blocking",
            "Public condition identities are not an exact validated one-to-one "
            "compiled bundle set.",
            condition_definition_issues or [
                f"compiled_condition_bindings="
                f"{definition_families.get('condition')!r}; expected="
                f"{len(condition_entries)}"
            ],
        ))
    elif materialization_error is not None:
        findings.append(Finding(
            "definitions.condition_binding_gap", "conditions", NOT_SCANNED,
            "scanner_failure",
            "The real presentation bundle compiler did not execute, so raw JSON "
            "set equality is not reported as compiled condition closure.",
        ))
    if spell_catalog_keys != public_spell_keys:
        delta = sorted(key_label(key) for key in spell_catalog_keys ^ public_spell_keys)
        findings.append(Finding("definitions.spell_catalog_divergence", "spells", BROKEN, "frame_blocking", "Backend spell and public content catalogs disagree.", delta))
    elif materialization_error is not None:
        findings.append(Finding(
            "spells.generated_geometry_route", "spells", NOT_SCANNED,
            "scanner_failure",
            "NeuroClient's real spell generator/validator could not be executed: "
            + materialization_error,
        ))
    elif not spell_materialization_exact:
        findings.append(Finding(
            "spells.generated_geometry_route", "spells", BROKEN,
            "definition_materialization",
            "The real NeuroClient generator/validator did not materialize one exact "
            f"draft per backend spell without warnings: {materialization!r}",
        ))
    else:
        status_counts = Counter(materialization["statuses"].values())
        findings.append(Finding(
            "spells.generated_geometry_route", "spells", CONNECTED, "structural",
            f"NeuroClient's real compiler materialized structurally valid data-driven "
            f"recipes for all {len(spell_catalog)} backend spell rows without warnings "
            f"(statuses={dict(sorted(status_counts.items()))}); generated Pixi geometry "
            "is a first-class route and a spritesheet is not required. Global spell cue "
            "and CastIntent dispatcher closure is audited separately.",
            evidence=[ev(generated, "createGeneratedSpellPresentationDraft", "catalog row -> generated recipe"), ev(resolver, "resolveAuthoredSpellPresentation", "recipe -> runtime presentation")],
        ))

    findings.append(Finding(
        "definitions.reachable_runtime_identity_gap", "systemic",
        NOT_SCANNED if materialization_error is not None
        else BROKEN if missing_reachable_runtime_keys
        else CONNECTED,
        "frame_blocking",
        f"Dependency traversal from all {len(public_seed_keys)} public declarations "
        f"reaches {len(reachable_runtime_keys)} action/reaction/spell/condition "
        "runtime identities. Exact frontend bindings are missing for "
        f"{len(missing_reachable_runtime_keys)}: "
        f"{missing_reachable_runtime_labels}.",
        missing_reachable_runtime_labels,
    ))

    multiattack_ids = sorted(
        row.ref.content_id for row in action_entries
        if {"configured_action", "multiattack"}
        <= set(row.tags)
    )
    missing_runtime_ids = {
        registry_declarations[key].ref.content_id
        for key in missing_reachable_runtime_keys
    }
    action_event_block = text(base_actions)[text(base_actions).find("class ActionEvent"):text(base_actions).find("class BaseAction")]
    multiattack_configured_identity_lost = (
        "configured_action_ref" not in action_event_block
        and "configured_action_ref" not in text(server_mapper)[
            text(server_mapper).find("def _action_node"):
            text(server_mapper).find("def _light_node")
        ]
    )
    multiattack_internal_unbound = (
        "action.monster.multiattack" in missing_runtime_ids
    )
    multiattack_broken = multiattack_configured_identity_lost
    findings.append(Finding(
        "monster.multiattack_identity", "monster_trait_and_configured_actions",
        BROKEN if multiattack_broken else CONNECTED,
        "frame_blocking" if multiattack_internal_unbound
        else "transport_identity_drift",
        "All configured Multiattacks lose their public configured_action_ref; "
        + (
            "the root exposes an internal implementation ref with no frontend "
            "binding, and nested Attacks are unattributed."
            if multiattack_internal_unbound
            else "the configured presentation identity is still not transported."
        ),
        multiattack_ids,
        [ev(base_actions, "configured_action_ref", "identity exists on action discovery model"), ev(monster_traits, "class MultiattackAction", "composite runtime action"), ev(server_mapper, "def _action_node", "projection reads behavior binding only")],
    ))

    direct_site_exact = bool(action_site_report["exact_set_match"])
    installed_identity_labels = {
        identity_label(key) for key in registry_declarations
    }
    invalid_expected_site_refs: list[str] = []
    for row in action_site_report["sites"]:
        checked = row.get("checked_disposition")
        expected = checked.get("expected_identity_key") if checked else None
        if expected is not None and expected not in installed_identity_labels:
            invalid_expected_site_refs.append(f"{row['key']}->{expected}")
    if not direct_site_exact:
        errors.append(
            "Direct BaseAction site audit is not exact: missing="
            f"{action_site_report['missing_dispositions']}; stale="
            f"{action_site_report['stale_dispositions']}; unresolved_bases="
            f"{action_site_report['unresolved_class_bases']}; identity_errors="
            f"{action_site_report['identity_validation_errors']}; self_tests="
            f"{action_site_report['self_test_errors']}"
        )
    if invalid_expected_site_refs:
        errors.append(
            "Direct BaseAction site dispositions reference absent identities: "
            + repr(invalid_expected_site_refs)
        )
    findings.append(Finding(
        "actions.direct_apply_site_discovery", "systemic",
        CONNECTED if direct_site_exact and not invalid_expected_site_refs else NOT_SCANNED,
        "audit_authority",
        f"AST discovery found {action_site_report['action_class_descendant_count']} "
        f"BaseAction descendants and {action_site_report['site_count']} direct "
        "constructor-to-apply sites; the checked disposition ledger has exact set "
        f"equality={direct_site_exact}.",
    ))
    action_site_frame_blocking_ids: set[str] = set()
    multiattack_child_frame_blocking = False
    disposition_status = {
        "CONNECTED_EXPLICIT_BINDING": CONNECTED,
        "BROKEN_FRAME_BLOCKING": BROKEN,
        "BROKEN_SEMANTIC_OMISSION": BROKEN,
        "INTENTIONAL_STATE_ONLY": STATE_ONLY,
    }
    for row in action_site_report["sites"]:
        checked = row.get("checked_disposition")
        if checked is None:
            continue
        disposition = str(checked["disposition"])
        expected = checked.get("expected_identity_key")
        expected_content_id = (
            expected.split(":", 2)[2].rsplit("@", 1)[0]
            if expected is not None else None
        )
        if expected is not None and expected not in installed_identity_labels:
            status = NOT_SCANNED
        else:
            status = disposition_status[disposition]
        if row["action_class"] in {"dnd.actions.Move", "dnd.actions.Dash"}:
            category = "movement"
        elif expected is not None and ":reaction:" in expected:
            category = "reactions"
        elif expected is not None and ":spell:" in expected:
            category = "spells"
        elif expected_content_id is not None:
            category = action_category(expected_content_id)
        else:
            category = "monster_trait_and_configured_actions"
        affected = [expected_content_id] if expected_content_id else []
        if disposition == "BROKEN_FRAME_BLOCKING" and expected_content_id:
            action_site_frame_blocking_ids.add(expected_content_id)
        if (
            disposition == "BROKEN_FRAME_BLOCKING"
            and row["scope"] == "MultiattackAction._apply"
        ):
            multiattack_child_frame_blocking = True
            affected = list(multiattack_ids)
        finding_id = "direct_apply_site." + re.sub(
            r"[^a-z0-9]+", ".", str(row["scope"]).lower()
        ).strip(".")
        findings.append(Finding(
            finding_id, category, status,
            "frame_blocking" if disposition == "BROKEN_FRAME_BLOCKING"
            else "semantic_omission" if disposition == "BROKEN_SEMANTIC_OMISSION"
            else "connected",
            str(checked["detail"]),
            affected,
            [Evidence(
                str(engine / str(row["path"])),
                int(row["constructor"]["line"]),
                f"source-discovered {row['action_class']} constructor -> apply",
            )],
        ))
    acid_public_parents = sorted(
        declaration.ref.content_id
        for declaration in registry_declarations.values()
        if declaration.descriptor.visibility.value == "public"
        and any(
            dependency.target_ref.content_id == "spell.acid_flask"
            for dependency in declaration.dependencies
        )
    )
    acid_exact_client_join = "spell.acid_flask" in missing_runtime_ids
    findings.append(Finding(
        "item.acid_flask_spell_surface", "item_owned_spell_routes",
        BROKEN if acid_public_parents and acid_exact_client_join
        else CONNECTED if acid_public_parents
        else NOT_SCANNED,
        "frame_blocking",
        (
            "Acid Flask emits a private/OBSERVED spell behavior absent from the "
            "frontend spell definitions, so no draft can be resolved."
            if acid_exact_client_join
            else "Acid Flask's reachable private spell behavior has an exact "
            "frontend definition."
        ),
        acid_public_parents,
        [ev(spell_items, "class _AcidFlaskSpell", "private item spell"), ev(resolver, "No compiled spell presentation draft", "exact frontend catalog join")],
    ))

    projectile = sorted(
        f"spell.{row.id}" for row in spell_catalog
        if row.aoe_shape_type is None and row.projectile_type is not None
        and row.range_type not in {"self", "touch"}
        and row.target_type in {"entity", "multi_entity"}
    )
    touch = sorted(
        f"spell.{row.id}" for row in spell_catalog
        if row.aoe_shape_type is None and row.range_type == "touch"
        and row.target_type in {"entity", "multi_entity"}
    )
    direct = sorted(
        f"spell.{row.id}" for row in spell_catalog
        if row.aoe_shape_type is None and row.projectile_type is None
        and row.range_type not in {"self", "touch"}
        and row.target_type in {"entity", "multi_entity"}
    )
    privacy_by_delivery = {
        "projectile": projectile,
        "touch": touch,
        "direct": direct,
    }
    mapping_probes = (
        materialization.get("mappingProbes", {})
        if materialization is not None else {}
    )
    zero_target_probe_names = {
        "projectile": "projectile_zero",
        "touch": "touch_zero",
        "direct": "direct_zero",
    }
    server_privacy_filter_present = (
        "applications: list[_SpellApplication]" in text(server_mapper)
        and "if target_uuid is None or not _identity_allowed" in text(server_mapper)
    )
    privacy_broken_ids: set[str] = set()
    for delivery, ids in privacy_by_delivery.items():
        client_probe = mapping_probes.get(zero_target_probe_names[delivery])
        probe_ready = bool(
            isinstance(client_probe, dict)
            and isinstance(client_probe.get("accepted"), bool)
        )
        rejects_zero = bool(probe_ready and not client_probe["accepted"])
        if rejects_zero:
            privacy_broken_ids.update(ids)
        findings.append(Finding(
            f"spells.redacted_target_cardinality.{delivery}", "spells",
            (
                NOT_SCANNED if not server_privacy_filter_present or not probe_ready
                else BROKEN if rejects_zero
                else CONNECTED
            ),
            "conditional_frame_blocking",
            f"The server contract/projector permit {len(ids)} {delivery} spell "
            "definitions to reach an observer with caster identity but targets=[] "
            "after per-target privacy filtering; this is a source-derived conditional "
            f"variant set, not {len(ids)} replayed executions. "
            + (
                f"The real client mapper probe returned {client_probe}."
            ),
            ids if rejects_zero else [],
            [
                ev(server_mapper, "applications: list[_SpellApplication] = []", "target applications projected independently"),
                ev(server_mapper, "if target_uuid is None or not _identity_allowed", "per-target privacy filter"),
                ev(mapper, "function mapSpell", f"real zero-target {delivery} mapper probe"),
            ],
        ))
    position_probe_names = {
        "touch": "touch_position",
        "projectile": "projectile_position",
        "missile_volley": "missile_position",
        "direct": "direct_position",
    }
    contract_accepts_position = (
        "target_uuid: Optional[str] = None" in text(contract)
        and "position: Optional[Position] = None" in text(contract)
    )
    server_synthesizes_position = all(
        marker in text(server_mapper) for marker in (
            "isinstance(node.payload, _SpatialEffectPayload)",
            "target_uuid=None",
            "position=position",
            "parent_payload.applications.append(application_match)",
        )
    )
    position_probe_results = {
        delivery: mapping_probes.get(probe_name)
        for delivery, probe_name in position_probe_names.items()
    }
    position_probes_ready = all(
        isinstance(result, dict) and isinstance(result.get("accepted"), bool)
        for result in position_probe_results.values()
    )
    rejected_position_routes = sorted(
        delivery for delivery, result in position_probe_results.items()
        if isinstance(result, dict) and result.get("accepted") is False
    )
    position_route_status = (
        NOT_SCANNED
        if not contract_accepts_position
        or not server_synthesizes_position
        or not position_probes_ready
        else BROKEN if rejected_position_routes
        else CONNECTED
    )
    findings.append(Finding(
        "spells.position_application_routes", "spells",
        position_route_status,
        "contract_variant_frame_blocking",
        "SpellTargetPresentation permits entity-or-position applications and the "
        "server can synthesize a position application from an owned spatial effect. "
        f"Real client mapper probes={position_probe_results}; rejected routes="
        f"{rejected_position_routes}.",
        [f"spell.delivery.{delivery}:position" for delivery in rejected_position_routes],
        [
            ev(contract, "class SpellTargetPresentation", "entity-or-position application contract"),
            ev(server_mapper, "target_uuid=None", "spatial-effect position application synthesis"),
            ev(mapper, "function mapSpell", "real position-application mapper probes"),
        ],
    ))
    # Derive this from real successful actions and canonical subjective
    # projection. Route metadata alone cannot prove application cardinality.
    zero_application_probe = execute_zero_application_spell_probe()
    catalog_special_routes = sorted(
        f"spell.{row.id}" for row in spell_catalog
        if row.aoe_shape_type is None
        and row.target_type not in {"entity", "multi_entity"}
        and row.range_type != "self"
    )
    probed_routes = sorted(zero_application_probe)
    deterministic_zero_application = sorted(
        content_id
        for content_id, routes in zero_application_probe.items()
        if routes and all(count == 0 for _delivery, count in routes)
    )
    unexpected_zero_application_probe = sorted(
        content_id
        for content_id, routes in zero_application_probe.items()
        if not routes or any(count != 0 for _delivery, count in routes)
    )
    zero_application_probe_results: dict[str, Any] = {}
    rejected_zero_application: list[str] = []
    for content_id, routes in zero_application_probe.items():
        route_results = [
            mapping_probes.get(zero_target_probe_names.get(delivery, ""))
            for delivery, _count in routes
        ]
        zero_application_probe_results[content_id] = route_results
        if routes and all(
            isinstance(result, dict) and result.get("accepted") is False
            for result in route_results
        ):
            rejected_zero_application.append(content_id)
    rejected_zero_application.sort()
    client_zero_probe_drift = sorted(
        content_id
        for content_id, results in zero_application_probe_results.items()
        if not results or any(
            not isinstance(result, dict)
            or not isinstance(result.get("accepted"), bool)
            for result in results
        )
    )
    special_probe_drift = sorted(
        set(catalog_special_routes) ^ set(probed_routes)
    )
    findings.append(Finding(
        "spells.successful_zero_application", "spells",
        (
            NOT_SCANNED
            if unexpected_zero_application_probe
            or special_probe_drift
            or client_zero_probe_drift
            else BROKEN if rejected_zero_application
            else CONNECTED
        ),
        "frame_blocking",
        "The source-derived non-entity/non-self route set is executed through "
        "canonical projection. "
        f"catalog_routes={catalog_special_routes}; probe={zero_application_probe}; "
        f"route_set_drift={special_probe_drift}; client_mapper_probes="
        f"{zero_application_probe_results}; client_probe_drift="
        f"{client_zero_probe_drift}. "
        + (
            "The client rejects these ordinary successful zero-application frames."
            if rejected_zero_application
            else "The client accepts these zero-application frames."
        ),
        rejected_zero_application,
        [ev(engine / "tests/manual/test_121_canonical_presentation_mapper.py", "def _project_event_queue_since", "real EventQueue -> canonical projection"), ev(mapper, "function mapSpell", "real client mapper probes")],
    ))

    shape_fields = {
        "cone": ("angle_degrees", "angleDegrees"),
        "line": ("width_feet", "widthFeet"),
        "cylinder": ("height_feet", "heightFeet"),
    }
    cast_block = declaration(text(types), "CastIntent")
    area_projection = mapper_source[
        mapper_source.find("function projectCastAreaGeometry"):
        mapper_source.find("\nfunction directionalEndpoint")
    ]
    aoe_source = text(client / "app/src/render/clips/AoeFx.ts")
    aoe_options = declaration(aoe_source, "AoeSpawnOptions")
    for shape, (wire_field, runtime_field) in shape_fields.items():
        shape_ids = sorted(
            f"spell.{row.id}" for row in spell_catalog
            if row.aoe_shape_type == shape
        )
        contract_has = wire_field in text(contract)
        mapper_reads = f"area.{wire_field}" in area_projection
        intent_carries = (
            runtime_field in cast_block or wire_field in cast_block
        )
        options_carry = (
            runtime_field in aoe_options or wire_field in aoe_options
        )
        renderer_reads = (
            f"opts.{runtime_field}" in aoe_source
            or f"opts.{wire_field}" in aoe_source
        )
        connected = all((
            contract_has, mapper_reads, intent_carries,
            options_carry, renderer_reads,
        ))
        missing_layers = [
            label for label, present in (
                ("contract", contract_has),
                ("mapper", mapper_reads),
                ("CastIntent", intent_carries),
                ("AoeFx options", options_carry),
                ("AoeFx consumption", renderer_reads),
            ) if not present
        ]
        findings.append(Finding(
            f"spells.aoe_geometry_fidelity.{shape}", "spells",
            CONNECTED if connected else BROKEN,
            "authoritative_data_dropped",
            f"{shape} AoE executes, but authoritative {wire_field} is not closed "
            f"contract -> mapper -> CastIntent -> AoeFx; missing={missing_layers}.",
            [] if connected else shape_ids,
            [
                ev(contract, wire_field, f"authoritative {shape} field"),
                ev(mapper, "function projectCastAreaGeometry", "client projection"),
                ev(types, "export type CastIntent", "renderer intent"),
                ev(client / "app/src/render/clips/AoeFx.ts", "export interface AoeSpawnOptions", "renderer input"),
            ],
        ))

    spell_event_id_drift = (
        'spell_id=normalize_spell_id(self.name or "")' in text(engine / "dnd/actions.py")
        and 'name=f"True Strike ({label})"' in text(evocation)
    )
    findings.append(Finding(
        "spells.true_strike_wire_id", "spells",
        BROKEN if spell_event_id_drift else NOT_SCANNED,
        "transport_identity_drift",
        "True Strike variants emit spell_id=true_strike_melee/true_strike_ranged instead of catalog ID true_strike. Current client mapping survives only because it selects by behavior ContentRef.",
        ["true_strike_melee", "true_strike_ranged"],
        [ev(engine / "dnd/actions.py", 'spell_id=normalize_spell_id(self.name or "")', "wire ID derived from display name"), ev(evocation, 'name=f"True Strike ({label})"', "variant display names")],
    ))

    shove_mapper_block = mapper_source[
        mapper_source.find("function mapShove"):
        mapper_source.find("function mapItemAction")
    ]
    item_mapper_block = mapper_source[
        mapper_source.find("function mapItemAction"):
        mapper_source.find("function mapAttack")
    ]
    shove_transport_fields = {"actor_clip", "contact_frame", "playback_speed"}
    item_transport_fields = {
        "actor_clip", "effect_frame", "playback_speed", "hidden_slots",
    }
    ignored_shove_fields = sorted(
        field for field in shove_transport_fields
        if field in text(contract) and f"cue.{field}" not in shove_mapper_block
    )
    ignored_item_fields = sorted(
        field for field in item_transport_fields
        if field in text(contract) and f"cue.{field}" not in item_mapper_block
    )
    item_action_ids = sorted(
        row["definitionRef"]["content_id"]
        for row in action_recipes_doc["recipes"]
        if "item_action" in row.get("compatibleCueKinds", [])
    )
    findings.append(Finding(
        "actions.shove_contract_authority", "universal_and_base_actions",
        BROKEN if ignored_shove_fields else CONNECTED,
        "contract_authority_drift",
        "Shove transports actor/timing fields that the client ignores in favor "
        f"of the exact ContentRef recipe; ignored fields={ignored_shove_fields}.",
        ["action.shove"] if ignored_shove_fields else [],
        [ev(contract, "class ShovePresentationCue", "transported shove fields"), ev(mapper, "function mapShove", "client recipe selection")],
    ))
    findings.append(Finding(
        "items.item_action_contract_authority", "item_actions",
        BROKEN if ignored_item_fields else CONNECTED,
        "contract_authority_drift",
        "Item Action transports actor/timing/visibility fields that the client "
        f"ignores in favor of the exact ContentRef recipe; ignored fields="
        f"{ignored_item_fields}.",
        item_action_ids if ignored_item_fields else [],
        [ev(contract, "class ItemActionPresentationCue", "transported item fields"), ev(mapper, "function mapItemAction", "client recipe selection")],
    ))

    locomotion_runtime_source = text(move_clip) + "\n" + text(locomotion_owner)
    connector_unused = "intent.connector" not in locomotion_runtime_source
    elevation_unused = "elevationFeet" not in locomotion_runtime_source
    findings.append(Finding(
        "movement.connector_identity", "movement",
        BROKEN if connector_unused else CONNECTED, "authoritative_data_dropped",
        "Connector identity reaches MoveIntent but the locomotion executor consumes "
        "no connector presentation key/kind/revision; it executes as ordinary planar movement.",
        ["movement.connector.presentation_key"] if connector_unused else [],
        [ev(contract, "class ConnectorPresentationIdentity", "server identity"), ev(move_clip, "export async function run", "movement executor")],
    ))
    jump_clip = client / "app/src/render/clips/JumpClip.ts"
    elevation_runtime_source = locomotion_runtime_source + "\n" + text(jump_clip)
    elevation_unused = "elevationFeet" not in elevation_runtime_source
    findings.append(Finding(
        "movement.anchor_elevation", "movement",
        BROKEN if elevation_unused else CONNECTED, "authoritative_data_dropped",
        "Elevation reaches locomotion anchors but neither path movement nor JumpClip "
        "consumes it; vertical motion is not bridged from the backend anchor data.",
        ["movement.anchor.elevation_feet"] if elevation_unused else [],
        [ev(types, "export interface LocomotionAnchorIntent", "client carries elevation"), ev(jump_clip, "export async function run", "jump executor")],
    ))
    movement_runtime_test = (
        engine / "tests/manual/test_122_canonical_replication_runtime.py"
    )
    continuity_broken = (
        "assert len(movement_frames) == 3" in text(movement_runtime_test)
        and
        "await stopWalking()" in text(move_clip)
        and "activeBySourceGenerationEntity.delete(key)" in text(locomotion_owner)
    )
    findings.append(Finding(
        "movement.cross_head_body_continuity", "movement",
        BROKEN if continuity_broken else NOT_SCANNED, "runtime_continuity",
        "One server move can arrive as independent observation heads; each head ends Walking and deletes the locomotion session, so the client restarts the body cycle.",
        ["movement.multi_step_across_observation_heads"],
        [ev(movement_runtime_test, "assert len(movement_frames) == 3", "one move is delivered as three observation heads"), ev(move_clip, "await stopWalking()", "per-head walking settlement"), ev(locomotion_owner, "activeBySourceGenerationEntity.delete(key)", "per-head session retirement")],
    ))

    bundle_source = text(bundle)
    context_binding_start = bundle_source.find("const CONTEXT_BINDINGS")
    context_binding_end = bundle_source.find("const SYSTEM_BINDINGS", context_binding_start)
    context_binding_block = bundle_source[
        context_binding_start:
        context_binding_end if context_binding_end >= 0 else len(bundle_source)
    ]
    equipment_coverage_gap = (
        "equipment_transition" in text(context_source)
        and "equipment_transition" not in context_binding_block
        and "equipment.structural" in mapper_source
    )
    findings.append(Finding(
        "equipment.transition_coverage", "environment_and_equipment",
        BROKEN if equipment_coverage_gap else NOT_SCANNED,
        "coverage_gate",
        "SwitchWeapon executes from the authored equipment_transition context, but bundle coverage omits that context and reports equipment.structural instead.",
        ["equipment_transition"],
        [ev(context_source, '"equipment_transition"', "authored runtime context"), ev(bundle, "const CONTEXT_BINDINGS", "compiled context coverage"), ev(mapper, "equipment.structural", "reported provenance")],
    ))

    findings.append(Finding(
        "passive_proc.identity", "class_and_monster_passive_procs",
        NOT_SCANNED, "audit_boundary",
        "The catalog does not identify which class-feature/trait handlers produce "
        "gameplay activations, and HandlerDispatchEvidence omits the handler's "
        "existing BehaviorBinding. A static list would be a handwritten guess, so "
        "this tool refuses to claim exhaustive passive-proc bridge coverage. Add the "
        "existing binding snapshot to dispatch evidence, then this audit can join "
        "effected handlers to projected attribution without a new subsystem.",
        evidence=[ev(engine / "dnd/core/events.py", "RuntimeBehaviorKind.REACTION", "effective presentation retained only for reactions"), ev(server_mapper, "def _add_effective_handler_nodes", "handler evidence projection")],
    ))

    state_only_count = sum(row.get("disposition") == "state_only" for row in client_condition_rows)
    if not condition_definition_issues and condition_bundle_exact:
        findings.append(Finding(
            "conditions.explicit_dispositions", "conditions", CONNECTED, "structural",
            f"All {len(condition_entries)} public runtime condition identities have exact client dispositions; {state_only_count} are explicitly state-only.",
            evidence=[ev(client / "app/src/render/data/animation/conditionPresentation.json", '"recipes"', "condition disposition registry")],
        ))
    expected_state_only_probes = {
        "door": "door_reducer_state",
        "light": "light_reducer_state",
        "spatial_effect": "spatial_effect_reducer_state",
        "equipment_none": "unequipped_loadout_replacement",
        "encounter_start": "encounter_reducer_transition",
        "encounter_turn_start": None,
    }
    state_only_probes = (
        materialization.get("stateOnlyProbes", {})
        if materialization is not None else {}
    )
    reducer_state_only_exact = state_only_probes == expected_state_only_probes
    findings.append(Finding(
        "world.reducer_owned_cues", "environment_and_encounter",
        STATE_ONLY if reducer_state_only_exact else NOT_SCANNED, "structural",
        "The real shared semantic classifier marks door, light, spatial-effect "
        "lifecycle, equipment-none, and non-visual encounter transitions as "
        f"reducer/replica-owned; probes={state_only_probes}.",
        (["door", "light", "spatial_effect", "equipment:none", "encounter:structural"]
         if reducer_state_only_exact else []),
        [ev(mapper, 'case "door"', "state-only mapper branch"), ev(mapper, 'case "spatial_effect"', "state-only mapper branch")],
    ))
    ingestion_source = text(event_ingestion)
    settlement_call = ingestion_source.find(
        "settleStateOnlyEntityPositionPatches(preview.frame, renderWorld)"
    )
    settlement_prefix = ingestion_source[
        max(0, settlement_call - 500):settlement_call
    ]
    guard_match = re.search(r"if\s*\((\w+)\)\s*\{[\s\S]*$", settlement_prefix)
    settlement_guard = guard_match.group(1) if guard_match else None
    guard_definition_match = (
        re.search(
            rf"const\s+{re.escape(settlement_guard)}\s*=\s*\(([\s\S]*?)\);",
            ingestion_source,
        )
        if settlement_guard else None
    )
    state_settlement_broken = bool(
        guard_definition_match
        and "plan.kind === \"state_only\"" in guard_definition_match.group(1)
        and "presentation.length === 0" in guard_definition_match.group(1)
    )
    findings.append(Finding(
        "state_only.position_settlement", "systemic",
        BROKEN if state_settlement_broken else NOT_SCANNED, "render_state_divergence",
        "Entity-position settlement is limited to cue-empty state-only frames; a nonempty state-only cue plus position patch can leave the scene stale.",
        evidence=[ev(event_ingestion, 'frame.presentation.length === 0', "over-narrow settlement predicate")],
    ))
    bootstrap = client / "app/src/render/presentationBundleBootstrap.ts"
    exact_definition_gate = (
        has_throwing_guard(text(bundle), "missingDefinitionRefs")
        or has_throwing_guard(text(bundle), "missingDefinitionCount")
        or has_throwing_guard(text(bootstrap), "missingDefinitionCount")
    )
    gate_broken = not exact_definition_gate
    findings.append(Finding(
        "authoring.missing_definition_gate", "audit_authority",
        BROKEN if gate_broken else NOT_SCANNED, "coverage_gate",
        "The bundle computes missingDefinitionRefs and bootstrap reports a "
        "control-plane diagnostic, but the bundle is still published when every "
        "cue kind has some binding. Missing exact definition ownership is diagnosed "
        "without being enforced as an authoring/install gate.",
        evidence=[ev(bundle, "const missingDefinitionRefs", "exact missing rows computed"), ev(bundle, "coverage.cueKinds[cueKind] === 0", "aggregate-only compile gate"), ev(bootstrap, "missingDefinitionCount", "diagnostic-only bootstrap handling")],
    ))

    # This inventory is deliberately definition-only. Runtime identity,
    # cardinality and field-consumption failures are the findings below; mixing
    # those axes made earlier coverage reports actively misleading.
    by_category: dict[str, dict[str, str]] = {}
    for row in action_entries:
        key = ref_key(row.ref)
        category = (
            "reactions" if row.ref.definition_kind.value == "reaction"
            else action_category(row.ref.content_id)
        )
        by_category.setdefault(category, {})[key_label(key)] = (
            CONNECTED if key in client_action_keys and action_bundle_exact
            else NOT_SCANNED if materialization_error is not None
            else BROKEN
        )
    spell_definition_status = (
        CONNECTED
        if spell_catalog_keys == public_spell_keys and spell_materialization_exact
        else NOT_SCANNED if materialization_error is not None
        else BROKEN
    )
    spell_members = {
        key_label(ref_key(row.content_ref)): spell_definition_status
        for row in spell_catalog
    }
    by_category["spells"] = spell_members
    client_condition_by_key = {
        ref_key(row["definitionRef"]): row for row in client_condition_rows
    }
    condition_members: dict[str, str] = {}
    for row in condition_entries:
        key = ref_key(row.ref)
        client_row = client_condition_by_key.get(key)
        condition_members[key_label(key)] = (
            NOT_SCANNED if materialization_error is not None
            else BROKEN if client_row is None or not condition_bundle_exact
            else STATE_ONLY if client_row.get("disposition") == "state_only"
            else CONNECTED
        )
    by_category["conditions"] = condition_members

    if any(item.status == NOT_SCANNED for item in findings):
        audit_gaps.append(
            "At least one audit surface is NOT_SCANNED; the default command "
            "fails rather than pretending the report is exhaustive."
        )
    deterministic_identity_ids = set(action_site_frame_blocking_ids)
    if multiattack_internal_unbound or multiattack_child_frame_blocking:
        deterministic_identity_ids.update(multiattack_ids)
    acid_finding = next(
        finding for finding in findings
        if finding.id == "item.acid_flask_spell_surface"
    )
    if acid_finding.status == BROKEN:
        deterministic_identity_ids.update(acid_finding.affected_ids)
    public_spell_ids = {f"spell.{row.id}" for row in spell_catalog}
    spell_identity_blockers = (
        deterministic_identity_ids & public_spell_ids
    )
    zero_application_ids = (
        rejected_zero_application
        if next(
            finding.status for finding in findings
            if finding.id == "spells.successful_zero_application"
        ) == BROKEN
        else []
    )
    facts = {
        "public_content_rows": len(public_entries),
        "public_dependency_closure_rows": len(reachable_keys),
        "public_action_and_reaction_rows": len(action_entries),
        "public_spell_rows": len(spell_catalog),
        "public_runtime_condition_rows": len(condition_entries),
        "public_reachable_presentation_runtime_identities": len(
            reachable_runtime_keys
        ),
        "reachable_runtime_identities_without_frontend_binding": len(
            missing_reachable_runtime_keys
        ),
        "server_cue_kinds": len(server_cues),
        "runtime_intent_kinds": len(runtime_intents),
        "deterministic_identity_frame_blocking_entry_points": len(
            deterministic_identity_ids
        ),
        "deterministic_zero_application_spell_entry_points": len(zero_application_ids),
        "known_deterministic_frame_blocking_entry_points": len(
            deterministic_identity_ids | set(zero_application_ids)
        ),
        "privacy_variant_frame_blocking_spells": len(privacy_broken_ids),
        "public_spells_with_known_frame_blocking_variant": len(
            set(privacy_broken_ids)
            | set(rejected_zero_application)
            | spell_identity_blockers
        ),
    }
    return Report(
        str(engine), str(client),
        [inventory(name, members) for name, members in sorted(by_category.items())],
        findings, facts, audit_gaps, errors,
    )


def render_markdown(report: Report) -> str:
    lines = [
        "# Gameplay presentation bridge audit", "",
        "This report excludes sprite/art quality. `BROKEN` means a concrete current bridge defect; `NOT_SCANNED` means only that this tool needs updating. Current `projectile`/`touch`/`direct`/`missile_volley` labels below name the renderer-shaped contract being audited; they are not endorsed as the neutral target contract. The action hard-cut plan deletes backend spell route and morphology authority.", "",
        "## Run", "",
        "```bash",
        ".venv/bin/python -B tools/audit_presentation_bridge.py \\",
        "  --markdown tools/PRESENTATION_BRIDGE_AUDIT.md \\",
        "  --json tools/PRESENTATION_BRIDGE_AUDIT.json",
        "```", "",
        "The strict command writes both reports and exits non-zero for any "
        "`BROKEN`, `NOT_SCANNED`, or scanner-error result. Add `--allow-broken` "
        "only when deliberately refreshing the known-defect snapshot.", "",
        "## Facts", "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in report.facts.items())
    lines.extend([
        "", "## Static definition-binding closure by category", "",
        "`CONNECTED` here means the exact public definition has a compiled client "
        "binding. It is not a runtime verdict; transport variants, identity loss, "
        "and continuity are reported separately below.",
        "", "| Category | Total | Status counts |", "|---|---:|---|",
    ])
    for row in report.inventories:
        counts = ", ".join(f"{key}={value}" for key, value in row.counts.items())
        lines.append(f"| `{row.category}` | {row.total} | {counts} |")
    actionable_by_category: dict[str, list[Finding]] = {}
    for finding in report.findings:
        if finding.status in {BROKEN, NOT_SCANNED}:
            actionable_by_category.setdefault(finding.category, []).append(finding)
    lines.extend([
        "", "## Runtime bridge defects by category", "",
        "Counts in parentheses are affected identities/variants for that check; "
        "they are not added together because checks can overlap.", "",
        "| Category | Broken checks | Audit gaps |", "|---|---|---|",
    ])
    for category, category_findings in sorted(actionable_by_category.items()):
        broken = ", ".join(
            f"`{item.id}` ("
            + (
                str(len(item.affected_ids))
                if item.affected_ids else "not independently enumerated"
            )
            + ")"
            for item in category_findings if item.status == BROKEN
        ) or "—"
        gaps = ", ".join(
            f"`{item.id}`" for item in category_findings
            if item.status == NOT_SCANNED
        ) or "—"
        lines.append(f"| `{category}` | {broken} | {gaps} |")
    lines.extend(["", "## Exact findings", "", "| Status | Category | Impact | Finding | Affected |", "|---|---|---|---|---:|"])
    for finding in report.findings:
        affected = str(len(finding.affected_ids)) if finding.affected_ids else "—"
        lines.append(
            f"| **{finding.status}** | `{finding.category}` | `{finding.impact}` | "
            f"`{finding.id}` — {finding.detail} | {affected} |"
        )
    lines.extend(["", "## Affected IDs", ""])
    for finding in report.findings:
        if finding.affected_ids:
            lines.append(
                f"- `{finding.id}`: "
                + ", ".join(f"`{item}`" for item in finding.affected_ids)
            )
    lines.extend(["", "## Evidence", ""])
    for finding in report.findings:
        if not finding.evidence:
            continue
        lines.append(f"- `{finding.id}`")
        for item in finding.evidence:
            lines.append(f"  - `{item.file}:{item.line}` — {item.detail}")
    if report.audit_gaps:
        lines.extend(["", "## Audit gaps", ""])
        lines.extend(f"- {item}" for item in report.audit_gaps)
    if report.scanner_errors:
        lines.extend(["", "## Scanner errors", ""])
        lines.extend(f"- {item}" for item in report.scanner_errors)
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, default=ENGINE_ROOT)
    parser.add_argument("--client-root", type=Path, default=CLIENT_ROOT)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--allow-broken", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    report = build_report(args.engine_root.resolve(), args.client_root.resolve())
    markdown = render_markdown(report)
    if args.markdown:
        args.markdown.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    if args.json:
        args.json.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    blocking = (
        report.scanner_errors
        or report.audit_gaps
        or any(item.status in {BROKEN, NOT_SCANNED} for item in report.findings)
    )
    return 0 if args.allow_broken or not blocking else 1


if __name__ == "__main__":
    raise SystemExit(main())
