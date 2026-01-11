import datetime
import math
from typing import cast, Any, List, Dict

import requests
import yaml
import traceback
import sys

from pydantic import BaseModel

from ..PromptGenerator import PromptGenerator
from .data import *
from ..ActionManager import ActionManager
from ..EventManager import EventManager
from ..Logger import log
from ..Models import LLMModel, EmbeddingModel

# Type alias for projected states dictionary
ProjectedStates = dict[str, BaseModel]


def get_state_dict(projected_states: ProjectedStates, key: str, default: dict | None = None) -> dict:
    """Helper to get a projection state as a dict for backward-compatible access patterns."""
    if default is None:
        default = {}
    state = projected_states.get(key)
    if state is None:
        return default
    if hasattr(state, 'model_dump'):
        return state.model_dump()
    return state if isinstance(state, dict) else default

llm_model: LLMModel = cast(LLMModel, None)
embedding_model: EmbeddingModel = cast(EmbeddingModel, None)
event_manager: EventManager = cast(EventManager, None)
prompt_generator: PromptGenerator = cast(PromptGenerator, None)
agent_max_tries: int = 7

def web_search_agent(
        obj,
        projected_states,
        prompt_generator,
        llm_model: LLMModel | None = None,
        max_loops: int = 7,
     ):
    """
    Uses an agentic loop to answer a web-related query by calling various internal tools.
    """
    if not llm_model:
        return "LLM model not configured."
    
    query = obj.get('query')
    if not query:
        return "Please provide a query for the web search."

    # These are the tools the agent can use.
    # The functions are defined later in this file.
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_stored_ships",
                "description": "Return all stored ships",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_stored_ship_modules",
                "description": "Return current stored ship modules",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_galnet_news",
                "description": "Retrieve current interstellar news from Galnet. Use this for questions about recent events, thargoids, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Inquiry you are trying to answer. Example: 'What happened to the thargoids recently?'"
                        },
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "system_finder",
                "description": "Find a star system based on allegiance, government, state, power, primary economy, and more.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reference_system": { "type": "string", "description": "Name of the current system. Example: 'Sol'" },
                        "reference_route": { "type": "object", "properties": { "source": { "type": "string" }, "destination": { "type": "string" } }, "required": ["source", "destination"], "description": "Search along a route instead of a single reference system." },
                        "name": { "type": "string", "description": "Required string in system name" },
                        "distance": { "type": "number", "description": "The maximum distance to search" },
                        "allegiance": { "type": "array", "items": { "type": "string", "enum": ["Alliance", "Empire", "Federation", "Guardian", "Independent", "Pilots Federation", "Player Pilots", "Thargoid"] } },
                        "state": { "type": "array", "items": { "type": "string" } },
                        "government": { "type": "array", "items": { "type": "string" } },
                        "power": { "type": "array", "items": { "type": "string" } },
                        "primary_economy": { "type": "array", "items": { "type": "string" } },
                        "security": { "type": "array", "items": { "type": "string" } },
                        "thargoid_war_state": { "type": "array", "items": { "type": "string" } },
                        "population": { "type": "object", "properties": { "comparison": { "type": "string", "enum": ["<", ">"] }, "value": { "type": "number" } } },
                        "sort_by": { "type": "string", "enum": ["distance", "population"], "description": "Sort systems by distance or by population (highest first). Default: distance." },
                        "size": { "type": "integer", "description": "Number of results to return (1-25). Default: 3." }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "station_finder",
                "description": "Find a station for commodities, modules and ships. Sorted by distance or best price when commodity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reference_system": { "type": "string", "description": "Name of the current system. Example: 'Sol'" },
                        "reference_route": { "type": "object", "properties": { "source": { "type": "string" }, "destination": { "type": "string" } }, "required": ["source", "destination"], "description": "Search along a route instead of a single reference system." },
                        "name": { "type": "string", "description": "Required string in station name" },
                        "distance": { "type": "number", "description": "The maximum distance to search in" },
                        "material_trader": { "type": "array", "items": { "type": "string", "enum": ["Encoded", "Manufactured", "Raw"] } },
                        "technology_broker": { "type": "array", "items": { "type": "string", "enum": ["Guardian", "Human"] } },
                        "modules": { "type": "array", "items": { "type": "object", "properties": { "name": { "type": "string" }, "class": { "type": "array", "items": { "type": "string" } }, "rating": { "type": "array", "items": { "type": "string" } } }, "required": ["name"] } },
                        "commodities": { "type": "array", "items": { "type": "object", "properties": { "name": { "type": "string" }, "amount": { "type": "integer" }, "transaction": { "type": "string", "enum": ["Buy", "Sell"] } }, "required": ["name", "amount", "transaction"]} },
                        "ships": { "type": "array", "items": { "type": "object", "properties": { "name": { "type": "string" } }, "required": ["name"] } },
                        "services": { "type": "array", "items": { "type": "object", "properties": { "name": { "type": "string", "enum": ["Black Market", "Interstellar Factors Contact"] } }, "required": ["name"] } },
                        "sort_by": { "type": "string", "enum": ["distance", "bestprice"], "description": "Sort stations either by distance or best price when commodities are included. Default: bestprice." },
                        "include_player_fleetcarrier": { "type": "boolean", "description": "Include Drake-Class Carrier (player-owned fleet carriers) in searches" },
                        "unfiltered_results": { "type": "object", "description": "Set a category to true to include all returned data instead of only the requested items.", "properties": { "commodities": { "type": "boolean" }, "modules": { "type": "boolean" }, "ships": { "type": "boolean" } } },
                        "size": { "type": "integer", "description": "Number of results to return (1-25). Default: 3." }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "body_finder",
                "description": "Find a planet or star of a certain type or with a landmark.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reference_system": { "type": "string", "description": "Name of the current system. Example: 'Sol'" },
                        "reference_route": { "type": "object", "properties": { "source": { "type": "string" }, "destination": { "type": "string" } }, "required": ["source", "destination"], "description": "Search along a route instead of a single reference system." },
                        "name": { "type": "string", "description": "Required string in body name" },
                        "subtype": { "type": "array", "items": { "type": "string" } },
                        "landmark_subtype": { "type": "array", "items": { "type": "string" } },
                        "distance": { "type": "number", "description": "Maximum distance to search" },
                        "rings": { "type": "object", "properties": { "material": { "type": "string" }, "hotspots": { "type": "integer" } }, "required": ["material", "hotspots"] },
                        "signals": { "type": "array", "items": { "type": "string", "enum": ["Biological", "Geological", "Human", "Guardian", "Thargoid"] }, "description": "Filter for signals on the body surface." },
                        "size": { "type": "integer", "description": "Number of results to return (1-25). Default: 3." }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "engineer_finder",
                "description": "Get information about engineers' location, standing and modifications.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": { "type": "string", "description": "Filter engineers by name" },
                        "system": { "type": "string", "description": "Filter engineers by system/location" },
                        "modifications": { "type": "string", "description": "Filter engineers by what they modify" },
                        "progress": { "type": "string", "enum": ["Unknown", "Known", "Invited", "Unlocked"], "description": "Filter engineers by their current progress status" }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "blueprint_finder",
                "description": "Find engineer blueprints based on search criteria. Returns material costs with grade calculations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "modifications": { "type": "array", "items": { "type": "string" }, "description": "Array of modification names to search for - supports fuzzy search." },
                        "engineer": { "type": "string", "description": "Engineer name to search for" },
                        "module": { "type": "string", "description": "Module/hardware name to search for" },
                        "grade": { "type": "integer", "description": "Grade to search for" }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "material_finder",
                "description": "Find and search a list of materials for both ship and suit engineering from my inventory and where to source them from.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": { "type": "array", "items": { "type": "string" }, "description": "Array of material names to search for - supports fuzzy search." },
                        "grade": { "type": "integer", "minimum": 1, "maximum": 5, "description": "Filter ship materials by grade (1-5). Suit materials don't have grades." },
                        "type": { "type": "string", "enum": ["raw", "manufactured", "encoded", "items", "components", "data", "consumables", "ship", "suit"], "description": "Filter by material type." }
                    }
                }
            }
        }
    ]

    # The available_functions dict maps function names to the actual functions
    available_functions = {
        "get_galnet_news": get_galnet_news,
        "system_finder": system_finder,
        "station_finder": station_finder,
        "body_finder": body_finder,
        "engineer_finder": engineer_finder,
        "blueprint_finder": blueprint_finder,
        "material_finder": material_finder,
        "get_stored_ship_modules": get_stored_ship_modules,
        "get_stored_ships": get_stored_ships,
    }

    system_prompt = """
    You are an expert assistant for the game Elite: Dangerous.
    Your goal is to answer the user's question by using the available tools.
    You will be given a user query and a set of tools.
    You can call one or more tools to gather information.
    Once you have enough information, you must generate a concise and helpful final report answering the user's query.
    The report summarizes the interpretation of the query, the search parameters used to acquire the answer and the answer to the user's query.
    
    Do not just regurgitate the tool outputs. Synthesize them into a coherent answer.
    
    If a tool returns an error or no results, try to call it again with different parameters if it makes sense, or try a different tool.
    If you can not find an answer to the user's question, do your best to provide related information given your set of tools and mention this limitation in your final output.

    If you are uncertain if something is a material or a commodity, search for both.
    If the user asks for a specific commodity or module, search explicitly for that in stations, rather than with fitting economies or service that could supply that.
    Explore both options for commodity procurement: mining from planet ring's hotspots or buying it from a station's market.
    
    material_finder returns inventory counts, trade-in calculations, and drop locations.
    blueprint_finder lists material costs per grade, calculates missing materials from inventory, and lists capable engineers.
    engineer_finder reports unlock status (known/invited/unlocked), rank progress, and workshop locations.
    station_finder can locate Material Traders and Technology Brokers. body_finder finds biological signals and mining hotspots.

    Here are some examples of how to use the tools:

    User Query: "Where can I buy a Fer-de-Lance near Sol?"
    1. Call `station_finder` with `{"ships": [{"name": "Fer-de-Lance"}], "reference_system": "Sol"}`.
    2. Summarize the results from `station_finder` and present them to the user in the final report.

    User Query: "I need to engineer my FSD for increased range. What do I need?"
    1. Call `blueprint_finder` with `{"modifications": ["Increased FSD Range"]}` and list all missing grades up to 5 for your ship.
    2. The result will show the materials needed for the different grades.
    3. Call `material_finder` for each of the required materials to check if you have them and where to find them.
    4. Call `engineer_finder` to find the location of the engineers that can perform the modification.
    5. Generate a report summarizing the required materials, where to find them, and which engineers can apply the blueprint.

    User Query: "What's the latest news about the Thargoids?"
    1. Call `get_galnet_news` with `{"query": "Thargoids"}`.
    2. Summarize the news articles in the final report.

    User Query: "Where can I mine Painite?"
    1. Call `body_finder` with `{"rings": {"material": "Painite", "hotspots": 1}}`.
    2. Summarize the found bodies and their hotspot details.
    """

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Current game state is:\n{prompt_generator.generate_status_message(projected_states)}\n\nUser query: {query}"}
    ]

    for iter in range(max_loops):
        try:
            if iter == max_loops - 1:
                messages.append({
                    "role": "user",
                    "content": "Maximum number of iterations reached. Please provide the best possible answer based on the information gathered so far."
                })
                
            response_text, tool_calls = llm_model.generate(
                messages=messages,
                tools=tools if iter < max_loops - 1 else [],
                tool_choice="auto",
            )

            if tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "tool_calls": [t.model_dump() for t in tool_calls]
                })
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = available_functions.get(function_name)
                    if not function_to_call:
                        function_response = f"Error: function {function_name} does not exist."
                    else:
                        try:
                            function_args = json.loads(tool_call.function.arguments)
                            print(function_name, "request:", function_args, file=sys.stderr, flush=True)
                            # All tool functions expect (obj, projected_states)
                            function_response = function_to_call(function_args, projected_states)
                        except Exception as e:
                            log('error', f"Error calling function {function_name}: {e}", traceback.format_exc())
                            print(function_name, "error:", e, traceback.format_exc(), file=sys.stderr, flush=True)
                            function_response = f"Error executing function {function_name}: {e}"

                    print(function_name, "result:", str(function_response), file=sys.stderr, flush=True)
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": str(function_response),
                        }
                    )
            else:
                # No tool call, so this should be the final answer
                return response_text or 'No response content.'

        except Exception as e:
            log('error', f"An error occurred in the agentic loop: {e}", traceback.format_exc())
            return "Sorry, an error occurred while processing your request."

    return "The request could not be completed within the allowed number of steps."

