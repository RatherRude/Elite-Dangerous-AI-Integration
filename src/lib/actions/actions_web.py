import json
import traceback
import math
import yaml

import openai
import requests


from .data import *
from ..Logger import log
from ..EDKeys import EDKeys
from ..EventManager import EventManager
from ..ActionManager import ActionManager

llm_client: openai.OpenAI = None
llm_model_name: str = None
event_manager: EventManager = None


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

            completion = llm_client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com/RatherRude/Elite-Dangerous-AI-Integration",
                    "X-Title": "Elite Dangerous AI Integration",
                },
                model=llm_model_name,
                messages=[{
                    "role": "user",
                    "content": f"Analyze the following list of news articles, either answer the given inquiry or create a short summary that includes all named entities: {articles}\nInquiry: {obj.get('query')}"
                }],
            )

            return completion.choices[0].message.content

        return "News feed currently unavailable"

    except:
        return "News feed currently unavailable"



def blueprint_finder(obj, projected_states):
    import yaml
    # Get current location coordinates for distance calculation
    current_location = projected_states.get('Location', {})
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
    engineer_progress = projected_states.get('EngineerProgress')
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
    materials_data = projected_states.get('Materials', {})
    shiplocker_data = projected_states.get('ShipLocker', {})

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
    current_location = projected_states.get('Location', {})
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

    engineer_progress = projected_states.get('EngineerProgress')

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
            rank = game_data.get('Rank')
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
    materials_data = projected_states.get('Materials', {})
    shiplocker_data = projected_states.get('ShipLocker', {})

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

        if result.get('tradeable_higher_grades'):
            trading_lines = ["Tradeable, higher grades:"]
            for higher_mat in result['tradeable_higher_grades']:
                if higher_mat['count'] > 0:
                    trading_lines.append(f"- {higher_mat['count']}x {higher_mat['name']} (Grade {higher_mat['grade']})")

            if source_info:
                trading_lines.append(f"Source: {source_info}")

            if len(trading_lines) > 1:  # Only add if there are actual tradeable materials
                formatted_results.append(material_line)
                formatted_results.extend(trading_lines)
            else:
                formatted_results.append(material_line)
        else:
            # No higher grades available, but still show source if available
            formatted_results.append(material_line)
            if source_info:
                formatted_results.append(f"Source: {source_info}")

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

# Prepare a request for the spansh station finder
def prepare_station_request(obj, projected_states):# Helper function for fuzzy matching
    
    log('debug', 'Station Finder Request', obj)
    filters = {
        "type": {
            "value": known_station_types
        },
        "distance": {
            "min": "0",
            "max": str(obj.get("distance", 50000))
        }
    }
    # Add optional filters if they exist
    requires_large_pad = projected_states.get('ShipInfo').get('LandingPadSize') == 'L'
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

    sort_object = {"distance": {"direction": "asc"}}
    if filters.get("market") and len(filters["market"]) > 0:
        if filters.get("market")[0].get("demand"):
            sort_object = {"market_sell_price": [{"name": filters["market"][0]["name"], "direction": "desc"}]}
        elif filters["market"][0].get("demand"):
            sort_object = {"market_buy_price": [{"name": filters["market"][0]["name"], "direction": "asc"}]}

    # Build the request body
    request_body = {
        "filters": filters,
        "sort": [
            sort_object
        ],
        "size": 3,
        "page": 0,
        "reference_system": obj.get("reference_system", "Sol")
    }
    return request_body


# filter a spansh station result set for only relevant information
def filter_station_response(request, response):
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
            filtered_market = [
                commodity for commodity in result["market"]
                if commodity["commodity"] in commodities_requested
            ]
            filtered_result["market"] = filtered_market

        if "modules" in result:
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
            filtered_ships = []
            for ship in result["ships"]:
                for requested_ship in ships_requested:
                    if requested_ship.lower() in ship["name"].lower():
                        filtered_ships.append(ship)

            if filtered_ships:
                filtered_result["ships"] = filtered_ships

        if "services" in result:
            filtered_services = []
            for service in result["services"]:
                for requested_service in services_requested:
                    if requested_service.lower() in service["name"].lower():
                        filtered_services.append(service)

            if filtered_services:
                filtered_result["services"] = filtered_services

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

        filtered_data = filter_station_response(request_body, data)
        # tech broker, material trader

        return f'Here is a list of stations: {json.dumps(filtered_data)}'
    except Exception as e:
        log('error', e, traceback.format_exc())
        return 'An error has occurred. The station finder seems currently not available.'


