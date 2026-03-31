import json
import requests
import quickjs
from typing import Optional, Dict, Tuple, Any, Literal
from .Database import CodeStore
from .Logger import PromptUsageStats, log_llm_usage, log, observe

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
You are an expert UI Engineer for Elite Dangerous.
Your goal is to update a collection of Preact components that visualize game state.

CRITICAL RULES:
1. ENVIRONMENT: You are running in a specific QuickJS environment.
   - NO 'import' statements.
   - 'preact', 'htm', 'renderToString' are already loaded globally.
   - Use 'html' (tagged template) instead of JSX.

2. SYNTAX:
   - Define your component as a function accepting a 'props' object.
   - The game state is passed as 'props.state'.
   - Return html`...`.
   - Use Tailwind CSS for styling.

3. COMPONENT STRUCTURE:
   - The root component MUST be named `App`.
   - You MAY create and edit additional helper components as separate components in the collection.
   - `App` remains the entry point rendered by validation.

4. ROBUSTNESS:
   - Always check if nested properties exist in 'state' before accessing them to prevent runtime errors.
   - Example: state.ship?.fuel?.current ?? 0

5. EDITING WORKFLOW:
   - Call `list_components()` to see the current component collection.
   - You are editing a collection of components via tools, not by printing the full code.
   - Call `read(component_name, offset?, limit?)` to inspect one component before editing.
   - Use `write(component_name, content)` to create or fully replace a component.
   - Use `edit(component_name, old_string, new_string, replace_all?)` for exact string replacements within one component.
   - Use `clear_overlay_ui(component_names?)` to delete helper components. It can never delete `App`.
   - If removing helper components changes what `App` renders, update `App` and then run `validate()`.
   - Use `get_projection_schema(projection_name)` when you need the detailed schema and current value for a specific projection.
   - Prefer small, targeted edits over broad rewrites.
   - After making changes, call `validate()` to run SSR validation.
   - Do not paste the full component collection in assistant messages.

6. CHANGE SCOPE:
   - Only apply minimal changes needed to fulfill the user's request.
   - Preserve existing functionality, layout, and style as much as possible.
   - Avoid large rewrites unless absolutely necessary.
