"""SQLite index for /network and /stats (B3).

Hindsight is the brain; this database is the exact-value index the UI draws.
Schema follows architecture.md section 6, plus one `contradictions` table that
/stats needs for `contradictions_caught` (B5 writes to it).

Every function opens its own short-lived connection. At demo scale this is
simpler and safer than sharing one connection across FastAPI's thread pool.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Sequence

from config import settings

NODE_TYPES = ("alias", "upi", "phone", "agency_claimed")
RING_TYPES = ("alias", "upi", "phone")
RELATION_BY_TYPE = {
    "upi": "uses_upi",
    "phone": "uses_phone",
    "agency_claimed": "claims_agency",
    "case_number": "gave_case_number",
}
SCAMMER_TURN_SECONDS = 45

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id                  TEXT PRIMARY KEY,
    started_at          TEXT NOT NULL,
    ended_at            TEXT,
    persona             TEXT NOT NULL DEFAULT 'ajji',
    memory_enabled_last INTEGER NOT NULL DEFAULT 1,
    summary_json        TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender          TEXT NOT NULL CHECK (sender IN ('scammer', 'ajji')),
    text            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    script_stage    TEXT
);

CREATE TABLE IF NOT EXISTS iocs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT NOT NULL,
    value      TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    count      INTEGER NOT NULL DEFAULT 1,
    UNIQUE (type, value)
);

CREATE TABLE IF NOT EXISTS ioc_sightings (
    ioc_id          INTEGER NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_id      INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    UNIQUE (ioc_id, message_id)
);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_ioc  INTEGER NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    target_ioc  INTEGER NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    relation    TEXT NOT NULL,
    weight      INTEGER NOT NULL DEFAULT 1,
    UNIQUE (source_ioc, target_ioc, relation)
);

CREATE TABLE IF NOT EXISTS contradictions (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id        TEXT NOT NULL,
    message_id             INTEGER,
    kind                   TEXT NOT NULL,
    claim_now              TEXT NOT NULL,
    claim_before           TEXT NOT NULL,
    source_conversation_id TEXT NOT NULL,
    severity               TEXT NOT NULL,
    created_at             TEXT NOT NULL,
    UNIQUE (conversation_id, kind, claim_now, claim_before, source_conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_sightings_conversation ON ioc_sightings(conversation_id);
CREATE INDEX IF NOT EXISTS idx_sightings_ioc ON ioc_sightings(ioc_id);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_ioc);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_ioc);
"""


# ── Plumbing ────────────────────────────────────────────────────


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _iso(value: datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return value or utc_now_iso()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode = WAL")


def reset_db() -> None:
    """Drop every table and recreate the schema. Leaves no rows behind."""
    with connect() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            """
            DROP TABLE IF EXISTS contradictions;
            DROP TABLE IF EXISTS edges;
            DROP TABLE IF EXISTS ioc_sightings;
            DROP TABLE IF EXISTS iocs;
            DROP TABLE IF EXISTS messages;
            DROP TABLE IF EXISTS conversations;
            """
        )
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode = WAL")


# ── Conversations and messages ──────────────────────────────────


