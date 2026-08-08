# tests/test_cli_version.py
"""
F-001 — Comando 'version' del CLI.

Tests trazables a los criterios de aceptación de la feature:
    R1  constante ETL_VERSION en config/settings.py
    R2  `python main.py version` imprime la versión y sale con código 0
    R3  la salida usa IMAGE_TAG del entorno, o 'local' si no está definida
    R4  todo se valida con CliRunner, sin red ni BBDD

No tocan red ni BBDD: `version` ni siquiera carga la configuración.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from config.settings import BUILD_UNKNOWN, ETL_VERSION
from main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_f001_r1_etl_version_es_semver_no_vacio() -> None:
    """R1: existe ETL_VERSION y tiene forma de versión (mayor.menor.parche)."""
    assert ETL_VERSION
    partes = ETL_VERSION.split(".")
    assert len(partes) == 3
    assert all(p.isdigit() for p in partes)


def test_f001_r2_version_sale_con_codigo_cero(runner: CliRunner) -> None:
    """R2: el comando termina en 0 e imprime la versión."""
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert ETL_VERSION in result.output


def test_f001_r2_version_no_carga_la_configuracion(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    R2: 'version' no debe pasar por get_settings().

    Es el caso real que justifica el comando: un contenedor arranca sin
    SIGRID_API_* y get_settings() aborta, pero aun así necesitas saber qué
    imagen está corriendo. Se comprueba haciendo estallar get_settings en vez
    de borrar variables de entorno, porque un .env en disco haría pasar el
    test por el motivo equivocado.
    """

    def _no_debe_llamarse() -> None:
        raise AssertionError("el comando 'version' no debe cargar la configuración")

    monkeypatch.setattr("main.get_settings", _no_debe_llamarse)

    result = runner.invoke(cli, ["version"])

    assert result.exit_code == 0
    assert ETL_VERSION in result.output


def test_f001_r3_image_tag_desde_entorno(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3: con IMAGE_TAG definida, la salida muestra ese tag."""
    monkeypatch.setenv("IMAGE_TAG", "datamart-seg-anual:r20260808-0300")

    result = runner.invoke(cli, ["version"])

    assert result.exit_code == 0
    assert "image: datamart-seg-anual:r20260808-0300" in result.output


def test_f001_r3_image_tag_local_si_no_hay_entorno(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3: sin IMAGE_TAG (ejecución desde el repo), el tag es 'local'."""
    monkeypatch.delenv("IMAGE_TAG", raising=False)

    result = runner.invoke(cli, ["version"])

    assert result.exit_code == 0
    assert f"image: {BUILD_UNKNOWN}" in result.output


def test_f001_r3_build_date_desde_entorno(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R3: la fecha de build también viene del entorno, con el mismo criterio."""
    monkeypatch.setenv("BUILD_DATE", "2026-08-08T03:00:00Z")
    result = runner.invoke(cli, ["version"])
    assert "build: 2026-08-08T03:00:00Z" in result.output

    monkeypatch.delenv("BUILD_DATE", raising=False)
    result = runner.invoke(cli, ["version"])
    assert f"build: {BUILD_UNKNOWN}" in result.output


def test_f001_r2_version_aparece_en_la_ayuda(runner: CliRunner) -> None:
    """R2: el comando está registrado en el grupo y es descubrible."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.output
