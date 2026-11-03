# Plugin UI and Runtime Integration

This guide describes the declarative plugin UI framework implemented in this
checkout. It complements [Plugin development](Development.md); plugins targeting
an older application release must check that the hooks below are available.

## Architecture and ownership

The application supplies the plugin host, generic UI components, message
transport, lifecycle dispatch, and navigation. Each plugin supplies its views,
translations, interactions, state, and domain-specific presentation logic.

A plugin must be able to contribute its UI without adding an Angular import,
hardcoded tab, translation entry, or plugin-specific action instruction to the
application. Removing the plugin must leave no plugin-specific panel behind.

The framework extends the existing `PluginBase`, `PluginManager`, and
`PluginHelper` contracts. Views are Python dictionaries serialized to the
frontend; no separately compiled Angular component is required. Use the public
`TypedDict` constructors (`PluginSettings(...)`, `SettingsGrid(...)`,
`PluginUIView(...)`, `TextInput(...)`, `Button(...)`, `Progress(...)`, etc.) for declarations so type checkers can
check their fields. These constructors still produce ordinary dictionaries.

Relevant source files:

| Responsibility | Source |
| --- | --- |
| Public hooks | `src/lib/PluginBase.py` |
| Shared Python component types | `src/lib/PluginUIDefinitions.py` |
| Settings layout, provider types and deprecated component aliases | `src/lib/PluginSettingDefinitions.py` |
| Registration, publication, interaction routing | `src/lib/PluginManager.py` |
| Runtime event/action integration | `src/lib/PluginHelper.py` |
| Command handling before and during Run | `src/Chat.py` |
| Registered-view navigation | `src/lib/actions/actions_ui.py` |
| Frontend view/content types | `ui/src/app/services/plugin-ui.ts` |
| Contributions, translations, request/results | `ui/src/app/services/plugin-ui.service.ts` |
| View host and shared recursive renderer | `ui/src/app/components/plugin-view/`, `settings-field/`, `plugin-content/` |

## Lifecycle and public hooks

Plugins are instantiated before the assistant starts. Settings, translations,
and view definitions are registered during configuration. Runtime services are
provided only through `on_chat_start(helper)` after **Run**.

At registration, the core validates and freezes a namespace from the loaded
manifest. Duplicate namespaces are rejected. Settings ownership, translations,
UI routing, runtime helpers and data directories use this registry rather than
plugin-supplied ownership fields or later manifest changes. This is API-level
isolation for in-process Python plugins, not a process sandbox.

| `PluginBase` method | Contract |
| --- | --- |
| `on_registered()` | Called once after namespace assignment; initialize configuration-state data using `get_plugin_data_path()`. |
| `get_plugin_data_path()` | Return the core-owned data directory before or during Run. |
| `update_setting(key, value)` | Persist a flat local setting in this plugin's section. |
| `get_ui_views() -> list[PluginUIView]` | Return the current views. The default is an empty list. |
| `get_ui_settings() -> PluginSettings \| None` | Return the exported settings schema. Defaults to `settings_config`; override to convert internal data to generic presentation. |
| `get_ui_translations() -> dict[str, dict[str, Any]]` | Return language dictionaries. Defaults to `{}`. |
| `on_ui_action(action, payload) -> Any` | Handle an interaction and return a JSON-serializable result, or raise an error. |
| `on_ui_changed(key, value, state)` | Handle an input edit in either context with a detached snapshot of all current input values. |
| `get_ui_state()` | Return the same detached input snapshot, including from button/action callbacks. |
| `set_ui_value(key, value)` | Reset a declared, editable input for this plugin without saving or invoking input callbacks. Raises before registration or for unknown/readonly inputs; call `publish_ui()` afterward. |
| `publish_ui()` | Refresh and broadcast settings, views, input state, translations and provider settings. |
| `publish_settings()` | Deprecated alias of `publish_ui()`. |
| `get_app_config()` | Return a detached copy of application configuration with only this plugin's settings section, or `{}` before registration. |

`publish_ui()` and `publish_settings()` are available after settings registration,
including before Run. Before registration, they do nothing. They broadcast
derived presentation; they do not save it to `config.json` or persist plugin data.

The manager refreshes contributions after runtime start/stop hooks and successful
UI actions. For asynchronous or event-driven changes, update plugin-owned state
and call `publish_ui()` once for both contexts. Persisted configuration changes
also refresh both contexts after `on_settings_changed()`.

