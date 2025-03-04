import io
import json
import sys
import traceback
from typing import Any, final

from openai import OpenAI
from openai.types.chat import ChatCompletion

from lib.Config import Config, assign_ptt, get_ed_appdata_path, get_ed_journals_path, get_system_info, load_config, save_config, update_config, update_event_config
from lib.ActionManager import ActionManager
from lib.Actions import register_actions
from lib.ControllerManager import ControllerManager
from lib.EDCoPilot import EDCoPilot
from lib.EDKeys import EDKeys
from lib.Event import Event
from lib.Projections import registerProjections
from lib.PromptGenerator import PromptGenerator
from lib.STT import STT
from lib.TTS import TTS
from lib.StatusParser import Status, StatusParser
from lib.EDJournal import *
from lib.EventManager import EventManager


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


@final
class Chat:
    def __init__(self, config: Config):
        self.config = config # todo: remove
        if self.config["api_key"] == '':
            self.config["api_key"] = '-'
        
        self.backstory = self.config["character"].replace("{commander_name}", self.config['commander_name'])
            
        self.is_thinking = False
        
        self.controller_manager = ControllerManager()
        self.action_manager = ActionManager()

        enabled_game_events: list[str] = []
        for category in self.config["game_events"].values():

            for event, state in category.items():
                if state:
                    enabled_game_events.append(event)

        self.jn = EDJournal(self.config["game_events"], get_ed_journals_path(config))
            
        self.copilot = EDCoPilot(self.config["edcopilot"], is_edcopilot_dominant=self.config["edcopilot_dominant"],
                            enabled_game_events=enabled_game_events)

        # gets API Key from config.json
        self.llmClient = OpenAI(
            base_url="https://api.openai.com/v1" if self.config["llm_endpoint"] == '' else self.config["llm_endpoint"],
            api_key=self.config["api_key"] if self.config["llm_api_key"] == '' else self.config["llm_api_key"],
        )
        
        # vision
        self.visionClient: OpenAI | None = None
        if self.config["vision_var"]:
            self.visionClient = OpenAI(
                base_url="https://api.openai.com/v1" if self.config["vision_endpoint"] == '' else self.config["vision_endpoint"],
                api_key=self.config["api_key"] if self.config["vision_api_key"] == '' else self.config["vision_api_key"],
            )
            

        self.sttClient = OpenAI(
            base_url=self.config["stt_endpoint"],
            api_key=self.config["api_key"] if self.config["stt_api_key"] == '' else self.config["stt_api_key"],
        )

        self.ttsClient: OpenAI | None = None
        if self.config["tts_provider"] in ['openai', 'custom']:
            self.ttsClient = OpenAI(
                base_url=self.config["tts_endpoint"],
                api_key=self.config["api_key"] if self.config["tts_api_key"] == '' else self.config["tts_api_key"],
            )
            
        tts_provider = 'none' if self.config["edcopilot_dominant"] else self.config["tts_provider"]
        self.tts = TTS(openai_client=self.ttsClient, provider=tts_provider, model=self.config["tts_model_name"], voice=self.config["tts_voice"], speed=self.config["tts_speed"], output_device=self.config["output_device_name"])
        self.stt = STT(openai_client=self.sttClient, input_device_name=self.config["input_device_name"], model=self.config["stt_model_name"], custom_prompt=self.config["stt_custom_prompt"], required_word=self.config["stt_required_word"])

        self.enabled_game_events: list[str] = []
        if self.config["event_reaction_enabled_var"]:
            for category in self.config["game_events"].values():
                for event, state in category.items():
                    if state:
                        self.enabled_game_events.append(event)

        self.ed_keys = EDKeys(get_ed_appdata_path(config))
        self.status_parser = StatusParser(get_ed_journals_path(config))
        self.prompt_generator = PromptGenerator(self.config["commander_name"], self.config["character"], important_game_events=enabled_game_events)
        self.event_manager = EventManager(
            on_reply_request=lambda events, new_events, states: self.reply(events, new_events, states),
            game_events=enabled_game_events,
            continue_conversation=self.config["continue_conversation_var"],
            react_to_text_local=self.config["react_to_text_local_var"],
            react_to_text_starsystem=self.config["react_to_text_starsystem_var"],
            react_to_text_npc=self.config["react_to_text_npc_var"],
            react_to_text_squadron=self.config["react_to_text_squadron_var"],
            react_to_material=self.config["react_to_material"],
            react_to_danger_mining=self.config["react_to_danger_mining_var"],
            react_to_danger_onfoot=self.config["react_to_danger_onfoot_var"]
        )
        
    def execute_actions(self, actions: list[dict[str, Any]], projected_states: dict[str, dict]):
        action_descriptions: list[str | None] = []
        action_results: list[Any] = []
        for action in actions:
            action_input_desc = self.action_manager.getActionDesc(action, projected_states)
            action_descriptions.append(action_input_desc)
            if action_input_desc:
                self.tts.say(action_input_desc)
            action_result = self.action_manager.runAction(action, projected_states)
            action_results.append(action_result)
            self.event_manager.add_tool_call([action.model_dump()], [action_result], [action_input_desc] if action_input_desc else None)



    def verify_action(self, user_input: list[str], action: dict[str, Any], prompt: list, tools: list):
        """ Verify the action prediction by sending the user input without any context to the model and check if the action is still predicted """
        log("debug", "Verifying action:", user_input, action)
        
        draft_action = self.action_manager.has_prediction_draft(user_input, tools)
        if not draft_action:
            self.action_manager.save_prediction_draft(user_input, action, tools)
            return
        
        completion = self.llmClient.chat.completions.create(
            model=self.config["llm_model_name"],
            messages=[prompt[0]] + [{"role": "user", "content": user} for user in user_input],
            tools=tools
        )
        
        if not isinstance(completion, ChatCompletion) or hasattr(completion, 'error'):
            log("debug", "error during action verification:", completion)
            return

        self.action_manager.save_prediction_verification(user_input, action, completion.choices[0].message.tool_calls, tools)
    


    def reply(self, events: list[Event], new_events: list[Event], projected_states: dict[str, dict]):
        self.is_thinking = True
        log('debug', 'Starting reply...')
        prompt = self.prompt_generator.generate_prompt(events=events, projected_states=projected_states, pending_events=new_events)

        user_input: list[str] = [event.content for event in new_events if event.kind == 'user']
        use_tools = self.config["tools_var"] and len(user_input)
        reasons = [event.content.get('event', event.kind) if event.kind=='game' else event.kind for event in new_events if event.kind in ['user', 'game', 'tool', 'status']]

        current_status = projected_states.get("CurrentStatus")
        flags = current_status["flags"]
        flags2 = current_status["flags2"]

        active_mode = None
        if flags:
            if flags["InMainShip"]:
                active_mode = "mainship"
            elif flags["InFighter"]:
                active_mode = "fighter"
            elif flags["InSRV"]:
                active_mode = "buggy"
        if flags2:
            if flags2["OnFoot"]:
                active_mode = "humanoid"

        uses_actions = self.config["game_actions_var"]
        uses_web_actions = self.config["web_search_actions_var"]
        tool_list = self.action_manager.getToolsList(active_mode, uses_actions, uses_web_actions) if use_tools else None
        predicted_actions = None
        if tool_list and user_input:
            predicted_actions = self.action_manager.predict_action(user_input, tool_list)
            
        if predicted_actions:
            #log('info', 'predicted_actions', predicted_actions)
            response_text = None
            response_actions = predicted_actions
        else:
            completion = self.llmClient.chat.completions.create(
                model=self.config["llm_model_name"],
                messages=prompt,
                tools=tool_list
            )

            if not isinstance(completion, ChatCompletion) or hasattr(completion, 'error'):
                log("error", "completion with error:", completion)
                is_thinking = False
                return
            if hasattr(completion, 'usage') and completion.usage:
                log("Debug", f'Prompt: {completion.usage.prompt_tokens}, Completion: {completion.usage.completion_tokens}')

            response_text = completion.choices[0].message.content
            response_actions = completion.choices[0].message.tool_calls

        if response_text and not response_actions:
            self.tts.say(response_text)
            self.event_manager.add_conversation_event('assistant', completion.choices[0].message.content)
            self.copilot.output_covas(response_text, reasons)

        self.is_thinking = False


        if response_actions:
            self.execute_actions(response_actions, projected_states)

            if not predicted_actions and config["use_action_cache_var"]:
                self.verify_action(user_input, response_actions, prompt, tool_list)

    def run(self):
        log('info', f"Initializing CMDR {self.config['commander_name']}'s personal AI...\n")
        log('info', "API Key: Loaded")
        log('info', f"Using Push-to-Talk: {self.config['ptt_var']}")
        log('info', f"Using Function Calling: {self.config['tools_var']}")
        log('info', f"Current model: {self.config['llm_model_name']}")
        log('info', f"Current TTS voice: {self.config['tts_voice']}")
        log('info', f"Current TTS Speed: {self.config['tts_speed']}")
        log('info', "Current backstory: " + self.backstory)

        # TTS Setup
        log('info', "Basic configuration complete.")
        log('info', "Loading voice output...")
        if self.config["edcopilot_dominant"]:
            log('info', "EDCoPilot is dominant, voice output will be handled by EDCoPilot.")

        if self.config['ptt_var'] and self.config['ptt_key']:
            log('info', f"Setting push-to-talk hotkey {self.config['ptt_key']}.")
            self.controller_manager.register_hotkey(
                self.config["ptt_key"], 
                lambda _: self.stt.listen_once_start(),
                lambda _: self.stt.listen_once_end()
            )
        else:
            self.stt.listen_continuous()
        log('info', "Voice interface ready.")

        registerProjections(self.event_manager)

        if self.config['tools_var']:
            register_actions(self.action_manager, self.event_manager, self.llmClient, self.config["llm_model_name"], self.visionClient, self.config["vision_model_name"], self.ed_keys)
            log('info', "Actions ready.")
        
        if not self.config["continue_conversation_var"]:
            self.action_manager.reset_action_cache()
            
        log('info', 'Initializing states...')
        while self.jn.historic_events:
            self.event_manager.add_historic_game_event(self.jn.historic_events.pop(0))
            
        self.event_manager.add_status_event(self.status_parser.current_status)
        self.event_manager.process()

        # Cue the user that we're ready to go.
        log('info', "System Ready.")

        while True:
            try:
                status = None
                # check status file for updates
                while not self.status_parser.status_queue.empty():
                    status = self.status_parser.status_queue.get()
                    self.event_manager.add_status_event(status)
                    
                # mute continuous listening during response
                if self.config["mute_during_response_var"]:
                    if self.tts.get_is_playing():
                        self.stt.pause_continuous_listening(True)
                    else:
                        self.stt.pause_continuous_listening(False)

                # check STT recording
                if self.stt.recording:
                    if self.tts.get_is_playing():
                        log('debug', 'interrupting TTS')
                        self.tts.abort()
                    if not self.event_manager.is_listening:
                        self.event_manager.is_listening = True
                else:
                    if self.event_manager.is_listening:
                        self.event_manager.is_listening = False

                # check STT result queue
                if not self.stt.resultQueue.empty():
                    text = self.stt.resultQueue.get().text
                    self.tts.abort()
                    self.copilot.output_commander(text)
                    self.event_manager.add_conversation_event('user', text)

                if not self.is_thinking and not self.tts.get_is_playing() and self.event_manager.is_replying:
                    self.event_manager.add_assistant_complete_event()

                # check EDJournal files for updates
                while not self.jn.events.empty():
                    event = self.jn.events.get()
                    self.event_manager.add_game_event(event)

                while not self.copilot.event_publication_queue.empty():
                    event = self.copilot.event_publication_queue.get()
                    self.event_manager.add_external_event('External'+event.service.capitalize()+'Notification', event.model_dump())

                self.event_manager.process()

                # Infinite loops are bad for processors, must sleep.
                sleep(0.25)
            except KeyboardInterrupt:
                break
            except Exception as e:
                log("error", e, traceback.format_exc())
                break

        # Teardown TTS
        self.tts.quit()


if __name__ == "__main__":
    try:
        print(json.dumps({"type": "ready"})+'\n')
        # Wait for start signal on stdin
        config = load_config()
        print(json.dumps({"type": "config", "config": config})+'\n', flush=True)
        system = get_system_info()
        print(json.dumps({"type": "system", "system": system})+'\n', flush=True)
        while True:
            # print(f"Waiting for command...")
            line = sys.stdin.readline().strip()
            # print(f"Received command: {line}")
            if not line:
                continue
                
            try:
                data = json.loads(line)
                if data.get("type") == "start":
                    break
                if data.get("type") == "assign_ptt":
                    config = assign_ptt(config, ControllerManager())
                if data.get("type") == "change_config":
                    config = update_config(config, data["config"])
                if data.get("type") == "change_event_config":
                    config = update_event_config(config, data["section"], data["event"], data["value"])
                
            except json.JSONDecodeError:
                continue
        
        # Once start signal received, initialize and run chat
        config = load_config()
        Chat(config).run()
    except Exception as e:
        log("error", e, traceback.format_exc())
        sys.exit(1)