"""

GENUI_COMPONENTS_ROOT = r"C:\genui\components"
GENUI_LOG_PREFIX = "Generating UI"
GENUI_COMPONENT_START = "// COMPONENT:"
GENUI_COMPONENT_END = "// END COMPONENT:"

GENUI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_components",
            "description": "List the current components in the editable UI collection.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "Read one component from the editable UI collection, optionally using line-based offset and limit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The component to read. App is the root component."
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Optional 0-based starting line offset."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Optional maximum number of lines to return."
                    }
                },
                "required": ["component_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Create or fully replace one component in the editable UI collection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The component to create or replace. App is the root component."
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete component source code."
                    }
                },
                "required": ["component_name", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Perform an exact string replacement in one editable UI component.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_name": {
                        "type": "string",
                        "description": "The component to modify."
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact text to replace."
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The replacement text. Must be different from old_string."
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "Replace all occurrences of old_string instead of only the first occurrence."
                    }
                },
                "required": ["component_name", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "clear_overlay_ui",
            "description": "Delete one or more helper components from the editable UI collection. This tool never deletes App.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_names": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Optional helper component names to delete. If omitted, all helper components except App are deleted."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_projection_schema",
            "description": "Return the detailed schema and current value for a specific projection in props.state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "projection_name": {
                        "type": "string",
                        "description": "The projection name to inspect, such as CurrentStatus or Cargo."
                    }
                },
                "required": ["projection_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate",
            "description": "Run SSR validation for the current file and return rendered HTML on success.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


def _preview_for_log(value: Any, max_len: int = 120) -> str:
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _log_genui(level: Literal["info", "debug", "warn", "error"], message: str, *args: Any) -> None:
    log(level, f"{GENUI_LOG_PREFIX}: {message}", *args)


def _component_virtual_path(component_name: str) -> str:
    return f"{GENUI_COMPONENTS_ROOT}\\{component_name}.js"


def _normalize_component_name(component_name: Any) -> str | None:
    if not isinstance(component_name, str):
        return None
    normalized = component_name.strip()
    if not normalized:
        return None
    return normalized


def _clean_projection_description(description: Any) -> str:
    text = str(description or "").strip()
    text = " ".join(text.split())
    return text or "No description available."


def _build_projection_catalog(state_schema: Dict[str, Any]) -> str:
    lines = ["Available Projections (use get_projection_schema for full field details):"]
    for projection_name in sorted(state_schema.keys()):
        schema_entry = state_schema.get(projection_name, {})
        description = ""
        if isinstance(schema_entry, dict):
            description = _clean_projection_description(schema_entry.get("description"))
        else:
            description = "No description available."
        lines.append(f"- {projection_name}: {description}")
    return "\n".join(lines)


def build_default_component_collection() -> dict[str, str]:
    return {
        "EmptyState": """const EmptyState = () => {
  return html`<div></div>`;
};""",
        "App": """const App = ({ state }) => {
  return html`<${EmptyState} />`;
};""",
    }


def build_default_component_code() -> str:
    return _compose_component_code(build_default_component_collection())


def _initialize_component_collection(current_code: str) -> dict[str, str]:
    parsed_components: dict[str, str] = {}
    current_component_name: str | None = None
    current_component_lines: list[str] = []

    for line in current_code.splitlines():
        stripped = line.strip()
        if stripped.startswith(GENUI_COMPONENT_START):
            if current_component_name is not None:
                return {"App": current_code}
            current_component_name = stripped[len(GENUI_COMPONENT_START):].strip()
            current_component_lines = []
            continue

        if stripped.startswith(GENUI_COMPONENT_END):
            end_component_name = stripped[len(GENUI_COMPONENT_END):].strip()
            if current_component_name is None or end_component_name != current_component_name:
                return {"App": current_code}
            parsed_components[current_component_name] = "\n".join(current_component_lines).strip()
            current_component_name = None
            current_component_lines = []
            continue

        if current_component_name is not None:
            current_component_lines.append(line)

    if current_component_name is not None:
        return {"App": current_code}

    if parsed_components:
        return parsed_components

    return {
        "App": current_code,
    }


def _build_component_catalog(components: dict[str, str]) -> str:
    lines = ["Current Components (use list_components to refresh, read to inspect):"]
    for component_name in sorted(components.keys()):
        marker = "root component" if component_name == "App" else "helper component"
        lines.append(f"- {component_name}: {marker}")
    return "\n".join(lines)


def _compose_component_code(components: dict[str, str]) -> str:
    ordered_names = [name for name in sorted(components.keys()) if name != "App"]
    if "App" in components:
        ordered_names.append("App")
    return "\n\n".join(
        "\n".join([
            f"{GENUI_COMPONENT_START} {component_name}",
            component_code.strip(),
            f"{GENUI_COMPONENT_END} {component_name}",
        ])
        for component_name in ordered_names
        if (component_code := components.get(component_name, "").strip())
    )

def build_preact_bundle():
    print("Downloading libraries...")
    
    # 1. Define the UMD URLs
    # We use specific versions to ensure compatibility
    libs = [
        "https://unpkg.com/preact@10.19.3/dist/preact.umd.js",
        "https://unpkg.com/htm@3.1.1/dist/htm.umd.js", 
        "https://unpkg.com/preact-render-to-string@6.3.1/dist/index.umd.js"
    ]
    
    bundle_content = []
    
    try:
        for url in libs:
            print(f"Fetching {url}...")
            response = requests.get(url)
            response.raise_for_status()
            bundle_content.append(response.text)
            
        # 2. Add the "Bridge" Code
        # This exposes the libraries to the global scope so QuickJS can see them
        bridge_code = """
        // --- GLOBAL BRIDGE ---
        var preact = this.preact || window.preact;
        var htm = this.htm || window.htm;
        var preactRenderToString = this.preactRenderToString || window.preactRenderToString;
        
        // Bind htm to preact immediately for convenience
        var html = htm.bind(preact.h);
        var render = preactRenderToString.render;
        """
        bundle_content.append(bridge_code)
            
        print("✅ Preact bundle built successfully.")
        
        return bundle_content
        
    except Exception as e:
        print(f"❌ Error building bundle: {e}")
        return None

class GenUIValidator:
    def __init__(self):
        # Build the bundle in memory (not stored on disk)
        print("Building Preact bundle...")
        bundle_parts = build_preact_bundle()
        if bundle_parts:
            self.bundle_code = "\n".join(bundle_parts)
        else:
            self.bundle_code = "/* Missing Bundle */" 
            print("WARNING: Failed to build bundle. Validation will fail.")

    @observe()
    def validate(self, code: str, mock_state: Dict) -> Tuple[bool, str]:
        _log_genui("debug", f"Starting SSR validation for code length={len(code)}")
        ctx = quickjs.Context()
        
        # --- 1. ENVIRONMENT MOCK (The Fix) ---
        # We define 'window' and 'self' so UMD libraries attach correctly.
        # We also create a 'console' so libraries don't crash on logging.
        env_setup = """
        const window = this;
        const self = this;
        const global = this;
        const console = { 
            log: (msg) => {}, 
            error: (msg) => {}, 
            warn: (msg) => {} 
        };
        """

        # --- 2. LOAD LIBRARIES ---
        # Inject the bundle. It will now attach 'preact' to 'window.preact'
        libs = f"""
        {self.bundle_code}
        """

        # --- 3. BRIDGE & SETUP ---
        # Safely extract globals. The bridge code already defines preact, htm, html, render
        setup = """
        // Ensure we have the libraries (already defined by bridge, just validate)
        if (!preact) throw new Error("Preact failed to load from bundle.");
        if (!htm) throw new Error("HTM failed to load from bundle.");
        
        // Extract additional utilities from preact
        var h = preact.h;
        var Component = preact.Component;
        
        // Ensure render is available (handle different bundle versions)
        if (!render) {
            render = preactRenderToString.render || preactRenderToString;
        }
        """

        # --- 4. DATA INJECTION ---
        data = f"const mockState = {json.dumps(mock_state)};"

        # --- 5. EXECUTION HARNESS ---
        harness = f"""
        {env_setup}
        {libs}
        {setup}
        {data}

        // Declare _App in outer scope to capture user's App component
        var _App;

        // WRAP USER CODE
        try {{
            {code}
            // Capture the App component into outer scope
            _App = App;
        }} catch (e) {{
            throw new Error("Syntax Error in User Code: " + e.toString());
        }}

        // RUN SSR
        try {{
            if (typeof _App !== 'function') throw new Error("No App component found. Define a component named 'App'.");
            
            // Render!
            const output = render(html`<${{_App}} state=${{mockState}} />`);
            
            if (typeof output !== 'string') throw new Error("Output was not a string.");
            
            output; // Return to Python
            
        }} catch (e) {{
            throw new Error("SSR Validation Error: " + e.toString());
        }}
        """

        try:
            result = ctx.eval(harness)
            _log_genui("info", f"SSR validation succeeded rendered_length={len(result)}")
            return True, result
        except quickjs.JSException as e:
            _log_genui("warn", "SSR validation failed with JS exception", str(e))
            return False, str(e)
        except Exception as e:
            _log_genui("error", "SSR validation failed with system error", str(e))
            return False, f"System Error: {str(e)}"


# Review system prompt for validating generated HTML
REVIEW_SYSTEM_PROMPT = """
You are a QA engineer reviewing generated HTML output from a Preact component.
Your job is to verify that the rendered HTML correctly implements the user's request.

