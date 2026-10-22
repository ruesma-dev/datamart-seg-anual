# tests/test_f147_contenido.py
"""
F-147 · El contenido decidido por el humano (R7-R16).

La tabla de `specs/F-147-presupuesto-contexto-mcp/revision_reglas.md`, decidida
el 2026-10-22, convertida en comprobaciones: qué reglas quedan, cuáles se
funden o se retiran, qué se sirve de cada una, a qué ficha va el detalle que
sale y qué no puede volver a afirmarse (el IVA de compras, la obra activa, las
cifras que envejecen).

Se barre el diccionario CARGADO, no el YAML crudo, salvo donde lo que se mira
es el YAML como fichero (convenciones y barrido de códigos retirados): el
plegado de `>-` parte las frases (ver `tests/_texto.py`).

Ningún test abre red ni BBDD.
"""

from __future__ import annotations

import re
import subprocess
from functools import cache
from pathlib import Path

import pytest
import yaml

from etl_sigrid.domain.diccionario import (
    CODIGOS_REGLAS_OBLIGATORIAS,
    MAX_PREGUNTAS_ENRUTADO,
    validar,
)
from tests._texto import normalizado
from tests.test_f006_formato import PASOS_NOCTURNOS, _dicc, _esquemas

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"

#: Las 21 reglas del YAML tras F-147 (D1, D3): 27 - 4 de perfiles + 1
#: - 3 de `fact_compras_linea` + 1 - `R-COSTE-CONSULTA`.
REGLAS_TRAS_F147 = {
    "R-FRESCURA", "R-IMPORTE-MES", "R-VENTA-COEFICIENTES", "R-UNIVERSO-OBRA",
    "R-CODIGO-POR-EMPRESA", "R-EMPRESA-POR-DEFECTO", "R-SALDO-CONTABLE",
    "R-PERFILES", "R-TESORERIA-ESTADO", "R-DESCOMPUESTO-ORIGEN",
    "R-PROVEEDOR-INTRAGRUPO", "R-SIGRID-CON", "R-ALBARAN-ABSURDO",
    "R-OBRA-ACTIVA", "R-VERSION-MASTER", "R-FAS-AMBIGUO", "R-CLAVE-SUSTITUTA",
    "R-PARTIDA-CODIGO-NO-UNICO", "R-RETENCION-NO-JOIN-LINEAS",
    "R-COMPRAS-SIN-IVA", "R-COMPRAS-LINEA",
}

#: Los ocho códigos que F-147 retira (R8). Se escriben partidos para que este
#: mismo fichero no sea el primer hallazgo de su barrido.
_R = "R-"
CODIGOS_RETIRADOS = tuple(
    _R + c
    for c in (
        "CONTABILIDAD-RESTRINGIDA", "TESORERIA-RESTRINGIDA", "COMPRAS-RESTRINGIDA",
        "PERFIL-RESTRINGIDO", "COMPRAS-TIPO-DOC", "ABONO-NEGATIVO",
        "LINEA-ID-NO-UNICA", "COSTE-CONSULTA",
    )
)


@cache
def _cargado():
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    return cargar_diccionario(DIR_DICCIONARIO)[0]


@cache
def _real():
    from etl_sigrid.domain.diccionario import derivar_avisos

    return derivar_avisos(_cargado())


def _regla(codigo: str):
    return next(r for r in _real().reglas if r.codigo == codigo)


def _global() -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8"))


def _texto_ficha(nombre: str) -> str:
    ficha = _real().por_nombre[nombre]
    partes = [ficha.descripcion, ficha.grano or "", ficha.motivo_no_consumo or ""]
    partes += [c.significado for c in ficha.columnas]
    return normalizado(" ".join(partes))


# ---------------------------------------------------------------------------
# R7 · Las reglas, su entrega y la versión
# ---------------------------------------------------------------------------


def test_f147_r7_quedan_las_21_reglas_decididas() -> None:
    assert {r.codigo for r in _real().reglas} == REGLAS_TRAS_F147


def test_f147_r7_solo_r_perfiles_va_entera_y_solo_r_sigrid_con_fuera() -> None:
    """D2 y petición B de `mcp-bbdd`: `R-PERFILES` trata de lo que el perfil NO
    ve, así que nunca le llegaría por `describir_tabla`: se sirve entera."""
    entregas = {r.codigo: r.entrega for r in _real().reglas}

    assert entregas.pop("R-PERFILES") == "entera"
    assert entregas.pop("R-SIGRID-CON") == "fuera_mcp"
    assert set(entregas.values()) == {"resumen"}


