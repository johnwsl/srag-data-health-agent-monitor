# Arquitetura Conceitual da Solução SRAG

Este documento apresenta o diagrama conceitual da solução **SRAG Data Health Agent Monitor**, cobrindo frontend, backend, agente principal orquestrador, tools, integração com LLM, banco de dados e fontes externas de notícias.

## Visão Geral

A solução combina dados oficiais de SRAG do OpenDataSUS, processamento analítico em DuckDB, uma API FastAPI, um dashboard Shiny e um agente de IA que gera resumo executivo com apoio de métricas oficiais e notícias recentes.

```mermaid
flowchart LR
    Usuario[Usuário / Analista] --> Frontend[Frontend<br/>Dashboard Shiny<br/>localhost:8080]

    Frontend -->|HTTP JSON| API[Backend FastAPI<br/>localhost:8000]
    API --> Views[Views / Rotas HTTP<br/>dataset_routes<br/>metrics_routes<br/>agent_routes]
    Views --> Controllers[Controllers<br/>dataset_controller<br/>metrics_controller<br/>agent_controller]
    Controllers --> Services[Services<br/>Regras de negócio e integrações]

    Services --> MetricsService[SRAGMetrics<br/>Cálculo das métricas]
    MetricsService --> DuckDB[(DuckDB<br/>data/srag.duckdb<br/>tabela srag_notificacoes)]

    OpenDataSUS[OpenDataSUS<br/>CSVs públicos SRAG] --> Downloader[Download<br/>httpx]
    Downloader --> RawData[raw_data/<br/>CSVs brutos]
    RawData --> ETL[ETL<br/>pandas]
    ETL --> DuckDB

    Frontend -->|POST /agents/report| AgentEndpoint[Endpoint do Agente<br/>POST /agents/report]
    AgentEndpoint --> AgentController[AgentController]
    AgentController --> Orchestrator[Agente Principal<br/>SragReportAgent<br/>Orquestrador]

    Orchestrator -->|verifica pipeline| PipelineStatus[GET /datasets/status]
    Orchestrator -->|executa se necessário| PipelineRun[POST /datasets/pipeline]

    Orchestrator --> MetricsTool[Tool LangChain<br/>consultar_metricas_srag]
    MetricsTool --> MetricsAPI[API SRAG<br/>/metrics/estado<br/>/casos-diarios<br/>/casos-mensais]
    MetricsAPI --> DuckDB

    Orchestrator --> NewsTool[Tool LangChain<br/>buscar_noticias_srag]
    NewsTool --> Tavily[Tavily Search<br/>Notícias recentes sobre SRAG]
    Tavily --> NewsSources[Fontes de notícias<br/>gov.br<br/>saude.gov.br<br/>G1<br/>UOL<br/>CNN Brasil]

    Orchestrator -->|dados oficiais + notícias| LLM[LLM OpenAI<br/>via LangChain / ChatOpenAI]
    LLM --> Summary[Resumo executivo<br/>até 4000 caracteres]
    Summary --> Frontend
```

## Componentes Principais

### Frontend

O frontend é o dashboard em **Shiny for Python**, disponível em `http://localhost:8080`.

Ele permite selecionar uma UF ou `BRASIL`, visualizar cards de métricas, acompanhar gráficos de casos diários e mensais com Plotly e solicitar o relatório executivo por IA pelo botão **Gerar Relatório por IA**.

### Backend

O backend é uma API **FastAPI**. Documentação da API disponível em: `http://localhost:8000/docs`.

Ele expõe endpoints para saúde da aplicação, download dos datasets, execução da pipeline, consulta de métricas e geração do relatório por IA.

Principais rotas envolvidas:

- `GET /health`
- `POST /datasets/download`
- `POST /datasets/etl`
- `POST /datasets/pipeline`
- `GET /datasets/status`
- `GET /metrics/{estado}`
- `GET /metrics/{estado}/casos-diarios`
- `GET /metrics/{estado}/casos-mensais`
- `POST /agents/report`

### Camada de Dados

A camada de dados usa arquivos CSV públicos do **OpenDataSUS** como fonte oficial.

O fluxo de dados é:

1. Download dos CSVs para `raw_data/`.
2. ETL com `pandas`, incluindo merge, limpeza, filtros e derivação de variáveis de período.
3. Persistência no **DuckDB**, no arquivo `data/srag.duckdb`.
4. Consulta analítica pela API para cálculo das métricas SRAG.

