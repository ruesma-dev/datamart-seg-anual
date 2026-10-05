# tests/test_f123_origenes.py
"""
F-123 · La regla de origenes del descompuesto, comprobada OFFLINE (R1-R21).

Decidido por el humano el 2026-10-02: Estudios es el master 0. Donde la obra
tiene version 0 del master con descompuesto, su origen pasa de llamarse
`MASTER_INICIAL` a `MASTER_ESTUDIO` y no se publica `ESTUDIO`; `ESTUDIO` (la
«Descomposicion» de la fase viva) sigue como hoy solo en las obras sin master 0.
Vista nueva `v_pbi_master_estudio` con las columnas de `v_pbi_estudio`.

Ningun test toca red ni base de datos: se fija el TEXTO del SQL (sin comentarios
`--`), el dominio, el diccionario y la documentacion. La regla contra datos se
contrasto en un PostgreSQL desechable (T8) y contra Azure es MANUAL (R22-R24).

Los nombres de los tests evitan a proposito las palabras clave de los `-k` de
las otras tareas de `tasks.md` (master, sello, estudio, cuadre...): cada `-k`
selecciona solo lo que su tarea ya ha escrito. Los helpers se copian de
`test_f097_descompuestos.py`: la suite de otra feature no es una API.
"""

from __future__ import annotations

import hashlib
import re
from functools import cache
from pathlib import Path

import pytest
import yaml

from etl_sigrid.domain.descompuestos import ESTADOS_CUADRE, ORIGENES

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DIR_DES = DIR_SQL / "descompuestos"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

COSTE = "02_lineas_coste.sql"
MASTER = "03_lineas_master.sql"
ELEMENTOS = "04_elementos.sql"
CUADRE = "05_cuadre.sql"
VISTAS = "06_views.sql"

#: Los cinco origenes de F-123, en el orden de la ficha (R6).
ORIGENES_F123 = ("ESTUDIO", "PLANIF_JO", "MASTER_ESTUDIO", "MASTER_PRE_ABC", "MASTER_PLANIF_JO")

#: El nombre que deja de existir (R5). Solo queda en el bloque de migracion.
ORIGEN_VIEJO = "MASTER_INICIAL"

#: El sello de produccion antes de F-123 (F-120, 2026-10-02): tiene que cambiar.
SELLO_DE_F120 = "7cad480aee614b2a"

#: Las 21 columnas de `v_pbi_estudio`, EN ORDEN (R13) y las de la vista nueva (R14).
COLUMNAS_VISTA_ESTUDIOS = [
    "obra_id", "partida_id", "presupuesto_id", "orden",
    "codigo_elemento", "descripcion", "unidad", "codigo_alternativo",
    "tipo_elemento_codigo", "tipo_elemento", "naturaleza_codigo", "naturaleza",
    "rendimiento", "precio", "importe_unitario", "cantidad_total", "importe_total",
    "es_porcentaje", "porcentaje", "base_porcentaje", "factor",
]

#: Las columnas de `descompuestos.elementos`, EN ORDEN: la renombrada en su sitio (R7).
COLUMNAS_ELEMENTOS = [
    "obra_id", "codigo_elemento", "descripcion", "unidad", "tipo_elemento",
    "num_lineas", "lineas_estudio", "lineas_planif_jo", "lineas_master_estudio",
    "lineas_master_pre_abc", "lineas_master_planif_jo", "producto_id", "via_producto",
]

#: Huellas del texto compacto (sin comentarios) de los trozos que F-123 NO toca,
#: tomadas de `main` (d4f58ea, F-120). Si una cambia, el cambio se salio del
#: alcance (R3, R8, R10): o se revierte o se justifica en la spec.
HUELLA_PLANIF_JO = "f55320200a6f8f4e"        # 02: el INSERT de PLANIF_JO entero
HUELLA_ESTUDIO_SELECT = "158954cd31dfcf4d"   # 02: las columnas del INSERT de ESTUDIO
HUELLA_ESTUDIO_WITH = "d79b1212acd034c7"     # 02: el troceado y `enlazadas`
HUELLA_CUADRE_COSTE = "20f367990493a455"     # 05: DELETE, h, s, su, INSERT y CASE

