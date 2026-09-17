"""W1 QC thresholds and rating logic."""
from __future__ import annotations

from typing import Literal

THRESHOLD_VERSION = "1.0"

Grade = Literal["A", "B", "C", "D", "F"]
OverallRating = Literal["优", "良", "可接受", "需关注", "不建议下游"]

GRADE_SCORE = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
GRADE_LABEL = {4: "A", 3: "B", 2: "C", 1: "D", 0: "F"}

STAGE_WEIGHTS = {
    "S3_depth": 0.30,
    "S1_quality": 0.25,
    "S2_rrna": 0.15,
    "S4_assembly": 0.30,
}


def _tier(value: float, cutoffs: list[float], higher_is_better: bool = True) -> Grade:
    labels: list[Grade] = ["A", "B", "C", "D", "F"]
    if higher_is_better:
        for i, lo in enumerate(cutoffs):
            if value >= lo:
                return labels[i]
        return "F"
    for i, hi in enumerate(cutoffs):
        if value <= hi:
            return labels[i]
    return "F"


def grade_merge_depth(reads: float) -> Grade:
    return _tier(reads / 1e6, [15, 10, 5, 2])


def grade_fastp_retention(rate: float) -> Grade:
    return _tier(rate, [0.85, 0.80, 0.70, 0.60])


def grade_q30(q30: float) -> Grade:
    return _tier(q30, [0.92, 0.90, 0.85, 0.80])


def grade_duplication(dup: float) -> Grade:
    return _tier(dup, [0.15, 0.20, 0.30, 0.40], higher_is_better=False)


def grade_rrna_retention(rate: float) -> Grade:
    if 0.75 <= rate <= 0.98:
        return "A"
    if 0.65 <= rate <= 0.99:
        return "B"
    if 0.50 <= rate <= 0.99:
        return "C"
    if 0.40 <= rate <= 0.99:
        return "D"
    return "F"


def grade_contigs_ge1kb(n: float) -> Grade:
    return _tier(n, [8000, 5000, 3000, 1000])


def grade_s1_combined(retention: float, q30: float, dup: float) -> Grade:
    scores = [
        GRADE_SCORE[grade_fastp_retention(retention)],
        GRADE_SCORE[grade_q30(q30)],
        GRADE_SCORE[grade_duplication(dup)],
    ]
    return GRADE_LABEL[round(sum(scores) / len(scores))]  # type: ignore


def overall_rating(weighted_score: float) -> OverallRating:
    if weighted_score >= 3.5:
        return "优"
    if weighted_score >= 3.0:
        return "良"
    if weighted_score >= 2.0:
        return "可接受"
    if weighted_score >= 1.0:
        return "需关注"
    return "不建议下游"


def batch_pass(ratings: list[str]) -> bool:
    n = len(ratings) or 1
    good = sum(1 for r in ratings if r in ("优", "良"))
    bad = sum(1 for r in ratings if r == "不建议下游")
    return good / n >= 0.8 and bad / n <= 0.1
