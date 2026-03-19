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
from ..GenUI import generate_ui_code, build_default_component_code
from ..Database import CodeStore

# Type alias for projected states dictionary
ProjectedStates = dict[str, BaseModel]

# Default empty skeleton UI code stored in serialized component-collection format
DEFAULT_UI_CODE = build_default_component_code()


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
        and sending it to the frontend. If no saved code exists, initializes
        with the default skeleton UI code.
        """
        try:
            # Use CodeStore.init() which returns existing entry or creates default
            entry = self._store.init(
                self.STORE_KEY, 
                DEFAULT_UI_CODE, 
                "Initial default UI", 
                "1.0"
            )
            self.current_code = entry.code
            self._send_to_frontend(self.current_code)
            log('info', f"GenUI: Loaded and sent UI code on startup (version {entry.version})")
        except Exception as e:
            log('warn', f"GenUI: Failed to load saved UI code on startup: {e}")
    
    def _send_to_frontend(self, code: str) -> None:
        """Send GenUI code to the frontend for rendering."""
        send_message({
            "type": "genui",
            "code": code,
        })
    
    def generate(self, instruction: str | None, projected_states: ProjectedStates, undo: bool = False) -> str:
        """
        Generate or modify UI components, or undo the latest saved version.
        
        Args:
            instruction: What UI to generate or modify
            projected_states: Current game state as Pydantic models
            undo: If true, delete the newest saved version and restore the previous one
            
        Returns:
            Status message describing the result
        """
        if undo:
            if instruction:
                return "Undo and instruction are mutually exclusive. Provide either undo=true or an instruction."

            try:
                history = self._store.get_history(self.STORE_KEY, limit=2)
                if len(history) < 2:
                    return "There is no previous overlay UI version to restore."

                deleted = self._store.delete_latest(self.STORE_KEY)
                if not deleted:
                    return "Failed to delete the latest overlay UI version."

                previous_entry = self._store.get_latest(self.STORE_KEY)
                if previous_entry is None:
                    return "Failed to load the previous overlay UI version after undo."

                self.current_code = previous_entry.code
                self._send_to_frontend(previous_entry.code)
                log('info', f"GenUI: Undid latest UI version and restored version {previous_entry.version}")
                return f"UI reverted to the previous saved version ({previous_entry.version})."
            except Exception as e:
                log('error', f"GenUI: Failed to undo latest UI version: {e}")
                return f"Error undoing UI version: {str(e)}"

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
        Clear the current UI overlay, resetting to the default empty skeleton.
        
        Returns:
            Status message confirming the clear
        """
        self.current_code = DEFAULT_UI_CODE
        self._send_to_frontend(DEFAULT_UI_CODE)
        
        # Save the reset state to database
        try:
            self._store.commit(self.STORE_KEY, DEFAULT_UI_CODE, "Reset to default", "0.0")
            log('info', "GenUI: Cleared overlay and reset to default skeleton")
        except Exception as e:
            log('warn', f"GenUI: Failed to save cleared UI to database: {e}")
        
        return "UI overlay cleared and reset to default."
    
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
    return _genui_manager.generate(obj.get('instruction'), projected_states, bool(obj.get('undo', False)))


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
    sends it to the frontend, and registers the top-level UI generation action.
    """
    global _genui_manager
    
    # Create and initialize the manager
    _genui_manager = GenUIManager(
        llm_model=llmModel,
        max_retries=maxRetries
    )
    _genui_manager.init()
    
    # Main UI generation action. Clear/reset requests route through the internal
    # GenUI agent tools, while undo is handled here by rolling back the saved DB history.
    actionManager.registerAction(
        'generate_overlay_ui',
        "Generate, modify, reset, or undo the game overlay UI. Use an instruction to update the overlay, or set undo=true to delete the most recent saved version and restore the previous one. Undo and instruction are mutually exclusive.",
        {
            "type": "object",
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "Description of what UI to create, change, or reset. Be specific about what information to display and where. Limit the input to the requested change only, no need to reiterate the full requirements. Examples: 'Move fuel and cargo in the top right', 'Create a mission tracker in the bottom left', 'Add a heat warning indicator', 'Clear the overlay and reset it to default'. Mutually exclusive with undo."
                },
                "undo": {
                    "type": "boolean",
                    "description": "Set to true to undo the latest saved overlay UI version by deleting it from the database and loading the previous version. Mutually exclusive with instruction."
                }
            },
            "additionalProperties": False
        },
        _generate_ui_action,
        'ui',
        input_template=lambda i, s: "Undoing latest overlay UI version" if i.get('undo', False) else f"Generating UI: {i.get('instruction', '')}",
    )
