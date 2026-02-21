from pathlib import Path
from typing import Any, Callable
import traceback
import yaml

from .Logger import log


class QuestCatalogManager:
    def __init__(self, reload_callback: Callable[[], None] | None = None):
        self.reload_callback = reload_callback

    def get_catalog_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "data" / "quests.yaml"

    def validate_catalog(self, catalog: Any) -> list[str]:
        errors: list[str] = []
        if not isinstance(catalog, dict):
            return ["Quest catalog must be an object."]
        if not isinstance(catalog.get("version"), str):
            errors.append("Quest catalog version must be a string.")
        actors = catalog.get("actors", [])
        actor_ids: set[str] = set()
        if actors is None:
            actors = []
        if not isinstance(actors, list):
            errors.append("Quest catalog actors must be a list.")
        else:
            for actor_index, actor in enumerate(actors):
                if not isinstance(actor, dict):
                    errors.append(f"Actor #{actor_index + 1} must be an object.")
                    continue
                for field in ("id", "name", "name_color", "voice", "avatar_url", "prompt"):
                    if field not in actor:
                        errors.append(
                            f"Actor '{actor.get('id', actor_index + 1)}' missing {field}.",
                        )
                if not isinstance(actor.get("id"), str):
                    errors.append(f"Actor #{actor_index + 1} id must be a string.")
                else:
                    actor_ids.add(actor["id"])
                if not isinstance(actor.get("name"), str):
                    errors.append(
                        f"Actor '{actor.get('id', actor_index + 1)}' name must be a string.",
                    )
                if not isinstance(actor.get("name_color"), str):
                    errors.append(
                        f"Actor '{actor.get('id', actor_index + 1)}' name_color must be a string.",
                    )
                if not isinstance(actor.get("voice"), str):
                    errors.append(
                        f"Actor '{actor.get('id', actor_index + 1)}' voice must be a string.",
                    )
                if not isinstance(actor.get("avatar_url"), str):
                    errors.append(
                        f"Actor '{actor.get('id', actor_index + 1)}' avatar_url must be a string.",
                    )
                if not isinstance(actor.get("prompt"), str):
                    errors.append(
                        f"Actor '{actor.get('id', actor_index + 1)}' prompt must be a string.",
                    )
        quests = catalog.get("quests")
        if not isinstance(quests, list):
            errors.append("Quest catalog quests must be a list.")
            return errors
        for quest_index, quest in enumerate(quests):
            if not isinstance(quest, dict):
                errors.append(f"Quest #{quest_index + 1} must be an object.")
                continue
            for field in ("id", "title", "description", "stages"):
                if field not in quest:
                    errors.append(
                        f"Quest '{quest.get('id', quest_index + 1)}' missing {field}.",
                    )
            if not isinstance(quest.get("id"), str):
                errors.append(f"Quest #{quest_index + 1} id must be a string.")
            if not isinstance(quest.get("title"), str):
                errors.append(
                    f"Quest '{quest.get('id', quest_index + 1)}' title must be a string.",
                )
            if not isinstance(quest.get("description"), str):
                errors.append(
                    f"Quest '{quest.get('id', quest_index + 1)}' description must be a string.",
                )
            stages = quest.get("stages")
            if not isinstance(stages, list):
                errors.append(
                    f"Quest '{quest.get('id', quest_index + 1)}' stages must be a list.",
                )
                continue
            for stage_index, stage in enumerate(stages):
                if not isinstance(stage, dict):
                    errors.append(
                        f"Quest '{quest.get('id', quest_index + 1)}' stage #{stage_index + 1} must be an object.",
                    )
                    continue
                for field in ("id", "description", "instructions"):
                    if field not in stage:
                        errors.append(
                            f"Quest '{quest.get('id', quest_index + 1)}' stage #{stage_index + 1} missing {field}.",
                        )
                if not isinstance(stage.get("id"), str):
                    errors.append(
                        f"Quest '{quest.get('id', quest_index + 1)}' stage #{stage_index + 1} id must be a string.",
                    )
                if not isinstance(stage.get("description"), str):
                    errors.append(
                        f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' description must be a string.",
                    )
                if not isinstance(stage.get("instructions"), str):
                    errors.append(
                        f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' instructions must be a string.",
                    )
                plan = stage.get("plan", [])
                if plan is None:
                    plan = []
                if not isinstance(plan, list):
                    errors.append(
                        f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' plan must be a list.",
                    )
                    continue
                for step_index, step in enumerate(plan):
                    if not isinstance(step, dict):
                        errors.append(
                            f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' plan step #{step_index + 1} must be an object.",
                        )
                        continue
                    conditions = step.get("conditions")
                    actions = step.get("actions")
                    if not isinstance(conditions, list):
                        errors.append(
                            f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' plan step #{step_index + 1} conditions must be a list.",
                        )
                    if not isinstance(actions, list):
                        errors.append(
                            f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' plan step #{step_index + 1} actions must be a list.",
                        )
                    if isinstance(conditions, list):
                        for condition_index, condition in enumerate(conditions):
                            if not isinstance(condition, dict):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' condition #{condition_index + 1} must be an object.",
                                )
                                continue
                            for field in ("source", "path", "operator", "value"):
                                if field not in condition:
                                    errors.append(
                                        f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' condition #{condition_index + 1} missing {field}.",
                                    )
                            if condition.get("operator") not in ("equals", "=="):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' condition #{condition_index + 1} operator must be equals or ==.",
                                )
                            if condition.get("source") != "event":
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' condition #{condition_index + 1} source must be event.",
                                )
                    if isinstance(actions, list):
                        for action_index, action in enumerate(actions):
                            if not isinstance(action, dict):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} must be an object.",
                                )
                                continue
                            action_type = action.get("action")
                            if action_type not in (
                                "log",
                                "advance_stage",
                                "set_active",
                                "play_sound",
                                "npc_message",
                            ):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} action must be log, advance_stage, set_active, play_sound, or npc_message.",
                                )
                                continue
                            if action_type == "log" and "message" not in action:
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} missing message.",
                                )
                            if (
                                action_type == "advance_stage"
                                and "target_stage_id" not in action
                            ):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} missing target_stage_id.",
                                )
                            if (
                                action_type == "set_active"
                                and "quest_id" not in action
                            ):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} missing quest_id.",
                                )
                            if (
                                action_type == "play_sound"
                                and "file_name" not in action
                            ):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} missing file_name.",
                                )
                            if action_type == "play_sound":
                                file_name = action.get("file_name")
                                if not isinstance(file_name, str) or not file_name.strip():
                                    errors.append(
                                        f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} file_name must be a non-empty string.",
                                    )
                                else:
                                    normalized_name = file_name.replace("\\", "/")
                                    if "/" in normalized_name:
                                        errors.append(
                                            f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} file_name must not contain path separators.",
                                        )
                                    lowered = normalized_name.lower()
                                    if not (lowered.endswith(".mp3") or lowered.endswith(".wav")):
                                        errors.append(
                                            f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} file_name must end with .mp3 or .wav.",
                                        )
                            if (
                                action_type == "play_sound"
                                and "transcription" not in action
                            ):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} missing transcription.",
                                )
                            if "actor_id" in action and action.get("actor_id") is not None and not isinstance(
                                action.get("actor_id"),
                                str,
                            ):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} actor_id must be a string.",
                                )
                            if (
                                isinstance(action.get("actor_id"), str)
                                and action.get("actor_id") not in actor_ids
                            ):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} actor_id references unknown actor.",
                                )
                            if (
                                action_type == "npc_message"
                                and not isinstance(action.get("actor_id"), str)
                            ):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} missing actor_id.",
                                )
                            if (
                                action_type == "npc_message"
                                and "transcription" not in action
                            ):
                                errors.append(
                                    f"Quest '{quest.get('id', quest_index + 1)}' stage '{stage.get('id', stage_index + 1)}' action #{action_index + 1} missing transcription.",
                                )
        return errors

    def get_catalog(self) -> dict[str, Any]:
        quests_path = self.get_catalog_path()
        try:
            if not quests_path.exists():
                return {
                    "error": f"Quest catalog not found at {quests_path}",
                    "catalog": {"version": "1.0", "quests": []},
                    "raw": "",
                    "path": str(quests_path),
                }
            raw = quests_path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw) if raw.strip() else {}
            if not isinstance(data, dict):
                return {
                    "error": "Quest catalog is not an object.",
                    "path": str(quests_path),
                }
            if "version" not in data:
                data["version"] = "1.0"
            if "actors" not in data or not isinstance(data["actors"], list):
                data["actors"] = []
            else:
                normalized_actors: list[dict[str, Any]] = []
                for actor in data["actors"]:
                    if isinstance(actor, dict):
                        actor.setdefault("prompt", "")
                        actor.setdefault("name_color", "#7cb3ff")
                        normalized_actors.append(actor)
                data["actors"] = normalized_actors
            if "quests" not in data or not isinstance(data["quests"], list):
                data["quests"] = []
            return {"catalog": data, "raw": raw, "path": str(quests_path)}
        except Exception as e:
            log("error", f"Error fetching quest catalog: {e}")
            log("error", traceback.format_exc())
            return {"error": str(e), "path": str(quests_path)}

    def save_catalog(self, catalog: Any) -> dict[str, Any]:
        errors = self.validate_catalog(catalog)
        if errors:
            return {"success": False, "message": " ".join(errors)}
        quests_path = self.get_catalog_path()
        try:
            with quests_path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(catalog, handle, sort_keys=False, allow_unicode=True)
            raw = quests_path.read_text(encoding="utf-8")
            if self.reload_callback:
                try:
                    self.reload_callback()
                except Exception as e:
                    log("warn", f"Quest reload failed after save: {e}")
            return {"success": True, "catalog": catalog, "raw": raw}
        except Exception as e:
            log("error", f"Error saving quest catalog: {e}")
            log("error", traceback.format_exc())
            return {"success": False, "message": str(e)}
