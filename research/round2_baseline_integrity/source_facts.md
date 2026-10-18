# Score-Direction Source Facts (bi1)

Generated 2026-10-13 16:00:15 by scripts/bi1_source_facts.py. Every excerpt is the
executable text at the cited lines; pattern assertions fail the run
if the code moves. Verdict questions follow analysis_plan.md sec.4.

## kit.baseline_match

- File: `kit.py`
- Classification: **CORRECT**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | Higher raw score = better (score = count of SOFT fields observed non-None on both sides and equal). |
| 2. Maximize or minimize the intended score? | No global objective: greedy take-while-free in descending score order over the whole day edge list. |
| 3. Score negated into a maximizing solver? | (-score, key) is only an ASCENDING sort key; the value is never handed to a maximizer. Direction correct. |
| 4. Unknown / mismatch / match scoring? | None on either side contributes 0 - neither match nor penalty. Observed mismatch 0, observed match 1. |
| 5. Tie resolution? | sorted() on the canonical tuple key (u, v) ascending. |
| 6. Sequential greedy or fixed-k global? | SEQUENTIAL greedy, unconstrained cardinality (not fixed-k). |
| 7. Output matches the report? | Matches its use as the official control everywhere (tests, evaluate.py, tournament, e3, round2). |

Excerpts:

`kit.py`

```
 210| def baseline_match(state):
 211|     members=[m for m in state['members'] if m['available']]
 212|     past={tuple(sorted((i['user_a'],i['user_b']))) for i in state['introductions']}
 213|     edges=[]
 214|     for a,b in itertools.combinations(members,2):
 215|         key=tuple(sorted((a['member_id'],b['member_id'])))
 216|         if key in past or eligibility(a,b)['status']!='feasible':continue
 217|         score=sum(a['fields'].get(k) is not None and a['fields'].get(k)==b['fields'].get(k) for k in SOFT)
 218|         edges.append((-score,key))
 219|     used=set();out=[]
 220|     for _,pair in sorted(edges):
 221|         if not used.intersection(pair):out.append(list(pair));used.update(pair)
 222|     return out
```

## n01.allocate

- File: `research/next_method_search/n01_autopsy.py`
- Classification: **CORRECT**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | Same as kit: higher count = better; pairs identical to the control (docstring + sorted-edge take loop). |
| 2. Maximize or minimize the intended score? | Sequential greedy for pairs; edges metadata in the (-score, key) sort-key convention. |
| 3. Score negated into a maximizing solver? | Negation present but consumed ONLY by sorted() inside allocate; the defect appears when a later writer un-negates and a further consumer re-negates (see s1/fc). |
| 4. Unknown / mismatch / match scoring? | Identical to kit (both-non-None and equal). |
| 5. Tie resolution? | Canonical key ascending, identical to kit. |
| 6. Sequential greedy or fixed-k global? | Sequential greedy replica. |
| 7. Output matches the report? | Report claims pairs identical to control; code supports it. |

Excerpts:

`research/next_method_search/n01_autopsy.py`

```
 137| def allocate(state):
 138|     """kit.baseline_match line-for-line (kit.py L210-222) plus edge metadata.
 139| 
 140|     Returns (pairs, edges, degree, used): pairs identical to the control
 141|     action, edges as (-score, key), endpoint degree counter, used endpoints.
 142|     """
 143|     members = [m for m in state['members'] if m['available']]
 144|     past = {tuple(sorted((i['user_a'], i['user_b'])))
 145|             for i in state['introductions']}
 146|     edges = []
 147|     for a, b in itertools.combinations(members, 2):
 148|         key = tuple(sorted((a['member_id'], b['member_id'])))
 149|         if key in past or eligibility(a, b)['status'] != 'feasible':
 150|             continue
 151|         score = sum(a['fields'].get(k) is not None
 152|                     and a['fields'].get(k) == b['fields'].get(k) for k in SOFT)
 153|         edges.append((-score, key))
 154|     degree = Counter()
 155|     for _, key in edges:
 156|         degree.update(key)
 157|     used = set()
 158|     pairs = []
 159|     for _, key in sorted(edges):
 160|         if not used.intersection(key):
 161|             pairs.append(list(key))
 162|             used.update(key)
 163|     return pairs, edges, degree, used
```

