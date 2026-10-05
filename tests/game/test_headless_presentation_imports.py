"""The shared presentation binder must not import native execution or initialize graphics."""

from pathlib import Path
import subprocess
import sys


def test_binding_and_catalog_load_without_graphics_import():
    program = '''
import sys
class RejectGraphics:
    def find_spec(self, fullname, path=None, target=None):
        if (fullname == "pygame" or fullname.startswith("pygame.")
                or fullname in ("dnd.core.events", "dnd.entity", "dnd.content_system.runtime")):
            raise AssertionError("Shared binding imported " + fullname)
sys.meta_path.insert(0, RejectGraphics())
from game.choreography import bind_choreography, bind_motion
from game.animation_data import load_animation_data
from game.player_reduction import decode_player_sequence
from game.export_schema import export_schemas
from devtools.animation_review.trace import group_trace, motion_trace
from game.condition_media_lifetime import register_condition_lifetimes
from game.spatial_media_lifetime import register_spatial_lifetimes
from game.construction_media_lifetime import register_construction_lifetimes
from game.item_attachment_lifetime import register_item_attachment_starts
from game.concentration_media import register_concentration_lifetimes
from game.deposit_media import register_deposit_starts
assert load_animation_data().drafts
assert "pygame" not in sys.modules
'''
    result = subprocess.run([sys.executable, '-c', program],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
