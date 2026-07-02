# Agente Orquestrador SRAG

## Objetivo

O agente orquestrador gera um **resumo executivo** sobre a situação de SRAG para uma UF ou para `BRASIL`, combinando:

- **dados oficiais** da API SRAG
- **notícias recentes** buscadas via Tavily
- **síntese textual** produzida por um modelo da OpenAI via LangChain

O resultado é exposto pela API em `POST /agents/report` e também pode ser consumido no dashboard em **[http://localhost:8080](http://localhost:8080)**.

---

## Arquitetura

O fluxo segue o padrão MVC já adotado no projeto:

- `app/views/agent_routes.py`  
  expõe o endpoint `POST /agents/report`
- `app/controllers/agent_controller.py`  
  valida a entrada e trata erros HTTP
- `app/services/srag_report_agent.py`  
  orquestra a pipeline, as tools e a chamada à LLM

### Services envolvidos

| Classe | Responsabilidade |
|--------|------------------|
| `OpenAILangChainService` | Conecta a OpenAI via LangChain |
| `SragMetricsApiLangChainService` | Consulta status, pipeline, métricas e séries da API |
| `TavilyNewsLangChainService` | Busca notícias recentes sobre SRAG no Brasil |
| `SragReportAgent` | Coordena tudo e gera o resumo executivo final |

---

## Fluxo de execução

Quando `POST /agents/report` é chamado com um payload como:

```json
{
  "estado": "SP"
}
```

o agente executa a seguinte sequência:

1. chama `GET /datasets/status`
2. se os dados não estiverem prontos, chama `POST /datasets/pipeline`
3. consulta as métricas oficiais em:
   - `GET /metrics/{estado}`
   - `GET /metrics/{estado}/casos-diarios`
   - `GET /metrics/{estado}/casos-mensais`
4. busca notícias recentes com Tavily Search
5. envia tudo para a OpenAI
6. retorna um resumo executivo com até **1500 caracteres**

---

## Diagrama

```mermaid
flowchart TD
    A[POST /agents/report] --> B[AgentController]
    B --> C[SragReportAgent]
    C --> D[GET /datasets/status]
    D --> E{Dados prontos?}
    E -- não --> F[POST /datasets/pipeline]
    E -- sim --> G[Consultar métricas]
    F --> G
    G --> H[GET /metrics/{estado}]
    G --> I[GET /metrics/{estado}/casos-diarios]
    G --> J[GET /metrics/{estado}/casos-mensais]
    C --> K[Tavily Search]
    H --> L[OpenAI via LangChain]
    I --> L
    J --> L
    K --> L
    L --> M[Resumo executivo]
```

---

## Formato do resumo

O prompt do agente instrui a LLM a produzir:

- panorama geral
- bloco **Dados oficiais**
- destaque para as **4 métricas**
- tendências dos casos diários e mensais
- bloco **Notícias**
- linguagem objetiva
- limite de **1500 caracteres**

As notícias são usadas apenas como **contexto complementar** e devem permanecer separadas dos dados oficiais.

---

## Guardrails

### Dados oficiais

- a fonte oficial é a própria API SRAG
- se a pipeline não estiver pronta, o agente tenta executá-la automaticamente
- o agente não consulta DuckDB diretamente; ele usa a API do projeto

### Notícias

- o agente usa apenas **Tavily Search**
- a query é restrita a notícias recentes sobre SRAG no Brasil
- conteúdos com termos inadequados são filtrados
- notícias não substituem os números oficiais

### Resposta

- o texto final é truncado para no máximo 1500 caracteres, se necessário
- o agente deve deixar clara a separação entre fatos medidos e contexto noticioso

---

## Endpoint

### Requisição

```bash
curl -X POST http://localhost:8000/agents/report \
  -H "Content-Type: application/json" \
  -d "{\"estado\":\"SP\"}"
```

### Resposta

```json
{
  "estado": "SP",
  "resumo_executivo": "Resumo executivo em português..."
}
```

---

## Variáveis de ambiente

O agente depende destas variáveis:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_TEMPERATURE`
- `TAVILY_API_KEY`
- `API_BASE_URL`

Elas são carregadas a partir do `.env`.

---

## Integração com o dashboard

O dashboard em **[http://localhost:8080](http://localhost:8080)** possui:

- filtro de estado
- botão **Gerar relatório**
- card textual para exibir o resumo do agente

Assim, o frontend apresenta métricas, gráficos e análise executiva em uma única interface.

---

## Testes

Os testes do agente estão principalmente em:

- `tests/unit/test_srag_report_agent.py`
- `tests/unit/test_agent_routes.py`
- `tests/unit/test_srag_metrics_api_service.py`

Execução:

```bash
pytest tests/unit/test_srag_report_agent.py tests/unit/test_agent_routes.py tests/unit/test_srag_metrics_api_service.py -v
```
