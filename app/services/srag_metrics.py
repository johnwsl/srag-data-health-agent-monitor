from datetime import date, timedelta
from pathlib import Path

import duckdb

from app.config import (
    DUCKDB_PATH,
    ETL_TABLE_NAME,
    SRAG_BRASIL_CODE,
    SRAG_EVOLUCAO_OBITO,
    SRAG_STATE_CODES,
    SRAG_UTI_INTERNADO,
    SRAG_VACINA_COV_VACINADO,
    SRAG_VALID_CLASSI_FIN,
)
from app.models.metrics import (
    CaseIncreaseRateMetric,
    CovidVaccinationRateMetric,
    DailyCasePoint,
    DailyCasesSeriesResponse,
    MonthlyCasePoint,
    MonthlyCasesSeriesResponse,
    MortalityRateMetric,
    UtiOccupancyRateMetric,
)


class SRAGMetrics:
    def __init__(
        self,
        duckdb_path: Path = DUCKDB_PATH,
        table_name: str = ETL_TABLE_NAME,
        valid_classi_fin: tuple[int, ...] = SRAG_VALID_CLASSI_FIN,
        evolucao_obito: int = SRAG_EVOLUCAO_OBITO,
        uti_internado: int = SRAG_UTI_INTERNADO,
        vacina_cov_vacinado: int = SRAG_VACINA_COV_VACINADO,
        state_codes: tuple[str, ...] = SRAG_STATE_CODES,
        brasil_code: str = SRAG_BRASIL_CODE,
    ):
        self.duckdb_path = duckdb_path
        self.table_name = table_name
        self.valid_classi_fin = valid_classi_fin
        self.evolucao_obito = evolucao_obito
        self.uti_internado = uti_internado
        self.vacina_cov_vacinado = vacina_cov_vacinado
        self.state_codes = state_codes
        self.brasil_code = brasil_code

    @staticmethod
    def _subtract_months(year: int, month: int, months: int) -> tuple[int, int]:
        month -= months
        while month <= 0:
            month += 12
            year -= 1
        return year, month

    def _normalize_estado(self, estado: str | None) -> str | None:
        if estado is None or estado.upper() == self.brasil_code:
            return None
        estado = estado.upper()
        if estado not in self.state_codes:
            raise ValueError(f"UF inválida: {estado}. Use uma sigla válida ou {self.brasil_code}.")
        return estado

    def _metric_scope(self, estado: str | None) -> str:
        return self.brasil_code if estado is None else estado

    def _state_filter_clause(self, estado: str | None) -> tuple[str, list[str]]:
        if estado is None:
            return "", []
        return "AND SG_UF_NOT = ?", [estado]

    def _load_available_months_before(
        self,
        reference_date: date,
        estado: str | None = None,
    ) -> set[tuple[int, int]]:
        state_clause, state_parameters = self._state_filter_clause(estado)
        query = f"""
            SELECT DISTINCT ANO_NOTIFIC, MES_NOTIFIC
            FROM "{self.table_name}"
            WHERE ANO_NOTIFIC IS NOT NULL
              AND MES_NOTIFIC IS NOT NULL
              AND (
                  ANO_NOTIFIC < ?
                  OR (ANO_NOTIFIC = ? AND MES_NOTIFIC < ?)
              )
              {state_clause}
        """
        parameters = [
            reference_date.year,
            reference_date.year,
            reference_date.month,
            *state_parameters,
        ]

        connection = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            rows = connection.execute(query, parameters).fetchall()
        finally:
            connection.close()

        return {(int(year), int(month)) for year, month in rows}

    def _find_latest_available_month(
        self,
        start_year: int,
        start_month: int,
        available_months: set[tuple[int, int]],
        max_steps: int = 1200,
    ) -> tuple[int, int]:
        year, month = start_year, start_month
        for _ in range(max_steps):
            if (year, month) in available_months:
                return year, month
            year, month = self._subtract_months(year, month, 1)
        return start_year, start_month

    def _resolve_comparison_months(
        self,
        reference_date: date,
        estado: str | None = None,
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        available_months = self._load_available_months_before(reference_date, estado)

        calendar_mes_atual = self._subtract_months(reference_date.year, reference_date.month, 1)
        mes_atual = self._find_latest_available_month(
            calendar_mes_atual[0],
            calendar_mes_atual[1],
            available_months,
        )

        calendar_mes_anterior = self._subtract_months(mes_atual[0], mes_atual[1], 1)
        mes_anterior = self._find_latest_available_month(
            calendar_mes_anterior[0],
            calendar_mes_anterior[1],
            available_months,
        )

        return mes_atual, mes_anterior

    def _count_cases_by_month(self, year: int, month: int, estado: str | None = None) -> int:
        classi_fin_placeholders = ", ".join("?" for _ in self.valid_classi_fin)
        state_clause, state_parameters = self._state_filter_clause(estado)
        query = f"""
            SELECT COUNT(*)
            FROM "{self.table_name}"
            WHERE ANO_NOTIFIC = ?
              AND MES_NOTIFIC = ?
              AND TRY_CAST(CLASSI_FIN AS INTEGER) IN ({classi_fin_placeholders})
              {state_clause}
        """
        parameters = [year, month, *self.valid_classi_fin, *state_parameters]

        connection = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            result = connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

        return int(result[0]) if result else 0

    def _count_period_stats(
        self,
        mes_atual: tuple[int, int],
        mes_anterior: tuple[int, int],
        estado: str | None = None,
    ) -> tuple[int, int]:
        state_clause, state_parameters = self._state_filter_clause(estado)
        query = f"""
            SELECT
                COUNT(*) AS total_casos,
                COUNT(*) FILTER (
                    WHERE TRY_CAST(EVOLUCAO AS INTEGER) = ?
                ) AS total_obitos
            FROM "{self.table_name}"
            WHERE (
                (ANO_NOTIFIC = ? AND MES_NOTIFIC = ?)
                OR (ANO_NOTIFIC = ? AND MES_NOTIFIC = ?)
            )
            {state_clause}
        """
        parameters = [
            self.evolucao_obito,
            mes_atual[0],
            mes_atual[1],
            mes_anterior[0],
            mes_anterior[1],
            *state_parameters,
        ]

        connection = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            result = connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

        if not result:
            return 0, 0

        return int(result[0]), int(result[1])

    def _count_period_uti_stats(
        self,
        mes_atual: tuple[int, int],
        mes_anterior: tuple[int, int],
        estado: str | None = None,
    ) -> tuple[int, int]:
        state_clause, state_parameters = self._state_filter_clause(estado)
        query = f"""
            SELECT
                COUNT(*) AS total_casos,
                COUNT(*) FILTER (
                    WHERE TRY_CAST(UTI AS INTEGER) = ?
                ) AS casos_com_uti
            FROM "{self.table_name}"
            WHERE (
                (ANO_NOTIFIC = ? AND MES_NOTIFIC = ?)
                OR (ANO_NOTIFIC = ? AND MES_NOTIFIC = ?)
            )
            {state_clause}
        """
        parameters = [
            self.uti_internado,
            mes_atual[0],
            mes_atual[1],
            mes_anterior[0],
            mes_anterior[1],
            *state_parameters,
        ]

        connection = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            result = connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

        if not result:
            return 0, 0

        return int(result[0]), int(result[1])

    def _count_period_vaccination_stats(
        self,
        mes_atual: tuple[int, int],
        mes_anterior: tuple[int, int],
        estado: str | None = None,
    ) -> tuple[int, int]:
        state_clause, state_parameters = self._state_filter_clause(estado)
        query = f"""
            SELECT
                COUNT(*) AS total_casos,
                COUNT(*) FILTER (
                    WHERE TRY_CAST(VACINA_COV AS INTEGER) = ?
                ) AS casos_vacinados
            FROM "{self.table_name}"
            WHERE (
                (ANO_NOTIFIC = ? AND MES_NOTIFIC = ?)
                OR (ANO_NOTIFIC = ? AND MES_NOTIFIC = ?)
            )
            {state_clause}
        """
        parameters = [
            self.vacina_cov_vacinado,
            mes_atual[0],
            mes_atual[1],
            mes_anterior[0],
            mes_anterior[1],
            *state_parameters,
        ]

        connection = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            result = connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

        if not result:
            return 0, 0

        return int(result[0]), int(result[1])

    def _all_scopes(self) -> list[str | None]:
        return [None, *self.state_codes]

    def _classi_fin_filter_sql(self) -> str:
        placeholders = ", ".join("?" for _ in self.valid_classi_fin)
        return f"TRY_CAST(CLASSI_FIN AS INTEGER) IN ({placeholders})"

    def _last_n_months(
        self,
        reference: date,
        months: int,
    ) -> list[tuple[int, int]]:
        year, month = reference.year, reference.month
        result: list[tuple[int, int]] = []
        for _ in range(months):
            result.append((year, month))
            year, month = self._subtract_months(year, month, 1)
        result.reverse()
        return result

    def _last_n_days(self, reference: date, days: int) -> list[date]:
        start = reference - timedelta(days=days - 1)
        return [start + timedelta(days=offset) for offset in range(days)]

    def casos_ultimos_30_dias(
        self,
        reference_date: date | None = None,
        estado: str | None = None,
    ) -> DailyCasesSeriesResponse:
        reference = reference_date or date.today()
        estado_filter = self._normalize_estado(estado)
        data_inicio = reference - timedelta(days=29)
        state_clause, state_parameters = self._state_filter_clause(estado_filter)
        query = f"""
            SELECT
                CAST(DT_NOTIFIC AS DATE) AS data_notific,
                COUNT(*) AS total_casos
            FROM "{self.table_name}"
            WHERE CAST(DT_NOTIFIC AS DATE) >= ?
              AND CAST(DT_NOTIFIC AS DATE) <= ?
              AND {self._classi_fin_filter_sql()}
              {state_clause}
            GROUP BY 1
            ORDER BY 1
        """
        parameters = [
            data_inicio,
            reference,
            *self.valid_classi_fin,
            *state_parameters,
        ]

        connection = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            rows = connection.execute(query, parameters).fetchall()
        finally:
            connection.close()

        counts = {row[0]: int(row[1]) for row in rows}
        pontos = [
            DailyCasePoint(data=day, total_casos=counts.get(day, 0))
            for day in self._last_n_days(reference, 30)
        ]

        return DailyCasesSeriesResponse(
            sg_uf_not=self._metric_scope(estado_filter),
            data_inicio=data_inicio,
            data_fim=reference,
            pontos=pontos,
        )

    def casos_ultimos_12_meses(
        self,
        reference_date: date | None = None,
        estado: str | None = None,
    ) -> MonthlyCasesSeriesResponse:
        reference = reference_date or date.today()
        estado_filter = self._normalize_estado(estado)
        months = self._last_n_months(reference, 12)
        state_clause, state_parameters = self._state_filter_clause(estado_filter)
        month_filters = " OR ".join("(ANO_NOTIFIC = ? AND MES_NOTIFIC = ?)" for _ in months)
        query = f"""
            SELECT
                ANO_NOTIFIC,
                MES_NOTIFIC,
                COUNT(*) AS total_casos
            FROM "{self.table_name}"
            WHERE ({month_filters})
              AND {self._classi_fin_filter_sql()}
              {state_clause}
            GROUP BY ANO_NOTIFIC, MES_NOTIFIC
            ORDER BY ANO_NOTIFIC, MES_NOTIFIC
        """
        parameters: list[object] = []
        for year, month in months:
            parameters.extend([year, month])
        parameters.extend(self.valid_classi_fin)
        parameters.extend(state_parameters)

        connection = duckdb.connect(str(self.duckdb_path), read_only=True)
        try:
            rows = connection.execute(query, parameters).fetchall()
        finally:
            connection.close()

        counts = {(int(year), int(month)): int(total) for year, month, total in rows}
        pontos = [
            MonthlyCasePoint(
                ano=year,
                mes=month,
                total_casos=counts.get((year, month), 0),
            )
            for year, month in months
        ]

        return MonthlyCasesSeriesResponse(
            sg_uf_not=self._metric_scope(estado_filter),
            pontos=pontos,
        )

    def taxa_aumento_casos(
        self,
        reference_date: date | None = None,
        estado: str | None = None,
    ) -> CaseIncreaseRateMetric:
        """Calcula a taxa de aumento de casos entre os dois últimos meses completos.

        Use estado=None ou BRASIL para todo o Brasil, ou uma UF (ex.: SP).
        """
        reference = reference_date or date.today()
        estado_filter = self._normalize_estado(estado)
        (mes_atual_ano, mes_atual_mes), (mes_anterior_ano, mes_anterior_mes) = (
            self._resolve_comparison_months(reference, estado_filter)
        )

        casos_mes_atual = self._count_cases_by_month(mes_atual_ano, mes_atual_mes, estado_filter)
        casos_mes_anterior = self._count_cases_by_month(
            mes_anterior_ano,
            mes_anterior_mes,
            estado_filter,
        )

        if casos_mes_anterior == 0:
            taxa_aumento_percentual = None
        else:
            taxa_aumento_percentual = (
                (casos_mes_atual - casos_mes_anterior) / casos_mes_anterior
            ) * 100

        return CaseIncreaseRateMetric(
            sg_uf_not=self._metric_scope(estado_filter),
            mes_atual_ano=mes_atual_ano,
            mes_atual_mes=mes_atual_mes,
            mes_anterior_ano=mes_anterior_ano,
            mes_anterior_mes=mes_anterior_mes,
            casos_mes_atual=casos_mes_atual,
            casos_mes_anterior=casos_mes_anterior,
            taxa_aumento_percentual=taxa_aumento_percentual,
        )

    def taxa_aumento_casos_brasil_e_estados(
        self,
        reference_date: date | None = None,
    ) -> list[CaseIncreaseRateMetric]:
        return [self.taxa_aumento_casos(reference_date, estado=scope) for scope in self._all_scopes()]

    def taxa_mortalidade(
        self,
        reference_date: date | None = None,
        estado: str | None = None,
    ) -> MortalityRateMetric:
        """Calcula a taxa de mortalidade nos dois últimos meses completos.

        Use estado=None ou BRASIL para todo o Brasil, ou uma UF (ex.: SP).
        """
        reference = reference_date or date.today()
        estado_filter = self._normalize_estado(estado)
        (mes_atual_ano, mes_atual_mes), (mes_anterior_ano, mes_anterior_mes) = (
            self._resolve_comparison_months(reference, estado_filter)
        )

        total_casos_2_meses, total_obitos_2_meses = self._count_period_stats(
            (mes_atual_ano, mes_atual_mes),
            (mes_anterior_ano, mes_anterior_mes),
            estado_filter,
        )

        if total_casos_2_meses == 0:
            taxa_mortalidade_percentual = None
        else:
            taxa_mortalidade_percentual = (total_obitos_2_meses / total_casos_2_meses) * 100

        return MortalityRateMetric(
            sg_uf_not=self._metric_scope(estado_filter),
            mes_atual_ano=mes_atual_ano,
            mes_atual_mes=mes_atual_mes,
            mes_anterior_ano=mes_anterior_ano,
            mes_anterior_mes=mes_anterior_mes,
            total_casos_2_meses=total_casos_2_meses,
            total_obitos_2_meses=total_obitos_2_meses,
            taxa_mortalidade_percentual=taxa_mortalidade_percentual,
        )

    def taxa_mortalidade_brasil_e_estados(
        self,
        reference_date: date | None = None,
    ) -> list[MortalityRateMetric]:
        return [self.taxa_mortalidade(reference_date, estado=scope) for scope in self._all_scopes()]

    def taxa_ocupacao_uti(
        self,
        reference_date: date | None = None,
        estado: str | None = None,
    ) -> UtiOccupancyRateMetric:
        """Calcula a taxa de ocupação de UTI nos dois últimos meses completos.

        Use estado=None ou BRASIL para todo o Brasil, ou uma UF (ex.: SP).
        """
        reference = reference_date or date.today()
        estado_filter = self._normalize_estado(estado)
        (mes_atual_ano, mes_atual_mes), (mes_anterior_ano, mes_anterior_mes) = (
            self._resolve_comparison_months(reference, estado_filter)
        )

        total_casos_2_meses, casos_com_uti_2_meses = self._count_period_uti_stats(
            (mes_atual_ano, mes_atual_mes),
            (mes_anterior_ano, mes_anterior_mes),
            estado_filter,
        )

        if total_casos_2_meses == 0:
            taxa_ocupacao_uti_percentual = None
        else:
            taxa_ocupacao_uti_percentual = (casos_com_uti_2_meses / total_casos_2_meses) * 100

        return UtiOccupancyRateMetric(
            sg_uf_not=self._metric_scope(estado_filter),
            mes_atual_ano=mes_atual_ano,
            mes_atual_mes=mes_atual_mes,
            mes_anterior_ano=mes_anterior_ano,
            mes_anterior_mes=mes_anterior_mes,
            total_casos_2_meses=total_casos_2_meses,
            casos_com_uti_2_meses=casos_com_uti_2_meses,
            taxa_ocupacao_uti_percentual=taxa_ocupacao_uti_percentual,
        )

    def taxa_ocupacao_uti_brasil_e_estados(
        self,
        reference_date: date | None = None,
    ) -> list[UtiOccupancyRateMetric]:
        return [self.taxa_ocupacao_uti(reference_date, estado=scope) for scope in self._all_scopes()]

    def taxa_vacinacao_populacao(
        self,
        reference_date: date | None = None,
        estado: str | None = None,
    ) -> CovidVaccinationRateMetric:
        """Calcula a taxa de vacinação da população nos dois últimos meses completos.

        Use estado=None ou BRASIL para todo o Brasil, ou uma UF (ex.: SP).
        """
        reference = reference_date or date.today()
        estado_filter = self._normalize_estado(estado)
        (mes_atual_ano, mes_atual_mes), (mes_anterior_ano, mes_anterior_mes) = (
            self._resolve_comparison_months(reference, estado_filter)
        )

        total_casos_2_meses, casos_vacinados_2_meses = self._count_period_vaccination_stats(
            (mes_atual_ano, mes_atual_mes),
            (mes_anterior_ano, mes_anterior_mes),
            estado_filter,
        )

        if total_casos_2_meses == 0:
            taxa_vacinacao_percentual = None
        else:
            taxa_vacinacao_percentual = (casos_vacinados_2_meses / total_casos_2_meses) * 100

        return CovidVaccinationRateMetric(
            sg_uf_not=self._metric_scope(estado_filter),
            mes_atual_ano=mes_atual_ano,
            mes_atual_mes=mes_atual_mes,
            mes_anterior_ano=mes_anterior_ano,
            mes_anterior_mes=mes_anterior_mes,
            total_casos_2_meses=total_casos_2_meses,
            casos_vacinados_2_meses=casos_vacinados_2_meses,
            taxa_vacinacao_percentual=taxa_vacinacao_percentual,
        )

    def taxa_vacinacao_populacao_brasil_e_estados(
        self,
        reference_date: date | None = None,
    ) -> list[CovidVaccinationRateMetric]:
        return [
            self.taxa_vacinacao_populacao(reference_date, estado=scope) for scope in self._all_scopes()
        ]
