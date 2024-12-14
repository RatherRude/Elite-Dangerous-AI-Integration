import time

from EDMesg.EDMesgClient import EDMesgClient

from .Logger import log
from typing import Optional
import os
from EDMesg.EDCoPilot import create_edcopilot_client
from EDMesg.CovasNext import (
    create_covasnext_provider,
    create_covasnext_client,
    CommanderSpoke,
    CovasReplied,
)


class EDCoPilot:
    def __init__(self, is_enabled: bool, is_edcopilot_dominant: bool):
        self.install_path = self.get_install_path()
        self.proc_id = self.get_process_id()
        self.is_enabled = is_enabled and self.is_installed()
        self.client = create_edcopilot_client() if self.is_enabled else None
        self.provider = create_covasnext_provider() if self.is_enabled else None
        self.is_edcopilot_dominant = is_edcopilot_dominant

        log("info", f"EDCoPilot is installed: {self.is_installed()}")
        log("info", f"EDCoPilot is running: {self.is_running()}")
        log("info", f"EDCoPilot is enabled: {self.is_enabled}")
        log("info", f"EDCoPilot is dominant: {self.is_edcopilot_dominant}")

    def is_installed(self) -> bool:
        """Check if EDCoPilot is installed"""
        return self.install_path is not None

    def is_running(self) -> bool:
        """Check if EDCoPilot is running"""
        if self.proc_id:
            import psutil

            if psutil.pid_exists(self.proc_id):
                return True

        self.proc_id = self.get_process_id()
        return self.proc_id is not None

    def get_install_path(self) -> (str | None):
        """Check the windows registry for COMPUTER / HKEY_CURRENT_USER / SOFTWARE / EDCoPilot"""
        try:
            import winreg

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "SOFTWARE\\EDCoPilot")
            value, _ = winreg.QueryValueEx(key, "EDCoPilotLib")
            winreg.CloseKey(key)
            return value
        except Exception:
            return None

    def get_process_id(self) -> (int | None):
        """Check if EDCoPilot is running"""
        try:
            import psutil

            for proc in psutil.process_iter():
                if "EDCoPilot" in proc.name():
                    return proc.pid
            return None
        except Exception:
            return None

    def output_commander(self, message: str):
        """send PrintThis: "message" request"""
        if self.provider:
            return self.provider.publish(
                CommanderSpoke(muted=self.is_edcopilot_dominant, text=message)
            )

    def output_covas(self, message: str, reasons: list[str]):
        """send SpeakThis: "message" request"""
        if self.provider:
            return self.provider.publish(
                CovasReplied(
                    muted=self.is_edcopilot_dominant, text=message, reasons=reasons
                )
            )


if __name__ == "__main__":
    client = create_covasnext_client()
    while True:
        while not client.pending_events.empty():
            print("incoming event")
            print(client.pending_events.get())
        time.sleep(0.1)
