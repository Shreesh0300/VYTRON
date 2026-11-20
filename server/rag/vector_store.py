"""
VYTRON RAG — ChromaDB Vector Store & Embedding Engine
Manages persistent local vector embeddings via SentenceTransformers ('all-MiniLM-L6-v2')
and provides semantic similarity search across troubleshooting documents.
"""

import os
from typing import Any
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from server.rag.ingestion import DocumentLoader, TextChunker, DocumentChunk

CHROMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "chroma_db"
)
KNOWLEDGE_BASE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "knowledge_base"
)
COLLECTION_NAME = "vytron_troubleshooting_kb"
MODEL_NAME = "all-MiniLM-L6-v2"

class VectorStore:
    def __init__(self, persist_dir: str = CHROMA_DIR):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        
        # Initialize persistent ChromaDB client
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        
        # Initialize SentenceTransformers embedding function
        self.embed_fn = self._init_embedding_function()
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embed_fn,
            metadata={"description": "VYTRON AIOps Infrastructure Troubleshooting Knowledge Base"}
        )

        # Ingest documents if collection is empty
        if self.collection.count() == 0:
            print("[VectorStore] Knowledge base collection is empty. Starting initial document ingestion...")
            self.ingest_knowledge_base()
        else:
            print(f"[VectorStore] Loaded persistent collection '{COLLECTION_NAME}' with {self.collection.count()} chunks.")

    def _init_embedding_function(self):
        """Initializes SentenceTransformerEmbeddingFunction with resilient fallback."""
        try:
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=MODEL_NAME
            )
        except Exception as e:
            print(f"[VectorStore] Warning: SentenceTransformers load error ({e}). Falling back to DefaultEmbeddingFunction.")
            return embedding_functions.DefaultEmbeddingFunction()

    def ingest_knowledge_base(self, kb_dir: str = KNOWLEDGE_BASE_DIR) -> int:
        """Loads, cleans, chunks, and indexes all documents from knowledge_base directory."""
        loader = DocumentLoader(kb_dir)
        chunker = TextChunker(target_chunk_size=650, chunk_overlap=120)

        docs = loader.load_all()
        if not docs:
            print(f"[VectorStore] No documents found in {kb_dir}")
            return 0

        all_chunks: list[DocumentChunk] = []
        for doc in docs:
            chunks = chunker.chunk_document(doc)
            all_chunks.extend(chunks)

        if not all_chunks:
            return 0

        ids = [c.chunk_id for c in all_chunks]
        documents = [c.content for c in all_chunks]
        metadatas = [c.metadata for c in all_chunks]

        # Upsert in batches of 50 to avoid memory spikes
        batch_size = 50
        total_ingested = 0
        for i in range(0, len(all_chunks), batch_size):
            b_ids = ids[i : i + batch_size]
            b_docs = documents[i : i + batch_size]
            b_metas = metadatas[i : i + batch_size]

            self.collection.upsert(
                ids=b_ids,
                documents=b_docs,
                metadatas=b_metas
            )
            total_ingested += len(b_ids)

        print(f"[VectorStore] Successfully ingested {total_ingested} chunks into '{COLLECTION_NAME}'.")
        return total_ingested

    def search(
        self,
        query_text: str,
        n_results: int = 4,
        where_filter: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Performs semantic similarity search against indexed technical documentation.
        Returns sorted document chunks with metadata and relevance scores.
        """
        if self.collection.count() == 0:
            return []

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=min(n_results, self.collection.count()),
                where=where_filter,
            )
        except Exception as e:
            print(f"[VectorStore] Query error ({e}). Retrying without metadata filter...")
            results = self.collection.query(
                query_texts=[query_text],
                n_results=min(n_results, self.collection.count()),
            )

        output: list[dict[str, Any]] = []
        if not results or not results["documents"] or not results["documents"][0]:
            return output

        docs = results["documents"][0]
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
        ids = results["ids"][0] if results.get("ids") else [""] * len(docs)

        for i in range(len(docs)):
            # Convert cosine distance to similarity score between 0.0 and 1.0
            dist = distances[i] if i < len(distances) else 1.0
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))

            output.append({
                "chunk_id": ids[i],
                "content": docs[i],
                "metadata": metas[i],
                "distance": dist,
                "relevance_score": round(similarity, 3),
            })

        return output

    def get_all_sources(self) -> list[dict[str, Any]]:
        """Returns catalog of all loaded knowledge base documents (Markdown and Official PDF manuals)."""
        loader = DocumentLoader(KNOWLEDGE_BASE_DIR)
        docs = loader.load_all()
        sources = []
        for d in docs:
            m = d["metadata"]
            sources.append({
                "doc_name": d["doc_name"],
                "title": m.get("title", d["doc_name"]),
                "source": m.get("source", "Technical Documentation"),
                "url": m.get("url", ""),
                "category": m.get("category", "General"),
                "server_relevance": m.get("server_relevance", ["ALL"]),
            })

        # Add official technical PDF sources from knowledge taxonomy
        pdf_sources = [
            {
                "doc_name": "canonical-ubuntu-server-documentation-readthedocs-hosted-com-en-latest.pdf",
                "title": "Ubuntu Server Official Documentation",
                "source": "Canonical Ubuntu Documentation",
                "url": "https://ubuntu.com/server/docs",
                "category": "Linux & OS Operations",
                "server_relevance": ["APP-01", "DB-01", "AUTH-01", "BACKUP-01", "NETWORK-01"],
            },
            {
                "doc_name": "postgresql-19-A4.pdf",
                "title": "PostgreSQL Official Technical Manual",
                "source": "The PostgreSQL Global Development Group",
                "url": "https://www.postgresql.org/docs/",
                "category": "Database & Query Performance",
                "server_relevance": ["DB-01", "APP-01"],
            },
            {
                "doc_name": "Reference.pdf",
                "title": "Kubernetes API & Architecture Reference",
                "source": "Kubernetes Official Documentation (CNCF)",
                "url": "https://kubernetes.io/docs/reference/",
                "category": "Container Orchestration & Networking",
                "server_relevance": ["APP-01", "NETWORK-01", "AUTH-01"],
            },
            {
                "doc_name": "troubleshoot-windows-server.pdf",
                "title": "Microsoft Windows Server Troubleshooting Guide",
                "source": "Microsoft Learn Documentation",
                "url": "https://learn.microsoft.com/en-us/troubleshoot/windows-server/",
                "category": "Windows Server & Enterprise Networking",
                "server_relevance": ["APP-01", "NETWORK-01", "AUTH-01", "BACKUP-01"],
            },
        ]
        sources.extend(pdf_sources)
        return sources
