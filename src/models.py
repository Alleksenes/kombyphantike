from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union

# The data payload for each node
class NodeData(BaseModel):
    # Core Identification
    knot_id: Optional[str] = None
    hero: Optional[str] = None

    # Text Content
    source_sentence: Optional[str] = None
    target_sentence: Optional[str] = None
    target_transliteration: Optional[str] = None
    instruction_text: Optional[str] = None  # For theme node

    # Philological Data
    knot_definition: Optional[str] = None
    parent_concept: Optional[str] = None
    nuance: Optional[str] = None
    ancient_context: Optional[Union[Dict[str, Any], str]] = None
    modern_context: Optional[str] = None
    knot_context: Optional[str] = None
    theme: Optional[str] = None

    # Core Vocab Roles (Rule Node)
    core_verb: Optional[str] = None
    core_adj: Optional[str] = None
    optional_praepositio: Optional[str] = None
    optional_adverb: Optional[str] = None

    # Lemma Inspector Data (Lemma Node)
    lemma: Optional[str] = None
    english_meaning: Optional[str] = None
    pos: Optional[str] = None
    etymology: Optional[str] = None
    frequency_score: Optional[float] = None
    kds_score: Optional[float] = None

    # Session Data (Theme Node)
    session_data: Optional[Dict[str, Any]] = None

    # API Fill Tokenization (Filled by API)
    target_tokens: Optional[List[Dict[str, Any]]] = None
    source_tokens: Optional[List[Dict[str, Any]]] = None

class ConstellationNode(BaseModel):
    id: str
    label: str
    type: str
    status: str
    x: float = 0.0 # Added for frontend/test compatibility
    y: float = 0.0 # Added for frontend/test compatibility
    data: Optional[NodeData] = None # <-- DATA IS A STRUCTURED OBJECT

class ConstellationLink(BaseModel):
    source: str
    target: str
    value: float = 1.0

class ConstellationGraph(BaseModel):
    nodes: List[ConstellationNode]
    links: List[ConstellationLink]
    golden_path: List[str] = [] # Added default for backward compatibility
