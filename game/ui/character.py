"""Cold character drafts and their Pygame view; no live character per edit."""

from dataclasses import dataclass, replace
from typing import Literal, TypeAlias, cast

import pygame

from dnd.content.characters.builds import CharacterBuild, resolve_character_build
from dnd.content.characters.class_definitions import class_level_choices, next_class_level
from dnd.content.characters.origin_definitions import ABILITY_ORDER, SPECIES_DEFINITIONS, origin_choices
from dnd.content.characters.premades import PREMADE_CHARACTER_BUILDS
from dnd.content.items.item_loadouts import CLASS_STARTING_LOADOUTS, BACKGROUND_ITEM_LOADOUTS
from dnd.core.progression import point_buy_cost
from dnd.types.appearance import BodyCategory, HeadCategory
from dnd.types.character_progression import Background, CharacterClass, ClassChoiceSelection, OriginChoiceSelection, Species
from game.animation import ActorContact, sample_idle_body
from game.animation_data import resolve_actor_layers
from game.animation_draw import LoadedBodyRows, actor_draw_commands, load_actor_media
from game.animation_types import AnimationData
from dnd.core.equipment_types import WeaponSet
from game.projection import Camera
from game.ui.layout import UILayout
from game.ui.media import UIPresentationCatalog, UIReference, ui_image, reference_label, item_reference, action_reference
from game.ui.primitives import UIFonts, GOLD, GREEN, MUTED, RED, text, wrap
from game.ui.skin import UISkin, draw_skin


Page = Literal['Identity', 'Abilities', 'Classes', 'Appearance', 'Review']
PAGES: tuple[Page, ...] = ('Identity', 'Abilities', 'Classes', 'Appearance', 'Review')
CreatorVerb: TypeAlias = Literal['start', 'quit', 'premade', 'new', 'edit', 'remove', 'save', 'cancel', 'page',
    'name', 'species', 'variant', 'background', 'score', 'bonus', 'choice',
    'level', 'add_level', 'remove_level', 'appearance', 'value', 'apply', 'back']


@dataclass(frozen=True, slots=True)
class ChoiceEdit:
    scope: Literal['origin', 'class', 'portrait']
    identity: str
    allowed: tuple[str, ...]
    counts: tuple[int, ...]
    values: tuple[str, ...]
    optional: bool = False
    selection_labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CharacterDraft:
    build: CharacterBuild
    page: Page = 'Identity'
    level_index: int = 0
    choice: ChoiceEdit | None = None
    scroll: int = 0
    search: str = ''
    editing_name: bool = False
    status: str = ''


@dataclass(frozen=True, slots=True)
class CreatorHit:
    rect: pygame.Rect
    verb: CreatorVerb
    index: int = 0
    value: str = ''
    enabled: bool = True


def draft_error(build: CharacterBuild) -> str:
    try:
        resolve_character_build(build)
    except ValueError as error:
        return str(error)
    return ''


def starting_loadout(build: CharacterBuild) -> CharacterBuild:
    """Expand a newly chosen package once, not during paint or deployment."""
    package = next((value for choice in build.class_levels[0].choices
                    for value in choice.values if value in CLASS_STARTING_LOADOUTS), None)
    items = CLASS_STARTING_LOADOUTS[package] if package is not None else ()
    return replace(build, item_loadout=(*items, *BACKGROUND_ITEM_LOADOUTS.get(build.background.value, ())))


def new_draft(premade_id: str) -> CharacterDraft:
    source = PREMADE_CHARACTER_BUILDS[premade_id]
    return CharacterDraft(starting_loadout(replace(source, class_levels=source.class_levels[:1],
        prepared_spells=(), feature_toggles=(), description='Player-created character')))


def _origin_defaults(build: CharacterBuild) -> CharacterBuild:
    retained = {row.choice_id: row.values for row in build.origin_choices}
    return replace(build, origin_choices=tuple(OriginChoiceSelection(row.choice_id,
        retained[row.choice_id] if row.choice_id in retained
        and len(retained[row.choice_id]) == row.selections
        and all(value in row.allowed_values for value in retained[row.choice_id])
        else row.allowed_values[:row.selections])
        for row in origin_choices(build.species, build.species_variant, build.background)))


