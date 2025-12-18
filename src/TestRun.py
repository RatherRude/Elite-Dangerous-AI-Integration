import copy
import sys
from time import sleep
from typing import Any, cast, final
import os
import threading
import json
import io
import traceback
from datetime import datetime

from Chat import Chat

from lib.Logger import log
from lib.Config import (
    load_config,
)
from lib.PluginManager import PluginManager

if __name__ == "__main__":
    try:
        print(json.dumps({"type": "ready"})+'\n')
        # Wait for start signal on stdin
        config = load_config()
        print(json.dumps({"type": "config", "config": config})+'\n', flush=True)
        

        # Load plugins.
        log('debug', "Loading plugins...")
        plugin_manager = PluginManager(config=config)
        plugin_manager.load_plugins()
        log('debug', "Registering plugin settings for the UI...")
        plugin_manager.register_settings()
        plugin_manager.on_settings_changed(config)
        print(json.dumps({"type": "start"})+'\n', flush=True)
        

        chat = Chat(config, plugin_manager)
        
        def run_chat(chat: Chat):
            log("debug", "Running chat...")
            chat.run()
        # run chat in a thread
        chat_thread = threading.Thread(target=run_chat, args=(chat,), daemon=True)
        chat_thread.start()
        
        # Keep the main thread alive to listen for stdin input
        
        sleep(10)
        chat.submit_input("Hello, Assistant!")
        sleep(10)
        exit()
        
    except Exception as e:
        log("error", e, traceback.format_exc())
        sys.exit(1)
