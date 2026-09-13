"""
Agent 6 — Policy RAG Agent (Dedicated, NVIDIA-Powered)
The single agent responsible for retrieval-augmented answering over company policies.
All other agents requiring policy checks call this agent.
Uses Pinecone vector query + NVIDIA NIM LLM with Gemini secondary fallback
and deterministic BM25 section-level policy retrieval.
Includes similarity threshold guardrails (confidence: low if weak match).
"""

import os
import sys
import json
import re
import math
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

from backend.models import Agent6Output
from backend.database import log_audit
from backend.agents.base import call_nvidia_llm, has_valid_key, get_gemini_client, SIMULATED_AI

# Ensure rag directory is importable
RAG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "rag"))
if RAG_DIR not in sys.path:
    sys.path.insert(0, RAG_DIR)

load_dotenv()

# Standard stop words to prevent common filler terms from hijacking similarity scoring
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", 
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", 
    "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", 
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", 
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", 
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", 
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "s", "same", "she", 
    "should", "so", "some", "such", "t", "than", "that", "the", "their", "theirs", "them", 
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too", 
    "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which", 
    "while", "who", "whom", "why", "will", "with", "would", "you", "your", "yours", "yourself",
}

# Cache for local policy chunks and inverted index
_POLICY_CACHE: Dict[str, Any] = {
    "mtime": 0.0,
    "chunks": [],
    "idf": {},
    "avg_dl": 0.0,
}


def _stem_word(w: str) -> str:
    """Lightweight rule-based morphological stemmer for English domain terms."""
    w = w.lower().strip()
    if len(w) <= 3:
        return w

    # Core customer service domain keyword normalizations
    for prefix in ("deliver", "cancel", "replac", "refund", "return", "damag", "defect", "eligib"):
        if w.startswith(prefix):
            return prefix

    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        return w[:-3]
    if w.endswith("ed") and len(w) > 4:
        return w[:-2]
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    if w.endswith("ment") and len(w) > 6:
        return w[:-4]
    if w.endswith("able") and len(w) > 6:
        return w[:-4]
    if w.endswith("tion") and len(w) > 6:
        return w[:-4]
    return w


def _tokenize(text: str) -> List[str]:
    """Tokenizes text into normalized stems, splitting punctuation and stripping stop words."""
    words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
    return [_stem_word(w) for w in words if w not in STOP_WORDS and len(w) > 1]


def _clean_text(text: str) -> str:
    """Normalize unicode dashes and whitespace for clean terminal and log display."""
    return (
        text.replace("\u2014", " - ")
        .replace("\u2013", " - ")
        .replace("\u2212", "-")
        .strip()
    )


