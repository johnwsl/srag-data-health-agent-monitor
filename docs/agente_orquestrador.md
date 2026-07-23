# Agente Orquestrador SRAG

## Objetivo

O agente orquestrador gera um **resumo executivo** sobre a situação de SRAG para uma UF ou para `BRASIL`, combinando:

- **dados oficiais** da API SRAG (métricas e séries temporais)
- **notícias recentes** buscadas via Tavily Search
- **síntese textual** produzida por um modelo da OpenAI via LangChain

O resultado é exposto pela API em `POST /agents/report` e, no dashboard (**[http://localhost:8080](http://localhost:8080)**), é gerado pelo **chatbot** via tool `gerar_relatorio_executivo`. O texto completo do relatório **não** aparece no chat — só na seção **Relatório gerado por IA** (`ChatResponse.report`).

---

## Arquitetura

O fluxo segue o padrão MVC já adotado no projeto:

| Camada | Arquivo | Responsabilidade |
|--------|---------|------------------|
| Rota | `app/views/agent_routes.py` | Expõe `POST /agents/report` e `POST /agents/chat` |
| Controller | `app/controllers/agent_controller.py` | Valida entrada e trata erros HTTP |
| Orquestrador | `app/services/langgraph_orchestrator_agent.py` | Orquestrador unico LangGraph (relatorio + chat + Tavily) |
| Facades | `srag_report_agent.py`, `srag_chat_agent.py` | Atalhos de compatibilidade do mesmo orquestrador |
| Modelos | `app/models/agent.py`, `app/models/chat.py` | Request/response de relatorio e chat |
| ChartSpec | `app/models/chart.py` + `app/services/chart_spec_service.py` | Contrato e montagem dos gráficos oficiais |

### Services envolvidos

| Classe | Arquivo | Responsabilidade |
|--------|---------|------------------|
| `LangGraphOrchestratorAgent` | `app/services/langgraph_orchestrator_agent.py` | Orquestrador unico (`create_react_agent` + MemorySaver) |
| `OpenAILangChainService` | `app/services/openai_langchain_service.py` | Chat model OpenAI via LangChain (`ChatOpenAI`) |
| `SragMetricsApiLangChainService` | `app/services/srag_metrics_api_service.py` | Cliente HTTP da API SRAG como tools |
| `ChartSpecService` | `app/services/chart_spec_service.py` | Monta ChartSpec / tool `gerar_especificacao_grafico` |
| `TavilyNewsLangChainService` | `app/services/tavily_news_service.py` | Tool `buscar_noticias_srag` (Tavily) |

---

## Fluxo de execução

### Relatório direto (`POST /agents/report`)

Quando `POST /agents/report` é chamado com `{"estado": "SP"}`:

1. `ensure_pipeline_ready()` (status + pipeline se necessário)
2. carrega métricas oficiais + notícias (Tavily)
3. monta ChartSpec a partir das séries
4. LLM sintetiza o resumo (até **4000** caracteres)
5. retorna `resumo_executivo` + `charts`

### Relatório via chatbot (`POST /agents/chat`)

No dashboard não há filtro de UF nem botão “Gerar Relatório por IA”. O usuário pede o relatório no chat (ex.: “Gere o relatório de SP”). O orquestrador LangGraph:

1. identifica UF ou `BRASIL` na mensagem
2. chama a tool `gerar_relatorio_executivo`
3. responde no chat só com confirmação breve
4. devolve o texto completo em `report` para a seção **Relatório gerado por IA**

Tools do chat: `consultar_metricas_srag`, `consultar_serie_temporal`, `gerar_especificacao_grafico`, `buscar_noticias_srag`, `gerar_relatorio_executivo`. Memória por `session_id`.

---

## Diagrama

```mermaid
flowchart TD
    A[POST /agents/report] --> B[AgentController]
    B --> C[SragReportAgent]
    C --> D[ensure_pipeline_ready]
    D --> E[GET /datasets/status]
    E --> F{Dados prontos?}
    F -- não --> G[POST /datasets/pipeline]
    F -- sim --> H[Loop tool calling LLM]
    G --> H
    H --> I[consultar_metricas_srag]
    H --> J[consultar_serie_temporal]
    H --> K[gerar_especificacao_grafico]
    H --> L[buscar_noticias_srag]
    I --> M[API /metrics]
    J --> M
    K --> N[ChartSpec]
    L --> O[Tavily Search]
    H --> P[Resumo executivo + charts]
```

---

## Tools LangChain

O agente utiliza tools estruturadas (`StructuredTool` do LangChain). A LLM escolhe dinamicamente quais chamar.

### `consultar_metricas_srag`

Definida em `SragMetricsApiLangChainService.as_tool()`.

| Propriedade | Valor |
|-------------|-------|
| Nome | `consultar_metricas_srag` |
| Entrada | `estado` (sigla da UF ou `BRASIL`) |
| Saída | JSON com métricas, casos diários e casos mensais |

O método `get_full_metrics_data()` agrega as três chamadas à API em um único payload:

```json
{
  "sg_uf_not": "SP",
  "metricas": {
    "taxa_aumento_casos": { "..." },
    "taxa_mortalidade": { "..." },
    "taxa_ocupacao_uti": { "..." },
    "taxa_vacinacao_populacao": { "..." }
  },
  "casos_diarios": { "..." },
  "casos_mensais": { "..." }
}
```

### `consultar_serie_temporal`

Definida em `SragMetricsApiLangChainService.as_series_tool()`.

| Propriedade | Valor |
|-------------|-------|
| Nome | `consultar_serie_temporal` |
| Entrada | `estado`, `serie` (`diaria` ou `mensal`) |
| Saída | JSON da série temporal oficial |

### `gerar_especificacao_grafico`

Definida em `ChartSpecService.as_tool(metrics_service)`.

| Propriedade | Valor |
|-------------|-------|
| Nome | `gerar_especificacao_grafico` |
| Entrada | `estado`, `serie` (`diaria` ou `mensal`) |
| Saída | JSON `ChartSpec` para renderização no dashboard |

### `buscar_noticias_srag`

Definida em `TavilyNewsLangChainService.as_tool()`.

| Propriedade | Valor |
|-------------|-------|
| Nome | `buscar_noticias_srag` |
| Entrada | vazia (consulta fixa otimizada) |
| Saída | Texto com manchetes, resumos e URLs |

Configuração da busca Tavily:

| Parâmetro | Valor |
|-----------|-------|
| `topic` | `news` |
| `search_depth` | `advanced` |
| `time_range` | `year` |
| `max_results` | `5` |
| `include_domains` | `gov.br`, `saude.gov.br`, `g1.globo.com`, `uol.com.br`, `cnnbrasil.com.br` |

---

## Formato do resumo

O prompt do agente instrui a LLM a produzir:

- panorama geral
- bloco **Dados oficiais**
- destaque para as **4 métricas**
- tendências dos casos diários e mensais
- bloco **Notícias**
- linguagem objetiva
- limite de **4000 caracteres**

As notícias são usadas apenas como **contexto complementar** e devem permanecer separadas dos dados oficiais.

Se não houver notícias relevantes, o agente deve informar isso explicitamente.

---

## Guardrails

### Dados oficiais

- a fonte oficial é a própria API SRAG
- se a pipeline não estiver pronta, o agente tenta executá-la automaticamente via `ensure_pipeline_ready()`
- o agente **não** consulta DuckDB diretamente; ele usa a API do projeto
- UF inválida retorna HTTP **422**

### Notícias

- o agente usa apenas **Tavily Search**
- a query padrão é restrita a notícias recentes sobre SRAG no Brasil
- resultados são filtrados para conter referência ao Brasil ou domínio `.br` e termos relacionados a SRAG/respiratório
- conteúdos com termos inadequados são bloqueados: `porn`, `sexo`, `violencia`, `racismo`, `politica`, `celebridade`, `guerra`, `crime`, `assassinato`, `terrorismo`
- notícias não substituem os números oficiais

### Resposta

- o texto final é truncado para no máximo 4000 caracteres, se necessário (corte em limite de palavra)
- o agente deve deixar clara a separação entre fatos medidos e contexto noticioso
- falhas na geração retornam HTTP **502**

---

## Endpoint

### Requisição

```bash
curl -X POST http://localhost:8000/agents/report \
  -H "Content-Type: application/json" \
  -d "{\"estado\":\"SP\"}"
```

### Resposta (`ExecutiveSummaryResponse`)

```json
{
  "estado": "SP",
  "resumo_executivo": "Resumo executivo em português...",
  "charts": [
    {
      "id": "casos_diarios",
      "type": "line",
      "title": "Casos diários de SRAG — SP",
      "x": {"field": "data", "label": "Data"},
      "y": {"field": "casos", "label": "Notificações"},
      "data": [{"data": "2026-06-01", "casos": 12}],
      "source": "GET /metrics/SP/casos-diarios",
      "caveat": "Períodos recentes podem estar incompletos por atraso de digitação/notificação; ..."
    },
    {
      "id": "casos_mensais",
      "type": "bar",
      "title": "Casos mensais de SRAG — SP",
      "x": {"field": "label", "label": "Mês"},
      "y": {"field": "casos", "label": "Notificações"},
      "data": [{"label": "05/2026", "casos": 100}],
      "source": "GET /metrics/SP/casos-mensais",
      "caveat": "Períodos recentes podem estar incompletos por atraso de digitação/notificação; ..."
    }
  ]
}
```

Os gráficos (`ChartSpec`) são montados por `ChartSpecService` a partir das séries oficiais da API. O prompt do agente orienta a não interpretar queda recente como redução real sem considerar atraso de notificação.
### Códigos de erro

| Código | Situação |
|--------|----------|
| `422` | UF inválida ou erro de validação |
| `502` | Falha na geração do resumo (OpenAI, Tavily, pipeline, etc.) |

---

## Chatbot LangGraph (`POST /agents/chat`)

O chatbot multi-turno usa o **mesmo** `LangGraphOrchestratorAgent` do relatório (`create_react_agent` + `MemorySaver` + tools, incluindo Tavily).

### Requisição

```bash
curl -X POST http://localhost:8000/agents/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Mostre a tendencia mensal\",\"estado_contexto\":\"SP\",\"session_id\":\"sess-123\"}"
```

### Resposta (`ChatResponse`)

```json
{
  "session_id": "sess-123",
  "estado_contexto": "SP",
  "reply": "Resposta do assistente...",
  "charts": [],
  "tools_used": ["consultar_metricas_srag", "gerar_especificacao_grafico"]
}
```

| Campo | Descrição |
|-------|-----------|
| `session_id` | Memória da conversa (thread do LangGraph). Se omitido na request, a API cria um novo |
| `estado_contexto` | UF/`BRASIL` usado como contexto padrão das tools |
| `reply` | Texto da resposta |
| `charts` | ChartSpecs gerados nesta rodada |
| `tools_used` | Tools invocadas nesta rodada |

Arquivos principais: `app/services/srag_chat_agent.py`, `app/models/chat.py`.

---

## Variáveis de ambiente

O agente depende destas variáveis (definidas no `.env`):

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `OPENAI_API_KEY` | Chave da API OpenAI | — (obrigatória) |
| `OPENAI_MODEL` | Modelo utilizado | `gpt-4o-mini` |
| `OPENAI_TEMPERATURE` | Temperatura da LLM | `0` |
| `TAVILY_API_KEY` | Chave da API Tavily | — (obrigatória) |
| `API_BASE_URL` | URL base da API SRAG | `http://127.0.0.1:8000` |
| `HTTP_TIMEOUT_SECONDS` | Timeout das chamadas HTTP | `300` |
| `LOG_LEVEL` | Nível de logging | `INFO` |

No Docker, o serviço `dashboard` usa `API_BASE_URL=http://api:8000` para comunicação interna entre containers. Após alterar o `.env`, recrie os containers com `docker compose up -d --force-recreate` para que as novas variáveis sejam carregadas.

---

## Integração com o dashboard

O dashboard em **[http://localhost:8080](http://localhost:8080)** (`shiny_app/dashboard.py`) possui:

- filtro de estado (UF ou `BRASIL`)
- verificação automática do status do pipeline
- cards com as quatro métricas principais
- botão **Gerar Relatório por IA**
- card textual para exibir o resumo do agente
- gráficos do relatório (diário e mensal) renderizados via Plotly a partir de `charts`
- **Chatbot SRAG (LangGraph)** com histórico, tools e gráficos da conversa
- botão **Nova conversa do chat**

Assim, o frontend apresenta métricas, gráficos e análise executiva em uma única interface.

---

## Testes

Os testes do agente e dos serviços relacionados estão em:

| Arquivo | Cobertura |
|---------|-----------|
| `tests/unit/test_srag_report_agent.py` | Orquestração do agente, charts e limite de 4000 caracteres |
| `tests/unit/test_srag_chat_agent.py` | Chatbot LangGraph (sessão, reply, charts, tools) |
| `tests/unit/test_agent_routes.py` | Endpoints `/agents/report` e `/agents/chat` |
| `tests/unit/test_chart_spec_service.py` | Montagem de ChartSpec a partir das séries oficiais |
| `tests/unit/test_srag_metrics_api_service.py` | Cliente HTTP, tool LangChain e `ensure_pipeline_ready` |
| `tests/unit/test_openai_langchain_service.py` | Integração com OpenAI via LangChain |
| `tests/unit/test_tavily_news_service.py` | Busca de notícias, filtros e tool LangChain |

Execução:

```bash
pytest tests/unit/test_srag_report_agent.py \
       tests/unit/test_agent_routes.py \
       tests/unit/test_srag_metrics_api_service.py \
       tests/unit/test_openai_langchain_service.py \
       tests/unit/test_tavily_news_service.py -v
```

Ou execute a suíte completa:

```bash
pytest
```
