# Spell VFX integration ranking — 4 October 2026

**Subsequent human decision:** all delivered Godot artwork is accepted, including
the Restrained/Petrified and Disintegrate outcome supplements called candidates
below. Those historical acceptance gates are closed. The current implementation
scope and required backend repairs are in the
[implementation plan](SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md). The original
audit review hashes certify the pre-amendment inventory, not this later notice.

Audit of the production handoff against committed game source at
`95a47cd5ca5` (`goblins and some demons`). This is an integration inventory and
proposed order, not an implementation or new artwork approval. Character work
stays paused. No other chat was read or contacted.

Source entry:
[/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/PRODUCTION_VFX_BACKLOG_HANDOFF_2026-10-03.md](/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/PRODUCTION_VFX_BACKLOG_HANDOFF_2026-10-03.md).
Source paths below are relative to that file's directory.

## What is actually ready

Most of this queue has accepted source artwork. The remaining work is largely
binding it to recorded game events, adapting supplied composition/material
operators, and checking actual placement and lifetime. **Asset-ready does not
mean finished, JSON-only, or mechanically complete.**

Static inspection of the default bundles selected by `game/animation_data.py`
finds **97 distinct spell bindings**. This is a selection count, not 97 visual
acceptances or a claim about every spell in the catalogue. All **29 first-binding
entries** in the handoff remain unbound. Call Lightning selects its older
four-camera effect, not the accepted `hand-contact-v5` replacement. Fly and the
three summoning spells are already selected; this pass does not reopen them.

The current handoff has three separate workloads:

- 29 first bindings and one Call Lightning replacement.
- Eight follow-ups to already selected spells, plus shared conditions/surfaces.
- 21 approved class presentation sets. These are not 21 additional spells.

The [Godot handoff](SPELL_VFX_MISSING_ASSETS_HANDOFF_2026-10-04.md) separates
missing delivery/coverage, conditional artwork, and existing candidates awaiting
human acceptance. Do not send the whole integration queue back for new art.

## Ranked first integrations

Ranks order integration effort and dependencies, not spell power or importance.
Within a rank, batch shared mechanisms and source packages. A backend issue in
rank 4 must be resolved in an implementation plan before claiming end-to-end
completion; the renderer must never fill it in.

