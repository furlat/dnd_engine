# Packet 2 ECS / event / import-DAG review — 2026-10-04

Verdict: **changes required** for the two bounded presentation findings below. This is an independent read-only production review against base `95a47cd`, not approval of packet 3 necromancy, packet 4, packet 5, Telekinesis, or the remaining Antimagic suppression work. Continual Flame is not implemented and is outside this receipt. No production code, tests, assets or recordings were changed or executed by this review.

## Findings

1. **Source-owned flame removal inherits recipient contact timing.** `game/choreography.py:970` advances a bound cast's inherited clock to projectile travel end. `game/choreography.py:1088` then admits its consumed condition removal at that clock. `game/condition_media_lifetime.py:178` derives `consumed_ms` from this membership edge. Therefore later Hurl retains the held flame throughout flight rather than ending it at source release. The consumed flag correctly suppresses the clear tail, but does not establish the correct removal milestone. Use the existing bound action's release milestone for the explicit source-owned consumption and its causally owned light/sensory removal; leave recipient damage/contact on its existing milestones. Also cover `dnd/spells/conjuration.py:4883`: an initial direct throw while an older flame is retained removes that exact condition with `consumed=False`, currently selecting ordinary clear-tail semantics. Establish this consumption explicitly in native facts rather than recognizing spell names in the renderer. Acceptance must distinguish before release, in flight, contact, hit/miss and failed admission, with retained replay/seek.

2. **The four supported buffs cannot all be presented concurrently.** Every new condition recipe uses `composition.group="nature_support"`, priority 40, `maxLayers=3` (`game/data/condition-recipes.json:9396`, and the other three entries). `resolve_condition_appearance` counts each recipe in that group (`game/condition_animation.py:239`), including material-only recipes. With Barkskin, Fire Shield, Produce Flame and Shillelagh active, deterministic content ordering admits the first three and silently omits Shillelagh's exact-item material. Admit the four compatible treatments through authored composition policy; no new runtime compositor is necessary. Validate their simultaneous native memberships and resulting materials/layers, then remove each owner independently.

## Architectural assessment

- Shillelagh uses the existing actor-owned condition and typed `ConditionState.affected_item_uuid`; the draw path joins that value to `RigLayer.item_uuid`. Native weapon overrides remain keyed by the exact condition UUID. There is no second item condition or magical-item registry. Same-alpha material/glint sampling extends the existing item operator.
- Barkskin retains the existing AC minimum constraint and concentration ownership. The accepted `body-material.js` bark math and registered original texture are translated into the shared body material operator. Current silhouette/equipment and original alpha are the inputs; original shadow separation remains. No flattened pose image or spell-name drawing branch was added.
- Produce Flame uses an ordinary retained native condition, exact granted action cleanup, native light ownership, and recorded attack outcomes. Hurl is classified as an ability while retaining the spell effect origin; shared Sanctuary, metamagic exclusion, Globe and Antimagic admission were extended at their existing boundaries. Range admission now precedes payment/consumption. The retained head is addressed through the existing projectile phases and actual source/recipient endpoints, without the delivery fixture's +X trajectory.
- The new named hand attachment uses existing pose-socket lookup over the actual clip/frame/facing. Original modular measured points and explicit nulls are retained. Unmeasured fixed rigs and occluded frames have no fabricated standing offset. This receipt does not expand rig coverage or certify visual quality.
- Fire Shield publishes its native warm/chill selection through the existing energy field. Its normal incoming/applied damage events carry exact `source_condition_uuid`; observer projection admits only a disclosed non-internal owner. `bind_event_condition_response` extends the existing response binder and lifetime sampler with typed request/applied triggers and owner/recipient participants. Local shield response and positive-damage attacker contact remain separate factual boundaries; there is no duplicate damage event or private retaliation timeline. Native support-height distance and existing exact handler/modifier/light cleanup are reused.
- The offline importer preserves/checks source bytes and registers banks through the common paged billboard storage path. It registers data and textures; it adds no runtime effect executor or registry.
- Inspected new shared game import edges, including `condition_media_lifetime -> body_presentation`, have no return path in the current static game module graph. The targeted game-module name search found no runtime branches naming these four spells. Native spell modules retain the existing downward dependency direction. Typed scalar fields, enums, UUID ownership, authored selectors and numeric operators remain portable to TypeScript without copying Python entity instances into presentation.

## Evidence boundary

Reviewed the native/presentation source, existing/new focused test scenarios as specifications, accepted material source files and the modular hand socket receipt. No new test or rendering results are claimed. Parent-run test expansion and recordings require their own results. The findings above are source-derived and remain blocking until corrected and checked. Deferred general Antimagic contribution suspension is not approved here.

