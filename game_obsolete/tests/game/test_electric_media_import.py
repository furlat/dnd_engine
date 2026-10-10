"""Electric metadata failure must leave prior assets and recipes untouched."""

import hashlib
import json

import pytest

from devtools.import_electric_media import import_electric_media


@pytest.fixture
def delivery(tmp_path):
    source, preserved, production, repo = (tmp_path / part for part in ('source', 'archive', 'production', 'repo'))
    (source / 'assets').mkdir(parents=True)
    (source / 'cast-assets').mkdir()
    production.mkdir()
    payload = b'accepted component'
    (source / 'assets/arc-material.png').write_bytes(payload)
    (source / 'components.json').write_text(json.dumps({'files': {
        'arc-material.png': {'sha256': hashlib.sha256(payload).hexdigest()}}}))
    (source / 'cast-assets/lightning-hands.png').write_bytes(b'accepted hands')
    for name in ('CAST_HANDOFF.md', 'LIGHTNING_BOLT.md', 'lifecycle.js', 'spell.js', 'bolt.js',
                 'cast-assets/hand-sockets.json'):
        (source / name).write_text('accepted metadata')
    (production / 'art-manifest.json').write_text('{"files": [], "total_bytes": 0}')
    return source, preserved, production, repo


@pytest.mark.parametrize('defect', ('missing-late-metadata', 'conflicting-archive', 'escaping-archive'))
def test_late_metadata_rejection_cannot_partially_install(delivery, defect):
    source, preserved, production, repo = delivery
    before = (production / 'art-manifest.json').read_bytes()
    preserved.mkdir()
    if defect == 'missing-late-metadata':
        (source / 'cast-assets/hand-sockets.json').unlink()
    elif defect == 'conflicting-archive':
        (preserved / 'bolt.js').write_text('earlier preserved source')
    else:
        (preserved / 'cast-assets').symlink_to(source.parent, target_is_directory=True)
    with pytest.raises((FileNotFoundError, ValueError)):
        import_electric_media(source, preserved=preserved, production=production, repo=repo)
    assert (production / 'art-manifest.json').read_bytes() == before
    assert not (preserved / 'assets').exists()
    assert not (production / 'game').exists()
    assert not repo.exists()


def test_repeat_preserves_originals_and_recipe(delivery):
    source, preserved, production, repo = delivery
    import_electric_media(source, preserved=preserved, production=production, repo=repo)
    recipe = repo / 'game/data/electric_media/electric-draft.json'
    recipe.write_text('selected recipe')
    import_electric_media(source, preserved=preserved, production=production, repo=repo)
    assert recipe.read_text() == 'selected recipe'
    assert (preserved / 'bolt.js').read_bytes() == (source / 'bolt.js').read_bytes()
    assert (repo / 'game/assets/electric_media/arc-material.png').read_bytes() == (source / 'assets/arc-material.png').read_bytes()