## s1_opportunities day_edges writer

- File: `research/round2_decision_ceiling/scripts/s1_opportunities.py`
- Classification: **CORRECT_BUT_STALE_DOCUMENTATION**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | Writes day_edges entries as [-(-score), key] = [+count, key]: the stored first element is a POSITIVE count (previously verified against feat.pair_score). |
| 2. Maximize or minimize the intended score? | Serialization only. |
| 3. Score negated into a maximizing solver? | This line UN-negates n01's sort key. Any consumer that applies -e[0] believing it still sees a negated score therefore NEGATES the count. |
| 4. Unknown / mismatch / match scoring? | n/a (writes counts produced by the kit-equivalent formula). |
| 5. Tie resolution? | n/a. |
| 6. Sequential greedy or fixed-k global? | n/a. |
| 7. Output matches the report? | ce_common.py L335 docstring still says "(neg_score, key) from n01.allocate" - STALE, contradicts this executable line; this stale doc is the root cause of the downstream defect. |

Excerpts:

`research/round2_decision_ceiling/scripts/s1_opportunities.py`

```
  50|                 n_intros_so_far=ctx['n_intros'],
  51|                 n_feedback=ctx['n_feedback'],
  52|                 ask_budget=ctx['state']['ask_budget_remaining'])
  53|             day_rows.append(dict(seed=_s, variant=_v, day=ctx['day'],
  54|                                  edges=[[-e[0], list(e[1])] for e in ctx['edges']],
  55|                                  pairs=[list(p) for p in ctx['pairs']],
  56|                                  metrics=metrics, day_ctx=ctx['day_ctx']))
  57|         c.replay_world(seed, variant, per_day=per_day, follow_up=False)
  58|     c.write_jsonl(c.OUT / 'day_edges.jsonl', [
```

## fc_selectors F1-SCORE + solve_exact_k

- File: `research/round2_fixed_cardinality/scripts/fc_selectors.py`
- Classification: **DIRECTION_BUG**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | Intended: higher baseline count = better (the report describes F1-SCORE as "exact-k max of baseline soft-match count"). |
| 2. Maximize or minimize the intended score? | solve_exact_k MAXIMIZES the sum of the weights it is given (best_val updated on wsum >). |
| 3. Score negated into a maximizing solver? | raw stores POSITIVE counts (s1 writer), yet weights = -e[0]: the maximizer therefore MAXIMIZES -count = MINIMIZES the count. Double-negation defect at fc_selectors.py L123. |
| 4. Unknown / mismatch / match scoring? | Count semantics inherited from the kit formula: unknown -> 0. |
| 5. Tie resolution? | Lexicographically smallest optimal matching (deterministic); branch-and-bound order (-weight, canonical edge). |
| 6. Sequential greedy or fixed-k global? | GLOBAL fixed-cardinality exact-k optimization (by design). |
| 7. Output matches the report? | FAILS Q7: report says "max of baseline soft-match count"; actual output minimizes it (81 < greedy 90 < maximizer 88 is the measured fingerprint). |

Excerpts:

`research/round2_fixed_cardinality/scripts/fc_selectors.py`

```
 121|         # ---- exact-k arms --------------------------------------------------
 122|         weightings = {
 123|             'F1-SCORE':  [-e[0] for e in raw],
 124|             'F2-SOFT':   [oof[(key[0], key[1], key[2], e[0], e[1])]['F2_soft_state']
 125|                           for e in edges],
 126|             'F3-OBSERV': [oof[(key[0], key[1], key[2], e[0], e[1])]['F4_full_legal_observables']
 127|                           for e in edges],
 128|             'F5-ORACLE': [lab[e] for e in edges],
 129|         }
 130|         selected = {}
 131|         for arm in ('F1-SCORE', 'F2-SOFT', 'F3-OBSERV', 'F5-ORACLE'):
 132|             if kt == 0:
 133|                 sel_i, obj, nodes, failed = (), 0.0, 0, False
 134|             else:
 135|                 sel_i, obj, nodes, failed = solve_exact_k(edges, weightings[arm], kt)
```

