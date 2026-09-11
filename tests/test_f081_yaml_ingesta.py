# tests/test_f081_yaml_ingesta.py
"""
F-081 · La configuración de la ingesta no puede mentir sobre qué columna
da el nombre legible (criterios 1, 2 y 3).

`config/tables_sigrid.yaml` es **la fuente que gobierna la ingesta**: quien
venga detrás a escribir SQL sobre una tabla de `raw` lee ahí qué es cada
columna. Hasta F-081 decía que el nombre del medio de pago estaba en
`auxefp.est`, y era falso —medido el 2026-09-11 contra Sigrid: `est` viene a
NULL en 5 de las 10 filas y a cadena vacía en las otras 5, mientras que `res`
trae CHEQUE, EFECTIVO, PAGARÉ, TRANSFERENCIA…—. Publicar `est` habría dado una
columna vacía con un nombre convincente y **ningún test se habría enterado**.

## Qué gobierna qué, y por qué el test deriva del SQL

La afirmación no se contrasta contra otro documento —eso es lo que produjo las
dos mentiras que arrastraba F-006— sino contra **nuestro propio SQL**, que es
la única fuente de primera mano: no correría contra una columna inexistente ni
publicaría una columna que no lee. Si el SQL toma el nombre de `res`, el YAML
no puede atribuírselo a otra columna; si el SQL no lee ninguna columna propia
de la tabla —el caso de `cen`, cuyo nombre sale de `raw.con`—, el YAML no puede
atribuirle ninguna.

El mismo criterio de `tests/test_f006_fuente_que_gobierna.py`, aplicado a un
fichero que aquel no mira.

NINGÚN test de este fichero abre red ni BBDD: los dos lados de la comparación
son ficheros del repositorio.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
YAML_INGESTA = RAIZ / "config" / "tables_sigrid.yaml"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"

#: Columnas de Sigrid que pueden llevar un nombre legible. Son las únicas que
#: se buscan en la prosa: `ide`, `tiemod` o `cla` no nombran a nadie.
COLUMNAS_DE_NOMBRE = ("res", "est", "cod", "raz", "nom")

#: Con una de estas palabras, una frase está atribuyendo el nombre legible.
PALABRAS_DE_NOMBRE = ("nombre", "legible", "texto", "literal")

#: Tabla de `raw` → el SQL que GOBIERNA de dónde sale su nombre legible.
#: `auxefp` y `cen` son las dos entradas que mentían; `auxpag`, `auxpro` y
#: `auxmun` entran como control positivo: si el detector solo supiera encender
#: la luz roja, este fichero no probaría nada.
GOBIERNAN = {
    "auxefp": "compras/04_formas_pago.sql",
    "cen": "maestro/04_centros_coste.sql",
    "auxpag": "compras/04_formas_pago.sql",
    "auxpro": "maestro/01_obras.sql",
    "auxmun": "maestro/01_obras.sql",
}


# ---------------------------------------------------------------------------
# Lectura del YAML: el bloque de comentarios de una entrada
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _texto_yaml() -> str:
    return YAML_INGESTA.read_text(encoding="utf-8")


def bloque_de(tabla: str, texto: str | None = None) -> str:
    """Los comentarios de la entrada `source_table: <tabla>`, sin las `#`.

    Va de su `- source_table:` al siguiente, que es exactamente lo que lee
    quien viene a ver qué se ingiere de esa tabla. El `texto` se puede pasar a
    mano para probar el detector contra un YAML inventado.
    """
    texto = _texto_yaml() if texto is None else texto
    inicio = texto.index(f"- source_table: {tabla}\n")
    resto = texto[inicio + 1 :]
    siguiente = resto.find("- source_table:")
    entrada = resto if siguiente == -1 else resto[:siguiente]
    lineas = [
        re.sub(r"^\s*#\s?", "", linea)
        for linea in entrada.split("\n")
        if linea.lstrip().startswith("#")
    ]
    return " ".join(lineas)


def frases(texto: str) -> list[str]:
    """Trocea en frases sin que un `tabla.campo` parta una por la mitad."""
    protegido = re.sub(
        r"`[^`]*`", lambda m: m.group(0).replace(".", "\x00"), texto
    )
    return [trozo.replace("\x00", ".") for trozo in protegido.split(".")]


def columnas_a_las_que_el_yaml_atribuye_el_nombre(
    tabla: str, texto: str | None = None
) -> set[str]:
    """Columnas que la prosa de la entrada presenta como el nombre legible.

    Una columna cuenta si aparece en la MISMA frase que «nombre», «legible»,
    «texto» o «literal». No se miran las referencias cualificadas
    (`auxpag.efeide`) ni las rutas de fichero: hablan de otra tabla o de otro
    sitio, no de una columna propia.
    """
    encontradas: set[str] = set()
    for frase in frases(bloque_de(tabla, texto)):
        limpia = re.sub(r"`[^`]*[./][^`]*`", " ", frase)
        bajada = limpia.lower()
        if not any(palabra in bajada for palabra in PALABRAS_DE_NOMBRE):
            continue
        for columna in COLUMNAS_DE_NOMBRE:
            if re.search(rf"(?<![\w.]){columna}(?![\w.])", limpia):
                encontradas.add(columna)
    return encontradas


# ---------------------------------------------------------------------------
# Lectura del SQL: qué columnas propias de esa tabla publica de verdad
# ---------------------------------------------------------------------------


def campos_propios_que_usa_el_sql(tabla: str, sql_relativo: str) -> set[str]:
    """Columnas de `raw.<tabla>` que el SQL lee, por su alias.

    Es la fuente que gobierna el hecho: el SQL corre cada noche contra Sigrid,
    así que una columna que no existe o que no lee no puede estar aquí.
    """
    sql = (DIR_SQL / sql_relativo).read_text(encoding="utf-8")
    sin_comentarios = re.sub(r"--[^\n]*", " ", sql)
    alias = set(re.findall(rf"\braw\.{tabla}\s+(?:AS\s+)?(\w+)", sin_comentarios))
    campos: set[str] = set()
    for nombre in alias:
        campos.update(re.findall(rf"\b{nombre}\.(\w+)", sin_comentarios))
    return campos


# ---------------------------------------------------------------------------
# Criterio 3 · el YAML no puede volver a declarar el nombre donde no está
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", sorted(GOBIERNAN))
def test_f081_c3_el_yaml_solo_atribuye_el_nombre_a_una_columna_que_el_sql_lee(
    tabla: str,
) -> None:
    """**El test que impide deshacer la corrección en silencio.**

    Si alguien vuelve a escribir que el nombre del medio de pago está en `est`,
    esta comparación se pone en rojo: `04_formas_pago.sql` publica `medio_pago`
    desde `res` y no lee `est` en ninguna parte.
    """
    declaradas = columnas_a_las_que_el_yaml_atribuye_el_nombre(tabla)
    del_sql = campos_propios_que_usa_el_sql(tabla, GOBIERNAN[tabla])

    assert declaradas <= del_sql, (
        f"config/tables_sigrid.yaml atribuye a `{tabla}` "
        f"{sorted(declaradas - del_sql)} como columna de nombre legible, y "
        f"{GOBIERNAN[tabla]} —que es quien gobierna el hecho— solo lee "
        f"{sorted(del_sql)}. Quien lea el YAML publicará una columna que no "
        f"dice lo que el YAML promete."
    )


def test_f081_c1_el_yaml_dice_que_el_nombre_del_medio_de_pago_esta_en_res() -> None:
    """El otro lado de la moneda: no basta con no mentir, tiene que decirlo.

    Un comentario que se limitara a callar dejaría al siguiente adivinando, que
    es de donde salió el error: `est` es texto ilimitado y entra a `raw`, así
    que parece la columna buena hasta que se miran las 10 filas.
    """
    declaradas = columnas_a_las_que_el_yaml_atribuye_el_nombre("auxefp")

    assert declaradas == {"res"}, (
        "la entrada de `auxefp` tiene que decir que el nombre del medio de "
        f"pago está en `res`, y hoy señala {sorted(declaradas) or 'ninguna'}"
    )


def test_f081_c1_el_yaml_deja_escrita_la_medicion_que_lo_respalda() -> None:
    """La afirmación viaja con su medida o no viaja: es lo que distingue este
    comentario del que había, que sonaba igual de seguro y era falso."""
    bloque = bloque_de("auxefp")

    assert "10 filas" in bloque, "la medición es sobre las 10 filas del catálogo"
    assert "2026-09-11" in bloque, "cuándo se midió"
    assert re.search(r"NULL", bloque), "qué trae `est`: NULL en 5 filas"
    assert "vac" in bloque.lower(), "y cadena vacía en las otras 5"


# ---------------------------------------------------------------------------
# Controles · un detector que no muerde no protege nada
# ---------------------------------------------------------------------------


def test_f081_c3_control_el_detector_muerde_con_la_mentira_de_vuelta() -> None:
    """Se le da al detector el texto EXACTO que el YAML tenía antes de F-081 y
    tiene que volver a encenderse. Sin este control, el test de arriba podría
    estar pasando por no encontrar nada que mirar."""
    como_estaba = (
        "- source_table: auxefp\n"
        "    target_table: auxefp\n"
        "    # Medios de pago (10 filas, 13 columnas), a donde apunta\n"
        "    # `auxpag.efeide`. Tiene `tiemod` (medido). Su columna `est` es "
        "texto\n"
        "    # ilimitado y entra: son 10 filas y es lo que da nombre al medio.\n"
    )

    assert columnas_a_las_que_el_yaml_atribuye_el_nombre("auxefp", como_estaba) == {
        "est"
    }, "con la frase de antes de vuelta, el detector tiene que señalar `est`"


def test_f081_c3_control_el_detector_no_confunde_una_columna_con_otra_tabla() -> None:
    """`auxpag.efeide` no es una columna propia de `auxefp`, y una ruta de
    fichero no es una columna de nada: si el detector las contara, el test de
    arriba fallaría por ruido en vez de por una mentira."""
    texto = (
        "Medios de pago. A donde apunta `auxpag.efeide`. El nombre esta en "
        "`res`, que es lo que publica `sql/compras/04_formas_pago.sql`."
    )
    frase_del_nombre = [f for f in frases(texto) if "nombre" in f.lower()]
    assert frase_del_nombre, "la frase del nombre tiene que sobrevivir al troceo"

    limpia = re.sub(r"`[^`]*[./][^`]*`", " ", frase_del_nombre[0])
    encontradas = {
        columna
        for columna in COLUMNAS_DE_NOMBRE
        if re.search(rf"(?<![\w.]){columna}(?![\w.])", limpia)
    }
    assert encontradas == {"res"}


def test_f081_c2_el_sql_de_las_formas_de_pago_publica_el_nombre_desde_res() -> None:
    """Control del otro lado: si este derivador dejara de encontrar `res`, el
    test principal pasaría por vacío en vez de por correcto."""
    campos = campos_propios_que_usa_el_sql("auxefp", "compras/04_formas_pago.sql")

    assert "res" in campos, "04_formas_pago.sql lee `auxefp.res`"
    assert "est" not in campos, "y no lee `est` en ninguna parte"


def test_f081_c2_el_nombre_del_centro_de_coste_no_sale_de_raw_cen() -> None:
    """La segunda mentira encontrada en el barrido, y la que explica por qué el
    test es paramétrico y no un caso suelto.

    La entrada de `cen` decía que bastaba con «ide + res» para mostrar el texto
    de la cabecera del cierre. **`raw.cen` no tiene columna `res`**: medido el
    2026-09-11 contra `INFORMATION_SCHEMA.COLUMNS` de Sigrid, sus 68 columnas
    incluyen `reside`, `resepifor1`…, ninguna `res`. El nombre del centro sale
    de `raw.con`, que es de donde lo toma `04_centros_coste.sql`.
    """
    campos = campos_propios_que_usa_el_sql("cen", "maestro/04_centros_coste.sql")

    assert campos == {"ide"}, (
        "de `raw.cen` el puente solo lee el identificador; el código, el "
        "nombre y la empresa salen de `raw.con`"
    )
