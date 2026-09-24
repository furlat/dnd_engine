"""Offline selection over existing storage addresses, without an owner registry."""

from pathlib import PurePosixPath
from typing import Iterator


def _paths(storage: dict) -> Iterator[str]:
    for phase in storage.get("phases", {}).values():
        packet = phase.get("surfaceFrames")
        if packet is not None:
            if packet.get("pattern") is not None:
                yield packet["pattern"]
            if packet.get("archive") is not None:
                yield packet["archive"]["file"]
            for parts in packet.get("componentsByFacing", {}).values():
                for part in parts:
                    if part.get("pattern") is not None:
                        yield part["pattern"]
                    if part.get("archive") is not None:
                        yield part["archive"]["file"]
        for layer in phase.get("layers", ()):
            if layer.get("pattern") is not None:
                yield layer["pattern"]
            for pages in layer.get("pages", {}).values():
                for page in pages:
                    yield page["file"]
            sequences = layer.get("partsByFacing", {}).values() if "partsByFacing" in layer else (layer.get("parts", ()),)
            for frames in sequences:
                for parts in frames:
                    for part in parts:
                        yield part["file"]
                        if part.get("footpoint") is not None:
                            yield part["footpoint"]["file"]


def owns_selected_media(storage: dict, identity: str, media_root: str) -> bool:
    """A historical converter may refresh its own selected media, not another delivery.

    No selection yet permits initial conversion. Explicitly importing the newer
    delivery owns replacement; rerunning an older bundle preserves that choice.
    The predicate inspects metadata already loaded by the importer, never files.
    """
    selected = storage.get(identity)
    if selected is None:
        return True
    paths = tuple(_paths(selected))
    return bool(paths) and all(PurePosixPath(path).is_relative_to(media_root) for path in paths)
