"""Generate production schema roots and report missing independently admitted models."""
import json
from pathlib import Path
from game.export_schema import export_schemas

destination = Path(".runtime/codebase-review-20261005/exported-schemas")
paths = export_schemas(destination)
documents = [json.loads(path.read_text()) for path in paths]
available = {document.get("title") for document in documents}
available.update(name for document in documents for name in document.get("$defs", {}))
print("exported_roots", len(paths))
for name in ("ConditionMediaDocument", "ConditionMediaSource", "ProjectileStorage", "AuthoredProjectileAsset",
             "ContentActionRecipe", "MovementPresentation", "InterruptionPresentation", "AttackProfileFile"):
    print(name, "PRESENT" if name in available else "ABSENT")
