export interface UIText {
  text?: string;
  key?: string;
  params?: Record<string, string | number | UIText>;
  localized?: Record<string, string>;
}

interface UIElementProperties {
  key?: string;
  label?: string | null;
  readonly?: boolean | null;
  placeholder?: string | null;
  default_value?: unknown;
  params?: Record<string, string | number>;
  content?: string;
  max_length?: number | null;
  min_length?: number | null;
  hidden?: boolean | null;
  rows?: number | null;
  cols?: number | null;
  min_value?: number | null;
  max_value?: number | null;
  step?: number | null;
  select_options?: SelectOption[] | null;
  multi_select?: boolean;
  items?: ListRow[];
  row_actions?: ListAction[];
  count_labels?: {one: string; many: string};
  details_collapsible?: boolean;
  text?: UIText;
  tone?: "default" | "info" | "warning" | "success" | "muted" | "danger";
  outlined?: boolean;
  level?: number | "info" | "warning" | "error";
  children?: UIComponent[];
  value?: number;
  maximum?: number;
  action?: string;
  payload?: Record<string, unknown>;
  icon?: string;
}

export interface UIElement extends UIElementProperties {
  type: "paragraph" | "notification" | "number" | "toggle" | "text" | "textarea" | "select" | "button" | "list" | "filter" | "error" | "heading" | "section" | "inline" | "progress" | "action";
}

export interface UICondition {
  key: string;
  operator: "eq" | "neq" | "gt" | "geq" | "lt" | "leq" | "in" | "not_in" | "contains" | "not_contains" | "is_set" | "is_unset";
  value?: unknown;
  default_show?: boolean;
}

export interface Condition extends UIElementProperties {
  key: string;
  type: "condition";
  condition: UICondition;
  fields: UIComponent[];
}

export type UIComponent = UIElement | Condition;
export type UINode = UIComponent;

export interface GridHeaderAction {
  key: string;
  label?: string;
  icon?: string;
}

export interface UIGrid {
  key: string;
  label: string;
  collapsible?: boolean;
  default_collapsed?: boolean;
  header_action?: GridHeaderAction;
  content?: UIComponent[];
  fields: UIComponent[];
}

/** Include hidden descendants; conditions have no stored value. */
export function uiFields(elements: UIComponent[]): UIElement[] {
  return elements.flatMap(element => element.type === "condition"
    ? uiFields(element.fields)
    : [
      element,
      ...uiFields(element.children ?? []),
      ...(element.items ?? []).flatMap(row => uiFields([...(row.summary ?? []), ...(row.details ?? [])])),
    ]);
}

export function matchesUICondition(condition: UICondition, actual: unknown): boolean {
  const unset = actual === undefined || actual === null;
  if (condition.operator === "is_set") return !unset;
  if (condition.operator === "is_unset") return unset;
  if (unset) return condition.default_show ?? false;
  const expected = condition.value;
  switch (condition.operator) {
    case "eq": return actual === expected;
    case "neq": return actual !== expected;
    case "gt": case "geq": case "lt": case "leq":
      if (typeof actual !== "number" || typeof expected !== "number"
        || !Number.isFinite(actual) || !Number.isFinite(expected)) return false;
      switch (condition.operator) {
        case "gt": return actual > expected;
        case "geq": return actual >= expected;
        case "lt": return actual < expected;
        case "leq": return actual <= expected;
      }
    case "in": case "not_in":
      if (!Array.isArray(expected)) return false;
      return condition.operator === "in" ? expected.includes(actual) : !expected.includes(actual);
    case "contains": case "not_contains": {
      let contains: boolean;
      if (Array.isArray(actual)) contains = actual.includes(expected);
      else if (typeof actual === "string" && typeof expected === "string") contains = actual.includes(expected);
      else return false;
      return condition.operator === "contains" ? contains : !contains;
    }
    default: return false;
  }
}

export interface SelectOption {
  key: string;
  label: string;
  value: unknown;
  disabled: boolean;
}

export interface ListAction {
  action: string;
  icon?: string;
  label?: string;
  danger?: boolean;
  inline_edit?: boolean;
  secondary?: boolean;
  confirmation?: string;
}

export interface ListRow {
  key: string;
  title: string;
  title_key?: string;
  suffix?: string;
  meta?: string;
  params?: Record<string, string | number>;
  group?: string;
  pending?: boolean;
  tone?: string;
  details?: UIComponent[];
  summary?: UIComponent[];
  highlighted?: boolean;
}

export interface UIViewSection {
  key: string;
  label: string;
  voice_aliases?: string[];
  grids?: string[];
  content?: UINode[];
}

export interface PluginUIView {
  id: string;
  label: string;
  voice_aliases?: string[];
  description?: string;
  icon?: string;
  order?: number;
  modes?: ("configuring" | "running")[];
  sections: UIViewSection[];
}

export interface RegisteredUIView extends PluginUIView {
  pluginGuid: string;
  target: string;
}