def test_f147_r7_el_diccionario_real_valida_entero() -> None:
    from tests.test_f006_frescura import pasos_del_pipeline_nocturno

    assert validar(_cargado(), pasos_del_pipeline_nocturno()) == []


def test_f147_r7_version_59() -> None:
    assert str(_global()["version"]) == "59"


def test_f147_r7_el_orden_no_se_repite() -> None:
    """Hallazgo 6: `R-SIGRID-CON` y `R-PROVEEDOR-INTRAGRUPO` compartían `orden`."""
    ordenes = [r.orden for r in _real().reglas]

    assert len(ordenes) == len(set(ordenes)), sorted(ordenes)


def test_f147_b_r_perfiles_es_corta_y_su_ambito_la_deja_ver_al_restringido() -> None:
    """Petición B: si la F-029 de `mcp-bbdd` deja de servir a un perfil las
    reglas cuyo ámbito no puede leer, `R-PERFILES` tiene que seguir llegando al
    restringido. Su ámbito incluye objetos que SÍ lee (`compras`, `retenciones`).
    Y como se sirve entera en cada conversación, su texto es corto."""
    from config.settings import DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS

    legibles = set(DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS.split(","))
    regla = _regla("R-PERFILES")

    assert any(destino.split(".")[0] in legibles for destino in regla.ambito)
    assert len(regla.regla) + len(regla.motivo) <= 1_000


# ---------------------------------------------------------------------------
# R8 · Códigos obligatorios y retirados
# ---------------------------------------------------------------------------


def test_f147_r8_los_obligatorios_incluyen_los_nuevos_y_no_los_fundidos() -> None:
    assert {"R-PERFILES", "R-COMPRAS-LINEA"} <= set(CODIGOS_REGLAS_OBLIGATORIAS)
    assert not set(CODIGOS_RETIRADOS) & set(CODIGOS_REGLAS_OBLIGATORIAS)


