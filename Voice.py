# pip install pyttsx3
import sys
from threading import Thread
import kthread
import queue
import pyttsx3
from time import sleep

from Logger import log

class Voice:

    def __init__(self, rate_multiplier: float = 1, voice: str = 'zira'):
        self.q = queue.Queue(5)
        self.v_enabled = False
        self.v_quit = False
        self.t = kthread.KThread(target=self.voice_exec, name="Voice", daemon=True)
        self.t.start()
        self.v_id = 0
        self._is_playing = False
        self.rate = rate_multiplier
        self.voice = voice

    def get_is_playing(self):
        return self._is_playing or not self.q.empty()

    def say(self, vSay):
        if self.v_enabled:
            self.q.put(vSay)

    def set_off(self):
        self.v_enabled = False

    def set_on(self):
        self.v_enabled = True

    def quit(self):
        self.v_quit = True
        
    def voice_exec(self):
        default_voice = True
        engine = pyttsx3.init()
        engine.setProperty('rate', 160*self.rate)
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[0].id)
        for voice in voices:
            if self.voice.lower() in voice.name.lower():
                default_voice = False
                engine.setProperty('voice', voice.id)  # changes the voice

        if default_voice:
            log('Debug ', 'TTS Voice ' + self.voice + ' has not been found. Using fallback TTS Voice.')
            log('Debug ', 'List of available models: ' + ', '.join([voice.name for voice in voices]))

        while not self.v_quit:
            try:
                words = self.q.get(timeout=1)
                self.q.task_done()
                if words is not None:
                    self._is_playing = True
                    engine.say(words)
                    engine.runAndWait()
                    self._is_playing = False
            except:
                pass

    def abort(self):
        pass

def main():
    v = Voice(rate_multiplier=1.2)
    v.set_on()
    sleep(2)
    v.say("Hey dude")
    sleep(2)
    v.say("whats up")
    sleep(2)
    v.quit()


if __name__ == "__main__":
    main()
