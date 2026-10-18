# OPR Estimator Design (`opr_core.py`)

Research-only module. Never imported by `policy.py` or any deployed
entrypoint. Consumes hidden world fields at analysis time only.

## API

- `fit_score(truth_a, truth_b, variant)` — kit._prob fit term (+1 equal,
  -0.5 mismatch; shift variant uses SHIFT_WEIGHTS).
- `drift_term(variant, day)` — -0.5 iff drift variant and day >= 35.
- `z_accept` / `q_second` — acceptance and second-intent logits.
- `date_deadline_prob(variant)` — exact finite enumeration; cached; 1.0 for
  every non-'delayed' variant (max date offset 21 <= 30).
- `p_msmi_conditional_g(m_a, m_b, variant, day, g)` — full chain:
  ra*sb(z_a)*rb*sb(z_b) * D * 0.78 * prod_i[ra_i*(3/5)*sb(q_i)].
- `p_msmi(m_a, m_b, variant, day, n=8001)` — E_g under N(0, 0.45^2) via
  midpoint rule on z in [-7, 7], Richardson-extrapolated (O(h^4)).
  Invariants hoisted out of the quadrature loop. Deterministic; tail mass
  beyond 7 sigma < 1.3e-12. Cross-checked in tests against independent
  adaptive Simpson to < 1e-10.
- `simulate_outcome(seed, a, b, day, variant, members)` — exact mirror of
  kit.Simulator.advance draw order for one introduction; returns realized
  MSMI and internals. Used for stream re-derivation (D-A).
- `rand_for` — mirror of kit.rand_for (sha256-keyed stream).

## Why the probability is exact (not estimated)

Every introduction draws from its own `random.Random(sha256(seed|a|b|day))`.
Conditional on world hidden state, introductions are mutually independent;
within one introduction, the only coupling is the shared latent
g ~ N(0, 0.45^2) driving both acceptance logits and both second-intent
logits. All other draws (responses, delays, happened, second answers) are
independent Bernoulli/uniforms, so the chain probability factorizes up to
the one-dimensional integral over g, which quadrature evaluates to < 1e-10.

## Prohibitions encoded in the module header

No deployed-policy import; hidden fields are analysis-time only; stdlib
only; no edits to kit.py / policy.py / evaluate.py / Dockerfile.
