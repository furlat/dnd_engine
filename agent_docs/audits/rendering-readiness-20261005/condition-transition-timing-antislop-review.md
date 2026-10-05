# Condition transition timing evidence review

Independent source review of compile_condition and bind_condition_body in game/condition_animation.py.

Verdict: accepted for the bounded producer annotation. Existing start, complete, alpha-end and body-transition calculations are unchanged. Event UUID owns each occurrence, while membership remains keyed by condition UUID; repeated applications are not collapsed into a behavior-level timing owner. The caller still commits membership at transition.start_ms. Body extension preserves alpha_end_ms at the prior completion and records a maximum against the prior completion producer.

Completion operands cover the same gated alpha, rig appearance, body ramp and transition effect durations used in the existing maximum. Each contributing effect retains its own ID. Activated/consumed removals keep their existing media suppression gate. Updated and missing-recipe conditions remain zero-duration and do not invent animation durations. Floating feedback does not prolong joins.

No callback, phase or schedule regression found. The input admission clock is supplied by the existing parent binding; this annotation does not independently establish which parent cause selected it. Authored-field paths are local explanatory labels interpreted alongside the condition fact and selected recipe, not a new lookup registry. Tests and projection wiring remain root responsibilities; no whole-plan completion claim.
