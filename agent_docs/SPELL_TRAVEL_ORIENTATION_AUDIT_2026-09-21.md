# Travelling spell orientation — September 21

The user asked whether any other spell has Fireball's sideways-flight problem.
The observable contract is that directional travel artwork follows its actual
projected trajectory, while floor explosions keep their authored floor alignment.
Contacts, paths, targets, clocks and gameplay facts must remain unchanged.

## Findings and bounded correction

All eleven active recipes with sprite travel enable fine rotation. Replaying
twenty saved native-event narratives exposed one additional recipe error:
**Magic Missile** used `directionSource: target_vector` on its curved darts.
That retained the initial curve tangent throughout travel, producing up to
61.419 degrees of heading error near arrival in the recorded repeated-target cast.

Only its selected recipe now uses the existing `tangent` mode. The executor
already selects directional rows and residual rotation from the moving curve.
No schema, renderer, importer or backend change is required. The same directional
Rune Dart lifecycle continues into the body impact with its arrival heading;
this is not a floor explosion. Its centered sprite registration keeps the curve
and target contact fixed as the image rotates.

Fireball retains its travel-only override and unrotated floor explosion. Other
spell records, including Fire Bolt's authored contacts, remain unchanged.

## Scope and evidence

The diagnostic samples real saved sequences at five travel positions from all
four camera corners. It includes repeated/split targets, misses, raised contacts
and cannon shots. It compares projected row direction plus residual rotation
against finite differences of the actual projected path, rather than inspecting
the recipe flag alone.

| Spell | Sampled orientations | Result |
| --- | ---: | --- |
| Acid Splash | 40 | Aligned |
| Eldritch Blast | 120 | Aligned |
| Fire Bolt | 120 | Aligned |
| Fireball | 80 | Aligned after the preceding travel-only repair |
| Guiding Bolt | 40 | Aligned |
| Ice Knife | 40 | Aligned |
| Magic Missile | 120 | Initial heading retained before; aligned after correction |
| Poison Spray | 40 | Aligned |
| Ray of Frost | 40 | Aligned |
| Sleep | 40 | Aligned |
| Web | 60 | Aligned |

All 740 computed orientations agree after the correction, within floating-point
precision. This proves the sampled motion/row contract, not pixel-perfect asset
calibration or every possible scene. Anchored spells and floor effects have no
travelling sprite and are outside this particular defect. The Magic Missile
atlas was also inspected: its travel has directional tails and its impact is
directional body media. Animated particles vary around their row axis; this did
not justify new calibration metadata or edits to the artwork.

The one-off diagnostic and before/after results are local artifacts under
`.runtime/spell-orientation-audit/`. They are not a runtime audit, new testing
framework or asset-validation gate. Two obsolete native input archives (height
and repeated missiles) needed recapture through their ordinary engine commands
because the current event schema requires temporary-HP grant ownership. Their
new saved inputs were then reused for the before/after review; no event bytes
were patched to manufacture compatibility.

## Regression coverage and review

The selected Magic Missile fixture uses a real compiled A/B/A delivery. Twelve
cases cover both curve signs and four cameras, require changing heading to agree
with actual movement, and preserve the legacy trajectory, contacts, delivery
state and clock. The directional impact retains the arrival heading. All twelve
failed before the one-line data correction.

The legacy `target_vector` test now explicitly selects that mode, preserving its
existing contract independently of the shipping spell recipe. Existing Fireball
checks continue to cover mage/cannon travel and its unrotated ground explosion.

Anti-slop and anti-OOP/ECS reviews approved the existing-field correction and
rejected the need for a renderer branch, new schema or global behavior change.
The focused suite passes **99 tests** across authored projectiles, tangent
projectiles, device animation and animation-space contracts. Scoped Pyright
reports zero errors. The final anti-slop review found no actionable issue.

## Clip review

The [seven-clip review](http://127.0.0.1:8767/runs/20260921T085827Z-954b01/index.html)
includes Magic Missile's caster and both recipients, plus Fire Bolt and Fireball
from both participants, with four cameras per clip. All 1,101 encoded frames
pass the existing checks and there are no presentation gaps. The
[before-correction missile clips](http://127.0.0.1:8767/runs/20260921T085735Z-ff5aa5/index.html)
remain available for comparison. Travel frames were inspected side by side.

All three before/after missile inputs are byte-identical; retained lineages and
presentation clocks match. Initial/final gameplay states match after excluding
the initial sensory cache's process-local Python hash, which changes between
processes. No input or gameplay observation was changed for this comparison.
Human approval of the revised clips remains pending.
