import json
from pathlib import Path
import sys

from openai.types.chat import ChatCompletionMessageFunctionToolCall

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.lib.actions import actions_web


class FakePromptGenerator:
    def generate_status_message(self, projected_states: dict) -> str:
        return "status"


class FakeLLMModel:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, messages: list, tools: list, tool_choice: str):
        self.calls += 1
        if self.calls == 1:
            return "", [ChatCompletionMessageFunctionToolCall(
                type="function",
                id="internal_call_1",
                function={
                    "name": "get_galnet_news",
                    "arguments": json.dumps({"query": "thargoids"}),
                },
            )], {}
        return "Final report", None, {}


class FailingLLMModel:
    def generate(self, messages: list, tools: list, tool_choice: str):
        raise RuntimeError("model unavailable")


def consume_generator(generator):
    values = []
    while True:
        try:
            values.append(next(generator))
        except StopIteration as stop:
            return values, stop.value


def test_web_search_agent_yields_internal_tool_processing_events(monkeypatch) -> None:
    monkeypatch.setattr(actions_web, "get_galnet_news", lambda args, projected_states: "news result")

    updates, final_result = consume_generator(actions_web.web_search_agent(
        {"query": "latest thargoid news"},
        {},
        prompt_generator=FakePromptGenerator(),
        llm_model=FakeLLMModel(),
        max_loops=3,
    ))

    assert updates == [
        {
            "status": "searching",
            "query": "latest thargoid news",
        },
        {
            "status": "started",
            "query": "latest thargoid news",
            "iteration": 1,
            "internal_tool_call_id": "internal_call_1",
            "internal_tool_name": "get_galnet_news",
            "arguments": {"query": "thargoids"},
        },
        {
            "status": "completed",
            "query": "latest thargoid news",
            "iteration": 1,
            "internal_tool_call_id": "internal_call_1",
            "internal_tool_name": "get_galnet_news",
            "result": "news result",
        },
    ]
    assert final_result == "Final report"


def test_web_search_agent_returns_actionable_loop_error() -> None:
    updates, final_result = consume_generator(actions_web.web_search_agent(
        {"query": "search for aluminum"},
        {},
        prompt_generator=FakePromptGenerator(),
        llm_model=FailingLLMModel(),
        max_loops=3,
    ))

    assert updates == [{"status": "searching", "query": "search for aluminum"}]
    assert final_result == (
        "Web search failed while requesting the search agent model response "
        "on iteration 1 for query 'search for aluminum'. RuntimeError: model unavailable"
    )


def test_plot_name_match_score_prefers_exact_match() -> None:
    assert actions_web.plot_name_match_score("Sol", "Sol") == 1.0
    assert actions_web.plot_name_match_score("Jameson Memorial", "jameson memorial") == 1.0
    assert actions_web.plot_name_match_score("HIP 58412 8 D", "HIP584128D") == 1.0
    assert actions_web.plot_name_match_score("Sol", "Alpha Centauri") == 0.0
    assert actions_web.is_plot_name_exact_match("Earth", "Earth") is True
    assert actions_web.is_plot_name_exact_match("Earth", "Earth Expeditionary Fleet 4") is False


def test_select_best_plot_target_prefers_exact_match_over_fuzzy() -> None:
    candidates = [
        actions_web.ResolvedPlotTarget(
            target_type="body",
            name="Earth Expeditionary Fleet 4",
            system_name="Earth Expeditionary Fleet",
            system_map_category="LANDFALL PLANETS",
            distance=22032.0,
            match_score=0.9,
            details={},
            is_landable=True,
        ),
        actions_web.ResolvedPlotTarget(
            target_type="body",
            name="Earth",
            system_name="Sol",
            system_map_category="LANDFALL PLANETS",
            distance=0.0,
            match_score=1.0,
            details={},
            is_landable=False,
        ),
    ]

    best_match = actions_web._select_best_plot_target(candidates, "Earth")
    assert best_match is not None
    assert best_match.name == "Earth"
    assert best_match.system_name == "Sol"


def test_select_best_plot_target_uses_match_score_then_distance() -> None:
    candidates = [
        actions_web.ResolvedPlotTarget(
            target_type="system",
            name="Sol",
            system_name="Sol",
            system_map_category=None,
            distance=10.0,
            match_score=0.7,
            details={},
        ),
        actions_web.ResolvedPlotTarget(
            target_type="station",
            name="Jameson Memorial",
            system_name="Shinrarta Dezhra",
            system_map_category="ORBITAL PORTS",
            distance=5.0,
            match_score=1.0,
            details={},
        ),
    ]

    best_match = actions_web._select_best_plot_target(candidates, "Jameson Memorial")
    assert best_match is not None
    assert best_match.name == "Jameson Memorial"


