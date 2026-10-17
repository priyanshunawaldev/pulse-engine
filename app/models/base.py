import uuid

import uuid_utils
from sqlalchemy.orm import DeclarativeBase


def uuid7_gen() -> uuid.UUID:
    """Generate time-sortable RFC 9562 UUIDv7 compliant standard UUID."""
    return uuid.UUID(str(uuid_utils.uuid7()))


class Base(DeclarativeBase):
    pass
