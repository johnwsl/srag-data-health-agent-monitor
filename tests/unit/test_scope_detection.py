from shiny_app.constants import detect_scope_from_text, scope_label


def test_detect_scope_from_sigla():
    assert detect_scope_from_text("Como está a mortalidade em SP?") == "SP"
    assert detect_scope_from_text("dados do brasil") == "BRASIL"


def test_detect_scope_from_state_name():
    assert detect_scope_from_text("mostre UTI em São Paulo") == "SP"
    assert detect_scope_from_text("casos em Pernambuco") == "PE"
    assert detect_scope_from_text("Rio Grande do Sul") == "RS"


def test_detect_scope_none_when_absent():
    assert detect_scope_from_text("o que e SRAG?") is None


def test_scope_label():
    assert scope_label("SP") == "SP (São Paulo)"
    assert scope_label("BRASIL") == "Brasil"
