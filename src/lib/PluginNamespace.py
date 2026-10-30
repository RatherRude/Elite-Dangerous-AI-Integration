from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class PluginNamespace:
    guid: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', self.guid):
            raise ValueError('Plugin GUID must be a nonempty namespace identifier')

    @property
    def translation_prefix(self) -> str:
        return f'plugin.{self.guid}.'

    def translation_key(self, value: str) -> str:
        if value.startswith('@'):
            key = value[1:]
            if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*', key):
                raise ValueError('Invalid local plugin translation key')
            return self.translation_prefix + key
        if value.startswith('plugin.') and not value.startswith(self.translation_prefix):
            raise ValueError('Plugin translation references must belong to their owner')
        return value

    def event_name(self, name: str) -> str:
        prefix = f'{self.guid}.'
        local = name.removeprefix(prefix)
        if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*', local):
            raise ValueError('Invalid local plugin event name')
        return prefix + local

    def translations(self, languages: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result = deepcopy(languages)
        for language, translations in result.items():
            if not isinstance(translations, dict):
                raise ValueError('Plugin translations must be language dictionaries')
            if 'plugin' in translations:
                owners = translations['plugin']
                if set(translations) != {'plugin'} or not isinstance(owners, dict) or set(owners) != {self.guid}:
                    raise ValueError('Plugin translations must belong to their owner')
                result[language] = owners[self.guid]
            self._validate_translations(result[language])
        return result

    def _validate_translations(self, translations: dict[str, Any]) -> None:
        for key, value in translations.items():
            if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', key):
                raise ValueError('Translation dictionaries must use local key segments')
            if isinstance(value, dict):
                self._validate_translations(value)
            elif not isinstance(value, str):
                raise ValueError('Translation values must be strings or dictionaries')

    def presentation(self, value: Any) -> Any:
        result = deepcopy(value)
        self._scope_presentation(result)
        return result

    def _scope_presentation(self, value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                self._scope_presentation(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {'payload', 'default_value', 'value', 'select_options'}:
                    if key == 'select_options' and isinstance(item, list):
                        for option in item:
                            if isinstance(option.get('label'), str):
                                option['label'] = self.translation_key(option['label'])
                    continue
                if key == 'header_link' and isinstance(item, dict):
                    for field in ('text', 'label'):
                        if isinstance(item.get(field), str):
                            item[field] = self.translation_key(item[field])
                elif key in {'label', 'placeholder', 'content', 'title_key', 'meta', 'group', 'confirmation', 'notification'} and isinstance(item, str):
                    value[key] = self.translation_key(item)
                elif key == 'text' and isinstance(item, dict):
                    self._scope_text(item)
                elif key == 'count_labels' and isinstance(item, dict):
                    for count, label in item.items():
                        item[count] = self.translation_key(label)
                elif key == 'params' and isinstance(item, dict):
                    for param in item.values():
                        if isinstance(param, dict):
                            self._scope_text(param)
                else:
                    self._scope_presentation(item)

    def _scope_text(self, value: dict[str, Any]) -> None:
        if isinstance(value.get('key'), str):
            value['key'] = self.translation_key(value['key'])
        for param in value.get('params', {}).values():
            if isinstance(param, dict):
                self._scope_text(param)
