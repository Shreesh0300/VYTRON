"""
VYTRON RAG — High-Performance PDF Ingestion & Vector Embedding Engine
Extracts, cleans, chunks, embeds, and indexes official technical documentation PDFs
into the local ChromaDB persistent vector database with full metadata preservation.
"""

import os
import re
import sys
import time
from typing import Any, Generator

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

import chromadb
from sentence_transformers import SentenceTransformer

# ── Paths and Configuration ──────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAG_PDF_DIR = os.path.join(os.path.dirname(BASE_DIR), "rag_pdf")
CHROMA_DIR = os.path.join(BASE_DIR, "data", "chroma_db")
COLLECTION_NAME = "vytron_troubleshooting_kb"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# ── PDF Document Configurations & Taxonomy ──────────────────────────────────
PDF_SPECIFICATIONS = [
    {
        "filename": "canonical-ubuntu-server-documentation-readthedocs-hosted-com-en-latest.pdf",
        "prefix": "ubuntu",
        "title": "Ubuntu Server Official Documentation",
        "source": "Canonical Ubuntu Documentation",
        "url": "https://ubuntu.com/server/docs",
        "category": "Linux & OS Operations",
        "server_relevance": "APP-01, DB-01, AUTH-01, BACKUP-01, NETWORK-01",
        "topics": ["Linux system administration", "networking", "storage", "virtualization", "security", "systemd", "kernel tuning"]
    },
    {
        "filename": "postgresql-19-A4.pdf",
        "prefix": "postgres",
        "title": "PostgreSQL Official Technical Manual",
        "source": "The PostgreSQL Global Development Group",
        "url": "https://www.postgresql.org/docs/",
        "category": "Database & Query Performance",
        "server_relevance": "DB-01, APP-01",
        "topics": ["PostgreSQL query tuning", "indexing", "connection pooling", "locks", "WAL replication", "vacuum", "disk I/O"]
    },
    {
        "filename": "Reference.pdf",
        "prefix": "k8s",
        "title": "Kubernetes API & Architecture Reference",
        "source": "Kubernetes Official Documentation (CNCF)",
        "url": "https://kubernetes.io/docs/reference/",
        "category": "Container Orchestration & Networking",
        "server_relevance": "APP-01, NETWORK-01, AUTH-01",
        "topics": ["Kubernetes API", "pod resource limits", "cluster networking", "ingress controller", "kubelet", "RBAC"]
    },
    {
        "filename": "troubleshoot-windows-server.pdf",
        "prefix": "winserver",
        "title": "Microsoft Windows Server Troubleshooting Guide",
        "source": "Microsoft Learn Documentation",
        "url": "https://learn.microsoft.com/en-us/troubleshoot/windows-server/",
        "category": "Windows Server & Enterprise Networking",
        "server_relevance": "APP-01, NETWORK-01, AUTH-01, BACKUP-01",
        "topics": ["Windows Server diagnostics", "Active Directory", "VSS backup failures", "TCP/IP latency", "event viewer", "memory dumps"]
    },
]

