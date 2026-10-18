"""An observer's sense modes compare by a value that is the same in every process.

A seat's replay in a fresh process (another PYTHONHASHSEED) must rebuild the same client state, so the
published and folded sense-mode value cannot be a `hash()` of strings.
"""

import json
import os
from pathlib import Path
import subprocess
import sys

from dnd.blocks.sensory import capture_senses_snapshot
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state

ROOT = Path(__file__).resolve().parents[2]
PROBE = """
import json
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.sensory_fold import sense_modes_key
from dnd.types.senses import SenseMode, SensesType
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state
reset_senses_state(width=8, height=3)
observer = create_skeleton(name="Observer", position=(0, 1), darkvision=True)
modes = (SenseMode(sense_type=SensesType.TREMORSENSE, range_feet=30), SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
print(json.dumps([capture_senses_snapshot(observer.senses).sense_modes_key, sense_modes_key(modes)]))
"""


def _probe(seed: str) -> list:
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, capture_output=True, text=True, check=True,
                            env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(ROOT)})
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_sense_modes_compare_the_same_in_processes_with_different_hash_seeds():
    first, second = _probe("1"), _probe("2")
    assert first == second
    published, folded = first
    assert published == [["Darkvision", 60]]
    assert folded == [["Darkvision", 60], ["Tremorsense", 30]]


def test_a_published_snapshot_names_its_sense_modes():
    reset_senses_state(width=8, height=3)
    observer = create_skeleton(name="Observer", position=(0, 1), darkvision=True)
    assert capture_senses_snapshot(observer.senses).sense_modes_key == (("Darkvision", 60),)