`research/round2_fixed_cardinality/scripts/fc_matching.py`

```
  29| def solve_exact_k(edges: Sequence[Tuple[str, str]],
  30|                   weights: Sequence[float],
  31|                   k: int,
  32|                   ) -> Tuple[Optional[Tuple[int, ...]], Optional[float], int, bool]:
  33|     """Max-weight vertex-disjoint set of EXACTLY k edges.
  34| 
  35|     Returns (edge_indices, objective, nodes_visited, failed).
  36|     edge_indices are indices into the input `edges` sequence.
  37|     failed=True means the node limit was breached, in which case the objective
  38|     is None and the caller MUST report the failure.
  39|     """
  40|     n = len(edges)
  41|     if k == 0:
  42|         return (), 0.0, 0, False
  43|     if k < 0 or n == 0 or k > n:
  44|         return None, None, 0, False          # infeasible
  45| 
  46|     # ---- pass 1: find the optimal objective by branch and bound -------------
  47|     order = sorted(range(n), key=lambda i: (-weights[i], _canon(edges[i])))
```

## mo_validate F1-SCORE reproduction

- File: `research/round2_missed_oracle/scripts/mo_validate.py`
- Classification: **DIRECTION_BUG (faithful reproduction)**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | Intended same as fc F1-SCORE (frozen reproduction). |
| 2. Maximize or minimize the intended score? | Exact-k maximizer (imported from fc_matching). |
| 3. Score negated into a maximizing solver? | Same -e[0] on positive counts: reproduces the defective arm faithfully (P_F1 = 81 matches fc). |
| 4. Unknown / mismatch / match scoring? | Same as fc. |
| 5. Tie resolution? | Same solver, lex-smallest. |
| 6. Sequential greedy or fixed-k global? | Global fixed-cardinality exact-k. |
| 7. Output matches the report? | Reproduces the frozen (defective) arm as registered; the reproduction is correct even though the arm itself is direction-defective. |

Excerpts:

`research/round2_missed_oracle/scripts/mo_validate.py`

```
 168|         edges = [tuple(e[1]) for e in raw]
 169|         kt = len(d['pairs'])
 170|         lab = labels[k]
 171|         weights = {
 172|             'F1-SCORE':  [-e[0] for e in raw],
 173|             'F2-SOFT':   [score_of[(k[0], k[1], k[2], e[0], e[1])]['F2-SOFT'] for e in edges],
 174|             'F3-OBSERV': [score_of[(k[0], k[1], k[2], e[0], e[1])]['F3-OBSERV'] for e in edges],
 175|             'F5-ORACLE': [lab[e] for e in edges],
 176|         }
```

## gr_common weight_g1f / weight_g1m

- File: `research/round2_goal_rule/scripts/gr_common.py`
- Classification: **CORRECT (defect reproduced only as a labelled series)**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | day_edges values are positive counts (parameter name "neg_scores" is stale but the values are positive). |
| 2. Maximize or minimize the intended score? | Both weights feed solve_exact_k (maximizer): g1f = -count MINIMIZES (frozen reproduction, 81); g1m = +count MAXIMIZES (spec-faithful, 88). |
| 3. Score negated into a maximizing solver? | g1f keeps the historical defect on purpose; g1m removes it. Both series are published side by side (Amendment 1). |
| 4. Unknown / mismatch / match scoring? | Same count semantics for both. |
| 5. Tie resolution? | Same solver. |
| 6. Sequential greedy or fixed-k global? | Global fixed-cardinality exact-k. |
| 7. Output matches the report? | Matches the report: G1f labelled frozen reproduction, G1m labelled corrected maximizer. |

Excerpts:

`research/round2_goal_rule/scripts/gr_common.py`