Keep contribution getters fast and free of operations such as station searches
or route calculations. Opening or refreshing a panel should display existing
state. Perform calculations through an explicit plugin action.

## View definitions

A `PluginUIView` contains:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | Yes | Nonempty local identifier, unique within the plugin, without `:`. |
| `label` | Yes | User-facing translation key. |
| `voice_aliases` | No | Business names/synonyms in any supported language, independent of the displayed label. |
| `sections` | Yes | Ordered section definitions. |
| `icon` | No | Material icon name. |
| `description` | No | Assistant-facing description used in the `showUI` tool schema. Explain the view's purpose and any preparation action here. |
| `order` | No | Frontend ordering priority; defaults to `0`. Ties use the full navigation target. |
| `modes` | No | `['running']` by default; use `['configuring']` or both modes as needed. |

Runtime views appear as dynamically created main tabs. Configuration views are
rendered below the settings menu. Sections appear as tabs inside the view.

Each section has a stable `key`, a translated `label`, and optionally:

- `grids`: ordered keys referencing grids from this plugin's exported settings.
- `content`: ordered generic content nodes.
- `voice_aliases`: business names/synonyms for this subtab, independent of its displayed label or GUI language.

Both may be supplied: the grids render first, followed by content. Missing grid
references produce no grid. Keep section keys unique and stable for navigation.

The `showUI` schema includes translated view/subtab labels from every registered
language, their stable keys and `voice_aliases`. For example:

```python
UIViewSection(
    key="session",
    label="@progress.title",
    voice_aliases=["progression du vaisseau", "suivi des ameliorations", "ship upgrade progress"],
    grids=["session"],
)
```

The GUI may display **Progress** while French voice requests select this same
subtab. Exact French/English display requests, including `affiche-moi`,
`montre-moi` and `show me`, are resolved locally from published plugin metadata
before the action cache or model, even when the action cache is disabled.
They open the requested view/subtab first; the assistant may then give a spoken
summary, but a status-reading operation alone does not fulfill a display request.
No domain-specific plugin names are embedded in this local resolver.
The same requests are also prefilled against the final tool schema.
When multiple plugin views are
available, unqualified plugin navigation requests go through the model rather
than a direct prefilled shortcut, so semantically similar aliases cannot bypass
disambiguation. Qualified subtab requests include the view name, for example
`show progress in ship upgrades`. Exact collisions, including accent variants,
are never prefilled, even when qualified.

The tool exposes each view's owning plugin name alongside its translated labels
and aliases. If multiple plugins, views or subtabs plausibly match the request,
the assistant must ask the player which one they mean, naming the alternatives
in the player's language, and leave the UI unchanged until clarified. It must
not choose based on registration order or the currently open tab. Explicitly
identifying a view/subtab allows navigation; a shared alias alone does not.
Publishing new labels, aliases or available views refreshes navigation without
changing plugin data or overriding built-in navigation shortcuts.

`setUISectionExpanded` controls collapsible content in the active subtab by name
or one-based visible header index. The tool receives available plugin grid,
category and detail labels. The shared renderer exposes stable identities and
translations for lookup; generic Material accordion headers and native `details`
summaries are also supported. Headers hidden in inactive tabs or under a closed
parent are excluded from indexing. The command carries a correlated request ID;
the desktop UI acknowledges the actual expanded state through
`ui_section_result`. Errors and a five-second timeout are returned
to the assistant. These are transient presentation changes, not plugin actions.

## Shared components

Conditional settings from the host remain supported alongside shared components,
collapsible grids and grouped buttons. Hidden fields keep their saved values and
defaults; hidden buttons are not selected by Enter-to-submit. Plugin notification
labels and content use the same translation resolution as other shared fields.

Settings `fields`, grid `content`, view-section `content`, container `children`
and list-row `details` all accept the same `UIComponent` union and use the same
recursive renderer. A text input or button does not have to be placed inside a
settings grid to work in a view; progress and other display components do not
have to be placed in a separate settings `content` array.

Import new typed constructors from `lib.PluginUIDefinitions`:

