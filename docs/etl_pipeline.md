# Pipeline de Dados SRAG

Este documento descreve o processo de **pipeline** do projeto *SRAG Data Health Agent Monitor*: a orquestração que combina o **download** dos datasets do [Portal de Dados Abertos do SUS](https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026) com o **ETL** (Extract, Transform, Load) que prepara os dados para consulta no DuckDB e cálculo de métricas.

---

## Fonte dos dados

Os dados sobre **SRAG** (Síndrome Respiratória Aguda Grave) utilizados neste projeto são obtidos diretamente do SUS, por meio do portal oficial:

**[Banco de dados da Síndrome Respiratória Aguda Grave (SRAG) — 2019 a 2026](https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026)**

Esse conjunto de dados reúne informações do **Sivep-Gripe** (Sistema de Informação da Vigilância Epidemiológica da Gripe), sistema oficial para registro de casos e óbitos por SRAG no Brasil. No portal estão disponíveis:

- Arquivos CSV organizados por **ano epidemiológico** (2019 a 2026)
- **Dicionário de dados** e ficha de notificação
- Bases de anos anteriores “congeladas” e banco **vivo** do ano corrente, atualizado semanalmente

As URLs configuradas no `.env` apontam para os arquivos CSV publicados nesse portal (armazenados no repositório S3 do DATASUS). O pipeline baixa esses arquivos automaticamente na etapa de download.

---

## Visão geral

O pipeline transforma dados brutos de SRAG, publicados em CSV no [Portal de Dados Abertos do SUS](https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026), em uma tabela analítica pronta para métricas, séries temporais, dashboard e agentes de IA.

```mermaid
flowchart LR
    A[Portal Dados Abertos SUS] -->|HTTP| B[Download]
    B --> C[raw_data/*.csv]
    C --> D[ETL]
    D --> E[DuckDB]
    E --> F[SRAGMetrics]
    F --> G[GET /metrics/estado]
    G --> H[Dashboard Shiny]
    G --> I[Agente de IA]
```

### Endpoints do fluxo de dados

| Endpoint | Descrição |
|----------|-----------|
| `GET /health` | Health check da API |
| `GET /datasets/status` | Indica se os dados já estão prontos para consulta |
| `POST /datasets/pipeline` | Fluxo completo (recomendado) |
| `POST /datasets/download` | Apenas download |
| `POST /datasets/etl` | Apenas ETL |
| `GET /metrics/{estado}` | Consulta das 4 métricas SRAG (requer ETL executado) |
| `GET /metrics/{estado}/casos-diarios` | Série diária dos últimos 30 dias |
| `GET /metrics/{estado}/casos-mensais` | Série mensal dos últimos 12 meses |

O endpoint de pipeline **não duplica lógica**: ele orquestra os controllers de download e ETL em sequência, mantendo cada etapa independente e testável.

---

## Arquitetura do pipeline

```mermaid
sequenceDiagram
    participant Cliente
    participant PipelineController
    participant DatasetController
    participant EtlController
    participant DatasetService
    participant EtlService
    participant Disco as raw_data / DuckDB
    participant MetricsController
    participant SRAGMetrics

    Cliente->>EtlController: GET /datasets/status
    EtlController->>EtlService: get_status()
    EtlService->>Disco: verifica DuckDB
    EtlService-->>Cliente: ready / row_count

    Cliente->>PipelineController: POST /datasets/pipeline
    PipelineController->>DatasetController: download_datasets()
    DatasetController->>DatasetService: download_all_datasets()
    DatasetService->>Disco: grava CSVs
    DatasetService-->>DatasetController: resultados
    DatasetController-->>PipelineController: DatasetsDownloadResponse

    PipelineController->>EtlController: run_etl()
    EtlController->>EtlService: run()
    EtlService->>Disco: lê CSVs, grava DuckDB
    EtlService-->>EtlController: estatísticas
    EtlController-->>PipelineController: EtlResponse

    PipelineController-->>Cliente: PipelineResponse

    Cliente->>MetricsController: GET /metrics/SP
    MetricsController->>SRAGMetrics: taxa_*()
    SRAGMetrics->>Disco: consulta DuckDB
    SRAGMetrics-->>MetricsController: métricas
    MetricsController-->>Cliente: SRAGMetricsResponse
```

### Camadas envolvidas

