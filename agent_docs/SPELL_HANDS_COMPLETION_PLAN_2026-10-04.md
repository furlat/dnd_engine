# Complete spell hand effects — 4 October 2026

The human requires every spell to have magic casting/attack energy using its spell
palette. The earlier palette work left 28 canonical rows without a cast Magic
slot; that inventory was not a completion criterion.

Bounded correction:
1. Inspect the actual selected recipes. Add an enabled automatic Magic overlay to
   all 27 active modular casts that currently lack it. Reuse their current pose
   and installed matching sheet: Attack5/Magic2 and Special1/Magic3, following the
   existing selections rather than introducing a new aesthetic rule. Preserve
   release frames, sockets, speed, gameplay events, delivery media and timings.
2. Apply the same correction to those spells' independently authored effect
   variants. Existing repeat/reaction aliases inherit their owning recipe.
3. True Strike has no separate cast: its real child weapon attack already owns
   authored spell-colored charge overlays. Verify those rendered pixels and
   preserve its single attack and action economy; do not fake compliance with an
   enabled but unplayed parent cast. Any remaining actual visual gap must be
   reported and resolved in the existing presentation path. Preserve the exact
   shortsword/shortbow charges. Add one explicit modular-rig fallback per Attack1–6
   pose using existing original Magic2 sheets; exact weapon rows take precedence.
   Resolve automatic child overlays from the parent spell palette through the same
   layer palette function used by casting. No changes to weapon/attack selection.
   Copy only those six existing sheets into the private production release and
   installed assets, register their sourceSheet addresses, and record checksums.
4. Keep existing explicit artwork overrides and fixed creature gestures intact.
   No new art, backend changes, effect4/5 attack aura work or spell policy
   redesign in this correction.
5. Check all canonical spells at the resolved/rendered boundary, including the
   child-attack case; verify new layers' exact palette, nonempty preparation and
   alpha preservation. Run existing hand-palette, casting, True Strike and relevant
   presentation checks. Inspect actual in-engine playback representatives. Update
   inventory/report and the explorer's read-only mapping so it cannot keep stating
   that completed spells have no effects.

Independent anti-slop and anti-OOP/ECS reviewers inspect the plan and final delta.
No external chat communication. No commit requested. Changes must be compared
against this turn's starting files because the shared tree contains prior work.
