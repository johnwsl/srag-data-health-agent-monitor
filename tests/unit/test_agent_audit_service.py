import json
from pathlib import Path

from app.services.agent_audit_service import AgentAuditService


def test_audit_service_records_and_lists(tmp_path: Path):
    db_path = tmp_path / "audit.duckdb"
    service = AgentAuditService(
        duckdb_path=db_path,
        table_name="agent_audit_log",
        enabled=True,
    )

    audit_id = service.record(
        kind="chat",
        session_id="sess-1",
        estado_contexto="SP",
        user_message="Como esta a mortalidade?",
        reply="A taxa e 10%.",
        tools_used=["consultar_metricas_srag"],
        tool_events=[
            {
                "name": "consultar_metricas_srag",
                "args": {"estado": "SP"},
                "result": '{"taxa": 10}',
            }
        ],
        report_generated=False,
        charts_count=0,
        duration_ms=12.5,
        status="ok",
    )

    assert audit_id
    items = service.list_events(limit=10)
    assert len(items) == 1
    assert items[0]["audit_id"] == audit_id
    assert items[0]["session_id"] == "sess-1"
    assert items[0]["tools_used"] == ["consultar_metricas_srag"]
    assert items[0]["tool_events"][0]["name"] == "consultar_metricas_srag"

    by_session = service.get_by_session("sess-1")
    assert len(by_session) == 1

    by_id = service.get_by_id(audit_id)
    assert by_id is not None
    assert by_id["reply"] == "A taxa e 10%."


def test_audit_service_disabled_is_noop(tmp_path: Path):
    service = AgentAuditService(
        duckdb_path=tmp_path / "noop.duckdb",
        enabled=False,
    )
    assert service.record(
        kind="chat",
        session_id="s",
        estado_contexto="BRASIL",
        user_message="oi",
        reply="ola",
        duration_ms=1.0,
    ) is None
    assert service.list_events() == []


def test_audit_service_truncates_long_tool_results(tmp_path: Path):
    service = AgentAuditService(duckdb_path=tmp_path / "trunc.duckdb", enabled=True)
    audit_id = service.record(
        kind="report",
        session_id="report-1",
        estado_contexto="BRASIL",
        user_message="relatorio",
        reply="ok",
        tool_events=[{"name": "t", "args": {}, "result": "X" * 5000}],
        report_generated=True,
        charts_count=2,
        duration_ms=100.0,
    )
    item = service.get_by_id(audit_id)
    assert item is not None
    assert len(item["tool_events"][0]["result"]) <= 2000
    assert item["tool_events"][0]["result"].endswith("...")


def test_audit_service_filters_by_kind(tmp_path: Path):
    service = AgentAuditService(duckdb_path=tmp_path / "kind.duckdb", enabled=True)
    service.record(
        kind="chat",
        session_id="s1",
        estado_contexto="SP",
        user_message="a",
        reply="b",
        duration_ms=1,
    )
    service.record(
        kind="report",
        session_id="s2",
        estado_contexto="SP",
        user_message="c",
        reply="d",
        duration_ms=2,
        report_generated=True,
    )
    chats = service.list_events(kind="chat")
    reports = service.list_events(kind="report")
    assert len(chats) == 1
    assert chats[0]["kind"] == "chat"
    assert len(reports) == 1
    assert reports[0]["kind"] == "report"
    # tools_used roundtrip
    assert isinstance(json.loads(json.dumps(chats[0]["tools_used"])), list)