| Camada | Arquivo | Papel |
|--------|---------|-------|
| Rota (pipeline) | `app/views/pipeline_routes.py` | Expõe `POST /datasets/pipeline` e `GET /datasets/status` |
| Rota (download) | `app/views/dataset_routes.py` | Expõe `POST /datasets/download` |
| Rota (ETL) | `app/views/etl_routes.py` | Expõe `POST /datasets/etl` |
| Rota (métricas) | `app/views/metrics_routes.py` | Expõe `GET /metrics/{estado}` e séries temporais |
| Controller | `app/controllers/pipeline_controller.py` | Orquestra download → ETL |
| Controller | `app/controllers/etl_controller.py` | Executa ETL e expõe status |
| Controller | `app/controllers/metrics_controller.py` | Orquestra as 4 métricas e séries |
| Serviço (download) | `app/services/dataset_service.py` | Baixa e persiste CSVs |
| Serviço (ETL) | `app/services/etl_service.py` | Transforma, grava no DuckDB e verifica status |
| Serviço (métricas) | `app/services/srag_metrics.py` | Calcula métricas e séries a partir do DuckDB |
| Configuração | `app/config.py` + `.env` | URLs, caminhos, colunas e constantes SRAG |
| Logging | `app/logging_config.py` | Configuração de logs para stdout |

---

## Status do pipeline (`GET /datasets/status`)

Antes de consultar métricas ou gerar relatórios, o sistema pode verificar se os dados já estão disponíveis.

O método `EtlService.get_status()` verifica:

1. Se o arquivo DuckDB existe
2. Se a tabela `srag_notificacoes` existe
3. Se há registros na tabela

### Exemplo de resposta (dados prontos)

```json
{
  "ready": true,
  "message": "Dados SRAG disponíveis para consulta.",
  "row_count": 385167
}
```

### Exemplo de resposta (dados ausentes)

```json
{
  "ready": false,
  "message": "Banco de dados SRAG não encontrado. Execute o pipeline.",
  "row_count": 0
}
```

O agente de IA e o dashboard utilizam esse endpoint para decidir se precisam executar o pipeline automaticamente.

---

## Etapa 1 — Download dos datasets

### Objetivo

Obter os arquivos CSV de SRAG a partir das URLs configuradas no [Portal de Dados Abertos do SUS](https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026) e salvá-los localmente em `RAW_DATA_DIR` (padrão: `./raw_data`).

### Datasets configurados

Por padrão, o sistema baixa **dois arquivos**, definidos no `.env`:

| Variável | Exemplo |
|----------|---------|
| `DATASET_NAME_2019` | `INFLUD19-23-03-2026.csv` |
| `DATASET_URL_2019` | URL do CSV de 2019 no portal SUS |
| `DATASET_NAME_2025` | `INFLUD25-29-06-2026.csv` |
| `DATASET_URL_2025` | URL do CSV de 2025 no portal SUS |

### Como funciona

1. Garante que a pasta `raw_data` existe.
2. Para cada dataset configurado, verifica se o arquivo **já existe e não está vazio**.
3. Se o arquivo já existir → **ignora o download** (`skipped: true`).
4. Se não existir (ou estiver vazio) → faz requisição HTTP com `httpx.AsyncClient`.
5. Salva o conteúdo no disco com o nome definido em `DATASET_NAME_*`.

### Parâmetros relevantes

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `HTTP_TIMEOUT_SECONDS` | Tempo máximo de espera por download | `300` (5 min) |
| `RAW_DATA_DIR` | Pasta de destino dos CSVs | `./raw_data` |

### Comportamento em falhas

- **Falha em um dataset**: retorna `success: false` para aquele arquivo, mas continua os demais.
- **Falha em todos os datasets**: retorna HTTP `502` e o pipeline **interrompe** (ETL não é executado).
- **Falha parcial**: download retorna sucesso parcial; o ETL roda com os arquivos disponíveis em `raw_data`.

### Exemplo de resposta (download)

```json
{
  "message": "Download concluído; alguns datasets já estavam presentes.",
  "total": 2,
  "successful": 2,
  "failed": 0,
  "datasets": [
    {
      "name": "INFLUD19-23-03-2026.csv",
      "url": "https://s3.sa-east-1.amazonaws.com/...",
      "path": "./raw_data/INFLUD19-23-03-2026.csv",
      "size_bytes": 52428800,
      "success": true,
      "skipped": true,
      "error": null
    }
  ]
}
```

---

## Etapa 2 — ETL (Extract, Transform, Load)

### Objetivo

Ler todos os CSVs em `raw_data`, aplicar regras de limpeza e tratamento, e persistir o resultado na tabela DuckDB configurada.

### Passos do ETL

```mermaid
flowchart TD
    A[1. Merge de todos os *.csv] --> B[2. Seleção de colunas]
    B --> C[3. Filtro NU_NOTIFIC]
    C --> D[4. Filtro SG_UF_NOT]
    D --> E[5. Preencher ausentes com 9]
    E --> F[6. Derivar ANO_NOTIFIC e MES_NOTIFIC]
    F --> G[7. Salvar no DuckDB]
```

#### 1. Merge

Concatena **todos** os arquivos `*.csv` presentes em `raw_data`, não apenas os configurados no `.env`. Isso permite incluir datasets adicionais manualmente, se necessário.