| Constructor | `type` | Purpose |
| --- | --- | --- |
| `TextInput`, `TextArea`, `NumberInput`, `Toggle`, `Select`, `Filter` | `text`, `textarea`, `number`, `toggle`, `select`, `filter` | Inputs with local keys, labels and typed `default_value` properties. |
| `Button` | `button` | Calls `on_settings_button(key)` by default, in either context. Set `action` and optional `payload` to call `on_ui_action` instead. |
| `Paragraph`, `Error` | `paragraph`, `error` | Label and `content`, with optional interpolation `params`. |
| `Text`, `Heading`, `Section`, `Inline`, `List`, `Progress`, `Action` | See below | Display, layout and structured actions. |

Constructors still require the explicit `type` discriminator, as historical
settings constructors did. `TextInput(type="text", ...)` is an input;
`Text(type="text", text=UIText(...))` displays text. `List` can have `items` and
`row_actions`, or `children` for a bullet list. Input keys are nonempty, flat,
local names; reusing a key in settings and views deliberately shares its value.
Use distinct keys for independent inputs.

### Historical aliases

The original import path `lib.PluginSettingDefinitions` remains supported.
These names are deprecated aliases, not wrappers, and still construct ordinary
dictionaries with the same properties and behavior:

| Historical name | Shared constructor |
| --- | --- |
| `SettingBase` | `InputBase` |
| `TextSetting` | `TextInput` (including password input through `hidden=True`) |
| `TextAreaSetting` | `TextArea` |
| `NumericalSetting` | `NumberInput` |
| `ToggleSetting` | `Toggle` |
| `SelectSetting` | `Select` |
| `ButtonSetting` | `Button` |
| `ParagraphSetting` | `Paragraph` |
| `ErrorSetting` | `Error` |

`PluginSettings`, `SettingsGrid`, `SelectOption` and provider definitions retain
their import paths. The additional `FilterSetting` and `ListSetting` names also
remain aliases. Existing `settings_config`, `on_settings_changed()` and
single-argument `on_settings_button(key)` implementations continue to work.

### Display and layout

`UINode` is a recursive presentation structure:

| `type` | Rendering and relevant fields |
| --- | --- |
| `text` | Text from `text: UIText`. |
| `heading` | A heading; `level: 4` uses `h4`, otherwise `h3`. |
| `section` | A container with `children`; `outlined: true` adds a highlighted border. |
| `inline` | A wrapping horizontal group of `children`. |
| `list` | A bullet list with one item per child. |
| `progress` | Optional text and a progress bar: `value / maximum`, clamped to 0–100%; missing/zero maximum displays 0%. |
| `action` | A button with translated text, optional `icon`, an `action` identifier and optional structured `payload`. |

Optional `tone` values are `default`, `info`, `warning`, `success`, `muted`, and
`danger`. A node may also carry a `key`; content order follows the supplied array.
Grouping, sorting, domain rules, and deciding which tone to use belong to the
plugin. The renderer does not inspect domain-specific field names.

### Text and translations

A `UIText` supports:

```python
from lib.PluginUIDefinitions import UIText

UIText(
    key="@missing",
    params={
        "resource": UIText(localized={"en": "Iron", "fr": "Fer"}),
        "count": 2,
    },
    text="Fallback text",
)
```

Parameters may be strings, numbers, or nested `UIText` objects. Nested text is
resolved before translation interpolation. For the text itself, a known key wins;
otherwise the renderer tries the current language's `localized` value, its English
value, then `text`. An unknown key without a fallback remains visible as a key.

Use `@local.key` for plugin-owned translation references and return local
dictionaries. The core qualifies presentation references, including nested
`UIText` parameters, as `plugin.<registered-guid>.local.key`. It does not rewrite
literal text, action payloads, setting values or option values. Core keys such as
`common.cancel` remain available. For example:

```python
def get_ui_translations(self):
    return {
        "en": {"title": "Dashboard", "missing": "{{resource}}: {{count}} missing"},
        "fr": {"title": "Tableau de bord", "missing": "{{resource}} : {{count}} manquants"},
    }
```

Ship these translations with the plugin, for example in a JSON file loaded by
the hook. The manager sends the initial `plugin_ui` contribution before settings.
The frontend wraps each local dictionary in the owner supplied by the registry,
then merges translations for each language and clears previous plugin
contributions when a new registry replaces them or the backend restarts.

Use translated text for UI chrome and status messages. Literal fallbacks are
useful for data such as user-defined names. Core strings such as `common.cancel`
may be reused. Backend error strings surfaced in the UI should also be keys.

