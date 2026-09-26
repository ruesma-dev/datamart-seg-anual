# tests/test_f057_personal.py
"""
F-057 · El esquema `personal`, comprobado OFFLINE (R28).

Ninguno de estos tests toca red ni base de datos, y no es una comodidad: los
tres objetos se construyen contra un PostgreSQL compartido con `albaranes` y
`partes` **en produccion**, asi que construirlos desde la suite seria escribir
en produccion. Lo que si se puede es fijar por escrito las decisiones que el
diseno tomo midiendo contra Sigrid vivo el 2026-09-18, de modo que un refactor
que se lleve por delante cualquiera de ellas rompa la suite y no la nocturna.
Las cifras contra la base viva son verificacion MANUAL del humano (T23).

Mismo criterio y mismos helpers que `tests/test_f073_sql.py`.

Tres familias de test aqui dentro:

1. **El SQL**, sobre su texto: el DDL, los dos `INSERT` y la vista.
2. **La propagacion**, que es donde se olvidan las cosas: el step, el DAG, los
   tres puntos de `main.py`, los esquemas de consumo, `ESQUEMAS_DEL_DATAMART` y
   las tres puertas (`check-declarados`, `check-unicidad`, `check-relaciones`).
3. **La ficha del diccionario**, que es lo unico que el agente del MCP va a
   leer antes de escribir una consulta: si no declara la trampa de la unidad,
   la trampa se comete.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DIRECTORIO_SQL = (
    RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
)
DIR_PERSONAL = DIRECTORIO_SQL / "personal"
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"

RUTA_SETUP = DIR_PERSONAL / "00_setup.sql"
RUTA_RECURSOS = DIR_PERSONAL / "01_recursos.sql"
RUTA_PARTES = DIR_PERSONAL / "02_partes_lineas.sql"
RUTA_VISTAS = DIR_PERSONAL / "05_views.sql"

#: Los seis ficheros del step, EN ORDEN. El orden es el de la numeracion:
#: `00_setup.sql` crea el esquema y las tablas, y los demas las llenan. F-101
#: anade `03_partes.sql` y `04_recursos_tipos_hora.sql` y renumera la vista.
FICHEROS_PERSONAL = [
    "00_setup.sql",
    "01_recursos.sql",
    "02_partes_lineas.sql",
    "03_partes.sql",
    "04_recursos_tipos_hora.sql",
    "05_views.sql",
]


@cache
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """El texto EJECUTABLE: sin las lineas `--` de comentario.

    Los guardas de identificador vetado (R13, R16b, R8) se aplican sobre esto y
    no sobre el fichero entero, para poder EXPLICAR en un comentario por que un
    campo no sirve sin que el propio comentario haga fallar el test.
    """
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _compacto(texto: str) -> str:
    """Una sola linea, espacios colapsados: para buscar expresiones SQL."""
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


# ===========================================================================
# R1, R11, R27 · el DDL
# ===========================================================================


def test_f057_r1_ddl_recursos() -> None:
    """`personal.recursos` es una TABLA con las 17 columnas del diseno."""
    compacto = _compacto(_sql(RUTA_SETUP))

    assert "CREATE SCHEMA IF NOT EXISTS personal" in compacto
    assert "CREATE TABLE IF NOT EXISTS personal.recursos (" in compacto
    for columna in (
        "recurso_id", "codigo_recurso", "nombre_recurso", "clase",
        "tipo_recurso_id", "tipo_recurso", "activo", "fecha_baja", "nif",
        "empleado_id", "dni", "nombre_pila", "apellido1", "apellido2",
        "es_externo", "proveedor_id", "_built_at",
    ):
        assert re.search(rf"\b{columna}\s+[A-Z]", compacto), (
            f"personal.recursos debe declarar la columna {columna} (R1)"
        )


def test_f057_r1_recursos_lleva_sus_dos_indices() -> None:
    """`(clase, activo)` y `(empleado_id)`: los dos cortes del diseno."""
    compacto = _compacto(_sql(RUTA_SETUP))

    assert re.search(
        r"CREATE INDEX IF NOT EXISTS \w+ ON personal\.recursos \(clase, activo\)",
        compacto,
    )
    assert re.search(
        r"CREATE INDEX IF NOT EXISTS \w+ ON personal\.recursos \(empleado_id\)",
        compacto,
    )


def test_f057_r11_ddl_partes_lineas() -> None:
    """`personal.partes_lineas` es una TABLA con las 16 columnas del diseno."""
    compacto = _compacto(_sql(RUTA_SETUP))

    assert "CREATE TABLE IF NOT EXISTS personal.partes_lineas (" in compacto
    for columna in (
        "linea_id", "parte_id", "recurso_id", "obra_id", "en_seguimiento",
        "partida_id", "fecha", "anio", "mes", "tipo_hora_id", "tipo_hora",
        "unidad", "cantidad", "precio", "importe", "_built_at",
    ):
        assert re.search(rf"\b{columna}\s+[A-Z]", compacto), (
            f"personal.partes_lineas debe declarar la columna {columna} (R11)"
        )


def test_f057_r11_partes_lineas_lleva_sus_cuatro_indices() -> None:
    compacto = _compacto(_sql(RUTA_SETUP))

    for indice in (
        r"\(obra_id, anio, mes\)", r"\(recurso_id\)", r"\(partida_id\)",
        r"\(unidad\)",
    ):
        assert re.search(
            rf"CREATE INDEX IF NOT EXISTS \w+ ON personal\.partes_lineas {indice}",
            compacto,
        ), f"falta el indice {indice} de personal.partes_lineas (R11)"


def test_f057_r1_y_r11_la_clave_primaria_es_el_ide_de_origen() -> None:
    """`recurso_id` y `linea_id` son PK: el grano no depende de la suerte."""
    compacto = _compacto(_sql(RUTA_SETUP))

    assert "recurso_id BIGINT PRIMARY KEY" in compacto
    assert "linea_id BIGINT PRIMARY KEY" in compacto


def test_f057_r27_ddl_idempotente() -> None:
    """Dos ejecuciones seguidas dejan el mismo contenido.

    El DDL crea con `IF NOT EXISTS` —nunca `DROP TABLE`, que se llevaria por
    delante los `GRANT` y dejaria a Power BI sin la tabla hasta el siguiente
    `apply_grants`—, los dos INSERT vacian con `TRUNCATE` antes de llenar, y la
    vista se rehace con `DROP VIEW IF EXISTS` + `CREATE VIEW`.
    """
    setup = _sin_comentarios(_sql(RUTA_SETUP))

    assert "DROP TABLE" not in setup.upper(), (
        "el DDL de personal no puede dropear sus tablas: perderia los GRANT (R27)"
    )
    # F-101 anade `partes` y `recursos_tipos_hora`: cuatro tablas, ninguna se dropea.
    assert setup.upper().count("CREATE TABLE IF NOT EXISTS") == 4
    assert "CREATE OR REPLACE FUNCTION personal.fn_fecha" in _compacto(_sql(RUTA_SETUP))

    for ruta, tabla in ((RUTA_RECURSOS, "recursos"), (RUTA_PARTES, "partes_lineas")):
        compacto = _compacto(_sql(ruta))
        assert f"TRUNCATE TABLE personal.{tabla}" in compacto, (
            f"{ruta.name} tiene que vaciar antes de insertar (R27)"
        )
        assert f"INSERT INTO personal.{tabla}" in compacto

    vistas = _compacto(_sql(RUTA_VISTAS))
    assert "DROP VIEW IF EXISTS personal.v_pbi_horas_obra_mes" in vistas
    assert "CREATE VIEW personal.v_pbi_horas_obra_mes" in vistas


def test_f057_r27_la_funcion_de_fecha_es_local_al_esquema() -> None:
    """Copia local a proposito: `personal` no puede depender de `stg` para
    tipar una fecha, igual que `compras.fn_sigrid_date` y `maestro.fn_fecha`."""
    compacto = _compacto(_sql(RUTA_SETUP))

    assert "personal.fn_fecha(d BIGINT) RETURNS DATE" in compacto
    for ajena in ("stg.fn_sigrid_date_to_date", "compras.fn_sigrid_date",
                  "maestro.fn_fecha", "retenciones.fn_sigrid_date"):
        assert ajena not in _sin_comentarios(_sql(RUTA_SETUP))


# ===========================================================================
# R1-R10 · el maestro de recursos
# ===========================================================================


def test_f057_r1_recursos_una_fila_por_fila_de_raw_res() -> None:
    """El grano es `raw.res`, y el codigo y el nombre salen de `raw.con`
    (regla dura `R-SIGRID-CON`: `res` no tiene ni `cod` ni `res` propios)."""
    compacto = _compacto(_sql(RUTA_RECURSOS))

    assert "FROM raw.res" in compacto
    assert re.search(r"JOIN\s+raw\.con\s+\w+\s+ON\s+\w+\.ide\s*=\s*\w+\.ide", compacto), (
        "el codigo y el nombre del recurso salen de su fila de `con` (R1)"
    )
    assert re.search(r"AS codigo_recurso\b", compacto)
    assert re.search(r"AS nombre_recurso\b", compacto)


def test_f057_r2_clase_desde_cla() -> None:
    """1 = PERSONA, 0 = CONSUMO, 2 = MEDIO. Manda `res.cla`, no `auxrestip`:
    hay un JEFE DE GRUPO con `cla = 0` y un CONSUMOS TELEFONO con `cla = 2`."""
    compacto = _compacto(_sql(RUTA_RECURSOS))

    clase = re.search(r"CASE\s+.{0,40}\.cla\b.*?END.*?AS clase", compacto)
    assert clase, "`clase` se deriva de `res.cla` con un CASE (R2)"
    texto = clase.group(0)
    assert "WHEN 1 THEN 'PERSONA'" in texto
    assert "WHEN 0 THEN 'CONSUMO'" in texto
    assert "WHEN 2 THEN 'MEDIO'" in texto
    assert "ELSE 'OTRO'" in texto, "un cuarto valor en origen no puede ser NULL"


def test_f057_r2_el_tipo_de_recurso_es_descriptivo_y_no_clasifica() -> None:
    """`auxrestip` aporta el literal (`OFIC. 1a ALBANIL`), no la clase: 492
    personas y 48 medios no tienen tipo, asi que el JOIN es LEFT."""
    compacto = _compacto(_sql(RUTA_RECURSOS))

    assert re.search(r"LEFT JOIN raw\.auxrestip", compacto), (
        "540 recursos no tienen tipo: con JOIN se perderian (R2)"
    )
    assert re.search(r"AS tipo_recurso\b", compacto)
    assert re.search(r"AS tipo_recurso_id\b", compacto)


def test_f057_r3_activo_es_fecbaj_del_concepto() -> None:
    """`raw.res` no tiene columna de baja: la baja es la del CONCEPTO (`con`).

    Es el criterio de Juan Romero («los recursos en rojo estan de baja»)
    traducido a un booleano: 1.722 de baja y 896 de alta.
    """
    compacto = _compacto(_sql(RUTA_RECURSOS))

    activo = re.search(
        r"\(\s*(?:COALESCE\(\s*)?(?P<alias>\w+)\.fecbaj\s*(?:,\s*0\s*\))?\s*"
        r"=\s*0\s*\)(?:::BOOLEAN)?\s+AS activo",
        compacto,
    )
    assert activo, "`activo` se deriva de `fecbaj` con un `= 0` (R3)"
    assert re.search(
        rf"JOIN\s+raw\.con\s+{activo.group('alias')}\b", compacto
    ), (
        "`activo` tiene que salir de la baja del CONCEPTO (`raw.con`): "
        "`raw.res` no tiene columna de baja propia (R3)"
    )
    assert re.search(r"personal\.fn_fecha\(\w+\.fecbaj\)\s+AS fecha_baja", compacto)


def test_f057_r4_no_filtra_por_activo() -> None:
    """BANDERA, no filtro. Filtrar aqui dejaria fuera a 1.722 de 2.618
    recursos, y con ellos el 43,2 % de las horas imputadas (R5)."""
    compacto = _compacto(_sql(RUTA_RECURSOS))
    # El `WHERE` del LATERAL es la correlacion `emp.ide = res.conide`, no un
    # filtro de filas de `res`: se quita antes de mirar.
    fuera_del_lateral = re.sub(r"LEFT JOIN LATERAL \(.*?\) \w+ ON TRUE", " ", compacto)

    assert " WHERE " not in fuera_del_lateral.upper(), (
        "`personal.recursos` publica las 2.618 filas, de alta y de baja: "
        "cualquier WHERE en la consulta principal es un filtro que el diseno "
        "prohibe (R4)"
    )


def test_f057_r6_empleado_por_lateral_limit_1() -> None:
    """`res.conide -> emp.ide`, y el LATERAL es lo que protege el grano.

    Hoy 3 recursos comparten `conide`. Un JOIN desnudo multiplicaria esas filas
    el dia que `raw.emp` traiga dos con el mismo `ide`, y el grano dejaria de
    ser «una fila por `raw.res`» sin que nadie se entere.
    """
    compacto = _compacto(_sql(RUTA_RECURSOS))

    assert "LEFT JOIN LATERAL" in compacto, (
        "con JOIN LATERAL se perderian los 1.794 recursos sin empleado (R6)"
    )
    lateral = re.search(r"LEFT JOIN LATERAL \((.*?)\) \w+ ON TRUE", compacto)
    assert lateral, "el lateral cuelga con ON TRUE para no filtrar (R6)"
    cuerpo = lateral.group(1)
    assert "FROM raw.emp" in cuerpo
    assert re.search(r"\w+\.ide\s*=\s*\w+\.conide", cuerpo), (
        "la relacion recurso-empleado va por `res.conide` (R6)"
    )
    assert re.search(r"ORDER BY \w+\.ide LIMIT 1", cuerpo), (
        "sin ORDER BY + LIMIT 1 el grano depende de la suerte (R6)"
    )


def test_f057_r7_publica_nombre_y_dni() -> None:
    """Autorizado por el humano el 2026-09-18: «el dni puede salir, no es un
    problema». No hay hash, ni truncado, ni tabla aparte."""
    compacto = _compacto(_sql(RUTA_RECURSOS))

    for columna, origen in (
        ("nif", r"\w+\.cif"),
        ("dni", r"\w+\.dni"),
        ("nombre_pila", r"\w+\.nomnom"),
        ("apellido1", r"\w+\.nomape1"),
        ("apellido2", r"\w+\.nomape2"),
        ("empleado_id", r"\w+\.ide"),
    ):
        assert re.search(rf"AS {columna}\b", compacto), f"falta `{columna}` (R7)"
        assert re.search(origen, compacto), f"falta el origen de `{columna}` (R7)"

    for ofuscacion in ("md5", "sha256", "digest", "encode(", "left("):
        assert ofuscacion not in compacto.lower(), (
            f"`{ofuscacion}` ofusca un dato que el humano autorizo publicar (R7)"
        )


#: LO UNICO que `raw.emp` sube al datamart curado (R7, R8): el identificador,
#: el DNI y el nombre estructurado. Es una LISTA BLANCA a proposito.
#:
#: La primera version era una lista negra de 19 «nombres reales de Sigrid», y
#: 14 no existian en `emp` (`nss`, `iban`, `movil`...): con el lateral leyendo
#: `emp.tarseg` (Seguridad Social) y `emp.ban` (banco) la suite pasaba entera.
#: Una lista negra solo protege de lo que alguien se acordo de listar; para
#: cerrar un conjunto, lista blanca. Los nombres reales de las 152 columnas
#: estan en `azure-apps/sigrid_tablas.md`, tabla `emp`.
COLUMNAS_AUTORIZADAS_DE_EMP = frozenset({"ide", "dni", "nomnom", "nomape1", "nomape2"})

_LATERAL_EMP = re.compile(
    r"LEFT JOIN LATERAL \( SELECT (?P<lista>.*?) FROM raw\.emp (?P<alias>\w+) "
    r"(?P<resto>[^()]*?)\) (?P<exterior>\w+) ON TRUE"
)


def _lateral_emp() -> re.Match[str]:
    compacto = _compacto(_sql(RUTA_RECURSOS))
    lateral = _LATERAL_EMP.search(compacto)
    assert lateral, "`raw.emp` se lee en un LEFT JOIN LATERAL (R8)"
    return lateral


def test_f057_r8_raw_emp_solo_se_lee_en_el_lateral() -> None:
    """Una sola lectura de `raw.emp`: la del lateral que vigilan los demas.

    Un segundo JOIN, o una subconsulta escalar en el SELECT, se saltaria la
    lista blanca del lateral sin tocarlo.
    """
    compacto = _compacto(_sql(RUTA_RECURSOS))

    assert len(re.findall(r"\braw\.emp\b", compacto)) == 1, (
        "`raw.emp` se lee UNA vez, en el lateral de la lista blanca (R8)"
    )
    _lateral_emp()


def test_f057_r8_el_lateral_lee_exactamente_la_lista_blanca() -> None:
    """El lateral selecciona EXACTAMENTE las cinco columnas autorizadas.

    Cada elemento es `alias.columna` desnudo: sin `*`, sin expresiones y sin
    renombrar, porque `emp.tarseg AS dni` pasaria por una columna autorizada.
    """
    lateral = _lateral_emp()
    alias = lateral["alias"]
    elementos = [e.strip() for e in lateral["lista"].split(",")]

    columnas = []
    for elemento in elementos:
        desnudo = re.fullmatch(rf"{alias}\.(\w+)", elemento)
        assert desnudo, f"`{elemento}`: el lateral lee columnas desnudas de `raw.emp` (R8)"
        columnas.append(desnudo.group(1).lower())

    assert len(columnas) == len(set(columnas)), "columna repetida en el lateral (R8)"
    assert set(columnas) == COLUMNAS_AUTORIZADAS_DE_EMP, (
        f"el lateral lee {sorted(columnas)}; lo autorizado el 2026-09-18 es "
        f"{sorted(COLUMNAS_AUTORIZADAS_DE_EMP)} y nada mas (R8)"
    )
    resto = set(re.findall(rf"\b{alias}\.(\w+)", lateral["resto"]))
    assert resto <= COLUMNAS_AUTORIZADAS_DE_EMP, (
        f"el lateral mira {sorted(resto - COLUMNAS_AUTORIZADAS_DE_EMP)} de `raw.emp` (R8)"
    )


def test_f057_r8_el_select_exterior_no_usa_otra_columna_del_empleado() -> None:
    """Fuera del lateral, `e.<columna>` solo puede ser una de las cinco."""
    lateral = _lateral_emp()
    exterior = lateral["exterior"]
    compacto = _compacto(_sql(RUTA_RECURSOS))
    fuera = compacto[: lateral.start()] + compacto[lateral.end():]

    usadas = {c.lower() for c in re.findall(rf"\b{exterior}\.(\w+)", fuera)}
    assert usadas, f"el SELECT exterior no usa el lateral `{exterior}` (R7)"
    assert usadas <= COLUMNAS_AUTORIZADAS_DE_EMP, (
        f"el SELECT exterior usa {sorted(usadas - COLUMNAS_AUTORIZADAS_DE_EMP)} "
        "del empleado: fuera de lo autorizado (R8)"
    )


def test_f057_r10_externo_y_proveedor() -> None:
    """`res.prvide`: informado en 459 de las 1.354 personas, 85 proveedores."""
    compacto = _compacto(_sql(RUTA_RECURSOS))

    assert re.search(
        r"\(\s*(?:COALESCE\(\s*)?\w+\.prvide\s*(?:,\s*0\s*\))?\s*<>\s*0\s*\)"
        r"(?:::BOOLEAN)?\s+AS es_externo",
        compacto,
    ), "`es_externo` es `res.prvide <> 0` (R10)"
    assert re.search(r"NULLIF\(\w+\.prvide, 0\)\s+AS proveedor_id", compacto)


# ===========================================================================
# R11-R20 · el hecho
# ===========================================================================


def test_f057_r11_partes_una_fila_por_fila_de_raw_hmores() -> None:
    compacto = _compacto(_sql(RUTA_PARTES))

    assert "FROM raw.hmores" in compacto
    assert re.search(r"\w+\.ide\s+AS linea_id", compacto)


def test_f057_r12_obra_de_la_linea_no_de_la_cabecera() -> None:
    """769 lineas contradicen a su cabecera, y manda la LINEA.

    El guarda es doble: que `obra_id` salga de `hmores.obride` y que el SQL no
    una `raw.hmo` en absoluto. Un JOIN a la cabecera «solo para mirar» es como
    se cuela la atribucion equivocada.
    """
    compacto = _compacto(_sql(RUTA_PARTES))

    assert re.search(r"NULLIF\(\w+\.obride, 0\)\s+AS obra_id", compacto), (
        "la obra sale de `hmores.obride`, el de la LINEA (R12)"
    )
    assert not re.search(r"\braw\.hmo\b", _sin_comentarios(_sql(RUTA_PARTES))), (
        "la cabecera `raw.hmo` no participa: 769 lineas la contradicen (R12)"
    )


def test_f057_r13_no_usa_centro_de_coste() -> None:
    """La trampa de `apu`/F-045 NO aplica: el parte trae la obra.

    Se veta en los DOS ficheros y sobre el texto ejecutable, comentarios `--`
    aparte, al estilo de `test_f073_r3_no_usa_cen_obride`. `res.cenconide` esta
    informado al 75,5 % pero con 9 valores distintos: no es la obra.

    F-107 publica `res.cenconide` en `personal.recursos`, pero como lo que es
    --la CONTRAPARTIDA del recurso, un identificador de centro de coste-- y en
    una sola proyeccion literal. Esa proyeccion, y solo esa, se descuenta del
    texto antes de vetar: cualquier otro uso (un JOIN, un filtro, atribuir obra
    con el) sigue en rojo, y en las lineas de parte no se admite ninguno.
    """
    permitida = "NULLIF(r.cenconide, 0) AS centro_coste_contrapartida_id"
    for ruta in (RUTA_RECURSOS, RUTA_PARTES):
        ejecutable = _sin_comentarios(_sql(ruta))
        if ruta == RUTA_RECURSOS:
            ejecutable = re.sub(r"\s+", " ", ejecutable)
            assert ejecutable.count(permitida) == 1, "F-107: la contrapartida, una vez"
            ejecutable = ejecutable.replace(permitida, " ")
        assert "maestro.centros_coste" not in ejecutable, (
            f"{ruta.name}: F-073 no participa en la atribucion de obra (R13)"
        )
        assert not re.search(r"\bcenconide\b", ejecutable), (
            f"{ruta.name}: `res.cenconide` tiene 9 valores distintos, no es la obra (R13)"
        )
        assert not re.search(r"\bcenide\b", ejecutable), (
            f"{ruta.name}: el centro de coste no atribuye obra aqui (R13)"
        )


def test_f057_r14_no_filtra_universo_de_obra() -> None:
    """`en_seguimiento` es una MARCA resuelta con EXISTS contra `stg.obras`.

    No se replican los filtros de `stg/03_obras.sql`: duplicar esa lista de
    codigos administrativos es como se desincronizan dos verdades. Y no se
    filtra: 10.373 lineas de obra administrativa y 1.373 con la obra a cero se
    publican igual.
    """
    compacto = _compacto(_sql(RUTA_PARTES))

    assert re.search(
        r"EXISTS \(\s*SELECT 1 FROM stg\.obras \w+ WHERE \w+\.obra_id = .*?\)"
        r"\s+AS en_seguimiento",
        compacto,
    ), "`en_seguimiento` se resuelve por EXISTS contra `stg.obras` (R14)"

    cuerpo = compacto.split("FROM raw.hmores", 1)[1]
    assert " WHERE " not in cuerpo.upper(), (
        "`personal.partes_lineas` publica las 330.638 lineas: aqui no se "
        "filtra el universo de obra (R14)"
    )


def test_f057_r15_partida() -> None:
    """`hmores.paride`, informado en 302.575 lineas; las 302.575 existen en
    `raw.obrparpar` y son de la MISMA obra de la linea (cero inconsistencias)."""
    compacto = _compacto(_sql(RUTA_PARTES))

    assert re.search(r"NULLIF\(\w+\.paride, 0\)\s+AS partida_id", compacto)


def test_f057_r16_unidad_desde_medide() -> None:
    """LA DECISION QUE EVITA LA CIFRA FALSA.

    `hmores.can` mezcla HORA, DIA, MES y UD, y el clasificador es
    `auxhor.medide`: 1 HORA, 2 DIA, 3 MES, 19 UD.
    """
    compacto = _compacto(_sql(RUTA_PARTES))

    assert re.search(r"LEFT JOIN raw\.auxhor", compacto), (
        "10 lineas apuntan a un tipo de hora sin catalogo: el JOIN es LEFT (R16)"
    )
    unidad = re.search(r"CASE\s+\w+\.medide\b.*?END(?:::VARCHAR\(\d+\))?\s+AS unidad", compacto)
    assert unidad, "`unidad` se deriva de `auxhor.medide` con un CASE (R16)"
    texto = unidad.group(0)

    # IGUALDAD EXACTA, no «contiene». Con `in` pasaban un `WHEN 4 THEN 'HORA'`
    # anadido, un `WHEN 5 THEN 'KM'` y —el peor— un `WHEN 3 THEN 'HORA'`
    # antepuesto, que convierte los MESES en horas: el error que esta feature
    # existe para impedir. Cada WHEN tiene que ser `WHEN n THEN 'X'` literal.
    pares = re.findall(r"\bWHEN (\d+) THEN '([^']*)'", texto)
    assert len(pares) == len(re.findall(r"\bWHEN\b", texto)), (
        "cada rama del CASE es `WHEN n THEN 'LITERAL'` (R16)"
    )
    valores = [int(n) for n, _ in pares]
    assert len(valores) == len(set(valores)), (
        f"`medide` repetido en el CASE {valores}: gana el primero y cambia la unidad (R16)"
    )
    assert {int(n): u for n, u in pares} == {1: "HORA", 2: "DIA", 3: "MES", 19: "UD"}, (
        f"el CASE de la unidad es exactamente 1 HORA, 2 DIA, 3 MES, 19 UD; hay {pares} (R16)"
    )


def test_f057_r16b_no_usa_auxhor_ext() -> None:
    """`auxhor.ext` esta a CERO en las 60 filas del catalogo.

    Parece el clasificador —se llama «Extra»— y no clasifica nada. Quien lo
    mire concluira que el catalogo no distingue unidades, que es justo el error
    que esta feature existe para no cometer.
    """
    ejecutable = _sin_comentarios(_sql(RUTA_PARTES))

    assert not re.search(r"\bext\b", ejecutable, re.IGNORECASE), (
        "`auxhor.ext` esta a 0 en las 60 filas: no clasifica la unidad (R16)"
    )


def test_f057_r17_medide_desconocido_no_se_traduce() -> None:
    """Un quinto valor en origen sale como DESCONOCIDA, nunca como HORA.

    Es el seguro de D5 (`auxmed` no se ingiere): si Sigrid anade una unidad, la
    rama `ELSE` la hace visible en vez de colarla en la cifra de horas.
    """
    compacto = _compacto(_sql(RUTA_PARTES))
    unidad = re.search(r"CASE\s+\w+\.medide\b.*?END", compacto)

    assert unidad, "falta el CASE de la unidad (R17)"
    assert re.findall(r"\bELSE (.*?) END\b", unidad.group(0)) == ["'DESCONOCIDA'"], (
        "sin rama ELSE, un `medide` nuevo saldria NULL y se sumaria en silencio (R17)"
    )


def test_f057_r19_importe_con_signo() -> None:
    """`hmores.tot` tal cual: 11.036 lineas valen 0 y 9.119 son negativas
    (correcciones). Un `ABS` o un `WHERE tot > 0` borraria las correcciones."""
    compacto = _compacto(_sql(RUTA_PARTES))

    assert re.search(r"\w+\.tot.*?\s+AS importe", compacto)
    assert re.search(r"\w+\.can.*?\s+AS cantidad", compacto)
    assert re.search(r"\w+\.pre.*?\s+AS precio", compacto)
    assert "ABS(" not in compacto.upper(), (
        "las 9.119 lineas negativas son correcciones y conservan su signo (R19)"
    )


# ===========================================================================
# R21-R22 · la superficie de consumo
# ===========================================================================


def test_f057_r21_vista_solo_horas() -> None:
    """`WHERE unidad = 'HORA'` CABLEADO en la vista.

    No es un filtro por defecto que el consumidor pueda quitar: es lo que hace
    que la trampa de R18 no se pueda cometer desde aqui. El 71,7 % del euro
    esta en las lineas de MES, y sumarlas junto a las horas da 1.837.201,23
    «horas» que no existen.
    """
    compacto = _compacto(_sql(RUTA_VISTAS))

    # EXACTAMENTE el corte, no «empieza por el corte»: con `re.search` pasaba
    # `WHERE pl.unidad = 'HORA' OR pl.unidad = 'MES'`, que mete los meses.
    filtros = re.findall(r"\bWHERE (.*?) GROUP BY\b", compacto)
    assert len(filtros) == 1 and re.fullmatch(r"\w+\.unidad = 'HORA'", filtros[0]), (
        f"la vista se construye SOLO con unidad = 'HORA', y el filtro es {filtros} (R21)"
    )
    assert len(re.findall(r"\bWHERE\b", compacto)) == 1, (
        "un unico WHERE en la vista: el corte de la unidad (R21)"
    )
    for columna in ("obra_id", "codigo_obra", "nombre_obra", "anio", "mes",
                    "tipo_recurso", "es_externo", "recursos", "horas", "importe"):
        assert re.search(rf"AS {columna}\b", compacto), (
            f"la vista debe exponer {columna} (R21)"
        )
    assert "COUNT(DISTINCT" in compacto.upper()


def test_f057_r22_vista_sin_datos_personales() -> None:
    """Un agregado con el nombre dentro son filas de una persona disfrazadas
    de agregado. El nombre y el DNI viven en `personal.recursos` (R7)."""
    compacto = _compacto(_sql(RUTA_VISTAS))

    for prohibida in ("nombre_recurso", "nif", "dni", "nombre_pila",
                      "apellido1", "apellido2", "codigo_recurso"):
        assert not re.search(rf"\b{prohibida}\b", compacto), (
            f"`{prohibida}` no puede salir en un agregado obra x mes (R22)"
        )


# ===========================================================================
# LA PROPAGACION · 12 puntos
# ===========================================================================


def test_f057_r24_step_nombre_stage_y_dependencias() -> None:
    """PROPAGACION 1/12. El step existe y declara lo que lee."""
    from etl_sigrid.application.steps.build_personal_step import BuildPersonalStep

    paso = BuildPersonalStep(SimpleNamespace())

    assert paso.name == "build_personal"
    assert paso.stage == "build_aux"
    assert paso.depends_on == ["build_stg"], (
        "lee `stg.obras` para la marca `en_seguimiento` (R14): si `build_stg` "
        "no esta en el DAG, un build contra una base sin `stg` revienta (R24)"
    )


def test_f057_r24_los_sub_pasos_van_en_el_orden_de_sus_ficheros() -> None:
    from etl_sigrid.application.steps import build_personal_step

    assert [s.sql_file for s in build_personal_step.SUB_PASOS] == FICHEROS_PERSONAL


def test_f057_r24_cada_sub_paso_declarado_existe_en_disco() -> None:
    """Un nombre mal escrito aqui sale como FAILED a las tres de la manana."""
    from etl_sigrid.application.steps import build_personal_step

    for sub in build_personal_step.SUB_PASOS:
        assert (DIR_PERSONAL / sub.sql_file).exists(), (
            f"personal/{sub.sql_file} esta declarado y no existe"
        )


def test_f057_r24_los_dos_sub_pasos_que_llenan_cuentan_sus_filas() -> None:
    """Sin `target_schema`/`target_table` el sub-paso no aporta a
    `rows_processed`, y un cero en `_meta.etl_runs` no distingue «construida
    vacia» de «no construida»."""
    from etl_sigrid.application.steps import build_personal_step

    por_nombre = {s.name: s for s in build_personal_step.SUB_PASOS}

    assert por_nombre["recursos"].target_schema == "personal"
    assert por_nombre["recursos"].target_table == "recursos"
    assert por_nombre["partes_lineas"].target_table == "partes_lineas"
    assert por_nombre["setup"].target_table is None, (
        "`00_setup.sql` crea las tablas VACIAS: contar ahi daria 0 la primera vez"
    )


def test_f057_r24_el_step_encadena_sus_cuatro_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ejecutado de verdad contra un doble: `build_postgres_client` es la
    unica puerta por la que este step sale del proceso (R28)."""
    from etl_sigrid.application.steps import build_personal_step
    from etl_sigrid.application.steps.build_personal_step import BuildPersonalStep
    from etl_sigrid.domain.entities import StepStatus

    class _PgFalso:
        def __init__(self) -> None:
            self.ejecutados: list[str] = []
            self.contados: list[tuple[str, str]] = []

        def execute_sql_file(self, path: Path) -> None:
            self.ejecutados.append(path.name)

        def count_rows(self, schema: str, table: str) -> int:
            self.contados.append((schema, table))
            return 7

    pg = _PgFalso()
    monkeypatch.setattr(build_personal_step, "build_postgres_client", lambda _s: pg)

    resultado = BuildPersonalStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.ejecutados == FICHEROS_PERSONAL
    assert pg.contados == [
        ("personal", "recursos"), ("personal", "partes_lineas"),
        ("personal", "partes"), ("personal", "recursos_tipos_hora"),
    ]
    assert resultado.rows_processed == 28


