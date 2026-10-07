"""Reproduce the planning inventory without importing the game or loading artwork.

Run from the engine root with Python. This inventories source coverage, not runtime
correctness. Family assignments describe proposed ownership, not completed ports.
"""

import ast
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
GROUPS = {
    "engine-player-boundary": "actor_facts actor_projection audience event_record player_commands player_facts player_projection presentation session ui_content_composition",
    "public-reduction": "player_reduction recording_compat",
    "authored-contracts": "animation_types asset_types body_pose_types condition_types interaction_types world_binding_types",
    "authoring-export": "animation_data authoring_conversion export_schema presentation_export",
    "presentation-semantics": "animation animation_rates attack body_action body_history body_hop body_presentation choreography combat condition_animation condition_reaction connector_motion construction_transitions damage entity_lifecycle feedback forced_movement interruption motion playback_frame presentation_group presentation_retained presentation_timing scene scene_actors spatial_field timing_evidence visual_position world_animation",
    "media-selection-and-lifetimes": "absence_media action_media cast_media cell_media concentration_media condition_media condition_media_lifetime condition_sampling construction_media construction_media_lifetime deposit_media directed_contacts directed_media directed_mesh_media directed_plasma_media environment_animation item_appearance item_attachment_lifetime maintained_media mechanism_projectile motion_media orbit_media particle_media portal_animation residue_media spatial_contact_media spatial_field_media spatial_media_lifetime spatial_response stationary_media surface_residue wall_assembly_media wall_media wall_profile weapon_trail_media wind_flow_media",
    "gpu-composition-and-materials": "app animation_draw area_media blood_draw body_effects boundary_occlusion choreography_draw component_particles concentration_draw condition_draw construction_surface deposit_draw device_draw directed_surface draw_commands environment_draw finite_material fixture_depth floor_composition interruption_draw item_draw item_effects media_blend media_coverage mechanism_projectile_draw object_dust portal_draw projection registered_media spatial_media_draw spatial_response_draw spell_palette stationary_draw sustained_draw thorns_surface volume_media water",
    "resources": "assets device_art environment_art portal_art projectile_media",
    "ui-and-input": "controls interaction_frame ui_composition",
    "replace-entrypoint-or-transport": "__init__ __main__ character_select combat_demo demo encounter_play play reference runtime_connection runtime_protocol runtime_worker",
    "recording-and-review-tools": "animation_preview presentation_coverage replay",
}
ASSIGNMENT = {name: group for group, names in GROUPS.items() for name in names.split()}


def fields(node):
    return [{"name": n.target.id, "type": ast.unparse(n.annotation), "line": n.lineno}
            for n in node.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]


def inventory():
    modules = []
    functions = []
    validators = []
    for path in sorted([*(ROOT / "game").glob("*.py"), *(ROOT / "game/ui").glob("*.py")]):
        relative = path.relative_to(ROOT).as_posix()
        if "assets" in path.relative_to(ROOT / "game").parts:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        group = ("ui-and-input" if path.parent.name == "ui" else ASSIGNMENT.get(path.stem))
        if group is None:
            raise ValueError(f"Unassigned module: {relative}")
        records = [{"name": node.name, "line": node.lineno, "fields": fields(node)}
                   for node in tree.body if isinstance(node, ast.ClassDef)]
        imports = sorted({n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
                         | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
        declared = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                declared.append((node.name, node))
            elif isinstance(node, ast.ClassDef):
                declared.extend((f"{node.name}.{child.name}", child) for child in node.body
                                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)))
        for name, node in declared:
            functions.append({"module": relative, "name": name, "line": node.lineno,
                              "end_line": node.end_lineno, "proposed_owner": group})
            decorators = [ast.unparse(d) for d in node.decorator_list]
            if any("validator" in d for d in decorators):
                validators.append({"module": relative, "name": name, "line": node.lineno,
                                   "decorators": "; ".join(decorators)})
        modules.append({"path": relative, "sha256": hashlib.sha256(source.encode()).hexdigest(),
                        "proposed_owner": group, "description": ast.get_docstring(tree) or "",
                        "imports": imports, "functions": len(declared), "records": records})
    catalog = next(m for m in modules if m["path"] == "game/animation_types.py")
    catalog_fields = next(r["fields"] for r in catalog["records"] if r["name"] == "AnimationData")
    public = next(m for m in modules if m["path"] == "game/player_facts.py")
    authored = [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted((ROOT / "game/data").rglob("*.json"))]
    result = {"status": "planning inventory; no runtime or migration acceptance",
              "module_count": len(modules), "function_count": len(functions),
              "catalog_fields": catalog_fields, "public_record_count": len(public["records"]),
              "authored_json": authored, "modules": modules}
    (OUT / "source-inventory.json").write_text(json.dumps(result, indent=2) + "\n")
    with (OUT / "function-port-ledger.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(functions[0]))
        writer.writeheader()
        writer.writerows(functions)
    with (OUT / "semantic-validator-ledger.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(validators[0]))
        writer.writeheader()
        writer.writerows(validators)
    lines = ["# Current source coverage", "", "Generated by `inventory.py`; proposed ownership, not completed ports.", "",
             "| Module | Proposed owner | Declared functions/methods |", "|---|---|---:|"]
    lines.extend(f"| `{m['path']}` | {m['proposed_owner']} | {m['functions']} |" for m in modules)
    (OUT / "module-port-ledger.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"modules": len(modules), "functions": len(functions),
                      "catalog_fields": len(catalog_fields), "public_records": len(public["records"]),
                      "authored_json_files": len(authored), "decorated_validators": len(validators)}))


if __name__ == "__main__":
    inventory()
