import yaml
import os
import json
import requests
import quickjs
from openai import OpenAI
from typing import Optional, Dict, Tuple, Any
from .Database import CodeStore

# --- CONFIGURATION ---
MAX_RETRIES = 3

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
You are an expert UI Engineer for Elite Dangerous.
Your goal is to write Preact components that visualize game state.

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

3. COMPONENT NAME:
   - You MUST name your main component `App`.
   - You MAY define helper components inside the same code.

4. ROBUSTNESS:
   - Always check if nested properties exist in 'state' before accessing them to prevent runtime errors.
   - Example: state.ship?.fuel?.current ?? 0

5. CHANGE SCOPE:
   - Only apply minimal changes needed to fulfill the user's request.
   - Preserve existing functionality, layout, and style as much as possible.
   - Avoid large rewrites unless absolutely necessary.
   - Always repeat the full existing code in your response, with minimal changes.

Example Output:
const App = ({ state }) => {
  const numOrNull = (v) => {
    if (v == null || v === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  
  // ---------- PIPS (SYS/ENG/WEP) ----------
  // Bind directly to live status model:
  const pipsRaw = state?.CurrentStatus?.Pips ?? null;

  const pipSys = numOrNull(pipsRaw?.system);
  const pipEng = numOrNull(pipsRaw?.engine);
  const pipWep = numOrNull(pipsRaw?.weapons);

  const pipKnown = pipSys != null && pipEng != null && pipWep != null;

  const pipBarPct = (v) => {
    if (v == null) return 0;
    const clamped = Math.max(0, Math.min(4, v)); // typical range 0..4
    return (clamped / 4) * 100;
  };

  const panelClass =
    "rounded-md border border-gray-700 bg-gray-900/70 backdrop-blur px-3 py-2 shadow-lg";
  const labelClass = "text-[10px] font-semibold tracking-wide text-gray-300/80";
  const valueClass = "text-xs font-semibold text-gray-100 tabular-nums";

  const pipItems = [
    { k: "SYS", v: pipSys, c: "bg-sky-400" },
    { k: "ENG", v: pipEng, c: "bg-amber-400" },
    { k: "WEP", v: pipWep, c: "bg-rose-400" },
  ];

  return html`
    <div class="fixed top-3 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
      <div class="w-[34rem] max-w-[96vw]">
        <div class="grid grid-cols-3 gap-2">
          <!-- (3) PIPS -->
          <div class=${panelClass}>
            <div class="flex items-center justify-between">
              <div class=${labelClass}>PIPS</div>
              <div class=${valueClass}>
                ${pipKnown
                  ? `${pipSys.toFixed(1)} / ${pipEng.toFixed(1)} / ${pipWep.toFixed(1)}`
                  : "--.- / --.- / --.-"}
              </div>
            </div>

            <div class="mt-2 grid grid-cols-3 gap-2">
              ${pipItems.map(
                (p) => html`
                  <div class="min-w-0">
                    <div class="flex items-center justify-between">
                      <div class="text-[10px] font-semibold text-gray-300/80">${p.k}</div>
                      <div class="text-[10px] font-semibold text-gray-200/90 tabular-nums">
                        ${p.v == null ? "--.-" : p.v.toFixed(1)}
                      </div>
                    </div>
                    <div class="mt-1 h-1.5 w-full rounded bg-gray-800 overflow-hidden">
                      <div
                        class=${["h-full", p.c].join(" ")}
                        style=${`width:${pipBarPct(p.v)}%; transition: width 200ms linear; opacity:${p.v == null ? 0.35 : 1};`}
                      ></div>
                    </div>
                  </div>
                `
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
};
"""

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

    def validate(self, code: str, mock_state: Dict) -> Tuple[bool, str]:
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
            return True, result
        except quickjs.JSException as e:
            return False, str(e)
        except Exception as e:
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
        self.max_retries = MAX_RETRIES
        self.max_review_rejections = 2  # Max times the review can reject before accepting

    def _call_llm(self, messages: list, tools: Optional[list] = None) -> tuple[str | None, list | None]:
        """
        Call the LLM using the project's LLMModel abstraction.
        Returns (text_response, tool_calls)
        """
        return self.llm_model.generate(
            messages=messages, 
            tools=tools if tools else [], 
            tool_choice="auto" if tools else None
        )

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
            state_documentation = f"""
Available State Schema (props.state):
{yaml.dump(state_schema, indent=2)}

Current State Values:
{yaml.dump(state, indent=2)}
"""
        else:
            state_documentation = f"State Structure: {json.dumps(state)}"
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Current Code:\n{current_code}\n\nTask: {instruction}\n\n{state_documentation}"}
        ]

        print(f"--- Agent Task: {instruction} ---")

        for attempt in range(self.max_retries):
            # 1. Call LLM to generate code
            print(f"Attempt {attempt + 1}/{self.max_retries} generating...")
            response_text, _ = self._call_llm(messages)
            
            if not response_text:
                print("Empty response from LLM")
                continue
            
            new_code = self._clean_code(response_text)

            # 2. Validate with SSR
            success, result = self.validator.validate(new_code, state)

            if not success:
                # SSR failed - add error to context and retry
                print(f"SSR Validation: FAILED ({result})")
                messages.append({"role": "assistant", "content": new_code})
                messages.append({"role": "user", "content": f"That code crashed during SSR validation with this error:\n{result}\n\nPlease fix the code."})
                continue
            
            print("SSR Validation: SUCCESS")
            html_output = result
            
            # 3. Review loop - let LLM verify the output
            review_result = self._review_output(instruction, new_code, html_output, state)
            
            if review_result["approved"]:
                print(f"Review: APPROVED - {review_result['reason']}")
                return new_code, html_output
            else:
                # Review rejected - add critique and retry
                print(f"Review: REJECTED - {review_result['reason']}")
                messages.append({"role": "assistant", "content": new_code})
                messages.append({"role": "user", "content": f"The code was reviewed and rejected with this feedback:\n{review_result['reason']}\n\nPlease fix the code to address this issue."})
                continue

        raise RuntimeError("Agent failed to generate valid code after max retries.")

    def _review_output(self, instruction: str, code: str, html_output: str, state: Dict) -> Dict:
        """
        Review the generated HTML output using an LLM with tools.
        
        Returns:
            Dict with keys: approved (bool), reason (str)
        """
        review_messages = [
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
                        return {"approved": True, "reason": func_args.get("reason", "Approved")}
                    elif func_name == "reject_ui":
                        # On the last review attempt, force approval to prevent infinite loops
                        if review_attempt >= self.max_review_rejections:
                            return {"approved": True, "reason": f"Force approved after {self.max_review_rejections} rejections. Last rejection reason: {func_args.get('reason', 'Unknown')}"}
                        return {"approved": False, "reason": func_args.get("reason", "Rejected")}
            
            # No tool call - try to parse from text or default to approved
            if response_text:
                lower_text = response_text.lower()
                if "reject" in lower_text or "issue" in lower_text or "problem" in lower_text:
                    if review_attempt >= self.max_review_rejections:
                        return {"approved": True, "reason": "Force approved after max rejections (no tool call)"}
                    return {"approved": False, "reason": response_text[:500]}
            
            # Default to approved if we can't determine
            return {"approved": True, "reason": "Auto-approved (no clear rejection)"}
        
        # Fallback - approve to prevent infinite loops
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
    
    return final_code, html_output

# --- EXAMPLE USAGE ---
if __name__ == "__main__":
    from openai import OpenAI
    
    # 1. Mock Game State
    game_state = {
        "ship": {
            "name": "Cobra MkIII",
            "heat": 0.45,
            "fuel": {"current": 12, "max": 32},
            "cargo": [{"item": "Gold", "qty": 4}]
        }
    }

    # 2. Create a simple LLM model wrapper for testing
    class SimpleLLMModel:
        def __init__(self):
            self.client = OpenAI()
        
        def generate(self, messages, tools=None, tool_choice=None):
            kwargs = {
                "messages": messages,
                "temperature": 0.2
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = tool_choice or "auto"
            
            response = self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            return choice.message.content, choice.message.tool_calls
    
    llm = SimpleLLMModel()
    agent = GenUIAgent(llm_model=llm)

    # 3. Run Request
    try:
        final_code, html_output = agent.iterate_genui(
            current_code="", 
            state=game_state, 
            instruction="Create a dashboard showing fuel bar and cargo list."
        )
        
        print("\n=== FINAL VALIDATED CODE ===\n")
        print(final_code)
        
        print("\n=== RENDERED HTML ===\n")
        print(html_output)
        
    except Exception as e:
        print(f"Process failed: {e}")