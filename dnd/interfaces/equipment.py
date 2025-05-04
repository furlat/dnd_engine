# dnd/interfaces/equipment.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Any
from uuid import UUID, uuid4

from dnd.core.modifiers import DamageType
from dnd.core.events import RangeType, WeaponSlot
from dnd.interfaces.values import ModifiableValueSnapshot
from dnd.interfaces.abilities import AbilityName

class RangeSnapshot(BaseModel):
    """Interface model for weapon Range"""
    type: RangeType
    normal: int
    long: Optional[int] = None
    
    @classmethod
    def from_engine(cls, range_obj):
        """Create a snapshot from an engine Range object"""
        return cls(
            type=range_obj.type,
            normal=range_obj.normal,
            long=range_obj.long
        )

class DamageSnapshot(BaseModel):
    """Interface model for weapon Damage"""
    uuid: UUID
    name: str
    damage_dice: int
    dice_numbers: int
    damage_bonus: Optional[ModifiableValueSnapshot] = None
    damage_type: DamageType
    source_entity_uuid: UUID
    target_entity_uuid: Optional[UUID] = None
    
    @classmethod
    def from_engine(cls, damage):
        """Create a snapshot from an engine Damage object"""
        return cls(
            uuid=damage.uuid,
            name=damage.name,
            damage_dice=damage.damage_dice,
            dice_numbers=damage.dice_numbers,
            damage_bonus=ModifiableValueSnapshot.from_engine(damage.damage_bonus) if damage.damage_bonus else None,
            damage_type=damage.damage_type,
            source_entity_uuid=damage.source_entity_uuid,
            target_entity_uuid=damage.target_entity_uuid
        )

class WeaponSnapshot(BaseModel):
    """Interface model for a Weapon"""
    uuid: UUID
    name: str
    description: Optional[str] = None
    damage_dice: int
    dice_numbers: int
    damage_type: DamageType
    damage_bonus: Optional[ModifiableValueSnapshot] = None
    attack_bonus: ModifiableValueSnapshot
    range: RangeSnapshot
    properties: List[str]  # WeaponProperty values as strings
    
    # Extra damage information
    extra_damages: List[DamageSnapshot] = Field(default_factory=list)
    
    @classmethod
    def from_engine(cls, weapon):
        """Create a snapshot from an engine Weapon object"""
        # Create extra damages
        extra_damages = []
        for i in range(len(weapon.extra_damage_dices)):
            if i < len(weapon.extra_damage_dices_numbers) and i < len(weapon.extra_damage_type):
                damage = DamageSnapshot(
                    uuid=uuid4(),  # Generate a new UUID as this doesn't exist in the engine
                    name=f"Extra damage {i+1}",
                    damage_dice=weapon.extra_damage_dices[i],
                    dice_numbers=weapon.extra_damage_dices_numbers[i],
                    damage_bonus=ModifiableValueSnapshot.from_engine(weapon.extra_damage_bonus[i]) 
                        if i < len(weapon.extra_damage_bonus) else None,
                    damage_type=weapon.extra_damage_type[i],
                    source_entity_uuid=weapon.source_entity_uuid,
                    target_entity_uuid=weapon.target_entity_uuid
                )
                extra_damages.append(damage)
        
        return cls(
            uuid=weapon.uuid,
            name=weapon.name,
            description=weapon.description,
            damage_dice=weapon.damage_dice,
            dice_numbers=weapon.dice_numbers,
            damage_type=weapon.damage_type,
            damage_bonus=ModifiableValueSnapshot.from_engine(weapon.damage_bonus) if weapon.damage_bonus else None,
            attack_bonus=ModifiableValueSnapshot.from_engine(weapon.attack_bonus),
            range=RangeSnapshot.from_engine(weapon.range),
            properties=[prop.value for prop in weapon.properties],
            extra_damages=extra_damages
        )

