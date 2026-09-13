"""
Reference implementation of the `pinecone_query` tool used by Agent 6
(the Policy RAG Agent). Wire this into your FastAPI tool endpoint.

Uses the SAME embedding module as ingest_policies.py — this is the
piece that must stay consistent for retrieval to actually work.
"""

import os
from pinecone import Pinecone

try:
    from embedding import embed  # shared module, same one ingest_policies.py uses
except ImportError:
    from rag.embedding import embed

LOW_CONFIDENCE_THRESHOLD = 0.35  # cosine similarity below this = treat as no-match

_index = None


def get_index():
    global _index
    if _index is None:
        api_key = os.environ.get("PINECONE_API_KEY", "")
        index_name = os.environ.get("PINECONE_INDEX_NAME", "company-policies")
        pc = Pinecone(api_key=api_key)
        _index = pc.Index(index_name)
    return _index


def pinecone_query(question: str, top_k: int = 4) -> dict:
    """
    Called by Agent 6 when it needs to answer a policy question.
    Returns retrieved chunks + a confidence signal so Agent 6 can
    decide whether to trust the result or return confidence: "low".
    """
    index = get_index()
    query_vector = embed(question, input_type="query")  # "query" not "passage" — asymmetric model

    results = index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
    )

    matches = results.get("matches", [])
    chunks = [
        {
            "text": m["metadata"]["text"],
            "source": m["metadata"]["source"],
            "category": m["metadata"]["category"],
            "score": m["score"],
        }
        for m in matches
    ]

    top_score = chunks[0]["score"] if chunks else 0.0

    return {
        "chunks": chunks,
        "top_score": top_score,
        "low_confidence": top_score < LOW_CONFIDENCE_THRESHOLD,
    }


# --- Example usage inside Agent 6's tool-calling flow ---
# result = pinecone_query("Can a premium customer return an item after 35 days?")
# if result["low_confidence"]:
#     # Agent 6 should return confidence: "low" rather than letting the LLM guess
#     ...
# else:
#     # pass result["chunks"] to the NVIDIA-hosted LLM as context, with instructions
#     # to answer only from these chunks and cite which one(s) supported the answer
#     ...
