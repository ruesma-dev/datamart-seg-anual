# tests/test_f074_ingesta_censo.py
"""
F-074 · Las nueve tablas que destapo el censo de F-072, los dos arreglos que
viajan en el mismo fichero y la limpieza de `obrprv`.

Aqui no se abre ninguna conexion. Las tres fuentes que gobiernan los hechos que
se comprueban son:

* `config/tables_sigrid.yaml` — que se ingiere y con que exclusiones;
* `config/diccionario/raw.yaml` — que se publica de ello;
* `config/settings.py` mas `infra/sql/02_roles.sql` — que puede leer el rol del
  MCP (el mecanismo de F-068).

Las cifras que aparecen en los mensajes se **midieron contra Sigrid el
2026-09-09** por `sigrid-api` en solo lectura (`INFORMATION_SCHEMA.COLUMNS` y
`COUNT(*)`), y estan en `progress/explore_F-074_las_nueve.md`.

EL HECHO QUE MANDA SOBRE LA CARGA, y que esta feature NO decide porque ya estaba
decidido: **el job nocturno arranca `run-all --full`** (`CMD` del `Dockerfile`),
y eso es `TRUNCATE` + recarga entera de TODAS las tablas. `incremental_column`
no es un interruptor de modo de carga: solo decide si `copy_rows` rellena
`_source_tiemod` (`ingest_raw_step.py:279`). Por eso «esta tabla no tiene
`tiemod`» NO significa «lo modificado no vuelve a bajar»: significa que la fila
de `raw` no lleva sello de origen. Es el error exacto de la octava pasada de
F-006, y por eso `tests/test_f006_fuente_que_gobierna.py` existe.
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

#: Cuantas tablas ingiere el ETL cuando esta feature cierra: 56 + 9.
TOTAL_TABLAS = 68

#: Las tres que SI tienen `tiemod`, comprobado en `INFORMATION_SCHEMA` y
#: poblado al 100 % en las tres (7/7, 60/60 y 37/37).
CON_TIEMOD = ("auxdpt", "auxhor", "auxrestip")

#: Las seis que NO tienen ninguna columna de tipo fecha. Lo que parece fecha
#: (`fec`, `fecalt`, `fecult`, `fecultact`) es un entero AAAAMMDD.
SIN_TIEMOD = ("cet", "pro", "reshor", "emphis", "dcaprodes", "ctrprodes")

#: Las nueve altas con su recuento medido y sus exclusiones.
NUEVAS: dict[str, tuple[int, tuple[str, ...]]] = {
    "auxdpt": (7, ()),
    "auxhor": (60, ()),
    "auxrestip": (37, ()),
    "cet": (40, ("repnom", "repno1", "repap1", "repap2", "repdni", "repcar", "dirtex")),
    "pro": (55_179, ("esigurl1", "esigurl2", "esigpromt", "carprotex")),
    "reshor": (8_949, ()),
    "emphis": (1_633, ("notas",)),
    "dcaprodes": (850_985, ()),
    "ctrprodes": (424_475, ()),
}

#: Datos de nomina: fuera del alcance del rol del MCP, como `emp` y `res`.
DE_NOMINA = ("reshor", "emphis")

#: Las tres que declaraban `incremental_column: tiemod` sin tener la columna.
MENTIAN_TIEMOD = ("com", "comlin", "comprv")


@lru_cache(maxsize=1)
def _crudo() -> dict:
    return yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _ingesta() -> dict[str, dict]:
    return {t["source_table"]: t for t in _crudo()["tables"]}


@lru_cache(maxsize=1)
def _fichas() -> dict[str, dict]:
    return yaml.safe_load(FICHERO_RAW.read_text(encoding="utf-8"))["objetos"]


def _texto_ficha(nombre: str) -> str:
    ficha = _fichas()[nombre]
    return f"{ficha['descripcion']} {ficha.get('motivo_no_consumo', '') or ''}"


@lru_cache(maxsize=1)
def _bloques_yaml() -> dict[str, str]:
    """El texto crudo de cada entrada del YAML, comentarios incluidos.

    Se lee el fichero como TEXTO y no como YAML a proposito: lo que este
    fichero comprueba en varios sitios es que la decision quede escrita **en el
    comentario**, y `yaml.safe_load` tira los comentarios. El bloque de una
    tabla va desde su `- source_table:` hasta el siguiente (o el fin).
    """
    texto = FICHERO_TABLAS.read_text(encoding="utf-8")
    cortes = [m for m in re.finditer(r"^  - source_table:\s*(\w+)", texto, re.M)]
    bloques: dict[str, str] = {}
    for i, m in enumerate(cortes):
        fin = cortes[i + 1].start() if i + 1 < len(cortes) else len(texto)
        bloques[m.group(1)] = texto[m.start():fin]
    return bloques


# ---------------------------------------------------------------------------
# A1 · las nueve estan declaradas y la nocturna las trae
# ---------------------------------------------------------------------------


def test_f074_r1_las_nueve_tablas_estan_dadas_de_alta() -> None:
    faltan = sorted(set(NUEVAS) - set(_ingesta()))
    assert faltan == [], f"no se ingieren todavia: {faltan}"


def test_f074_r1_la_ingesta_pasa_a_sesenta_y_cinco_tablas() -> None:
    """56 + 9. El numero importa porque cuatro documentos lo citan."""
    assert len(_ingesta()) == TOTAL_TABLAS


def test_f074_r1_ninguna_tabla_esta_declarada_dos_veces() -> None:
    """La leccion de F-066: el YAML llego a tener 17 entradas repetidas y
    ningun test lo vio, porque todos leian la ingesta como un `dict` y eso
    colapsa duplicados. Esta comprobacion lee la LISTA."""
    nombres = [t["source_table"] for t in _crudo()["tables"]]
    repetidas = sorted({n for n in nombres if nombres.count(n) > 1})
    assert repetidas == [], (
        f"declaradas dos veces: {repetidas}. Con `run-all --full` la tabla se "
        f"truncaria y recargaria dos veces por noche, sin decir nada"
    )


def test_f074_r1_la_lista_del_yaml_y_el_diccionario_tienen_lo_mismo() -> None:
    """Control del anterior: si discrepan, hay duplicados."""
    assert len(_crudo()["tables"]) == len(_ingesta()) == TOTAL_TABLAS


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f074_r1_origen_y_destino_se_llaman_igual_y_en_minusculas(tabla: str) -> None:
    entrada = _ingesta()[tabla]
    assert entrada["source_table"] == entrada["target_table"] == tabla
    assert tabla == tabla.lower()


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f074_r1_la_clave_de_paginacion_es_ide(tabla: str) -> None:
    """Medido: las nueve tienen `ide`, y `COUNT(*) = COUNT(DISTINCT ide)`."""
    assert _ingesta()[tabla]["id_column"] == "ide"


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f074_r1_ninguna_de_las_nueve_lleva_filtro(tabla: str) -> None:
    assert _ingesta()[tabla]["where"] is None


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f074_r1_ninguna_fija_su_propio_tamano_de_pagina(tabla: str) -> None:
    """`SIGRID_API_PAGE_SIZE` ya vale 10.000, que es lo que la exploracion
    proponia escribir a mano en las dos grandes. Fijarlo aqui no cambiaria
    nada hoy y las dejaria pinchadas en 10.000 el dia que haya que bajar el
    global porque la pasarela recorte su `MAX_ALLOWED_ROWS`."""
    assert "page_size" not in _ingesta()[tabla]


# ---------------------------------------------------------------------------
# A2 · nada se declara de oido: la columna incremental, medida
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f074_r2_solo_declara_tiemod_la_tabla_que_lo_tiene(tabla: str) -> None:
    """Declarar una columna que la tabla no tiene no rompe la ingesta: el paso
    la degrada a `None` en silencio (`ingest_raw_step.py:279`). Por eso hay que
    comprobarlo aqui, donde si se ve."""
    esperado = "tiemod" if tabla in CON_TIEMOD else None
    assert _ingesta()[tabla]["incremental_column"] == esperado


def test_f074_r2_las_tres_con_tiemod_y_las_seis_sin_el_suman_nueve() -> None:
    """Control: si alguien vacia una de las dos constantes, los tests de arriba
    seguirian pasando sobre la mitad de las tablas."""
    assert set(CON_TIEMOD) | set(SIN_TIEMOD) == set(NUEVAS)
    assert set(CON_TIEMOD) & set(SIN_TIEMOD) == set()


@pytest.mark.parametrize("tabla", sorted(SIN_TIEMOD))
def test_f074_r2_el_yaml_explica_por_que_esa_tabla_no_es_incremental(
    tabla: str,
) -> None:
    """Lo que se decide se escribe DONDE se lee, no solo en el informe: quien
    abra este fichero dentro de un año tiene que ver por que hay un `null` ahi
    y que se comprobo antes de ponerlo."""
    bloque = _bloques_yaml()[tabla]
    assert "VERIFICADO" in bloque, (
        f"`{tabla}` declara `incremental_column: null` y el YAML no dice que se "
        f"comprobo contra Sigrid: un `null` sin motivo es indistinguible de un "
        f"descuido"
    )


def test_f074_r2_la_bandera_full_de_run_all_es_un_flag_booleano() -> None:
    """El ancla de TODO el razonamiento de carga de esta feature.

    La decision de F-074 --las seis sin `tiemod` no abren ningun agujero-- se
    apoya en que el job nocturno arranque `run-all --full` y en que eso sea una
    bandera que se activa por presencia. Si `--full` dejara de ser un flag, el
    `CMD` del `Dockerfile` --que la pasa desnuda, sin valor-- se romperia o
    dejaria de significar lo que significa, y las seis tablas SI quedarian
    congeladas.

    `test_f006_r13_el_cli_declara_full_y_no_full_refresh` comprueba que la
    opcion EXISTE, leyendo `main.py` con una expresion regular. No comprueba
    QUE ES: lo caza la campaña de mutacion de esta feature, donde
    `is_flag=True -> is_flag=False` sobrevivio. Esto lo cierra preguntandoselo
    a click, no al texto del fichero.
    """
    from main import cli

    opcion = next(
        p for p in cli.commands["run-all"].params if "--full" in getattr(p, "opts", [])
    )
    assert opcion.is_flag is True, (
        "`--full` ha dejado de ser una bandera: el `CMD` del Dockerfile la pasa "
        "sin valor y la nocturna dejaria de hacer recarga completa"
    )
    assert opcion.default is False, "el defecto de `run-all` no es full, y no debe serlo"
    assert opcion.name == "full_refresh"


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f074_r2_el_yaml_anota_el_recuento_medido_de_cada_tabla(tabla: str) -> None:
    """A1 pide el tamaño real «medido y anotado». Se anota en el fichero que
    gobierna la ingesta, no en un informe que nadie vuelve a abrir."""
    filas, _ = NUEVAS[tabla]
    bloque = _bloques_yaml()[tabla]
    formas = (f"{filas:,}".replace(",", "."), str(filas))
    assert any(f in bloque for f in formas), (
        f"el bloque de `{tabla}` no anota sus {filas} filas medidas: {formas}"
    )


# ---------------------------------------------------------------------------
# A3 · `reshor` y `emphis`, fuera del alcance del rol del MCP (F-068)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", DE_NOMINA)
def test_f074_r3_las_dos_de_nomina_estan_en_la_lista_de_exclusion(tabla: str) -> None:
    """`reshor` es el precio/hora por recurso y `emphis` el historico de
    contrato de 1.017 empleados. El rol `mcp_sigrid_dm_ro` lo lee cualquier
    cuenta del tenant, asi que entran por donde entraron `emp` y `res`."""
    from config.settings import DEFAULT_EXCLUDED_TABLES

    declaradas = [t.strip() for t in DEFAULT_EXCLUDED_TABLES.split(",") if t.strip()]
    assert f"raw.{tabla}" in declaradas, (
        f"raw.{tabla} son datos de nomina y `apply_grants` le concede SELECT "
        f"cada noche con `GRANT SELECT ON ALL TABLES IN SCHEMA raw`"
    )


def test_f074_r3_la_lista_de_exclusion_son_exactamente_cuatro() -> None:
    """Las dos de F-068 y las dos de F-074, ni una mas: excluir de mas deja
    ciega a la IA sobre datos que si puede ver."""
    from config.settings import DEFAULT_EXCLUDED_TABLES

    declaradas = [t.strip() for t in DEFAULT_EXCLUDED_TABLES.split(",") if t.strip()]
    assert declaradas == ["raw.emp", "raw.res", "raw.reshor", "raw.emphis"]


@pytest.mark.parametrize("tabla", DE_NOMINA)
def test_f074_r3_el_revoke_se_emite_de_verdad_para_esa_tabla(tabla: str) -> None:
    """No basta con declararla en la lista: hay que ver la sentencia.

    F-068 existe porque `ALTER DEFAULT PRIVILEGES` reponia el permiso en
    silencio, asi que aqui se comprueban las DOS mitades: el `REVOKE` de la
    tabla, DESPUES del `GRANT` del esquema que se lo acaba de dar, y que el
    esquema `raw` no recupere su regla de catalogo.
    """
    from config.settings import DEFAULT_EXCLUDED_TABLES
    from etl_sigrid.infrastructure.postgres.grants import (
        build_readonly_grant_statements,
    )

    rol, dueno = "mcp_sigrid_dm_ro", "sigrid_dm_etl"
    excluidas = [t.strip() for t in DEFAULT_EXCLUDED_TABLES.split(",") if t.strip()]
    sentencias = build_readonly_grant_statements(
        rol, dueno, ["mart", "raw", "stg"], excluded_tables=excluidas
    )

    revoke = f'REVOKE ALL PRIVILEGES ON TABLE "raw"."{tabla}" FROM "{rol}"'
    assert revoke in sentencias, f"raw.{tabla} no pierde el SELECT del MCP"

    posicion_grant = next(
        i for i, s in enumerate(sentencias)
        if 'GRANT SELECT ON ALL TABLES IN SCHEMA "raw"' in s
    )
    assert sentencias.index(revoke) > posicion_grant, (
        "el REVOKE se emite ANTES del GRANT del esquema, que lo pisaria"
    )

    prohibida = (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{dueno}" IN SCHEMA "raw" '
        f'GRANT SELECT ON TABLES TO "{rol}"'
    )
    assert prohibida not in sentencias


@pytest.mark.parametrize("tabla", DE_NOMINA)
def test_f074_r3_el_revoke_sobrevive_a_que_la_tabla_no_exista_aun(tabla: str) -> None:
    """El caso REAL de esta feature, y es el agujero que cazo el review de
    F-068: `raw.reshor` y `raw.emphis` **todavia no existen** en Azure, porque
    esta ingesta no se ha desplegado. Si la regla del catalogo dependiera de
    que la tabla exista hoy, la noche del estreno las crearia legibles.
    """
    from config.settings import DEFAULT_EXCLUDED_TABLES
    from etl_sigrid.infrastructure.postgres.grants import (
        build_readonly_grant_statements,
    )

    rol, dueno = "mcp_sigrid_dm_ro", "sigrid_dm_etl"
    excluidas = [t.strip() for t in DEFAULT_EXCLUDED_TABLES.split(",") if t.strip()]
    sentencias = build_readonly_grant_statements(
        rol, dueno, ["mart", "raw", "stg"],
        excluded_tables=excluidas,
        missing_tables=[f"raw.{tabla}"],
    )

    esperada = (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{dueno}" IN SCHEMA "raw" '
        f'REVOKE SELECT ON TABLES FROM "{rol}"'
    )
    assert esperada in sentencias, (
        f"con raw.{tabla} ausente se deja de revocar el privilegio por defecto "
        f"de `raw`: la tabla naceria legible la noche que se ingiera"
    )
    assert not any(f'"raw"."{tabla}"' in s for s in sentencias), (
        "se intenta revocar sobre una tabla que no existe: eso da error y "
        "tumbaria el paso"
    )


def test_f074_r3_el_sql_de_provision_excluye_lo_mismo_que_el_codigo() -> None:
    """`02_roles.sql` es lo que se aplica al crear el rol DESDE CERO. Si dijera
    otra cosa, un rol recien provisionado naceria con la nomina legible."""
    from config.settings import DEFAULT_EXCLUDED_TABLES

    sql = (RAIZ / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")
    declaradas = {t.strip() for t in DEFAULT_EXCLUDED_TABLES.split(",") if t.strip()}
    assert set(re.findall(r"'(raw\.[a-z_]+)'", sql)) == declaradas


@pytest.mark.parametrize("tabla", DE_NOMINA)
def test_f074_r3_la_ficha_avisa_de_que_el_mcp_no_la_lee(tabla: str) -> None:
    """Quien lea el diccionario tiene que saber por que esa tabla no responde,
    o lo tomara por un fallo y buscara un rodeo."""
    texto = _texto_ficha(tabla)
    assert "F-068" in texto, f"la ficha de raw.{tabla} no cita el mecanismo"
    assert "nomina" in texto.lower()


# ---------------------------------------------------------------------------
# A5 · cada tabla nueva, con ficha escrita
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f074_r5_cada_tabla_nueva_tiene_ficha_con_el_patron_de_raw(tabla: str) -> None:
    ficha = _fichas().get(tabla)
    assert ficha is not None, f"raw.{tabla} se ingiere y no tiene ficha"
    assert ficha["tipo"] == "tabla"
    assert ficha["capa"] == "origen"
    assert ficha["consumo_recomendado"] is False
    assert ficha["clave_negocio"] == ["ide"]
    assert ficha["paso_etl"] == "ingest_raw"
    assert ficha["refresco"] == "nocturno"
    assert ficha["columnas"] == {}, "`raw` se documenta a nivel de objeto (DA-2)"
    assert (ficha.get("motivo_no_consumo") or "").strip()


@pytest.mark.parametrize("tabla", sorted(NUEVAS))
def test_f074_r5_la_ficha_anota_el_recuento_medido(tabla: str) -> None:
    filas, _ = NUEVAS[tabla]
    texto = _texto_ficha(tabla)
    formas = (f"{filas:,}".replace(",", "."), str(filas))
    assert any(f in texto for f in formas), (
        f"la ficha de raw.{tabla} no dice cuantas filas tiene: {formas}"
    )


def test_f074_r5_ninguna_de_las_nueve_se_aplaza_como_pendiente() -> None:
    """El trinquete de `pendientes` esta a cero y SOLO BAJA: aplazar nueve
    fichas de golpe dejaria el techo donde nadie lo volveria a apretar."""
    datos = yaml.safe_load(FICHERO_GLOBAL.read_text(encoding="utf-8")) or {}
    declarados = [str(o).strip().lower() for o in (datos.get("pendientes") or [])]
    aplazadas = [o for o in declarados if o.removeprefix("raw.") in NUEVAS]
    assert aplazadas == [], f"fichas de F-074 aplazadas en el trinquete: {aplazadas}"


# ---------------------------------------------------------------------------
# A6 · la declaracion falsa de `tiemod` en `com`, `comlin` y `comprv`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", MENTIAN_TIEMOD)
def test_f074_r6_ya_no_declaran_una_columna_que_no_existe(tabla: str) -> None:
    """`tiemod` NO existe en estas tres (error 42S22 contra
    `INFORMATION_SCHEMA`) y `_source_tiemod` esta a NULL en sus 287.673 filas.
    Quitarlo no cambia el comportamiento: lo hace visible."""
    assert _ingesta()[tabla]["incremental_column"] is None, (
        f"`{tabla}` sigue declarando una columna de corte que Sigrid no tiene; "
        f"el paso la degrada en silencio y la mentira sobrevive"
    )


@pytest.mark.parametrize("tabla", MENTIAN_TIEMOD)
def test_f074_r6_el_yaml_deja_escrito_que_se_midio(tabla: str) -> None:
    assert "VERIFICADO" in _bloques_yaml()[tabla], (
        f"`{tabla}` pasa a `null` sin decir por que: el siguiente que lea el "
        f"fichero volvera a poner `tiemod` de memoria"
    )


@pytest.mark.parametrize("tabla", MENTIAN_TIEMOD)
def test_f074_r6_las_tres_siguen_ingeriendose_y_sin_filtro(tabla: str) -> None:
    """El arreglo es de la declaracion, no del alcance: no se cae ninguna."""
    assert tabla in _ingesta()
    assert _ingesta()[tabla]["where"] is None


def test_f074_r6_ninguna_tabla_declara_tiemod_sin_haberlo_medido() -> None:
    """El barrido, que es lo que evita que esto vuelva a pasar en otra tabla.

    Las que declaran `tiemod` a fecha de hoy son las que se midieron: las de
    siempre mas las tres de F-066 y las tres de F-074. Ampliar la lista exige
    medir la columna primero, que es exactamente el punto.
    """
    declarantes = {
        t for t, cfg in _ingesta().items() if cfg.get("incremental_column") == "tiemod"
    }
    assert declarantes & set(MENTIAN_TIEMOD) == set()
    assert set(CON_TIEMOD) <= declarantes


# ---------------------------------------------------------------------------
# A7 · `prvcer` deja de excluir `tex`
# ---------------------------------------------------------------------------


def test_f074_r7_prvcer_ya_no_excluye_tex() -> None:
    """`tex` es el UNICO campo que dice de que es cada certificado: la tabla no
    tiene campo de tipo. Estaba excluido por la lista estandar del modulo
    COMPRAS, que se aplica a bulto, no por una decision sobre esta tabla."""
    assert "tex" not in _ingesta()["prvcer"]["exclude_columns"]


def test_f074_r7_prvcer_conserva_las_otras_doce_exclusiones() -> None:
    """Se recupera un campo, no se abre la tabla entera."""
    assert len(_ingesta()["prvcer"]["exclude_columns"]) == 12


def test_f074_r7_la_ficha_de_prvcer_dice_doce_y_no_trece() -> None:
    texto = _fichas()["prvcer"]["descripcion"]
    assert re.search(r"No se traen\W{0,4}12\b", texto), (
        "la ficha de `prvcer` sigue diciendo 13: `tex` ya se trae"
    )


def test_f074_r7_ninguna_otra_tabla_de_compras_pierde_su_exclusion() -> None:
    """Control del alcance: la lista estandar sigue completa en las demas.

    `prvcer` es la unica excepcion y lo es por un motivo medido. Si mañana
    alguien recorta otra, este test lo dice.
    """
    estandar = {
        "tex", "med", "des", "obs", "ima", "emptex", "dirtex", "eiotex",
        "desesp", "texcom", "serdesdat", "texobs", "coestr",
    }
    for tabla in ("conact", "prvobrpag", "confir", "deffir", "dcorec", "conest"):
        faltan = sorted(estandar - set(_ingesta()[tabla]["exclude_columns"]))
        assert faltan == [], f"a `{tabla}` le faltan de la lista estandar: {faltan}"


# ---------------------------------------------------------------------------
# A8 · que se hace con `obrprv`, que tiene 0 filas en el origen
# ---------------------------------------------------------------------------


def test_f074_r8_obrprv_se_queda_en_la_ingesta() -> None:
    """DECISION: se queda. No es gratis por descuido, es barato a proposito.

    Tiene 0 filas en Sigrid y 0 en `raw`, asi que la noche le cuesta UNA
    peticion HTTP que devuelve cero filas. A cambio es el canario: dos ficheros
    de `sql/maestro/` construyen el vinculo obra-proveedor POR OTRA VIA
    justamente porque esta vacia, y `check-raw-recuentos` es lo unico que
    diria que ha dejado de estarlo. Sacarla de aqui convierte un hecho vigilado
    en una suposicion de 2026.

    No contradice la regla R3 de F-066 —una tabla vacia no se DA DE ALTA—:
    aquella evita construir sobre la nada con tablas nuevas; esta ya esta de
    alta, ya tiene ficha y ya tiene dos SQL que dependen de su vacio.
    """
    assert "obrprv" in _ingesta()


def test_f074_r8_el_yaml_deja_escrito_el_motivo_de_que_se_quede() -> None:
    """A8 pide la decision «con el motivo escrito», y el sitio donde se lee es
    el fichero que la ejecuta."""
    bloque = _bloques_yaml()["obrprv"]
    assert "F-074" in bloque, "el bloque de `obrprv` no dice quien lo decidio"
    assert "0 filas" in bloque or "vacia" in bloque.lower()


def test_f074_r8_los_dos_sql_que_dependen_de_su_vacio_siguen_ahi() -> None:
    """Lo que sostiene la decision: si estos dejaran de existir, `obrprv` seria
    una tabla vacia sin ningun consumidor y la decision habria que rehacerla."""
    directorio = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "maestro"
    citantes = [
        f.name for f in sorted(directorio.glob("*.sql"))
        if "obrprv" in f.read_text(encoding="utf-8")
    ]
    assert citantes == ["02_proveedores.sql", "03_proveedores_obra.sql"], (
        f"cambiaron los SQL que se apoyan en que `obrprv` este vacia: {citantes}"
    )


# ---------------------------------------------------------------------------
# A9 · lo que crece la nocturna, y los documentos que citan el numero
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fichero", [FICHERO_RAW, FICHERO_GLOBAL], ids=lambda p: p.name
)
def test_f074_r9_ningun_documento_sigue_hablando_de_cincuenta_y_seis(
    fichero: pathlib.Path,
) -> None:
    texto = fichero.read_text(encoding="utf-8")
    assert "56 tablas" not in texto, (
        f"{fichero.name} sigue diciendo «56 tablas» y son {TOTAL_TABLAS}"
    )
    assert "las 56 " not in texto


def test_f074_r9_la_cabecera_de_raw_yaml_cuenta_las_tablas_que_hay() -> None:
    """El numero se compara con `len(tables)`, no con una constante: asi no se
    puede quedar viejo sin que este test lo diga."""
    hallazgo = re.search(r"[Ss]on (\d+) tablas", FICHERO_RAW.read_text(encoding="utf-8"))
    assert hallazgo and int(hallazgo.group(1)) == len(_ingesta())


def test_f074_r9_la_regla_de_oro_cuenta_las_tablas_que_hay() -> None:
    assert f"{TOTAL_TABLAS} tablas" in FICHERO_GLOBAL.read_text(encoding="utf-8")


def test_f074_r9_la_version_del_diccionario_sube() -> None:
    """Cambiar `raw.yaml` sin subir la version publica un diccionario que dice
    ser el mismo de ayer."""
    version = yaml.safe_load(FICHERO_GLOBAL.read_text(encoding="utf-8"))["version"]
    assert int(version) >= 17


def test_f074_r9_la_arquitectura_declara_las_nueve_y_lo_que_cuestan() -> None:
    """El coste de la ventana nocturna es lo que decide si esto cabe, y no vive
    en ningun sitio ejecutable: tiene que estar escrito donde se busca."""
    texto = (RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert f"{TOTAL_TABLAS} tablas" in texto
    assert "F-074" in texto
    for tabla in NUEVAS:
        assert f"`{tabla}`" in texto, f"ARCHITECTURE.md no menciona `{tabla}`"


def test_f074_r9_las_dos_grandes_son_el_grueso_de_lo_que_se_anade() -> None:
    """Control de la cifra que sostiene la medicion de la ventana: 1.275.460 de
    las 1.341.365 filas nuevas son `dcaprodes` y `ctrprodes`."""
    total = sum(filas for filas, _ in NUEVAS.values())
    grandes = NUEVAS["dcaprodes"][0] + NUEVAS["ctrprodes"][0]
    assert total == 1_341_365
    assert grandes == 1_275_460
    assert round(100 * grandes / total) == 95