class ShieldSnapshot(BaseModel):
    """Interface model for a Shield"""
    uuid: UUID
    name: str
    description: Optional[str] = None
    ac_bonus: ModifiableValueSnapshot
    
    @classmethod
    def from_engine(cls, shield):
        """Create a snapshot from an engine Shield object"""
        return cls(
            uuid=shield.uuid,
            name=shield.name,
            description=shield.description,
            ac_bonus=ModifiableValueSnapshot.from_engine(shield.ac_bonus)
        )

class ArmorSnapshot(BaseModel):
    """Interface model for Armor"""
    uuid: UUID
    name: str
    description: Optional[str] = None
    type: str  # ArmorType value as string
    body_part: str  # BodyPart value as string
    ac: ModifiableValueSnapshot
    max_dex_bonus: ModifiableValueSnapshot
    
    # Requirements
    strength_requirement: Optional[int] = None
    dexterity_requirement: Optional[int] = None
    intelligence_requirement: Optional[int] = None
    constitution_requirement: Optional[int] = None
    charisma_requirement: Optional[int] = None
    wisdom_requirement: Optional[int] = None
    stealth_disadvantage: Optional[bool] = None
    
    @classmethod
    def from_engine(cls, armor):
        """Create a snapshot from an engine Armor object"""
        return cls(
            uuid=armor.uuid,
            name=armor.name,
            description=armor.description,
            type=armor.type.value,
            body_part=armor.body_part.value,
            ac=ModifiableValueSnapshot.from_engine(armor.ac),
            max_dex_bonus=ModifiableValueSnapshot.from_engine(armor.max_dex_bonus),
            strength_requirement=armor.strength_requirement,
            dexterity_requirement=armor.dexterity_requirement,
            intelligence_requirement=armor.intelligence_requirement,
            constitution_requirement=armor.constitution_requirement,
            charisma_requirement=armor.charisma_requirement,
            wisdom_requirement=armor.wisdom_requirement,
            stealth_disadvantage=armor.stealth_disadvantage
        )