The host uses `@ngx-translate/core` with bundled English/French dictionaries in
`ui/src/app/services/i18n-translations.ts` and an inline loader. English is the
initial language; `TranslateService.use(language)` selects another loaded language.
Settings strings that look like dot-separated translation keys are resolved with
their parameters. Literal labels from existing plugins continue to display as-is.

## Settings tabs and lists

Settings may include an optional `header_link: SettingsHeaderLink` contribution.
It renders a small, right-aligned line above the settings tabs, wrapping on narrow
windows, and is not rendered in runtime views. `text` and `label` accept local
translation references; `url` must be an absolute HTTP(S) address. The link opens
externally through the application's existing external-link handling.

```python
from lib.PluginSettingDefinitions import SettingsHeaderLink

header_link = SettingsHeaderLink(
    text="@project.prompt", label="@project.link", url="https://example.org/project",
)
```

Settings grids may include optional `content: list[UIComponent]`, rendered after their
fields by the same component renderer used in views. Reference that grid
from both a settings tab and a runtime section to share one presentation across
lifecycle modes. An empty grid label omits the non-collapsible grid header.

The existing grid/field settings UI remains available. Plugins may declare
settings tabs explicitly:

```python
from lib.PluginSettingDefinitions import PluginSettings, SettingsTab

PluginSettings(
    key="settings",
    label="@title",
    icon="dashboard",
    grids=grids,
    tabs=[
        SettingsTab(key="general", label="@general", grids=["options", "status"]),
        SettingsTab(key="library", label="@library", grids=["import", "items"]),
    ],
)
```

Without `tabs`, grids retain flat rendering. With `tabs`, the plugin chooses which
grids to include and their order; the host does not infer tabs from grid names.

Generic list rows support `key`, `title`, optional `title_key`, `suffix`, `meta`,
`params`, `group`, `pending`, `tone`, `summary: list[UIComponent]`,
`highlighted`, and `details: list[UIComponent]`. List fields may
supply `count_labels: {one: <key>, many: <key>}` using a `count` parameter; absent
labels fall back to the host's generic item count. `row_actions` belongs to the
list field, not an individual row.

Set `details_collapsible=True` on a list to put row details behind a native
disclosure, initially closed; the compact `summary` stays visible. Without this
flag existing detail rendering is unchanged. A newly `highlighted` row is
accented and reveals its collapsed group, which the user can collapse again.

Row actions are visible icon buttons by default. `secondary=True` moves an
action into the row's overflow menu. An optional `confirmation` translation key
opens the standard confirmation dialog before performing the action (including
inline edits). Its interpolation parameters include row `params` plus `title`.
Cancellation does not invoke the backend. Enforcement of data constraints must
still happen in the plugin.

List row buttons continue to call `on_settings_button('<action>:<row-key>', value)`;
inline edits pass the edited value. Grid header actions and ordinary buttons
also use the existing button hook. Generic action nodes inside row `details`
instead carry their own structured payload to `on_ui_action`.

## UI interactions and transport

### Input callbacks and persistence

All ordinary plugin and model-provider input edits use the reserved `ui_changed`
action with `payload={"key": "<local input key>", "value": ...}`. The core
validates that the input is declared and editable, then calls
`on_ui_changed(key, value, state)` before publishing both contexts. The `state`
argument includes defaults, persisted settings and the latest transient edits,
including the current edit. It is constructed by the core, not trusted from a
client-supplied snapshot. Separate plugins have separate input state. State
snapshots are detached; mutating a snapshot does not change core input state.
Character-scoped provider voice settings keep their character persistence path.

The default callback persists inputs declared in exported settings or ordinary
model-provider settings, then calls the historical `on_settings_changed()` hook.
Inputs declared only in views are transient by default. Override the callback
to choose which edits persist, regardless of where an input is rendered:

```python
def on_ui_changed(self, key, value, state):
    if key == "search":
        self.query = state["search"]
        self.filtered_items = [
            item for item in self.items if self.query.casefold() in item.casefold()
        ]
        # No persistence: the core publishes the filtered presentation on return.
    elif key == "preferred_item":
        self.update_setting(key, value)
    else:
        super().on_ui_changed(key, value, state)
```