#: La condicion de «obra sin master 0» (design §3), con el alias de cada fichero.
SIN_MASTER_0 = ("NOT EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v "
                "WHERE v.obra_id = {alias}.obra_id AND v.fase_num = 0)")


@cache
def _crudo(nombre: str) -> str:
    ruta = DIR_DES / nombre
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _compactar(texto: str) -> str:
    sin_comentarios = "\n".join(linea.split("--", 1)[0] for linea in texto.splitlines())
    return re.sub(r"\s+", " ", sin_comentarios).strip()


@cache
def _sql(nombre: str) -> str:
    """El SQL sin comentarios `--` y con los blancos colapsados."""
    return _compactar(_crudo(nombre))


def _bloque(nombre: str, desde: str, hasta: str | None = None) -> str:
    texto = _sql(nombre)
    assert desde in texto, f"no encuentro «{desde}» en {nombre}"
    trozo = texto.split(desde, 1)[1]
    if hasta is not None:
        assert hasta in trozo, f"no encuentro «{hasta}» detras de «{desde}» en {nombre}"
        trozo = trozo.split(hasta, 1)[0]
    return trozo


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def _bloque_do() -> str:
    """El bloque `DO $$ ... END $$;` de la migracion de 02, compacto."""
    return "DO $$" + _bloque(COSTE, "DO $$", "END $$;") + "END $$;"


def _columnas_vista(vista: str) -> list[str]:
    cuerpo = _bloque(VISTAS, f"CREATE OR REPLACE VIEW descompuestos.{vista} AS SELECT ",
                     " FROM descompuestos.lineas")
    return [c.strip() for c in cuerpo.split(",")]


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def _ficha(objeto: str) -> dict:
    return _yaml("descompuestos.yaml")["objetos"][objeto]


def _texto(valor: object) -> str:
    return yaml.safe_dump(valor, allow_unicode=True, width=10_000)


# ===========================================================================
# R1 · R2 · R3 · el alcance
# ===========================================================================


#: Los SQL de fuera de `sql/descompuestos/` que SI leen el esquema, cada uno con
#: la feature que lo decidio. F-038 Fase 2 (2026-10-05): la base del coste
#: objetivo es el descompuesto de la primera ABC (D4); su design §8 lo declara
#: como el primer lector de fuera. Lee `origen`, `fase_num`, `es_primera_abc`,
#: `dncpro_id` y `precio` de `descompuestos.lineas`.
LECTORES_DE_FUERA = {"09_comparativos_detalle.sql"}


def test_f123_r1_nadie_fuera_del_esquema_lo_lee() -> None:
    """Ningun SQL fuera de `sql/descompuestos/` nombra el esquema salvo los
    lectores DECLARADOS: `stg`, `mart` y `cierre` no cambian porque no lo leen
    (comprobado el 2026-10-02). Un lector nuevo tiene que entrar en la lista."""
    fuera = [r for r in DIR_SQL.rglob("*.sql") if DIR_DES not in r.parents]
    assert fuera, "no encuentro los SQL de las otras capas"
    lectores = set()
    for ruta in fuera:
        texto = _compactar(ruta.read_text(encoding="utf-8"))
        if re.search(r"\bdescompuestos\.", texto):
            lectores.add(ruta.name)
    assert lectores == LECTORES_DE_FUERA, f"leen descompuestos: {sorted(lectores)}"


def test_f123_r2_el_estado_del_incremental_intacto() -> None:
    destruye = re.compile(
        r"(DELETE\s+FROM|DROP\s+TABLE(\s+IF\s+EXISTS)?|TRUNCATE(\s+TABLE)?)\s+"
        r"descompuestos\.(_des_texto|_versiones_cargadas)\b")
    for ruta in sorted(DIR_DES.glob("*.sql")):
        assert not destruye.search(_sql(ruta.name)), f"{ruta.name} destruye el estado (R2)"


