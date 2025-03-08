import io
import json
from os import listdir
import os
from os.path import join, isfile, getmtime
from queue import Queue
import threading
from time import sleep
import traceback
from typing import TypedDict

from .Logger import log

class JournalEntry(TypedDict):
    id: str
    timestamp: str
    event: str

class EDJournal:
    def __init__(self, logs_path: str):
        self.events: Queue[JournalEntry] = Queue()
        self.logs_path: str = logs_path
        
        self.historic_events: list[JournalEntry] = []
        self.load_history()
        
        thread = threading.Thread(target=self._reading_loop)
        thread.daemon = True
        thread.start()
    
    def get_event_id(self, log: str, file_index: int) -> str:
        return log.replace('\\', '/').split('/')[-1] + '.' + str(file_index).zfill(6)
        
    def augment_event(self, entry: JournalEntry) -> JournalEntry:
        if entry.get('event') == "NavRoute":
            entry = self.augment_event_from_file(entry, "NavRoute.json")
        if entry.get('event') == "Market":
            entry = self.augment_event_from_file(entry, "Market.json")
        if entry.get('event') == "Outfitting":
            entry = self.augment_event_from_file(entry, "Outfitting.json")
        if entry.get('event') == "Shipyard":
            entry = self.augment_event_from_file(entry, "Shipyard.json")
        if entry.get('event') == "Cargo":
            entry = self.augment_event_from_file(entry, "Cargo.json")
        if entry.get('event') == "ModuleInfo":
            entry = self.augment_event_from_file(entry, "ModulesInfo.json")
        if entry.get('event') == "ShipLocker":
            entry = self.augment_event_from_file(entry, "ShipLocker.json")
        if entry.get('event') == "Backpack":
            entry = self.augment_event_from_file(entry, "Backpack.json")
        return entry

    def augment_event_from_file(self, entry: JournalEntry, filename: str) -> JournalEntry:
        file_path = join(self.logs_path, filename)

        try:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)
            except json.JSONDecodeError:
                sleep(0.1)
                with open(file_path, 'r', encoding='utf-8') as file:
                    data = json.load(file)

            if data.get("timestamp") == entry.get("timestamp"):
                return {**entry, **data}
        except Exception as e:
            log('error', f"Failed to augment event {entry.get('event')} with data from {filename}", e, traceback.format_exc())
        return entry
        
    def load_history(self):
        latest_log = self.get_latest_log()
        if latest_log is None:
            return

        with open(latest_log, 'r', encoding='utf-8') as f:
            file_index = 0
            # read the file from start to finish, line by line
            for line in f:
                #log("debug", f"Loading history from {latest_log} at line {file_index}")
                file_index += 1
                try:
                    entry: JournalEntry = json.loads(line)
                    entry['id'] = self.get_event_id(latest_log, file_index)
                    entry = self.augment_event(entry)

                    self.historic_events.append(entry)
                except json.JSONDecodeError:
                    continue
            log("debug", f"Loaded {len(self.historic_events)} historicevents from {latest_log}")
                
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
            with open(latest_log, 'r', encoding='utf-8') as f:
                file_index = 0
                while True:
                    line = f.readline() # this is blocking, so we need to check if the file has changed somehow
                    if not line:
                        if latest_log != self.get_latest_log():
                            break
                        sleep(0.01)
                        continue

                    file_index += 1 
                    try:
                        entry: JournalEntry = json.loads(line)
                        entry['id'] = self.get_event_id(latest_log, file_index)
                        entry = self.augment_event(entry)
                    
                        if self.historic_events and self.historic_events[-1].get('id') >= entry.get('id'):
                            continue
                        self.events.put(entry)
                    except json.JSONDecodeError:
                        sleep(0.1)
                        continue
            sleep(0.01)

    def get_latest_log(self):
        try:
            list_of_logs = [join(self.logs_path, f) for f in listdir(self.logs_path) if
                            isfile(join(self.logs_path, f)) and f.startswith('Journal.')]
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
