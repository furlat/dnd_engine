# Electric, death, control and portal handoff audit — 4 October 2026

Read-only code/artwork audit at `95a47cd5ca508838bce8a2e67d6fe1fc591ce4e6`. No implementation, imports, native renders, tests, or external-chat access. This report is the only file written for this slice. The source master is [the current VFX handoff][master]; earlier “pending”, “unsent”, and installation statements are historical unless confirmed below.

**Result:** of these twelve spells, only Call Lightning has a selected game spell recipe, and that recipe is the older artwork. The other eleven have native spell definitions but no selected game spell recipe. All referenced accepted raster pages inspected exist. There is no demonstrated need for a new visual design in this accepted slice. Several items still need substantial renderer/event work; several single-view packages need a production view/reuse decision before anyone can promise complete camera coverage. Generic condition recipes do not count as the approved condition media being integrated.

## Current selection, independent of the old snapshot

The loader reads `game/data/neuroclient/spell-studio-drafts.materialized.json`, merges only explicitly named bundles, and installs action aliases: [animation_data.py:276][loader], [animation_data.py:347][bundles], [animation_data.py:410][aliases]. A read-only JSON inventory of these selected data found only `spell.call_lightning` among the twelve spell identities in this slice.

- **Call Lightning:** selected [draft:8][call-draft] uses `Special1`, release frame 11, a tinted `/healing-spells/aid/cast.png` glow, two legacy `target_ground` finite banks, and 31.25 ms contact. Its eight installed PNG files exist, totaling **2,178,435 bytes**. This is not Attack5/frame-7 hand-contact-v5 or its 494,540-byte blue LeLu strike. The current [action delivery:3273][call-alias] already maps `action.spell.call_lightning.strike` to the same spell recipe: the earlier missing-repeat-binding assertion is stale. Selection and file existence are not a fresh visual pass; area-center attachment and empty-repeat behavior still need actual verification when replacing the artwork.
- **Lightning Bolt, Chain Lightning, Blight, Circle of Death, Harm, Eyebite, Finger of Death, Power Word Stun, Power Word Kill, Banishment, Dimension Door:** native definitions exist; no matching selected spell drafts/bindings found. Do not count imported source archives or catalog entries as runtime presentation.
- **Frightened:** accepted media is already selected by [condition-recipes.json:7614][frightened-recipe] and [condition-media.json:1545][frightened-media]. Apply/hold share eight existing PNG pages, **1,755,238 bytes**, with interior-window overlap and source removal fade. This does not close Eyebite's special immediate impact-to-Frightened transition: the current application starts at native frame zero, while the accepted Eyebite correction bypasses the near-empty first 0.22 seconds.
- **Sleep:** the current local `condition.spell.sleep` recipe selects existing face-attached Sleep media, and [condition-overrides.json][condition-overrides] supplies Die/down/recovery. These assets exist (two sustain PNG files, **54,580 bytes**). Eyebite Asleep is a different condition identity and does not inherit that local recipe automatically.
- **Eyebite Asleep/Panicked/Sickened:** imported generic recipes exist in [conditionPresentation.json:3501][generic-conditions], with empty persistent layers and generic feedback. Sickened and Asleep accepted media are not selected. Panicked applies native Frightened, whose shared presentation is selected.
- **Stunned:** imported generic recipe exists at [conditionPresentation.json:10825][generic-stunned], but has only desaturation/brightness and generic feedback; the approved stars are not selected.
- **Restrained/Petrified:** imported generic recipes exist, and spell-specific Web restraint is selected separately. The new generic overhead fetter and stone material remain **unapproved candidates**, not missing commissioned designs or approved imports.

Condition selection is exact-ID replacement, not inferred inheritance: [condition_types.py:349][condition-loader].

## Relative order for production work

This is a dependency/effort ranking, not implementation authorization. “No new art” includes importing/repacking already accepted source files, creating registrations, and writing presentation code. Each row retains the coverage limitations below.

