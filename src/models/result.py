import datetime

from sqlalchemy import Date, Index, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class XSMBResult(Base):
    __tablename__ = "xsmb_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    draw_date: Mapped[datetime.date] = mapped_column(Date, unique=True, nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Prize columns
    giai_db: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_1: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_2_1: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_2_2: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_1: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_2: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_3: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_4: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_5: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_3_6: Mapped[str] = mapped_column(String(5), nullable=False)
    giai_4_1: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_4_2: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_4_3: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_4_4: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_1: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_2: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_3: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_4: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_5: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_5_6: Mapped[str] = mapped_column(String(4), nullable=False)
    giai_6_1: Mapped[str] = mapped_column(String(3), nullable=False)
    giai_6_2: Mapped[str] = mapped_column(String(3), nullable=False)
    giai_6_3: Mapped[str] = mapped_column(String(3), nullable=False)
    giai_7_1: Mapped[str] = mapped_column(String(2), nullable=False)
    giai_7_2: Mapped[str] = mapped_column(String(2), nullable=False)
    giai_7_3: Mapped[str] = mapped_column(String(2), nullable=False)
    giai_7_4: Mapped[str] = mapped_column(String(2), nullable=False)

    # Computed fields
    raw_string: Mapped[str | None] = mapped_column(String(110))
    loto_array: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    de_dau: Mapped[str | None] = mapped_column(String(2))
    de_duoi: Mapped[str | None] = mapped_column(String(2))

    # Metadata
    ky_tu: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_xsmb_draw_date", draw_date.desc()),
        Index("idx_xsmb_giai_db", "giai_db"),
        Index("idx_xsmb_de_dau", "de_dau"),
        Index("idx_xsmb_day_of_week", "day_of_week"),
        Index(
            "idx_xsmb_year_month",
            func.extract("year", draw_date),
            func.extract("month", draw_date),
        ),
    )
