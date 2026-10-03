"""A second client receives the actual passive wire and authoring vocabulary."""

import json
from pathlib import Path
import subprocess
import sys


def test_schema_export_cold_start_has_no_native_or_raster_runtime(tmp_path):
    script = '''
import sys
from pathlib import Path
from game.export_schema import export_schemas
paths = export_schemas(Path(sys.argv[1]))
assert len(paths) == 16
for forbidden in ('dnd.entity', 'dnd.core.events', 'dnd.content_system.runtime', 'server', 'pygame'):
    assert forbidden not in sys.modules, forbidden
'''
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    schemas = {path.stem.removesuffix('.schema'): json.loads(path.read_text()) for path in tmp_path.glob('*.json')}
    expected_fields = {
        'damage-context': {'numberFrame', 'flashFrame', 'conditionFrame', 'deathFrame'},
        'death-context': {'equipmentHideFrame', 'bodyClip'},
        'attack-recipe': {'actor', 'anchors', 'variants', 'attackFeedback'},
        'voluntary-movement-context': {'walkClip', 'walkStepDurationMs', 'jumpBaseDurationMs', 'connectorProfiles'},
        'condition-recipe': {'application', 'persistent', 'removal'},
        'body-rig': {'clips'},
        'rig-tables': {'ANIM_FPS', 'FACING_ROW', 'CELL_W', 'CELL_H'},
    }
    for name, fields in expected_fields.items():
        assert schemas[name]['$schema'] == 'https://json-schema.org/draft/2020-12/schema'
        assert fields <= set(schemas[name]['properties']), name
    definitions = schemas['player-sequence-v2']['$defs']
    assert {'DamageRequestFact', 'DamageResultFact', 'EventResolutionRef', 'ApplicationResolutionRef'} <= definitions.keys()