```
 168|     return 0.0
 169| 
 170| 
 171| def weight_g1f(neg_scores):
 172|     """Bit-exact frozen F1-SCORE weight (fc_selectors.py:123,
 173|     mo_validate.py:172). day_edges stores POSITIVE counts
 174|     (s1_opportunities.py:54), so this weight MINIMIZES total match
 175|     count - the Amendment 1 discrepancy."""
 176|     return [-float(x) for x in neg_scores]
 177| 
 178| 
 179| def weight_g1m(neg_scores):
 180|     """Spec-faithful baseline (Amendment 1): MAXIMIZE the total number
 181|     of matching observed soft fields."""
 182|     return [float(x) for x in neg_scores]
 183| 
 184| 
```

## policy.py A+C scoring, floor, candidates

- File: `policy.py`
- Classification: **CORRECT**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | Higher is better: model score = sigmoid(baseline + tree sum) in (0,1); rule_score feasible 1.0 > needs_clarification 0.5 > infeasible -1, +0.01 per soft match. |
| 2. Maximize or minimize the intended score? | Per-day approximate MAX-score matching (greedy seed + up to 8 strictly-improving moves), floor-gated; fallback rule-greedy. |
| 3. Score negated into a maximizing solver? | -score / -rule_score appear only as descending sort keys; never passed as maximization weights. Direction correct. |
| 4. Unknown / mismatch / match scoring? | Rule branch: unknown/declined fields do not count as soft matches (0 contribution); model branch uses observed soft-state features. |
| 5. Tie resolution? | (-score, a, b) then canonical (a, b) output order; deterministic. |
| 6. Sequential greedy or fixed-k global? | Full-sequential per-day policy (not fixed-k, not a replica of per-pair sequential greedy - a documented design difference). |
| 7. Output matches the report? | policy_ac.py forces mode=ac; container default covers it. Matches spec R5 description. |

Excerpts:

`policy.py`

```
 415| def rule_score(state, a_id, b_id):
 416|     """Deterministic observable heuristic (fallback + T1 tie ordering): availability >
 417|     feasibility > soft agreement. Never raises; NaN-guarded."""
 418|     by_id = {m['member_id']: m for m in state['members']}
 419|     a, b = by_id.get(a_id), by_id.get(b_id)
 420|     if a is None or b is None or not a['available'] or not b['available']:
 421|         return -1.0
 422|     status = eligibility(a, b)['status']
 423|     if status == 'infeasible':
 424|         return -1.0
 425|     score = 1.0 if status == 'feasible' else 0.5
 426|     try:
 427|         f = pair_features(state, a_id, b_id, state.get('day', 0))
 428|         v = f.get('soft_match_count')
 429|         if v is not None and v == v:          # NaN guard: nan != nan
 430|             score += 0.01 * float(v)
 431|     except Exception:
 432|         pass
 433|     return score
 434| 
 435| 
 436| def _rule_greedy(edges):
 437|     """Deterministic no-floor greedy fallback: sort by (-score, a, b), disjoint pairs.
 438|     ONE member pool: occupancy is a single 'used' set (either endpoint consumes a member)."""
 439|     picked, used = [], set()
 440|     for a, b, s in sorted(edges, key=lambda e: (-e[2], e[0], e[1])):
 454| def max_score_matching(nodes, edges, floor):
 455|     """Greedy seed by (-score, a, b) + up to 8 deterministic strictly-improving local moves.
 456| 
 457|     GENERAL GRAPH: one member pool - a member may be either endpoint of any edge.
 458|     Occupancy is a single partner map (node -> (other, score)); edge lookups use
 459|     canonical keys _canon(a, b) so orientation never matters; a member is never in
 460|     two kept edges (kit.advance raises 'overlapping allocation' otherwise).
 461|     Returns unique (a, b, score), every score >= floor, sorted by (a, b).
 462|     All candidate edges below floor -> [] (conservative wait, spec section 9).
 463|     """
 464|     if not edges:
 465|         return []
 466|     valid = set(nodes)
 467|     above = sorted((e for e in edges
 468|                     if e[0] in valid and e[1] in valid and e[0] != e[1]
 469|                     and e[2] >= floor),
 470|                    key=lambda e: (-e[2], e[0], e[1]))
 471|     if not above:
 472|         return []
 473|     score_of = {}
 474|     for a, b, s in above:                  # canonical key; first in (-score, a, b) wins
 558| def ac_match(state):
 559|     """Floor-gated approximate max-score global matching (spec sections 5.2, 9).
 560| 
 561|     Returns sorted [[a, b], ...] - the exact shape evaluate.validate_response accepts.
 562|     Candidate pairs: available members, kit-feasible, never previously introduced.
 563|     Model path: floor-gated max_score_matching. Fallback (blob missing/corrupt or
 564|     scoring exception): deterministic no-floor rule greedy (spec T8).
 565|     """
 566|     try:
 567|         members = sorted((m for m in state['members'] if m['available']),
 568|                          key=lambda m: m['member_id'])
 569|         if not members:
 570|             return []
 571|         past = _past_pairs(state)
 572|         cand = []
 573|         for i, a in enumerate(members):
 574|             for b in members[i + 1:]:
 575|                 key = tuple(sorted((a['member_id'], b['member_id'])))
 576|                 if key in past:
 577|                     continue
 578|                 if eligibility(a, b)['status'] != 'feasible':
 579|                     continue
 580|                 cand.append((a['member_id'], b['member_id']))
 581|         if not cand:
 582|             return []
 583|         if len(cand) > 12000:  # C7 count-based cap (spec 8): top 12,000 by (-rule_score, a, b) - never time-based
 584|             cand = sorted(cand, key=lambda p: (-rule_score(state, p[0], p[1]), p[0], p[1]))[:12000]
 585|         model = load_model()
 586|         chosen = None
 587|         if model is not None:
 588|             try:
 589|                 edges = [(x, y, _score_pair(model, state, x, y)) for x, y in cand]
 590|                 chosen = max_score_matching([m['member_id'] for m in members],
 591|                                             edges, float(model['floor']))
 592|             except Exception:
 593|                 chosen = None                # scoring failure -> rule fallback (T8)
 594|         if chosen is None:
 595|             chosen = _rule_greedy([(x, y, rule_score(state, x, y)) for x, y in cand])
 596|         return [[a, b] for a, b, _ in sorted(chosen, key=lambda e: (e[0], e[1]))]
```

