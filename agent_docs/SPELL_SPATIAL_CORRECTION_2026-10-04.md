# Spell spatial rendering correction

The complete active repair plan is now
[SPELL_PRESENTATION_REPAIR_PLAN_2026-10-04.md](SPELL_PRESENTATION_REPAIR_PLAN_2026-10-04.md).
This document retains the first diagnostic evidence and early review context.

Scope: the reported Magic Missile trajectory/depth failure, Fireball tile-shaped
cuts, Sleep's flat lower cut, and Shocking Grasp's inconsistent lightning palette.
Use the saved gameplay inputs; preserve the 298-clip export and do not regenerate
it. No gameplay, event, action-economy, condition or artwork changes.

Evidence from the actual recorded frames:

- Magic Missile's inverse camera rotation treats the Bézier displacement as an
  absolute map position. Cameras 1–3 acquire 63-cell offsets in painter contacts.
- At Fireball's 2.250-second frame, affected-cell admission retains only
  4,848/9,424 smoke pixels and 2,158/4,090 additive pixels. Removing that stencil
  restores the round blast. Real supports and barriers remain separate tests.
- At Sleep's 1.656-second frame, the same-level floor mask removes 14,263 cloud
  pixels. Removing admission has no effect. The original cloud has a soft fringe
  extending below its registered ground plane; it must not become a hard cut.
- Shocking Grasp's current palette is yellow; Lightning Bolt and Chain Lightning
  share a blue/cyan/bright palette. The automatic hands inherit those values.

Implementation:

1. In the existing projectile contact calculation, inverse-rotate curve offsets
   as vectors by subtracting the inverse-rotated zero. Keep the actual visual
   curve, measured sockets, elevation and clocks unchanged.
2. Preserve the observation-time admission grant: projected affected cells also
   carry what this observer witnessed. For spherical cast volumes, reuse the
   existing `sphere_field_owners` mapping before permission lookup. Decorative
   exterior borrows its stable declared edge owner; undisclosed interior cells
   remain undisclosed. Use the world's existing bounds, never the observed subset
   to redefine that edge. This removes the geometric cell-shaped cut without
   deleting permission checks or inventing another observation event. Continue
   continuous propagation against received finite barriers (`resolved_occupancy`
   must no longer bypass it for transient casts), actual silhouette occlusion
   and protected-volume exclusions. Keep authoritative affected cells, staged
   destruction topology and clump selection intact. Persistent clouds unchanged.
3. Add one explicit support-clipping policy to the existing authored phase and
   media-track records: physical (default) or raised (ignore supports at/below
   the registered base including vertical translation, retain higher/sloped terrain).
   Select raised for Sleep's ground
   cloud only. Do not disable real falling-particle floor clipping globally.
4. Match Shocking Grasp's owning palette to the existing lightning palette.
   Hands/effects inherit it automatically. Any main-media recoloring uses the
   existing exact palette-replacement path, never RGB multiplication.
5. Add regression checks at the existing projection/draw boundaries, with actual
   media and all four cameras. Recheck wall/door, Globe exclusion, below-floor
   Ice Knife and staged breach behavior. Inspect corrected recorded frames and
   export only the small set of reported cases from their unchanged inputs.

Reviews: independent anti-slop and anti-OOP/ECS review of this bounded solution
before implementation; final source and evidence review after verification.
Grease is a question about an existing clip, not an authorized rules rewrite.

Review correction: the first proposed blanket removal of transient admission
was rejected by the ECS reviewer because it also carries subjective sight. The
amended solution above reuses the already-established decorative ownership
policy and retains the exact grant. Lightning's third palette stop is amber.

## Additional reported casting/condition corrections

The user identified the general placeholder-palette problem and requested checks
of the same failure throughout the loaded recipes. Ten owners have all-white
cast palettes; match their existing main media/material colors while retaining
neutral white selectors on already-colored condition media. Warm/chill Fire
Shield and radiant/necrotic Spirit Guardians must select from existing received
energy facts, through a small typed authored palette selector, never names or
logs. No native event/rule change.

Produce Flame must keep its actual hand attachment in every direction. Inspect
and complete missing measured pose sockets; do not borrow another body pose.
Creation and hurl remain separate existing action identities and receive explicit
authored casts if needed, using existing effectDrafts/actionDeliveries.

Bestow Curse finite touch art is ground-registered and must attach to ground,
while head marks retain their measured head clearance. Retiming must join the
touch/contact/condition clock and resisted cue. Fear's existing Frightened
visual, Hold Person connection speed/size, and Hypnotic Pattern rotation/ground
lifetime are reported corrections to inspect and implement from existing art.
All six wall spells use the requested ground-strike motion, with explicitly
authored Effect1/2/3 diversity at stronger levels. Preserve main Godot VFX,
actual eight-direction sockets and fair progression. No random runtime choice.

The independent anti-slop and ECS reviewers review these amendments and final
source/pixel evidence. Export only affected native saved-input recordings in the
standard gallery; original 298 clips remain unchanged.

## Formation and latest feedback

Keep two presentation dates: formation artwork starts at delivery; the existing
received spatial/world observation commits at an authored formation milestone.
Add the optional milestone to the existing spatial and construction bindings,
not a new registry or native event. Both physical walls and maintained fields
must retain witnessed pending artwork through existing lifetimes without
inserting its barriers, visibility or lighting into displayed state early.
Cold acquisition remains a sustain; seek must reproduce the two dates. Review
cloud, light and physical-wall evidence immediately before/at that milestone.

Eyebite delivery needs shorter travel; its Asleep pose must use the same shared
sleep/unconscious pose as ordinary Sleep. Inspect damage transition overlap for
Scorching Ray and existing hit/blood feedback for Power Words. Reserve the
Attack5 skeleton accent for Blight; replace other uses with accepted accents
suited to their chosen motion. Keep every correction visual: no new damage,
condition or action-economy rules.

## Additional review notes retained

- Sunburst: same reported admission cuts as Fireball; include its actual media.
- Sunbeam / Lightning Bolt / Chain Lightning: verify shared hand origin, timing
  and stability throughout delivery after motion changes.
- Lightning family: remove amber from cast accents to match main blue artwork.
- Dimension Door: emergence begins as ingress completes; shorten the authored
  concealed interval rather than changing relocation rules.
- The original 298 media files remain archived; corrected evidence must identify
  refreshed native inputs separately from unchanged-input rendering replays.
