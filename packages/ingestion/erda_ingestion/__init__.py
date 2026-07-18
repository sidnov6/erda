"""ERDA ingestion: per-source connectors, one module per source_id (spec §4).

Every connector declares a pandera contract, writes parquet, and attaches provenance
{source_id, retrieved_at, source_url, transform_version}. A failing source raises and
stops — it never invents data.
"""

__version__ = "0.1.0"
