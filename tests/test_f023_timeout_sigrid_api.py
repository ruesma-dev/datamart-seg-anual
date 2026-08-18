# tests/test_f023_timeout_sigrid_api.py
"""
F-023 · El timeout hacia sigrid-api no puede superar el techo de la API.

La noche del 2026-08-18 el job de Azure falló en las 31 tablas de la ingesta
con `HTTP 400: timeout_seconds ... less than or equal to 230, input 300`. El
default del código era 300 y el ajuste a 230 vivía solo en los `.env` del
puesto, que el job no lleva. Estos tests fijan que el DEFAULT vale para el job
y que un valor mayor por entorno se rechaza antes de llegar a la API.
"""
import pytest
from pydantic import ValidationError

from config import settings as cfg


def _sigrid(**extra):
    base = {"base_url": "https://ejemplo.invalid", "function_key": "x"}
    base.update(extra)
    return cfg.SigridApiSettings(_env_file=None, **base)


def test_f023_el_techo_de_sigrid_api_es_230():
    assert cfg.SIGRID_API_TIMEOUT_MAX_S == 230.0


def test_f023_el_default_del_timeout_no_supera_el_techo():
    # Sin .env (como el job de Azure) el default tiene que ser aceptado por la API.
    assert _sigrid().timeout_s <= cfg.SIGRID_API_TIMEOUT_MAX_S


def test_f023_un_timeout_por_encima_del_techo_se_rechaza_al_arrancar():
    with pytest.raises(ValidationError):
        _sigrid(timeout_s=300)


def test_f023_un_timeout_igual_o_menor_al_techo_se_acepta():
    assert _sigrid(timeout_s=230).timeout_s == 230
    assert _sigrid(timeout_s=120).timeout_s == 120