| Rank | Spell | Accepted revision / contract | Work remaining; additional-art decision |
| --- | --- | --- | --- |
| 1 | Darkvision | `sensory-fps32-delivery/HANDOFF.md` | Existing sensory/condition mechanism; distinct head and ground anchors. No extra art. |
| 1 | Longstrider | `nature-utility-batch/HANDOFF.md`, `compact-palm-v7` | Bind wind application/hold/removal to the real owner. No extra art. |
| 1 | Power Word Kill | `death-curse-review/necrotic-batch-v1/APPROVED_HANDOFF.md`, V2 | Finite contact, actual HP gate/kill, existing death/corpse handling. No extra art. |
| 1 | Power Word Stun | Same necrotic contract, V2 + Stunned V1 | Finite hit and shared, independently owned Stunned loop. No extra art. |
| 2 | Shillelagh | Same nature package | Adapt supplied material operator and retained item ownership on the actual eligible weapon. No conjured replacement staff. No extra art; not just a spell-sheet binding. |
| 2 | Barkskin | Same nature package | Adapt supplied bark texture/operator through current body and gear alpha, including removal. No extra art. |
| 2 | Blight | `death-curse-review/blight-lifecycle-v1/NOTES.md`, `native-colored-aim-v4` | Contact and supplied silhouette treatment; real save/plant/immunity/death outcomes. No extra art established; humanoid veil is not certified on every anatomy. |
| 2 | Produce Flame | Nature package, `compact-palm-v7` | Held hand flame, light, hurl hit/miss and dismissal; adapt existing head/trail to actual path. Do not copy the +X fixture. No new art established as necessary. |
| 2 | Wall of Force | `wall-spells-study/force-disintegrate-v2/production-handoff/HANDOFF.md`, blue Force V2 | Panels and dome art exist. Current construction consumer accepts only WallSegment: shared dome support/world binding is required. Preserve accepted invisibility cue and whole-owner Disintegrate removal; resolve V1 dependencies, not the authoring dump. No extra art. |
| 2 | Spirit Guardians | `holy-guardians-study/SPIRIT_GUARDIANS_HANDOFF.md`, `relaxed-flow-v5` | Both variants; implement supplied orbit/haze/trail composition using shared presentation data/operators; follow owner, not fixture path. Damage recipients come from events. No extra art. |
| 2 | Guardian of Faith | `holy-guardians-study/guardian-of-faith/HANDOFF.md`, `lean-horned-v3` | Anchored object, eight-heading strike/contact/recovery/retirement; reuse radiant contact. No extra art. Current 5×5 backend footprint is an explicit mechanics-review point, not a visual hit test. |
| 3 | Fire Shield | Nature package, `compact-palm-v7` | Both warm/chill; first retain the actual shield-kind discriminator, then contact only on an admitted qualifying melee hit and independent removal. No extra art. |
| 3 | Eyebite | `control-binding-study/production-handoff/FEAR_EYEBITE.md` and `directed-cast-completion/HANDOFF.md` | Caster-eye concentration owner, initial self-cast and granted Eyebite Strike delivery; substantial socket/trajectory adapter and immediate handover to resolved Asleep, Panicked/Frightened or Sickened. Bind Eyebite Asleep explicitly: Sleep media's different identity is not inherited automatically. No extra art. |
| 3 | Lightning Bolt | `electric-live-study/LIGHTNING_BOLT.md`, `heavy-line-v1` | Supplied modular arc material/geometry; actual 100×5-foot admitted corridor and hand release. No extra art, but substantial reusable geometry work. |
| 3 | Circle of Death | Necrotic approved contract, `native-fissure-smoke-v9` | Compose supplied fissures/smoke over authoritative area and schedule finite recipient contact; no persistent damage zone. Existing bank is overview-resolution/q0: first validate production resolution/reuse; extra existing-source export only if insufficient. |
| 3 | Finger of Death | `death-curse-review/production-handoff/HANDOFF.md` plus directed adapters | Normal discharge versus confirmed Counterspell cancellation; actual portal/hand/target transforms and depth. No extra art; adapt the supplied geometry instead of exporting each encounter. |
| 3 | Disintegrate | Force V2 contract, `power-projectile-static-ice-v2` | Accepted projectile and Force response can integrate now: exact launch/contact/depth/first obstruction. Extra save/lethal-dust/object supplements exist but are unapproved. Native creature dust/corpse/equipment outcomes are also unfinished; art approval alone will not implement them. Larger-object partial destruction remains unsupported. |
| 3 | Ice Storm | `cold-weather-batch/HANDOFF.md`, `textured-fracture-v3` | Scatter supplied independent modules; align impact/reaction and terrain retirement. Single-view components need camera-relative validation, not an automatic four-bank commission. Verify retained range discrepancy separately. |
| 3 | Sleet Storm | Same cold contract, `soft-ground-contact-v5` | Owner-lived weather/ground; repeat hold, clear on removal, no damage. Validate rotational/camera-relative reuse and actual occlusion before requesting any extra bank. |
| 3 | Sunbeam | `solar-spells-study/HANDOFF.md`, `solar-lifecycle-v1` | Fix measured hand-root offset and clip to actual 60×5-foot corridor, repeat-cast timing, depth; verify native light/timer/blindness facts. No extra art. |
| 3 | Sunburst | Same solar contract, `ground-coverage-v2` | Actual affected cells, one resolution and independent Blinded ownership; verify native darkness interaction. No extra art. |
| 4 | Chain Lightning | `electric-live-study/CAST_HANDOFF.md`, `hand-socket-v3` | Art supports arbitrary graphs. Retain the actual resolved hop-parent edges before drawing causal branches; do not reconstruct the graph from recipient distances in the client. No extra art. |
| 4 | Harm | Necrotic approved contract, `native-family-v3` | Art ready. Current method applies the damage floor but lacks the handoff's max-HP-reduction branch; resolve rules scope before claiming full completion. |
| 4 | Banishment | `death-curse-review/banishment-lifecycle-v1/HANDOFF.md`, `departure-echo-return-v1` | Art ready. Align actual absence/return with retained state; inspected implementation lacks explicit duration/native-plane/no-return handling. No renderer-invented return timer. |
| 4 | Dimension Door | `death-curse-review/dimension-door-lifecycle-v1/HANDOFF.md`, `simultaneous-v2` | Art ready. Current native teleport is caster-only; passenger behavior shown by the source is not implemented merely by drawing two travellers. Review supported destination/selection scope first. |
| 4 | Telekinesis | `final-utility-batch/HANDOFF.md`, `grounded-layering-v2` | Art ready; actual admitted grab/move/release paths, height, recorded subject, large-body fit and sorting require a bounded native/event review. |
| 4 | Antimagic Field | Same utility contract | Art ready; follow caster without hovering. Suppression/restoration and independently owned linked effects require native/event verification. A violet dome cannot implement suppression. |
| 4 | Heroes' Feast | `holy-guardians-study/heroes-feast/HANDOFF.md`, `spectral-material-v2` | Table/blessing art ready. Unfinished eating pose, buff duration, serving/prop lifetime and stated immunity/healing differences need a scoped decision. Author interaction from existing rig poses first; no missing new sprite sheet has been established. |
| Delivery gate | Cone of Cold | Cold contract, `straight-alpha-volume-v4` | Accepted connected cone is q0/+X only. Missing relative-heading coverage or a validated native geometry adapter is needed for the general spell (G1). Separately require authoritative frozen-corpse/thaw state before binding the accepted lethal material; art must not invent it. Existing contact/material assets can be retained. |

