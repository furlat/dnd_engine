"""Concrete spell-created creatures, composed from native actions and areas."""
from uuid import UUID
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from dnd.core.aoe import AoEShape, Sphere
from dnd.actions import Move, Dash, Disengage, SpellAction, SpellEvent, entity_action_economy_cost_evaluator
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.blocks.equipment import EquipmentConfig
from dnd.blocks.health import HealthConfig
from dnd.monsters.traits import InnateFlight, NaturalAttack
from pydantic_core import PydanticUndefined
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import ActionCategory, ActionOutcomeProfile, Cost, DamageRollProfile, OutcomeResolution, TargetType
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionTag, DurationType, HazardFilter
from dnd.core.content.dependencies import ContentDependency, ContentDependencyPhase, ContentDependencyRelation
from dnd.core.content.descriptors import ContentDescriptorSpec, ContentPresentation, ContentVisibility
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.materialization import CreatureBuildContext
from dnd.core.content.provenance import ContentFidelity, ContentProvenance, ContentProvenanceRelation, ContentReviewStatus
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import behavior_content_ref, creature_factory, get_content_declaration
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.effect_types import EffectOrigin
from dnd.core.spell_damage import roll_spell_damage
from dnd.core.events import Damage, Event, EventHandler, EventPhase, EventType, Range, RangeType, SpatialChangeEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.core.values import ModifiableValue, parts
from dnd.core.saving_throw_types import DamageSaveContext, SavingThrowContext
from dnd.entity import Entity, EntityConfig
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.environmental_conditions import FireSurface
from dnd.spatial.ignition import apply_elemental_surface_contacts
from dnd.spells.content_metadata import srd_action_identity, srd_condition_identity
from dnd.types.discovery import ActorScan
from dnd.types.summoning import DragonColor
from dnd.types.spatial_effects import SpatialEffectAnchorKind, SpatialEffectLayer, SpatialEffectOccupancyPolicy, SpatialEffectTriggerKind
from dnd.types.world import MovementMode


@srd_action_identity(content_id="action.spell.spiritual_weapon.strike",display_name="Spiritual Weapon Strike",
    description="Native bonus-action force attack using the summoner's retained casting modifier.",
    parent_spell_name="Spiritual Weapon",source_page=179,sort_order=3261,
    adaptation_notes="BG3 autonomous spell creature; native natural-attack composition.")
class SpiritualWeaponStrike(NaturalAttack):
    name: str = "Spiritual Weapon Strike"
    natural_damage_dice: Literal[4,6,8,10,12,20] = 8
    natural_damage_type: DamageType = DamageType.FORCE
    magical: bool = True
    costs: list[Cost] = Field(default_factory=lambda:[Cost(name="Spiritual Weapon Strike",cost_type="bonus_actions",
        cost=1,evaluator=entity_action_economy_cost_evaluator)])


class SpellSummonParameters(BaseModel):
    model_config=ConfigDict(extra="forbid",frozen=True)
    caster_uuid: UUID | None = None
    casting_modifier: int = 0
    proficiency: int = 2
    slot_level: int = Field(default=2,ge=2,le=9)
    spell_dc: int = 12
    attack_bonus: int = 0
    dragon_color: DragonColor = DragonColor.RED
    effect_origin: EffectOrigin | None = None


def _sphere_damage(caster_uuid: UUID,target: Entity,*,dc: int,dice_count: int,event: Event,
                   origin: EffectOrigin | None,context: SavingThrowContext | None=None,
                   source_condition_uuid: UUID | None=None):
    caster=Entity.get(caster_uuid)
    if caster is None:
        return
    request=caster.create_saving_throw_request(target.uuid,"dexterity",dc,parent_event=event.uuid,saving_throw_context=context)
    _,_,saved=target.saving_throw(request)
    damage=Damage(name="Flaming Sphere",source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,
        damage_dice=6,dice_numbers=dice_count,damage_type=DamageType.FIRE,effect_origin=origin,
        damage_bonus=parts(ModifiableValue(source_entity_uuid=caster.uuid,base=0)))
    roll=roll_spell_damage(damage, parent_event=event, attack_outcome=AttackOutcome.HIT, effect_origin=origin)
    target.receive_damage(roll.total//2 if saved else roll.total,DamageType.FIRE,caster.uuid,
        damages=[damage],damage_rolls=[roll],parent_event=event.uuid,effect_origin=origin,source_condition_uuid=source_condition_uuid,
        damage_save=DamageSaveContext(ability="dexterity", success=saved, success_fraction=0.5))


