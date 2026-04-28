"""Pluggable embeddings + reranking for the workflow vector DB.

Selects a provider from the EMBEDDINGS_PROVIDER env var:

  voyage  (default) -- voyage-code-3 + rerank-2.5-lite. Free tier (200M tokens),
                       code-tuned, includes cross-encoder reranking.
  openai            -- text-embedding-3-small (or 3-large via OPENAI_EMBEDDING_MODEL).
                       No native reranker; rerank() returns None and callers
                       fall back to vector distance ordering.

Each provider's SDK is imported lazily, so users only need to install the SDK
for the provider they actually use.

Configuration (env vars):
  EMBEDDINGS_PROVIDER         "voyage" | "openai"  (default: voyage)
  VOYAGE_API_KEY              required if provider=voyage
  VOYAGE_EMBEDDING_MODEL      default: voyage-code-3
  VOYAGE_RERANK_MODEL         default: rerank-2.5-lite
  OPENAI_API_KEY              required if provider=openai
  OPENAI_EMBEDDING_MODEL      default: text-embedding-3-small
  OPENAI_BASE_URL             optional, for Azure / compatible endpoints
"""
import os
import sys
from typing import Optional


def get_provider() -> str:
    return os.getenv("EMBEDDINGS_PROVIDER", "voyage").strip().lower()


class _VoyageProvider:
    def __init__(self):
        try:
            import voyageai
        except ImportError:
            print("[ERROR] voyageai not installed. `pip install voyageai` "
                  "or set EMBEDDINGS_PROVIDER=openai", file=sys.stderr)
            sys.exit(1)
        api_key = os.getenv("VOYAGE_API_KEY")
        if not api_key:
            print("[ERROR] VOYAGE_API_KEY not set in .env", file=sys.stderr)
            sys.exit(1)
        self._client = voyageai.Client(api_key=api_key)
        self.embedding_model = os.getenv("VOYAGE_EMBEDDING_MODEL", "voyage-code-3")
        self.rerank_model = os.getenv("VOYAGE_RERANK_MODEL", "rerank-2.5-lite")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._client.embed(texts, model=self.embedding_model, input_type="document").embeddings

    def embed_query(self, text: str) -> list[float]:
        return self._client.embed([text], model=self.embedding_model, input_type="query").embeddings[0]

    def rerank(self, query: str, documents: list[str], top_k: int):
        rr = self._client.rerank(query=query, documents=documents,
                                 model=self.rerank_model, top_k=top_k, truncation=True)
        return [(item.index, item.relevance_score) for item in rr.results]


class _OpenAIProvider:
    def __init__(self):
        try:
            from openai import OpenAI
        except ImportError:
            print("[ERROR] openai not installed. `pip install openai` "
                  "or set EMBEDDINGS_PROVIDER=voyage", file=sys.stderr)
            sys.exit(1)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("[ERROR] OPENAI_API_KEY not set in .env", file=sys.stderr)
            sys.exit(1)
        kwargs = {"api_key": api_key}
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self.embedding_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self.embedding_model, input=texts)
        return [d.embedding for d in resp.data]

    def embed_query(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(model=self.embedding_model, input=[text])
        return resp.data[0].embedding

    def rerank(self, query: str, documents: list[str], top_k: int):
        return None


_PROVIDERS = {"voyage": _VoyageProvider, "openai": _OpenAIProvider}
_INSTANCE: Optional[object] = None


def get() -> object:
    """Return a singleton provider instance based on EMBEDDINGS_PROVIDER."""
    global _INSTANCE
    if _INSTANCE is not None:
        return _INSTANCE
    name = get_provider()
    if name not in _PROVIDERS:
        print(f"[ERROR] Unknown EMBEDDINGS_PROVIDER={name!r}. "
              f"Use one of: {', '.join(_PROVIDERS)}", file=sys.stderr)
        sys.exit(1)
    _INSTANCE = _PROVIDERS[name]()
    return _INSTANCE


def describe() -> str:
    """Short string for logging — provider + embedding model."""
    p = get()
    return f"{get_provider()}:{p.embedding_model}"
