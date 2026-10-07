"""Export production value schemas, HTTP documentation and owner field inventory."""
import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from player_server.app import create_app
from player_server.config import SeatCredential, ServerConfig
from player_server.protocol import protocol_identity, public_schema
from player_server.recording import close_recording


def source_owners(root: Path) -> dict[str, list[dict]]:
    owners: dict[str, list[dict]] = {}
    for directory in ('dnd', 'player_server'):
        for path in sorted((root / directory).rglob('*.py')):
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.ClassDef):
                    names = [node.name]
                    fields = {item.target.id: item.lineno for item in node.body
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)}
                elif isinstance(node, ast.Assign):
                    names = [target.id for target in node.targets if isinstance(target, ast.Name)]
                    fields = {}
                else:
                    continue
                for name in names:
                    owners.setdefault(name, []).append({'file': str(path.relative_to(root)),
                        'line': node.lineno, 'fields': fields})
    return owners


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = public_schema()
    text = json.dumps(schema, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    for directory in ('sdk/protocol', 'sdk/python/src/dnd_player', 'sdk/player-typescript/src'):
        (root / directory / 'player-api-v1.schema.json').write_text(text)
    identity = json.dumps(protocol_identity().model_dump(), indent=2) + '\n'
    for directory in ('sdk/protocol', 'sdk/python/src/dnd_player', 'sdk/player-typescript/src'):
        (root / directory / 'protocol-identity.json').write_text(identity)
    with TemporaryDirectory(prefix='player-openapi-') as spool:
        app = create_app(ServerConfig(credentials=(SeatCredential(seat_id='documentation',
            token='documentation-only-no-running-game'),), spool_directory=Path(spool)))
        try:
            (root / 'sdk/protocol/openapi.json').write_text(json.dumps(app.openapi(), indent=2) + '\n')
        finally:
            close_recording(app.state.player_host.recording)
    owners = source_owners(root)
    ledger = []
    for name, definition in sorted(schema['$defs'].items()):
        candidates = owners.get(name, [])
        for field, value in definition.get('properties', {}).items():
            direct = [row for row in candidates if field in row['fields']]
            ledger.append({'field': name + '.' + field,
                'schema_pointer': '/$defs/' + name + '/properties/' + field,
                'owners': [{'file': row['file'], 'line': row['fields'].get(field, row['line'])}
                    for row in (direct or candidates)],
                'required': field in definition.get('required', []), 'schema': value})
    (root / 'sdk/protocol/field-ledger.json').write_text(json.dumps(ledger, indent=2) + '\n')
    print(f"Exported {len(schema['$defs'])} shared definitions, {len(ledger)} fields; digest {protocol_identity().schema_digest}")


if __name__ == '__main__':
    main()
