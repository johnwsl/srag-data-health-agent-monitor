import json
import re
import time
import uuid
from typing import Any

from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from app.config import SRAG_BRASIL_CODE, SRAG_STATE_CODES
from app.services.agent_audit_service import AgentAuditService
from app.services.agent_tools import build_srag_agent_tools
from app.services.chart_spec_service import ChartSpecService
from app.services.openai_langchain_service import OpenAILangChainService
from app.services.srag_metrics_api_service import SragMetricsApiLangChainService
from app.services.tavily_news_service import TavilyNewsLangChainService


class ReportToolInput(BaseModel):
    estado: str = Field(
        description="Sigla da UF (ex.: SP, RJ) ou BRASIL. Inferir a partir da mensagem do usuario."
    )


class LangGraphOrchestratorAgent:
    """Orquestrador unico LangGraph para chat e relatorio (tools + Tavily)."""

    SYSTEM_PROMPT = (
        "Voce e um assistente analitico de saude publica especializado em SRAG no Brasil. "
        "Use as ferramentas disponiveis para obter dados oficiais e noticias; nao invente numeros. "
        "Tools: consultar_metricas_srag, consultar_serie_temporal, gerar_especificacao_grafico, "
        "buscar_noticias_srag (Tavily) e gerar_relatorio_executivo. "
        "Identifique UF (sigla) ou BRASIL mencionados pelo usuario e use esse escopo nas tools. "
        "Nas respostas do chat que usem metricas oficiais, informe explicitamente o escopo "
        "(UF ou BRASIL) e o periodo analisado para o cálculo das metricas (ex.: 05/2026 -> 06/2026), usando os campos "
        "mes_anterior_* e mes_atual_* retornados pelas tools — nao invente o periodo. "
        "Chame gerar_relatorio_executivo SOMENTE quando o usuario pedir de forma EXPLICITA e DIRETA "
        "um relatorio/resumo executivo/painel completo (ex.: 'gere o relatorio do Brasil', "
        "'resumo executivo de SP'). "
        "NAO chame gerar_relatorio_executivo para perguntas pontuais sobre metricas, taxas, "
        "tendencias, series ou noticias — mesmo que ja exista um relatorio na conversa. "
        "Nesses casos use apenas consultar_metricas_srag, consultar_serie_temporal, "
        "gerar_especificacao_grafico e/ou buscar_noticias_srag. "
        "IMPORTANTE: NUNCA cole o texto completo do relatorio na resposta do chat. "
        "No chat, apenas confirme de forma breve que o relatorio foi gerado e sera exibido "
        "na secao 'Relatorio gerado por IA', mencionando escopo e periodo quando disponiveis. "
        "Importante sobre vies temporal: dados recentes sofrem atraso de digitacao/notificacao. "
        "Nao interprete queda abrupta no fim da serie como reducao real sem mencionar incompleteness. "
        "Se a pergunta estiver fora de SRAG/saude respiratoria no Brasil, recuse educadamente."
    )

    def __init__(
        self,
        llm_service: OpenAILangChainService | None = None,
        metrics_service: SragMetricsApiLangChainService | None = None,
        news_service: TavilyNewsLangChainService | None = None,
        chart_spec_service: ChartSpecService | None = None,
        audit_service: AgentAuditService | None = None,
        checkpointer=None,
        graph=None,
        max_chars: int = 5000,
    ) -> None:
        self.llm_service = llm_service or OpenAILangChainService()
        self.metrics_service = metrics_service or SragMetricsApiLangChainService()
        self.news_service = news_service or TavilyNewsLangChainService()
        self.chart_spec_service = chart_spec_service or ChartSpecService()
        self.audit_service = audit_service if audit_service is not None else AgentAuditService()
        self._checkpointer = checkpointer
        self._graph = graph
        self.max_chars = max_chars
        self.last_report: dict[str, Any] | None = None

    def _get_checkpointer(self):
        if self._checkpointer is None:
            self._checkpointer = MemorySaver()
        return self._checkpointer

    def _normalize_estado(self, estado: str) -> str:
        scope = (estado or SRAG_BRASIL_CODE).strip().upper()
        if scope != SRAG_BRASIL_CODE and scope not in SRAG_STATE_CODES:
            raise ValueError(f"UF invalida: {scope}. Use uma sigla valida ou BRASIL.")
        return scope

    def _compose_executive_report(self, estado: str) -> dict[str, Any]:
        scope = self._normalize_estado(estado)
        self.metrics_service.ensure_pipeline_ready()
        payload = self.metrics_service.get_full_metrics_data(scope)
        news_items = self._load_news_items()
        news_data = self._format_news_for_llm(news_items)
        charts = self.chart_spec_service.from_metrics_payload(payload)
        self.chart_spec_service.generated_charts = list(charts)

        system_prompt = (
            "Voce e um analista de saude publica. Escreva um resumo executivo em portugues, "
            "com no maximo 3500 caracteres, em tom humano e profissional, como um briefing "
            "para gestores de saude. "
            "Use secoes curtas com titulo em linha propria "
            "(Escopo e periodo, Analise dos dados oficiais, Tendencias, Observacoes), "
            "separadas por linha em branco. "
            "IMPORTANTE: escreva apenas paragrafos corridos. "
            "Nao use listas, bullets, tracos (-) nem enumeracoes (1., 2.). "
            "Nao monte tabelas e nao liste noticias — a tabela de metricas e a secao de "
            "noticias com links serao acrescentadas automaticamente depois. "
            "Integre numeros e metricas naturalmente nas frases. "
            "Cubra as 4 metricas principais e tendencias sem inventar dados. "
            "Mencione atraso de notificacao se a serie recente parecer incompleta. "
            "Use **negrito** com parcimonia, so em numeros ou termos-chave."
        )
        user_prompt = (
            f"Estado consultado: {scope}\n\n"
            "Dados oficiais da API SRAG:\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
            "Noticias recentes coletadas (apenas contexto; nao liste URLs):\n"
            f"{news_data}\n\n"
            "Escreva o resumo executivo em prosa continua, sem listas, sem tabela e sem URLs."
        )
        narrative = self._limit_text(
            self._humanize_report_text(self.llm_service.ask(user_prompt, system_prompt=system_prompt)),
            max_chars=3500,
        )
        structured = "\n\n".join(
            part
            for part in (
                self._format_metrics_table_markdown(payload),
                self._format_news_section_markdown(news_items),
            )
            if part
        )
        resumo = narrative
        if structured:
            resumo = f"{narrative}\n\n{structured}".strip()
        return {
            "estado": scope,
            "resumo_executivo": self._limit_text(resumo),
            "charts": charts,
        }

    def _load_news_items(self) -> list[dict[str, str]]:
        listar = getattr(self.news_service, "listar_noticias", None)
        if callable(listar):
            try:
                items = listar()
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
            except Exception:  # noqa: BLE001
                pass
        raw = self.news_service.buscar_noticias()
        return self._parse_news_text_fallback(str(raw or ""))

    @staticmethod
    def _format_news_for_llm(news_items: list[dict[str, str]]) -> str:
        if not news_items:
            return "Nenhuma noticia relevante sobre SRAG no Brasil foi encontrada."
        lines = ["Noticias recentes sobre SRAG no Brasil:"]
        for index, item in enumerate(news_items, start=1):
            title = str(item.get("title") or "Sem titulo").strip()
            snippet = str(item.get("snippet") or "").strip()
            lines.append(f"{index}. {title}")
            if snippet:
                lines.append(f"   Resumo: {snippet}")
        return "\n".join(lines)

    @staticmethod
    def _parse_news_text_fallback(raw: str) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        current: dict[str, str] | None = None
        for line in (raw or "").splitlines():
            stripped = line.strip()
            match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
            if match:
                if current:
                    items.append(current)
                current = {"title": match.group(2).strip(), "url": "", "snippet": ""}
                continue
            if current is None:
                continue
            if stripped.lower().startswith("resumo:"):
                current["snippet"] = stripped.split(":", 1)[1].strip()
            elif stripped.lower().startswith("url:"):
                current["url"] = stripped.split(":", 1)[1].strip()
        if current:
            items.append(current)
        return items

    @staticmethod
    def _format_percent(value: Any) -> str:
        if value is None:
            return "N/D"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "N/D"
        return f"{number:.2f}%".replace(".", ",")

    @staticmethod
    def _format_int(value: Any) -> str:
        if value is None:
            return "N/D"
        try:
            return f"{int(value):,}".replace(",", ".")
        except (TypeError, ValueError):
            return "N/D"

    @staticmethod
    def _format_month_year(ano: Any, mes: Any) -> str:
        try:
            return f"{int(mes):02d}/{int(ano)}"
        except (TypeError, ValueError):
            return "N/D"

    def _format_metrics_table_markdown(self, payload: dict[str, Any]) -> str:
        metricas = payload.get("metricas") or {}
        if not isinstance(metricas, dict) or not metricas:
            return ""

        aumento = metricas.get("taxa_aumento_casos") or {}
        mortalidade = metricas.get("taxa_mortalidade") or {}
        uti = metricas.get("taxa_ocupacao_uti") or {}
        vacina = metricas.get("taxa_vacinacao_populacao") or {}

        if not isinstance(aumento, dict):
            aumento = {}
        if not isinstance(mortalidade, dict):
            mortalidade = {}
        if not isinstance(uti, dict):
            uti = {}
        if not isinstance(vacina, dict):
            vacina = {}

        periodo_aumento = (
            f"{self._format_month_year(aumento.get('mes_anterior_ano'), aumento.get('mes_anterior_mes'))}"
            f" → {self._format_month_year(aumento.get('mes_atual_ano'), aumento.get('mes_atual_mes'))}"
        )
        detalhe_aumento = (
            f"{periodo_aumento}; "
            f"{self._format_int(aumento.get('casos_mes_anterior'))} → "
            f"{self._format_int(aumento.get('casos_mes_atual'))} casos"
        )
        periodo_2m = (
            f"{self._format_month_year(mortalidade.get('mes_anterior_ano'), mortalidade.get('mes_anterior_mes'))}"
            f" → {self._format_month_year(mortalidade.get('mes_atual_ano'), mortalidade.get('mes_atual_mes'))}"
        )

        rows = [
            (
                "Taxa de aumento de casos",
                self._format_percent(aumento.get("taxa_aumento_percentual")),
                detalhe_aumento,
            ),
            (
                "Taxa de mortalidade",
                self._format_percent(mortalidade.get("taxa_mortalidade_percentual")),
                (
                    f"{periodo_2m}; "
                    f"{self._format_int(mortalidade.get('total_obitos_2_meses'))} óbitos / "
                    f"{self._format_int(mortalidade.get('total_casos_2_meses'))} casos"
                ),
            ),
            (
                "Taxa de ocupação de UTI",
                self._format_percent(uti.get("taxa_ocupacao_uti_percentual")),
                (
                    f"{self._format_int(uti.get('casos_com_uti_2_meses'))} internados em UTI / "
                    f"{self._format_int(uti.get('total_casos_2_meses'))} casos"
                ),
            ),
            (
                "Taxa de vacinação COVID",
                self._format_percent(vacina.get("taxa_vacinacao_percentual")),
                (
                    f"{self._format_int(vacina.get('casos_vacinados_2_meses'))} vacinados / "
                    f"{self._format_int(vacina.get('total_casos_2_meses'))} casos"
                ),
            ),
        ]

        lines = [
            "## Quatro métricas principais",
            "",
            "| Métrica | Valor | Detalhe |",
            "| --- | --- | --- |",
        ]
        for metric, value, detail in rows:
            lines.append(f"| {metric} | {value} | {detail} |")
        return "\n".join(lines)

    @staticmethod
    def _format_news_section_markdown(news_items: list[dict[str, str]]) -> str:
        lines = ["## Notícias encontradas", ""]
        if not news_items:
            lines.append("Nenhuma notícia relevante sobre SRAG no Brasil foi encontrada.")
            return "\n".join(lines)

        for index, item in enumerate(news_items, start=1):
            title = str(item.get("title") or "Sem título").strip() or "Sem título"
            url = str(item.get("url") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if url:
                lines.append(f"{index}. [{title}]({url})")
            else:
                lines.append(f"{index}. {title}")
            if snippet:
                lines.append(f"   {snippet}")
            if url:
                lines.append(f"   Link: {url}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _report_tool(self):
        def gerar_relatorio_executivo(estado: str) -> str:
            try:
                composed = self._compose_executive_report(estado)
            except ValueError as error:
                return str(error)
            except Exception as error:  # noqa: BLE001
                return f"Erro ao gerar relatorio executivo: {error}"

            self.last_report = {
                "estado": composed["estado"],
                "resumo_executivo": composed["resumo_executivo"],
                "charts": composed["charts"],
            }
            return (
                f"Relatorio executivo para {composed['estado']} gerado com sucesso. "
                "NAO cole o texto completo na resposta do chat. "
                "Confirme apenas que o relatorio esta disponivel na secao "
                "'Relatorio gerado por IA'."
            )

        return StructuredTool.from_function(
            func=gerar_relatorio_executivo,
            name="gerar_relatorio_executivo",
            description=(
                "Gera o relatorio executivo completo de SRAG para uma UF ou BRASIL. "
                "Use APENAS quando o usuario pedir explicitamente um relatorio/resumo executivo/"
                "painel completo. Nao use para perguntas pontuais de metricas ou noticias. "
                "O texto completo sera exibido na secao Relatorio gerado por IA do dashboard; "
                "nao deve ser colado no chat."
            ),
            args_schema=ReportToolInput,
        )

    def _build_graph(self):
        tools = [
            *build_srag_agent_tools(
                self.metrics_service,
                self.news_service,
                self.chart_spec_service,
            ),
            self._report_tool(),
        ]
        return create_react_agent(
            self.llm_service.get_model(),
            tools,
            prompt=self.SYSTEM_PROMPT,
            checkpointer=self._get_checkpointer(),
        )

    def _get_graph(self):
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    @staticmethod
    def _new_session_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part)
        return str(content)

    @staticmethod
    def _messages_for_current_turn(messages: list[Any]) -> list[Any]:
        """Retorna so as mensagens apos o ultimo turno humano (evita tools de historico)."""
        last_human_idx = -1
        for idx, message in enumerate(messages):
            message_type = getattr(message, "type", None)
            if message_type == "human":
                last_human_idx = idx
                continue
            if isinstance(message, dict) and message.get("role") in {"user", "human"}:
                last_human_idx = idx
        if last_human_idx < 0:
            return messages
        return messages[last_human_idx + 1 :]

    @staticmethod
    def _extract_tools_used(messages: list[Any]) -> list[str]:
        used: list[str] = []
        for message in LangGraphOrchestratorAgent._messages_for_current_turn(messages):
            tool_calls = getattr(message, "tool_calls", None) or []
            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    name = tool_call.get("name")
                else:
                    name = getattr(tool_call, "name", None)
                if name:
                    used.append(str(name))

        seen: set[str] = set()
        ordered: list[str] = []
        for name in used:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    @staticmethod
    def _extract_tool_events(messages: list[Any]) -> list[dict[str, Any]]:
        """Extrai nome/args/resultado das tools apenas do turno atual."""
        pending: dict[str, dict[str, Any]] = {}
        events: list[dict[str, Any]] = []

        for message in LangGraphOrchestratorAgent._messages_for_current_turn(messages):
            tool_calls = getattr(message, "tool_calls", None) or []
            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    call_id = str(tool_call.get("id") or "")
                    name = str(tool_call.get("name") or "unknown")
                    args = tool_call.get("args") or {}
                else:
                    call_id = str(getattr(tool_call, "id", "") or "")
                    name = str(getattr(tool_call, "name", None) or "unknown")
                    args = getattr(tool_call, "args", {}) or {}

                payload = {"name": name, "args": args, "result": None}
                if call_id:
                    pending[call_id] = payload
                else:
                    events.append(payload)

            if getattr(message, "type", None) == "tool":
                call_id = str(getattr(message, "tool_call_id", "") or "")
                result_text = LangGraphOrchestratorAgent._extract_text(
                    getattr(message, "content", "")
                )
                base = pending.pop(call_id, None) if call_id else None
                events.append(
                    {
                        "name": (base or {}).get("name")
                        or str(getattr(message, "name", None) or "unknown"),
                        "args": (base or {}).get("args") or {},
                        "result": result_text,
                    }
                )

        events.extend(pending.values())
        return events

    def _humanize_report_text(self, text: str) -> str:
        """Converte blocos em lista em paragrafos corridos, mais naturais para leitura."""
        compact = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not compact:
            return ""

        bullet_re = re.compile(r"^([-*•]|\d+\.)\s+")
        blocks = re.split(r"\n{2,}", compact)
        rendered: list[str] = []

        for block in blocks:
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if not lines:
                continue

            # Preserva tabelas markdown e secoes ja estruturadas com links.
            if any(line.startswith("|") for line in lines) or any("](" in line for line in lines):
                rendered.append("\n".join(lines))
                continue

            bullet_lines = [line for line in lines if bullet_re.match(line)]
            if len(bullet_lines) >= 2:
                heading_parts: list[str] = []
                items: list[str] = []
                for line in lines:
                    if bullet_re.match(line):
                        item = bullet_re.sub("", line).strip().rstrip(";")
                        if item:
                            items.append(item)
                    elif not items:
                        heading = re.sub(r"^#{1,6}\s*", "", line)
                        if heading.startswith("**") and heading.endswith("**") and heading.count("**") == 2:
                            heading = heading[2:-2].strip()
                        heading_parts.append(heading.rstrip(":"))
                    else:
                        items.append(line)

                sentences: list[str] = []
                for item in items:
                    sentence = item.strip()
                    if not sentence:
                        continue
                    if not sentence.endswith((".", "!", "?")):
                        sentence = f"{sentence}."
                    sentence = sentence[0].upper() + sentence[1:]
                    sentences.append(sentence)

                if heading_parts:
                    rendered.append(" ".join(heading_parts).strip())
                if sentences:
                    rendered.append(" ".join(sentences))
                continue

            cleaned_lines: list[str] = []
            for line in lines:
                if bullet_re.match(line):
                    item = bullet_re.sub("", line).strip()
                    if item and not item.endswith((".", "!", "?")):
                        item = f"{item}."
                    cleaned_lines.append(item)
                else:
                    cleaned_lines.append(line)
            rendered.append("\n".join(cleaned_lines))

        return "\n\n".join(rendered)

    def _limit_text(self, text: str, max_chars: int | None = None) -> str:
        limit = self.max_chars if max_chars is None else max_chars
        compact = text.strip()
        if len(compact) <= limit:
            return compact

        truncated = compact[: limit - 3].rstrip()
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        return f"{truncated}..."

    def _extract_reply(self, messages: list[Any]) -> str:
        reply = ""
        for message_item in reversed(messages):
            message_type = getattr(message_item, "type", None)
            if message_type == "ai" and not (getattr(message_item, "tool_calls", None) or []):
                reply = self._extract_text(getattr(message_item, "content", ""))
                break
            if message_type == "ai" and not reply:
                reply = self._extract_text(getattr(message_item, "content", ""))
        return reply.strip() or "Nao foi possivel gerar uma resposta nesta rodada."

    def _record_audit(self, **kwargs: Any) -> str | None:
        try:
            return self.audit_service.record(**kwargs)
        except Exception:  # noqa: BLE001
            return None

    def _invoke(
        self,
        *,
        human_content: str,
        thread_id: str,
        estado: str,
    ) -> dict[str, Any]:
        pipeline_status = self.metrics_service.ensure_pipeline_ready()
        self.chart_spec_service.reset_generated_charts()

        content = (
            f"[Contexto geografico inicial: {estado}]\n"
            f"[Status da pipeline: {pipeline_status}]\n"
            "Identifique UF ou BRASIL na mensagem do usuario quando relevante.\n\n"
            f"{human_content}"
        )

        started = time.perf_counter()
        result = self._get_graph().invoke(
            {"messages": [{"role": "user", "content": content}]},
            config={"configurable": {"thread_id": thread_id}},
        )
        duration_ms = (time.perf_counter() - started) * 1000
        messages = list(result.get("messages") or [])

        return {
            "session_id": thread_id,
            "estado_contexto": estado,
            "reply": self._extract_reply(messages),
            "charts": list(self.chart_spec_service.generated_charts),
            "tools_used": self._extract_tools_used(messages),
            "tool_events": self._extract_tool_events(messages),
            "duration_ms": duration_ms,
            "user_message": human_content,
        }

    def chat(
        self,
        message: str,
        *,
        session_id: str | None = None,
        estado_contexto: str = "BRASIL",
    ) -> dict[str, Any]:
        texto = (message or "").strip()
        if not texto:
            raise ValueError("A mensagem do chat nao pode ser vazia.")

        estado = (estado_contexto or SRAG_BRASIL_CODE).strip().upper()
        thread_id = (session_id or "").strip() or self._new_session_id()
        self.last_report = None

        try:
            result = self._invoke(human_content=texto, thread_id=thread_id, estado=estado)
            report = self.last_report
            if report is not None:
                result["estado_contexto"] = report["estado"]
                # Graficos do relatorio ficam apenas em result["report"], nao no chat.
                result["charts"] = []

            result["report"] = report
            charts_count = len((report or {}).get("charts") or result.get("charts") or [])
            audit_id = self._record_audit(
                kind="chat",
                session_id=result["session_id"],
                estado_contexto=result["estado_contexto"],
                user_message=texto,
                reply=result["reply"],
                tools_used=result.get("tools_used") or [],
                tool_events=result.get("tool_events") or [],
                report_generated=report is not None,
                charts_count=charts_count,
                duration_ms=float(result.get("duration_ms") or 0.0),
                status="ok",
            )
            result["audit_id"] = audit_id
            return result
        except Exception as error:
            self._record_audit(
                kind="chat",
                session_id=thread_id,
                estado_contexto=estado,
                user_message=texto,
                reply="",
                tools_used=[],
                tool_events=[],
                report_generated=False,
                charts_count=0,
                duration_ms=0.0,
                status="error",
                error_message=str(error),
            )
            raise

    def generate_executive_summary(self, estado: str) -> dict[str, Any]:
        started = time.perf_counter()
        scope = self._normalize_estado(estado)
        session_id = f"report-{scope}-{self._new_session_id()}"
        user_message = f"Gerar relatorio executivo para {scope}"

        try:
            composed = self._compose_executive_report(scope)
            duration_ms = (time.perf_counter() - started) * 1000
            tools_used = ["gerar_relatorio_executivo"]
            tool_events = [
                {
                    "name": "gerar_relatorio_executivo",
                    "args": {"estado": scope},
                    "result": f"resumo_chars={len(composed['resumo_executivo'])}; charts={len(composed['charts'])}",
                }
            ]
            audit_id = self._record_audit(
                kind="report",
                session_id=session_id,
                estado_contexto=composed["estado"],
                user_message=user_message,
                reply=composed["resumo_executivo"],
                tools_used=tools_used,
                tool_events=tool_events,
                report_generated=True,
                charts_count=len(composed["charts"]),
                duration_ms=duration_ms,
                status="ok",
            )
            return {
                "resumo_executivo": composed["resumo_executivo"],
                "charts": composed["charts"],
                "tools_used": tools_used,
                "session_id": session_id,
                "audit_id": audit_id,
            }
        except Exception as error:
            self._record_audit(
                kind="report",
                session_id=session_id,
                estado_contexto=scope,
                user_message=user_message,
                reply="",
                tools_used=[],
                tool_events=[],
                report_generated=False,
                charts_count=0,
                duration_ms=(time.perf_counter() - started) * 1000,
                status="error",
                error_message=str(error),
            )
            raise
