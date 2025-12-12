"""
GenUI Actions - LLM-generated UI components for Elite Dangerous overlay
"""
import json
from typing import Optional, Dict, cast

from ..ActionManager import ActionManager
from ..EventManager import EventManager
from ..PromptGenerator import PromptGenerator
from ..Models import LLMModel
from ..UI import send_message
from ..Logger import log
from ..GenAI import generate_ui_code

# Module-level references
llm_model: LLMModel = cast(LLMModel, None)
event_manager: EventManager = cast(EventManager, None)
prompt_generator: PromptGenerator = cast(PromptGenerator, None)
genui_max_retries: int = 3

# Current UI code state
current_ui_code: str = ""




def send_genui_code(code: str):
    """Send GenUI code to the frontend for rendering."""
    send_message({
        "type": "genui",
        "code": code,
    })


def generate_ui(obj: Dict, projected_states: Dict) -> str:
    """
    Generate or modify UI components based on user instructions.
    Uses the GenAI module to create Preact components with SSR validation and review.
    """
    global current_ui_code, llm_model
    
    if not llm_model:
        return "LLM model not configured for UI generation."
    
    instruction = obj.get('instruction', '')
    if not instruction:
        return "Please provide an instruction for the UI generation."
    
    # Build a simplified state structure for the LLM to understand
    state_structure = _build_state_structure(projected_states)
    
    log('info', f"GenUI: Generating UI for instruction: {instruction}")
    
    try:
        # Use the GenAI module which handles:
        # 1. LLM code generation
        # 2. SSR validation with QuickJS
        # 3. Review loop with approval/rejection
        new_code, html_output = generate_ui_code(
            instruction=instruction,
            state=state_structure,
            current_code=current_ui_code,
            llm_model=llm_model,
            max_retries=genui_max_retries
        )
        
        # Success - update state and send to frontend
        current_ui_code = new_code
        send_genui_code(new_code)
        
        log('info', "GenUI: Successfully generated and validated UI code")
        return f"UI updated successfully. The overlay now shows: {instruction}"
        
    except RuntimeError as e:
        log('error', f"GenUI: Failed to generate valid UI: {e}")
        return f"Failed to generate valid UI code: {str(e)}"
    except Exception as e:
        log('error', f"GenUI: Unexpected error: {e}")
        return f"Error generating UI: {str(e)}"


def clear_ui(obj: Dict, projected_states: Dict) -> str:
    """Clear the current UI overlay."""
    global current_ui_code
    
    current_ui_code = ""
    send_genui_code("")
    
    return "UI overlay cleared."

def _build_state_structure(projected_states: Dict) -> Dict:
    """
    Build a simplified state structure for the LLM to understand.
    This extracts key information from projected_states.
    """
    state = {}
    
    # Ship info
    if 'Ship' in projected_states:
        ship = projected_states['Ship']
        state['ship'] = {
            'name': ship.get('Name', 'Unknown'),
            'type': ship.get('Ship', 'Unknown'),
            'ident': ship.get('ShipIdent', ''),
        }
    
    # Current status (flags, fuel, cargo, etc.)
    if 'CurrentStatus' in projected_states:
        status = projected_states['CurrentStatus']
        state['status'] = {
            'flags': status.get('flags', {}),
            'flags2': status.get('flags2', {}),
        }
        if 'fuel' in status:
            state['ship'] = state.get('ship', {})
            state['ship']['fuel'] = status['fuel']
        if 'cargo' in status:
            state['ship'] = state.get('ship', {})
            state['ship']['cargo'] = status['cargo']
    
    # Location
    if 'Location' in projected_states:
        loc = projected_states['Location']
        state['location'] = {
            'system': loc.get('StarSystem', 'Unknown'),
            'body': loc.get('Body', ''),
            'station': loc.get('StationName', ''),
        }
    
    # Navigation
    if 'Navigation' in projected_states:
        nav = projected_states['Navigation']
        state['navigation'] = {
            'destination': nav.get('Destination', {}),
            'route': nav.get('Route', []),
        }
    
    # Missions
    if 'Missions' in projected_states:
        state['missions'] = projected_states['Missions']
    
    # Materials
    if 'Materials' in projected_states:
        state['materials'] = projected_states['Materials']
    
    # Cargo
    if 'Cargo' in projected_states:
        state['cargo'] = projected_states['Cargo']
    
    return state


def register_genui_actions(
    actionManager: ActionManager, 
    eventManager: EventManager,
    promptGenerator: PromptGenerator,
    llmModel: LLMModel | None,
    maxRetries: int = 3
):
    """Register GenUI actions with the ActionManager."""
    global event_manager, llm_model, prompt_generator, genui_max_retries
    
    event_manager = eventManager
    prompt_generator = promptGenerator
    llm_model = cast(LLMModel, llmModel)
    genui_max_retries = maxRetries
    
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
        generate_ui,
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
        clear_ui,
        'ui',
        input_template=lambda i, s: "Clearing overlay UI",
    )
