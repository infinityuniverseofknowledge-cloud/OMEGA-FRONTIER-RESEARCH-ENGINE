"""Offline knowledge store and a small, explicitly synthetic scenario catalog.

No bundled entry is an observation, citation, scientific validation or prediction.
The caller owns database paths, backup and source verification. stdlib only.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

SCHEMA_VERSION = 1
SYNTHETIC_ORIGIN = "OMEGA synthetic teaching presets v1; invented assumptions, not empirical data"

# Four illustrative ecological contexts and three distinct pressures. Values are
# dimensionless toy parameters, chosen for readable behavior, not calibrated.
_CONTEXTS = (
    ("grassland", "Open grassland", 80.0, 120.0, 0.16),
    ("forest", "Temperate forest", 100.0, 160.0, 0.09),
    ("wetland", "Freshwater wetland", 65.0, 100.0, 0.14),
    ("island", "Small island habitat", 35.0, 60.0, 0.08),
)
_PRESSURES = (
    ("baseline", "No additional pressure", 0.00),
    ("moderate", "Moderate persistent pressure", 0.04),
    ("high", "High persistent pressure", 0.10),
)


def generate_scenarios() -> list[dict[str, Any]]:
    """Return 12 reproducible combinations, each a *hypothesis*, not evidence."""
    result = []
    for habitat, label, initial, capacity, growth in _CONTEXTS:
        for pressure_id, pressure, loss in _PRESSURES:
            result.append({
                "id": f"synthetic:{habitat}:{pressure_id}",
                "title": f"{label} — {pressure}",
                "description": (f"A single abstract population in {label.lower()} "
                                f"under {pressure.lower()}; no species, spatial "
                                "structure or causal intervention is represented."),
                "parameters": {"initial_population": initial, "carrying_capacity": capacity,
                               "growth_rate": growth, "pressure": loss,
                               "noise_fraction": 0.10, "steps": 40, "replicates": 100},
                "provenance": SYNTHETIC_ORIGIN,
                "evidence_status": "synthetic_hypothesis",
            })
    return result


class KnowledgeStore:
    """Small SQLite store. Each instance owns its connection; use close() or with.

    FTS5 is optional. Public search uses Unicode case-folded literal substrings
    independently of FTS. A scenario's parameter JSON is distinct from evidence.
    """
    def __init__(self, path: str = ":memory:", *, enable_fts: bool = True):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.fts_enabled = False
        try:
            # SQLite LIKE only ignores ASCII case. Python's Unicode casefold
            # makes the public substring search work across writing systems.
            self.connection.create_function(
                'omega_contains', 2,
                lambda text, needle: int(isinstance(text, str) and needle in text.casefold()))
            self._initialize(enable_fts)
        except Exception:
            self.connection.close()
            raise

    def _initialize(self, enable_fts: bool) -> None:
        db = self.connection
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, SCHEMA_VERSION):
            raise RuntimeError(f"Unsupported schema version {version}")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL CHECK(length(trim(title)) > 0),
            locator TEXT NOT NULL CHECK(length(trim(locator)) > 0),
            source_type TEXT NOT NULL CHECK(length(trim(source_type)) > 0),
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY,
            source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
            claim TEXT NOT NULL CHECK(length(trim(claim)) > 0),
            excerpt TEXT NOT NULL CHECK(length(trim(excerpt)) > 0),
            assessment TEXT NOT NULL CHECK(assessment IN ('unverified','supported','contested')),
            limitations TEXT NOT NULL CHECK(length(trim(limitations)) > 0)
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_assessment ON evidence(assessment);
        CREATE TABLE IF NOT EXISTS scenarios (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            parameters_json TEXT NOT NULL,
            provenance TEXT NOT NULL,
            evidence_status TEXT NOT NULL CHECK(evidence_status = 'synthetic_hypothesis')
        );
        CREATE INDEX IF NOT EXISTS idx_scenarios_title ON scenarios(title);
        """)
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        if enable_fts:
            try:
                db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(claim, excerpt, content='evidence', content_rowid='id')")
            except sqlite3.OperationalError as exc:
                # Do not hide disk, syntax, lock or corruption errors as missing FTS.
                if "no such module: fts5" not in str(exc).lower():
                    raise
            else:
                db.executescript("""
                CREATE TRIGGER IF NOT EXISTS evidence_ai AFTER INSERT ON evidence BEGIN
                  INSERT INTO evidence_fts(rowid, claim, excerpt) VALUES (new.id, new.claim, new.excerpt);
                END;
                CREATE TRIGGER IF NOT EXISTS evidence_ad AFTER DELETE ON evidence BEGIN
                  INSERT INTO evidence_fts(evidence_fts, rowid, claim, excerpt) VALUES('delete', old.id, old.claim, old.excerpt);
                END;
                CREATE TRIGGER IF NOT EXISTS evidence_au AFTER UPDATE ON evidence BEGIN
                  INSERT INTO evidence_fts(evidence_fts, rowid, claim, excerpt) VALUES('delete', old.id, old.claim, old.excerpt);
                  INSERT INTO evidence_fts(rowid, claim, excerpt) VALUES (new.id, new.claim, new.excerpt);
                END;
                """)
                # Covers records created before FTS was enabled.
                db.execute("INSERT INTO evidence_fts(evidence_fts) VALUES('rebuild')")
                self.fts_enabled = True
        db.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def add_source(self, title: str, locator: str, source_type: str, notes: str = "") -> int:
        """Record a caller-supplied source; this does not verify its authenticity."""
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO sources(title, locator, source_type, notes) VALUES(?,?,?,?)",
                (title, locator, source_type, notes))
            return cursor.lastrowid

    def add_evidence(self, source_id: int, claim: str, excerpt: str,
                     assessment: str = "unverified", limitations: str = "Not independently verified") -> int:
        """Record a claim with source, specific excerpt and explicit limitations."""
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO evidence(source_id,claim,excerpt,assessment,limitations) VALUES(?,?,?,?,?)",
                (source_id, claim, excerpt, assessment, limitations))
            return cursor.lastrowid

    def search_evidence(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search literal Unicode case-folded substrings, independent of FTS.

        Leading/trailing query whitespace is stripped. Accents are not removed,
        and Unicode normalization is not performed. This scans evidence text;
        it does not use the optional FTS index and may be slow on large stores.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a nonempty string")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer from 1 to 1000")
        folded = query.strip().casefold()
        rows = self.connection.execute("""
            SELECT e.*, s.title AS source_title, s.locator, s.source_type, s.notes AS source_notes
            FROM evidence e JOIN sources s ON s.id=e.source_id
            WHERE omega_contains(e.claim, ?) OR omega_contains(e.excerpt, ?)
            ORDER BY e.id LIMIT ?
        """, (folded, folded, limit))
        return [dict(row) for row in rows]

    def seed_scenarios(self) -> int:
        """Insert missing curated scenarios; repeat calls do not replace edits."""
        scenarios = generate_scenarios()
        with self.connection:
            before = self.connection.total_changes
            self.connection.executemany("""
                INSERT OR IGNORE INTO scenarios
                (id,title,description,parameters_json,provenance,evidence_status)
                VALUES (:id,:title,:description,:parameters_json,:provenance,:evidence_status)
            """, [{**s, "parameters_json": json.dumps(s["parameters"], sort_keys=True, allow_nan=False)}
                  for s in scenarios])
            return self.connection.total_changes - before

    def list_scenarios(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM scenarios ORDER BY id")
        result = []
        for row in rows:
            item = dict(row)
            item["parameters"] = json.loads(item.pop("parameters_json"))
            result.append(item)
        return result