| Rank | Work | Existing accepted input | Main remaining work and dependencies |
| --- | --- | --- | --- |
| 0 | Retain shared Frightened/Sleep; retain Call repeat alias | Already selected references above | Reuse. Bind Eyebite's distinct identities/transitions later; do not re-import the whole Fear pack or reopen its approval. |
| 1 | Shared Stunned, then Power Word Stun / Kill | Stunned V1; Stun/Kill V2, finite contacts | Low-to-medium media/recipe work: import pinned contact/stars pages, head fit, separate finite contact from owned condition; actual HP-gate and instant-death outcome branches. Camera-0 reuse/view validation remains. |
| 1 | Harm V3 finite recipient impact | Two accepted pages | Low-to-medium visual binding, actual target/save/HP-floor reaction and cleanup. The separate missing max-HP mechanic noted below must not be implemented in the renderer or silently declared complete. |
| 2 | Blight V4 | Two contact pages + donor-noise texture + preserved alpha-material reference | Medium work: finite silhouette withering on real body/equipment layers, Magic2 hand/socket, save intensity, immunity/plant/lethal outcomes. Native quadruped coating is not certified; do not stretch the humanoid veil onto Wolf. |
| 2 | Call Lightning replacement | Blue-local-v4 native strike + approved v5 hand/contact compositor | Medium work, depends on shared electric-contact adaptation: one strike at actual area center, Attack5/frame-7 hand attachment, per-resolved-recipient finite arcs, all admitted reactions at contact, initial/repeat/empty cases. No concentration storm floor or overhead cloud. Missing view/reuse evidence is separate below. |
| 2–3 | Circle of Death V9 | 25-page accepted overview bank + reused Blight contacts | Medium-to-high area composition and sorting; preserve 60-foot radius, actual affected recipients, one finite resolution and individual contacts. Final resolution choice remains open; do not call the overview bank a certified full-resolution delivery. |
| 3 | Lightning Bolt, then Chain Lightning | Shared five textures, isolated hand sheet/socket metadata, procedural render/lifecycle sources | High renderer/event integration, **not new artwork**: native-world ribbon sampling, finite reveal/decay, depth, hand and recipient contact; exact 100 × 5-foot Bolt corridor. Chain additionally needs an authoritative retained parent-link contract (current selection records recipients, not graph edges). No target-configuration raster export. |
| 3 | Banishment / Dimension Door | Accepted portals, silhouette/threshold reference operators and native source | High lifecycle/renderer work: captured departure pose/equipment echo and actual return; simultaneous Door endpoints, actual stride, portal-plane clipping, empty transfer interval and cleanup. Mechanics gaps below are separate. Native camera/relative-heading suitability needs evidence. |
| 4 | Eyebite / Finger of Death | Pinned four-camera fixture banks + parameterized directed-source adapters | Highest adaptation: arbitrary actual target vectors, shared coordinate transform, real sockets, body/world depth, source retirement and action/outcome timing. Eyebite additionally needs eye sustain, repeat action, independent Sickened/Asleep, and immediate Frightened. Finger additionally needs mutually exclusive normal/counterspelled branches and full hand/portal/socket transform. Existing source equations and models should drive this work; a fixture bank is not an arbitrary-range runtime bank. |

For the art handoff, these ranks must not become a list of “artist blockers” merely because production code is unfinished.

## Accepted source payloads verified on disk

All paths below are within the source root `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/`. Counts cover manifest-selected PNG pages, not actor/floor preview dependencies or entire authoring trees. All listed pages exist. This audit read/checksummed source files only; it did not execute their validators.