class EquipmentSnapshot(BaseModel):
    """Interface model for Equipment"""
    uuid: UUID
    name: str
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    
    # Equipped items
    helmet: Optional[ArmorSnapshot] = None
    body_armor: Optional[ArmorSnapshot] = None
    gauntlets: Optional[ArmorSnapshot] = None
    greaves: Optional[ArmorSnapshot] = None
    boots: Optional[ArmorSnapshot] = None
    amulet: Optional[ArmorSnapshot] = None
    ring_left: Optional[ArmorSnapshot] = None
    ring_right: Optional[ArmorSnapshot] = None
    cloak: Optional[ArmorSnapshot] = None
    weapon_main_hand: Optional[WeaponSnapshot] = None
    weapon_off_hand: Optional[Union[WeaponSnapshot, ShieldSnapshot]] = None
    
    # Core values
    unarmored_ac_type: str  # UnarmoredAc value as string
    unarmored_ac: ModifiableValueSnapshot
    ac_bonus: ModifiableValueSnapshot
    damage_bonus: ModifiableValueSnapshot
    attack_bonus: ModifiableValueSnapshot
    melee_attack_bonus: ModifiableValueSnapshot
    ranged_attack_bonus: ModifiableValueSnapshot
    melee_damage_bonus: ModifiableValueSnapshot
    ranged_damage_bonus: ModifiableValueSnapshot
    
    # Unarmed attack properties
    unarmed_attack_bonus: ModifiableValueSnapshot
    unarmed_damage_bonus: ModifiableValueSnapshot
    unarmed_damage_type: DamageType
    unarmed_damage_dice: int
    unarmed_dice_numbers: int
    unarmed_properties: List[str] = Field(default_factory=list)  # WeaponProperty values as strings
    
    # Total Armor Class – computed from the owning entity if available
    armor_class: Optional[int] = None
    
    @classmethod
    def from_engine(cls, equipment, entity: Optional[Any] = None):
        """Create a snapshot from an engine Equipment object"""
        # Handle optional armor pieces
        helmet = ArmorSnapshot.from_engine(equipment.helmet) if equipment.helmet else None
        body_armor = ArmorSnapshot.from_engine(equipment.body_armor) if equipment.body_armor else None
        gauntlets = ArmorSnapshot.from_engine(equipment.gauntlets) if equipment.gauntlets else None
        greaves = ArmorSnapshot.from_engine(equipment.greaves) if equipment.greaves else None
        boots = ArmorSnapshot.from_engine(equipment.boots) if equipment.boots else None
        amulet = ArmorSnapshot.from_engine(equipment.amulet) if equipment.amulet else None
        ring_left = ArmorSnapshot.from_engine(equipment.ring_left) if equipment.ring_left else None
        ring_right = ArmorSnapshot.from_engine(equipment.ring_right) if equipment.ring_right else None
        cloak = ArmorSnapshot.from_engine(equipment.cloak) if equipment.cloak else None
        
        # Handle weapons/shield
        weapon_main_hand = None
        if equipment.weapon_main_hand:
            weapon_main_hand = WeaponSnapshot.from_engine(equipment.weapon_main_hand)
            
        weapon_off_hand = None
        if equipment.weapon_off_hand:
            if hasattr(equipment.weapon_off_hand, 'ac_bonus'):  # Check if it's a shield
                weapon_off_hand = ShieldSnapshot.from_engine(equipment.weapon_off_hand)
            else:
                weapon_off_hand = WeaponSnapshot.from_engine(equipment.weapon_off_hand)
        
        # Calculate final AC if the full Entity is provided (so that ability modifiers and other bonuses
        # can be taken into account). We purposefully keep this optional so that callers such as the
        # standalone `/equipment` API or other internal usages that don't have an Entity handy can still
        # rely on this method.

        final_ac: Optional[int] = None
        if entity is not None:
            try:
                # Entity.ac_bonus returns a ModifiableValue – we need the normalized score only.
                ac_value = entity.ac_bonus()
                final_ac = ac_value.normalized_score if hasattr(ac_value, "normalized_score") else None
            except Exception:
                # In the unlikely event of an error (for example, the entity is missing required data),
                # we fall back to None so that API callers still receive a valid response rather than a 500.
                final_ac = None

        return cls(
            uuid=equipment.uuid,
            name=equipment.name,
            source_entity_uuid=equipment.source_entity_uuid,
            source_entity_name=equipment.source_entity_name,
            helmet=helmet,
            body_armor=body_armor,
            gauntlets=gauntlets,
            greaves=greaves,
            boots=boots,
            amulet=amulet,
            ring_left=ring_left,
            ring_right=ring_right,
            cloak=cloak,
            weapon_main_hand=weapon_main_hand,
            weapon_off_hand=weapon_off_hand,
            unarmored_ac_type=equipment.unarmored_ac_type.value,
            unarmored_ac=ModifiableValueSnapshot.from_engine(equipment.unarmored_ac),
            ac_bonus=ModifiableValueSnapshot.from_engine(equipment.ac_bonus),
            damage_bonus=ModifiableValueSnapshot.from_engine(equipment.damage_bonus),
            attack_bonus=ModifiableValueSnapshot.from_engine(equipment.attack_bonus),
            melee_attack_bonus=ModifiableValueSnapshot.from_engine(equipment.melee_attack_bonus),
            ranged_attack_bonus=ModifiableValueSnapshot.from_engine(equipment.ranged_attack_bonus),
            melee_damage_bonus=ModifiableValueSnapshot.from_engine(equipment.melee_damage_bonus),
            ranged_damage_bonus=ModifiableValueSnapshot.from_engine(equipment.ranged_damage_bonus),
            unarmed_attack_bonus=ModifiableValueSnapshot.from_engine(equipment.unarmed_attack_bonus),
            unarmed_damage_bonus=ModifiableValueSnapshot.from_engine(equipment.unarmed_damage_bonus),
            unarmed_damage_type=equipment.unarmed_damage_type,
            unarmed_damage_dice=equipment.unarmed_damage_dice,
            unarmed_dice_numbers=equipment.unarmed_dice_numbers,
            unarmed_properties=[prop.value for prop in equipment.unarmed_properties],
            armor_class=final_ac
        )

