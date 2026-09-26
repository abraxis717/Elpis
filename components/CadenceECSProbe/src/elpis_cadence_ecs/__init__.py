"""Offline ECS history experiments; no runtime admission or automatic caller."""

from .probe import ProbeError, ProbeReport, ProbeStep, evaluate_history

RUNTIME_ADMISSION = False

__all__ = ["RUNTIME_ADMISSION", "ProbeError", "ProbeReport", "ProbeStep", "evaluate_history"]
