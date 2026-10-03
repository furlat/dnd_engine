"""Original body/composite pairs reproduce visible pixels without invented art."""

import io

from PIL import Image
import pytest

from devtools.import_fixed_rig import recover_visible_shadow


def png(pixels: tuple[tuple[int, int, int, int], ...]) -> bytes:
    image = Image.new("RGBA", (len(pixels), 1))
    image.putdata(pixels)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_visible_shadow_keeps_original_alpha_and_recomposes_exactly() -> None:
    body = png(((40, 80, 120, 255), (0, 0, 0, 0), (0, 0, 0, 0)))
    combined = png(((40, 80, 120, 255), (0, 0, 0, 234), (5, 7, 9, 73)))
    shadow = Image.open(io.BytesIO(recover_visible_shadow(body, combined)))
    assert shadow.tobytes() == bytes((0, 0, 0, 0, 0, 0, 0, 234, 5, 7, 9, 73))
    assert Image.alpha_composite(shadow, Image.open(io.BytesIO(body))).tobytes() == Image.open(io.BytesIO(combined)).tobytes()


@pytest.mark.parametrize("body,combined,reason", [
    (((40, 80, 120, 255),), ((41, 80, 120, 255),), "changes opaque body"),
    (((40, 80, 120, 128),), ((40, 80, 120, 255),), "binary-alpha body"),
    (((40, 80, 120, 255),), ((40, 80, 120, 255), (0, 0, 0, 100)), "dimensions differ"),
])
def test_unusable_pairs_are_rejected(body, combined, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        recover_visible_shadow(png(body), png(combined))
