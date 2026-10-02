"""Import accepted humanoid chains without owning paralysis or native spell rules."""

import argparse
import json
from pathlib import Path

from devtools.import_registered_media import import_registered_bank


ROOT = Path(__file__).resolve().parents[1]


def import_humanoid_holds(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    """Selected bind53/still1/release87 windows retain original source addresses."""
    row = json.loads((source / 'media.json').read_text())['hold_human']
    if (row['fps'], row['frames'], row['cell']) != (32, 141, 384):
        raise ValueError('Holds require the pinned humanoid finite/still/release windows')
    return import_registered_bank(source, row, 'hold_human',
        (('apply', 0, 53), ('hold', 53, 1), ('release', 54, 87)),
        repo, bundle='control_media', default_scale=.5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=ROOT)
    args = parser.parse_args()
    print(f'Registered {len(import_humanoid_holds(args.source, repo=args.repo))} humanoid phase layers')