The new bark/weapon operators and item-state projection do not already exist
merely because their source is delivered. Rank 3's source geometry/material
programs are artwork ingredients, not portable production implementations.
Keep those adaptations typed and shared, with no second browser renderer or
spell-name branches determining game outcomes.

**Coverage qualification across ranks:** Blight, the necrotic-family banks and
Banishment/Dimension Door include single-native-view fixtures. Blight's native
humanoid coating is not certified on quadrupeds; Door's portal plane needs a
valid relative-orientation mapping. Circle's bank is explicitly an overview
export. Validate actual consumer resolution, camera-relative reuse and body fit
before claiming full coverage. If existing components/operators cannot preserve
the approved appearance, request only the missing existing-source export. These
are conditional checks, not automatic new art orders for every camera/creature.

## Call Lightning replacement

Keep the current selected effect until its replacement is complete. The current
repeat action aliases `spell.call_lightning`; the old missing-repeat-binding
finding is stale. The replacement's hand/finite body electricity components
exist, but its preserved full native strike is explicitly a **single-camera
pilot**. G2 requests proof of valid camera-relative reuse or the missing native
views. Do not substitute unrelated old strike layers and label that V5 complete.

## Follow-ups to selected spells

| Priority | Existing selection | Remaining work / artwork status |
| --- | --- | --- |
| First | See Invisibility; True Seeing | Upgrade to accepted `sensory-fps32` head/ground cues. No extra art. |
| First | Hold Monster | Supplied Ogre/large-body attachment, quiet sustain and independent Paralysis/removal. No extra art. |
| Then | Continual Flame | Current spell creates its own object at a position, not arbitrary carried-object selection. Socket/elevation binding is code work; arbitrary existing-object attachment needs a native targeting decision. No extra art. |
| Then | Wall of Stone | Existing sections; use accepted intact-retirement law rather than a disappearance hard cut; local break, neighbors, permanent owner. No extra art. |
| Then | Wall of Ice | Import/select static dome and quiet frigid air. Shared dome consumer support is missing: current construction drawer rejects non-WallSegment geometry. Preserve flat local break versus whole 120-HP dome and parent cleanup. No extra art in the approved forms. |
| Split | Wall of Thorns | Flat modules/contact need code work. Ring cannot be declared ready: backend height 20ft versus registered art 10ft fails the renderer's dimension check. Conditional G4 requires the correct contract, not stretched pixels. Partial disclosure also needs production composition. |
| Split | Wind Wall | Existing modules/joins/lifetimes are usable. Isolated directional missile-block gust still needs extraction/adaptation (G3); actual intercepted projectile event/position is production-owned. |

## Shared conditions and surface work

| Shared presentation | Current state and next work |
| --- | --- |
| Frightened; Asleep/Sleep; Charmed | Existing selected cues are reusable. Bind source ownership for each new consumer; keep Eyebite branches distinct. |
| Paralyzed; Blinded; Deafened | Existing authored local selections exist. Verify independent owners and reuse them rather than importing duplicates. |
| Incapacitated | Approved pause cue exists; general selection remains separate from Hypnotic-specific presentation. No extra art. |
| Stunned; Eyebite Sickened | Accepted dedicated cues need selection; generic placeholder recipe rows are not the new art. No extra art. |
| Chilled / Frozen / thaw / shatter | Accepted `outline-tests-v6` operators/components exist for different silhouettes. Integrate only against real supported condition/death/corpse transitions. No new condition is authorized by its artwork. |
| Ground fire / ignition / water quench / steam | Accepted surface package and two-second overlap work exist; current wall heat contact is only part of it. Bind recorded surface reactions, footprints and retirement; no automatic neighbor ignition or new Grease rules. Finite 2.5-second quench wisps do not constitute a maintained SteamCloud. Its producer/lifecycle needs a separate native scope decision before requesting more art. |
| Restrained / Petrified; Disintegrate supplemental outcomes | Source candidates exist, but acceptance is missing. Separate review queue, not missing-file claims or permission to import them. |