def _ficheros_del_repositorio() -> list[Path]:
    salida = subprocess.run(
        ["git", "-C", str(RAIZ), "ls-files", "-z"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return [RAIZ / f for f in salida.split("\0") if f]


#: Lo que SÍ puede citar un código retirado: la historia (`progress/`, `specs/`),
#: el backlog generado (`BACKLOG.md`) y su fuente (`harness/features.json`, cuyo
#: texto ES el de `BACKLOG.md`: excluir uno y no el otro no tiene sentido), y
#: este propio test.
EXCLUIDOS = ("progress/", "specs/", "BACKLOG.md", "harness/features.json",
             "tests/test_f147_contenido.py")


def test_f147_r8_ningun_fichero_cita_un_codigo_retirado() -> None:
    hallazgos = []
    for fichero in _ficheros_del_repositorio():
        relativo = fichero.relative_to(RAIZ).as_posix()
        if relativo.startswith(EXCLUIDOS) or not fichero.is_file():
            continue
        try:
            texto = fichero.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for codigo in CODIGOS_RETIRADOS:
            if re.search(rf"{re.escape(codigo)}(?![A-Z-])", texto):
                hallazgos.append(f"{relativo}: {codigo}")

    assert hallazgos == [], hallazgos


# ---------------------------------------------------------------------------
# R9 · El detalle que sale de las reglas, en su ficha
# ---------------------------------------------------------------------------

#: Objetos SIN empresa ni `obra_id` que la v58 enumeraba en `R-EMPRESA-POR-DEFECTO`.
SIN_EMPRESA = (
    "compras.facturas", "compras.albaranes", "compras.vencimientos",
    "compras.v_facturas_pago", "compras.documento_alarmas",
    "compras_restringida.documento_alarmas", "compras.documento_liquidatoria",
    "compras.v_estado_documentos", "compras.contrato_lineas",
    "compras.factura_recargos", "compras.albaran_recargos",
    "compras_restringida.documento_cuenta_bancaria", "personal.partes",
    "retenciones.v_pbi_retencion_entidad", "retenciones.v_pbi_retencion_resumen",
    "retenciones.v_pbi_retenciones_vivas", "retenciones.v_pbi_retenciones_vencidas",
    "retenciones.v_cuadre_proveedor",
)


@pytest.mark.parametrize("objeto", SIN_EMPRESA)
def test_f147_r9_la_ficha_sin_empresa_dice_que_mezcla_las_38(objeto: str) -> None:
    assert "mezcla las 38 empresas" in _texto_ficha(objeto).lower(), objeto


@pytest.mark.parametrize(
    ("objeto", "camino"),
    [
        ("compras.vencimientos", "tesoreria.efectos"),
        ("retenciones.v_pbi_retencion_resumen", "retenciones.movimientos"),
        ("retenciones.v_pbi_retencion_entidad", "retenciones.movimientos"),
    ],
)
def test_f147_r9_la_ficha_sin_empresa_da_su_camino_comprobado(objeto, camino) -> None:
    assert camino in _texto_ficha(objeto)


def test_f147_r9_la_cuenta_del_proveedor_no_se_reconstruye() -> None:
    texto = _texto_ficha("compras_restringida.documento_cuenta_bancaria")

    assert "compras.v_facturas_pago" in texto
    assert "R-PERFILES" in texto


@pytest.mark.parametrize(
    ("objeto", "debe_decir"),
    [
        ("contabilidad.saldos_cuenta_mes", "num_apuntes_restringidos"),
        ("contabilidad.saldos_cuenta_mes", "contabilidad.apuntes_restringidos_mes"),
        ("tesoreria.efectos", "tesoreria.efectos_restringidos_mes"),
        ("contabilidad.plan_cuentas", "640"),
    ],
)
def test_f147_r9_los_contadores_de_lo_restringido_estan_en_su_ficha(
    objeto: str, debe_decir: str
) -> None:
    assert debe_decir in _texto_ficha(objeto)


@pytest.mark.parametrize("objeto", ["stg.plan_mensual", "compras.fact_compras_linea"])
def test_f147_r9_las_caras_lo_dicen_en_su_ficha(objeto: str) -> None:
    """Lo que quedaba vivo de `R-COSTE-CONSULTA` (punto 3)."""
    assert "una sola consulta" in _texto_ficha(objeto).lower()


@pytest.mark.parametrize(
    "objeto", ["mart.v_fact_periodificado", "cierre.v_pbi_cierre_indirectos_detalle"]
)
def test_f147_r9_las_inconsultables_siguen_fuera_del_consumo(objeto: str) -> None:
    """El punto 1 de `R-COSTE-CONSULTA` ya lo decían sus fichas: que lo sigan."""
    ficha = _real().por_nombre[objeto]

    assert not ficha.consumo_recomendado
    assert "60 s" in normalizado(ficha.motivo_no_consumo or "")


def test_f147_r9_las_cuatro_obras_de_ficha_distinta_van_a_stg_obras() -> None:
    texto = _texto_ficha("stg.obras")

    for obra in ("0581", "0606", "0671", "0720"):
        assert obra in texto
    assert "es_ficha_principal" in texto


@pytest.mark.parametrize(
    "objeto", ["descompuestos.v_pbi_master_estudio", "descompuestos.v_pbi_estudio"]
)
def test_f147_r9_estudios_es_el_master_0_en_sus_fichas(objeto: str) -> None:
    assert "master 0" in _texto_ficha(objeto).lower()


# ---------------------------------------------------------------------------
# R7 · Los recortes de la tabla
# ---------------------------------------------------------------------------


def test_f147_r7_empresa_por_defecto_queda_en_la_orden() -> None:
    """El 80 % de la regla era un inventario que envejecía con cada objeto."""
    regla = _regla("R-EMPRESA-POR-DEFECTO")

    assert len(regla.regla) <= 1_200, len(regla.regla)
    assert "empresa_id = 1" in normalizado(regla.resumen)


def test_f147_r7_codigo_por_empresa_con_el_motivo_en_una_frase() -> None:
    assert len(_regla("R-CODIGO-POR-EMPRESA").motivo) <= 400


def test_f147_r7_fas_ambiguo_no_habla_de_raw_en_lo_servido() -> None:
    regla = _regla("R-FAS-AMBIGUO")

    assert "raw" not in regla.regla and "raw" not in regla.resumen


def test_f147_r7_clave_sustituta_resume_sin_la_excepcion() -> None:
    assert "aux" not in _regla("R-CLAVE-SUSTITUTA").resumen


def test_f147_r7_intragrupo_sin_cifras_en_la_orden() -> None:
    regla = _regla("R-PROVEEDOR-INTRAGRUPO")

    for texto in (regla.resumen, regla.regla, regla.titulo):
        assert "M€" not in texto and not re.search(r"\d+,\d", texto), texto
    assert "A81873903" in regla.resumen


# ---------------------------------------------------------------------------
# R10, R11 · Obra activa = obra VIVA de F-025
# ---------------------------------------------------------------------------


def test_f147_r10_obra_activa_es_la_obra_viva_de_la_nocturna() -> None:
    regla = _regla("R-OBRA-ACTIVA")
    texto = normalizado(regla.regla)

    for debe in ("config/business_rules.yaml", "ventana", "maestro.obras",
                 "stg.fases", "_meta.v_frescura_obra", "no es equivalente"):
        assert debe in texto, debe
    assert re.search(r"SELECT .* FROM maestro\.obras", texto), "la consulta equivalente"
    assert "NO se puede responder" not in texto, "eso dejó de ser cierto"
    assert {"stg.obras", "maestro.obras", "stg.fases", "_meta.v_frescura_obra"} <= set(
        regla.ambito
    )


def test_f147_r11_obra_activa_se_ata_a_business_rules() -> None:
    """Si cambia la ventana de F-025 y la regla no, la IA contaría otras obras."""
    reglas = yaml.safe_load((RAIZ / "config/business_rules.yaml").read_text(encoding="utf-8"))
    ventana = reglas["ventana"]
    texto = normalizado(_regla("R-OBRA-ACTIVA").regla)

    estados = ", ".join(str(e) for e in ventana["estados_que_congelan"])
    assert f"NOT IN ({estados})" in texto
    assert ventana["patron_codigo_administrativo"] in texto
    assert f"<= {ventana['meses_sin_actividad']}" in texto
    # Review F-147 (cambio 3): con la F-029 de `mcp-bbdd` el RESUMEN es lo único
    # que se sirve en cada conversación, así que se ata a la ventana entero, no
    # solo por los meses: estados, patrón administrativo y meses.
    resumen = normalizado(_regla("R-OBRA-ACTIVA").resumen)
    assert f"({estados})" in resumen, "los estados que congelan, en el resumen"
    digitos = re.fullmatch(r"\^\[0-9\]\{(\d+)\}\$", ventana["patron_codigo_administrativo"])
    assert digitos, "el patrón administrativo ya no es «N dígitos»: reescribe esta guarda"
    assert f"{digitos.group(1)} dígitos" in resumen, "el patrón administrativo, en el resumen"
    assert str(ventana["meses_sin_actividad"]) in resumen


# ---------------------------------------------------------------------------
# R12 · El IVA de compras
# ---------------------------------------------------------------------------

_FALSO_IVA = (
    re.compile(r"todos los importes (del esquema )?`?compras`? son sin iva", re.IGNORECASE),
    re.compile(r"[uú]nico importe con iva", re.IGNORECASE),
    re.compile(r"son sin iva \(base imponible de linea\)", re.IGNORECASE),
)


def _textos_iva() -> dict[str, str]:
    compras = (DIR_DICCIONARIO / "compras.yaml").read_text(encoding="utf-8")
    cabecera = compras.split("\nobjetos:")[0]
    regla = _regla("R-COMPRAS-SIN-IVA")
    return {
        "regla": normalizado(f"{regla.titulo} {regla.resumen} {regla.regla} {regla.motivo}"),
        "convencion": normalizado(str(_global()["convenciones"]["importes_iva"])),
        "cabecera de compras.yaml": normalizado(cabecera),
    }


@pytest.mark.parametrize("donde", ["regla", "convencion", "cabecera de compras.yaml"])
def test_f147_r12_nadie_dice_que_todo_compras_es_sin_iva(donde: str) -> None:
    texto = _textos_iva()[donde]

    for falso in _FALSO_IVA:
        assert not falso.search(texto), f"{donde}: {falso.pattern}"


def test_f147_r12_la_regla_nombra_los_totales_con_iva() -> None:
    regla = _regla("R-COMPRAS-SIN-IVA")

    for columna in ("total_factura", "total_documento", "total_a_pagar"):
        assert columna in regla.resumen and columna in regla.regla, columna


# ---------------------------------------------------------------------------
# R13 · El albarán absurdo, mínimo y sin cifras
# ---------------------------------------------------------------------------


def test_f147_r13_albaran_absurdo_sin_cifras_que_envejezcan() -> None:
    regla = _regla("R-ALBARAN-ABSURDO")

    for campo in ("titulo", "resumen", "regla", "motivo"):
        texto = getattr(regla, campo)
        assert "M€" not in texto and "billones" not in texto, campo
        assert not re.search(r"\d{1,3}(\.\d{3})+", texto), campo


def test_f147_r13_albaran_absurdo_conserva_lo_que_no_cambia() -> None:
    regla = _regla("R-ALBARAN-ABSURDO")
    texto = normalizado(f"{regla.resumen} {regla.regla}")

    assert "AC21/03345" in texto
    assert "< 1e8" in texto
    # El umbral de 1.000 M€ se escribe en letra: con cifras chocaría con la
    # prohibición de importes con separador de miles de esta misma regla.
    assert "mil millones" in texto
    assert len(regla.regla) + len(regla.motivo) <= 400


# ---------------------------------------------------------------------------
# R14 · Convenciones que dependían de `raw`
# ---------------------------------------------------------------------------


def test_f147_r14_identidad_sigrid_es_una_entrada_corta_que_remite() -> None:
    texto = str(_global()["convenciones"]["identidad_sigrid"])

    assert "R-SIGRID-CON" in texto
    assert len(normalizado(texto)) <= 300


def test_f147_r14_fechas_no_habla_de_raw() -> None:
    assert "raw" not in str(_global()["convenciones"]["fechas"])


# ---------------------------------------------------------------------------
# R15 · Enrutado: reordenar, nunca borrar
# ---------------------------------------------------------------------------


def _preguntas_en_main() -> dict[str, list[str]] | None:
    """Las preguntas de cada ficha en `main`, o `None` si no hay git a mano."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    try:
        salida = subprocess.run(
            ["git", "-C", str(RAIZ), "ls-tree", "--name-only", "main", "config/diccionario/"],
            capture_output=True, check=True, text=True,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return None
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        for ruta in salida:
            contenido = subprocess.run(
                ["git", "-C", str(RAIZ), "show", f"main:{ruta}"],
                capture_output=True, check=True,
            ).stdout
            (Path(tmp) / Path(ruta).name).write_bytes(contenido)
        dicc, _ = cargar_diccionario(Path(tmp))
    return {f.nombre: list(f.ejemplos_preguntas) for f in dicc.fichas}


def test_f147_r15_ninguna_pregunta_se_borra() -> None:
    """Las que no enrutan siguen en `describir_tabla`: se reordena, no se borra.
    Compara contra `main` (el día que esta feature esté en `main`, consigo misma)."""
    antes = _preguntas_en_main()
    if antes is None:
        pytest.skip("sin git no hay con qué comparar")
    ahora = {f.nombre: list(f.ejemplos_preguntas) for f in _real().fichas}

    perdidas = {
        nombre: sorted(set(preguntas) - set(ahora.get(nombre, [])))
        for nombre, preguntas in antes.items()
        if nombre in ahora and set(preguntas) - set(ahora[nombre])
    }
    assert perdidas == {}


def test_f147_r15_las_dos_primeras_son_distintas() -> None:
    for ficha in _real().fichas:
        primeras = ficha.ejemplos_preguntas[:MAX_PREGUNTAS_ENRUTADO]
        assert len(set(primeras)) == len(primeras), ficha.nombre


# ---------------------------------------------------------------------------
# R16 · `para_que_sirve` acotado
# ---------------------------------------------------------------------------


def test_f147_r16_un_para_que_sirve_de_mas_de_350_falla_nombrando_el_esquema() -> None:
    esquemas = _esquemas()
    esquemas["compras"]["para_que_sirve"] = "x" * 351

    errores = validar(_dicc(esquemas=esquemas), PASOS_NOCTURNOS)

    assert any("compras" in e.detalle and "350" in e.detalle for e in errores), errores


def test_f147_r16_350_justos_validan() -> None:
    esquemas = _esquemas()
    esquemas["compras"]["para_que_sirve"] = "x" * 350

    assert validar(_dicc(esquemas=esquemas), PASOS_NOCTURNOS) == []


def test_f147_r16_ningun_esquema_del_arbol_pasa_de_350() -> None:
    largos = {
        nombre: len(str(e.get("para_que_sirve", "")).strip())
        for nombre, e in _global()["esquemas"].items()
        if len(str(e.get("para_que_sirve", "")).strip()) > 350
    }
    assert largos == {}
