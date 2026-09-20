# New spell delivery and exact spell palettes

Authorized unit: integrate the received production-v8 Ray of Frost, Ice Knife
and Chill Touch art, and use each authored spell's actual palette for isolated
casting effects and the normal 150ms target flash. The user is AFK and asks us
to complete implementation and review clips autonomously.

Source: `/home/tommaso/.codex/worktrees/1aac/dnd_engine/docs/ICE_SPELL_PRODUCTION_HANDOFF_2026-09-20.md`
and its `output/weapon-vfx/ice-spells/production-v8/` package. These are art
references, not replacement gameplay actors or another authoritative renderer.

## Contract and boundaries

Input: real discovered spell actions, then saved subjective event lineages.
Output: original native effects, replayable without a running engine, with
authored media, contact timing, per-spell colors and the real actors' appearance.
Both participants and all four cameras must be represented in review clips.
Passing mechanics tests and media availability do not replace visual inspection.

1. Preserve Ray of Frost and Chill Touch's existing native rules and condition
   lifetimes. Add missing Ice Knife using the existing spell/area application
   mechanisms: selected-target piercing attack, then a five-foot cold burst on
   hit or miss, one paid cast and complete parent/child causality. Critical
   multiplication applies to piercing only. Verify the source rule and content
   ownership before declaring it.
2. Adapt the delivered phase pages into the existing authored projectile storage
   and shared resolver. Keep exact frames, dimensions, fixed facing pivots,
   alpha/additive phases and gains. Cache only requested pages with bounded
   storage; no eager decode, runtime hashes or external source validation.
3. Extend shared phase data only for actual missing delivery contracts: a
   target-local effect with an authored contact point in its media clock, and
   post-contact travel overlap that keeps advancing/fading at the destination.
   Chill smoke starts with the cast, sample206 is416.67ms, sample236 contacts
   at625ms. Damage/TakeDamage begins at contact, not first visible smoke. Ray
   overlaps160ms, Ice Knife2/144seconds. No spell-name branches in sampling.
4. Add passive palette mapping data to authored cast/flash bindings. Reuse one
   cached luminance/noise remap against actual actor/isolated effect pixels.
   Preserve silhouettes, normal TakeDamage speed, existing frame anchors and
   150ms no-fade flash. Use each actual delivered palette, including existing
   Fire Bolt, Fireball, Magic Missile, Acid Splash, Guiding Bolt and Eldritch
   Blast. Chill alone selects its delivered dark hand-noise treatment through
   data; other spells retain their own highlights. Never recolor clothing as
   part of caster effects or substitute demonstration actors.
5. Record actual hit/miss/condition and Ice Knife burst sequences once, then
   replay the serialized inputs for clips. Include existing spells to review
   cast/hit colors; inspect new contact and fade moments and camera rotation.
   Test native effects and serialization, phase page transitions, pivots,
   palette/alpha preservation, contact timing and unchanged ordinary playback.
6. Document completion, limitations and a separate chilled-ground proposal.
   The latter is design only: no automatic freeze or new ground mechanics are
   authorized by an art handoff.

## Independent reviews

Anti-slop: `gore_antislop`; ECS/anti-OOP: `gore_ecs_review`. Both investigate
existing code independently before reviewing these concrete boundaries. Their
initial findings confirm existing Ray/Chill rules, missing Ice Knife, page
storage needs and the distinction between target-local media and travel.
Final anti-slop implementation review (`weapon_antislop`) found no concrete
blocker in native burst ownership, media clocks, registration, cache behavior or
palette isolation. The ECS reviewer confirmed passive recipe ownership and
requested three documentation clarifications, all applied: native expiration of
future persistent frost, the existing first-per-turn ice save gate, and the
distinction between Chill's contact sample236 and approach-depth cut sample240.
These approvals concern the implementation and its boundaries; visual acceptance
still belongs to the user.

## Implemented result

### Native mechanics and retained events

