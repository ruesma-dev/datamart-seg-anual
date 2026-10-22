# tests/test_f147_resumen_reglas.py
"""
F-147 · Resumen y entrega por regla: el contrato aditivo con `mcp-bbdd` (R1-R6).

Cada regla dura publica un `resumen` corto que basta por sí solo y una
`entrega` (`resumen` | `entera` | `fuera_mcp`). Lo que se prueba aquí es la
mitad de este repositorio del contrato pactado en T1 con `mcp-bbdd`:

* las dos columnas van AL FINAL de `_meta.diccionario_reglas`, sin tocar las
  siete que el MCP lee hoy;
* el DDL las añade sin tomar un `ACCESS EXCLUSIVE` en cada publicación;
* la base GARANTIZA lo que el MCP da por hecho (petición A de `mcp-bbdd`):
  `entrega` en (`resumen`, `entera`) y un `resumen` de 1 a 250 caracteres;
* las `fuera_mcp` no llegan a la tabla y `n_reglas` solo cuenta las publicadas
  (petición C).

Ningún test de este fichero abre red ni BBDD. La prueba del DDL contra un
PostgreSQL real (clúster desechable en local) está en `progress/impl_F-147.md`.
"""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from etl_sigrid.domain.diccionario import (
    ENTREGAS,
    RESUMEN_MAX,
    RESUMEN_MIN,
    Regla,
    validar,
)
from tests.test_f006_formato import (
    GLOBAL_MINIMO,
    PASOS_NOCTURNOS,
    _dicc,
    _directorio,
    _regla,
    _reglas_minimas,
)

RAIZ = Path(__file__).resolve().parents[1]
DDL = RAIZ / "etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql"

#: Las siete columnas que `mcp-bbdd` lee hoy, en su orden (contrato de F-006).
COLUMNAS_LEIDAS_HOY = ["codigo", "titulo", "severidad", "ambito", "regla", "motivo", "orden"]

RESUMEN_VALIDO = (
    "Haz esto y no aquello: nombra la columna exacta y dilo en la respuesta."
)


def _ddl_sin_comentarios() -> str:
    return re.sub(r"--[^\n]*", " ", DDL.read_text(encoding="utf-8"))


def _con(codigo: str, **kwargs) -> list[Regla]:
    """Las reglas obligatorias más una nueva `codigo` con `kwargs`."""
    reglas = _reglas_minimas()
    reglas.append(_regla(codigo, **kwargs))
    return reglas


# ---------------------------------------------------------------------------
# R1 · Las claves `resumen` y `entrega`
# ---------------------------------------------------------------------------


def test_f147_r1_regla_gana_resumen_y_entrega_al_final() -> None:
    """Los campos nuevos van detrás de los de siempre: nadie que construya una
    `Regla` por posición ve sus argumentos corridos."""
    nombres = [f.name for f in fields(Regla)]

    assert nombres[:7] == ["codigo", "titulo", "severidad", "ambito", "regla", "motivo", "orden"]
    assert nombres[7:] == ["resumen", "entrega"]
    assert Regla("R-X", "t", "bloqueante", ("mart",), "r", "m").entrega == "resumen"


def test_f147_r1_el_vocabulario_de_entrega_es_cerrado() -> None:
    assert ENTREGAS == ("resumen", "entera", "fuera_mcp")


