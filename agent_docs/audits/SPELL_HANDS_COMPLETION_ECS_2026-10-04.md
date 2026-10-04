# Spell hands completion — ECS / import-DAG review, 4 October 2026

**Runtime, data and presentation contract approved within the amended plan.**
No ECS, dependency, native-event or documentation blocker remains in the
inspected implementation. This is not acceptance of the separate condition
audit or of gameplay recordings still being prepared.

Compared the four runtime files and affected authored JSON against this turn's
`.runtime/spell-hands-completion-20261004/before/` snapshots. Unrelated existing
checkout changes were excluded from this review.

- The runtime change extends the existing passive `ChildAttackPose` with an
  optional weapon qualifier. `bind_attack` selects the exact weapon row first,
  then a fallback matching the same rig and actual clip. Existing ambiguity and
  destination-slot checks remain. No spell-name case, registry, manager or
  secondary attack/cast executor was added.
- Choreography obtains the existing parent spell's palette through its retained
  causal relationship and prepares child layer values using the same
  `_layer_palette` function as ordinary casts. Explicit charge artwork remains
  unchanged. The actual attack still owns profile, weapon, outcome, contact,
  projectile and timing; True Strike's separate parent cast remains disabled.
- The import DAG is unchanged: choreography calls the existing animation
  module, which consumes passive animation types. No new mechanics dependency,
  engine field, event, late import or reflective dispatch was introduced.
- Semantic JSON comparison found exactly 43 additions: 31 cast `weaponGlow`
  records (27 canonical plus four Bestow Curse variants), six source resource
  bindings, and six True Strike fallback rows. Existing cast settings, delivery,
  timing, explicit overrides and the two exact True Strike pose rows remain
  unchanged.
- Current production-loader inspection finds 126 canonical spells, including
  125 enabled casts with Magic hands and disabled-parent True Strike. No enabled
  selected recipe lacks the required hand layer. All six action/reaction aliases
  have values equal to their owning recipe after loading. Modular child attack
  clips Attack1–6 are covered; the separate PhysicalGesture attack profiles are
  explicitly fixed-Goblin profiles and do not receive these modular fallbacks.
- The six fallbacks remain qualified to `neuroclient.modular`; fixed-rig
  gesture substitution is unchanged. Ordinary new cast layers reuse the
  existing matching Ray of Frost/Haste source geometry with automatic colors.
  No category was assigned to an unsupported extra rig slot.
- Independently compared each of the six copied Magic2 sheets against the
  original, installed copy and private production copy. All SHA-256 values
  match `asset-receipt.json`: six unchanged originals, 1,496,267 bytes total.

Reviewed the added whole-catalog palette/alpha/preparation check and the
longsword/heavy-crossbow hit/miss cases. The latter compare actual four-camera
actor pixels while preserving ordinary attack timing and appearance, and the
existing exact shortsword/shortbow charge tests are unchanged. The focused
`tests.log` reports **79 passed in 60.53 seconds**. This reviewer read the test
source and completed log; no tests or gameplay renders were executed here.
The completed scoped `types.log` also reports **0 errors, 0 warnings and
0 informations**.

## Documentation closure

`game/data/PRESENTATION_CONTRACT.md`, in the `StudioSpellDraft.childAttack`
paragraph, now correctly describes optional `weaponCategory`, exact-row
precedence over explicit rig/clip fallbacks, same-specificity ambiguity checks,
parent-spell automatic palettes, and the existing Magic2 Attack1–6 sheets.
The correction matches the inspected implementation and closes the sole
documentation follow-up. Unmatched rigs/clips remain explicitly reported.

Only this review receipt was written by this reviewer. No production changes
or external chat access occurred.
