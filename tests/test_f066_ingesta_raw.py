# tests/test_f066_ingesta_raw.py
"""
F-066 · Las 25 tablas que faltaban en `raw`, y lo que sus fichas tienen que
decir (R1 a R9, R11, R13, R14).

Aquí no se abre ninguna conexión: todo sale de `config/tables_sigrid.yaml` y de
`config/diccionario/raw.yaml`, que son las dos fuentes que **gobiernan** los
hechos que se comprueban —qué se ingiere y qué se publica de ello—.

Las cifras que aparecen en los mensajes se **midieron contra Sigrid el
2026-09-06** por `sigrid-api` en solo lectura (`INFORMATION_SCHEMA.COLUMNS` y
`COUNT(*)`), y están en `design.md` §1. Dos correcciones respecto a lo que la
spec suponía, las dos medidas:

* `hmo` (16 columnas), `cua` (16) y `asi` (7) **no tienen ninguna columna de
  texto ni binario ilimitado**, así que no excluyen nada. R7 manda excluir «las
  columnas de texto ilimitado que no se usan aguas abajo»; cuando no hay
  ninguna, la lista correcta es la vacía, y `tasks.md` lo confirma en T4 y T5.
* las tablas de compras llevan la **lista estándar de 13 nombres** aunque casi
  ninguna tenga las trece: es la convención del YAML desde el módulo COMPRAS
  —excluir un nombre que la tabla no tiene es inofensivo— y evita ir
  descubriéndolas de una en una a golpe de `COPY` roto.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

import pytest
import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[1]
FICHERO_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
FICHERO_RAW = RAIZ / "config" / "diccionario" / "raw.yaml"
FICHERO_GLOBAL = RAIZ / "config" / "diccionario" / "00_global.yaml"
FICHERO_PENDIENTES = RAIZ / "config" / "objetos_pendientes.yaml"

#: Cuántas tablas ingiere el ETL cuando esta feature cierra: 31 + 25.
TOTAL_TABLAS = 56

#: La lista estándar de nombres de texto/binario ilimitado de documentos, tal y
#: como la declara el bloque COMPRAS de `config/tables_sigrid.yaml`.
LISTA_ESTANDAR = (
    "tex", "med", "des", "obs", "ima", "emptex", "dirtex", "eiotex",
    "desesp", "texcom", "serdesdat", "texobs", "coestr",
)

#: Lo que `dco` añade a la lista estándar. **`pagtex` y `pagfor` NO están** (R8):
#: son las condiciones de pago del documento y esta feature las recupera.
EXTRA_DOCUMENTO = ("dircon1", "dircon2", "dircon3", "dirdir1", "dirdir2",
                   "dirdir3", "eittra", "texent")

#: Las 11 exclusiones **técnicas** de `emp` (§3 del diseño): la foto (`ima`,
#: binario ilimitado) y diez columnas de texto ilimitado. Medido el 2026-09-06:
#: son exactamente las 11 columnas ilimitadas que tiene la tabla, ni una más.
EXCLUSIONES_EMP = ("ima", "dir", "dirtex", "web", "tex", "eleloc", "disobs",
                   "podtex", "traele", "tracta", "obsnom")

#: Columnas de dato personal de `emp` y `res` que **entran** en `raw` por
#: decisión del humano del 2026-09-06 (DA-5). Ninguna puede estar excluida.
COLUMNAS_PERSONALES = ("dni", "tarseg", "ban", "bancue", "fecnac", "ele",
                       "tel", "esigpas")

#: Las 19 candidatas con **0 filas** en Sigrid, contadas una a una el
#: 2026-09-06. Ninguna se da de alta (R3): una tabla vacía en `raw` es una
#: invitación a construir encima de la nada. **Reabrir una es cambiar esta
#: constante**, que es justo lo que la hace una decisión y no un despiste.
VACIAS_EN_SIGRID = (
    "PFfir", "logfirdoc", "auxfam", "act", "auxacttip", "actent", "actseg",
    "comlinpar", "ctrrevpre", "ctrproact", "dcfproimp", "verhis", "auxtarprv",
    "auxsec", "confam", "entfam", "prvres", "prvcalsel", "rqs",
)

#: Las tres tablas nuevas que tienen `tiemod` (medido: ninguna otra lo tiene).
CON_TIEMOD = ("auxpronat", "auxpag", "auxefp")

#: Las que bajan el tamaño de página a 5.000 por número de filas × columnas
#: (R9), como ya hacen `dcapro` y `dcfpro`.
PAGINA_CORTA = ("dcopro", "dncpro")

GRUPO_PERSONAL = "personal"
GRUPO_CONTABILIDAD = "contabilidad"
GRUPO_COMPRAS = "compras"

#: Las 25 altas, con el grupo al que pertenecen y las exclusiones que le tocan a
#: cada una. El grupo NO es decorativo: decide la lista de exclusión (R7).
NUEVAS: dict[str, tuple[str, tuple[str, ...]]] = {
    # A · personal (F-057 construirá el mart encima)
    "res": (GRUPO_PERSONAL, ()),
    "emp": (GRUPO_PERSONAL, EXCLUSIONES_EMP),
    "hmo": (GRUPO_PERSONAL, ()),
    "hmores": (GRUPO_PERSONAL, ("tex",)),
    # B · contabilidad (F-056)
    "cua": (GRUPO_CONTABILIDAD, ()),
    "asi": (GRUPO_CONTABILIDAD, ()),
    "apu": (GRUPO_CONTABILIDAD, ("tex",)),
    "apa": (GRUPO_CONTABILIDAD, ("tex",)),
    # C · compras y proveedor (F-055, F-067)
    "conact": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "auxpronat": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "prvcer": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "prvobrpag": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "confir": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "deffir": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "dco": (GRUPO_COMPRAS, LISTA_ESTANDAR + EXTRA_DOCUMENTO),
    "dcopro": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "dcorec": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "dnc": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "dncpro": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "ctrrec": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "dcfrec": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "dcarec": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "auxpag": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "auxefp": (GRUPO_COMPRAS, LISTA_ESTANDAR),
    "conest": (GRUPO_COMPRAS, LISTA_ESTANDAR),
}

#: Las que ya estaban y esta feature NO puede tocar (R4): `raw.con` ya trae el
#: plan de cuentas (44.778 filas `tip = 16`), así que no hace falta añadir nada.
INTACTAS = ("con", "com", "comlin", "comprv", "ctr", "ctrpro", "pag")


@lru_cache(maxsize=1)
def _ingesta() -> dict[str, dict]:
    datos = yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))
    return {t["source_table"]: t for t in datos["tables"]}


@lru_cache(maxsize=1)
def _fichas() -> dict[str, dict]:
    return yaml.safe_load(FICHERO_RAW.read_text(encoding="utf-8"))["objetos"]


def _texto_ficha(nombre: str) -> str:
    ficha = _fichas()[nombre]
    return f"{ficha['descripcion']} {ficha.get('motivo_no_consumo', '') or ''}"


# ---------------------------------------------------------------------------
# R1 · el alta de las 25
# ---------------------------------------------------------------------------


def test_f066_r1_las_veinticinco_tablas_estan_dadas_de_alta() -> None:
    faltan = sorted(set(NUEVAS) - set(_ingesta()))
    assert faltan == [], f"no se ingieren todavía: {faltan}"


def test_f066_r1_la_ingesta_pasa_a_cincuenta_y_seis_tablas() -> None:
    """31 + 25. El número importa porque tres documentos lo citan (R13)."""
    assert len(_ingesta()) == TOTAL_TABLAS


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f066_r1_origen_y_destino_se_llaman_igual_y_en_minusculas(tabla: str) -> None:
    entrada = _ingesta()[tabla]
    assert entrada["source_table"] == entrada["target_table"] == tabla
    assert tabla == tabla.lower(), "el destino en Postgres va en minúsculas"


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f066_r1_la_clave_de_paginacion_es_ide(tabla: str) -> None:
    """Medido: las 25 tienen `ide`, y es el índice primario y único."""
    assert _ingesta()[tabla]["id_column"] == "ide"


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f066_r1_solo_declara_tiemod_la_tabla_que_lo_tiene(tabla: str) -> None:
    """Declarar una columna de corte que la tabla no tiene es una mentira que
    nadie ejecuta: la carga nocturna va con `--full` y no la mira."""
    esperado = "tiemod" if tabla in CON_TIEMOD else None
    assert _ingesta()[tabla]["incremental_column"] == esperado


# ---------------------------------------------------------------------------
# R2 · `apu` entera
# ---------------------------------------------------------------------------


def test_f066_r2_apu_se_trae_entera_sin_filtro() -> None:
    """2.154.543 filas (medido). Partir por empresa o por ejercicio ahorra
    ≤ 15 % y exige una subconsulta a `con` vía `asi` (DA-1)."""
    assert _ingesta()["apu"]["where"] is None


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f066_r2_ninguna_tabla_nueva_lleva_filtro(tabla: str) -> None:
    assert _ingesta()[tabla]["where"] is None


# ---------------------------------------------------------------------------
# R3 · las 19 vacías no entran
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", VACIAS_EN_SIGRID)
def test_f066_r3_una_tabla_vacia_en_sigrid_no_se_da_de_alta(tabla: str) -> None:
    declaradas = {t.lower() for t in _ingesta()}
    assert tabla.lower() not in declaradas, (
        f"`{tabla}` tenía 0 filas en Sigrid el 2026-09-06. Si hoy tiene datos, "
        f"quítala de VACIAS_EN_SIGRID con la cifra medida: reabrirla es una "
        f"decisión, no un descuido"
    )


def test_f066_r3_la_lista_de_vacias_son_diecinueve_y_sin_repetidas() -> None:
    """Control: si alguien vacía la constante, los 19 de arriba pasan en vacío."""
    assert len(VACIAS_EN_SIGRID) == 19
    assert len(set(VACIAS_EN_SIGRID)) == 19


# ---------------------------------------------------------------------------
# R4 · lo que ya estaba no se toca
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", INTACTAS)
def test_f066_r4_las_tablas_de_siempre_siguen_sin_filtro(tabla: str) -> None:
    """`raw.con` ya trae las 44.778 filas `tip = 16` del plan de cuentas: esta
    feature no añade un `where` que las dejaría fuera."""
    assert tabla in _ingesta(), f"`{tabla}` ha desaparecido de la ingesta"
    assert _ingesta()[tabla]["where"] is None


# ---------------------------------------------------------------------------
# R5, R6 · `emp` y `res`: solo exclusiones técnicas
# ---------------------------------------------------------------------------


def test_f066_r5_emp_excluye_exactamente_las_once_tecnicas() -> None:
    assert tuple(_ingesta()["emp"]["exclude_columns"]) == EXCLUSIONES_EMP


@pytest.mark.parametrize("columna", COLUMNAS_PERSONALES)
def test_f066_r5_ninguna_columna_personal_de_emp_esta_excluida(columna: str) -> None:
    """Decisión del humano del 2026-09-06 frente a la propuesta de excluir 72
    columnas: se trae todo y **se declara** en la ficha (DA-5)."""
    assert columna not in _ingesta()["emp"]["exclude_columns"]


def test_f066_r6_res_se_trae_entera() -> None:
    """55 columnas y ninguna binaria ni de texto ilimitado (medido)."""
    assert _ingesta()["res"]["exclude_columns"] == []


# ---------------------------------------------------------------------------
# R7 · las exclusiones de cada grupo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f066_r7_cada_tabla_nueva_excluye_lo_que_le_toca(tabla: str) -> None:
    _, esperadas = NUEVAS[tabla]
    assert tuple(_ingesta()[tabla]["exclude_columns"]) == esperadas


@pytest.mark.parametrize(
    "tabla", sorted(t for t, (g, _) in NUEVAS.items() if g == GRUPO_COMPRAS)
)
def test_f066_r7_las_de_compras_llevan_la_lista_estandar(tabla: str) -> None:
    excluidas = set(_ingesta()[tabla]["exclude_columns"])
    faltan = sorted(set(LISTA_ESTANDAR) - excluidas)
    assert faltan == [], f"a `{tabla}` le faltan de la lista estándar: {faltan}"


def test_f066_r7_dco_anade_las_ocho_de_documento() -> None:
    excluidas = set(_ingesta()["dco"]["exclude_columns"])
    assert set(EXTRA_DOCUMENTO) <= excluidas
    assert len(excluidas) == 21


# ---------------------------------------------------------------------------
# R8 · `dcf` recupera las condiciones de pago
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", ["dcf", "dco"])
@pytest.mark.parametrize("columna", ["pagtex", "pagfor"])
def test_f066_r8_las_condiciones_de_pago_del_documento_se_ingieren(
    tabla: str, columna: str
) -> None:
    """Estaban excluidas por tamaño, no por decisión de negocio, y son la
    carencia (4) del correo de Compras. Medido: `pagtex` viene informado en
    165.390 de las 165.391 facturas, con una media de 15,6 bytes."""
    assert columna not in _ingesta()[tabla]["exclude_columns"]


def test_f066_r8_dcf_baja_de_veintitres_exclusiones_a_veintiuna() -> None:
    assert len(_ingesta()["dcf"]["exclude_columns"]) == 21


def test_f066_r8_dca_no_cambia() -> None:
    """El albarán no entra en la decisión: sigue con sus 23."""
    assert len(_ingesta()["dca"]["exclude_columns"]) == 23


# ---------------------------------------------------------------------------
# R9 · el tamaño de página de las dos tablas de línea
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", PAGINA_CORTA)
def test_f066_r9_las_tablas_de_linea_bajan_el_tamano_de_pagina(tabla: str) -> None:
    """787.641 filas × 71 columnas y 286.432 × 73: mismo caso que `dcapro`."""
    assert _ingesta()[tabla].get("page_size") == 5000


@pytest.mark.parametrize("tabla", sorted(t for t in NUEVAS if t not in PAGINA_CORTA))
def test_f066_r9_las_demas_usan_el_tamano_global(tabla: str) -> None:
    assert "page_size" not in _ingesta()[tabla]


# ---------------------------------------------------------------------------
# R10, R11 · lo que las fichas tienen que decir
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f066_r10_cada_tabla_nueva_tiene_ficha_con_el_patron_de_rec(tabla: str) -> None:
    ficha = _fichas().get(tabla)
    assert ficha is not None, f"raw.{tabla} se ingiere y no tiene ficha"
    assert ficha["tipo"] == "tabla"
    assert ficha["capa"] == "origen"
    assert ficha["consumo_recomendado"] is False
    assert ficha["clave_negocio"] == ["ide"]
    assert ficha["paso_etl"] == "ingest_raw"
    assert ficha["refresco"] == "nocturno"
    assert ficha["columnas"] == {}, "DA-2: `raw` se documenta a nivel de objeto"
    assert (ficha.get("motivo_no_consumo") or "").strip(), (
        "una ficha que desaconseja el consumo sin decir por qué no desaconseja nada"
    )


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f066_r10_la_ficha_dice_que_de_noche_se_recarga_entera(tabla: str) -> None:
    assert "recarga entera" in _fichas()[tabla]["descripcion"]


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f066_r10_la_ficha_remite_al_diccionario_de_campos(tabla: str) -> None:
    texto = _texto_ficha(tabla)
    assert "azure-apps/sigrid_tablas.md" in texto
    assert tabla in texto, "el puntero tiene que decir qué bloque buscar allí"


#: Lo que la ficha de `emp` tiene que declarar que contiene (R11).
PERSONALES_DECLARADOS = ("DNI", "cuenta bancaria", "domicilio", "fecha de nacimiento")


@pytest.mark.parametrize("dato", PERSONALES_DECLARADOS)
def test_f066_r11_la_ficha_de_emp_declara_los_datos_personales(dato: str) -> None:
    """Se trae todo (DA-5), y por eso hay que decir qué es «todo»: `raw` lo lee
    entero cualquier agente conectado al MCP."""
    assert dato.lower() in _texto_ficha("emp").lower()


def test_f066_r11_la_ficha_de_res_declara_que_lleva_el_nif() -> None:
    texto = _texto_ficha("res").lower()
    assert "nif" in texto
    assert "cif" in texto, "hay que decir en qué columna está"


@pytest.mark.parametrize("tabla", ["emp", "res"])
def test_f066_r11_ninguna_columna_personal_se_cita_como_no_traida(tabla: str) -> None:
    """Decir que no se trae algo que sí se trae es peor que no decir nada."""
    texto = _texto_ficha(tabla)
    citadas: set[str] = set()
    for trozo in re.findall(r"No se traen[^.]*", texto, re.S):
        citadas |= set(re.findall(r"`(\w+)`", trozo))
    assert citadas & set(COLUMNAS_PERSONALES) == set()


def test_f066_r11_la_ficha_de_dcf_dice_veintiuna() -> None:
    texto = _fichas()["dcf"]["descripcion"]
    assert re.search(r"No se traen\W{0,4}21\b", texto), (
        "la ficha de `dcf` sigue diciendo 23: `pagtex` y `pagfor` ya se traen"
    )


# ---------------------------------------------------------------------------
# R13 · el número que tres documentos citan
# ---------------------------------------------------------------------------


def _numero_de_tablas_en_cabecera(texto: str) -> int | None:
    hallazgo = re.search(r"[Ss]on (\d+) tablas", texto)
    return int(hallazgo.group(1)) if hallazgo else None


def test_f066_r13_la_cabecera_de_raw_yaml_dice_las_tablas_que_hay() -> None:
    """El número se compara con `len(tables)`, no con una constante: así no se
    puede quedar viejo sin que este test lo diga."""
    declarado = _numero_de_tablas_en_cabecera(FICHERO_RAW.read_text(encoding="utf-8"))
    assert declarado == len(_ingesta())


@pytest.mark.parametrize(
    "fichero", [FICHERO_RAW, FICHERO_GLOBAL, FICHERO_PENDIENTES],
    ids=lambda p: p.name,
)
def test_f066_r13_ningun_documento_sigue_hablando_de_treinta_y_una(
    fichero: pathlib.Path,
) -> None:
    texto = fichero.read_text(encoding="utf-8")
    assert "31 tablas" not in texto, (
        f"{fichero.name} sigue diciendo «31 tablas» y son {TOTAL_TABLAS}"
    )
    assert "las 31 " not in texto


def test_f066_r13_la_regla_de_oro_cuenta_las_tablas_que_hay() -> None:
    assert f"{TOTAL_TABLAS} tablas" in FICHERO_GLOBAL.read_text(encoding="utf-8")


def test_f066_r13_la_version_del_diccionario_sube() -> None:
    """Cambiar `raw.yaml` sin subir la versión publica un diccionario que dice
    ser el mismo de ayer."""
    version = yaml.safe_load(FICHERO_GLOBAL.read_text(encoding="utf-8"))["version"]
    assert int(version) >= 14


# ---------------------------------------------------------------------------
# R14 · qué pregunta de compras responde cada una, y cuál NO
# ---------------------------------------------------------------------------


def test_f066_r14_la_ficha_de_confir_dice_que_no_hay_fecha_de_cambio_de_estado() -> None:
    """Es el hallazgo que manda a F-067 a construir el histórico por foto
    diaria: Sigrid no lo guarda, así que ningún `raw` lo puede traer."""
    assert "cambio de estado" in _texto_ficha("confir").lower()


def test_f066_r14_la_ficha_de_conest_dice_que_el_estado_se_traduce_por_tip() -> None:
    """La misma cifra significa cosas distintas en un contrato y en una
    factura: sin `tip`, un 7 se traduce mal y nadie se entera."""
    assert "por `tip`" in _texto_ficha("conest")


@pytest.mark.parametrize("tabla", ["confir", "conact", "dco", "ctrrec", "dcfrec"])
def test_f066_r14_las_fichas_de_compras_dicen_a_que_pregunta_responden(
    tabla: str,
) -> None:
    """No basta con describir la tabla: hay que decir para qué sirve y para qué
    no, que es lo que el correo de Compras preguntaba."""
    texto = _texto_ficha(tabla)
    assert "**No** responde" in texto, (
        f"la ficha de raw.{tabla} no dice qué pregunta NO responde"
    )
