# Cleanup repair: in-engine acceptance evidence

The normal gallery contains **44 distinct observer clips from 24 scenarios**,
rendered from saved public input at 32 fps in all four camera corners. This is
coverage of the repaired contracts, not a claim that every spell has finished art.

[Open the combined gallery](http://127.0.0.1:8768/cleanup-20261003/acceptance/runs/20261003-final-acceptance/index.html).
The index references existing recordings without modifying their bytes. The
corrected push in `20261003T022901Z-4ba612` replaces the earlier push from
`20261003T021756Z-043126`; that obsolete clip is not an acceptance result.
Other inputs come from `20261003T021219Z-abe536` and
`20261003T023352Z-6e63a6` and `20261003T031028Z-5b9d74` under `.runtime/cleanup-20261003/acceptance/runs/`.

The full per-observer checks, public-input/trace hashes and state transitions are
in `.runtime/cleanup-20261003/validation/final/visual-evidence.json`. Extracted
frames inspected below are in the adjacent `frames/` directory. Video time is
quantized to 31.25 ms; exact boundary and reverse-seek assertions use the shared
sampler in the game tests. The event reviewer independently checked all 44 traces, 389 roots, 1,706 causal
nodes and 11,195 frames. Cold replay creates no live engine events; final-state
equality and camera actor/contact parity pass. Both jaw perspectives keep the
recorded landing after each hop ends.

| Contract | Recordings and inspected video times | Result |
| --- | --- | --- |
| Selected weapon and ordinary damage | `melee-hit` 1.1s; `ranged-hit` 1.4s; both observers | One body each, selected weapon retained, 7 slashing / 4 piercing with the corresponding HP. Existing contact/HP and history/latest checks pass. |
| Object attack loadout | `shared-attack-bow-melee`, `shared-attack-bow-unarmed` 2.2s; attacker/witness | Melee uses the melee body/weapon; unarmed uses hands rather than the previously held bow. Construction clips below cover actual destruction. |
| Retaliation | `damage-resolution-retaliation` 1.2s | Separate 4 bludgeoning and 5 fire results; 16/20 defender and 15/20 attacker. Causal IDs remain distinct even when authored contact times coincide. |
| Multiple sequential exposures | corrected `damage-resolution-push` 1.6s/2.5s; `damage-resolution-walk` 2.4s | No early final position. Push HP is 20→18→16→14, with one thunder and two piercing results; walking has two independent piercing results. Exact native order and reverse seek are separately asserted. |
| Hidden damage | `damage-resolution-hidden` 0.3s/0.5s | Only the permitted recipient is shown. Normal/temporary HP changes from 40+5 to 38+0 together at the authored commit; no hidden source or location is added. The HUD does not separately display temporary HP, so its equality is established by trace and boundary tests. |
| Condition lifetime | `control-blindness-overlap` 1.5s/4.5s and `control-blindness-saved` 1.5s; caster/recipient | Sustained glyph present while admitted, removed after the final overlapping source leaves; successful save leaves no glyph. Native veto/replacement tests cover effects that must never be admitted. |
| Interrupted movement | `walk-paralyzed` 1.5s and `walk-killed` 1.8s; mover/reactor | Opportunity reaction interrupts movement, commits condition/death and retains one body at the interrupted placement. All four cameras agree on state. |
| Existing trap avoidance hop | `mechanism-jaw-save` 1s/1.8s/3.8s/5.8s; traveler/witness | Successful saves still close the jaws, avoid damage and settle the actor at the recorded previous cell (2,2). The reset and second trigger retain one body and 80 HP. The unchanged landing regression and full jaw/forced-movement/resolution modules pass after the final timing correction. |
| Ground-to-ground Fly | `flight-ground-to-ground` 0.9s/2s; mover/observer | Real Move with Flying mode spends 15 feet and ends at ground position (6,3); ordinary idle resumes. The recording starts with Fly already active and uses the existing movement pose. It does not claim new flight/cast art. Cast, rejection, removal and shared-budget rules are native test coverage. |
| Open edge, wall and Globe | `cloud-loop-cloudkill` 7.2s; `cloud-boundary-cloudkill` 12.6s; `cloud-globe-fog-cloud` 5.5s; paired observers | Existing overhang, wall ordering and subjective Globe/cloud composition are preserved. Foreground cloud still occludes parts of the Globe. No cloud mask, art or occlusion policy was changed by this repair. |
| Wall of Fire formation | `wall-fire-formation-multiple` 1.6s/2.1s; four observer clips | Flames are present before the two formation victims lose HP. Both commit 20 fire at the same formation milestone; subsequent hot-side exposures remain separate native turn events. Safe-side HP remains 510. |
| Construction formation, break and dismissal | `construction-ice-break` 1.5s/3.6s/8.2s; `construction-stone-break` 6s/11s/15.7s; caster/recipient | Three committed sections form, one attacked section becomes debris while two remain, concentration removal clears the remaining construction. Object count is 0→3→2→0, with no phantom duplicate. Stone takes multiple actual attacks because its HP is higher. |
| Item identity and coating | `item-dagger-transfer-melee-main` 7s/12s, `item-dagger-transfer-melee-off` 12s | The orange coated dagger appears on the ground after dropping, leaves the ground on pickup, appears in the selected recipient hand and attacks once. The floor item disappears at 8.28125s; no copy remains. Palette replacement is unchanged. |
| Powered equipment | `item-warden-power-cycle` 1.3s/3.7s; wearer/witness | Real use adds Resistance/concentration, removal clears both. Owner-only resource facts consume to 0 and recharge to 1 on the same backpack UUID; witness receives neither charge fact. The existing HUD does not display inventory charges. The capture invokes the existing long-rest item hook, not a new rest implementation. |
| Call Lightning catalog capture | `call-lightning-area-repeat` 1.6s/5.8s; caster/target | Actual initial and repeat results are 12/6/12; the successful save takes half, the outside occupant stays at 108 HP, concentration clears at 8.5s. The existing repeat-action binding limitation below remains visible in the diagnostics. |
| Replay independence | All 44 public inputs and traces | Recording, terminal descendants, settled state, history/latest equality, four-camera parity and encoded-frame checks pass. Identity/milestone/reverse-seek tests and the passive fresh-process import tests cover the underlying event contract. |

## Existing artwork limits, retained explicitly

Both Call Lightning perspectives report the same two diagnostics for the granted
`action.spell.call_lightning.strike` root: **Authored action delivery is not bound**
and **recipient-free cast requires source-anchored media**. The original cast and
recipient damage lightning are visible; the targetless repeat action lacks its
own delivery binding. The event reviewer traced this to the pre-cleanup
`combat.py`/`animation.py` behavior and unchanged authored data, not the repaired
resolution ownership. The approved work excludes new art/bindings. These clips
pass replay/state checks; they are not reported as gap-free art acceptance.

Fly keeps its existing movement pose. The item-charge HUD and a full UI redesign
are outside this cleanup. Neither these recordings nor the repaired tests certify
the paused server's database/deployment behavior.