def test_f057_r24_un_sub_paso_a_medio_configurar_no_cuenta_filas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EL GUARDIAN DE `target_schema`/`target_table`, y por que `SUB_PASOS` es
    DATO a nivel de modulo: sustituirla es lo unico que permite ejercitarlo.

    El step solo cuenta filas cuando el sub-paso declara **las dos** cosas. Con
    un `or` en vez del `and` —que hoy da el mismo resultado, porque los cuatro
    sub-pasos reales las tienen ambas o ninguna— un `_SubStep` a medio
    configurar llamaria a `count_rows(esquema, None)`, y eso revienta contra la
    base a las tres de la manana en vez de en la suite.

    Lo destapo la campaña de mutacion: era el unico superviviente de
    `build_personal_step.py` con riesgo real, y este test lo mata.
    """
    from etl_sigrid.application.steps import build_personal_step
    from etl_sigrid.application.steps.build_personal_step import (
        BuildPersonalStep,
        _SubStep,
    )
    from etl_sigrid.domain.entities import StepStatus

    class _PgQueAnota:
        def __init__(self) -> None:
            self.contados: list[tuple[str, str]] = []

        def execute_sql_file(self, path: Path) -> None:
            pass

        def count_rows(self, schema: str, table: str) -> int:
            self.contados.append((schema, table))
            return 5

    pg = _PgQueAnota()
    monkeypatch.setattr(build_personal_step, "build_postgres_client", lambda _s: pg)
    monkeypatch.setattr(
        build_personal_step,
        "SUB_PASOS",
        (
            _SubStep(name="solo_esquema", sql_file="00_setup.sql",
                     target_schema="personal"),
            _SubStep(name="solo_tabla", sql_file="01_recursos.sql",
                     target_table="recursos"),
        ),
    )

    resultado = BuildPersonalStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.SUCCESS
    assert pg.contados == [], (
        "un sub-paso con solo la mitad de su destino NO puede contar filas: "
        "`count_rows` recibiria un None y reventaria contra la base"
    )
    assert resultado.rows_processed == 0


class _PgQueRevienta:
    """Ejecuta hasta el fichero indicado y ahi lanza, como haria Postgres."""

    def __init__(self, falla_en: str) -> None:
        self.ejecutados: list[str] = []
        self._falla_en = falla_en

    def execute_sql_file(self, path: Path) -> None:
        self.ejecutados.append(path.name)
        if path.name == self._falla_en:
            raise RuntimeError('relation "raw.hmores" does not exist')

    def count_rows(self, schema: str, table: str) -> int:
        return 0


@pytest.mark.parametrize(
    ("falla_en", "sub_paso", "ejecutados"),
    [
        ("00_setup.sql", "setup", ["00_setup.sql"]),
        ("02_partes_lineas.sql", "partes_lineas", FICHEROS_PERSONAL[:3]),
    ],
)
def test_f057_r24_un_sql_que_revienta_da_failed_nombrando_el_sub_paso(
    monkeypatch: pytest.MonkeyPatch,
    falla_en: str,
    sub_paso: str,
    ejecutados: list[str],
) -> None:
    """A las tres de la manana «fallo el build» no sirve: hay que decir donde.

    Y tiene que PARAR: `02_partes_lineas.sql` lee lo que dejo `00_setup.sql`, y
    seguir ejecutando despues de un fallo deja el esquema a medias sin que el
    estado del paso lo refleje.
    """
    from etl_sigrid.application.steps import build_personal_step
    from etl_sigrid.application.steps.build_personal_step import BuildPersonalStep
    from etl_sigrid.domain.entities import StepStatus

    pg = _PgQueRevienta(falla_en)
    monkeypatch.setattr(build_personal_step, "build_postgres_client", lambda _s: pg)

    resultado = BuildPersonalStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.FAILED
    assert sub_paso in resultado.error_message
    assert "relation" in resultado.error_message
    assert resultado.finished_at is not None
    assert pg.ejecutados == ejecutados, "siguio ejecutando despues de fallar"


def test_f057_r24_un_sql_que_falta_da_failed_con_la_ruta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """El modo de fallo SILENCIOSO de este tipo de step.

    Si manana cambia la ruta del SQL, `execute_sql_file` no se llama y el paso
    podria declararse SUCCESS sin haber construido nada. Tiene que ser un fallo
    ruidoso y con la ruta dentro, que es lo unico accionable.
    """
    from etl_sigrid.application.steps import build_personal_step
    from etl_sigrid.application.steps.build_personal_step import BuildPersonalStep
    from etl_sigrid.domain.entities import StepStatus

    class _PathQueApuntaA:
        """Sustituye `Path(__file__)` para que el step busque en un vacio."""

        def __init__(self, destino: Path) -> None:
            self._destino = destino

        def __call__(self, _ruta: str) -> Path:
            return self

        def resolve(self) -> _PathQueApuntaA:
            return self

        @property
        def parents(self) -> list[Path]:
            return [self._destino] * 5

    monkeypatch.setattr(
        build_personal_step, "build_postgres_client", lambda _s: _PgQueRevienta("")
    )
    monkeypatch.setattr(build_personal_step, "Path", _PathQueApuntaA(tmp_path))

    resultado = BuildPersonalStep(SimpleNamespace()).run()

    assert resultado.status == StepStatus.FAILED
    assert "SQL file no encontrado" in resultado.error_message


def test_f057_r24_orden_topologico_y_no_bloquea() -> None:
    """PROPAGACION 2/12. El orquestador es generico: se VERIFICA, no se toca.

    Dos cosas, y la segunda es la que sostiene `R-FRESCURA`: que `build_personal`
    corra despues de `build_stg`, y que **ningun paso lo declare en su
    `depends_on`**. Si falla, la noche continua y termina.
    """
    import main
    from etl_sigrid.application.orchestrator import Orchestrator

    pasos = main.build_pipeline_steps(_settings_falso())
    ordenados = [p.name for p in Orchestrator(pasos)._topological_sort()]

    assert "build_personal" in ordenados
    assert ordenados.index("build_stg") < ordenados.index("build_personal")

    for paso in pasos:
        assert "build_personal" not in paso.depends_on, (
            f"`{paso.name}` depende de `build_personal`: un fallo del esquema "
            "de personal tumbaria la nocturna, que es justo lo que el esquema "
            "modulo evita (R24)"
        )


def _settings_falso() -> SimpleNamespace:
    """Lo minimo que miran los constructores de los steps del pipeline."""
    return SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role="mcp_sigrid_dm_ro",
            set_role="sigrid_dm_etl",
            consumption_schema_list=["mart"],
        )
    )


def test_f057_r25_existe_comando_build_personal() -> None:
    """PROPAGACION 3/12. El comando suelto, junto a sus hermanos."""
    import main

    assert "build-personal" in main.cli.commands
    # `reset-personal` NO existe, y es deliberado: `build-compras` y
    # `build-retenciones` tienen su reset, pero la spec no lo pidio para este
    # esquema y esta implementacion no la rediseña. Si el humano lo quiere, es
    # una tarea suya, no un extra que se cuela aqui.
    assert "reset-personal" not in main.cli.commands


def test_f057_r25_paso_en_el_pipeline_y_posicion() -> None:
    """PROPAGACION 4/12. En `build_pipeline_steps`, entre retenciones y cierre.

    El orden EFECTIVO lo garantiza `depends_on`; la posicion es legibilidad, y
    se fija aqui para que no se mueva sin querer.
    """
    import main

    nombres = [p.name for p in main.build_pipeline_steps(_settings_falso())]

    assert "build_personal" in nombres, (
        "sin esto el esquema no se construye de noche y su dato envejece "
        "en silencio (R25)"
    )
    assert nombres.index("build_retenciones") < nombres.index("build_personal")
    assert nombres.index("build_personal") < nombres.index("build_cierre")


def test_f057_r25_run_all_declara_cinco_build() -> None:
    """PROPAGACION 5/12. El docstring que contaba cuatro.

    Un comentario falso es peor que ninguno: quien lea `run-all` tiene que ver
    los cinco build de negocio, y que `personal` es uno de ellos.
    """
    import main

    documentacion = (main.run_all.__doc__ or "").lower()

    assert "cuatro build" not in documentacion
    assert "cinco build" in documentacion
    assert "personal" in documentacion


def test_f057_r25_build_personal_es_un_comando_que_escribe() -> None:
    """PROPAGACION 13/12 — el punto que los doce medidos NO listaban.

    Lo destapó `bash harness/init.sh`, no una revisión: `run-all` reventó en
    `tests/test_f024_cli.py` con `AttributeError: 'SimpleNamespace' object has
    no attribute 'postgres'`, porque su `STEPS_POR_COMANDO` sustituye por un
    doble cada step de un comando que ESCRIBE, y `build_personal` no estaba.
    El paso real intentaba abrir conexión dentro de un test offline.

    Esa lista **es el requisito** de R4 de F-024 —todo comando que escribe
    marca las huérfanas antes de actuar—, así que un comando de escritura que
    no esté ahí no es un fallo del doble: es un comando sin vigilar. Se ancla
    aquí para que el esquema `personal` no vuelva a colarse.
    """
    from tests.test_f024_cli import COMANDOS_QUE_ESCRIBEN, STEPS_POR_COMANDO

    assert "build-personal" in COMANDOS_QUE_ESCRIBEN
    assert STEPS_POR_COMANDO["build-personal"] == (
        "BuildPersonalStep", "build_personal", "build_aux"
    ), (
        "el doble tiene que declarar el `stage` REAL (`build_aux`), que en este "
        "paso no coincide con su nombre como sí ocurre en los cuatro de F-047"
    )


def test_f057_r25_personal_en_consumption_schemas() -> None:
    """PROPAGACION 6/12. La superficie que el rol del MCP puede leer."""
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS

    assert "personal" in DEFAULT_CONSUMPTION_SCHEMAS.split(",")

    entorno = (RAIZ / ".env.example").read_text(encoding="utf-8")
    linea = next(
        (fila for fila in entorno.splitlines()
         if fila.startswith("PG_CONSUMPTION_SCHEMAS=")),
        None,
    )
    assert linea is not None
    assert "personal" in linea.split("=", 1)[1].split(","), (
        "`.env.example` es lo que se copia para montar un entorno: si no lo "
        "trae, el esquema nuevo queda invisible para el MCP (R25)"
    )


def test_f057_r25_apply_grants_no_cablea_esquemas() -> None:
    """PROPAGACION 6/12 (b). El paso concede lo que diga la CONFIGURACION.

    Se VERIFICA que lee `consumption_schema_list` y que no lleva ninguna lista
    de esquemas escrita a mano: si la llevara, `personal` se habria quedado
    fuera sin que nadie lo notara hasta que Power BI devolviese vacio.
    """
    from etl_sigrid.application.steps import apply_grants_step

    fuente = Path(apply_grants_step.__file__).read_text(encoding="utf-8")
    ejecutable = "\n".join(
        fila for fila in fuente.splitlines()
        if not fila.lstrip().startswith("#")
    )

    assert "consumption_schema_list" in ejecutable
    for esquema in ("mart", "cierre", "compras", "maestro", "retenciones", "personal"):
        assert f'"{esquema}"' not in ejecutable, (
            f"`{esquema}` esta cableado en apply_grants: la lista vive en la "
            "configuracion, no en el codigo (R25)"
        )


def test_f057_r25_personal_en_esquemas_del_datamart() -> None:
    """PROPAGACION 7/12. Lo que hace que las puertas MIREN el esquema.

    Sin esto, el validador del diccionario no exige entrada para `personal`
    (R4 de F-006) y `check-declarados` no lo cuenta.
    """
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART

    assert "personal" in ESQUEMAS_DEL_DATAMART
    assert len(ESQUEMAS_DEL_DATAMART) == 10


def test_f057_r25_el_fichero_de_provision_trae_los_diez_esquemas() -> None:
    """PROPAGACION (pasada 2 del review). `infra/sql/02_roles.sql` crea,
    concede y comprueba los esquemas A MANO en tres listas, y las tres se
    quedaron en nueve: la nocturna no lo nota —`apply-grants` lee la
    configuracion—, pero un reaprovisionamiento del servidor dejaria
    `personal` sin permisos y la comprobacion del punto 6 mentiria.
    """
    from etl_sigrid.domain.diccionario import ESQUEMAS_DEL_DATAMART

    crudo = (RAIZ / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")
    sql = _sin_comentarios(crudo)
    esperado = set(ESQUEMAS_DEL_DATAMART)

    creados = set(re.findall(r"CREATE SCHEMA IF NOT EXISTS (\w+);", sql))
    assert creados == esperado, f"punto 4: crea {sorted(creados)} (R25)"

    concedidos = re.search(r"FOREACH esquema IN ARRAY ARRAY\[(.*?)\]", sql, re.DOTALL)
    assert concedidos, "falta el ARRAY del GRANT del punto 5"
    assert set(re.findall(r"'(\w+)'", concedidos.group(1))) == esperado, (
        "punto 5: el GRANT del MCP no cubre los diez esquemas (R25)"
    )

    comprobados = re.search(r"WHERE nspname IN \((.*?)\)", sql, re.DOTALL)
    assert comprobados, "falta la comprobacion de esquemas del punto 6"
    assert set(re.findall(r"'(\w+)'", comprobados.group(1))) == esperado, (
        "punto 6: la comprobacion no lista los diez esquemas (R25)"
    )
    assert "nueve" not in crudo, "`02_roles.sql` sigue hablando de nueve esquemas"


def test_f057_r26_check_declarados_cubre_personal() -> None:
    """PROPAGACION 8/12. Los cuatro objetos entran en el inventario.

    `check-declarados` contrasta lo que el SQL del repositorio DECLARA contra el
    catalogo real. Si el inventario no ve `sql/personal/**`, una noche que no
    construya el esquema terminaria en verde mintiendo.
    """
    from etl_sigrid.infrastructure.inventario_repositorio import (
        inventario_del_repositorio,
    )

    # El inventario REAL, el mismo que lee `check-declarados`, y no un glob
    # escrito aqui: lo que hay que demostrar es que la puerta ve la carpeta
    # nueva, no que la expresion regular sepa leer un CREATE.
    nombres = {o.nombre: o.tipo for o in inventario_del_repositorio()}

    assert nombres.get("personal.recursos") == "tabla"
    assert nombres.get("personal.partes_lineas") == "tabla"
    assert nombres.get("personal.v_pbi_horas_obra_mes") == "vista"
    assert nombres.get("personal.fn_fecha") == "funcion"


def test_f057_r26_no_hay_pendientes_declarados() -> None:
    """PROPAGACION 8/12 (b). La lista de pendientes es un trinquete: solo baja.

    Los cuatro objetos se construyen en esta feature, asi que ninguno se aplaza.
    """
    import yaml

    pendientes = yaml.safe_load(
        (RAIZ / "config" / "objetos_pendientes.yaml").read_text(encoding="utf-8")
    )
    declarados = (pendientes or {}).get("pendientes") or []

    assert not [p for p in declarados if str(p).startswith("personal.")], (
        "`personal` no aplaza ningun objeto (R26)"
    )


# ===========================================================================
# LA FICHA · lo unico que el agente del MCP lee antes de consultar
# ===========================================================================


@cache
def _diccionario():
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


def _ficha_de(objeto: str):
    fichas = {f.objeto: f for f in _diccionario().fichas if f.esquema == "personal"}
    assert objeto in fichas, f"falta la ficha de personal.{objeto} (R23)"
    return fichas[objeto]


def test_f057_r23_fichas_de_los_tres_objetos() -> None:
    """PROPAGACION 11/12. El YAML nuevo, con sus tres fichas y la del esquema."""
    assert (DIR_DICCIONARIO / "personal.yaml").exists()

    for objeto, tipo in (
        ("recursos", "tabla"),
        ("partes_lineas", "tabla"),
        ("v_pbi_horas_obra_mes", "vista"),
    ):
        ficha = _ficha_de(objeto)
        assert ficha.tipo == tipo
        assert ficha.paso_etl == "build_personal"
        assert ficha.refresco == "nocturno"

    entrada = _diccionario().esquemas.get("personal")
    assert entrada is not None, "`personal` necesita entrada en 00_global.yaml (R23)"
    assert entrada["refresco"] == "nocturno"
    assert entrada["consumo_recomendado"] is True


def test_f057_r23_el_diccionario_sube_de_version() -> None:
    """La version es lo que el MCP ve para saber que el contrato cambio."""
    assert int(_diccionario().version) >= 25


def test_f057_r23_el_diccionario_real_sigue_validando() -> None:
    """La ficha nueva no puede romper el diccionario entero.

    Es la puerta que `bash harness/init.sh` recorre: aqui se adelanta para no
    descubrirlo trece minutos despues.
    """
    import main
    from etl_sigrid.domain.diccionario import validar

    pasos = tuple(p.name for p in main.build_pipeline_steps(_settings_falso()))
    errores = validar(_diccionario(), pasos)

    assert errores == [], "\n".join(f"{e.objeto}: {e.detalle}" for e in errores[:10])


def test_f057_r9_ficha_declara_datos_personales() -> None:
    """Quien consulte tiene que SABER que esta mirando datos personales."""
    ficha = _ficha_de("recursos")
    texto = ficha.descripcion.lower()

    assert "dato" in texto and "personal" in texto, (
        "la ficha de `personal.recursos` tiene que declarar que contiene datos "
        "personales: nombre, NIF y DNI (R9)"
    )
    assert "2026-09-18" in ficha.descripcion, (
        "la autorizacion del humano va con su fecha: es una decision del "
        "responsable del dato, no un descuido (R9)"
    )


def test_f057_r5_ficha_declara_el_43_por_ciento_de_horas_de_recursos_de_baja() -> None:
    """Filtrar por `activo` borra 539.774,87 de 1.249.038,44 horas.

    El recurso de baja de hoy trabajo ayer: esa cifra es la que impide que
    alguien «limpie» la consulta y pierda el 43,2 % sin enterarse.
    """
    texto = _ficha_de("recursos").descripcion + str(
        next(c.significado for c in _ficha_de("recursos").columnas if c.nombre == "activo")
    )

    assert "43,2" in texto
    assert "539.774,87" in texto


def test_f057_r18_ficha_prohibe_sumar_cantidad() -> None:
    """LA TRAMPA QUE HACE FALSA UNA SUMA, escrita donde el agente la lee.

    `SUM(cantidad)` sin filtrar `unidad` suma horas de albanil con meses de
    jefe de obra, dias de vacaciones y kilometros: 1.837.201,23 de nada.
    """
    ficha = _ficha_de("partes_lineas")
    cantidad = next(c for c in ficha.columnas if c.nombre == "cantidad")

    assert "unidad" in cantidad.significado.lower()
    assert "1.837.201,23" in cantidad.significado, (
        "la cifra del error es lo que hace que la advertencia se respete (R18)"
    )
    unidad = next(c for c in ficha.columnas if c.nombre == "unidad")
    assert set(unidad.valores) == {"HORA", "DIA", "MES", "UD", "DESCONOCIDA"}
    assert "71,7" in ficha.descripcion, (
        "el 71,7 % del euro esta en las lineas de MES, no en las de hora (R18)"
    )


def test_f057_r20_ficha_declara_los_defectos_de_calidad_medidos() -> None:
    """No se corrigen en origen: se declaran. 5 fechas a 0, una del ano 3103."""
    fecha = next(
        c for c in _ficha_de("partes_lineas").columnas if c.nombre == "fecha"
    )
    texto = fecha.significado + (fecha.nulo_significa or "")

    assert "3103" in texto


def test_f057_r26_claves_y_relaciones_declaradas() -> None:
    """PROPAGACION 9/12 y 10/12. `check-unicidad` y `check-relaciones`.

    Los dos comandos se alimentan del diccionario, asi que cubren `personal` en
    cuanto el YAML declara `clave_negocio` y `relaciones`: lo que hay que
    escribir es el YAML, no el comando.
    """
    assert _ficha_de("recursos").clave_negocio == ("recurso_id",)
    assert _ficha_de("partes_lineas").clave_negocio == ("linea_id",)

    destinos = {r.de: r.a for r in _ficha_de("partes_lineas").relaciones}

    assert destinos.get("obra_id") == "maestro.obras.obra_id"
    assert destinos.get("partida_id") == "stg.partidas.partida_id"
    assert destinos.get("recurso_id") == "personal.recursos.recurso_id"


def test_f057_r21_la_vista_es_superficie_de_consumo_recomendada() -> None:
    """Es la respuesta por defecto a «horas imputadas a una obra» (R21)."""
    ficha = _ficha_de("v_pbi_horas_obra_mes")

    assert ficha.consumo_recomendado is True
    assert ficha.ejemplos_preguntas, "sin ejemplos no se enruta la pregunta"
    assert "HORA" in ficha.descripcion or "hora" in ficha.grano.lower()
