from __future__ import annotations

from sqlalchemy.types import JSON, TypeDecorator

from pgvector.sqlalchemy import Vector


class VectorType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return [float(item) for item in value]

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return [float(item) for item in value]