Ray of Frost and Chill Touch keep their existing native effects. Ice Knife is
now a discovered level-one spell: one paid casting declaration/execution, a
selected-target piercing attack, then an unpaid five-foot cold burst on hit or
miss. The burst enters at EFFECT, so it cannot consume another action/slot or
trigger a second Counterspell opportunity. Its ordinary saves/damage retain the
original cast lineage and execution identity. It uses actual area propagation,
including blockers and eligible allies/self. Criticals double piercing dice;
upcasting adds cold dice. One shared cold roll serves the burst's recipients.

The spell belongs to `content.neurodragon`, with the legacy official source
recorded in the existing catalog/provenance format; it is not mislabeled SRD5.1.
`SpellEvent.effect_id` identifies the burst inside the owning spell. The same
optional fact crosses player projection and selects a passive `effectDrafts`
recipe. A renderer does not decide which targets take damage.

The final replay pass also exposed old native-v2 compatibility omissions. An
older spell has no subeffect identity; an older sensory update has no observed
fixture delta. Those specific added fields now use their native None/empty
defaults in the existing additive-field list. Required identities are still
required. The original Fire Bolt/Magic Missile recordings remain unchanged and
replay without running their gameplay again.

### Shared playback and approved artwork

Production-v8 supplies 21,888 dense samples in 368 PNG pages (about96MiB).
The shared projectile resolver reads the requested page and frame; it preserves
the exported directional pivots, blends, gains and alpha. Its bounded cache
fills on demand. Loading animation metadata decodes no projectile pages.

Chill's local effect begins with the cast and reaches contact at625ms. Its
piecewise source clock preserves sample206 at416.67ms and sample236 at contact;
damage animation starts at contact rather than opening smoke. Ray's160ms
post-contact travel and Ice Knife's2/144s overlap advance their source frames
and fade at the destination. Native contact is not delayed. Ice Knife's nested
area recipe uses `cast.enabled=false` rather than a second caster gesture.
These are shared serializable fields, not spell-name cases in the frame loop.

Casting overlays and the150ms contact flash now use exact authored palettes for
Fire Bolt, Magic Missile, Fireball, Eldritch Blast, Guiding Bolt, Acid Splash,
Ray of Frost, Ice Knife and Chill Touch. The actor's actual modular/fixed-rig
silhouette and animation remain in use. Casting recolors isolated effect
layers; target recolors are cached from the actual body row. Chill selects the
delivered dark noise treatment through data. Existing normal TakeDamage speed,
floating-number/HP and death anchors are preserved.

The latest approved Fireball/Eldritch color revision is also imported into the
actual projectile media: 3,520 selected existing frames, with no timeline or
geometry replacement. `devtools.import_spell_color_revision`,
`devtools.import_ice_spells` and `devtools.bake_spell_palettes` are offline tools;
their source projects are not runtime dependencies. Package READMEs record the
reproduction order.

### Validation and review evidence