def test_f123_r3_planif_jo_igual_que_en_f120() -> None:
    assert _huella(_bloque(COSTE, "SELECT 'PLANIF_JO'")) == HUELLA_PLANIF_JO
    assert "DELETE FROM descompuestos.lineas WHERE origen IN ('ESTUDIO', 'PLANIF_JO');" in _sql(COSTE)
    for vista, origen in (("v_pbi_planif_jo", "PLANIF_JO"),
                          ("v_pbi_master_planif_jo", "MASTER_PLANIF_JO")):
        cuerpo = _bloque(VISTAS, f"CREATE OR REPLACE VIEW descompuestos.{vista} AS", ";")
        assert f"FROM descompuestos.lineas WHERE origen = '{origen}'" in cuerpo, vista


# ===========================================================================
# R4 · R5 · R6 · R7 · el master 0 es Estudios
# ===========================================================================


def test_f123_r4_master_0_con_su_origen_nuevo() -> None:
    atributos = _bloque(MASTER, "CREATE TEMP TABLE _atributos", ";")
    assert ("CASE WHEN v.fase_num = 0 THEN 'MASTER_ESTUDIO' WHEN abc.fase_abc IS NOT NULL "
            "AND v.fase_num >= abc.fase_abc THEN 'MASTER_PLANIF_JO' ELSE 'MASTER_PRE_ABC' END "
            "AS origen") in atributos
    assert ("DELETE FROM descompuestos.lineas l USING _lote t WHERE l.ambito_id = 8 AND "
            "l.obra_id = t.obra_id AND l.fase_num = t.fase_num AND l.origen IN "
            "('MASTER_ESTUDIO', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO');") in _sql(MASTER)


def test_f123_r5_ningun_sql_nombra_el_origen_viejo() -> None:
    """Ni en el codigo ni en los comentarios, salvo dentro del bloque `DO` de la
    migracion, que es quien lo traduce (design §3)."""
    for ruta in sorted(DIR_DES.glob("*.sql")):
        crudo = _crudo(ruta.name)
        if ruta.name == COSTE:
            inicio = crudo.index("DO $$")
            fin = crudo.index("END $$;", inicio)
            assert ORIGEN_VIEJO in crudo[inicio:fin], "la migracion lo tiene que nombrar"
            crudo = crudo[:inicio] + crudo[fin:]
        assert ORIGEN_VIEJO not in crudo, f"{ruta.name} nombra {ORIGEN_VIEJO}"


def test_f123_r6_dominio_origenes_exactos() -> None:
    assert ORIGENES == ORIGENES_F123


def test_f123_r6_los_dos_check_son_los_origenes() -> None:
    lista = _lista(ORIGENES_F123)
    lineas = _bloque(COSTE, "CREATE TABLE IF NOT EXISTS descompuestos.lineas (", ");")
    cuadre = _bloque(COSTE, "CREATE TABLE IF NOT EXISTS descompuestos.cuadre_partida (", ");")
    assert f"CONSTRAINT ck_lineas_origen CHECK (origen IN ({lista}))" in lineas
    assert f"CONSTRAINT ck_cuadre_origen CHECK (origen IN ({lista}))" in cuadre
    assert "'F-097. Una fila por linea de descompuesto de cada partida, con su origen" in _sql(COSTE)
    assert "(ESTUDIO, PLANIF_JO, MASTER_ESTUDIO, MASTER_PRE_ABC, MASTER_PLANIF_JO)" in _sql(COSTE)


def test_f123_r7_elementos_columna_renombrada_en_su_sitio() -> None:
    texto = _sql(ELEMENTOS)
    assert "COUNT(*) FILTER (WHERE origen = 'MASTER_ESTUDIO') AS lineas_master_estudio" in texto
    assert "COUNT(*) FILTER (WHERE origen = 'ESTUDIO') AS lineas_estudio" in texto
    assert "a.lineas_master_estudio::INTEGER AS lineas_master_estudio" in texto
    final = _bloque(ELEMENTOS, "CREATE TABLE descompuestos.elementos AS", ";")
    ultimo_select = final[final.rindex("SELECT "):]
    columnas = re.findall(r" AS (\w+)(?:,| FROM)", ultimo_select)
    assert columnas == COLUMNAS_ELEMENTOS[2:]


# ===========================================================================
# R8 · R9 · R10 · R11 · R12 · ESTUDIO solo donde no hay master 0
# ===========================================================================