def test_f147_r1_cargador_lee_resumen_y_entrega(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    global_yaml = GLOBAL_MINIMO.replace(
        "    motivo: Bug de la Tanda 1.4; multiplicaba por nueve.\n",
        "    motivo: Bug de la Tanda 1.4; multiplicaba por nueve.\n"
        f"    resumen: {RESUMEN_VALIDO}\n"
        "    entrega: entera\n",
    )
    dicc, _ = cargar_diccionario(_directorio(tmp_path, **{"00_global.yaml": global_yaml}))

    regla = dicc.reglas[0]
    assert regla.resumen == RESUMEN_VALIDO
    assert regla.entrega == "entera"


def test_f147_r1_sin_entrega_el_cargador_entiende_resumen(tmp_path) -> None:
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(_directorio(tmp_path))

    assert dicc.reglas[0].entrega == "resumen"


# ---------------------------------------------------------------------------
# R2 · Resumen obligatorio y acotado
# ---------------------------------------------------------------------------


def test_f147_r2_una_regla_sin_resumen_falla_nombrandola() -> None:
    errores = validar(_dicc(reglas=_con("R-NUEVA", resumen="")), PASOS_NOCTURNOS)

    assert any(e.objeto == "R-NUEVA" and "resumen" in e.detalle for e in errores), errores


@pytest.mark.parametrize("longitud", [RESUMEN_MIN - 1, RESUMEN_MAX + 1])
def test_f147_r2_un_resumen_fuera_de_los_limites_falla(longitud: int) -> None:
    errores = validar(
        _dicc(reglas=_con("R-NUEVA", resumen="x" * longitud)), PASOS_NOCTURNOS
    )

    assert any(e.objeto == "R-NUEVA" and "resumen" in e.detalle for e in errores), errores


@pytest.mark.parametrize("longitud", [RESUMEN_MIN, RESUMEN_MAX])
def test_f147_r2_los_limites_incluidos_validan(longitud: int) -> None:
    assert validar(
        _dicc(reglas=_con("R-NUEVA", resumen="x" * longitud)), PASOS_NOCTURNOS
    ) == []


def test_f147_r2_el_resumen_se_mide_sin_los_blancos_de_los_extremos() -> None:
    """La base mide `char_length(btrim(resumen))`: el validador, igual."""
    relleno = "   " + "x" * (RESUMEN_MIN - 1) + "   "

    errores = validar(_dicc(reglas=_con("R-NUEVA", resumen=relleno)), PASOS_NOCTURNOS)

    assert any(e.objeto == "R-NUEVA" for e in errores)


def test_f147_r2_tambien_las_fuera_mcp_llevan_resumen() -> None:
    errores = validar(
        _dicc(reglas=_con("R-NUEVA", resumen="", entrega="fuera_mcp")), PASOS_NOCTURNOS
    )

    assert any(e.objeto == "R-NUEVA" and "resumen" in e.detalle for e in errores)


def test_f147_r2_el_tope_del_validador_es_el_check_de_la_base() -> None:
    """Petición A de `mcp-bbdd`: la base rechaza un resumen de más de 250. Si el
    validador admitiera más, la publicación reventaría en Azure en vez de en
    `init.sh`. Los dos números son el mismo, leído del DDL."""
    patron = re.compile(
        r"char_length\s*\(\s*btrim\s*\(\s*resumen\s*\)\s*\)\s+BETWEEN\s+(\d+)\s+AND\s+(\d+)",
        re.IGNORECASE,
    )
    coincidencia = patron.search(_ddl_sin_comentarios())

    assert coincidencia, "falta el CHECK del resumen en el DDL"
    assert int(coincidencia.group(1)) == 1
    assert int(coincidencia.group(2)) == RESUMEN_MAX
    assert RESUMEN_MIN >= 1


# ---------------------------------------------------------------------------
# R3 · Vocabulario de entrega
# ---------------------------------------------------------------------------


def test_f147_r3_una_entrega_inventada_falla_con_el_vocabulario() -> None:
    errores = validar(
        _dicc(reglas=_con("R-NUEVA", resumen=RESUMEN_VALIDO, entrega="parcial")),
        PASOS_NOCTURNOS,
    )

    assert any(
        e.objeto == "R-NUEVA" and "resumen | entera | fuera_mcp" in e.detalle
        for e in errores
    ), errores


@pytest.mark.parametrize("entrega", ENTREGAS)
def test_f147_r3_las_entregas_del_vocabulario_validan(entrega: str) -> None:
    assert validar(
        _dicc(reglas=_con("R-NUEVA", resumen=RESUMEN_VALIDO, entrega=entrega)),
        PASOS_NOCTURNOS,
    ) == []


# ---------------------------------------------------------------------------
# R4 · Las dos columnas, AL FINAL
# ---------------------------------------------------------------------------


def test_f147_r4_el_insert_lleva_las_columnas_nuevas_al_final() -> None:
    from etl_sigrid.infrastructure.postgres.diccionario_sql import SQL_INSERT_REGLA

    columnas = re.search(r"\((.*?)\)\s*VALUES", SQL_INSERT_REGLA, re.DOTALL).group(1)
    nombres = [c.strip() for c in columnas.split(",")]

    assert nombres == COLUMNAS_LEIDAS_HOY + ["resumen", "entrega"]
    assert SQL_INSERT_REGLA.count("%s") == 9


def test_f147_r4_las_filas_traen_resumen_y_entrega_detras_de_lo_de_siempre() -> None:
    from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_reglas

    regla = _regla(
        "R-NUEVA", resumen=RESUMEN_VALIDO, entrega="entera", ambito=("mart", "stg")
    )
    filas = filas_reglas(_dicc(reglas=[regla]))

    assert filas == [
        (
            "R-NUEVA",
            regla.titulo,
            "bloqueante",
            ["mart", "stg"],
            regla.regla,
            regla.motivo,
            0,
            RESUMEN_VALIDO,
            "entera",
        )
    ]


def test_f147_r4_el_create_table_conserva_las_siete_columnas_del_contrato() -> None:
    """Lo que `mcp-bbdd` lee hoy no cambia de nombre, tipo ni posición: las
    columnas nuevas no se cuelan en el `CREATE TABLE`, se añaden después."""
    from tests.test_f006_fichas import columnas_del_create_table

    reales = columnas_del_create_table(
        DDL.read_text(encoding="utf-8"), "_meta.diccionario_reglas"
    )

    assert reales == COLUMNAS_LEIDAS_HOY


# ---------------------------------------------------------------------------
# R5 · DDL idempotente que no bloquea a los lectores en cada publicación
# ---------------------------------------------------------------------------


def _bloques_do(texto: str) -> list[str]:
    return re.findall(r"DO\s+\$\$(.*?)\$\$\s*;", texto, re.DOTALL | re.IGNORECASE)


def test_f147_r5_ningun_alter_table_fuera_de_un_bloque_do() -> None:
    """`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` toma `ACCESS EXCLUSIVE` AUNQUE
    la columna exista, y este DDL corre en CADA publicación con el MCP leyendo."""
    texto = _ddl_sin_comentarios()
    fuera = re.sub(r"DO\s+\$\$.*?\$\$\s*;", " ", texto, flags=re.DOTALL | re.IGNORECASE)

    assert "ALTER TABLE" not in fuera.upper()
    assert not re.search(r"ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS", texto, re.IGNORECASE)


@pytest.mark.parametrize(
    ("columna", "tipo"),
    [("resumen", r"TEXT\s+NOT\s+NULL\s+DEFAULT\s+''"),
     ("entrega", r"TEXT\s+NOT\s+NULL\s+DEFAULT\s+'resumen'")],
)
def test_f147_r5_cada_columna_se_anade_solo_si_falta(columna: str, tipo: str) -> None:
    cuerpo = " ".join(_bloques_do(_ddl_sin_comentarios()))
    normal = re.sub(r"\s+", " ", cuerpo)

    guarda = re.search(
        rf"IF NOT EXISTS \( SELECT 1 FROM information_schema\.columns WHERE "
        rf"table_schema = '_meta' AND table_name = 'diccionario_reglas' AND "
        rf"column_name = '{columna}' \) THEN ALTER TABLE _meta\.diccionario_reglas "
        rf"ADD COLUMN {columna} ",
        normal,
        re.IGNORECASE,
    )
    assert guarda, f"`{columna}` no se añade dentro de su guarda de information_schema"
    assert re.search(rf"ADD COLUMN {columna} {tipo}", normal, re.IGNORECASE)


# ---------------------------------------------------------------------------
# Petición A de `mcp-bbdd`: la base garantiza lo que el MCP da por hecho
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "expresion"),
    [
        ("diccionario_reglas_entrega_check",
         r"CHECK \( ?entrega IN \( ?'resumen', ?'entera' ?\) ?\)"),
        ("diccionario_reglas_resumen_check",
         r"CHECK \( ?char_length\( ?btrim\( ?resumen ?\) ?\) BETWEEN 1 AND 250 ?\)"),
    ],
)
def test_f147_a_el_check_se_anade_not_valid_y_solo_si_falta(
    nombre: str, expresion: str
) -> None:
    """La tabla ya tiene filas cuando llega el DDL nuevo: con `resumen` a ''
    por el DEFAULT, un CHECK validado fallaría. Se añade `NOT VALID` —obliga a
    toda fila NUEVA desde ya— y se valida cuando lo ya escrito cumple."""
    normal = re.sub(r"\s+", " ", " ".join(_bloques_do(_ddl_sin_comentarios())))

    assert re.search(
        rf"IF NOT EXISTS \( SELECT 1 FROM pg_constraint WHERE conrelid = "
        rf"'_meta\.diccionario_reglas'::regclass AND conname = '{nombre}' \) THEN "
        rf"ALTER TABLE _meta\.diccionario_reglas ADD CONSTRAINT {nombre} "
        rf"{expresion} NOT VALID",
        normal,
        re.IGNORECASE,
    ), f"{nombre}: no se añade NOT VALID dentro de su guarda de pg_constraint"


