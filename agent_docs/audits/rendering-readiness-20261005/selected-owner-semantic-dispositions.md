# Selected-owner semantic dispositions

2026-10-05. Source inspection plus actual load_animation_data catalog inspection. This is a finite consumer receipt; no new metadata or production edits.

| Selected owner | Current text input / phase | Disposition |
|---|---|---|
| BoundCast delivery | Public spell label, permitted source/target, projectile prepare/travel/impact intervals; per-application identity | Neutral phase wording. Does not use asset filenames or claim detailed geometry. Sufficient for effect origin/travel/contact; not a claim of art-specific prose. |
| BoundAttack | Native result/log plus selected BodyClip meaning at body end | Outcome and supported gesture. Projectile-specific decorative description is silent. |
| Modular selected body/layers | BodyClip.description, preparation/release/body-end; accents at whole gesture/recovery | Authored semantic prose. Replacement sourceSheet only inherits accents for the exact original sheet. No early completed-flare claim. |
| Fixed-rig body, e.g. demonbeast04 Attack1/Attack2 | Existing rig clip fields, no description metadata in checked fixed-rig JSON | Intentional gesture silence; native attack/movement/result still narrates. Do not copy humanoid phrases or infer from source_clip names. |
| Visible motion legs | Selected clip description at admitted leg end; ordinary public movement fact/log | Only visible legs; dwell is silent. No hidden path reconstructed. |
| Direct condition sheets: web_bound_back/front and support.guidance/resistance/shield_of_faith/light back/front | Public condition name + selected head/body/ground attachment | Neutral inspection: condition marker/effect. Does not claim chains/runes from a filename. Application/removal comes from public facts, not membership inspection. |
| Conditions with named external media | Existing asset displayName when distinct from assetId; otherwise public condition name/attachment | Inspection names eligible attachment, not current carousel frame. Suppression resolved by existing appearance resolver. |
| Item attachment condition.spell.continual_flame | Existing named layer or condition recipe label; held exposed item or ground object | Neutral item appearance, suppression excluded. Shared binding survives transfer; inventory is not called visible equipment. |
| Perceived fields and construction | Public name/description, known geometry/object facets; selected media name if available | Known-state inspection. Raw matching assetId/displayName falls back to maintained field. No inferred creation event. |
| Body manifestations | Existing manifestation material alpha/palette selection | Neutral translucent manifestation / palette replacement inspection, not an inferred summon event. |
| Finite contact_media / decorative_contact_media / entity_lifecycle tracks | Existing selected records and clocks, but no presentation_text consumer of these collections | Currently silent decorative occurrence. Native summon/despawn/block/etc. outcome may narrate, but the actual finite portal/impact media phase does not. This is the remaining promised selected-media consumer gap, not a metadata gap. |
| Action strips | Actual loaded action media names body.bone, body.corrosive_blood, body.dread_blood, body.blood | No dedicated finite strip narrative consumer. These labels are technical and should not be printed as polished art prose; neutral impact/debris wording or explicit silence is safer. |
| Particle assets | particles.body.blood; particles.region.blood/bone/poison/corrosive/dread/water/oil; schema has no human label | Intentional particle-detail silence. Native damage/deposit/state remains describable. Do not derive material meaning by parsing these IDs. No requirement for a new particle simulator or blanket displayName expansion. |
| State-only terrain/connectors/residues/objects | Projected public state labels/facets and detailed inspection | Known state, explicitly separate from witnessed occurrences; remembered entities qualified. No per-cell invented actions. |

## Remaining consumer distinction

The current code genuinely lacks a finite selected-media occurrence consumer for the already-bound contact/lifecycle/strip collections. This was promised by the earlier selected-description work list. It can be satisfied with existing owner identity, attachment, permitted named subject and start phase plus neutral wording; no new spell registry or art semantics inferred from IDs are needed. Alternatively it must be explicitly called intentional decorative silence rather than reported as complete external-media narrative coverage.

Particles, fixed-rig unlabelled gestures and arbitrary replacement-sheet accents are legitimately silent because the catalog has no reviewed semantic prose for them. That is not a reason to expand metadata indiscriminately. Existing factual narration remains available for all these families.

## Finite consumer follow-up

`finite_media_entries` now consumes selected strips and stationary/contact media at their existing start snapshot. Lifecycle media already belongs to contact_media and is not selected twice from recipes. It uses a permitted public label or neutral visual-effect wording, and does not parse technical asset names. This closes the missing consumer scope.

Review found one identity issue to fix before acceptance: copied contact cues can occur both in an enclosing MotionTimeline and the nested group traversed by walk_bound_timelines. Collection-local enumeration indices differ and therefore cannot be the occurrence identity. Use the stable cue event/track/absolute-start/attachment identity so the existing narrative dedup collapses the repeated encounter. No new dedup registry is required.

Verified correction: contact occurrence key now uses track ID, absolute start, attachment, position/elevation and actor; event UUID remains part of NarrativeEntry identity. Collection index is removed. Bounded finite consumer source review accepted. Runtime nested-cue regression is owned by the implementation test lane.
