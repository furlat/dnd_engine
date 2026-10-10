"""Companion grids preserve the source colour's authored registration."""
import pytest
from pydantic import ValidationError

from game.asset_types import ImageResourceSource


def sampled_image():
    return {
        'path': '/media/environment/wall.png', 'native_size': [256, 256],
        'pivot': [128, 208], 'scale': 1,
        'geometry': {
            'kind': 'ray_depth', 'basis': 'object_local', 'depthRange': [-2, 2],
            'pixelToRayOrigin': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            'rayDirection': [1, -1, 1],
        },
        'geometry_region': {'path': '/media/environment/wall-geometry.png',
                            'rect': [512, 0, 256, 256]},
    }


def test_image_keeps_companion_region_separate_from_colour_placement():
    source = sampled_image()
    result = ImageResourceSource.model_validate(source).model_dump(mode='json', exclude_unset=True)
    assert result == source
    source.pop('geometry_region')
    source.pop('geometry')
    assert ImageResourceSource.model_validate(source).geometry_region is None


@pytest.mark.parametrize('change, message', [
    ({'geometry': None}, 'ray-depth calibration'),
    ({'geometry_region': {'path': 'geometry.png', 'rect': [0, 0, 128, 128]}}, 'explicit colour-to-data'),
])
def test_unregistered_companion_cannot_be_admitted(change, message):
    with pytest.raises(ValidationError, match=message):
        ImageResourceSource.model_validate(sampled_image() | change)


def test_native_packet_grid_does_not_resize_or_move_colour():
    source = sampled_image() | {
        'geometry_region': {'path': 'geometry-native.png', 'rect': [128, 256, 128, 128]},
        'geometry_sampling': {'scale': [.5, .5], 'offset': [0, 0], 'pixel_center': [.5, .5]},
        'normal': {
            'region': {'path': 'geometry-native.png', 'rect': [128, 256, 128, 128]},
            'encoding': 'oct8_ba', 'sampling': {'scale': [.5, .5]},
            'normalToLocal': [[1, 0, 0], [0, 0, 2], [0, -1, 0]],
        },
    }
    result = ImageResourceSource.model_validate(source).model_dump(mode='json', exclude_unset=True)
    assert result == source


def test_arch_packet_and_aperture_mesh_keep_distinct_roles():
    source = sampled_image() | {
        'receiving_geometry': {
            'kind': 'mesh', 'basis': 'object_local',
            'vertices': [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            'triangles': [[0, 1, 2]], 'uvs': [[0, 0], [1, 0], [0, 1]],
            'faceIds': ['arch-left-member'],
        },
        'roles': [{
            'role': 'ground_shadow', 'source_label': 'painted source ground shadow',
            'selection': {'kind': 'source_rgba',
                          'bounds': {'minimum': [0, 0, 0, 1], 'maximum': [1, 1, 1, 249]}},
            'receiver': {'kind': 'support', 'height_steps': 0},
        }],
        'qualification': 'Visible receiving geometry; not a hidden closed collider.',
    }
    result = ImageResourceSource.model_validate(source).model_dump(mode='json', exclude_unset=True)
    assert result == source
