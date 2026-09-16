"""Reference metrics for human-checked, semantically normalized proposition IDs.

This module does NOT normalize text or verify that propositions are equivalent.
Inputs must contain stable concept IDs, not raw sentences to be compared as IDs.
Each run is an independent output under one fixed experimental condition.

CLI, one condition::

    python3 aci_reference.py input.json --output result.json

Input::

    {"fixed_normalization": true, "runs": [
      {"run_id": "r1", "status": "ok", "concept_ids": ["c1", "c2"]},
      {"run_id": "r2", "status": "ok", "concept_ids": ["c1", "c3"]}
    ]}

Two conditions use "groups": {"A": [...], "B": [...]} instead of "runs".
Failed/missing runs use status "failed"/"missing" and no concept IDs. They are
reported and excluded; resulting scores are explicitly conditional on success.
An ok-but-empty run blocks main analysis unless --exclude-empty-ok is supplied.
That option excludes empty outputs and changes the estimand; it never turns a
failure into an empty concept set.

Inference requires fixed_normalization=true: an assertion that the pairwise
semantic rule/mapping was fixed independently of the analysis runs. Merely
saving a mapping jointly learned from all current runs does not establish this.
With false/omitted, the CLI produces descriptive scores only. Valid uncertainty
also requires independent, identically distributed runs within each condition.
The confidence bound covers run sampling, NOT semantic normalization error,
historical validity, factual correctness, or generalization to other papers.

The permutation function assumes complete runs are exchangeable under its null.
It is for two independent groups within ONE paper/stratum. It does not implement
paired, multi-paper, batch-clustered, or general weak-equal-mean tests.

Python 3.9+; standard library only; no network/model calls.
"""

import argparse
import itertools
import json
import math
from pathlib import Path
import random
import sys
from typing import Iterable, List, Sequence, FrozenSet


def _concept_set(ids: Iterable[str]) -> FrozenSet[str]:
    if isinstance(ids, (str, bytes)):
        raise ValueError("concept_ids must be a collection of IDs, not a string")
    try:
        values = list(ids)
    except TypeError as exc:
        raise ValueError("concept_ids must be iterable") from exc
    if any(not isinstance(x, str) or not x.strip() for x in values):
        raise ValueError("Every concept ID must be a nonempty string")
    return frozenset(values)  # Repeated wording within a run counts only once.


def _checked_sets(runs: Sequence[Iterable[str]], minimum: int = 2) -> List[FrozenSet[str]]:
    sets = [_concept_set(ids) for ids in runs]
    if len(sets) < minimum:
        raise ValueError("At least %d usable runs are required" % minimum)
    if any(not ids for ids in sets):
        raise ValueError("Main metrics require nonempty runs; report empties separately")
    return sets


def jaccard_distance(a: Iterable[str], b: Iterable[str]) -> float:
    """Set Jaccard distance. Both empty => 0 by convention; main analysis rejects empties."""
    a, b = _concept_set(a), _concept_set(b)
    union = a | b
    return 0.0 if not union else 1.0 - len(a & b) / len(union)