class PDFIngestor:
    def __init__(
        self,
        pdf_dir: str = RAG_PDF_DIR,
        chroma_dir: str = CHROMA_DIR,
        collection_name: str = COLLECTION_NAME,
        chunk_size: int = 850,
        chunk_overlap: int = 150,
        batch_size: int = 128,
        upsert_batch_size: int = 256
    ):
        self.pdf_dir = pdf_dir
        self.chroma_dir = chroma_dir
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.batch_size = batch_size
        self.upsert_batch_size = upsert_batch_size

        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) is not installed. Please install with: pip install pymupdf")

        print(f"[PDFIngestor] Initializing embedding model: {EMBEDDING_MODEL_NAME}...")
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print(f"[PDFIngestor] Initializing ChromaDB PersistentClient at: {self.chroma_dir}...")
        os.makedirs(self.chroma_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.chroma_dir)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "VYTRON AIOps Infrastructure Troubleshooting Knowledge Base"}
        )
        print(f"[PDFIngestor] Target collection '{self.collection_name}' currently has {self.collection.count()} chunks.")

    @staticmethod
    def is_toc_or_index_page(text: str) -> bool:
        """Identifies Table of Contents or index pages with repeating dot leaders or minimal content."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return True
        if len(text.strip()) < 80:
            return True
        # TOC detection: line contains '.... 123'
        dot_lines = sum(1 for l in lines if re.search(r'\.{4,}\s*\d+', l))
        if len(lines) > 5 and (dot_lines / len(lines)) > 0.30:
            return True
        return False

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """Removes control chars, null bytes, and normalizes whitespaces."""
        # Remove null characters and non-printable control codes
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw_text)
        # Normalize multiple spaces and tabs
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        # Normalize excessive newlines (keep at most 2)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    @staticmethod
    def extract_section_title(text: str, default: str) -> str:
        """Extracts candidate section header from the first few non-empty lines."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines[:4]:
            # Look for lines that look like a heading (short, no period at end, or starts with digit/Chapter/Section)
            if 3 < len(line) < 90 and not line.endswith("."):
                return re.sub(r'^[#0-9\.\-\s]+', '', line).strip() or line
        return default

    def chunk_text(self, text: str) -> list[str]:
        """Splits text into chunks of target size with sliding window overlap."""
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                current_chunk = f"{current_chunk}\n\n{para}".strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    overlap = current_chunk[-self.chunk_overlap:]
                    current_chunk = f"{overlap}\n\n{para}".strip()
                else:
                    # Paragraph itself exceeds chunk_size: slice cleanly
                    start = 0
                    while start < len(para):
                        end = min(start + self.chunk_size, len(para))
                        chunks.append(para[start:end].strip())
                        start += (self.chunk_size - self.chunk_overlap)
                    current_chunk = ""

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def process_pdf(self, spec: dict[str, Any]) -> int:
        """
        Extracts, chunks, embeds, and upserts a single PDF document in streaming batches.
        Returns total number of chunks upserted.
        """
        fname = spec["filename"]
        prefix = spec["prefix"]
        title = spec["title"]
        source = spec["source"]
        url = spec["url"]
        category = spec["category"]
        server_relevance = spec["server_relevance"]

        fpath = os.path.join(self.pdf_dir, fname)
        if not os.path.isfile(fpath):
            print(f"[PDFIngestor] Warning: File not found: {fpath}")
            return 0

        t_start = time.time()
        doc = fitz.open(fpath)
        total_pages = len(doc)
        print(f"\n{'='*70}")
        print(f"[PDFIngestor] Processing: {title}")
        print(f"  File: {fname} ({os.path.getsize(fpath) / (1024*1024):.1f} MB | {total_pages} pages)")
        print(f"  Category: {category} | Relevance: {server_relevance}")
        print(f"{'='*70}")

        batch_ids = []
        batch_docs = []
        batch_metas = []
        total_chunks_doc = 0
        skipped_pages = 0

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc[page_idx]
            raw_text = page.get_text()

            if self.is_toc_or_index_page(raw_text):
                skipped_pages += 1
                continue

            cleaned = self.clean_text(raw_text)
            if len(cleaned) < 80:
                skipped_pages += 1
                continue

            section = self.extract_section_title(cleaned, default=f"Page {page_num}")
            chunks = self.chunk_text(cleaned)

            for c_idx, chunk_body in enumerate(chunks):
                chunk_id = f"{prefix}_p{page_num:04d}_c{c_idx+1:02d}"

                # Enriched text for vector similarity
                enriched_text = (
                    f"Document: {title} (Page {page_num})\n"
                    f"Section: {section}\n"
                    f"Category: {category}\n"
                    f"Applicable Infrastructure: {server_relevance}\n\n"
                    f"{chunk_body}"
                )

                chunk_meta = {
                    "doc_name": fname,
                    "title": title,
                    "source": source,
                    "url": url,
                    "category": category,
                    "section": section[:100],
                    "page": page_num,
                    "server_relevance": server_relevance,
                    "file_type": "pdf"
                }

                batch_ids.append(chunk_id)
                batch_docs.append(enriched_text)
                batch_metas.append(chunk_meta)
                total_chunks_doc += 1

                # Flush batch when ready
                if len(batch_ids) >= self.upsert_batch_size:
                    self._flush_batch(batch_ids, batch_docs, batch_metas)
                    batch_ids.clear()
                    batch_docs.clear()
                    batch_metas.clear()

                    # Progress report
                    elapsed = time.time() - t_start
                    pct = (page_num / total_pages) * 100
                    rate = total_chunks_doc / max(0.1, elapsed)
                    print(
                        f"  [{pct:5.1f}%] Page {page_num:4d}/{total_pages} | "
                        f"Indexed: {total_chunks_doc:5d} chunks | Rate: {rate:5.1f} chunks/s",
                        end="\r",
                        flush=True
                    )

        # Flush any remaining chunks
        if batch_ids:
            self._flush_batch(batch_ids, batch_docs, batch_metas)
            batch_ids.clear()
            batch_docs.clear()
            batch_metas.clear()

        doc.close()
        elapsed = time.time() - t_start
        print(f"\n[PDFIngestor] Completed {title}:")
        print(f"  Pages Processed: {total_pages - skipped_pages}/{total_pages} (Skipped {skipped_pages} TOC/empty pages)")
        print(f"  Chunks Created & Upserted: {total_chunks_doc}")
        print(f"  Time Taken: {elapsed:.2f}s ({total_chunks_doc / max(0.1, elapsed):.1f} chunks/s)")

        return total_chunks_doc

    def _flush_batch(self, ids: list[str], docs: list[str], metas: list[dict[str, Any]]):
        """Generates embeddings and performs upsert into ChromaDB."""
        if not ids:
            return

        # Encode text batch into vectors
        embeddings = self.model.encode(
            docs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True
        ).tolist()

        # Upsert into ChromaDB persistent collection
        self.collection.upsert(
            ids=ids,
            documents=docs,
            embeddings=embeddings,
            metadatas=metas
        )

    def ingest_all(self) -> dict[str, int]:
        """Iterates through all configured PDF documentation and ingests them into ChromaDB."""
        t_global_start = time.time()
        print(f"\n{'#'*70}")
        print(f"[PDFIngestor] STARTING COMPLETE PDF INGESTION & VECTOR EMBEDDING")
        print(f"  PDF Source Directory: {self.pdf_dir}")
        print(f"  Target ChromaDB:      {self.chroma_dir}")
        print(f"  Collection Name:      {self.collection_name}")
        print(f"  Embedding Model:      {EMBEDDING_MODEL_NAME}")
        print(f"{'#'*70}\n")

        results = {}
        for spec in PDF_SPECIFICATIONS:
            chunks_count = self.process_pdf(spec)
            results[spec["filename"]] = chunks_count

        total_chunks = sum(results.values())
        total_time = time.time() - t_global_start
        final_collection_count = self.collection.count()

        print(f"\n{'#'*70}")
        print(f"[PDFIngestor] ALL PDFS SUCCESSFULLY EMBEDDED & INDEXED!")
        print(f"  Total Chunks Added:       {total_chunks}")
        print(f"  Total Collection Chunks:  {final_collection_count}")
        print(f"  Total Processing Time:    {total_time:.2f}s ({total_time / 60:.1f} mins)")
        print(f"  Average Processing Speed: {total_chunks / max(0.1, total_time):.1f} chunks/sec")
        print(f"{'#'*70}\n")

        return results

if __name__ == "__main__":
    ingestor = PDFIngestor()
    ingestor.ingest_all()