| Source entry point | Selected revision/payload | Scope and dependencies |
| --- | --- | --- |
| [electric-live-study/components.json][electric-components] + [CAST_HANDOFF.md][chain-contract] + [LIGHTNING_BOLT.md][bolt-contract] | Five textures **302,297 B**, all five manifest hashes match; shared hand sheet **83,131 B**, metadata `cast-assets/hand-sockets.json` | Chain hand-socket-v3 / Bolt heavy-line-v1. `spell.js`, `lifecycle.js`, `bolt.js`, `contact-renderer.js` are reusable procedural source, not installed Python-renderer operators. Hand source is Attack5, 15 frames × eight directions, release frame 7. Four-camera procedural preview does not certify occlusion. |
| [call-lightning-rework/REVISION_V5.md][call-contract] + `media.json` + `delivery-receipt-v4.json` | hand-contact-v5 preserves blue-local-v4: **1 page / 494,540 B**, PNG hash matches | 48 samples at 32 FPS; camera 0. Existing LeLu electricity scene, all thunder2 material surfaces, secondary particles/shaders retained. Shared electric arc material/hand/socket dependencies exist. Keep original strike layers and colors. |
| [death-curse-review/blight-lifecycle-v1/contact.json][blight-media] + `delivery-receipt.json` | native-colored-aim-v4: **2 pages / 215,107 B**, page hashes match; donor noise **7,651 B**; total **222,758 B** | 52 samples / 32 FPS; camera 0 native coating, separate silhouette operator. Native LeLu/DeathElementary dependencies and body/equipment fit described in [NOTES.md][blight-contract]. |
| [death-curse-review/necrotic-batch-v1/media.json][death-media] + [APPROVED_HANDOFF.md][death-contract] | Circle V9 **25 pages / 7,581,330 B**; Harm V3 **2 / 546,988 B**; Kill V2 **2 / 251,424 B**; Stun V2 **2 / 252,062 B**; Stunned V1 **2 / 21,898 B**. All **33 page hashes match**. | Circle64 frames; remaining banks44 frames, all32 FPS. Total **8,653,702 B**. Mixed revisions are intentional. Current Circle adapter `native-v9/circle/whole`; Harm `native-v3`; Kill/Stun `native-v2`; independent Stunned `native/stunned`. Camera0 only; Circle overview zoom .35. Reuse Blight contact, do not add duplicate recipient art. |
| [death-curse-review/banishment-lifecycle-v1/portal.json][banish-media] + [HANDOFF.md][banish-contract] | departure-echo-return-v1, reused `../media/banishment_v2/q0`: **4 pages / 907,268 B**, four hashes match | 64 samples /32 FPS; independent back/front; native TypeB portal plus production silhouette operator. Package parent-relative paths correctly. |
| [death-curse-review/dimension-door-lifecycle-v1/portal.json][door-media] + [HANDOFF.md][door-contract] | simultaneous-v2: **3 pages / 509,452 B**, all hashes match | 88 samples /32 FPS; camera0; timing revision reuses pages. Native TypeA particles + retained arch/recess/sill adapter. Actual actor walk sheets remain independent. |
| [death-curse-review/finger-of-death-approved-media.json][finger-media] + [normal][finger-normal] / [cameo][finger-cameo] | Ground hand V8 **8 / 549,661 B**; lance V3 **8 / 104,998 B**; impact V2 **9 / 1,418,143 B**; cameo V5 **8 / 662,610 B**; stop V1 **8 / 33,169 B** | Four camera quarters per fixture. Total **41 PNG pages / 2,768,581 B**. Pinned normal/cameo GLB models exist; existing opposing Special1 and Counterspell hand assets are explicit dependencies. Normal save retains hit; only confirmed successful Counterspell selects cameo. |
| [control-binding-study/production-handoff/fear-eyebite-approved-media.json][eyebite-media] + [FEAR_EYEBITE.md][eyebite-contract] | Eye V1 **8 / 1,446,402 B**; hit V2 **8 / 282,795 B**; Sickened V5 **8 / 2,338,973 B**; directed-first V3 **8 / 294,499 B**; directed-second V3 **8 / 434,808 B** | Four quarters; directed banks are only two fixture vectors. Frightened V5 source **8 / 2,001,692 B**, already repacked/selected locally. Sleep manifest/face-anchor dependencies exist. Full source checksum list: **106 matching entries**. |

Finger's original checksum list has **56 matching entries**; its three changed Markdown contracts match the later [documentation amendment receipt][doc-receipt]. This is a documented text-only amendment, not failed media provenance. `branch-assets.json` still says geometry is pending; the later [source contract][finger-contract] and [directed supplement][directed-contract] explicitly supersede any blanket XYZ obligation.

The original `godot-library/projects/lelu-portal`, `lelu-electricity`, and `binbun-statusfxfull` projects exist. Inspected recorder, TypeB portal, electricity scene, DeathStatus dark/shatter donors and Circle smoke texture exist. Both directed `.gd.in` sources, pinned hand GLBs, Sleep media manifest and face sockets exist. The directed compile helper also depends on local temporary Godot projects; both currently exist, but are not a portable standalone source package. A future production consumer must resolve these declared dependencies instead of shipping a whole authoring tree. No rebuild was attempted or claimed.

## Exact artwork-delivery gaps and conditional requests

**No unconditional new-art request was established for this slice.** Existing accepted art supports starting each integration within its demonstrated limits. Complete runtime coverage is not thereby proven.

