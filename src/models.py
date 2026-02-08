from pydantic import BaseModel
from typing import List, Optional, Any

class CurriculumRequest(BaseModel):
    theme: str
    sentence_count: int = 5

class ConstellationNode(BaseModel):
    id: str
    label: str
    type: str  # 'lemma', 'rule', 'theme'
    status: str = "locked" # 'locked', 'unlocked', 'mastered'
    x: float = 0.0
    y: float = 0.0
    data: Optional[Any] = None

class ConstellationLink(BaseModel):
    source: str
    target: str
    value: float = 1.0

class ConstellationGraph(BaseModel):
    nodes: List[ConstellationNode]
    links: List[ConstellationLink]