def test_f123_r8_estudio_igual_en_obras_sin_master_0() -> None:
    """Lo que se publica en una obra sin master 0 es lo de hoy: mismo troceado,
    mismo `enlazadas`, mismas columnas."""
    assert _huella(_bloque(COSTE, "WITH troceado AS (", "SELECT 'ESTUDIO'")) == HUELLA_ESTUDIO_WITH
    assert _huella(_bloque(COSTE, "SELECT 'ESTUDIO'", "WHERE NOT EXISTS")) == HUELLA_ESTUDIO_SELECT
    insert = _bloque(COSTE, "SELECT 'ESTUDIO'", ";")
    assert "NOT EXISTS (SELECT 1 FROM enlazadas e WHERE e.presupuesto_id = t.presupuesto_id)" in insert


def test_f123_r9_r11_estudio_excluye_las_obras_con_version_0() -> None:
    """Contra `_versiones_cargadas` y no contra `lineas`: 02 corre antes que 03
    (design §3). Con la condicion en el INSERT, R11 se cumple por construccion."""
    insert = _bloque(COSTE, "SELECT 'ESTUDIO'", ";")
    assert ("WHERE NOT EXISTS (SELECT 1 FROM enlazadas e WHERE e.presupuesto_id = t.presupuesto_id) "
            "AND " + SIN_MASTER_0.format(alias="t")) in insert
    assert "descompuestos.lineas" not in insert, "la obra con master 0 se decide por lo cargado"


def test_f123_r10_cuadre_de_la_fase_viva_por_obra() -> None:
    texto = _sql(CUADRE)
    assert _huella(_bloque(CUADRE, "DELETE FROM", "FROM h CROSS JOIN")) == HUELLA_CUADRE_COSTE
    assert "CROSS JOIN (VALUES ('ESTUDIO'), ('PLANIF_JO')) o(origen)" in texto
    assert texto.endswith(
        "LEFT JOIN su ON su.obra_id = h.obra_id AND su.partida_id = h.partida_id "
        "WHERE o.origen = 'PLANIF_JO' OR " + SIN_MASTER_0.format(alias="h") + ";")
    assert "THEN 'SUSTITUIDO_POR_PLANIFICACION'" in texto


def test_f123_r12_sin_objeto_ni_estado_nuevo() -> None:
    from etl_sigrid.domain.inventario import objetos_de_sql

    assert ESTADOS_CUADRE == ("CUADRA", "NO_CUADRA", "SIN_DESCOMPUESTO", "SUSTITUIDO_POR_PLANIFICACION")
    textos = {f"descompuestos/{f.name}": f.read_text(encoding="utf-8") for f in sorted(DIR_DES.glob("*.sql"))}
    declarados = {o.objeto for o in objetos_de_sql(textos)}
    assert declarados == {
        "_des_texto", "_versiones_cargadas", "lineas", "cuadre_partida", "elementos",
        "v_pbi_estudio", "v_pbi_planif_jo", "v_pbi_master_planif_jo", "v_pbi_master_estudio",
        "fn_num", "fn_fecha", "fn_trocear"}
    assert sorted(f.name for f in DIR_DES.glob("*.sql"))[-1] == VISTAS, "sin fichero 07"


# ===========================================================================
# R13 · R14 · el consumo
# ===========================================================================


def test_f123_r13_vistas_la_de_siempre_igual() -> None:
    assert _columnas_vista("v_pbi_estudio") == COLUMNAS_VISTA_ESTUDIOS
    cuerpo = _bloque(VISTAS, "CREATE OR REPLACE VIEW descompuestos.v_pbi_estudio AS", ";")
    assert cuerpo.endswith("FROM descompuestos.lineas WHERE origen = 'ESTUDIO'")


