"""Agent grader????????????????"""
from __future__ import annotations

import json
import logging
import re

from app.config import get_settings

logger = logging.getLogger(__name__)


def ngram_overlap(query: str, text: str, n: int = 3) -> float:
    """?? n-gram ????query ???? text ?? n-gram ???"""
    q_ngrams = {query[i:i+n] for i in range(len(query)-n+1)}
    if not q_ngrams:
        return 0.0
    t_ngrams = {text[i:i+n] for i in range(len(text)-n+1)}
    overlap = q_ngrams & t_ngrams
    return len(overlap) / len(q_ngrams)


def llm_grade(query: str, context: str) -> dict:
    """???? LLM ???????????????????"""
    from app.llm_zhipu import get_zhipu_client
    
    settings = get_settings()
    prompt = f"""???? AI ??????????????????????????????????????

??? JSON??????????

{{
  "sufficient": true/false,
  "confidence": 0.0-1.0,
  "missing_info": "?????????????",
  "rewrite_hint": "??????????????????????"
}}

???{query}

?????
{context}
"""
    client = get_zhipu_client()
    try:
        resp = client.chat.completions.create(
            model=settings.zhipu_chat_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=512,
        )
        text = resp.choices[0].message.content.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text).rstrip("`").strip()
        return json.loads(text)
    except Exception as exc:
        logger.warning("LLM grader ??: %s??????", exc)
        return {"sufficient": False, "confidence": 0.0, "missing_info": "", "rewrite_hint": ""}


def grade_sufficiency(query: str, context: str) -> dict:
    """?????auto ???? LLM Key ? LLM???????"""
    settings = get_settings()
    mode = getattr(settings, "agent_grader_mode", "auto")
    if mode == "llm" or (mode == "auto" and getattr(settings, "zhipuai_api_key", None)):
        result = llm_grade(query, context)
        if result.get("sufficient"):
            return result
    
    # ????n-gram ???
    overlap = ngram_overlap(query, context)
    min_overlap = getattr(settings, "agent_grader_min_query_overlap", 0.12)
    sufficient = overlap >= min_overlap
    return {
        "sufficient": sufficient,
        "confidence": min(overlap * 2, 1.0),
        "missing_info": "",
        "rewrite_hint": query if not sufficient else "",
    }
