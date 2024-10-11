import time

from .Logger import log
from typing import Optional
import os

class EDCoPilot:
    def __init__(self, is_enabled: bool):
        self.install_path = self.get_install_path()
        self.proc_id = self.get_process_id()
        self.is_enabled = is_enabled and self.is_installed()

        log('info', f'EDCoPilot is installed: {self.is_installed()}')
        log('info', f'EDCoPilot is running: {self.is_running()}')
        log('info', f'EDCoPilot is enabled: {self.is_enabled}')

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

    def get_install_path(self) -> Optional[str]:
        """Check the windows registry for COMPUTER / HKEY_CURRENT_USER / SOFTWARE / EDCoPilot"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'SOFTWARE\\EDCoPilot')
            value, _ = winreg.QueryValueEx(key, 'EDCoPilotLib')
            winreg.CloseKey(key)
            return value
        except Exception:
            return None

    def get_process_id(self) -> Optional[int]:
        """Check if EDCoPilot is running"""
        try:
            import psutil
            for proc in psutil.process_iter():
                if 'EDCoPilot' in proc.name():
                    return proc.pid
            return None
        except Exception:
            return None
    
    def write_request(self, message: str):
        """write "message" to EDCoPilot.request.txt in the install path"""
        if not self.is_enabled:
            return False
        if not self.is_running():
            return False
        install_path = self.get_install_path()
        if install_path:
            path = os.path.join(install_path, 'EDCoPilot.request.txt')
            with open(path, 'a', encoding='utf-8') as f:
                f.write(message.replace('\n', ' ')+'\r\n')
            return True
        return False

    def print_this(self, message: str):
        """send PrintThis: "message" request"""
        return self.write_request('PrintThis: '+message)

    def speak_this(self, message: str):
        """send SpeakThis: "message" request"""
        return self.write_request('SpeakThis: '+message)
    

if __name__ == '__main__':
    copilot = EDCoPilot(is_enabled=True)
    copilot.print_this('covas: What the hell do you want, Commander? You know I\ufffdm not here to hold your hand while you shoot stuff in this chaotic mess of a system!')
    time.sleep(2)
    copilot.speak_this('covas: What the hell do you want, Commander? You know I\'m not here to hold your hand while you shoot stuff in this chaotic mess of a system!')