You will be given:
1. The original user instruction
2. The generated Preact component code
3. The rendered HTML output from SSR (Server-Side Rendering)

Evaluate whether the HTML output:
- Correctly displays the requested information
- Has proper structure and layout
- Uses appropriate styling for an Elite Dangerous game overlay
- Handles edge cases (empty data, missing values) 

Be lenient on different interpretations of the content that is shown. The user's instruction may be impossible to implement exactly as requested.

You MUST call one of the provided tools to indicate your decision:
- Use 'approve_ui' if the output is correct and meets the requirements
- Use 'reject_ui' if there are issues that need to be fixed
"""

# Tools for the review agent
REVIEW_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "approve_ui",
            "description": "Approve the generated UI as correct and ready for use.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why the UI is approved."
                    }
                },
                "required": ["reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reject_ui",
            "description": "Reject the generated UI due to issues that need fixing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Detailed explanation of what is wrong and how to fix it."
                    }
                },
                "required": ["reason"]
            }
        }
    }
]


class GenUIAgent:
    """
    Manages the LLM lifecycle: Generate -> Validate -> Review -> Fix.
    
    Uses the project's LLMModel abstraction for LLM calls (same as web agent).
    """
    def __init__(self, llm_model: Any):
        if llm_model is None:
            raise ValueError("llm_model is required for GenUIAgent")
        self.llm_model = llm_model
        self.validator = GenUIValidator()
        self.max_retries = 3
        self.max_tool_steps = 20
        self.max_review_rejections = 2  # Max times the review can reject before accepting

    def _call_llm(self, messages: list, tools: Optional[list] = None) -> tuple[str | None, list | None]:
        """
        Call the LLM using the project's LLMModel abstraction.
        Returns (text_response, tool_calls)
        """
        response, tools, model_usage = self.llm_model.generate(
            messages=messages, 
            tools=tools if tools else [], 
            tool_choice="auto" if tools else None
        )

        prompt_usage = PromptUsageStats(genui_chars=sum(len(str(m.get('content', ''))) for m in messages if isinstance(m.get('content'), str)))
        log_llm_usage("genui", model_usage=model_usage, prompt_usage=prompt_usage, llm_model=self.llm_model)
        return response, tools

    @observe()
    def iterate_genui(self, current_code: str, state: Dict, instruction: str, state_schema: Optional[Dict] = None) -> tuple[str, str]:
        """
        Main entry point. Takes instructions and ensures valid output.
        
        Args:
            current_code: Existing UI code to modify
            state: Current game state values (dict)
            instruction: User's instruction for UI generation
            state_schema: Optional schema documentation for the state structure
        
        Returns:
            tuple[str, str]: (generated_code, rendered_html)
        """
        # Build the state documentation for the LLM
        if state_schema:
            state_documentation = _build_projection_catalog(state_schema)
        else:
            projection_names = ", ".join(sorted(state.keys()))
            state_documentation = (
                "Available Projections (schema/value available via get_projection_schema): "
                f"{projection_names}"
            )

        working_components = _initialize_component_collection(current_code)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Task: {instruction}\n\n"
                f"{_build_component_catalog(working_components)}\n\n"
                "Use read(), write(), edit(), clear_overlay_ui(), and validate() to update the component collection. "
                "Start by calling read(component_name='App') unless the task is explicitly to remove helper components first. "
                "clear_overlay_ui() only deletes helper components and will never delete App. "
                "After deleting components, update App if it still references removed helpers, then run validate().\n\n"
                f"{state_documentation}"
            )}
        ]

        print(f"--- Agent Task: {instruction} ---")
        _log_genui(
            "info",
            "Starting generation run",
            f"instruction={_preview_for_log(instruction)}",
            f"initial_component_count={len(working_components)}",
            f"initial_code_length={len(_compose_component_code(working_components))}",
        )
        last_validation: Optional[Dict[str, Any]] = None

        for attempt in range(self.max_retries):
            print(f"Attempt {attempt + 1}/{self.max_retries} generating...")
            _log_genui("info", f"Attempt {attempt + 1}/{self.max_retries} started")

            for _step in range(self.max_tool_steps):
                _log_genui("debug", f"Attempt {attempt + 1} step {_step + 1}/{self.max_tool_steps} requesting LLM action")
                response_text, tool_calls = self._call_llm(messages, tools=GENUI_TOOLS)

                if tool_calls:
                    _log_genui(
                        "debug",
                        "Model requested tools",
                        ", ".join(tool_call.function.name for tool_call in tool_calls),
                    )
                    messages.append({
                        "role": "assistant",
                        "content": response_text or "",
                        "tool_calls": [t.model_dump() for t in tool_calls]
                    })

                    for tool_call in tool_calls:
                        func_name = tool_call.function.name
                        func_args_str = tool_call.function.arguments

                        try:
                            func_args = json.loads(func_args_str) if func_args_str else {}
                        except json.JSONDecodeError:
                            func_args = {}

                        tool_result = self._run_generation_tool(
                            func_name=func_name,
                            func_args=func_args,
                            current_components=working_components,
                            state=state,
                            state_schema=state_schema,
                        )
                        working_components = tool_result["components"]

                        if func_name == "validate":
                            last_validation = tool_result["validation"]
                            if last_validation and last_validation["success"]:
                                print("SSR Validation: SUCCESS")
                                _log_genui("info", f"Validation passed on attempt {attempt + 1} step {_step + 1}")
                            elif last_validation:
                                print(f"SSR Validation: FAILED ({last_validation['result']})")
                                _log_genui(
                                    "warn",
                                    f"Validation failed on attempt {attempt + 1} step {_step + 1}",
                                    _preview_for_log(last_validation["result"]),
                                )

                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": func_name,
                            "content": tool_result["content"],
                        })
                    continue

                messages.append({"role": "assistant", "content": response_text or ""})

                current_code = _compose_component_code(working_components)
                if last_validation and last_validation["success"] and last_validation["code"] == current_code:
                    html_output = last_validation["result"]
                    _log_genui("debug", "Starting review for last validated output")
                    review_result = self._review_output(instruction, current_code, html_output, state)

                    if review_result["approved"]:
                        print(f"Review: APPROVED - {review_result['reason']}")
                        _log_genui("info", "Review approved", _preview_for_log(review_result["reason"]))
                        return current_code, html_output

                    print(f"Review: REJECTED - {review_result['reason']}")
                    _log_genui("warn", "Review rejected", _preview_for_log(review_result["reason"]))
                    messages.append({
                        "role": "user",
                        "content": (
                            "The latest validated code was reviewed and rejected with this feedback:\n"
                            f"{review_result['reason']}\n\n"
                            "Continue using read(), edit(), and validate() to fix the file."
                        )
                    })
                    break

                messages.append({
                    "role": "user",
                    "content": (
                        "You must use the provided tools to finish the task. "
                        "Do not return the full code directly. Read or edit the file, then run validate()."
                    )
                })
                _log_genui("warn", "Model responded without completing required tool flow")
            else:
                messages.append({
                    "role": "user",
                    "content": "You reached the step limit for this attempt. Make smaller edits and re-run validate()."
                })
                _log_genui("warn", f"Attempt {attempt + 1} reached max tool steps")

        _log_genui("error", f"Generation failed after {self.max_retries} attempts")
        raise RuntimeError("Agent failed to generate valid code after max retries.")

    @observe()
    def _run_generation_tool(self, func_name: str, func_args: Dict[str, Any], current_components: Dict[str, str], state: Dict, state_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if func_name == "list_components":
            _log_genui("debug", "Executing list_components tool", f"component_count={len(current_components)}")
            return {
                "components": current_components,
                "content": json.dumps({
                    "success": True,
                    "components": [
                        {
                            "component_name": component_name,
                            "file_path": _component_virtual_path(component_name),
                            "role": "root" if component_name == "App" else "helper",
                        }
                        for component_name in sorted(current_components.keys())
                    ],
                }),
                "validation": None,
            }

        if func_name == "read":
            component_name = _normalize_component_name(func_args.get("component_name"))
            offset = func_args.get("offset")
            limit = func_args.get("limit")

            if component_name is None:
                _log_genui("warn", "Read rejected due to invalid component name")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "component_name must be a non-empty string.",
                    }),
                    "validation": None,
                }

            component_code = current_components.get(component_name)
            if component_code is None:
                _log_genui("warn", "Read rejected because component was not found", component_name)
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": f"Unknown component: {component_name}",
                        "available_components": sorted(current_components.keys()),
                    }),
                    "validation": None,
                }
            lines = component_code.splitlines(keepends=True)
            start = offset if isinstance(offset, int) and offset >= 0 else 0
            _log_genui(
                "debug",
                "Executing read tool",
                f"component_name={component_name}",
                f"offset={start}",
                f"limit={limit if isinstance(limit, int) and limit >= 0 else 'all'}",
                f"total_lines={len(lines)}",
            )

            if isinstance(limit, int) and limit >= 0:
                end = start + limit
                content = "".join(lines[start:end])
            else:
                content = "".join(lines[start:])

            return {
                "components": current_components,
                "content": json.dumps({
                    "success": True,
                    "component_name": component_name,
                    "file_path": _component_virtual_path(component_name),
                    "offset": start,
                    "limit": limit if isinstance(limit, int) and limit >= 0 else None,
                    "total_lines": len(lines),
                    "content": content,
                }),
                "validation": None,
            }

        if func_name == "get_projection_schema":
            projection_name = func_args.get("projection_name")
            _log_genui("debug", "Executing get_projection_schema tool", f"projection_name={projection_name}")

            if not isinstance(projection_name, str) or not projection_name.strip():
                _log_genui("warn", "Projection schema request rejected due to invalid projection name")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "projection_name must be a non-empty string.",
                    }),
                    "validation": None,
                }

            if not state_schema:
                _log_genui("warn", "Projection schema request rejected because no schema catalog is available")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "No projection schema data is available for this run.",
                    }),
                    "validation": None,
                }

            schema = state_schema.get(projection_name)
            if schema is None:
                _log_genui("warn", "Projection schema request failed because projection was not found", projection_name)
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": f"Unknown projection: {projection_name}",
                        "available_projections": sorted(state_schema.keys()),
                    }),
                    "validation": None,
                }

            current_value = state.get(projection_name)
            _log_genui("info", "Returned projection schema and current value", f"projection_name={projection_name}")
            return {
                "components": current_components,
                "content": json.dumps({
                    "success": True,
                    "projection_name": projection_name,
                    "schema": schema,
                    "current_value": current_value,
                }),
                "validation": None,
            }

        if func_name == "write":
            component_name = _normalize_component_name(func_args.get("component_name"))
            content = func_args.get("content")
            _log_genui(
                "debug",
                "Executing write tool",
                f"component_name={component_name}",
                f"content_preview={_preview_for_log(content)}",
            )

            if component_name is None:
                _log_genui("warn", "Write rejected due to invalid component name")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "component_name must be a non-empty string.",
                    }),
                    "validation": None,
                }

            if not isinstance(content, str):
                _log_genui("warn", "Write rejected due to invalid content type")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "content must be a string.",
                    }),
                    "validation": None,
                }

            updated_components = dict(current_components)
            updated_components[component_name] = content
            _log_genui(
                "info",
                "Wrote component",
                f"component_name={component_name}",
                f"component_length={len(content)}",
                f"component_count={len(updated_components)}",
            )
            return {
                "components": updated_components,
                "content": json.dumps({
                    "success": True,
                    "component_name": component_name,
                    "file_path": _component_virtual_path(component_name),
                    "component_length": len(content),
                    "component_count": len(updated_components),
                }),
                "validation": None,
            }

        if func_name == "edit":
            component_name = _normalize_component_name(func_args.get("component_name"))
            old_string = func_args.get("old_string")
            new_string = func_args.get("new_string")
            replace_all = bool(func_args.get("replace_all", False))
            _log_genui(
                "debug",
                "Executing edit tool",
                f"component_name={component_name}",
                f"replace_all={replace_all}",
                f"old={_preview_for_log(old_string)}",
                f"new={_preview_for_log(new_string)}",
            )

            if component_name is None:
                _log_genui("warn", "Edit rejected due to invalid component name")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "component_name must be a non-empty string.",
                    }),
                    "validation": None,
                }

            current_code = current_components.get(component_name)
            if current_code is None:
                _log_genui("warn", "Edit rejected because component was not found", component_name)
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": f"Unknown component: {component_name}",
                        "available_components": sorted(current_components.keys()),
                    }),
                    "validation": None,
                }

            if not isinstance(old_string, str) or not isinstance(new_string, str):
                _log_genui("warn", "Edit rejected due to invalid argument types")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "old_string and new_string must both be strings.",
                    }),
                    "validation": None,
                }

            if old_string == new_string:
                _log_genui("warn", "Edit rejected because old_string matches new_string")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "new_string must differ from old_string.",
                    }),
                    "validation": None,
                }

            occurrence_count = current_code.count(old_string)
            if occurrence_count == 0:
                _log_genui("warn", "Edit rejected because old_string was not found", _preview_for_log(old_string))
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "old_string was not found. Call read() to inspect the latest component contents.",
                    }),
                    "validation": None,
                }

            updated_code = current_code.replace(
                old_string,
                new_string,
                occurrence_count if replace_all else 1,
            )
            replaced_occurrences = occurrence_count if replace_all else 1
            updated_components = dict(current_components)
            updated_components[component_name] = updated_code
            _log_genui(
                "info",
                "Applied component patch",
                f"component_name={component_name}",
                f"replaced_occurrences={replaced_occurrences}",
                f"code_length_before={len(current_code)}",
                f"code_length_after={len(updated_code)}",
            )

            return {
                "components": updated_components,
                "content": json.dumps({
                    "success": True,
                    "component_name": component_name,
                    "file_path": _component_virtual_path(component_name),
                    "replaced_occurrences": replaced_occurrences,
                }),
                "validation": None,
            }

        if func_name == "clear_overlay_ui":
            component_names = func_args.get("component_names")
            if component_names is not None and (
                not isinstance(component_names, list)
                or not all(isinstance(component_name, str) for component_name in component_names)
            ):
                _log_genui("warn", "Component deletion rejected due to invalid component_names payload")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "component_names must be an array of strings when provided.",
                    }),
                    "validation": None,
                }

            requested_names = None if component_names is None else {
                component_name.strip()
                for component_name in component_names
                if component_name.strip()
            }
            deleted_components: list[str] = []
            skipped_components: list[str] = []
            updated_components = dict(current_components)

            if requested_names is None:
                target_names = [component_name for component_name in current_components.keys() if component_name != "App"]
            else:
                target_names = sorted(requested_names)

            for component_name in target_names:
                if component_name == "App":
                    skipped_components.append("App")
                    continue
                if component_name not in updated_components:
                    skipped_components.append(component_name)
                    continue
                del updated_components[component_name]
                deleted_components.append(component_name)

            _log_genui(
                "info",
                "Deleted overlay helper components",
                f"deleted_count={len(deleted_components)}",
                f"skipped_count={len(skipped_components)}",
            )
            return {
                "components": updated_components,
                "content": json.dumps({
                    "success": True,
                    "deleted_components": deleted_components,
                    "skipped_components": skipped_components,
                    "remaining_components": sorted(updated_components.keys()),
                    "message": "Requested helper components were deleted. App was preserved.",
                }),
                "validation": None,
            }

        if func_name == "validate":
            _log_genui("debug", "Executing validate tool")
            if "App" not in current_components:
                _log_genui("warn", "Validation rejected because App component is missing")
                return {
                    "components": current_components,
                    "content": json.dumps({
                        "success": False,
                        "error": "The component collection must always include App.",
                    }),
                    "validation": {
                        "success": False,
                        "result": "The component collection must always include App.",
                        "code": _compose_component_code(current_components),
                    },
                }

            composed_code = _compose_component_code(current_components)
            success, result = self.validator.validate(composed_code, state)
            payload: Dict[str, Any] = {"success": success}
            if success:
                payload["rendered_output"] = result
            else:
                payload["error"] = result
            payload["component_names"] = sorted(current_components.keys())

            return {
                "components": current_components,
                "content": json.dumps(payload),
                "validation": {
                    "success": success,
                    "result": result,
                    "code": composed_code,
                },
            }

        return {
            "components": current_components,
            "content": json.dumps({
                "success": False,
                "error": f"Unknown tool: {func_name}",
            }),
            "validation": None,
        }

    @observe()
    def _review_output(self, instruction: str, code: str, html_output: str, state: Dict) -> Dict:
        """
        Review the generated HTML output using an LLM with tools.
        
        Returns:
            Dict with keys: approved (bool), reason (str)
        """
        review_messages: list[dict[str, Any]] = [
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": f"""Please review this generated UI:

