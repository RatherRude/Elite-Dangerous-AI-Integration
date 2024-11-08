from io import SEEK_END
import json
from os import listdir
from os.path import join, isfile, getmtime
from queue import Queue
from sys import platform
import threading
from time import sleep
import traceback
from typing import TypedDict

from .Logger import log

class JournalEntry(TypedDict):
    timestamp: str
    event: str

class EDJournal:
    def __init__(self, game_events: dict[str, dict[str, bool]]):
        self.events: Queue[JournalEntry] = Queue()
        
        self.historic_events: list[JournalEntry] = []
        self.load_timestamp: str = '1970-01-01T00:00:00Z'
        self.load_history()
        
        thread = threading.Thread(target=self._reading_loop)
        thread.daemon = True
        thread.start()
        
    def load_history(self):
        latest_log = self.get_latest_log()
        if latest_log is None:
            return

        with open(latest_log, 'r') as f:
            # read the file from start to finish, line by line
            for line in f:
                try:
                    entry = json.loads(line)
                    self.historic_events.append(entry)
                    self.load_timestamp = entry.get("timestamp")
                except json.JSONDecodeError:
                    continue

    def _reading_thread(self):
        backoff = 1
        while True:
            try: 
                self._reading_loop()
            except Exception as e:
                log('error', 'An error occurred during journal processing', e, traceback.format_exc())
                sleep(backoff)
                log('info', 'Attempting to restart journal processing after failure')
                backoff *= 2
    
    def _reading_loop(self):
        while True:
            latest_log = self.get_latest_log()
            if latest_log is None:
                sleep(1)
                continue
            with open(latest_log, 'r') as f:
                while True: # TODO we need to check if there is a new file
                    line = f.readline() # this is blocking, so we need to check if the file has changed somehow
                    try:
                        entry = json.loads(line)  # pyright: ignore[reportAny]
                        if entry.get("timestamp") <= self.load_timestamp:
                            continue
                        self.events.put(entry)  # pyright: ignore[reportAny]
                    except json.JSONDecodeError:
                        sleep(0.1)
                        continue

    def get_latest_log(self):
        """Returns the full path of the latest (most recent) elite log file (journal) from specified path"""
        if platform != "win32":
            path_logs = './linux_ed'
        else:
            from . import WindowsKnownPaths as winpaths
            saved_games = winpaths.get_path(winpaths.FOLDERID.SavedGames, winpaths.UserHandle.current) 
            if saved_games is None:
                raise FileNotFoundError("Saved Games folder not found")
            path_logs = saved_games + "\\Frontier Developments\\Elite Dangerous"
        try:
            list_of_logs = [join(path_logs, f) for f in listdir(path_logs) if
                            isfile(join(path_logs, f)) and f.startswith('Journal.')]
        except:
            return None
        if not list_of_logs:
            return None
        latest_log = max(list_of_logs, key=getmtime)
        return latest_log



def main():
    jn = EDJournal({})
    while True:
        sleep(0.1)
        while not jn.events.empty():
            print(jn.events.get())


if __name__ == "__main__":
    main()
