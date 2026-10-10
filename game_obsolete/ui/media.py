"""Exact presentation references; no display-name or runtime-template guessing."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal, Mapping
from types import MappingProxyType

import pygame
from pydantic import TypeAdapter

from dnd.core.content.descriptors import ContentDescriptor, ContentPresentation
from dnd.core.content.identities import ContentRef
from dnd.player.facts import PlayerActor
from game.asset_types import AssetSpec, image_resources
from game.assets import ASSET_ROOT, DATA_ROOT
from game.ui.media_types import ChoiceRecord, PresentationRecord, UIPresentationDocument


@dataclass(frozen=True, slots=True)
class UIReference:
    kind: Literal['content_ref', 'direct_feature', 'direct_item', 'portrait_choice', 'common']
    identity: str
    content_ref: ContentRef | None = None


@dataclass(frozen=True, slots=True)
class UIPresentationCatalog:
    content: Mapping[ContentRef, ContentDescriptor]
    content_refs: Mapping[str, ContentRef]
    authored: UIPresentationDocument
    resources: Mapping[str, AssetSpec]
    choices: tuple[ChoiceRecord,...]



def load_ui_media(content: Mapping[ContentRef, ContentDescriptor], *,
                  feature_ids: frozenset[str], item_ids: frozenset[str],
                  data_root: Path = DATA_ROOT) -> UIPresentationCatalog:
    document = UIPresentationDocument.model_validate_json((data_root / 'ui_presentation.json').read_text())
    registered={ref.content_id for ref in content}
    if set(document.direct_features) != feature_ids-registered:
        raise ValueError('Direct UI features must match current unregistered feature IDs')
    if set(document.direct_items) != item_ids-registered:
        raise ValueError('Direct UI items must match current unregistered item IDs')
    resources = image_resources(json.loads((data_root / 'ui_media.json').read_text()), ASSET_ROOT)
    choices = TypeAdapter(tuple[ChoiceRecord,...]).validate_json((data_root / 'ui_choices.json').read_text())
    for choice in choices:
        if choice.owner not in content or 'icon:'+choice.icon_key not in resources:
            raise ValueError(f'Unregistered UI choice: {choice.owner.content_id}/{choice.value}')
    for rows in (document.direct_features, document.direct_items, document.portrait_choices, document.common):
        for row in rows.values():
            if row.presentation.icon_key is not None and 'icon:'+row.presentation.icon_key not in resources:
                raise ValueError(f'Unregistered UI icon: {row.presentation.icon_key}')
            if row.presentation.portrait_key is not None and 'portrait:'+row.presentation.portrait_key not in resources:
                raise ValueError(f'Unregistered UI portrait: {row.presentation.portrait_key}')
    return UIPresentationCatalog(MappingProxyType(dict(content)), MappingProxyType({key:ref for ref in content for key in (ref.content_id,ref.identity_key)}),
        document, MappingProxyType(resources), choices)


def presentation(catalog: UIPresentationCatalog, reference: UIReference) -> ContentPresentation | None:
    match reference.kind:
        case 'content_ref':
            descriptor=catalog.content.get(reference.content_ref) if reference.content_ref is not None else None
            return descriptor.presentation if descriptor is not None else None
        case 'direct_feature': rows = catalog.authored.direct_features
        case 'direct_item': rows = catalog.authored.direct_items
        case 'portrait_choice': rows = catalog.authored.portrait_choices
        case 'common': rows = catalog.authored.common
    record = rows.get(str(reference.identity))
    return record.presentation if record is not None else None


def reference_label(catalog: UIPresentationCatalog, reference: UIReference) -> str:
    if reference.kind=='content_ref':
        descriptor=catalog.content.get(reference.content_ref) if reference.content_ref is not None else None
        return descriptor.display_name if descriptor is not None else 'Unknown'
    rows={'direct_feature':catalog.authored.direct_features,'direct_item':catalog.authored.direct_items,
          'portrait_choice':catalog.authored.portrait_choices,'common':catalog.authored.common}
    record=rows[reference.kind].get(reference.identity)
    return record.label if record is not None else 'Unknown'


def actor_portrait_reference(catalog: UIPresentationCatalog, actor: PlayerActor) -> UIReference:
    # Explicit player choices take precedence. A creature uses its exact native
    # descriptor; its ordinary and summoned instances share that presentation.
    if actor.appearance.portrait_key:
        return UIReference('portrait_choice',actor.appearance.portrait_key)
    ref=catalog.content_refs.get(actor.creature_content_ref or '')
    return UIReference('content_ref',ref.content_id if ref is not None else '',ref)


def item_reference(catalog: UIPresentationCatalog, item_id: str) -> UIReference:
    ref = catalog.content_refs.get(item_id)
    return UIReference('content_ref', ref.content_id, ref) if ref is not None else UIReference('direct_item',item_id)


def action_reference(catalog: UIPresentationCatalog, behavior_id: str,
                     configured: ContentRef | None = None, *, provided_by_id: str | None = None) -> UIReference:
    if configured is not None:
        return UIReference('content_ref', configured.content_id, configured)
    ref = catalog.content_refs.get(behavior_id)
    if ref is not None:
        return UIReference('content_ref', ref.content_id, ref)
    return UIReference('direct_feature', provided_by_id or behavior_id)


def ui_image(catalog: UIPresentationCatalog, reference: UIReference, size: tuple[int,int],
             cache: dict[tuple[str,tuple[int,int]],pygame.Surface], *, portrait: bool = False,
             portrait_role: Literal['initiative','hud','sheet'] | None = None) -> pygame.Surface | None:
    row = presentation(catalog, reference)
    key = None if row is None else row.portrait_key if portrait else row.icon_key
    identity = ('portrait:' if portrait else 'icon:') + key if key is not None else None
    if identity is not None and portrait_role is not None:
        identity += ':' + portrait_role
    return resource_image(catalog,identity,size,cache,portrait=portrait)


def choice_image(catalog: UIPresentationCatalog, owner: ContentRef | None, facet: str, value: str,
                 facets: Mapping[str,str], size: tuple[int,int],
                 cache: dict[tuple[str,tuple[int,int]],pygame.Surface]) -> pygame.Surface | None:
    row=next((row for row in catalog.choices if row.owner==owner and row.facet==facet and row.value==value
        and all(facets.get(key)==required for key,required in row.requirements.items())),None)
    return resource_image(catalog,'icon:'+row.icon_key if row else None,size,cache)


def resource_image(catalog: UIPresentationCatalog, identity: str | None, size: tuple[int,int],
                   cache: dict[tuple[str,tuple[int,int]],pygame.Surface], *, portrait: bool=False) -> pygame.Surface | None:
    resource = catalog.resources.get(identity) if identity is not None else None
    if resource is None:
        return None
    if not portrait and resource.native_size == (28,28):
        multiple=max(1,min(size)//28)
        size=(28*multiple,28*multiple)
    pixel_portrait = portrait and resource.native_size in ((36,48),(48,64),(96,128))
    if pixel_portrait:
        multiple=max(1,min(size[0]//resource.native_size[0],size[1]//resource.native_size[1]))
        size=resource.native_size[0]*multiple,resource.native_size[1]*multiple
    cache_key = resource.asset_id,size
    if cache_key not in cache:
        if len(cache) >= 192:
            cache.pop(next(iter(cache)))
        image=pygame.image.load(resource.path).convert_alpha()
        if resource.rect is not None:
            image=image.subsurface(resource.rect)
        cache[cache_key]=(pygame.transform.scale(image,size) if pixel_portrait or not portrait and resource.native_size == (28,28)
                          else pygame.transform.smoothscale(image,size))
    return cache[cache_key]