## method_tournament greedy_take + retained methods

- File: `research/method_tournament/alloc.py`
- Classification: **CORRECT**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | e[2] is the POSITIVE count; (-e[2], pair_key) sorts descending on count - same as kit. |
| 2. Maximize or minimize the intended score? | Sequential take-while-free (same as kit); retained methods build on take_ordered/Hungarian with their own positive scores, none weights a maximizer with -count. |
| 3. Score negated into a maximizing solver? | Sort-key only, consumed by sorted(); direction correct. |
| 4. Unknown / mismatch / match scoring? | Counts from the kit-equivalent score (unknown -> 0). |
| 5. Tie resolution? | pair_key canonical order, matching kit. |
| 6. Sequential greedy or fixed-k global? | Sequential greedy control; candidates = full-sequential episodes run through evaluate.py on identical seeds. |
| 7. Output matches the report? | "identical to kit.baseline_match" supported by code; every tournament row is paired against this control with seed-cluster inference. |

Excerpts:

`research/method_tournament/alloc.py`

```
  10| def _take(ordered):
  11|     used = set()
  12|     out = []
  13|     for a, b in ordered:
  14|         if a in used or b in used:
  15|             continue
  16|         out.append([a, b])
  17|         used.add(a)
  18|         used.add(b)
  19|     return out
  20| 
  21| 
  22| def greedy_take(edges):
  23|     """Sort by (-score, pair_key) then take non-overlapping: identical to kit.baseline_match."""
  24|     ordered = [(a, b) for a, b, s in sorted(edges, key=lambda e: (-e[2], pair_key(e[0], e[1])))]
  25|     return _take(ordered)
```

## mo_analyze baseline rank (suspected second inversion)

