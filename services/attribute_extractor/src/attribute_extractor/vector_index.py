"""VectorIndex: абстрактный интерфейс и лексический fallback (hashed BoW)."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from attribute_extractor.constants import DEFAULT_VECTOR_DIM

_TOKEN_RE = re.compile(r"[0-9a-zа-яё]+")
_NOISE_RE = re.compile(r"[.,;:()\[\]{}\"'/\\|]+")


class VectorIndex(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def add(self, key: str, vector: list[float] | None = None) -> None: ...

    def search(self, vector: list[float], k: int) -> list[tuple[str, float]]: ...


def _coverage(query: list[float], stored: list[float]) -> float:
    """Доля ненулевых измерений запроса, присутствующих в документе.

    Устойчива к «разбавлению» длинного текста поля синонимами: короткий запрос
    («озу») матчится с полем, где этот токен есть, даже если у поля много
    других токенов.
    """
    query_dims = [i for i, value in enumerate(query) if value > 0.0]
    if not query_dims:
        return 0.0
    matched = sum(1 for i in query_dims if i < len(stored) and stored[i] > 0.0)
    return matched / len(query_dims)


def _token_hash(token: str, dim: int) -> int:
    digest = hashlib.md5(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dim


class LexicalVectorIndex:
    """Лексический bag-of-words индекс на детерминированном хэшировании токенов.

    Не требует моделей и служит fallback при недоступности семантического
    индекса: близость — доля токенов запроса, найденных в документе. Хэш-функция
    стабильна между запусками (в отличие от встроенного ``hash``).
    """

    def __init__(self, dim: int = DEFAULT_VECTOR_DIM) -> None:
        self._dim = dim
        self._keys: list[str] = []
        self._vectors: list[list[float]] = []
        self._seen: set[str] = set()

    def _normalize(self, text: str) -> str:
        s = (text or "").lower().replace("ё", "е")
        return _NOISE_RE.sub(" ", s)

    def _tokens(self, text: str) -> list[str]:
        return _TOKEN_RE.findall(self._normalize(text))

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for token in self._tokens(text):
            vec[_token_hash(token, self._dim)] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]

    def add(self, key: str, vector: list[float] | None = None) -> None:
        if key in self._seen:
            return
        self._seen.add(key)
        self._keys.append(key)
        self._vectors.append(vector if vector is not None else self.embed(key))

    def search(self, vector: list[float], k: int = 5) -> list[tuple[str, float]]:
        scores = [
            (key, _coverage(vector, stored))
            for key, stored in zip(self._keys, self._vectors, strict=True)
        ]
        scores.sort(key=lambda item: item[1], reverse=True)
        return scores[:k]


class InMemoryVectorIndex(LexicalVectorIndex):
    """MVP-реализация в памяти (лексический fallback)."""
