"""New Sorcerer spells use actual source-owned class choices and casts."""
from dataclasses import replace
import pytest
from dnd.content.characters.sorcerer_grants import apply_sorcerer_level
from dnd.core.dice import fixed_dice_faces
from dnd.types.character_progression import ClassChoiceSelection
from dnd.spells.evocation import SorcerousBurst, DancingLights, ChromaticOrb
from dnd.spells.necromancy import RayOfSickness
from dnd.spells.transmutation import DragonsBreath
from dnd.spells.illusion import PhantasmalForce
from tests.progression.test_direct_sorcerer_progression import _entity, _level
from tests.engine.test_bg3_rank_one_two_spells import game, combatant


def test_new_sorcerer_cantrips_and_first_level_spells_learn_from_exact_class_source(game):
    caster=_entity()
    first=_level(1)
    replacements={
        'class.sorcerer.level_1.cantrips':('spell.sorcerous_burst','spell.dancing_lights','spell.fire_bolt','spell.light'),
        'class.sorcerer.level_1.spell_known':('spell.chromatic_orb','spell.ray_of_sickness'),
    }
    choices=tuple(ClassChoiceSelection(choice.choice_id,replacements.get(choice.choice_id,choice.values)) for choice in first.choices)
    apply_sorcerer_level(caster,replace(first,choices=choices))
    caster.compose_entity()
    game.deploy_entity(caster,(2,2))
    enemy=combatant(game,'Enemy',(5,2),'foes')
    for spell in (SorcerousBurst,DancingLights,ChromaticOrb,RayOfSickness):
        action=next(action for action in caster.registered_actions if isinstance(action,spell))
        assert action.spellcasting_source_id in caster.spellcasting.sources
    burst=next(action for action in caster.registered_actions if isinstance(action,SorcerousBurst))
    hp=enemy.get_hp()
    with fixed_dice_faces(15,3):result=burst.instantiate(target_entity_uuid=enemy.uuid).apply()
    assert result is not None and not result.canceled
    assert enemy.get_hp()==hp-3,(hp,enemy.get_hp(),result.attack_outcome,result.damage_rolls)


@pytest.mark.parametrize('spell_id,spell_type',[('spell.dragons_breath',DragonsBreath),('spell.phantasmal_force',PhantasmalForce)])
def test_new_second_level_sorcerer_spell_can_be_selected_at_class_level_three(game,spell_id,spell_type):
    caster=_entity()
    for level in (1,2):apply_sorcerer_level(caster,_level(level))
    third=_level(3)
    choices=tuple(ClassChoiceSelection(choice.choice_id,(spell_id,)) if choice.choice_id=='class.sorcerer.level_3.spell_known'
        else choice for choice in third.choices)
    apply_sorcerer_level(caster,replace(third,choices=choices))
    action=next(action for action in caster.registered_actions if isinstance(action,spell_type))
    assert action.spellcasting_source_id in caster.spellcasting.sources
