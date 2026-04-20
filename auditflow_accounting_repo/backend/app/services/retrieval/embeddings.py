import hashlib
import math
import re


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


class EmbeddingProvider:
    @property
    def vector_size(self) -> int:
        raise NotImplementedError

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class DeterministicEmbeddingProvider(EmbeddingProvider):
    def __init__(self, vector_size: int = 64) -> None:
        if vector_size <= 0:
            raise ValueError("vector_size must be greater than zero.")
        self._vector_size = vector_size

    @property
    def vector_size(self) -> int:
        return self._vector_size

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._vector_size
        for token in self._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._vector_size
            vector[index] += 1.0

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector
        return [value / magnitude for value in vector]

    def _tokens(self, text: str) -> list[str]:
        return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]
