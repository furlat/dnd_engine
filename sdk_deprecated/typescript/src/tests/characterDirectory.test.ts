import assert from "node:assert/strict";
import test from "node:test";

import {
  GameDirectoryClient,
  type DirectoryPrincipalCredential,
} from "../directoryClient.js";
import type {
  AdminCharacterAdvancementAwardRequest,
  CharacterBuildValidationRequest,
  CharacterCreationValidationRequest,
  CharacterLevelUpRequest,
  CharacterLoadoutMutationRequest,
  CharacterRespecRequest,
  CreateCharacterRequest,
  EncounterRecipe,
  EncounterRosterRecipe,
  ReplaceSavedEncounterRequest,
  ReplaceSavedEncounterRosterRequest,
  SaveEncounterRequest,
  SaveEncounterRosterRequest,
  UpdateCharacterPresentationPreferencesRequest,
  UpdateCharacterProfileSettingsRequest,
} from "../generated/contracts.generated.js";
import { ContractValidationError } from "../validation.js";

interface CapturedRequest {
  readonly url: string;
  readonly method: string;
  readonly principalId: string | null;
  readonly principalCapability: string | null;
  readonly accept: string | null;
  readonly contentType: string | null;
  readonly body: unknown;
}

const credential: DirectoryPrincipalCredential = {
  principalId: "00000000-0000-0000-0000-000000000001",
  principalCapability: "directory-secret",
};

const characterId = "character/id with space";
const digest = "a".repeat(64);
const creatureRef = {
  pack_id: "core.rules",
  definition_kind: "creature",
  content_id: "creature.player_body",
  content_version: 1,
  definition_contract_hash: digest,
} as const;
const speciesRef = {
  ...creatureRef,
  definition_kind: "species",
  content_id: "species.human",
} as const;
const backgroundRef = {
  ...creatureRef,
  definition_kind: "background",
  content_id: "background.adventurer",
} as const;
const classRef = {
  ...creatureRef,
  definition_kind: "class",
  content_id: "class.fighter",
} as const;
const buildValidationRequest = {
  build: {
    body_recipe: {
      ref: creatureRef,
      parameters: {},
      recipe_digest: digest,
    },
    species_ref: speciesRef,
    species_variant_ref: null,
    background_ref: backgroundRef,
    immutable_origin_choices: [],
    appearance: { options: [] },
    base_ability_scores: {
      strength: 15,
      dexterity: 14,
      constitution: 13,
      intelligence: 10,
      wisdom: 12,
      charisma: 8,
    },
    flexible_ability_bonuses: {
      plus_two: "strength",
      plus_one: "constitution",
    },
    class_levels: [{
      class_level_id: { value: "level.one" },
      character_level: 1,
      class_ref: classRef,
      resulting_class_level: 1,
      subclass_ref: null,
      choices: [],
    }],
    premade_id: null,
  },
  loadout: {
    prepared_spells: [],
    feature_toggles: [],
  },
  expected_content_set_digest: digest,
  expected_ruleset_digest: digest,
} satisfies CharacterBuildValidationRequest;
const creationValidationRequest = {
  ...buildValidationRequest,
  creation_plan_id: "creation_plan.blank_custom",
  creation_plan_digest: digest,
} satisfies CharacterCreationValidationRequest;
const createCharacterRequest = {
  ...creationValidationRequest,
  display_name: "Canonical Hero",
  idempotency_key: "00000000-0000-0000-0000-000000000010",
} satisfies CreateCharacterRequest;
const mutationExpectation = {
  expected_row_version: 1,
  expected_heads: {
    definition_revision: 1,
    definition_digest: digest,
    holdings_revision: 1,
    holdings_digest: digest,
    loadout_revision: 1,
    loadout_digest: digest,
  },
};
const levelUpRequest = {
  ...buildValidationRequest,
  ...mutationExpectation,
  idempotency_key: "00000000-0000-0000-0000-000000000011",
} satisfies CharacterLevelUpRequest;
const respecRequest = {
  ...buildValidationRequest,
  ...mutationExpectation,
  idempotency_key: "00000000-0000-0000-0000-000000000012",
} satisfies CharacterRespecRequest;
const loadoutRequest = {
  ...mutationExpectation,
  idempotency_key: "00000000-0000-0000-0000-000000000013",
  loadout: buildValidationRequest.loadout,
  expected_content_set_digest: digest,
  expected_ruleset_digest: digest,
} satisfies CharacterLoadoutMutationRequest;
const settingsRequest = {
  expected_settings_version: 1,
  permissive_multiclass_prerequisites: true,
  multiclass_slot_rounding_policy: "srd_5_2_round_up",
  allow_respec: true,
  spell_preparation_policy: "long_rest",
} satisfies UpdateCharacterProfileSettingsRequest;
const adminAwardRequest = {
  idempotency_key: "00000000-0000-0000-0000-000000000014",
  expected_earned_character_level: 1,
  level_delta: 1,
} satisfies AdminCharacterAdvancementAwardRequest;
const presentationPreferencesRequest = {
  expected_revision: 0,
  preferences: {
    neuroclient: {
      portrait_identity: "gallery.hero.ember.v2",
      experimental: {
        layer_opacity: 0.75,
      },
    },
  },
} satisfies UpdateCharacterPresentationPreferencesRequest;
const savedRosterRecipe = {
  roster_id: "roster.saved/party",
  recipe_digest: digest,
} as unknown as EncounterRosterRecipe;
const savedEncounterRecipe = {
  encounter_id: "encounter.saved/duel",
  recipe_digest: digest,
} as unknown as EncounterRecipe;
const savedRosterId = "saved.roster/party";
const savedEncounterId = "saved.encounter/duel";
const saveRosterRequest = {
  title: "Saved Party",
  recipe: savedRosterRecipe,
} satisfies SaveEncounterRosterRequest;
const replaceRosterRequest = {
  title: "Renamed Party",
  recipe: savedRosterRecipe,
  expected_revision: 1,
  expected_recipe_digest: digest,
} satisfies ReplaceSavedEncounterRosterRequest;
const saveEncounterRequest = {
  title: "Saved Duel",
  recipe: savedEncounterRecipe,
} satisfies SaveEncounterRequest;
const replaceEncounterRequest = {
  title: "Renamed Duel",
  recipe: savedEncounterRecipe,
  expected_revision: 1,
  expected_recipe_digest: digest,
} satisfies ReplaceSavedEncounterRequest;

