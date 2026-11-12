"""Deterministic engine: distance, score, flags (robustness, gapscope, comparelab later)."""

from ember.engine.distance import interval_log_distance, transfer_distance
from ember.engine.flags import flags_for
from ember.engine.score import evidence_to_dict, rank, scenario_to_dict, score

__all__ = [
    "interval_log_distance",
    "transfer_distance",
    "flags_for",
    "evidence_to_dict",
    "rank",
    "scenario_to_dict",
    "score",
]