def create_conversation(
    conversation_id: str,
    started_at: datetime | str | None = None,
    persona: str = "ajji",
    memory_enabled_last: bool = True,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO conversations (id, started_at, ended_at, persona, memory_enabled_last)
            VALUES (?, ?, NULL, ?, ?)
            """,
            (conversation_id, _iso(started_at), persona, int(memory_enabled_last)),
        )


def conversation_exists(conversation_id: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return row is not None


def next_conversation_id() -> str:
    """conv_0001, conv_0002… based on the highest existing numeric suffix."""
    with connect() as conn:
        rows = conn.execute("SELECT id FROM conversations").fetchall()
    highest = 0
    for row in rows:
        match = re.search(r"(\d+)$", row["id"])
        if match:
            highest = max(highest, int(match.group(1)))
    return f"conv_{highest + 1:04d}"


def add_message(
    conversation_id: str,
    sender: str,
    text: str,
    created_at: datetime | str | None = None,
    script_stage: str | None = None,
    memory_enabled: bool | None = None,
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO messages (conversation_id, sender, text, created_at, script_stage)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, sender, text, _iso(created_at), script_stage),
        )
        if memory_enabled is not None:
            conn.execute(
                "UPDATE conversations SET memory_enabled_last = ? WHERE id = ?",
                (int(memory_enabled), conversation_id),
            )
        return int(cursor.lastrowid)


def set_message_stage(message_id: int, stage: str | None) -> None:
    with connect() as conn:
        conn.execute("UPDATE messages SET script_stage = ? WHERE id = ?", (stage, message_id))


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return None
        messages = conn.execute(
            """
            SELECT id, sender, text, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()

    return {
        "conversation_id": row["id"],
        "persona": row["persona"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "messages": [
            {
                "id": message["id"],
                "sender": message["sender"],
                "text": message["text"],
                "created_at": message["created_at"],
            }
            for message in messages
        ],
    }


def end_conversation(
    conversation_id: str,
    ended_at: datetime | str | None = None,
    summary: dict[str, Any] | None = None,
) -> bool:
    """Stamp the end time and summary once. A second call keeps the first values."""
    ended = _iso(ended_at)
    payload = json.dumps(summary, ensure_ascii=False) if summary is not None else None
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return False
        conn.execute(
            """
            UPDATE conversations
            SET ended_at = COALESCE(ended_at, ?),
                summary_json = COALESCE(summary_json, ?)
            WHERE id = ?
            """,
            (ended, payload, conversation_id),
        )
    return True


def get_summary(conversation_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT summary_json FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
    if row is None or not row["summary_json"]:
        return None
    return json.loads(row["summary_json"])


SUMMARY_BUCKETS = {
    "alias": "aliases",
    "agency_claimed": "agencies_claimed",
    "case_number": "case_numbers",
    "upi": "upi_ids",
    "phone": "phones",
}


def conversation_summary_parts(conversation_id: str) -> dict[str, list[str]]:
    """Distinct identifiers and stages seen in one conversation, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT i.type AS type, i.value AS value
            FROM iocs i
            JOIN ioc_sightings s ON s.ioc_id = i.id
            WHERE s.conversation_id = ?
            GROUP BY i.id
            ORDER BY MIN(i.first_seen), i.value
            """,
            (conversation_id,),
        ).fetchall()
        stages = conn.execute(
            """
            SELECT script_stage, MIN(id) AS first_id
            FROM messages
            WHERE conversation_id = ? AND script_stage IS NOT NULL
            GROUP BY script_stage
            ORDER BY first_id
            """,
            (conversation_id,),
        ).fetchall()

    summary: dict[str, list[str]] = {
        "aliases": [],
        "agencies_claimed": [],
        "case_numbers": [],
        "upi_ids": [],
        "phones": [],
        "stages_reached": [row["script_stage"] for row in stages],
    }
    for row in rows:
        bucket = SUMMARY_BUCKETS.get(row["type"])
        if bucket and row["value"] not in summary[bucket]:
            summary[bucket].append(row["value"])
    return summary


# ── IOC indexing ────────────────────────────────────────────────


def _field(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _pairs(iocs: Sequence[Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in iocs:
        ioc_type = _field(item, "type")
        value = _field(item, "value")
        if ioc_type and value:
            pairs.append((str(ioc_type), str(value)))
    # Preserve order, drop duplicates inside one message.
    return list(dict.fromkeys(pairs))


def upsert_iocs(
    conversation_id: str,
    message_id: int,
    iocs: Sequence[Any],
    seen_at: datetime | str | None = None,
) -> None:
    """Index IOCs, record sightings and (re)build alias→identifier edges."""
    seen = _iso(seen_at)
    pairs = _pairs(iocs)
    if not pairs:
        return

    with connect() as conn:
        for ioc_type, value in pairs:
            conn.execute(
                """
                INSERT INTO iocs (type, value, first_seen, last_seen, count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT (type, value) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    count = count + 1
                """,
                (ioc_type, value, seen, seen),
            )
            row = conn.execute(
                "SELECT id FROM iocs WHERE type = ? AND value = ?", (ioc_type, value)
            ).fetchone()
            conn.execute(
                """
                INSERT OR IGNORE INTO ioc_sightings (ioc_id, conversation_id, message_id)
                VALUES (?, ?, ?)
                """,
                (row["id"], conversation_id, message_id),
            )

        current = set(pairs)
        aliases = conn.execute(
            """
            SELECT DISTINCT i.id, i.type, i.value
            FROM iocs i
            JOIN ioc_sightings s ON s.ioc_id = i.id
            WHERE s.conversation_id = ? AND i.type = 'alias'
            """,
            (conversation_id,),
        ).fetchall()
        targets = conn.execute(
            """
            SELECT DISTINCT i.id, i.type, i.value
            FROM iocs i
            JOIN ioc_sightings s ON s.ioc_id = i.id
            WHERE s.conversation_id = ? AND i.type IN ('upi', 'phone', 'agency_claimed', 'case_number')
            """,
            (conversation_id,),
        ).fetchall()

        for alias in aliases:
            for target in targets:
                relation = RELATION_BY_TYPE.get(target["type"])
                if relation is None:
                    continue
                edge = conn.execute(
                    """
                    SELECT id FROM edges
                    WHERE source_ioc = ? AND target_ioc = ? AND relation = ?
                    """,
                    (alias["id"], target["id"], relation),
                ).fetchone()
                if edge is None:
                    conn.execute(
                        """
                        INSERT INTO edges (source_ioc, target_ioc, relation, weight)
                        VALUES (?, ?, ?, 1)
                        """,
                        (alias["id"], target["id"], relation),
                    )
                elif (alias["type"], alias["value"]) in current and (
                    target["type"],
                    target["value"],
                ) in current:
                    # Weight counts messages where this alias and target co-occur.
                    conn.execute("UPDATE edges SET weight = weight + 1 WHERE id = ?", (edge["id"],))


def record_contradiction(
    conversation_id: str,
    flag: Any,
    message_id: int | None = None,
    created_at: datetime | str | None = None,
) -> None:
    """Store one contradiction so /stats can count it. Duplicates are ignored."""
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO contradictions
                (conversation_id, message_id, kind, claim_now, claim_before,
                 source_conversation_id, severity, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                message_id,
                str(_field(flag, "kind") or ""),
                str(_field(flag, "claim_now") or ""),
                str(_field(flag, "claim_before") or ""),
                str(_field(flag, "source_conversation_id") or ""),
                str(_field(flag, "severity") or "low"),
                _iso(created_at),
            ),
        )


# ── Network ─────────────────────────────────────────────────────


def _display_label(ioc_type: str, value: str) -> str:
    if ioc_type == "alias":
        words = value.split()
        return " ".join(
            word.upper() if word in {"cbi", "trai", "ed", "rbi"} else word.title()
            for word in words
        )
    if ioc_type == "phone":
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) == 10:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        return value
    if ioc_type == "agency_claimed":
        if len(value) <= 4:
            return value.upper()
        return value.replace("_", " ").title()
    return value


def _ring_assignment(conn: sqlite3.Connection) -> dict[int, str]:
    """Union alias/UPI/phone into components; only 2+ alias components are rings.

    Agencies are deliberately excluded so "CBI" does not merge every ring.
    """
    rows = conn.execute(
        "SELECT id, type, value, first_seen FROM iocs WHERE type IN ('alias', 'upi', 'phone')"
    ).fetchall()
    parent = {row["id"]: row["id"] for row in rows}
    first_seen = {row["id"]: row["first_seen"] for row in rows}
    values = {row["id"]: row["value"] for row in rows}
    types = {row["id"]: row["type"] for row in rows}

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    edge_rows = conn.execute(
        """
        SELECT e.source_ioc, e.target_ioc
        FROM edges e
        JOIN iocs s ON s.id = e.source_ioc
        JOIN iocs t ON t.id = e.target_ioc
        WHERE s.type IN ('alias', 'upi', 'phone')
          AND t.type IN ('alias', 'upi', 'phone')
        """
    ).fetchall()
    for edge in edge_rows:
        union(edge["source_ioc"], edge["target_ioc"])

    components: dict[int, list[int]] = defaultdict(list)
    for node in parent:
        components[find(node)].append(node)

    candidates: list[tuple[tuple[str, str], list[int]]] = []
    for members in components.values():
        if sum(1 for node in members if types[node] == "alias") < 2:
            continue
        sort_key = (
            min(first_seen[node] for node in members),
            min(values[node] for node in members),
        )
        candidates.append((sort_key, members))

    candidates.sort(key=lambda item: item[0])
    assignment: dict[int, str] = {}
    for index, (_, members) in enumerate(candidates, start=1):
        for node in members:
            assignment[node] = f"ring_{index}"
    return assignment


def get_network(conversation_id: str | None = None) -> dict[str, Any]:
    """Build the GET /network response from API.md."""
    with connect() as conn:
        node_rows = conn.execute(
            """
            SELECT id, type, value, first_seen, count
            FROM iocs
            WHERE type IN ('alias', 'upi', 'phone', 'agency_claimed')
            ORDER BY first_seen ASC, type ASC, value ASC
            """
        ).fetchall()

        in_current: set[int] = set()
        if conversation_id:
            in_current = {
                row["ioc_id"]
                for row in conn.execute(
                    "SELECT DISTINCT ioc_id FROM ioc_sightings WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchall()
            }

        ring_by_ioc = _ring_assignment(conn)

        nodes = [
            {
                "id": f"{row['type']}:{row['value']}",
                "type": row["type"],
                "label": _display_label(row["type"], row["value"]),
                "first_seen": row["first_seen"],
                "count": row["count"],
                "ring_id": ring_by_ioc.get(row["id"]),
                "in_current": row["id"] in in_current,
            }
            for row in node_rows
        ]

        edge_rows = conn.execute(
            """
            SELECT s.type AS source_type, s.value AS source_value,
                   t.type AS target_type, t.value AS target_value,
                   e.relation, e.weight
            FROM edges e
            JOIN iocs s ON s.id = e.source_ioc
            JOIN iocs t ON t.id = e.target_ioc
            WHERE s.type IN ('alias', 'upi', 'phone', 'agency_claimed')
              AND t.type IN ('alias', 'upi', 'phone', 'agency_claimed')
            ORDER BY s.type, s.value, t.type, t.value, e.relation
            """
        ).fetchall()

    edges = [
        {
            "source": f"{row['source_type']}:{row['source_value']}",
            "target": f"{row['target_type']}:{row['target_value']}",
            "relation": row["relation"],
            "weight": row["weight"],
        }
        for row in edge_rows
    ]

    return {"nodes": nodes, "edges": edges}


# ── Stats ───────────────────────────────────────────────────────


def get_stats() -> dict[str, Any]:
    """Build the GET /stats response from API.md."""
    with connect() as conn:
        conversations = conn.execute("SELECT COUNT(*) AS n FROM conversations").fetchone()["n"]
        scammer_turns = conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE sender = 'scammer'"
        ).fetchone()["n"]

        def unique(ioc_type: str) -> int:
            return conn.execute(
                "SELECT COUNT(*) AS n FROM iocs WHERE type = ?", (ioc_type,)
            ).fetchone()["n"]

        unique_aliases = unique("alias")
        unique_upi = unique("upi")
        unique_phones = unique("phone")

        ring_count = len(set(_ring_assignment(conn).values()))
        contradictions = conn.execute("SELECT COUNT(*) AS n FROM contradictions").fetchone()["n"]
        ended = conn.execute(
            "SELECT COUNT(*) AS n FROM conversations WHERE ended_at IS NOT NULL"
        ).fetchone()["n"]

    # Every scammer turn is retained, and every ended conversation adds a summary.
    memories_in_bank = scammer_turns + ended
    minutes = int(round(scammer_turns * SCAMMER_TURN_SECONDS / 60))

    return {
        "conversations": conversations,
        "total_minutes_wasted_estimate": minutes,
        "minutes_is_estimate": True,
        "unique_aliases": unique_aliases,
        "unique_upi": unique_upi,
        "unique_phones": unique_phones,
        "rings_detected": ring_count,
        "contradictions_caught": contradictions,
        "memories_in_bank": memories_in_bank,
    }