An override that does not call `super()` owns its persistence policy; UI
publication alone never saves preferences. Buttons and structured actions can
read the same current values with `self.get_ui_state()`. The old
`change_config` and `plugin_settings_button` transports remain accepted.
Invalid input keys, readonly inputs and callback exceptions produce correlated
failure results; rejected transient edits are rolled back.

### Dynamic updates

Change plugin-owned presentation data and call `self.publish_ui()` once.
For example, a `Select` can return fresh `select_options`, a `Text` can return a
new status message, and a `Progress` can return a new `value`. The publication
rebuilds both settings and views, along with provider settings and translations,
without writing configuration. Removed settings or views disappear on the next
publication. Dynamic publications retain current input values; newer pending
typing is not replaced by an earlier request's snapshot.

```python
from lib.PluginUIDefinitions import Select, SelectOption, Progress, UIText

def status_components(self):
    return [
        Select(key="preferred_item", type="select", label="Item",
               default_value=None, multi_select=False,
               select_options=[
                   SelectOption(key=item, label=item, value=item, disabled=False)
                   for item in self.filtered_items
               ]),
        Progress(type="progress", value=self.completed, maximum=self.total,
                 text=UIText(text=self.status)),
    ]
```

Return this list from settings `fields` or view-section `content` without
converting it. In background/event work, update `filtered_items`, `status` or
`completed`, then publish. Synchronize shared plugin state if work is concurrent.

### Action request/results

The frontend sends:

```json
{
  "type": "plugin_ui_action",
  "timestamp": "2026-10-14T12:00:00Z",
  "request_id": "plugin-ui-1",
  "plugin_guid": "example-guid",
  "action": "refresh",
  "payload": {"item_id": "one"}
}
```

The manager locates the owning plugin by GUID and calls `on_ui_action` (or
`on_ui_changed` for an input edit). For a
successful action, it refreshes paragraph values and UI/settings contributions,
then emits a correlated result:

```json
{
  "type": "plugin_ui_result",
  "request_id": "plugin-ui-1",
  "plugin_guid": "example-guid",
  "success": true,
  "result": {"updated": true}
}
```

A failure has `success: false` and `error: <string>`. Backend messages also carry
the normal timestamp; the frontend transport supplies its message index.
Unknown owners return `common.pluginUnavailable`. The base implementation returns
`common.invalidAction` for unsupported actions or malformed button payloads.

The reserved action `settings_button` forwards `payload.key` and optional string
`payload.value` to `on_settings_button`. When overriding `on_ui_action`, delegate
unhandled actions to `super()` to preserve that behavior. The legacy
`plugin_settings_button` command remains supported for existing callers.

For transient success feedback, an action can return
`{"notification": "@added", "params": {"name": "Item"}}`. The core scopes
`notification` and list-action `confirmation` translation references to the
plugin owner, preserving literal parameter values. The frontend displays the
translated notification for four seconds only after a correlated successful
action result. It is not a field or durable state: repeated UI publications do
not replay it. Errors should still be raised or shown explicitly inline.

UI callbacks execute synchronously in the backend command reader. The frontend
waits for the backend result rather than considering a successful send to be
successful execution. Requests time out after 120 seconds; this timeout does not
cancel backend work. For long operations, return promptly and publish later results
from plugin-managed work, with appropriate synchronization of plugin state.

## Navigation and assistant integration

Each view has a stable target:

```text
plugin:<plugin-guid>:<view-id>
```

The `showUI` tool's allowed targets and section choices are refreshed from
registered runtime contributions. An example tool argument object is:

```json
{"tab": "plugin:example-guid:dashboard", "submenu": "overview"}
```

The backend validates the view and section before requesting frontend navigation.
The same local view ID can be used by different plugins because its GUID forms
part of the target. Configuration-only views are not exposed through this runtime
navigation action.

Use the view's `description`, registered action descriptions, and status
generators for plugin-specific guidance to the assistant. The host's built-in
action descriptions must not name an optional plugin's actions. Selecting a view
does not calculate a route, fetch external data, or perform a plugin operation.

## Runtime events and state

Register runtime behavior in `on_chat_start(helper)` using existing APIs:

- `register_action`: an assistant tool with Pydantic parameters and a callback.
- `register_projection`: plugin state updated from events, with persistence/replay
  managed by the event manager. Projection names use class names; choose distinct
  names to avoid collisions.
