import json
import logging
from typing import Dict, Any, List, Optional
from src.llm_core import llm_call_async

logger = logging.getLogger(__name__)

ROUTER_PROMPT = """You are the "Model Fabric Orchestrator" for the Aurex Cognitive OS. Your job is to intercept the user's prompt, analyze the task requirements, and intelligently route the request to the absolute best LLM for the job. You will output the selected model category and a brief justification.

Available Model Categories:
1. VISION_MODEL: Used when the user uploads an image, PDF, or visual file.
2. REASONING_MODEL: Used ONLY for complex logic, advanced mathematics, or deep problem solving that requires step-by-step internal thought.
3. GENERATION_MODEL: Used for writing long essays, generating massive study plans, summarizing huge documents, or general chatting.
4. CODING_MODEL: Used for writing, debugging, or analyzing software code and repositories.

CRITICAL ROUTING RULES:
* Rule 1 - The Vision Check: If the input context contains an image, screenshot, or visual element, you MUST route to a VISION_MODEL with a large context window. Standard text models will crash.
* Rule 2 - The Massive Generation Trap: If the user asks for a massive output (e.g., "write a full 2-day schedule", "generate a 20-page report", "create 500 flashcards", or "write study notes"), you MUST route to a GENERATION_MODEL (a non-reasoning model). CRITICAL: Do NOT use a REASONING_MODEL for massive generation or note-taking. Reasoning models generate thousands of hidden tokens in a <think> block which counts toward the strict Output Limit (usually 4k - 8k tokens). This will cause the response to get forcefully cut off mid-way before the task is finished.
* Rule 3 - The Reasoning Check: If the task requires solving a complex math theorem, deep logic puzzle, or strategic planning—and does *not* require a massive word-count output—route to a REASONING_MODEL.
* Rule 4 - The System & Tool Check: If the user's prompt implies they need to run shell commands, interact with the operating system, edit files, create PDFs/PPTXs, or use complex tools, you MUST route to a CODING_MODEL. Coding models are heavily optimized for strict JSON tool-calling and system access.
* Rule 5 - The Default: If the task is simple (e.g., "summarize this paragraph" or "what is the capital of France"), route to a fast, cheap, free GENERATION_MODEL to save API costs.

Output Format (Strict JSON):
{
  "selected_category": "GENERATION_MODEL",
  "justification": "The user requested a massive study plan. Routing to a non-reasoning model to avoid hitting the output limit from hidden <think> tokens."
}"""

async def determine_best_model(user_prompt: str, has_images: bool, available_models: List[Dict]) -> Dict[str, str]:
    # Find a fast model to act as the router. Prefer gpt-4o-mini, claude-3-haiku, llama3, etc.
    router_model_id = None
    router_url = None
    
    # Categorize available models
    categories = {
        "VISION_MODEL": None,
        "REASONING_MODEL": None,
        "GENERATION_MODEL": None,
        "CODING_MODEL": None
    }
    
    for m in available_models:
        mid = m["id"].lower()
        url = m["url"]
        
        # Pick a router (fast/cheap)
        if not router_model_id and any(x in mid for x in ["mini", "haiku", "llama3-8b", "flash"]):
            router_model_id = m["id"]
            router_url = url
            
        # Classify for destinations
        if "vision" in mid or "gpt-4o" in mid or "claude-3.5-sonnet" in mid:
            if not categories["VISION_MODEL"]: categories["VISION_MODEL"] = m
        if "reasoning" in mid or "o1" in mid or "deepseek-r1" in mid or "math" in mid:
            if not categories["REASONING_MODEL"]: categories["REASONING_MODEL"] = m
        if "coder" in mid or "claude-3.5-sonnet" in mid or "qwen2.5-coder" in mid:
            if not categories["CODING_MODEL"]: categories["CODING_MODEL"] = m
        if "claude" in mid or "gpt" in mid or "llama" in mid:
            if not categories["GENERATION_MODEL"]: categories["GENERATION_MODEL"] = m
            
    # Fill in blanks with fallbacks
    fallback = categories["GENERATION_MODEL"] or available_models[0]
    for k in categories:
        if not categories[k]:
            categories[k] = fallback
            
    if not router_model_id:
        router_model_id = fallback["id"]
        router_url = fallback["url"]
        
    messages = [
        {"role": "system", "content": ROUTER_PROMPT},
        {"role": "user", "content": f"HAS_IMAGES: {has_images}\n\nUSER PROMPT:\n{user_prompt}"}
    ]
    
    try:
        response_text = await llm_call_async(
            url=router_url,
            model=router_model_id,
            messages=messages,
            temperature=0.0,
            max_tokens=100
        )
        # Extract JSON
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()
            
        decision = json.loads(json_str)
        cat = decision.get("selected_category", "GENERATION_MODEL")
        just = decision.get("justification", "Auto-routed.")
        
        chosen_model = categories.get(cat, fallback)
        
        return {
            "category": cat,
            "justification": just,
            "model_id": chosen_model["id"],
            "endpoint_url": chosen_model["url"],
            "endpoint_id": chosen_model["endpoint_id"]
        }
    except Exception as e:
        logger.error(f"Auto-router failed: {e}")
        return {
            "category": "GENERATION_MODEL",
            "justification": "Router failed, falling back.",
            "model_id": fallback["id"],
            "endpoint_url": fallback["url"],
            "endpoint_id": fallback["endpoint_id"]
        }
