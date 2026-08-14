import assert from "node:assert/strict";
import test from "node:test";
import { DndEngineClient, GameDirectoryClient, } from "../index.js";
import { ContractValidationError } from "../validation.js";
const digest = "a".repeat(64);
const fireBoltRef = {
    pack_id: "content.srd_5_1_cc",
    definition_kind: "spell",
    content_id: "spell.fire_bolt",
    content_version: 1,
    definition_contract_hash: digest,
};
const poisonedRef = {
    pack_id: "core.rules",
    definition_kind: "condition",
    content_id: "condition.poisoned",
    content_version: 1,
    definition_contract_hash: digest,
};
const manifest = {
    schema_version: 2,
    engine_content_api: 1,
    content_set_digest: digest,
    built_in_artifact_digest: digest,
    packs: [{
            pack_id: "content.srd_5_1_cc",
            pack_version: "1",
            origin: "built_in",
            dependencies: ["core.rules"],
            manifest_contract_digest: null,
            pack_digest: null,
        }],
    sources: [{
            source_id: "srd.5_1_cc",
            source_family: "srd_5_1_cc",
            title: "SRD 5.1 CC",
            source_version: "5.1",
            rules_baseline: "2014",
            license_id: "CC-BY-4.0",
            canonical_uri: "https://example.invalid/srd",
            document_digest: digest,
            attribution_text: "Test attribution",
            notices: [],
        }],
};
const catalog = {
    schema_version: 7,
    content_set_digest: digest,
    catalog_digest: digest,
    entries: [{
            ref: fireBoltRef,
            display_name: "Fire Bolt",
            description: "A spell catalog fixture.",
            tags: ["cantrip", "evocation", "spell", "srd"],
            visibility: "public",
            presentation: {
                icon_key: "spell.fire_bolt",
                portrait_key: null,
                sprite_key: "fire_bolt",
                visual_variant_key: "fire_bolt",
                tint_rgb: 0xff6b21,
                vfx_profile: "spell.fire_bolt",
                audio_key: null,
                ui_group: "spells.evocation",
                equipment_sprites: [],
            },
            ordering: {
                sort_group: "spells.level_0.evocation",
                sort_order: 10,
            },
            related_content_refs: [],
            provenance: {
                primary_source_id: "srd.5_1_cc",
                source_anchor: "SRD spell fixture",
                relation: "faithful_implementation",
                fidelity: "partial",
                review_status: "reviewed",
                adapted_from_source_id: null,
                notes: "",
            },
            definition_mode: "behavior_identity",
            runtime_behavior_kind: "spell",
            condition_effect_coverage: "none",
            condition_effect_profile: null,
            condition_lifecycle: null,
            item_definition: null,
            spatial_effect_definition: null,
            dependencies: [],
            parameter_schema: null,
        }],
    presets: [],
    safe_presentations: [{
            ref: { presentation_contract_hash: digest },
            presentation: {
                icon_key: "spell.fire_bolt",
                portrait_key: null,
                sprite_key: "fire_bolt",
                visual_variant_key: "fire_bolt",
                tint_rgb: 0xff6b21,
                vfx_profile: "spell.fire_bolt",
                audio_key: null,
                ui_group: "spells.evocation",
                equipment_sprites: [],
            },
        }],
};
const spellCatalog = {
    version: "2026-07-25.1",
    generated_at: null,
    spells: [{
            id: "fire_bolt",
            content_ref: fireBoltRef,
            name: "Fire Bolt",
            level: 0,
            school: "evocation",
            description: "A spell catalog fixture.",
            action_category: "spell",
            target_type: "entity",
            range_type: "ranged",
            range_ft: 120,
            projectile_type: "bolt",
            aoe_shape_type: null,
            aoe_radius_ft: null,
            aoe_length_ft: null,
            aoe_width_ft: null,
            aoe_height_ft: null,
            damage_types: ["Fire"],
            healing: false,
            attack_roll: true,
            saving_throws: [],
            concentration: false,
            ritual: false,
            verbal: true,
            somatic: null,
            material: null,
            classes: ["wizard"],
            subclasses: [],
            source: "backend_catalog",
            multi_target: null,
            vfx: {
                projectile_type: "bolt",
                aoe_shape_type: null,
                route_hint: "single_projectile",
                recommended_asset_tags: ["bolt", "fire"],
            },
        }],
};
test("standalone and directory clients expose the same unversioned content surface", async () => {
    const requests = [];
    const fetchImplementation = async (input) => {
        const url = String(input);
        requests.push(url);
        const payload = url.endsWith("/content/manifest") ? manifest : catalog;
        return jsonResponse(payload);
    };
    const engine = new DndEngineClient("/api/", { fetchImplementation });
    const directory = new GameDirectoryClient("/gateway/", { fetchImplementation });
    assert.deepEqual(await engine.getContentManifest(), manifest);
    assert.deepEqual(await engine.getContentCatalog(), catalog);
    assert.deepEqual(await directory.getContentManifest(), manifest);
    assert.deepEqual(await directory.getContentCatalog(), catalog);
    assert.deepEqual(requests, [
        "/api/content/manifest",
        "/api/content/catalog",
        "/gateway/content/manifest",
        "/gateway/content/catalog",
    ]);
});
test("content clients validate the generated wire model instead of accepting loose JSON", async () => {
    const client = new DndEngineClient("/api", {
        fetchImplementation: async () => jsonResponse({
            ...manifest,
            schema_version: 1,
        }),
    });
    await assert.rejects(client.getContentManifest(), ContractValidationError);
});
test("content catalog accepts the authored tint field and spell catalog exposes the same exact ref", async () => {
    const client = new DndEngineClient("/api", {
        fetchImplementation: async (input) => (String(input).endsWith("/catalog/spells")
            ? jsonResponse(spellCatalog)
            : jsonResponse(catalog)),
    });
    const decodedContent = await client.getContentCatalog();
    const decodedSpells = await client.getSpellCatalog();
    assert.equal(decodedContent.schema_version, 7);
    assert.equal(decodedContent.entries[0]?.presentation.tint_rgb, 0xff6b21);
    assert.deepEqual(decodedContent.entries[0]?.ref, fireBoltRef);
    assert.deepEqual(decodedContent.safe_presentations[0]?.ref, { presentation_contract_hash: digest });
    assert.deepEqual(decodedSpells.spells[0]?.content_ref, fireBoltRef);
    assert.deepEqual(decodedSpells.spells[0]?.saving_throws, []);
    assert.equal(decodedSpells.spells[0]?.aoe_height_ft, null);
});
test("content catalog decodes exact ordered condition effects and lifecycle facts", async () => {
    const sourceEntry = catalog.entries[0];
    assert.ok(sourceEntry);
    const conditionCatalog = {
        ...catalog,
        entries: [{
                ...sourceEntry,
                dependencies: [{
                        relation: "applies_condition",
                        target_ref: poisonedRef,
                        required: true,
                        phase: "runtime_reference",
                        notes: "",
                    }],
                condition_effect_coverage: "profiled",
                condition_effect_profile: {
                    branches: [{
                            branch_id: "failed-save",
                            disposition: "harmful",
                            included_creature_types: [],
                            excluded_creature_types: ["construct"],
                            gates: [{
                                    kind: "saving_throw",
                                    ability: "constitution",
                                    outcome: "failed",
                                    dc_source: "actor_spell_save_dc",
                                    fixed_dc: null,
                                }],
                            effects: [{
                                    effect_id: "apply-poisoned",
                                    source_ref: fireBoltRef,
                                    operation: "apply",
                                    condition_ref: poisonedRef,
                                    selector: null,
                                    target: "selected_target",
                                }],
                        }],
                },
                condition_lifecycle: null,
            }, {
                ...sourceEntry,
                ref: poisonedRef,
                display_name: "Poisoned",
                runtime_behavior_kind: "condition",
                dependencies: [],
                condition_effect_coverage: "lifecycle_only",
                condition_effect_profile: null,
                condition_lifecycle: {
                    application_policy: "replace_existing",
                    tags: ["poison"],
                    removal_triggers: [],
                    agency_denial: "none",
                },
            }],
    };
    const client = new DndEngineClient("/api", {
        fetchImplementation: async () => jsonResponse(conditionCatalog),
    });
    const decoded = await client.getContentCatalog();
    assert.equal(decoded.entries[0]?.condition_effect_profile?.branches[0]
        ?.effects[0]?.condition_ref?.content_id, "condition.poisoned");
    assert.equal(decoded.entries[1]?.condition_lifecycle?.application_policy, "replace_existing");
    const malformed = JSON.parse(JSON.stringify(conditionCatalog));
    const malformedEffect = malformed.entries[0]
        ?.condition_effect_profile?.branches[0]?.effects[0];
    assert.ok(malformedEffect);
    malformedEffect.condition_semantic_key = "Poisoned";
    const malformedClient = new DndEngineClient("/api", {
        fetchImplementation: async () => jsonResponse(malformed),
    });
    await assert.rejects(malformedClient.getContentCatalog(), ContractValidationError);
});
test("content catalog requires exact compound equipment render-layer rows", async () => {
    const equipmentCatalog = {
        ...catalog,
        safe_presentations: catalog.safe_presentations.map((row, index) => ({
            ...row,
            presentation: {
                ...row.presentation,
                equipment_sprites: index === 0
                    ? [
                        {
                            equipment_slot: "body_armor",
                            render_layer: "chest",
                            sprite_key: "Chest6",
                            tint_rgb: 0x5c2a0e,
                        },
                        {
                            equipment_slot: "body_armor",
                            render_layer: "legs",
                            sprite_key: "Legs9",
                            tint_rgb: 0x6b4226,
                        },
                    ]
                    : row.presentation.equipment_sprites,
            },
        })),
    };
    const client = new DndEngineClient("/api", {
        fetchImplementation: async () => jsonResponse(equipmentCatalog),
    });
    const decoded = await client.getContentCatalog();
    assert.deepEqual(decoded.safe_presentations[0]?.presentation.equipment_sprites, [
        {
            equipment_slot: "body_armor",
            render_layer: "chest",
            sprite_key: "Chest6",
            tint_rgb: 0x5c2a0e,
        },
        {
            equipment_slot: "body_armor",
            render_layer: "legs",
            sprite_key: "Legs9",
            tint_rgb: 0x6b4226,
        },
    ]);
    const invalidCatalog = structuredClone(catalog);
    delete invalidCatalog.safe_presentations[0]?.presentation.equipment_sprites;
    const invalidClient = new DndEngineClient("/api", {
        fetchImplementation: async () => jsonResponse(invalidCatalog),
    });
    await assert.rejects(invalidClient.getContentCatalog(), ContractValidationError);
    const retiredSlotCatalog = structuredClone(catalog);
    const retiredPresentation = retiredSlotCatalog.safe_presentations[0];
    assert.ok(retiredPresentation !== undefined);
    retiredPresentation.presentation.equipment_sprites = [{
            slot: "body_armor",
            sprite_key: "Chest6",
        }];
    const retiredClient = new DndEngineClient("/api", {
        fetchImplementation: async () => jsonResponse(retiredSlotCatalog),
    });
    await assert.rejects(retiredClient.getContentCatalog(), ContractValidationError);
});
test("content and spell decoders reject retired compatibility shapes", async () => {
    const { safe_presentations: _safePresentations, ...catalogV2Shape } = catalog;
    const catalogClient = new DndEngineClient("/api", {
        fetchImplementation: async () => jsonResponse({
            ...catalogV2Shape,
            schema_version: 2,
        }),
    });
    await assert.rejects(catalogClient.getContentCatalog(), ContractValidationError);
    const spell = spellCatalog.spells[0];
    assert.ok(spell !== undefined);
    const spellClient = new DndEngineClient("/api", {
        fetchImplementation: async () => jsonResponse({
            ...spellCatalog,
            spells: [{ ...spell, aliases: [] }],
        }),
    });
    await assert.rejects(spellClient.getSpellCatalog(), ContractValidationError);
});
function jsonResponse(payload) {
    return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
    });
}
//# sourceMappingURL=contentCatalog.test.js.map