def test_f123_r14_vistas_la_nueva_con_las_mismas_columnas() -> None:
    from etl_sigrid.application.steps import build_descompuestos_step

    assert _columnas_vista("v_pbi_master_estudio") == COLUMNAS_VISTA_ESTUDIOS
    cuerpo = _bloque(VISTAS, "CREATE OR REPLACE VIEW descompuestos.v_pbi_master_estudio AS", ";")
    assert cuerpo.endswith("FROM descompuestos.lineas WHERE origen = 'MASTER_ESTUDIO'")
    assert _sql(VISTAS).count("CREATE OR REPLACE VIEW") == 4
    assert _sql(VISTAS).rindex("v_pbi_master_estudio") > _sql(VISTAS).rindex("v_pbi_master_planif_jo"), (
        "la vista nueva va al final"
    )
    assert "las cuatro vistas" in _crudo(VISTAS)
    assert "v_pbi_master_estudio" in (build_descompuestos_step.__doc__ or "")


# ===========================================================================
# R15 · R16 · R17 · la migracion de lo ya cargado
# ===========================================================================


@pytest.mark.parametrize(("tabla", "restriccion"), [("lineas", "ck_lineas_origen"),
                                                    ("cuadre_partida", "ck_cuadre_origen")])
def test_f123_r15_migracion_de_cada_tabla(tabla: str, restriccion: str) -> None:
    bloque = _bloque_do()
    guarda = (f"IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{restriccion}' "
              f"AND conrelid = 'descompuestos.{tabla}'::regclass "
              f"AND pg_get_constraintdef(oid) LIKE '%{ORIGEN_VIEJO}%') THEN "
              f"ALTER TABLE descompuestos.{tabla} DROP CONSTRAINT {restriccion}; "
              f"UPDATE descompuestos.{tabla} SET origen = 'MASTER_ESTUDIO' WHERE origen = '{ORIGEN_VIEJO}'; "
              f"ALTER TABLE descompuestos.{tabla} ADD CONSTRAINT {restriccion} CHECK (origen IN "
              f"({_lista(ORIGENES_F123)})); END IF;")
    assert guarda in bloque, f"la migracion de {tabla} no es la del diseno"


def test_f123_r15_migracion_antes_del_primer_insert_y_sin_destruir() -> None:
    texto = _sql(COSTE)
    do = texto.index("DO $$")
    assert texto.index("CREATE TABLE IF NOT EXISTS descompuestos.cuadre_partida") < do
    assert do < texto.index("DELETE FROM descompuestos.lineas")
    assert do < texto.index("INSERT INTO")
    assert texto.count("DO $$") == 1
    assert not re.search(r"(DROP\s+TABLE|TRUNCATE)[^;]*(lineas|cuadre_partida)", texto)


def test_f123_r16_migracion_idempotente() -> None:
    """Cada tabla con su guarda: la segunda vez el `CHECK` ya no nombra el origen
    viejo y el bloque no hace nada (ni `DROP CONSTRAINT` ni `UPDATE`)."""
    bloque = _bloque_do()
    ramas = bloque.split("END IF;")[:-1]
    assert len(ramas) == 2
    for rama in ramas:
        antes, _, despues = rama.partition(" THEN ")
        assert f"LIKE '%{ORIGEN_VIEJO}%'" in antes and "IF EXISTS (" in antes
        assert "DROP CONSTRAINT" in despues and "UPDATE" in despues
    assert "DROP CONSTRAINT" not in bloque.split(" THEN ")[0]


def test_f123_r17_el_sello_cambia_sin_releer() -> None:
    from etl_sigrid.application.steps.build_descompuestos_step import sello_de_troceado

    assert sello_de_troceado() != SELLO_DE_F120, "el literal vive en 03: el sello tiene que cambiar"
    for ruta in sorted(DIR_DES.glob("*.sql")):
        assert not re.search(r"(INSERT INTO|UPDATE|DELETE FROM|TRUNCATE)\s+descompuestos\._des_texto",
                             _sql(ruta.name)), ruta.name


# ===========================================================================
# R18 · R19 · R20 · el diccionario
# ===========================================================================


def test_f123_r18_diccionario_version_40() -> None:
    assert _yaml("00_global.yaml")["version"] >= 40, "F-113 la sube a 41"


