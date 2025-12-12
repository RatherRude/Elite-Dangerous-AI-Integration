"""
GenUI Actions - LLM-generated UI components for Elite Dangerous overlay
"""
import json
from typing import Optional, Dict, cast, Any

from pydantic import BaseModel
from ..ActionManager import ActionManager
from ..EventManager import EventManager
from ..PromptGenerator import PromptGenerator
from ..Models import LLMModel
from ..UI import send_message
from ..Logger import log
from ..GenUI import generate_ui_code
from ..Database import CodeStore

# Type alias for projected states dictionary
ProjectedStates = dict[str, BaseModel]


class GenUIManager:
    """
    Manages the GenUI overlay system, encapsulating code storage, 
    initialization, and UI generation.
    """
    
    STORE_NAME = "genui"
    STORE_KEY = "default_ui"
    
    def __init__(
        self,
        llm_model: LLMModel | None = None,
        max_retries: int = 3
    ):
        """
        Initialize the GenUI manager.
        
        Args:
            llm_model: LLM model for generating UI code
            max_retries: Maximum retries for UI generation
        """
        self.llm_model = llm_model
        self.max_retries = max_retries
        self.current_code: str = ""
        self._store = CodeStore(self.STORE_NAME)
    
    def init(self) -> None:
        """
        Initialize the GenUI system by loading saved code from the database
        and sending it to the frontend.
        """
        try:
            entry = self._store.get_latest(self.STORE_KEY)
            if entry and entry.code:
                self.current_code = entry.code
                self._send_to_frontend(self.current_code)
                log('info', f"GenUI: Loaded and sent saved UI code on startup (version {entry.version})")
            else:
                log('info', "GenUI: No saved UI code found, starting fresh")
        except Exception as e:
            log('warn', f"GenUI: Failed to load saved UI code on startup: {e}")
    
    def _send_to_frontend(self, code: str) -> None:
        """Send GenUI code to the frontend for rendering."""
        send_message({
            "type": "genui",
            "code": code,
        })
    
    def generate(self, instruction: str, projected_states: ProjectedStates) -> str:
        """
        Generate or modify UI components based on user instructions.
        
        Args:
            instruction: What UI to generate or modify
            projected_states: Current game state as Pydantic models
            
        Returns:
            Status message describing the result
        """
        if not self.llm_model:
            return "LLM model not configured for UI generation."
        
        if not instruction:
            return "Please provide an instruction for the UI generation."
        
        # Build state schema documentation and current values from Pydantic models
        state_schemas, state_values = self._build_state_for_llm(projected_states)
        
        log('info', f"GenUI: Generating UI for instruction: {instruction}")
        
        try:
            # Use the GenUI module which handles:
            # 1. LLM code generation
            # 2. SSR validation with QuickJS
            # 3. Review loop with approval/rejection
            new_code, html_output = generate_ui_code(
                instruction=instruction,
                state=state_values,
                current_code=self.current_code,
                llm_model=self.llm_model,
                max_retries=self.max_retries,
                store_key=self.STORE_KEY,
                state_schema=state_schemas
            )
            
            # Success - update state and send to frontend
            self.current_code = new_code
            self._send_to_frontend(new_code)
            
            log('info', "GenUI: Successfully generated and validated UI code")
            return f"UI updated successfully. The overlay now shows: {instruction}"
            
        except RuntimeError as e:
            log('error', f"GenUI: Failed to generate valid UI: {e}")
            return f"Failed to generate valid UI code: {str(e)}"
        except Exception as e:
            log('error', f"GenUI: Unexpected error: {e}")
            return f"Error generating UI: {str(e)}"
    
    def clear(self) -> str:
        """
        Clear the current UI overlay.
        
        Returns:
            Status message confirming the clear
        """
        self.current_code = ""
        self._send_to_frontend("")
        
        # Also clear from database
        try:
            self._store.commit(self.STORE_KEY, "", "Cleared overlay", "0.0")
        except Exception as e:
            log('warn', f"GenUI: Failed to clear saved UI from database: {e}")
        
        return "UI overlay cleared."
    
    def _build_state_for_llm(self, projected_states: ProjectedStates) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Build both the state schema documentation and current values for the LLM.
        
        Dynamically extracts schemas from the actual Pydantic model instances in projected_states.
        
        Returns:
            tuple: (schema_documentation, current_values)
        """
        schemas: dict[str, Any] = {}
        values: dict[str, Any] = {}
        
        for state_name, state in projected_states.items():
            # Extract schema from the model class
            if isinstance(state, BaseModel):
                try:
                    schemas[state_name] = self._get_state_schema(type(state))
                except Exception as e:
                    log('warn', f"Failed to get schema for {state_name}: {e}")
                    schemas[state_name] = {"description": f"State model for {state_name}"}
                
                # Get the current value
                values[state_name] = state.model_dump()
        
        return schemas, values
    
    @staticmethod
    def _get_state_schema(model_class: type[BaseModel]) -> dict[str, Any]:
        """
        Extract a simplified JSON schema from a Pydantic model for LLM documentation.
        Includes field descriptions and types.
        """
        schema = model_class.model_json_schema()
        
        # Simplify the schema - remove complex $defs and inline the types
        simplified: dict[str, Any] = {
            "description": schema.get("description", model_class.__doc__ or ""),
            "properties": {}
        }
        
        properties = schema.get("properties", {})
        defs = schema.get("$defs", {})
        
        for field_name, field_schema in properties.items():
            field_info: dict[str, Any] = {
                "type": field_schema.get("type", "any"),
            }
            
            # Add description if available
            if "description" in field_schema:
                field_info["description"] = field_schema["description"]
            
            # Handle $ref references
            if "$ref" in field_schema:
                ref_name = field_schema["$ref"].split("/")[-1]
                if ref_name in defs:
                    ref_def = defs[ref_name]
                    field_info["type"] = ref_def.get("type", "object")
                    if "description" in ref_def:
                        field_info["description"] = ref_def.get("description", "")
                    if "properties" in ref_def:
                        field_info["properties"] = {
                            k: {"type": v.get("type", "any"), "description": v.get("description", "")}
                            for k, v in ref_def["properties"].items()
                        }
            
            # Handle anyOf (Optional types)
            if "anyOf" in field_schema:
                types = [t.get("type") for t in field_schema["anyOf"] if t.get("type") != "null"]
                if types:
                    field_info["type"] = types[0] if len(types) == 1 else types
            
            # Handle arrays
            if field_schema.get("type") == "array" and "items" in field_schema:
                items = field_schema["items"]
                if "$ref" in items:
                    ref_name = items["$ref"].split("/")[-1]
                    if ref_name in defs:
                        ref_def = defs[ref_name]
                        field_info["items"] = {
                            "type": "object",
                            "properties": {
                                k: {"type": v.get("type", "any"), "description": v.get("description", "")}
                                for k, v in ref_def.get("properties", {}).items()
                            }
                        }
                else:
                    field_info["items"] = {"type": items.get("type", "any")}
            
            simplified["properties"][field_name] = field_info
        
        return simplified


# Module-level manager instance
_genui_manager: GenUIManager | None = None


def get_genui_manager() -> GenUIManager | None:
    """Get the current GenUI manager instance."""
    return _genui_manager


def _generate_ui_action(obj: Dict, projected_states: ProjectedStates) -> str:
    """Action wrapper for UI generation."""
    if _genui_manager is None:
        return "GenUI manager not initialized."
    return _genui_manager.generate(obj.get('instruction', ''), projected_states)


def _clear_ui_action(obj: Dict, projected_states: ProjectedStates) -> str:
    """Action wrapper for clearing UI."""
    if _genui_manager is None:
        return "GenUI manager not initialized."
    return _genui_manager.clear()


def register_genui_actions(
    actionManager: ActionManager, 
    eventManager: EventManager,
    promptGenerator: PromptGenerator,
    llmModel: LLMModel | None,
    maxRetries: int = 3
):
    """
    Register GenUI actions with the ActionManager.
    
    This initializes the GenUI manager, loads any saved UI code from the database,
    sends it to the frontend, and registers the generate/clear actions.
    """
    global _genui_manager
    
    # Create and initialize the manager
    _genui_manager = GenUIManager(
        llm_model=llmModel,
        max_retries=maxRetries
    )
    _genui_manager.init()
    
    # Main UI generation action
    actionManager.registerAction(
        'generate_overlay_ui',
        "Generate or modify the game overlay UI. Use this when the user wants to see specific information displayed on their screen, create custom HUD elements, or modify the current overlay display.",
        {
            "type": "object",
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "Description of what UI to create or how to modify the current UI. Be specific about what information to display and where. Examples: 'Show fuel and cargo in the top right', 'Create a mission tracker in the bottom left', 'Add a heat warning indicator'."
                },
            },
            "required": ["instruction"]
        },
        _generate_ui_action,
        'ui',
        input_template=lambda i, s: f"Generating UI: {i.get('instruction', '')}",
    )
    
    # Clear UI action
    actionManager.registerAction(
        'clear_overlay_ui',
        "Clear the current overlay UI, removing all custom HUD elements.",
        {
            "type": "object",
            "properties": {},
        },
        _clear_ui_action,
        'ui',
        input_template=lambda i, s: "Clearing overlay UI",
    )