class AttackBonusCalculationSnapshot(BaseModel):
    """Model representing the detailed calculation of an attack bonus"""
    weapon_slot: WeaponSlot
    
    # The component parts
    proficiency_bonus: ModifiableValueSnapshot
    weapon_bonus: ModifiableValueSnapshot
    attack_bonuses: List[ModifiableValueSnapshot]
    ability_bonuses: List[ModifiableValueSnapshot]
    range: RangeSnapshot
    
    # Weapon information
    weapon_name: Optional[str] = None
    is_unarmed: bool = False
    is_ranged: bool = False
    properties: List[str] = Field(default_factory=list)
    
    # Cross-entity effects
    has_cross_entity_effects: bool = False
    target_entity_uuid: Optional[UUID] = None
    
    # The final combined result
    total_bonus: ModifiableValueSnapshot
    
    # Shortcut to commonly needed values
    final_modifier: int
    
    @classmethod
    def from_engine(cls, entity, weapon_slot=WeaponSlot.MAIN_HAND):
        """
        Create a snapshot of the attack bonus calculation from an entity
        
        Args:
            entity: The engine Entity object
            weapon_slot: The weapon slot to calculate for
        """
        # Get all the components using entity._get_attack_bonuses
        proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, range_obj = entity._get_attack_bonuses(weapon_slot)
        
        # Determine if this is a weapon attack or unarmed
        is_unarmed = entity.equipment.is_unarmed(weapon_slot)
        
        # Determine if this is a ranged attack
        is_ranged = entity.equipment.is_ranged(weapon_slot) if not is_unarmed else False
        
        # Get weapon properties if applicable
        properties = []
        weapon_name = None
        if not is_unarmed:
            weapon = entity.equipment.weapon_main_hand if weapon_slot == WeaponSlot.MAIN_HAND else entity.equipment.weapon_off_hand
            if hasattr(weapon, 'properties'):  # If it's not a shield
                properties = [prop.value for prop in weapon.properties]
                weapon_name = weapon.name
        
        # Calculate the total bonus
        total_bonus = entity.attack_bonus(weapon_slot)
        
        return cls(
            weapon_slot=weapon_slot,
            proficiency_bonus=ModifiableValueSnapshot.from_engine(proficiency_bonus),
            weapon_bonus=ModifiableValueSnapshot.from_engine(weapon_bonus),
            attack_bonuses=[ModifiableValueSnapshot.from_engine(bonus) for bonus in attack_bonuses],
            ability_bonuses=[ModifiableValueSnapshot.from_engine(bonus) for bonus in ability_bonuses],
            range=RangeSnapshot.from_engine(range_obj),
            weapon_name=weapon_name,
            is_unarmed=is_unarmed,
            is_ranged=is_ranged,
            properties=properties,
            has_cross_entity_effects=entity.target_entity_uuid is not None,
            target_entity_uuid=entity.target_entity_uuid,
            total_bonus=ModifiableValueSnapshot.from_engine(total_bonus),
            final_modifier=total_bonus.normalized_score
        )

