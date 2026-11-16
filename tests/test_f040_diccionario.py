# tests/test_f040_diccionario.py
"""F-040 · Diccionario y documentación de ventas (R31-R33), sin red ni BBDD.

Las fichas de `ventas` y `ventas_restringida` (una por objeto del SQL, con las
columnas EXACTAS que publica y sus trampas), sus `valores` contra el dominio,
las fichas de las siete tablas nuevas de `raw` y de `dvf` ampliada, las reglas
de `00_global.yaml` (versión, esquemas, `R-VENTAS-TRES-CIFRAS`,
`R-VENTAS-RESTRINGIDA`, `R-PERFILES`, `R-FRESCURA`) y la documentación.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

from etl_sigrid.domain import ventas as dom
from tests.test_f040_sql import COLUMNAS, VISTAS

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICC = RAIZ / "config" / "diccionario"
DIR_V = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "ventas"

VERSION_ANTERIOR = 74
TABLAS_RAW_NUEVAS = ("cli", "cer", "cerpro", "cerrec", "cerprodes", "dvfpro", "dvfrec")


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _fichas(esquema: str) -> dict:
    return _yaml(f"{esquema}.yaml")["objetos"]


def _global() -> dict:
    return _yaml("00_global.yaml")


def _regla(codigo: str) -> dict:
    return next(r for r in _global()["reglas"] if r["codigo"] == codigo)


def _texto(ficha: dict) -> str:
    return re.sub(r"\s+", " ", str(ficha))


def _objetos_del_sql() -> set[str]:
    """`esquema.objeto` de cada CREATE del SQL de ventas."""
    objetos: set[str] = set()
    for ruta in DIR_V.glob("*.sql"):
        sql = "\n".join(re.sub(r"--.*$", "", l) for l in ruta.read_text(encoding="utf-8").splitlines())
        objetos |= set(re.findall(
            r"CREATE (?:OR REPLACE )?(?:TABLE|VIEW|FUNCTION) (ventas(?:_restringida)?\.\w+)", sql))
    return objetos


def _columnas_esperadas() -> dict[str, tuple[str, ...]]:
    esperadas = {objeto: columnas for (_, objeto), columnas in COLUMNAS.items()}
    esperadas.update(VISTAS)
    return esperadas


# ===========================================================================
# R31 · una ficha por objeto, con sus columnas exactas
# ===========================================================================


def test_f040_r31_una_ficha_por_objeto_del_sql() -> None:
    fichados = {f"ventas.{n}" for n in _fichas("ventas")}
    fichados |= {f"ventas_restringida.{n}" for n in _fichas("ventas_restringida")}
    objetos = _objetos_del_sql()
    assert len(objetos) == 19, sorted(objetos)  # 8 tablas, 3 vistas, 5 funciones y 3 restringidas
    assert fichados == objetos


@pytest.mark.parametrize("esquema", ["ventas", "ventas_restringida"])
def test_f040_r31_paso_refresco_y_cabecera(esquema: str) -> None:
    contenido = _yaml(f"{esquema}.yaml")
    assert contenido["esquema"] == esquema
    for nombre, ficha in contenido["objetos"].items():
        assert ficha["paso_etl"] == "build_ventas", nombre
        assert ficha["refresco"] == "nocturno", nombre
    primera = (DIR_DICC / f"{esquema}.yaml").read_text(encoding="utf-8").splitlines()[0]
    assert primera == f"# config/diccionario/{esquema}.yaml"


@pytest.mark.parametrize("objeto", sorted(_columnas_esperadas()))
def test_f040_r31_las_columnas_de_la_ficha_son_las_del_sql(objeto: str) -> None:
    esquema, nombre = objeto.split(".")
    ficha = _fichas(esquema)[nombre]
    assert tuple(ficha["columnas"]) == _columnas_esperadas()[objeto]
    for columna, datos in ficha["columnas"].items():
        assert len(datos["significado"].strip()) >= 15, columna


def test_f040_r31_las_funciones_son_de_operacion_y_no_de_consumo() -> None:
    funciones = {n: f for n, f in _fichas("ventas").items() if f["tipo"] == "funcion"}
    assert set(funciones) == {"fn_fecha", "fn_cif_normalizado", "fn_es_persona_fisica",
                              "fn_cif_valido", "fn_clase_recargo"}
    for nombre, ficha in funciones.items():
        assert ficha["capa"] == "operacion" and ficha["consumo_recomendado"] is False, nombre
        assert ficha["columnas"] == {}, nombre
    assert "D4" in _texto(funciones["fn_clase_recargo"])


def test_f040_r31_valores_contra_el_dominio() -> None:
    f = _fichas("ventas")
    for tabla in ("factura_recargos", "certificacion_recargos"):
        assert f[tabla]["columnas"]["clase_recargo"]["valores"] == list(dom.CLASES_RECARGO), tabla
    assert (f["v_seguimiento_certificacion"]["columnas"]["estado_seguimiento"]["valores"]
            == list(dom.ESTADOS_SEGUIMIENTO))
    assert f["cobertura_enlace"]["columnas"]["eslabon"]["valores"] == list(dom.ESLABONES_COBERTURA)
    assert f["facturas"]["columnas"]["obra_via"]["valores"] == ["CENTRO", "OBRA"]


def test_f040_r31_el_general_no_documenta_columnas_personales() -> None:
    for nombre, ficha in _fichas("ventas").items():
        for columna in ficha.get("columnas") or {}:
            assert not columna.startswith(dom.PREFIJOS_PROHIBIDOS_EN_VENTAS), f"{nombre}.{columna}"


def test_f040_r31_las_trampas_estan_en_las_fichas() -> None:
    f = _fichas("ventas")
    clientes = _texto(f["clientes"])
    assert "persona fisica" in clientes and "NULL" in clientes and "ventas_restringida" in clientes
    assert "no es «sin CIF»" in clientes
    facturas = _texto(f["facturas"])
    for cosa in ("1024", "D4", "RETESP", "obra_via", "ventas_restringida.factura_cabecera"):
        assert cosa in facturas, cosa
    certificaciones = _texto(f["certificaciones"])
    for cosa in ("a cuenta", "coeficientes", "base_origen_contrato", "cuenta", "R-VENTAS-TRES-CIFRAS"):
        assert cosa in certificaciones, cosa
    enlace = _texto(f["certificacion_factura"])
    assert "N:M" in enlace and "idefac" in enlace
    seguimiento = _texto(f["v_seguimiento_certificacion"])
    assert "factura_compartida" in seguimiento and "0,01" in seguimiento
    cobro = _texto(f["v_factura_cobro"])
    assert "AGR" in cobro and "BAJA" in cobro and "F-104" in cobro
    contraste = _texto(f["v_contraste_certificado_obra"])
    assert "F-160" in contraste and "receta" in contraste
    assert "lineas" in _texto(f["factura_lineas"]) and "NULL" in _texto(f["factura_lineas"])


def test_f040_r31_las_fichas_restringidas_citan_la_autorizacion() -> None:
    fichas = _fichas("ventas_restringida")
    assert set(fichas) == {"clientes_contacto", "factura_cabecera", "factura_lineas_persona"}
    for nombre, ficha in fichas.items():
        assert ficha["descripcion"].startswith("**ACCESO RESTRINGIDO"), nombre
        assert "D2" in ficha["descripcion"] and "D6" in ficha["descripcion"], nombre
        assert "permission denied" in ficha["descripcion"], nombre
    cabecera = (DIR_DICC / "ventas_restringida.yaml").read_text(encoding="utf-8")
    assert "perfil TOTAL" in cabecera and "2026-11-07" in cabecera


def test_f040_r31_ejemplos_preguntas() -> None:
    f = _fichas("ventas")
    assert any("clientes" in p for p in f["clientes"]["ejemplos_preguntas"][:2])
    assert any("cobr" in p for p in f["v_seguimiento_certificacion"]["ejemplos_preguntas"][:2])
    assert any("factur" in p for p in f["facturas"]["ejemplos_preguntas"][:2])
    assert any("certific" in p for p in f["certificaciones"]["ejemplos_preguntas"][:2])


@pytest.mark.parametrize("tabla", TABLAS_RAW_NUEVAS)
def test_f040_r31_raw_tiene_ficha_de_cada_tabla_nueva(tabla: str) -> None:
    ficha = _fichas("raw")[tabla]
    texto = _texto(ficha)
    assert "F-040" in texto, tabla
    assert ficha["consumo_recomendado"] is False
    assert "personal" in texto.lower(), f"{tabla}: dice qué trae de personal (o que nada)"


def test_f040_r31_raw_dvf_a_35_columnas() -> None:
    texto = _texto(_fichas("raw")["dvf"])
    assert f"Solo se traen {len(dom.COLUMNAS_DVF)}" in texto
    for columna in dom.COLUMNAS_PERSONALES_DVF:
        assert f"`{columna}`" in texto, columna


# ===========================================================================
# R32 · 00_global.yaml
# ===========================================================================


def test_f040_r32_la_version_sube_en_uno() -> None:
    assert _global()["version"] >= VERSION_ANTERIOR + 1
    texto = (DIR_DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 75 (F-040, 2026-11-" in texto.split("\nversion:", 1)[0]


def test_f040_r32_los_dos_esquemas() -> None:
    esquemas = _global()["esquemas"]
    for nombre in ("ventas", "ventas_restringida"):
        assert esquemas[nombre]["pasos_etl"] == ["build_ventas"], nombre
        assert esquemas[nombre]["refresco"] == "nocturno"
        assert len(esquemas[nombre]["para_que_sirve"].strip()) <= 350
    assert "perfil total" in esquemas["ventas_restringida"]["para_que_sirve"]


def test_f040_r32_regla_tres_cifras() -> None:
    regla = _regla("R-VENTAS-TRES-CIFRAS")
    assert regla["severidad"] == "bloqueante"
    assert regla.get("entrega", "resumen") == "resumen"
    assert 40 <= len(regla["resumen"].strip()) <= 250
    assert set(regla["ambito"]) == {"ventas"}
    for cosa in ("certificado", "facturado", "cobrado", "factura_compartida", "a cuenta"):
        assert cosa in regla["regla"], cosa


def test_f040_r32_regla_ventas_restringida() -> None:
    regla = _regla("R-VENTAS-RESTRINGIDA")
    assert regla["severidad"] == "bloqueante"
    assert regla.get("entrega", "resumen") == "resumen"
    assert 40 <= len(regla["resumen"].strip()) <= 250
    assert set(regla["ambito"]) == {"ventas", "ventas_restringida"}
    for cosa in ("nombre", "publico", "perfil total", "permission denied", "nunca se cruza por nombre"):
        assert cosa in regla["regla"], cosa
    assert "D2" in regla["motivo"] and "D6" in regla["motivo"]


def test_f040_r32_perfiles_con_ventas() -> None:
    regla = _regla("R-PERFILES")
    assert {"ventas", "ventas_restringida"} <= set(regla["ambito"])
    assert "ventas" in regla["regla"] and "F-040" in regla["motivo"]
    assert "tampoco `ventas`" in regla["regla"], "el restringido tampoco lee ventas"


def test_f040_r32_frescura_alcanza_los_dos_esquemas() -> None:
    regla = _regla("R-FRESCURA")
    assert {"ventas", "ventas_restringida"} <= set(regla["ambito"])
    assert "build_ventas" in regla["regla"] and "build_ventas" in regla["motivo"]
    assert "ventas" in regla["resumen"]
    assert regla["titulo"].startswith("Diez esquemas")


def test_f040_r32_el_diccionario_real_valida() -> None:
    """El validador entero, con los pasos del pipeline REAL (diecisiete)."""
    from types import SimpleNamespace

    import main
    from etl_sigrid.domain.diccionario import formatear_errores, validar
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    ajustes = SimpleNamespace(postgres=SimpleNamespace(), sigrid=SimpleNamespace(),
                              etl=SimpleNamespace())
    pasos = [p.name for p in main.build_pipeline_steps(ajustes)]
    assert "build_ventas" in pasos
    dicc, _ = cargar_diccionario(DIR_DICC)
    errores = validar(dicc, pasos)
    assert errores == [], formatear_errores(errores)


# ===========================================================================
# R33 · documentación
# ===========================================================================


def test_f040_r33_architecture_describe_ventas() -> None:
    texto = (RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for cosa in ("ventas_restringida", "build_ventas", "F-040", "obrcer", "cerprodes", "F-104"):
        assert cosa in texto, cosa


def test_f040_r33_claude_md_mapa() -> None:
    texto = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
    for cosa in ("ventas/", "ventas_restringida", "F-040", "diecisiete pasos"):
        assert cosa in texto, cosa


def test_f040_r33_runbook_seccion_15() -> None:
    texto = (RAIZ / "docs" / "runbook_postgres_azure.md").read_text(encoding="utf-8")
    assert "## 15. Alta de `ventas_restringida` (F-040)" in texto
    seccion = texto.split("## 15. Alta de `ventas_restringida` (F-040)", 1)[1]
    assert "SIN CAMBIOS" in seccion and "Vuelta atrás" in seccion
    assert not re.search(r"\$env:\w+_PWD\s*=", seccion), "ninguna contraseña se carga en § 15"
