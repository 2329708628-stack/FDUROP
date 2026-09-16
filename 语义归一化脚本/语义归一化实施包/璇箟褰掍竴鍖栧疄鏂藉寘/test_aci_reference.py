"""Behavioral checks for the public reference module; no third-party packages."""

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import aci_reference as aci


def records(sets):
    return [{"run_id": "r%d" % i, "status": "ok", "concept_ids": list(ids)}
            for i, ids in enumerate(sets)]


class MetricTests(unittest.TestCase):
    def test_jaccard_endpoints_and_empty_convention(self):
        self.assertEqual(aci.jaccard_distance(["a"], ["a"]), 0)
        self.assertEqual(aci.jaccard_distance(["a"], ["b"]), 1)
        self.assertEqual(aci.jaccard_distance([], []), 0)
        self.assertEqual(aci.jaccard_distance([], ["a"]), 1)
        with self.assertRaises(ValueError):
            aci.aci_j([[], []])

    def test_two_camps_count_bias_does_not_masquerade_as_pair_convergence(self):
        for n in (4, 20, 100):
            runs = [["a"]] * (n // 2) + [["b"]] * (n // 2)
            counts = aci.count_metrics(runs)
            self.assertAlmostEqual(counts["original_U_over_T"], 2 / n)
            self.assertAlmostEqual(counts["count_endpoint_corrected"], 1 / (n - 1))
            self.assertAlmostEqual(aci.aci_j(runs), n / (2 * (n - 1)))

    def test_same_count_statistics_distinct_cooccurrence(self):
        camps = [list(x) for x in ("ab", "ab", "cd", "cd")]
        cycle = [list(x) for x in ("ab", "bc", "cd", "da")]
        self.assertEqual(aci.count_metrics(camps), aci.count_metrics(cycle))
        self.assertAlmostEqual(aci.aci_j(camps), 2 / 3)
        self.assertAlmostEqual(aci.aci_j(cycle), 7 / 9)

    def test_identical_and_disjoint_count_endpoints(self):
        self.assertEqual(aci.count_metrics([["a"]] * 4)["count_endpoint_corrected"], 0)
        self.assertEqual(aci.count_metrics([["a"], ["b"], ["c"]])["count_endpoint_corrected"], 1)

    def test_within_run_deduplication(self):
        repeated = [["a", "a", "b"], ["b", "b", "c"]]
        unique = [["a", "b"], ["b", "c"]]
        self.assertEqual(aci.aci_j(repeated), aci.aci_j(unique))
        self.assertEqual(aci.count_metrics(repeated), aci.count_metrics(unique))
        self.assertEqual(aci.concept_frequencies(repeated)["b"]["run_count"], 2)
        _, qc, _ = aci.prepare_records(records(repeated))
        self.assertEqual(qc["within_run_duplicate_ids_removed"], 2)

    def test_run_order_and_bijective_id_rename_invariance(self):
        original = [["a", "b"], ["a"], ["b", "c"], ["a", "c"]]
        rename = {"a": "甲", "b": "乙", "c": "丙"}
        renamed = [[rename[x] for x in ids] for ids in reversed(original)]
        self.assertAlmostEqual(aci.aci_j(original), aci.aci_j(renamed))
        self.assertAlmostEqual(aci.jackknife_se(original), aci.jackknife_se(renamed))
        self.assertEqual(aci.count_metrics(original), aci.count_metrics(renamed))

    def test_n_two_has_no_jackknife_se(self):
        self.assertIsNone(aci.jackknife_se([["a"], ["b"]]))
        self.assertGreater(aci.hoeffding_interval(0.5, 2)["upper"], 0.5)

    def test_jackknife_known_nonconstant_three_run_example(self):
        # Distances: 0, 1, 1; deleting runs yields 1, 1, 0.
        self.assertAlmostEqual(aci.jackknife_se([["a"], ["a"], ["b"]]), 2 / 3)

    def test_zero_se_is_not_certainty(self):
        result = aci.summarize_sets([["a"]] * 20, fixed_normalization=True)
        self.assertEqual(result["inference"]["jackknife_run_delete_se"], 0)
        self.assertGreater(result["inference"]["hoeffding_interval"]["upper"], 0)
        self.assertTrue(result["inference"]["zero_se_does_not_imply_certainty"])

    def test_hoeffding_bound_formula_and_limits(self):
        bound = aci.hoeffding_interval(0.5, 20)
        self.assertAlmostEqual(bound["half_width_before_clipping"], math.sqrt(math.log(40) / 20))
        self.assertEqual(aci.hoeffding_interval(0.5, 3)["lower"], 0)
        self.assertEqual(aci.hoeffding_interval(0.5, 3)["upper"], 1)
        for alpha in (0, 1, -0.1):
            with self.assertRaises(ValueError):
                aci.hoeffding_interval(0.5, 3, alpha)

    def test_insufficient_data_rejected(self):
        for runs in ([], [["a"]]):
            with self.assertRaises(ValueError):
                aci.aci_j(runs)
        with self.assertRaises(ValueError):
            aci.permutation_test([["a"]], [["b"], ["c"]], 19)

    def test_raw_string_and_empty_id_rejected(self):
        with self.assertRaises(ValueError):
            aci.jaccard_distance("abc", ["a"])
        with self.assertRaises(ValueError):
            aci.aci_j([[" "], ["a"]])

    def test_coarsening_is_not_a_jaccard_bound(self):
        self.assertAlmostEqual(aci.jaccard_distance(list("abc"), list("abd")), 0.5)
        self.assertAlmostEqual(aci.jaccard_distance(list("ec"), list("ed")), 2 / 3)


class InputAndPermutationTests(unittest.TestCase):
    def test_failures_and_missing_reported_separately_not_empty(self):
        inp = records([["a"], ["b"]]) + [
            {"run_id": "f", "status": "failed"},
            {"run_id": "m", "status": "missing"},
        ]
        result = aci.analyze_payload({"runs": inp})["groups"]["single"]
        self.assertEqual(result["analysis"]["aci_j"], 1)
        self.assertEqual(result["input_qc"]["failed_run_ids"], ["f"])
        self.assertEqual(result["input_qc"]["missing_run_ids"], ["m"])
        self.assertEqual(result["input_qc"]["ok_but_empty_run_ids"], [])
        self.assertEqual(result["input_qc"]["nonempty_success_fraction_of_supplied_records"], 0.5)

    def test_empty_ok_blocks_default_and_explicit_exclusion_is_reported(self):
        payload = {"runs": records([["a"], ["b"], []])}
        default = aci.analyze_payload(payload)["groups"]["single"]
        self.assertIsNone(default["analysis"])
        self.assertTrue(default["analysis_errors"])
        explicit = aci.analyze_payload(payload, exclude_empty_ok=True)["groups"]["single"]
        self.assertEqual(explicit["analysis"]["aci_j"], 1)
        self.assertEqual(explicit["input_qc"]["ok_but_empty_run_ids"], ["r2"])
        self.assertTrue(explicit["input_qc"]["empty_ok_exclusion_explicitly_requested"])

    def test_missing_status_cannot_be_silently_assumed_ok(self):
        with self.assertRaises(ValueError):
            aci.prepare_records([{"run_id": "r", "concept_ids": ["a"]}])

    def test_failed_nonempty_record_cannot_enter_analysis(self):
        with self.assertRaises(ValueError):
            aci.prepare_records([{"run_id": "r", "status": "failed", "concept_ids": ["a"]}])

    def test_duplicate_run_ids_rejected(self):
        inp = records([["a"], ["b"]])
        inp[1]["run_id"] = inp[0]["run_id"]
        with self.assertRaises(ValueError):
            aci.prepare_records(inp)

    def test_inference_requires_fixed_normalization_assertion(self):
        payload = {"groups": {"A": records([["a"], ["a"], ["a"]]),
                              "B": records([["a"], ["b"], ["c"]])}}
        descriptive = aci.analyze_payload(payload, permutations=19)
        self.assertIsNone(descriptive["groups"]["A"]["analysis"]["inference"])
        self.assertIsNone(descriptive["comparison"])
        payload["fixed_normalization"] = True
        inferential = aci.analyze_payload(payload, permutations=19)
        self.assertIsNotNone(inferential["comparison"])

    def test_permutation_seed_reproducibility_and_group_effect_direction(self):
        a, b = [["a"]] * 4, [["a"], ["b"], ["c"], ["d"]]
        first = aci.permutation_test(a, b, permutations=199, seed=42)
        second = aci.permutation_test(a, b, permutations=199, seed=42)
        self.assertEqual(first, second)
        self.assertEqual(first["delta_A_minus_B"], -1)
        self.assertGreaterEqual(first["p_value_two_sided"], 1 / 200)
        self.assertLessEqual(first["p_value_two_sided"], 1)
        self.assertEqual(first["independent_run_counts"], {"A": 4, "B": 4})

    def test_permutation_no_difference_returns_one(self):
        self.assertEqual(aci.permutation_test([["a"]] * 3, [["a"]] * 3, 99)["p_value_two_sided"], 1)

    def test_cli_success_and_blocked_input_exit_codes(self):
        script = Path(aci.__file__).resolve()
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.json", Path(directory) / "result.json"
            source.write_text(json.dumps({"fixed_normalization": True, "runs": records([["a"], ["b"]])}), encoding="utf-8")
            call = subprocess.run([sys.executable, str(script), str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(call.returncode, 0, call.stderr)
            self.assertEqual(json.loads(output.read_text())["groups"]["single"]["analysis"]["aci_j"], 1)
            source.write_text(json.dumps({"runs": records([["a"], []])}), encoding="utf-8")
            call = subprocess.run([sys.executable, str(script), str(source)], capture_output=True, text=True)
            self.assertEqual(call.returncode, 2)
            parsed = json.loads(call.stdout)
            self.assertIsNone(parsed["groups"]["single"]["analysis"])
            self.assertEqual(parsed["groups"]["single"]["input_qc"]["ok_but_empty_run_ids"], ["r1"])


if __name__ == "__main__":
    unittest.main()