@pytest.mark.parametrize(
    "nombre", ["diccionario_reglas_entrega_check", "diccionario_reglas_resumen_check"]
)
def test_f147_a_el_check_se_valida_solo_cuando_ninguna_fila_lo_incumple(
    nombre: str,
) -> None:
    normal = re.sub(r"\s+", " ", " ".join(_bloques_do(_ddl_sin_comentarios())))

    assert re.search(
        rf"conname = '{nombre}' AND NOT convalidated\b.*?AND NOT EXISTS \( SELECT 1 "
        rf"FROM _meta\.diccionario_reglas WHERE NOT \(.*?\) \) THEN ALTER TABLE "
        rf"_meta\.diccionario_reglas VALIDATE CONSTRAINT {nombre}",
        normal,
        re.IGNORECASE,
    ), f"{nombre}: falta el VALIDATE guardado por `convalidated` y por las filas"


def test_f147_a_el_ddl_no_hace_drop_ni_truncate() -> None:
    """Ni para quitar el DEFAULT: un `DROP` en este fichero es un cambio de API."""
    texto = _ddl_sin_comentarios().upper()

    assert "DROP " not in texto
    assert "TRUNCATE" not in texto


# ---------------------------------------------------------------------------
# R6 · `fuera_mcp` no se publica; `n_reglas` cuenta lo publicado (petición C)
# ---------------------------------------------------------------------------