Para cada arquivo, o ETL lê o cabeçalho e importa apenas as colunas definidas em `ETL_COLUMNS` que existirem naquele CSV (separador `;`, encoding UTF-8).

#### 2. Seleção de colunas

Mantém apenas:

| Coluna | Descrição |
|--------|-----------|
| `NU_NOTIFIC` | Número da notificação (identificador do caso) |
| `DT_NOTIFIC` | Data da notificação |
| `SG_UF_NOT` | UF de notificação |
| `CLASSI_FIN` | Classificação final |
| `EVOLUCAO` | Evolução do caso |
| `UTI` | Internação em UTI |
| `VACINA_COV` | Vacina COVID-19 |
| `VACINA` | Vacina contra influenza |

Se alguma coluna obrigatória estiver ausente após o merge, o ETL retorna HTTP **422**.

#### 3 e 4. Filtros

Remove linhas que **não possuem informação** em:

- `NU_NOTIFIC` (vazio ou nulo)
- `SG_UF_NOT` (vazio ou nulo)

#### 5. Tratamento de valores ausentes

Nas colunas `CLASSI_FIN`, `EVOLUCAO`, `UTI`, `VACINA_COV` e `VACINA`, valores vazios ou nulos são preenchidos com **`9`**, código padrão de “ignorado/não informado” nos dados do DATASUS.

#### 6. Derivação de período

A partir de `DT_NOTIFIC`, cria:

- `ANO_NOTIFIC` — ano da notificação
- `MES_NOTIFIC` — mês da notificação

> **Nota:** `NU_NOTIFIC` é um identificador numérico do caso, não uma data. Por isso ano e mês são derivados de `DT_NOTIFIC`.

#### 7. Persistência no DuckDB

O dataset tratado é salvo com:

```sql
CREATE OR REPLACE TABLE "srag_notificacoes" AS SELECT * FROM etl_frame
```

A tabela é **recriada** a cada execução do ETL.

### Configuração do DuckDB

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `DUCKDB_PATH` | Caminho do arquivo do banco | `./data/srag.duckdb` |
| `ETL_TABLE_NAME` | Nome da tabela | `srag_notificacoes` |

No Docker, os volumes mapeiam:

- `./raw_data` → `/app/raw_data`
- `./data` → `/app/data`

### Schema final (10 colunas)

```
NU_NOTIFIC, DT_NOTIFIC, SG_UF_NOT, CLASSI_FIN, EVOLUCAO,
UTI, VACINA_COV, VACINA, ANO_NOTIFIC, MES_NOTIFIC
```

### Exemplo de resposta (ETL)

```json
{
  "message": "ETL concluído com sucesso.",
  "files_merged": [
    "INFLUD19-23-03-2026.csv",
    "INFLUD25-29-06-2026.csv"
  ],
  "rows_before_filter": 385213,
  "rows_after_filter": 385167,
  "rows_saved": 385167,
  "table_name": "srag_notificacoes",
  "database_path": "./data/srag.duckdb"
}
```

---

## Etapa 3 — Consulta de métricas e séries

Após o ETL, os dados no DuckDB alimentam o serviço `SRAGMetrics`, exposto pela API.

### Parâmetro `estado`

| Valor | Escopo |
|-------|--------|
| `BRASIL` | Todo o país (agregação nacional) |
| Sigla da UF | `AC`, `AL`, `AM`, `AP`, `BA`, `CE`, `DF`, `ES`, `GO`, `MA`, `MG`, `MS`, `MT`, `PA`, `PB`, `PE`, `PI`, `PR`, `RJ`, `RN`, `RO`, `RR`, `RS`, `SC`, `SE`, `SP`, `TO` |

A sigla é normalizada para maiúsculas (`/metrics/sp` equivale a `/metrics/SP`). UF inválida retorna HTTP **422**.

### Endpoints disponíveis

| Endpoint | Descrição |
|----------|-----------|
| `GET /metrics/{estado}` | Quatro métricas agregadas |
| `GET /metrics/{estado}/casos-diarios` | Contagem diária dos últimos 30 dias |
| `GET /metrics/{estado}/casos-mensais` | Contagem mensal dos últimos 12 meses |

Detalhes de fórmulas, filtros e cenários especiais das métricas estão em [`metricas_srag.md`](metricas_srag.md).

### Exemplo de resposta (métricas)

```json
{
  "sg_uf_not": "SP",
  "taxa_aumento_casos": {
    "sg_uf_not": "SP",
    "mes_atual_ano": 2026,
    "mes_atual_mes": 6,
    "mes_anterior_ano": 2026,
    "mes_anterior_mes": 5,
    "casos_mes_atual": 1200,
    "casos_mes_anterior": 980,
    "taxa_aumento_percentual": 22.45
  },
  "taxa_mortalidade": { "..." : "..." },
  "taxa_ocupacao_uti": { "..." : "..." },
  "taxa_vacinacao_populacao": { "..." : "..." }
}
```

