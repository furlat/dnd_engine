"""Companions follow selected source frames; they do not redefine the artwork."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from game.asset_types import SurfaceCompanionSource
from game.device_art import DeviceArtSource
from game.environment_art import EnvironmentBankSource, EnvironmentDoorSource, EnvironmentDocument, EnvironmentLibraryFamilySource
from game.portal_art import PortalHatchSource


def normal_frame(path):
    return {'normal': {
        'region': {'path': path, 'rect': [0, 0, 64, 64]},
        'encoding': 'oct8_ba', 'sampling': {'scale': [.5, .5]},
        'normalToLocal': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    }}


def bank_source():
    return {
        'path': 'selected-colour.png', 'cell': [128, 128], 'ground_pivot': [64, 112],
        'pivots_by_pose': {'e': [64, 112]}, 'rows': ['e'], 'scale': 1,
        'frame_count': 2, 'sample_times_ms': [0, 75], 'duration_ms': 150,
        'actor_depth': {'path': 'legacy-contact.png', 'cell': [64, 64],
                        'depth_range': [-4, 4], 'pixels_per_unit_by_pose': {'e': 32},
                        'encoding': 'rg16le_contact'},
        'surface_frames_by_pose': {'e': [normal_frame('corrected-frame0.png'),
                                         normal_frame('source-animation-frame1.png')]},
    }


def test_legacy_depth_and_corrected_frame_zero_keep_the_colour_clock():
    source = bank_source()
    decoded = EnvironmentBankSource.model_validate(source)
    assert decoded.model_dump(mode='json', exclude_unset=True) == source
    assert decoded.surface_frames_by_pose['e'][0].geometry is None
    assert decoded.actor_depth.encoding == 'rg16le_contact'


@pytest.mark.parametrize('frames', [[], [normal_frame('frame0.png')]])
def test_missing_animation_companion_is_not_reused_from_another_frame(frames):
    source = bank_source()
    source['surface_frames_by_pose']['e'] = frames
    with pytest.raises(ValidationError, match='selected colour frames'):
        EnvironmentBankSource.model_validate(source)


def test_physical_floor_contacts_are_distinct_from_sprite_pivots():
    source = bank_source() | {'physical_source_contact_by_pose': {'e': [60, 110]},
                              'camera_quarter_by_pose': {'e': 0}}
    bank = EnvironmentBankSource.model_validate(source)
    assert bank.model_dump(mode='json', exclude_unset=True) == source
    assert bank.pivots_by_pose['e'] == (64, 112)
    source['camera_quarter_by_pose'] = {}
    with pytest.raises(ValidationError, match='contacts and camera quarters must cover'):
        EnvironmentBankSource.model_validate(source)


def assembly_door():
    return {'openings': {}, 'destructions': {}, 'pose_offset': 0, 'frame_resource_by_pose': {},
            'assembly_variants': {'header': {'primary': True, 'members': [
                {'role': 'supported_floor', 'family_id': 'floor', 'offset_XHZ': [0, 0, 0]},
                {'role': 'opening_header', 'family_id': 'header', 'offset_XHZ': [0, 0, 0]},
                {'role': 'adjacent_partition', 'family_id': 'partition', 'offset_XHZ': [0, 0, -1]},
                {'role': 'adjacent_partition', 'family_id': 'partition', 'offset_XHZ': [0, 0, 1]},
            ]}}}


def test_door_assembly_survives_serialization_and_resolves_existing_library():
    door = assembly_door()
    assert EnvironmentDoorSource.model_validate(door).model_dump(mode='json', exclude_unset=True) == door
    document = {'version': 1, 'banks': {}, 'doors': {'door': door}, 'traps': {}, 'wrecks': {},
                'library': {name: {'label': name, 'role': 'environment', 'samples': []}
                            for name in ('floor', 'header', 'partition')}}
    assert EnvironmentDocument.model_validate(document).model_dump(mode='json', exclude_unset=True) == document
    del document['library']['partition']
    with pytest.raises(ValidationError, match='door: unregistered assembly family partition'):
        EnvironmentDocument.model_validate(document)


def test_incomplete_or_duplicated_assembly_is_rejected():
    door = assembly_door()
    door['assembly_variants']['header']['members'].pop()
    with pytest.raises(ValidationError, match='one floor, one header and two adjacent partitions'):
        EnvironmentDoorSource.model_validate(door)
    door = assembly_door()
    door['assembly_variants']['header']['primary'] = False
    with pytest.raises(ValidationError, match='exactly one primary'):
        EnvironmentDoorSource.model_validate(door)


def test_fractional_library_support_is_not_an_integer_native_stair():
    sample = {'colour': {'path': 'timber.png', 'rect': [0, 0, 384, 384]},
              'source_view': 'e', 'pivot': [192, 272], 'physical_source_contact_px': [160, 288],
              'camera_quadrant': 0}
    source = {'label': 'Timber', 'role': 'stair', 'samples': [sample], 'support_profile': {
        'contacts_XHZ': {'lower_floor': [0, 0, 0], 'entry_tread': [0, .08, -.04],
                         'exit_tread': [0, .9, -.94], 'upper_landing': [0, .9, -.99]},
        'supports': [{'center_XHZ': [0, .08, -.04],
                      'polygon_XZ': [[-.2, 0], [.2, 0], [.2, -.09], [-.2, -.09]],
                      'contact_px_by_pose': {'e': [163, 281]}}],
        'lane_width_cells': .43, 'upper_landing_required': True}}
    decoded = EnvironmentLibraryFamilySource.model_validate(source)
    assert decoded.model_dump(mode='json', exclude_unset=True) == source
    source['support_profile']['supports'][0]['contact_px_by_pose'] = {}
    with pytest.raises(ValidationError, match='support contacts must cover'):
        EnvironmentLibraryFamilySource.model_validate(source)


def test_surface_paint_preserves_parent_and_role_codes():
    source = {
        'receiver': {'kind': 'resource', 'resource_id': 'spikes.e.1'},
        'roles': [{'role': 'surface_paint', 'selection': {'kind': 'whole'}}],
        'support': {'region': {'path': 'support.png', 'rect': [0, 0, 64, 64]},
                    'labels': {'0': 'absent', '1': 'source hit', '2': 'qualified edge'}},
    }
    assert SurfaceCompanionSource.model_validate(source).model_dump(mode='json', exclude_unset=True) == source


def device_source():
    return {
        'cell': [128, 128], 'anchor': [64, 112], 'rows': ['E', 'W'],
        'fps': 12, 'releaseFrame': 1, 'frameCount': 2, 'scale': 1,
        'operatorRecipe': 'existing-recipe', 'launchPitchDegrees': 15,
        'controlDistanceFraction': .5,
        'pitchBanks': [{
            'pitchDegrees': 15, 'sheets': ['q0.png', 'q1.png', 'q2.png', 'q3.png'],
            'muzzlePixels': [[[[64, 20], [65, 21]] for _ in range(2)] for _ in range(4)],
            'forwardScreen': [[[1, 0], [-1, 0]] for _ in range(4)],
            'muzzleHeightStepsByRow': [.5, .5],
            'surface_frames_by_camera': [
                [[normal_frame(f'q{camera}-aim{aim}-frame{frame}.png')
                  for frame in range(2)] for aim in range(2)] for camera in range(4)],
        }],
    }


def test_device_companions_keep_camera_aim_and_animation_indices():
    source = device_source()
    decoded = DeviceArtSource.model_validate(source)
    assert decoded.model_dump(mode='json', exclude_unset=True) == source
    assert decoded.pitchBanks[0].surface_frames_by_camera[3][1][0].normal.region.path == 'q3-aim1-frame0.png'
    truncated = deepcopy(source)
    truncated['pitchBanks'][0]['surface_frames_by_camera'][3][1].pop()
    with pytest.raises(ValidationError, match='selected device animation frames'):
        DeviceArtSource.model_validate(truncated)


def test_hatch_front_and_moving_layer_have_independent_samples():
    source = {
        'sheet': 'hatch-overlay.png', 'front': 'hatch-front.png', 'cell': [128, 128],
        'pivot': [64, 112], 'opening': [0, 1], 'closing': [2], 'fps': 12,
        'surface_frames_by_camera': [[normal_frame(f'moving-q{q}-f{f}.png')
                                     for f in range(3)] for q in range(4)],
        'front_surface_frames_by_camera': [[normal_frame(f'front-q{q}-f{f}.png')
                                           for f in range(3)] for q in range(4)],
    }
    decoded = PortalHatchSource.model_validate(source)
    assert decoded.model_dump(mode='json', exclude_unset=True) == source
    source['front_surface_frames_by_camera'][1].pop()
    with pytest.raises(ValidationError, match='selected source frame'):
        PortalHatchSource.model_validate(source)


def test_library_variants_do_not_guess_a_mount_or_merge_duplicate_names():
    sample = {'colour': {'path': 'utility.png', 'rect': [0, 0, 128, 128]},
              'source_view': 'single', 'state': 'ready', 'variant_name': 'same display name'}
    source = {'label': 'Unassigned source family', 'role': 'source utility',
              'samples': [sample | {'variant_index': 0}, sample | {'variant_index': 1}],
              'clocks': [{'state': 'ready', 'variant_index': 1, 'frame_count': 1,
                          'duration_ms': 500}]}
    decoded = EnvironmentLibraryFamilySource.model_validate(source)
    assert decoded.model_dump(mode='json', exclude_unset=True) == source
    assert all(frame.pivot is None and frame.scale is None for frame in decoded.samples)


def test_ground_shadow_keeps_its_own_surface_and_translated_source_grid():
    source = {'roles': [{
        'role': 'ground_shadow', 'selection': {'kind': 'whole'},
        'receiver': {'kind': 'support', 'height_steps': 0},
        'surface': {
            'geometry': {'kind': 'ray_depth', 'basis': 'object_local', 'depthRange': [-1, 1],
                         'pixelToRayOrigin': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                         'rayDirection': [1, -1, 1]},
            'geometry_region': {'path': 'ground-shadow-geometry.png', 'rect': [0, 0, 256, 256]},
            'geometry_sampling': {'scale': [1, 1], 'offset': [-64, -64]},
        },
    }]}
    assert SurfaceCompanionSource.model_validate(source).model_dump(mode='json', exclude_unset=True) == source
