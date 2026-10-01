# AUREX PHASE 4 — PROVIDER AUDIT

## 1. Executive Summary
Aurex's current model selection and provider routing is primarily rigid, user-configured, and manual. The system relies on fixed metadata dictionaries (`model_capabilities.py`), static discovery files (`model_discovery.py`), and simple user preferences (`foreground_model_routing.py`) to select a model. 

For Aurex to become an intelligent agent capable of dynamically evaluating tasks and routing them to the appropriate model based on health, capability, quotas, and privacy, a new `Provider Intelligence & Model Fabric` layer must be introduced without breaking the existing manual override and legacy fallback behaviors.

## 2. Current Architecture

### Provider/Model Discovery
- `src/model_discovery.py`: Scans configured endpoints (e.g., Ollama, LM Studio, OpenAI-compatibles) and populates available models into user settings.
- `src/model_capability_readers/`: Contains static and dynamic readers that guess a model's capabilities (e.g. `OllamaReader`, `OpenAIReader`).

### Capability Detection
- `src/model_capabilities.py`: Contains a large, static, hard-coded dictionary of capabilities (e.g. `_KNOWN_CAPABILITIES`). It matches capabilities using regex or simple substring matching against model names.
- This creates problems when new models are added, as their capabilities are often "unknown" unless explicitly hardcoded.

### Routing Logic
- `src/foreground_model_routing.py`: Implements a basic "fallback" mechanism based on the user's configured preference (`foreground_model_fallbacks`). 
- When a model fails with a specific HTTP status code (e.g., 429, 500, 503), it blindly tries the next model in the user's list.
- **Flaw**: It does not check if the fallback model possesses the required capabilities (e.g., falling back from a Vision model to a Text-only model).

### Provider Adapters
- Currently, Aurex uses an `openai-python` compatible interface for almost everything (`api_interaction.py` / `llm_core.py`), with scattered `if` statements throughout `agent_loop.py` to handle provider quirks (e.g., DeepSeek's `reasoning_content`, Gemini's `extra_content`).
- *Phase 3* began migrating these into `ContextRenderer`, but the network execution layer (`llm_core.py`) still lacks formalized adapters.

### Configuration Storage
- Stored in the `_users[owner]` dictionary in `prefs_routes._load()` or a legacy flat `settings.json`.

### Health & Quota
- Barebones tracking. `foreground_model_routing.py` checks for failure statuses, but there is no formalized "HealthManager" tracking latency, rate limits, or transient vs permanent failures. No quota management exists.

## 3. What Needs to be Replaced or Refactored
1. **Static Capability Dictionaries**: `model_capabilities.py` needs to be backed by a proper `CapabilityRegistry` using normalized constants (e.g. `TEXT_GENERATION`, `VISION`).
2. **Blind Fallback**: `foreground_model_routing.py` must be upgraded/replaced by a `RoutingEngine` that performs Capability-Preserving Fallback.
3. **Implicit Task Requirements**: Currently, if a task needs vision, the user has to manually select a vision model. We need a `TaskRequirements` object.

## 4. What Can Be Reused
- Existing UI for model configuration.
- `endpoint_resolver.py` (hardware-fit and endpoint resolution logic).
- Basic connection wrappers in `llm_core.py` and Phase 3 `ContextEngine` formatting boundaries.
- Local model connectors (Ollama, LM Studio).

## 5. Security Concerns
- Credentials currently float freely into the `agent_loop`. A proper `ProviderRegistry` should isolate API keys and auth headers so that the routing engine can select a provider without the agent loop needing direct access to the raw keys, preserving Phase 1 Secure Execution boundaries.
