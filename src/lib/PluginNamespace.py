from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PluginNamespace:
    guid: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', self.guid):
            raise ValueError('Plugin GUID must be a nonempty namespace identifier')

    def event_name(self, name: str) -> str:
        prefix = f'{self.guid}.'
        local = name.removeprefix(prefix)
        if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*', local):
            raise ValueError('Invalid local plugin event name')
        return prefix + local
