"""Runtime schema preparation preserves the already published client contract."""

from hashlib import sha256
import json
from pathlib import Path

from player_server.protocol import protocol_identity, public_schema


def test_runtime_schema_matches_the_published_client_contract():
    path = Path(__file__).resolve().parents[2] / "sdk/protocol/player-api-v1.schema.json"
    published = json.loads(path.read_text())
    assert public_schema() == published
    canonical = json.dumps(published, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert protocol_identity().schema_digest == sha256(canonical).hexdigest()