def edit_draft(draft: CharacterDraft, hit: CreatorHit, media: UIPresentationCatalog,
               data: AnimationData) -> CharacterDraft:
    """UI input changes passive values; the existing resolver admits the result."""
    build = draft.build
    if not hit.enabled:
        return draft
    match hit.verb:
        case 'page':
            return replace(draft, page=PAGES[hit.index], choice=None, scroll=0, search='', editing_name=False)
        case 'name':
            return replace(draft, editing_name=True)
        case 'species':
            species = tuple(Species)[hit.index]
            variants = SPECIES_DEFINITIONS[species].variants
            build = _origin_defaults(replace(build, species=species, species_variant=variants[0] if variants else None))
        case 'variant':
            values = (None, *SPECIES_DEFINITIONS[build.species].variants)
            build = _origin_defaults(replace(build, species_variant=values[hit.index]))
        case 'background':
            build = starting_loadout(_origin_defaults(replace(build, background=tuple(Background)[hit.index])))
        case 'score':
            scores = list(build.base_ability_scores)
            ability, value = scores[hit.index]
            candidate = value + int(hit.value)
            try:
                point_buy_cost(candidate)
            except ValueError as error:
                return replace(draft, status=str(error))
            scores[hit.index] = (ability, candidate)
            build = replace(build, base_ability_scores=tuple(scores))
        case 'bonus':
            ability = ABILITY_ORDER[hit.index]
            amount = int(hit.value)
            # Picking an already-used ability swaps the two choices.
            previous = next(name for name, value in build.flexible_ability_bonuses if value == amount)
            build = replace(build, flexible_ability_bonuses=tuple(sorted(
                ((ability if value == amount else previous if name == ability else name, value)
                 for name, value in build.flexible_ability_bonuses), key=lambda row: ABILITY_ORDER.index(row[0]))))
        case 'choice':
            if hit.value == 'portrait':
                keys = tuple(media.authored.portrait_choices)
                selected = tuple(key for key in keys if media.authored.portrait_choices[key].presentation.portrait_key == build.appearance.portrait_key)
                return replace(draft, choice=ChoiceEdit('portrait','Portrait',keys,(1,),selected),scroll=0,search='')
            if draft.page == 'Identity':
                row = origin_choices(build.species,build.species_variant,build.background)[hit.index]
                values = next((row_.values for row_ in build.origin_choices if row_.choice_id==row.choice_id),())
                choice = ChoiceEdit('origin',row.choice_id,row.allowed_values,(row.selections,),values)
            else:
                level = build.class_levels[draft.level_index]
                row_ = class_level_choices(level,first_class=draft.level_index==0)[hit.index]
                values = next((row.values for row in level.choices if row.choice_id==row_.choice_id),())
                choice = ChoiceEdit('class',row_.choice_id,row_.allowed_values,row_.selections,values,row_.optional,row_.selection_labels)
            return replace(draft,choice=choice,scroll=0,search='',editing_name=False)
        case 'value' if draft.choice is not None:
            values = list(draft.choice.values)
            if hit.value in values:
                values.remove(hit.value)
            elif max(draft.choice.counts) == 1:
                values = [hit.value]
            elif len(values) < max(draft.choice.counts):
                values.append(hit.value)
            return replace(draft,choice=replace(draft.choice,values=tuple(values)))
        case 'apply' if draft.choice is not None:
            choice = draft.choice
            if len(choice.values) not in choice.counts and not (choice.optional and not choice.values):
                return replace(draft,status='Select the indicated number of choices')
            if choice.scope == 'portrait':
                build = replace(build,appearance=replace(build.appearance,
                    portrait_key=media.authored.portrait_choices[choice.values[0]].presentation.portrait_key))
            elif choice.scope == 'origin':
                requirements = origin_choices(build.species,build.species_variant,build.background)
                values = {row.choice_id:row.values for row in build.origin_choices}
                values[choice.identity] = choice.values
                build = replace(build,origin_choices=tuple(OriginChoiceSelection(row.choice_id,values[row.choice_id])
                    for row in requirements if values.get(row.choice_id)))
            else:
                levels = list(build.class_levels)
                level = levels[draft.level_index]
                requirements = class_level_choices(level,first_class=draft.level_index==0)
                values = {row.choice_id:row.values for row in level.choices}
                values[choice.identity] = choice.values
                levels[draft.level_index] = replace(level,choices=tuple(ClassChoiceSelection(row.choice_id,values[row.choice_id])
                    for row in requirements if values.get(row.choice_id)))
                build = replace(build,class_levels=tuple(levels))
                if any(value in CLASS_STARTING_LOADOUTS for value in choice.allowed):
                    build = starting_loadout(build)
            return replace(draft,build=build,choice=None,scroll=0,search='',status='')
        case 'back':
            return replace(draft,choice=None,scroll=0,search='',status='')
        case 'level':
            return replace(draft,level_index=hit.index,status='')
        case 'add_level':
            level = next_class_level(tuple(CharacterClass)[hit.index],build.class_levels)
            build = replace(build,class_levels=(*build.class_levels,level))
            return replace(draft,build=replace(build,prepared_spells=()),level_index=len(build.class_levels)-1,status='')
        case 'remove_level' if len(build.class_levels)>1:
            build = replace(build,class_levels=build.class_levels[:-1],prepared_spells=(),feature_toggles=())
            return replace(draft,build=build,level_index=min(draft.level_index,len(build.class_levels)-1),status='')
        case 'appearance':
            appearance = build.appearance
            bodies = tuple(category for category in data.rigs[data.root_rig].slot_categories['body']
                           if category in ('NakedBody','NakedBody2','NakedBody3') and category in data.rigs[data.root_rig].clips['Idle'].sheets)
            heads = (None, *tuple(category for category in data.rigs[data.root_rig].slot_categories['head']
                                if category in ('Head1','Head9','Head10','Head16','Head17','Head22') and category in data.rigs[data.root_rig].clips['Idle'].sheets))
            if hit.value == 'body':
                appearance = replace(appearance,body_category=cast(BodyCategory,bodies[hit.index]))
            elif hit.value == 'head':
                appearance = replace(appearance,head_category=cast(HeadCategory|None,heads[hit.index]))
            elif hit.value == 'beard':
                appearance = replace(appearance,has_beard=not appearance.has_beard)
            else:
                colors = (0xE6BC98,0xDDAA88,0x947657,0x684D3F,0x993F00,0xD0BFA1,0x181820,0xDBD5C1)
                color = colors[hit.index]
                if hit.value=='skin_tint':
                    appearance=replace(appearance,skin_tint=color)
                elif hit.value=='hair_tint':
                    appearance=replace(appearance,hair_tint=color)
                elif hit.value=='beard_tint':
                    appearance=replace(appearance,beard_tint=color)
            build = replace(build,appearance=appearance)
    return replace(draft,build=build,status='',editing_name=False)


