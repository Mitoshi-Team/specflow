"""VectorIndex: абстрактный интерфейс + MVP с graceful degradation."""

from __future__ import annotations

from typing import Protocol


class VectorIndex(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def add(self, key: str, vector: list[float] | None = None) -> None: ...

    def search(self, vector: list[float], k: int) -> list[tuple[str, float]]: ...


class LexicalVectorIndex:
    def __init__(self) -> None:
        self._store: dict[str, set[str]] = {}
        self._keys: list[str] = []

    def _normalize(self, text: str) -> str:
        s = (text or "").strip().lower()
        s = s.replace("ё", "е")
        for ch in ".,;:()[]{}\"'/\\|-–—":
            s = s.replace(ch, " ")
        return " ".join(s.split())

    def add(self, key: str, vector: list[float] | None = None) -> None:
        if key not in self._store:
            self._store[key] = set(self._normalize(key).split())
            self._keys.append(key)

    def embed(self, text: str) -> list[float]:
        tokens = self._normalize(text).split()
        if not tokens or not self._keys:
            return []
        vec = [0.0] * len(self._keys)
        for t in tokens:
            for i, k in enumerate(self._keys):
                if t in self._store[k]:
                    vec[i] += 1.0
        if sum(vec) == 0:
            return vec
        total = sum(vec)
        return [v / total for v in vec]

    def search(self, vector: list[float], k: int = 5) -> list[tuple[str, float]]:
        if not self._keys:
            return []
        scores = []
        for i, key in enumerate(self._keys):
            v = vector[i] if i < len(vector) else 0.0
            scores.append((key, float(max(0.0, min(1.0, v)))))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]


class InMemoryVectorIndex(LexicalVectorIndex):
    pass
