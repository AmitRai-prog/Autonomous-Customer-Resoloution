"""
Shared embedding function using NVIDIA's hosted embedding model
(via the NVIDIA API Catalog / NIM endpoint, OpenAI-compatible API).

Import this from BOTH:
  - ingest_policies.py (index time, input_type="passage")
  - Agent 6 / the policy_rag_search tool (query time, input_type="query")

Never re-implement embedding separately in the agent code — importing
this exact function guarantees index-time and query-time vectors are
produced by the same model, which is required for retrieval to work.

Setup:
  1. Get a free API key at https://build.nvidia.com (NVIDIA API Catalog)
  2. pip install openai   (NVIDIA's endpoint is OpenAI-client compatible)
  3. export NVIDIA_API_KEY=your_key_here
"""

import os
from openai import OpenAI

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "YOUR_NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# nv-embedqa-e5-v5: NVIDIA's retrieval-tuned embedding model, 1024-dim.
# This model is ASYMMETRIC — it embeds queries and documents/passages
# differently on purpose (better retrieval accuracy than a single mode).
# That's why input_type matters below; sentence-transformers didn't
# need this distinction, but this model does.
EMBEDDING_MODEL_NAME = "nvidia/nv-embedqa-e5-v5"
EMBEDDING_DIM = 1024  # Pinecone index must be created with this exact dimension

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("NVIDIA_API_KEY", "")
        _client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)
    return _client


def embed(text: str, input_type: str = "passage") -> list[float]:
    """
    input_type must be:
      - "passage" when embedding policy document chunks (ingestion time)
      - "query"   when embedding a customer/agent question (Agent 6 query time)
    Using the wrong input_type for either side measurably hurts retrieval
    quality with this model, since it's trained asymmetrically.
    """
    client = _get_client()
    response = client.embeddings.create(
        input=[text],
        model=EMBEDDING_MODEL_NAME,
        encoding_format="float",
        extra_body={"input_type": input_type, "truncate": "END"},
    )
    return response.data[0].embedding
