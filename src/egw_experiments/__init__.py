"""Experiment harness and reproducible analysis for the EGW campaign.

Implements the normative plan sections 5.1/5.8 (environment and evidence
structure), 7.1 (experimental conditions), 7.2 (metrics), 7.3 (statistical
definitions) and 9.1 (reproducibility), together with CONTRACTS.md
sections 5 (controller event log), 7 (simulator CLI) and 9 (metric
definitions).

Design rules enforced here:

- Core analysis is standard-library only (csv, json, statistics, math).
  matplotlib is an optional extra used exclusively for figure generation;
  pandas is never required.
- ``results/processed`` and ``results/figures`` are always regenerated in
  full from ``results/raw`` by a single entrypoint (``analyze``).
- Raw run directories are treated as immutable evidence: the runner refuses
  to overwrite an existing ``results/raw/<run_id>/``.
"""

from .protocol import PROTOCOL_VERSION

__all__ = ["PROTOCOL_VERSION"]