def _load_policy_chunks() -> Tuple[List[Dict[str, Any]], Dict[str, float], float]:
    """
    Parses combined_policies.md into discrete section chunks with BM25 statistics.
    Automatically reloads if the underlying policy document is edited (supports mid-demo updates).
    """
    global _POLICY_CACHE
    policy_path = os.path.join(RAG_DIR, "combined_policies.md")
    if not os.path.exists(policy_path):
        return [], {}, 0.0

    current_mtime = os.path.getmtime(policy_path)
    if _POLICY_CACHE["chunks"] and _POLICY_CACHE["mtime"] == current_mtime:
        return _POLICY_CACHE["chunks"], _POLICY_CACHE["idf"], _POLICY_CACHE["avg_dl"]

    with open(policy_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    blocks = [b.strip() for b in raw_text.split("\n---\n") if b.strip()]
    all_chunks = []

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("# "):
            continue
        doc_title = _clean_text(lines[0].replace("# ", "").strip())
        category = doc_title.lower().replace(" ", "_").replace("-", "_")

        sections = re.split(r"\n(?=## )", block)
        for sec in sections:
            sec = sec.strip()
            if not sec or sec.startswith("# "):
                continue

            sec_lines = sec.splitlines()
            sec_heading = _clean_text(sec_lines[0].replace("## ", "").strip()) if sec_lines else ""
            body = "\n".join(sec_lines[1:]).strip() if len(sec_lines) > 1 else sec
            body_clean = _clean_text(body)
            full_clean = f"## {sec_heading}\n{body_clean}" if sec_heading else body_clean

            token_source = f"{doc_title} {sec_heading} {body_clean}"
            all_chunks.append({
                "source": doc_title,
                "section": sec_heading,
                "category": category,
                "text": full_clean,
                "body": body_clean,
                "tokens": _tokenize(token_source)
            })

    # Compute BM25 Inverse Document Frequencies (IDF)
    total_docs = len(all_chunks)
    df: Dict[str, int] = {}
    for c in all_chunks:
        unique_terms = set(c["tokens"])
        for t in unique_terms:
            df[t] = df.get(t, 0) + 1

    idf: Dict[str, float] = {}
    for t, count in df.items():
        idf[t] = math.log(1.0 + (total_docs - count + 0.5) / (count + 0.5))

    avg_dl = sum(len(c["tokens"]) for c in all_chunks) / max(total_docs, 1)

    _POLICY_CACHE = {
        "mtime": current_mtime,
        "chunks": all_chunks,
        "idf": idf,
        "avg_dl": avg_dl,
    }
    return all_chunks, idf, avg_dl


def _local_policy_search(question: str, top_k: int = 4) -> Dict[str, Any]:
    """
    High-precision BM25 policy search over combined_policies.md.
    Features:
      - Term rarity (IDF) weighting.
      - Document and section title field boosts.
      - Phrase matching for domain rules (return window, out of stock, pre-shipment, etc.).
      - Intent disambiguation (prevents cancellation clauses from hijacking standard return questions).
      - Strict low-confidence detection for out-of-scope/unrelated questions.
    """
    chunks, idf, avg_dl = _load_policy_chunks()
    if not chunks:
        return {"chunks": [], "top_score": 0.0, "low_confidence": True}

    q_tokens = _tokenize(question)
    q_lower = question.lower()
    if not q_tokens:
        return {"chunks": [], "top_score": 0.0, "low_confidence": True}

    k1 = 1.2
    b = 0.75
    scored: List[Tuple[float, Dict[str, Any]]] = []

    for c in chunks:
        tokens = c["tokens"]
        doc_len = len(tokens)
        score = 0.0

        # Term frequencies for chunk
        tf_map: Dict[str, int] = {}
        for t in tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        for qt in q_tokens:
            if qt in tf_map:
                tf = tf_map[qt]
                term_idf = idf.get(qt, 1.0)
                term_score = term_idf * (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (doc_len / avg_dl)))
                score += term_score

        # Field boosts: query terms matching doc title and section heading
        title_tokens = set(_tokenize(c["source"]))
        sec_tokens = set(_tokenize(c["section"]))
        score += len(set(q_tokens).intersection(title_tokens)) * 1.5
        score += len(set(q_tokens).intersection(sec_tokens)) * 2.0

        c_text_lower = c["text"].lower()

        # Domain phrase boosts
        if "return window" in q_lower and "return window" in c_text_lower:
            score += 3.0
        if "out of stock" in q_lower and ("out of stock" in c_text_lower or "zero available stock" in c_text_lower):
            score += 4.0
        if "fallback" in q_lower and "fallback" in c_text_lower:
            score += 3.0
        if any(d in q_tokens for d in ["defect", "defective", "damag", "broken", "faulty"]) and any(d in c["tokens"] for d in ["defect", "damag"]):
            score += 3.5
        if (any(term in q_lower for term in ["final sale", "personalized", "customized"]) or re.search(r"\bcustom\b", q_lower)) and (any(term in c_text_lower for term in ["final sale", "personalized", "customized"]) or re.search(r"\bcustom\b", c_text_lower)):
            score += 3.5
        if "cash on delivery" in q_lower and "cash-on-delivery" in c_text_lower:
            score += 4.0
        if any(p in q_lower for p in ["pre-shipment", "before shipment", "not shipped", "status is placed"]) and "pre-shipment" in c_text_lower:
            score += 3.5
        if any(p in q_lower for p in ["post-shipment", "status is shipped", "already shipped"]) and "post-shipment" in c_text_lower:
            score += 3.5

        # Disambiguation penalties:
        # 1. Pure cancellation questions should prioritize Cancellation Rules Policy
        if "cancel" in q_lower and not ("return" in q_lower or "refund" in q_lower or "replace" in q_lower):
            if "cancellation" not in c["category"]:
                score *= 0.5
        # 2. Pure return/refund/replace questions should not match Post-Shipment Cancellation clauses
        if ("return" in q_lower or "refund" in q_lower or "replace" in q_lower) and "cancel" not in q_lower:
            if "cancellation" in c["category"]:
                score *= 0.3

        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_matches = scored[:top_k]

    raw_top = top_matches[0][0] if top_matches else 0.0
    # Normalize BM25 top score into a 0.0 - 1.0 confidence index
    norm_score = round(min(1.0, raw_top / 10.0), 3)

    retrieved = [
        {
            "text": item[1]["text"],
            "body": item[1]["body"],
            "source": item[1]["source"],
            "section": item[1]["section"],
            "category": item[1]["category"],
            "score": round(item[0], 3)
        }
        for item in top_matches if item[0] > 1.2
    ]

    top_score = norm_score if retrieved else 0.0
    return {
        "chunks": retrieved,
        "top_score": top_score,
        "low_confidence": top_score < 0.25 or not retrieved
    }


