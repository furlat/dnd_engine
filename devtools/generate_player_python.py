"""Generate JSON-shaped TypedDicts; adapt unsupported generator syntax only.

Runtime validation always uses the unchanged production JSON Schema. The type
adapter keeps UUIDs as JSON strings, lets unions use their existing literal
members, and teaches codegen about the draft-2020 fixed-array item schemas.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any


def generator_schema(schema: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(schema)

    def adapt(value: Any) -> None:
        if isinstance(value, dict):
            if value.get('format') == 'uuid':
                value.pop('format')
            value.pop('discriminator', None)
            if 'prefixItems' in value:
                # TypedDict fields contain JSON lists; codegen makes the union
                # of the positional element types. Runtime validates positions.
                value['items'] = value.pop('prefixItems')
            for member in value.values():
                adapt(member)
        elif isinstance(value, list):
            for member in value:
                adapt(member)

    adapt(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--codegen', default='datamodel-codegen')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / 'sdk/protocol/player-api-v1.schema.json'
    destination = root / 'sdk/python/src/dnd_player/contracts.py'
    with tempfile.TemporaryDirectory(prefix='player-python-types-') as directory:
        adapted = Path(directory) / 'python-type-schema.json'
        adapted.write_text(json.dumps(generator_schema(json.loads(source.read_bytes()))))
        subprocess.run([args.codegen, '--input', str(adapted), '--input-file-type', 'jsonschema',
            '--output', str(destination), '--output-model-type', 'typing.TypedDict',
            '--target-python-version', '3.12', '--use-standard-collections', '--use-union-operator',
            '--enum-field-as-literal', 'all', '--disable-timestamp'], check=True)


if __name__ == '__main__':
    main()
