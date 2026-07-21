"""PTCG cabt player agent package."""

try:
    from .policy import choose_actions
except Exception:  # partial package during multi-agent build
    choose_actions = None  # type: ignore

__all__ = ["choose_actions"]