---

## Resposta do pipeline completo

O endpoint `POST /datasets/pipeline` retorna um objeto unificado com o resultado das duas etapas:

```json
{
  "message": "Pipeline concluído: download e ETL executados com sucesso.",
  "download": { "...": "..." },
  "etl": { "...": "..." }
}
```

### Mensagens possíveis

| Situação | Mensagem |
|----------|----------|
| Download e ETL OK | *Pipeline concluído: download e ETL executados com sucesso.* |
| Arquivos já existiam | *Pipeline concluído: datasets já presentes e ETL executado com sucesso.* |
| Falha parcial no download | *Pipeline concluído com falhas parciais no download; ETL executado com os arquivos disponíveis.* |

---

## Logging

A aplicação usa o módulo **`logging`** do Python, configurado em `app/logging_config.py` e inicializado em `app/main.py`.

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `LOG_LEVEL` | Nível de verbosidade (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |

Os logs são enviados para **stdout** no formato:

```
2026-07-02 19:15:05 | INFO     | app.main | API iniciada
2026-07-02 19:15:09 | INFO     | app.request | GET /health 200 4.40ms
2026-07-02 19:15:12 | ERROR    | app.services.etl_service | Nenhum arquivo CSV encontrado em /app/raw_data
```

Com Docker, o driver **`json-file`** persiste esses logs (até ~50 MB por container: 5 arquivos × 10 MB).

---

## Como executar

### Via API (Swagger)

1. Inicie a aplicação (`docker compose up` ou `uvicorn app.main:app`).
2. Acesse [http://localhost:8000/docs](http://localhost:8000/docs).
3. Verifique `GET /datasets/status` ou execute `POST /datasets/pipeline`.
4. Consulte `GET /metrics/BRASIL`, `GET /metrics/SP` ou as séries temporais.

### Via curl

```bash
# Status do pipeline
curl http://localhost:8000/datasets/status

# Pipeline completo
curl -X POST http://localhost:8000/datasets/pipeline

# Métricas
curl http://localhost:8000/metrics/BRASIL
curl http://localhost:8000/metrics/SP

# Séries temporais
curl http://localhost:8000/metrics/SP/casos-diarios
curl http://localhost:8000/metrics/SP/casos-mensais
```

### Fluxo manual (etapas separadas)

```bash
# Apenas download
curl -X POST http://localhost:8000/datasets/download

# Apenas ETL (requer CSVs em raw_data)
curl -X POST http://localhost:8000/datasets/etl

# Métricas (requer ETL executado)
curl http://localhost:8000/metrics/RJ
```

### Dashboard

Com a API em execução, o dashboard Shiny está disponível em **[http://localhost:8080](http://localhost:8080)** (serviço `dashboard` no Docker ou `shiny run shiny_app/dashboard.py` localmente).

---

## Testes automatizados

O projeto inclui **71 testes** em `tests/unit` e `tests/integration`:

| Arquivo | Cobertura |
|---------|-----------|
| `tests/unit/test_dataset_service.py` | Download de datasets |
| `tests/unit/test_etl_service.py` | Pipeline de ETL |
| `tests/unit/test_pipeline_status.py` | Status do pipeline (`GET /datasets/status`) |
| `tests/unit/test_srag_metrics.py` | Cálculo de métricas, séries temporais e escopo por UF |
| `tests/unit/test_metrics_routes.py` | Rotas de métricas com mocks |
| `tests/integration/test_metrics_routes.py` | Integração real com a API de métricas e séries |

```bash
pytest
```

Os testes de download usam `httpx.MockTransport` (sem internet). Os testes de ETL e métricas usam bancos DuckDB temporários.

---

## Diagrama de pastas após o pipeline

```
srag-data-health-agent-monitor/
├── raw_data/
│   ├── INFLUD19-23-03-2026.csv    ← download
│   └── INFLUD25-29-06-2026.csv    ← download
└── data/
    └── srag.duckdb                ← ETL (tabela srag_notificacoes)
                                   ← consultado por GET /metrics/{estado}
```

---

## Integração com o restante da solução

Com os dados no DuckDB e as métricas expostas pela API, a aplicação oferece:

- **Dashboard Shiny** em [http://localhost:8080](http://localhost:8080) para visualização interativa
- **Agente de IA** via `POST /agents/report` para resumos executivos (ver [`agente_orquestrador.md`](agente_orquestrador.md))
- **Séries temporais** para gráficos de casos diários e mensais

O pipeline e as métricas formam a **base de dados e indicadores** sobre os quais o dashboard e o agente operam.
