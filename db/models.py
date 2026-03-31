"""
lexilab — SQLAlchemy ORM models
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True)
    session_id = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    datasets   = relationship("Dataset", back_populates="user")


# ──────────────────────────────────────────────
class Dataset(Base):
    __tablename__ = "datasets"

    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name         = Column(String(255), nullable=False)
    lang         = Column(String(10))
    raw_text     = Column(Text, nullable=False)
    token_count  = Column(Integer)
    unique_count = Column(Integer)
    is_public    = Column(Boolean, default=True)
    is_research  = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    user         = relationship("User", back_populates="datasets")
    analysis     = relationship("Analysis", back_populates="dataset", uselist=False)
    collocations = relationship("Collocation", back_populates="dataset")
    benchmarks   = relationship("Benchmark", back_populates="dataset")


# ──────────────────────────────────────────────
class Analysis(Base):
    __tablename__ = "analyses"

    id            = Column(Integer, primary_key=True)
    dataset_id    = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"))
    ttr           = Column(Float)
    yules_k       = Column(Float)
    hapax_count   = Column(Integer)
    zipf_constant = Column(Float)
    zipf_corr     = Column(Float)
    fits_zipf     = Column(Boolean)
    top_words     = Column(JSONB)
    freq_bands    = Column(JSONB)
    created_at    = Column(DateTime, default=datetime.utcnow)

    dataset       = relationship("Dataset", back_populates="analysis")


# ──────────────────────────────────────────────
class Collocation(Base):
    __tablename__ = "collocations"

    id         = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"))
    measure    = Column(String(20), nullable=False)
    w1         = Column(String(100), nullable=False)
    w2         = Column(String(100), nullable=False)
    freq       = Column(Integer)
    score      = Column(Float)
    rank       = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset    = relationship("Dataset", back_populates="collocations")

    __table_args__ = (
        Index("idx_colls_dataset_measure", "dataset_id", "measure"),
    )


# ──────────────────────────────────────────────
class Benchmark(Base):
    __tablename__ = "benchmarks"

    id         = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"))
    method     = Column(String(50), nullable=False)
    time_ms    = Column(Float)
    memory_kb  = Column(Float)
    available  = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset    = relationship("Dataset", back_populates="benchmarks")