- `register_sideeffect`: a callback receiving an event and current projection states.
- `register_event` and `dispatch_event`: custom `PluginEvent` handling and optional
  assistant replies. Use distinctive event names and `plugin_event_content`.
- `register_status_generator`: plugin context included in assistant status output.
- `get_current_state()`: the processed events and current projection-state mapping.

Current projection states may be Pydantic models. Treat these shared objects as
read-only; use `model_dump()` when a plain dictionary is required. Registering a
side effect does not replay historical journal entries through that callback:
the event pipeline updates projections for historic `GameEvent`s, then skips side
effects for them. Seed the UI from current projections at runtime startup.

Runtime events are not supplied by `PluginHelper` before Run. A configuration UI
can still operate on plugin-owned data; any configuration-state journal watching
is a separate plugin implementation. Keep event callbacks short and avoid network
requests or expensive computation on the event-processing path.

## Complete example: an event-driven dashboard

Place the following class in the Python entrypoint identified by your manifest.
It has a settings button available before Run, a runtime dashboard, translated
messages, a structured UI action, and live updates after a `Docked` event.

For example, use `plugins/dashboard/dashboard.py` with this `manifest.json`
(generate a new GUID for your own plugin):

```json
{
  "guid": "a1b2c3d4-0000-4000-8000-000000000001",
  "name": "Dashboard Example",
  "author": "Example Author",
  "version": "0.1.0",
  "description": "An event-driven plugin dashboard.",
  "entrypoint": "dashboard.py"
}
```

```python
from typing import Any

from lib.Event import GameEvent
from lib.PluginBase import PluginBase, PluginManifest
from lib.PluginHelper import PluginHelper
from lib.PluginSettingDefinitions import PluginSettings, SettingsGrid, SettingsTab
from lib.PluginUIDefinitions import Button, PluginUIView, Text, Action, UIText, UIViewSection


class DashboardPlugin(PluginBase):
    def __init__(self, plugin_manifest: PluginManifest):
        super().__init__(plugin_manifest)
        self._helper = None
        self._system = ""
        self.settings_config = PluginSettings(
            key="settings",
            label="@title",
            icon="dashboard",
            grids=[SettingsGrid(
                key="general",
                label="@general",
                fields=[Button(
                    key="refresh", label="@refresh", type="button",
                    readonly=False, placeholder=None, icon="refresh",
                )],
            )],
            tabs=[SettingsTab(key="general", label="@general", grids=["general"])],
        )

    def get_ui_translations(self):
        return {
            "en": {
                "title": "Dashboard", "general": "General", "overview": "Overview",
                "refresh": "Refresh", "location": "Current system: {{system}}",
                "unknown": "Unknown", "runtimeRequired": "Start the assistant first.",
            },
            "fr": {
                "title": "Tableau de bord", "general": "Général", "overview": "Vue d’ensemble",
                "refresh": "Actualiser", "location": "Système actuel : {{system}}",
                "unknown": "Inconnu", "runtimeRequired": "Démarrez d’abord l’assistant.",
            },
        }

    def get_ui_views(self) -> list[PluginUIView]:
        system = UIText(text=self._system) if self._system else UIText(key="@unknown")
        return [PluginUIView(
            id="dashboard",
            label="@title",
            description="Shows the current system from existing runtime state.",
            icon="dashboard",
            modes=["running"],
            sections=[UIViewSection(
                key="overview",
                label="@overview",
                content=[
                    Text(type="text", text=UIText(
                        key="@location", params={"system": system},
                    )),
                    Action(type="action", action="refresh",
                           text=UIText(key="@refresh"), icon="refresh"),
                ],
            )],
        )]

    def _read_location(self):
        if self._helper is None:
            return
        _, states = self._helper.get_current_state()
        location = states.get("Location")
        if hasattr(location, "model_dump"):
            location = location.model_dump()
        self._system = str((location or {}).get("StarSystem") or "")

    def on_chat_start(self, helper: PluginHelper):
        self._helper = helper
        self._read_location()
        helper.register_sideeffect(self._on_event)

    def on_chat_stop(self, helper: PluginHelper):
        self._helper = None

    def _on_event(self, event, states):
        if isinstance(event, GameEvent) and event.content.get("event") == "Docked":
            self._system = str(event.content.get("StarSystem") or "")
            self.publish_ui()

    def on_settings_button(self, key: str, value: str | None = None):
        if key != "refresh":
            raise ValueError("common.invalidAction")
        self._read_location()
        self.publish_ui()

    def on_ui_action(self, action: str, payload: dict[str, Any]) -> Any:
        if action != "refresh":
            return super().on_ui_action(action, payload)
        if self._helper is None:
            raise ValueError("@runtimeRequired")
        self._read_location()
        return {"updated": True}
```

