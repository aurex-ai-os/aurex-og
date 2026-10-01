# AUREX PHASE 4 — PROVIDER ARCHITECTURE

## 1. Overview
The Provider Intelligence layer isolates provider selection, routing, health, quota, and capability mapping from the actual agent execution loop. This converts Aurex from a manual, hard-coded model caller into an intelligent, dynamic agent fabric.

## 2. Core Components

### `models.py`
Contains canonical types defining Providers, Models, Capabilities, Health, Quota, Privacy, and Routing Decisions.
- `Capability`: Normalized enum (`TEXT_GENERATION`, `VISION`, etc.) preventing arbitrary string checks.
- `PrivacyLevel`: (`LOCAL_ONLY`, `ALLOW_REMOTE`, etc.) enforces security boundaries at the routing level.

### Registries
- `ProviderRegistry`: Stores `ProviderDefinition`s.
- `ModelRegistry`: Stores `ModelDefinition`s.
- `CapabilityRegistry`: Translates static provider models into normalized capabilities dynamically.

### Managers
- `HealthManager`: Tracks success/failure for each route. Upgrades to `UNAVAILABLE` after consecutive failures and automatically degrades to probing state after a recovery timeout.
- `QuotaManager`: Tracks provider rate limits and exhaustion.
- `PrivacyManager`: Cross-references `TaskRequirements.privacy_requirement` against a provider/model's `is_local` tag to prevent data leakage.

### Intelligence Engine
- `CandidateSelector`: Performs hard filtering based on privacy, capabilities, health, and user overrides.
- `RoutingEngine`: Scores the remaining candidates to generate a deterministic `RoutingDecision`. It outputs the primary route and valid fallbacks.

## 3. Legacy Migration Strategy
To avoid shattering existing legacy configuration (e.g. users who manually entered local IP addresses into Aurex's fallback settings), `legacy_adapter.py` exists to map `(endpoint, model, headers)` tuples dynamically into transient `ProviderDefinition`s. 

`chat_routes.py` now runs `ProviderIntelligence` to select the best model from the available fallback pool *before* the Agent Loop starts, rather than the agent loop blindly crashing and taking the next index in the array.

## 4. Boundaries
- **Task Requirement Generation**: Context Engine / Agent Loop determines *what* is needed.
- **Provider Intelligence**: Determines *who* should run it.
- **Context Renderer (Phase 3)**: Determines *how* to format the prompt for the selected provider.
