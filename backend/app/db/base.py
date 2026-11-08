"""Base class for SQLAlchemy database models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Database models will inherit from this class."""