- File: `research/round2_missed_oracle/scripts/mo_analyze.py`
- Classification: **SUSPECTED_DIRECTION_BUG (impact decided by C5)**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | rank 1 = greatest score passed in. For F2 that is the highest F2 score (correct). For baseline the score passed is -raw with raw a POSITIVE count, so rank 1 = LOWEST count - inverted relative to count quality. |
| 2. Maximize or minimize the intended score? | Descriptive ranking only (no selection). |
| 3. Score negated into a maximizing solver? | -raw[i][0] applies the stale neg_score convention a second time; same root cause as the F1 selector defect. |
| 4. Unknown / mismatch / match scoring? | n/a. |
| 5. Tie resolution? | Competition ranking (1 + count strictly greater) - tied scores share a rank, identically in both frames. |
| 6. Sequential greedy or fixed-k global? | n/a (descriptive). |
| 7. Output matches the report? | Downstream claims ("baseline already puts most positives near the top", "count ranks them BETTER (0.388)", "F2 outranks baseline on only 32.4%") read lower rank as better under this inverted frame. Whether they stand or invert is decided by computation C5, not by this reading. |

Excerpts:

`research/round2_missed_oracle/scripts/mo_analyze.py`

```
  31| def competition_rank(score, all_scores):
  32|     """1 + count of strictly greater scores."""
  33|     return 1 + sum(1 for s in all_scores if s > score + EPS)
  88|         # ---- one row per COUNTERFACTUAL-POSITIVE edge ----------------------
  89|         m2_neg = [e for e in M2 if lab[e] == 0]
  90|         m2_pos = [e for e in M2 if lab[e] == 1]
  91|         s2_rank = {edges[i]: competition_rank(s2[i], s2) for i in range(len(edges))}
  92|         base_rank = {edges[i]: competition_rank(-raw[i][0], [-r[0] for r in raw])
  93|                      for i in range(len(edges))}
 115|             rank_rows.append(dict(
 116|                 seed=k[0], variant=k[1], day=k[2],
 117|                 user_a=e[0], user_b=e[1], n_edges=len(edges), k_t=kt,
 118|                 f2_score=round(sc, 8), f2_rank=s2_rank[e],
 119|                 f2_percentile=round(s2_rank[e] / len(edges), 6),
 120|                 f2_tie_size=sum(1 for x in s2 if abs(x - sc) <= EPS),
 121|                 baseline_raw=-raw[i][0], baseline_rank=base_rank[e],
 122|                 in_F5_optimal_set=int(e in M5), f2_selected=int(captured),
```

## mo decomposition formulas (claim C)

- File: `research/round2_missed_oracle/scripts/mo_analyze.py`
- Classification: **CORRECT (independent of the F1 defect)**

| Verdict question | Answer |
|---|---|
| 1. Higher or lower raw score is better? | Components are differences of positive counts of positives captured; R_t = positives among top-k_t by F2. |
| 2. Maximize or minimize the intended score? | Additive decomposition identity: (P5 - R_t) + (R_t - P2) = P5 - P2 = 67. |
| 3. Score negated into a maximizing solver? | None: no F1 term appears in either component (P_F1 exists only as an aggregate context column in mo_decomp L22). |
| 4. Unknown / mismatch / match scoring? | Labels are counterfactual MSMI flags; no score semantics. |
| 5. Tie resolution? | R_t ties broken canonically by (-s2, canon) at L79. |
| 6. Sequential greedy or fixed-k global? | Diagnostic identity over saved sets. |
| 7. Output matches the report? | Formulas match the report/plan decomposition definition verbatim. |

Excerpts:

`research/round2_missed_oracle/scripts/mo_analyze.py`

```
 164|             R_t=R_t, U_t=U_t,
 165|             gap_F5_F2=gap,
 166|             ranking_component=P['F5-ORACLE'] - R_t,
 167|             conflict_component=R_t - P['F2-SOFT'],
 168|             irreducible_matching_cost=U_t - P['F5-ORACLE'],
```

## Repo-wide negation scan

`-e[0]` weight construction outside fc/mo/goal_rule: **0 hits**
- none (no other study negates edge scores into a maximizer).
