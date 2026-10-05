"""A consumer can relocate the catalog without altering authored prose."""

from dataclasses import replace
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from game.animation_data import load_animation_data
from game.presentation_export import PresentationCatalogExport, export_catalog


def test_portable_catalog_preserves_types_relative_resources_and_literal_prose():
    data = load_animation_data()
    identity, asset = next(iter(data.projectile_assets.items()))
    literal = str(data.media_root)
    assets = dict(data.projectile_assets)
    assets[identity] = asset.model_copy(update={'displayName': literal})
    encoded = export_catalog(replace(data, projectile_assets=assets), Path(__file__).resolve().parents[2])
    decoded = PresentationCatalogExport.model_validate_json(encoded)
    assert decoded.catalog.media_root == Path('.')
    assert decoded.catalog.projectile_assets[identity].displayName == literal
    assert decoded.catalog.drafts == data.drafts
    document = json.loads(encoded)
    document['catalog']['unexpected_policy'] = 'must not silently disappear'
    with pytest.raises(ValidationError, match='unexpected_policy'):
        PresentationCatalogExport.model_validate_json(json.dumps(document))
