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
Record final recommendations and resulting validation here.
