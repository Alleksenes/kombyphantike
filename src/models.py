from pydantic import BaseModel
from typing import List, Optional, Any

class ConstellationNode(BaseModel):
    id: str
    label: str
    type: str  # "theme", "lemma", "rule"
    status: str
    data: Optional[Any] = None

class ConstellationLink(BaseModel):
    source: str
    target: str
    value: float

class ConstellationGraph(BaseModel):
    nodes: List[ConstellationNode]
    links: List[ConstellationLink]