The [final combined gallery](http://127.0.0.1:8767/runs/20260920T005836Z-d15230/index.html)
passes **27/27 clips**, spanning **3,121 four-camera frames**, with **zero media
gaps**. All inputs are saved game events. Seven new native experiments provide
14 caster/recipient clips: Ray hit/miss, Chill hit/miss, Ice Knife hit/miss and
the wall-blocked burst. Five existing spell experiments add ten paired clips;
the three original Fire Bolt/Magic Missile references retain their single
original viewpoint. Each clip contains all four cameras in one pass.

The following are separate, partly overlapping test runs, not a summed count:

- Native Ice Knife/content/cold-effect/Sorcerer checks:46 passed, covering one
  paid cast, hit/miss burst, saves, crit/upcast, blocked recipients and lineage.
- Phase pages, sampling and ordinary animation:67 passed.
- New spell replay and contact timing:24 passed.
- Palette/drawing checks:51 passed; palette/NeuroClient-oracle/volley checks:
  106 passed.
- Retained-history compatibility, including older optional facts:9 passed.
- Broader media, area composition and architecture run:252 passed,3 failures
  in unchanged architecture files, itemized below.
- Affected implementation modules passed Pyright; touched tracked text passed
  `git diff --check`.

Contact frames were inspected from real four-camera clips for Ray, Chill and
Ice Knife, including the wall-blocked burst. The caster/recipient recordings
retain native outcomes and independent history playback. Existing point-spell
and Fireball contact frames were inspected after importing their current colors.
Passing replay checks does not claim acceptance of every artistic choice.

A fresh-process diagnostic on this mounted checkout measured about750ms for
imports and122ms for animation metadata, with zero decoded projectile bytes
after metadata loading. This is an import/metadata measurement, not a benchmark
of encounter construction or overall game startup. Palette work is prepared
before the hit; there are no source hashes or filesystem audits in playback.

### Explicit limits and separate findings

- Magic Missile's existing recipe has no enabled casting overlay. Its target
  flash uses the actual wine-colored palette; this unit did not invent a new
  casting effect.
- Chill uses the delivered demonic hand mesh. Its existing native NoHealing
  condition remains necrotic; this work adds neither persistent hand art nor
  cold/freezing semantics.
- Ice Knife's compound attack-plus-save numerical AI outcome profile is not
  represented by the current profile vocabulary. Native execution is complete;
  AI scoring is not falsely reported as a full model of both components.
- Sacred Flame, Shocking Grasp and Poison Spray remain manual art-review
  candidates in the source task, outside this approved delivery.
- [Chilled ground](CHILLED_GROUND_PROPOSAL_2026-09-20.md) is a reviewed proposal
  only. No new surface handler or automatic freezing behavior was implemented.

The broader architecture failures are the unchanged `server/world_contracts.py`
import of `SenseMode` from `dnd.core.senses` (two checks) and the existing duplicate
`EquipmentSlot` ownership in `game.condition_types` (one check). The palette
reviewer also encountered two existing `test_damage_animation.py` assertions
that require `SpatialChangeEvent` as an immediate parent where spike effects
now use `SpatialEffectChangeEvent`. Those files were unchanged by this unit.
They are recorded separately; this result does not claim a green whole-repo suite.

## Body-contact correction after visual review

The user reports Ray of Frost and Ice Knife striking too low compared with Fire
Bolt. Requested behavior: incoming hits read at the torso. Boundary: authored
projectile attachment in the final four-camera gameplay clips. Input: the same
saved hit/miss lineages. Expected output: the incoming contact rises on the
actual actor, with Ice Knife's subsequent area explosion remaining grounded.

The new recipes used the modular rig's `(64,72)` body attachment with no lift,
only15 reference pixels above the ground origin. Fire Bolt's older registration
combines a canvas offset and approach inset, yielding a higher apparent contact
that varies with direction. The bounded correction authors `liftY=-12` on the
two incoming body recipes, leaving the rig-relative scale and existing export
pivots in charge. It does not change the shared body socket, other spells,
native events or the copied Ice Knife burst recipe. This targets the same torso
region rather than copying Fire Bolt's legacy canvas-padding convention.

Anti-slop review: `weapon_antislop`; ECS review: `gore_ecs_review`.
Existing timing/area checks and saved-event clips provide the validation.
Both reviewers approved the data-only correction and its placement after the
burst recipe copy. **78 existing timing/area tests passed.** The
[corrected 12-clip gallery](http://127.0.0.1:8767/runs/20260920T093827Z-8a6af9/index.html)
passes across **1,426 four-camera frames**, with no media gaps and byte-identical
saved inputs to the preceding gallery. It covers paired Ray/Ice Knife hit/miss,
the wall-blocked burst and the two original Fire Bolt references. Inspected
approach/contact frames now meet the upper torso in all four views; Ice Knife's
ring stays at the feet. Endpoint-dependent flight times adjust naturally by
about15–17ms in these hit examples; native outcomes and authored speed stay intact.