| Item | What is actually absent/unverified | Concrete handoff request if production needs more than the approved pilot |
| --- | --- | --- |
| Call Lightning | Only camera0 native strike delivered; procedural contact geometry's four-view suitability does not add native strike views. | Provide a validated camera-relative reuse/registration contract for the complete blue strike, or export only genuinely missing native relative views from the retained source. Preserve all native material/particle layers, pivot/offsets, 32 FPS and cleanup. Do not blindly commission four new banks. |
| Blight, Harm, Kill/Stun/Stunned, Banishment | Camera0 native recipient/portal media; eight caster facings in reviews are not eight recipient banks. Blight's native Wolf coating is not certified. | First validate the actual attachment/reuse approach with required production camera and body silhouettes. If it cannot preserve the accepted appearance, request only the missing views or silhouette-specific coating from the existing source, with registration and an exact acceptance receipt. Generic body-alpha operator adaptation remains engine work. |
| Circle of Death | Only accepted camera0 **overview-resolution** bank; normal gameplay zoom/full-resolution suitability and sorting unresolved. | Production first selects target resolution/reuse policy and demonstrates whether current pages suffice. If not, request a production-resolution V9 export at the actual60-foot radius, retaining connected crimson base/fissure smoke, pivots and finite64-frame lifecycle. This is a conditional existing-source export, not a new concept. |
| Dimension Door | Camera0 doorway and fixture portal plane; no certified all-heading/all-camera relative-view mapping. | Establish legal portal orientation and camera-relative reuse. If reusable views do not cover production orientation, request only needed native relative views of the retained arch/source. Plane clipping, strides, simultaneous clocks and passenger membership are production work. |
| Finger / Eyebite | Arbitrary-target raster banks are not supplied. Directed adapters provide source motion/socket evidence, including only bounded off-axis native samples; Finger supplement is the projectile layer, not an entire transformed hand raster solution. | Choose and implement the established source/geometry adaptation in production. If a sprite-only consumer requires extra extracted modules, specify its real heading/range/view need first and retain shared transforms/materials. Do not request a bank for every encounter or disguise missing engine adaptation as artist design. |

No blanket XYZ/depth maps, arbitrary camera raster explosion, persistent Shocked, electrified water, or new teleport/world mechanics are authorized by these approvals. An extra spatial payload needs an actual consumer and reproduced defect under the [storage policy][spatial-policy]. Restrained/Petrified require **human artwork review of existing candidates** before import; their source already exists at [shared-conditions-completion/HANDOFF.md][candidate-contract].

## Native mechanics and event-contract findings — separate from artwork

These bounded source observations are not permission to widen the audit into spell-rule implementation.

- **Call Lightning:** [conjuration.py:165][call-native] and [conjuration.py:211][call-native-main] retain range60, radius7, ten-turn concentration-owned repeat action and an empty-ground-capable area. The current alias closes the recorded repeat-recipe gap. Keep targeting and damage from actual backend results, not the preview's `backend-events.json` fixtures.
- **Lightning Bolt:** [evocation.py:1276][bolt-native] uses `Line(length_feet=100,width_feet=5)`, excludes caster and admits all relationships. Its effect retains each recipient save/damage. Clip visuals to that admitted corridor rather than extending rules to fit hand-offset art.
- **Chain Lightning:** [evocation.py:3639][chain-native] builds a recipient list by minimum distance to **any** previously admitted chain position. It saves neither the winning parent position nor a per-target edge in its final event. The compositor requires actual graph provenance; recording/deriving a lawful presentation-link contract from native selection is code/event work, and the browser's fixture graph is not authority.
- **Harm:** [necromancy.py:1899][harm-native] implements save/half damage and pre-damage floor at1HP. Its inspected method has no max-HP reduction or duration owner. The artist handoff's “backend owns one-hour maximum-HP reduction” must not be treated as proof that this mechanic exists. Preserve a separate mechanics decision; do not add a persistent visual to simulate it.
- **Dimension Door:** [conjuration.py:4245][door-native] explicitly implements caster-only direct teleport to a visible, walkable, unoccupied position. No companion selection or occupied-destination mishap damage appears in that method. The preview's companion is not an existing native branch; integrate the supported result or obtain separate gameplay authorization. Presentation strides must not create intermediate movement/opportunity attacks.
- **Banishment:** [abjuration.py:1376][banish-condition] owns suspension, incapacitation and a prepared authoritative spatial return; [abjuration.py:1584][banish-native] links it to concentration. The inspected spell/condition supply no explicit timed-duration/native-plane/no-return branch. The accepted no-return preview cannot manufacture that result. Real spatial presence/return cells and removal facts must drive the portal/echo.
- **Eyebite:** [necromancy.py:1490][eyebite-native] resolves native asleep/panicked/sickened and links each to concentration; [necromancy.py:1557][eyebite-cast] grants a repeat action. Its art needs an explicit repeat-action delivery as well as the spell. Asleep has native wake-on-damage/assistance; Panicked owns Frightened plus flee behavior; Sickened remains its own identity, not Poisoned. This audit does not certify all repeat-action causal recording.
- **Finger:** [necromancy.py:1628][finger-native] resolves save/necrotic damage; art does not add zombie creation. Preserve Counterspell cancellation separately from save success and other cancellation reasons.
- **Power Words:** [enchantment.py:651][kill-native] uses actual instant-death admission and supports protection/cancellation; [enchantment.py:1061][stun-native] owns Stunned plus end-turn saves, with HP gate150 in the spell. An HP threshold alone is not sufficient reason for the renderer to declare death or apply a condition.

