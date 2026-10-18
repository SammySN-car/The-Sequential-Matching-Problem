from pathlib import Path
src = Path(r'research\round2_stage3_intermediate_floor\diagnose3.py').read_text(encoding='utf-8')
assert src.count('sys.path.insert(0, str(REPO))') == 1, 'anchor count'
src = src.replace('"""Round 2 Stage 3 - instrumented diagnostic runner (measurement only, no tuning).',
 '"""Round 2 PROMOTION copy of Stage 3 diagnose3.py (measurement only, no tuning).\n\nPROVENANCE: copied from research/round2_stage3_intermediate_floor/diagnose3.py\nfor the fresh-seed promotion experiment (the original is frozen and asserts\noutputs stay in its own directory). Only change: one sys.path line so the\nfrozen intermediate_policy.py shim imports from the frozen Stage 3 directory.\nInstrumentation, arms, and fidelity checks are unchanged.', 1)
old = 'sys.path.insert(0, str(REPO))'
new = old + "\nsys.path.insert(0, str(REPO / 'research' / 'round2_stage3_intermediate_floor'))  # frozen Stage 3 shim for 'intermediate' arm"
src = src.replace(old, new, 1)
src = src.replace('Writes only into research/round2_stage3_intermediate_floor/.',
 'Writes only into research/round2_promotion_fresh_seeds/ (the HERE of this copy).')
Path(r'research\round2_promotion_fresh_seeds\diag_promo.py').write_text(src, encoding='utf-8')
print('diag_promo.py written:', len(src), 'bytes')