from datetime import date

import duckdb
import pytest

from app.services.srag_metrics import SRAGMetrics


@pytest.fixture
def metrics_db(tmp_path):
    db_path = tmp_path / "metrics.duckdb"
    connection = duckdb.connect(str(db_path))
    connection.execute(
        """
        CREATE TABLE srag_notificacoes (
            NU_NOTIFIC VARCHAR,
            DT_NOTIFIC VARCHAR,
            SG_UF_NOT VARCHAR,
            CLASSI_FIN VARCHAR,
            EVOLUCAO VARCHAR,
            UTI VARCHAR,
            VACINA_COV VARCHAR,
            VACINA VARCHAR,
            ANO_NOTIFIC INTEGER,
            MES_NOTIFIC INTEGER
        )
        """
    )
    rows = [
        ("1", "2026-06-01", "SP", "1", "1", "2", "9", "2", 2026, 6),
        ("2", "2026-06-02", "SP", "2", "1", "2", "9", "2", 2026, 6),
        ("3", "2026-06-03", "SP", "3", "1", "2", "9", "2", 2026, 6),
        ("4", "2026-06-04", "SP", "4", "1", "2", "9", "2", 2026, 6),
        ("5", "2026-06-05", "SP", "9", "1", "2", "9", "2", 2026, 6),
        ("6", "2026-05-01", "SP", "1", "1", "2", "9", "2", 2026, 5),
        ("7", "2026-05-02", "SP", "2", "1", "2", "9", "2", 2026, 5),
        ("8", "2026-07-01", "SP", "1", "1", "2", "9", "2", 2026, 7),
        ("9", "2026-07-02", "SP", "2", "1", "2", "9", "2", 2026, 7),
    ]
    connection.executemany(
        """
        INSERT INTO srag_notificacoes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.close()
    return db_path


@pytest.fixture
def metrics_service(metrics_db) -> SRAGMetrics:
    return SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")


def test_taxa_aumento_casos_calculates_percent_increase(metrics_service):
    result = metrics_service.taxa_aumento_casos(reference_date=date(2026, 7, 15))

    assert result.sg_uf_not == "BRASIL"
    assert result.mes_atual_ano == 2026
    assert result.mes_atual_mes == 6
    assert result.mes_anterior_ano == 2026
    assert result.mes_anterior_mes == 5
    assert result.casos_mes_atual == 4
    assert result.casos_mes_anterior == 2
    assert result.taxa_aumento_percentual == 100.0


def test_taxa_aumento_casos_ignores_current_incomplete_month(metrics_service):
    result = metrics_service.taxa_aumento_casos(reference_date=date(2026, 7, 15))

    assert result.casos_mes_atual == 4


def test_taxa_aumento_casos_excludes_invalid_classi_fin(metrics_service):
    result = metrics_service.taxa_aumento_casos(reference_date=date(2026, 7, 15))

    assert result.casos_mes_atual == 4


def test_taxa_aumento_casos_uses_april_when_reference_is_june(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute(
        """
        INSERT INTO srag_notificacoes VALUES
        ('10', '2026-04-01', 'SP', '1', '1', '2', '9', '2', 2026, 4)
        """
    )
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_aumento_casos(reference_date=date(2026, 6, 10))

    assert result.mes_atual_ano == 2026
    assert result.mes_atual_mes == 5
    assert result.mes_anterior_ano == 2026
    assert result.mes_anterior_mes == 4
    assert result.casos_mes_atual == 2
    assert result.casos_mes_anterior == 1
    assert result.taxa_aumento_percentual == 100.0


def test_taxa_aumento_casos_returns_none_when_previous_month_has_zero_cases(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute("DELETE FROM srag_notificacoes WHERE ANO_NOTIFIC = 2026 AND MES_NOTIFIC = 5")
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_aumento_casos(reference_date=date(2026, 7, 15))

    assert result.casos_mes_anterior == 0
    assert result.taxa_aumento_percentual is None


def test_taxa_aumento_casos_negative_rate(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute(
        """
        INSERT INTO srag_notificacoes VALUES
        ('11', '2026-05-03', 'SP', '3', '1', '2', '9', '2', 2026, 5),
        ('12', '2026-05-04', 'SP', '4', '1', '2', '9', '2', 2026, 5),
        ('13', '2026-05-05', 'SP', '1', '1', '2', '9', '2', 2026, 5)
        """
    )
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_aumento_casos(reference_date=date(2026, 7, 15))

    assert result.casos_mes_atual == 4
    assert result.casos_mes_anterior == 5
    assert result.taxa_aumento_percentual == -20.0


def test_taxa_mortalidade_calculates_rate(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute(
        """
        UPDATE srag_notificacoes SET EVOLUCAO = '2' WHERE NU_NOTIFIC IN ('1', '2', '6')
        """
    )
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_mortalidade(reference_date=date(2026, 7, 15))

    assert result.mes_atual_ano == 2026
    assert result.mes_atual_mes == 6
    assert result.mes_anterior_ano == 2026
    assert result.mes_anterior_mes == 5
    assert result.total_casos_2_meses == 7
    assert result.total_obitos_2_meses == 3
    assert result.taxa_mortalidade_percentual == pytest.approx(42.857142857142854)


def test_taxa_mortalidade_ignores_current_incomplete_month(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute(
        """
        UPDATE srag_notificacoes SET EVOLUCAO = '2' WHERE NU_NOTIFIC IN ('8', '9')
        """
    )
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_mortalidade(reference_date=date(2026, 7, 15))

    assert result.total_obitos_2_meses == 0


def test_taxa_mortalidade_returns_none_when_no_cases_in_period(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute("DELETE FROM srag_notificacoes")
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_mortalidade(reference_date=date(2026, 7, 15))

    assert result.total_casos_2_meses == 0
    assert result.total_obitos_2_meses == 0
    assert result.taxa_mortalidade_percentual is None


def test_taxa_mortalidade_zero_deaths(metrics_service):
    result = metrics_service.taxa_mortalidade(reference_date=date(2026, 7, 15))

    assert result.total_casos_2_meses == 7
    assert result.total_obitos_2_meses == 0
    assert result.taxa_mortalidade_percentual == 0.0


def test_taxa_ocupacao_uti_calculates_rate(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute(
        """
        UPDATE srag_notificacoes SET UTI = '1' WHERE NU_NOTIFIC IN ('1', '2', '6')
        """
    )
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_ocupacao_uti(reference_date=date(2026, 7, 15))

    assert result.mes_atual_ano == 2026
    assert result.mes_atual_mes == 6
    assert result.mes_anterior_ano == 2026
    assert result.mes_anterior_mes == 5
    assert result.total_casos_2_meses == 7
    assert result.casos_com_uti_2_meses == 3
    assert result.taxa_ocupacao_uti_percentual == pytest.approx(42.857142857142854)


def test_taxa_ocupacao_uti_ignores_current_incomplete_month(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute(
        """
        UPDATE srag_notificacoes SET UTI = '1' WHERE NU_NOTIFIC IN ('8', '9')
        """
    )
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_ocupacao_uti(reference_date=date(2026, 7, 15))

    assert result.casos_com_uti_2_meses == 0


def test_taxa_ocupacao_uti_returns_none_when_no_cases_in_period(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute("DELETE FROM srag_notificacoes")
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_ocupacao_uti(reference_date=date(2026, 7, 15))

    assert result.total_casos_2_meses == 0
    assert result.casos_com_uti_2_meses == 0
    assert result.taxa_ocupacao_uti_percentual is None


def test_taxa_ocupacao_uti_zero_uti_cases(metrics_service):
    result = metrics_service.taxa_ocupacao_uti(reference_date=date(2026, 7, 15))

    assert result.total_casos_2_meses == 7
    assert result.casos_com_uti_2_meses == 0
    assert result.taxa_ocupacao_uti_percentual == 0.0


def test_taxa_vacinacao_populacao_calculates_rate(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute(
        """
        UPDATE srag_notificacoes SET VACINA_COV = '1' WHERE NU_NOTIFIC IN ('1', '2', '6')
        """
    )
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_vacinacao_populacao(reference_date=date(2026, 7, 15))

    assert result.mes_atual_ano == 2026
    assert result.mes_atual_mes == 6
    assert result.mes_anterior_ano == 2026
    assert result.mes_anterior_mes == 5
    assert result.total_casos_2_meses == 7
    assert result.casos_vacinados_2_meses == 3
    assert result.taxa_vacinacao_percentual == pytest.approx(42.857142857142854)


def test_taxa_vacinacao_populacao_ignores_current_incomplete_month(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute(
        """
        UPDATE srag_notificacoes SET VACINA_COV = '1' WHERE NU_NOTIFIC IN ('8', '9')
        """
    )
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_vacinacao_populacao(reference_date=date(2026, 7, 15))

    assert result.casos_vacinados_2_meses == 0


def test_taxa_vacinacao_populacao_returns_none_when_no_cases_in_period(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute("DELETE FROM srag_notificacoes")
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_vacinacao_populacao(reference_date=date(2026, 7, 15))

    assert result.total_casos_2_meses == 0
    assert result.casos_vacinados_2_meses == 0
    assert result.taxa_vacinacao_percentual is None


def test_taxa_vacinacao_populacao_zero_vaccinated_cases(metrics_service):
    result = metrics_service.taxa_vacinacao_populacao(reference_date=date(2026, 7, 15))

    assert result.total_casos_2_meses == 7
    assert result.casos_vacinados_2_meses == 0
    assert result.taxa_vacinacao_percentual == 0.0


def test_resolve_comparison_months_skips_missing_calendar_months(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute("DELETE FROM srag_notificacoes WHERE ANO_NOTIFIC = 2026 AND MES_NOTIFIC = 7")
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    mes_atual, mes_anterior = service._resolve_comparison_months(date(2026, 9, 15))

    assert mes_atual == (2026, 6)
    assert mes_anterior == (2026, 5)


def test_resolve_comparison_months_uses_may_when_intermediate_months_are_missing(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute(
        "DELETE FROM srag_notificacoes WHERE ANO_NOTIFIC = 2026 AND MES_NOTIFIC IN (6, 7)"
    )
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    mes_atual, mes_anterior = service._resolve_comparison_months(date(2026, 9, 15))

    assert mes_atual == (2026, 5)
    assert mes_anterior == (2026, 4)


def test_taxa_aumento_casos_skips_missing_months_when_reference_is_september(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute("DELETE FROM srag_notificacoes WHERE ANO_NOTIFIC = 2026 AND MES_NOTIFIC = 7")
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_aumento_casos(reference_date=date(2026, 9, 15))

    assert result.mes_atual_mes == 6
    assert result.mes_anterior_mes == 5
    assert result.casos_mes_atual == 4
    assert result.casos_mes_anterior == 2


def test_taxa_mortalidade_skips_missing_months_when_reference_is_september(metrics_db):
    connection = duckdb.connect(str(metrics_db))
    connection.execute("DELETE FROM srag_notificacoes WHERE ANO_NOTIFIC = 2026 AND MES_NOTIFIC = 7")
    connection.close()

    service = SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    result = service.taxa_mortalidade(reference_date=date(2026, 9, 15))

    assert result.mes_atual_mes == 6
    assert result.mes_anterior_mes == 5
    assert result.total_casos_2_meses == 7


def test_taxa_aumento_casos_for_specific_state(metrics_service):
    result = metrics_service.taxa_aumento_casos(reference_date=date(2026, 7, 15), estado="SP")

    assert result.sg_uf_not == "SP"
    assert result.casos_mes_atual == 4
    assert result.casos_mes_anterior == 2


def test_taxa_aumento_casos_for_state_without_data(metrics_service):
    result = metrics_service.taxa_aumento_casos(reference_date=date(2026, 7, 15), estado="RJ")

    assert result.sg_uf_not == "RJ"
    assert result.casos_mes_atual == 0
    assert result.casos_mes_anterior == 0
    assert result.taxa_aumento_percentual is None


def test_taxa_aumento_casos_accepts_brasil_code(metrics_service):
    result = metrics_service.taxa_aumento_casos(reference_date=date(2026, 7, 15), estado="BRASIL")

    assert result.sg_uf_not == "BRASIL"
    assert result.casos_mes_atual == 4


def test_taxa_aumento_casos_rejects_invalid_state(metrics_service):
    with pytest.raises(ValueError, match="UF inválida"):
        metrics_service.taxa_aumento_casos(reference_date=date(2026, 7, 15), estado="XX")


def test_taxa_aumento_casos_brasil_e_estados(metrics_service):
    results = metrics_service.taxa_aumento_casos_brasil_e_estados(reference_date=date(2026, 7, 15))

    assert len(results) == 28
    assert results[0].sg_uf_not == "BRASIL"
    assert {result.sg_uf_not for result in results} == {"BRASIL", *metrics_service.state_codes}
    assert results[1].sg_uf_not == "AC"


def test_taxa_mortalidade_brasil_e_estados_returns_all_scopes(metrics_service):
    results = metrics_service.taxa_mortalidade_brasil_e_estados(reference_date=date(2026, 7, 15))

    assert len(results) == 28
    assert results[0].sg_uf_not == "BRASIL"


def test_casos_ultimos_30_dias_returns_complete_series(metrics_service):
    result = metrics_service.casos_ultimos_30_dias(reference_date=date(2026, 7, 15))

    assert result.sg_uf_not == "BRASIL"
    assert result.data_inicio == date(2026, 6, 16)
    assert result.data_fim == date(2026, 7, 15)
    assert len(result.pontos) == 30

    counts = {point.data: point.total_casos for point in result.pontos}
    assert counts[date(2026, 7, 1)] == 1
    assert counts[date(2026, 7, 2)] == 1
    assert counts[date(2026, 6, 20)] == 0


def test_casos_ultimos_12_meses_returns_complete_series(metrics_service):
    result = metrics_service.casos_ultimos_12_meses(reference_date=date(2026, 7, 15))

    assert result.sg_uf_not == "BRASIL"
    assert len(result.pontos) == 12

    counts = {(point.ano, point.mes): point.total_casos for point in result.pontos}
    assert counts[(2026, 6)] == 4
    assert counts[(2026, 5)] == 2
    assert counts[(2026, 7)] == 2
    assert counts[(2025, 8)] == 0

