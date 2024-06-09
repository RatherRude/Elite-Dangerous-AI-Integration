import tkinter as tk
from tkinter import messagebox
import json
import subprocess
from pathlib import Path
from threading import Thread
from queue import Queue

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Elite Dangerous AI Integration")

        self.process = None
        self.output_queue = Queue()
        self.read_thread = None

        # Load initial data from JSON file if exists
        self.data = self.load_data()

        # Background Image
        try:
            background_image = tk.PhotoImage(file="screen/EDAI_logo.png")
            self.background_label = tk.Label(root, image=background_image)
            self.background_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.background_label.image = background_image
        except tk.TclError as e:
            print(f"Failed to load background image: {e}")

        # Main Frame (for other widgets)
        self.main_frame = tk.Frame(root, bd=1)  # White background for visibility
        self.main_frame.pack(padx=20, pady=20)

        # Commander Name (Small Input)
        tk.Label(self.main_frame, text="Commander Name:").grid(row=0, column=0, sticky=tk.W)
        self.commander_name = tk.Entry(self.main_frame, width=50)
        self.commander_name.grid(row=0, column=1, padx=10, pady=5)

        # Character (Multi-line Input)
        tk.Label(self.main_frame, text="AI Character:").grid(row=1, column=0, sticky=tk.W)
        self.character = tk.Text(self.main_frame, width=80, height=10)
        self.character.grid(row=1, column=1, padx=10, pady=5)

        # API Key (Secure Entry) - Placed above the first button
        tk.Label(self.main_frame, text="OpenAI API Key:").grid(row=2, column=0, sticky=tk.W)
        self.api_key = tk.Entry(self.main_frame, show='*', width=50)  # Show '*' to indicate a secure entry
        self.api_key.grid(row=2, column=1, padx=10, pady=5)

        # AI Geeks Section (Initially hidden)
        self.ai_geeks_frame = tk.Frame(self.main_frame, bg='lightgrey', bd=1)
        self.ai_geeks_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky=tk.W)
        self.ai_geeks_frame.grid_remove()  # Initially hide

        # Disclaimer
        tk.Label(self.ai_geeks_frame, text="None of the AI Geek options are required.").grid(row=0, column=0, columnspan=2, sticky=tk.W)

        # LLM Model Name
        tk.Label(self.ai_geeks_frame, text="LLM Model Name:").grid(row=1, column=0, sticky=tk.W)
        self.llm_model_name = tk.Entry(self.ai_geeks_frame, width=50)
        self.llm_model_name.grid(row=1, column=1, padx=10, pady=5)

        ## Alternative LLM (Checkbox)
        #self.alternative_llm_var = tk.BooleanVar()
        #self.alternative_llm_var.set(False)  # Default value
        #self.alternative_llm_checkbox = tk.Checkbutton(self.ai_geeks_frame, text="Alternative LLM", variable=self.alternative_llm_var)
        #self.alternative_llm_checkbox.grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)

        # LLM Endpoint
        tk.Label(self.ai_geeks_frame, text="LLM Endpoint:").grid(row=3, column=0, sticky=tk.W)
        self.llm_endpoint = tk.Entry(self.ai_geeks_frame, width=50)
        self.llm_endpoint.grid(row=3, column=1, padx=10, pady=5)

        # LLM API Key
        tk.Label(self.ai_geeks_frame, text="LLM API Key:").grid(row=4, column=0, sticky=tk.W)
        self.llm_api_key = tk.Entry(self.ai_geeks_frame, show='*', width=50)
        self.llm_api_key.grid(row=4, column=1, padx=10, pady=5)

        # Alternative STT (Checkbox)
        self.alternative_stt_var = tk.BooleanVar()
        self.alternative_stt_var.set(False)  # Default value
        self.alternative_stt_checkbox = tk.Checkbutton(self.ai_geeks_frame, text="Local STT(whisper-medium)", variable=self.alternative_stt_var)
        self.alternative_stt_checkbox.grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)

        ## STT Endpoint
        #tk.Label(self.ai_geeks_frame, text="STT Endpoint:").grid(row=9, column=0, sticky=tk.W)
        #self.stt_endpoint = tk.Entry(self.ai_geeks_frame, width=50)
        #self.stt_endpoint.grid(row=6, column=1, padx=10, pady=5)

        ## STT API Key
        #tk.Label(self.ai_geeks_frame, text="STT API Key:").grid(row=10, column=0, sticky=tk.W)
        #self.stt_api_key = tk.Entry(self.ai_geeks_frame, show='*', width=50)
        #self.stt_api_key.grid(row=7, column=1, padx=10, pady=5)

        # Alternative TTS (Checkbox)
        self.alternative_tts_var = tk.BooleanVar()
        self.alternative_tts_var.set(False)  # Default value
        self.alternative_tts_checkbox = tk.Checkbutton(self.ai_geeks_frame, text="Local TTS (OS Voices)", variable=self.alternative_tts_var)
        self.alternative_tts_checkbox.grid(row=8, column=0, sticky=tk.W, padx=10, pady=5)

        ## TTS Endpoint
        #tk.Label(self.ai_geeks_frame, text="TTS Endpoint:").grid(row=12, column=0, sticky=tk.W)
        #self.tts_endpoint = tk.Entry(self.ai_geeks_frame, width=50)
        #self.tts_endpoint.grid(row=9, column=1, padx=10, pady=5)

        ## TTS API Key
        #tk.Label(self.ai_geeks_frame, text="TTS API Key:").grid(row=13, column=0, sticky=tk.W)
        #self.tts_api_key = tk.Entry(self.ai_geeks_frame, show='*', width=50)
        #self.tts_api_key.grid(row=10, column=1, padx=10, pady=5)

        ## Alternative Vision Model (Checkbox)
        #self.alternative_vision_var = tk.BooleanVar()
        #self.alternative_vision_var.set(False)  # Default value
        #self.alternative_vision_checkbox = tk.Checkbutton(self.ai_geeks_frame, text="Alternative Vision Model (Coming soon™)", variable=self.alternative_vision_var)
        #self.alternative_vision_checkbox.grid(row=11, column=0, sticky=tk.W, padx=10, pady=5)
