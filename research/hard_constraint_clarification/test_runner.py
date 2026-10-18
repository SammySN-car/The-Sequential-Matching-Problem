"""TDD suite for run_experiment.py (crash-safe paired runner). RED first.

Run from repo root:  python -m unittest research.hard_constraint_clarification.test_runner -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.hard_constraint_clarification import run_experiment as rx


class PhaseKeys(unittest.TestCase):
    def test_pilot_has_54_keys_and_replay_2(self):
        self.assertEqual(len(rx.phase_keys('pilot')), 54)
        self.assertEqual(len(rx.phase_keys('pilot_replay')), 2)

    def test_confirmatory_has_1206_keys_with_spot_check(self):
        keys = rx.phase_keys('confirmatory')
        self.assertEqual(len(keys), 1206)
        spot = [k for k in keys if k[0] == 'greedy_official']
        self.assertEqual(len(spot), 6)
        self.assertTrue(all(s == 120001 for _, s, _ in spot))
        pairs = [(s, v) for a, s, v in keys if a in ('greedy', 'unlock')]
        self.assertEqual(len(pairs), 1200)

    def test_keys_unique_within_phase(self):
        for phase in ('pilot', 'pilot_replay', 'confirmatory'):
            keys = rx.phase_keys(phase)
            self.assertEqual(len(keys), len(set(keys)))

    def test_confirmatory_pairs_are_interleaved_by_seed(self):
        keys = rx.phase_keys('confirmatory')
        first_greedy = next(i for i, k in enumerate(keys) if k[0] == 'greedy')
        first_unlock = next(i for i, k in enumerate(keys) if k[0] == 'unlock')
        self.assertEqual(keys[first_greedy][1], keys[first_unlock][1])


class CommandAndEnv(unittest.TestCase):
    def test_build_cmd_official_has_no_policy_flag(self):
        cmd = rx.build_cmd('greedy_official', 119001, 'development', 'tmp/o.json')
        self.assertNotIn('--policy', cmd)
        self.assertIn('evaluate.py', cmd[1])
        i = cmd.index('--baseline')
        self.assertEqual(cmd[i + 1], 'greedy')

    def test_build_cmd_instrumented_points_at_candidate(self):
        cmd = rx.build_cmd('unlock', 120001, 'drift', 'tmp/o.json')
        self.assertIn('--policy', cmd)
        pol = cmd[cmd.index('--policy') + 1]
        self.assertTrue(pol.endswith('candidate_policy.py'))
        self.assertIn(pol.split('/')[-1] if '/' in pol else pol.split('\\')[-1],
                      ['candidate_policy.py'])

    def test_seeds_and_variants_passthrough(self):
        cmd = rx.build_cmd('greedy', 120077, 'cold_start', 'o.json')
        self.assertEqual(cmd[cmd.index('--seeds') + 1], '120077')
        self.assertEqual(cmd[cmd.index('--variants') + 1], 'cold_start')
        self.assertEqual(cmd[cmd.index('--output') + 1], 'o.json')

    def test_build_env_mode_and_log(self):
        env_off = rx.build_env('greedy_official', 119001, 'development', Path('/x'))
        self.assertNotIn('HCC_MODE', env_off)
        env_g = rx.build_env('greedy', 119001, 'development', Path('/x'))
        self.assertEqual(env_g['HCC_MODE'], 'greedy')
        self.assertIn(rx.key_str('greedy', 119001, 'development'), env_g['HCC_LOG'])
        env_u = rx.build_env('unlock', 119001, 'development', Path('/x'))
        self.assertEqual(env_u['HCC_MODE'], 'unlock')


class Progress(unittest.TestCase):
    def test_load_done_tolerates_missing_and_garbage(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'progress.jsonl'
            self.assertEqual(rx.load_done(p), {})            # missing file
            p.write_text('{"key": "a__1__v"}\nnot json at all\n{"key": "b__2__w"}\n',
                         encoding='utf-8')
            done = rx.load_done(p)
            self.assertEqual(set(done), {'a__1__v', 'b__2__w'})

    def test_record_from_output_valid_and_invalid(self):
        out = {'schema_version': '1.0.0', 'seeds': [1], 'variants': ['development'],
               'episodes': [{'seed': 1, 'variant': 'development', 'valid': True,
                         'msmi_per_100_arrived_members': 0.5, 'action_sha256': 'ff'}],
               'summary': {}}
        rec = rx.record_from_output('unlock', 1, 'development', 0, 1.5, out)
        self.assertTrue(rec['valid'])
        self.assertEqual(rec['row']['action_sha256'], 'ff')
        bad = rx.record_from_output('unlock', 1, 'development', 2, 1.5,
                                    {'episodes': [{'valid': False, 'error': 'boom'}]})
        self.assertFalse(bad['valid'])
        self.assertEqual(bad['row']['error'], 'boom')


class RunPhase(unittest.TestCase):
    def _tmp_exp(self, d):
        exp = Path(d)
        (exp / 'results').mkdir()
        (exp / 'logs').mkdir()
        (exp / 'tmp').mkdir()
        return exp

    def test_resume_skips_done_and_runs_rest_in_order(self):
        with tempfile.TemporaryDirectory() as d:
            exp = self._tmp_exp(d)
            prog = rx.progress_path(exp, 'pilot')
            first = rx.phase_keys('pilot')[0]
            prog.write_text(json.dumps({'key': rx.key_str(*first)}) + '\n', encoding='utf-8')
            calls, written = [], []

            def fake(key, phase, exp_dir):
                calls.append(key)
                return rx.record_from_output(key[0], key[1], key[2], 0, 0.1,
                                             {'episodes': [{'valid': True}]})

            summ = rx.run_phase('pilot', exp=exp, execute=fake)
            self.assertEqual(len(calls), 53)
            self.assertEqual(calls[0], rx.phase_keys('pilot')[1])
            self.assertEqual(summ['executed'], 53)
            self.assertEqual(summ['skipped'], 1)
            done = rx.load_done(prog)
            self.assertEqual(len(done), 54)

    def test_stop_on_invalid_halts_and_records(self):
        with tempfile.TemporaryDirectory() as d:
            exp = self._tmp_exp(d)
            calls = []

            def fake(key, phase, exp_dir):
                calls.append(key)
                invalid = len(calls) == 2
                return rx.record_from_output(key[0], key[1], key[2], 0, 0.1,
                                             {'episodes': [{'valid': not invalid}]})

            summ = rx.run_phase('pilot', exp=exp, execute=fake)
            self.assertEqual(len(calls), 2)          # halted after first invalid
            self.assertTrue(summ['stopped'])
            self.assertEqual(summ['invalid'], 1)
            done = rx.load_done(rx.progress_path(exp, 'pilot'))
            self.assertEqual(len(done), 2)           # both records persisted

    def test_limit_and_fresh_run(self):
        with tempfile.TemporaryDirectory() as d:
            exp = self._tmp_exp(d)
            calls = []

            def fake(key, phase, exp_dir):
                calls.append(key)
                return rx.record_from_output(key[0], key[1], key[2], 0, 0.1,
                                             {'episodes': [{'valid': True}]})

            summ = rx.run_phase('pilot', exp=exp, execute=fake, limit=3)
            self.assertEqual(summ['executed'], 3)
            summ2 = rx.run_phase('pilot', exp=exp, execute=fake, limit=3, resume=False)
            self.assertEqual(summ2['executed'], 3)    # resume=False re-runs


if __name__ == '__main__':
    unittest.main()