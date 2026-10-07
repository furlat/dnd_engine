"""A rejected cold pack cannot leave a position for an event it rolled back."""

import subprocess
import sys
from uuid import uuid4


def test_failed_cold_pack_restores_the_native_event_position_index(tmp_path):
    identity = uuid4()
    pack = tmp_path / 'capture_index'
    package = pack / 'src' / 'fixture_capture_index'
    package.mkdir(parents=True)
    (pack / 'content-pack.toml').write_text('\n'.join((
        'schema_version = 1', 'pack_id = "fixture.capture_index"', 'pack_version = "1.0.0"',
        'engine_content_api = 2', 'python_root = "src"', 'python_package = "fixture_capture_index"',
    )))
    (package / '__init__.py').write_text('\n'.join((
        'from uuid import UUID',
        'from dnd.core.events import Event, EventType',
        f'Event(uuid=UUID({str(identity)!r}), source_entity_uuid=UUID({str(identity)!r}), event_type=EventType.BASE_ACTION)',
    )))
    # External packs load in a fresh process, before any encounter or dice exist.
    # Other tests legitimately retain dice, so exercise the real cold boundary.
    script = """
import sys
from pathlib import Path
from uuid import UUID
from dnd.content_system.pack_loader import load_content_system
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap
GridMap.reset()
EventQueue.reset()
try:
    load_content_system(pack_roots=(Path(sys.argv[1]),))
except RuntimeError as error:
    assert 'mutated engine runtime state' in str(error), str(error)
else:
    raise AssertionError('Mutating cold pack was accepted')
identity = UUID(sys.argv[2])
assert EventQueue.event_cursor() == 0
assert EventQueue.get_event_by_uuid(identity) is None
assert EventQueue.get_event_index(identity) is None
"""
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path), str(identity)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
