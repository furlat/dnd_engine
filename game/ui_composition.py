"""SDL startup adapter for current native content descriptors."""

from game.ui_content_composition import ui_content_manifest
from game.ui.media import UIPresentationCatalog, load_ui_media


def compose_ui_media() -> UIPresentationCatalog:
    manifest = ui_content_manifest()
    return load_ui_media(dict(manifest.content), feature_ids=manifest.feature_ids, item_ids=manifest.item_ids)
