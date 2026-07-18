"""ERDA engine: deterministic economics — dcf, emv, monte_carlo, fiscal (spec §10.5).

DETERMINISTIC CORE (spec §0 rule 2): import-pure — no I/O, no network, no unseeded
randomness, no LLM. TEST-FIRST from the golden fixture (§11.3); a red test blocks
everything downstream. LLM narrates, code calculates: all arithmetic lives here.
"""

__version__ = "0.1.0"
