from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    product: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    storage_uri: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    sections: Mapped[List["DocumentSection"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    tags: Mapped[List["DocumentTag"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentSection(Base):
    __tablename__ = "document_sections"
    doc_id: Mapped[str] = mapped_column(
        ForeignKey("documents.doc_id", ondelete="CASCADE"), primary_key=True
    )
    section_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chunk_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    storage_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    document: Mapped[Document] = relationship(back_populates="sections")


class DocumentTag(Base):
    __tablename__ = "document_tags"
    __table_args__ = (UniqueConstraint("doc_id", "tag", name="uq_document_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(ForeignKey("documents.doc_id", ondelete="CASCADE"), index=True)
    tag: Mapped[str] = mapped_column(String(64), index=True)

    document: Mapped[Document] = relationship(back_populates="tags")
