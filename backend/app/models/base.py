import uuid as _uuid

from sqlalchemy import TypeDecorator, types
from sqlalchemy.orm import DeclarativeBase


class PortableUUID(TypeDecorator):
    impl = types.Uuid
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(types.Uuid())
        return dialect.type_descriptor(types.String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, _uuid.UUID):
            if dialect.name == "postgresql":
                return value
            return str(value)
        if isinstance(value, bytes):
            value = _uuid.UUID(bytes=value)
            if dialect.name == "postgresql":
                return value
            return str(value)
        if isinstance(value, str):
            if dialect.name == "postgresql":
                return _uuid.UUID(value)
            return value
        if dialect.name == "postgresql":
            return _uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, _uuid.UUID):
            return value
        try:
            return _uuid.UUID(str(value))
        except (ValueError, AttributeError, TypeError):
            return value


class Base(DeclarativeBase):
    pass
