# Weapon motion and review facing correction — September 20

The user caught a piercing critical playing a slash in the body-release review.
This is a real presentation defect: imported NeuroStudio `melee-critical`
(precedence 600, Attack2) overrides `melee-piercing` (400, Attack6). The global
`melee-elemental` variant (700, Attack4) has the same problem. Python faithfully
selects those rows; importing them did not establish their suitability.

Inspected the original NeuroClient recipe matcher and the actual 128px / 15-frame
body, weapon and Slash1/Slash2 sheets. Attack6 is a forward thrust; Attack1 a sweep;
Attack2 a turning swing; Attack4 an overhead strike. The Slash category is a slot
name, not a guarantee of a slashing attack: its Attack6 sheet is a thrust effect.

## Bounded correction

- Keep the imported source intact. Author one local set of existing typed
  `AttackVariant` records for normal, extra and opportunity attacks. Bind those
  three identities explicitly; reuse the existing selector and timeline.
- Remove global critical/elemental body overrides. As the user clarified,
  weapon-specific authored choices precede damage-type defaults. Piercing
  defaults to Attack6, bludgeoning to the authored blunt swing, slashing to the
  standard sweep or existing explicit heavy-weapon cleave. Match the blunt
  default by physical damage type; retain an explicit morningstar swing override
  (its spiked head pierces through a swung blow). The user requested an overhead
  dagger critical: bind only dagger criticals to Attack4, with its authored
  contact and no broad cleave wave. Constrain heavy cleaves to slashing.
- Keep ranged and offhand source records unchanged. Current local weapon
  matches use stable `sourceItemIds`; the optional field extends the original
  match vocabulary. Imported `sourceItemRefs` remain readable, but no obsolete
  content digest is invented for newly authored gear choices.
- Existing onHit/onMiss/onCrit layers retain contact anchors and choose their
  matching clip sheets. Existing element color token supplies injury-element
  color without replacing the motion. This changes physical trails from white
  to their authored neutral silver palette. No new timing or rule system.
- Add optional review-only starting facing records (actor's initial grid cell
  and look-at grid cell). Resolve once against visible retained actors; thereafter
  normal playback owns facing. Save them with review settings. No native facing,
  auto-turn-on-hit, advantage, flanking or Sneak Attack mechanics.
- Ordinary directed-release examples face each other. Add real normal/critical
  dagger rear-hit captures and a rotated example, from both participant views
  and all four cameras. Titles describe visual rear hits, not a new damage bonus.

## Verification and limits

Use actual weapon commands and round-tripped player lineages. Cover three physical
families across hit, miss and critical; physical weapons with an added native
energy damage component; original ranged and opportunity sequencing; contact HP
and body-release timing, including the deliberately different dagger critical
anchor. Inspect composed four-camera frames, not just profile IDs.
Review initial poses must persist on hit and through saved playback. Native state
and damage must be identical for frontal/rear presentation settings.

The root offhand clip is a left-arm strike (Attack5). There is no demonstrated
left-hand thrust set here; retain it and report that coverage limit rather than
reuse right-hand weapon sheets as a fabricated offhand solution. Fixed-creature
clip mappings and their already reported missing optional slash layers remain
explicit rig coverage, not a reason to rewrite their attacks.

## Independent review

Both independent reviewers approved the final implementation. Anti-slop review
caught the morningstar distinction before implementation; the plan incorporated
it. Final review approved stable item IDs, the authored dagger-specific override,
and the small shared binding rather than another animation system. ECS review
approved unchanged native facts/reduction and review-only initial poses, with
existing attack timelines retaining contact and reaction ownership. Neither
review substituted for composed-frame inspection.

## Authored records and delivery

Eight variant records are shared by the three attack behaviors. The additional
runtime work is the optional stable-item match predicate, decoding one typed
file, and replacing the imported variants for those explicit behaviors. There
are no weapon-name branches in the binder, sampler, compositor or backend.
Imported NeuroClient source bytes remain unchanged.

| Selection | Body clip | Contact frame | Detail |
| --- | --- | --- | --- |
| Dagger critical | Attack4 | 8 | Overhead; no broad cleave wave |
| Morningstar / soul-draining morningstar | Attack2 | 8 | Swing, including critical and necrotic weapon |
| Explicit heavy slashing weapons | Attack4 | 8 | Existing overhead cleave |
| Bludgeoning fallback | Attack2 | 8 | Existing turning swing |
| Piercing fallback | Attack6 | 7 | Thrust, including other piercing criticals |
| Remaining main-hand melee | Attack1 | 8 | Sweep |
| Offhand | Attack5 | 8 | Preserved authored left-arm strike |
| Ranged | Attack3 | release 8 | Preserved projectile delivery |

Ordinary review poses were changed in 34 saved input settings. Their player
sequences were compared directly before/after and are unchanged. Three new
native experiments add ordinary rear thrust, critical rear overhead, and a
rotated critical rear overhead; both real observer packets are retained.

Composed frames inspected: the original modular sheets; four-camera frontal
thrust, frontal overhead, and rear overhead at contact. The directional poses
persist through damage. Existing injury flashes temporarily recolor the victim;
that is the original hit feedback, not a new residue or facing effect.


## Validation result

- **68 tests passed** across attack animation, saved frontal/rear review,
  movement interruptions, body releases/geometry, equipment sequences and the
  complete animation-review export/replay suite (108.61 seconds). The expanded
  attack matrix includes real dagger, rapier, mace, morningstar, greatsword,
  flaming scimitar and soul-draining morningstar commands. Elemental trail color
  is checked alongside physical body motion. Ranged and opportunity tests pass.
- Affected modules and the new/expanded tests passed Pyright with zero errors.
- [40 saved-input clips](http://127.0.0.1:8767/runs/20260919T233559Z-0ebdbd/index.html)
  passed, comprising 3,506 four-camera frames, paired observer views, and no
  reported media gaps in this selection. The static review URL returned HTTP 200.
- The explicit identical-packet frontal/rear test proves unchanged lineages,
  per-frame native state and contact duration while the recipient keeps its
  authored starting facing. Rendering creates zero native events.

The earlier source-wide fixed-goblin decorative slash gap is outside this
selection; the offhand left-arm clip is preserved. This result does not assert
that every possible weapon/rig combination has distinct authored art. These
are review candidates with inspected contact frames, not presumed human approval.
