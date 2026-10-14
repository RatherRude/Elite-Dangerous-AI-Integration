export interface UIText {
  text?: string;
  key?: string;
  params?: Record<string, string | number | UIText>;
  localized?: Record<string, string>;
}

export interface UINode {
  key?: string;
  type: "text" | "heading" | "section" | "inline" | "list" | "progress" | "action";
  text?: UIText;
  tone?: "default" | "info" | "warning" | "success" | "muted" | "danger";
  outlined?: boolean;
  level?: number;
  children?: UINode[];
  value?: number;
  maximum?: number;
  action?: string;
  payload?: Record<string, unknown>;
  icon?: string;
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