def test_system_map_category_for_station_uses_spansh_types() -> None:
    assert actions_web.system_map_category_for_station({"type": "Coriolis Starport"}) == "ORBITAL PORTS"
    assert actions_web.system_map_category_for_station({"type": "Planetary Outpost"}) == "PLANETARY PORTS"
    assert actions_web.system_map_category_for_station({"type": "Drake-Class Carrier"}) == "FLEET CARRIERS"
    assert actions_web.system_map_category_for_station({"type": "Mega ship"}) == "INSTALLATIONS"
    assert actions_web.system_map_category_for_station({"type": "Surface Settlement"}) == "SURFACE SETTLEMENTS"
    assert actions_web.system_map_category_for_station({"type": "Settlement"}) == "ODYSSEY SETTLEMENTS"
    assert actions_web.system_map_category_for_station({"type": "Unknown Type"}) is None


def test_ensure_in_system_plot_target_rejects_unlandable_body() -> None:
    target = actions_web.ResolvedPlotTarget(
        target_type="body",
        name="Earth",
        system_name="Sol",
        system_map_category="LANDFALL PLANETS",
        distance=0.0,
        match_score=1.0,
        details={"is_landable": False},
        is_landable=False,
    )

    try:
        actions_web.ensure_in_system_plot_target(target)
    except Exception as error:
        assert "not landable" in str(error)
    else:
        raise AssertionError("Expected unlandable body to be rejected")


def test_plot_candidates_from_bodies_skips_non_planets_and_requests_ten_results(monkeypatch) -> None:
    captured_sizes: list[int] = []
    captured_names: list[str] = []

    def fake_prepare_body_request(obj, projected_states):
        captured_sizes.append(obj["size"])
        captured_names.append(obj["name"])
        return {"filters": {}, "size": obj["size"], "page": 0}

    def fake_post(url: str, request_body: dict) -> dict:
        return {
            "results": [
                {
                    "name": "Earth Expeditionary Fleet",
                    "system_name": "Earth Expeditionary Fleet",
                    "type": "Star",
                    "distance": 22032.0,
                    "is_landable": False,
                },
                {
                    "name": "Earth",
                    "system_name": "Sol",
                    "type": "Planet",
                    "distance": 0.0,
                    "is_landable": False,
                },
            ]
        }

    monkeypatch.setattr(actions_web, "prepare_body_request", fake_prepare_body_request)
    monkeypatch.setattr(actions_web, "_spansh_post", fake_post)

    candidates = actions_web._plot_candidates_from_bodies("Earth", {"Location": {"StarSystem": "Sol"}})

    assert captured_sizes == [10]
    assert captured_names == ["Eart?"]
    assert len(candidates) == 1
    assert candidates[0].name == "Earth"
    assert candidates[0].is_landable is False


def test_plot_search_query_prefers_station_then_body_then_system() -> None:
    assert actions_web.plot_search_query(station="Jameson Memorial", body="Earth", system="Sol") == "Jameson Memorial"
    assert actions_web.plot_search_query(body="Earth", system="Sol") == "Earth"
    assert actions_web.plot_search_query(system="Sol") == "Sol"
    assert actions_web.plot_search_query() is None


def test_spansh_plot_search_name_disables_fuzzy_matching() -> None:
    assert actions_web.spansh_plot_search_name("Earth") == "Eart?"
    assert actions_web.spansh_plot_search_name("Sol") == "So?"
    assert actions_web.spansh_plot_search_name("A") == "?"
    assert actions_web.spansh_plot_search_name("") == ""
    assert actions_web._plot_search_obj("Jameson Memorial") == {
        "name": "Jameson Memoria?",
        "size": actions_web.PLOT_TARGET_SEARCH_SIZE,
    }


def test_resolve_plot_target_queries_all_spansh_endpoints(monkeypatch) -> None:
    posted_urls: list[str] = []

    def fake_post(url: str, request_body: dict) -> dict:
        posted_urls.append(url)
        if url == actions_web.SPANSH_SYSTEMS_URL:
            assert request_body["size"] == 10
            return {"results": [{"name": "Sol", "distance": 100.0}]}
        if url == actions_web.SPANSH_STATIONS_URL:
            return {"results": []}
        if url == actions_web.SPANSH_BODIES_URL:
            return {"results": []}
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(actions_web, "_spansh_post", fake_post)

    resolved = actions_web.lookup_plot_target(system="Sol", projected_states={"Location": {"StarSystem": "Alpha Centauri"}})

    assert sorted(posted_urls) == sorted([
        actions_web.SPANSH_BODIES_URL,
        actions_web.SPANSH_STATIONS_URL,
        actions_web.SPANSH_SYSTEMS_URL,
    ])
    assert resolved is not None
    assert resolved.target_type == "system"
    assert resolved.system_name == "Sol"
