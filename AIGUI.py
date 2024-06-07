import tkinter as tk
from tkinter import messagebox
import json
import subprocess
import sys
import time

from threading import Thread
from queue import Queue, Empty

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
        tk.Label(self.ai_geeks_frame, text="None of the AI Geek options are required.").grid(row=10, column=0, sticky=tk.W)

        # OpenRouter (Checkbox)
        self.openrouter_var = tk.BooleanVar()
        self.openrouter_var.set(False)  # Default value
        self.openrouter_checkbox = tk.Checkbutton(self.ai_geeks_frame, text="OpenRouter", variable=self.openrouter_var)
        self.openrouter_checkbox.grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

        # Model Name (Small Input)
        tk.Label(self.ai_geeks_frame, text="Model Name:").grid(row=1, column=0, sticky=tk.W)
        self.model_name = tk.Entry(self.ai_geeks_frame, width=50)
        self.model_name.grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)

        # Alternative Endpoint (Small Input)
        self.local_model_var = tk.BooleanVar()
        self.local_model_var.set(False)  # Default value
        self.local_model_checkbox = tk.Checkbutton(self.ai_geeks_frame, text="Local LLM(coming soon)", variable=self.local_model_var)
        self.local_model_checkbox.grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        #tk.Label(self.ai_geeks_frame, text="Alternative Endpoint").grid(row=2, column=0, sticky=tk.W)
        self.alternative_endpoint = tk.Entry(self.ai_geeks_frame, width=50)
        self.alternative_endpoint.grid(row=2, column=1, padx=10, pady=5)

        # Local STT (Checkbox)
        self.local_stt_var = tk.BooleanVar()
        self.local_stt_var.set(False)  # Default value
        self.local_stt_checkbox = tk.Checkbutton(self.ai_geeks_frame, text="Local STT(coming soon)", variable=self.local_stt_var)
        self.local_stt_checkbox.grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)

        # Local TTS (Checkbox)
        self.local_tts_var = tk.BooleanVar()
        self.local_tts_var.set(False)  # Default value
        self.local_tts_checkbox = tk.Checkbutton(self.ai_geeks_frame, text="Local TTS(coming soon)", variable=self.local_tts_var)
        self.local_tts_checkbox.grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)

        # Save Button - Placed below the first button
        self.save_button = tk.Button(self.main_frame, text="Save Settings", command=self.save_settings)
        self.save_button.grid(row=5, column=0, columnspan=2, pady=10)

        # Toggle Section Button
        self.toggle_section_button = tk.Button(self.main_frame, text="Toggle AI Geeks Section", command=self.toggle_ai_geeks_section)
        self.toggle_section_button.grid(row=3, column=0, columnspan=2, pady=10)

        # Debug Frame and Text Widget
        self.debug_frame = tk.Frame(root, bg='white', bd=1)  # White background for visibility
        self.debug_frame.pack(side=tk.BOTTOM, padx=20, pady=20)

        tk.Label(self.debug_frame, text="Debug Log:", bg='white').pack()
        self.debug_text = tk.Text(self.debug_frame, width=80, height=10)
        self.debug_text.tag_configure("normal", foreground="black")
        self.debug_text.tag_configure("human", foreground="red")
        self.debug_text.tag_configure("ai", foreground="blue")
        self.debug_text.tag_configure("action", foreground="yellow")
        self.debug_text.pack(padx=10, pady=10)

        # Start and Stop Buttons for External Script
        self.start_button = tk.Button(root, text="Start AI", command=self.start_external_script)
        self.start_button.pack()

        self.stop_button = tk.Button(root, text="Stop AI", command=self.stop_external_script)
        self.stop_button.pack_forget()

        # Initialize fields with loaded data
        self.update_fields()

        # Process handle for subprocess
        self.process = None

    def load_data(self):
        try:
            with open('config.json', 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            data = {
                'commander_name': "",
                'character':
                "You will be addressed as 'Computer'. Acknowledge given orders. \n" +
                 "You possess extensive knowledge and can provide detailed and accurate information on a wide range of topics, \n" +
                 "including galactic navigation, ship status, the current system, and more. \n" +
                 "Do not inform about my ship status and my location unless it's relevant or requested by me. \n" +
                 "Guide and support me with witty and intelligent commentary. \n" +
                 "Provide clear mission briefings, sarcastic comments, and humorous observations. Answer within 3 sentences. \n" +
                 "Advance the narrative involving bounty hunting. \n" +
                 "I am a broke bounty hunter who can barely pay the fuel.",
                'openrouter': False,
                'api_key': "",
                'model_name': "gpt-4o",
                'alternative_endpoint': "",
                'local_model': False,
                'local_stt': False,
                'local_tts': False
            }
        return data

    def save_settings(self):
        self.data['commander_name'] = self.commander_name.get()
        self.data['character'] = self.character.get("1.0", tk.END).strip()
        self.data['openrouter'] = self.openrouter_var.get()
        self.data['api_key'] = self.api_key.get()
        self.data['model_name'] = self.model_name.get()
        self.data['alternative_endpoint'] = self.alternative_endpoint.get()
        self.data['local_model'] = self.local_model_var.get()
        self.data['local_stt'] = self.local_stt_var.get()
        self.data['local_tts'] = self.local_tts_var.get()

        with open('config.json', 'w') as file:
            json.dump(self.data, file, indent=4)

        #messagebox.showinfo("Settings Saved", "Settings have been saved successfully.")

    def update_fields(self):
        self.commander_name.insert(0, self.data['commander_name'])
        self.character.insert(tk.END, self.data['character'])
        self.api_key.insert(0, self.data['api_key'])
        self.openrouter_var.set(self.data['openrouter'])
        self.model_name.insert(0, self.data['model_name'])
        self.alternative_endpoint.insert(0, self.data['alternative_endpoint'])
        self.local_model_var.set(self.data['local_model'])
        self.local_stt_var.set(self.data['local_stt'])
        self.local_tts_var.set(self.data['local_tts'])

    def toggle_ai_geeks_section(self):
        if self.ai_geeks_frame.winfo_viewable():
            self.ai_geeks_frame.grid_remove()
            self.toggle_section_button.config(text="Show AI Geeks Section")
        else:
            self.ai_geeks_frame.grid()
            self.toggle_section_button.config(text="Hide AI Geeks Section")

    def start_external_script(self):
        self.debug_text.insert(tk.END, "Starting external script...\n")
        #self.debug_text.update_idletasks()

        try:
            # Example script execution
            self.process = subprocess.Popen(['python', 'Chat.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, universal_newlines=True)
            self.stop_button.pack()
            self.start_button.pack_forget()  # Hide the start button

            # Read output in a separate thread
            self.thread = Thread(target=self.read_process_output)
            self.thread.start()

        except FileNotFoundError:
            self.debug_text.insert(tk.END, "Failed to start external script: File not found.\n")
            self.debug_text.see(tk.END)
        except Exception as e:
            self.debug_text.insert(tk.END, f"Failed to start external script: {str(e)}\n")
            self.debug_text.see(tk.END)

    def read_process_output(self):
        while True:
            stdout_line = self.process.stdout.readline()
            if stdout_line:
                if stdout_line.startswith("CMDR"):
                    self.debug_text.insert(tk.END, stdout_line[:6], "human")
                    self.debug_text.insert(tk.END, stdout_line[6:], "normal")
                elif stdout_line.startswith("AI"):
                    self.debug_text.insert(tk.END, stdout_line, "ai")
                elif stdout_line.startswith("ACTION"):
                    self.debug_text.insert(tk.END, stdout_line, "action")
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
            self.debug_text.insert(tk.END, "External script stopped.\n")
            self.debug_text.see(tk.END)
            self.stop_button.pack_forget()
            self.start_button.pack()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()