The manager publishes the initial dashboard after `on_chat_start`, republishes
it after successful UI actions, and the event handler publishes its own updates.
No dashboard-specific changes are needed in the core or frontend.

## Migrating an existing plugin

1. Replace hardcoded main-view imports/tabs with `get_ui_views()` contributions.
2. Declare settings `tabs` instead of relying on host-side grid-name heuristics.
3. Supply local dictionaries through `get_ui_translations()` and use `@local.key` references; the core assigns ownership.
4. Convert domain list/progress data into `suffix`, `tone`, `count_labels`, and
   generic `details` rather than adding domain fields to the host's settings types.
5. Generate grouped work content in the plugin rather than interpreting
   field-name prefixes in a shared Angular component.
6. Use `publish_ui()` and `helper.get_current_state()`
   instead of mutating manager registries or reading private runtime fields.
7. Replace explicit-GUID setting updates with `update_setting(key, value)`;
   use local event names and parameterless data-path APIs. Move configuration
   data initialization out of the constructor into `on_registered()`.
8. Put plugin-specific assistant guidance in its view/action descriptions or
   status generator, then remove such references from built-in actions.

Defaults preserve settings-only plugins and the existing settings button hook.
The manifest and model-provider contracts are unchanged. Existing button hooks
that accept only `key` remain supported when no inline-edit value is supplied.
Legacy fully qualified translation references and dictionaries are accepted only
for the registered owner. Cross-plugin references and contributions are rejected.
The settings schema's top-level `key` is overwritten by the core. Legacy helper
manager setting updates are restricted to the helper's registered owner.

The current contract uses full registry snapshots and synchronous interactions.
It does not register arbitrary JavaScript/Angular components, define an inter-plugin
bus, or provide hot installation/unloading. Runtime validation checks namespace
ownership, translation dictionaries/references, view IDs and the default button
payload, rather than every nested content field.

## Validation

Focused regression coverage:

- `test/lib/test_plugin_namespace.py`: registration identity, duplicate namespaces,
  isolated settings/data paths/events/translations, and local UI error references.
- `test/lib/test_plugin_ui.py`: two plugins sharing local view IDs, owner routing,
  success/error results, event-driven publication, dynamic navigation, and no plugins.
- `ui/src/app/services/plugin-ui.service.spec.ts`: translations, registry replacement,
  backend restart, and correlated interaction results.
- `ui/src/app/components/plugin-content/plugin-content.component.spec.ts`: nested
  rendering, translated parameters, progress, tones, and structured actions.
- `ui/src/app/components/plugin-view/plugin-view.component.spec.ts`: pre-mount
  navigation and preserving user section selection across content updates.
- `ui/src/app/components/settings-field/settings-field.component.spec.ts`: grouped
  lists, inline editing, translated counts, and actions in generic row details.
- `ui/src/app/services/setting-text.spec.ts`: language selection, parameters,
  legacy literals, and translation fallbacks.

From the repository root:

```powershell
.\.venv312\Scripts\python.exe -m pytest -q test/lib/test_plugin_manager_settings.py test/lib/test_plugin_ui.py
.\.venv312\Scripts\python.exe -m pytest -q
git diff --check
```

Run plugin-specific tests separately when changing a plugin: the global pytest
configuration excludes directories named `plugins`. From `ui/`:

```powershell
$env:Path = 'C:\Program Files\nodejs;' + $env:Path
npm run build
npm test -- --watch=false --browsers=ChromeHeadless --include=src/app/services/setting-text.spec.ts --include=src/app/services/plugin-ui.service.spec.ts --include=src/app/components/plugin-content/plugin-content.component.spec.ts --include=src/app/components/plugin-view/plugin-view.component.spec.ts --include=src/app/components/settings-grid/settings-grid.component.spec.ts --include=src/app/components/settings-field/settings-field.component.spec.ts --include=src/app/services/provider-ui.spec.ts
```

Use `CHROME_BIN` when a Chromium-compatible browser is installed outside the
launcher's default location.