## All 21 class sets, ranked separately

All use `class-action-vfx-proposals/live/HANDOFF.md`, approved `roar-cast-v5`:
36 native banks / 5,371,384 bytes, plus explicit reused dependencies. No new
character or weapon art is needed. The supplied single-weapon slash fixture is
not a universal blade path.

| Order | Sets included | Integration dependency |
| --- | --- | --- |
| C1: existing facts/composition | Second Wind; Action Surge; Survivor; Dragon Wings | Actual healing/action facts; compatible Bag8 class selection already works, add finite manifestation wind. |
| C2: owned status/application | Rage/End Rage; Frenzy; Reckless/exposed; Mindless Rage cleanse; Intimidating Presence/refresh | One Rage/Frenzy treatment; actual cleanse/veto; finite mouth-origin intimidation wave, unchanged shared Frightened. |
| C2: resource conversions | Font of Magic slot→points; Font of Magic points→slot | Real resource changes/action outcome; actual hands, no spell-rank parsing from names. |
| C3: provenance/discriminators | Relentless Rage; Indomitable; Protection; Quickened; Twinned; Distant; Elemental Affinity | First retain explicit feature-success, intervention or mode/energy facts missing from current projection. Generic 1HP, final save success or attack miss is insufficient evidence. Preparation consumption/clear comes only from real events. |
| C3: equipment and spatial | Equipped Frenzied Strike/Retaliation/extra/critical attacks; Draconic Presence Awe; Draconic Presence Fear | Actual weapon trajectories; typed Awe/Fear mode, following areas and real recipient saves. |

Those rows total 4 + 5 + 2 + 7 + 3 = 21 sets. Dragon Wings already selects compatible
Bag8 wings through a class condition recipe; its accepted finite manifestation
wind and the complete class-action packet are still not integrated. Do not
rebuild the working wing compositor or claim that Fly completed the class batch.

## Explicit exclusions

Fly, Wall of Fire and the accepted summoning work are not new import tasks.
Beacon of Hope, Daylight, Mass Healing Word, Divine Word, Bestow Curse, Hold
Person, Hypnotic Pattern, Slow, Fear, Scorching Ray and Flame Strike already have
selected accepted art; no old candidate review is reopened here.

Prismatic Spray and Prismatic Wall stay deliberately deferred. So do persistent
Shocked/electrified-water mechanics, floating/tilted/stacked walls, full spheres,
bridges/ramps and unapproved dome sizes. Do not turn their absence into Godot's
required delivery list. Thorns XYZ remains revoked; Wind's pinned companion is
optional. There is no blanket XYZ request.

## Evidence and review

- [Walls, cold, solar and surfaces audit](audits/SPELL_HANDOFF_WALL_COLD_SOLAR_2026-10-04.md).
- [Electric/death/control audit](audits/SPELL_HANDOFF_ELECTRIC_DEATH_2026-10-04.md).
- [Utility/class/shared-condition audit](audits/SPELL_HANDOFF_UTILITY_CLASS_2026-10-04.md).
- [Holy audit](audits/SPELL_HANDOFF_HOLY_2026-10-04.md).
- Current selection evidence: `.runtime/spell-handoff-audit-20261004/current-selection.json`.
- Rechecked source integrity: `.runtime/spell-handoff-audit-20261004/source-integrity.json`:
  **53 documents, 487 local links, 166 selected media records; zero errors**.
  This checks that defined files/receipts agree, not every source asset or game
  camera. The dated catalogue-count assertions belong to the original snapshot;
  the current binding count above was obtained separately.
- Independent anti-slop and ECS/event-boundary reviews of the consolidated
  ranking and Godot handoff are recorded in the review receipt once complete.

No native test suite, game capture, artwork import or production-code mutation
was needed for this audit. Future integration acceptance requires saved native
event replay, relevant cameras/directions, interruption/removal/outcomes, sockets,
source ownership and real media timing; a binding row alone never closes it.
