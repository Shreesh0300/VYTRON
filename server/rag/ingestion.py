"""
VYTRON RAG — Multi-Format Document Ingestion & Text Chunking Engine
Extracts, cleans, and chunks technical documentation (.md, .txt, .html, .pdf)
with section hierarchy and metadata preservation.
"""

import os
import re
from typing import Any, NamedTuple

class DocumentChunk(NamedTuple):
    chunk_id: str
    doc_name: str
    title: str
    source: str
    url: str
    category: str
    section: str
    server_relevance: list[str]
    content: str
    metadata: dict[str, Any]

class DocumentLoader:
    def __init__(self, knowledge_base_dir: str):
        self.knowledge_base_dir = knowledge_base_dir

    def load_all(self) -> list[dict[str, Any]]:
        """Loads all supported documents (.md, .txt, .html) from the knowledge base directory."""
        documents = []
        if not os.path.exists(self.knowledge_base_dir):
            return documents

        for fname in os.listdir(self.knowledge_base_dir):
            fpath = os.path.join(self.knowledge_base_dir, fname)
            if not os.path.isfile(fpath):
                continue

            ext = os.path.splitext(fname)[1].lower()
            if ext in (".md", ".txt", ".markdown"):
                doc = self._load_markdown_or_text(fpath, fname)
                if doc:
                    documents.append(doc)
            elif ext in (".html", ".htm"):
                doc = self._load_html(fpath, fname)
                if doc:
                    documents.append(doc)
            elif ext == ".pdf":
                doc = self._load_pdf(fpath, fname)
                if doc:
                    documents.append(doc)

        return documents

    def _load_markdown_or_text(self, fpath: str, fname: str) -> dict[str, Any] | None:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()

            metadata = {
                "doc_name": fname,
                "title": fname,
                "source": "VYTRON Knowledge Base",
                "url": f"https://vytron.aiops/docs/{fname}",
                "category": "General Troubleshooting",
                "server_relevance": ["ALL"],
            }

            content = raw_text
            # Parse YAML frontmatter if present
            if raw_text.startswith("---"):
                parts = raw_text.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1]
                    content = parts[2].strip()
                    for line in fm_text.strip().splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k == "server_relevance" and v.startswith("["):
                                # Parse simple list: ["APP-01", "DB-01"]
                                items = [x.strip().strip('"').strip("'") for x in v.strip("[]").split(",")]
                                metadata[k] = items
                            else:
                                metadata[k] = v

            return {
                "doc_name": fname,
                "metadata": metadata,
                "content": content,
            }
        except Exception as e:
            print(f"[DocumentLoader] Error reading {fname}: {e}")
            return None

    def _load_html(self, fpath: str, fname: str) -> dict[str, Any] | None:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
            # Strip script and style elements
            html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
            # Replace tags with newlines
            clean_text = re.sub(r"<[^>]+>", "\n", html)
            clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

            return {
                "doc_name": fname,
                "metadata": {
                    "doc_name": fname,
                    "title": fname.replace(".html", "").replace("_", " ").title(),
                    "source": "HTML Technical Guide",
                    "url": f"https://vytron.aiops/docs/{fname}",
                    "category": "HTML Documentation",
                    "server_relevance": ["ALL"],
                },
                "content": clean_text,
            }
        except Exception as e:
            print(f"[DocumentLoader] Error reading HTML {fname}: {e}")
            return None

    def _load_pdf(self, fpath: str, fname: str) -> dict[str, Any] | None:
        # Fallback PDF extraction
        try:
            import pypdf
            reader = pypdf.PdfReader(fpath)
            pages = [p.extract_text() for p in reader.pages if p.extract_text()]
            content = "\n\n".join(pages)
            return {
                "doc_name": fname,
                "metadata": {
                    "doc_name": fname,
                    "title": fname.replace(".pdf", "").title(),
                    "source": "PDF Technical Manual",
                    "url": f"https://vytron.aiops/docs/{fname}",
                    "category": "PDF Manual",
                    "server_relevance": ["ALL"],
                },
                "content": content,
            }
        except Exception:
            return None


class TextChunker:
    def __init__(self, target_chunk_size: int = 650, chunk_overlap: int = 120):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, doc: dict[str, Any]) -> list[DocumentChunk]:
        """
        Splits a document into semantic chunks respecting section headers (##, ###),
        preserving full contextual metadata for vector embedding.
        """
        doc_name = doc["doc_name"]
        metadata = doc["metadata"]
        content = doc["content"]

        title = metadata.get("title", doc_name)
        source = metadata.get("source", "Technical Documentation")
        url = metadata.get("url", "")
        category = metadata.get("category", "General")
        server_rel = metadata.get("server_relevance", ["ALL"])

        # Split document by Markdown headers (## or #)
        sections = self._split_by_headers(content)
        chunks: list[DocumentChunk] = []

        chunk_seq = 0
        for section_title, section_text in sections:
            section_chunks = self._sliding_window_chunk(section_text)
            for s_idx, c_text in enumerate(section_chunks):
                chunk_seq += 1
                chunk_id = f"{doc_name}:{chunk_seq:03d}"
                
                # Prepend contextual header to give vector embedding strong semantic context
                enriched_content = (
                    f"Document: {title}\n"
                    f"Section: {section_title}\n"
                    f"Category: {category}\n\n"
                    f"{c_text.strip()}"
                )

                chunk_meta = {
                    "doc_name": doc_name,
                    "title": title,
                    "source": source,
                    "url": url,
                    "category": category,
                    "section": section_title,
                    "server_relevance": ",".join(server_rel) if isinstance(server_rel, list) else str(server_rel),
                }

                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    doc_name=doc_name,
                    title=title,
                    source=source,
                    url=url,
                    category=category,
                    section=section_title,
                    server_relevance=server_rel if isinstance(server_rel, list) else [str(server_rel)],
                    content=enriched_content,
                    metadata=chunk_meta,
                ))

        return chunks

    def _split_by_headers(self, text: str) -> list[tuple[str, str]]:
        """Splits text by markdown headings (# and ##)."""
        lines = text.splitlines()
        sections = []
        current_title = "Introduction"
        current_lines = []

        for line in lines:
            if re.match(r"^#{1,3}\s+", line):
                if current_lines:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                    current_lines = []
                current_title = re.sub(r"^#{1,3}\s+", "", line).strip()
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_title, "\n".join(current_lines).strip()))

        return sections if sections else [("General", text)]

    def _sliding_window_chunk(self, text: str) -> list[str]:
        """Chunks a section of text using a character window with overlap at paragraph boundaries."""
        if len(text) <= self.target_chunk_size:
            return [text] if text.strip() else []

        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= self.target_chunk_size:
                current_chunk = f"{current_chunk}\n\n{para}".strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    # Carry over overlap
                    overlap_len = min(len(current_chunk), self.chunk_overlap)
                    overlap_text = current_chunk[-overlap_len:]
                    current_chunk = f"{overlap_text}\n\n{para}".strip()
                else:
                    # Paragraph is longer than target_chunk_size by itself: split by sentences
                    chunks.append(para[:self.target_chunk_size])
                    current_chunk = para[self.target_chunk_size - self.chunk_overlap:]

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
