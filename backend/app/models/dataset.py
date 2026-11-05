from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        CheckConstraint("byte_size >= 0", name="ck_datasets_byte_size_nonnegative"),
        CheckConstraint("row_count >= 0", name="ck_datasets_row_count_nonnegative"),
        CheckConstraint("column_count >= 0", name="ck_datasets_column_count_nonnegative"),
        CheckConstraint(
            "status IN ('processing', 'ready', 'failed')",
            name="ck_datasets_status",
        ),
        Index("ix_datasets_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing")
    byte_size: Mapped[int] = mapped_column(nullable=False, default=0)
    row_count: Mapped[int] = mapped_column(nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(nullable=False, default=0)
    columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    initial_quality_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=utc_now_iso,
        onupdate=utc_now_iso,
    )

    cleaning_runs: Mapped[list["CleaningRun"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
