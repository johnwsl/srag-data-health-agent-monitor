# SRAG Data Health Agent Monitor

API em FastAPI para ingestão, tratamento e disponibilização de dados de **SRAG** (Síndrome Respiratória Aguda Grave) do [OpenDataSUS](https://opendatasus.saude.gov.br/). O sistema faz o download dos datasets brutos, executa um pipeline de ETL e persiste os dados tratados em **DuckDB**, preparando a base para métricas de saúde e agentes de IA.

## O que o sistema faz

1. **Download** — Baixa arquivos CSV de SRAG a partir de URLs configuradas e salva em `raw_data/`. Arquivos já presentes são reutilizados, sem novo download.
2. **ETL** — Faz merge dos CSVs, seleciona colunas relevantes, filtra registros inválidos, trata valores ausentes e deriva variáveis de período (`ANO_NOTIFIC`, `MES_NOTIFIC`).
3. **Persistência** — Grava o dataset tratado no DuckDB (`data/srag.duckdb`), na tabela `srag_notificacoes`.
4. **Pipeline** — Orquestra download + ETL em uma única chamada.

### Endpoints principais

| Método | Caminho | Descrição |
|--------|---------|-----------|
| `GET` | `/health` | Health check da API |
| `POST` | `/datasets/download` | Download dos datasets |
| `POST` | `/datasets/etl` | Executa o ETL |
| `POST` | `/datasets/pipeline` | Download + ETL (fluxo completo) |

Documentação interativa: `http://localhost:8000/docs`

## Executando com Docker

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose instalados

### 1. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Ajuste o `.env` se necessário. Os valores padrão já funcionam para desenvolvimento local.

### 2. Subir a aplicação

```bash
docker compose up -d --build
```

### 3. Verificar se a API está no ar

```bash
curl http://localhost:8000/health
```

Resposta esperada: `{"status":"ok"}`

### 4. Executar o pipeline de dados

```bash
curl -X POST http://localhost:8000/datasets/pipeline
```

Ou acesse `http://localhost:8000/docs` e execute `POST /datasets/pipeline` pela interface Swagger.

### 5. Parar a aplicação

```bash
docker compose down
```

### Volumes

| Pasta local | Destino no container | Conteúdo |
|-------------|----------------------|----------|
| `./raw_data` | `/app/raw_data` | CSVs brutos do OpenDataSUS |
| `./data` | `/app/data` | Banco DuckDB (`srag.duckdb`) |

## Testes

Na raiz do projeto:

```bash
pip install -r requirements.txt
pytest
```

## Documentação

Informações mais detalhadas estão na pasta [`docs/`](docs/):

| Documento | Conteúdo |
|-----------|----------|
| [`docs/etl_pipeline.md`](docs/etl_pipeline.md) | Pipeline completo: download, ETL, arquitetura, configuração e exemplos |

## Stack

- **FastAPI** — API HTTP
- **httpx** — Download assíncrono dos datasets
- **pandas** — Transformação dos dados no ETL
- **DuckDB** — Armazenamento analítico
- **Docker** — Containerização
