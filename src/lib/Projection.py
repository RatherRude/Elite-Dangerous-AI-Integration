

from abc import ABC, abstractmethod
from typing import Optional

from .Event import Event


class Projection(ABC):
    @abstractmethod
    def get_default_state(self) -> dict:
        return {}
    
    def __init__(self):
        self.state = self.get_default_state()
        self.last_processed = 0.0
        pass

    @abstractmethod
    def process(self, event: Event) -> dict:
        pass
