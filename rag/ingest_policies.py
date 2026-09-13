"""
One-time (or re-run-as-needed) ingestion script.
Reads all .md files in this folder, chunks them by section (##),
embeds each chunk, and upserts into a Pinecone index.

Run this after writing/editing any policy doc, and again whenever
you want to simulate a "policy update mid-demo" by editing
04_loyalty_exceptions.md and re-running.
"""

import os
import re
from pinecone import Pinecone
from embedding import embed, EMBEDDING_DIM  # shared module — also used by Agent 6

# --- CONFIG ---
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "YOUR_PINECONE_KEY")
INDEX_NAME = "company-policies"
POLICY_DIR = os.path.dirname(__file__)

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)
# NOTE: when creating this Pinecone index (one-time setup, e.g. via the
# Pinecone console or pc.create_index()), set dimension=EMBEDDING_DIM (1024)
# and metric="cosine" to match NVIDIA's nv-embedqa-e5-v5 model.


def chunk_by_section(text: str) -> list[dict]:
    """
    Splits a markdown policy doc into chunks by '## ' headings,
    keeping each numbered rule's full clause intact rather than
    splitting mid-sentence.
    """
    sections = re.split(r"\n(?=## )", text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section or section.startswith("# "):
            # skip the top-level title-only line, keep everything else
            if section.startswith("# ") and "\n" in section:
                section = section.split("\n", 1)[1].strip()
            else:
                continue
        if section:
            chunks.append(section)
    return chunks


def main():
    for filename in sorted(os.listdir(POLICY_DIR)):
        if not filename.endswith(".md"):
            continue

        category = filename.replace(".md", "").split("_", 1)[-1]
        path = os.path.join(POLICY_DIR, filename)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_by_section(text)
        vectors = []
        for i, chunk in enumerate(chunks):
            vector_id = f"{filename}-{i}"
            embedding = embed(chunk, input_type="passage")
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "source": filename,
                    "category": category,
                    "text": chunk,
                }
            })

        if vectors:
            index.upsert(vectors=vectors)
            print(f"Ingested {len(vectors)} chunks from {filename}")

    print("Ingestion complete.")


def chunk_combined_file(text: str) -> list[dict]:
    """
    For the single combined_policies.md file: splits first on '---'
    dividers into per-document blocks, then further splits each
    block by '## ' headings (same rule-level granularity as the
    multi-file mode). Each chunk keeps track of which original
    policy section it came from via its '# ' title line.
    """
    blocks = [b.strip() for b in text.split("\n---\n") if b.strip()]
    all_chunks = []
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines or not lines[0].startswith("# "):
            continue  # skip the handbook title block itself
        doc_title = lines[0].replace("# ", "").strip()
        category = doc_title.lower().replace(" ", "_").replace("-", "_")
        sub_chunks = chunk_by_section(block)
        for sc in sub_chunks:
            all_chunks.append({"category": category, "source": doc_title, "text": sc})
    return all_chunks


def main_combined(filepath: str = "combined_policies.md"):
    """
    Use this instead of main() if you're handing Antigravity the
    single combined_policies.md file rather than 8 separate files.
    """
    path = os.path.join(POLICY_DIR, filepath)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = chunk_combined_file(text)
    vectors = []
    for i, c in enumerate(chunks):
        vector_id = f"combined-{c['category']}-{i}"
        embedding = embed(c["text"], input_type="passage")
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "source": c["source"],
                "category": c["category"],
                "text": c["text"],
            }
        })

    if vectors:
        index.upsert(vectors=vectors)
        print(f"Ingested {len(vectors)} chunks from {filepath}")
    print("Ingestion complete.")


if __name__ == "__main__":
    # Default to combined-file mode since that's what's typically handed
    # to Antigravity. Switch to main() if using the 8 separate .md files.
    main_combined()