def web_search(obj, projected_states):
    res = web_search_agent(
        obj,
        projected_states,
        prompt_generator=prompt_generator,
        llm_model=llm_model,
        max_loops=agent_max_tries,
    )
    return res

# returns summary of galnet news
def get_galnet_news(obj, projected_states):
    url = "https://cms.zaonce.net/en-GB/jsonapi/node/galnet_article?&sort=-published_at&page[offset]=0&page[limit]=10"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)
        results = json.loads(response.content.decode())["data"]
        articles = []

        if results:
            for result in results:
                article = {
                    "date": result["attributes"]["field_galnet_date"],
                    "title": result["attributes"]["title"],
                    "content": result["attributes"]["body"]["value"],
                }
                articles.append(article)

            response_text, _ = llm_model.generate(
                messages=[{
                    "role": "user",
                    "content": f"Analyze the following list of news articles, either answer the given inquiry or create a short summary that includes all named entities: {articles}\nInquiry: {obj.get('query')}"
                }],
            )

            return response_text

        return "News feed currently unavailable"

    except:
        return "News feed currently unavailable"

def get_stored_ship_modules(obj, projected_states):
    stored_modules = projected_states.get('StoredModules', {})
    items = stored_modules.get('Items', [])
    
    if not items:
        return 'No stored modules found. Advise user to interact with an outfitting service in a station to retrieve information.'
    
    # Group items by star system
    grouped = {}
    for item in items:
        star_system = item.get('StarSystem', 'Unknown')
        if star_system not in grouped:
            grouped[star_system] = {
                'transfer_time': item.get('TransferTime', 0),
                'modules': []
            }
        
        # Build module string
        name = item.get('Name_Localised', item.get('Name', 'Unknown'))
        module_parts = [name]
        
        # Add engineering info if present
        if 'EngineerModifications' in item:
            eng_mod = item.get('EngineerModifications', '')
            level = item.get('Level', '')
            module_parts.append(f"({eng_mod} {level})")
        
        # Add hot indicator
        if item.get('Hot', False):
            module_parts.append("(HOT)")
        
        grouped[star_system]['modules'].append(' '.join(module_parts))
    
    # Format output
    result = {}
    for system, data in grouped.items():
        transfer_time = data['transfer_time']
        header = f"{system} ({transfer_time} seconds)" if transfer_time > 0 else system
        result[header] = data['modules']
    
    return result

def get_stored_ships(obj, projected_states):
    stored_ships = projected_states.get('StoredShips', {})
    ships_here = stored_ships.get('ShipsHere', [])
    ships_remote = stored_ships.get('ShipsRemote', [])
    
    if not ships_here and not ships_remote:
        return {}
    
    result = {}
    
    # Add ships at current station
    if ships_here:
        current_station = stored_ships.get('StationName', 'Current Station')
        ship_names = []
        for ship in ships_here:
            ship_type = ship.get('ShipType', 'Unknown')
            name = ship.get('Name', '')
            if name:
                ship_names.append(f"{ship_type} '{name}'")
            else:
                ship_names.append(ship_type)
        result[current_station] = ship_names
    
    # Group remote ships by star system
    remote_grouped = {}
    for ship in ships_remote:
        # Skip ships that are in transit (they'll be shown separately)
        if ship.get('InTransit', False):
            continue
            
        star_system = ship.get('StarSystem', 'Unknown')
        if star_system not in remote_grouped:
            remote_grouped[star_system] = {
                'transfer_time': ship.get('TransferTime', 0),
                'ships': []
            }
        
        # Build ship string
        ship_type = ship.get('ShipType_Localised', ship.get('ShipType', 'Unknown'))
        name = ship.get('Name', '')
        ship_parts = [f"{ship_type} '{name}'" if name else ship_type]
        
        # Add hot indicator
        if ship.get('Hot', False):
            ship_parts.append("(HOT)")
        
        remote_grouped[star_system]['ships'].append(' '.join(ship_parts))
    
    # Format remote ships output
    for system, data in remote_grouped.items():
        transfer_time = data['transfer_time']
        header = f"{system} ({transfer_time} seconds)" if transfer_time > 0 else system
        result[header] = data['ships']
    
    return result

