from enum import Enum
from typing import List, Dict, Any, Optional, Set
from pydantic import BaseModel, Field

class Capability(str, Enum):
    TEXT_GENERATION = "TEXT_GENERATION"
    REASONING = "REASONING"
    LONG_CONTEXT = "LONG_CONTEXT"
    VISION = "VISION"
    DOCUMENT_UNDERSTANDING = "DOCUMENT_UNDERSTANDING"
    TOOL_CALLING = "TOOL_CALLING"
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"
    JSON_MODE = "JSON_MODE"
    IMAGE_GENERATION = "IMAGE_GENERATION"
    AUDIO_INPUT = "AUDIO_INPUT"
    AUDIO_OUTPUT = "AUDIO_OUTPUT"
    EMBEDDINGS = "EMBEDDINGS"
    LOCAL_EXECUTION = "LOCAL_EXECUTION"
    STREAMING = "STREAMING"

class PrivacyLevel(str, Enum):
    LOCAL_ONLY = "LOCAL_ONLY"               # Never leaves the device
    ALLOW_REMOTE = "ALLOW_REMOTE"           # Any provider allowed
    PREFER_LOCAL = "PREFER_LOCAL"           # Will use local if capabilities match
    NO_EXTERNAL_SERVICE = "NO_EXTERNAL_SERVICE" # Allowed remote, but no third-party APIs (e.g. self-hosted VPC allowed)

class ProviderType(str, Enum):
    NATIVE = "NATIVE"               # e.g., Anthropic native API, Google native API
    OPENAI_COMPAT = "OPENAI_COMPAT" # e.g., vLLM, standard proxy
    LOCAL = "LOCAL"                 # e.g., Ollama, LM Studio
    PROVIDER_POOL = "PROVIDER_POOL" # e.g., OmniRoute, FreeLLMAPI, OpenRouter

class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"

class QuotaState(str, Enum):
    HEALTHY = "HEALTHY"
    LIMITED = "LIMITED"
    RATE_LIMITED = "RATE_LIMITED"
    EXHAUSTED = "EXHAUSTED"
    UNKNOWN = "UNKNOWN"

class PricingInfo(BaseModel):
    input_cost_per_m: Optional[float] = None  # Cost per million input tokens
    output_cost_per_m: Optional[float] = None # Cost per million output tokens
    cached_input_cost_per_m: Optional[float] = None
    is_free_tier: bool = False
    is_unknown: bool = True

class ModelDefinition(BaseModel):
    id: str
    provider_id: str
    provider_pool: Optional[str] = None
    canonical_model_id: Optional[str] = None
    name: str
    display_name: str
    context_window: int = 8192
    max_output: int = 4096
    capabilities: Set[Capability] = Field(default_factory=set)
    is_local: bool = False
    pricing: PricingInfo = Field(default_factory=PricingInfo)
    is_available: bool = True
    is_deprecated: bool = False
    health: HealthState = HealthState.UNKNOWN
    reliability: float = 1.0
    metadata_source: str = "direct"
    metadata_confidence: float = 1.0
    last_verified_at: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ProviderDefinition(BaseModel):
    id: str
    display_name: str
    provider_type: ProviderType
    endpoint_url: str
    is_local: bool = False
    capabilities_supported: Set[Capability] = Field(default_factory=set)
    privacy_level: PrivacyLevel = PrivacyLevel.ALLOW_REMOTE
    is_enabled: bool = True
    priority: int = 50
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TaskRequirements(BaseModel):
    hard_capabilities: Set[Capability] = Field(default_factory=set)
    soft_capabilities: Set[Capability] = Field(default_factory=set)
    privacy_requirement: PrivacyLevel = PrivacyLevel.ALLOW_REMOTE
    requires_local: bool = False
    min_context_window: int = 0
    max_latency_ms: Optional[int] = None
    max_cost_per_m: Optional[float] = None
    explicit_provider_id: Optional[str] = None
    explicit_model_id: Optional[str] = None

class RoutingDecision(BaseModel):
    selected_provider_id: str
    selected_model_id: str
    route_type: str = "PRIMARY"
    reason_codes: List[str] = Field(default_factory=list)
    capabilities_matched: Set[Capability] = Field(default_factory=set)
    fallback_candidates: List[str] = Field(default_factory=list)
    timestamp: float = 0.0
