from pydantic import BaseModel
from typing import List, Optional, Any

class CurriculumRequest(BaseModel):
    theme: str
    sentence_count: int = 5
    
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
