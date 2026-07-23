import os
import re
import unicodedata

from app.config import SRAG_BRASIL_CODE, SRAG_STATE_CODES

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
PIPELINE_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "300"))

STATE_CHOICES: dict[str, str] = {SRAG_BRASIL_CODE: "Brasil (nacional)"}
STATE_CHOICES.update({uf: uf for uf in SRAG_STATE_CODES})

STATE_DISPLAY_NAMES: dict[str, str] = {
    SRAG_BRASIL_CODE: "Brasil",
    "AC": "Acre",
    "AL": "Alagoas",
    "AM": "Amazonas",
    "AP": "Amapá",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MG": "Minas Gerais",
    "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso",
    "PA": "Pará",
    "PB": "Paraíba",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "PR": "Paraná",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RO": "Rondônia",
    "RR": "Roraima",
    "RS": "Rio Grande do Sul",
    "SC": "Santa Catarina",
    "SE": "Sergipe",
    "SP": "São Paulo",
    "TO": "Tocantins",
}

_STATE_NAME_ALIASES: dict[str, str] = {
    "brasil": SRAG_BRASIL_CODE,
    "nacional": SRAG_BRASIL_CODE,
    "acre": "AC",
    "alagoas": "AL",
    "amazonas": "AM",
    "amapa": "AP",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "minas gerais": "MG",
    "mato grosso do sul": "MS",
    "mato grosso": "MT",
    "paraiba": "PB",
    "pernambuco": "PE",
    "piaui": "PI",
    "parana": "PR",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rondonia": "RO",
    "roraima": "RR",
    "rio grande do sul": "RS",
    "santa catarina": "SC",
    "sergipe": "SE",
    "sao paulo": "SP",
    "tocantins": "TO",
}

_UF_CODE_PATTERN = re.compile(
    r"(?<![A-Za-z])(" + "|".join(SRAG_STATE_CODES) + r"|BRASIL)(?![A-Za-z])",
    re.IGNORECASE,
)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def detect_scope_from_text(text: str) -> str | None:
    """Extrai UF ou BRASIL de um texto livre (sigla ou nome)."""
    raw = (text or "").strip()
    if not raw:
        return None

    folded = _strip_accents(raw).casefold()

    # Nomes compostos primeiro (mais especificos).
    for alias in sorted(_STATE_NAME_ALIASES, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", folded):
            return _STATE_NAME_ALIASES[alias]

    match = _UF_CODE_PATTERN.search(raw)
    if match:
        code = match.group(1).upper()
        if code == SRAG_BRASIL_CODE or code in SRAG_STATE_CODES:
            return code
    return None


def scope_label(scope: str) -> str:
    code = (scope or SRAG_BRASIL_CODE).strip().upper()
    name = STATE_DISPLAY_NAMES.get(code)
    if not name:
        return code
    if code == SRAG_BRASIL_CODE:
        return name
    return f"{code} ({name})"


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
