"""
VYTRON RAG — Master Troubleshooting Pipeline
Coordinates contextual query building, ChromaDB vector retrieval, and LLM guidance synthesis.
"""

from typing import Any
from server.rag.vector_store import VectorStore
from server.rag.query_builder import ContextualQueryBuilder
from server.rag.synthesizer import RAGSynthesizer

# Global singleton vector store instance
_vector_store: VectorStore | None = None
_synthesizer: RAGSynthesizer | None = None

def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store

def get_synthesizer() -> RAGSynthesizer:
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = RAGSynthesizer()
    return _synthesizer

async def troubleshoot_incident(incident: dict[str, Any]) -> dict[str, Any]:
    """
    Executes the end-to-end RAG troubleshooting workflow:
    1. Extracts sanitized evidence & builds contextual semantic query.
    2. Searches ChromaDB for relevant technical documentation chunks.
    3. Synthesizes 8-section guidance via the LLM / grounded expert engine.
    """
    vector_store = get_vector_store()
    synthesizer = get_synthesizer()

    # Step 1: Build semantic query
    query_text, hints = ContextualQueryBuilder.build_query(incident)

    # Step 2: Retrieve relevant chunks from ChromaDB
    retrieved_chunks = vector_store.search(
        query_text=query_text,
        n_results=4
    )

    # Step 3: Synthesize guidance
    guidance = await synthesizer.generate_troubleshooting(
        incident=incident,
        retrieved_chunks=retrieved_chunks
    )

    # Append retrieval metadata for transparency
    guidance["retrieval_query"] = query_text
    guidance["retrieved_chunks_count"] = len(retrieved_chunks)

    return guidance
