"""Existing authored references resolve without aliases or fabricated content IDs."""

from pathlib import Path
import json

import pygame
import pytest

from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.content.descriptors import ContentPresentation
from game.ui_composition import compose_ui_media
from game.ui.media import UIReference, load_ui_media, presentation, action_reference, ui_image, reference_label


@pytest.fixture(scope='module')
def catalog():
    loaded=SERVER_CONTENT_SYSTEM_RUNTIME.require()
    pygame.init();pygame.display.set_mode((1,1))
    yield compose_ui_media()
    pygame.quit()


def test_current_registered_ref_and_direct_feature_use_their_distinct_owners(catalog):
    ref=action_reference(catalog,'spell.magic_missile')
    assert ref.kind=='content_ref' and ref.content_ref is not None
    assert presentation(catalog,ref)==catalog.content[ref.content_ref].presentation
    direct=UIReference('direct_feature','class_feature.fighter.action_surge')
    assert presentation(catalog,direct).icon_key=='condition.dnd-classes-fighter-actionsurgefeature'
    assert action_reference(catalog,'unknown.magic_missile').content_ref is None
    assert presentation(catalog,UIReference('direct_feature','unknown.magic_missile')) is None


def test_every_selected_resource_exists_and_portrait_choices_are_complete(catalog):
    assert len(catalog.authored.portrait_choices)==56
    assert all(row.path.is_file() for row in catalog.resources.values())
    cache={}
    for key in ('spell.magic_missile','spell.fly'):
        reference=action_reference(catalog,key)
        image=ui_image(catalog,reference,(42,42),cache)
        assert image is not None and image.get_size()==(28,28)
        descriptor=presentation(catalog,reference)
        assert descriptor is not None and descriptor.icon_key is not None
        source=pygame.image.load(catalog.resources['icon:'+descriptor.icon_key].path).convert_alpha()
        assert pygame.image.tobytes(image,'RGBA')==pygame.image.tobytes(source,'RGBA')
    assert ui_image(catalog,UIReference('direct_item','unknown.weapon'),(42,42),cache) is None


def test_pixelated_portraits_use_the_delivered_native_role_without_resampling(catalog):
    cache={}
    reference=UIReference('portrait_choice','hero.fighter_l5_shield_torch.hero')
    for role,size in (('initiative',(36,48)),('hud',(48,64)),('sheet',(96,128))):
        image=ui_image(catalog,reference,size,cache,portrait=True,portrait_role=role)
        assert image is not None and image.size==size
        resource=catalog.resources['portrait:hero.fighter_l5_shield_torch.hero:'+role]
        source=pygame.image.load(resource.path).convert_alpha()
        assert pygame.image.tobytes(image,'RGBA')==pygame.image.tobytes(source,'RGBA')
        enlarged=ui_image(catalog,reference,(size[0]*2,size[1]*2),cache,portrait=True,portrait_role=role)
        assert pygame.image.tobytes(enlarged,'RGBA')==pygame.image.tobytes(pygame.transform.scale(source,enlarged.size),'RGBA')
    assert catalog.resources['portrait:hero.fighter_l5_shield_torch.hero'].path.suffix=='.webp'


def test_direct_item_binding_reports_provisional_weapon_substitution(catalog):
    row=catalog.authored.direct_items['weapon.pistol']
    assert row.presentation.icon_key=='item.light-crossbow'
    assert row.approximation is not None
    assert catalog.authored.direct_items['weapon.longsword'].presentation.icon_key=='item.longsword'


def test_new_creature_portraits_resolve_all_roles_through_exact_content_and_rig_identity(catalog):
    cache={}
    records={ref:descriptor for ref,descriptor in catalog.content.items()
        if descriptor.presentation.portrait_key is not None and
        'portrait:'+descriptor.presentation.portrait_key+':initiative' in catalog.resources}
    assert len(records)==41
    for ref,descriptor in records.items():
        binding=next(json.loads(path.read_text()) for path in Path('game/data/rigs').glob('*.json')
            if ref.identity_key in json.loads(path.read_text())['creature_content_refs'])
        assert binding['rig_id'].startswith('smallscale.')
        reference=UIReference('content_ref',ref.content_id,ref)
        for role,size in (('initiative',(36,48)),('hud',(48,64)),('sheet',(96,128))):
            image=ui_image(catalog,reference,size,cache,portrait=True,portrait_role=role)
            assert image is not None and image.size==size
        assert reference_label(catalog,reference)==descriptor.display_name
    assert presentation(catalog,UIReference('portrait_choice','goblin_archer')) is None
    assert reference_label(catalog,action_reference(catalog,'spell.magic_missile'))=='Magic Missile'