def query_pinecone_or_fallback(question: str, top_k: int = 4) -> Dict[str, Any]:
    """
    Executes pinecone_query if live Pinecone & NVIDIA keys are available,
    otherwise uses high-precision local policy search fallback.
    """
    pinecone_key = os.environ.get("PINECONE_API_KEY", "")
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")

    if has_valid_key(pinecone_key) and has_valid_key(nvidia_key):
        try:
            from rag.agent6_rag_query import pinecone_query
            res = pinecone_query(question, top_k=top_k)
            # Ensure each chunk has clean section field
            for c in res.get("chunks", []):
                if not c.get("section"):
                    sec_match = re.match(r"^##\s+([^\n]+)", c.get("text", ""))
                    c["section"] = sec_match.group(1).strip() if sec_match else c.get("category", "")
                if not c.get("body"):
                    c["body"] = re.sub(r"^##\s+[^\n]+\n*", "", c.get("text", "")).strip()
            return res
        except Exception as e:
            print(f"[Agent 6] Pinecone query failed, falling back to local search: {e}")

    return _local_policy_search(question, top_k=top_k)


def run_agent6_policy_rag(question: str, case_id: Optional[str] = None) -> Agent6Output:
    """
    Agent 6 execution function:
    1. Query Pinecone (or fallback BM25) for top-k chunks.
    2. Check similarity threshold guardrails (confidence: low if weak match).
    3. If low confidence: return confidence: 'low' directly without hallucinating.
    4. Pass chunks to NVIDIA NIM LLM (or Gemini fallback) to generate cited answer.
    5. In deterministic/offline mode: synthesize a clean, cited response from top clauses.
    """
    retrieval_res = query_pinecone_or_fallback(question)
    chunks = retrieval_res.get("chunks", [])
    low_confidence = retrieval_res.get("low_confidence", False)
    top_score = retrieval_res.get("top_score", 0.0)

    try:
        log_audit(
            case_id,
            "Agent6PolicyRAG",
            "pinecone_query",
            {
                "question": question,
                "top_score": top_score,
                "low_confidence": low_confidence,
                "chunk_count": len(chunks)
            }
        )
    except Exception as e:
        print(f"[Agent 6] Audit log notice: {e}")

    # Similarity threshold guardrail: reject irrelevant questions without hallucinating
    if low_confidence or not chunks:
        output = Agent6Output(
            answer="No relevant company policy found with sufficient confidence to answer this question.",
            supporting_snippets=[],
            source_documents=[],
            confidence="low"
        )
        try:
            log_audit(case_id, "Agent6PolicyRAG", "policy_response", output.model_dump())
        except Exception:
            pass
        return output

    # Build context and clean citations
    context_blocks = []
    sources = []
    snippets = []

    for i, c in enumerate(chunks):
        sec_title = c.get("section") or c.get("category", "")
        src_label = f"{c['source']} (Section {sec_title})" if sec_title else c["source"]
        if src_label not in sources:
            sources.append(src_label)

        # Snippet: clean clause body with clean boundary truncation
        body_text = c.get("body") or re.sub(r"^##\s+[^\n]+\n*", "", c.get("text", "")).strip()
        body_text = _clean_text(body_text)
        if len(body_text) > 250:
            truncated = body_text[:247].rsplit(" ", 1)[0] + "..."
        else:
            truncated = body_text
        snippets.append(truncated)

        context_blocks.append(f"--- CHUNK {i+1} [Source: {src_label}] ---\n{c['text']}")

    context_str = "\n\n".join(context_blocks)

    system_prompt = (
        "You are the dedicated Company Policy RAG Agent. "
        "Answer the question ONLY based on the provided policy chunks. "
        "Do NOT invent or fabricate any exceptions, numbers, or rules. "
        "Cite the source document and section in your answer."
    )
    user_prompt = (
        f"POLICY CONTEXT:\n{context_str}\n\n"
        f"QUESTION: {question}\n\n"
        "Provide a concise, direct answer citing the relevant policy clauses."
    )

    # Multi-tier LLM generation:
    # 1. Primary: NVIDIA NIM LLaMA-3 70B
    generated_answer = call_nvidia_llm(user_prompt, system_prompt)

    # 2. Secondary: Google Gemini Flash (if NVIDIA key not configured or failed)
    if not generated_answer and not SIMULATED_AI:
        gemini_client = get_gemini_client()
        if gemini_client:
            try:
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                resp = gemini_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=full_prompt
                )
                generated_answer = (resp.text or "").strip()
            except Exception as e:
                print(f"[Agent 6] Gemini generation fallback warning: {e}")

    # 3. Deterministic fallback: cleanly synthesize answer from top matching clauses
    if not generated_answer:
        clean_clauses = []
        for c in chunks[:2]:
            sec_title = c.get("section") or c.get("category", "")
            clause_body = c.get("body") or re.sub(r"^##\s+[^\n]+\n*", "", c.get("text", "")).strip()
            clause_body = _clean_text(clause_body)
            clean_clauses.append(f"According to {c['source']} ({sec_title}): {clause_body}")
        generated_answer = "\n\n".join(clean_clauses)

    confidence = "high" if top_score >= 0.50 else "medium"

    output = Agent6Output(
        answer=generated_answer.strip(),
        supporting_snippets=snippets[:3],
        source_documents=sources[:3],
        confidence=confidence
    )

    try:
        log_audit(case_id, "Agent6PolicyRAG", "policy_response", output.model_dump())
    except Exception:
        pass
    return output
