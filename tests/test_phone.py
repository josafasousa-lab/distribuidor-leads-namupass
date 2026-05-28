import pytest
from core.phone import normalizar


@pytest.mark.parametrize("raw,esperado", [
    ("(11) 99999-9999",      "+5511999999999"),
    ("11.99999.9999",        "+5511999999999"),
    ("+55 11 9 9999-9999",   "+5511999999999"),
    ("(11) 3333-3333",       "+551133333333"),   # fixo 8 dígitos válido
    ("99999-9999",           None),              # sem DDD
    ("",                     None),
    (None,                   None),
    ("00000-0000",           None),              # sequência inválida
])
def test_normalizar(raw, esperado):
    assert normalizar(raw) == esperado
