export interface UIText {
  text?: string;
  key?: string;
  params?: Record<string, string | number | UIText>;
  localized?: Record<string, string>;
}

export interface UIComponent {
  key?: string;
  type: "paragraph" | "number" | "toggle" | "text" | "textarea" | "select" | "button" | "list" | "filter" | "error" | "heading" | "section" | "inline" | "progress" | "action";
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
  text?: UIText;
  tone?: "default" | "info" | "warning" | "success" | "muted" | "danger";
  outlined?: boolean;
  level?: number;
  children?: UIComponent[];
  value?: number;
  maximum?: number;
  action?: string;
  payload?: Record<string, unknown>;
  icon?: string;
}

export type UINode = UIComponent;

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
}

export interface UIViewSection {
  key: string;
  label: string;
  grids?: string[];
  content?: UINode[];
}

export interface PluginUIView {
  id: string;
  label: string;
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