class ACBonusCalculationSnapshot(BaseModel):
    """Model representing the detailed calculation of AC bonus"""
    # Armor state
    is_unarmored: bool
    
    # Components for unarmored calculation
    unarmored_values: Optional[List[ModifiableValueSnapshot]] = None
    unarmored_abilities: Optional[List[AbilityName]] = None
    ability_bonuses: Optional[List[ModifiableValueSnapshot]] = None
    ability_modifier_bonuses: Optional[List[ModifiableValueSnapshot]] = None
    
    # Components for armored calculation
    armored_values: Optional[List[ModifiableValueSnapshot]] = None
    max_dexterity_bonus: Optional[ModifiableValueSnapshot] = None
    dexterity_bonus: Optional[ModifiableValueSnapshot] = None
    dexterity_modifier_bonus: Optional[ModifiableValueSnapshot] = None
    combined_dexterity_bonus: Optional[ModifiableValueSnapshot] = None
    
    # Cross-entity effects
    has_cross_entity_effects: bool = False
    target_entity_uuid: Optional[UUID] = None
    
    # The final combined result
    total_bonus: ModifiableValueSnapshot
    
    # Shortcut to commonly needed values
    final_ac: int
    
    @classmethod
    def from_engine(cls, entity):
        """
        Create a snapshot of the AC bonus calculation from an entity
        
        Args:
            entity: The engine Entity object
        """
        is_unarmored = entity.equipment.is_unarmored()
        
        # Initialize variables for both paths
        unarmored_values = None
        unarmored_abilities = None
        ability_bonuses = None
        ability_modifier_bonuses = None
        armored_values = None
        max_dexterity_bonus = None
        dexterity_bonus = None
        dexterity_modifier_bonus = None
        combined_dexterity_bonus = None
        
        # Calculate AC using the same logic as entity.ac_bonus
        if is_unarmored:
            # Get unarmored values
            unarmored_values_raw = entity.equipment.get_unarmored_ac_values()
            unarmored_values = [ModifiableValueSnapshot.from_engine(value) for value in unarmored_values_raw]
            
            # Get ability bonuses
            unarmored_abilities = entity.equipment.get_unarmored_abilities()
            ability_bonuses_raw = [entity.ability_scores.get_ability(ability).ability_score for ability in unarmored_abilities]
            ability_bonuses = [ModifiableValueSnapshot.from_engine(bonus) for bonus in ability_bonuses_raw]
            
            ability_modifier_bonuses_raw = [entity.ability_scores.get_ability(ability).modifier_bonus for ability in unarmored_abilities]
            ability_modifier_bonuses = [ModifiableValueSnapshot.from_engine(bonus) for bonus in ability_modifier_bonuses_raw]
        else:
            # Get armored values
            armored_values_raw = entity.equipment.get_armored_ac_values()
            armored_values = [ModifiableValueSnapshot.from_engine(value) for value in armored_values_raw]
            
            # Get dexterity bonuses
            max_dexterity_bonus_raw = entity.equipment.get_armored_max_dex_bonus()
            max_dexterity_bonus = ModifiableValueSnapshot.from_engine(max_dexterity_bonus_raw)
            
            dexterity_bonus_raw = entity.ability_scores.get_ability("dexterity").ability_score
            dexterity_bonus = ModifiableValueSnapshot.from_engine(dexterity_bonus_raw)
            
            dexterity_modifier_bonus_raw = entity.ability_scores.get_ability("dexterity").modifier_bonus
            dexterity_modifier_bonus = ModifiableValueSnapshot.from_engine(dexterity_modifier_bonus_raw)
            
            combined_dexterity_bonus_raw = dexterity_bonus_raw.combine_values([dexterity_modifier_bonus_raw])
            if combined_dexterity_bonus_raw.normalized_score > max_dexterity_bonus_raw.normalized_score:
                combined_dexterity_bonus_raw = max_dexterity_bonus_raw
            combined_dexterity_bonus = ModifiableValueSnapshot.from_engine(combined_dexterity_bonus_raw)
        
        # Calculate the final AC
        total_bonus = entity.ac_bonus()
        
        return cls(
            is_unarmored=is_unarmored,
            unarmored_values=unarmored_values,
            unarmored_abilities=unarmored_abilities,
            ability_bonuses=ability_bonuses,
            ability_modifier_bonuses=ability_modifier_bonuses,
            armored_values=armored_values,
            max_dexterity_bonus=max_dexterity_bonus,
            dexterity_bonus=dexterity_bonus,
            dexterity_modifier_bonus=dexterity_modifier_bonus,
            combined_dexterity_bonus=combined_dexterity_bonus,
            has_cross_entity_effects=entity.target_entity_uuid is not None,
            target_entity_uuid=entity.target_entity_uuid,
            total_bonus=ModifiableValueSnapshot.from_engine(total_bonus),
            final_ac=total_bonus.normalized_score
        )