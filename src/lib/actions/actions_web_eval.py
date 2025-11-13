from __future__ import annotations

from typing import Any
import os

from dotenv import load_dotenv
load_dotenv()
from pydantic import BaseModel

from openai import AsyncOpenAI, OpenAI
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.settings import ModelSettings
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge

from ..Logger import logger 
import logging
logger.setLevel(logging.WARNING)

from .actions_web import web_search_agent, station_finder, body_finder

model = OpenAIChatModel(
    os.environ.get("OPENAI_MODEL_NAME_JUDGE", "gpt-4.1"),
    #settings=ModelSettings(max_tokens=500, temperature=0.8),
    provider=OpenAIProvider(openai_client=AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY_JUDGE"), base_url=os.environ.get("OPENAI_BASE_URL_JUDGE"))),
)


class Sample(BaseModel):
    query: str
    projected_states: dict[str, Any]


class SampleResult(BaseModel):
    answer: str


dummy_projected_state = {
    "Location": {
        "StarSystem": "Sol",
        "StarPos": [0.0, 0.0, 0.0],
        "SystemAddress": 10477373803
    },
    "EngineerProgress": {
        "Engineers": [
            {
                "EngineerID": 300160,
                "Engineer": "Marco Qwent",
                "Progress": "Unlocked"
            },
            {
                "Engineer": "Didi Vatermann",
                "EngineerID": 300000,
                "Progress": "Unlocked",
                "RankProgress": 0,
                "Rank": 5
            },
        ]
    },
    "Materials": {
        "Raw": [{"Name": "iron", "Count": 100}],
        "Manufactured": [],
        "Encoded": []
    },
    "ShipInfo": {"LandingPadSize": 'L'},
    "ShipLocker": {
        "Items": [],
        "Components": [],
        "Data": [],
        "Consumables": []
    }
}
dummy_construction_state = {
    "ConstructionProgress": 0.034678,
    "ConstructionComplete": False, "ConstructionFailed": False,
    "ResourcesRequired": [
        {"Name": "$cmmcomposite_name;", "Name_Localised": "CMM Composite", "RequiredAmount": 39737, "ProvidedAmount": 0, "Payment": 6788},
        {"Name": "$powergenerators_name;", "Name_Localised": "Power Generators", "RequiredAmount": 277, "ProvidedAmount": 0, "Payment": 3072},
        {"Name": "$semiconductors_name;", "Name_Localised": "Semiconductors", "RequiredAmount": 413, "ProvidedAmount": 0, "Payment": 1526},
        {"Name": "$steel_name;", "Name_Localised": "Steel", "RequiredAmount": 63936, "ProvidedAmount": 7616, "Payment": 5057},
        {"Name": "$titanium_name;", "Name_Localised": "Titanium", "RequiredAmount": 35165, "ProvidedAmount": 0, "Payment": 5360}
    ],
    "MarketID": 4263743747,
    "StarSystem": "Praea Euq LV-Y b5",
    "StarSystemRecall": "Praea Euq LV-Y b5"
}

web_search_agent_llm_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY_AGENT"), base_url=os.environ.get("OPENAI_BASE_URL_AGENT"))


async def run_sample(sample: Sample) -> SampleResult:
    res = web_search_agent(
        {"query": sample.query},
        {**dummy_projected_state, **sample.projected_states},
        llm_client=web_search_agent_llm_client,
        llm_model_name=os.environ.get("OPENAI_MODEL_NAME_AGENT", "gpt-4.1")
    ) or ""
    return SampleResult(answer=res)


web_tool_dataset = Dataset[Sample, SampleResult, Any](
    cases=[
        # system finder
        Case(
            name='system name sirius',
            inputs=Sample(
                query='find system named Sirius', projected_states={}
            ),
            expected_output=SampleResult(answer='Sirius'),
            metadata={},
        ),
        Case(
            name='system allied empire',
            inputs=Sample(
                query='find systems allied to the Empire', projected_states={}
            ),
            expected_output=SampleResult(answer='Toolfa'),
            metadata={},
        ),
        Case(
            name='system government anarchy',
            inputs=Sample(
                query='find systems with an anarchy government', projected_states={}
            ),
            expected_output=SampleResult(answer='WISE 0410+1502'),
            metadata={},
        ),
        Case(
            name='system power li yong-rui',
            inputs=Sample(
                query='find systems controlled by Li Yong-Rui', projected_states={}
            ),
            expected_output=SampleResult(answer='Sirius'),
            metadata={},
        ),
        Case(
            name='system economy agriculture',
            inputs=Sample(
                query='find systems with an agriculture economy', projected_states={}
            ),
            expected_output=SampleResult(answer='Epsilon Eridani'),
            metadata={},
        ),
        Case(
            name='system low security',
            inputs=Sample(
                query='find low security systems', projected_states={}
            ),
            expected_output=SampleResult(answer='Alpha Centauri'),
            metadata={},
        ),
        Case(
            name='system population over 1m',
            inputs=Sample(
                query='find systems with at least 1 million population', projected_states={}
            ),
            expected_output=SampleResult(answer='Barnard\'s Star'),
            metadata={},
        ),
        Case(
            name='distance to maia',
            inputs=Sample(
                query='give me the distance to Maia', projected_states={}
            ),
            expected_output=SampleResult(answer='383'),
            metadata={},
        ),

        # station finder
        Case(
            name='station name solaris',
            inputs=Sample(
                query='find a station named Solaris', projected_states={}
            ),
            expected_output=SampleResult(answer='Vox Solaris in Col 285 Sector XA-N d7-51'),
            metadata={},
        ),
        Case(
            name='closest encoded material trader',
            inputs=Sample(
                query='find me the closest material trader for encoded materials', projected_states={}
            ),
            expected_output=SampleResult(answer='Magnus Gateway in the EZ Aquarii system'),
            metadata={},
        ),
        Case(
            name='closest guardian technology broker',
            inputs=Sample(
                query='find the closest technology broker for guardian technology', projected_states={}
            ),
            expected_output=SampleResult(answer='Magnus Gateway in the EZ Aquarii system'),
            metadata={},
        ),
        Case(
            name='buy guardian fsd booster',
            inputs=Sample(
                query='where can I buy a Guardian frame shift drive booster', projected_states={}
            ),
            expected_output=SampleResult(answer='Magnus Gateway in EZ Aquarii system'),
            metadata={},
        ),
        Case(
            name='buy meta-alloys',
            inputs=Sample(
                query='where can I buy meta-alloys', projected_states={}
            ),
            expected_output=SampleResult(answer='Darnielle\'s Progress in the Maia system'),
            metadata={},
        ),
        Case(
            name='buy imperial courier',
            inputs=Sample(
                query='where to buy imperial courier', projected_states={}
            ),
            expected_output=SampleResult(answer='Cayley Enterprise in the Wolf 359 system'),
            metadata={},
        ),
        Case(
            name='closest interstellar factors',
            inputs=Sample(
                query='where is the closest interstellar factors', projected_states={}
            ),
            expected_output=SampleResult(answer=
                station_finder({
                    "reference_system": "Sol",
                    "services": [{"name":"Interstellar Factors Contact"}],
                }, dummy_projected_state)
            ),
            metadata={},
        ),

        # body finder
        Case(
            name='body named earth',
            inputs=Sample(
                query='find a body named Earth', projected_states={}
            ),
            expected_output=SampleResult(answer='Earth in Sol'),
            metadata={},
        ),
        Case(
            name='next fuelable star',
            inputs=Sample(
                query='next fuelable star', projected_states={}
            ),
            expected_output=SampleResult(answer='Alpha Centauri'),
            metadata={},
        ),
        Case(
            name='closest neutron star',
            inputs=Sample(
                query='closest neutron star', projected_states={}
            ),
            expected_output=SampleResult(answer='18 Camelopardalis C'),
            metadata={},
        ),
        #   Need Expected results and populated projections
        # engineer finder
        Case(
            name='engineer shields helper',
            inputs=Sample(
                query='what engineer can help me with my shields?', projected_states={
                    "EngineerProgress": {
                        "Engineers": [
                            {
                                "Engineer": "Didi Vatermann",
                                "EngineerID": 300000,
                                "Progress": "Unlocked",
                                "RankProgress": 0,
                                "Rank": 5
                            },
                        ]
                    },
                }
            ),
            expected_output=SampleResult(answer='Didi Vatermann, but only up to grade 3. Lei Cheung and Mel Brandon can upgrade to grade 5, but still need to be unlocked.'),
            metadata={},
        ),
        Case(
            name='unlock felicity',
            inputs=Sample(
                query='unlock felicity', projected_states={}
            ),
            expected_output=SampleResult(answer='1 unit of Meta Alloys'),
            metadata={},
        ),
        # blueprint finder
        Case(
            name='blueprint thermal resistant shields',
            inputs=Sample(
                query='can I upgrade my shield with thermal resistance?', projected_states={
                    "Materials": {
                        "timestamp": "2025-10-28T19:15:13Z",
                        "event": "Materials",
                        "Raw": [
                            {
                                "Name": "mercury",
                                "Count": 3
                            },
                            {
                                "Name": "ruthenium",
                                "Count": 3
                            }
                        ],
                        "Manufactured": [
                            {
                                "Name": "shieldsoakanalysis",
                                "Name_Localised": "Inconsistent Shield Soak Analysis",
                                "Count": 4
                            },
                            {
                                "Name": "focuscrystals",
                                "Name_Localised": "Focus Crystals",
                                "Count": 4
                            },
                        ],
                        "Encoded": [
                            {
                                "Name": "shielddensityreports",
                                "Name_Localised": "Untypical Shield Scans",
                                "Count": 110
                            },
                        ],
                        "id": "Journal.2025-10-28T201448.01.log.000004"
                    },
                    "Loadout": {
                        "timestamp": "2025-10-28T19:15:38Z",
                        "event": "Loadout",
                        "Ship": "anaconda",
                        "ShipID": 10,
                        "ShipName": "Landing party",
                        "ShipIdent": "P4I27y",
                        "HullValue": 146969451,
                        "ModulesValue": 385626720,
                        "HullHealth": 1.0,
                        "UnladenMass": 1266.605713,
                        "CargoCapacity": 32,
                        "MaxJumpRange": 33.260761,
                        "FuelCapacity": {
                          "Main": 32.0,
                          "Reserve": 1.07
                        },
                        "Rebuy": 26629811,
                        "Modules": [
                          {
                            "Slot": "Slot01_Size7",
                            "Item": "int_shieldgenerator_size7_class3_fast",
                            "On": True,
                            "Priority": 0,
                            "Health": 1.0,
                            "Value": 8548185,
                            "Engineering": {
                              "Engineer": "Lei Cheung",
                              "EngineerID": 300120,
                              "BlueprintID": 128673844,
                              "BlueprintName": "ShieldGenerator_Thermic",
                              "Level": 3,
                              "Quality": 1.0,
                              "ExperimentalEffect": "special_shield_regenerative",
                              "ExperimentalEffect_Localised": "Fast Charge",
                              "Modifiers": [
                                {
                                  "Label": "Integrity",
                                  "Value": 183.399994,
                                  "OriginalValue": 131.0,
                                  "LessIsGood": 0
                                },
                                {
                                  "Label": "RegenRate",
                                  "Value": 5.06,
                                  "OriginalValue": 4.4,
                                  "LessIsGood": 0
                                },
                                {
                                  "Label": "BrokenRegenRate",
                                  "Value": 12.65,
                                  "OriginalValue": 11.0,
                                  "LessIsGood": 0
                                },
                                {
                                  "Label": "KineticResistance",
                                  "Value": 26.919996,
                                  "OriginalValue": 39.999996,
                                  "LessIsGood": 0
                                },
                                {
                                  "Label": "ThermicResistance",
                                  "Value": 39.099998,
                                  "OriginalValue": -20.000004,
                                  "LessIsGood": 0
                                },
                                {
                                  "Label": "ExplosiveResistance",
                                  "Value": 49.25,
                                  "OriginalValue": 50.0,
                                  "LessIsGood": 0
                                }
                              ]
                            }
                          }
                        ],
                        "id": "Journal.2025-10-28T201448.01.log.000018"
                      }
                }
            ),
            expected_output=SampleResult(answer='\n'.join([
                "Current Grade: 3",
                "Grade 4 requirements: 1 Mercury (4 required, 3 in cargo)",
                "Grade 5 requirements: Refined Focus Crystal (5 required, 0 in cargo)"
            ])),
            metadata={},
        ),
        # material finder
        Case(
            name='material refined focus crystals source',
            inputs=Sample(
                query='refined focus crystals', projected_states={}
            ),
            expected_output=SampleResult(answer="Mission reward"),
            metadata={},
        ),
        # complicated queries
        Case(
            name='closest scoopable primary system',
            inputs=Sample(
                query='closest system with a scoopable primary star', projected_states={}
            ),
            expected_output=SampleResult(answer='Alpha Centauri'),
            metadata={},
        ),
        Case(
            name='closest raw material trader near marco',
            inputs=Sample(
                query="closest raw material trader near marco", projected_states={}
            ),
            expected_output=SampleResult(answer=
                station_finder({
                    "reference_system": "Sirius",
                    "material_trader": ["Raw"],
                }, dummy_projected_state)),
            metadata={},
        ),
        # Case(
        #     name='closest raw material trader near navroute',
        #     inputs=Sample(
        #         query="what's the closest material trader for raw materials near my navroute destination?", projected_states={}
        #     ),
        #     expected_output=SampleResult(answer='Magnus Gateway'),
        #     metadata={},
        # ),
        # Case(
        #     name='compound broker fsd booster painite',
        #     inputs=Sample(
        #         query="what's the closest system that has a material broker where I can buy a guardian frame shift drive booster where I can mine painite", projected_states={}
        #     ),
        #     expected_output=SampleResult(answer='Painite'),
        #     metadata={},
        # ),
        # Case(
        #     name='buy cmm composite',
        #     inputs=Sample(
        #         query='buy cmm composite', projected_states={}
        #     ),
        #     expected_output=SampleResult(answer='CMM Composite'),
        #     metadata={},
        # ),
        Case(
            name='mine painite',
            inputs=Sample(
                query='painite', projected_states={}
            ),
            expected_output=SampleResult(answer=
                "Painite can be acquired by mining hotspots. "+
                body_finder({
                    "reference_system": "Sol",
                    "rings": { "material": "Painite", "hotspots": 1 }
                }, dummy_projected_state)),
            metadata={},
        ),
        Case(
            name='steel for construction',
            inputs=Sample(
                query='where do i find the remaining steel for my construction?', projected_states={
                    "ColonisationConstruction": dummy_construction_state
                }
            ),
            expected_output=SampleResult(answer=station_finder({
                "reference_system": "Praea Euq LV-Y b5",
                "commodities": [{"name": "Steel", "amount": 56.320, "transaction": "Buy"}],
            }, {
                **dummy_projected_state,
                "ColonisationConstruction": dummy_construction_state,
            })),
            metadata={},
        ),
    ],
    evaluators=[
        LLMJudge(
            rubric='The result should answer the input query. It may contain additional details and alternatives, but must mention the expected output.',
            include_input=True,
            include_expected_output=True,
            model=model,
        ),
    ],
)

report = web_tool_dataset.evaluate_sync(run_sample)
report.print(include_input=True, include_output=True, include_expected_output=True, include_durations=True, include_reasons=True)
