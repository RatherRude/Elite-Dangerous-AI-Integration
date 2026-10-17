import json
import math
import re
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Callable, Literal, Mapping, TYPE_CHECKING

from .Logger import log

if TYPE_CHECKING:
    from .Models import STTModel


PARAKEET_GUID = "b77dec4f-8993-4213-8d44-caf902dabc6d"
PARAKEET_MODEL = "parakeet-stt"
PARAKEET_PROVIDER = f"plugin:{PARAKEET_GUID}:{PARAKEET_MODEL}"
VoiceState = Literal["standby", "active", "error", "disabled"]
VoiceInputKind = Literal["command", "wake", "close"]


def normalized_words(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return tuple(re.findall(r"[^\W_]+", normalized))


@dataclass(frozen=True)
class VoiceLanguagePhrases:
    invocation_prefixes: tuple[str, ...]
    closing_phrases: tuple[str, ...]
    wake_acknowledgments: tuple[str, ...]
    close_acknowledgments: tuple[str, ...]
    language_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class VoicePhrases:
    default_language: str
    languages: Mapping[str, VoiceLanguagePhrases]


def normalize_voice_language(value: object, phrases: VoicePhrases | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        languages = {normalize_voice_language(language, phrases) for language in value}
        return next(iter(languages)) if len(languages) == 1 else None
    if not isinstance(value, str):
        raise ValueError("A speech language must be a language code, name or list of languages.")
    value = value.strip()
    if value.casefold() in ("", "auto", "automatic", "multilingual", "default"):
        return None
    if re.search(r"[,;/|]", value):
        return normalize_voice_language(re.split(r"[,;/|]", value), phrases)
    if re.fullmatch(r"[a-zA-Z]{2}(?:[-_][a-zA-Z0-9]{2,8})*", value):
        return value[:2].lower()
    if phrases is None:
        phrases = load_voice_phrases()
    matches = {
        language for language, localized in phrases.languages.items()
        if any(normalized_words(value) == normalized_words(name) for name in localized.language_names)
    }
    if len(matches) == 1:
        return next(iter(matches))
    raise ValueError(f"Unknown or ambiguous speech language '{value}'. Use a language code such as 'en' or 'fr'.")


def load_voice_phrases(path: Path | None = None) -> VoicePhrases:
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "voice_phrases.json"
    try:
        with path.open(encoding="utf-8") as file:
            data: object = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not load voice phrases from '{path}': {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Voice phrases in '{path}' must be a JSON object.")
    languages = data.get("languages")
    if not isinstance(languages, dict) or not languages:
        raise ValueError(f"Voice phrases in '{path}' require a non-empty 'languages' object.")
    default_language = data.get("default_language")
    if not isinstance(default_language, str) or default_language not in languages:
        raise ValueError(f"Voice phrases in '{path}' require a 'default_language' present in 'languages'.")

    def read_phrases(
        language_data: Mapping[str, object], language: str, key: str, allow_empty: bool = False,
    ) -> tuple[str, ...]:
        entries = language_data.get(key)
        if not isinstance(entries, list) or (not entries and not allow_empty):
            raise ValueError(f"Voice phrases field '{language}.{key}' in '{path}' must be a "
                             f"{'possibly empty' if allow_empty else 'non-empty'} list of phrases.")
        phrases: list[str] = []
        for entry in entries:
            if not isinstance(entry, str) or not normalized_words(entry):
                raise ValueError(f"Voice phrases field '{language}.{key}' in '{path}' must contain "
                                 "strings with at least one letter or number.")
            phrases.append(entry.strip())
        return tuple(phrases)

    localized: dict[str, VoiceLanguagePhrases] = {}
    for language, language_data in languages.items():
        if (
            not isinstance(language, str)
            or not re.fullmatch(r"[a-z]{2}", language)
        ):
            raise ValueError(f"Voice phrase language keys in '{path}' must be lowercase two-letter language codes.")
        if not isinstance(language_data, dict):
            raise ValueError(f"Voice phrases for '{language}' in '{path}' must be a JSON object.")
        localized[language] = VoiceLanguagePhrases(
            invocation_prefixes=read_phrases(language_data, language, "invocation_prefixes", allow_empty=True),
            closing_phrases=read_phrases(language_data, language, "closing_phrases"),
            wake_acknowledgments=read_phrases(language_data, language, "wake_acknowledgments"),
            close_acknowledgments=read_phrases(language_data, language, "close_acknowledgments"),
            language_names=(
                read_phrases(language_data, language, "language_names", allow_empty=True)
                if "language_names" in language_data else ()
            ),
        )
    return VoicePhrases(default_language=default_language, languages=localized)


def voice_config_error(config: Mapping[str, object]) -> str | None:
    name = config.get("wake_word_name", "Simone")
    if not isinstance(name, str) or not normalized_words(name):
        return "The activation name must contain at least one letter or number."
    timeout = config.get("wake_word_timeout", 10)
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        return "The dialogue timeout must be a finite number greater than zero."
    if config.get("wake_word_source", "main") not in ("main", "parakeet"):
        return "Unknown voice activation source."
    if config.get("wake_word_first_command", "retranscribe") not in ("retranscribe", "reuse"):
        return "Unknown first-command transcription strategy."
    return None


def resolve_activation_model(
    main_model: "STTModel",
    main_provider: str,
    source: str,
    parakeet_available: bool,
    create_parakeet: Callable[[], "STTModel | None"],
) -> tuple["STTModel", bool]:
    if source == "main" or main_provider == PARAKEET_PROVIDER:
        return main_model, False
    if not parakeet_available:
        return main_model, True
    model = create_parakeet()
    if model is None:
        raise RuntimeError("Could not initialize Parakeet voice activation. No remote fallback was used.")
    return model, False


@dataclass(frozen=True)
class VoiceTicket:
    generation: int
    active: bool


@dataclass(frozen=True)
class VoiceInput:
    kind: VoiceInputKind
    text: str
    generation: int
    language: str


class VoiceActivation:
    def __init__(
        self,
        name: str,
        timeout: float,
        main_model: "STTModel",
        activation_model: "STTModel",
        first_command: str = "retranscribe",
        clock: Callable[[], float] = monotonic,
        phrases: VoicePhrases | None = None,
        tts_language: object = None,
        stt_language: object = None,
        detect_language: Callable[[str], str | None] | None = None,
    ) -> None:
        error = voice_config_error({
            "wake_word_name": name,
            "wake_word_timeout": timeout,
            "wake_word_first_command": first_command,
        })
        if error:
            raise ValueError(error)
        self.name = name
        self.timeout = timeout
        self.main_model = main_model
        self.activation_model = activation_model
        self.first_command = first_command
        self.phrases = phrases if phrases is not None else load_voice_phrases()
        self._preferred_language = (
            normalize_voice_language(tts_language, self.phrases)
            or normalize_voice_language(stt_language, self.phrases)
        )
        self._last_language = self.phrases.default_language
        self._detect_language = detect_language
        self._warned_languages: set[str] = set()
        self._closing_languages: dict[tuple[str, ...], set[str]] = {}
        for language, localized in self.phrases.languages.items():
            for phrase in localized.closing_phrases:
                self._closing_languages.setdefault(normalized_words(phrase), set()).add(language)
        name_words = normalized_words(name)
        self._invocation_prefixes = (name_words,) + tuple(
            normalized_words(prefix) + name_words
            for localized in self.phrases.languages.values()
            for prefix in localized.invocation_prefixes
        )
        self._clock = clock
        self._lock = threading.RLock()
        self._state: VoiceState = "standby"
        self._generation = 0
        self._deadline: float | None = None
        self._busy = False
        self._capturing = False
        self._output_busy = False
        self._control_pending = False

    @property
    def state(self) -> VoiceState:
        with self._lock:
            return self._state

    @property
    def active(self) -> bool:
        return self.state == "active"

    @property
    def automatic_language(self) -> bool:
        return self._preferred_language is None

    @property
    def suppressed(self) -> bool:
        with self._lock:
            return (
                self._state == "disabled"
                or self._control_pending
                or (self._output_busy and self._state != "active")
            )

    def strip_invocation(self, text: str) -> str | None:
        text = unicodedata.normalize("NFC", text)
        words = list(re.finditer(r"[^\W_]+", text))
        tokens = tuple("".join(normalized_words(word.group())) for word in words)
        for prefix in self._invocation_prefixes:
            if tokens[:len(prefix)] == prefix:
                end = words[len(prefix) - 1].end()
                return re.sub(r"^[\W_]+", "", text[end:])
        return None

    def _close(self, state: VoiceState = "standby") -> None:
        self._state = state
        self._generation += 1
        self._deadline = None
        self._control_pending = False

    def stop(self) -> None:
        with self._lock:
            self._close("disabled")

    def fail(self) -> None:
        with self._lock:
            if self._state != "disabled":
                self._close("error")

    def _expire(self) -> None:
        if (
            self._state == "active"
            and not self._busy
            and not self._capturing
            and not self._control_pending
            and self._deadline is not None
            and self._clock() >= self._deadline
        ):
            self._close()

    def tick(self, busy: bool, output_busy: bool = False) -> None:
        with self._lock:
            self._busy = busy
            self._output_busy = output_busy
            if self._state != "active":
                return
            if busy or self._capturing or self._control_pending:
                self._deadline = None
            elif self._deadline is None:
                self._deadline = self._clock() + self.timeout
            else:
                self._expire()

    def begin_audio(self) -> VoiceTicket | None:
        with self._lock:
            if self.suppressed:
                return None
            self._expire()
            if self._state == "error":
                self._state = "standby"
            ticket = VoiceTicket(self._generation, self._state == "active")
            self._capturing = True
            if ticket.active:
                self._deadline = None
            return ticket

    def end_audio(self) -> None:
        with self._lock:
            self._capturing = False

    def finish_control(self) -> None:
        with self._lock:
            self._control_pending = False

    def accepts(self, result: VoiceInput) -> bool:
        with self._lock:
            return (
                result.generation == self._generation
                and self._state != "disabled"
                and (result.kind == "close" or self._state == "active")
            )

    def recognize(
        self,
        ticket: VoiceTicket,
        transcribe: Callable[["STTModel"], str],
    ) -> VoiceInput | None:
        with self._lock:
            if ticket.generation != self._generation or self._state == "disabled":
                return None
        model = self.main_model if ticket.active else self.activation_model
        text = transcribe(model).strip()
        if not text:
            return None
        command = self.strip_invocation(text)
        if not ticket.active:
            if command is None:
                return None
            if command and self.activation_model is not self.main_model and self.first_command == "retranscribe":
                with self._lock:
                    if ticket.generation != self._generation or self._state == "disabled":
                        return None
                text = transcribe(self.main_model).strip()
                if not text:
                    return None
                stripped = self.strip_invocation(text)
                command = text if stripped is None else stripped
        elif command is None:
            command = text

        closing_languages = self._closing_languages.get(normalized_words(command), set())
        detected_language = None
        if not self._preferred_language and command:
            if len(closing_languages) == 1:
                detected_language = next(iter(closing_languages))
            elif not closing_languages and self._detect_language is not None:
                detected_language = self._detect_language(command)

        with self._lock:
            if ticket.generation != self._generation or self._state == "disabled":
                return None
            if detected_language is not None:
                self._last_language = detected_language
            language = self._preferred_language or self._last_language
            if language not in self.phrases.languages:
                if language not in self._warned_languages:
                    log("warn", f"No voice acknowledgments configured for '{language}'; "
                        f"using '{self.phrases.default_language}'.")
                    self._warned_languages.add(language)
                language = self.phrases.default_language
            if not ticket.active:
                self._state = "active"
                self._generation += 1
                self._deadline = None
            if closing_languages:
                self._close()
                self._control_pending = True
                return VoiceInput("close", "", self._generation, language)
            if not command:
                self._control_pending = True
                return VoiceInput("wake", "", self._generation, language)
            return VoiceInput("command", command, self._generation, language)
