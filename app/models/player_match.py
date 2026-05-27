from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlayerMatch(Base):
    __tablename__ = "player_matches"
    __table_args__ = (
        UniqueConstraint("player_puuid", "match_id", name="uq_player_matches_player_match"),
        Index("ix_player_matches_player_puuid", "player_puuid"),
        Index("ix_player_matches_match_id", "match_id"),
        Index("ix_player_matches_player_champion", "player_puuid", "champion_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_puuid: Mapped[str] = mapped_column(
        Text,
        ForeignKey("players.puuid", ondelete="CASCADE"),
        nullable=False,
    )
    match_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("matches.match_id", ondelete="CASCADE"),
        nullable=False,
    )
    champion_id: Mapped[int] = mapped_column(Integer, nullable=False)
    champion_name: Mapped[str] = mapped_column(Text, nullable=False)
    team_position: Mapped[str | None] = mapped_column(Text)
    win: Mapped[bool] = mapped_column(Boolean, nullable=False)
    kills: Mapped[int] = mapped_column(Integer, nullable=False)
    deaths: Mapped[int] = mapped_column(Integer, nullable=False)
    assists: Mapped[int] = mapped_column(Integer, nullable=False)
    kda: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    gold_earned: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_minions_killed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    neutral_minions_killed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    vision_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_damage_dealt_to_champions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    summoner_spell_1_id: Mapped[int] = mapped_column(Integer, nullable=False)
    summoner_spell_2_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item0: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    item1: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    item2: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    item3: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    item4: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    item5: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    item6: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