## Original Instruction
{instruction}

## State Data Used
{json.dumps(state, indent=2)}

## Generated Preact Code
```javascript
{code}
```

## Rendered HTML Output
```html
{html_output}
```

Evaluate whether this output correctly implements the user's request. Use the approve_ui or reject_ui tool to indicate your decision."""}
        ]
        
        for review_attempt in range(self.max_review_rejections + 1):
            response_text, tool_calls = self._call_llm(review_messages, tools=REVIEW_TOOLS)
            
            if tool_calls:
                for tool_call in tool_calls:
                    # Use object attribute access (same pattern as web agent)
                    func_name = tool_call.function.name
                    func_args_str = tool_call.function.arguments
                    
                    try:
                        func_args = json.loads(func_args_str) if func_args_str else {}
                    except json.JSONDecodeError:
                        func_args = {"reason": "Invalid JSON in tool arguments"}
                    
                    if func_name == "approve_ui":
                        _log_genui("info", "Reviewer approved UI", _preview_for_log(func_args.get("reason", "Approved")))
                        return {"approved": True, "reason": func_args.get("reason", "Approved")}
                    elif func_name == "reject_ui":
                        # On the last review attempt, force approval to prevent infinite loops
                        if review_attempt >= self.max_review_rejections:
                            _log_genui(
                                "warn",
                                "Reviewer rejected UI but approval was forced after max rejections",
                                _preview_for_log(func_args.get("reason", "Unknown")),
                            )
                            return {"approved": True, "reason": f"Force approved after {self.max_review_rejections} rejections. Last rejection reason: {func_args.get('reason', 'Unknown')}"}
                        _log_genui("warn", "Reviewer rejected UI", _preview_for_log(func_args.get("reason", "Rejected")))
                        return {"approved": False, "reason": func_args.get("reason", "Rejected")}
            
            # No tool call - try to parse from text or default to approved
            if response_text:
                lower_text = response_text.lower()
                if "reject" in lower_text or "issue" in lower_text or "problem" in lower_text:
                    if review_attempt >= self.max_review_rejections:
                        _log_genui("warn", "Reviewer returned text rejection but approval was forced after max rejections")
                        return {"approved": True, "reason": "Force approved after max rejections (no tool call)"}
                    _log_genui("warn", "Reviewer returned rejection text without tool call", _preview_for_log(response_text))
                    return {"approved": False, "reason": response_text[:500]}
            
            # Default to approved if we can't determine
            _log_genui("info", "Reviewer result auto-approved due to no clear rejection")
            return {"approved": True, "reason": "Auto-approved (no clear rejection)"}
        
        # Fallback - approve to prevent infinite loops
        _log_genui("warn", "Reviewer loop exhausted; auto-approving")
        return {"approved": True, "reason": "Auto-approved (review loop exhausted)"}

    def _clean_code(self, raw_text: str) -> str:
        """Strips Markdown code blocks if present."""
        if "```javascript" in raw_text:
            return raw_text.split("```javascript")[1].split("```")[0].strip()
        if "```jsx" in raw_text:
            return raw_text.split("```jsx")[1].split("```")[0].strip()
        if "```" in raw_text:
            parts = raw_text.split("```")
            if len(parts) >= 3:
                return parts[1].strip()
        return raw_text.strip()


