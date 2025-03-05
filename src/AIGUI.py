import argparse
import datetime
import json
import os
import time
import re
import subprocess
import sys
import tkinter as tk
import traceback
import webbrowser
from queue import Queue
import platform
from threading import Thread
from tkinter import messagebox
from typing import Dict, final
import typing

from wrapt import synchronized

import pyaudio
import requests
from openai import APIError, OpenAI

from lib.Config import Config, get_input_device_names, get_output_device_names, load_config, check_and_upgrade_model, ModelValidationResult
from lib.ControllerManager import ControllerManager
from lib.EDCoPilot import EDCoPilot


class VerticalScrolledFrame(tk.Frame):
    """A pure Tkinter scrollable frame that actually works!
    * Use the 'interior' attribute to place widgets inside the scrollable frame.
    * Construct and pack/place/grid normally.
    * This frame only allows vertical scrolling.
    """

    def __init__(self, outer_frame, width, *args, **kw):
        scrollbar_width = 16
        inner_width = width - scrollbar_width

        # base class initialization
        tk.Frame.__init__(self, outer_frame, width=width)

        scrollbar = tk.Scrollbar(self, width=scrollbar_width)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, expand=False)

        self.canvas = tk.Canvas(self, yscrollcommand=scrollbar.set, width=inner_width)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.inner_frame = tk.Frame(self.canvas, width=inner_width, borderwidth=2, relief="ridge", *args, **kw)
        # self.inner_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.canvas.yview)

        self.canvas.bind('<Configure>', self.__fill_canvas)

        # assign this obj (the inner frame) to the windows item of the canvas
        self.windows_item = self.canvas.create_window(0, 0, window=self.inner_frame, width=inner_width, anchor=tk.NW)
        self.canvas.configure(background='black')

    def __fill_canvas(self, event):
        "Enlarge the windows item to the canvas width"

        self.update_idletasks()
        self.canvas.itemconfig("inner_frame", width=self.canvas.winfo_width())

    def update(self):
        "Update the canvas and the scrollregion"

        self.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.canvas.itemconfig("inner_frame", width=self.canvas.winfo_width())

        self.canvas.bind('<Enter>', self.__on_enter)
        self.canvas.bind('<Leave>', self.__on_leave)

    def __on_enter(self, event):
        self.canvas.bind_all("<MouseWheel>", self.__onmousewheel)

    def __on_leave(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def __onmousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")



def ask_for_update(release_name='A new release',
                   release_url='https://github.com/RatherRude/Elite-Dangerous-AI-Integration/releases/'):
    # Ask the user if they want to download the new version
    result = messagebox.askyesno(f"Update available",
                                 f"Would you like to download {release_name}?")

    if result:
        webbrowser.open(release_url)


def check_for_updates(current_commit):
    url = f'https://api.github.com/repos/RatherRude/Elite-Dangerous-AI-Integration/releases'
    response = requests.get(url)

    if response.status_code == 200:
        release_data = response.json()
        tag_name = release_data[0]['tag_name']
        release_url = release_data[0]['html_url']
        release_name = release_data[0]['name']

        # Get the commit id for the release tag
        tag_url = f'https://api.github.com/repos/RatherRude/Elite-Dangerous-AI-Integration/git/ref/tags/{tag_name}'
        tag_response = requests.get(tag_url)

        if tag_response.status_code == 200:
            tag_data = tag_response.json()
            if tag_data['object']['sha'] != current_commit:
                ask_for_update(release_name, release_url)

@final
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("COVAS:NEXT")
        root.protocol("WM_DELETE_WINDOW", self.on_closing)

        parser = argparse.ArgumentParser()
        python_executable = sys.executable
        parser.add_argument("--chat", default=python_executable + " ./src/Chat.py", help="command to run the chat app")
        parser.add_argument("--release", default="", help="current release")
        args = parser.parse_args()
        self.chat_command_arg: str = args.chat
        self.release_version_arg: str = args.release

        self.check_vars = {}

        self.ptt_key = None

        self.controller_manager = ControllerManager()
        self.edcopilot = EDCoPilot(False) # this is only for the GUI, the actual EDCoPilot client is created in the Chat

        self.process = None
        self.output_queue = Queue()
        self.read_thread = None
        # Load initial data from JSON file if exists
        self.data: Config = self.load_data()

        # Background Image
        try:
            background_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../docs/screen/EDAI_logo.png'))
            if hasattr(sys, 'frozen'):
                background_image_path = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), './screen/EDAI_logo.png'))
            background_image = tk.PhotoImage(file=background_image_path)
            self.background_label = tk.Label(root, bg="black", image=background_image)
            self.background_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.background_label.image = background_image
        except tk.TclError as e:
            print(f"Failed to load background image: {e}")

        self.incr = 0

        def get_next():
            self.incr += 1
            return self.incr

        def get_same():
            return self.incr

        # Main Frame (for other widgets)
        self.main_frame = tk.Frame(root, bd=1)  # White background for visibility
        self.main_frame.pack(padx=20, pady=20)

        # Commander Name (Small Input)
        tk.Label(self.main_frame, text="Commander Name:").grid(row=0, column=0, sticky=tk.W)
        self.commander_name = tk.Entry(self.main_frame, width=50)
        self.commander_name.grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)

        # Character (Multi-line Input)
        tk.Label(self.main_frame, text="AI Character:").grid(row=get_next(), column=0, sticky=tk.W)
        self.character = tk.Text(self.main_frame, width=80, height=15)
        self.character.grid(row=get_same(), column=1, padx=10, pady=5, sticky=tk.W)

        # API Key (Secure Entry) - Placed above the first button
        tk.Label(self.main_frame, text="OpenAI API Key:").grid(row=get_next(), column=0, sticky=tk.W)
        self.api_key = tk.Entry(self.main_frame, show='*', width=50)  # Show '*' to indicate a secure entry
        self.api_key.grid(row=get_same(), column=1, padx=10, pady=5, sticky=tk.W)

        # Push-to-talk
        tk.Label(self.main_frame, text="Push-to-talk:", font=('Helvetica', 10)).grid(row=get_next(), column=0, sticky=tk.W)
        # PTT (Checkbox)
        self.ptt_var = tk.BooleanVar()
        self.ptt_var.set(False)  # Default value
        self.ptt_checkbox = tk.Checkbutton(self.main_frame, text="Enabled", variable=self.ptt_var,
                                           command=self.toggle_ptt)
        self.ptt_checkbox.grid(row=get_same(), column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.main_frame, text="Uses automatic voice detection if not enabled", font="Helvetica 10 italic").grid(
            row=get_same(), column=1, sticky=tk.W, padx=80, pady=5)

        self.pptButton = tk.Button(self.main_frame, text="Key Binding: Press any key", font=('Helvetica', 10))
        self.pptButton.grid(row=get_same(), column=1, sticky=tk.W, padx=(370, 10), pady=5)
        self.pptButton.bind("<Button-1>", self.on_label_click)

        self.mute_during_response_var = tk.BooleanVar()
        self.mute_during_response_var.set(False)  # Default value
        self.muteResponseCheckbox = tk.Checkbutton(self.main_frame, text="Mute microphone during AI response", variable=self.mute_during_response_var)
        self.muteResponseCheckbox.grid(row=get_same(), column=1, sticky=tk.W, padx=(370, 10), pady=5)

        # Continue Conversation
        tk.Label(self.main_frame, text="Resume Chat:", font=('Helvetica', 10)).grid(row=get_next(), column=0, sticky=tk.W)
        # Conversation (Checkbox)
        self.continue_conversation_var = tk.BooleanVar()
        self.continue_conversation_var.set(True)  # Default value
        self.continue_conversation_checkbox = tk.Checkbutton(self.main_frame, text="Enabled",
                                                             variable=self.continue_conversation_var)
        self.continue_conversation_checkbox.grid(row=get_same(), column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.main_frame, text="Resumes previous conversation if enabled", font="Helvetica 10 italic").grid(row=get_same(),
                                                                                                                column=1,
                                                                                                                sticky=tk.W,
                                                                                                                padx=80,
                                                                                                                pady=5)

        tk.Label(self.main_frame, text="Input Device:", font=('Helvetica', 10)).grid(row=get_next(), column=0, sticky=tk.W)
        input_device_names = get_input_device_names()
        self.input_device_name_var = tk.StringVar()
        self.input_device_name_var.set(input_device_names[0])
        self.input_device_name = tk.OptionMenu(self.main_frame, self.input_device_name_var, *input_device_names)
        self.input_device_name.grid(row=get_same(), column=1, padx=10, pady=5, sticky=tk.W)
        
        tk.Label(self.main_frame, text="Output Device:", font=('Helvetica', 10)).grid(row=get_next(), column=0, sticky=tk.W)
        output_device_names = get_output_device_names()
        self.output_device_name_var = tk.StringVar()
        self.output_device_name_var.set(output_device_names[0])
        self.output_device_name = tk.OptionMenu(self.main_frame, self.output_device_name_var, *output_device_names)
        self.output_device_name.grid(row=get_same(), column=1, padx=10, pady=5, sticky=tk.W)


        # Toggle Section Button
        self.toggle_behavior_section_button = tk.Button(self.main_frame, text="Behavior",
                                                           command=self.toggle_behavior_section)
        self.toggle_behavior_section_button.grid(row=get_next(), column=0, columnspan=2, pady=10, padx=(0, 90), sticky="")

        # Toggle Section Button
        self.toggle_third_party_section_button = tk.Button(self.main_frame, text="Third-Party Apps",
                                                        command=self.toggle_third_party_section)
        self.toggle_third_party_section_button.grid(row=get_same(), column=0, columnspan=2, pady=10, padx=(335, 0), sticky="")

        # Toggle Section Button
        self.toggle_ai_geeks_section_button = tk.Button(self.main_frame, text="Advanced Settings",
                                                        command=self.toggle_ai_geeks_section)
        self.toggle_ai_geeks_section_button.grid(row=get_same(), column=0, columnspan=2, pady=10, padx=(100, 0), sticky="")

        # Toggle Section Button
        # self.toggle_game_events_section_button = tk.Button(self.main_frame, text=" Events Triggers",
        #                                                    command=self.toggle_game_events_section)
        # self.toggle_game_events_section_button.grid(row=get_same(), column=0, columnspan=2, pady=10, padx=(0, 205), sticky="")

        # Game Events (Initially hidden)
        self.game_events_frame = VerticalScrolledFrame(self.main_frame, width=600)
        self.game_events_frame.grid(row=get_next(), column=0, columnspan=2, sticky="")

        self.game_events_save_cb = self.populate_game_events_frame(self.game_events_frame.inner_frame,
                                                                   self.data['game_events'])
        self.game_events_frame.update()  # update scrollable area
        self.game_events_frame.grid_remove()  # Initially hide

        # Behavior (Initially hidden)
        self.behavior_frame = VerticalScrolledFrame(self.main_frame, width=600)
        self.behavior_frame.grid(row=get_next(), column=0, columnspan=2, sticky="")

        tk.Label(self.behavior_frame.inner_frame, text="Game Event Reactions", font=('Helvetica', 10)).grid(row=1, column=0,
                                                                                    sticky=tk.W)
        self.event_reaction_enabled_var = tk.BooleanVar()
        self.behavior_reactions_checkbox = tk.Checkbutton(self.behavior_frame.inner_frame, text="Enabled",
                                                 variable=self.event_reaction_enabled_var)
        self.behavior_reactions_checkbox.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.behavior_frame.inner_frame, text="Allow reactions to the game", font="Helvetica 10 italic").grid(
            row=1,
            column=1,
            sticky=tk.W,
            padx=80,
            pady=5)
        self.behavior_customize_reactions_button = tk.Button(self.behavior_frame.inner_frame, text="Customize",
                                                           command=self.toggle_game_events_section)
        self.behavior_customize_reactions_button.grid(row=1, column=1, pady=5, padx=248, sticky="")

        tk.Label(self.behavior_frame.inner_frame, text="Game Actions", font=('Helvetica', 10)).grid(row=2, column=0, sticky=tk.W)
        self.game_actions_var = tk.BooleanVar()
        self.behavior_game_actions_checkbox = tk.Checkbutton(self.behavior_frame.inner_frame, text="Enabled",
                                                 variable=self.game_actions_var)
        self.behavior_game_actions_checkbox.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.behavior_frame.inner_frame, text="Allow controlling the game (Ship/SRV/Suit/Vision)", font="Helvetica 10 italic").grid(
            row=2,
            column=1,
            sticky=tk.W,
            padx=80,
            pady=5)

        tk.Label(self.behavior_frame.inner_frame, text="Web Search Actions", font=('Helvetica', 10)).grid(row=3,
                                                                                                            column=0,
                                                                                                            sticky=tk.W)

        self.web_search_actions_var = tk.BooleanVar()
        self.behavior_web_actions_checkbox = tk.Checkbutton(self.behavior_frame.inner_frame, text="Enabled",
                                                 variable=self.web_search_actions_var)
        self.behavior_web_actions_checkbox.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.behavior_frame.inner_frame, text="Allow third-party web searches (Galnet/Spansh API)", font="Helvetica 10 italic").grid(
            row=3,
            column=1,
            sticky=tk.W,
            padx=80,
            pady=5)

        tk.Label(self.behavior_frame.inner_frame, text="Action Cache", font=('Helvetica', 10)).grid(row=4, column=0, sticky=tk.W)
        
        self.use_action_cache_var = tk.BooleanVar()
        self.use_action_cache_checkbox = tk.Checkbutton(self.behavior_frame.inner_frame, text="Enabled",
                                                        variable=self.use_action_cache_var)
        self.use_action_cache_checkbox.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(self.behavior_frame.inner_frame, text="Learn actions from previous interactions", font="Helvetica 10 italic").grid(
            row=4,
            column=1,
            sticky=tk.W,
            padx=80,
            pady=5)
        

        self.behavior_frame.update()
        self.behavior_frame.grid_remove()  # Initially hide        


        # Third Party (Initially hidden)
        self.third_party_frame = VerticalScrolledFrame(self.main_frame, width=600)
        self.third_party_frame.grid(row=get_next(), column=0, columnspan=2, sticky="")
        self.third_party_frame.grid_remove()  # Initially hide

        # self.incr = 0
        # EDCoPilot (Checkbox)
        self.edcopilot_label = tk.Label(self.third_party_frame.inner_frame, text="EDCoPilot-Integration (WIP)", font=('Helvetica 11 bold'))
        self.edcopilot_label.grid(row=0, column=0, columnspan=2, sticky="W")
        # tk.Label(self.third_party_frame.inner_frame, text="EDCoPilot:", font=('Helvetica', 10)).grid(row=get_next(), column=0, sticky="NW")
        self.edcopilot_var = tk.BooleanVar()
        self.edcopilot_var.set(True)
        self.edcopilot_checkbox = tk.Checkbutton(self.third_party_frame.inner_frame, text="Enabled", variable=self.edcopilot_var)
        self.edcopilot_checkbox.grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.edcopilot_description = tk.Label(self.third_party_frame.inner_frame, text="COVAS:NEXT sends messages to EDCoPilot.",
                                              font=('Helvetica 10 italic'))
        self.edcopilot_description.grid(row=1, column=1, sticky=tk.W)

        if not self.edcopilot.is_installed():
            self.edcopilot_label.grid_remove()
            self.edcopilot_checkbox.grid_remove()
            self.edcopilot_description.grid_remove()

        self.edcopilot_dominant_var = tk.BooleanVar()
        self.edcopilot_dominant_var.set(False)
        self.edcopilot_dominant_checkbox = tk.Checkbutton(self.third_party_frame.inner_frame, text="EDCoPilot-Dominant",
                                                          variable=self.edcopilot_dominant_var)
        self.edcopilot_dominant_checkbox.grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        self.edcopilot_dominant_description = tk.Text(
            self.third_party_frame.inner_frame,
            wrap="word",
            font=('Helvetica', 10),
            borderwidth=0,
            highlightthickness=0,
            cursor="arrow",
            bg=self.third_party_frame.inner_frame.cget('background')
        )
        # Clear existing content (if necessary)
        self.edcopilot_dominant_description.delete("1.0", "end")

        # Insert the text
        self.edcopilot_dominant_description.insert("1.0", "WARNING:")
        self.edcopilot_dominant_description.insert("1.8",
                                                   " COVAS:NEXT's reactions and general audio will be\nmanaged by EDCoPilot! ")
        self.edcopilot_dominant_description.insert("3.0", "Only activate this if you know\nwhat you're doing! ")

        # Apply bold formatting
        self.edcopilot_dominant_description.tag_configure("bold", font=('Helvetica', 10, 'bold'))
        self.edcopilot_dominant_description.tag_add("bold", "1.0", "1.8")  # "WARNING:"
        self.edcopilot_dominant_description.tag_add("bold", "2.21", "3.19")  # "Only activate this..."

        # Apply red color to "WARNING:"
        self.edcopilot_dominant_description.tag_configure("red", foreground="red")
        self.edcopilot_dominant_description.tag_add("red", "1.0", "1.8")


        # Disable text selection by binding a callback to block selection actions
        self.edcopilot_dominant_description.bind("<Button-1>", lambda e: "break")
        self.edcopilot_dominant_description.bind("<Control-c>", lambda e: "break")
        self.edcopilot_dominant_description.bind("<Control-x>", lambda e: "break")
        self.edcopilot_dominant_description.bind("<Control-v>", lambda e: "break")

        # Disable editing
        self.edcopilot_dominant_description.config(state="disabled")

        # Place the Text widget
        self.edcopilot_dominant_description.grid(row=2, column=1, sticky="W")

        self.edcopilot_dominant_doc_link = tk.Label(self.third_party_frame.inner_frame, text="Read more about this here", fg="blue", cursor="hand2",
                                                    font=('Helvetica 10 bold'))
        self.edcopilot_dominant_doc_link.grid(row=2, column=1, sticky="NW", pady=(49,0), padx=(0,0))

        self.edcopilot_dominant_doc_link.bind("<Button-1>", lambda e: webbrowser.open_new(
            "https://ratherrude.github.io/Elite-Dangerous-AI-Integration/50_EDCoPilot/"))

        if not self.edcopilot.is_installed():
            self.edcopilot_dominant_description.grid_remove()
            self.edcopilot_dominant_checkbox.grid_remove()
            self.edcopilot_dominant_description.grid_remove()
            self.edcopilot_dominant_doc_link.grid_remove()
            self.toggle_third_party_section_button.grid_remove()

        self.third_party_frame.update()

        # AI Settings (Initially hidden)
        self.ai_geeks_frame = VerticalScrolledFrame(self.main_frame, width=600)
        self.ai_geeks_frame.grid(row=get_same(), column=0, columnspan=2)
        self.ai_geeks_frame.grid_remove()  # Initially hide

        self.incr = 0

        # LLM
        tk.Label(self.ai_geeks_frame.inner_frame, text="Text LLM options",
                 font="Helvetica 11 bold").grid(row=get_next(), column=0, columnspan=2, sticky="W")

        # LLM Model Name
        tk.Label(self.ai_geeks_frame.inner_frame, text="LLM Model Name:").grid(row=get_next(), column=0, sticky=tk.W)
        self.llm_model_name = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.llm_model_name.grid(row=get_same(), column=1, padx=10, pady=5)

        # LLM Endpoint
        tk.Label(self.ai_geeks_frame.inner_frame, text="LLM Endpoint:").grid(row=get_next(), column=0, sticky=tk.W)
        self.llm_endpoint = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.llm_endpoint.grid(row=get_same(), column=1, padx=10, pady=5)

        # LLM API Key
        tk.Label(self.ai_geeks_frame.inner_frame, text="LLM API Key:").grid(row=get_next(), column=0, sticky=tk.W)
        self.llm_api_key = tk.Entry(self.ai_geeks_frame.inner_frame, show='*', width=50)
        self.llm_api_key.grid(row=get_same(), column=1, padx=10, pady=5)

        # Function Calling (Checkbox)
        self.tools_var = tk.BooleanVar()
        self.tools_var.set(True)  # Default value
        tk.Label(self.ai_geeks_frame.inner_frame, text="Allow AI Actions (Tool Use)", font=('Helvetica', 10)).grid(row=get_next(),
                                                                                                            column=0,
                                                                                                            sticky=tk.W)

        self.tools_checkbox = tk.Checkbutton(self.ai_geeks_frame.inner_frame, text="Enable",
                                             variable=self.tools_var)
        self.tools_checkbox.grid(row=get_same(), column=1, padx=10, pady=10, sticky=tk.W)

        # STT
        tk.Label(self.ai_geeks_frame.inner_frame, text="STT options",
                 font="Helvetica 11 bold").grid(row=get_next(), column=0, columnspan=2, sticky="W")
        
        ## STT Provider
        self.stt_provider_label = tk.Label(self.ai_geeks_frame.inner_frame, text="STT Provider:")
        self.stt_provider_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.stt_provider_select_var = tk.StringVar()
        self.stt_provider_select = tk.OptionMenu(self.ai_geeks_frame.inner_frame, self.stt_provider_select_var, "openai", "custom",
                                                    command=self.toggle_stt_provider)
        self.stt_provider_select.grid(row=get_same(), column=1, padx=10, pady=5, sticky=tk.W)

        ## STT Model
        self.stt_model_name_label = tk.Label(self.ai_geeks_frame.inner_frame, text="STT Model Name:")
        self.stt_model_name_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.stt_model_name = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.stt_model_name.grid(row=get_same(), column=1, padx=10, pady=5)

        ## STT Endpoint
        self.stt_endpoint_label = tk.Label(self.ai_geeks_frame.inner_frame, text="STT Endpoint:")
        self.stt_endpoint_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.stt_endpoint = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.stt_endpoint.grid(row=get_same(), column=1, padx=10, pady=5)

        ## STT API Key
        self.stt_api_key_label = tk.Label(self.ai_geeks_frame.inner_frame, text="STT API Key:")
        self.stt_api_key_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.stt_api_key = tk.Entry(self.ai_geeks_frame.inner_frame, show='*', width=50)
        self.stt_api_key.grid(row=get_same(), column=1, padx=10, pady=5)

        # TTS
        tk.Label(self.ai_geeks_frame.inner_frame, text="TTS options",
                 font="Helvetica 11 bold").grid(row=get_next(), column=0, columnspan=2, sticky="W")
        
        ## TTS Provider
        self.tts_provider_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS Provider:")
        self.tts_provider_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_provider_select_var = tk.StringVar()
        self.tts_provider_select = tk.OptionMenu(self.ai_geeks_frame.inner_frame, self.tts_provider_select_var,
                                                 "openai", "edge-tts", "custom", "none",
                                                 command=self.toggle_tts_provider)
        self.tts_provider_select.grid(row=get_same(), column=1, padx=10, pady=5, sticky=tk.W)

        ## TTS Model
        self.tts_model_name_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS Model Name:")
        self.tts_model_name_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_model_name = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.tts_model_name.grid(row=get_same(), column=1, padx=10, pady=5)

        ## TTS Endpoint
        self.tts_endpoint_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS Endpoint:")
        self.tts_endpoint_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_endpoint = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.tts_endpoint.grid(row=get_same(), column=1, padx=10, pady=5)

        ## TTS API Key
        self.tts_api_key_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS API Key:")
        self.tts_api_key_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_api_key = tk.Entry(self.ai_geeks_frame.inner_frame, show='*', width=50)
        self.tts_api_key.grid(row=get_same(), column=1, padx=10, pady=5)

        # TTS Voice
        self.tts_voice_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS Voice:")
        self.tts_voice_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_voice = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.tts_voice.grid(row=get_same(), column=1, padx=10, pady=5)

        # TTS Speed
        self.tts_speed_label = tk.Label(self.ai_geeks_frame.inner_frame, text="TTS Speed:")
        self.tts_speed_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.tts_speed = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.tts_speed.grid(row=get_same(), column=1, padx=10, pady=5)

        # Vision
        tk.Label(self.ai_geeks_frame.inner_frame, text="Vision LLM options",
                 font="Helvetica 11 bold").grid(row=get_next(), column=0, columnspan=2, sticky="W")

        ## Vision Model
        self.vision_model_name_label = tk.Label(self.ai_geeks_frame.inner_frame, text="Vision Model Name:")
        self.vision_model_name_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.vision_model_name = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.vision_model_name.grid(row=get_same(), column=1, padx=10, pady=5)
        #
        ## Vision Model Endpoint
        self.vision_endpoint_label = tk.Label(self.ai_geeks_frame.inner_frame, text="Vision Model Endpoint:")
        self.vision_endpoint_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.vision_endpoint = tk.Entry(self.ai_geeks_frame.inner_frame, width=50)
        self.vision_endpoint.grid(row=get_same(), column=1, padx=10, pady=5)
        #
        ## Vision Model API Key
        self.vision_api_key_label = tk.Label(self.ai_geeks_frame.inner_frame, text="Vision Model API Key:")
        self.vision_api_key_label.grid(row=get_next(), column=0, sticky=tk.W)
        self.vision_api_key = tk.Entry(self.ai_geeks_frame.inner_frame, show='*', width=50)
        self.vision_api_key.grid(row=get_same(), column=1, padx=10, pady=5)

        # Vision Capabilities (Checkbox)
        tk.Label(self.ai_geeks_frame.inner_frame, text="Vision Capabilities", font=('Helvetica', 10)).grid(row=get_next(),
                                                                                                            column=0,
                                                                                                            sticky=tk.W)

        self.vision_var = tk.BooleanVar()
        self.vision_var.set(True)  # Default value
        self.vision_checkbox = tk.Checkbutton(self.ai_geeks_frame.inner_frame, text="Enable",
                                              variable=self.vision_var, command=self.toggle_vision)
        self.vision_checkbox.grid(row=get_same(), column=1, padx=10, pady=10, sticky=tk.W)

        self.ai_geeks_frame.update()


        # Debug Frame and Text Widget
        self.debug_frame = tk.Frame(root, bg='black', bd=1)  # White background for visibility
        self.debug_frame.pack(side=tk.TOP, padx=20, pady=20)

        tk.Label(self.debug_frame, text="Debug Output:").pack(anchor=tk.W)
        self.debug_text = tk.Text(self.debug_frame, width=100, height=43, bg='black')
        self.debug_text.tag_configure("normal", foreground="white", font="Helvetica 12")
        self.debug_text.tag_configure("human", foreground="red", font="Helvetica 12 bold")
        self.debug_text.tag_configure("ai", foreground="blue", font="Helvetica 12 bold")
        self.debug_text.tag_configure("action", foreground="yellow", font="Helvetica 12 bold")
        self.debug_text.tag_configure("event", foreground="orange", font="Helvetica 12 bold")
        self.debug_text.tag_configure("debug", foreground="gray", font="Helvetica 12 bold")
        self.debug_text.tag_configure("error", foreground="red", font="Helvetica 12 bold")
        self.debug_text.pack(side=tk.LEFT, padx=10, pady=10)

        self.debug_frame.pack_forget()

        # Button Frame
        self.button_frame = tk.Frame(root, bg='black')
        self.button_frame.pack(side=tk.BOTTOM, pady=10)

        # Start and Stop Buttons for External Script
        self.start_button = tk.Button(self.button_frame, text="Start AI", command=self.start_external_script)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(self.button_frame, text="Stop AI", command=self.stop_external_script)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.pack_forget()

        # category_label = tk.Label(self.ai_geeks_frame, text="category", font=('Helvetica', 14, 'bold'))
        #        var = tk.BooleanVar(value=self.check_vars.get(event, event not in default_off_events))
        #        chk = tk.Checkbutton(self.ai_geeks_frame, text=event, variable=var)

        # for category, events in game_events.items():
        #    category_label = tk.Label(self.ai_geeks_frame, text=category, font=('Helvetica', 14, 'bold'))
        #    for event in events:
        #        var = tk.BooleanVar(value=self.check_vars.get(event, event not in default_off_events))
        #        chk = tk.Checkbutton(self.ai_geeks_frame, text=event, variable=var)
        #        self.check_vars[event] = var

        # Initialize fields with loaded data
        self.update_fields()

        # Process handle for subprocess
        self.process = None

        if self.release_version_arg:
            check_for_updates(self.release_version_arg)

    def toggle_tts_provider(self, provider, defaults=True):
        """
            Toggle the input options for each provider.
            Hide the inputs that are not needed, show the ones that are and set the default values.
            openai: model_name (default: tts-1), voice (default: nova), speed (default: 1.2)
            edge-tts: voice (default: en-GB-SoniaNeural), speed (default: 1.2)
            custom: model_endpoint (default: https://api.openai.com/v1), model_name (default: tts-1), api_key (default: ""), voice (default: nova), speed (default: 1.2)
        """
        if provider == 'openai':
            self.tts_model_name_label.grid()
            self.tts_model_name.grid()
            if defaults:
                self.tts_model_name.delete(0, tk.END)
                self.tts_model_name.insert(0, "tts-1")
            self.tts_endpoint_label.grid_remove()
            self.tts_endpoint.grid_remove()
            if defaults:
                self.tts_endpoint.delete(0, tk.END)
                self.tts_endpoint.insert(0, "https://api.openai.com/v1")
            self.tts_api_key_label.grid_remove()
            self.tts_api_key.grid_remove()
            if defaults:
                self.tts_api_key.delete(0, tk.END)
                self.tts_api_key.insert(0, "")
            self.tts_voice_label.grid()
            self.tts_voice.grid()
            if defaults:
                self.tts_voice.delete(0, tk.END)
                self.tts_voice.insert(0, "nova")
            self.tts_speed_label.grid()
            self.tts_speed.grid()
            if defaults:
                self.tts_speed.delete(0, tk.END)
                self.tts_speed.insert(0, "1.2")
        elif provider == 'edge-tts':
            self.tts_model_name_label.grid_remove()
            self.tts_model_name.grid_remove()
            if defaults:
                self.tts_model_name.delete(0, tk.END)
                self.tts_model_name.insert(0, "edge-tts")
            self.tts_endpoint_label.grid_remove()
            self.tts_endpoint.grid_remove()
            if defaults:
                self.tts_endpoint.delete(0, tk.END)
                self.tts_endpoint.insert(0, "")
            self.tts_api_key_label.grid_remove()
            self.tts_api_key.grid_remove()
            if defaults:
                self.tts_api_key.delete(0, tk.END)
                self.tts_api_key.insert(0, "")
            self.tts_voice_label.grid()
            self.tts_voice.grid()
            if defaults:
                self.tts_voice.delete(0, tk.END)
                self.tts_voice.insert(0, "en-GB-SoniaNeural")
            self.tts_speed_label.grid()
            self.tts_speed.grid()
            if defaults:
                self.tts_speed.delete(0, tk.END)
                self.tts_speed.insert(0, "1.2")
        elif provider == 'custom':
            self.tts_model_name_label.grid()
            self.tts_model_name.grid()
            if defaults:
                self.tts_model_name.delete(0, tk.END)
                self.tts_model_name.insert(0, "tts-1")
            self.tts_endpoint_label.grid()
            self.tts_endpoint.grid()
            if defaults:
                self.tts_endpoint.delete(0, tk.END)
                self.tts_endpoint.insert(0, "https://api.openai.com/v1")
            self.tts_api_key_label.grid()
            self.tts_api_key.grid()
            if defaults:
                self.tts_api_key.delete(0, tk.END)
                self.tts_api_key.insert(0, "")
            self.tts_voice_label.grid()
            self.tts_voice.grid()
            if defaults:
                self.tts_voice.delete(0, tk.END)
                self.tts_voice.insert(0, "nova")
            self.tts_speed_label.grid()
            self.tts_speed.grid()
            if defaults:
                self.tts_speed.delete(0, tk.END)
                self.tts_speed.insert(0, "1.2")
        elif provider == 'none':
            self.tts_model_name_label.grid_remove()
            self.tts_model_name.grid_remove()
            if defaults:
                self.tts_model_name.delete(0, tk.END)
                self.tts_model_name.insert(0, "none")
            self.tts_endpoint_label.grid_remove()
            self.tts_endpoint.grid_remove()
            if defaults:
                self.tts_endpoint.delete(0, tk.END)
                self.tts_endpoint.insert(0, "")
            self.tts_api_key_label.grid_remove()
            self.tts_api_key.grid_remove()
            if defaults:
                self.tts_api_key.delete(0, tk.END)
                self.tts_api_key.insert(0, "")
            self.tts_voice_label.grid_remove()
            self.tts_voice.grid_remove()
            if defaults:
                self.tts_voice.delete(0, tk.END)
                self.tts_voice.insert(0, "")
            self.tts_speed_label.grid_remove()
            self.tts_speed.grid_remove()
            if defaults:
                self.tts_speed.delete(0, tk.END)
                self.tts_speed.insert(0, "1.2")

    def toggle_stt_provider(self, provider, defaults=True):
        """
            Toggle the input options for each provider.
            Hide the inputs that are not needed, show the ones that are and set the default values.
            openai: model_name (default: whisper-1)
            custom: model_endpoint (default: https://api.openai.com/v1), model_name (default: whisper-1), api_key (default: "")
        """
        if provider == 'openai':
            self.stt_model_name_label.grid_remove()
            self.stt_model_name.grid_remove()
            if defaults:
                self.stt_model_name.delete(0, tk.END)
                self.stt_model_name.insert(0, "whisper-1")
            self.stt_endpoint_label.grid_remove()
            self.stt_endpoint.grid_remove()
            if defaults:
                self.stt_endpoint.delete(0, tk.END)
                self.stt_endpoint.insert(0, "https://api.openai.com/v1")
            self.stt_api_key_label.grid_remove()
            self.stt_api_key.grid_remove()
            if defaults:
                self.stt_api_key.delete(0, tk.END)
                self.stt_api_key.insert(0, "")
        elif provider == 'custom':
            self.stt_model_name_label.grid()
            self.stt_model_name.grid()
            if defaults:
                self.stt_model_name.delete(0, tk.END)
                self.stt_model_name.insert(0, "whisper-1")
            self.stt_endpoint_label.grid()
            self.stt_endpoint.grid()
            if defaults:
                self.stt_endpoint.delete(0, tk.END)
                self.stt_endpoint.insert(0, "https://api.openai.com/v1")
            self.stt_api_key_label.grid()
            self.stt_api_key.grid()
            if defaults:
                self.stt_api_key.delete(0, tk.END)
                self.stt_api_key.insert(0, "")

    def populate_game_events_frame(self, frame: tk.Frame, game_events: Dict[str, Dict[str, bool]]):
        category_values: Dict[str, Dict[str, tk.BooleanVar]] = {}
        rowCounter = 1
        for category, events in game_events.items():
            category_label = tk.Label(frame, text=category, font=('Helvetica', 14, 'bold'))
            category_label.grid(row=rowCounter, column=0, sticky=tk.W)
            category_values[category] = {}

            for event, state in events.items():
                var = tk.BooleanVar(value=state)
                chk = tk.Checkbutton(frame, text=event, variable=var)
                chk.grid(row=rowCounter, column=1, sticky=tk.W)
                category_values[category][event] = var
                rowCounter += 1
                if event == "ReceiveText":
                    self.react_to_text_local_var = tk.BooleanVar()
                    self.react_to_text_local_var.set(True)  # Default value
                    tk.Checkbutton(frame, text='React to local chat', variable=self.react_to_text_local_var).grid(row=rowCounter, column=1, sticky=tk.W, padx=(50,0))
                    rowCounter += 1
                    self.react_to_text_starsystem_var = tk.BooleanVar()
                    self.react_to_text_starsystem_var.set(True)  # Default value
                    tk.Checkbutton(frame, text='React to system chat', variable=self.react_to_text_starsystem_var).grid(row=rowCounter, column=1, sticky=tk.W, padx=(50,0))
                    rowCounter += 1
                    self.react_to_text_squadron_var = tk.BooleanVar()
                    self.react_to_text_squadron_var.set(True)  # Default value
                    tk.Checkbutton(frame, text='React to squadron chat', variable=self.react_to_text_squadron_var).grid(row=rowCounter, column=1, sticky=tk.W, padx=(50,0))
                    rowCounter += 1
                    self.react_to_text_npc_var = tk.BooleanVar()
                    self.react_to_text_npc_var.set(False)  # Default value
                    tk.Checkbutton(frame, text='React to NPC chatter', variable=self.react_to_text_npc_var).grid(row=rowCounter, column=1, sticky=tk.W, padx=(50,0))
                    rowCounter += 1

                if event == "ProspectedAsteroid":
                    tk.Label(frame, text="Name must include:").grid(row=rowCounter, column=1, sticky=tk.W)
                    self.react_to_material = tk.Entry(frame, width=35)
                    self.react_to_material.grid(row=rowCounter, column=1, padx=(115,0), pady=5)
                    rowCounter += 1

                if event == "InDanger":
                    self.react_to_danger_mining_var = tk.BooleanVar()
                    self.react_to_danger_mining_var.set(False)  # Default value
                    tk.Checkbutton(frame, text='React while mining', variable=self.react_to_danger_mining_var).grid(
                        row=rowCounter, column=1, sticky=tk.W, padx=(50, 0))
                    rowCounter += 1
                    self.react_to_danger_onfoot_var = tk.BooleanVar()
                    self.react_to_danger_onfoot_var.set(False)  # Default value
                    tk.Checkbutton(frame, text='React while on-foot', variable=self.react_to_danger_onfoot_var).grid(
                        row=rowCounter, column=1, sticky=tk.W, padx=(50, 0))
                    rowCounter += 1
                    self.react_to_danger_supercruise_var = tk.BooleanVar()
                    self.react_to_danger_supercruise_var.set(False)  # Default value
                    tk.Checkbutton(frame, text='React while in supercruise', variable=self.react_to_danger_supercruise_var).grid(
                        row=rowCounter, column=1, sticky=tk.W, padx=(50, 0))
                    rowCounter += 1


        return lambda: {category: {
            event: state.get() for event, state in events.items()
        } for category, events in category_values.items()}

    def on_closing(self):
        self.save_settings()
        root.destroy()

    def on_label_click(self, event):
        self.pptButton.config(text="Press a key...")
        self.controller_manager.listen_hotkey(self.on_hotkey_detected)

    def on_hotkey_detected(self, key: str):
        self.ptt_key = key
        self.update_label_text()

    def update_label_text(self):
        if self.ptt_key:
            self.pptButton.config(text=f"Key Binding: {self.ptt_key}")
        else:
            self.pptButton.config(text="Set Key Binding")

    def load_data(self) -> Config:
        return load_config()

    def check_settings(self):
        # Save current settings to the config
        self.save_settings()
        
        # Use the validation function from Config.py
        validation_result = check_and_upgrade_model(self.data)
        
        if validation_result.success:
            # Update the UI with any changes made during validation
            if validation_result.config['llm_model_name'] != self.llm_model_name.get():
                self.llm_model_name.delete(0, tk.END)
                self.llm_model_name.insert(0, validation_result.config['llm_model_name'])
            
            # Show upgrade message if available
            if validation_result.upgrade_message:
                messagebox.showinfo("Upgrade to GPT-4o-mini", validation_result.upgrade_message)
            
            # Show fallback message if available
            if validation_result.fallback_message:
                messagebox.showinfo("Fallback to GPT-3.5-Turbo", validation_result.fallback_message)
            
            # Update the config with validated values
            self.data = validation_result.config
            return True
        else:
            # Show error message
            if validation_result.error_message:
                messagebox.showerror("Model Validation Error", validation_result.error_message)
            return False

    def save_settings(self):
        self.data['commander_name'] = self.commander_name.get()
        self.data['character'] = self.character.get("1.0", tk.END).strip()
        self.data['api_key'] = self.api_key.get().strip()
        self.data['llm_model_name'] = self.llm_model_name.get()
        self.data['llm_endpoint'] = self.llm_endpoint.get()
        self.data['llm_api_key'] = self.llm_api_key.get()
        self.data['vision_model_name'] = self.vision_model_name.get()
        self.data['vision_endpoint'] = self.vision_endpoint.get()
        self.data['vision_api_key'] = self.vision_api_key.get()
        self.data['stt_provider'] = self.stt_provider_select_var.get()
        self.data['stt_model_name'] = self.stt_model_name.get()
        self.data['stt_endpoint'] = self.stt_endpoint.get()
        self.data['stt_api_key'] = self.stt_api_key.get()
        self.data['tts_provider'] = self.tts_provider_select_var.get()
        self.data['tts_model_name'] = self.tts_model_name.get()
        self.data['tts_endpoint'] = self.tts_endpoint.get()
        self.data['tts_api_key'] = self.tts_api_key.get()
        self.data['tools_var'] = self.tools_var.get()
        self.data['vision_var'] = self.vision_var.get()
        self.data['react_to_text_local_var'] = self.react_to_text_local_var.get()
        self.data['react_to_text_starsystem_var'] = self.react_to_text_starsystem_var.get()
        self.data['react_to_text_npc_var'] = self.react_to_text_npc_var.get()
        self.data['react_to_text_squadron_var'] = self.react_to_text_squadron_var.get()
        self.data['react_to_material'] = self.react_to_material.get()
        self.data['react_to_danger_mining_var'] = self.react_to_danger_mining_var.get()
        self.data['react_to_danger_onfoot_var'] = self.react_to_danger_onfoot_var.get()
        self.data['react_to_danger_supercruise_var'] = self.react_to_danger_supercruise_var.get()
        self.data['ptt_var'] = self.ptt_var.get()
        self.data['mute_during_response_var'] = self.mute_during_response_var.get()
        self.data['continue_conversation_var'] = self.continue_conversation_var.get()
        self.data['event_reaction_enabled_var'] = self.event_reaction_enabled_var.get()
        self.data['game_actions_var'] = self.game_actions_var.get()
        self.data['web_search_actions_var'] = self.web_search_actions_var.get()
        self.data['use_action_cache_var'] = self.use_action_cache_var.get()
        self.data['edcopilot'] = self.edcopilot_var.get()
        self.data['edcopilot_dominant'] = self.edcopilot_dominant_var.get()
        self.data['tts_voice'] = self.tts_voice.get()
        self.data['tts_speed'] = self.tts_speed.get()
        self.data['ptt_key'] = self.ptt_key
        self.data['input_device_name'] = self.input_device_name_var.get()
        self.data['output_device_name'] = self.output_device_name_var.get()
        self.data['game_events'] = self.game_events_save_cb()

        with open('config.json', 'w') as file:
            json.dump(self.data, file, indent=4)

        # messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")

    def update_fields(self):
        self.commander_name.insert(0, self.data['commander_name'])
        self.character.insert(tk.END, self.data['character'])
        self.api_key.insert(0, self.data['api_key'])
        self.llm_model_name.insert(0, self.data['llm_model_name'])
        self.llm_endpoint.insert(0, self.data['llm_endpoint'])
        self.llm_api_key.insert(0, self.data['llm_api_key'])
        self.vision_model_name.insert(0, self.data['vision_model_name'])
        self.vision_endpoint.insert(0, self.data['vision_endpoint'])
        self.vision_api_key.insert(0, self.data['vision_api_key'])
        self.stt_provider_select_var.set(self.data['stt_provider'])
        self.stt_model_name.insert(0, self.data['stt_model_name'])
        self.stt_endpoint.insert(0, self.data['stt_endpoint'])
        self.stt_api_key.insert(0, self.data['stt_api_key'])
        self.tts_provider_select_var.set(self.data['tts_provider'])
        self.tts_model_name.insert(0, self.data['tts_model_name'])
        self.tts_endpoint.insert(0, self.data['tts_endpoint'])
        self.tts_api_key.insert(0, self.data['tts_api_key'])
        self.tools_var.set(self.data['tools_var'])
        self.vision_var.set(self.data['vision_var'])
        self.react_to_text_local_var.set(self.data['react_to_text_local_var'])
        self.react_to_text_starsystem_var.set(self.data['react_to_text_starsystem_var'])
        self.react_to_text_npc_var.set(self.data['react_to_text_npc_var'])
        self.react_to_text_squadron_var.set(self.data['react_to_text_squadron_var'])
        self.react_to_material.insert(0, self.data['react_to_material'])
        self.react_to_danger_mining_var.set(self.data['react_to_danger_mining_var'])
        self.react_to_danger_onfoot_var.set(self.data['react_to_danger_onfoot_var'])
        self.react_to_danger_supercruise_var.set(self.data['react_to_danger_supercruise_var'])
        self.ptt_var.set(self.data['ptt_var'])
        self.mute_during_response_var.set(self.data['mute_during_response_var'])
        self.continue_conversation_var.set(self.data['continue_conversation_var'])
        self.event_reaction_enabled_var.set(self.data['event_reaction_enabled_var'])
        self.game_actions_var.set(self.data['game_actions_var'])
        self.web_search_actions_var.set(self.data['web_search_actions_var'])
        self.use_action_cache_var.set(self.data['use_action_cache_var'])
        self.edcopilot_var.set(self.data['edcopilot'])
        self.edcopilot_dominant_var.set(self.data['edcopilot_dominant'])
        self.tts_voice.insert(0, self.data['tts_voice'])
        self.tts_speed.insert(0, self.data['tts_speed'])
        self.ptt_key = self.data['ptt_key']
        self.input_device_name_var.set(self.data['input_device_name'] if self.data['input_device_name'] in get_input_device_names() else get_input_device_names()[0])
        self.output_device_name_var.set(self.data['output_device_name'] if self.data['output_device_name'] in get_output_device_names() else get_output_device_names()[0])

        self.update_label_text()
        self.toggle_ptt()
        self.toggle_vision()
        self.toggle_stt_provider(self.data['stt_provider'], defaults=False)
        self.toggle_tts_provider(self.data['tts_provider'], defaults=False)

    def toggle_ai_geeks_section(self):
        if self.ai_geeks_frame.winfo_viewable():
            self.ai_geeks_frame.grid_remove()
        else:
            self.ai_geeks_frame.grid()

            self.game_events_frame.grid_remove()
            self.third_party_frame.grid_remove()
            self.behavior_frame.grid_remove()

    def toggle_third_party_section(self):
        if self.third_party_frame.winfo_viewable():
            self.third_party_frame.grid_remove()
        else:
            self.third_party_frame.grid()

            self.ai_geeks_frame.grid_remove()
            self.game_events_frame.grid_remove()
            self.behavior_frame.grid_remove()

    def toggle_game_events_section(self):
        if self.game_events_frame.winfo_viewable():
            self.game_events_frame.grid_remove()
        else:
            self.game_events_frame.grid()

            self.ai_geeks_frame.grid_remove()
            self.third_party_frame.grid_remove()
            self.behavior_frame.grid_remove()

    def toggle_behavior_section(self):
        if self.behavior_frame.winfo_viewable():
            self.behavior_frame.grid_remove()
        else:
            self.behavior_frame.grid()

            self.ai_geeks_frame.grid_remove()
            self.game_events_frame.grid_remove()
            self.third_party_frame.grid_remove()

    def toggle_ptt(self):
        if self.ptt_var.get():
            self.pptButton.grid()
            self.muteResponseCheckbox.grid_remove()
        else:
            self.pptButton.grid_remove()
            self.muteResponseCheckbox.grid()

    def toggle_vision(self):
        if self.vision_var.get():
            self.vision_model_name.grid()
            self.vision_model_name_label.grid()
            self.vision_endpoint.grid()
            self.vision_endpoint_label.grid()
            self.vision_api_key.grid()
            self.vision_api_key_label.grid()
        else:
            self.vision_model_name.grid_remove()
            self.vision_model_name_label.grid_remove()
            self.vision_endpoint.grid_remove()
            self.vision_endpoint_label.grid_remove()
            self.vision_api_key.grid_remove()
            self.vision_api_key_label.grid_remove()

    def start_external_script(self):
        if not self.check_settings():
            return

        self.save_settings()
        self.debug_text.config(state=tk.NORMAL) # Make the text widget read-write
        self.debug_text.delete("1.0", tk.END)
        self.debug_text.focus_set()  # Give focus to the text widget
        self.print_to_debug('', "Starting COVAS:NEXT...\n")

        try:
            # create log file
            outlog = f"./logs/{int(time.time())}.out.log"
            os.makedirs(os.path.dirname(outlog), exist_ok=True)
            self.outlog_file = open(outlog, "w", encoding="utf-8")

            # Script execution
            startupinfo = None
            if platform.system() == 'Windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.process = subprocess.Popen(self.chat_command_arg.split(' ')+['--microphone', self.input_device_name_var.get()], startupinfo=startupinfo,
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
                                            universal_newlines=True, encoding='utf-8', shell=False, close_fds=True)

            self.debug_frame.pack()
            self.main_frame.pack_forget()
            self.stop_button.pack()
            self.start_button.pack_forget()  # Hide the start button

            # Read output in a separate thread
            self.thread_process_stdout = Thread(target=self.read_process_output, args=[self.process, self.outlog_file], daemon=True)
            self.thread_process_stdout.start()
            self.thread_process_stderr = Thread(target=self.read_process_error, args=[self.process, self.outlog_file], daemon=True)
            self.thread_process_stderr.start()
            
            # Send start signal to chat
            print(json.dumps({"type": "start", "oldUi": True}), file=self.process.stdin)

        except FileNotFoundError as e:
            print(e)
            self.debug_text.insert(tk.END, "Failed to start COVAS:NEXT: File not found.\n")
            self.debug_text.see(tk.END)
        except Exception as e:
            print(e, traceback.format_exc())
            self.debug_text.insert(tk.END, f"Failed to start COVAS:NEXT: {str(e)}\n")
            self.debug_text.see(tk.END)

    def strip_ansi_codes(self, s: str):
        return re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', s)
    
    @synchronized  # TODO useful but still not enough, segfaults on large amounts of text... probably needs to run in the main thread
    def print_to_debug(self, prefix: str, line: str):
        if not line.strip():
            return
        prefix = prefix.lower()
        prefixes = {
            "": "",
            "cmdr": "CMDR",
            "covas": "COVAS",
            "event": "Event",
            "action": "Action",
            "info": "Info",
            "debug": "Debug",
            "error": "Error",
        }
        colors = {
            "cmdr": "human",
            "covas": "ai",
            "event": "event",
            "action": "action",
            "info": "debug",
            "debug": "debug",
            "error": "error",
        }

        if prefix == "debug": # Debug is hidden in the UI, but can be found in the log file
            return
        
        # set the debug widget to read-write
        self.debug_text.config(state=tk.NORMAL)
        
        if prefix in prefixes and prefix in colors:
            self.debug_text.insert(tk.END, prefixes[prefix]+' ', colors[prefix])
        self.debug_text.insert(tk.END, line, "normal")
        
        self.debug_text.config(state=tk.DISABLED) # Make the text widget read-only
        self.debug_text.see(tk.END)  # Scroll to the end of the text widget

    def read_process_output(self, process: subprocess.Popen, outlog_file: typing.TextIO):
        while process and process.poll() is None:
            stdout_line = process.stdout.readline()
            stdout_line = self.strip_ansi_codes(stdout_line)
            outlog_file.write(stdout_line)
            outlog_file.flush()
            
            if stdout_line:
                try:
                    content = json.loads(stdout_line)
                    if content.get('type') == 'log':
                        self.print_to_debug(content['prefix'], content['message'])
                except json.JSONDecodeError:
                    self.print_to_debug('', stdout_line)

    def read_process_error(self, process: subprocess.Popen, outlog_file: typing.TextIO):
        while process and process.poll() is None:
            stderr_line = process.stderr.readline()
            stderr_line = self.strip_ansi_codes(stderr_line)
                
            if stderr_line:
                outlog_file.write(json.dumps({"type": "error", "timestamp": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "message": stderr_line})+'\n')
                outlog_file.flush()
                self.print_to_debug('error', stderr_line)

    def stop_external_script(self):
        if self.process:
            # self.send_signal(signal.SIGINT)  # Terminate the subprocess
            # self.process.wait()  # Terminate the subprocess
            self.process.kill()  # Terminate the subprocess (@TODO check why terminate doesn't work on linux, windows does the same for both anyway)
            self.process.wait()
            self.process = None
        if self.thread_process_stdout:
            if self.thread_process_stdout.is_alive():
                self.thread_process_stdout.join(timeout=1)  # Wait for the thread to complete
            self.thread_process_stdout = None
        if self.thread_process_stderr:
            if self.thread_process_stderr.is_alive():
                self.thread_process_stderr.join(timeout=1)  # Wait for the thread to complete
            self.thread_process_stderr = None
        self.print_to_debug('', "COVAS:NEXT stopped.\n")
        self.stop_button.pack_forget()
        self.debug_frame.pack_forget()
        self.main_frame.pack(padx=20, pady=20)
        self.start_button.pack()

    def shutdown(self):
        if self.process:
            self.process.terminate()  # Terminate the subprocess


if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = App(root)
        root.mainloop()
        app.shutdown()
    except Exception as e:
        print(e, traceback.format_exc())
        try:
            with open(f'crashlog{int(time.time())}.log', 'w') as file:
                file.write(str(e))
                file.write(traceback.format_exc())
            messagebox.showerror("Error", "An unexpected error occurred. Please check the crashlog for more information.")
        except:
            print("Failed to write crash log")
            messagebox.showerror("Error", "An unexpected error occurred. Unable to write crash log.")