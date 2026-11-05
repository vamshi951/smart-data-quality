from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CleaningRun(Base):
    __tablename__ = "cleaning_runs"
    __table_args__ = (
        CheckConstraint(
            "row_count_before >= 0",
            name="ck_cleaning_runs_row_count_before_nonnegative",
        ),
        CheckConstraint(
            "row_count_after >= 0",
            name="ck_cleaning_runs_row_count_after_nonnegative",
        ),
        Index("ix_cleaning_runs_dataset_created", "dataset_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    dataset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    rules_json: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    row_count_before: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count_after: Mapped[int] = mapped_column(Integer, nullable=False)
    change_counts_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    quality_before_json: Mapped[str] = mapped_column(Text, nullable=False)
    quality_after_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    dataset: Mapped["Dataset"] = relationship(back_populates="cleaning_runs")
