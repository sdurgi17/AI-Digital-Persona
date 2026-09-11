from typing import Protocol

from ..config import get_settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self) -> None:
        from openai import OpenAI

        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for EMBEDDING_PROVIDER=openai")
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        self.model = settings.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), 100):
            batch = texts[start : start + 100]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            out.extend(item.embedding for item in resp.data)
        return out


class FastEmbedEmbedder:
    """Local ONNX embeddings, no API key. Weak for Telugu; prefer openai there."""

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        settings = get_settings()
        self.model = TextEmbedding(model_name=settings.embedding_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self.model.embed(texts)]


def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embedding_provider == "openai":
        return OpenAIEmbedder()
    if settings.embedding_provider == "fastembed":
        return FastEmbedEmbedder()
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider!r}")


def check_embedding_consistency(conn) -> None:
    """Refuse to mix embeddings from different models in one vector table."""
    settings = get_settings()
    current = f"{settings.embedding_provider}:{settings.embedding_model}"
    row = conn.execute("SELECT value FROM settings WHERE key = 'embedding_model_used'").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('embedding_model_used', ?)", (current,)
        )
        conn.commit()
    elif row["value"] != current:
        raise RuntimeError(
            f"Vector store was built with '{row['value']}' but config now says '{current}'. "
            "Re-embed everything (delete documents and rebuild persona) or restore the old config."
        )
