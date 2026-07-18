"""Per-source connectors for ERDA Phase 2 labels and global augmentation.

Each module declares SOURCE_ID, TRANSFORM_VERSION, TABLE, a pandera SCHEMA,
a pure ``normalize()``, and ``fetch() -> FetchResult`` — run through
``erda_ingestion.base.run_connector`` so nothing reaches parquet without
provenance and a passing contract.
"""
