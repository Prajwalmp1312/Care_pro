"""
rag_service.py  —  RAG (Retrieval-Augmented Generation) pipeline for CareConnect Pro
======================================================================================
Responsibilities
----------------
1. INDEX   – When a medical record is uploaded, split its extracted text into overlapping
             chunks, embed them with ChromaDB's built-in embedding function, and upsert them
             into a per-patient ChromaDB collection.

2. RETRIEVE – Given a user query, embed it and return the top-K most semantically
              similar chunks from that patient's collection.

3. DELETE  – When a record is deleted, remove its chunks from the vector store.

4. REINDEX – Utility to re-index all existing records (useful on first deployment).

Dependency:
    pip install chromadb
"""

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Dict

# ---------------------------------------------------------------------------
# Lazy-load heavy dependencies so the module can be imported without crashing
# if the optional packages are not yet installed.
# ---------------------------------------------------------------------------
_chroma_client = None
_chroma_embedding_function = None
_chroma_initialization_lock = threading.Lock()
_chroma_retry_after = 0.0
_chroma_last_error = ""

logger = logging.getLogger(__name__)


class RagUnavailableError(RuntimeError):
    """Chroma is temporarily unavailable; callers should use their fallback."""


def _rag_retry_cooldown_seconds() -> int:
    try:
        value = int(os.getenv("RAG_RETRY_COOLDOWN_SECONDS", "300"))
    except (TypeError, ValueError):
        value = 300
    return max(30, min(value, 3600))


def _get_chroma_client():
    """Return (and lazily initialise) the persistent ChromaDB client."""
    global _chroma_client, _chroma_retry_after, _chroma_last_error
    if _chroma_client is not None:
        return _chroma_client

    now = time.monotonic()
    if now < _chroma_retry_after:
        raise RagUnavailableError(_chroma_last_error)

    with _chroma_initialization_lock:
        if _chroma_client is not None:
            return _chroma_client
        now = time.monotonic()
        if now < _chroma_retry_after:
            raise RagUnavailableError(_chroma_last_error)
        try:
            import chromadb
            db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
            os.makedirs(db_path, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=db_path)
            _chroma_last_error = ""
            _chroma_retry_after = 0.0
            logger.info("ChromaDB initialised at %s", db_path)
        except Exception as exc:
            _chroma_last_error = f"{type(exc).__name__}: {exc}"
            _chroma_retry_after = now + _rag_retry_cooldown_seconds()
            runtime_hint = (
                " Run the API with the repository's Python 3.11/3.12 virtual "
                "environment; Python 3.14 is incompatible with the installed "
                "Chroma/Protobuf stack."
                if sys.version_info >= (3, 14)
                else " Verify the chromadb installation and CHROMA_DB_PATH."
            )
            logger.error(
                "RAG is temporarily disabled for %ds after ChromaDB failed to "
                "initialize: %s.%s",
                _rag_retry_cooldown_seconds(),
                _chroma_last_error,
                runtime_hint,
            )
            raise RagUnavailableError(_chroma_last_error) from exc
    return _chroma_client


def _get_chroma_embedding_function():
    """Create Chroma's local embedding model with an app-owned cache path."""
    global _chroma_embedding_function
    if _chroma_embedding_function is None:
        from chromadb.utils.embedding_functions import (
            DefaultEmbeddingFunction,
            ONNXMiniLM_L6_V2,
        )

        cache_root = Path(
            os.getenv("CHROMA_EMBEDDING_CACHE_PATH", "./chroma_cache")
        ).resolve()
        cache_root.mkdir(parents=True, exist_ok=True)
        # Chroma otherwise writes beneath Path.home(), which is unreliable for
        # service accounts and locked-down Windows application processes.
        ONNXMiniLM_L6_V2.DOWNLOAD_PATH = (
            cache_root / ONNXMiniLM_L6_V2.MODEL_NAME
        )
        # Use Chroma's "default" wrapper so this remains compatible with
        # collections created before the cache path became configurable.
        _chroma_embedding_function = DefaultEmbeddingFunction()
    return _chroma_embedding_function



# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_collection_name(patient_email: str) -> str:
    """
    ChromaDB collection names must match [a-zA-Z0-9_-]{3,63}.
    Convert an email address to a safe name.
    """
    safe = (
        patient_email
        .replace("@", "_at_")
        .replace(".", "_dot_")
        .replace("+", "_plus_")
        .replace("-", "_dash_")
    )
    # Trim to ChromaDB's 63-char limit
    return safe[:63]


def _get_patient_collection(patient_email: str):
    """Return (or create) the ChromaDB collection for a specific patient."""
    client = _get_chroma_client()
    name = _safe_collection_name(patient_email)
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},  # cosine similarity
        embedding_function=_get_chroma_embedding_function(),
    )