Snapshot manifest SHA256: `210aec7921b8cd834928b834610fac29d4ff0708076c33bb31cc6a426aa7e75e` (SHA256 of the exact UTF-8 manifest block below, with its final newline). The shared checkout is concurrent; unrelated portions of native files are fingerprinted for reproducibility but are not thereby reviewed or approved.

```text
5a9d266e55dff8e12393457dac28b9a4b381248abd28019688b0f2b32de012ab  dnd/spells/conjuration.py
6a76389c4e8914219c4f15b38e0ea5c9ee4e8136d6e26924e2755dce5472958e  dnd/spells/evocation.py
9fcb741f49d0a7b11e3383230d2f8b58cbe2c79959f295c129404595f08ea9dd  dnd/spells/transmutation.py
459f32bd60d6fa860dc27b2e0140882efe5ed2c0a0eb8537ec96d91b30f1b1c7  dnd/spells/abjuration.py
b4f5bd5903cde14e5599d8afbb428bad4d76569cd555823d1418e280ced2f325  dnd/classes/sorcerer.py
3277b3e8a2d8147df4cfe7338cce2499463592e365a6b11a4d36cefb3a995ade  dnd/actions.py
1de52035d4a53307cee21fc704e14577918b10e6a29d168334c4a63f702b8347  dnd/core/events.py
4fb39336f316d6e6b16aa14d25cf77f5e1cf30cee7e47adb48548f0ffb6cc066  dnd/entity.py
0c3c0834ba1ea7d61d7629eb5ae288d2300e82579e5b56b30894176b0bebef98  dnd/types/actor.py
9493e00792376c2c72de5d4065ff9575bdbd1dab662055074bfe8d6b417c3588  game/player_facts.py
761682cfa2050011a282deb3043640de233f1fc1671cbdaa2fb3d8c980525102  game/player_projection.py
e8c8126dfa484c0fe1eca2c25635477f5636325322c2790bfde5d0c75a815b87  game/animation.py
ae6de06153661a06368619e7829e4ab1ada9a989d0be6799daf6efa291dd671b  game/animation_types.py
8bdb11c54eba59cc888a89c4ec15c5d377bcb9d6139cc2191a3d10e6b4f63877  game/animation_data.py
d53c4e1750451297b5c017ee9a771fb5dd531cf06526008fe5d241e06302939a  game/animation_draw.py
b78237da57e3b0d35bcb36aee779f416bea0f6de3897cf8e0ada2d273e93a418  game/cast_media.py
901efe26b9202778dfdf247efeb5e0b48e3d1f358bf9c614b2e9a5234705750c  game/choreography.py
dbe1893b6b32a8d9de8fff55806aa041d9b640de9ca5689d466fb4ee8e32796d  game/condition_types.py
566613b0696a6c0e910b2eeb1876aa542841bef5eb5a1fe6c978285756bf226c  game/condition_animation.py
77fec946b8ac07564fe955ec4a39cb7d5e7045ed974d81a5a532e90d0806d7d1  game/condition_media.py
d14ba9143b622e449963f953bbb68cc5eee724f5f6e73cdd46aa0caa78659932  game/condition_media_lifetime.py
94ad7f4b1c307357fa72d8d0b463b1a47b0d587a9fcc2db40ad3b0a32260dba0  game/condition_draw.py
98d34d4b68528f8ba7eebe63650a2de4e522cd2c12c48ac8bc1f90f7cd7c9e95  game/item_effects.py
90a6c4bb45ce9a3c3ed4543f22042aa6e63efec1f4299e8f5417f13df6a7972d  game/data/condition-recipes.json
1ae7fbbc3bd723d972e3eb78f3985ef33fed33d3edceb3d31b3dfe2d6cda6295  game/data/condition-media.json
ec71ca2ae7a6f80feb2bba2a38ef1c48cf391030b5767691d9207e0d1f8f56f4  game/data/support_conditions/nature-draft.json
55f6dcfa9b71bca10bed675bca4ca5a9a6a67dcc5b22af7496bc4c6834499a43  game/data/support_conditions/bindings.json
a71a86713ce175df321fbbf9f58b6f9b026b05a429ed28f61510188e0ff68c72  game/data/support_conditions/projectile-assets.json
480ba7eb4598e2bd85aadc730581d71271535df265cdfb9de79ef9c9f2fd2711  game/data/support_conditions/nature-source.json
8b4c8a39995f3ea6ad90bcece45941fce7abc15b14d87718854f3087a621ebc7  game/data/neuroclient/pose-sockets.json
53140f45c8246f934175e1b0b7f3db5cf51d17458a2c2c34ac7379cb0825b41e  devtools/import_nature_utility.py
f544ace31855152e625ec740176cc64ba02c0417ec19301ff1e9e01e35a14706  devtools/import_registered_media.py
2e83db8e861f41a39d2119cd2bc34a7e073e82478b9eb8b5966120b3061c60f7  devtools/media_delivery.py
```
