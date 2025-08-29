from __future__ import annotations

from typing import Any
import os

from pydantic import BaseModel

from openai import AsyncOpenAI, OpenAI
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import LLMJudge

from .actions_web import web_search, init_llm_client

model = OpenAIModel(
    'gpt-4.1-mini',
    settings=ModelSettings(temperature=0.8, max_tokens=500),
    provider=OpenAIProvider(openai_client=AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))),
)

class Sample(BaseModel):
    query: str
    projected_states: dict[str, Any]


class SampleResult(BaseModel):
    answer: str


async def run_sample(sample: Sample) -> SampleResult:
    res = web_search({"query": sample.query}, sample.projected_states) or ""
    return SampleResult(answer=res)

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
            }
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

web_tool_dataset = Dataset[Sample, SampleResult, Any](
    cases=[
        # system finder
        Case(
            name='system name sirius',
            inputs=Sample(
                query='find system named Sirius', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Sirius'),
            metadata={},
        ),
        Case(
            name='system allied empire',
            inputs=Sample(
                query='find systems allied to the Empire', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Toolfa'),
            metadata={},
        ),
        Case(
            name='system government anarchy',
            inputs=Sample(
                query='find systems with an anarchy government', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='WISE 0410+1502'),
            metadata={},
        ),
        Case(
            name='system power li yong-rui',
            inputs=Sample(
                query='find systems controlled by Li Yong-Rui', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Sirius'),
            metadata={},
        ),
        Case(
            name='system economy agriculture',
            inputs=Sample(
                query='find systems with an agriculture economy', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Epsilon Eridani'),
            metadata={},
        ),
        Case(
            name='system low security',
            inputs=Sample(
                query='find low security systems', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Alpha Centauri'),
            metadata={},
        ),
        Case(
            name='system population over 1m',
            inputs=Sample(
                query='find systems with at least 1 million population', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Barnard\'s Star'),
            metadata={},
        ),
        Case(
            name='distance to maia',
            inputs=Sample(
                query='give me the distance to Maia', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='383'),
            metadata={},
        ),

        # station finder
        Case(
            name='station name solaris',
            inputs=Sample(
                query='find a station named Solaris', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Vox Solaris in Col 285 Sector XA-N d7-51'),
            metadata={},
        ),
        Case(
            name='closest encoded material trader',
            inputs=Sample(
                query='find me the closest material trader for encoded materials', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Magnus Gateway in the EZ Aquarii system'),
            metadata={},
        ),
        Case(
            name='closest guardian technology broker',
            inputs=Sample(
                query='find the closest technology broker for guardian technology', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Magnus Gateway in the EZ Aquarii system'),
            metadata={},
        ),
        Case(
            name='buy guardian fsd booster',
            inputs=Sample(
                query='where can I buy a Guardian frame shift drive booster', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Magnus Gateway in EZ Aquarii system'),
            metadata={},
        ),
        Case(
            name='buy meta-alloys',
            inputs=Sample(
                query='where can I buy meta-alloys', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Darnielle\'s Progress in the Maia system'),
            metadata={},
        ),
        Case(
            name='buy imperial courier',
            inputs=Sample(
                query='where to buy imperial courier', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Cayley Enterprise in the Wolf 359 system'),
            metadata={},
        ),
        Case(
            name='closest interstellar factors',
            inputs=Sample(
                query='where is the closest interstellar factors', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Kawle Genetics Complex in Alpha Centauri system'),
            metadata={},
        ),

        # body finder
        Case(
            name='body named earth',
            inputs=Sample(
                query='find a body named Earth', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Earth in Sol'),
            metadata={},
        ),
        Case(
            name='next fuelable star',
            inputs=Sample(
                query='next fuelable star', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Alpha Centauri'),
            metadata={},
        ),
        Case(
            name='closest neutron star',
            inputs=Sample(
                query='closest neutron star', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='18 Camelopardalis C'),
            metadata={},
        ),

        # engineer finder
        Case(
            name='engineer shields helper',
            inputs=Sample(
                query='what engineer can help me with my shields?', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Didi Vatermann'),
            metadata={},
        ),
        Case(
            name='engineer unlock felicity',
            inputs=Sample(
                query='what do I need to unlock felicity?', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Meta-Alloys'),
            metadata={},
        ),

        # blueprint finder
        Case(
            name='blueprint thermal resistant shields',
            inputs=Sample(
                query='can I upgrade my shield with thermal resistance?', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Thermal resistant'),
            metadata={},
        ),

        # material finder
        Case(
            name='material lead count',
            inputs=Sample(
                query='How much lead do I have?', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Lead'),
            metadata={},
        ),
        Case(
            name='material refined focus crystals source',
            inputs=Sample(
                query='Where do i find refined focus crystals?', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Mission reward'),
            metadata={},
        ),

        # complicated queries
        Case(
            name='closest scoopable primary system',
            inputs=Sample(
                query='closest system with a scoopable primary star', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Alpha Centauri'),
            metadata={},
        ),
        Case(
            name='closest raw material trader near marco',
            inputs=Sample(
                query="what's the closest material trader for raw materials close to marco?", projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Magnus Gateway'),
            metadata={},
        ),
        Case(
            name='closest raw material trader near navroute',
            inputs=Sample(
                query="what's the closest material trader for raw materials near my navroute destination?", projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Magnus Gateway'),
            metadata={},
        ),
        Case(
            name='compound broker fsd booster painite',
            inputs=Sample(
                query="what's the closest system that has a material broker where I can buy a guardian frame shift drive booster where I can mine painite", projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Painite'),
            metadata={},
        ),
        Case(
            name='buy cmm composite',
            inputs=Sample(
                query='Where can I buy CMM Composites?', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='CMM Composite'),
            metadata={},
        ),
        Case(
            name='mine painite',
            inputs=Sample(
                query='Where can i mine painite?', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Painite'),
            metadata={},
        ),
        Case(
            name='find steel commodity',
            inputs=Sample(
                query='where do i find the remaining steel for my construction?', projected_states=dummy_projected_state
            ),
            expected_output=SampleResult(answer='Steel'),
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

init_llm_client(OpenAI(api_key=os.environ.get("OPENAI_API_KEY")),'gpt-4.1-mini')

report = web_tool_dataset.evaluate_sync(run_sample)
report.print(include_input=True, include_output=True, include_durations=True)