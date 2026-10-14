"""Small local RAG index: Markdown chunks, real embeddings, and hybrid search."""

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from openai import AsyncOpenAI

from marketpilot.execution import utc_now

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIRECTORY = PROJECT_ROOT / "knowledge"
INDEX_PATH = PROJECT_ROOT / "data" / "knowledge_index.json"
EMBEDDING_MODEL = "text-embedding-3-small"
SearchMode = Literal["keyword", "semantic", "hybrid"]


@dataclass
class Document:
    source: str
    body: str
    body_start_line: int
    metadata: dict[str, str]


def load_documents(directory: Path = KNOWLEDGE_DIRECTORY) -> list[Document]:
    """Read Markdown with a deliberately small key: value metadata header."""
    documents = []
    for path in sorted(directory.rglob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        metadata = {"title": path.stem, "status": "unspecified", "tags": ""}
        body_start = 0
        if lines and lines[0].strip() == "---":
            end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
            if end is None:
                raise ValueError(f"Unclosed metadata header in {path.name}.")
            for line in lines[1:end]:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                key, separator, value = line.partition(":")
                if not separator or not key.strip():
                    raise ValueError(f"Use simple key: value metadata in {path.name}.")
                metadata[key.strip()] = value.strip().strip("\"'")
            body_start = end + 1
        body = "".join(lines[body_start:])
        if body.strip():
            documents.append(Document(
                source=f"knowledge/{path.relative_to(directory).as_posix()}",
                body=body, body_start_line=body_start + 1, metadata=metadata,
            ))
    if not documents:
        raise ValueError("No nonempty Markdown documents found in knowledge/.")
    return documents


def chunk_document(document: Document, chunk_size: int = 1000, overlap: int = 150) -> list[dict]:
    """Keep heading sections separate; overlap long sections to preserve context."""
    if not 0 <= overlap < chunk_size:
        raise ValueError("Chunk overlap must be nonnegative and smaller than chunk size.")
    headings = list(re.finditer(r"^#{1,6}\s+(.+)$", document.body, re.MULTILINE))
    boundaries = sorted({0, *(match.start() for match in headings), len(document.body)})
    chunks = []
    for section_start, section_end in zip(boundaries, boundaries[1:]):
        section = document.body[section_start:section_end]
        heading = next((match.group(1).strip() for match in headings if match.start() == section_start), document.metadata["title"])
        for start in range(0, len(section), chunk_size - overlap):
            raw = section[start:start + chunk_size]
            text = raw.strip()
            if text:
                offset = section_start + start + len(raw) - len(raw.lstrip())
                start_line = document.body_start_line + document.body[:offset].count("\n")
                identity = f"{document.source}:{offset}:{text}"
                chunks.append({
                    "chunk_id": hashlib.sha256(identity.encode()).hexdigest()[:16],
                    "source": document.source, "heading": heading, "text": text,
                    "start_line": start_line, "end_line": start_line + text.count("\n"),
                    "metadata": dict(document.metadata),
                })
            if start + chunk_size >= len(section):
                break
    return chunks


def collect_chunks(directory: Path = KNOWLEDGE_DIRECTORY) -> list[dict]:
    return [chunk for document in load_documents(directory) for chunk in chunk_document(document)]


def corpus_fingerprint(chunks: list[dict]) -> str:
    """Detect source, metadata, or chunking changes before using cached vectors."""
    return hashlib.sha256(json.dumps(chunks, sort_keys=True).encode()).hexdigest()


def searchable_text(chunk: dict) -> str:
    """Include titles and tags so both search methods see document context."""
    return f"{chunk['metadata']['title']}\n{chunk['metadata']['tags']}\n{chunk['heading']}\n{chunk['text']}"


async def embed_texts(texts: list[str], model: str = EMBEDDING_MODEL) -> list[list[float]]:
    """Batch real API embeddings. No mock vector fallback exists in application code."""
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("OPENAI_API_KEY is required for embeddings. Use keyword mode to search without it.")
    vectors = []
    async with AsyncOpenAI(timeout=90, max_retries=1) as client:
        for start in range(0, len(texts), 64):
            batch = texts[start:start + 64]
            response = await client.embeddings.create(model=model, input=batch, encoding_format="float")
            ordered = sorted(response.data, key=lambda item: item.index)
            if [item.index for item in ordered] != list(range(len(batch))):
                raise ValueError("Embedding response did not match the requested inputs.")
            vectors.extend(item.embedding for item in ordered)
    return vectors


async def build_index(directory: Path = KNOWLEDGE_DIRECTORY, index_path: Path = INDEX_PATH, force: bool = False) -> dict:
    """Embed the corpus once; reuse an unchanged index without another API call."""
    chunks = collect_chunks(directory)
    fingerprint = corpus_fingerprint(chunks)
    if index_path.exists() and not force:
        try:
            existing = load_index(index_path, fingerprint)
            return {"status": "reused", "chunks": len(existing["chunks"]), "path": str(index_path)}
        except ValueError:
            pass  # Stale or malformed indexes are rebuilt explicitly by this command.
    vectors = await embed_texts([searchable_text(chunk) for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("Embedding count does not match the number of chunks.")
    record = {"schema_version": 1, "embedding_model": EMBEDDING_MODEL, "fingerprint": fingerprint, "created_at": utc_now(), "chunks": [{**chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors)]}
    validate_vectors(record["chunks"])
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = index_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(index_path)
    return {"status": "built", "chunks": len(chunks), "path": str(index_path)}


def validate_vectors(chunks: list[dict]) -> None:
    """Reject inconsistent vectors rather than silently computing bad rankings."""
    if not chunks:
        raise ValueError("Knowledge index contains no chunks.")
    dimension = len(chunks[0]["embedding"])
    for chunk in chunks:
        vector = chunk["embedding"]
        if not dimension or len(vector) != dimension or not all(
            isinstance(value, (int, float)) and math.isfinite(value) for value in vector
        ) or not any(vector):
            raise ValueError("Knowledge index contains invalid embedding vectors.")


def load_index(index_path: Path, fingerprint: str) -> dict:
    if not index_path.exists():
        raise ValueError("Knowledge index is missing. Run: python -m marketpilot.knowledge_cli index")
    try:
        record = json.loads(index_path.read_text(encoding="utf-8"))
        if record["schema_version"] != 1 or record["embedding_model"] != EMBEDDING_MODEL:
            raise ValueError("Knowledge index format/model changed; rebuild the index.")
        if record["fingerprint"] != fingerprint:
            raise ValueError("Knowledge index is stale. Run: python -m marketpilot.knowledge_cli index")
        validate_vectors(record["chunks"])
        # Fingerprint the stored text too; source metadata must agree with the current corpus.
        stored_chunks = [{key: value for key, value in chunk.items() if key != "embedding"} for chunk in record["chunks"]]
        if corpus_fingerprint(stored_chunks) != fingerprint:
            raise ValueError("Knowledge index text is inconsistent; rebuild the index.")
        return record
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Knowledge index is malformed; rebuild the index.") from exc


def keyword_score(query: str, text: str) -> float:
    """Fraction of distinct query words present; intentionally simpler than BM25."""
    query_words = set(re.findall(r"\w+", query.lower()))
    text_words = set(re.findall(r"\w+", text.lower()))
    return len(query_words & text_words) / len(query_words) if query_words else 0.0


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compare vector direction: higher similarity means closer semantic meaning."""
    if len(left) != len(right) or not left:
        raise ValueError("Embedding dimensions do not match.")
    denominator = math.sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    if not denominator:
        raise ValueError("Cannot compare a zero embedding vector.")
    return sum(a * b for a, b in zip(left, right)) / denominator


async def retrieve_knowledge(query: str, mode: SearchMode = "hybrid", top_k: int = 3, directory: Path = KNOWLEDGE_DIRECTORY, index_path: Path = INDEX_PATH) -> dict:
    """Return evidence passages; the main agent generates the answer afterward."""
    if not query.strip() or len(query) > 2000:
        raise ValueError("Knowledge query must contain 1–2000 characters.")
    if mode not in ("keyword", "semantic", "hybrid") or not 1 <= top_k <= 5:
        raise ValueError("Use keyword, semantic, or hybrid mode and top_k from 1 to 5.")
    chunks = collect_chunks(directory)
    query_vector = None
    if mode != "keyword":
        index = load_index(index_path, corpus_fingerprint(chunks))
        chunks = index["chunks"]
        query_vector = (await embed_texts([query], index["embedding_model"]))[0]
    matches = []
    for chunk in chunks:
        keyword = keyword_score(query, searchable_text(chunk))
        semantic = cosine_similarity(query_vector, chunk["embedding"]) if query_vector is not None else None
        # Simple weighted fusion. Scores are ranking signals, not probabilities.
        score = keyword if mode == "keyword" else semantic if mode == "semantic" else (
            0.7 * max(semantic, 0.0) + 0.3 * keyword
        )
        if mode == "keyword" and keyword == 0:
            continue
        matches.append({
            **{key: value for key, value in chunk.items() if key != "embedding"},
            "score": round(score, 4), "keyword_score": round(keyword, 4),
            "semantic_score": round(semantic, 4) if semantic is not None else None,
            "citation": f"[{chunk['source']}:{chunk['start_line']}]",
        })
    matches.sort(key=lambda match: (-match["score"], match["source"], match["start_line"]))
    return {"query": query, "mode": mode, "matches": matches[:top_k],
            "embedding_model": EMBEDDING_MODEL if mode != "keyword" else None,
            "note": "Scores rank passages, not confidence. Verify evidence and its metadata; demo documents are fictional."}