def _label(value: str) -> str:
    if value.startswith('ability_score.'):
        _, ability, amount = value.split('.')
        return f'{ability.title()} +{amount}'
    return value.replace('_',' ').split('.')[-1].title()


def draw_creator(screen: pygame.Surface, geometry: UILayout, font: UIFonts, skin: UISkin,
                 media: UIPresentationCatalog, data: AnimationData,
                 images: dict[tuple[str,tuple[int,int]],pygame.Surface], party: tuple[CharacterBuild,...],
                 draft: CharacterDraft | None, status: str, mouse: tuple[int,int]) -> tuple[tuple[CreatorHit,...],int]:
    rect, scale = geometry.modal, geometry.scale
    px = lambda value: round(value*scale)
    screen.fill((12,16,22))
    text(screen,font.heading,'Choose your party' if draft is None else draft.build.name,(rect.left,rect.top-px(34)),GOLD)
    hits = []

    def control(label: str, box: pygame.Rect, verb: CreatorVerb, *,
                index: int = 0, value: str = '', enabled: bool = True) -> None:
        state = 'disabled' if not enabled else 'hover' if box.collidepoint(mouse) else 'normal'
        draw_skin(screen,box,skin['button'][state],scale=scale)
        while len(label)>1 and font.small.size(label)[0]>box.width-px(10):
            label=label[:-2]+'…'
        image=font.small.render(label,True,(231,229,221) if enabled else MUTED)
        screen.blit(image,image.get_rect(center=box.center))
        hits.append(CreatorHit(box,verb,index,value,enabled))

    if draft is None:
        for index,build in enumerate(party):
            y=rect.top+index*px(180)
            image=next((ui_image(media,UIReference('portrait_choice',key),(px(104),px(140)),images,portrait=True,portrait_role='sheet')
                        for key,row in media.authored.portrait_choices.items()
                        if row.presentation.portrait_key==build.appearance.portrait_key),None)
            if image is not None:
                screen.blit(image,(rect.left,y))
            x=rect.left+px(120)
            text(screen,font.heading,build.name,(x,y))
            text(screen,font.body,f'Level {len(build.class_levels)} · {_label(build.species.value)}',(x,y+px(28)),MUTED)
            roster_controls: tuple[tuple[str,CreatorVerb],...]=(('Edit','edit'),('Next premade','premade'),('Remove','remove'))
            for col,(label,verb) in enumerate(roster_controls):
                control(label,pygame.Rect(x+col*px(145),y+px(62),px(138),px(30)),verb,index=index,
                        enabled=verb!='remove' or len(party)>1)
        y=rect.bottom-px(98)
        for index,class_id in enumerate(CharacterClass):
            control('New '+_label(class_id.value),pygame.Rect(rect.left+index*px(190),y,px(180),px(32)),
                    'new',index=index,enabled=len(party)<2)
        control('Start encounter',pygame.Rect(rect.right-px(190),rect.bottom-px(38),px(190),px(36)),'start')
        control('Quit',pygame.Rect(rect.left,rect.bottom-px(38),px(100),px(36)),'quit')
        if status:
            text(screen,font.small,status,(rect.left,rect.bottom-px(60)),RED,max_width=rect.width)
        return tuple(hits),0

    build=draft.build
    for index,page in enumerate(PAGES):
        control(page,pygame.Rect(rect.left+index*rect.width//5,rect.top,rect.width//5-px(3),px(32)),'page',index=index)
    content=pygame.Rect(rect.left,rect.top+px(48),rect.width,rect.height-px(118))
    previous=screen.get_clip();screen.set_clip(content.clip(previous))
    y=content.top-draft.scroll
    x=content.left

    def field(label: str, value: str, verb: CreatorVerb, *, index: int=0, choice: str='') -> None:
        nonlocal y
        text(screen,font.body,label,(x,y+px(5)),MUTED,max_width=content.width//2-px(12))
        control(value,pygame.Rect(x+content.width//2,y,content.width//2,px(32)),verb,index=index,value=choice)
        y+=px(42)

    if draft.choice is not None:
        choice=draft.choice
        text(screen,font.body,_label(choice.identity)+f' · choose {" or ".join(map(str,choice.counts))}',(x,y),GOLD);y+=px(30)
        for index,label in enumerate(choice.selection_labels):
            text(screen,font.small,label+': '+(_label(choice.values[index]) if index<len(choice.values) else 'Choose…'),(x,y),GOLD);y+=px(26)
        text(screen,font.small,'Type to filter · Backspace edits filter · wheel scrolls',(x,y),MUTED);y+=px(26)
        text(screen,font.small,'Filter: '+draft.search,(x,y));y+=px(28)
        for value in choice.allowed:
            if draft.search.casefold() not in _label(value).casefold():
                continue
            if choice.scope=='portrait':
                image=ui_image(media,UIReference('portrait_choice',value),(px(36),px(48)),images,portrait=True,portrait_role='initiative')
                if image is not None:
                    screen.blit(image,(x,y))
            control(('✓ ' if value in choice.values else '')+(reference_label(media,UIReference('portrait_choice',value)) if choice.scope=='portrait' else reference_label(media,action_reference(media,value)) if value.startswith(('spell.','feat.','class_feature.','metamagic.')) else _label(value)),
                    pygame.Rect(x+px(40),y,content.width-px(40),px(32)),'value',value=value)
            y+=px(52 if choice.scope=='portrait' else 37)
    elif draft.page=='Identity':
        field('Name',build.name+(' |' if draft.editing_name else ''),'name')
        species=tuple(Species);field('Species',_label(build.species.value),'species',index=(species.index(build.species)+1)%len(species))
        variants=(None,*SPECIES_DEFINITIONS[build.species].variants)
        field('Variant',_label(build.species_variant.value) if build.species_variant else 'None','variant',index=(variants.index(build.species_variant)+1)%len(variants))
        backgrounds=tuple(Background);field('Background',_label(build.background.value),'background',index=(backgrounds.index(build.background)+1)%len(backgrounds))
        for index,row in enumerate(origin_choices(build.species,build.species_variant,build.background)):
            values=next((row_.values for row_ in build.origin_choices if row_.choice_id==row.choice_id),())
            field(_label(row.choice_id),', '.join(map(_label,values)) or 'Choose…','choice',index=index)
    elif draft.page=='Abilities':
        points=sum(point_buy_cost(score) for _,score in build.base_ability_scores)
        text(screen,font.body,f'Point buy: {points} / 27 · exact total required',(x,y),GREEN if points==27 else GOLD);y+=px(36)
        for index,(ability,score) in enumerate(build.base_ability_scores):
            bonus=next((amount for name,amount in build.flexible_ability_bonuses if name==ability),0)
            text(screen,font.body,ability.title(),(x,y+px(6)))
            text(screen,font.body,f'{score} + {bonus}',(x+px(210),y+px(6)))
            score_controls: tuple[tuple[str,CreatorVerb,str],...]=(('−','score','-1'),('+','score','1'),('+2 bonus','bonus','2'),('+1 bonus','bonus','1'))
            for col,(label,verb,value) in enumerate(score_controls):
                control(label,pygame.Rect(x+px(340)+col*px(115),y,px(106),px(30)),verb,index=index,value=value)
            y+=px(42)
    elif draft.page=='Classes':
        level=build.class_levels[draft.level_index]
        text(screen,font.heading,f'Character level {draft.level_index+1} · {_label(level.class_id.value)} {level.resulting_class_level}',(x,y));y+=px(38)
        for col,(label,index) in enumerate((('Previous',max(0,draft.level_index-1)),('Next',min(len(build.class_levels)-1,draft.level_index+1)))):
            control(label,pygame.Rect(x+col*px(140),y,px(130),px(30)),'level',index=index)
        control('Remove last level',pygame.Rect(content.right-px(200),y,px(200),px(30)),'remove_level',enabled=len(build.class_levels)>1);y+=px(42)
        for index,class_id in enumerate(CharacterClass):
            control('Add '+_label(class_id.value),pygame.Rect(x+index*px(190),y,px(180),px(30)),'add_level',index=index,enabled=len(build.class_levels)<20)
        y+=px(42)
        for index,row in enumerate(class_level_choices(level,first_class=draft.level_index==0)):
            values=next((row_.values for row_ in level.choices if row_.choice_id==row.choice_id),())
            field(_label(row.choice_id),', '.join(map(_label,values)) or ('Skip / optional' if row.optional else 'Choose…'),'choice',index=index)
    elif draft.page=='Appearance':
        field('Portrait','Choose portrait','choice',choice='portrait')
        # Valid categories come from the same native appearance type and actual rig.
        bodies=tuple(category for category in data.rigs[data.root_rig].slot_categories['body']
                     if category in ('NakedBody','NakedBody2','NakedBody3') and category in data.rigs[data.root_rig].clips['Idle'].sheets)
        heads=(None,*tuple(category for category in data.rigs[data.root_rig].slot_categories['head']
                          if category in ('Head1','Head9','Head10','Head16','Head17','Head22') and category in data.rigs[data.root_rig].clips['Idle'].sheets))
        body_index=bodies.index(build.appearance.body_category) if build.appearance.body_category in bodies else -1
        head_index=heads.index(build.appearance.head_category) if build.appearance.head_category in heads else -1
        field('Body',{'NakedBody':'Human','NakedBody2':'Skeleton','NakedBody3':'Body 3'}[build.appearance.body_category],'appearance',index=(body_index+1)%len(bodies),choice='body')
        field('Head',('Style '+build.appearance.head_category.removeprefix('Head')) if build.appearance.head_category else 'None','appearance',index=(head_index+1)%len(heads),choice='head')
        field('Beard','On' if build.appearance.has_beard else 'Off','appearance',choice='beard')
        for role,label in (('skin_tint','Skin'),('hair_tint','Hair'),('beard_tint','Beard color')):
            text(screen,font.body,label,(x,y+px(4)),MUTED)
            for index,color in enumerate((0xE6BC98,0xDDAA88,0x947657,0x684D3F,0x993F00,0xD0BFA1,0x181820,0xDBD5C1)):
                box=pygame.Rect(x+px(210)+index*px(42),y,px(34),px(30))
                pygame.draw.rect(screen,((color>>16)&255,(color>>8)&255,color&255),box)
                hits.append(CreatorHit(box,'appearance',index,role))
            y+=px(42)
    else:
        error=draft_error(build)
        summaries=(('Ready to deploy' if not error else error),
            f'{_label(build.species.value)} · {_label(build.background.value)} · Level {len(build.class_levels)}',
            ' → '.join(f'{_label(row.class_id.value)} {row.resulting_class_level}' for row in build.class_levels),
            'Starting gear: '+', '.join(reference_label(media,item_reference(media,item.item_id)) for item in build.item_loadout))
        for value in summaries:
            for line in wrap(value,font.body,content.width):
                text(screen,font.body,line,(x,y));y+=font.body.get_linesize()
            y+=px(12)
    screen.set_clip(previous)
    # Input matches the same content clipping as the visible controls.
    hits=[replace(hit,rect=hit.rect.clip(content)) if hit.verb!='page' else hit for hit in hits]
    hits=[hit for hit in hits if hit.rect.width and hit.rect.height]
    if draft.choice is not None:
        control('Back',pygame.Rect(rect.left,rect.bottom-px(36),px(100),px(34)),'back')
        allowed=len(draft.choice.values) in draft.choice.counts or draft.choice.optional and not draft.choice.values
        control('Apply choices',pygame.Rect(rect.right-px(190),rect.bottom-px(36),px(190),px(34)),'apply',enabled=allowed)
    else:
        control('Cancel edit',pygame.Rect(rect.left,rect.bottom-px(36),px(140),px(34)),'cancel')
        control('Use character',pygame.Rect(rect.right-px(190),rect.bottom-px(36),px(190),px(34)),'save',enabled=not draft_error(build))
    error=draft.status or draft_error(build)
    if error:
        text(screen,font.small,error,(rect.left,rect.bottom-px(62)),RED,max_width=rect.width)
    return tuple(hits),max(0,y+draft.scroll-content.bottom)


def draw_appearance(screen: pygame.Surface, build: CharacterBuild, data: AnimationData,
                    rows: LoadedBodyRows, rect: pygame.Rect, elapsed_ms: float) -> None:
    """Existing modular composition from appearance input, without a live Entity."""
    contact=ActorContact('creator-preview',(0,0),'S',build.appearance.visual_scale,
                         visual_scale_x=build.appearance.visual_scale_x,rig_id=data.root_rig)
    layers=resolve_actor_layers(data,build.appearance.config(),(),(),WeaponSet.MELEE,rig_id=data.root_rig)
    load_actor_media(data,((contact,layers,('Idle',)),),body_rows=rows)
    camera=Camera(viewport=screen.size,zoom=1.).with_focus((0,0)).with_screen_pan(
        (rect.centerx-screen.width/2,rect.bottom-screen.height/2))
    body=sample_idle_body(data,contact,elapsed_ms)
    previous=screen.get_clip();screen.set_clip(rect.clip(previous))
    for command in actor_draw_commands(data,body,contact,layers,rows,camera):
        screen.blit(command.surface,command.destination,special_flags=command.blend)
    screen.set_clip(previous)
