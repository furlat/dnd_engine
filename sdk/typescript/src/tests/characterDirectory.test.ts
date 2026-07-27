import assert from "node:assert/strict";
import test from "node:test";

import {
  GameDirectoryClient,
  type DirectoryPrincipalCredential,
} from "../directoryClient.js";
import type {
  AdminCharacterAdvancementAwardRequest,
  CharacterBuildValidationRequest,
  CharacterLevelUpRequest,
  CharacterLoadoutMutationRequest,
  CharacterRespecRequest,
  CreateCharacterRequest,
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
const createCharacterRequest = {
  ...buildValidationRequest,
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
    () => client.validateCharacterBuild(credential, buildValidationRequest),
    () => client.createCharacter(credential, createCharacterRequest),
    () => client.listCharacters(credential),
    () => client.getCharacter(credential, characterId),
    () => client.getCharacterDefinition(credential, characterId),
    () => client.getCharacterDefinitionHistory(credential, characterId),
    () => client.getCharacterHoldings(credential, characterId),
    () => client.getCharacterLoadout(credential, characterId),
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
      buildValidationRequest,
    ),
    privateRequest(
      "/api/directory/characters",
      "POST",
      createCharacterRequest,
    ),
    privateRequest("/api/directory/characters"),
    privateRequest(`/api/directory/characters/${encodedId}`),
    privateRequest(`/api/directory/characters/${encodedId}/definition`),
    privateRequest(`/api/directory/characters/${encodedId}/definitions`),
    privateRequest(`/api/directory/characters/${encodedId}/holdings`),
    privateRequest(`/api/directory/characters/${encodedId}/loadout`),
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

test("creator catalog decodes exact schema-2 premade build rows", async () => {
  const expectedPremades = [
    ["hero.barbarian_l5_berserker_torch", "Berserker"],
    ["hero.fighter_2_sorcerer_3_spellblade", "Draconic Spellblade"],
    ["hero.fighter_l5_shield_torch", "Shield Fighter"],
    ["hero.sorcerer_l5_standard_torch", "Draconic Sorcerer"],
  ] as const;
  const payload = {
    schema_version: 1,
    content_set_digest: digest,
    rules: {
      schema_version: 1,
      rules_baseline: "srd_5_1_with_selected_bg3_creation_rules",
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
    body_recipes: [],
    body_recipe_presets: [],
    species: [],
    species_variants: [],
    backgrounds: [],
    classes: [],
    subclasses: [],
    premades: expectedPremades.map(([premadeId, displayName]) => ({
      schema_version: 2,
      premade_id: premadeId,
      display_name: displayName,
      build: {
        ...buildValidationRequest.build,
        premade_id: premadeId,
      },
      loadout: buildValidationRequest.loadout,
      premade_digest: digest,
    })),
    starting_equipment_packages: [],
  };
  const client = new GameDirectoryClient("/api", {
    fetchImplementation: async () => new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  });

  const catalog = await client.getCharacterCreationCatalog();

  assert.deepEqual(
    catalog.premades.map((row) => [row.premade_id, row.display_name]),
    expectedPremades,
  );
  assert.equal(
    catalog.premades.find(
      (row) => (
        row.premade_id === "hero.fighter_2_sorcerer_3_spellblade"
      ),
    )?.build.premade_id,
    "hero.fighter_2_sorcerer_3_spellblade",
  );
  assert.ok(
    catalog.premades.every(
      (row) => row.loadout.prepared_spells.length === 0,
    ),
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