def _chunk_text(text: str, chunk_size: int = 450, overlap: int = 80) -> List[str]:
    """
    Split *text* into overlapping windows of ~chunk_size characters.
    Overlap keeps contextual continuity across chunk boundaries.
    """
    if not text or not text.strip():
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_record(
    patient_email: str,
    record_id: int,
    record_name: str,
    record_type: str,
    record_date: str,
    text: str,
) -> int:
    """
    Embed *text* for *record_id* and upsert all chunks into the patient's
    vector store.  Idempotent — re-uploading the same record_id just
    overwrites its chunks.

    Returns the number of chunks indexed (0 if text was empty).
    """
    if not text or not text.strip():
        logger.debug("index_record: empty text for record %d, skipping.", record_id)
        return 0

    try:
        collection = _get_patient_collection(patient_email)
        chunks = _chunk_text(text)
        if not chunks:
            return 0

        ids = [f"rec_{record_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "record_id": record_id,
                "record_name": record_name,
                "record_type": record_type,
                "record_date": record_date,
            }
            for _ in chunks
        ]

        # upsert so re-uploads don't create duplicate chunks
        collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
        )

        logger.info(
            "RAG indexed record %d (%s): %d chunks for patient %s",
            record_id, record_name, len(chunks), patient_email,
        )
        return len(chunks)

    except RagUnavailableError:
        logger.debug("RAG indexing skipped while ChromaDB is unavailable")
        return 0
    except Exception as exc:
        # Non-fatal: log and continue without crashing the upload endpoint
        logger.error("RAG index_record failed for record %d: %s", record_id, exc)
        return 0


def retrieve_relevant_chunks(
    patient_email: str,
    query: str,
    top_k: int = 5,
) -> List[Dict]:
    """
    Retrieve the *top_k* most semantically relevant text chunks for *query*
    from this patient's vector store.

    Returns a list of dicts with keys:
        text, record_name, record_type, record_date, record_id
    Returns [] if the collection is empty or an error occurs.
    """
    if not query or not query.strip():
        return []

    try:
        collection = _get_patient_collection(patient_email)
        total = collection.count()
        if total == 0:
            logger.debug("retrieve: no indexed records for patient %s", patient_email)
            return []

        n = min(top_k, total)
        results = collection.query(
            query_texts=[query],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        chunks: List[Dict] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text": doc,
                "record_name": meta.get("record_name", "Unknown"),
                "record_type": meta.get("record_type", "Unknown"),
                "record_date": meta.get("record_date", "Unknown"),
                "record_id":   meta.get("record_id", -1),
                "similarity":  round(1 - dist, 4),   # convert cosine distance → similarity
            })

        logger.debug(
            "RAG retrieved %d chunks for query='%s...' patient=%s",
            len(chunks), query[:40], patient_email,
        )
        return chunks

    except RagUnavailableError:
        logger.debug("RAG retrieval skipped while ChromaDB is unavailable")
        return []
    except Exception as exc:
        logger.error("RAG retrieve_relevant_chunks failed: %s", exc)
        return []


def delete_record_chunks(patient_email: str, record_id: int) -> int:
    """
    Remove all vector-store chunks belonging to *record_id*.
    Called when a medical record is deleted from the DB.

    Returns number of chunks deleted (0 on error or none found).
    """
    try:
        collection = _get_patient_collection(patient_email)
        existing = collection.get(where={"record_id": record_id})
        chunk_ids = existing.get("ids", [])
        if chunk_ids:
            collection.delete(ids=chunk_ids)
            logger.info(
                "RAG deleted %d chunks for record %d (patient %s)",
                len(chunk_ids), record_id, patient_email,
            )
            return len(chunk_ids)
        return 0
    except RagUnavailableError:
        logger.debug("RAG deletion skipped while ChromaDB is unavailable")
        return 0
    except Exception as exc:
        logger.error("RAG delete_record_chunks failed for record %d: %s", record_id, exc)
        return 0


def reindex_all_records(db_session, RecordModel) -> Dict:
    """
    Utility: iterate over every medical record in the database and (re-)index it.
    Call this once after first deployment or whenever you want to rebuild the
    vector store from scratch.

    Usage from a Python shell or a one-off admin endpoint:
        from rag_service import reindex_all_records
        from database import SessionLocal
        from models import MedicalRecord
        with SessionLocal() as db:
            result = reindex_all_records(db, MedicalRecord)
            print(result)
    """
    indexed = 0
    skipped = 0
    errors  = 0

    records = db_session.query(RecordModel).all()
    logger.info("RAG reindex_all_records: processing %d records", len(records))

    for rec in records:
        text = rec.extracted_text or ""
        if not text.strip():
            skipped += 1
            continue
        try:
            date_str = rec.uploaded_at.strftime("%Y-%m-%d") if rec.uploaded_at else "Unknown"
            n = index_record(
                patient_email=rec.patient_email,
                record_id=rec.id,
                record_name=rec.name or "Unknown",
                record_type=rec.type or "Unknown",
                record_date=date_str,
                text=text,
            )
            if n > 0:
                indexed += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.error("reindex_all_records: error on record %d: %s", rec.id, exc)
            errors += 1

    summary = {
        "total_records": len(records),
        "indexed": indexed,
        "skipped_no_text": skipped,
        "errors": errors,
    }
    logger.info("RAG reindex complete: %s", summary)
    return summary