## Agente Principal Orquestrador

O **Agente Principal** é implementado pelo serviço `SragReportAgent`.

Ele coordena a geração do resumo executivo a partir de três blocos de contexto:

- status da pipeline de dados;
- métricas e séries temporais oficiais vindas da própria API SRAG;
- notícias recentes sobre SRAG no Brasil.

O agente não consulta o DuckDB diretamente. Ele usa a API do próprio projeto como fonte oficial de dados.

## Tools Utilizadas

### `consultar_metricas_srag`

Tool estruturada do LangChain definida por `SragMetricsApiLangChainService`.

Responsabilidades:

- verificar se a pipeline está pronta com `GET /datasets/status`;
- executar `POST /datasets/pipeline` se os dados ainda não estiverem prontos;
- consultar `GET /metrics/{estado}`;
- consultar `GET /metrics/{estado}/casos-diarios`;
- consultar `GET /metrics/{estado}/casos-mensais`;
- devolver um JSON consolidado com métricas e séries temporais.

As quatro métricas principais retornadas são:

- taxa de aumento de casos;
- taxa de mortalidade;
- taxa de ocupação de UTI;
- taxa de vacinação COVID na população analisada.

### `buscar_noticias_srag`

Tool estruturada do LangChain definida por `TavilyNewsLangChainService`.

Responsabilidades:

- buscar notícias recentes sobre SRAG no Brasil via **Tavily Search**;
- limitar a busca a notícias recentes, com `topic=news`, `search_depth=advanced`, `time_range=month` e `max_results=5`;
- priorizar fontes como `gov.br`, `saude.gov.br`, `g1.globo.com`, `uol.com.br` e `cnnbrasil.com.br`;
- aplicar guardrails para evitar conteúdos fora do tema, fora do Brasil ou inadequados;
- retornar manchetes, resumos e URLs relevantes.

## Interação com a LLM

A interação com a LLM é encapsulada pelo `OpenAILangChainService`, que usa `ChatOpenAI` via LangChain.

O `SragReportAgent` monta um prompt com:

- estado consultado;
- status da pipeline SRAG;
- dados oficiais retornados pela tool `consultar_metricas_srag`;
- notícias retornadas pela tool `buscar_noticias_srag`;
- instruções para separar claramente **Dados oficiais** e **Notícias**.

A LLM retorna um resumo executivo em português, objetivo, limitado a até 4000 caracteres.

## Fluxo do Relatório por IA

```mermaid
sequenceDiagram
    participant U as Usuário
    participant F as Dashboard Shiny
    participant A as FastAPI
    participant O as SragReportAgent
    participant MT as consultar_metricas_srag
    participant NT as buscar_noticias_srag
    participant DB as DuckDB
    participant TV as Tavily Search
    participant L as OpenAI / LangChain

    U->>F: Seleciona UF ou BRASIL
    U->>F: Clica em Gerar Relatório por IA
    F->>A: POST /agents/report
    A->>O: generate_executive_summary(estado)
    O->>MT: ensure_pipeline_ready()
    MT->>A: GET /datasets/status
    MT->>A: POST /datasets/pipeline se necessário
    O->>MT: consultar_metricas_srag(estado)
    MT->>A: GET /metrics/estado
    MT->>A: GET /metrics/estado/casos-diarios
    MT->>A: GET /metrics/estado/casos-mensais
    A->>DB: Consulta dados analíticos
    DB-->>A: Métricas e séries
    A-->>MT: JSON consolidado
    O->>NT: buscar_noticias_srag()
    NT->>TV: Busca notícias recentes
    TV-->>NT: Manchetes, resumos e URLs
    O->>L: Envia dados oficiais + notícias + instruções
    L-->>O: Resumo executivo
    O-->>A: ExecutiveSummaryResponse
    A-->>F: JSON com resumo_executivo
    F-->>U: Exibe relatório no dashboard
```

## Resultado Esperado

Ao final do fluxo, o usuário recebe no dashboard:

- métricas oficiais de SRAG para a UF ou para `BRASIL`;
- séries temporais de casos diários e mensais;
- notícias recentes usadas apenas como contexto complementar;
- resumo executivo gerado pela LLM, com separação clara entre dados oficiais e notícias.

