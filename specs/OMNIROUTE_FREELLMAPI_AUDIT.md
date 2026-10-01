# OMNIROUTE & FREELLMAPI DEEP AUDIT

## OmniRoute Analysis
1. **OpenAI-compatible endpoint:** Exposed via standard `/v1/chat/completions` API conforming exactly to OpenAI request/response schemas.
2. **Model discovery:** Exposes `/v1/models` endpoint returning a JSON array of `Model` objects, often mapping upstream provider models.
3. **Usage reporting:** Injects `usage` metadata (prompt_tokens, completion_tokens) directly into standard OpenAI completion responses.
4. **Error reporting:** Returns standard HTTP 4xx/5xx status codes with JSON error payloads (`{"error": {"message": "..."}}`).
5. **Context limits:** Relies heavily on upstream errors (e.g. 400 Context Length Exceeded). Some configurations perform internal token counting.
6. **Fallback:** Configurable retry and fallback loops in the routing layer, iterating through multiple providers automatically on 429/5xx errors.
7. **Context relay:** Passes standard OpenAI `messages` array transparently; some branches handle system-prompt coalescing.
8. **Compression:** Some experimental internal logic for removing system prompts or truncating `messages` arrays, but often semantically lossy.

## FreeLLMAPI Analysis
9. **OpenAI-compatible endpoint:** Provides a `/v1/chat/completions` proxy mimicking OpenAI.
10. **Model reporting:** `/v1/models` dynamically populated based on current free-tier API scraping.
11. **Usage reporting:** Often mocked or passed-through directly from the upstream free provider; accuracy varies.
12. **Rate limits:** Extremely volatile. Often returns 429 Too Many Requests when upstream free providers throttle.
13. **Provider failure:** Frequently returns 500 or 503 when the scraped endpoint changes or goes offline.
14. **Metadata exposure:** Typically exposes model name and ID, but lacks reliable pricing/quota metadata since it's "free".
15. **Untrustworthy info:** Context window limits and guaranteed availability are completely untrustworthy on FreeLLMAPI.
16. **Authentication:** Uses a generic API key passed via standard `Bearer` token header.
17. **Credentials:** The gateway itself holds the upstream credentials; Aurex only needs the gateway API key.
18. **Log leaks:** High risk. Both gateways, depending on deployment, may log raw `messages` (including PII) to standard out.
19. **Local execution:** OmniRoute can route to local Ollama; FreeLLMAPI is strictly external web scraping.
20. **Context limitations:** Both gateways impose their own hard-coded Nginx/proxy body size limits (e.g., 2MB payload cap) completely independent of token limits.

## Architectural Conclusions
- **Never trust model discovery completely.** Aurex Provider Intelligence must verify context windows and maintain its own health status.
- **Context sizing is Aurex's job.** Do not rely on either gateway to gracefully handle context overflow. Aurex must shrink context *before* sending.
- **Do not send raw sensitive data** to FreeLLMAPI due to logging risks.
- **Implement ProviderPool abstraction** to treat both gateways identically as opaque downstream routers.

