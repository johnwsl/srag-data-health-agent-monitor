import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.config import AGENT_AUDIT_ENABLED, AGENT_AUDIT_TABLE_NAME, DUCKDB_PATH

logger = logging.getLogger(__name__)


class AgentAuditService:
    """Persiste e consulta eventos de auditoria do orquestrador LangGraph no DuckDB."""

    def __init__(
        self,
        duckdb_path: Path = DUCKDB_PATH,
        table_name: str = AGENT_AUDIT_TABLE_NAME,
        enabled: bool = AGENT_AUDIT_ENABLED,
    ) -> None:
        self.duckdb_path = Path(duckdb_path)
        self.table_name = table_name
        self.enabled = enabled
        self._ensured = False

    def _connect(self, *, read_only: bool = False):
        self.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(self.duckdb_path), read_only=read_only)

    def ensure_table(self) -> None:
        if self._ensured or not self.enabled:
            return

        connection = self._connect(read_only=False)
        try:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS "{self.table_name}" (
                    audit_id VARCHAR PRIMARY KEY,
                    created_at VARCHAR NOT NULL,
                    kind VARCHAR NOT NULL,
                    session_id VARCHAR NOT NULL,
                    estado_contexto VARCHAR NOT NULL,
                    user_message VARCHAR NOT NULL,
                    reply VARCHAR NOT NULL,
                    tools_used VARCHAR NOT NULL,
                    tool_events VARCHAR NOT NULL,
                    report_generated BOOLEAN NOT NULL,
                    charts_count INTEGER NOT NULL,
                    duration_ms DOUBLE NOT NULL,
                    status VARCHAR NOT NULL,
                    error_message VARCHAR
                )
                """
            )
        finally:
            connection.close()
        self._ensured = True

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        compact = (text or "").strip()
        if len(compact) <= max_chars:
            return compact
        return f"{compact[: max_chars - 3].rstrip()}..."

    def record(
        self,
        *,
        kind: str,
        session_id: str,
        estado_contexto: str,
        user_message: str,
        reply: str,
        tools_used: list[str] | None = None,
        tool_events: list[dict[str, Any]] | None = None,
        report_generated: bool = False,
        charts_count: int = 0,
        duration_ms: float = 0.0,
        status: str = "ok",
        error_message: str | None = None,
    ) -> str | None:
        """Grava um evento de auditoria. Falhas de persistencia nao interrompem o agente."""
        if not self.enabled:
            return None

        audit_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        tools = list(tools_used or [])
        events = list(tool_events or [])

        # Limita tamanho dos resultados das tools para nao inflar o banco.
        safe_events: list[dict[str, Any]] = []
        for event in events:
            safe_events.append(
                {
                    "name": str(event.get("name") or "unknown"),
                    "args": event.get("args") or {},
                    "result": self._truncate(str(event.get("result") or ""), 2000),
                }
            )

        try:
            self.ensure_table()
            connection = self._connect(read_only=False)
            try:
                connection.execute(
                    f"""
                    INSERT INTO "{self.table_name}" VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    [
                        audit_id,
                        created_at,
                        kind,
                        session_id,
                        estado_contexto,
                        self._truncate(user_message, 4000),
                        self._truncate(reply, 4000),
                        json.dumps(tools, ensure_ascii=False),
                        json.dumps(safe_events, ensure_ascii=False),
                        bool(report_generated),
                        int(charts_count),
                        float(duration_ms),
                        status,
                        error_message,
                    ],
                )
            finally:
                connection.close()
            return audit_id
        except Exception as error:  # noqa: BLE001
            logger.warning("Falha ao gravar auditoria do agente: %s", error)
            return None

    def _row_to_dict(self, row: tuple[Any, ...]) -> dict[str, Any]:
        (
            audit_id,
            created_at,
            kind,
            session_id,
            estado_contexto,
            user_message,
            reply,
            tools_used,
            tool_events,
            report_generated,
            charts_count,
            duration_ms,
            status,
            error_message,
        ) = row

        def _loads(value: Any, default: Any) -> Any:
            if value is None or value == "":
                return default
            if isinstance(value, (list, dict)):
                return value
            try:
                return json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return default

        return {
            "audit_id": audit_id,
            "created_at": created_at,
            "kind": kind,
            "session_id": session_id,
            "estado_contexto": estado_contexto,
            "user_message": user_message,
            "reply": reply,
            "tools_used": _loads(tools_used, []),
            "tool_events": _loads(tool_events, []),
            "report_generated": bool(report_generated),
            "charts_count": int(charts_count or 0),
            "duration_ms": float(duration_ms or 0.0),
            "status": status,
            "error_message": error_message,
        }

    def list_events(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        kind: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []

        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))

        clauses: list[str] = []
        params: list[Any] = []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([safe_limit, safe_offset])

        try:
            self.ensure_table()
            connection = self._connect(read_only=True)
            try:
                rows = connection.execute(
                    f"""
                    SELECT
                        audit_id, created_at, kind, session_id, estado_contexto,
                        user_message, reply, tools_used, tool_events,
                        report_generated, charts_count, duration_ms, status, error_message
                    FROM "{self.table_name}"
                    {where}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    params,
                ).fetchall()
            finally:
                connection.close()
        except Exception as error:  # noqa: BLE001
            logger.warning("Falha ao consultar auditoria do agente: %s", error)
            return []

        return [self._row_to_dict(row) for row in rows]

    def get_by_session(self, session_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.list_events(limit=limit, offset=0, session_id=session_id)

    def get_by_id(self, audit_id: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        try:
            self.ensure_table()
            connection = self._connect(read_only=True)
            try:
                row = connection.execute(
                    f"""
                    SELECT
                        audit_id, created_at, kind, session_id, estado_contexto,
                        user_message, reply, tools_used, tool_events,
                        report_generated, charts_count, duration_ms, status, error_message
                    FROM "{self.table_name}"
                    WHERE audit_id = ?
                    LIMIT 1
                    """,
                    [audit_id],
                ).fetchone()
            finally:
                connection.close()
        except Exception as error:  # noqa: BLE001
            logger.warning("Falha ao consultar auditoria por id: %s", error)
            return None

        if row is None:
            return None
        return self._row_to_dict(row)