def _reglas_con_una_fuera() -> list[Regla]:
    return [
        _regla("R-A", resumen=RESUMEN_VALIDO),
        _regla("R-B", resumen=RESUMEN_VALIDO, entrega="entera"),
        _regla("R-C", resumen=RESUMEN_VALIDO, entrega="fuera_mcp"),
    ]


def test_f147_r6_las_fuera_mcp_no_llegan_a_la_tabla() -> None:
    from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_reglas

    filas = filas_reglas(_dicc(reglas=_reglas_con_una_fuera()))

    assert [f[0] for f in filas] == ["R-A", "R-B"]
    assert {f[8] for f in filas} <= {"resumen", "entera"}, "el CHECK de la base"


def test_f147_r6_c_n_reglas_cuenta_solo_las_publicadas() -> None:
    from datetime import datetime

    from etl_sigrid.infrastructure.postgres.diccionario_sql import (
        fila_publicacion,
        filas_reglas,
    )

    dicc = _dicc(reglas=_reglas_con_una_fuera())
    fila = fila_publicacion(dicc, "h" * 64, datetime(2026, 10, 22), None, None)

    assert fila[6] == 2 == len(filas_reglas(dicc))


def test_f147_r6_la_validacion_sigue_aplicandose_a_las_fuera_mcp() -> None:
    """No publicarla no la exime: sigue en el YAML y sigue siendo obligatoria."""
    errores = validar(
        _dicc(reglas=_con("R-NUEVA", resumen=RESUMEN_VALIDO, entrega="fuera_mcp",
                         ambito=("esquema_que_no_existe",))),
        PASOS_NOCTURNOS,
    )

    assert any(e.objeto == "R-NUEVA" and e.regla == "R11" for e in errores)


def test_f147_r6_publicar_manda_nueve_columnas_y_sin_las_fuera_mcp() -> None:
    """Por el cliente real (con una conexión falsa): lo que viaja a la base."""
    from dataclasses import replace
    from datetime import datetime

    from tests.test_f006_publicacion import _cliente_falso, _diccionario_real, _informe_real

    real, hash_fuente = _diccionario_real()
    dicc = replace(real, reglas=tuple(_reglas_con_una_fuera()))
    diario: list = []

    _cliente_falso(diario).publicar_diccionario(
        dicc, hash_fuente=hash_fuente, informe=_informe_real(),
        batch_id=None, ahora=datetime(2026, 10, 22),
    )

    lote = next(d[2] for d in diario if d[0] == "executemany" and "diccionario_reglas" in d[1])
    assert [f[0] for f in lote] == ["R-A", "R-B"]
    assert all(len(f) == 9 for f in lote)
    publicacion = next(
        d[2] for d in diario
        if d[0] == "execute" and "INSERT INTO _meta.diccionario_publicacion" in (d[1] or "")
    )
    assert publicacion[6] == 2
