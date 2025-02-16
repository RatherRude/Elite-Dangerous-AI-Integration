import os
import json
from collections import defaultdict
from types import NoneType
from typing import TypedDict


def process(data, stats):
    """
    Collect events by type for later model derivation.
    """
    event_type = data.get("event", "unknown")
    stats[event_type].append(data)


def derive_typeddict(name, data_list) -> tuple[str, str]:
    """
    Generate a TypedDict model from a list of dictionaries.
    """
    if not data_list:
        return 'Any', ''
    types = list(set([type(e) for e in data_list]))
    
    if None in data_list:
        t, model = derive_typeddict(name, [e for e in data_list if e is not None])
        return 'NotRequired[' + t + ']', model
    
    if len(types) > 1:
        return 'Any', ''
    
    if types[0] in (int, float, str, bool):
        if len(set(data_list)) == 1 and types[0] in (int, str):
            return 'Literal[' + json.dumps(data_list[0]) + ']', ''
        return types[0].__name__, ''
    
    if types[0] == list:
        elements = []
        for e in data_list:
            elements.extend(e)
        t, model = derive_typeddict(name+'Item', elements)
        return 'list[' + t + ']', model
    
    if types[0] == dict:
        keys = set()
        for e in data_list:
            keys.update(list(e.keys()))
        
        model_def = ''
            
        fields = {}
        for key in keys:
            values = [e.get(key, None) for e in data_list]
            t, model = derive_typeddict(name+key.capitalize(), values)
            model_def += model
            fields[key] = t

        model_def += f"class {name}(TypedDict):\n"
        for field, field_type in fields.items():
            model_def += f"    {field}: {field_type}\n"
        return (name, model_def)
    
    return 'Any', ''


def process_journal_files(directory):
    """
    Walks through all Journal.* files in the given directory,
    reads them line by line, parses them as JSON, and calls process().
    """
    stats = defaultdict(list)

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".log") or file.endswith(".json"):
                file_path = os.path.join(root, file)
                print(f"Processing file: {file_path}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            json_data = json.loads(line.strip())
                            process(json_data, stats)
                        except json.JSONDecodeError as e:
                            print(f"Skipping invalid JSON in {file_path}: {e}")

    # Sort event types by number of occurrences
    sorted_stats = sorted(stats.items(), key=lambda x: len(json.dumps(x[1])), reverse=True)

    output_file = os.path.join(os.path.dirname(__file__), "./lib/EventModels.py")
    event_classes = []
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# THIS FILE IS AUTO-GENERATED\n")
        f.write("# DO NOT EDIT\n")
        f.write("# USE BuildEventModels.py TO UPDATE\n\n")
        f.write("from typing import TypedDict, NotRequired, Literal, Any\n\n")
        for event_type, events in sorted_stats:
            class_name = event_type + "Event"
            name, model = derive_typeddict(class_name, events)
            if model:
                f.write(f"# {event_type}: {len(json.dumps(events))} characters, {len(events)} entries\n")
                f.write(model + "\n\n")
                event_classes.append(class_name)

        if event_classes:
            f.write(f"AnyEvent = {' | '.join(event_classes)}\n")
    print(f"Statistics written to {output_file}")


if __name__ == "__main__":
    directory = "."
    process_journal_files(directory)