def _distance(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    return 1.0 - len(a & b) / len(a | b)


def aci_j(runs: Sequence[Iterable[str]]) -> float:
    """Mean unordered-pair Jaccard distance; lower means more set convergence."""
    sets = _checked_sets(runs)
    distances = [_distance(a, b) for a, b in itertools.combinations(sets, 2)]
    return math.fsum(distances) / len(distances)


def concept_frequencies(runs: Sequence[Iterable[str]]) -> dict:
    sets = _checked_sets(runs, minimum=1)
    counts = {}
    for ids in sets:
        for concept_id in ids:
            counts[concept_id] = counts.get(concept_id, 0) + 1
    return {
        c: {"run_count": counts[c], "prevalence": counts[c] / len(sets)}
        for c in sorted(counts)
    }


def count_metrics(runs: Sequence[Iterable[str]]) -> dict:
    """Auxiliary count ratios, NOT run-count-invariant convergence measures."""
    sets = _checked_sets(runs, minimum=1)
    n = len(sets)
    total = sum(map(len, sets))
    unique = len(set().union(*sets))
    return {
        "n": n,
        "T_total_within_run_deduplicated": total,
        "U_unique_concepts": unique,
        "original_U_over_T": unique / total,
        "count_endpoint_corrected": (
            (n * unique - total) / ((n - 1) * total) if n > 1 else None
        ),
    }


def jackknife_se(runs: Sequence[Iterable[str]]):
    """Delete-one-RUN SE, or None if n<3. Not a finite-sample exact CI.

    Assumes a fixed pairwise rule and iid runs. A zero SE can arise from a
    degenerate observed distance matrix and does NOT establish certainty.
    """
    sets = _checked_sets(runs)
    n = len(sets)
    if n < 3:
        return None
    leave_one_out = [aci_j(sets[:i] + sets[i + 1:]) for i in range(n)]
    mean = math.fsum(leave_one_out) / n
    variance = ((n - 1) / n) * math.fsum((x - mean) ** 2 for x in leave_one_out)
    return math.sqrt(max(0.0, variance))


def hoeffding_interval(estimate: float, n: int, alpha: float = 0.05) -> dict:
    """Conservative bounded-kernel U-statistic interval, not a normal approximation.

    P(|U-theta| >= epsilon) <= 2 exp(-2 floor(n/2) epsilon^2), assuming
    independent iid runs and a fixed symmetric [0,1]-valued distance kernel.
    It is deliberately conservative, including at zero observed variance.
    """
    if not isinstance(n, int) or isinstance(n, bool) or n < 2:
        raise ValueError("n must be an integer >= 2")
    if not 0.0 <= estimate <= 1.0 or not math.isfinite(estimate):
        raise ValueError("estimate must be finite and between 0 and 1")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    pairs = n // 2
    half_width = math.sqrt(math.log(2.0 / alpha) / (2 * pairs))
    return {
        "method": "fixed_kernel_U_statistic_Hoeffding",
        "confidence_level": 1.0 - alpha,
        "lower": max(0.0, estimate - half_width),
        "upper": min(1.0, estimate + half_width),
        "half_width_before_clipping": half_width,
        "floor_n_over_2": pairs,
    }


def summarize_sets(runs: Sequence[Iterable[str]], fixed_normalization: bool = False,
                   alpha: float = 0.05) -> dict:
    sets = _checked_sets(runs)
    score = aci_j(sets)
    result = {
        "aci_j": score,
        "distance_matrix_in_input_usable_run_order": [[0.0 if i == j else _distance(a,b) for j,b in enumerate(sets)] for i,a in enumerate(sets)],
        "pair_count_not_independent_sample_size": len(sets) * (len(sets) - 1) // 2,
        "counts": count_metrics(sets),
        "per_run_concept_counts": [len(x) for x in sets],
        "concept_frequencies": concept_frequencies(sets),
        "inference": None,
    }
    if fixed_normalization:
        result["inference"] = {
            "jackknife_run_delete_se": jackknife_se(sets),
            "hoeffding_interval": hoeffding_interval(score, len(sets), alpha),
            "assumptions": "iid runs; symmetric pairwise rule fixed independently of analysis runs",
            "zero_se_does_not_imply_certainty": True,
            "normalization_error_included": False,
            "n_under_10_warning": len(sets) < 10,
        }
    else:
        result["inference_note"] = (
            "Descriptive only: independently fixed normalization was not asserted"
        )
    return result


def permutation_test(group_a: Sequence[Iterable[str]], group_b: Sequence[Iterable[str]],
                     permutations: int = 9999, seed: int = 1729) -> dict:
    """Two-sided Monte Carlo label permutation of WHOLE runs in one stratum.

    Fixed mapping/rule, independent groups and exchangeability are caller
    preconditions. The null is identical output distributions/exchangeable
    condition labels, stronger than equal mean ACI. No pairwise-distance
    observations are independently permuted. Repeated Monte Carlo partitions
    are permitted; the +1 correction prevents zero Monte Carlo p-values.
    """
    a, b = _checked_sets(group_a), _checked_sets(group_b)
    if not isinstance(permutations, int) or isinstance(permutations, bool) or permutations < 1:
        raise ValueError("permutations must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    combined = a + b
    n_total, n_a = len(combined), len(a)
    matrix = [[0.0] * n_total for _ in range(n_total)]
    for i, j in itertools.combinations(range(n_total), 2):
        matrix[i][j] = matrix[j][i] = _distance(combined[i], combined[j])

    def pair_mean(indices):
        distances = [matrix[i][j] for i, j in itertools.combinations(indices, 2)]
        return math.fsum(distances) / len(distances)

    observed = pair_mean(range(n_a)) - pair_mean(range(n_a, n_total))
    rng = random.Random(seed)
    extreme = 0
    population = list(range(n_total))
    for _ in range(permutations):
        selected = set(rng.sample(population, n_a))
        # Sorting controls floating-point summation order; complete runs move.
        ia = [i for i in population if i in selected]
        ib = [i for i in population if i not in selected]
        permuted = pair_mean(ia) - pair_mean(ib)
        if abs(permuted) >= abs(observed) or math.isclose(
                abs(permuted), abs(observed), rel_tol=1e-12, abs_tol=1e-15):
            extreme += 1
    return {
        "delta_A_minus_B": observed,
        "p_value_two_sided": (1 + extreme) / (permutations + 1),
        "permutations": permutations,
        "seed": seed,
        "extreme_permutations": extreme,
        "independent_run_counts": {"A": len(a), "B": len(b)},
        "null": "complete output distributions identical; whole-run labels exchangeable",
        "scope": "one stratum; independent groups; fixed normalization; no semantic error correction",
    }


def prepare_records(records, exclude_empty_ok: bool = False):
    """Validate records and return (usable sets, QC report, analysis-blocking reasons)."""
    if not isinstance(records, list):
        raise ValueError("runs must be a JSON array of run records")
    ids_seen = set()
    usable, usable_ids, failed, missing, empty = [], [], [], [], []
    duplicates_removed = 0
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each run must be an object with run_id and explicit status")
        run_id = record.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip() or run_id in ids_seen:
            raise ValueError("run_id must be a unique nonempty string within a group")
        ids_seen.add(run_id)
        status = record.get("status")
        if status not in ("ok", "failed", "missing"):
            raise ValueError("Run %s needs explicit status ok, failed, or missing" % run_id)
        if status != "ok":
            if record.get("concept_ids") not in (None, []):
                raise ValueError("Unsuccessful run %s cannot supply usable concept IDs" % run_id)
            (failed if status == "failed" else missing).append(run_id)
            continue
        raw_ids = record.get("concept_ids")
        if not isinstance(raw_ids, list):
            raise ValueError("Successful run %s needs a concept_ids array" % run_id)
        concepts = _concept_set(raw_ids)
        duplicates_removed += len(raw_ids) - len(concepts)
        if not concepts:
            empty.append(run_id)
        else:
            usable.append(concepts)
            usable_ids.append(run_id)
    qc = {
        "records_supplied": len(records),
        "usable_nonempty_ok_runs": len(usable),
        "usable_run_ids": usable_ids,
        "failed_run_ids": failed,
        "missing_run_ids": missing,
        "ok_but_empty_run_ids": empty,
        "within_run_duplicate_ids_removed": duplicates_removed,
        "nonempty_success_fraction_of_supplied_records": len(usable) / len(records) if records else None,
        "empty_ok_exclusion_explicitly_requested": exclude_empty_ok,
        "estimand": "convergence conditional on status=ok AND a nonempty normalized output",
        "unreported_missing_runs_cannot_be_detected": True,
    }
    errors = []
    if empty and not exclude_empty_ok:
        errors.append("ok-but-empty runs present: main analysis blocked; explicitly exclude them only if justified")
    if len(usable) < 2:
        errors.append("Fewer than two usable nonempty successful runs")
    return usable, qc, errors


def analyze_payload(payload, exclude_empty_ok: bool = False, alpha: float = 0.05,
                    permutations: int = 9999, seed: int = 1729) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Top-level input must be an object")
    fixed = payload.get("fixed_normalization", False)
    if not isinstance(fixed, bool):
        raise ValueError("fixed_normalization must be true or false")
    if ("runs" in payload) == ("groups" in payload):
        raise ValueError("Supply exactly one of runs or groups")
    groups = payload.get("groups") if "groups" in payload else {"single": payload["runs"]}
    if not isinstance(groups, dict) or not groups or any(
            not isinstance(name, str) or not name.strip() for name in groups):
        raise ValueError("groups must be a nonempty object with named groups")
    if "groups" in payload and len(groups) != 2:
        raise ValueError("This reference CLI supports exactly two groups, or a single runs array")
    output = {
        "schema_version": "1.0",
        "fixed_normalization_independent_of_analysis_runs_asserted": fixed,
        "groups": {},
        "comparison": None,
        "warning": "Scores do not establish semantic accuracy, source fidelity, or historical validity",
    }
    prepared = {}
    for name, records in groups.items():
        sets, qc, errors = prepare_records(records, exclude_empty_ok)
        prepared[name] = sets
        output["groups"][name] = {
            "input_qc": qc,
            "analysis": None if errors else summarize_sets(sets, fixed, alpha),
            "analysis_errors": errors,
        }
    if len(groups) == 2:
        names = list(groups)
        if any(output["groups"][name]["analysis_errors"] for name in names):
            output["comparison_note"] = "Blocked because one or both groups lack usable main analysis"
        elif not fixed:
            output["comparison_note"] = "No inferential comparison: independently fixed normalization not asserted"
        else:
            result = permutation_test(prepared[names[0]], prepared[names[1]], permutations, seed)
            result["A_group_name"], result["B_group_name"] = names
            output["comparison"] = result
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="UTF-8 JSON containing verified concept IDs")
    parser.add_argument("--output", type=Path, help="Output JSON; omitted means standard output")
    parser.add_argument("--exclude-empty-ok", action="store_true",
                        help="Explicitly condition analysis on nonempty successful runs; report excluded empties")
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--permutations", type=int, default=9999)
    parser.add_argument("--seed", type=int, default=1729)
    args = parser.parse_args(argv)
    try:
        if not 0 < args.alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        if args.permutations < 1:
            raise ValueError("permutations must be positive")
        with args.input.open(encoding="utf-8") as stream:
            payload = json.load(stream)
        output = analyze_payload(payload, args.exclude_empty_ok, args.alpha, args.permutations, args.seed)
        exit_code = 2 if any(x["analysis_errors"] for x in output["groups"].values()) else 0
    except (OSError, ValueError, TypeError) as exc:
        output, exit_code = {"error": str(exc)}, 2
    rendered = json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