def blueprint_finder(obj, projected_states):
    import yaml
    # Get current location coordinates for distance calculation
    current_location = get_state_dict(projected_states, 'Location')
    current_coords = current_location.get('StarPos', [0, 0, 0])
    
    # Helper function to calculate distance to engineer
    def calculate_distance_to_engineer(engineer_coords):
        if not current_coords or len(current_coords) != 3:
            return "Unknown"
        
        x1, y1, z1 = current_coords
        x2, y2, z2 = engineer_coords['x'], engineer_coords['y'], engineer_coords['z']
        
        distance_ly = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
        return round(distance_ly, 2)

    # Get engineer progress data
    engineer_progress = get_state_dict(projected_states, 'EngineerProgress')
    game_engineers = {}
    if engineer_progress:
        engineers = engineer_progress.get('Engineers', [])
        for engineer in engineers:
            # Convert EngineerID to string to match ship_engineers.json keys
            engineer_id = str(engineer.get('EngineerID'))
            game_engineers[engineer_id] = engineer

    # Helper function to format engineer name with location/status
    def format_engineer_info(engineer_name):
        """Format engineer name with location and unlock status"""
        # Find engineer in ship_engineers data
        engineer_info = None
        engineer_id = None
        
        # Search through ship_engineers to find matching engineer
        for eng_id, eng_data in ship_engineers.items():
            if eng_data['Engineer'] == engineer_name:
                engineer_info = eng_data
                engineer_id = eng_id
                break
        
        if not engineer_info:
            # Fallback: return just the name if not found in ship_engineers
            return engineer_name
        
        # Check if engineer is unlocked
        game_data = game_engineers.get(engineer_id)
        if game_data and game_data.get('Progress') == 'Unlocked':
            # Engineer is unlocked - show location and distance
            distance = calculate_distance_to_engineer(engineer_info['Coords'])
            location = engineer_info['Location'].replace(' (permit required)', '')
            
            if distance != "Unknown":
                return f"{engineer_name} ({location} {distance}LY)"
            else:
                return f"{engineer_name} ({location})"
        else:
            # Engineer is not unlocked - show as locked
            return f"{engineer_name} (Locked)"

    # Extract search parameters - can be combined
    search_modifications = []
    if obj and obj.get('modifications'):
        modifications_param = obj.get('modifications')
        # Only accept arrays of modifications now
        if isinstance(modifications_param, list):
            search_modifications = [mod.lower().strip() for mod in modifications_param if mod]
    search_engineer = obj.get('engineer', '').lower().strip() if obj else ''
    search_module = obj.get('module', '').lower().strip() if obj else ''
    search_grade = obj.get('grade', '') if obj else ''

    # Convert search_grade to int if provided
    if search_grade and str(search_grade).isdigit():
        search_grade = int(search_grade)
    else:
        search_grade = None

    # Get inventory data from projected states
    materials_data = get_state_dict(projected_states, 'Materials')
    shiplocker_data = get_state_dict(projected_states, 'ShipLocker')

    # Helper function to get inventory count for a material
    def get_inventory_count(material_name):
        """Get the total count of a material from both Materials and ShipLocker inventories"""
        total_count = 0
        material_name_lower = material_name.lower()
        
        # Check Materials projection (ship materials)
        for material_type in ['Raw', 'Manufactured', 'Encoded']:
            type_materials = materials_data.get(material_type, [])
            for material in type_materials:
                # Check both Name and Name_Localised for matching
                if (material.get('Name', '').lower() == material_name_lower or
                    material.get('Name_Localised', '').lower() == material_name_lower):
                    total_count += material.get('Count', 0)
        
        # Check ShipLocker projection (suit materials)
        for locker_type in ['Items', 'Components', 'Data', 'Consumables']:
            type_materials = shiplocker_data.get(locker_type, [])
            for material in type_materials:
                # Check both Name and Name_Localised for matching
                if (material.get('Name', '').lower() == material_name_lower or
                    material.get('Name_Localised', '').lower() == material_name_lower):
                    total_count += material.get('Count', 0)
        
        return total_count

    # Helper function to check material availability and create inventory info
    def check_material_availability(materials_needed):
        """Check availability of materials and return simplified info"""
        missing_materials = {}
        has_all_materials = True
        
        for material_name, needed_count in materials_needed.items():
            # Skip credits as they're not tracked in material inventory
            if material_name.lower() == 'credits':
                continue
                
            available_count = get_inventory_count(material_name)
            if available_count < needed_count:
                has_all_materials = False
                shortage = needed_count - available_count
                missing_materials[material_name] = shortage
        
        return missing_materials, has_all_materials


    # Helper function for fuzzy matching using Levenshtein distance
    def matches_fuzzy(search_term, target_string):
        if not search_term or not target_string:
            return False

        # Module synonyms mapping - maps synonyms to their main module names
        MODULE_SYNONYMS = {
            # Kinematic Armaments Weapons synonyms
            "karma p-15": "Kinematic Armaments Weapons",
            "karma l-6": "Kinematic Armaments Weapons", 
            "karma c-44": "Kinematic Armaments Weapons",
            "karma ar-50": "Kinematic Armaments Weapons",
            "karma": "Kinematic Armaments Weapons",
            
            # Takada Weapons synonyms
            "tk aphelion": "Takada Weapons",
            "tk eclipse": "Takada Weapons", 
            "tk zenith": "Takada Weapons",
            "takada": "Takada Weapons",
            
            # Manticore weapons synonyms
            "manticore executioner": "Manticore weapons",
            "manticore intimidator": "Manticore weapons",
            "manticore oppressor": "Manticore weapons", 
            "manticore tormentor": "Manticore weapons",
            "manticore": "Manticore weapons",
            
            # Suit synonyms
            "flight suit": "suit",
            "artemis suit": "suit",
            "maverick suit": "suit", 
            "dominator suit": "suit"
        }

        search_lower = search_term.lower()
        target_lower = target_string.lower()

        # First check if the search term is a synonym
        if search_lower in MODULE_SYNONYMS:
            # If the search term is a synonym, check if it maps to the target
            if MODULE_SYNONYMS[search_lower].lower() == target_lower:
                return True

        # Check if any part of the search term matches a synonym
        search_words = search_lower.split()
        for word in search_words:
            if word in MODULE_SYNONYMS:
                if MODULE_SYNONYMS[word].lower() == target_lower:
                    return True

        # Original fuzzy matching logic - check for exact substring matches
        if search_lower in target_lower:
            return True

        # Split into words for fuzzy matching
        target_words = target_lower.replace(',', ' ').replace('(', ' ').replace(')', ' ').split()

        # Fuzzy matching using Levenshtein distance
        for search_word in search_words:
            for target_word in target_words:
                # Allow some fuzzy matching based on word length
                max_distance = max(1, len(search_word) // 3)  # Allow 1 error per 3 characters
                if levenshtein_distance(search_word, target_word) <= max_distance:
                    return True

        return False

        # Helper function to calculate total materials needed for a grade

    def calculate_materials_for_grade(base_cost, grade):
        """Calculate total materials needed for a specific grade"""
        total_materials = {}

        # Multiply each material by the grade level
        for material, amount in base_cost.items():
            total_materials[material] = amount * grade

        return total_materials

    # Build results
    results = {}

    # Prepare lists for fuzzy matching
    all_modifications = list(engineering_modifications.keys())
    all_engineers = set()
    all_modules = set()

    # Collect all unique engineers and modules
    for mod_name, mod_data in engineering_modifications.items():
        if "module_recipes" in mod_data:
            for module_name, grades in mod_data["module_recipes"].items():
                all_modules.add(module_name)
                for grade, grade_info in grades.items():
                    for engineer in grade_info.get("engineers", []):
                        all_engineers.add(engineer)

    all_engineers = list(all_engineers)
    all_modules = list(all_modules)

    # Search through all modifications
    for mod_name, mod_data in engineering_modifications.items():
        # Check if modification matches search criteria
        if search_modifications:
            modification_match = False
            for search_mod in search_modifications:
                if matches_fuzzy(search_mod, mod_name):
                    modification_match = True
                    break
            if not modification_match:
                continue

        if "module_recipes" not in mod_data:
            continue

        mod_results = {}

        for module_name, grades in mod_data["module_recipes"].items():
            # Check if module matches search criteria
            if search_module and not matches_fuzzy(search_module, module_name):
                continue

            module_results = {}

            for grade, grade_info in grades.items():
                # Convert grade to integer for comparison and calculations
                grade_int = int(grade) if grade.isdigit() else 0
                
                # Check if grade matches search criteria
                if search_grade is not None and grade_int != search_grade:
                    continue

                # Check if any engineer matches search criteria
                engineers = grade_info.get("engineers", [])
                if search_engineer:
                    matching_engineers = [eng for eng in engineers if matches_fuzzy(search_engineer, eng)]
                    if not matching_engineers:
                        continue
                    engineers = matching_engineers

                    # Calculate total materials needed for this grade
                base_cost = grade_info.get("cost", {})
                total_materials = calculate_materials_for_grade(base_cost, grade_int)

                # Check material availability
                missing_materials, has_all_materials = check_material_availability(total_materials)

                # Format engineers with location and status info
                formatted_engineers = [format_engineer_info(eng) for eng in engineers]

                grade_results = {
                    "materials_needed": total_materials
                }
                if missing_materials:
                    grade_results["materials_missing"] = missing_materials
                grade_results["engineers"] = formatted_engineers
                grade_results["enough_mats"] = has_all_materials

                module_results[f"Grade {grade}"] = grade_results

            if module_results:
                mod_results[module_name] = module_results

        if mod_results:
            # Check if this is an experimental modification and add suffix
            display_name = mod_name
            if mod_data.get("experimental", False):
                display_name = f"{mod_name} (Experimental)"
            results[display_name] = mod_results

    # Check if any blueprints were found
    if not results:
        search_terms = []
        if search_modifications:
            if len(search_modifications) == 1:
                search_terms.append(f"modifications: '{search_modifications[0]}'")
            else:
                mod_list = ', '.join([f"'{mod}'" for mod in search_modifications])
                search_terms.append(f"modifications: {mod_list}")
        if search_engineer:
            search_terms.append(f"engineer: '{search_engineer}'")
        if search_module:
            search_terms.append(f"module: '{search_module}'")
        if search_grade:
            search_terms.append(f"grade: {search_grade}")

        if search_terms:
            # If searching by modifications failed, show available options
            if search_modifications:
                if len(search_modifications) == 1:
                    return f"No blueprints found matching modifications: '{search_modifications[0]}'\n\nAvailable modification types:\n" + yaml.dump(sorted(all_modifications))
                else:
                    mod_list = ', '.join([f"'{mod}'" for mod in search_modifications])
                    return f"No blueprints found matching modifications: {mod_list}\n\nAvailable modification types:\n" + yaml.dump(sorted(all_modifications))
            elif search_engineer:
                return f"No blueprints found matching engineer: '{search_engineer}'\n\nAvailable engineers:\n" + yaml.dump(sorted(all_engineers))
            elif search_module:
                return f"No blueprints found matching module: '{search_module}'\n\nAvailable modules:\n" + yaml.dump(sorted(all_modules))
            else:
                return f"No blueprints found matching search criteria: {', '.join(search_terms)}"
        else:
            return "No search criteria provided. Please specify modifications, engineer, module, or grade."

    # Convert to YAML format
    yaml_output = yaml.dump(results, default_flow_style=False, sort_keys=False)

    # Add search info to the output if filters were applied
    search_info = []
    if search_modifications:
        if len(search_modifications) == 1:
            search_info.append(f"modifications: '{search_modifications[0]}'")
        else:
            mod_list = ', '.join([f"'{mod}'" for mod in search_modifications])
            search_info.append(f"modifications: {mod_list}")
    if search_engineer:
        search_info.append(f"engineer: '{search_engineer}'")
    if search_module:
        search_info.append(f"module: '{search_module}'")
    if search_grade:
        search_info.append(f"grade: {search_grade}")

    if search_info:
        return f"Blueprint Search Results (filtered by {', '.join(search_info)}):\n\n```yaml\n{yaml_output}```"
    else:
        return f"All Available Blueprints:\n\n```yaml\n{yaml_output}```"


def engineer_finder(obj, projected_states):
    # Get current location coordinates for distance calculation
    current_location = get_state_dict(projected_states, 'Location')
    current_coords = current_location.get('StarPos', [0, 0, 0])
    
    # Helper function to calculate distance to engineer
    def calculate_distance_to_engineer(engineer_coords):
        if not current_coords or len(current_coords) != 3:
            return "Unknown"
        
        x1, y1, z1 = current_coords
        x2, y2, z2 = engineer_coords['x'], engineer_coords['y'], engineer_coords['z']
        
        distance_ly = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)
        return round(distance_ly, 2)
    


    # Extract search parameters - can be combined
    search_name = obj.get('name', '').lower().strip() if obj else ''
    search_system = obj.get('system', '').lower().strip() if obj else ''
    search_modifications = obj.get('modifications', '').lower().strip() if obj else ''
    search_progress = obj.get('progress', '').strip() if obj else ''

    engineer_progress = get_state_dict(projected_states, 'EngineerProgress')

    if not engineer_progress:
        return "No engineer progress found"

    engineers = engineer_progress.get('Engineers', [])

    # Create a lookup for engineers from game data
    game_engineers = {}
    for engineer in engineers:
        # Convert EngineerID to string to match ship_engineers.json keys
        engineer_id = str(engineer.get('EngineerID'))
        game_engineers[engineer_id] = engineer

    # Helper function for fuzzy matching modifications using Levenshtein distance
    def matches_modifications(modifies_dict, search_term):
        search_terms = search_term.split()
        modifies_words = []

        # Extract all words from modification names
        for mod_name in modifies_dict.keys():
            mod_lower = mod_name.lower()
            # First check for exact substring matches
            for term in search_terms:
                if term in mod_lower:
                    return True
            # Add words for fuzzy matching
            mod_words = mod_lower.replace(',', ' ').replace('(', ' ').replace(')', ' ').split()
            modifies_words.extend(mod_words)

        # Fuzzy matching using Levenshtein distance
        for search_word in search_terms:
            for modifies_word in modifies_words:
                # Allow some fuzzy matching based on word length
                max_distance = max(1, len(search_word) // 3)  # Allow 1 error per 3 characters
                if levenshtein_distance(search_word, modifies_word) <= max_distance:
                    return True

        return False

    # Helper function to check if engineer matches search criteria
    def matches_search_criteria(engineer_info, engineer_name, engineer_progress):
        # Check name match
        if search_name and search_name not in engineer_name.lower():
            return False

        # Check system/location match
        if search_system:
            location = engineer_info.get('Location', '').lower()
            # Remove permit required text for matching
            location_clean = location.replace(' (permit required)', '')
            if search_system not in location_clean:
                return False

        # Check modifications match
        if search_modifications:
            modifies = engineer_info.get('Modifies', '')
            if not matches_modifications(modifies, search_modifications):
                return False

        # Check progress match
        if search_progress and search_progress != engineer_progress:
            return False

        return True

    # Build the comprehensive engineer overview
    engineer_overview = {
        'ship_engineers': {},
        'suit_engineers': {}
    }

    # Process ALL ship engineers
    for engineer_id, engineer_info in ship_engineers.items():
        engineer_name = engineer_info['Engineer']

        engineer_data = engineer_info.copy()
        game_data = game_engineers.get(engineer_id)

        if game_data:
            # Engineer is known in game
            progress = game_data.get('Progress')
            rank = game_data.get('Rank', 0)
            rank_progress = game_data.get('RankProgress', 0)

            engineer_data['Progress'] = progress

            if progress == 'Unlocked':
                engineer_data['Rank'] = rank
                if rank_progress > 0:
                    engineer_data['RankProgress'] = f"{rank_progress}% towards rank {rank + 1}"
                else:
                    engineer_data['RankProgress'] = "Max rank achieved" if rank >= 5 else "No progress towards next rank"

                # Keep HowToGainRep if not max rank
                if rank < 5:
                    engineer_data['HowToGainRep'] = engineer_info['HowToGainRep']

            elif progress == 'Invited':
                engineer_data['NextStep'] = f"To unlock: {engineer_info['HowToUnlock']}"
            elif progress == 'Known':
                engineer_data['NextStep'] = f"To get invite: {engineer_info['HowToGetInvite']}"
        else:
            # Engineer is unknown - show how to find them
            progress = 'Unknown'
            engineer_data['Progress'] = progress
            engineer_data['NextStep'] = f"To discover: {engineer_info['HowToFind']}"

        # Check if engineer matches search criteria
        if not matches_search_criteria(engineer_info, engineer_name, progress):
            continue

        # Calculate distance and create new Location format
        distance = calculate_distance_to_engineer(engineer_info['Coords'])
        workshop = engineer_info['Workshop']
        location = engineer_info['Location']
        
        if distance != "Unknown":
            engineer_data['Location'] = f"{workshop} ({location} {distance}LY)"
        else:
            engineer_data['Location'] = f"{workshop} ({location})"

        # Clean up fields not needed in final output (except HowToGainRep for unlocked engineers with rank < 5)
        fields_to_remove = ['HowToGetInvite', 'HowToUnlock', 'HowToFind', 'Engineer', 'Workshop', 'Coords']
        if game_data and game_data.get('Progress') == 'Unlocked' and game_data.get('Rank', 0) < 5:
            # Keep HowToGainRep for unlocked engineers not at max rank
            pass  # Don't add HowToGainRep to removal list
        else:
            fields_to_remove.append('HowToGainRep')

        for field in fields_to_remove:
            engineer_data.pop(field, None)

        engineer_overview['ship_engineers'][engineer_name] = engineer_data

    # Process ALL suit engineers
    for engineer_id, engineer_info in suit_engineers.items():
        engineer_name = engineer_info['Engineer']

        engineer_data = engineer_info.copy()
        game_data = game_engineers.get(engineer_id)

        if game_data:
            # Engineer is known in game
            progress = game_data.get('Progress')
            engineer_data['Progress'] = progress

            if progress == 'Unlocked':
                engineer_data['Status'] = 'Available for modifications'
                if engineer_info.get('HowToReferral') != 'N/A':
                    engineer_data['ReferralTask'] = engineer_info['HowToReferral']
            elif progress == 'Invited':
                engineer_data['NextStep'] = f"To unlock: Visit {engineer_info['Location']}"
            elif progress == 'Known':
                engineer_data['NextStep'] = f"To get invite: {engineer_info['HowToGetInvite']}"
        else:
            # Engineer is unknown - show how to find them
            progress = 'Unknown'
            engineer_data['Progress'] = progress
            engineer_data['NextStep'] = f"To discover: {engineer_info['HowToFind']}"

        # Check if engineer matches search criteria
        if not matches_search_criteria(engineer_info, engineer_name, progress):
            continue

        # Calculate distance and create new Location format
        distance = calculate_distance_to_engineer(engineer_info['Coords'])
        location = engineer_info['Location']
        
        if distance != "Unknown":
            engineer_data['Location'] = f"{location} ({distance}LY)"
        else:
            engineer_data['Location'] = location

        # Clean up fields not needed in final output for suit engineers
        fields_to_remove = ['HowToGetInvite', 'HowToFind', 'HowToReferral', 'Engineer', 'Coords']
        for field in fields_to_remove:
            engineer_data.pop(field, None)

        # Convert modifications from dict to list for suit engineers (no ranks)
        if 'Modifies' in engineer_data:
            engineer_data['Modifies'] = list(engineer_data['Modifies'].keys())

        engineer_overview['suit_engineers'][engineer_name] = engineer_data

    # Check if any engineers were found
    total_engineers = len(engineer_overview['ship_engineers']) + len(engineer_overview['suit_engineers'])
    if total_engineers == 0:
        search_terms = []
        if search_name:
            search_terms.append(f"name: '{search_name}'")
        if search_system:
            search_terms.append(f"system: '{search_system}'")
        if search_modifications:
            search_terms.append(f"modifications: '{search_modifications}'")
        if search_progress:
            search_terms.append(f"progress: '{search_progress}'")

        if search_terms:
            # If searching by modifications failed, show available options
            if search_modifications:
                # Collect all unique modification values
                all_modifications = set()
                for engineer_info in ship_engineers.values():
                    mods = engineer_info.get('Modifies', {})
                    # Add all modification names from dict keys
                    for mod_name in mods.keys():
                        all_modifications.add(mod_name)

                for engineer_info in suit_engineers.values():
                    mods = engineer_info.get('Modifies', {})
                    # Add all modification names from dict keys
                    for mod_name in mods.keys():
                        all_modifications.add(mod_name)

                sorted_mods = sorted(list(all_modifications))
                return f"No engineers found matching modifications: '{search_modifications}'\n\nValid modification types:\n" + yaml.dump(sorted_mods)

            return f"No engineers found matching search criteria: {', '.join(search_terms)}"
        else:
            return "No engineers found"

    # Convert to YAML format
    yaml_output = yaml.dump(engineer_overview, default_flow_style=False, sort_keys=False)
    # log('debug', 'engineers', yaml_output)

    # Add search info to the output if filters were applied
    search_info = []
    if search_name:
        search_info.append(f"name: '{search_name}'")
    if search_system:
        search_info.append(f"system: '{search_system}'")
    if search_modifications:
        search_info.append(f"modifications: '{search_modifications}'")
    if search_progress:
        search_info.append(f"progress: '{search_progress}'")

    if search_info:
        return f"Engineer Progress Overview (filtered by {', '.join(search_info)}):\n\n```{yaml_output}```"
    else:
        return f"Engineer Progress Overview:\n\n```yaml\n{yaml_output}```"


def material_finder(obj, projected_states):
    import yaml

    # Extract search parameters
    search_names = []
    if obj and obj.get('name'):
        name_param = obj.get('name')
        if isinstance(name_param, list):
            search_names = [name.lower().strip() for name in name_param if name]

    search_grade = obj.get('grade', 0) if obj else 0
    search_type = obj.get('type', '').lower().strip() if obj else ''

    # Get data from projected states
    materials_data = get_state_dict(projected_states, 'Materials')
    shiplocker_data = get_state_dict(projected_states, 'ShipLocker')

    # Helper function to find ship material info
    def find_ship_material_info(material_name):
        if not material_name:
            return None
        material_name_lower = material_name.lower()

        # Check raw materials
        for category, grades in ship_raw_materials_map.items():
            for grade, materials in grades.items():
                if material_name_lower in materials:
                    return {'category': 'Ship', 'type': 'Raw', 'grade': grade, 'section': f'Category {category}'}

        # Check manufactured materials
        for section, grades in ship_manufactured_materials_map.items():
            for grade, materials in grades.items():
                if material_name_lower in materials:
                    return {'category': 'Ship', 'type': 'Manufactured', 'grade': grade, 'section': section}

        # Check encoded materials
        for section, grades in ship_encoded_materials_map.items():
            for grade, materials in grades.items():
                if material_name_lower in materials:
                    return {'category': 'Ship', 'type': 'Encoded', 'grade': grade, 'section': section}

        return None

    # Helper function to find suit material info
    def find_suit_material_info(material_name):
        if not material_name:
            return None
        material_name_lower = material_name.lower()

        if material_name_lower in suit_items_materials:
            return {'category': 'Suit', 'type': 'Items', 'grade': None, 'section': 'Items'}
        elif material_name_lower in suit_components_materials:
            return {'category': 'Suit', 'type': 'Components', 'grade': None, 'section': 'Components'}
        elif material_name_lower in suit_data_materials:
            return {'category': 'Suit', 'type': 'Data', 'grade': None, 'section': 'Data'}
        elif material_name_lower in suit_consumables_materials:
            return {'category': 'Suit', 'type': 'Consumables', 'grade': None, 'section': 'Consumables'}

        return None

    # Helper function to get higher grade materials from the same family
    def get_higher_materials(material_info, current_material):
        higher_materials = []

        if material_info['category'] != 'Ship' or material_info['grade'] is None:
            return higher_materials  # Only ship materials have grades

        if material_info['type'] == 'Raw':
            materials_map = ship_raw_materials_map
            max_grade = 4  # Raw materials go up to grade 4
            # For raw materials, find the category that contains this material
            material_category = None
            for category, grades in materials_map.items():
                for grade, materials in grades.items():
                    if current_material in materials:
                        material_category = category
                        break
                if material_category:
                    break

            if material_category and material_category in materials_map:
                for grade in range(material_info['grade'] + 1, max_grade + 1):
                    if grade in materials_map[material_category]:
                        for mat_name in materials_map[material_category][grade]:
                            # Check if player has this material
                            player_materials = materials_data.get('Raw', [])
                            for player_mat in player_materials:
                                if player_mat.get('Name', '').lower() == mat_name:
                                    display_name = display_names.get(mat_name, mat_name.title())
                                    higher_materials.append({
                                        'name': display_name,
                                        'count': player_mat.get('Count', 0),
                                        'grade': grade
                                    })

        elif material_info['type'] in ['Manufactured', 'Encoded']:
            materials_map = ship_manufactured_materials_map if material_info['type'] == 'Manufactured' else ship_encoded_materials_map
            max_grade = 5  # Manufactured and Encoded materials go up to grade 5

            # Find the section that contains this material
            material_section = material_info['section']
            if material_section in materials_map:
                for grade in range(material_info['grade'] + 1, max_grade + 1):
                    if grade in materials_map[material_section]:
                        for mat_name in materials_map[material_section][grade]:
                            # Check if player has this material
                            player_materials = materials_data.get(material_info['type'], [])
                            for player_mat in player_materials:
                                if player_mat.get('Name', '').lower() == mat_name:
                                    display_name = display_names.get(mat_name, mat_name.title())
                                    higher_materials.append({
                                        'name': display_name,
                                        'count': player_mat.get('Count', 0),
                                        'grade': grade
                                    })

        return higher_materials

    # Helper function to check if material matches search criteria
    def matches_criteria(material_name, material_info, count):
        # Check name match using fuzzy search
        if search_names:
            display_name = display_names.get(material_name, material_name)
            name_match = False
            for search_name in search_names:
                # First check for exact substring matches (case insensitive)
                if search_name in material_name or search_name in display_name.lower():
                    name_match = True
                    break
                
                # Then use more restrictive fuzzy matching based on string length
                max_distance = max(1, min(len(search_name), len(material_name)) // 4)  # Allow 1 error per 4 characters, minimum 1
                if (levenshtein_distance(search_name, material_name) <= max_distance or 
                    levenshtein_distance(search_name, display_name.lower()) <= max_distance):
                    name_match = True
                    break
            if not name_match:
                return False

        # Check grade match (only for ship materials)
        if search_grade > 0 and material_info['grade'] is not None:
            if material_info['grade'] != search_grade:
                return False

        # Check type match
        if search_type:
            type_matches = {
                'raw': 'Raw', 'manufactured': 'Manufactured', 'encoded': 'Encoded',
                'items': 'Items', 'components': 'Components', 'data': 'Data', 'consumables': 'Consumables',
                'ship': 'Ship', 'suit': 'Suit'
            }
            expected_type = type_matches.get(search_type)
            if expected_type in ['Raw', 'Manufactured', 'Encoded', 'Items', 'Components', 'Data', 'Consumables']:
                if material_info['type'] != expected_type:
                    return False
            elif expected_type in ['Ship', 'Suit']:
                if material_info['category'] != expected_type:
                    return False

        return True

    # Build results
    results = []

    # Process ship materials from Materials projection
    if materials_data:
        for material_type in ['Raw', 'Manufactured', 'Encoded']:
            type_materials = materials_data.get(material_type, [])

            for material in type_materials:
                material_name = material.get('Name', '').lower()
                count = material.get('Count', 0)

                if count == 0:
                    continue

                material_info = find_ship_material_info(material_name)
                if not material_info:
                    continue

                if not matches_criteria(material_name, material_info, count):
                    continue

                display_name = display_names.get(material_name, material_name.title())

                # Get higher grade materials for trading info
                higher_materials = get_higher_materials(material_info, material_name)

                result = {
                    'name': display_name,
                    'count': count,
                    'category': material_info['category'],
                    'type': material_info['type'],
                    'grade': material_info['grade'],
                    'section': material_info['section']
                }

                if higher_materials:
                    result['tradeable_higher_grades'] = higher_materials

                results.append(result)

    # Process suit materials from ShipLocker projection
    if shiplocker_data:
        for material_type in ['Items', 'Components', 'Data', 'Consumables']:
            type_materials = shiplocker_data.get(material_type, [])

            for material in type_materials:
                material_name = material.get('Name', '').lower()
                count = material.get('Count', 0)

                if count == 0:
                    continue

                material_info = find_suit_material_info(material_name)
                if not material_info:
                    continue

                if not matches_criteria(material_name, material_info, count):
                    continue

                display_name = display_names.get(material_name, material.get('Name_Localised', material_name.title()))

                result = {
                    'name': display_name,
                    'count': count,
                    'category': material_info['category'],
                    'type': material_info['type'],
                    'section': material_info['section']
                }

                results.append(result)

    # Check if any materials were found and handle missing materials when searching by name - this is due to E:D omitting missing materials
    if not results and search_names:
        missing_materials = []
        
        for search_name in search_names:
            # Skip if search_name is None or empty
            if not search_name:
                continue

            # Check if this is a valid ship material
            ship_material_info = find_ship_material_info(search_name)
            if ship_material_info:
                display_name = display_names.get(search_name, search_name.title())
                
                # Get higher grade materials for trading info (same as found materials)
                higher_materials = get_higher_materials(ship_material_info, search_name)

                result = {
                    'name': display_name,
                        'count': 0,
                        'category': ship_material_info['category'],
                        'type': ship_material_info['type'],
                        'grade': ship_material_info['grade'],
                        'section': ship_material_info['section']
                    }

                if higher_materials:
                    result['tradeable_higher_grades'] = higher_materials
                
                missing_materials.append(result)
                continue

            # Check if this is a valid suit material
            suit_material_info = find_suit_material_info(search_name)
            if suit_material_info:
                display_name = display_names.get(search_name, search_name.title())
                missing_materials.append({
                'name': display_name,
                    'count': 0,
                    'category': suit_material_info['category'],
                    'type': suit_material_info['type'],
                    'section': suit_material_info['section']
                })
        
        # If we found valid materials that are just missing, show them with count 0
        if missing_materials:
            results.extend(missing_materials)

    # Check if any materials were found after checking for missing ones
    if not results:
        search_terms = []
        if search_names:
            name_list = ', '.join([f"'{name}'" for name in search_names])
            search_terms.append(f"name(s): {name_list}")
        if search_grade > 0:
            search_terms.append(f"grade: {search_grade}")
        if search_type:
            search_terms.append(f"type: '{search_type}'")

        if search_terms:
            return f"No materials found matching search criteria: {', '.join(search_terms)}"
        else:
            return "No materials found"

    # Format results
    formatted_results = []
    for result in results:
        if result['category'] == 'Ship':
            material_line = f"{result['count']}x {result['name']} ({result['category']} {result['type']}, Grade {result['grade']})"
        else:  # Suit materials
            material_line = f"{result['count']}x {result['name']} ({result['category']} {result['type']})"

        # Get source information for this material category
        source_info = ""
        if result['type'] == 'Raw':
            # Extract category number from "Category X" format
            category_num = int(result['section'].replace('Category ', ''))
            if category_num in ship_raw_materials_map:
                source_info = ship_raw_materials_map[category_num].get('source', '')
        elif result['type'] == 'Manufactured' and result['section'] in ship_manufactured_materials_map:
            source_info = ship_manufactured_materials_map[result['section']].get('source', '')
        elif result['type'] == 'Encoded' and result['section'] in ship_encoded_materials_map:
            source_info = ship_encoded_materials_map[result['section']].get('source', '')

        trading_lines = []
        higher_convertible_total = 0

        # Higher grade trade-down list with convertible amounts
        if result.get('tradeable_higher_grades'):
            trading_lines.append("Higher grades trade-in:")
            target_grade = int(result.get('grade', 0) or 0)
            for higher_mat in result['tradeable_higher_grades']:
                count_h = int(higher_mat.get('count', 0) or 0)
                grade_h = int(higher_mat.get('grade', 0) or 0)
                if grade_h > target_grade and count_h > 0:
                    steps = grade_h - target_grade
                    convertible_h = count_h * (3 ** steps)
                    if convertible_h > 0:
                        trading_lines.append(f"- {count_h}x {higher_mat.get('name', '')} (Grade {grade_h}) => +{convertible_h}")
                        higher_convertible_total += convertible_h

        # Lower grade trade-up list and new total
        lower_list = result.get('tradeable_lower_grades') or []
        lower_lines = []
        lower_convertible_total = 0
        if lower_list:
            lower_lines.append("Lower grades trade-in:")
            target_grade = int(result.get('grade', 0) or 0)
            for low in lower_list:
                low_count = int(low.get('count', 0) or 0)
                low_grade = int(low.get('grade', 0) or 0)
                if target_grade > low_grade and low_count > 0:
                    steps = target_grade - low_grade
                    convertible = low_count // (6 ** steps)
                    if convertible > 0:
                        lower_lines.append(f"- {low_count}x {low.get('name', '')} (Grade {low_grade}) => +{convertible}")
                        lower_convertible_total += convertible

        # Append lines to output
        formatted_results.append(material_line)
        if lower_lines:
            formatted_results.extend(lower_lines)
        if trading_lines:
            formatted_results.extend(trading_lines)
        if lower_lines or trading_lines:
            total_all = int(result.get('count', 0) or 0) + lower_convertible_total + higher_convertible_total
            formatted_results.append(f"Total if all traded in: {total_all}")
        if source_info:
            formatted_results.append(f"Source location for the highest grade: {source_info}")

    # Sort results while preserving trading info structure
    def sort_key(item):
        if isinstance(item, str) and 'x ' in item and '(' in item:
            if 'Ship Raw' in item:
                type_order = 0
            elif 'Ship Manufactured' in item:
                type_order = 1
            elif 'Ship Encoded' in item:
                type_order = 2
            elif 'Suit Items' in item:
                type_order = 3
            elif 'Suit Components' in item:
                type_order = 4
            elif 'Suit Data' in item:
                type_order = 5
            elif 'Suit Consumables' in item:
                type_order = 6
            else:
                type_order = 7

            # Extract grade for ship materials
            import re
            match = re.search(r'Grade (\d)', item)
            grade = int(match.group(1)) if match else 0

            # Extract name for sorting
            name_match = re.search(r'\d+x ([^(]+)', item)
            name = name_match.group(1).strip() if name_match else ''

            return (type_order, grade, name)
        else:
            return (999, 999, item)  # Put non-material lines at end

    # Sort while preserving trading info structure
    material_blocks = []
    current_block = []

    for line in formatted_results:
        if isinstance(line, str) and 'x ' in line and '(' in line:
            if current_block:
                material_blocks.append(current_block)
            current_block = [line]
        else:
            current_block.append(line)

    if current_block:
        material_blocks.append(current_block)

    # Sort blocks by their main material line
    material_blocks.sort(key=lambda block: sort_key(block[0]))

    # Flatten back to single list
    sorted_results = []
    for block in material_blocks:
        sorted_results.extend(block)

    # Add search info to the output if filters were applied
    search_info = []
    if search_names:
        if len(search_names) == 1:
            search_info.append(f"name: '{search_names[0]}'")
        else:
            name_list = ', '.join([f"'{name}'" for name in search_names])
            search_info.append(f"names: {name_list}")
    if search_grade > 0:
        search_info.append(f"grade: {search_grade}")
    if search_type:
        search_info.append(f"type: '{search_type}'")

    yaml_output = yaml.dump(sorted_results, default_flow_style=False, sort_keys=False)

    if search_info:
        return f"Materials Inventory (filtered by {', '.join(search_info)}):\n\n```yaml\n{yaml_output}```"
    else:
        return f"Materials Inventory:\n\n```yaml\n{yaml_output}```"


def educated_guesses_message(search_query, valid_list):
    search_lower = search_query.lower()
    suggestions = []

    # First try substring matching (existing behavior)
    split_string = search_query.split()
    for word in split_string:
        for element in valid_list:
            if word.lower() in element.lower() and element not in suggestions:
                suggestions.append(element)

    # If we don't have enough suggestions, add fuzzy matches
    if len(suggestions) < 5:
        scored_matches = []
        max_distance = max(2, len(search_query) // 3)  # Allow more errors for suggestions

        for element in valid_list:
            if element not in suggestions:  # Don't duplicate existing suggestions
                distance = levenshtein_distance(search_lower, element.lower())
                if distance <= max_distance:
                    scored_matches.append((distance, element))

        # Sort by distance and add the best fuzzy matches
        scored_matches.sort(key=lambda x: x[0])
        for distance, element in scored_matches[:5 - len(suggestions)]:
            suggestions.append(element)

    message = ""
    if suggestions:
        guesses_str = ', '.join(suggestions[:5])  # Limit to 5 suggestions
        message = (
            f"Restart search with valid inputs, here are suggestions: {guesses_str}"
        )

    return message
# Retrieve relevant long-term memory notes by semantic search
def remember_memories(obj, projected_states):
    query = (obj or {}).get('query', '').strip()
    top_k = (obj or {}).get('top_k', 5)
    if not query:
        return "Please provide a 'query' string to search memories."

    try:
        k = int(top_k)
    except Exception:
        k = 5
    k = max(1, min(k, 20))

    # Create embedding for the query and search the vector store
    if not embedding_model:
        log('warn', 'Embeddings model not configured, cannot search memories.')
        return 'Unable to search memories, please configure the embedding model.'

    (model_name, embedding) = embedding_model.create_embedding(query)

    results = event_manager.long_term_memory.search(query, model_name, embedding, n=k)

    if not results:
        return f"No relevant memories found for '{query}'."

    formatted = []
    for result in results:
        time_until: float = result["metadata"].get('time_until', 0.0)
        time_since: float = result["metadata"].get('time_since', 0.0)
        item = {
            'score': round(result["score"], 3),
            'summary': result["content"],
            'time_until': datetime.datetime.fromtimestamp(time_until).strftime('%Y-%m-%d %H:%M:%S') if time_until else 'Unknown',
            'time_since': datetime.datetime.fromtimestamp(time_since).strftime('%Y-%m-%d %H:%M:%S') if time_since else 'Unknown',
        }
        formatted.append(item)

    yaml_output = yaml.dump(formatted, default_flow_style=False, sort_keys=False)
    return f"Top {len(formatted)} memory matches for '{query}':\n\n```yaml\n{yaml_output}\n```"



# Helper function
def find_best_match(search_term, known_list):
    search_lower = search_term.lower()

    # First try exact match
    for item in known_list:
        if item.lower() == search_lower:
            return item

    # Then try fuzzy matching
    best_match = None
    best_distance = float('inf')
    max_distance = max(1, len(search_term) // 3)  # Allow 1 error per 3 characters

    for item in known_list:
        distance = levenshtein_distance(search_lower, item.lower())
        if distance <= max_distance and distance < best_distance:
            best_distance = distance
            best_match = item

    return best_match

# Normalize requested result size with sane bounds for Spansh queries
def ensure_result_size(obj):
    default_size = 3
    try:
        size = int(obj.get("size", default_size))
    except Exception:
        size = default_size
    return max(1, min(25, size))

# Prepare a request for the spansh station finder
def prepare_station_request(obj, projected_states):# Helper function for fuzzy matching
    log('debug', 'Station Finder Request', obj)
    size = ensure_result_size(obj)

    station_types = list(known_station_types)
    if obj.get("include_player_fleetcarrier"):
        station_types.append("Drake-Class Carrier")

    filters = {
        "type": {
            "value": station_types
        },
        "distance": {
            "min": "0",
            "max": str(obj.get("distance", 50000))
        }
    }
    # Add optional filters if they exist
    ship_info = get_state_dict(projected_states, 'ShipInfo')
    requires_large_pad = ship_info.get('LandingPadSize') == 'L'
    if requires_large_pad:
        filters["has_large_pad"] = {"value": True}
    if "material_trader" in obj and obj["material_trader"]:
        filters["material_trader"] = {"value": obj["material_trader"]}
    if "technology_broker" in obj and obj["technology_broker"]:
        filters["technology_broker"] = {"value": obj["technology_broker"]}
    if "commodities" in obj and obj["commodities"]:
        market_filters = []
        for market_item in obj["commodities"]:
            # Find matching commodity name using fuzzy matching
            matching_commodity = find_best_match(market_item["name"], known_commodities)
            if not matching_commodity:
                raise Exception(
                    f"Invalid commodity name: {market_item['name']}. {educated_guesses_message(market_item['name'], known_commodities)}")
            market_item["name"] = matching_commodity
            market_filter = {
                "name": market_item["name"]
            }
            if market_item["transaction"] == "Buy":
                market_filter["supply"] = {
                    "value": [
                        str(market_item.get('amount', 10)),
                        "999999999"
                    ],
                    "comparison": "<=>"
                }
            elif market_item["transaction"] == "Sell":
                market_filter["demand"] = {
                    "value": [
                        str(market_item.get('amount', 10)),
                        "999999999"
                    ],
                    "comparison": "<=>"
                }
            market_filters.append(market_filter)
        filters["market"] = market_filters
    if "modules" in obj:
        modules_filter = {}
        for module in obj["modules"]:
            # Find matching module name using exact matching only
            module_name_lower = module["name"].lower()
            matching_module = next((m for m in known_modules if m.lower() == module_name_lower), None)
            if not matching_module:
                raise Exception(
                    f"Invalid module name: {module['name']}. {educated_guesses_message(module['name'], known_modules)}")
            module["name"] = matching_module
        filters["modules"] = obj["modules"]
    if "ships" in obj:
        for ship in obj["ships"]:
            # Find matching ship name using fuzzy matching
            matching_ship = find_best_match(ship["name"], known_ships)
            if not matching_ship:
                raise Exception(
                    f"Invalid ship name: {ship['name']}. {educated_guesses_message(ship['name'], known_ships)}")
            ship["name"] = matching_ship
        filters["ships"] = {"value": obj["ships"]}
    if "services" in obj:
        for service in obj["services"]:
            # Find matching service name using fuzzy matching
            matching_service = find_best_match(service["name"], known_services)
            if not matching_service:
                raise Exception(
                    f"Invalid service name: {service['name']}. {educated_guesses_message(service['name'], known_services)}")
            service["name"] = matching_service
        filters["services"] = {"value": obj["services"]}
    if "name" in obj and obj["name"]:
        filters["name"] = {
            "value": obj["name"]
        }

    sort_preference = obj.get("sort_by", "bestprice")
    sort_object = {"distance": {"direction": "asc"}}
    if sort_preference == "bestprice" and filters.get("market") and len(filters["market"]) > 0:
        if filters.get("market")[0].get("demand"):
            sort_object = {"market_sell_price": [{"name": filters["market"][0]["name"], "direction": "desc"}]}
        elif filters["market"][0].get("supply"):
            sort_object = {"market_buy_price": [{"name": filters["market"][0]["name"], "direction": "asc"}]}

    # Build the request body
    request_body = {
        "filters": filters,
        "sort": [
            sort_object
        ],
        "size": size,
        "page": 0
    }

    reference_route = obj.get("reference_route")
    if reference_route:
        source = reference_route.get("source")
        destination = reference_route.get("destination")
        if not source or not destination:
            raise Exception("reference_route must include both 'source' and 'destination'.")
        request_body["reference_route"] = {
            "source": source,
            "destination": destination
        }
    else:
        location = get_state_dict(projected_states, 'Location')
        request_body["reference_system"] = obj.get("reference_system", location.get("StarSystem", "Sol"))

    return request_body


# filter a spansh station result set for only relevant information
def filter_station_response(request, response, unfiltered_results=None):
    unfiltered_results = unfiltered_results or {}
    unfiltered_markets = unfiltered_results.get("commodities", False)
    unfiltered_modules = unfiltered_results.get("modules", False)
    unfiltered_ships = unfiltered_results.get("ships", False)
    # Extract requested commodities and modules
    commodities_requested = {item["name"] for item in request["filters"].get("market", {})}
    modules_requested = {item["name"] for item in request["filters"].get("modules", {})}
    ships_requested = {item["name"] for item in request["filters"].get("ships", {}).get("value", [])}
    services_requested = {item["name"] for item in request["filters"].get("services", {}).get("value", [])}

    log('debug', 'modules_requested', modules_requested)

    filtered_results = []

    for result in response["results"]:
        filtered_result = {
            "name": result["name"],
            "system": result["system_name"],
            "distance": result["distance"],
            "orbit": result["distance_to_arrival"],
            "is_planetary": result["is_planetary"]
        }

        if "market" in result:
            if unfiltered_markets:
                filtered_result["market"] = result["market"]
            else:
                filtered_market = [
                    commodity for commodity in result["market"]
                    if commodity["commodity"] in commodities_requested
                ]
                filtered_result["market"] = filtered_market

        if "modules" in result:
            if unfiltered_modules:
                filtered_result["modules"] = result["modules"]
            else:
                filtered_modules = []
                for module in result["modules"]:
                    for requested_module in modules_requested:
                        if requested_module.lower() in module["name"].lower():
                            filtered_modules.append(
                                {"name": module["name"], "class": module["class"], "rating": module["rating"],
                                 "price": module["price"]})

                if filtered_modules:
                    filtered_result["modules"] = filtered_modules

        if "ships" in result:
            if unfiltered_ships:
                filtered_result["ships"] = result["ships"]
            else:
                filtered_ships = []
                for ship in result["ships"]:
                    for requested_ship in ships_requested:
                        if requested_ship.lower() in ship["name"].lower():
                            filtered_ships.append(ship)

                if filtered_ships:
                    filtered_result["ships"] = filtered_ships

        # if "services" in result:
        #     if unfiltered_services:
        filtered_result["services"] = result["services"]
        # else:
        #     filtered_services = []
        #     for service in result["services"]:
        #         for requested_service in services_requested:
        #             if requested_service.lower() in service["name"].lower():
        #                 filtered_services.append(service)
        #
        #     if filtered_services:
        #         filtered_result["services"] = filtered_services

        filtered_results.append(filtered_result)

    return {
        "amount_total": response["count"],
        "amount_displayed": min(response["count"], response["size"]),
        "results": filtered_results
    }


def station_finder(obj, projected_states):
    # Initialize the filters
    request_body = prepare_station_request(obj, projected_states)
    log('debug', 'station search input', request_body)

    url = "https://spansh.co.uk/api/stations/search"
    try:
        response = requests.post(url, json=request_body, timeout=15)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        data = response.json()

        filtered_data = filter_station_response(request_body, data, obj.get("unfiltered_results"))

        return f'Here is a list of stations: {json.dumps(filtered_data)}'
    except Exception as e:
        log('error', e, traceback.format_exc())
        return 'An error has occurred. The station finder seems currently not available.'


def prepare_system_request(obj, projected_states):# Helper function for fuzzy matching
    
    log('debug', 'System Finder Request', obj)
    size = ensure_result_size(obj)
    filters = {
        "distance": {
            "min": "0",
            "max": str(obj.get("distance", 50000))
        }
    }

    # Add optional filters if they exist
    if "allegiance" in obj and obj["allegiance"]:
        validated_allegiances = []
        for allegiance in obj["allegiance"]:
            # Find matching allegiance using fuzzy matching
            matching_allegiance = find_best_match(allegiance, known_allegiances)
            if not matching_allegiance:
                raise Exception(
                    f"Invalid allegiance: {allegiance}. {educated_guesses_message(allegiance, known_allegiances)}")
            validated_allegiances.append(matching_allegiance)
        filters["allegiance"] = {"value": validated_allegiances}

    if "state" in obj and obj["state"]:
        validated_states = []
        for state in obj["state"]:
            # Find matching state using fuzzy matching
            matching_state = find_best_match(state, known_states)
            if not matching_state:
                raise Exception(
                    f"Invalid state: {state}. {educated_guesses_message(state, known_states)}")
            validated_states.append(matching_state)
        filters["state"] = {"value": validated_states}

    if "government" in obj and obj["government"]:
        validated_governments = []
        for government in obj["government"]:
            # Find matching government using fuzzy matching
            matching_government = find_best_match(government, known_governments)
            if not matching_government:
                raise Exception(
                    f"Invalid government: {government}. {educated_guesses_message(government, known_governments)}")
            validated_governments.append(matching_government)
        filters["government"] = {"value": validated_governments}

    if "power" in obj and obj["power"]:
        validated_powers = []
        for power in obj["power"]:
            # Find matching power using fuzzy matching
            matching_power = find_best_match(power, known_powers)
            if not matching_power:
                raise Exception(
                    f"Invalid power: {power}. {educated_guesses_message(power, known_powers)}")
            validated_powers.append(matching_power)
        filters["controlling_power"] = {"value": validated_powers}

    if "primary_economy" in obj and obj["primary_economy"]:
        validated_economies = []
        for economy in obj["primary_economy"]:
            # Find matching economy using fuzzy matching
            matching_economy = find_best_match(economy, known_economies)
            if not matching_economy:
                raise Exception(
                    f"Invalid primary economy: {economy}. {educated_guesses_message(economy, known_economies)}")
            validated_economies.append(matching_economy)
        filters["primary_economy"] = {"value": validated_economies}

    if "security" in obj and obj["security"]:
        validated_security = []
        for security_level in obj["security"]:
            # Find matching security level using fuzzy matching
            matching_security = find_best_match(security_level, known_security_levels)
            if not matching_security:
                raise Exception(
                    f"Invalid security level: {security_level}. {educated_guesses_message(security_level, known_security_levels)}")
            validated_security.append(matching_security)
        filters["security"] = {"value": validated_security}

    if "thargoid_war_state" in obj and obj["thargoid_war_state"]:
        validated_thargoid_states = []
        for thargoid_war_state in obj["thargoid_war_state"]:
            # Find matching thargoid war state using fuzzy matching
            matching_state = find_best_match(thargoid_war_state, known_thargoid_war_states)
            if not matching_state:
                raise Exception(
                    f"Invalid thargoid war state: {thargoid_war_state}. {educated_guesses_message(thargoid_war_state, known_thargoid_war_states)}")
            validated_thargoid_states.append(matching_state)
        filters["thargoid_war_state"] = {"value": validated_thargoid_states}

    if "population" in obj and obj["population"]:
        comparison = obj["population"].get("comparison", ">")
        value = obj["population"].get("value", 0)

        lower_bound = value if comparison == ">" else 0
        upper_bound = value if comparison == "<" else 100000000000

        filters["population"] = {
            "comparison": "<=>",
            "value": [lower_bound, upper_bound]
        }

    if "name" in obj and obj["name"]:
        filters["name"] = {
            "value": obj["name"]
        }

    # Determine sort order based on sort_by parameter
    sort_preference = obj.get("sort_by", "distance")
    if sort_preference == "population":
        sort_object = {"population": {"direction": "desc"}}
    else:
        sort_object = {"distance": {"direction": "asc"}}

    # Build the request body
    request_body = {
        "filters": filters,
        "sort": [
            sort_object
        ],
        "size": size,
        "page": 0
    }

    reference_route = obj.get("reference_route")
    if reference_route:
        source = reference_route.get("source")
        destination = reference_route.get("destination")
        if not source or not destination:
            raise Exception("reference_route must include both 'source' and 'destination'.")
        request_body["reference_route"] = {
            "source": source,
            "destination": destination
        }
    else:
        location = get_state_dict(projected_states, "Location")
        request_body["reference_system"] = obj.get("reference_system",
                                                   location.get("StarSystem", "Sol"))

    return request_body


# Function to filter and format the system response
def filter_system_response(request, response):
    filtered_results = []

    # Check which filters are in the request and adjust the response accordingly
    request_filters = request.get("filters", {})

    for system in response.get("results", []):
        filtered_system = {}

        # if "name" in system and system["name"]:
        filtered_system["name"] = system.get("name")
        filtered_system["allegiance"] = system.get("allegiance", "Independent")
        if "controlling_minor_faction" in system and system["controlling_minor_faction"]:
            filtered_system["minor_faction"] = system.get("controlling_minor_faction", )
        if "controlling_minor_faction_state" in system and system["controlling_minor_faction_state"]:
            filtered_system["minor_faction_state"] = system.get("controlling_minor_faction_state")
        # Only add power if it was requested
        if "power" in request_filters and "power" in system and system["power"]:
            filtered_system["power"] = system.get("power")
            filtered_system["power_state"] = system.get("power_state", "None")
        filtered_system["distance"] = system.get("distance")
        filtered_system["body_count"] = system.get("body_count", 0)
        filtered_system["station_count"] = len(system.get("stations", []))
        filtered_system["population"] = system.get("population", 0)
        # Only add government if it was requested
        if "government" in request_filters and "government" in system and system["government"]:
            filtered_system["government"] = system.get("government")

        filtered_system["primary_economy"] = system.get("primary_economy", "None")
        filtered_system["security"] = system.get("security", "Anarchy")

        # Only add thargoid war state if it was requested
        if "thargoid_war_state" in request_filters and "thargoid_war_state" in system and system["thargoid_war_state"]:
            filtered_system["thargoid_war_state"] = system.get("thargoid_war_state")

        # Only add if needs_permit is true
        if "needs_permit" in request_filters and "needs_permit" in system and system["needs_permit"]:
            filtered_system["needs_permit"] = system.get("needs_permit")

        # Add filtered system to the list
        filtered_results.append(filtered_system)

    # Construct and return the filtered response
    return {
        "amount_total": response["count"],
        "amount_displayed": min(response["count"], response["size"]),
        "results": filtered_results,
    }


# System finder function that sends the request to the Spansh API
def system_finder(obj, projected_states):
    # Build the request body
    request_body = prepare_system_request(obj, projected_states)

    url = "https://spansh.co.uk/api/systems/search"

    try:
        response = requests.post(url, json=request_body, timeout=15)
        response.raise_for_status()

        data = response.json()
        # Filter the response
        filtered_data = filter_system_response(request_body, data)

        return f'Here is a list of systems: {json.dumps(filtered_data)}'

    except Exception as e:
        log('error', e, traceback.format_exc())
        return 'An error occurred. The system finder seems to be currently unavailable.'


def prepare_body_request(obj, projected_states):
    size = ensure_result_size(obj)
    filters = {
        "distance": {
            "min": "0",
            "max": str(obj.get("distance", 50000))
        }
    }

    # Add optional filters if they exist
    if "subtype" in obj and obj["subtype"]:
        validated_subtypes = []
        for subtype in obj["subtype"]:
            # Find matching subtype using fuzzy matching
            matching_subtype = find_best_match(subtype, known_subtypes)
            if not matching_subtype:
                raise Exception(
                    f"Invalid celestial body subtype: {subtype}. {educated_guesses_message(subtype, known_subtypes)}")
            validated_subtypes.append(matching_subtype)
        filters["subtype"] = {"value": validated_subtypes}

    if "landmark_subtype" in obj and obj["landmark_subtype"]:
        validated_landmarks = []
        for landmark_subtype in obj["landmark_subtype"]:
            # Find matching landmark subtype using fuzzy matching
            matching_landmark = find_best_match(landmark_subtype, known_landmarks)
            if not matching_landmark:
                raise Exception(
                    f"Invalid Landmark Subtype: {landmark_subtype}. {educated_guesses_message(landmark_subtype, known_landmarks)}")
            validated_landmarks.append(matching_landmark)

        filters["landmark_subtype"] = {"value": validated_landmarks}

    if "name" in obj and obj["name"]:
        filters["name"] = {
            "value": obj["name"]
        }

    # Add ring filters if rings parameter is provided
    if "rings" in obj and obj["rings"]:
        rings_config = obj["rings"]
        if "material" in rings_config and "hotspots" in rings_config:
            # Validate and auto-correct mining material using fuzzy matching
            material = rings_config["material"]
            matching_material = find_best_match(material, known_mining_commodities)
            if not matching_material:
                raise Exception(
                    f"Invalid mining material: {material}. {educated_guesses_message(material, known_mining_commodities)}")
            
            filters["reserve_level"] = {
                "value": [
                    "Pristine"
                ]
            }
            filters["ring_signals"] = [
                {
                    "name": matching_material,
                    "value": [
                        rings_config["hotspots"],
                        99
                    ],
                    "comparison": "<=>"
                }
            ]

    if "signals" in obj and obj["signals"]:
        signal_filters = []
        for signal in obj["signals"]:
            signal_filters.append({
                "comparison": "<=>",
                "count": [
                    1,
                    999
                ],
                "name": signal.capitalize()
            })
        filters["signals"] = signal_filters

    # Build the request body
    request_body = {
        "filters": filters,
        "sort": [
            {
                "distance": {
                    "direction": "asc"
                }
            }
        ],
        "size": size,
        "page": 0
    }

    reference_route = obj.get("reference_route")
    if reference_route:
        source = reference_route.get("source")
        destination = reference_route.get("destination")
        if not source or not destination:
            raise Exception("reference_route must include both 'source' and 'destination'.")
        request_body["reference_route"] = {
            "source": source,
            "destination": destination
        }
    else:
        location = get_state_dict(projected_states, 'Location')
        request_body["reference_system"] = obj.get("reference_system",
                                                   location.get("StarSystem", "Sol"))

    return request_body


# Function to filter and format the system response
def filter_body_response(request, response):
    filtered_results = []

    # Check which filters are in the request and adjust the response accordingly
    request_filters = request.get("filters", {})

    for body in response.get("results", []):
        filtered_body = {}

        # if "name" in system and system["name"]:
        filtered_body["name"] = body.get("name")
        filtered_body["subtype"] = body.get("subtype")
        filtered_body["system_name"] = body.get("system_name")
        # landmark_subtype
        if "landmark_subtype" in request_filters:
            if "landmark_subtype" in body and body["landmarks"]:
                filtered_landmarks = [
                    {
                        "latitude": landmark["latitude"],
                        "longitude": landmark["longitude"],
                        "subtype": landmark["subtype"],
                        "type": landmark["type"],
                        "variant": landmark["variant"]
                    }
                    for landmark in body.get("landmarks", [])
                    if landmark["subtype"] in request_filters["landmark_subtype"]
                ]

                filtered_body["landmarks"] = filtered_landmarks

        # rings information
        if "ring_signals" in request_filters:
            if "rings" in body and body["rings"]:
                ring_signals = []
                for ring in body["rings"]:
                    if "signals" in ring and ring["signals"]:
                        ring_signals.extend(ring["signals"])
                
                if ring_signals:
                    filtered_body["rings"] = {"signals": ring_signals}

        # signals information
        if "signals" in request_filters:
            if "signals" in body and body["signals"]:
                filtered_body["signals"] = body.get("signals")

        # Add filtered system to the list
        filtered_results.append(filtered_body)

    # Construct and return the filtered response
    return {
        "amount_total": response["count"],
        "amount_displayed": min(response["count"], response["size"]),
        "results": filtered_results,
    }


# Body finder function that sends the request to the Spansh API
def body_finder(obj, projected_states):
    # Build the request body
    request_body = prepare_body_request(obj, projected_states)

    url = "https://spansh.co.uk/api/bodies/search"

    try:
        response = requests.post(url, json=request_body, timeout=15)
        response.raise_for_status()

        data = response.json()
        # Filter the response
        filtered_data = filter_body_response(request_body, data)

        return f'Here is a list of celestial bodies: {json.dumps(filtered_data)}'

    except Exception as e:
        log('error', f"Error: {e}")
        return 'An error occurred. The system finder seems to be currently unavailable.'


def register_web_actions(actionManager: ActionManager, eventManager: EventManager, 
                        promptGenerator: PromptGenerator,
                         llmModel: LLMModel | None,
                         embeddingModel: EmbeddingModel | None,
                         agentMaxTries: int = 7):
    global event_manager, llm_model, embedding_model, prompt_generator, agent_max_tries
    event_manager = eventManager
    prompt_generator = promptGenerator
    llm_model = cast(LLMModel, llmModel)
    embedding_model = cast(EmbeddingModel, embeddingModel)
    agent_max_tries = agentMaxTries

    actionManager.registerAction(
        'web_search_agent',
        "Request a detailed report about information from the game, including news, system, station, body, engineers, blueprint, material lookups, owned ships and modules. Use this tool whenever the user asks about anything related to external or global information.",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be as specific as possible. E.g., 'buy 10 Fer-de-Lance and Steel for the construction project near Sol' or 'engineer requirements to increase my FSD range'. The query can reference player specific details like 'active construction' or 'active mission'. Multiple questions may be asked in a single query."
                },
            },
            "required": ["query"]
        },
        web_search,
        'web',
        input_template=lambda i, s: f"Searching: {i.get('query', '')}",
    )

    # Retrieve memories via semantic search

    if embeddingModel:
        actionManager.registerAction(
            'remember_memories',
        "Retrieve relevant long-term memory notes from logbook by semantic search. Use this to remember and recall older logbook entries and memories than currently known to answer questions concerning the past.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Semantic search query for memory retrieval"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of memory notes to return (1-20)",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 5
                    }
                },
                "required": ["query"]
            },
            input_template=lambda i, s: f"""Retrieving memories
                    about '{i.get('query', '')}'
                    top {i.get('top_k', 5)}
                """,
            method=remember_memories,
            action_type='web'
        )

