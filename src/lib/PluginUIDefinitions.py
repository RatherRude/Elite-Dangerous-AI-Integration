from typing import Any, Iterator, Literal, NotRequired, TypedDict


class UIText(TypedDict, total=False):
    text: str
    key: str
    params: dict[str, Any]
    localized: dict[str, str]


ComponentType = Literal['paragraph', 'notification', 'text', 'textarea', 'toggle', 'number', 'select', 'button', 'list', 'filter', 'error', 'heading', 'section', 'inline', 'progress', 'action']


class _ComponentProperties(TypedDict, total=False):
    label: str | None
    readonly: bool
    placeholder: str | None
    params: dict[str, str | int | float]
    text: UIText
    tone: Literal['default', 'info', 'warning', 'success', 'muted', 'danger']
    outlined: bool
    level: int | Literal['info', 'warning', 'error']
    children: list['UIComponent']
    value: float
    maximum: float
    action: str
    payload: dict[str, Any]
    icon: str


class UINode(_ComponentProperties, total=False):
    key: str
    type: ComponentType


class InputBase(_ComponentProperties):
    key: str
    type: ComponentType


class SelectOption(TypedDict):
    key: str
    label: str
    value: object
    disabled: bool


class Select(InputBase):
    default_value: str | list[str] | None
    select_options: list[SelectOption] | None
    multi_select: bool


class TextInput(InputBase):
    default_value: str | None
    max_length: int | None
    min_length: int | None
    hidden: NotRequired[bool]


class Filter(TextInput):
    pass


class TextArea(InputBase):
    default_value: str | None
    rows: int | float | None
    cols: int | float | None


class NumberInput(InputBase):
    default_value: int | float | None
    min_value: int | float | None
    max_value: int | float | None
    step: int | float | None


class Toggle(InputBase):
    default_value: bool | None


class Button(InputBase):
    pass


class Paragraph(InputBase):
    content: str


class Notification(Paragraph):
    pass


class Error(Paragraph):
    pass


class Text(UINode):
    pass


class Heading(UINode):
    pass


class Section(UINode):
    pass


class Inline(UINode):
    pass


class Progress(UINode):
    pass


class Action(UINode):
    pass


class ListAction(TypedDict):
    action: str
    icon: NotRequired[str]
    label: NotRequired[str]
    danger: NotRequired[bool]
    inline_edit: NotRequired[bool]
    secondary: NotRequired[bool]
    confirmation: NotRequired[str]


class ListRow(TypedDict):
    key: str
    title: str
    title_key: NotRequired[str]
    suffix: NotRequired[str]
    meta: NotRequired[str]
    params: NotRequired[dict[str, str | int | float]]
    group: NotRequired[str]
    pending: NotRequired[bool]
    tone: NotRequired[str]
    details: NotRequired[list['UIComponent']]
    summary: NotRequired[list['UIComponent']]
    highlighted: NotRequired[bool]


class List(UINode):
    items: NotRequired[list[ListRow]]
    row_actions: NotRequired[list[ListAction]]
    count_labels: NotRequired[dict[str, str]]
    details_collapsible: NotRequired[bool]


class UICondition(TypedDict):
    """Compare a key in the current namespace, or use default_show when unset."""
    key: str
    operator: Literal['eq', 'neq', 'gt', 'geq', 'lt', 'leq', 'in', 'not_in', 'contains', 'not_contains', 'is_set', 'is_unset']
    value: NotRequired[object]
    default_show: NotRequired[bool]


class Condition(TypedDict):
    """Show nested components when the condition matches; hidden values are preserved."""
    key: str
    type: Literal['condition']
    condition: UICondition
    fields: list['UIComponent']


UIComponent = UINode | TextInput | Filter | TextArea | NumberInput | Toggle | Select | Button | Paragraph | Notification | Error | Text | Heading | Section | Inline | Progress | Action | List | Condition


class GridHeaderAction(TypedDict):
    key: str
    icon: NotRequired[str]
    label: NotRequired[str]


class UIGrid(TypedDict):
    key: str
    label: str
    fields: list[UIComponent]
    content: NotRequired[list[UIComponent]]
    collapsible: NotRequired[bool]
    default_collapsed: NotRequired[bool]
    header_action: NotRequired[GridHeaderAction]


def ui_fields(elements: list[UIComponent]) -> Iterator[UIComponent]:
    """Include hidden descendants without treating conditions as value-bearing fields."""
    for element in elements:
        if element['type'] == 'condition':
            yield from ui_fields(element['fields'])
        else:
            yield element
            yield from ui_fields(element.get('children', []))
            if element['type'] == 'list':
                for row in element.get('items', []):
                    yield from ui_fields(row.get('summary', []))
                    yield from ui_fields(row.get('details', []))


class UIViewSection(TypedDict):
    key: str
    label: str
    voice_aliases: NotRequired[list[str]]
    grids: NotRequired[list[str]]
    content: NotRequired[list[UIComponent]]


class PluginUIView(TypedDict):
    id: str
    label: str
    voice_aliases: NotRequired[list[str]]
    description: NotRequired[str]
    icon: NotRequired[str]
    order: NotRequired[int]
    modes: NotRequired[list[Literal['configuring', 'running']]]
    sections: list[UIViewSection]


def view_target(plugin_guid: str, view_id: str) -> str:
    return f'plugin:{plugin_guid}:{view_id}'