#
        ## Vision Model Endpoint
        #tk.Label(self.ai_geeks_frame, text="Vision Model Endpoint:").grid(row=6, column=0, sticky=tk.W)
        #self.vision_model_endpoint = tk.Entry(self.ai_geeks_frame, width=50)
        #self.vision_model_endpoint.grid(row=12, column=1, padx=10, pady=5)
#
        ## Vision Model API Key
        #tk.Label(self.ai_geeks_frame, text="Vision Model API Key:").grid(row=7, column=0, sticky=tk.W)
        #self.vision_model_api_key = tk.Entry(self.ai_geeks_frame, show='*', width=50)
        #self.vision_model_api_key.grid(row=13, column=1, padx=10, pady=5)

        # Save Button - Placed below the first button
        self.save_button = tk.Button(self.main_frame, text="Save Settings", command=self.save_settings)
        self.save_button.grid(row=5, column=0, columnspan=2, pady=10)

        # Toggle Section Button
        self.toggle_section_button = tk.Button(self.main_frame, text="Toggle AI Geeks Section", command=self.toggle_ai_geeks_section)
        self.toggle_section_button.grid(row=3, column=0, columnspan=2, pady=10)

        # Debug Frame and Text Widget
        self.debug_frame = tk.Frame(root, bg='white', bd=1)  # White background for visibility
        self.debug_frame.pack(side=tk.TOP, padx=20, pady=20)

        tk.Label(self.debug_frame, text="Debug Output:").pack(anchor=tk.W)
        self.debug_text = tk.Text(self.debug_frame, width=100, height=25)
        self.debug_text.tag_configure("normal", foreground="black")
        self.debug_text.tag_configure("human", foreground="red")
        self.debug_text.tag_configure("ai", foreground="blue")
        self.debug_text.tag_configure("action", foreground="yellow")
        self.debug_text.pack(side=tk.LEFT, padx=10, pady=10)

        self.debug_frame.pack_forget()

        # Button Frame
        self.button_frame = tk.Frame(root)
        self.button_frame.pack(side=tk.BOTTOM, pady=10)

        # Hide Settings Button
        self.hide_settings_button = tk.Button(self.button_frame, text="Hide Settings", command=self.toggle_settings)
        self.hide_settings_button.pack(side=tk.LEFT, padx=5)

        # Start and Stop Buttons for External Script
        self.start_button = tk.Button(self.button_frame, text="Start AI", command=self.start_external_script)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(self.button_frame, text="Stop AI", command=self.stop_external_script)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.pack_forget()

        # Initialize fields with loaded data
        self.update_fields()

        # Process handle for subprocess
        self.process = None

    def toggle_settings(self):
        if self.main_frame.winfo_ismapped():
            self.main_frame.pack_forget()
            self.hide_settings_button.config(text="Show Settings")
        else:
            self.main_frame.pack(padx=20, pady=20)
            self.hide_settings_button.config(text="Hide Settings")

    def load_data(self):
        try:
            with open('config.json', 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            data = {
                'commander_name': "",
                'character':
                "You will be addressed as 'Computer'. Acknowledge given orders. \n" +
                 "You possess extensive knowledge and can provide detailed and accurate information on a wide range of topics, " +
                 "including galactic navigation, ship status, the current system, and more. \n" +
                 "Do not inform about my ship status and my location unless it's relevant or requested by me. \n" +
                 "Guide and support me with witty and intelligent commentary. \n" +
                 "Provide clear mission briefings, sarcastic comments, and humorous observations. Answer within 3 sentences. \n" +
                 "Advance the narrative involving bounty hunting. \n" +
                 "I am a broke bounty hunter who can barely pay the fuel.",
                'api_key': "",
                'alternative_stt_var': False,
                'alternative_tts_var': False,
                'llm_model_name': "gpt-4o",
                'llm_endpoint': "",
                'llm_api_key': ""
                #'vision_model_endpoint': "",
                #'vision_model_api_key': "",
                #'stt_endpoint': "",
                #'stt_api_key': "",
                #'tts_endpoint': "",
                #'tts_api_key': ""
            }
        return data

    def save_settings(self):
        self.data['commander_name'] = self.commander_name.get()
        self.data['character'] = self.character.get("1.0", tk.END).strip()
        self.data['api_key'] = self.api_key.get()
        self.data['llm_model_name'] = self.llm_model_name.get()
        self.data['llm_endpoint'] = self.llm_endpoint.get()
        self.data['llm_api_key'] = self.llm_api_key.get()
        #self.data['vision_model_endpoint'] = self.vision_model_endpoint.get()
        #self.data['vision_model_api_key'] = self.vision_model_api_key.get()
        #self.data['stt_endpoint'] = self.stt_endpoint.get()
        #self.data['stt_api_key'] = self.stt_api_key.get()
        #self.data['tts_endpoint'] = self.tts_endpoint.get()
        #self.data['tts_api_key'] = self.tts_api_key.get()
        self.data['alternative_stt_var'] = self.alternative_stt_var.get()
        self.data['alternative_tts_var'] = self.alternative_tts_var.get()

        with open('config.json', 'w') as file:
            json.dump(self.data, file, indent=4)

        #messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")

    def update_fields(self):
        self.commander_name.insert(0, self.data['commander_name'])
        self.character.insert(tk.END, self.data['character'])
        self.api_key.insert(0, self.data['api_key'])
        self.llm_model_name.insert(0, self.data['llm_model_name'])
        self.llm_endpoint.insert(0, self.data['llm_endpoint'])
        self.llm_api_key.insert(0, self.data['llm_api_key'])
        #self.vision_model_endpoint.insert(0, self.data['vision_model_endpoint'])
        #self.vision_model_api_key.insert(0, self.data['vision_model_api_key'])
        #self.stt_endpoint.insert(0, self.data['stt_endpoint'])
        #self.stt_api_key.insert(0, self.data['stt_api_key'])
        #self.tts_endpoint.insert(0, self.data['tts_endpoint'])
        #self.tts_api_key.insert(0, self.data['tts_api_key'])
        self.alternative_stt_var.set(self.data['alternative_stt_var'])
        self.alternative_tts_var.set(self.data['alternative_tts_var'])

    def toggle_ai_geeks_section(self):
        if self.ai_geeks_frame.winfo_viewable():
            self.ai_geeks_frame.grid_remove()
            self.toggle_section_button.config(text="Show AI Geeks Section")
        else:
            self.ai_geeks_frame.grid()
            self.toggle_section_button.config(text="Hide AI Geeks Section")

    def start_external_script(self):
        self.debug_text.delete('1.0', tk.END)
        self.debug_text.insert(tk.END, "Starting Elite Dangerous AI Integration...\n", "normal")
        #self.debug_text.update_idletasks()

        try:
            # Example script execution
            self.process = subprocess.Popen(['python', 'Chat.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
            self.debug_frame.pack()
            if self.main_frame.winfo_ismapped():
                self.main_frame.pack_forget()
                self.hide_settings_button.config(text="Show Settings")
            self.stop_button.pack()
            self.start_button.pack_forget()  # Hide the start button

            # Read output in a separate thread
            self.thread = Thread(target=self.read_process_output)
            self.thread.start()

        except FileNotFoundError:
            self.debug_text.insert(tk.END, "Failed to start Elite Dangerous AI Integration: File not found.\n")
            self.debug_text.see(tk.END)
        except Exception as e:
            self.debug_text.insert(tk.END, f"Failed to start Elite Dangerous AI Integration: {str(e)}\n")
            self.debug_text.see(tk.END)

    def read_process_output(self):
        while True:
            stdout_line = self.process.stdout.readline()
            if stdout_line:
                if stdout_line.startswith("CMDR"):
                    self.debug_text.insert(tk.END, stdout_line[:4], "human")
                    self.debug_text.insert(tk.END, stdout_line[4:], "normal")
                elif stdout_line.startswith("AI"):
                    self.debug_text.insert(tk.END, stdout_line[:2], "ai")
                    self.debug_text.insert(tk.END, stdout_line[2:], "normal")
                elif stdout_line.startswith("ACTION"):
                    self.debug_text.insert(tk.END, stdout_line[:6], "action")
                    self.debug_text.insert(tk.END, stdout_line[6:], "normal")
                else:
                    self.debug_text.insert(tk.END, stdout_line, "normal")

                self.debug_text.see(tk.END)  # Scroll to the end of the text widget
            else:
                break  # No more output from subprocess

    def stop_external_script(self):
        if self.process:
            self.process.terminate()  # Terminate the subprocess
            self.process = None
        if self.thread:
            self.thread.join()  # Wait for the thread to complete
            self.thread = None
        self.debug_text.insert(tk.END, "Elite Dangerous AI Integration stopped.\n")
        self.debug_text.see(tk.END)
        self.stop_button.pack_forget()
        self.debug_frame.pack_forget()
        if not self.main_frame.winfo_ismapped():
            self.main_frame.pack(padx=20, pady=20)
            self.hide_settings_button.config(text="Hide Settings")
        self.start_button.pack()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()