## Review constraints

Anti-slop check for the consolidated handoff: keep source existence, approval, runtime selection and actual visual verification distinct; do not re-open accepted designs, duplicate integrated Frightened/Sleep, or promote conditional exports into mandatory giant asset requests. Anti-OOP/ECS check: presentation consumes retained facts, exact conditions/source IDs and existing data recipes; no new spell managers, backend sprite paths, renderer-owned target selection or invented lifecycle state. Independent final-document review is still to be assigned by the parent; this report does not claim those review approvals.

[master]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/PRODUCTION_VFX_BACKLOG_HANDOFF_2026-10-03.md
[loader]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py:276
[bundles]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py:347
[aliases]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/animation_data.py:410
[call-draft]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/lightning_media/spell-studio-drafts.json:8
[call-alias]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/lightning_media/bindings.json:3273
[frightened-recipe]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/condition-recipes.json:7614
[frightened-media]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/condition-media.json:1545
[condition-overrides]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/condition-overrides.json
[generic-conditions]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/neuroclient/source/src/render/data/animation/conditionPresentation.json:3501
[generic-stunned]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/data/neuroclient/source/src/render/data/animation/conditionPresentation.json:10825
[condition-loader]: /mnt/c/users/tommaso/documents/dev/dnd_engine/game/condition_types.py:349
[electric-components]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/electric-live-study/components.json
[chain-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/electric-live-study/CAST_HANDOFF.md:34
[bolt-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/electric-live-study/LIGHTNING_BOLT.md:17
[call-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/call-lightning-rework/REVISION_V5.md:26
[blight-media]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/blight-lifecycle-v1/contact.json
[blight-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/blight-lifecycle-v1/NOTES.md:3
[death-media]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/necrotic-batch-v1/media.json
[death-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/necrotic-batch-v1/APPROVED_HANDOFF.md:3
[banish-media]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/banishment-lifecycle-v1/portal.json
[banish-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/banishment-lifecycle-v1/HANDOFF.md:7
[door-media]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/dimension-door-lifecycle-v1/portal.json
[door-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/dimension-door-lifecycle-v1/HANDOFF.md:20
[finger-media]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/finger-of-death-approved-media.json
[finger-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/production-handoff/HANDOFF.md
[finger-normal]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/production-handoff/FINGER_OF_DEATH_NORMAL.md
[finger-cameo]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/death-curse-review/production-handoff/COUNTERSPELL_CAMEO.md
[eyebite-media]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/control-binding-study/production-handoff/fear-eyebite-approved-media.json
[eyebite-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/control-binding-study/production-handoff/FEAR_EYEBITE.md:19
[directed-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/directed-cast-completion/HANDOFF.md:11
[doc-receipt]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/handoff-review-2026-10-03/documentation-receipt.json
[candidate-contract]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/shared-conditions-completion/HANDOFF.md:3
[spatial-policy]: /home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/SPATIAL_EXPORT_POLICY_2026-10-02.md
[call-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py:165
[call-native-main]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py:211
[bolt-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:1276
[chain-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:3639
[harm-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:1899
[door-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/conjuration.py:4245
[banish-condition]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:1376
[banish-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/abjuration.py:1584
[eyebite-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:1490
[eyebite-cast]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:1557
[finger-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/necromancy.py:1628
[kill-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/enchantment.py:651
[stun-native]: /mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/enchantment.py:1061