@srd_condition_identity(content_id="spatial_effect.spell.flaming_sphere.aura",display_name="Flaming Sphere Aura",
    description="Enemies ending their turn within five feet make a Dexterity save for half fire damage.")
class FlamingSphereZone(AreaCondition):
    name: str = "Flaming Sphere Aura"
    description: str = "Enemies ending their turn within five feet make a Dexterity save for half fire damage."
    anchor_kind: SpatialEffectAnchorKind = SpatialEffectAnchorKind.ENTITY
    anchor_uuid: UUID = Field(default=PydanticUndefined,validate_default=True)
    layer: SpatialEffectLayer = SpatialEffectLayer.FIELD
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    area: AoEShape = Sphere(radius_feet=5)
    spell_dc: int
    dice_count: int = 2
    hazard_filter: HazardFilter = HazardFilter.ENEMIES
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.TURN_END})
    duration: Duration = Field(default_factory=lambda:Duration(duration_type=DurationType.PERMANENT))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    has_visible_presence: bool = True

    def relocate_anchor(self,position,*,parent_event):
        return self.move_zone(position,parent_event=parent_event)

    def _create_zone_turn_end_handler(self):
        def expose(event: Event,_: UUID):
            target=Entity.get(event.source_entity_uuid)
            caster=Entity.get(self.source_entity_uuid)
            if target is not None and caster is not None and caster.is_enemy(target):
                _sphere_damage(self.source_entity_uuid,target,dc=self.spell_dc,dice_count=self.dice_count,
                    event=event,origin=self.effect_origin,source_condition_uuid=self.uuid,
                    context=self.saving_throw_context(effect_id="spell.flaming_sphere.aura"))
            return None
        return EventHandler(name="Flaming Sphere end-turn aura",source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END,event_phase=EventPhase.EXECUTION)],event_processor=expose)


class FlamingSphereAura(BaseCondition):
    creates = (FireSurface, FlamingSphereZone)
    name: str = "Flaming Sphere Fire"
    description: str = "Owns the moving fire aura, light and native fire-trail handler."
    duration: Duration = Field(default_factory=lambda:Duration(duration_type=DurationType.PERMANENT))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    spell_dc: int
    dice_count: int = 2
    light_source_uuid: UUID | None = None

    def _apply(self,event: Event):
        sphere=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        caster=Entity.get(self.source_entity_uuid)
        if sphere is None or caster is None:
            return [],[],[],[],event.cancel(status_message="Sphere owner is absent")
        zone=FlamingSphereZone(source_entity_uuid=caster.uuid,position=sphere.position,anchor_uuid=sphere.uuid,
            faction=caster.faction,spell_dc=self.spell_dc,dice_count=self.dice_count,
            effect_origin=self.effect_origin,content_ref=get_content_declaration(FlamingSphereZone).ref)
        admitted=zone.activate(parent_event=event)
        if admitted is None or admitted.canceled:
            return [],[],[],[],event.cancel(status_message="Sphere aura was rejected")
        self.add_linked_condition(zone.uuid,zone.uuid)
        self.light_source_uuid=get_map().add_light_source(sphere.position,bright_radius_feet=20,dim_radius_feet=20,
            anchor_uuid=sphere.uuid,contribution_owner_uuid=self.uuid,parent_event=event.uuid)
        def trail(change: Event,_: UUID):
            if isinstance(change,SpatialChangeEvent) and change.entity_uuid==sphere.uuid and change.old_position is not None:
                patch=FireSurface(source_entity_uuid=caster.uuid,position=change.old_position,
                    affected_positions={change.old_position},effect_origin=self.effect_origin)
                patch.activate(parent_event=change)
                apply_elemental_surface_contacts(change,{change.old_position},DamageType.FIRE)
            return None
        def object_contacts(turn: Event,_: UUID):
            active=BaseCondition.get(zone.uuid)
            if isinstance(active,FlamingSphereZone):
                positions={cell for cell in active.affected_positions if active.allows_contribution_at(cell)}
                objects={identity for position in positions for identity in get_map().get_objects_at(position)}
                for identity in sorted(objects,key=str):
                    item=BaseBlock.get(identity)
                    if not isinstance(item,BaseItem) or not item.is_active or not item.is_targetable or not item.is_breakable():
                        continue
                    damage=Damage(name="Flaming Sphere object contact",source_entity_uuid=caster.uuid,target_entity_uuid=item.uuid,
                        damage_dice=6,dice_numbers=self.dice_count,damage_type=DamageType.FIRE,effect_origin=self.effect_origin,
                        damage_bonus=parts(ModifiableValue(source_entity_uuid=caster.uuid,base=0)))
                    roll=roll_spell_damage(damage, parent_event=turn, attack_outcome=AttackOutcome.HIT, effect_origin=self.effect_origin)
                    item.receive_damage(roll.total,DamageType.FIRE,caster.uuid,damages=[damage],damage_rolls=[roll],parent_event=turn)
                apply_elemental_surface_contacts(turn,positions,DamageType.FIRE)
            return None
        handlers=[EventHandler(name="Flaming Sphere trail",source_entity_uuid=sphere.uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED,event_phase=EventPhase.EFFECT)],event_processor=trail),
            EventHandler(name="Flaming Sphere fire contacts",source_entity_uuid=sphere.uuid,
                trigger_conditions=[Trigger(event_type=EventType.TURN_END,event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=sphere.uuid)],event_processor=object_contacts)]
        for handler in handlers:sphere.add_event_handler(handler)
        return [],[handler.uuid for handler in handlers],[],[],event.phase_to(EventPhase.EFFECT)

    def _release_owned_runtime_state(self,*,parent_event: Event | None=None):
        if self.light_source_uuid is not None:
            get_map().remove_light_source(self.light_source_uuid,parent_event=parent_event.uuid if parent_event else None)
            self.light_source_uuid=None
        super()._release_owned_runtime_state(parent_event=parent_event)


