"""Habitica Personal Productivity Intelligence — ETL & analytics package.

Modules:
  config      — paths, timezone, decode constants (all analytical choices)
  loaders     — read & checksum the raw exports (no interpretation)
  transform   — pure, testable transforms (timestamps, value-delta decode, text)
  database    — SQLite schema + idempotent, transaction-safe ingestion
  validation  — integrity checks + CSV<->JSON reconciliation
  analytics   — parameterised SQL -> pandas helpers for the notebook
"""
from . import analytics, config, database, loaders, transform, validation  # noqa: F401

__all__ = ["config", "loaders", "transform", "database", "validation", "analytics"]