# Singleton validator instance (expensive to create due to bundle download)
_validator_instance: Optional[GenUIValidator] = None

def get_validator() -> GenUIValidator:
    """Get or create the singleton GenUIValidator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = GenUIValidator()
    return _validator_instance

@observe()
def generate_ui_code(
    instruction: str,
    state: Dict,
    current_code: str = "",
    llm_model: Any = None,
    max_retries: int = 3,
    store_key: str = "default_ui",
    state_schema: Optional[Dict] = None
) -> tuple[str, str]:
    """
    High-level function to generate UI code.
    
    Args:
        instruction: What UI to generate
        state: Current game state values (dict)
        current_code: Existing UI code to modify (optional)
        llm_model: LLMModel instance to use (required)
        max_retries: Maximum generation attempts
        store_key: Key to use for persistence in CodeStore
        state_schema: Optional schema documentation describing state structure
    
    Returns:
        tuple[str, str]: (generated_code, rendered_html)
    
    Raises:
        ValueError: If llm_model is not provided
    """
    if llm_model is None:
        raise ValueError("llm_model is required for generate_ui_code")
    
    store = CodeStore("genui")
    
    # If no current code provided, try to load from store
    if not current_code:
        entry = store.get_latest(store_key)
        if entry:
            current_code = entry.code
            print(f"Loaded existing UI code from store (version {entry.version})")
            _log_genui("info", f"Loaded existing UI code from store version={entry.version}")

    agent = GenUIAgent(llm_model=llm_model)
    agent.max_retries = max_retries
    agent.validator = get_validator()
    
    final_code, html_output = agent.iterate_genui(current_code, state, instruction, state_schema)
    
    # Save to store
    # Simple versioning: increment major version if we could parse it, else 1.0
    new_version = "1.0"
    latest = store.get_latest(store_key)
    if latest:
        try:
            v = float(latest.version)
            new_version = f"{v + 0.1:.1f}"
        except ValueError:
            pass
            
    store.commit(store_key, final_code, instruction, new_version)
    print(f"Saved new UI code to store (version {new_version})")
    _log_genui(
        "info",
        f"Saved UI code to store version={new_version}",
        f"final_code_length={len(final_code)}",
        f"rendered_length={len(html_output)}",
    )
    
    return final_code, html_output
