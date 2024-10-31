

from abc import ABC, abstractmethod
from typing import Optional

from .Event import Event


class Projection(ABC):
    @abstractmethod
    def get_default_state(self) -> dict:
        return {}
    
    def __init__(self, state: Optional[dict] = None, offset: Optional[int] = 0):
        self.state = state if state!=None else self.get_default_state()
        self.offset = offset
        pass

    @abstractmethod
    def process(self, event: Event) -> dict:
        pass
