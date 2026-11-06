"""Exact contradiction checks against SQLite (B5).

The LLM never decides a contradiction. These are joins over the IOCs and
sightings we already indexed, restricted to *other* conversations so the
memory toggle stays honest.

Four kinds, matching API.md:
- case_number_changed : same alias gave a different case number elsewhere
- alias_shares_upi    : this UPI was used by a different alias elsewhere
- alias_shares_phone  : this phone was used by a different alias elsewhere
- agency_changed      : same alias (or phone) claimed a different agency elsewhere

At most three flags are returned, most severe first.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import db

MAX_FLAGS = 3

KIND_ORDER = {
    "case_number_changed": 0,
    "alias_shares_upi": 1,
    "alias_shares_phone": 2,
    "agency_changed": 3,
}

ACRONYMS = {"cbi", "trai", "ed", "rbi"}


def _field(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name, None)


def _by_type(current_iocs: Sequence[Any]) -> dict[str, list[str]]:
    grouped: dict[str, set[str]] = {
        "alias": set(),
        "upi": set(),
        "phone": set(),
        "case_number": set(),
        "agency_claimed": set(),
    }
    for item in current_iocs:
        ioc_type = _field(item, "type")
        value = _field(item, "value")
        if ioc_type in grouped and value:
            grouped[ioc_type].add(str(value))
    return {key: sorted(values) for key, values in grouped.items()}


def _alias_label(value: str) -> str:
    return " ".join(
        word.upper() if word in ACRONYMS else word.title() for word in value.split()
    )


def _agency_label(value: str) -> str:
    if len(value) <= 4:
        return value.upper()
    return value.replace("_", " ").title()


def _in_clause(values: Iterable[str]) -> tuple[str, list[str]]:
    values = list(values)
    if not values:
        return "", []
    return f" AND a.value NOT IN ({', '.join('?' for _ in values)})", values


def _case_number_changes(
    conn,
    conversation_id: str,
    aliases: list[str],
    case_numbers: list[str],
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for alias in aliases:
        for case_number in case_numbers:
            row = conn.execute(
                """
                SELECT cn.value AS previous_value,
                       c.id AS source_conversation_id,
                       c.started_at AS source_started_at
                FROM edges e
                JOIN iocs a ON a.id = e.source_ioc
                JOIN iocs cn ON cn.id = e.target_ioc
                JOIN ioc_sightings sa ON sa.ioc_id = a.id
                JOIN ioc_sightings sc
                     ON sc.ioc_id = cn.id
                    AND sc.conversation_id = sa.conversation_id
                JOIN conversations c ON c.id = sa.conversation_id
                WHERE a.type = 'alias'
                  AND a.value = ?
                  AND cn.type = 'case_number'
                  AND e.relation = 'gave_case_number'
                  AND sa.conversation_id <> ?
                  AND cn.value <> ?
                ORDER BY c.started_at DESC, sa.conversation_id DESC
                LIMIT 1
                """,
                (alias, conversation_id, case_number),
            ).fetchone()
            if row is None:
                continue
            flags.append(
                {
                    "kind": "case_number_changed",
                    "claim_now": f"Case {case_number}",
                    "claim_before": f"Case {row['previous_value']}",
                    "source_conversation_id": row["source_conversation_id"],
                    "severity": "high",
                }
            )
    return flags


def _shared_target(
    conn,
    conversation_id: str,
    target_type: str,
    target_values: list[str],
    current_aliases: list[str],
    relation: str,
    kind: str,
    severity: str,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    alias_filter, alias_params = _in_clause(current_aliases)
    current_alias = _alias_label(current_aliases[0]) if current_aliases else "This caller"

    for value in target_values:
        row = conn.execute(
            f"""
            SELECT a.value AS previous_alias,
                   c.id AS source_conversation_id,
                   c.started_at AS source_started_at
            FROM edges e
            JOIN iocs a ON a.id = e.source_ioc
            JOIN iocs t ON t.id = e.target_ioc
            JOIN ioc_sightings sa ON sa.ioc_id = a.id
            JOIN ioc_sightings st
                 ON st.ioc_id = t.id
                AND st.conversation_id = sa.conversation_id
            JOIN conversations c ON c.id = sa.conversation_id
            WHERE a.type = 'alias'
              AND t.type = ?
              AND t.value = ?
              AND e.relation = ?
              AND st.conversation_id <> ?
              {alias_filter}
            ORDER BY c.started_at DESC, sa.conversation_id DESC
            LIMIT 1
            """,
            (target_type, value, relation, conversation_id, *alias_params),
        ).fetchone()
        if row is None:
            continue
        flags.append(
            {
                "kind": kind,
                "claim_now": f"{current_alias} used {value}",
                "claim_before": f"{_alias_label(row['previous_alias'])} used {value}",
                "source_conversation_id": row["source_conversation_id"],
                "severity": severity,
            }
        )
    return flags


def _agency_change_for_alias(
    conn,
    conversation_id: str,
    aliases: list[str],
    agencies: list[str],
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for alias in aliases:
        for agency in agencies:
            row = conn.execute(
                """
                SELECT ag.value AS previous_agency,
                       c.id AS source_conversation_id,
                       c.started_at AS source_started_at
                FROM edges e
                JOIN iocs a ON a.id = e.source_ioc
                JOIN iocs ag ON ag.id = e.target_ioc
                JOIN ioc_sightings sa ON sa.ioc_id = a.id
                JOIN ioc_sightings sg
                     ON sg.ioc_id = ag.id
                    AND sg.conversation_id = sa.conversation_id
                JOIN conversations c ON c.id = sa.conversation_id
                WHERE a.type = 'alias'
                  AND a.value = ?
                  AND ag.type = 'agency_claimed'
                  AND ag.value <> ?
                  AND e.relation = 'claims_agency'
                  AND sa.conversation_id <> ?
                ORDER BY c.started_at DESC, sa.conversation_id DESC
                LIMIT 1
                """,
                (alias, agency, conversation_id),
            ).fetchone()
            if row is None:
                continue
            flags.append(
                {
                    "kind": "agency_changed",
                    "claim_now": f"{_alias_label(alias)} claims {_agency_label(agency)}",
                    "claim_before": (
                        f"{_alias_label(alias)} claimed "
                        f"{_agency_label(row['previous_agency'])}"
                    ),
                    "source_conversation_id": row["source_conversation_id"],
                    "severity": "low",
                }
            )
    return flags


def _agency_change_for_phone(
    conn,
    conversation_id: str,
    phones: list[str],
    agencies: list[str],
) -> list[dict[str, Any]]:
    """Conservative fallback when the message has a phone but no alias.

    Only looks at earlier conversations with exactly one agency, so a chat
    mentioning both CBI and TRAI does not produce a false contradiction.
    """
    flags: list[dict[str, Any]] = []
    for phone in phones:
        for agency in agencies:
            row = conn.execute(
                """
                SELECT ag.value AS previous_agency,
                       c.id AS source_conversation_id,
                       c.started_at AS source_started_at
                FROM ioc_sightings sp
                JOIN iocs p ON p.id = sp.ioc_id
                JOIN ioc_sightings sg ON sg.conversation_id = sp.conversation_id
                JOIN iocs ag ON ag.id = sg.ioc_id
                JOIN conversations c ON c.id = sp.conversation_id
                WHERE p.type = 'phone'
                  AND p.value = ?
                  AND ag.type = 'agency_claimed'
                  AND ag.value <> ?
                  AND sp.conversation_id <> ?
                  AND (
                      SELECT COUNT(DISTINCT ag2.value)
                      FROM ioc_sightings sg2
                      JOIN iocs ag2 ON ag2.id = sg2.ioc_id
                      WHERE sg2.conversation_id = sp.conversation_id
                        AND ag2.type = 'agency_claimed'
                  ) = 1
                ORDER BY c.started_at DESC, sp.conversation_id DESC
                LIMIT 1
                """,
                (phone, agency, conversation_id),
            ).fetchone()
            if row is None:
                continue
            flags.append(
                {
                    "kind": "agency_changed",
                    "claim_now": f"This caller claims {_agency_label(agency)}",
                    "claim_before": (
                        f"This caller claimed {_agency_label(row['previous_agency'])}"
                    ),
                    "source_conversation_id": row["source_conversation_id"],
                    "severity": "low",
                }
            )
    return flags


def _dedupe(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for flag in flags:
        key = (
            flag["kind"],
            flag["claim_now"],
            flag["claim_before"],
            flag["source_conversation_id"],
        )
        if key not in seen:
            seen.add(key)
            unique.append(flag)
    return unique


def find_contradictions(
    current_iocs: Sequence[Any],
    conversation_id: str,
    recalled_memories: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return at most three contradiction flags, high severity first."""
    grouped = _by_type(current_iocs)
    aliases = grouped["alias"]
    upis = grouped["upi"]
    phones = grouped["phone"]
    case_numbers = grouped["case_number"]
    agencies = grouped["agency_claimed"]

    if not any((aliases, upis, phones, case_numbers, agencies)):
        return []

    with db.connect() as conn:
        conversation = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if conversation is None:
            return []

        flags: list[dict[str, Any]] = []
        if aliases and case_numbers:
            flags.extend(
                _case_number_changes(conn, conversation_id, aliases, case_numbers)
            )
        if upis:
            flags.extend(
                _shared_target(
                    conn,
                    conversation_id,
                    "upi",
                    upis,
                    aliases,
                    "uses_upi",
                    "alias_shares_upi",
                    "high",
                )
            )
        if phones:
            flags.extend(
                _shared_target(
                    conn,
                    conversation_id,
                    "phone",
                    phones,
                    aliases,
                    "uses_phone",
                    "alias_shares_phone",
                    "low",
                )
            )
        if agencies:
            if aliases:
                flags.extend(
                    _agency_change_for_alias(conn, conversation_id, aliases, agencies)
                )
            if phones:
                flags.extend(
                    _agency_change_for_phone(conn, conversation_id, phones, agencies)
                )

    flags = _dedupe(flags)
    flags.sort(
        key=lambda flag: (
            0 if flag["severity"] == "high" else 1,
            KIND_ORDER.get(flag["kind"], 99),
        )
    )
    return flags[:MAX_FLAGS]
