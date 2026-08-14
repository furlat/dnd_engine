export declare const PLAYER_REPLICATION_CONTRACT_VERSION: 3;
export declare const PLAYER_REPLICATION_CONTRACT_HASH: "bd9a978880d9e275ecb8af92fd7ca2129fa576a7cb2906775b7821b48e4dfca7";
export declare const OBJECTIVE_REPLAY_CONTRACT_VERSION: 2;
export declare const OBJECTIVE_REPLAY_CONTRACT_HASH: "68504ead03238ae5fd517d40edadd3c90b4ec6068cf8ffb86d092d5c686eff10";
export declare const PLAYER_REPLAY_CONTRACT_VERSION: 3;
export declare const PLAYER_REPLAY_CONTRACT_HASH: "1227cf4a155e03eb78e096a153e242f9f9023979de9eeb4176cd3a29bc1ffb28";
export declare const TIMELINE_CONTRACT_VERSION: 2;
export declare const TIMELINE_CONTRACT_HASH: "ed39a92fb7f6cc521d17ab0f3ca23557224947b1f47a846b85f8b4e7367dd078";
export declare const SDK_CONTRACT_VERSION: 1;
export declare const SDK_CONTRACT_HASH: "ec9c776e54d8a915723da0c61ffed382615db67fab218f2f27d893700ceb4eae";
export declare const EVENT_CONTRACT_VERSION: 2;
export declare const EVENT_CONTRACT_HASH: "601efd9c563e0134d11bb6802982e9be617242e867d42dcadb58d4ab14bfc551";
export type JsonPrimitive = null | boolean | number | string;
export type JsonValue = JsonPrimitive | ReadonlyArray<JsonValue> | {
    readonly [key: string]: JsonValue;
};
export type ContractDescriptor = {
    readonly kind: 'json';
    readonly python?: string;
} | {
    readonly kind: 'null' | 'boolean';
} | {
    readonly kind: 'string';
    readonly min_length?: number;
    readonly max_length?: number;
} | {
    readonly kind: 'number' | 'integer';
    readonly minimum?: number;
    readonly exclusive_minimum?: number;
    readonly maximum?: number;
    readonly exclusive_maximum?: number;
} | {
    readonly kind: 'literal';
    readonly value: JsonValue;
} | {
    readonly kind: 'enum' | 'model';
    readonly ref: string;
} | {
    readonly kind: 'array';
    readonly items: ContractDescriptor;
    readonly min_length?: number;
    readonly max_length?: number;
} | {
    readonly kind: 'record';
    readonly values: ContractDescriptor;
    readonly min_length?: number;
    readonly max_length?: number;
} | {
    readonly kind: 'tuple' | 'union';
    readonly items: ReadonlyArray<ContractDescriptor>;
};
export interface ContractModelDescriptor {
    readonly python: string;
    readonly typescript: string;
    readonly root_model: boolean;
    readonly fields: Readonly<Record<string, ContractDescriptor>>;
}
export interface ContractEnumDescriptor {
    readonly python: string;
    readonly typescript: string;
    readonly values: ReadonlyArray<JsonValue>;
}
export type GameOutcomeResolution = "victory" | "draw" | "indeterminate";
export type MetricAvailability = "available" | "partial" | "unavailable";
export type SummaryCompletenessStatus = "complete" | "partial";
export type CharacterBuildIssueCode = "content_set_mismatch" | "ruleset_mismatch" | "loadout_character_mismatch" | "loadout_definition_mismatch" | "content_ref_unknown" | "content_contract_mismatch" | "typed_definition_required" | "typed_definition_type_mismatch" | "body_factory_required" | "body_not_character_body" | "body_parameters_invalid" | "appearance_selection_invalid" | "species_variant_parent_mismatch" | "origin_implementation_blocked" | "subclass_parent_mismatch" | "subclass_selection_timing" | "subclass_selection_mismatch" | "class_level_definition_missing" | "duplicate_choice_requirement" | "missing_required_choice" | "unexpected_choice" | "choice_kind_mismatch" | "choice_selection_count" | "choice_ref_not_allowed" | "choice_proficiency_subject_not_allowed" | "duplicate_fighting_style" | "duplicate_metamagic" | "multiclass_prerequisite_unmet" | "spellcasting_source_duplicate" | "spell_choice_source_unknown" | "spell_learn_duplicate" | "spell_replacement_source_mismatch" | "spell_replacement_duplicate" | "prepared_spell_source_unknown" | "prepared_spell_source_inactive" | "prepared_spell_not_entitled" | "prepared_spell_rank_unavailable";
export type CharacterGrantScheduleKind = "automatic_content" | "selected_content" | "proficiency" | "ability_score_increase" | "spell_learn" | "spell_replacement";
export type CharacterGrantSourceKind = "species" | "species_variant" | "background" | "first_class_package" | "multiclass_class_package" | "class_level" | "subclass_level";
export type ActionSelectionParameterKind = "level";
export type ActionSystemicDomain = "action" | "item_action" | "spell" | "reaction";
export type MovementProvocationPolicy = "ordinary_exit" | "does_not_provoke";
export type MovementTerminationReason = "completed" | "collision" | "insufficient_movement" | "step_canceled" | "incapacitated" | "action_denied" | "dead" | "subjective_revalidation" | "position_diverged" | "invalid_path" | "invalid_cost" | "canceled";
export type PublicActionUsageRole = "configured_action" | "definition" | "source_item" | "provider";
export type OutcomeApplicationScope = "allocated_targets" | "each_affected_entity";
export type OutcomeResolution = "automatic" | "attack_roll" | "saving_throw" | "unknown";
export type RangeType = "Reach" | "Range" | "Self";
export type ActionAvailabilityStatus = "available" | "source_unaffordable" | "requirements_unmet" | "no_valid_targets" | "target_cost_unaffordable";
export type ActionCategory = "ability" | "attack" | "spell" | "movement";
export type ActionInformationOperation = "reveal_region" | "change_light" | "grant_sense" | "conceal_region";
export type ActionSetupDuration = "current_turn" | "until_next_turn" | "until_removed";
export type ActionSetupMaintenanceFailure = "remove_setup";
export type ActionSetupMaintenanceTrigger = "revealing_action";
export type ActionTopologyOperation = "create_blocker" | "remove_blocker";
export type ActionWorldEffectAnchor = "actor" | "selected_target" | "selected_position" | "selected_object";
export type ActionWorldEffectCertainty = "guaranteed" | "conditional";
export type ActionWorldEffectScope = "target" | "region" | "frontier" | "magical_darkness" | "hazard_region";
export type ActionWorldEffectShape = "sphere";
export type TargetEffectDisposition = "beneficial" | "harmful" | "neutral";
export type TargetType = "self" | "entity" | "position" | "position_path" | "position_los" | "position_aoe" | "multi_entity" | "object";
export type MovementMode = "walking" | "flying" | "swimming" | "burrowing";
export type CombatLogEntryType = "attack" | "movement" | "action" | "saving_throw" | "death_save" | "ability_check" | "skill_check" | "condition_applied" | "condition_removed" | "damage_taken" | "heal" | "temporary_hit_points" | "death" | "turn_start" | "turn_end" | "multi_entity_action" | "spell_save" | "spell_damage" | "spell_interruption" | "entity_spotted" | "hazard_detected" | "roll_modification" | "spatial_effect";
export type ConditionAgencyDenial = "none" | "full_turn";
export type ConditionApplicationDisposition = "applied" | "rejected" | "retained_stronger" | "promoted" | "immune";
export type ConditionApplicationPolicy = "replace_existing" | "most_potent_active";
export type ConditionCategory = "condition" | "status" | "internal";
export type ConditionRemovalTrigger = "positive_damage_applied" | "shake_awake";
export type ConditionTag = "magical" | "curse" | "disease" | "poison" | "exhaustion" | "petrification" | "ability_score_reduction" | "hit_point_maximum_reduction" | "concentration";
export type DurationType = "rounds" | "permanent" | "until_long_rest" | "on_condition";
export type HazardFilter = "all" | "enemies" | "non_source";
export type ContentDependencyPhase = "construction" | "runtime_reference";
export type ContentDependencyRelation = "grants_action" | "grants_spell" | "grants_feature" | "offers_subclass" | "offers_starting_equipment" | "has_species_variant" | "applies_condition" | "installs_handler" | "creates_zone" | "creates_spatial_effect" | "transforms_to_spatial_effect" | "creates_object" | "creates_item" | "equips_item" | "configures_creature" | "summons_creature" | "requires_primitive";
export type ContentVisibility = "public" | "observed" | "developer" | "internal";
export type DragonbornAncestry = "black" | "blue" | "brass" | "bronze" | "copper" | "gold" | "green" | "red" | "silver" | "white";
export type DragonbornBreathGeometry = "line" | "cone";
export type AbilityScoreName = "strength" | "dexterity" | "constitution" | "intelligence" | "wisdom" | "charisma";
export type ChoiceRequirementKind = "class_skill" | "starting_proficiency" | "fighting_style" | "subclass" | "cantrip" | "spell_known" | "spell_replacement" | "metamagic" | "elemental_ancestry" | "origin_trait" | "ability_score_improvement" | "ability_score_improvement_or_feat" | "feat" | "starting_equipment_package" | "starting_apparel_package";
export type ProficiencySubjectKind = "ability_check" | "skill" | "saving_throw" | "weapon" | "armor" | "shield" | "tool" | "language";
export type RitualPreparationPolicy = "none" | "known" | "prepared" | "spellbook";
export type EffectOriginKind = "spell" | "action" | "item" | "environment" | "unknown";
export type ConditionActionOutcome = "succeeded" | "failed";
export type ConditionAttackOutcome = "hit" | "critical" | "miss";
export type ConditionEffectCoverage = "profiled" | "none" | "indirect" | "internal_only" | "lifecycle_only";
export type ConditionEffectDisposition = "beneficial" | "harmful" | "neutral";
export type ConditionEffectOperation = "apply" | "remove" | "cleanse" | "reduce";
export type ConditionEffectTarget = "actor" | "selected_target" | "each_affected_entity" | "selected_object" | "source_item" | "equipped_item" | "world_position" | "created_spatial_effect";
export type ConditionSaveDCSource = "actor_spell_save_dc" | "actor_action_dc" | "fixed";
export type ConditionSaveOutcome = "failed" | "succeeded";
export type DamageAffinityStatus = "resistance" | "vulnerability" | "immunity";
export type EncounterCompatibilityCode = "battlefield_mismatch" | "blocked_spawn" | "duplicate_spawn" | "forbidden_capability" | "member_capacity" | "missing_capability" | "missing_character" | "missing_role_slot" | "occupied_spawn" | "out_of_bounds_spawn" | "unreachable_factions";
export type EncounterCompatibilityPhase = "static" | "built";
export type EncounterCompatibilitySeverity = "hard" | "diagnostic";
export type RosterControllerKind = "human" | "ai" | "codex";
export type RosterItemPlacement = "inventory" | "equipped" | "equipped_default";
export type ContentDefinitionKind = "item" | "creature" | "action" | "spell" | "condition" | "trait" | "reaction" | "feat" | "class_feature" | "class" | "subclass" | "species" | "species_variant" | "background" | "starting_equipment_package" | "environment_object" | "spatial_effect" | "rule_primitive";
export type ItemPersistencePolicy = "possession" | "intrinsic" | "encounter_only" | "environment";
export type ItemStackCompatibility = "recipe_digest";
export type OriginRuntimeSupportStatus = "available" | "blocked";
export type CharacterCreationPlanKind = "blank_custom" | "premade_template";
export type ContentFidelity = "complete" | "partial" | "blocked";
export type ContentProvenanceRelation = "faithful_implementation" | "compatible_adaptation" | "derived_content" | "original_content";
export type ContentReviewStatus = "reviewed" | "unreviewed";
export type ContentSourceFamily = "srd_5_1_cc" | "srd_5_2_1_cc" | "neurodragon_original" | "third_party_open" | "fixture_internal" | "provenance_unverified";
export type RulesBaseline = "2014" | "2024" | "engine_neutral";
export type ContentDeclarationMode = "factory" | "behavior_identity" | "typed_definition";
export type RuntimeBehaviorKind = "action" | "spell" | "reaction" | "trait" | "feat" | "class_feature" | "condition" | "item" | "environment_interaction" | "spatial_effect" | "system" | "unclassified";
export type SpatialEffectLifetimePolicy = "controller_duration" | "permanent_until_removed";
export type DamageType = "Acid" | "Bludgeoning" | "Cold" | "Fire" | "Force" | "Lightning" | "Necrotic" | "Piercing" | "Poison" | "Psychic" | "Radiant" | "Slashing" | "Thunder";
export type Size = "Tiny" | "Small" | "Medium" | "Large" | "Huge" | "Gargantuan";
export type AttackOutcome = "Hit" | "Miss" | "Crit" | "Crit Miss";
export type RollType = "Damage" | "Attack" | "Save" | "Check" | "Heal";
export type BodyPart = "Head" | "Body" | "Hands" | "Legs" | "Feet" | "Amulet" | "Ring" | "Cloak";
export type EquipmentRenderLayer = "belt" | "chest" | "hands" | "helmet" | "legs" | "offhand" | "shoes" | "weapon";
export type RingSlot = "Left Ring" | "Right Ring";
export type VisualLoadoutSlot = "weapon_melee_main" | "weapon_melee_off" | "weapon_ranged_main" | "weapon_ranged_off" | "helmet" | "body_armor" | "gauntlets" | "greaves" | "boots" | "amulet" | "cloak" | "ring_left" | "ring_right";
export type WeaponSet = "none" | "melee" | "ranged";
export type WeaponSlot = "MELEE_MAIN" | "MELEE_OFF" | "RANGED_MAIN" | "RANGED_OFF";
export type EventPhase = "declaration" | "execution" | "effect" | "completion" | "cancel";
export type EventType = "base_action" | "attack" | "movement" | "step_movement" | "forced_movement" | "ability_check" | "saving_throw" | "skill_check" | "inflicted_damage" | "take_damage" | "damage_applied" | "heal" | "temporary_hit_points" | "cast_spell" | "attack_miss" | "attack_hit" | "attack_critical" | "condition_application" | "condition_removal" | "weapon_equip" | "weapon_unequip" | "armor_equip" | "armor_unequip" | "shield_equip" | "shield_unequip" | "item_location_state" | "item_charge_consumption" | "traversal_connector_changed" | "trigger_event" | "dice_roll" | "d20_roll_result" | "attack_d20_roll" | "save_d20_roll" | "check_d20_roll" | "damage_roll_result" | "heal_roll_result" | "enemy_spotted" | "enemy_killed" | "enemy_engaged" | "spatial_entity_entered" | "spatial_entity_left" | "spatial_tile_changed" | "spatial_object_placed" | "spatial_object_removed" | "spatial_perceivability_changed" | "spatial_light_changed" | "spatial_object_changed" | "spatial_effect_changed" | "movement_collision" | "sensory_update" | "spatial_effect_interaction" | "encounter_start" | "encounter_end" | "round_start" | "round_end" | "turn_start" | "turn_end" | "life_state_change" | "revive" | "death_save" | "instant_death" | "death";
export type MovementTrajectory = "path" | "direct_arc" | "connector_transfer";
export type RollModificationOperation = "replace" | "append";
export type SensoryUpdateReason = "spatial" | "self_movement" | "light" | "perceivability" | "death" | "condition" | "life_state" | "turn_start" | "unknown";
export type SpatialChangeType = "entity_entered" | "entity_left" | "tile_changed" | "tile_created" | "tile_removed" | "object_placed" | "object_removed" | "perceivability_changed" | "light_changed" | "object_changed" | "movement_collision";
export type EquippedVisualPolicy = "visible" | "hidden";
export type ItemLocation = "floor" | "inventory" | "equipment" | "merged" | "destroyed";
export type ItemPresentationKind = "item" | "usable" | "weapon" | "armor" | "shield";
export type ItemRarity = "common" | "uncommon" | "rare" | "very_rare" | "legendary";
export type LifeState = "alive" | "dying" | "stable" | "dead";
export type LifeStateChangeReason = "damage" | "massive_damage" | "instant_death" | "death_save_failures" | "stabilization" | "healing" | "revival" | "direct_state_check";
export type AutoHitStatus = "None" | "Autohit" | "Automiss";
export type CriticalStatus = "None" | "Autocrit" | "Critical Immune";
export type ResistanceStatus = "None" | "Resistance" | "Immunity" | "Vulnerability";
export type CasterProgression = "non_caster" | "full_caster" | "half_caster" | "third_caster";
export type MulticlassSlotRoundingPolicy = "srd_5_2_round_up" | "srd_5_1_round_down";
export type AdvantageStatus = "None" | "Advantage" | "Disadvantage";
export type SavingThrowEffectTag = "charm" | "fear" | "poison";
export type SensesType = "Blindsight" | "Darkvision" | "Tremorsense" | "Truesight" | "Devils Sight" | "See Invisible";
export type SpatialEffectAnchorKind = "fixed_position" | "entity" | "world_object" | "independent_movable";
export type SpatialEffectBlockingPolicy = "none" | "anchor" | "footprint";
export type SpatialEffectChangeOperation = "created" | "footprint_changed" | "revealed" | "removed" | "transformed";
export type SpatialEffectInteractionIntensity = "minor" | "moderate" | "strong";
export type SpatialEffectInteractionOperation = "ignite" | "douse" | "freeze" | "electrify" | "vaporize" | "disperse";
export type SpatialEffectLayer = "ground_surface" | "cloud" | "field";
export type SpatialEffectOccupancyPolicy = "exclusive_transforming" | "overlapping";
export type SpatialEffectTransitionAction = "remove_affected" | "replace_affected" | "remove_affected_and_create_secondary";
export type SpatialEffectTriggerKind = "appear" | "enter" | "effect_enters_occupant" | "effect_leaves_occupant" | "leave" | "turn_start" | "turn_end" | "movement_interval" | "round_tick" | "interaction" | "removal";
export type ConnectorActionCostType = "actions" | "bonus_actions";
export type ConnectorDestinationStatus = "known_clear" | "known_blocked" | "unknown";
export type ConnectorProvocationPolicy = "provokes_source_exit" | "does_not_provoke";
export type TraversalConnectorChangeOperation = "register" | "replace" | "enable" | "disable" | "remove";
export type TraversalConnectorKind = "ladder" | "rope" | "lift" | "vertical_stairs" | "passage";
export type ElevationSurfaceKind = "ordinary" | "stairs" | "ramp";
export type SlopeAxis = "north_south" | "east_west";
export type ActionBindingUse = "behavior" | "trigger_behavior";
export type ActionExecutionAuthorization = "authorized" | "not_active_turn" | "turn_not_in_progress" | "encounter_inactive";
export type CharacterAppearanceControlKind = "choice" | "color";
export type CharacterContentRebaseIssueReason = "appearance_selection_unsupported" | "identity_not_installed" | "origin_choice_conflict" | "recipe_parameters_incompatible";
export type CharacterMutationIssueCode = "active_deployment" | "immutable_origin_changed" | "level_up_must_append_one_level" | "level_entitlement_unavailable" | "respec_disabled" | "respec_level_total_mismatch" | "initial_apparel_selection_required" | "content_rebase_unresolvable" | "unknown_creation_plan" | "creation_plan_digest_mismatch" | "creation_plan_level_mismatch";
export type ContentPackOrigin = "built_in" | "external";
export type CharacterAdvancementSourceKind = "creation" | "game_reward" | "developer" | "migration";
export type CharacterStatus = "active" | "retired";
export type ClientKind = "neuroclient" | "codex_cli" | "external_ai" | "observer_tool";
export type ExecutionKind = "hosted" | "local" | "imported";
export type GameLifecycleState = "reserved" | "starting" | "active" | "ended" | "failed" | "interrupted" | "archived";
export type MembershipRole = "owner" | "player" | "observer" | "agent" | "referee" | "administrator";
export type MembershipState = "invited" | "active" | "disconnected" | "revoked" | "left";
export type ObserverPolicy = "public" | "members" | "disabled";
export type PrincipalKind = "human" | "codex" | "service" | "system_ai";
export type SpellPreparationPolicy = "long_rest" | "out_of_combat";
export type VisibilityPolicy = "public" | "unlisted" | "private";
export type AttachmentPolicy = "parallel" | "replace_existing";
export type SubjectiveReplaySegmentEnd = "perspective_retired" | "encounter_ended";
export type ActiveWeaponSet = "none" | "melee" | "ranged";
export type ActorVisualSlot = "weapon" | "weaponGlow" | "offhand";
export type AttackDelivery = "melee" | "projectile";
export type SubjectiveAttackOutcome = "hit" | "miss" | "critical" | "critical_miss";
export type ConditionOperation = "applied" | "removed";
export type DeathSaveOutcome = "success" | "failure" | "critical_success" | "critical_failure";
export type EncounterTransition = "start" | "round_start" | "turn_start" | "turn_end" | "round_end" | "end";
export type FloorObjectBlockingChannel = "movement" | "vision" | "light" | "propagation";
export type FloorObjectDirection = "north" | "south" | "east" | "west";
export type FloorObjectProjectionKind = "item" | "interactable" | "container" | "hazard" | "door" | "directional_structure" | "light_source" | "generic";
export type ForcedMovementCause = "shove" | "spell" | "rule_effect";
export type ItemActionKind = "drink";
export type LifecycleCauseKind = "death_save" | "revive" | "instant_death" | "direct_state_check";
export type LocomotionFamily = "walk" | "swim" | "fly" | "burrow" | "jump" | "connector";
export type LocomotionTrajectory = "path" | "direct_arc" | "connector_transfer";
export type MovementEndpointOutcome = "committed" | "not_committed";
export type PerspectiveKind = "controlled_knowledge_union" | "spectator_knowledge_union";
export type PresentationDamageType = "Slashing" | "Piercing" | "Bludgeoning" | "Fire" | "Cold" | "Lightning" | "Thunder" | "Acid" | "Poison" | "Radiant" | "Necrotic" | "Psychic" | "Force";
export type PresentationDeliveryMode = "normal" | "presentation_reset_required";
export type PresentationProjectile = "bolt" | "ray" | "orb" | "beam" | "dart" | "spray" | "radiance" | "touch" | "rain";
export type PresentationResetReason = "source_presentation_discontinuity";
export type PresentationSpellSchool = "evocation" | "necromancy" | "abjuration" | "enchantment" | "conjuration" | "illusion" | "transmutation" | "divination";
export type PresentationWeaponSlot = "MELEE_MAIN" | "MELEE_OFF" | "RANGED_MAIN" | "RANGED_OFF";
export type ShoveOutcome = "resisted" | "succeeded_push" | "succeeded_prone" | "succeeded_blocked";
export type SpellApplicationOutcome = "automatic" | "hit" | "miss" | "critical" | "save_succeeded" | "save_failed" | "resisted" | "immune";
export type SpellDelivery = "self" | "touch" | "direct" | "projectile" | "missile_volley" | "aoe";
export type CombatLogProjection = "subjective" | "objective";
export type StructuralEdgeKind = "wall" | "door";
export interface AttackEvent {
    readonly wire_type: "dnd.actions.AttackEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "attack";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly costs: Array<BaseCost>;
    readonly source_item_uuid: string | null;
    readonly action_usage_domain: ActionSystemicDomain;
    readonly public_action_usage_subject: PublicContentUsage | SystemicUsage;
    readonly item_charge_cost: number;
    readonly item_charge_action_lineage_uuid: string | null;
    readonly declared_target_entity_uuids: Array<string>;
    readonly application_id: string | null;
    readonly description: string;
    readonly total_targets: number;
    readonly total_damage: number;
    readonly aoe_position: [number, number] | null;
    readonly weapon_slot: WeaponSlot;
    readonly range: Range | null;
    readonly is_long_range: boolean;
    readonly is_threatened: boolean;
    readonly attack_bonus: ModifiableValue | null;
    readonly ac: ModifiableValue | null;
    readonly dice_roll: DiceRoll | null;
    readonly attack_outcome: AttackOutcome | null;
    readonly damages: Array<Damage> | null;
    readonly damage_rolls: Array<DiceRoll> | null;
    readonly weapon_name: string | null;
    readonly override_ability: "strength" | "dexterity" | "constitution" | "intelligence" | "wisdom" | "charisma" | null;
    readonly damage_types: Array<DamageType>;
}
export interface JumpEvent {
    readonly wire_type: "dnd.actions.JumpEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "movement";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly costs: Array<BaseCost>;
    readonly source_item_uuid: string | null;
    readonly action_usage_domain: ActionSystemicDomain;
    readonly public_action_usage_subject: PublicContentUsage | SystemicUsage;
    readonly item_charge_cost: number;
    readonly item_charge_action_lineage_uuid: string | null;
    readonly declared_target_entity_uuids: Array<string>;
    readonly application_id: string | null;
    readonly description: string;
    readonly total_targets: number;
    readonly total_damage: number;
    readonly aoe_position: [number, number] | null;
    readonly start_position: [number, number];
    readonly requested_end_position: [number, number] | null;
    readonly end_position: [number, number];
    readonly objective_end_position: [number, number] | null;
    readonly start_elevation_feet: number;
    readonly requested_end_elevation_feet: number;
    readonly end_elevation_feet: number;
    readonly jump_distance: number;
    readonly movement_spent: number;
    readonly fixed_costs_committed: boolean;
    readonly path: Array<[number, number]> | null;
    readonly trajectory: MovementTrajectory;
    readonly termination_reason: MovementTerminationReason;
}
export interface MovementEvent {
    readonly wire_type: "dnd.actions.MovementEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "movement";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly costs: Array<BaseCost>;
    readonly source_item_uuid: string | null;
    readonly action_usage_domain: ActionSystemicDomain;
    readonly public_action_usage_subject: PublicContentUsage | SystemicUsage;
    readonly item_charge_cost: number;
    readonly item_charge_action_lineage_uuid: string | null;
    readonly declared_target_entity_uuids: Array<string>;
    readonly application_id: string | null;
    readonly description: string;
    readonly total_targets: number;
    readonly total_damage: number;
    readonly aoe_position: [number, number] | null;
    readonly start_position: [number, number];
    readonly end_position: [number, number];
    readonly requested_end_position: [number, number] | null;
    readonly objective_end_position: [number, number] | null;
    readonly path: Array<[number, number]> | null;
    readonly movement_mode: MovementMode;
    readonly trajectory: MovementTrajectory;
    readonly termination_reason: MovementTerminationReason;
    readonly controller_revalidation: boolean;
    readonly controller_revalidation_reason: string | null;
}
export interface ShoveEvent {
    readonly wire_type: "dnd.actions.ShoveEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "base_action";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly costs: Array<BaseCost>;
    readonly source_item_uuid: string | null;
    readonly action_usage_domain: ActionSystemicDomain;
    readonly public_action_usage_subject: PublicContentUsage | SystemicUsage;
    readonly item_charge_cost: number;
    readonly item_charge_action_lineage_uuid: string | null;
    readonly declared_target_entity_uuids: Array<string>;
    readonly application_id: string | null;
    readonly description: string;
    readonly total_targets: number;
    readonly total_damage: number;
    readonly aoe_position: [number, number] | null;
    readonly target_weight: number;
    readonly max_shove_weight: number;
    readonly shover_athletics: ModifiableValue | null;
    readonly target_passive: number;
    readonly target_resistance_skill: string;
    readonly dice_roll: DiceRoll | null;
    readonly contest_success: boolean | null;
    readonly push_distance: number;
    readonly push_direction: [number, number];
    readonly end_position: [number, number] | null;
    readonly knocked_prone: boolean;
    readonly blocked_by: string | null;
    readonly is_ally: boolean;
}
export interface SpellEvent {
    readonly wire_type: "dnd.actions.SpellEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "cast_spell";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly costs: Array<BaseCost>;
    readonly source_item_uuid: string | null;
    readonly action_usage_domain: ActionSystemicDomain;
    readonly public_action_usage_subject: PublicContentUsage | SystemicUsage;
    readonly item_charge_cost: number;
    readonly item_charge_action_lineage_uuid: string | null;
    readonly declared_target_entity_uuids: Array<string>;
    readonly application_id: string | null;
    readonly description: string;
    readonly total_targets: number;
    readonly total_damage: number;
    readonly aoe_position: [number, number] | null;
    readonly spell_level: number;
    readonly cast_at_level: number;
    readonly spell_school: string;
    readonly verbal: boolean;
    readonly source_position: [number, number] | null;
    readonly area_geometry: SpherePresentationGeometry | ConePresentationGeometry | LinePresentationGeometry | CubePresentationGeometry | CylinderPresentationGeometry | null;
    readonly attack_bonus: ModifiableValue | null;
    readonly ac: ModifiableValue | null;
    readonly dice_roll: DiceRoll | null;
    readonly attack_outcome: AttackOutcome | null;
    readonly is_threatened: boolean;
    readonly save_ability: "strength" | "dexterity" | "constitution" | "intelligence" | "wisdom" | "charisma" | null;
    readonly save_dc: number | null;
    readonly save_success: boolean | null;
    readonly save_roll: DiceRoll | null;
    readonly save_bonus: number | null;
    readonly damages: Array<Damage> | null;
    readonly damage_rolls: Array<DiceRoll> | null;
    readonly aoe_shape_type: string | null;
    readonly aoe_radius_ft: number | null;
    readonly range_type: string | null;
    readonly range_ft: number | null;
    readonly projectile_type: string | null;
    readonly damage_types: Array<DamageType>;
}
export interface TraverseConnectorEvent {
    readonly wire_type: "dnd.actions.TraverseConnectorEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "movement";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly costs: Array<BaseCost>;
    readonly source_item_uuid: string | null;
    readonly action_usage_domain: ActionSystemicDomain;
    readonly public_action_usage_subject: PublicContentUsage | SystemicUsage;
    readonly item_charge_cost: number;
    readonly item_charge_action_lineage_uuid: string | null;
    readonly declared_target_entity_uuids: Array<string>;
    readonly application_id: string | null;
    readonly description: string;
    readonly total_targets: number;
    readonly total_damage: number;
    readonly aoe_position: [number, number] | null;
    readonly connector_uuid: string;
    readonly connector_authored_id: string;
    readonly connector_kind: TraversalConnectorKind;
    readonly connector_presentation_key: string;
    readonly connector_revision: number;
    readonly connector_digest: string;
    readonly connector_provocation_policy: ConnectorProvocationPolicy;
    readonly connector_bidirectional: boolean;
    readonly start_position: [number, number];
    readonly requested_end_position: [number, number];
    readonly end_position: [number, number];
    readonly objective_end_position: [number, number] | null;
    readonly start_elevation_feet: number;
    readonly requested_end_elevation_feet: number;
    readonly end_elevation_feet: number;
    readonly movement_cost_feet: number;
    readonly action_cost_type: ConnectorActionCostType | null;
    readonly action_cost_amount: number;
    readonly termination_reason: MovementTerminationReason;
}
export interface PolicyDescriptor {
    readonly policy_id: string;
    readonly version: string;
    readonly display_name: string;
    readonly description: string;
    readonly deterministic: boolean;
}
export interface AppliedDamageByActionSubjectV3 {
    readonly subject: PublicContentUsage | SystemicUsage;
    readonly applied_damage: number;
}
export interface AttackStatisticsV1 {
    readonly attempted: number;
    readonly resolved: number;
    readonly hits: number;
    readonly misses: number;
    readonly critical_hits: number;
    readonly critical_misses: number;
    readonly canceled: number;
    readonly opportunity_attacks: number | null;
}
export interface CombatStatisticsV3 {
    readonly turns_started: number;
    readonly turns_ended: number;
    readonly attacks: AttackStatisticsV1;
    readonly damage_dealt: DamageStatisticsV3;
    readonly damage_taken: DamageStatisticsV3;
    readonly healing_done: HealingStatisticsV1;
    readonly healing_received: HealingStatisticsV1;
    readonly movement: MovementStatisticsV1;
    readonly action_usage: Array<ContentUsageCountV3>;
    readonly item_action_usage: Array<ContentUsageCountV3>;
    readonly spell_usage: Array<ContentUsageCountV3>;
    readonly item_charges_spent: Record<string, number>;
    readonly action_economy_spent: Record<string, number>;
    readonly resources_spent: Record<string, number>;
    readonly conditions_applied: Record<string, number>;
    readonly conditions_removed: Record<string, number>;
    readonly kills: number;
    readonly deaths: number;
    readonly saving_throws: ResolutionStatisticsV2;
    readonly skill_checks: ResolutionStatisticsV2;
    readonly dice: DiceStatisticsV2;
}
export interface ContentUsageCountV3 {
    readonly subject: PublicContentUsage | SystemicUsage;
    readonly usage: UsageCountV1;
}
export interface DamagePreventionStatisticsV2 {
    readonly event_prevented: number;
    readonly resistance_prevented: number;
    readonly immunity_prevented: number;
    readonly flat_reduction_prevented: number;
    readonly survival_cap_prevented: number;
    readonly blocked_damage: number;
    readonly vulnerability_bonus: number;
    readonly event_amplification: number;
}
export interface DamageStatisticsV3 {
    readonly incoming_raw: number;
    readonly applied: number;
    readonly normal_hit_point_damage: number;
    readonly temporary_hit_point_damage: number;
    readonly unapplied_remainder: number;
    readonly incoming_packets: number;
    readonly applied_packets: number;
    readonly blocked_packets: number;
    readonly applied_by_type: Record<string, number>;
    readonly effective_normal_hit_point_damage: number;
    readonly overkill_damage: number;
    readonly prevention: DamagePreventionStatisticsV2;
    readonly incoming_by_type: Record<string, number>;
    readonly after_affinity_by_type: Record<string, number>;
    readonly applied_by_counterparty: Record<string, number>;
    readonly applied_by_action_subject: Array<AppliedDamageByActionSubjectV3>;
    readonly applied_without_action_subject: number;
}
export interface DiceStatisticsV2 {
    readonly all_d20: RollLuckStatisticsV2;
    readonly attack_d20: RollLuckStatisticsV2;
    readonly saving_throw_d20: RollLuckStatisticsV2;
    readonly skill_check_d20: RollLuckStatisticsV2;
    readonly damage: RollLuckStatisticsV2;
    readonly healing: RollLuckStatisticsV2;
}
export interface EntitySnapshotV1 {
    readonly schema_version: 1;
    readonly entity_uuid: string;
    readonly name: string;
    readonly side_id: string;
    readonly normal_hit_points: number;
    readonly maximum_hit_points: number;
    readonly temporary_hit_points: number;
    readonly life_state: LifeState | null;
    readonly is_defeated: boolean;
    readonly position: [number, number] | null;
    readonly condition_semantic_keys: Array<string>;
    readonly resources: Record<string, number>;
}
export interface EntitySummaryV3 {
    readonly entity_uuid: string;
    readonly side_id: string;
    readonly name: string;
    readonly initial: EntitySnapshotV1 | null;
    readonly final: EntitySnapshotV1 | null;
    readonly statistics: CombatStatisticsV3;
}
export interface GameOutcomeV1 {
    readonly terminal_event_observed: boolean;
    readonly resolution: GameOutcomeResolution;
    readonly reason: string | null;
    readonly winning_side_ids: Array<string>;
    readonly losing_side_ids: Array<string>;
    readonly surviving_side_ids: Array<string>;
}
export interface GameSummaryV3 {
    readonly schema_name: "dnd.game-summary";
    readonly schema_version: 3;
    readonly game_id: string;
    readonly encounter_uuid: string;
    readonly started_at: string | null;
    readonly ended_at: string | null;
    readonly duration_seconds: number | null;
    readonly rounds_started: number;
    readonly terminal_cursor: TerminalCursorV1;
    readonly outcome: GameOutcomeV1;
    readonly entities: Array<EntitySummaryV3>;
    readonly sides: Array<SideSummaryV3>;
    readonly unattributed_statistics: CombatStatisticsV3;
    readonly completeness: SummaryCompletenessV1;
    readonly provenance: SummaryProvenanceV1;
    readonly canonical_sha256: string;
}
export interface HealingStatisticsV1 {
    readonly requested: number;
    readonly applied: number;
    readonly events: number;
    readonly blocked_events: number;
}
export interface MetricProvenanceV1 {
    readonly metric: string;
    readonly availability: MetricAvailability;
    readonly sources: Array<string>;
    readonly note: string;
}
export interface MovementStatisticsV1 {
    readonly voluntary_events: number;
    readonly voluntary_feet: number;
    readonly jump_events: number;
    readonly jump_feet: number;
    readonly forced_events: number;
    readonly forced_feet: number;
}
export interface OutcomeCountV2 {
    readonly attempted: number;
    readonly resolved: number;
    readonly successes: number;
    readonly failures: number;
}
export interface ResolutionStatisticsV2 {
    readonly attempted: number;
    readonly resolved: number;
    readonly successes: number;
    readonly failures: number;
    readonly by_kind: Record<string, OutcomeCountV2>;
}
export interface RollLuckStatisticsV2 {
    readonly roll_events: number;
    readonly outcome_samples: number;
    readonly random_faces_rolled: number;
    readonly observed_total: number;
    readonly expected_total: number;
    readonly variance_total: number;
    readonly average_observed: number | null;
    readonly average_expected: number | null;
    readonly luck_delta: number;
    readonly luck_z_score: number | null;
    readonly natural_ones: number;
    readonly natural_twenties: number;
    readonly advantage_events: number;
    readonly disadvantage_events: number;
    readonly modified_events: number;
}
export interface SideSummaryV3 {
    readonly side_id: string;
    readonly entity_uuids: Array<string>;
    readonly initial_combatant_count: number;
    readonly final_combatant_count: number;
    readonly surviving_combatant_count: number;
    readonly statistics: CombatStatisticsV3;
}
export interface SummaryCompletenessV1 {
    readonly status: SummaryCompletenessStatus;
    readonly issues: Array<string>;
}
export interface SummaryProvenanceV1 {
    readonly reducer_id: string;
    readonly event_model: string;
    readonly combat_log_model: string;
    readonly initial_snapshot_count: number;
    readonly final_snapshot_count: number;
    readonly event_versions_seen: number;
    readonly event_lineages_seen: number;
    readonly terminal_lineages_reduced: number;
    readonly top_level_combat_logs_seen: number;
    readonly structured_combat_logs_seen: number;
    readonly metric_provenance: Array<MetricProvenanceV1>;
}
export interface TerminalCursorV1 {
    readonly event_cursor: number;
    readonly combat_log_cursor: number;
}
export interface UsageCountV1 {
    readonly attempted: number;
    readonly completed: number;
    readonly canceled: number;
}
export interface ItemChargeConsumptionEvent {
    readonly wire_type: "dnd.blocks.base_item.ItemChargeConsumptionEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "item_charge_consumption";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly item_uuid: string;
    readonly item_semantic_key: string;
    readonly item_name: string;
    readonly amount: number;
    readonly charges_before: number;
    readonly charges_after: number;
    readonly stack_count_before: number;
    readonly stack_count_after: number;
    readonly item_destroyed: boolean;
}
export interface ItemLocationStateEvent {
    readonly wire_type: "dnd.blocks.base_item.ItemLocationStateEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "item_location_state";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly item_state: ItemPresentationState;
    readonly location: ItemLocation;
    readonly owner_uuid: string | null;
    readonly container_uuid: string | null;
    readonly tile_uuid: string | null;
    readonly position: [number, number] | null;
    readonly equipment_slot: WeaponSlot | BodyPart | RingSlot | null;
    readonly merged_into_item_uuid: string | null;
    readonly entity_armor_class_after: number | null;
}
export interface ArmorEquipEvent {
    readonly wire_type: "dnd.blocks.equipment.ArmorEquipEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "armor_equip";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly slot: WeaponSlot | BodyPart | RingSlot;
    readonly item_uuid: string;
}
export interface ArmorUnequipEvent {
    readonly wire_type: "dnd.blocks.equipment.ArmorUnequipEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "armor_unequip";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly slot: WeaponSlot | BodyPart | RingSlot;
    readonly item_uuid: string;
}
export interface ShieldEquipEvent {
    readonly wire_type: "dnd.blocks.equipment.ShieldEquipEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "shield_equip";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly slot: WeaponSlot | BodyPart | RingSlot;
    readonly item_uuid: string;
}
export interface ShieldUnequipEvent {
    readonly wire_type: "dnd.blocks.equipment.ShieldUnequipEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "shield_unequip";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly slot: WeaponSlot | BodyPart | RingSlot;
    readonly item_uuid: string;
}
export interface WeaponEquipEvent {
    readonly wire_type: "dnd.blocks.equipment.WeaponEquipEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "weapon_equip";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly slot: WeaponSlot | BodyPart | RingSlot;
    readonly item_uuid: string;
}
export interface WeaponUnequipEvent {
    readonly wire_type: "dnd.blocks.equipment.WeaponUnequipEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "weapon_unequip";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly slot: WeaponSlot | BodyPart | RingSlot;
    readonly item_uuid: string;
}
export interface ActionSelectionParameter {
    readonly kind: ActionSelectionParameterKind;
    readonly value: number;
}
export interface PublicContentUsage {
    readonly kind: "public_content";
    readonly role: PublicActionUsageRole;
    readonly ref: ContentRef;
}
export interface SystemicUsage {
    readonly kind: "systemic";
    readonly domain: ActionSystemicDomain;
}
export interface ActionOutcomeProfile {
    readonly effect_id: string | null;
    readonly resolution: OutcomeResolution;
    readonly applications: number;
    readonly application_scope: OutcomeApplicationScope;
    readonly damage_rolls: Array<DamageRollProfile>;
    readonly attack_bonus: number | null;
    readonly advantage: AdvantageStatus;
    readonly critical_threshold: number;
    readonly critical_extra_dice: number;
    readonly save_dc: number | null;
    readonly save_ability: string | null;
    readonly half_damage_on_save: boolean;
    readonly scope: "actor_baseline";
}
export interface DamageRollProfile {
    readonly dice_count: number;
    readonly die_size: number;
    readonly flat_bonus: number;
    readonly damage_type: string;
}
export interface ActionEvent {
    readonly wire_type: "dnd.core.base_actions.ActionEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "base_action";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly costs: Array<BaseCost>;
    readonly source_item_uuid: string | null;
    readonly action_usage_domain: ActionSystemicDomain;
    readonly public_action_usage_subject: PublicContentUsage | SystemicUsage;
    readonly item_charge_cost: number;
    readonly item_charge_action_lineage_uuid: string | null;
    readonly declared_target_entity_uuids: Array<string>;
    readonly application_id: string | null;
    readonly description: string;
    readonly total_targets: number;
    readonly total_damage: number;
    readonly aoe_position: [number, number] | null;
}
export interface ActionSelfSetupProfile {
    readonly semantic_id: string;
    readonly duration: ActionSetupDuration;
    readonly maximum_duration_rounds: number | null;
    readonly condition_fact_ids: Array<string>;
    readonly active_condition_semantic_keys: Array<string>;
    readonly increases_weapon_damage: boolean;
    readonly resistance_damage_types: Array<string>;
    readonly grants_bonus_action_attack: boolean;
    readonly grants_outgoing_attack_advantage: boolean;
    readonly grants_incoming_attack_advantage: boolean;
    readonly grants_incoming_attack_disadvantage: boolean;
    readonly armor_class_bonus: number;
    readonly movement_speed_multiplier: number;
    readonly extra_actions_per_turn: number;
    readonly grants_invisibility: boolean;
    readonly incapacitates_on_removal: boolean;
    readonly maintenance: ActionSetupMaintenanceProfile | null;
}
export interface ActionSetupMaintenanceProfile {
    readonly trigger: ActionSetupMaintenanceTrigger;
    readonly skill_name: string;
    readonly initial_dc: number;
    readonly dc_increment_per_success: number;
    readonly check_bonus: number;
    readonly check_advantage: AdvantageStatus;
    readonly failure: ActionSetupMaintenanceFailure;
}
export interface ActionTargetEffectBranchProfile {
    readonly effect_id: string;
    readonly disposition: TargetEffectDisposition;
    readonly included_creature_types: Array<string>;
    readonly excluded_creature_types: Array<string>;
    readonly resolution: OutcomeResolution;
    readonly save_dc: number | null;
    readonly save_ability: string | null;
    readonly condition_fact_ids: Array<string>;
    readonly condition_semantic_keys: Array<string>;
}
export interface ActionTargetEffectProfile {
    readonly semantic_id: string;
    readonly branches: Array<ActionTargetEffectBranchProfile>;
}
export interface ActionWorldEffectProfile {
    readonly semantic_id: string;
    readonly information_effects: Array<InformationEffectProfile>;
    readonly topology_effects: Array<TopologyEffectProfile>;
}
export interface AvailableTarget {
    readonly index: number;
    readonly target_uuid: string | null;
    readonly position: [number, number] | null;
    readonly target_name: string | null;
    readonly distance: number | null;
    readonly path_cost: number | null;
    readonly extra_target_uuids: Array<string> | null;
    readonly is_path_hazardous: boolean;
    readonly safe_path_cost: number | null;
    readonly path: Array<[number, number]> | null;
    readonly safe_path: Array<[number, number]> | null;
    readonly opportunity_attack_exposures: Array<OpportunityAttackExposure>;
    readonly safe_path_opportunity_attack_exposures: Array<OpportunityAttackExposure>;
    readonly affected_entity_uuids: Array<string> | null;
    readonly affected_entity_names: Array<string> | null;
    readonly affected_count: number | null;
    readonly affected_positions: Array<[number, number]> | null;
}
export interface BaseCost {
    readonly name: string;
    readonly cost_type: "actions" | "bonus_actions" | "reactions" | "movement" | "spell_slot_1" | "spell_slot_2" | "spell_slot_3" | "spell_slot_4" | "spell_slot_5" | "spell_slot_6" | "spell_slot_7" | "spell_slot_8" | "spell_slot_9";
    readonly cost: number;
    readonly resource_name: string | null;
    readonly resource_cost: number;
}
export interface InformationEffectProfile {
    readonly operation: ActionInformationOperation;
    readonly certainty: ActionWorldEffectCertainty;
    readonly anchor: ActionWorldEffectAnchor;
    readonly scope: ActionWorldEffectScope;
    readonly shape: ActionWorldEffectShape | null;
    readonly radius_feet: number | null;
    readonly sense_type: string | null;
}
export interface OpportunityAttackExposure {
    readonly reactor_uuid: string;
    readonly reactor_name: string;
    readonly from_position: [number, number];
    readonly to_position: [number, number];
}
export interface TopologyEffectProfile {
    readonly operation: ActionTopologyOperation;
    readonly certainty: ActionWorldEffectCertainty;
    readonly anchor: ActionWorldEffectAnchor;
    readonly scope: ActionWorldEffectScope;
    readonly shape: ActionWorldEffectShape | null;
    readonly radius_feet: number | null;
    readonly affects_movement: boolean;
    readonly affects_vision: boolean;
    readonly affects_hazards: boolean;
}
export interface BaseCondition {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly description: string;
    readonly semantic_key: string | null;
    readonly content_kind: RuntimeBehaviorKind;
    readonly effect_origin: EffectOrigin | null;
    readonly obscures_perceivability: boolean;
    readonly condition_category: ConditionCategory;
    readonly application_policy: ConditionApplicationPolicy;
    readonly duration: Duration;
    readonly application_saving_throw: SavingThrowEvent | null;
    readonly removal_saving_throw: SavingThrowEvent | null;
    readonly applied: boolean;
    readonly modifers_uuids: Record<string, Array<string>>;
    readonly parent_condition: string | null;
    readonly sub_conditions: Array<string>;
    readonly event_handlers_uuids: Array<string>;
    readonly spatial_handler_uuids: Array<string>;
    readonly linked_conditions: Array<[string, string]>;
    readonly parent_link: [string, string] | null;
    readonly child_removal_policy: "none" | "any" | "last";
    readonly hazard_filter: HazardFilter | null;
    readonly condition_stealth_dc: number | null;
    readonly tags: Array<ConditionTag>;
    readonly outcome_protections: Array<OutcomeProtection>;
    readonly removal_triggers: Array<ConditionRemovalTrigger>;
    readonly agency_denial: ConditionAgencyDenial;
    readonly applied_source_event_cursor: number | null;
}
export interface ConditionApplicationEvent {
    readonly wire_type: "dnd.core.base_conditions.ConditionApplicationEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "condition_application";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly condition: BaseCondition;
    readonly resulting_ac: number | null;
    readonly resulting_max_hp: number | null;
    readonly application_disposition: ConditionApplicationDisposition;
    readonly condition_content_identity: string | null;
}
export interface ConditionRemovalEvent {
    readonly wire_type: "dnd.core.base_conditions.ConditionRemovalEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "condition_removal";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly condition: BaseCondition;
    readonly expired: boolean;
    readonly condition_content_identity: string | null;
    readonly resulting_ac: number | null;
    readonly resulting_max_hp: number | null;
}
export interface Duration {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly duration: number | JsonValue | null;
    readonly duration_type: DurationType;
    readonly long_rested: boolean;
    readonly owned_by_condition: string | null;
    readonly is_expired: boolean;
}
export interface OutcomeProtection {
    readonly protection_id: string;
    readonly blocked_effect_ids: Array<string>;
}
export interface AbilityCheckLogData {
    readonly entity_name: string;
    readonly entity_uuid: string;
    readonly ability: string;
    readonly dc: number | null;
    readonly roll: DiceRollDisplay;
    readonly bonus_breakdown: Array<ModifierBreakdown>;
    readonly advantage_breakdown: Array<ModifierBreakdown>;
    readonly success: boolean | null;
}
export interface ActionLogData {
    readonly entity_name: string;
    readonly entity_uuid: string;
    readonly action_name: string;
    readonly effect_description: string;
    readonly target_name: string | null;
    readonly target_uuid: string | null;
}
export interface AttackLogData {
    readonly attacker_name: string;
    readonly attacker_uuid: string;
    readonly target_name: string;
    readonly target_uuid: string;
    readonly weapon_name: string;
    readonly weapon_slot: string | null;
    readonly attack_roll: DiceRollDisplay;
    readonly attack_breakdown: Array<ModifierBreakdown>;
    readonly target_ac: number;
    readonly ac_breakdown: Array<ModifierBreakdown>;
    readonly outcome: string;
    readonly is_hit: boolean;
    readonly is_crit: boolean;
    readonly damage_rolls: Array<DamageRollDisplay>;
    readonly total_damage: number;
    readonly target_hp: number | null;
    readonly advantage_breakdown: Array<ModifierBreakdown>;
    readonly is_opportunity_attack: boolean;
    readonly is_long_range: boolean;
    readonly is_threatened: boolean;
}
export interface CombatLogEntry {
    readonly entry_type: CombatLogEntryType;
    readonly source_name: string;
    readonly source_uuid: string;
    readonly target_name: string | null;
    readonly target_uuid: string | null;
    readonly compact: string;
    readonly verbose: string;
    readonly detailed: string;
    readonly data: Record<string, JsonValue>;
    readonly success: boolean | null;
    readonly sub_entries: Array<CombatLogEntry>;
    readonly perceiver_uuids: Array<string>;
    readonly revealed_entity_uuids: Array<string>;
}
export interface ConditionLogData {
    readonly condition_name: string;
    readonly condition_content_identity: string | null;
    readonly reveals_target: boolean;
    readonly application_disposition: ConditionApplicationDisposition | null;
}
export interface DamageRollDisplay {
    readonly dice_str: string;
    readonly dice_results: Array<number>;
    readonly bonus: number;
    readonly total: number;
    readonly damage_type: string;
    readonly bonus_breakdown: Array<ModifierBreakdown>;
}
export interface DamageTakenLogData {
    readonly target_name: string;
    readonly damage: number;
    readonly damage_type: string;
    readonly source_name: string;
    readonly effect_id: string | null;
    readonly blocked: boolean | null;
    readonly blocked_reason: string | null;
}
export interface DeathSaveLogData {
    readonly save_kind: "death";
    readonly entity_name: string;
    readonly entity_uuid: string;
    readonly roll: number;
    readonly natural_roll: number;
    readonly dc: number;
    readonly successes: number;
    readonly failures: number;
    readonly became_stable: boolean;
    readonly regained_hit_point: boolean;
    readonly died: boolean;
}
export interface DiceRollDisplay {
    readonly dice_str: string;
    readonly results: Array<number>;
    readonly bonus: number;
    readonly total: number;
    readonly all_d20_rolls: Array<number> | null;
    readonly d20_used: number | null;
    readonly advantage_status: string | null;
}
export interface EntitySpottedLogData {
    readonly observer_name: string;
    readonly observer_uuid: string;
    readonly target_name: string;
    readonly target_uuid: string;
    readonly target_position: [number, number];
    readonly passive_perception: number;
    readonly stealth_dc: number;
}
export interface HazardDetectedLogData {
    readonly observer_name: string;
    readonly observer_uuid: string;
    readonly hazard_name: string;
    readonly position: [number, number];
    readonly passive_perception: number;
    readonly stealth_dc: number;
}
export interface HealLogData {
    readonly entity_name: string;
    readonly entity_uuid: string;
    readonly amount: number;
    readonly source_description: string;
}
export interface ModifierBreakdown {
    readonly name: string;
    readonly value: number;
    readonly source: string;
}
export interface MovementLogData {
    readonly movement_type: "move" | "jump" | "connector";
    readonly entity_name: string;
    readonly entity_uuid: string;
    readonly start_position: [number, number];
    readonly end_position: [number, number];
    readonly path: Array<[number, number]>;
    readonly distance_feet: number;
    readonly movement_cost: number;
    readonly start_elevation_feet: number | null;
    readonly requested_end_elevation_feet: number | null;
    readonly end_elevation_feet: number | null;
    readonly requested_end_position: [number, number] | null;
    readonly objective_end_position: [number, number] | null;
    readonly termination_reason: string;
    readonly controller_revalidation: boolean;
    readonly controller_revalidation_reason: string | null;
    readonly connector_uuid: string | null;
    readonly connector_authored_id: string | null;
    readonly connector_kind: string | null;
    readonly connector_presentation_key: string | null;
    readonly connector_revision: number | null;
    readonly connector_digest: string | null;
    readonly connector_provocation_policy: string | null;
    readonly connector_action_cost_type: string | null;
    readonly connector_action_cost_amount: number;
    readonly connector_bidirectional: boolean | null;
}
export interface MultiEntityLogData {
    readonly action_name: string;
    readonly caster_name: string;
    readonly total_targets: number;
    readonly target_names: Array<string>;
    readonly total_damage: number;
    readonly per_target_damage: Array<number>;
    readonly saves_succeeded: number;
    readonly saves_failed: number;
    readonly per_target_logs: Array<Record<string, JsonValue> | null>;
    readonly aoe_shape: string | null;
    readonly aoe_center: [number, number] | null;
}
export interface RollModificationLogData {
    readonly roll_type: string;
    readonly modifications: Array<RollModificationLogFact>;
}
export interface RollModificationLogFact {
    readonly operation: "replace" | "append";
    readonly handler_name: string;
    readonly packet_index: number | null;
    readonly previous_total: number | null;
    readonly final_total: number;
    readonly reason: string;
    readonly packet_damage_type: string | null;
    readonly packet_dice: string | null;
}
export interface SavingThrowLogData {
    readonly save_kind: "ability";
    readonly entity_name: string;
    readonly entity_uuid: string;
    readonly ability: string;
    readonly dc: number;
    readonly roll: DiceRollDisplay;
    readonly bonus_breakdown: Array<ModifierBreakdown>;
    readonly advantage_breakdown: Array<ModifierBreakdown>;
    readonly success: boolean;
    readonly source_name: string | null;
}
export interface SkillCheckLogData {
    readonly entity_name: string;
    readonly entity_uuid: string;
    readonly skill: string;
    readonly dc: number | null;
    readonly roll: DiceRollDisplay;
    readonly bonus_breakdown: Array<ModifierBreakdown>;
    readonly advantage_breakdown: Array<ModifierBreakdown>;
    readonly success: boolean | null;
}
export interface SpatialEffectInteractionLogData {
    readonly operation: "ignite" | "douse" | "freeze" | "electrify" | "vaporize" | "disperse";
    readonly intensity: "minor" | "moderate" | "strong";
    readonly affected_positions: Array<[number, number]>;
    readonly source_content_identity: string | null;
}
export interface SpatialEffectLogData {
    readonly operation: "created" | "footprint_changed" | "removed" | "transformed" | "revealed";
    readonly content_identity: string;
    readonly layer: "ground_surface" | "cloud" | "field";
    readonly affected_positions: Array<[number, number]>;
}
export interface SpellInterruptionLogData {
    readonly outcome_code: string;
    readonly counterspeller_name: string;
    readonly counterspeller_uuid: string;
    readonly original_caster_name: string;
    readonly original_caster_uuid: string;
    readonly spell_name: string;
    readonly incoming_spell_level: number;
    readonly counterspell_slot_level: number;
    readonly automatic: boolean;
    readonly check_total: number | null;
    readonly check_dc: number | null;
    readonly succeeded: boolean;
}
export interface SpellSaveLogData {
    readonly caster_name: string;
    readonly caster_uuid: string;
    readonly target_name: string;
    readonly target_uuid: string;
    readonly spell_name: string;
    readonly spell_level: number;
    readonly save_ability: string;
    readonly save_dc: number;
    readonly save_roll: DiceRollDisplay;
    readonly save_bonus_breakdown: Array<ModifierBreakdown>;
    readonly save_advantage_breakdown: Array<ModifierBreakdown>;
    readonly save_success: boolean;
    readonly damage_rolls: Array<DamageRollDisplay>;
    readonly base_damage: number;
    readonly final_damage: number;
    readonly damage_type: string;
    readonly target_hp_after: number | null;
}
export interface TemporaryHitPointsLogData {
    readonly entity_name: string;
    readonly entity_uuid: string;
    readonly requested_amount: number;
    readonly previous_amount: number;
    readonly resulting_amount: number;
    readonly source_description: string;
}
export interface TurnLogData {
    readonly entity_name: string;
    readonly entity_uuid: string;
    readonly round_number: number;
    readonly turn_index: number;
}
export interface BattlefieldDefinition {
    readonly battlefield_id: string;
    readonly title: string;
    readonly width: number;
    readonly height: number;
    readonly tags: Array<string>;
    readonly light_level: "bright" | "darkness";
    readonly capabilities: Array<string>;
    readonly preview: BattlefieldPreview;
    readonly mechanical_revision: number;
    readonly content_digest: string;
}
export interface BattlefieldElevationCell {
    readonly position: [number, number];
    readonly elevation_steps: number;
    readonly surface_kind: ElevationSurfaceKind;
    readonly slope_axis: SlopeAxis | null;
}
export interface BattlefieldPreview {
    readonly cells: Array<BattlefieldPreviewCell>;
    readonly objects: Array<BattlefieldPreviewObject>;
    readonly elevation_cells: Array<BattlefieldElevationCell>;
    readonly connectors: Array<TraversalConnectorDefinition>;
}
export interface BattlefieldPreviewCell {
    readonly position: [number, number];
    readonly terrain: "gap" | "water" | "difficult_terrain" | "spikes";
    readonly walkable: boolean;
    readonly walking_cost: number;
    readonly hazardous: boolean;
}
export interface BattlefieldPreviewObject {
    readonly position: [number, number];
    readonly kind: "wall" | "door" | "wall_torch" | "healing_potion" | "trap_lever" | "fireball_cannon" | "loot_chest";
    readonly label: string;
    readonly blocked_directions: Array<"north" | "south" | "east" | "west">;
    readonly is_open: boolean | null;
}
export interface BoundContentIdentity {
    readonly ref: ContentRef;
    readonly visibility: ContentVisibility;
}
export interface ContentDependency {
    readonly relation: ContentDependencyRelation;
    readonly target_ref: ContentRef;
    readonly required: boolean;
    readonly phase: ContentDependencyPhase;
    readonly notes: string;
}
export interface ContentDescriptor {
    readonly display_name: string;
    readonly description: string;
    readonly tags: Array<string>;
    readonly visibility: ContentVisibility;
    readonly presentation: ContentPresentation;
    readonly ordering: ContentOrdering;
    readonly related_content_refs: Array<ContentRef>;
    readonly ref: ContentRef;
}
export interface ContentDescriptorSpec {
    readonly display_name: string;
    readonly description: string;
    readonly tags: Array<string>;
    readonly visibility: ContentVisibility;
    readonly presentation: ContentPresentation;
    readonly ordering: ContentOrdering;
    readonly related_content_refs: Array<ContentRef>;
}
export interface ContentOrdering {
    readonly sort_group: string;
    readonly sort_order: number;
}
export interface ContentPresentation {
    readonly icon_key: string | null;
    readonly portrait_key: string | null;
    readonly sprite_key: string | null;
    readonly visual_variant_key: string | null;
    readonly tint_rgb: number | null;
    readonly vfx_profile: string | null;
    readonly audio_key: string | null;
    readonly ui_group: string | null;
    readonly equipment_sprites: Array<EquipmentSpritePresentation>;
}
export interface EquipmentSpritePresentation {
    readonly equipment_slot: VisualLoadoutSlot;
    readonly render_layer: EquipmentRenderLayer;
    readonly sprite_key: string;
    readonly tint_rgb: number;
}
export interface AbilityScoreAllocation {
    readonly strength: number;
    readonly dexterity: number;
    readonly constitution: number;
    readonly intelligence: number;
    readonly wisdom: number;
    readonly charisma: number;
}
export interface AbilityScoreImprovementChoice {
    readonly choice_type: "ability_score_improvement";
    readonly choice_id: string;
    readonly increases: Array<[AbilityScoreName, number]>;
}
export interface AbilityScorePrerequisite {
    readonly prerequisite_type: "ability_score";
    readonly ability: AbilityScoreName;
    readonly minimum: number;
}
export interface AllOfPrerequisite {
    readonly prerequisite_type: "all_of";
    readonly prerequisites: Array<AllOfPrerequisite | AnyOfPrerequisite | NotPrerequisite | ClassLevelPrerequisite | TotalCharacterLevelPrerequisite | AbilityScorePrerequisite | HasFeaturePrerequisite | KnowsSpellPrerequisite>;
}
export interface AnyOfPrerequisite {
    readonly prerequisite_type: "any_of";
    readonly prerequisites: Array<AllOfPrerequisite | AnyOfPrerequisite | NotPrerequisite | ClassLevelPrerequisite | TotalCharacterLevelPrerequisite | AbilityScorePrerequisite | HasFeaturePrerequisite | KnowsSpellPrerequisite>;
}
export interface BackgroundDefinition {
    readonly runtime_support: OriginRuntimeSupport;
    readonly automatic_grant_refs: Array<ContentRef>;
    readonly starting_holdings_package_ref: ContentRef | null;
    readonly choice_requirements: Array<BuildChoiceRequirement>;
}
export interface BuildChoiceRequirement {
    readonly choice_id: string;
    readonly choice_kind: ChoiceRequirementKind;
    readonly minimum_selections: number;
    readonly maximum_selections: number;
    readonly allowed_refs: Array<ContentRef>;
    readonly allowed_proficiency_subjects: Array<ProficiencySubject>;
}
export interface CantripChoice {
    readonly choice_id: string;
    readonly selected_refs: Array<ContentRef>;
    readonly choice_type: "cantrip";
}
export interface CharacterAppearanceOptionSelection {
    readonly option_id: string;
    readonly value_id: string;
}
export interface CharacterAppearanceSelection {
    readonly options: Array<CharacterAppearanceOptionSelection>;
}
export interface CharacterDefinitionRevisionV2 {
    readonly character_id: string;
    readonly schema_version: 2;
    readonly definition_revision: number;
    readonly body_recipe: ContentRecipe;
    readonly species_ref: ContentRef;
    readonly species_variant_ref: ContentRef | null;
    readonly background_ref: ContentRef;
    readonly immutable_origin_choices: Array<ClassSkillChoice | StartingProficiencyChoice | FightingStyleChoice | SubclassChoice | CantripChoice | SpellKnownChoice | SpellReplacementChoice | MetamagicChoice | ElementalAncestryChoice | OriginTraitChoice | AbilityScoreImprovementChoice | FeatChoice | StartingEquipmentPackageChoice | StartingApparelPackageChoice>;
    readonly appearance: CharacterAppearanceSelection;
    readonly base_ability_scores: AbilityScoreAllocation;
    readonly flexible_ability_bonuses: FlexibleAbilityBonusSelection;
    readonly class_levels: Array<ClassLevelEntry>;
    readonly premade_id: string | null;
    readonly earned_character_level: number;
    readonly content_set_digest: string;
    readonly ruleset_digest: string;
    readonly definition_digest: string;
}
export interface CharacterHoldingsRevision {
    readonly character_id: string;
    readonly schema_version: 1;
    readonly holdings_revision: number;
    readonly items: Array<CharacterItemV1>;
    readonly holdings_digest: string;
}
export interface CharacterItemV1 {
    readonly schema_version: 1;
    readonly character_item_id: string;
    readonly recipe: ContentRecipe;
    readonly quantity: number;
    readonly remaining_charges: number | null;
    readonly durability_damage: number | null;
    readonly durable_augmentations: Array<ItemAugmentationRecord>;
    readonly equipped_slot: WeaponSlot | BodyPart | RingSlot | null;
    readonly character_item_digest: string;
}
export interface CharacterLoadoutRevisionV1 {
    readonly character_id: string;
    readonly schema_version: 1;
    readonly loadout_revision: number;
    readonly based_on_definition_revision: number;
    readonly prepared_spells: Array<PreparedSpellSourceLoadout>;
    readonly feature_toggles: Array<FeatureToggleSelection>;
    readonly loadout_digest: string;
}
export interface ClassDefinition {
    readonly hit_die: 4 | 6 | 8 | 10 | 12;
    readonly caster_progression: CasterProgression;
    readonly spellcasting_feature_class_level: number | null;
    readonly spellcasting_source_id: SpellcastingSourceId | null;
    readonly spellcasting_ability: AbilityScoreName | null;
    readonly ritual_policy: RitualPreparationPolicy;
    readonly spell_entitlements: Array<ClassSpellEntitlement>;
    readonly multiclass_prerequisite: AllOfPrerequisite | AnyOfPrerequisite | NotPrerequisite | ClassLevelPrerequisite | TotalCharacterLevelPrerequisite | AbilityScorePrerequisite | HasFeaturePrerequisite | KnowsSpellPrerequisite | null;
    readonly first_class_proficiencies: ClassProficiencyPackage;
    readonly multiclass_proficiencies: ClassProficiencyPackage;
    readonly saving_throw_proficiencies: Array<AbilityScoreName>;
    readonly level_definitions: Array<ClassLevelDefinition>;
}
export interface ClassLevelDefinition {
    readonly class_level: number;
    readonly automatic_grant_refs: Array<ContentRef>;
    readonly choice_requirements: Array<BuildChoiceRequirement>;
}
export interface ClassLevelEntry {
    readonly class_level_id: ClassLevelId;
    readonly character_level: number;
    readonly class_ref: ContentRef;
    readonly resulting_class_level: number;
    readonly subclass_ref: ContentRef | null;
    readonly choices: Array<ClassSkillChoice | StartingProficiencyChoice | FightingStyleChoice | SubclassChoice | CantripChoice | SpellKnownChoice | SpellReplacementChoice | MetamagicChoice | ElementalAncestryChoice | OriginTraitChoice | AbilityScoreImprovementChoice | FeatChoice | StartingEquipmentPackageChoice | StartingApparelPackageChoice>;
}
export interface ClassLevelId {
    readonly value: string;
}
export interface ClassLevelPrerequisite {
    readonly prerequisite_type: "class_level";
    readonly class_ref: ContentRef;
    readonly minimum: number;
}
export interface ClassProficiencyPackage {
    readonly automatic: Array<ProficiencySubject>;
    readonly choices: Array<BuildChoiceRequirement>;
}
export interface ClassSkillChoice {
    readonly choice_type: "class_skill";
    readonly choice_id: string;
    readonly skills: Array<string>;
}
export interface ClassSpellEntitlement {
    readonly spell_ref: ContentRef;
    readonly spell_rank: number;
}
export interface ElementalAncestryChoice {
    readonly choice_id: string;
    readonly selected_ref: ContentRef;
    readonly choice_type: "elemental_ancestry";
}
export interface FeatChoice {
    readonly choice_id: string;
    readonly selected_ref: ContentRef;
    readonly choice_type: "feat";
}
export interface FeatureToggleSelection {
    readonly feature_ref: ContentRef;
    readonly enabled: boolean;
}
export interface FightingStyleChoice {
    readonly choice_id: string;
    readonly selected_ref: ContentRef;
    readonly choice_type: "fighting_style";
}
export interface FlexibleAbilityBonusSelection {
    readonly plus_two: AbilityScoreName;
    readonly plus_one: AbilityScoreName;
}
export interface HasFeaturePrerequisite {
    readonly prerequisite_type: "has_feature";
    readonly feature_ref: ContentRef;
}
export interface ItemAugmentationRecord {
    readonly content_ref: ContentRef;
    readonly parameters: Record<string, JsonValue>;
    readonly durable_state: Record<string, JsonValue>;
    readonly augmentation_digest: string;
}
export interface KnowsSpellPrerequisite {
    readonly prerequisite_type: "knows_spell";
    readonly spell_ref: ContentRef;
}
export interface MetamagicChoice {
    readonly choice_id: string;
    readonly selected_refs: Array<ContentRef>;
    readonly choice_type: "metamagic";
}
export interface NotPrerequisite {
    readonly prerequisite_type: "not";
    readonly prerequisite: AllOfPrerequisite | AnyOfPrerequisite | NotPrerequisite | ClassLevelPrerequisite | TotalCharacterLevelPrerequisite | AbilityScorePrerequisite | HasFeaturePrerequisite | KnowsSpellPrerequisite;
}
export interface OriginInnateSpellGrant {
    readonly grant_id: string;
    readonly unlock_character_level: number;
    readonly spell_ref: ContentRef | null;
    readonly choice_id: string | null;
    readonly allowed_spell_refs: Array<ContentRef>;
    readonly fixed_cast_rank: number;
    readonly uses_per_long_rest: number | null;
}
export interface OriginInnateSpellcastingDefinition {
    readonly source_id: SpellcastingSourceId;
    readonly ability: AbilityScoreName;
    readonly grants: Array<OriginInnateSpellGrant>;
}
export interface OriginLevelGrant {
    readonly character_level: number;
    readonly grant_refs: Array<ContentRef>;
}
export interface OriginTraitChoice {
    readonly choice_id: string;
    readonly selected_ref: ContentRef;
    readonly choice_type: "origin_trait";
}
export interface PreparedSpellSourceLoadout {
    readonly spellcasting_source_id: SpellcastingSourceId;
    readonly spell_refs: Array<ContentRef>;
}
export interface ProficiencySubject {
    readonly subject_kind: ProficiencySubjectKind;
    readonly subject_id: string | null;
    readonly content_ref: ContentRef | null;
}
export interface SpeciesDefinition {
    readonly runtime_support: OriginRuntimeSupport;
    readonly level_grants: Array<OriginLevelGrant>;
    readonly choice_requirements: Array<BuildChoiceRequirement>;
    readonly innate_spellcasting: Array<OriginInnateSpellcastingDefinition>;
}
export interface SpeciesVariantDefinition {
    readonly parent_species_ref: ContentRef;
    readonly runtime_support: OriginRuntimeSupport;
    readonly level_grants: Array<OriginLevelGrant>;
    readonly choice_requirements: Array<BuildChoiceRequirement>;
    readonly innate_spellcasting: Array<OriginInnateSpellcastingDefinition>;
}
export interface SpellKnownChoice {
    readonly choice_id: string;
    readonly selected_refs: Array<ContentRef>;
    readonly choice_type: "spell_known";
}
export interface SpellReplacementChoice {
    readonly choice_type: "spell_replacement";
    readonly choice_id: string;
    readonly replaced_spell_ref: ContentRef;
    readonly learned_spell_ref: ContentRef;
}
export interface SpellcastingSourceId {
    readonly value: string;
}
export interface StartingApparelPackageChoice {
    readonly choice_id: string;
    readonly selected_ref: ContentRef;
    readonly choice_type: "starting_apparel_package";
}
export interface StartingEquipmentPackageChoice {
    readonly choice_id: string;
    readonly selected_ref: ContentRef;
    readonly choice_type: "starting_equipment_package";
}
export interface StartingProficiencyChoice {
    readonly choice_type: "starting_proficiency";
    readonly choice_id: string;
    readonly proficiencies: Array<ProficiencySubject>;
}
export interface SubclassChoice {
    readonly choice_id: string;
    readonly selected_ref: ContentRef;
    readonly choice_type: "subclass";
}
export interface SubclassDefinition {
    readonly parent_class_ref: ContentRef;
    readonly level_definitions: Array<ClassLevelDefinition>;
}
export interface TotalCharacterLevelPrerequisite {
    readonly prerequisite_type: "total_character_level";
    readonly minimum: number;
}
export interface EffectOrigin {
    readonly kind: EffectOriginKind;
    readonly source_identity: BoundContentIdentity | null;
    readonly source_event_lineage_uuid: string | null;
    readonly source_position: [number, number] | null;
    readonly base_spell_level: number | null;
    readonly effective_spell_level: number | null;
}
export interface ActionOutcomeConditionEffectGate {
    readonly kind: "action_outcome";
    readonly outcomes: Array<ConditionActionOutcome>;
}
export interface AttackOutcomeConditionEffectGate {
    readonly kind: "attack_outcome";
    readonly outcomes: Array<ConditionAttackOutcome>;
}
export interface AuthoredConditionEffect {
    readonly effect_id: string;
    readonly source_ref: ContentRef;
    readonly operation: ConditionEffectOperation;
    readonly condition_ref: ContentRef | null;
    readonly selector: ConditionEffectSelector | null;
    readonly target: ConditionEffectTarget;
}
export interface AuthoredConditionEffectBranch {
    readonly branch_id: string;
    readonly disposition: ConditionEffectDisposition;
    readonly included_creature_types: Array<string>;
    readonly excluded_creature_types: Array<string>;
    readonly gates: Array<AutomaticConditionEffectGate | AttackOutcomeConditionEffectGate | SavingThrowConditionEffectGate | ActionOutcomeConditionEffectGate | ConfigurationConditionEffectGate | OriginRootConditionEffectGate>;
    readonly effects: Array<AuthoredConditionEffect>;
}
export interface AuthoredConditionEffectProfile {
    readonly branches: Array<AuthoredConditionEffectBranch>;
}
export interface AuthoredConditionLifecycle {
    readonly application_policy: ConditionApplicationPolicy;
    readonly tags: Array<ConditionTag>;
    readonly removal_triggers: Array<ConditionRemovalTrigger>;
    readonly agency_denial: ConditionAgencyDenial;
}
export interface AutomaticConditionEffectGate {
    readonly kind: "automatic";
}
export interface ConditionEffectSelector {
    readonly required_tags: Array<ConditionTag>;
    readonly required_removal_triggers: Array<ConditionRemovalTrigger>;
    readonly resolved_condition_refs: Array<ContentRef>;
}
export interface ConfigurationConditionEffectGate {
    readonly kind: "configuration";
    readonly configuration_key: string;
    readonly values: Array<string>;
}
export interface OriginRootConditionEffectGate {
    readonly kind: "origin_root";
    readonly origin_root_refs: Array<ContentRef>;
}
export interface SavingThrowConditionEffectGate {
    readonly kind: "saving_throw";
    readonly ability: "strength" | "dexterity" | "constitution" | "intelligence" | "wisdom" | "charisma";
    readonly outcome: ConditionSaveOutcome;
    readonly dc_source: ConditionSaveDCSource;
    readonly fixed_dc: number | null;
}
export interface AuthoredCreatureRosterSource {
    readonly kind: "authored_creature";
    readonly recipe: ContentRecipe;
}
export interface EncounterCompatibilityIssue {
    readonly code: EncounterCompatibilityCode;
    readonly severity: EncounterCompatibilitySeverity;
    readonly message: string;
    readonly roster_slot_id: string | null;
    readonly member_id: string | null;
    readonly position: [number, number] | null;
}
export interface EncounterCompatibilityReport {
    readonly encounter_recipe_digest: string;
    readonly battlefield_id: string;
    readonly deployment_id: string;
    readonly phase: EncounterCompatibilityPhase;
    readonly issues: Array<EncounterCompatibilityIssue>;
    readonly admitted: boolean;
}
export interface EncounterDeploymentRoleSlot {
    readonly role: string;
    readonly position: [number, number];
}
export interface EncounterDeploymentSpec {
    readonly deployment_id: string;
    readonly title: string;
    readonly battlefield_id: string;
    readonly zones: Array<EncounterDeploymentZone>;
    readonly tags: Array<string>;
    readonly content_digest: string;
}
export interface EncounterDeploymentZone {
    readonly zone_id: string;
    readonly ordered_slots: Array<[number, number]>;
    readonly role_slots: Array<EncounterDeploymentRoleSlot>;
    readonly max_members: number | null;
}
export interface EncounterMemberPresentation {
    readonly member_id: string;
    readonly display_name: string;
}
export interface EncounterNotablePosition {
    readonly label: string;
    readonly position: [number, number];
}
export interface EncounterRecipe {
    readonly encounter_id: string;
    readonly title: string;
    readonly roster_slots: Array<EncounterRosterSlot>;
    readonly battlefield_id: string;
    readonly deployment: EncounterDeploymentSpec;
    readonly opening_policy: InitiativeOpeningPolicy | FixedRosterOpeningPolicy;
    readonly notable_positions: Array<EncounterNotablePosition>;
    readonly tags: Array<string>;
    readonly recipe_digest: string;
}
export interface EncounterRosterMember {
    readonly member_id: string;
    readonly display_name: string;
    readonly deployment_role: string;
    readonly source: AuthoredCreatureRosterSource | OwnedCharacterRosterSource;
    readonly scenario_setup_effects: Array<RosterItemGrant | RosterSpellGrant | RosterBehaviorGrant | RosterStartingDamage | RosterStartingCondition | RosterDamageAffinity | RosterResourceState>;
}
export interface EncounterRosterRecipe {
    readonly roster_id: string;
    readonly title: string;
    readonly members: Array<EncounterRosterMember>;
    readonly tags: Array<string>;
    readonly required_battlefield_capabilities: Array<string>;
    readonly forbidden_battlefield_capabilities: Array<string>;
    readonly recipe_digest: string;
}
export interface EncounterRosterSlot {
    readonly roster_slot_id: string;
    readonly roster: EncounterRosterRecipe;
    readonly faction_id: string;
    readonly deployment_zone_id: string;
    readonly controller_defaults: RosterControllerDefaults;
    readonly member_presentations: Array<EncounterMemberPresentation>;
}
export interface FixedRosterOpeningPolicy {
    readonly kind: "fixed_roster";
    readonly roster_slot_id: string;
}
export interface InitiativeOpeningPolicy {
    readonly kind: "initiative";
}
export interface OwnedCharacterRosterSource {
    readonly kind: "owned_character";
    readonly character_id: string;
    readonly expected_character_row_version: number;
    readonly expected_definition_revision: number;
    readonly expected_definition_digest: string;
    readonly expected_holdings_revision: number;
    readonly expected_holdings_digest: string;
    readonly expected_loadout_revision: number;
    readonly expected_loadout_digest: string;
    readonly expected_ruleset_digest: string;
}
export interface RosterBehaviorGrant {
    readonly kind: "behavior_grant";
    readonly behavior_ref: ContentRef;
    readonly configured_display_name: string | null;
    readonly action_cost_variant: "default" | "bonus_action";
}
export interface RosterControllerDefaults {
    readonly controller: RosterControllerKind;
    readonly participant_name: string;
    readonly policy_id: string | null;
    readonly member_overrides: Array<RosterMemberControllerOverride>;
}
export interface RosterDamageAffinity {
    readonly kind: "damage_affinity";
    readonly status: DamageAffinityStatus;
    readonly damage_type: DamageType;
    readonly label: string;
}
export interface RosterItemGrant {
    readonly kind: "item_grant";
    readonly recipe: ContentRecipe;
    readonly count: number;
    readonly placement: RosterItemPlacement;
    readonly equipment_slot: WeaponSlot | BodyPart | RingSlot | null;
    readonly replace_existing: boolean;
    readonly on_grant: "none" | "ignite";
}
export interface RosterMemberControllerOverride {
    readonly member_id: string;
    readonly controller: RosterControllerKind;
    readonly policy_id: string | null;
}
export interface RosterResourceState {
    readonly kind: "resource_state";
    readonly resource_ref: ContentRef;
    readonly value: JsonValue;
}
export interface RosterSpellGrant {
    readonly kind: "spell_grant";
    readonly spell_refs: Array<ContentRef>;
    readonly caster_level: number;
}
export interface RosterStartingCondition {
    readonly kind: "starting_condition";
    readonly condition_ref: ContentRef;
    readonly source_member_role: string | null;
}
export interface RosterStartingDamage {
    readonly kind: "starting_damage";
    readonly amount: number;
    readonly damage_type: DamageType;
    readonly source_member_role: string | null;
}
export interface ContentRef {
    readonly pack_id: string;
    readonly definition_kind: ContentDefinitionKind;
    readonly content_id: string;
    readonly content_version: number;
    readonly definition_contract_hash: string;
}
export interface ItemDefinition {
    readonly persistence_policy: ItemPersistencePolicy;
    readonly stack_compatibility: ItemStackCompatibility;
}
export interface OriginRuntimeSupport {
    readonly status: OriginRuntimeSupportStatus;
    readonly blocked_reason: string | null;
}
export interface CharacterBuildDraft {
    readonly body_recipe: ContentRecipe;
    readonly species_ref: ContentRef;
    readonly species_variant_ref: ContentRef | null;
    readonly background_ref: ContentRef;
    readonly immutable_origin_choices: Array<ClassSkillChoice | StartingProficiencyChoice | FightingStyleChoice | SubclassChoice | CantripChoice | SpellKnownChoice | SpellReplacementChoice | MetamagicChoice | ElementalAncestryChoice | OriginTraitChoice | AbilityScoreImprovementChoice | FeatChoice | StartingEquipmentPackageChoice | StartingApparelPackageChoice>;
    readonly appearance: CharacterAppearanceSelection;
    readonly base_ability_scores: AbilityScoreAllocation;
    readonly flexible_ability_bonuses: FlexibleAbilityBonusSelection;
    readonly class_levels: Array<ClassLevelEntry>;
    readonly premade_id: string | null;
}
export interface CharacterCreationPlan {
    readonly schema_version: 1;
    readonly plan_id: string;
    readonly plan_kind: CharacterCreationPlanKind;
    readonly display_name: string;
    readonly build: CharacterBuildDraft;
    readonly loadout: CharacterLoadoutDraft;
    readonly character_level_entitlement: number;
    readonly supplemental_holdings: Array<StarterHoldingTemplate>;
    readonly source_premade_id: string | null;
    readonly plan_digest: string;
}
export interface CharacterLoadoutDraft {
    readonly prepared_spells: Array<PreparedSpellSourceLoadout>;
    readonly feature_toggles: Array<FeatureToggleSelection>;
}
export interface StarterHoldingTemplate {
    readonly recipe: ContentRecipe;
    readonly quantity: number;
    readonly equipped_slot: WeaponSlot | BodyPart | RingSlot | null;
}
export interface ContentProvenance {
    readonly primary_source_id: string;
    readonly source_anchor: string;
    readonly relation: ContentProvenanceRelation;
    readonly fidelity: ContentFidelity;
    readonly review_status: ContentReviewStatus;
    readonly adapted_from_source_id: string | null;
    readonly notes: string;
}
export interface ContentSource {
    readonly source_id: string;
    readonly source_family: ContentSourceFamily;
    readonly title: string;
    readonly source_version: string;
    readonly rules_baseline: RulesBaseline;
    readonly license_id: string;
    readonly canonical_uri: string;
    readonly document_digest: string;
    readonly attribution_text: string;
    readonly notices: Array<string>;
}
export interface ContentRecipePreset {
    readonly ref: ContentRecipePresetRef;
    readonly recipe: ContentRecipe;
    readonly descriptor: ContentDescriptorSpec;
    readonly provenance: ContentProvenance;
}
export interface ContentRecipePresetRef {
    readonly pack_id: string;
    readonly preset_id: string;
    readonly preset_version: number;
    readonly preset_contract_hash: string;
}
export interface ContentRecipe {
    readonly ref: ContentRef;
    readonly parameters: Record<string, JsonValue>;
    readonly recipe_digest: string;
}
export interface SpatialEffectDefinition {
    readonly anchor_kind: SpatialEffectAnchorKind;
    readonly layer: SpatialEffectLayer;
    readonly occupancy_policy: SpatialEffectOccupancyPolicy;
    readonly blocking_policy: SpatialEffectBlockingPolicy;
    readonly lifetime_policy: SpatialEffectLifetimePolicy;
    readonly trigger_kinds: Array<SpatialEffectTriggerKind>;
    readonly first_per_turn_trigger_kinds: Array<SpatialEffectTriggerKind>;
    readonly transitions: Array<SpatialEffectTransitionDefinition>;
}
export interface SpatialEffectTransitionDefinition {
    readonly operation: SpatialEffectInteractionOperation;
    readonly minimum_intensity: SpatialEffectInteractionIntensity;
    readonly action: SpatialEffectTransitionAction;
    readonly replacement_recipe: ContentRecipe | null;
    readonly delay_rounds: number | null;
}
export interface StartingEquipmentPackageDefinition {
    readonly entries: Array<StartingEquipmentPackageEntry>;
}
export interface StartingEquipmentPackageEntry {
    readonly recipe: ContentRecipe;
    readonly quantity: number;
    readonly equipped_slot: WeaponSlot | BodyPart | RingSlot | null;
}
export interface DamageComponentResolution {
    readonly damage_type: DamageType;
    readonly incoming_damage: number;
    readonly resistance_status: ResistanceStatus;
    readonly multiplier: number;
    readonly after_affinity_damage: number;
    readonly affinity_prevented_damage: number;
    readonly vulnerability_bonus_damage: number;
}
export interface DamageResolution {
    readonly declared_damage: number;
    readonly incoming_damage: number;
    readonly event_prevented_damage: number;
    readonly event_amplified_damage: number;
    readonly components: Array<DamageComponentResolution>;
    readonly after_affinity_damage: number;
    readonly affinity_prevented_damage: number;
    readonly vulnerability_bonus_damage: number;
    readonly flat_reduction_damage: number;
    readonly mitigated_damage: number;
    readonly temporary_hit_point_damage: number;
    readonly normal_hit_point_damage: number;
    readonly survival_cap_prevented_damage: number;
    readonly effective_normal_hit_point_damage: number;
    readonly overkill_damage: number;
}
export interface Dice {
    readonly uuid: string;
    readonly count: number;
    readonly value: 4 | 6 | 8 | 10 | 12 | 20;
    readonly bonus: ModifiableValue;
    readonly roll_type: RollType;
    readonly attack_outcome: AttackOutcome | null;
    readonly crit_extra_dice: number;
    readonly source_entity_uuid: string;
    readonly target_entity_uuid: string | null;
    readonly roll: DiceRoll;
}
export interface DiceRoll {
    readonly roll_uuid: string;
    readonly dice_uuid: string;
    readonly die_size: number | null;
    readonly effective_dice_count: number | null;
    readonly random_faces_rolled: number | null;
    readonly roll_type: RollType;
    readonly results: Array<number> | number;
    readonly total: number;
    readonly bonus: number;
    readonly advantage_status: AdvantageStatus;
    readonly critical_status: CriticalStatus;
    readonly auto_hit_status: AutoHitStatus;
    readonly source_entity_uuid: string;
    readonly target_entity_uuid: string | null;
    readonly attack_outcome: AttackOutcome | null;
}
export interface AbilityCheckD20RollResultEvent {
    readonly wire_type: "dnd.core.events.AbilityCheckD20RollResultEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "check_d20_roll";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly roll_type: RollType;
    readonly roll_modifications: Array<RollModification>;
    readonly original_roll: DiceRoll;
    readonly final_roll: DiceRoll | null;
    readonly dc: number | null;
    readonly bonus: ModifiableValue | null;
    readonly result: boolean | null;
    readonly ability_name: "strength" | "dexterity" | "constitution" | "intelligence" | "wisdom" | "charisma";
}
export interface AbilityCheckEvent {
    readonly wire_type: "dnd.core.events.AbilityCheckEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "ability_check";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly dc: number | ModifiableValue | null;
    readonly bonus: number | ModifiableValue | null;
    readonly dice: Dice | null;
    readonly dice_roll: DiceRoll | null;
    readonly result: boolean | null;
    readonly ability_name: "strength" | "dexterity" | "constitution" | "intelligence" | "wisdom" | "charisma";
}
export interface AttackD20RollResultEvent {
    readonly wire_type: "dnd.core.events.AttackD20RollResultEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "attack_d20_roll";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly roll_type: RollType;
    readonly roll_modifications: Array<RollModification>;
    readonly original_roll: DiceRoll;
    readonly final_roll: DiceRoll | null;
    readonly dc: number | null;
    readonly bonus: ModifiableValue | null;
    readonly result: boolean | null;
    readonly weapon_slot: WeaponSlot | null;
}
export interface D20RollResultEvent {
    readonly wire_type: "dnd.core.events.D20RollResultEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "d20_roll_result";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly roll_type: RollType;
    readonly roll_modifications: Array<RollModification>;
    readonly original_roll: DiceRoll;
    readonly final_roll: DiceRoll | null;
    readonly dc: number | null;
    readonly bonus: ModifiableValue | null;
    readonly result: boolean | null;
}
export interface Damage {
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly damage_dice: 4 | 6 | 8 | 10 | 12 | 20;
    readonly dice_numbers: number;
    readonly damage_bonus: ModifiableValue | null;
    readonly damage_type: DamageType;
}
export interface DamageAppliedEvent {
    readonly wire_type: "dnd.core.events.DamageAppliedEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "damage_applied";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly applied_damage: number;
    readonly normal_hit_point_damage: number;
    readonly temporary_hit_point_damage: number;
    readonly resulting_normal_hp: number;
    readonly resulting_temporary_hp: number;
    readonly damage_type: DamageType;
    readonly damages: Array<Damage>;
    readonly effect_id: string | null;
    readonly resolution: DamageResolution | null;
}
export interface DamageRollPacket {
    readonly damage: Damage;
    readonly original_roll: DiceRoll;
    readonly final_roll: DiceRoll;
}
export interface DamageRollResultEvent {
    readonly wire_type: "dnd.core.events.DamageRollResultEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "damage_roll_result";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly roll_type: RollType;
    readonly roll_modifications: Array<RollModification>;
    readonly weapon_slot: WeaponSlot;
    readonly attack_outcome: AttackOutcome;
    readonly damage_packets: Array<DamageRollPacket>;
}
export interface DeathEvent {
    readonly wire_type: "dnd.core.events.DeathEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "death";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly entity_uuid: string;
    readonly entity_name: string;
    readonly killer_uuid: string | null;
    readonly killer_name: string;
    readonly final_hp: number;
    readonly encounter_uuid: string | null;
}
export interface DeathSaveEvent {
    readonly wire_type: "dnd.core.events.DeathSaveEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "death_save";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly entity_uuid: string;
    readonly entity_name: string;
    readonly encounter_uuid: string | null;
    readonly round_number: number;
    readonly turn_index: number;
    readonly roll: DiceRoll | null;
    readonly natural_roll: number | null;
    readonly dc: number;
    readonly succeeded: boolean;
    readonly successes: number;
    readonly failures: number;
    readonly became_stable: boolean;
    readonly regained_hit_point: boolean;
    readonly died: boolean;
}
export interface EncounterEndEvent {
    readonly wire_type: "dnd.core.events.EncounterEndEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "encounter_end";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly encounter_uuid: string;
    readonly combatant_uuids: Array<string>;
    readonly reason: string | null;
}
export interface EncounterStartEvent {
    readonly wire_type: "dnd.core.events.EncounterStartEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "encounter_start";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly encounter_uuid: string;
    readonly combatant_uuids: Array<string>;
    readonly initiative_order: Array<string>;
}
export interface EngineEvent {
    readonly wire_type: "dnd.core.events.Event";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "base_action" | "attack" | "movement" | "step_movement" | "forced_movement" | "ability_check" | "saving_throw" | "skill_check" | "inflicted_damage" | "take_damage" | "damage_applied" | "heal" | "temporary_hit_points" | "cast_spell" | "attack_miss" | "attack_hit" | "attack_critical" | "condition_application" | "condition_removal" | "weapon_equip" | "weapon_unequip" | "armor_equip" | "armor_unequip" | "shield_equip" | "shield_unequip" | "item_location_state" | "item_charge_consumption" | "traversal_connector_changed" | "trigger_event" | "dice_roll" | "d20_roll_result" | "attack_d20_roll" | "save_d20_roll" | "check_d20_roll" | "damage_roll_result" | "heal_roll_result" | "enemy_spotted" | "enemy_killed" | "enemy_engaged" | "spatial_entity_entered" | "spatial_entity_left" | "spatial_tile_changed" | "spatial_object_placed" | "spatial_object_removed" | "spatial_perceivability_changed" | "spatial_light_changed" | "spatial_object_changed" | "spatial_effect_changed" | "movement_collision" | "sensory_update" | "spatial_effect_interaction" | "encounter_start" | "encounter_end" | "round_start" | "round_end" | "turn_start" | "turn_end" | "life_state_change" | "revive" | "death_save" | "instant_death" | "death";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
}
export interface ForcedMovementEvent {
    readonly wire_type: "dnd.core.events.ForcedMovementEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "forced_movement";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly start_position: [number, number];
    readonly end_position: [number, number];
    readonly direction: [number, number];
    readonly intended_distance: number;
    readonly actual_distance: number;
    readonly blocked_by_obstacle: boolean;
    readonly blocked_by: string | null;
    readonly cause: string;
}
export interface HealEvent {
    readonly wire_type: "dnd.core.events.HealEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "heal";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly total_healing: number;
    readonly actual_healing: number;
    readonly source_description: string;
    readonly was_blocked: boolean;
    readonly spell_level: number;
    readonly resulting_hp: number | null;
    readonly resulting_normal_hp: number | null;
    readonly resulting_temporary_hp: number | null;
}
export interface HealRollResultEvent {
    readonly wire_type: "dnd.core.events.HealRollResultEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "heal_roll_result";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly roll_type: RollType;
    readonly roll_modifications: Array<RollModification>;
    readonly spell_name: string;
    readonly original_roll: DiceRoll;
    readonly final_roll: DiceRoll;
}
export interface InstantDeathEvent {
    readonly wire_type: "dnd.core.events.InstantDeathEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "instant_death";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly entity_uuid: string;
    readonly entity_name: string;
    readonly killer_uuid: string | null;
    readonly killer_name: string;
    readonly source_description: string;
}
export interface LifeStateChangeEvent {
    readonly wire_type: "dnd.core.events.LifeStateChangeEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "life_state_change";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly entity_uuid: string;
    readonly entity_name: string;
    readonly previous_state: LifeState;
    readonly new_state: LifeState;
    readonly reason: LifeStateChangeReason;
    readonly normal_hit_points: number;
}
export interface Range {
    readonly type: RangeType;
    readonly normal: number;
    readonly long: number | null;
}
export interface ReviveEvent {
    readonly wire_type: "dnd.core.events.ReviveEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "revive";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly entity_uuid: string;
    readonly entity_name: string;
    readonly hit_points: number;
    readonly reduce_exhaustion: boolean;
}
export interface RollModification {
    readonly operation: RollModificationOperation;
    readonly handler_name: string;
    readonly packet_index: number | null;
    readonly previous_total: number | null;
    readonly final_total: number;
    readonly reason: string;
    readonly source_ref: ContentRef | null;
    readonly selected_parameter: ActionSelectionParameter | null;
}
export interface RoundEndEvent {
    readonly wire_type: "dnd.core.events.RoundEndEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "round_end";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly encounter_uuid: string;
    readonly round_number: number;
}
export interface RoundStartEvent {
    readonly wire_type: "dnd.core.events.RoundStartEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "round_start";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly encounter_uuid: string;
    readonly round_number: number;
}
export interface SavingThrowD20RollResultEvent {
    readonly wire_type: "dnd.core.events.SavingThrowD20RollResultEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "save_d20_roll";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly roll_type: RollType;
    readonly roll_modifications: Array<RollModification>;
    readonly original_roll: DiceRoll;
    readonly final_roll: DiceRoll | null;
    readonly dc: number | null;
    readonly bonus: ModifiableValue | null;
    readonly result: boolean | null;
    readonly ability_name: "strength" | "dexterity" | "constitution" | "intelligence" | "wisdom" | "charisma" | null;
}
export interface SavingThrowEvent {
    readonly wire_type: "dnd.core.events.SavingThrowEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "saving_throw";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly dc: number | ModifiableValue | null;
    readonly bonus: number | ModifiableValue | null;
    readonly dice: Dice | null;
    readonly dice_roll: DiceRoll | null;
    readonly result: boolean | null;
    readonly ability_name: "strength" | "dexterity" | "constitution" | "intelligence" | "wisdom" | "charisma";
    readonly saving_throw_context: SavingThrowContext | null;
}
export interface SensesUpdateHint {
    readonly requires_fov: boolean;
    readonly requires_paths: boolean;
    readonly entity_entered: [string, [number, number]] | null;
    readonly entity_left: [string, [number, number]] | null;
    readonly light_changed_positions: Array<[number, number]> | null;
    readonly perceivability_entity: string | null;
    readonly object_placed: [string, [number, number]] | null;
    readonly object_removed: [string, [number, number]] | null;
    readonly entity_died: [string, [number, number]] | null;
    readonly directional_positions: Array<[number, number]> | null;
    readonly directional_neighbors: Array<[number, number]> | null;
    readonly directional_channels_changed: Array<string> | null;
    readonly requires_light_recompute: boolean;
    readonly requires_propagation_recompute: boolean;
}
export interface SensoryUpdateEvent {
    readonly wire_type: "dnd.core.events.SensoryUpdateEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "sensory_update";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly observer_uuid: string;
    readonly observer_position: [number, number];
    readonly observer_position_changed: boolean;
    readonly effective_light_levels: Record<string, number>;
    readonly cause_event_uuid: string;
    readonly update_reason: SensoryUpdateReason;
    readonly visible_cells_added: Array<[number, number]>;
    readonly visible_cells_removed: Array<[number, number]>;
    readonly seen_cells_added: Array<[number, number]>;
    readonly visible_entities_added: Record<string, [number, number]>;
    readonly visible_entities_removed: Record<string, [number, number]>;
    readonly visible_entities_moved: Record<string, [[number, number], [number, number]]>;
    readonly visible_objects_added: Record<string, [number, number]>;
    readonly visible_objects_removed: Record<string, [number, number]>;
    readonly visible_objects_moved: Record<string, [[number, number], [number, number]]>;
    readonly sense_modes_changed: boolean;
    readonly sense_modes: Array<SenseMode> | null;
    readonly passive_perception_changed: boolean;
    readonly passive_perception: number | null;
    readonly paths_dirty: boolean;
}
export interface SkillCheckD20RollResultEvent {
    readonly wire_type: "dnd.core.events.SkillCheckD20RollResultEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "check_d20_roll";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly roll_type: RollType;
    readonly roll_modifications: Array<RollModification>;
    readonly original_roll: DiceRoll;
    readonly final_roll: DiceRoll | null;
    readonly dc: number | null;
    readonly bonus: ModifiableValue | null;
    readonly result: boolean | null;
    readonly skill_name: "acrobatics" | "animal_handling" | "arcana" | "athletics" | "deception" | "history" | "insight" | "intimidation" | "investigation" | "medicine" | "nature" | "perception" | "performance" | "persuasion" | "religion" | "sleight_of_hand" | "stealth" | "survival" | null;
}
export interface SkillCheckEvent {
    readonly wire_type: "dnd.core.events.SkillCheckEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "skill_check";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly dc: number | ModifiableValue | null;
    readonly bonus: number | ModifiableValue | null;
    readonly dice: Dice | null;
    readonly dice_roll: DiceRoll | null;
    readonly result: boolean | null;
    readonly skill_name: "acrobatics" | "animal_handling" | "arcana" | "athletics" | "deception" | "history" | "insight" | "intimidation" | "investigation" | "medicine" | "nature" | "perception" | "performance" | "persuasion" | "religion" | "sleight_of_hand" | "stealth" | "survival";
}
export interface SpatialChangeEvent {
    readonly wire_type: "dnd.core.events.SpatialChangeEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "spatial_entity_entered" | "spatial_entity_left" | "spatial_tile_changed" | "spatial_object_placed" | "spatial_object_removed" | "spatial_perceivability_changed" | "spatial_light_changed" | "spatial_object_changed" | "spatial_effect_changed" | "movement_collision" | "spatial_effect_interaction";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly change_type: SpatialChangeType;
    readonly position: [number, number];
    readonly entity_uuid: string | null;
    readonly object_uuid: string | null;
    readonly old_position: [number, number] | null;
    readonly tile_walkable: boolean | null;
    readonly tile_visible: boolean | null;
    readonly senses_hint: SensesUpdateHint | null;
    readonly new_light_level: number | null;
    readonly light_level_map: Record<string, number> | null;
    readonly object_name: string | null;
    readonly object_map_char: string | null;
    readonly object_blocks_movement: boolean | null;
    readonly object_blocks_vision: boolean | null;
    readonly object_is_open: boolean | null;
    readonly directional_position: [number, number] | null;
    readonly directional_directions: Array<string> | null;
    readonly directional_channels: Array<string> | null;
    readonly directional_blocks_movement: Record<string, boolean> | null;
    readonly directional_blocks_vision: Record<string, boolean> | null;
    readonly directional_blocks_light: Record<string, boolean> | null;
    readonly directional_blocks_propagation: Record<string, boolean> | null;
    readonly transition_from: [number, number] | null;
    readonly transition_to: [number, number] | null;
}
export interface SpatialEffectChangeEvent {
    readonly wire_type: "dnd.core.events.SpatialEffectChangeEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "spatial_effect_changed";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly operation: SpatialEffectChangeOperation;
    readonly spatial_effect_uuid: string;
    readonly spatial_effect_content_ref: ContentRef;
    readonly spatial_effect_name: string;
    readonly layer: SpatialEffectLayer;
    readonly anchor_position: [number, number];
    readonly affected_positions: Array<[number, number]>;
    readonly previous_positions: Array<[number, number]>;
}
export interface SpatialEffectInteractionEvent {
    readonly wire_type: "dnd.core.events.SpatialEffectInteractionEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "spatial_effect_interaction";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly operation: SpatialEffectInteractionOperation;
    readonly positions: Array<[number, number]>;
    readonly intensity: SpatialEffectInteractionIntensity;
    readonly duration_rounds: number | null;
    readonly damage_type: DamageType | null;
    readonly source_object_uuid: string | null;
    readonly source_content_ref: ContentRef | null;
}
export interface StepMovementEvent {
    readonly wire_type: "dnd.core.events.StepMovementEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "step_movement";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly from_position: [number, number];
    readonly to_position: [number, number];
    readonly path_index: number;
    readonly total_path_length: number;
    readonly movement_cost: number;
    readonly trajectory: MovementTrajectory;
    readonly disclosed_path: Array<[number, number]>;
    readonly from_elevation_feet: number;
    readonly to_elevation_feet: number;
    readonly provocation_policy: MovementProvocationPolicy;
    readonly committed: boolean;
}
export interface TakeDamageEvent {
    readonly wire_type: "dnd.core.events.TakeDamageEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "take_damage";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly total_damage: number;
    readonly damage_rolls: Array<DiceRoll>;
    readonly damages: Array<Damage>;
    readonly effect_id: string | null;
    readonly final_damage: number | null;
    readonly normal_hit_point_damage_cap: number | null;
    readonly resulting_hp: number | null;
    readonly resolution: DamageResolution | null;
}
export interface TemporaryHitPointsEvent {
    readonly wire_type: "dnd.core.events.TemporaryHitPointsEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "temporary_hit_points";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly requested_amount: number;
    readonly previous_amount: number;
    readonly resulting_amount: number;
    readonly source_description: string;
}
export interface TileElevationChangeEvent {
    readonly wire_type: "dnd.core.events.TileElevationChangeEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "spatial_tile_changed";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly change_type: SpatialChangeType;
    readonly position: [number, number];
    readonly entity_uuid: string | null;
    readonly object_uuid: string | null;
    readonly old_position: [number, number] | null;
    readonly tile_walkable: boolean | null;
    readonly tile_visible: boolean | null;
    readonly senses_hint: SensesUpdateHint | null;
    readonly new_light_level: number | null;
    readonly light_level_map: Record<string, number> | null;
    readonly object_name: string | null;
    readonly object_map_char: string | null;
    readonly object_blocks_movement: boolean | null;
    readonly object_blocks_vision: boolean | null;
    readonly object_is_open: boolean | null;
    readonly directional_position: [number, number] | null;
    readonly directional_directions: Array<string> | null;
    readonly directional_channels: Array<string> | null;
    readonly directional_blocks_movement: Record<string, boolean> | null;
    readonly directional_blocks_vision: Record<string, boolean> | null;
    readonly directional_blocks_light: Record<string, boolean> | null;
    readonly directional_blocks_propagation: Record<string, boolean> | null;
    readonly transition_from: [number, number] | null;
    readonly transition_to: [number, number] | null;
    readonly tile_uuid: string;
    readonly old_height_steps: number;
    readonly new_height_steps: number;
    readonly old_surface_kind: ElevationSurfaceKind;
    readonly new_surface_kind: ElevationSurfaceKind;
    readonly old_slope_axis: SlopeAxis | null;
    readonly new_slope_axis: SlopeAxis | null;
}
export interface TraversalConnectorChangeEvent {
    readonly wire_type: "dnd.core.events.TraversalConnectorChangeEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "traversal_connector_changed";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly operation: TraversalConnectorChangeOperation;
    readonly connector_uuid: string;
    readonly authored_id: string;
    readonly old_connector: TraversalConnector | null;
    readonly new_connector: TraversalConnector | null;
}
export interface TurnEndEvent {
    readonly wire_type: "dnd.core.events.TurnEndEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "turn_end";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly encounter_uuid: string;
    readonly entity_uuid: string;
    readonly round_number: number;
    readonly turn_index: number;
    readonly actions_used: number;
    readonly bonus_actions_used: number;
    readonly movement_used: number;
}
export interface TurnStartEvent {
    readonly wire_type: "dnd.core.events.TurnStartEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "turn_start";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly encounter_uuid: string;
    readonly entity_uuid: string;
    readonly round_number: number;
    readonly turn_index: number;
    readonly actions_available: number;
    readonly bonus_actions_available: number;
    readonly movement_available: number;
    readonly reaction_available: number;
}
export interface ItemContentRefSnapshot {
    readonly pack_id: string;
    readonly definition_kind: "item" | "environment_object";
    readonly content_id: string;
    readonly content_version: number;
    readonly definition_contract_hash: string;
}
export interface ItemPresentationState {
    readonly item_uuid: string;
    readonly content_ref: ItemContentRefSnapshot | null;
    readonly semantic_key: string;
    readonly name: string;
    readonly description: string | null;
    readonly item_kind: ItemPresentationKind;
    readonly rarity: ItemRarity;
    readonly weight: number;
    readonly visual_item_name: string;
    readonly visual_variant_id: string | null;
    readonly equipped_visual_policy: EquippedVisualPolicy;
    readonly damage_dice: string | null;
    readonly damage_type: string | null;
    readonly weapon_properties: Array<string>;
    readonly armor_type: string | null;
    readonly armor_ac: number | null;
    readonly shield_ac_bonus: number | null;
    readonly charges: number | null;
    readonly max_charges: number | null;
    readonly stack_count: number;
    readonly max_stack: number;
    readonly is_consumable: boolean;
}
export interface AdvantageModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly value: AdvantageStatus;
    readonly numerical_value: number;
}
export interface AutoHitModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly value: AutoHitStatus;
}
export interface ContextualAdvantageModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
}
export interface ContextualAutoHitModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
}
export interface ContextualCriticalModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
}
export interface ContextualDamageTypeModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
}
export interface ContextualNumericalModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
}
export interface ContextualResistanceModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
}
export interface ContextualSizeModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
}
export interface CriticalModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly value: CriticalStatus;
}
export interface DamageTypeModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly value: DamageType;
}
export interface NumericalModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly value: number;
    readonly normalized_value: number;
}
export interface ResistanceModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly value: ResistanceStatus;
    readonly damage_type: DamageType;
    readonly numerical_value: number;
}
export interface SizeModifier {
    readonly name: string | null;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly value: Size;
}
export interface ConePresentationGeometry {
    readonly shape: "cone";
    readonly origin: [number, number];
    readonly direction: [number, number];
    readonly length_feet: number;
    readonly angle_degrees: number;
}
export interface CubePresentationGeometry {
    readonly shape: "cube";
    readonly origin: [number, number];
    readonly direction: [number, number] | null;
    readonly size_feet: number;
    readonly centered: boolean;
}
export interface CylinderPresentationGeometry {
    readonly shape: "cylinder";
    readonly center: [number, number];
    readonly radius_feet: number;
    readonly height_feet: number;
}
export interface LinePresentationGeometry {
    readonly shape: "line";
    readonly origin: [number, number];
    readonly direction: [number, number];
    readonly length_feet: number;
    readonly width_feet: number;
}
export interface SpherePresentationGeometry {
    readonly shape: "sphere";
    readonly center: [number, number];
    readonly radius_feet: number;
}
export interface SavingThrowContext {
    readonly cause_ref: ContentRef;
    readonly effect_id: string;
    readonly condition_ref: ContentRef | null;
    readonly is_magical: boolean;
    readonly effect_tags: Array<SavingThrowEffectTag>;
}
export interface SenseMode {
    readonly sense_type: SensesType;
    readonly range_feet: number;
}
export interface ConnectorTraversalDiscovery {
    readonly command: TraversalConnectorCommand;
    readonly authored_id: string;
    readonly kind: TraversalConnectorKind;
    readonly presentation_key: string;
    readonly source_elevation_feet: number;
    readonly destination_elevation_feet: number;
    readonly movement_cost_feet: number;
    readonly action_cost_type: ConnectorActionCostType | null;
    readonly action_cost_amount: number;
    readonly bidirectional: boolean;
    readonly provocation_policy: ConnectorProvocationPolicy;
    readonly destination_status: ConnectorDestinationStatus;
}
export interface TraversalConnector {
    readonly uuid: string;
    readonly authored_id: string;
    readonly kind: TraversalConnectorKind;
    readonly presentation_key: string;
    readonly endpoints: [TraversalConnectorEndpoint, TraversalConnectorEndpoint];
    readonly movement_cost_feet: number;
    readonly action_cost_type: ConnectorActionCostType | null;
    readonly action_cost_amount: number;
    readonly bidirectional: boolean;
    readonly enabled: boolean;
    readonly provocation_policy: ConnectorProvocationPolicy;
    readonly revision: number;
    readonly objective_digest: string;
}
export interface TraversalConnectorCommand {
    readonly connector_uuid: string;
    readonly connector_revision: number;
    readonly connector_digest: string;
    readonly source_position: [number, number];
    readonly destination_position: [number, number];
}
export interface TraversalConnectorDefinition {
    readonly authored_id: string;
    readonly kind: TraversalConnectorKind;
    readonly presentation_key: string;
    readonly endpoint_positions: [[number, number], [number, number]];
    readonly movement_cost_feet: number;
    readonly action_cost_type: ConnectorActionCostType | null;
    readonly action_cost_amount: number;
    readonly bidirectional: boolean;
    readonly enabled: boolean;
    readonly provocation_policy: ConnectorProvocationPolicy;
}
export interface TraversalConnectorEndpoint {
    readonly position: [number, number];
    readonly support_tile_uuid: string;
    readonly elevation_feet: number;
}
export interface ContextualValue {
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly generated_from: Array<string>;
    readonly global_normalizer: boolean;
    readonly value_modifiers: Record<string, ContextualNumericalModifier>;
    readonly min_constraints: Record<string, ContextualNumericalModifier>;
    readonly max_constraints: Record<string, ContextualNumericalModifier>;
    readonly advantage_modifiers: Record<string, ContextualAdvantageModifier>;
    readonly critical_modifiers: Record<string, ContextualCriticalModifier>;
    readonly auto_hit_modifiers: Record<string, ContextualAutoHitModifier>;
    readonly is_outgoing_modifier: boolean;
    readonly size_modifiers: Record<string, ContextualSizeModifier>;
    readonly damage_type_modifiers: Record<string, ContextualDamageTypeModifier>;
    readonly resistance_modifiers: Record<string, ContextualResistanceModifier>;
    readonly largest_size_priority: boolean;
    readonly min: number | null;
    readonly max: number | null;
    readonly score: number;
    readonly normalized_score: number;
    readonly advantage_sum: number;
    readonly advantage: AdvantageStatus;
    readonly critical: CriticalStatus;
    readonly auto_hit: AutoHitStatus;
    readonly size: Size;
    readonly damage_types: Array<DamageType>;
    readonly damage_type: DamageType | null;
    readonly resistance_sum: Record<string, number>;
    readonly resistance: Record<string, ResistanceStatus>;
}
export interface ModifiableValue {
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly generated_from: Array<string>;
    readonly global_normalizer: boolean;
    readonly self_static: StaticValue;
    readonly to_target_static: StaticValue;
    readonly self_contextual: ContextualValue;
    readonly to_target_contextual: ContextualValue;
    readonly from_target_contextual: ContextualValue | null;
    readonly from_target_static: StaticValue | null;
    readonly min: number | null;
    readonly max: number | null;
    readonly score: number;
    readonly normalized_score: number;
    readonly advantage_sum: number;
    readonly advantage: AdvantageStatus;
    readonly critical: CriticalStatus;
    readonly auto_hit: AutoHitStatus;
    readonly size: Size;
    readonly damage_types: Array<DamageType>;
    readonly damage_type: DamageType | null;
    readonly resistance_sum: Record<string, number>;
    readonly resistance: Record<string, ResistanceStatus>;
    readonly outgoing_advantage_sum: number;
    readonly outgoing_advantage: AdvantageStatus;
    readonly outgoing_critical: CriticalStatus;
    readonly outgoing_auto_hit: AutoHitStatus;
}
export interface StaticValue {
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly generated_from: Array<string>;
    readonly global_normalizer: boolean;
    readonly value_modifiers: Record<string, NumericalModifier>;
    readonly min_constraints: Record<string, NumericalModifier>;
    readonly max_constraints: Record<string, NumericalModifier>;
    readonly advantage_modifiers: Record<string, AdvantageModifier>;
    readonly critical_modifiers: Record<string, CriticalModifier>;
    readonly auto_hit_modifiers: Record<string, AutoHitModifier>;
    readonly is_outgoing_modifier: boolean;
    readonly size_modifiers: Record<string, SizeModifier>;
    readonly damage_type_modifiers: Record<string, DamageTypeModifier>;
    readonly resistance_modifiers: Record<string, ResistanceModifier>;
    readonly largest_size_priority: boolean;
    readonly min: number | null;
    readonly max: number | null;
    readonly score: number;
    readonly normalized_score: number;
    readonly advantage_sum: number;
    readonly advantage: AdvantageStatus;
    readonly critical: CriticalStatus;
    readonly auto_hit: AutoHitStatus;
    readonly size: Size;
    readonly damage_types: Array<DamageType>;
    readonly damage_type: DamageType | null;
    readonly resistance_sum: Record<string, number>;
    readonly resistance: Record<string, ResistanceStatus>;
}
export interface DragonbornBreathWeaponEvent {
    readonly wire_type: "dnd.origins.dragonborn.DragonbornBreathWeaponEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "base_action";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string | null;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly costs: Array<BaseCost>;
    readonly source_item_uuid: string | null;
    readonly action_usage_domain: ActionSystemicDomain;
    readonly public_action_usage_subject: PublicContentUsage | SystemicUsage;
    readonly item_charge_cost: number;
    readonly item_charge_action_lineage_uuid: string | null;
    readonly declared_target_entity_uuids: Array<string>;
    readonly application_id: string | null;
    readonly description: string;
    readonly total_targets: number;
    readonly total_damage: number;
    readonly aoe_position: [number, number] | null;
    readonly ancestry_ref: ContentRef;
    readonly ancestry: DragonbornAncestry;
    readonly damage_type: DamageType;
    readonly breath_geometry: DragonbornBreathGeometry;
    readonly save_ability: "dexterity" | "constitution";
    readonly save_dc: number;
    readonly save_success: boolean | null;
    readonly save_roll: DiceRoll | null;
    readonly damage_dice_count: number;
    readonly damages: Array<Damage>;
    readonly damage_rolls: Array<DiceRoll>;
}
export interface CounterspellReactionEvent {
    readonly wire_type: "dnd.spells.abjuration.CounterspellReactionEvent";
    readonly name: string;
    readonly uuid: string;
    readonly source_entity_uuid: string;
    readonly source_entity_name: string | null;
    readonly target_entity_uuid: string | null;
    readonly target_entity_name: string | null;
    readonly use_register: boolean;
    readonly lineage_uuid: string;
    readonly timestamp: string;
    readonly event_type: "trigger_event";
    readonly phase: EventPhase;
    readonly modified: boolean;
    readonly canceled: boolean;
    readonly canceled_from_phase: EventPhase | null;
    readonly parent_event: string | null;
    readonly turn_execution_id: string | null;
    readonly status_message: string | null;
    readonly outcome_code: string;
    readonly outcome_source_entity_uuid: string | null;
    readonly is_first: boolean;
    readonly is_last: boolean;
    readonly lineage_children_events: Array<string>;
    readonly children_events: Array<string>;
    readonly parent_lineage: string | null;
    readonly children_lineages: Array<string>;
    readonly costs: Array<BaseCost>;
    readonly source_item_uuid: string | null;
    readonly action_usage_domain: ActionSystemicDomain;
    readonly public_action_usage_subject: PublicContentUsage | SystemicUsage;
    readonly item_charge_cost: number;
    readonly item_charge_action_lineage_uuid: string | null;
    readonly declared_target_entity_uuids: Array<string>;
    readonly application_id: string | null;
    readonly description: string;
    readonly total_targets: number;
    readonly total_damage: number;
    readonly aoe_position: [number, number] | null;
    readonly triggered_event_uuid: string;
    readonly triggered_lineage_uuid: string;
    readonly incoming_spell_name: string;
    readonly incoming_spell_level: number;
    readonly counterspell_slot_level: number;
    readonly automatic: boolean;
    readonly check_total: number | null;
    readonly check_dc: number | null;
    readonly succeeded: boolean;
}
export interface PublicConfiguredActionSubject {
    readonly kind: "public_configured_action";
    readonly use: "behavior";
    readonly ref: ContentRef;
}
export interface PublicDefinitionSubject {
    readonly kind: "public_definition";
    readonly use: ActionBindingUse;
    readonly ref: ContentRef;
}
export interface PublicProviderSubject {
    readonly kind: "public_provider";
    readonly use: ActionBindingUse;
    readonly ref: ContentRef;
}
export interface PublicSourceItemFact {
    readonly kind: "public_source_item";
    readonly item_uuid: string;
    readonly ref: ContentRef;
}
export interface SystemicActionSubject {
    readonly kind: "systemic";
    readonly use: ActionBindingUse;
    readonly domain: ActionSystemicDomain;
}
export interface ObjectiveDiagnosticsBootstrap {
    readonly projection: "objective";
    readonly protocol: TimelineProtocolIdentity;
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly event_cursor: number;
    readonly combat_log_cursor: number;
    readonly world: ObjectiveReplicatedWorld;
}
export interface ObjectiveDiagnosticsSync {
    readonly projection: "objective";
    readonly protocol: TimelineProtocolIdentity;
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly event_cursor: number;
    readonly combat_log_cursor: number;
}
export interface SubjectiveParityMismatch {
    readonly path: string;
    readonly expected_json: string;
    readonly actual_json: string;
}
export interface SubjectiveRenderParityDiagnosticsResponse {
    readonly projection: "subjective_parity";
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly perspective_epoch_id: string;
    readonly source_event_cursor: number;
    readonly observation_cursor: number;
    readonly presentation_cursor: number;
    readonly combat_log_cursor: number;
    readonly expected_digest: string;
    readonly actual_digest: string;
    readonly matches: boolean;
    readonly compared_path_count: number;
    readonly visible_tile_count: number;
    readonly structural_edge_count: number;
    readonly door_edge_count: number;
    readonly non_empty_structural_edges: boolean;
    readonly mismatches: Array<SubjectiveParityMismatch>;
}
export interface AIProviderCatalogEntry {
    readonly provider_id: string;
    readonly base_url: string;
    readonly protocol_version: number;
    readonly protocol_hash: string;
    readonly policies: Array<PolicyDescriptor>;
    readonly capacity: number;
    readonly active_assignments: number;
    readonly available_capacity: number;
}
export interface AIProviderCatalogResponse {
    readonly providers: Array<AIProviderCatalogEntry>;
}
export interface AIProviderDeleteResponse {
    readonly status: "unregistered";
    readonly provider_id: string;
}
export interface AIProviderRegistrationRequest {
    readonly provider_id: string;
    readonly base_url: string;
}
export interface APIAvailableActionInfo {
    readonly template_name: string;
    readonly semantic_key: string;
    readonly selection_parameter: ActionSelectionParameter | null;
    readonly connector_traversal: ConnectorTraversalDiscovery | null;
    readonly target_type: TargetType;
    readonly availability_status: ActionAvailabilityStatus;
    readonly valid_targets: Array<AvailableTarget>;
    readonly can_afford: boolean;
    readonly display_name: string;
    readonly description: string;
    readonly cost_type: "actions" | "bonus_actions" | "reactions" | "movement" | "spell_slot_1" | "spell_slot_2" | "spell_slot_3" | "spell_slot_4" | "spell_slot_5" | "spell_slot_6" | "spell_slot_7" | "spell_slot_8" | "spell_slot_9";
    readonly cost_amount: number;
    readonly costs: Array<BaseCost>;
    readonly weapon_slot: string | null;
    readonly weapon_name: string | null;
    readonly damage_types: Array<string>;
    readonly outcome_profile: ActionOutcomeProfile | null;
    readonly self_setup_profile: ActionSelfSetupProfile | null;
    readonly target_effect_profile: ActionTargetEffectProfile | null;
    readonly world_effect_profile: ActionWorldEffectProfile | null;
    readonly action_category: ActionCategory;
    readonly base_template_name: string | null;
    readonly spell_level: number | null;
    readonly cast_at_level: number | null;
    readonly is_spell_variant: boolean;
    readonly requires_concentration: boolean;
    readonly num_projectiles: number | null;
    readonly allow_same_target: boolean | null;
    readonly is_item_use: boolean;
    readonly item_stack_count: number | null;
    readonly item_charge_cost: number;
    readonly fixed_healing: number | null;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject;
    readonly source_item_fact: PublicSourceItemFact | null;
}
export interface APIAvailableActions {
    readonly entity_uuid: string;
    readonly entity_actions: Array<APIAvailableActionInfo>;
    readonly position_actions: Array<APIAvailableActionInfo>;
    readonly self_actions: Array<APIAvailableActionInfo>;
    readonly object_actions: Array<APIAvailableActionInfo>;
    readonly remaining_movement: number;
    readonly handler_details: Array<APIAvailableHandlerInfo>;
    readonly execution_authorization: ActionExecutionAuthorization;
    readonly actions_remaining: number;
    readonly bonus_actions_remaining: number;
    readonly reactions_remaining: number;
    readonly extra_attacks_remaining: number;
    readonly spell_slots: Record<string, APIResourcePool>;
    readonly resources: Record<string, APIResourcePool>;
}
export interface APIAvailableHandlerInfo {
    readonly name: string;
    readonly uuid: string;
    readonly enabled: boolean;
    readonly trigger_event: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject;
}
export interface APIEntityHandlersResponse {
    readonly entity_uuid: string;
    readonly handlers: Array<APIAvailableHandlerInfo>;
}
export interface APIEquippableDisplacement {
    readonly item_uuid: string;
    readonly item_name: string;
    readonly slot: string;
}
export interface APIEquippableEntry {
    readonly item_uuid: string;
    readonly item_name: string;
    readonly displaced_items: Array<APIEquippableDisplacement>;
}
export interface APIEquippableItems {
    readonly entity_uuid: string;
    readonly equippable: Record<string, Array<APIEquippableEntry>>;
}
export interface APIResourcePool {
    readonly current: number;
    readonly max: number;
}
export interface APIServerTiming {
    readonly command_type: string;
    readonly diagnostics_enabled: boolean;
    readonly total_ms: number;
    readonly phases: Record<string, number>;
    readonly phase_counts: Record<string, number>;
    readonly phase_max_ms: Record<string, number>;
}
export interface ActionResult {
    readonly success: boolean;
    readonly message: string;
    readonly event_type: string | null;
    readonly outcome_code: string | null;
    readonly turn_continues: boolean;
    readonly encounter_ended: boolean;
    readonly available_actions: APIAvailableActions | null;
    readonly server_timing: APIServerTiming | null;
    readonly event_cursor_after: number | null;
    readonly combat_log_cursor_after: number | null;
}
export interface AdvanceEncounterResult {
    readonly status: string;
    readonly entity_uuid: string | null;
    readonly entity_name: string | null;
    readonly round: number | null;
    readonly turn_index: number | null;
    readonly event_cursor_after: number | null;
    readonly combat_log_cursor_after: number | null;
}
export interface AgentSessionEntityRow {
    readonly entity_uuid: string;
    readonly entity_name: string;
    readonly faction: string | null;
    readonly controller_type: string | null;
    readonly is_active_actor: boolean;
}
export interface AgentSessionListResponse {
    readonly sessions: Array<AgentSessionRow>;
    readonly active_game_id: string | null;
    readonly encounter_active: boolean;
}
export interface AgentSessionRow {
    readonly session_id: string;
    readonly player_type: string;
    readonly name: string;
    readonly connection_status: string;
    readonly is_active_turn: boolean;
    readonly active_controlled_entity_uuid: string | null;
    readonly active_controlled_entity_name: string | null;
    readonly controlled_entities: Array<AgentSessionEntityRow>;
    readonly agent_cursor: number;
    readonly earliest_agent_cursor: number;
    readonly observation_cursor: number | null;
    readonly current_epoch_id: string | null;
    readonly takeover_claim_ids: Array<string>;
}
export interface AoEPreviewResult {
    readonly success: boolean;
    readonly message: string;
    readonly affected_positions: Array<[number, number]>;
    readonly affected_entity_names: Array<string>;
    readonly affected_count: number;
}
export interface CreateSessionRequest {
    readonly player_type: string;
    readonly name: string | null;
}
export interface CreateSessionResponse {
    readonly session_id: string;
    readonly player_type: string;
    readonly name: string;
}
export interface EquipRequest {
    readonly session_id: string;
    readonly item_uuid: string;
    readonly slot: string | null;
}
export interface EquipmentMutationResult {
    readonly success: boolean;
    readonly message: string;
    readonly event_cursor_after: number | null;
    readonly combat_log_cursor_after: number | null;
}
export interface EventContractSummary {
    readonly contract_version: number;
    readonly contract_hash: string;
    readonly event_types: Array<string>;
    readonly wire_types: Array<string>;
}
export interface ExecuteByIndexRequest {
    readonly session_id: string;
    readonly entity_uuid: string;
    readonly template_name: string;
    readonly target_index: number;
    readonly extra_target_uuids: Array<string> | null;
    readonly prefer_safe: boolean;
    readonly return_available_actions: boolean;
    readonly include_timing: boolean;
}
export interface GameCreationAIPolicyOption {
    readonly descriptor: PolicyDescriptor;
    readonly execution: "in_process" | "registered_provider";
    readonly provider_id: string | null;
    readonly capacity: number | null;
    readonly active_assignments: number | null;
    readonly available_capacity: number | null;
}
export interface GameCreationActivateRequest {
    readonly session_id: string;
    readonly expected_source_stream_id: string;
    readonly expected_generation_id: string;
    readonly expected_perspective_epoch_id: string;
}
export interface GameCreationActivateResponse {
    readonly status: "activated" | "already_active";
    readonly game_id: string;
    readonly encounter_uuid: string;
}
export interface GameCreationAuthoredRosterSelection {
    readonly kind: "authored_roster";
    readonly roster_id: string;
}
export interface GameCreationCatalogResponse {
    readonly schema_version: 3;
    readonly controllers: Array<"human" | "ai" | "codex">;
    readonly ai_policies: Array<GameCreationAIPolicyOption>;
    readonly roster_recipes: Array<EncounterRosterRecipe>;
    readonly encounter_recipes: Array<EncounterRecipe>;
    readonly battlefields: Array<BattlefieldDefinition>;
    readonly deployments: Array<EncounterDeploymentSpec>;
}
export interface GameCreationComposeRequest {
    readonly title: string;
    readonly roster_slots: Array<GameCreationRosterSlotSelection>;
    readonly battlefield_id: string;
    readonly deployment_id: string;
    readonly opening_policy: InitiativeOpeningPolicy | FixedRosterOpeningPolicy;
}
export interface GameCreationComposeResponse {
    readonly schema_version: 1;
    readonly content_set_digest: string;
    readonly ruleset_digest: string;
    readonly recipe: EncounterRecipe;
    readonly compatibility: EncounterCompatibilityReport;
    readonly preview: GameCreationEncounterVisualPreviewResponse;
}
export interface GameCreationEntityAssignment {
    readonly member_id: string;
    readonly entity_uuid: string;
    readonly entity_name: string;
    readonly faction: string | null;
    readonly character_id: string | null;
    readonly controller: "human" | "ai" | "codex";
    readonly participant_name: string;
    readonly policy_id: string | null;
    readonly policy_execution: "in_process" | "registered_provider" | null;
    readonly provider_id: string | null;
    readonly codex_session_id: string | null;
    readonly takeover_claim_id: string | null;
    readonly takeover_expires_at: number | null;
}
export interface GameCreationOwnedCharacterControllerOverride {
    readonly character_id: string;
    readonly controller: "human" | "ai" | "codex";
    readonly policy_id: string | null;
}
export interface GameCreationOwnedCharacterRosterSelection {
    readonly kind: "owned_characters";
    readonly title: string;
    readonly character_ids: Array<string>;
    readonly member_controller_overrides: Array<GameCreationOwnedCharacterControllerOverride>;
}
export interface GameCreationPreviewRequest {
    readonly expected_content_set_digest: string;
    readonly expected_ruleset_digest: string;
    readonly recipe: EncounterRecipe;
}
export interface GameCreationRosterResult {
    readonly roster_slot_id: string;
    readonly roster_id: string;
    readonly roster_recipe_digest: string;
    readonly title: string;
    readonly entity_assignments: Array<GameCreationEntityAssignment>;
}
export interface GameCreationRosterSlotSelection {
    readonly roster_slot_id: string;
    readonly roster: GameCreationAuthoredRosterSelection | GameCreationSavedRosterSelection | GameCreationOwnedCharacterRosterSelection;
    readonly faction_id: string;
    readonly deployment_zone_id: string;
    readonly controller_defaults: RosterControllerDefaults;
}
export interface GameCreationSavedRosterSelection {
    readonly kind: "saved_roster";
    readonly saved_roster_id: string;
    readonly expected_revision: number;
    readonly expected_recipe_digest: string;
}
export interface GameCreationStartRequest {
    readonly expected_content_set_digest: string;
    readonly expected_ruleset_digest: string;
    readonly recipe: EncounterRecipe;
    readonly codex_lease_seconds: number;
}
export interface GameCreationStartResponse {
    readonly schema_version: 2;
    readonly recipe_digest: string;
    readonly encounter_uuid: string;
    readonly game_id: string;
    readonly encounter_name: string;
    readonly compatibility: EncounterCompatibilityReport;
    readonly rosters: Array<GameCreationRosterResult>;
    readonly status: "prepared";
}
export interface JoinGameRequest {
    readonly session_id: string;
    readonly entity_uuids: Array<string> | null;
    readonly observer_entity_uuids: Array<string> | null;
    readonly active_observer_uuid: string | null;
}
export interface JoinGameResponse {
    readonly success: boolean;
    readonly game_id: string;
    readonly session_id: string;
    readonly controlled_entities: Array<string>;
    readonly observer_entities: Array<string>;
    readonly active_observer_uuid: string | null;
    readonly message: string;
}
export interface MapEditorCatalog {
    readonly content_set_digest: string;
    readonly presets: Array<MapEditorCatalogEntry>;
    readonly tiles: Array<MapEditorCatalogEntry>;
    readonly objects: Array<MapEditorContentCatalogEntry>;
    readonly loot: Array<MapEditorContentCatalogEntry>;
}
export interface MapEditorCatalogEntry {
    readonly id: string;
    readonly name: string;
    readonly group: string;
    readonly category: string;
    readonly stability: "stable" | "candidate" | "demo";
    readonly placement: string;
    readonly map_char: string | null;
    readonly visual_item_name: string | null;
    readonly flags: Record<string, JsonValue>;
    readonly actions: Array<string>;
    readonly default_state: Record<string, JsonValue>;
}
export interface MapEditorConnectorDeleteRequest {
    readonly authored_id: string;
}
export interface MapEditorConnectorEnabledRequest {
    readonly authored_id: string;
    readonly enabled: boolean;
}
export interface MapEditorConnectorMutationResponse {
    readonly operation: TraversalConnectorChangeOperation;
    readonly connector_uuid: string;
    readonly authored_id: string;
    readonly connector_revision: number;
    readonly connector_digest: string;
    readonly connector: APITraversalConnector | null;
    readonly snapshot: MapEditorMapSnapshot;
}
export interface MapEditorConnectorUpsertRequest {
    readonly definition: TraversalConnectorDefinition;
    readonly replace_existing: boolean;
}
export interface MapEditorContentCatalogEntry {
    readonly recipe: ContentRecipe;
    readonly content_set_digest: string;
    readonly recipe_preset_ref: ContentRecipePresetRef | null;
    readonly display_name: string;
    readonly description: string;
    readonly tags: Array<string>;
    readonly presentation: ContentPresentation;
    readonly ordering: ContentOrdering;
}
export interface MapEditorCreateMapRequest {
    readonly source: "scratch" | "preset";
    readonly width: number;
    readonly height: number;
    readonly origin: [number, number];
    readonly default_tile: string;
    readonly default_light: number;
    readonly preset_id: string | null;
    readonly include_entities: boolean;
}
export interface MapEditorGridBounds {
    readonly min_x: number;
    readonly min_y: number;
    readonly max_x: number;
    readonly max_y: number;
}
export interface MapEditorLightCell {
    readonly x: number;
    readonly y: number;
    readonly light_level: number;
}
export interface MapEditorLightResponse {
    readonly cells: Array<MapEditorLightCell>;
}
export interface MapEditorMapSnapshot {
    readonly grid_bounds: MapEditorGridBounds;
    readonly tiles: Array<APITile>;
    readonly floor_objects: Array<APIFloorObject>;
    readonly connectors: Array<TraversalConnectorDefinition>;
}
export interface MapEditorObjectDeleteRequest {
    readonly object_uuid: string | null;
    readonly position: [number, number] | null;
}
export interface MapEditorObjectPlaceRequest {
    readonly recipe: ContentRecipe;
    readonly content_set_digest: string;
    readonly position: [number, number];
    readonly runtime_state: MapEditorObjectRuntimeState;
}
export interface MapEditorObjectRuntimeState {
    readonly is_open: boolean | null;
    readonly is_lit: boolean | null;
    readonly charges: number | null;
}
export interface MapEditorSaveMapRequest {
    readonly id: string | null;
    readonly name: string;
    readonly overwrite: boolean;
}
export interface MapEditorSavedMapDocument {
    readonly schema_version: 3;
    readonly content_set_digest: string;
    readonly metadata: MapEditorSavedMapMetadata;
    readonly snapshot: MapEditorMapSnapshot;
    readonly object_placements: Array<MapEditorSavedObjectPlacement>;
}
export interface MapEditorSavedMapList {
    readonly maps: Array<MapEditorSavedMapMetadata>;
}
export interface MapEditorSavedMapMetadata {
    readonly id: string;
    readonly name: string;
    readonly created_at: string;
    readonly updated_at: string;
    readonly revision: number;
    readonly grid_bounds: MapEditorGridBounds;
    readonly tile_count: number;
    readonly floor_object_count: number;
    readonly connector_count: number;
    readonly connector_digest: string;
}
export interface MapEditorSavedObjectPlacement {
    readonly recipe: ContentRecipe;
    readonly position: [number, number];
    readonly runtime_state: MapEditorObjectRuntimeState;
}
export interface MapEditorTilePatch {
    readonly x: number;
    readonly y: number;
    readonly type: string | null;
    readonly light_level: number | null;
    readonly elevation_steps: number | null;
    readonly elevation_surface_kind: ElevationSurfaceKind | null;
    readonly slope_axis: SlopeAxis | null;
    readonly directional_channel: "movement" | "vision" | "light" | "propagation" | null;
    readonly direction: "north" | "south" | "east" | "west" | null;
    readonly passable: boolean | null;
}
export interface MapEditorTilePatchRequest {
    readonly tiles: Array<MapEditorTilePatch>;
}
export interface MapEditorVisibilityCell {
    readonly x: number;
    readonly y: number;
    readonly blocks_visibility: boolean;
    readonly blocker: string | null;
}
export interface MapEditorVisibilityResponse {
    readonly cells: Array<MapEditorVisibilityCell>;
}
export interface MapEditorWalkabilityCell {
    readonly x: number;
    readonly y: number;
    readonly walkable: boolean;
    readonly blocker: string | null;
}
export interface MapEditorWalkabilityResponse {
    readonly cells: Array<MapEditorWalkabilityCell>;
}
export interface PositionPreviewRequest {
    readonly session_id: string;
    readonly entity_uuid: string;
    readonly action_name: string;
    readonly position: [number, number];
}
export interface ServerCapabilitiesResponse {
    readonly server_mode: "standalone" | "gateway";
    readonly game_directory_enabled: boolean;
    readonly persistent_game_history: boolean;
    readonly isolated_game_workers: boolean;
}
export interface SessionPingResponse {
    readonly status: string;
    readonly session_id: string;
    readonly connection_status: string;
    readonly is_my_turn: boolean;
    readonly active_entity_uuid: string | null;
    readonly active_entity_name: string | null;
    readonly controlled_entities: Array<string>;
}
export interface SimpleActionRequest {
    readonly session_id: string;
    readonly entity_uuid: string;
}
export interface SpellCatalogEntry {
    readonly id: string;
    readonly content_ref: ContentRef;
    readonly name: string;
    readonly level: number;
    readonly school: string;
    readonly description: string;
    readonly action_category: "spell";
    readonly target_type: string;
    readonly range_type: "self" | "touch" | "ranged";
    readonly range_ft: number;
    readonly projectile_type: "bolt" | "ray" | "orb" | "beam" | "dart" | "spray" | "radiance" | "touch" | "rain" | null;
    readonly aoe_shape_type: "sphere" | "cone" | "line" | "cube" | "cylinder" | null;
    readonly aoe_radius_ft: number | null;
    readonly aoe_length_ft: number | null;
    readonly aoe_width_ft: number | null;
    readonly aoe_height_ft: number | null;
    readonly damage_types: Array<string>;
    readonly healing: boolean;
    readonly attack_roll: boolean;
    readonly saving_throws: Array<SpellCatalogSavingThrow>;
    readonly concentration: boolean;
    readonly ritual: boolean;
    readonly verbal: boolean;
    readonly somatic: boolean | null;
    readonly material: boolean | null;
    readonly classes: Array<string>;
    readonly subclasses: Array<string>;
    readonly source: string;
    readonly multi_target: SpellCatalogMultiTarget | null;
    readonly vfx: SpellCatalogVfx;
}
export interface SpellCatalogMultiTarget {
    readonly min_targets: number | null;
    readonly max_targets: number | null;
    readonly allow_same_target: boolean | null;
    readonly projectiles_per_cast: number | null;
}
export interface SpellCatalogResponse {
    readonly version: string;
    readonly generated_at: string | null;
    readonly spells: Array<SpellCatalogEntry>;
}
export interface SpellCatalogSavingThrow {
    readonly ability: "strength" | "dexterity" | "constitution" | "intelligence" | "wisdom" | "charisma";
    readonly dc_source: "caster_spell_save_dc";
}
export interface SpellCatalogVfx {
    readonly projectile_type: "bolt" | "ray" | "orb" | "beam" | "dart" | "spray" | "radiance" | "touch" | "rain" | null;
    readonly aoe_shape_type: "sphere" | "cone" | "line" | "cube" | "cylinder" | null;
    readonly route_hint: "self" | "touch" | "single_projectile" | "missile_volley" | "aoe" | "aoe_projectile" | "beam" | "ray" | "none";
    readonly recommended_asset_tags: Array<string>;
}
export interface StandaloneGameSessionSummary {
    readonly session_id: string;
    readonly player_type: string;
    readonly name: string;
    readonly connection_status: string;
    readonly controlled_entities: Array<string>;
    readonly is_their_turn: boolean;
}
export interface StandaloneGameStatusResponse {
    readonly active: boolean;
    readonly game_id: string | null;
    readonly encounter_active: boolean;
    readonly active_entity_uuid: string | null;
    readonly sessions: Array<StandaloneGameSessionSummary>;
    readonly creation: GameCreationStartResponse | null;
}
export interface TakeoverClaimResponse {
    readonly claim_id: string;
    readonly session_id: string;
    readonly name: string;
    readonly faction: string | null;
    readonly created_at: number;
    readonly last_heartbeat_at: number;
    readonly lease_seconds: number;
    readonly expires_at: number;
    readonly is_expired: boolean;
    readonly claimed_entities: Array<TakeoverEntityRow>;
}
export interface TakeoverEntityRow {
    readonly entity_uuid: string;
    readonly entity_name: string;
    readonly faction: string | null;
    readonly previous_controller_uuid: string;
    readonly previous_controller_type: string | null;
    readonly current_controller_type: string | null;
    readonly previous_owner_session_id: string | null;
}
export interface TakeoverHeartbeatResponse {
    readonly status: string;
    readonly claim: TakeoverClaimResponse;
}
export interface TakeoverListResponse {
    readonly claims: Array<TakeoverClaimResponse>;
}
export interface TakeoverReleaseResponse {
    readonly status: string;
    readonly claim: TakeoverClaimResponse | null;
    readonly advance_result: AdvanceEncounterResult | null;
}
export interface TakeoverRequest {
    readonly faction: string | null;
    readonly entity_uuids: Array<string> | null;
    readonly session_id: string | null;
    readonly name: string;
    readonly force: boolean;
    readonly lease_seconds: number;
}
export interface ToggleHandlerRequest {
    readonly session_id: string;
    readonly enabled: boolean;
}
export interface ToggleHandlerResponse {
    readonly success: boolean;
    readonly handler_uuid: string;
    readonly enabled: boolean;
}
export interface UnequipRequest {
    readonly session_id: string;
    readonly slot: string;
}
export interface AdminCharacterAdvancementAwardRequest {
    readonly idempotency_key: string;
    readonly expected_earned_character_level: number;
    readonly level_delta: number;
}
export interface BackgroundCatalogEntry {
    readonly ref: ContentRef;
    readonly descriptor: ContentDescriptor;
    readonly definition: BackgroundDefinition;
}
export interface CasterContributionPreviewResponse {
    readonly class_ref: ContentRef;
    readonly class_level: number;
    readonly progression: CasterProgression;
    readonly spellcasting_feature_class_level: number | null;
    readonly spellcasting_source_id: SpellcastingSourceId | null;
    readonly spellcasting_ability: AbilityScoreName | null;
    readonly maximum_spell_rank: number;
    readonly ritual_policy: RitualPreparationPolicy;
}
export interface CharacterAdvancementResponse {
    readonly character_id: string;
    readonly earned_character_level: number;
    readonly awards: Array<CharacterAdvancementAwardRecord>;
}
export interface CharacterAppearanceCatalog {
    readonly schema_version: 4;
    readonly default_selection: CharacterAppearanceSelection;
    readonly options: Array<CharacterAppearanceOptionCatalogEntry>;
    readonly constraints: Array<CharacterAppearanceConstraintCatalogEntry>;
}
export interface CharacterAppearanceConstraintCatalogEntry {
    readonly when_option_id: string;
    readonly when_value_id: string;
    readonly required_option_id: string;
    readonly allowed_value_ids: Array<string>;
}
export interface CharacterAppearanceOptionCatalogEntry {
    readonly option_id: string;
    readonly display_name: string;
    readonly control_kind: CharacterAppearanceControlKind;
    readonly default_value_id: string;
    readonly values: Array<CharacterAppearanceValueCatalogEntry>;
}
export interface CharacterAppearanceOptionRebaseChange {
    readonly kind: "appearance_option_added";
    readonly path: Array<string>;
    readonly selection: CharacterAppearanceOptionSelection;
}
export interface CharacterAppearanceValueCatalogEntry {
    readonly value_id: string;
    readonly display_name: string;
    readonly tint_rgb: number | null;
    readonly tint_source_option_id: "appearance.hair_tint" | null;
    readonly body_category: "NakedBody" | "NakedBody2" | "NakedBody3" | null;
    readonly head_category: "Head1" | "Head9" | "Head10" | "Head16" | "Head17" | "Head22" | null;
    readonly visual_scale_multiplier: number | null;
    readonly visual_scale_x_multiplier: number | null;
}
export interface CharacterAttachmentSummary {
    readonly attachment_id: string;
    readonly game_id: string;
    readonly membership_id: string;
    readonly client_kind: ClientKind;
    readonly client_instance_id: string;
    readonly connected_at: string;
    readonly expires_at: string | null;
}
export interface CharacterBuildPreviewResponse {
    readonly class_level_counts: Array<[ContentRef, number]>;
    readonly automatic_grant_refs: Array<ContentRef>;
    readonly grant_schedule: Array<CharacterGrantScheduleEntryResponse>;
    readonly final_known_spell_refs: Array<ContentRef>;
    readonly caster_contributions: Array<CasterContributionPreviewResponse>;
    readonly effective_spellcaster_level: number;
    readonly normal_spell_slots: Array<[number, number]>;
    readonly final_known_spells: Array<KnownSpellGrantPreviewResponse>;
    readonly origin_innate_spells: Array<OriginInnateSpellGrantPreviewResponse>;
}
export interface CharacterBuildValidationIssueResponse {
    readonly code: CharacterBuildIssueCode | CharacterMutationIssueCode;
    readonly path: Array<string>;
    readonly content_refs: Array<ContentRef>;
    readonly detail: string;
}
export interface CharacterBuildValidationRequest {
    readonly build: CharacterBuildDraft;
    readonly loadout: CharacterLoadoutDraft;
    readonly expected_content_set_digest: string;
    readonly expected_ruleset_digest: string;
}
export interface CharacterBuildValidationResponse {
    readonly valid: boolean;
    readonly issues: Array<CharacterBuildValidationIssueResponse>;
    readonly preview: CharacterBuildPreviewResponse | null;
    readonly normalized_build: CharacterBuildDraft;
    readonly normalized_loadout: CharacterLoadoutDraft;
    readonly content_set_digest: string;
    readonly ruleset_digest: string;
    readonly preview_digest: string | null;
}
export interface CharacterBuildVisualPreviewResponse {
    readonly schema_version: 1;
    readonly content_set_digest: string;
    readonly ruleset_digest: string;
    readonly preview_digest: string;
    readonly normalized_build: CharacterBuildDraft;
    readonly normalized_loadout: CharacterLoadoutDraft;
    readonly entity: APIEntitySummary;
    readonly visual_loadout: EntityVisualLoadout;
}
export interface CharacterContentRebaseIssue {
    readonly path: Array<string>;
    readonly reason: CharacterContentRebaseIssueReason;
    readonly source_ref: ContentRef;
    readonly detail: string;
}
export interface CharacterContentRefRebaseChange {
    readonly kind: "content_ref";
    readonly path: Array<string>;
    readonly source_ref: ContentRef;
    readonly replacement_ref: ContentRef;
}
export interface CharacterCreationCatalogResponse {
    readonly schema_version: 7;
    readonly content_set_digest: string;
    readonly rules: CharacterCreationRulesMetadata;
    readonly appearance_catalog: CharacterAppearanceCatalog;
    readonly body_recipes: Array<ContentRecipe>;
    readonly body_recipe_presets: Array<ContentRecipePreset>;
    readonly species: Array<SpeciesCatalogEntry>;
    readonly species_variants: Array<SpeciesVariantCatalogEntry>;
    readonly backgrounds: Array<BackgroundCatalogEntry>;
    readonly classes: Array<ClassCatalogEntry>;
    readonly subclasses: Array<SubclassCatalogEntry>;
    readonly creation_plans: Array<CharacterCreationPlan>;
    readonly starting_equipment_packages: Array<StartingEquipmentPackageCatalogEntry>;
    readonly starting_apparel_requirement: BuildChoiceRequirement;
    readonly starting_apparel_packages: Array<StartingApparelPackageCatalogEntry>;
}
export interface CharacterCreationRulesMetadata {
    readonly schema_version: 2;
    readonly rules_baseline: "srd_5_1_with_selected_bg3_creation_rules";
    readonly initial_custom_character_level: 1;
    readonly character_level_cap: 20;
    readonly point_buy_budget: 27;
    readonly minimum_ability_score: 8;
    readonly maximum_pre_bonus_ability_score: 15;
    readonly ordinary_ability_score_cap: 20;
    readonly flexible_plus_two: 2;
    readonly flexible_plus_one: 1;
    readonly flexible_bonuses_must_target_distinct_abilities: true;
    readonly hit_points_after_character_level_one: "fixed_class_average";
    readonly supported_multiclass_slot_rounding_policies: Array<MulticlassSlotRoundingPolicy>;
    readonly default_multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy;
    readonly default_permissive_multiclass_prerequisites: boolean;
}
export interface CharacterCreationValidationRequest {
    readonly build: CharacterBuildDraft;
    readonly loadout: CharacterLoadoutDraft;
    readonly expected_content_set_digest: string;
    readonly expected_ruleset_digest: string;
    readonly creation_plan_id: string;
    readonly creation_plan_digest: string;
}
export interface CharacterDefinitionHistoryResponse {
    readonly character_id: string;
    readonly definitions: Array<CharacterDefinitionRecord>;
}
export interface CharacterDirectoryModel {
}
export interface CharacterEquipOperation {
    readonly operation: "equip";
    readonly character_item_id: string;
    readonly target_slot: WeaponSlot | BodyPart | RingSlot;
}
export interface CharacterEquipmentMutationRequest {
    readonly idempotency_key: string;
    readonly expected_row_version: number;
    readonly expected_heads: CharacterRevisionHeads;
    readonly operation: CharacterEquipOperation | CharacterUnequipOperation;
    readonly expected_content_set_digest: string;
    readonly expected_ruleset_digest: string;
}
export interface CharacterGrantProvenanceResponse {
    readonly source_kind: CharacterGrantSourceKind;
    readonly source_ref: ContentRef;
    readonly character_level: number | null;
    readonly class_level_id: string | null;
    readonly class_level: number | null;
    readonly choice_id: string | null;
    readonly ordinal_path: Array<number>;
}
export interface CharacterGrantScheduleEntryResponse {
    readonly kind: CharacterGrantScheduleKind;
    readonly provenance: CharacterGrantProvenanceResponse;
    readonly grant_token: string;
    readonly content_ref: ContentRef | null;
    readonly proficiency: ProficiencySubject | null;
    readonly ability: AbilityScoreName | null;
    readonly amount: number | null;
    readonly replaced_content_ref: ContentRef | null;
}
export interface CharacterLevelUpRequest {
    readonly idempotency_key: string;
    readonly expected_row_version: number;
    readonly expected_heads: CharacterRevisionHeads;
    readonly build: CharacterBuildDraft;
    readonly loadout: CharacterLoadoutDraft;
    readonly expected_content_set_digest: string;
    readonly expected_ruleset_digest: string;
}
export interface CharacterListResponse {
    readonly characters: Array<CanonicalCharacterRecord>;
}
export interface CharacterLoadoutMutationRequest {
    readonly idempotency_key: string;
    readonly expected_row_version: number;
    readonly expected_heads: CharacterRevisionHeads;
    readonly loadout: CharacterLoadoutDraft;
    readonly expected_content_set_digest: string;
    readonly expected_ruleset_digest: string;
}
export interface CharacterMutationExpectation {
    readonly idempotency_key: string;
    readonly expected_row_version: number;
    readonly expected_heads: CharacterRevisionHeads;
}
export interface CharacterOriginChoiceRebaseChange {
    readonly kind: "origin_choice_added";
    readonly path: Array<string>;
    readonly selection: ClassSkillChoice | StartingProficiencyChoice | FightingStyleChoice | SubclassChoice | CantripChoice | SpellKnownChoice | SpellReplacementChoice | MetamagicChoice | ElementalAncestryChoice | OriginTraitChoice | AbilityScoreImprovementChoice | FeatChoice | StartingEquipmentPackageChoice | StartingApparelPackageChoice;
}
export interface CharacterPresentationPreferencesResponse {
    readonly schema_version: 1;
    readonly character_id: string;
    readonly owner_principal_id: string;
    readonly revision: number;
    readonly preferences: Record<string, JsonValue>;
    readonly preferences_digest: string;
    readonly updated_at: string | null;
}
export interface CharacterProfileGameSeat {
    readonly membership: MembershipRecord;
    readonly controlled_entity_uuids: Array<string>;
    readonly active_attachments: Array<CharacterAttachmentSummary>;
}
export interface CharacterProfileResponse {
    readonly principal: PrincipalRecord;
    readonly settings: ProfileSettingsRecord;
    readonly characters: Array<CanonicalCharacterRecord>;
    readonly game_seats: Array<CharacterProfileGameSeat>;
}
export interface CharacterRespecRequest {
    readonly idempotency_key: string;
    readonly expected_row_version: number;
    readonly expected_heads: CharacterRevisionHeads;
    readonly build: CharacterBuildDraft;
    readonly loadout: CharacterLoadoutDraft;
    readonly expected_content_set_digest: string;
    readonly expected_ruleset_digest: string;
}
export interface CharacterRespecSeedResponse {
    readonly schema_version: 1;
    readonly character_id: string;
    readonly source: CharacterRespecSeedSource;
    readonly target_content_set_digest: string;
    readonly target_ruleset_digest: string;
    readonly ready: boolean;
    readonly editable_build: CharacterBuildDraft | null;
    readonly editable_loadout: CharacterLoadoutDraft | null;
    readonly changes: Array<CharacterContentRefRebaseChange | CharacterAppearanceOptionRebaseChange | CharacterOriginChoiceRebaseChange>;
    readonly issues: Array<CharacterContentRebaseIssue>;
}
export interface CharacterRespecSeedSource {
    readonly character_row_version: number;
    readonly heads: CharacterRevisionHeads;
    readonly definition_revision: number;
    readonly definition_digest: string;
    readonly content_set_digest: string;
    readonly ruleset_digest: string;
    readonly definition_created_at: string;
    readonly holdings_created_at: string;
    readonly loadout_created_at: string;
}
export interface CharacterSnapshotResponse {
    readonly character: CanonicalCharacterRecord;
    readonly heads: CharacterRevisionHeads;
    readonly definition: CharacterDefinitionRecord;
    readonly holdings: CharacterHoldingsRecord;
    readonly loadout: CharacterLoadoutRecord;
    readonly advancement: CharacterAdvancementResponse;
}
export interface CharacterUnequipOperation {
    readonly operation: "unequip";
    readonly character_item_id: string;
}
export interface ClassCatalogEntry {
    readonly ref: ContentRef;
    readonly descriptor: ContentDescriptor;
    readonly definition: ClassDefinition;
}
export interface CreateCharacterRequest {
    readonly build: CharacterBuildDraft;
    readonly loadout: CharacterLoadoutDraft;
    readonly expected_content_set_digest: string;
    readonly expected_ruleset_digest: string;
    readonly creation_plan_id: string;
    readonly creation_plan_digest: string;
    readonly display_name: string;
    readonly idempotency_key: string;
}
export interface KnownSpellGrantPreviewResponse {
    readonly spell_ref: ContentRef;
    readonly provider_ref: ContentRef;
    readonly spellcasting_source_id: SpellcastingSourceId;
    readonly grant_token: string;
}
export interface OriginInnateSpellGrantPreviewResponse {
    readonly grant_id: string;
    readonly spell_ref: ContentRef;
    readonly provider_ref: ContentRef;
    readonly spellcasting_source_id: SpellcastingSourceId;
    readonly spellcasting_ability: AbilityScoreName;
    readonly provider_level: number;
    readonly fixed_cast_rank: number;
    readonly uses_per_long_rest: number | null;
    readonly grant_token: string;
}
export interface ReplaceSavedEncounterRequest {
    readonly title: string;
    readonly recipe: EncounterRecipe;
    readonly expected_revision: number;
    readonly expected_recipe_digest: string;
}
export interface ReplaceSavedEncounterRosterRequest {
    readonly title: string;
    readonly recipe: EncounterRosterRecipe;
    readonly expected_revision: number;
    readonly expected_recipe_digest: string;
}
export interface SaveEncounterRequest {
    readonly title: string;
    readonly recipe: EncounterRecipe;
}
export interface SaveEncounterRosterRequest {
    readonly title: string;
    readonly recipe: EncounterRosterRecipe;
}
export interface SavedEncounterListResponse {
    readonly encounters: Array<SavedEncounterRecord>;
}
export interface SavedEncounterRosterListResponse {
    readonly rosters: Array<SavedEncounterRosterRecord>;
}
export interface SpeciesCatalogEntry {
    readonly ref: ContentRef;
    readonly descriptor: ContentDescriptor;
    readonly definition: SpeciesDefinition;
}
export interface SpeciesVariantCatalogEntry {
    readonly ref: ContentRef;
    readonly descriptor: ContentDescriptor;
    readonly definition: SpeciesVariantDefinition;
}
export interface StandaloneLocalProfileResponse {
    readonly profile_id: string;
    readonly display_name: string;
    readonly principal_capability: string;
    readonly settings: ProfileSettingsRecord;
}
export interface StartingApparelPackageCatalogEntry {
    readonly ref: ContentRef;
    readonly descriptor: ContentDescriptor;
    readonly definition: StartingEquipmentPackageDefinition;
}
export interface StartingEquipmentPackageCatalogEntry {
    readonly ref: ContentRef;
    readonly descriptor: ContentDescriptor;
    readonly definition: StartingEquipmentPackageDefinition;
}
export interface SubclassCatalogEntry {
    readonly ref: ContentRef;
    readonly descriptor: ContentDescriptor;
    readonly definition: SubclassDefinition;
}
export interface UpdateCharacterPresentationPreferencesRequest {
    readonly expected_revision: number;
    readonly preferences: Record<string, JsonValue>;
}
export interface UpdateCharacterProfileSettingsRequest {
    readonly expected_settings_version: number;
    readonly permissive_multiclass_prerequisites: boolean;
    readonly multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy;
    readonly allow_respec: boolean;
    readonly spell_preparation_policy: SpellPreparationPolicy;
}
export interface ContentCatalogEntry {
    readonly ref: ContentRef;
    readonly display_name: string;
    readonly description: string;
    readonly tags: Array<string>;
    readonly visibility: ContentVisibility;
    readonly presentation: ContentPresentation;
    readonly ordering: ContentOrdering;
    readonly related_content_refs: Array<ContentRef>;
    readonly provenance: ContentProvenance;
    readonly definition_mode: ContentDeclarationMode;
    readonly runtime_behavior_kind: RuntimeBehaviorKind | null;
    readonly item_definition: ItemDefinition | null;
    readonly spatial_effect_definition: SpatialEffectDefinition | null;
    readonly dependencies: Array<ContentDependency>;
    readonly condition_effect_coverage: ConditionEffectCoverage;
    readonly condition_effect_profile: AuthoredConditionEffectProfile | null;
    readonly condition_lifecycle: AuthoredConditionLifecycle | null;
    readonly parameter_schema: Record<string, JsonValue> | null;
}
export interface ContentCatalogResponse {
    readonly schema_version: 7;
    readonly content_set_digest: string;
    readonly catalog_digest: string;
    readonly entries: Array<ContentCatalogEntry>;
    readonly presets: Array<ContentRecipePresetCatalogEntry>;
    readonly safe_presentations: Array<SafeContentPresentationCatalogEntry>;
}
export interface ContentManifestResponse {
    readonly schema_version: 2;
    readonly engine_content_api: number;
    readonly content_set_digest: string;
    readonly built_in_artifact_digest: string;
    readonly packs: Array<ContentPackManifestEntry>;
    readonly sources: Array<ContentSource>;
}
export interface ContentPackManifestEntry {
    readonly pack_id: string;
    readonly pack_version: string;
    readonly origin: ContentPackOrigin;
    readonly dependencies: Array<string>;
    readonly manifest_contract_digest: string | null;
    readonly pack_digest: string | null;
}
export interface ContentRecipePresetCatalogEntry {
    readonly ref: ContentRecipePresetRef;
    readonly recipe: ContentRecipe;
    readonly display_name: string;
    readonly description: string;
    readonly tags: Array<string>;
    readonly visibility: ContentVisibility;
    readonly presentation: ContentPresentation;
    readonly ordering: ContentOrdering;
    readonly related_content_refs: Array<ContentRef>;
    readonly provenance: ContentProvenance;
}
export interface SafeContentPresentationCatalogEntry {
    readonly ref: SafeContentPresentationRef;
    readonly presentation: ContentPresentation;
}
export interface DirectoryStreamHeartbeat {
    readonly cursor: number;
    readonly server_time: number;
}
export interface DirectoryStreamSync {
    readonly cursor: number;
}
export interface EvictedPayload {
    readonly reason: string;
}
export interface GameCreationEncounterVisualPreviewResponse {
    readonly schema_version: 2;
    readonly content_set_digest: string;
    readonly ruleset_digest: string;
    readonly encounter_recipe_digest: string;
    readonly rosters: Array<GameCreationRosterVisualPreview>;
}
export interface GameCreationMemberVisualPreview {
    readonly member_id: string;
    readonly deployment_role: string;
    readonly entity: APIEntitySummary;
    readonly visual_loadout: EntityVisualLoadout;
}
export interface GameCreationRosterVisualPreview {
    readonly roster_slot_id: string;
    readonly roster_id: string;
    readonly title: string;
    readonly members: Array<GameCreationMemberVisualPreview>;
}
export interface CanonicalCharacterRecord {
    readonly character_id: string;
    readonly owner_principal_id: string;
    readonly display_name: string;
    readonly status: CharacterStatus;
    readonly revision_state: "canonical";
    readonly current_definition_revision: number;
    readonly current_definition_digest: string;
    readonly current_holdings_revision: number;
    readonly current_holdings_digest: string;
    readonly current_loadout_revision: number;
    readonly current_loadout_digest: string;
    readonly created_at: string;
    readonly updated_at: string;
    readonly row_version: number;
}
export interface CharacterAdvancementAwardRecord {
    readonly award_id: string;
    readonly character_id: string;
    readonly level_delta: number;
    readonly source_kind: CharacterAdvancementSourceKind;
    readonly source_id: string;
    readonly created_at: string;
}
export interface CharacterDefinitionRecord {
    readonly definition: CharacterDefinitionRevisionV2;
    readonly created_at: string;
}
export interface CharacterHoldingsRecord {
    readonly holdings: CharacterHoldingsRevision;
    readonly created_at: string;
}
export interface CharacterLoadoutRecord {
    readonly loadout: CharacterLoadoutRevisionV1;
    readonly created_at: string;
}
export interface CharacterRevisionHeads {
    readonly definition_revision: number;
    readonly definition_digest: string;
    readonly holdings_revision: number;
    readonly holdings_digest: string;
    readonly loadout_revision: number;
    readonly loadout_digest: string;
}
export interface DirectoryEventRecord {
    readonly cursor: number;
    readonly event_id: string;
    readonly game_id: string | null;
    readonly event_type: string;
    readonly payload: Record<string, JsonValue>;
    readonly payload_digest: string;
    readonly created_at: string;
}
export interface FinalSummaryRecord {
    readonly summary_id: string;
    readonly game_id: string;
    readonly schema_version: "dnd.game-summary.v3";
    readonly summary_revision: number;
    readonly summary: GameSummaryV3;
    readonly summary_digest: string;
    readonly winner_side_id: string | null;
    readonly terminal_reason: string;
    readonly round_count: number;
    readonly turn_count: number;
    readonly duration_ms: number;
    readonly source_event_digest: string;
    readonly source_combat_log_digest: string;
    readonly created_at: string;
    readonly supersedes_summary_id: string | null;
    readonly is_current: boolean;
}
export interface GameRecord {
    readonly game_id: string;
    readonly engine_game_id: string | null;
    readonly worker_id: string | null;
    readonly worker_generation: number | null;
    readonly created_by_principal_id: string;
    readonly lifecycle_state: GameLifecycleState;
    readonly visibility_policy: VisibilityPolicy;
    readonly observer_policy: ObserverPolicy;
    readonly execution_kind: ExecutionKind;
    readonly scenario_kind: string;
    readonly scenario_id: string;
    readonly display_name: string;
    readonly creation_manifest: Record<string, JsonValue>;
    readonly seed: number | null;
    readonly ruleset_version: string;
    readonly engine_version: string;
    readonly content_digest: string;
    readonly encounter_recipe: EncounterRecipe | null;
    readonly creation_manifest_digest: string;
    readonly created_at: string;
    readonly started_at: string | null;
    readonly ended_at: string | null;
    readonly archived_at: string | null;
    readonly terminal_reason: string | null;
    readonly winner_side_id: string | null;
    readonly final_event_cursor: number | null;
    readonly final_combat_log_cursor: number | null;
    readonly current_summary_digest: string | null;
    readonly row_version: number;
}
export interface MembershipCapabilities {
    readonly may_connect: boolean;
    readonly may_observe_public_state: boolean;
    readonly may_observe_subjective_state: boolean;
    readonly may_control_entities: boolean;
    readonly may_view_agent_telemetry: boolean;
    readonly may_manage_members: boolean;
    readonly may_manage_game: boolean;
    readonly may_view_objective_replay: boolean;
}
export interface MembershipRecord {
    readonly membership_id: string;
    readonly game_id: string;
    readonly principal_id: string;
    readonly role: MembershipRole;
    readonly side_id: string | null;
    readonly controller_kind: string | null;
    readonly membership_state: MembershipState;
    readonly capabilities: MembershipCapabilities;
    readonly subjective_source_membership_id: string | null;
    readonly authority_epoch: number;
    readonly joined_at: string;
    readonly disconnected_at: string | null;
    readonly revoked_at: string | null;
    readonly left_at: string | null;
}
export interface PrincipalRecord {
    readonly principal_id: string;
    readonly principal_kind: PrincipalKind;
    readonly display_name: string;
    readonly credential_hash: string | null;
    readonly metadata: Record<string, JsonValue>;
    readonly metadata_digest: string;
    readonly created_at: string;
    readonly last_seen_at: string | null;
    readonly disabled_at: string | null;
}
export interface ProfileSettingsRecord {
    readonly owner_principal_id: string;
    readonly permissive_multiclass_prerequisites: boolean;
    readonly multiclass_slot_rounding_policy: MulticlassSlotRoundingPolicy;
    readonly allow_respec: boolean;
    readonly spell_preparation_policy: SpellPreparationPolicy;
    readonly ruleset_digest: string;
    readonly settings_version: number;
    readonly updated_at: string;
}
export interface SavedEncounterRecord {
    readonly saved_encounter_id: string;
    readonly owner_principal_id: string;
    readonly title: string;
    readonly recipe: EncounterRecipe;
    readonly schema_version: 1;
    readonly recipe_digest: string;
    readonly revision: number;
    readonly created_at: string;
    readonly updated_at: string;
}
export interface SavedEncounterRosterRecord {
    readonly saved_roster_id: string;
    readonly owner_principal_id: string;
    readonly title: string;
    readonly recipe: EncounterRosterRecipe;
    readonly schema_version: 1;
    readonly recipe_digest: string;
    readonly revision: number;
    readonly created_at: string;
    readonly updated_at: string;
}
export interface AttachHostedGameRequest {
    readonly grant_id: string;
    readonly capability: string;
    readonly client_kind: ClientKind;
    readonly client_instance_id: string;
}
export interface AttachHostedGameResponse {
    readonly game: GameRecord;
    readonly connection: HostedGameConnection;
}
export interface CreateAgentGrantRequest {
    readonly principal_id: string;
    readonly principal_capability: string;
    readonly agent_principal_id: string;
    readonly roster_slot_id: string;
    readonly member_id: string;
}
export interface CreateAgentGrantResponse {
    readonly game: GameRecord;
    readonly membership: MembershipRecord;
    readonly runtime_session_id: string;
    readonly controlled_entity_uuids: Array<string>;
    readonly takeover_claim_id: string;
    readonly grant_id: string;
    readonly grant_capability: string;
}
export interface CreateHostedGameRequest {
    readonly principal_id: string;
    readonly principal_capability: string;
    readonly display_name: string;
    readonly creation: GameCreationStartRequest;
    readonly owner_roster_slot_id: string | null;
    readonly visibility_policy: VisibilityPolicy;
    readonly observer_policy: ObserverPolicy;
    readonly client_kind: ClientKind;
    readonly client_instance_id: string;
}
export interface CreateHostedGameResponse {
    readonly game: GameRecord;
    readonly creation: GameCreationStartResponse;
    readonly connection: HostedGameConnection;
    readonly reconnect_grant_id: string;
    readonly reconnect_capability: string;
}
export interface GatewayModel {
}
export interface GuestPrincipalRequest {
    readonly display_name: string;
}
export interface GuestPrincipalResponse {
    readonly principal: PrincipalRecord;
    readonly principal_capability: string;
}
export interface HostedGameConnection {
    readonly game_id: string;
    readonly attachment_id: string;
    readonly engine_base_url: string;
    readonly runtime_session_id: string;
    readonly runtime_token: string;
    readonly membership: MembershipRecord;
    readonly controlled_entity_uuids: Array<string>;
    readonly observer_entity_uuids: Array<string>;
    readonly active_observer_uuid: string;
    readonly takeover_claim_uuids: Array<string>;
    readonly access_mode: "participant" | "observer" | "agent";
    readonly authority_epoch: number;
    readonly expires_at: number;
}
export interface ObserveHostedGameRequest {
    readonly principal_id: string;
    readonly principal_capability: string;
    readonly client_kind: ClientKind;
    readonly client_instance_id: string;
}
export interface ObserveHostedGameResponse {
    readonly game: GameRecord;
    readonly connection: HostedGameConnection;
    readonly reconnect_grant_id: string;
    readonly reconnect_capability: string;
}
export interface PlayerIdentityRequest {
    readonly display_name: string;
    readonly client_instance_id: string;
}
export interface PlayerIdentityResponse {
    readonly principal: PrincipalRecord;
    readonly credential_id: string;
    readonly principal_capability: string;
    readonly authentication_kind: "name_only_local";
}
export interface ReconnectHostedGameRequest {
    readonly principal_id: string;
    readonly principal_capability: string;
    readonly membership_id: string;
    readonly client_kind: ClientKind;
    readonly client_instance_id: string;
    readonly attachment_policy: AttachmentPolicy;
}
export interface ReconnectHostedGameResponse {
    readonly game: GameRecord;
    readonly connection: HostedGameConnection;
    readonly replaced_attachment_ids: Array<string>;
}
export interface StopHostedGameRequest {
    readonly principal_id: string;
    readonly principal_capability: string;
}
export interface StopHostedGameResponse {
    readonly game: GameRecord;
    readonly stopped: boolean;
}
export interface GameHistoryListResponse {
    readonly games: Array<GameRecord>;
    readonly count: number;
}
export interface WorkerReplayCapture {
    readonly generation_id: string;
    readonly game_id: string;
    readonly encounter_uuid: string;
    readonly source_stream_id: string;
    readonly seed: ObjectiveReplaySeed;
    readonly source_event_origin: number;
    readonly source_combat_log_origin: number;
    readonly terminal_event_cursor: number;
    readonly terminal_combat_log_cursor: number;
}
export interface WorkerSummaryEvidence {
    readonly generation_id: string;
    readonly summary: GameSummaryV3;
    readonly source_event_digest: string;
    readonly source_combat_log_digest: string;
}
export interface ObjectiveReplayBundle {
    readonly replay_contract_version: 2;
    readonly replay_contract_hash: string;
    readonly protocol: TimelineProtocolIdentity;
    readonly game_id: string;
    readonly encounter_uuid: string;
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly seed: ObjectiveReplaySeed;
    readonly terminal_event_cursor: number;
    readonly terminal_combat_log_cursor: number;
    readonly events: Array<GameEventFrame>;
    readonly combat_log_frames: ObjectiveCombatLogFramesResponse;
}
export interface ObjectiveReplaySeed {
    readonly event_cursor: number;
    readonly combat_log_cursor: number;
    readonly world: ObjectiveReplicatedWorld;
}
export interface SubjectivePlayerReplayBundle {
    readonly replay_contract_version: number;
    readonly replay_contract_hash: string;
    readonly game_id: string;
    readonly encounter_uuid: string;
    readonly membership_id: string;
    readonly terminal_source_event_cursor: number;
    readonly terminal_combat_log_cursor: number;
    readonly segments: Array<SubjectiveReplaySegment>;
}
export interface SubjectiveReplaySegment {
    readonly segment_index: number;
    readonly membership_id: string;
    readonly runtime_session_id: string;
    readonly bootstrap: SubjectiveReplicationBootstrap;
    readonly deliveries: Array<SubjectiveFrameDelivery | SubjectiveCombatLogDelivery>;
    readonly through_watermarks: PlayerReplicationWatermarks;
    readonly end_reason: SubjectiveReplaySegmentEnd;
}
export interface ActionPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "action";
    readonly actor_uuid: string;
    readonly action_name: string;
    readonly target_uuids: Array<string>;
    readonly trigger_presentation_id: string | null;
    readonly effect_presentation_ids: Array<string>;
}
export interface AttackPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "attack";
    readonly actor_uuid: string;
    readonly target_uuid: string;
    readonly action_name: string;
    readonly outcome: SubjectiveAttackOutcome;
    readonly delivery: AttackDelivery;
    readonly weapon_slot: PresentationWeaponSlot | null;
    readonly damage_types: Array<PresentationDamageType>;
    readonly projectile_type: PresentationProjectile | null;
    readonly impact_effect_presentation_ids: Array<string>;
}
export interface ConditionPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "condition";
    readonly target_uuid: string;
    readonly condition_ref: ContentRef;
    readonly condition_semantic_key: string;
    readonly condition_name: string;
    readonly condition_category: string | null;
    readonly operation: ConditionOperation;
}
export interface ConeAreaGeometry {
    readonly shape: "cone";
    readonly origin: [number, number];
    readonly direction: [number, number];
    readonly length_feet: number;
    readonly angle_degrees: number;
}
export interface ConnectorPresentationIdentity {
    readonly uuid: string;
    readonly authored_id: string;
    readonly kind: TraversalConnectorKind;
    readonly presentation_key: string;
    readonly revision: number;
}
export interface ConnectorSetReplacePatch {
    readonly kind: "connector_set_replace";
    readonly connectors: Array<APITraversalConnector>;
}
export interface ControlledEquipmentReplacePatch {
    readonly kind: "controlled_equipment_replace";
    readonly entity_uuid: string;
    readonly equipment: APIEquipmentOverview;
}
export interface CounterspellAutomaticSuccess {
    readonly kind: "automatic_success";
}
export interface CounterspellCheckFailure {
    readonly kind: "check_failure";
    readonly check_total: number;
    readonly check_dc: number;
}
export interface CounterspellCheckSuccess {
    readonly kind: "check_success";
    readonly check_total: number;
    readonly check_dc: number;
}
export interface CounterspellPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "counterspell";
    readonly reactor_uuid: string;
    readonly incoming_caster_uuid: string;
    readonly incoming_spell_level: number;
    readonly counterspell_slot_level: number;
    readonly resolution: CounterspellAutomaticSuccess | CounterspellCheckSuccess | CounterspellCheckFailure;
}
export interface CubeAreaGeometry {
    readonly shape: "cube";
    readonly origin: [number, number];
    readonly direction: [number, number] | null;
    readonly size_feet: number;
    readonly centered: boolean;
}
export interface CylinderAreaGeometry {
    readonly shape: "cylinder";
    readonly center: [number, number];
    readonly radius_feet: number;
    readonly height_feet: number;
}
export interface DamagePresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "damage";
    readonly source_uuid: string | null;
    readonly target_uuid: string;
    readonly applied_amount: number;
    readonly resulting_hp: number;
    readonly damage_types: Array<PresentationDamageType>;
}
export interface DoorPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "door";
    readonly object_uuid: string;
    readonly position: [number, number];
    readonly is_open: boolean;
}
export interface DoorStatePatch {
    readonly kind: "door_state";
    readonly object_uuid: string;
    readonly position: [number, number];
    readonly is_open: boolean;
    readonly blocks_movement: boolean;
    readonly blocks_vision: boolean;
}
export interface EffectiveLightCell {
    readonly position: [number, number];
    readonly light_level: number;
}
export interface EncounterPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "encounter";
    readonly encounter_uuid: string;
    readonly transition: EncounterTransition;
    readonly round_number: number;
    readonly acting_entity_uuid: string | null;
    readonly reason: string | null;
    readonly terminal_barrier: boolean;
    readonly projected_combatant_uuids: Array<string>;
}
export interface EncounterReplacePatch {
    readonly kind: "encounter_replace";
    readonly encounter: SubjectiveEncounter | null;
}
export interface EncounterTerminalPresentationFact {
    readonly encounter_uuid: string;
    readonly source_event_uuid: string;
    readonly source_event_cursor: number;
    readonly terminal_authority_id: string;
    readonly reason: string | null;
    readonly projected_combatant_uuids: Array<string>;
    readonly terminal_barrier: true;
}
export interface EntityRemovePatch {
    readonly kind: "entity_remove";
    readonly entity_uuid: string;
}
export interface EntityUpsertPatch {
    readonly kind: "entity_upsert";
    readonly entity: APIEntitySummary;
}
export interface EntityVisualLoadout {
    readonly entity_uuid: string;
    readonly active_weapon_set: ActiveWeaponSet;
    readonly layers: Array<VisualEquipmentLayer>;
}
export interface EquipmentPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "equipment";
    readonly entity_uuid: string;
    readonly visual_loadout: EntityVisualLoadout;
}
export interface FloorObjectRemovePatch {
    readonly kind: "floor_object_remove";
    readonly object_uuid: string;
}
export interface FloorObjectUpsertPatch {
    readonly kind: "floor_object_upsert";
    readonly object: SubjectiveFloorObject;
}
export interface ForcedMovementPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "forced_movement";
    readonly entity_uuid: string;
    readonly source_uuid: string;
    readonly cause: ForcedMovementCause;
    readonly actor_action_presentation_id: string | null;
    readonly start_position: [number, number];
    readonly end_position: [number, number];
    readonly duration_ms: number;
    readonly target_clip: "TakeDamage";
    readonly brace_frame: number;
    readonly playback_speed: number;
}
export interface HealPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "heal";
    readonly source_uuid: string | null;
    readonly target_uuid: string;
    readonly amount: number;
    readonly resulting_hp: number;
}
export interface ItemActionPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "item_action";
    readonly actor_uuid: string;
    readonly item_uuid: string;
    readonly item_kind: ItemPresentationKind;
    readonly action_kind: ItemActionKind;
    readonly actor_clip: "Taunt";
    readonly effect_frame: number;
    readonly playback_speed: number;
    readonly hidden_slots: Array<ActorVisualSlot>;
    readonly effect_presentation_ids: Array<string>;
}
export interface LifeStatePresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "life_state";
    readonly entity_uuid: string;
    readonly previous: LifeState;
    readonly current: LifeState;
    readonly reason: LifeStateChangeReason;
    readonly causing_effect_presentation_id: string | null;
}
export interface LifecycleCausePresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "lifecycle_cause";
    readonly entity_uuid: string;
    readonly cause_kind: LifecycleCauseKind;
    readonly source_uuid: string | null;
    readonly death_save_outcome: DeathSaveOutcome | null;
}
export interface LightPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "light";
    readonly observer_uuid: string;
    readonly mode: "replacement";
    readonly cells: Array<EffectiveLightCell>;
}
export interface LineAreaGeometry {
    readonly shape: "line";
    readonly origin: [number, number];
    readonly direction: [number, number];
    readonly length_feet: number;
    readonly width_feet: number;
}
export interface LocomotionAnchor {
    readonly position: [number, number];
    readonly elevation_feet: number;
}
export interface MovementPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "movement";
    readonly entity_uuid: string;
    readonly locomotion_family: LocomotionFamily;
    readonly trajectory_family: LocomotionTrajectory;
    readonly anchors: Array<LocomotionAnchor>;
    readonly connector: ConnectorPresentationIdentity | null;
    readonly endpoint_outcome: MovementEndpointOutcome;
    readonly perception_commit: "observation_frame";
}
export interface ObserverVisibilityRemovePatch {
    readonly kind: "observer_visibility_remove";
    readonly observer_uuid: string;
}
export interface ObserverVisibilityReplacePatch {
    readonly kind: "observer_visibility_replace";
    readonly observer_uuid: string;
    readonly visibility: APIEntityVisibility;
}
export interface PlayerReplicationProtocolIdentity {
    readonly player_replication_contract_version: number;
    readonly player_replication_contract_hash: string;
    readonly source_stream_id: string;
    readonly generation_id: string;
}
export interface PlayerReplicationWatermarks {
    readonly source_event_cursor: number;
    readonly observation_cursor: number;
    readonly presentation_cursor: number;
    readonly combat_log_cursor: number;
}
export interface ShovePresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "shove";
    readonly actor_uuid: string;
    readonly target_uuid: string;
    readonly outcome: ShoveOutcome;
    readonly actor_clip: "Kick";
    readonly contact_frame: number;
    readonly playback_speed: number;
    readonly forced_movement_presentation_id: string | null;
    readonly prone_condition_presentation_id: string | null;
}
export interface SpatialEffectPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "spatial_effect";
    readonly effect_uuid: string;
    readonly content_ref: ContentRef;
    readonly operation: SpatialEffectChangeOperation;
    readonly layer: SpatialEffectLayer;
    readonly anchor_position: [number, number] | null;
    readonly affected_positions: Array<[number, number]>;
    readonly previous_positions: Array<[number, number]>;
}
export interface SpellPresentationCue {
    readonly presentation_cursor: number;
    readonly presentation_id: string;
    readonly parent_presentation_id: string | null;
    readonly child_presentation_ids: Array<string>;
    readonly source_event_cursor: number;
    readonly source_event_uuid: string;
    readonly binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly trigger_binding_subject: PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject | null;
    readonly source_item_fact: PublicSourceItemFact | null;
    readonly owner_application_id: string | null;
    readonly kind: "spell";
    readonly actor_uuid: string;
    readonly spell_name: string;
    readonly spell_school: PresentationSpellSchool;
    readonly spell_level: number;
    readonly delivery: SpellDelivery;
    readonly targets: Array<SpellTargetPresentation>;
    readonly projectile_type: PresentationProjectile | null;
    readonly area: SphereAreaGeometry | ConeAreaGeometry | LineAreaGeometry | CubeAreaGeometry | CylinderAreaGeometry | null;
}
export interface SpellTargetPresentation {
    readonly disclosed_index: number;
    readonly application_id: string | null;
    readonly outcome: SpellApplicationOutcome;
    readonly target_uuid: string | null;
    readonly position: [number, number] | null;
    readonly effect_presentation_ids: Array<string>;
}
export interface SphereAreaGeometry {
    readonly shape: "sphere";
    readonly center: [number, number];
    readonly radius_feet: number;
}
export interface SubjectiveBootstrapDeferred {
    readonly code: "source_batch_in_flight";
    readonly retryable: true;
    readonly source_stream_id: string;
    readonly generation_id: string;
}
export interface SubjectiveCombatLogDelivery {
    readonly kind: "combat_log";
    readonly watermarks: PlayerReplicationWatermarks;
    readonly frame: SubjectiveCombatLogFrame;
}
export interface SubjectiveCombatLogFrame {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly perspective_epoch_id: string;
    readonly projection: "subjective";
    readonly combat_log_cursor: number;
    readonly event_cursor: number;
    readonly entry: CombatLogEntry | null;
}
export interface SubjectiveCombatLogFramesResponse {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly perspective_epoch_id: string;
    readonly projection: "subjective";
    readonly retained_from_cursor: number;
    readonly from_cursor: number;
    readonly through_cursor: number;
    readonly frames: Array<SubjectiveCombatLogFrame>;
    readonly total: number;
}
export interface SubjectiveCombatant {
    readonly uuid: string;
    readonly name: string;
    readonly initiative: number;
    readonly life_state: LifeState | null;
}
export interface SubjectiveEncounter {
    readonly uuid: string;
    readonly name: string;
    readonly state: string;
    readonly round_number: number;
    readonly current_turn_index: number | null;
    readonly current_entity_uuid: string | null;
    readonly initiative_order: Array<SubjectiveCombatant>;
}
export interface SubjectiveFloorObject {
    readonly uuid: string;
    readonly name: string;
    readonly position: [number, number];
    readonly map_char: string;
    readonly object_kind: FloorObjectProjectionKind;
    readonly safe_presentation_ref: SafeContentPresentationRef;
    readonly visual_item_name: string;
    readonly visual_variant_id: string | null;
    readonly blocks_movement: boolean;
    readonly blocks_vision: boolean;
    readonly is_open: boolean | null;
    readonly blocked_directions: Array<FloorObjectDirection>;
    readonly blocked_channels: Array<FloorObjectBlockingChannel>;
    readonly is_lit: boolean | null;
    readonly very_bright_radius_feet: number | null;
    readonly bright_radius_feet: number | null;
    readonly dim_radius_feet: number | null;
}
export interface SubjectiveFrameDelivery {
    readonly kind: "frame";
    readonly frame: SubjectiveReplicationFrame;
}
export interface SubjectiveFramesResponse {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly perspective_epoch_id: string;
    readonly retained_from_observation_cursor: number;
    readonly from_watermarks: PlayerReplicationWatermarks;
    readonly through_watermarks: PlayerReplicationWatermarks;
    readonly captured_watermarks: PlayerReplicationWatermarks;
    readonly frames: Array<SubjectiveReplicationFrame>;
}
export interface SubjectiveGameState {
    readonly grid: APIGrid;
    readonly entities: Array<APIEntitySummary>;
    readonly encounter: SubjectiveEncounter | null;
    readonly floor_objects: Array<SubjectiveFloorObject>;
}
export interface SubjectivePerspective {
    readonly projection: "subjective";
    readonly perspective_epoch_id: string;
    readonly kind: PerspectiveKind;
    readonly controlled_entity_uuids: Array<string>;
    readonly observer_entity_uuids: Array<string>;
    readonly active_observer_uuid: string;
}
export interface SubjectiveReplicatedWorld {
    readonly state: SubjectiveGameState;
    readonly visibility: APIVisibilityResponse;
    readonly equipment_by_entity: Record<string, APIEquipmentOverview>;
    readonly visual_loadout_by_entity: Record<string, EntityVisualLoadout>;
}
export interface SubjectiveReplicationBootstrap {
    readonly protocol: PlayerReplicationProtocolIdentity;
    readonly perspective: SubjectivePerspective;
    readonly watermarks: PlayerReplicationWatermarks;
    readonly world: SubjectiveReplicatedWorld;
    readonly combat_log_frames: SubjectiveCombatLogFramesResponse;
}
export interface SubjectiveReplicationFrame {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly perspective_epoch_id: string;
    readonly watermarks: PlayerReplicationWatermarks;
    readonly presentation_from_cursor: number;
    readonly patches: Array<EntityUpsertPatch | EntityRemovePatch | TileUpsertPatch | ConnectorSetReplacePatch | FloorObjectUpsertPatch | FloorObjectRemovePatch | EncounterReplacePatch | ObserverVisibilityReplacePatch | ObserverVisibilityRemovePatch | ControlledEquipmentReplacePatch | VisualLoadoutReplacePatch | DoorStatePatch>;
    readonly presentation: Array<MovementPresentationCue | ActionPresentationCue | ForcedMovementPresentationCue | ShovePresentationCue | CounterspellPresentationCue | ItemActionPresentationCue | AttackPresentationCue | SpellPresentationCue | DamagePresentationCue | HealPresentationCue | LifecycleCausePresentationCue | LifeStatePresentationCue | ConditionPresentationCue | DoorPresentationCue | LightPresentationCue | SpatialEffectPresentationCue | EquipmentPresentationCue | EncounterPresentationCue>;
    readonly presentation_delivery: PresentationDeliveryMode;
    readonly presentation_reset_reason: PresentationResetReason | null;
    readonly encounter_terminal: EncounterTerminalPresentationFact | null;
}
export interface SubjectiveSyncDelivery {
    readonly kind: "sync";
    readonly protocol: PlayerReplicationProtocolIdentity;
    readonly perspective: SubjectivePerspective;
    readonly watermarks: PlayerReplicationWatermarks;
}
export interface TileUpsertPatch {
    readonly kind: "tile_upsert";
    readonly tile: APITile;
}
export interface VisualEquipmentLayer {
    readonly slot: VisualLoadoutSlot;
    readonly item_kind: ItemPresentationKind;
    readonly safe_presentation_ref: SafeContentPresentationRef;
    readonly visual_item_name: string;
    readonly visual_variant_id: string | null;
    readonly equipped_visual_policy: EquippedVisualPolicy;
}
export interface VisualLoadoutReplacePatch {
    readonly kind: "visual_loadout_replace";
    readonly loadout: EntityVisualLoadout;
}
export interface ObjectiveReplicatedWorld {
    readonly state: APIGameState;
    readonly visibility: APIVisibilityResponse;
    readonly equipment_by_entity: Record<string, APIEquipmentOverview>;
}
export interface TimelineCombatLogFrame {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly perspective_epoch_id: string;
    readonly projection: CombatLogProjection;
    readonly combat_log_cursor: number;
    readonly event_cursor: number;
    readonly entry: CombatLogEntry | null;
}
export interface TimelineCombatLogFramesResponse {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly perspective_epoch_id: string;
    readonly projection: CombatLogProjection;
    readonly retained_from_cursor: number;
    readonly from_cursor: number;
    readonly through_cursor: number;
    readonly frames: Array<TimelineCombatLogFrame>;
    readonly total: number;
}
export interface GameEventFrame {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly event_index: number;
    readonly event_cursor: number;
    readonly combat_log_cursor: number;
    readonly event: ServerEvent;
}
export interface GameEventFramesResponse {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly retained_from_cursor: number;
    readonly from_cursor: number;
    readonly through_cursor: number;
    readonly frames: Array<GameEventFrame>;
    readonly total: number;
}
export interface ObjectiveCombatLogFrame {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly perspective_epoch_id: "objective";
    readonly projection: "objective";
    readonly combat_log_cursor: number;
    readonly event_cursor: number;
    readonly entry: CombatLogEntry;
}
export interface ObjectiveCombatLogFramesResponse {
    readonly source_stream_id: string;
    readonly generation_id: string;
    readonly perspective_epoch_id: "objective";
    readonly projection: "objective";
    readonly retained_from_cursor: number;
    readonly from_cursor: number;
    readonly through_cursor: number;
    readonly frames: Array<ObjectiveCombatLogFrame>;
    readonly total: number;
}
export interface TimelineProtocolIdentity {
    readonly timeline_contract_version: 2;
    readonly timeline_contract_hash: string;
    readonly event_contract_version: number;
    readonly event_contract_hash: string;
}
export type WireEvent = ServerEvent;
export interface APIAppearance {
    readonly portrait_key: string | null;
    readonly presentation_kind: "layered" | "placeholder";
    readonly visual_scale: number;
    readonly visual_scale_x: number;
    readonly placeholder_tint: number;
    readonly body_category: "NakedBody" | "NakedBody2" | "NakedBody3";
    readonly skin_tint: number;
    readonly head_category: "Head1" | "Head9" | "Head10" | "Head16" | "Head17" | "Head22" | null;
    readonly hair_tint: number;
    readonly has_beard: boolean;
    readonly beard_tint: number;
}
export interface APICombatant {
    readonly uuid: string;
    readonly name: string;
    readonly initiative: number;
    readonly life_state: LifeState | null;
}
export interface APIConditionSummary {
    readonly content_ref: APIContentRefSnapshot;
    readonly semantic_key: string;
    readonly name: string;
    readonly description: string;
    readonly category: string;
    readonly duration_type: string;
    readonly remaining_rounds: number | null;
}
export interface APIContentRefSnapshot {
    readonly pack_id: string;
    readonly definition_kind: "item" | "creature" | "action" | "spell" | "condition" | "trait" | "reaction" | "feat" | "class_feature" | "species" | "species_variant" | "background" | "environment_object" | "spatial_effect" | "rule_primitive";
    readonly content_id: string;
    readonly content_version: number;
    readonly definition_contract_hash: string;
}
export interface APIDirectionalBlockMap {
    readonly north: boolean;
    readonly south: boolean;
    readonly east: boolean;
    readonly west: boolean;
}
export interface APIEncounter {
    readonly uuid: string;
    readonly name: string;
    readonly state: string;
    readonly round_number: number;
    readonly current_turn_index: number;
    readonly current_entity_uuid: string | null;
    readonly initiative_order: Array<APICombatant>;
}
export interface APIEntitySummary {
    readonly uuid: string;
    readonly content_ref: APIContentRefSnapshot;
    readonly species_ref: APIContentRefSnapshot | null;
    readonly species_variant_ref: APIContentRefSnapshot | null;
    readonly background_ref: APIContentRefSnapshot | null;
    readonly name: string;
    readonly position: [number, number];
    readonly hp: number;
    readonly max_hp: number;
    readonly ac: number;
    readonly conditions: Array<string>;
    readonly condition_details: Array<APIConditionSummary>;
    readonly life_state: LifeState;
    readonly faction: string | null;
    readonly creature_type: string;
    readonly size: string;
    readonly appearance: APIAppearance;
}
export interface APIEntityVisibility {
    readonly name: string;
    readonly position: [number, number];
    readonly visible_cells: Array<[number, number]>;
    readonly visible_entities: Array<string>;
    readonly visible_objects: Array<string>;
    readonly seen_cells: Array<[number, number]>;
    readonly sense_modes: Array<SenseMode>;
    readonly effective_light_levels: Record<string, number>;
}
export interface APIEquipmentOverview {
    readonly slots: Array<APIEquipmentSlot>;
    readonly active_weapon_set: WeaponSet;
    readonly ac: number;
    readonly inventory: Array<APIItemSummary>;
}
export interface APIEquipmentSlot {
    readonly slot: string;
    readonly slot_type: string;
    readonly item: APIItemSummary | null;
}
export interface APIFloorObject {
    readonly uuid: string;
    readonly name: string;
    readonly position: [number, number];
    readonly map_char: string;
    readonly state: Record<string, JsonValue>;
}
export interface APIGameState {
    readonly grid: APIGrid;
    readonly entities: Array<APIEntitySummary>;
    readonly encounter: APIEncounter | null;
    readonly floor_objects: Array<APIFloorObject>;
}
export interface APIGrid {
    readonly min_x: number;
    readonly min_y: number;
    readonly max_x: number;
    readonly max_y: number;
    readonly tiles: Array<APITile>;
    readonly connectors: Array<APITraversalConnector>;
}
export interface APIItemRuntimeRecipeRefSnapshot {
    readonly recipe_digest: string;
    readonly preset_ref: APIRecipePresetRefSnapshot | null;
}
export interface APIItemSummary {
    readonly uuid: string;
    readonly content_ref: APIContentRefSnapshot;
    readonly recipe_ref: APIItemRuntimeRecipeRefSnapshot;
    readonly safe_presentation_ref: SafeContentPresentationRef;
    readonly name: string;
    readonly description: string | null;
    readonly item_type: string;
    readonly rarity: string;
    readonly weight: number;
    readonly is_equipped: boolean;
    readonly equipped_slot: string | null;
    readonly visual_item_name: string;
    readonly visual_variant_id: string | null;
    readonly equipped_visual_policy: "visible" | "hidden";
    readonly damage_dice: string | null;
    readonly damage_type: string | null;
    readonly weapon_properties: Array<string>;
    readonly armor_type: string | null;
    readonly armor_ac: number | null;
    readonly shield_ac_bonus: number | null;
    readonly charges: number | null;
    readonly max_charges: number | null;
    readonly stack_count: number | null;
    readonly is_consumable: boolean;
}
export interface APIRecipePresetRefSnapshot {
    readonly pack_id: string;
    readonly preset_id: string;
    readonly preset_version: number;
    readonly preset_contract_hash: string;
}
export interface APISpatialEffectPresentation {
    readonly sprite_key: string | null;
    readonly visual_variant_key: string | null;
    readonly tint_rgb: number | null;
    readonly vfx_profile: string | null;
    readonly audio_key: string | null;
}
export interface APISpatialEffectSummary {
    readonly uuid: string;
    readonly content_ref: APIContentRefSnapshot;
    readonly layer: "ground_surface" | "cloud" | "field";
    readonly anchor_kind: "fixed_position" | "entity" | "world_object" | "independent_movable";
    readonly safe_presentation_ref: SafeContentPresentationRef;
    readonly presentation: APISpatialEffectPresentation;
}
export interface APITile {
    readonly x: number;
    readonly y: number;
    readonly visual_key: string;
    readonly walkable: boolean;
    readonly visible: boolean;
    readonly name: string;
    readonly walking_cost: number;
    readonly elevation_steps: number;
    readonly elevation_surface_kind: ElevationSurfaceKind;
    readonly slope_axis: SlopeAxis | null;
    readonly is_hazardous: boolean;
    readonly conditions: Array<string>;
    readonly condition_details: Array<APIConditionSummary>;
    readonly spatial_effects: Array<APISpatialEffectSummary>;
    readonly light_level: number;
    readonly directional_blocks_movement: APIDirectionalBlockMap;
    readonly directional_blocks_vision: APIDirectionalBlockMap;
    readonly directional_blocks_light: APIDirectionalBlockMap;
    readonly directional_blocks_propagation: APIDirectionalBlockMap;
    readonly directional_structural_edges: DirectionalStructuralEdgeMap;
}
export interface APITraversalConnector {
    readonly uuid: string;
    readonly authored_id: string;
    readonly kind: TraversalConnectorKind;
    readonly presentation_key: string;
    readonly endpoints: [APITraversalConnectorEndpoint, APITraversalConnectorEndpoint];
    readonly movement_cost_feet: number;
    readonly action_cost_type: ConnectorActionCostType | null;
    readonly action_cost_amount: number;
    readonly bidirectional: boolean;
    readonly enabled: boolean;
    readonly provocation_policy: ConnectorProvocationPolicy;
    readonly revision: number;
    readonly objective_digest: string;
}
export interface APITraversalConnectorEndpoint {
    readonly position: [number, number];
    readonly support_tile_uuid: string;
    readonly elevation_feet: number;
}
export type APIVisibilityResponse = Record<string, APIEntityVisibility>;
export interface DirectionalStructuralEdgeMap {
    readonly north: StructuralEdgeAppearance | null;
    readonly south: StructuralEdgeAppearance | null;
    readonly east: StructuralEdgeAppearance | null;
    readonly west: StructuralEdgeAppearance | null;
}
export interface SafeContentPresentationRef {
    readonly presentation_contract_hash: string;
}
export interface StructuralEdgeAppearance {
    readonly kind: StructuralEdgeKind;
    readonly is_open: boolean | null;
}
export type ActionBindingSubject = PublicConfiguredActionSubject | PublicDefinitionSubject | PublicProviderSubject | SystemicActionSubject;
export type SubjectiveWorldPatch = EntityUpsertPatch | EntityRemovePatch | TileUpsertPatch | ConnectorSetReplacePatch | FloorObjectUpsertPatch | FloorObjectRemovePatch | EncounterReplacePatch | ObserverVisibilityReplacePatch | ObserverVisibilityRemovePatch | ControlledEquipmentReplacePatch | VisualLoadoutReplacePatch | DoorStatePatch;
export type SubjectivePresentationCue = MovementPresentationCue | ActionPresentationCue | ForcedMovementPresentationCue | ShovePresentationCue | CounterspellPresentationCue | ItemActionPresentationCue | AttackPresentationCue | SpellPresentationCue | DamagePresentationCue | HealPresentationCue | LifecycleCausePresentationCue | LifeStatePresentationCue | ConditionPresentationCue | DoorPresentationCue | LightPresentationCue | SpatialEffectPresentationCue | EquipmentPresentationCue | EncounterPresentationCue;
export type SubjectiveStreamDelivery = SubjectiveSyncDelivery | SubjectiveFrameDelivery | SubjectiveCombatLogDelivery;
export type SubjectiveReplayDelivery = SubjectiveFrameDelivery | SubjectiveCombatLogDelivery;
export type ConcreteServerEvent = AttackEvent | JumpEvent | MovementEvent | ShoveEvent | SpellEvent | TraverseConnectorEvent | ItemChargeConsumptionEvent | ItemLocationStateEvent | ArmorEquipEvent | ArmorUnequipEvent | ShieldEquipEvent | ShieldUnequipEvent | WeaponEquipEvent | WeaponUnequipEvent | ActionEvent | ConditionApplicationEvent | ConditionRemovalEvent | AbilityCheckD20RollResultEvent | AbilityCheckEvent | AttackD20RollResultEvent | D20RollResultEvent | DamageAppliedEvent | DamageRollResultEvent | DeathEvent | DeathSaveEvent | EncounterEndEvent | EncounterStartEvent | ForcedMovementEvent | HealEvent | HealRollResultEvent | InstantDeathEvent | LifeStateChangeEvent | ReviveEvent | RoundEndEvent | RoundStartEvent | SavingThrowD20RollResultEvent | SavingThrowEvent | SensoryUpdateEvent | SkillCheckD20RollResultEvent | SkillCheckEvent | SpatialChangeEvent | SpatialEffectChangeEvent | SpatialEffectInteractionEvent | StepMovementEvent | TakeDamageEvent | TemporaryHitPointsEvent | TileElevationChangeEvent | TraversalConnectorChangeEvent | TurnEndEvent | TurnStartEvent | DragonbornBreathWeaponEvent | CounterspellReactionEvent;
export type ServerEvent = ConcreteServerEvent | EngineEvent;
export interface EventByWireType {
    readonly "dnd.actions.AttackEvent": AttackEvent;
    readonly "dnd.actions.JumpEvent": JumpEvent;
    readonly "dnd.actions.MovementEvent": MovementEvent;
    readonly "dnd.actions.ShoveEvent": ShoveEvent;
    readonly "dnd.actions.SpellEvent": SpellEvent;
    readonly "dnd.actions.TraverseConnectorEvent": TraverseConnectorEvent;
    readonly "dnd.blocks.base_item.ItemChargeConsumptionEvent": ItemChargeConsumptionEvent;
    readonly "dnd.blocks.base_item.ItemLocationStateEvent": ItemLocationStateEvent;
    readonly "dnd.blocks.equipment.ArmorEquipEvent": ArmorEquipEvent;
    readonly "dnd.blocks.equipment.ArmorUnequipEvent": ArmorUnequipEvent;
    readonly "dnd.blocks.equipment.ShieldEquipEvent": ShieldEquipEvent;
    readonly "dnd.blocks.equipment.ShieldUnequipEvent": ShieldUnequipEvent;
    readonly "dnd.blocks.equipment.WeaponEquipEvent": WeaponEquipEvent;
    readonly "dnd.blocks.equipment.WeaponUnequipEvent": WeaponUnequipEvent;
    readonly "dnd.core.base_actions.ActionEvent": ActionEvent;
    readonly "dnd.core.base_conditions.ConditionApplicationEvent": ConditionApplicationEvent;
    readonly "dnd.core.base_conditions.ConditionRemovalEvent": ConditionRemovalEvent;
    readonly "dnd.core.events.AbilityCheckD20RollResultEvent": AbilityCheckD20RollResultEvent;
    readonly "dnd.core.events.AbilityCheckEvent": AbilityCheckEvent;
    readonly "dnd.core.events.AttackD20RollResultEvent": AttackD20RollResultEvent;
    readonly "dnd.core.events.D20RollResultEvent": D20RollResultEvent;
    readonly "dnd.core.events.DamageAppliedEvent": DamageAppliedEvent;
    readonly "dnd.core.events.DamageRollResultEvent": DamageRollResultEvent;
    readonly "dnd.core.events.DeathEvent": DeathEvent;
    readonly "dnd.core.events.DeathSaveEvent": DeathSaveEvent;
    readonly "dnd.core.events.EncounterEndEvent": EncounterEndEvent;
    readonly "dnd.core.events.EncounterStartEvent": EncounterStartEvent;
    readonly "dnd.core.events.Event": EngineEvent;
    readonly "dnd.core.events.ForcedMovementEvent": ForcedMovementEvent;
    readonly "dnd.core.events.HealEvent": HealEvent;
    readonly "dnd.core.events.HealRollResultEvent": HealRollResultEvent;
    readonly "dnd.core.events.InstantDeathEvent": InstantDeathEvent;
    readonly "dnd.core.events.LifeStateChangeEvent": LifeStateChangeEvent;
    readonly "dnd.core.events.ReviveEvent": ReviveEvent;
    readonly "dnd.core.events.RoundEndEvent": RoundEndEvent;
    readonly "dnd.core.events.RoundStartEvent": RoundStartEvent;
    readonly "dnd.core.events.SavingThrowD20RollResultEvent": SavingThrowD20RollResultEvent;
    readonly "dnd.core.events.SavingThrowEvent": SavingThrowEvent;
    readonly "dnd.core.events.SensoryUpdateEvent": SensoryUpdateEvent;
    readonly "dnd.core.events.SkillCheckD20RollResultEvent": SkillCheckD20RollResultEvent;
    readonly "dnd.core.events.SkillCheckEvent": SkillCheckEvent;
    readonly "dnd.core.events.SpatialChangeEvent": SpatialChangeEvent;
    readonly "dnd.core.events.SpatialEffectChangeEvent": SpatialEffectChangeEvent;
    readonly "dnd.core.events.SpatialEffectInteractionEvent": SpatialEffectInteractionEvent;
    readonly "dnd.core.events.StepMovementEvent": StepMovementEvent;
    readonly "dnd.core.events.TakeDamageEvent": TakeDamageEvent;
    readonly "dnd.core.events.TemporaryHitPointsEvent": TemporaryHitPointsEvent;
    readonly "dnd.core.events.TileElevationChangeEvent": TileElevationChangeEvent;
    readonly "dnd.core.events.TraversalConnectorChangeEvent": TraversalConnectorChangeEvent;
    readonly "dnd.core.events.TurnEndEvent": TurnEndEvent;
    readonly "dnd.core.events.TurnStartEvent": TurnStartEvent;
    readonly "dnd.origins.dragonborn.DragonbornBreathWeaponEvent": DragonbornBreathWeaponEvent;
    readonly "dnd.spells.abjuration.CounterspellReactionEvent": CounterspellReactionEvent;
}
export interface SdkModelByName {
    readonly "AttackEvent": AttackEvent;
    readonly "JumpEvent": JumpEvent;
    readonly "MovementEvent": MovementEvent;
    readonly "ShoveEvent": ShoveEvent;
    readonly "SpellEvent": SpellEvent;
    readonly "TraverseConnectorEvent": TraverseConnectorEvent;
    readonly "PolicyDescriptor": PolicyDescriptor;
    readonly "AppliedDamageByActionSubjectV3": AppliedDamageByActionSubjectV3;
    readonly "AttackStatisticsV1": AttackStatisticsV1;
    readonly "CombatStatisticsV3": CombatStatisticsV3;
    readonly "ContentUsageCountV3": ContentUsageCountV3;
    readonly "DamagePreventionStatisticsV2": DamagePreventionStatisticsV2;
    readonly "DamageStatisticsV3": DamageStatisticsV3;
    readonly "DiceStatisticsV2": DiceStatisticsV2;
    readonly "EntitySnapshotV1": EntitySnapshotV1;
    readonly "EntitySummaryV3": EntitySummaryV3;
    readonly "GameOutcomeV1": GameOutcomeV1;
    readonly "GameSummaryV3": GameSummaryV3;
    readonly "HealingStatisticsV1": HealingStatisticsV1;
    readonly "MetricProvenanceV1": MetricProvenanceV1;
    readonly "MovementStatisticsV1": MovementStatisticsV1;
    readonly "OutcomeCountV2": OutcomeCountV2;
    readonly "ResolutionStatisticsV2": ResolutionStatisticsV2;
    readonly "RollLuckStatisticsV2": RollLuckStatisticsV2;
    readonly "SideSummaryV3": SideSummaryV3;
    readonly "SummaryCompletenessV1": SummaryCompletenessV1;
    readonly "SummaryProvenanceV1": SummaryProvenanceV1;
    readonly "TerminalCursorV1": TerminalCursorV1;
    readonly "UsageCountV1": UsageCountV1;
    readonly "ItemChargeConsumptionEvent": ItemChargeConsumptionEvent;
    readonly "ItemLocationStateEvent": ItemLocationStateEvent;
    readonly "ArmorEquipEvent": ArmorEquipEvent;
    readonly "ArmorUnequipEvent": ArmorUnequipEvent;
    readonly "ShieldEquipEvent": ShieldEquipEvent;
    readonly "ShieldUnequipEvent": ShieldUnequipEvent;
    readonly "WeaponEquipEvent": WeaponEquipEvent;
    readonly "WeaponUnequipEvent": WeaponUnequipEvent;
    readonly "ActionSelectionParameter": ActionSelectionParameter;
    readonly "PublicContentUsage": PublicContentUsage;
    readonly "SystemicUsage": SystemicUsage;
    readonly "ActionOutcomeProfile": ActionOutcomeProfile;
    readonly "DamageRollProfile": DamageRollProfile;
    readonly "ActionEvent": ActionEvent;
    readonly "ActionSelfSetupProfile": ActionSelfSetupProfile;
    readonly "ActionSetupMaintenanceProfile": ActionSetupMaintenanceProfile;
    readonly "ActionTargetEffectBranchProfile": ActionTargetEffectBranchProfile;
    readonly "ActionTargetEffectProfile": ActionTargetEffectProfile;
    readonly "ActionWorldEffectProfile": ActionWorldEffectProfile;
    readonly "AvailableTarget": AvailableTarget;
    readonly "BaseCost": BaseCost;
    readonly "InformationEffectProfile": InformationEffectProfile;
    readonly "OpportunityAttackExposure": OpportunityAttackExposure;
    readonly "TopologyEffectProfile": TopologyEffectProfile;
    readonly "BaseCondition": BaseCondition;
    readonly "ConditionApplicationEvent": ConditionApplicationEvent;
    readonly "ConditionRemovalEvent": ConditionRemovalEvent;
    readonly "Duration": Duration;
    readonly "OutcomeProtection": OutcomeProtection;
    readonly "AbilityCheckLogData": AbilityCheckLogData;
    readonly "ActionLogData": ActionLogData;
    readonly "AttackLogData": AttackLogData;
    readonly "CombatLogEntry": CombatLogEntry;
    readonly "ConditionLogData": ConditionLogData;
    readonly "DamageRollDisplay": DamageRollDisplay;
    readonly "DamageTakenLogData": DamageTakenLogData;
    readonly "DeathSaveLogData": DeathSaveLogData;
    readonly "DiceRollDisplay": DiceRollDisplay;
    readonly "EntitySpottedLogData": EntitySpottedLogData;
    readonly "HazardDetectedLogData": HazardDetectedLogData;
    readonly "HealLogData": HealLogData;
    readonly "ModifierBreakdown": ModifierBreakdown;
    readonly "MovementLogData": MovementLogData;
    readonly "MultiEntityLogData": MultiEntityLogData;
    readonly "RollModificationLogData": RollModificationLogData;
    readonly "RollModificationLogFact": RollModificationLogFact;
    readonly "SavingThrowLogData": SavingThrowLogData;
    readonly "SkillCheckLogData": SkillCheckLogData;
    readonly "SpatialEffectInteractionLogData": SpatialEffectInteractionLogData;
    readonly "SpatialEffectLogData": SpatialEffectLogData;
    readonly "SpellInterruptionLogData": SpellInterruptionLogData;
    readonly "SpellSaveLogData": SpellSaveLogData;
    readonly "TemporaryHitPointsLogData": TemporaryHitPointsLogData;
    readonly "TurnLogData": TurnLogData;
    readonly "BattlefieldDefinition": BattlefieldDefinition;
    readonly "BattlefieldElevationCell": BattlefieldElevationCell;
    readonly "BattlefieldPreview": BattlefieldPreview;
    readonly "BattlefieldPreviewCell": BattlefieldPreviewCell;
    readonly "BattlefieldPreviewObject": BattlefieldPreviewObject;
    readonly "BoundContentIdentity": BoundContentIdentity;
    readonly "ContentDependency": ContentDependency;
    readonly "ContentDescriptor": ContentDescriptor;
    readonly "ContentDescriptorSpec": ContentDescriptorSpec;
    readonly "ContentOrdering": ContentOrdering;
    readonly "ContentPresentation": ContentPresentation;
    readonly "EquipmentSpritePresentation": EquipmentSpritePresentation;
    readonly "AbilityScoreAllocation": AbilityScoreAllocation;
    readonly "AbilityScoreImprovementChoice": AbilityScoreImprovementChoice;
    readonly "AbilityScorePrerequisite": AbilityScorePrerequisite;
    readonly "AllOfPrerequisite": AllOfPrerequisite;
    readonly "AnyOfPrerequisite": AnyOfPrerequisite;
    readonly "BackgroundDefinition": BackgroundDefinition;
    readonly "BuildChoiceRequirement": BuildChoiceRequirement;
    readonly "CantripChoice": CantripChoice;
    readonly "CharacterAppearanceOptionSelection": CharacterAppearanceOptionSelection;
    readonly "CharacterAppearanceSelection": CharacterAppearanceSelection;
    readonly "CharacterDefinitionRevisionV2": CharacterDefinitionRevisionV2;
    readonly "CharacterHoldingsRevision": CharacterHoldingsRevision;
    readonly "CharacterItemV1": CharacterItemV1;
    readonly "CharacterLoadoutRevisionV1": CharacterLoadoutRevisionV1;
    readonly "ClassDefinition": ClassDefinition;
    readonly "ClassLevelDefinition": ClassLevelDefinition;
    readonly "ClassLevelEntry": ClassLevelEntry;
    readonly "ClassLevelId": ClassLevelId;
    readonly "ClassLevelPrerequisite": ClassLevelPrerequisite;
    readonly "ClassProficiencyPackage": ClassProficiencyPackage;
    readonly "ClassSkillChoice": ClassSkillChoice;
    readonly "ClassSpellEntitlement": ClassSpellEntitlement;
    readonly "ElementalAncestryChoice": ElementalAncestryChoice;
    readonly "FeatChoice": FeatChoice;
    readonly "FeatureToggleSelection": FeatureToggleSelection;
    readonly "FightingStyleChoice": FightingStyleChoice;
    readonly "FlexibleAbilityBonusSelection": FlexibleAbilityBonusSelection;
    readonly "HasFeaturePrerequisite": HasFeaturePrerequisite;
    readonly "ItemAugmentationRecord": ItemAugmentationRecord;
    readonly "KnowsSpellPrerequisite": KnowsSpellPrerequisite;
    readonly "MetamagicChoice": MetamagicChoice;
    readonly "NotPrerequisite": NotPrerequisite;
    readonly "OriginInnateSpellGrant": OriginInnateSpellGrant;
    readonly "OriginInnateSpellcastingDefinition": OriginInnateSpellcastingDefinition;
    readonly "OriginLevelGrant": OriginLevelGrant;
    readonly "OriginTraitChoice": OriginTraitChoice;
    readonly "PreparedSpellSourceLoadout": PreparedSpellSourceLoadout;
    readonly "ProficiencySubject": ProficiencySubject;
    readonly "SpeciesDefinition": SpeciesDefinition;
    readonly "SpeciesVariantDefinition": SpeciesVariantDefinition;
    readonly "SpellKnownChoice": SpellKnownChoice;
    readonly "SpellReplacementChoice": SpellReplacementChoice;
    readonly "SpellcastingSourceId": SpellcastingSourceId;
    readonly "StartingApparelPackageChoice": StartingApparelPackageChoice;
    readonly "StartingEquipmentPackageChoice": StartingEquipmentPackageChoice;
    readonly "StartingProficiencyChoice": StartingProficiencyChoice;
    readonly "SubclassChoice": SubclassChoice;
    readonly "SubclassDefinition": SubclassDefinition;
    readonly "TotalCharacterLevelPrerequisite": TotalCharacterLevelPrerequisite;
    readonly "EffectOrigin": EffectOrigin;
    readonly "ActionOutcomeConditionEffectGate": ActionOutcomeConditionEffectGate;
    readonly "AttackOutcomeConditionEffectGate": AttackOutcomeConditionEffectGate;
    readonly "AuthoredConditionEffect": AuthoredConditionEffect;
    readonly "AuthoredConditionEffectBranch": AuthoredConditionEffectBranch;
    readonly "AuthoredConditionEffectProfile": AuthoredConditionEffectProfile;
    readonly "AuthoredConditionLifecycle": AuthoredConditionLifecycle;
    readonly "AutomaticConditionEffectGate": AutomaticConditionEffectGate;
    readonly "ConditionEffectSelector": ConditionEffectSelector;
    readonly "ConfigurationConditionEffectGate": ConfigurationConditionEffectGate;
    readonly "OriginRootConditionEffectGate": OriginRootConditionEffectGate;
    readonly "SavingThrowConditionEffectGate": SavingThrowConditionEffectGate;
    readonly "AuthoredCreatureRosterSource": AuthoredCreatureRosterSource;
    readonly "EncounterCompatibilityIssue": EncounterCompatibilityIssue;
    readonly "EncounterCompatibilityReport": EncounterCompatibilityReport;
    readonly "EncounterDeploymentRoleSlot": EncounterDeploymentRoleSlot;
    readonly "EncounterDeploymentSpec": EncounterDeploymentSpec;
    readonly "EncounterDeploymentZone": EncounterDeploymentZone;
    readonly "EncounterMemberPresentation": EncounterMemberPresentation;
    readonly "EncounterNotablePosition": EncounterNotablePosition;
    readonly "EncounterRecipe": EncounterRecipe;
    readonly "EncounterRosterMember": EncounterRosterMember;
    readonly "EncounterRosterRecipe": EncounterRosterRecipe;
    readonly "EncounterRosterSlot": EncounterRosterSlot;
    readonly "FixedRosterOpeningPolicy": FixedRosterOpeningPolicy;
    readonly "InitiativeOpeningPolicy": InitiativeOpeningPolicy;
    readonly "OwnedCharacterRosterSource": OwnedCharacterRosterSource;
    readonly "RosterBehaviorGrant": RosterBehaviorGrant;
    readonly "RosterControllerDefaults": RosterControllerDefaults;
    readonly "RosterDamageAffinity": RosterDamageAffinity;
    readonly "RosterItemGrant": RosterItemGrant;
    readonly "RosterMemberControllerOverride": RosterMemberControllerOverride;
    readonly "RosterResourceState": RosterResourceState;
    readonly "RosterSpellGrant": RosterSpellGrant;
    readonly "RosterStartingCondition": RosterStartingCondition;
    readonly "RosterStartingDamage": RosterStartingDamage;
    readonly "ContentRef": ContentRef;
    readonly "ItemDefinition": ItemDefinition;
    readonly "OriginRuntimeSupport": OriginRuntimeSupport;
    readonly "CharacterBuildDraft": CharacterBuildDraft;
    readonly "CharacterCreationPlan": CharacterCreationPlan;
    readonly "CharacterLoadoutDraft": CharacterLoadoutDraft;
    readonly "StarterHoldingTemplate": StarterHoldingTemplate;
    readonly "ContentProvenance": ContentProvenance;
    readonly "ContentSource": ContentSource;
    readonly "ContentRecipePreset": ContentRecipePreset;
    readonly "ContentRecipePresetRef": ContentRecipePresetRef;
    readonly "ContentRecipe": ContentRecipe;
    readonly "SpatialEffectDefinition": SpatialEffectDefinition;
    readonly "SpatialEffectTransitionDefinition": SpatialEffectTransitionDefinition;
    readonly "StartingEquipmentPackageDefinition": StartingEquipmentPackageDefinition;
    readonly "StartingEquipmentPackageEntry": StartingEquipmentPackageEntry;
    readonly "DamageComponentResolution": DamageComponentResolution;
    readonly "DamageResolution": DamageResolution;
    readonly "Dice": Dice;
    readonly "DiceRoll": DiceRoll;
    readonly "AbilityCheckD20RollResultEvent": AbilityCheckD20RollResultEvent;
    readonly "AbilityCheckEvent": AbilityCheckEvent;
    readonly "AttackD20RollResultEvent": AttackD20RollResultEvent;
    readonly "D20RollResultEvent": D20RollResultEvent;
    readonly "Damage": Damage;
    readonly "DamageAppliedEvent": DamageAppliedEvent;
    readonly "DamageRollPacket": DamageRollPacket;
    readonly "DamageRollResultEvent": DamageRollResultEvent;
    readonly "DeathEvent": DeathEvent;
    readonly "DeathSaveEvent": DeathSaveEvent;
    readonly "EncounterEndEvent": EncounterEndEvent;
    readonly "EncounterStartEvent": EncounterStartEvent;
    readonly "EngineEvent": EngineEvent;
    readonly "ForcedMovementEvent": ForcedMovementEvent;
    readonly "HealEvent": HealEvent;
    readonly "HealRollResultEvent": HealRollResultEvent;
    readonly "InstantDeathEvent": InstantDeathEvent;
    readonly "LifeStateChangeEvent": LifeStateChangeEvent;
    readonly "Range": Range;
    readonly "ReviveEvent": ReviveEvent;
    readonly "RollModification": RollModification;
    readonly "RoundEndEvent": RoundEndEvent;
    readonly "RoundStartEvent": RoundStartEvent;
    readonly "SavingThrowD20RollResultEvent": SavingThrowD20RollResultEvent;
    readonly "SavingThrowEvent": SavingThrowEvent;
    readonly "SensesUpdateHint": SensesUpdateHint;
    readonly "SensoryUpdateEvent": SensoryUpdateEvent;
    readonly "SkillCheckD20RollResultEvent": SkillCheckD20RollResultEvent;
    readonly "SkillCheckEvent": SkillCheckEvent;
    readonly "SpatialChangeEvent": SpatialChangeEvent;
    readonly "SpatialEffectChangeEvent": SpatialEffectChangeEvent;
    readonly "SpatialEffectInteractionEvent": SpatialEffectInteractionEvent;
    readonly "StepMovementEvent": StepMovementEvent;
    readonly "TakeDamageEvent": TakeDamageEvent;
    readonly "TemporaryHitPointsEvent": TemporaryHitPointsEvent;
    readonly "TileElevationChangeEvent": TileElevationChangeEvent;
    readonly "TraversalConnectorChangeEvent": TraversalConnectorChangeEvent;
    readonly "TurnEndEvent": TurnEndEvent;
    readonly "TurnStartEvent": TurnStartEvent;
    readonly "ItemContentRefSnapshot": ItemContentRefSnapshot;
    readonly "ItemPresentationState": ItemPresentationState;
    readonly "AdvantageModifier": AdvantageModifier;
    readonly "AutoHitModifier": AutoHitModifier;
    readonly "ContextualAdvantageModifier": ContextualAdvantageModifier;
    readonly "ContextualAutoHitModifier": ContextualAutoHitModifier;
    readonly "ContextualCriticalModifier": ContextualCriticalModifier;
    readonly "ContextualDamageTypeModifier": ContextualDamageTypeModifier;
    readonly "ContextualNumericalModifier": ContextualNumericalModifier;
    readonly "ContextualResistanceModifier": ContextualResistanceModifier;
    readonly "ContextualSizeModifier": ContextualSizeModifier;
    readonly "CriticalModifier": CriticalModifier;
    readonly "DamageTypeModifier": DamageTypeModifier;
    readonly "NumericalModifier": NumericalModifier;
    readonly "ResistanceModifier": ResistanceModifier;
    readonly "SizeModifier": SizeModifier;
    readonly "ConePresentationGeometry": ConePresentationGeometry;
    readonly "CubePresentationGeometry": CubePresentationGeometry;
    readonly "CylinderPresentationGeometry": CylinderPresentationGeometry;
    readonly "LinePresentationGeometry": LinePresentationGeometry;
    readonly "SpherePresentationGeometry": SpherePresentationGeometry;
    readonly "SavingThrowContext": SavingThrowContext;
    readonly "SenseMode": SenseMode;
    readonly "ConnectorTraversalDiscovery": ConnectorTraversalDiscovery;
    readonly "TraversalConnector": TraversalConnector;
    readonly "TraversalConnectorCommand": TraversalConnectorCommand;
    readonly "TraversalConnectorDefinition": TraversalConnectorDefinition;
    readonly "TraversalConnectorEndpoint": TraversalConnectorEndpoint;
    readonly "ContextualValue": ContextualValue;
    readonly "ModifiableValue": ModifiableValue;
    readonly "StaticValue": StaticValue;
    readonly "DragonbornBreathWeaponEvent": DragonbornBreathWeaponEvent;
    readonly "CounterspellReactionEvent": CounterspellReactionEvent;
    readonly "PublicConfiguredActionSubject": PublicConfiguredActionSubject;
    readonly "PublicDefinitionSubject": PublicDefinitionSubject;
    readonly "PublicProviderSubject": PublicProviderSubject;
    readonly "PublicSourceItemFact": PublicSourceItemFact;
    readonly "SystemicActionSubject": SystemicActionSubject;
    readonly "ObjectiveDiagnosticsBootstrap": ObjectiveDiagnosticsBootstrap;
    readonly "ObjectiveDiagnosticsSync": ObjectiveDiagnosticsSync;
    readonly "SubjectiveParityMismatch": SubjectiveParityMismatch;
    readonly "SubjectiveRenderParityDiagnosticsResponse": SubjectiveRenderParityDiagnosticsResponse;
    readonly "AIProviderCatalogEntry": AIProviderCatalogEntry;
    readonly "AIProviderCatalogResponse": AIProviderCatalogResponse;
    readonly "AIProviderDeleteResponse": AIProviderDeleteResponse;
    readonly "AIProviderRegistrationRequest": AIProviderRegistrationRequest;
    readonly "APIAvailableActionInfo": APIAvailableActionInfo;
    readonly "APIAvailableActions": APIAvailableActions;
    readonly "APIAvailableHandlerInfo": APIAvailableHandlerInfo;
    readonly "APIEntityHandlersResponse": APIEntityHandlersResponse;
    readonly "APIEquippableDisplacement": APIEquippableDisplacement;
    readonly "APIEquippableEntry": APIEquippableEntry;
    readonly "APIEquippableItems": APIEquippableItems;
    readonly "APIResourcePool": APIResourcePool;
    readonly "APIServerTiming": APIServerTiming;
    readonly "ActionResult": ActionResult;
    readonly "AdvanceEncounterResult": AdvanceEncounterResult;
    readonly "AgentSessionEntityRow": AgentSessionEntityRow;
    readonly "AgentSessionListResponse": AgentSessionListResponse;
    readonly "AgentSessionRow": AgentSessionRow;
    readonly "AoEPreviewResult": AoEPreviewResult;
    readonly "CreateSessionRequest": CreateSessionRequest;
    readonly "CreateSessionResponse": CreateSessionResponse;
    readonly "EquipRequest": EquipRequest;
    readonly "EquipmentMutationResult": EquipmentMutationResult;
    readonly "EventContractSummary": EventContractSummary;
    readonly "ExecuteByIndexRequest": ExecuteByIndexRequest;
    readonly "GameCreationAIPolicyOption": GameCreationAIPolicyOption;
    readonly "GameCreationActivateRequest": GameCreationActivateRequest;
    readonly "GameCreationActivateResponse": GameCreationActivateResponse;
    readonly "GameCreationAuthoredRosterSelection": GameCreationAuthoredRosterSelection;
    readonly "GameCreationCatalogResponse": GameCreationCatalogResponse;
    readonly "GameCreationComposeRequest": GameCreationComposeRequest;
    readonly "GameCreationComposeResponse": GameCreationComposeResponse;
    readonly "GameCreationEntityAssignment": GameCreationEntityAssignment;
    readonly "GameCreationOwnedCharacterControllerOverride": GameCreationOwnedCharacterControllerOverride;
    readonly "GameCreationOwnedCharacterRosterSelection": GameCreationOwnedCharacterRosterSelection;
    readonly "GameCreationPreviewRequest": GameCreationPreviewRequest;
    readonly "GameCreationRosterResult": GameCreationRosterResult;
    readonly "GameCreationRosterSlotSelection": GameCreationRosterSlotSelection;
    readonly "GameCreationSavedRosterSelection": GameCreationSavedRosterSelection;
    readonly "GameCreationStartRequest": GameCreationStartRequest;
    readonly "GameCreationStartResponse": GameCreationStartResponse;
    readonly "JoinGameRequest": JoinGameRequest;
    readonly "JoinGameResponse": JoinGameResponse;
    readonly "MapEditorCatalog": MapEditorCatalog;
    readonly "MapEditorCatalogEntry": MapEditorCatalogEntry;
    readonly "MapEditorConnectorDeleteRequest": MapEditorConnectorDeleteRequest;
    readonly "MapEditorConnectorEnabledRequest": MapEditorConnectorEnabledRequest;
    readonly "MapEditorConnectorMutationResponse": MapEditorConnectorMutationResponse;
    readonly "MapEditorConnectorUpsertRequest": MapEditorConnectorUpsertRequest;
    readonly "MapEditorContentCatalogEntry": MapEditorContentCatalogEntry;
    readonly "MapEditorCreateMapRequest": MapEditorCreateMapRequest;
    readonly "MapEditorGridBounds": MapEditorGridBounds;
    readonly "MapEditorLightCell": MapEditorLightCell;
    readonly "MapEditorLightResponse": MapEditorLightResponse;
    readonly "MapEditorMapSnapshot": MapEditorMapSnapshot;
    readonly "MapEditorObjectDeleteRequest": MapEditorObjectDeleteRequest;
    readonly "MapEditorObjectPlaceRequest": MapEditorObjectPlaceRequest;
    readonly "MapEditorObjectRuntimeState": MapEditorObjectRuntimeState;
    readonly "MapEditorSaveMapRequest": MapEditorSaveMapRequest;
    readonly "MapEditorSavedMapDocument": MapEditorSavedMapDocument;
    readonly "MapEditorSavedMapList": MapEditorSavedMapList;
    readonly "MapEditorSavedMapMetadata": MapEditorSavedMapMetadata;
    readonly "MapEditorSavedObjectPlacement": MapEditorSavedObjectPlacement;
    readonly "MapEditorTilePatch": MapEditorTilePatch;
    readonly "MapEditorTilePatchRequest": MapEditorTilePatchRequest;
    readonly "MapEditorVisibilityCell": MapEditorVisibilityCell;
    readonly "MapEditorVisibilityResponse": MapEditorVisibilityResponse;
    readonly "MapEditorWalkabilityCell": MapEditorWalkabilityCell;
    readonly "MapEditorWalkabilityResponse": MapEditorWalkabilityResponse;
    readonly "PositionPreviewRequest": PositionPreviewRequest;
    readonly "ServerCapabilitiesResponse": ServerCapabilitiesResponse;
    readonly "SessionPingResponse": SessionPingResponse;
    readonly "SimpleActionRequest": SimpleActionRequest;
    readonly "SpellCatalogEntry": SpellCatalogEntry;
    readonly "SpellCatalogMultiTarget": SpellCatalogMultiTarget;
    readonly "SpellCatalogResponse": SpellCatalogResponse;
    readonly "SpellCatalogSavingThrow": SpellCatalogSavingThrow;
    readonly "SpellCatalogVfx": SpellCatalogVfx;
    readonly "StandaloneGameSessionSummary": StandaloneGameSessionSummary;
    readonly "StandaloneGameStatusResponse": StandaloneGameStatusResponse;
    readonly "TakeoverClaimResponse": TakeoverClaimResponse;
    readonly "TakeoverEntityRow": TakeoverEntityRow;
    readonly "TakeoverHeartbeatResponse": TakeoverHeartbeatResponse;
    readonly "TakeoverListResponse": TakeoverListResponse;
    readonly "TakeoverReleaseResponse": TakeoverReleaseResponse;
    readonly "TakeoverRequest": TakeoverRequest;
    readonly "ToggleHandlerRequest": ToggleHandlerRequest;
    readonly "ToggleHandlerResponse": ToggleHandlerResponse;
    readonly "UnequipRequest": UnequipRequest;
    readonly "AdminCharacterAdvancementAwardRequest": AdminCharacterAdvancementAwardRequest;
    readonly "BackgroundCatalogEntry": BackgroundCatalogEntry;
    readonly "CasterContributionPreviewResponse": CasterContributionPreviewResponse;
    readonly "CharacterAdvancementResponse": CharacterAdvancementResponse;
    readonly "CharacterAppearanceCatalog": CharacterAppearanceCatalog;
    readonly "CharacterAppearanceConstraintCatalogEntry": CharacterAppearanceConstraintCatalogEntry;
    readonly "CharacterAppearanceOptionCatalogEntry": CharacterAppearanceOptionCatalogEntry;
    readonly "CharacterAppearanceOptionRebaseChange": CharacterAppearanceOptionRebaseChange;
    readonly "CharacterAppearanceValueCatalogEntry": CharacterAppearanceValueCatalogEntry;
    readonly "CharacterAttachmentSummary": CharacterAttachmentSummary;
    readonly "CharacterBuildPreviewResponse": CharacterBuildPreviewResponse;
    readonly "CharacterBuildValidationIssueResponse": CharacterBuildValidationIssueResponse;
    readonly "CharacterBuildValidationRequest": CharacterBuildValidationRequest;
    readonly "CharacterBuildValidationResponse": CharacterBuildValidationResponse;
    readonly "CharacterBuildVisualPreviewResponse": CharacterBuildVisualPreviewResponse;
    readonly "CharacterContentRebaseIssue": CharacterContentRebaseIssue;
    readonly "CharacterContentRefRebaseChange": CharacterContentRefRebaseChange;
    readonly "CharacterCreationCatalogResponse": CharacterCreationCatalogResponse;
    readonly "CharacterCreationRulesMetadata": CharacterCreationRulesMetadata;
    readonly "CharacterCreationValidationRequest": CharacterCreationValidationRequest;
    readonly "CharacterDefinitionHistoryResponse": CharacterDefinitionHistoryResponse;
    readonly "CharacterDirectoryModel": CharacterDirectoryModel;
    readonly "CharacterEquipOperation": CharacterEquipOperation;
    readonly "CharacterEquipmentMutationRequest": CharacterEquipmentMutationRequest;
    readonly "CharacterGrantProvenanceResponse": CharacterGrantProvenanceResponse;
    readonly "CharacterGrantScheduleEntryResponse": CharacterGrantScheduleEntryResponse;
    readonly "CharacterLevelUpRequest": CharacterLevelUpRequest;
    readonly "CharacterListResponse": CharacterListResponse;
    readonly "CharacterLoadoutMutationRequest": CharacterLoadoutMutationRequest;
    readonly "CharacterMutationExpectation": CharacterMutationExpectation;
    readonly "CharacterOriginChoiceRebaseChange": CharacterOriginChoiceRebaseChange;
    readonly "CharacterPresentationPreferencesResponse": CharacterPresentationPreferencesResponse;
    readonly "CharacterProfileGameSeat": CharacterProfileGameSeat;
    readonly "CharacterProfileResponse": CharacterProfileResponse;
    readonly "CharacterRespecRequest": CharacterRespecRequest;
    readonly "CharacterRespecSeedResponse": CharacterRespecSeedResponse;
    readonly "CharacterRespecSeedSource": CharacterRespecSeedSource;
    readonly "CharacterSnapshotResponse": CharacterSnapshotResponse;
    readonly "CharacterUnequipOperation": CharacterUnequipOperation;
    readonly "ClassCatalogEntry": ClassCatalogEntry;
    readonly "CreateCharacterRequest": CreateCharacterRequest;
    readonly "KnownSpellGrantPreviewResponse": KnownSpellGrantPreviewResponse;
    readonly "OriginInnateSpellGrantPreviewResponse": OriginInnateSpellGrantPreviewResponse;
    readonly "ReplaceSavedEncounterRequest": ReplaceSavedEncounterRequest;
    readonly "ReplaceSavedEncounterRosterRequest": ReplaceSavedEncounterRosterRequest;
    readonly "SaveEncounterRequest": SaveEncounterRequest;
    readonly "SaveEncounterRosterRequest": SaveEncounterRosterRequest;
    readonly "SavedEncounterListResponse": SavedEncounterListResponse;
    readonly "SavedEncounterRosterListResponse": SavedEncounterRosterListResponse;
    readonly "SpeciesCatalogEntry": SpeciesCatalogEntry;
    readonly "SpeciesVariantCatalogEntry": SpeciesVariantCatalogEntry;
    readonly "StandaloneLocalProfileResponse": StandaloneLocalProfileResponse;
    readonly "StartingApparelPackageCatalogEntry": StartingApparelPackageCatalogEntry;
    readonly "StartingEquipmentPackageCatalogEntry": StartingEquipmentPackageCatalogEntry;
    readonly "SubclassCatalogEntry": SubclassCatalogEntry;
    readonly "UpdateCharacterPresentationPreferencesRequest": UpdateCharacterPresentationPreferencesRequest;
    readonly "UpdateCharacterProfileSettingsRequest": UpdateCharacterProfileSettingsRequest;
    readonly "ContentCatalogEntry": ContentCatalogEntry;
    readonly "ContentCatalogResponse": ContentCatalogResponse;
    readonly "ContentManifestResponse": ContentManifestResponse;
    readonly "ContentPackManifestEntry": ContentPackManifestEntry;
    readonly "ContentRecipePresetCatalogEntry": ContentRecipePresetCatalogEntry;
    readonly "SafeContentPresentationCatalogEntry": SafeContentPresentationCatalogEntry;
    readonly "DirectoryStreamHeartbeat": DirectoryStreamHeartbeat;
    readonly "DirectoryStreamSync": DirectoryStreamSync;
    readonly "EvictedPayload": EvictedPayload;
    readonly "GameCreationEncounterVisualPreviewResponse": GameCreationEncounterVisualPreviewResponse;
    readonly "GameCreationMemberVisualPreview": GameCreationMemberVisualPreview;
    readonly "GameCreationRosterVisualPreview": GameCreationRosterVisualPreview;
    readonly "CanonicalCharacterRecord": CanonicalCharacterRecord;
    readonly "CharacterAdvancementAwardRecord": CharacterAdvancementAwardRecord;
    readonly "CharacterDefinitionRecord": CharacterDefinitionRecord;
    readonly "CharacterHoldingsRecord": CharacterHoldingsRecord;
    readonly "CharacterLoadoutRecord": CharacterLoadoutRecord;
    readonly "CharacterRevisionHeads": CharacterRevisionHeads;
    readonly "DirectoryEventRecord": DirectoryEventRecord;
    readonly "FinalSummaryRecord": FinalSummaryRecord;
    readonly "GameRecord": GameRecord;
    readonly "MembershipCapabilities": MembershipCapabilities;
    readonly "MembershipRecord": MembershipRecord;
    readonly "PrincipalRecord": PrincipalRecord;
    readonly "ProfileSettingsRecord": ProfileSettingsRecord;
    readonly "SavedEncounterRecord": SavedEncounterRecord;
    readonly "SavedEncounterRosterRecord": SavedEncounterRosterRecord;
    readonly "AttachHostedGameRequest": AttachHostedGameRequest;
    readonly "AttachHostedGameResponse": AttachHostedGameResponse;
    readonly "CreateAgentGrantRequest": CreateAgentGrantRequest;
    readonly "CreateAgentGrantResponse": CreateAgentGrantResponse;
    readonly "CreateHostedGameRequest": CreateHostedGameRequest;
    readonly "CreateHostedGameResponse": CreateHostedGameResponse;
    readonly "GatewayModel": GatewayModel;
    readonly "GuestPrincipalRequest": GuestPrincipalRequest;
    readonly "GuestPrincipalResponse": GuestPrincipalResponse;
    readonly "HostedGameConnection": HostedGameConnection;
    readonly "ObserveHostedGameRequest": ObserveHostedGameRequest;
    readonly "ObserveHostedGameResponse": ObserveHostedGameResponse;
    readonly "PlayerIdentityRequest": PlayerIdentityRequest;
    readonly "PlayerIdentityResponse": PlayerIdentityResponse;
    readonly "ReconnectHostedGameRequest": ReconnectHostedGameRequest;
    readonly "ReconnectHostedGameResponse": ReconnectHostedGameResponse;
    readonly "StopHostedGameRequest": StopHostedGameRequest;
    readonly "StopHostedGameResponse": StopHostedGameResponse;
    readonly "GameHistoryListResponse": GameHistoryListResponse;
    readonly "WorkerReplayCapture": WorkerReplayCapture;
    readonly "WorkerSummaryEvidence": WorkerSummaryEvidence;
    readonly "ObjectiveReplayBundle": ObjectiveReplayBundle;
    readonly "ObjectiveReplaySeed": ObjectiveReplaySeed;
    readonly "SubjectivePlayerReplayBundle": SubjectivePlayerReplayBundle;
    readonly "SubjectiveReplaySegment": SubjectiveReplaySegment;
    readonly "ActionPresentationCue": ActionPresentationCue;
    readonly "AttackPresentationCue": AttackPresentationCue;
    readonly "ConditionPresentationCue": ConditionPresentationCue;
    readonly "ConeAreaGeometry": ConeAreaGeometry;
    readonly "ConnectorPresentationIdentity": ConnectorPresentationIdentity;
    readonly "ConnectorSetReplacePatch": ConnectorSetReplacePatch;
    readonly "ControlledEquipmentReplacePatch": ControlledEquipmentReplacePatch;
    readonly "CounterspellAutomaticSuccess": CounterspellAutomaticSuccess;
    readonly "CounterspellCheckFailure": CounterspellCheckFailure;
    readonly "CounterspellCheckSuccess": CounterspellCheckSuccess;
    readonly "CounterspellPresentationCue": CounterspellPresentationCue;
    readonly "CubeAreaGeometry": CubeAreaGeometry;
    readonly "CylinderAreaGeometry": CylinderAreaGeometry;
    readonly "DamagePresentationCue": DamagePresentationCue;
    readonly "DoorPresentationCue": DoorPresentationCue;
    readonly "DoorStatePatch": DoorStatePatch;
    readonly "EffectiveLightCell": EffectiveLightCell;
    readonly "EncounterPresentationCue": EncounterPresentationCue;
    readonly "EncounterReplacePatch": EncounterReplacePatch;
    readonly "EncounterTerminalPresentationFact": EncounterTerminalPresentationFact;
    readonly "EntityRemovePatch": EntityRemovePatch;
    readonly "EntityUpsertPatch": EntityUpsertPatch;
    readonly "EntityVisualLoadout": EntityVisualLoadout;
    readonly "EquipmentPresentationCue": EquipmentPresentationCue;
    readonly "FloorObjectRemovePatch": FloorObjectRemovePatch;
    readonly "FloorObjectUpsertPatch": FloorObjectUpsertPatch;
    readonly "ForcedMovementPresentationCue": ForcedMovementPresentationCue;
    readonly "HealPresentationCue": HealPresentationCue;
    readonly "ItemActionPresentationCue": ItemActionPresentationCue;
    readonly "LifeStatePresentationCue": LifeStatePresentationCue;
    readonly "LifecycleCausePresentationCue": LifecycleCausePresentationCue;
    readonly "LightPresentationCue": LightPresentationCue;
    readonly "LineAreaGeometry": LineAreaGeometry;
    readonly "LocomotionAnchor": LocomotionAnchor;
    readonly "MovementPresentationCue": MovementPresentationCue;
    readonly "ObserverVisibilityRemovePatch": ObserverVisibilityRemovePatch;
    readonly "ObserverVisibilityReplacePatch": ObserverVisibilityReplacePatch;
    readonly "PlayerReplicationProtocolIdentity": PlayerReplicationProtocolIdentity;
    readonly "PlayerReplicationWatermarks": PlayerReplicationWatermarks;
    readonly "ShovePresentationCue": ShovePresentationCue;
    readonly "SpatialEffectPresentationCue": SpatialEffectPresentationCue;
    readonly "SpellPresentationCue": SpellPresentationCue;
    readonly "SpellTargetPresentation": SpellTargetPresentation;
    readonly "SphereAreaGeometry": SphereAreaGeometry;
    readonly "SubjectiveBootstrapDeferred": SubjectiveBootstrapDeferred;
    readonly "SubjectiveCombatLogDelivery": SubjectiveCombatLogDelivery;
    readonly "SubjectiveCombatLogFrame": SubjectiveCombatLogFrame;
    readonly "SubjectiveCombatLogFramesResponse": SubjectiveCombatLogFramesResponse;
    readonly "SubjectiveCombatant": SubjectiveCombatant;
    readonly "SubjectiveEncounter": SubjectiveEncounter;
    readonly "SubjectiveFloorObject": SubjectiveFloorObject;
    readonly "SubjectiveFrameDelivery": SubjectiveFrameDelivery;
    readonly "SubjectiveFramesResponse": SubjectiveFramesResponse;
    readonly "SubjectiveGameState": SubjectiveGameState;
    readonly "SubjectivePerspective": SubjectivePerspective;
    readonly "SubjectiveReplicatedWorld": SubjectiveReplicatedWorld;
    readonly "SubjectiveReplicationBootstrap": SubjectiveReplicationBootstrap;
    readonly "SubjectiveReplicationFrame": SubjectiveReplicationFrame;
    readonly "SubjectiveSyncDelivery": SubjectiveSyncDelivery;
    readonly "TileUpsertPatch": TileUpsertPatch;
    readonly "VisualEquipmentLayer": VisualEquipmentLayer;
    readonly "VisualLoadoutReplacePatch": VisualLoadoutReplacePatch;
    readonly "ObjectiveReplicatedWorld": ObjectiveReplicatedWorld;
    readonly "TimelineCombatLogFrame": TimelineCombatLogFrame;
    readonly "TimelineCombatLogFramesResponse": TimelineCombatLogFramesResponse;
    readonly "GameEventFrame": GameEventFrame;
    readonly "GameEventFramesResponse": GameEventFramesResponse;
    readonly "ObjectiveCombatLogFrame": ObjectiveCombatLogFrame;
    readonly "ObjectiveCombatLogFramesResponse": ObjectiveCombatLogFramesResponse;
    readonly "TimelineProtocolIdentity": TimelineProtocolIdentity;
    readonly "WireEvent": WireEvent;
    readonly "APIAppearance": APIAppearance;
    readonly "APICombatant": APICombatant;
    readonly "APIConditionSummary": APIConditionSummary;
    readonly "APIContentRefSnapshot": APIContentRefSnapshot;
    readonly "APIDirectionalBlockMap": APIDirectionalBlockMap;
    readonly "APIEncounter": APIEncounter;
    readonly "APIEntitySummary": APIEntitySummary;
    readonly "APIEntityVisibility": APIEntityVisibility;
    readonly "APIEquipmentOverview": APIEquipmentOverview;
    readonly "APIEquipmentSlot": APIEquipmentSlot;
    readonly "APIFloorObject": APIFloorObject;
    readonly "APIGameState": APIGameState;
    readonly "APIGrid": APIGrid;
    readonly "APIItemRuntimeRecipeRefSnapshot": APIItemRuntimeRecipeRefSnapshot;
    readonly "APIItemSummary": APIItemSummary;
    readonly "APIRecipePresetRefSnapshot": APIRecipePresetRefSnapshot;
    readonly "APISpatialEffectPresentation": APISpatialEffectPresentation;
    readonly "APISpatialEffectSummary": APISpatialEffectSummary;
    readonly "APITile": APITile;
    readonly "APITraversalConnector": APITraversalConnector;
    readonly "APITraversalConnectorEndpoint": APITraversalConnectorEndpoint;
    readonly "APIVisibilityResponse": APIVisibilityResponse;
    readonly "DirectionalStructuralEdgeMap": DirectionalStructuralEdgeMap;
    readonly "SafeContentPresentationRef": SafeContentPresentationRef;
    readonly "StructuralEdgeAppearance": StructuralEdgeAppearance;
}
export type SdkModelName = keyof SdkModelByName;
export interface SdkAliasByName {
    readonly "ActionBindingSubject": ActionBindingSubject;
    readonly "SubjectiveWorldPatch": SubjectiveWorldPatch;
    readonly "SubjectivePresentationCue": SubjectivePresentationCue;
    readonly "SubjectiveStreamDelivery": SubjectiveStreamDelivery;
    readonly "SubjectiveReplayDelivery": SubjectiveReplayDelivery;
}
export type SdkAliasName = keyof SdkAliasByName;
export declare const SDK_MODEL_DESCRIPTORS: Readonly<Record<string, ContractModelDescriptor>>;
export declare const SDK_ENUM_DESCRIPTORS: Readonly<Record<string, ContractEnumDescriptor>>;
export declare const SDK_ALIAS_DESCRIPTORS: Readonly<Record<SdkAliasName, ContractDescriptor>>;
export declare const SDK_MODEL_PATHS_BY_NAME: Readonly<Record<SdkModelName, string>>;
export declare const SDK_EVENT_CLASSES: Readonly<Record<string, {
    readonly model: string;
    readonly typescript: string;
    readonly event_types: ReadonlyArray<string>;
}>>;
//# sourceMappingURL=contracts.generated.d.ts.map