"""
VYTRON RAG — PDF Embedding Ingestion CLI
Run this script to convert all PDF manuals in rag_pdf into embeddings and store in ChromaDB.
Usage:
    python ingest_pdfs.py
"""

import sys
import os

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.rag.pdf_ingest import PDFIngestor

if __name__ == "__main__":
    print("Starting VYTRON PDF Vector Embedding Ingestion Pipeline...")
    ingestor = PDFIngestor()
    results = ingestor.ingest_all()
    print("Ingestion results:")
    for fname, count in results.items():
        print(f"  - {fname}: {count} chunks embedded and indexed.")
