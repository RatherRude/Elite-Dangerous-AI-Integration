from typing import Literal, TypedDict
from pydantic import BaseModel

class SystemInfo(BaseModel):
    os: str
    input_device_names: list[str]
    output_device_names: list[str]
    edcopilot_installed: bool