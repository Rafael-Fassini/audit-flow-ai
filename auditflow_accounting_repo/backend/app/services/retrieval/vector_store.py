import math
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams


@dataclass(frozen=True)
class VectorPoint:
    id: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass(frozen=True)
class VectorSearchResult:
    id: str
    score: float
    payload: dict[str, Any]


class VectorStore:
    def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        raise NotImplementedError

    def upsert(self, collection_name: str, points: list[VectorPoint]) -> None:
        raise NotImplementedError

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int,
    ) -> list[VectorSearchResult]:
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._collections: dict[str, dict[str, VectorPoint]] = {}
        self._vector_sizes: dict[str, int] = {}

    def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        self._collections.setdefault(collection_name, {})
        self._vector_sizes[collection_name] = vector_size

    def upsert(self, collection_name: str, points: list[VectorPoint]) -> None:
        if collection_name not in self._collections:
            raise ValueError(f"Collection '{collection_name}' has not been created.")

        expected_size = self._vector_sizes[collection_name]
        for point in points:
            if len(point.vector) != expected_size:
                raise ValueError("Vector size does not match collection size.")
            self._collections[collection_name][point.id] = point

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int,
    ) -> list[VectorSearchResult]:
        if collection_name not in self._collections:
            raise ValueError(f"Collection '{collection_name}' has not been created.")

        results = [
            VectorSearchResult(
                id=point.id,
                score=self._cosine_similarity(query_vector, point.vector),
                payload=point.payload,
            )
            for point in self._collections[collection_name].values()
        ]
        results.sort(key=lambda result: result.score, reverse=True)
        return results[:limit]

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            raise ValueError("Vectors must have the same size.")

        dot_product = sum(
            left_value * right_value
            for left_value, right_value in zip(left, right)
        )
        left_magnitude = math.sqrt(sum(value * value for value in left))
        right_magnitude = math.sqrt(sum(value * value for value in right))
        if left_magnitude == 0 or right_magnitude == 0:
            return 0.0
        return max(0.0, min(1.0, dot_product / (left_magnitude * right_magnitude)))


class QdrantVectorStore(VectorStore):
    def __init__(self, client: QdrantClient) -> None:
        self._client = client

    def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        if self._collection_exists(collection_name):
            return

        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def upsert(self, collection_name: str, points: list[VectorPoint]) -> None:
        self._client.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=str(uuid5(NAMESPACE_URL, point.id)),
                    vector=point.vector,
                    payload=point.payload,
                )
                for point in points
            ],
        )

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int,
    ) -> list[VectorSearchResult]:
        results = self._client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
        )
        return [
            VectorSearchResult(
                id=str(result.id),
                score=float(result.score),
                payload=dict(result.payload or {}),
            )
            for result in results
        ]

    def _collection_exists(self, collection_name: str) -> bool:
        if hasattr(self._client, "collection_exists"):
            return bool(self._client.collection_exists(collection_name))

        try:
            self._client.get_collection(collection_name)
            return True
        except UnexpectedResponse:
            return False