test("character directory client uses the one exact unversioned route family", async () => {
  const requests: CapturedRequest[] = [];
  const fetchImplementation: typeof fetch = async (input, init) => {
    const headers = new Headers(init?.headers);
    const body = typeof init?.body === "string"
      ? JSON.parse(init.body)
      : null;
    requests.push({
      url: String(input),
      method: init?.method ?? "GET",
      principalId: headers.get("x-dnd-principal-id"),
      principalCapability: headers.get("x-dnd-principal-capability"),
      accept: headers.get("accept"),
      contentType: headers.get("content-type"),
      body,
    });
    return new Response("{}", {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const client = new GameDirectoryClient("/api/", { fetchImplementation });

  const requestsThatDecodeAfterFetch = [
    () => client.getCharacterCreationCatalog(),
    () => client.getStandaloneLocalProfile(),
    () => client.getCharacterProfile(credential),
    () => client.updateCharacterProfileSettings(credential, settingsRequest),
    () => client.validateCharacterBuild(credential, creationValidationRequest),
    () => client.previewCharacterBuild(credential, creationValidationRequest),
    () => client.createCharacter(credential, createCharacterRequest),
    () => client.listCharacters(credential),
    () => client.createSavedEncounterRoster(credential, saveRosterRequest),
    () => client.listSavedEncounterRosters(credential),
    () => client.getSavedEncounterRoster(
      credential,
      savedRosterId,
    ),
    () => client.replaceSavedEncounterRoster(
      credential,
      savedRosterId,
      replaceRosterRequest,
    ),
    () => client.deleteSavedEncounterRoster(
      credential,
      savedRosterId,
      1,
      digest,
    ),
    () => client.createSavedEncounter(credential, saveEncounterRequest),
    () => client.listSavedEncounters(credential),
    () => client.getSavedEncounter(
      credential,
      savedEncounterId,
    ),
    () => client.replaceSavedEncounter(
      credential,
      savedEncounterId,
      replaceEncounterRequest,
    ),
    () => client.deleteSavedEncounter(
      credential,
      savedEncounterId,
      1,
      digest,
    ),
    () => client.getCharacter(credential, characterId),
    () => client.getCharacterDefinition(credential, characterId),
    () => client.getCharacterDefinitionHistory(credential, characterId),
    () => client.getCharacterHoldings(credential, characterId),
    () => client.getCharacterLoadout(credential, characterId),
    () => client.getCharacterPresentationPreferences(
      credential,
      characterId,
    ),
    () => client.updateCharacterPresentationPreferences(
      credential,
      characterId,
      presentationPreferencesRequest,
    ),
    () => client.getCharacterAdvancement(credential, characterId),
    () => client.grantAdminCharacterAdvancementAward(
      credential,
      characterId,
      adminAwardRequest,
    ),
    () => client.validateCharacterLevelUp(
      credential,
      characterId,
      levelUpRequest,
    ),
    () => client.levelUpCharacter(credential, characterId, levelUpRequest),
    () => client.validateCharacterRespec(
      credential,
      characterId,
      respecRequest,
    ),
    () => client.getCharacterRespecSeed(credential, characterId),
    () => client.respecCharacter(credential, characterId, respecRequest),
    () => client.validateCharacterLoadout(
      credential,
      characterId,
      loadoutRequest,
    ),
    () => client.updateCharacterLoadout(
      credential,
      characterId,
      loadoutRequest,
    ),
  ];
  for (const request of requestsThatDecodeAfterFetch) {
    await assert.rejects(request, ContractValidationError);
  }

  const encodedId = "character%2Fid%20with%20space";
  const encodedRosterId = "saved.roster%2Fparty";
  const encodedEncounterId = "saved.encounter%2Fduel";
  const privateRequest = (
    url: string,
    method = "GET",
    body: unknown = null,
  ): CapturedRequest => ({
    url,
    method,
    principalId: credential.principalId,
    principalCapability: credential.principalCapability,
    accept: "application/json",
    contentType: body === null ? null : "application/json",
    body,
  });
  assert.deepEqual(requests, [
    {
      url: "/api/character-creation/catalog",
      method: "GET",
      principalId: null,
      principalCapability: null,
      accept: "application/json",
      contentType: null,
      body: null,
    },
    {
      url: "/api/directory/local-profile",
      method: "GET",
      principalId: null,
      principalCapability: null,
      accept: "application/json",
      contentType: null,
      body: null,
    },
    privateRequest("/api/directory/players/me"),
    privateRequest(
      "/api/directory/players/me/settings",
      "PUT",
      settingsRequest,
    ),
    privateRequest(
      "/api/character-builds/validate",
      "POST",
      creationValidationRequest,
    ),
    privateRequest(
      "/api/character-builds/visual-preview",
      "POST",
      creationValidationRequest,
    ),
    privateRequest(
      "/api/directory/characters",
      "POST",
      createCharacterRequest,
    ),
    privateRequest("/api/directory/characters"),
    privateRequest(
      "/api/directory/encounter-rosters",
      "POST",
      saveRosterRequest,
    ),
    privateRequest("/api/directory/encounter-rosters"),
    privateRequest(
      `/api/directory/encounter-rosters/${encodedRosterId}`,
    ),
    privateRequest(
      `/api/directory/encounter-rosters/${encodedRosterId}`,
      "PUT",
      replaceRosterRequest,
    ),
    privateRequest(
      `/api/directory/encounter-rosters/${encodedRosterId}?expected_revision=1&expected_recipe_digest=${digest}`,
      "DELETE",
    ),
    privateRequest(
      "/api/directory/encounters",
      "POST",
      saveEncounterRequest,
    ),
    privateRequest("/api/directory/encounters"),
    privateRequest(`/api/directory/encounters/${encodedEncounterId}`),
    privateRequest(
      `/api/directory/encounters/${encodedEncounterId}`,
      "PUT",
      replaceEncounterRequest,
    ),
    privateRequest(
      `/api/directory/encounters/${encodedEncounterId}?expected_revision=1&expected_recipe_digest=${digest}`,
      "DELETE",
    ),
    privateRequest(`/api/directory/characters/${encodedId}`),
    privateRequest(`/api/directory/characters/${encodedId}/definition`),
    privateRequest(`/api/directory/characters/${encodedId}/definitions`),
    privateRequest(`/api/directory/characters/${encodedId}/holdings`),
    privateRequest(`/api/directory/characters/${encodedId}/loadout`),
    privateRequest(
      `/api/directory/characters/${encodedId}/presentation-preferences`,
    ),
    privateRequest(
      `/api/directory/characters/${encodedId}/presentation-preferences`,
      "PUT",
      presentationPreferencesRequest,
    ),
    privateRequest(`/api/directory/characters/${encodedId}/advancement`),
    privateRequest(
      `/api/admin/characters/${encodedId}/advancement-awards`,
      "POST",
      adminAwardRequest,
    ),
    privateRequest(
      `/api/directory/characters/${encodedId}/level-up/validate`,
      "POST",
      levelUpRequest,
    ),
    privateRequest(
      `/api/directory/characters/${encodedId}/level-up`,
      "POST",
      levelUpRequest,
    ),
    privateRequest(
      `/api/directory/characters/${encodedId}/respec/validate`,
      "POST",
      respecRequest,
    ),
    privateRequest(
      `/api/directory/characters/${encodedId}/respec/seed`,
    ),
    privateRequest(
      `/api/directory/characters/${encodedId}/respec`,
      "POST",
      respecRequest,
    ),
    privateRequest(
      `/api/directory/characters/${encodedId}/loadout/validate`,
      "POST",
      loadoutRequest,
    ),
    privateRequest(
      `/api/directory/characters/${encodedId}/loadout`,
      "PUT",
      loadoutRequest,
    ),
  ]);
});

test("character directory response decoding is strict", async () => {
  const fetchImplementation: typeof fetch = async () => new Response(
    JSON.stringify({
      characters: [],
      retired_compatibility_field: true,
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
  const client = new GameDirectoryClient("/api", { fetchImplementation });

  await assert.rejects(
    () => client.listCharacters(credential),
    (error: unknown) => {
      assert.ok(error instanceof ContractValidationError);
      assert.match(error.message, /retired_compatibility_field/);
      return true;
    },
  );
});

test("character presentation preferences preserve flexible JSON inside a strict envelope", async () => {
  const payload = {
    schema_version: 1,
    character_id: "00000000-0000-0000-0000-000000000020",
    owner_principal_id: credential.principalId,
    revision: 3,
    preferences: {
      neuroclient: {
        portrait_identity: "gallery.hero.ember.v2",
        experimental: {
          palette: ["#112233", "#aabbcc"],
          layer_opacity: 0.75,
          enabled_layers: ["dragon_wings", "aura"],
        },
      },
    },
    preferences_digest: digest,
    updated_at: "2026-07-28T20:00:00.000000Z",
  } as const;
  const fetchImplementation: typeof fetch = async () => new Response(
    JSON.stringify(payload),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
  const client = new GameDirectoryClient("/api", { fetchImplementation });

  assert.deepEqual(
    await client.getCharacterPresentationPreferences(
      credential,
      payload.character_id,
    ),
    payload,
  );
});

test("creator catalog decodes only editable schema-7 creation plans", async () => {
  const expectedPremades = [
    ["hero.barbarian_l5_berserker_torch", "Berserker"],
    ["hero.fighter_2_sorcerer_3_spellblade", "Draconic Spellblade"],
    ["hero.fighter_l5_shield_torch", "Shield Fighter"],
    ["hero.sorcerer_l5_standard_torch", "Draconic Sorcerer"],
  ] as const;
  const payload = {
    schema_version: 7,
    content_set_digest: digest,
    rules: {
      schema_version: 2,
      rules_baseline: "srd_5_1_with_selected_bg3_creation_rules",
      initial_custom_character_level: 1,
      character_level_cap: 20,
      point_buy_budget: 27,
      minimum_ability_score: 8,
      maximum_pre_bonus_ability_score: 15,
      ordinary_ability_score_cap: 20,
      flexible_plus_two: 2,
      flexible_plus_one: 1,
      flexible_bonuses_must_target_distinct_abilities: true,
      hit_points_after_character_level_one: "fixed_class_average",
      supported_multiclass_slot_rounding_policies: [
        "srd_5_2_round_up",
        "srd_5_1_round_down",
      ],
      default_multiclass_slot_rounding_policy: "srd_5_2_round_up",
      default_permissive_multiclass_prerequisites: true,
    },
    appearance_catalog: {
      schema_version: 4,
      default_selection: {
        options: [
          {
            option_id: "appearance.beard",
            value_id: "appearance.beard.absent",
          },
          {
            option_id: "appearance.beard_tint",
            value_id: "appearance.beard_tint.follow_hair",
          },
          {
            option_id: "appearance.body",
            value_id: "appearance.body.humanoid",
          },
          {
            option_id: "appearance.build",
            value_id: "appearance.build.average",
          },
          {
            option_id: "appearance.hair_tint",
            value_id: "appearance.color.auburn",
          },
          {
            option_id: "appearance.head",
            value_id: "appearance.head.hair_09",
          },
          {
            option_id: "appearance.skin_tint",
            value_id: "appearance.color.light_tan",
          },
          {
            option_id: "appearance.stature",
            value_id: "appearance.stature.average",
          },
        ],
      },
      options: [
        {
          option_id: "appearance.beard",
          display_name: "Beard",
          control_kind: "choice",
          default_value_id: "appearance.beard.absent",
          values: [
            {
              value_id: "appearance.beard.absent",
              display_name: "No Beard",
              tint_rgb: null,
              tint_source_option_id: null,
              body_category: null,
              head_category: null,
              visual_scale_multiplier: null,
              visual_scale_x_multiplier: null,
            },
            {
              value_id: "appearance.beard.present",
              display_name: "Beard",
              tint_rgb: null,
              tint_source_option_id: null,
              body_category: null,
              head_category: null,
              visual_scale_multiplier: null,
              visual_scale_x_multiplier: null,
            },
          ],
        },
        {
          option_id: "appearance.beard_tint",
          display_name: "Beard Color",
          control_kind: "color",
          default_value_id: "appearance.beard_tint.follow_hair",
          values: [{
            value_id: "appearance.beard_tint.follow_hair",
            display_name: "Match Hair",
            tint_rgb: null,
            tint_source_option_id: "appearance.hair_tint",
            body_category: null,
            head_category: null,
            visual_scale_multiplier: null,
            visual_scale_x_multiplier: null,
          }],
        },
        {
          option_id: "appearance.body",
          display_name: "Body",
          control_kind: "choice",
          default_value_id: "appearance.body.humanoid",
          values: [{
            value_id: "appearance.body.humanoid",
            display_name: "Humanoid",
            tint_rgb: null,
            tint_source_option_id: null,
            body_category: "NakedBody",
            head_category: null,
            visual_scale_multiplier: null,
            visual_scale_x_multiplier: null,
          }],
        },
        {
          option_id: "appearance.build",
          display_name: "Build",
          control_kind: "choice",
          default_value_id: "appearance.build.average",
          values: [{
            value_id: "appearance.build.average",
            display_name: "Average",
            tint_rgb: null,
            tint_source_option_id: null,
            body_category: null,
            head_category: null,
            visual_scale_multiplier: null,
            visual_scale_x_multiplier: 1,
          }],
        },
        {
          option_id: "appearance.hair_tint",
          display_name: "Hair Color",
          control_kind: "color",
          default_value_id: "appearance.color.auburn",
          values: [{
            value_id: "appearance.color.auburn",
            display_name: "Auburn",
            tint_rgb: 0x993F00,
            tint_source_option_id: null,
            body_category: null,
            head_category: null,
            visual_scale_multiplier: null,
            visual_scale_x_multiplier: null,
          }],
        },
        {
          option_id: "appearance.head",
          display_name: "Hair",
          control_kind: "choice",
          default_value_id: "appearance.head.hair_09",
          values: [{
            value_id: "appearance.head.hair_09",
            display_name: "Hair 09",
            tint_rgb: null,
            tint_source_option_id: null,
            body_category: null,
            head_category: "Head9",
            visual_scale_multiplier: null,
            visual_scale_x_multiplier: null,
          }],
        },
        {
          option_id: "appearance.skin_tint",
          display_name: "Skin Color",
          control_kind: "color",
          default_value_id: "appearance.color.light_tan",
          values: [{
            value_id: "appearance.color.light_tan",
            display_name: "Light Tan",
            tint_rgb: 0xE6BC98,
            tint_source_option_id: null,
            body_category: null,
            head_category: null,
            visual_scale_multiplier: null,
            visual_scale_x_multiplier: null,
          }],
        },
        {
          option_id: "appearance.stature",
          display_name: "Stature",
          control_kind: "choice",
          default_value_id: "appearance.stature.average",
          values: [{
            value_id: "appearance.stature.average",
            display_name: "Average",
            tint_rgb: null,
            tint_source_option_id: null,
            body_category: null,
            head_category: null,
            visual_scale_multiplier: 1,
            visual_scale_x_multiplier: null,
          }],
        },
      ],
      constraints: [],
    },
    body_recipes: [],
    body_recipe_presets: [],
    species: [],
    species_variants: [],
    backgrounds: [],
    classes: [],
    subclasses: [],
    creation_plans: [
      {
        schema_version: 1,
        plan_id: "creation_plan.blank_custom",
        plan_kind: "blank_custom",
        display_name: "Blank Custom",
        build: buildValidationRequest.build,
        loadout: buildValidationRequest.loadout,
        character_level_entitlement: 1,
        supplemental_holdings: [],
        source_premade_id: null,
        plan_digest: digest,
      },
      ...expectedPremades.map(([premadeId, displayName]) => ({
        schema_version: 1,
        plan_id: `creation_plan.premade.${premadeId}`,
        plan_kind: "premade_template",
        display_name: displayName,
        build: {
          ...buildValidationRequest.build,
          premade_id: premadeId,
        },
        loadout: buildValidationRequest.loadout,
        character_level_entitlement: 1,
        supplemental_holdings: [],
        source_premade_id: premadeId,
        plan_digest: digest,
      })),
    ],
    starting_equipment_packages: [],
    starting_apparel_requirement: {
      choice_id: "character.creation.starting_apparel",
      choice_kind: "starting_apparel_package",
      minimum_selections: 1,
      maximum_selections: 1,
      allowed_refs: [],
      allowed_proficiency_subjects: [],
    },
    starting_apparel_packages: [],
  };
  const client = new GameDirectoryClient("/api", {
    fetchImplementation: async () => new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  });

  const catalog = await client.getCharacterCreationCatalog();
  const premadePlans = catalog.creation_plans.filter(
    (row) => row.plan_kind === "premade_template",
  );

  assert.deepEqual(
    premadePlans.map((row) => [row.source_premade_id, row.display_name]),
    expectedPremades,
  );
  assert.equal(
    premadePlans.find(
      (row) => (
        row.source_premade_id
        === "hero.fighter_2_sorcerer_3_spellblade"
      ),
    )?.build.premade_id,
    "hero.fighter_2_sorcerer_3_spellblade",
  );
  assert.ok(
    premadePlans.every(
      (row) => row.loadout.prepared_spells.length === 0,
    ),
  );
  assert.equal(catalog.creation_plans[0]?.plan_id, "creation_plan.blank_custom");
  assert.equal(catalog.rules.initial_custom_character_level, 1);
  assert.deepEqual(
    catalog.appearance_catalog.options.map((option) => option.option_id),
    catalog.appearance_catalog.default_selection.options.map(
      (selection) => selection.option_id,
    ),
  );
  assert.deepEqual(catalog.appearance_catalog.constraints, []);
  assert.equal(
    catalog.appearance_catalog.options.find(
      (option) => option.option_id === "appearance.beard_tint",
    )?.values[0]?.tint_source_option_id,
    "appearance.hair_tint",
  );
});

test("character list decoding accepts only the canonical closed response", async () => {
  const fetchImplementation: typeof fetch = async () => new Response(
    JSON.stringify({ characters: [] }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
  const client = new GameDirectoryClient("/api", { fetchImplementation });

  const result = await client.listCharacters(credential);

  assert.deepEqual(result, { characters: [] });
});
