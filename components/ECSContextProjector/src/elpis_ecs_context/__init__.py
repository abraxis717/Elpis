"""Standalone, read-only projection over Elpis ECS committed event records."""

from .contracts import ContextProjection, HistoryBinding, ProjectionError, ProjectionRequest
from .projector import project_history, project_verified_events

__all__ = [
    "ContextProjection", "HistoryBinding", "ProjectionError", "ProjectionRequest",
    "project_history", "project_verified_events",
]