def test_f123_r19_diccionario_la_regla_explica_la_fase_viva() -> None:
    reglas = {r["codigo"]: r for r in _yaml("00_global.yaml")["reglas"]}
    assert "R-FASE-VIVA" not in reglas, "D1: dentro de R-DESCOMPUESTO-ORIGEN, sin regla nueva"
    regla = reglas["R-DESCOMPUESTO-ORIGEN"]
    texto = regla["regla"] + " " + regla["motivo"]
    for termino in ("FASE VIVA", "jefe de obra", "planificacion de compras", "PLANIF_JO",
                    "MASTER_ESTUDIO", "ESTUDIO", "master 0", "sin master 0"):
        assert termino in texto, f"R-DESCOMPUESTO-ORIGEN no dice «{termino}»"
    assert ORIGEN_VIEJO not in texto
    assert "descompuestos.v_pbi_master_estudio" in regla["ambito"]


def test_f123_r20_diccionario_esquema_y_fichas() -> None:
    glob = _yaml("00_global.yaml")
    esquema = glob["esquemas"]["descompuestos"]["para_que_sirve"]
    for termino in ("MASTER_ESTUDIO", "master 0", "v_pbi_master_estudio"):
        assert termino in esquema, termino
    assert ORIGEN_VIEJO not in _texto(glob), "lo publicado, sin la cabecera"
    assert ORIGEN_VIEJO not in (DIR_DICCIONARIO / "descompuestos.yaml").read_text(encoding="utf-8")
    for objeto in ("lineas", "cuadre_partida"):
        assert _ficha(objeto)["columnas"]["origen"]["valores"] == list(ORIGENES_F123), objeto
    assert "lineas_master_estudio" in _ficha("elementos")["columnas"]
    assert list(_ficha("elementos")["columnas"]) == COLUMNAS_ELEMENTOS
    for objeto in ("lineas", "cuadre_partida", "v_pbi_estudio"):
        texto = _texto(_ficha(objeto))
        for termino in ("MASTER_ESTUDIO", "sin master 0", "medicion ACTUAL", "0726", "134,35"):
            assert termino in texto, f"{objeto}: falta «{termino}»"


def test_f123_r20_diccionario_ficha_de_la_vista_nueva() -> None:
    nueva = _ficha("v_pbi_master_estudio")
    assert nueva["tipo"] == "vista" and nueva["consumo_recomendado"] is True
    assert nueva["paso_etl"] == "build_descompuestos"
    assert list(nueva["columnas"]) == COLUMNAS_VISTA_ESTUDIOS
    assert list(_ficha("v_pbi_estudio")["columnas"]) == COLUMNAS_VISTA_ESTUDIOS
    assert nueva["clave_negocio"] == ["obra_id", "partida_id", "orden"]
    texto = _texto(nueva)
    for termino in ("MASTER_ESTUDIO", "v_pbi_estudio", "master 0"):
        assert termino in texto, termino
    assert "v_pbi_master_estudio" in _texto(_ficha("v_pbi_estudio"))


# ===========================================================================
# R21 · la documentacion
# ===========================================================================


def test_f123_r21_docs_arquitectura() -> None:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for termino in ("`MASTER_ESTUDIO`", "v_pbi_master_estudio", "master 0", "fase viva"):
        assert termino in texto, f"ARCHITECTURE.md no dice «{termino}»"
    assert ORIGEN_VIEJO not in texto


def test_f123_r21_docs_ayuda_de_build() -> None:
    import main

    comando = main.cli.commands["build-descompuestos"]
    ayuda = (comando.callback.__doc__ or "") + " ".join(o.help or "" for o in comando.params)
    for termino in ("MASTER_ESTUDIO", "cuatro vistas", "master 0"):
        assert termino in ayuda, f"la ayuda de build-descompuestos no dice «{termino}»"
    assert ORIGEN_VIEJO not in ayuda and "tres vistas" not in ayuda


def test_f123_r21_docs_azure_apps() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for termino in ("F-123", "MASTER_ESTUDIO", "v_pbi_master_estudio", "master 0"):
        assert termino in texto, f"azure-apps no dice «{termino}»"


def test_f123_un_test_por_requisito() -> None:
    """R1-R21 con al menos un test (R22-R24 son verificacion MANUAL)."""
    nombres = [n for n in globals() if n.startswith("test_f123_r")]
    for n in range(1, 22):
        assert any(re.match(rf"test_f123_(r\d+_)*r{n}_", x) for x in nombres), f"R{n} sin test"
