import json
from pathlib import Path
from typing import TypedDict


LANGUAGE_PACKS_DIRECTORY = Path(__file__).parent / "languages"


class ActionAlias(TypedDict):
    phrase: str
    action: str
    arguments: dict[str, object]


class ActionLanguagePack(TypedDict):
    name: str
    aliases: list[ActionAlias]


def load_action_language_packs() -> dict[str, ActionLanguagePack]:
    packs: dict[str, ActionLanguagePack] = {}

    for path in sorted(LANGUAGE_PACKS_DIRECTORY.glob("*.json")):
        with path.open(encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict) or not isinstance(data.get("name"), str):
            raise ValueError(f"Invalid action language pack metadata: {path}")

        aliases = data.get("aliases")
        if not isinstance(aliases, list):
            raise ValueError(f"Invalid action aliases in language pack: {path}")

        validated_aliases: list[ActionAlias] = []
        for alias in aliases:
            if (
                not isinstance(alias, dict)
                or not isinstance(alias.get("phrases"), list)
                or not alias["phrases"]
                or not all(isinstance(phrase, str) and phrase.strip() for phrase in alias["phrases"])
                or not isinstance(alias.get("action"), str)
                or not isinstance(alias.get("arguments"), dict)
            ):
                raise ValueError(f"Invalid action alias in language pack: {path}")

            for phrase in alias["phrases"]:
                validated_aliases.append({
                    "phrase": phrase.strip(),
                    "action": alias["action"],
                    "arguments": alias["arguments"],
                })

        packs[path.stem] = {
            "name": data["name"],
            "aliases": validated_aliases,
        }

    return packs