@srd_action_identity(content_id="action.spell.flaming_sphere.ram",display_name="Flaming Sphere Ram",
    description="The summoned sphere spends its bonus action on a saved fire ram.",
    parent_spell_name="Flaming Sphere",source_page=146,sort_order=3260,adaptation_notes="BG3 autonomous native creature bonus-action Ram.")
class FlamingSphereRam(SpellAction):
    name: str = "Flaming Sphere Ram"
    description: str = "Five-foot contact, retained caster DC, fire damage; Dexterity save for half."
    action_category: ActionCategory = ActionCategory.ABILITY
    spell_level: int = 2
    spell_school: str = "conjuration"
    spell_damage_type: DamageType = DamageType.FIRE
    alt_skip_slot: bool = True
    verbal: bool = False
    alt_cost_type: str | None = "bonus_actions"
    target_type: TargetType = TargetType.ENTITY
    spell_range: Range = Field(default_factory=lambda:Range(type=RangeType.REACH,normal=5))
    original_caster_uuid: UUID
    spell_dc: int
    dice_count: int = 2
    effect_origin: EffectOrigin | None = None

    def get_outcome_profile(self):
        return ActionOutcomeProfile(resolution=OutcomeResolution.SAVING_THROW,save_dc=self.spell_dc,save_ability="dexterity",
            half_damage_on_save=True,damage_rolls=(DamageRollProfile(dice_count=self.dice_count,die_size=6,damage_type="Fire"),))

    def _sphere_is_present(self) -> bool:
        actor=Entity.get(self.source_entity_uuid)
        return actor is not None and actor.has_runtime_agency() and any(condition.get_display_name()=="Summoned"
            and condition.contributions_active() for condition in actor.active_conditions_by_uuid.values())

    def _create_declaration_event(self,parent_event=None,use_register=True):
        event=super()._create_declaration_event(parent_event,use_register)
        return event.with_updates(retained_effect_origin=self.effect_origin) if isinstance(event,SpellEvent) else event

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        if not self._sphere_is_present():
            return "Sphere existence is absent or suppressed"
        return self.single_recipient_error(scan, selection)

    def _apply(self,event):
        effect=event.phase_to(EventPhase.EFFECT)
        target=Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        if not effect.canceled and target is not None and self._sphere_is_present():
            _sphere_damage(self.original_caster_uuid,target,dc=self.spell_dc,dice_count=self.dice_count,event=effect,origin=self.effect_origin)
        return effect


