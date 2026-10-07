"""Export the actual passive player and authored presentation contracts.

Run: python -m game.export_schema OUTPUT_DIRECTORY
No server, asset loading, native registration or raster initialization is needed.
"""

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter

from dnd.player.facts import PlayerSequence
from game.presentation_export import PresentationCatalogExport
from game.animation_types import (StudioDraftFile, DamageContext, DeathContext, AttackRecipe,
    VoluntaryMovementContext, BodyRig, RigTables, EquipmentTransitionContext,
    HealingContext, DeathSaveContext, LifeStateContext, MovementReactionContext, ForcedMovementContext)
from game.condition_types import ConditionRecipe
from game.world_binding_types import WorldBindingsSource


def export_schemas(destination: Path) -> tuple[Path, ...]:
    destination.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, model in (("player-sequence-v2", PlayerSequence),
                        ("presentation-catalog-v1", PresentationCatalogExport),
                        ("presentation-drafts", StudioDraftFile),
                        ("world-bindings", WorldBindingsSource),
                        ("damage-context", DamageContext), ("death-context", DeathContext),
                        ("attack-recipe", AttackRecipe), ("voluntary-movement-context", VoluntaryMovementContext),
                        ("condition-recipe", ConditionRecipe), ("body-rig", BodyRig), ("rig-tables", RigTables),
                        ("equipment-transition-context", EquipmentTransitionContext), ("healing-context", HealingContext),
                        ("death-save-context", DeathSaveContext), ("life-state-context", LifeStateContext),
                        ("movement-reaction-context", MovementReactionContext), ("forced-movement-context", ForcedMovementContext)):
        path = destination / f"{name}.schema.json"
        schema = TypeAdapter(model).json_schema(mode="serialization")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    for path in export_schemas(parser.parse_args().destination):
        print(path)


if __name__ == "__main__":
    main()
