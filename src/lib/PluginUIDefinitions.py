from typing import Any, Literal, NotRequired, TypedDict


class UIText(TypedDict, total=False):
    text: str
    key: str
    params: dict[str, Any]
    localized: dict[str, str]


class UINode(TypedDict, total=False):
    key: str
    type: Literal['text', 'heading', 'section', 'inline', 'list', 'progress', 'action']
    text: UIText
    tone: Literal['default', 'info', 'warning', 'success', 'muted', 'danger']
    outlined: bool
    level: int
    children: list['UINode']
    value: float
    maximum: float
    action: str
    payload: dict[str, Any]
    icon: str


class UIViewSection(TypedDict):
    key: str
    label: str
    grids: NotRequired[list[str]]
    content: NotRequired[list[UINode]]


class PluginUIView(TypedDict):
    id: str
    label: str
    description: NotRequired[str]
    icon: NotRequired[str]
    order: NotRequired[int]
    modes: NotRequired[list[Literal['configuring', 'running']]]
    sections: list[UIViewSection]


def view_target(plugin_guid: str, view_id: str) -> str:
    return f'plugin:{plugin_guid}:{view_id}'
