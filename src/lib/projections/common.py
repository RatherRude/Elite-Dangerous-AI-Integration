from pydantic import BaseModel

from .latest_event import LatestEventState

ProjectedStates = dict[str, BaseModel]


def get_state_dict(projected_states: ProjectedStates, key: str, default: dict | None = None) -> dict:
    """Helper to get a projection state as a dict for backward-compatible access patterns.

    Args:
        projected_states: The projected states dictionary
        key: The projection name (e.g., 'CurrentStatus', 'Location')
        default: Default value if key not found (defaults to empty dict)

    Returns:
        The state as a dict (via model_dump() if BaseModel, or as-is if already dict)
    """
    if default is None:
        default = {}
    state = projected_states.get(key)
    if state is None:
        return default
    if isinstance(state, LatestEventState):
        return state.data
    if hasattr(state, "model_dump"):
        return state.model_dump()
    return state if isinstance(state, dict) else default