def prepare_system_request(obj, projected_states):# Helper function for fuzzy matching
    
    log('debug', 'System Finder Request', obj)
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
        "size": 3,
        "page": 0,
        "reference_system": obj.get("reference_system", "Sol")
    }

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
        "size": 3,
        "page": 0,
        "reference_system": obj.get("reference_system", "Sol")
    }

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
                         llmClient: openai.OpenAI, llmModelName: str, edKeys: EDKeys):
    global event_manager, llm_client, llm_model_name, keys
    keys = edKeys
    event_manager = eventManager
    llm_client = llmClient
    llm_model_name = llmModelName

    # Register actions - Web Tools
    actionManager.registerAction(
        'getGalnetNews',
        "Retrieve current interstellar news from Galnet",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Inquiry you are trying to answer. Example: 'What happened to the thargoids recently?'"
                },
            },
            "required": ["query"]
        },
        get_galnet_news,
        'web',
        input_template=lambda i, s: f"""Fetching GalNet articles
            {'regarding: ' + i.get('query', '') if i.get('query', '') else ''}
        """,
    )

    # if ARC:
    # Register AI action for system finder
    actionManager.registerAction(
        'system_finder',
        "Find a star system based on allegiance, government, state, power, primary economy, and more. Ask for unknown values and ensure they are filled out.",
        input_template=lambda i, s: f"""Searching for systems
            {'called ' + i.get('name', '') if i.get('name', '') else ''}
            {'with allegiance to ' + ' and '.join(i.get('allegiance', [])) if i.get('allegiance', []) else ''}
            {'in state ' + ' and '.join(i.get('state', [])) if i.get('state', []) else ''}
            {'with government type ' + ' and '.join(i.get('government', [])) if i.get('government', []) else ''}
            {'controlled by ' + ' and '.join(i.get('power', [])) if i.get('power', []) else ''}
            {'with primary economy type ' + ' and '.join(i.get('primary_economy', [])) if i.get('primary_economy', []) else ''}
            {'with security level ' + ' and '.join(i.get('security', [])) if i.get('security', []) else ''}
            {'in Thargoid war state ' + ' and '.join(i.get('thargoid_war_state', [])) if i.get('thargoid_war_state', []) else ''}
            {'with a population over ' + i.get('population', {}).get('comparison', '') + ' ' + str(i.get('population', {}).get('value', '')) if i.get('population', {}) else ''}
            near {i.get('reference_system', 'Sol')}.
        """,
        parameters={
            "type": "object",
            "properties": {
                "reference_system": {
                    "type": "string",
                    "description": "Name of the current system. Example: 'Sol'"
                },
                "name": {
                    "type": "string",
                    "description": "Required string in system name"
                },
                "distance": {
                    "type": "number",
                    "description": "The maximum distance to search",
                    "example": 50000.0
                },
                "allegiance": {
                    "type": "array",
                    "description": "System allegiance to filter by",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Alliance",
                            "Empire",
                            "Federation",
                            "Guardian",
                            "Independent",
                            "Pilots Federation",
                            "Player Pilots",
                            "Thargoid"
                        ]
                    }
                },
                "state": {
                    "type": "array",
                    "description": "System state to filter by",
                    "items": {
                        "type": "string",
                    }
                },
                "government": {
                    "type": "array",
                    "description": "System government type to filter by",
                    "items": {
                        "type": "string",
                    }
                },
                "power": {
                    "type": "array",
                    "description": "Powers controlling or exploiting the system",
                    "items": {
                        "type": "string",
                    }
                },
                "primary_economy": {
                    "type": "array",
                    "description": "Primary economy type of the system",
                    "items": {
                        "type": "string",
                    }
                },
                "security": {
                    "type": "array",
                    "description": "Security level of the system",
                    "items": {
                        "type": "string",
                    }
                },
                "thargoid_war_state": {
                    "type": "array",
                    "description": "System's state in the Thargoid War",
                    "items": {
                        "type": "string",
                    }
                },
                "population": {
                    "type": "object",
                    "description": "Population comparison and value",
                    "properties": {
                        "comparison": {
                            "type": "string",
                            "description": "Comparison type",
                            "enum": ["<", ">"]
                        },
                        "value": {
                            "type": "number",
                            "description": "Size to compare with",
                        }
                    }
                }
            },
            "required": ["reference_system"]
        },
        method=system_finder,
        action_type='web'
    )
    actionManager.registerAction(
        'station_finder',
        "Find a station for commodities, modules and ships. Ask for unknown values and make sure they are known.",
        input_template=lambda i, s: f"""Searching for stations
            {'called ' + i.get('name', '') if i.get('name', '') else ''}
            {'with large pad' if i.get('has_large_pad', False) else ''}
            {'with material traders for ' + ' and '.join(i.get('material_trader', [])) + ' Materials' if i.get('material_trader', []) else ''}
            {'with technology brokers for ' + ' and '.join(i.get('technology_broker', [])) + ' Technology' if i.get('technology_broker', []) else ''}
            {'selling a ' + ' and a '.join([f"{module['name']} module class {module.get('class', 'any')} {module.get('class', '')} " for module in i.get('modules', [])]) if i.get('modules', []) else ''}
            {'selling a ' + ' and a '.join([f"{ship['name']}" for ship in i.get('ships', [])]) if i.get('ships', []) else ''}
            {' and '.join([f"where we can {market.get('transaction')} {market.get('amount', 'some')} {market.get('name')}" for market in i.get('commodities', [])]) if len(i.get('commodities', [])) <= 3 else f'where we can trade {len(i.get("commodities", []))} commodities'}
            {'with a ' + ' and '.join([service['name'] for service in i.get('services', [])]) if i.get('services', []) else ''}
            near {i.get('reference_system', 'Sol')}
            {'within ' + str(i.get('distance', 50000)) + ' light years' if i.get('distance', 50000) else ''}.
        """,
        parameters={
            "type": "object",
            "properties": {
                "reference_system": {
                    "type": "string",
                    "description": "Name of the current system. Example: 'Sol'"
                },
                "name": {
                    "type": "string",
                    "description": "Required string in station name"
                },
                "distance": {
                    "type": "number",
                    "description": "The maximum distance to search",
                    "default": 50000.0
                },
                "material_trader": {
                    "type": "array",
                    "description": "Material traders to find",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Encoded",
                            "Manufactured",
                            "Raw"
                        ]
                    },
                    "minItems": 1,
                },
                "technology_broker": {
                    "type": "array",
                    "description": "Technology brokers to find",
                    "items": {
                        "type": "string",
                        "enum": [
                            "Guardian",
                            "Human"
                        ]
                    },
                    "minItems": 1,
                },
                "modules": {
                    "type": "array",
                    "description": "Outfitting modules to buy",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the module.",
                                "example": "Frame Shift Drive"
                            },
                            "class": {
                                "type": "array",
                                "description": "Classes of the modules.",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "0", "1", "2", "3", "4", "5", "6", "7", "8"
                                    ],
                                },
                                "minItems": 1,
                            },
                            "rating": {
                                "type": "array",
                                "description": "Ratings of the modules.",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "A", "B", "C", "D", "E", "F", "G", "H", "I"
                                    ]
                                },
                                "example": ["A", "B", "C", "D"],
                                "minItems": 1
                            }
                        },
                        "required": ["name"]
                    },
                    "minItems": 1,
                },
                "commodities": {
                    "type": "array",
                    "description": "Commodities to buy or sell at a station. This is not the station name and must map to a commodity name",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the commodity.",
                                "example": "Tritium"
                            },
                            "amount": {
                                "type": "integer",
                                "description": "Tons of cargo to sell or buy. Use maximum cargo capacity."
                            },
                            "transaction": {
                                "type": "string",
                                "description": "Type of transaction.",
                                "enum": [
                                    "Buy", "Sell"
                                ],
                            }
                        },
                        "required": ["name", "amount", "transaction"]
                    },
                    "minItems": 1,
                },
                "ships": {
                    "type": "array",
                    "description": "Ships to buy",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of ship",
                            }
                        },
                        "required": ["name"]
                    },
                    "minItems": 1,
                },
                "services": {
                    "type": "array",
                    "description": "Services to use",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name services",
                                "enum": [
                                    "Black Market",
                                    "Interstellar Factors Contact"
                                ]
                            }
                        },
                        "required": ["name"]
                    },
                    "minItems": 1,
                }
            },
            "required": [
                "reference_system"
            ]
        },
        method=station_finder,
        action_type='web'
    )
    actionManager.registerAction(
        'body_finder',
        "Find a planet or star of a certain type or with a landmark. Ask for unknown values and make sure they are known.",
        input_template=lambda i, s: f"""Searching for bodies 
            {'called ' + i.get('name', '') if i.get('name', '') else ''}
            {'of subtype ' + ', '.join(i.get('subtype', [])) if i.get('subtype', []) else ''}
            {'with a landmark of subtype ' + ', '.join(i.get('landmark_subtype', [])) if i.get('landmark_subtype', []) else ''}
            {'with rings containing ' + str(i.get('rings', {}).get('hotspots', '')) + '+ hotspots of ' + i.get('rings', {}).get('material', '') if i.get('rings') else ''}
            near {i.get('reference_system', 'Sol')}
            {'within ' + str(i.get('distance', 50000)) + ' light years.' if i.get('distance', 50000) else ''}.
        """,
        parameters={
            "type": "object",
            "properties": {
                "reference_system": {
                    "type": "string",
                    "description": "Name of the current system. Example: 'Sol'"
                },
                "name": {
                    "type": "string",
                    "description": "Required string in station name"
                },
                "subtype": {
                    "type": "array",
                    "description": "Subtype of celestial body",
                    "items": {
                        "type": "string",
                    }
                },
                "landmark_subtype": {
                    "type": "array",
                    "description": "Landmark subtype on celestial body",
                    "items": {
                        "type": "string",
                    }
                },
                "distance": {
                    "type": "number",
                    "description": "Maximum distance to search",
                    "example": 50000.0
                },
                "rings": {
                    "type": "object",
                    "description": "Ring search criteria",
                    "properties": {
                        "material": {
                            "type": "string",
                            "description": "Material to look for in rings"
                        },
                        "hotspots": {
                            "type": "integer",
                            "description": "Minimum number of hotspots required",
                            "minimum": 1
                        }
                    },
                    "required": ["material", "hotspots"]
                },
            },
            "required": [
                "reference_system"
            ]
        },
        method=body_finder,
        action_type='web'
    )

    actionManager.registerAction(
        'engineer_finder', "Get information about engineers' location, standing and modifications.", {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Filter engineers by name"
                },
                "system": {
                    "type": "string",
                    "description": "Filter engineers by system/location"
                },
                "modifications": {
                    "type": "string",
                    "description": "Filter engineers by what they modify"
                },
                "progress": {
                    "type": "string",
                    "enum": ["Unknown", "Known", "Invited", "Unlocked"],
                    "description": "Filter engineers by their current progress status"
                }
            }
        },
        engineer_finder,
        'web'
    )

    # Register AI action for blueprint finder
    actionManager.registerAction(
        'blueprint_finder', "Find engineer blueprints based on search criteria. Returns material costs with grade calculations.", {
            "type": "object",
            "properties": {
                "modifications": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of modification names to search for - supports fuzzy search."
                },
                "engineer": {
                    "type": "string",
                    "description": "Engineer name to search for"
                },
                "module": {
                    "type": "string",
                    "description": "Module/hardware name to search for"
                },
                "grade": {
                    "type": "integer",
                    "description": "Grade to search for"
                }
            }
        },
        blueprint_finder,
        'web'
    )

    actionManager.registerAction(
        'material_finder',
        "Find and search a list of materials for both ship and suit engineering from my inventory and where to source them from.",
        {
            "type": "object",
            "properties": {
                "name": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Array of material names to search for - supports fuzzy search."
                },
                "grade": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Filter ship materials by grade (1-5). Suit materials don't have grades."
                },
                "type": {
                    "type": "string",
                    "enum": ["raw", "manufactured", "encoded", "items", "components", "data", "consumables", "ship", "suit"],
                    "description": "Filter by material type. Ship types: raw, manufactured, encoded. Suit types: items, components, data, consumables. Category filters: ship, suit."
                }
            }
        },
        material_finder,
        'web'
    )

if __name__ == "__main__":
    req = prepare_station_request({'reference_system': 'Coelho', 'market': [{'name': 'Gold', 'amount': 8, 'transaction': 'Buy'}]})
    print(json.dumps(req))