def _declare_spell_creature(key: str,name: str):
    def factory(raw_context: object,parameters: SpellSummonParameters):
        context=CreatureBuildContext.model_validate(raw_context)
        sphere=key=="flaming_sphere"
        steps=(parameters.slot_level-2)//2
        immune=(DamageType.FIRE,DamageType.NECROTIC,DamageType.POISON,DamageType.PSYCHIC) if sphere else (DamageType.POISON,DamageType.PSYCHIC)
        resistant=(DamageType.BLUDGEONING,DamageType.PIERCING,DamageType.SLASHING,DamageType.ACID,DamageType.LIGHTNING) if sphere else tuple(kind for kind in DamageType if kind not in immune)
        entity=Entity.create(context.runtime_entity_uuid,context.display_name,content_ref=context.requested_ref,
            config=EntityConfig(faction=context.faction,position=context.position,creature_type=CreatureType.ELEMENTAL if sphere else CreatureType.CONSTRUCT,
                requires_breathing=False,health=HealthConfig(max_hit_points_bonus=20 if sphere else 20+8*steps,
                    immunities=list(immune),resistances=list(resistant),vulnerabilities=[DamageType.COLD] if sphere else []),
                equipment=EquipmentConfig(unarmored_ac=16 if sphere else 10),
                action_economy=ActionEconomyConfig(movement=30 if sphere else 20,reactions=0)))
        entity.register_action(Move(source_entity_uuid=entity.uuid,template=True,
            movement_mode=MovementMode.WALKING if sphere else MovementMode.FLYING))
        entity.register_action(Dash(source_entity_uuid=entity.uuid,template=True))
        entity.register_action(Disengage(source_entity_uuid=entity.uuid,template=True))
        if sphere:
            entity.register_action(FlamingSphereRam(source_entity_uuid=entity.uuid,template=True,
                original_caster_uuid=parameters.caster_uuid or entity.uuid,spell_dc=parameters.spell_dc,
                dice_count=parameters.slot_level,effect_origin=parameters.effect_origin))
        else:
            entity.add_condition(InnateFlight(source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,flying_speed=20))
            entity.register_action(SpiritualWeaponStrike(source_entity_uuid=entity.uuid,template=True,name="Spiritual Weapon Strike",
                costs=[Cost(name="Spiritual Weapon Strike",cost_type="bonus_actions",cost=1,evaluator=entity_action_economy_cost_evaluator)],
                natural_damage_dice=8,natural_dice_numbers=1+steps,natural_damage_type=DamageType.FORCE,
                natural_range=Range(type=RangeType.REACH,normal=5),magical=True,
                fixed_attack_bonus=parameters.proficiency+parameters.casting_modifier,
                fixed_damage_bonus=1+parameters.casting_modifier))
        return entity
    factory.__name__=f"build_{key}"
    factory.__qualname__=factory.__name__
    dependencies=tuple(ContentDependency(relation=ContentDependencyRelation.GRANTS_ACTION,
        target_ref=get_content_declaration(action).ref,phase=ContentDependencyPhase.RUNTIME_REFERENCE)
        for action in (Move,Dash,Disengage,FlamingSphereRam if key=="flaming_sphere" else SpiritualWeaponStrike))
    if key=="spiritual_weapon":
        dependencies+=(ContentDependency(relation=ContentDependencyRelation.APPLIES_CONDITION,
            target_ref=behavior_content_ref(pack_id="content.srd_5_1_cc",content_id="trait.innate_flight",version=1,
                definition_kind=ContentDefinitionKind.TRAIT,runtime_behavior_kind=RuntimeBehaviorKind.CONDITION)),)
    decorated=creature_factory(pack_id="content.neurodragon",content_id=f"creature.spell.{key}",version=1,
        parameters=SpellSummonParameters,descriptor=ContentDescriptorSpec(display_name=name,
            description=f"BG3-style {name} using native summon rules and its caster's controller.",tags=("creature","spell_summon","construct"),
            visibility=ContentVisibility.PUBLIC,presentation=ContentPresentation(ui_group="creatures.spell_summon")),
        provenance=ContentProvenance(primary_source_id="neurodragon.original_b2b3930",source_anchor=f"BG3-style {name}",
            relation=ContentProvenanceRelation.COMPATIBLE_ADAPTATION,adapted_from_source_id="wotc.srd_5_1_cc",
            fidelity=ContentFidelity.PARTIAL,review_status=ContentReviewStatus.REVIEWED,
            notes="Approved native creature adaptation; summons follow their caster's controller."),dependencies=dependencies)(factory)
    return get_content_declaration(decorated)


SPIRITUAL_WEAPON_DECLARATION=_declare_spell_creature("spiritual_weapon","Spiritual Weapon")
FLAMING_SPHERE_DECLARATION=_declare_spell_creature("flaming_sphere","Flaming Sphere")
SPELL_SUMMON_DECLARATIONS=(SPIRITUAL_WEAPON_DECLARATION,FLAMING_SPHERE_DECLARATION)
SPIRITUAL_WEAPON_RECIPE=ContentRecipe.create(ref=SPIRITUAL_WEAPON_DECLARATION.ref,parameters={})
FLAMING_SPHERE_RECIPE=ContentRecipe.create(ref=FLAMING_SPHERE_DECLARATION.ref,parameters={})
