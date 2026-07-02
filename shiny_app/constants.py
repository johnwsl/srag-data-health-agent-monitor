import os

from app.config import SRAG_BRASIL_CODE, SRAG_STATE_CODES

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
PIPELINE_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "300"))

STATE_CHOICES: dict[str, str] = {SRAG_BRASIL_CODE: "Brasil (nacional)"}
STATE_CHOICES.update({uf: uf for uf in SRAG_STATE_CODES})

METRIC_LABELS = {
    "taxa_aumento_casos": "Aumento de casos",
    "taxa_mortalidade": "Mortalidade",
    "taxa_ocupacao_uti": "Ocupação de UTI",
    "taxa_vacinacao_populacao": "Vacinação COVID",
}

METRIC_RATE_FIELDS = {
    "taxa_aumento_casos": "taxa_aumento_percentual",
    "taxa_mortalidade": "taxa_mortalidade_percentual",
    "taxa_ocupacao_uti": "taxa_ocupacao_uti_percentual",
    "taxa_vacinacao_populacao": "taxa_vacinacao_percentual",
}

METRIC_THEMES = {
    "taxa_aumento_casos": "primary",
    "taxa_mortalidade": "danger",
    "taxa_ocupacao_uti": "warning",
    "taxa_vacinacao_populacao": "success",
}
