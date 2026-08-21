# tests/test_f006_fuente_que_gobierna.py
"""
Cada afirmación se contrasta con la fuente que GOBIERNA el hecho (8ª pasada).

Dos pasadas seguidas corrigiendo afirmaciones sobre el origen, y cada corrección
metió otra mentira. La causa no era descuido: era **escribirlas por
reconstrucción** y contrastarlas después contra una fuente que habla de otra
cosa.

    séptima pasada · «las 31 tablas se cargan incremental por `tiemod`»
        derivado de `config/tables_sigrid.yaml`, que declara una columna de
        corte que la ingesta no usa. Falso.

    octava pasada · «append por `MAX(ide)`; lo modificado no se refresca nunca»
        derivado de `ingest_raw_step.py`, que dice cómo funciona el paso pero
        **no qué se ejecuta de noche**. Falso también, y por el otro lado: el
        `Dockerfile` arranca `run-all --full`.

El criterio que aplica este fichero, y que el líder fijó como instrucción:

1. **Si una afirmación no es derivable de una fuente comprobable, no se
   escribe.** Ni reformulada ni matizada. Se omite, y si el hueco importa se
   declara como hueco.
2. **Se identifica la fuente que gobierna el hecho ANTES de derivar de ella.**
   «Qué corre de noche» lo gobierna el `Dockerfile`; «cómo carga el comando», el
   paso; «cómo se llama la bandera», el CLI.

Las fuentes que gobiernan, y lo que cada una decide:

| Hecho | Fuente que lo gobierna |
|---|---|
| Qué se ejecuta en el job nocturno | `Dockerfile` (`CMD`) |
| Cómo carga el comando según la bandera | `ingest_raw_step.py` |
| Cómo se llama la bandera | `main.py` (los `click.option`) |
| Qué campos propios de `raw` existen y se usan | nuestro SQL, que no correría contra columnas inexistentes |

`azure-apps/sigrid_tablas.md` **no está en esa tabla, y es deliberado**: es la
conversión literal de un PDF de 380 páginas y no se deja segmentar. Lo intenté
dos veces y las dos produjo una afirmación falsa —`cen.res`, que en realidad es
de `cenrep`—. Medido: mi segmentador da a `obr` un bloque de **1252 líneas** con
once `cod` y veintiún `res` dentro, porque se traga las entidades intermedias.
Lo que ese documento dice **no se afirma en ninguna ficha**.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

import pytest
import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
DOCKERFILE = RAIZ / "Dockerfile"
CLI = RAIZ / "main.py"
PASO_INGESTA = RAIZ / "etl_sigrid" / "application" / "steps" / "ingest_raw_step.py"


@lru_cache(maxsize=1)
def _fichas_raw() -> dict[str, dict]:
    doc = yaml.safe_load((DIR_DICCIONARIO / "raw.yaml").read_text(encoding="utf-8"))
    return doc["objetos"]


def _nombres() -> list[str]:
    return sorted(_fichas_raw())


# ---------------------------------------------------------------------------
# 1 · Qué corre de noche lo gobierna el Dockerfile
# ---------------------------------------------------------------------------


def test_f006_r13_el_job_nocturno_hace_recarga_completa() -> None:
    """El ancla del hecho. Si la imagen cambia, las 31 fichas quedan obsoletas.

    `infra/80_create_job.ps1` lo dice sin rodeos: «el alcance de la carga
    nocturna está escrito en el Dockerfile y en ningún sitio más». Pues ahí se
    comprueba.
    """
    texto = DOCKERFILE.read_text(encoding="utf-8")
    cmd = re.search(r'CMD\s*\[(.*?)\]', texto, re.S)
    assert cmd, "el Dockerfile ya no declara un CMD"
    argumentos = re.findall(r'"([^"]+)"', cmd.group(1))
    assert argumentos[0] == "run-all", f"el job nocturno ya no es `run-all`: {argumentos}"
    assert "--full" in argumentos, (
        f"el job nocturno ya NO pasa `--full`: {argumentos}. Si eso es "
        f"deliberado, las 31 fichas de `raw` describen una recarga que dejó de "
        f"ocurrir y hay que reescribirlas"
    )


def test_f006_r13_full_trunca_y_recarga() -> None:
    """Y qué significa `--full` lo gobierna el paso."""
    codigo = PASO_INGESTA.read_text(encoding="utf-8")
    assert re.search(
        r"if\s+self\._full_refresh:\s*\n\s*pg\.truncate_table\(", codigo
    ), "`--full` ya no trunca la tabla antes de recargar"
    assert re.search(
        r"last_id_already\s*=\s*pg\.get_max_id\(", codigo
    ), "sin `--full` ya no arranca el cursor en el MAX(ide) guardado"


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r13_la_ficha_dice_que_de_noche_se_recarga_entera(nombre: str) -> None:
    """Lo que el agente necesita saber es de cuándo es el dato que está leyendo."""
    texto = _fichas_raw()[nombre]["descripcion"]
    assert "recarga entera" in texto, (
        f"la ficha de raw.{nombre} no dice que el job nocturno recarga la tabla "
        f"entera. Es lo que decide cuán viejo es el dato"
    )
    assert "no se refresca" not in texto, (
        f"la ficha de raw.{nombre} sigue diciendo que lo modificado no se "
        f"refresca. Eso es cierto SOLO sin `--full`, y el job nocturno lo pasa"
    )


# ---------------------------------------------------------------------------
# 2 · Los nombres de comando y de bandera los gobierna el CLI
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _banderas_del_cli() -> frozenset[str]:
    """Las opciones largas que `main.py` declara de verdad."""
    return frozenset(re.findall(r'click\.option\(\s*"(--[\w-]+)"', CLI.read_text(encoding="utf-8")))


def test_f006_r13_el_cli_declara_full_y_no_full_refresh() -> None:
    """El control del control: si el CLI cambiase, este test lo dice."""
    banderas = _banderas_del_cli()
    assert "--full" in banderas
    assert "--full-refresh" not in banderas, (
        "si `--full-refresh` llegara a existir, revisar las fichas: se publicó "
        "31 veces cuando no existía"
    )


def _banderas_citadas(texto: str) -> set[str]:
    return set(re.findall(r"`(--[\w-]+)`", texto))


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r13_las_banderas_que_cita_la_ficha_existen(nombre: str) -> None:
    """Un comando inejecutable publicado es peor que no dar el comando."""
    ficha = _fichas_raw()[nombre]
    texto = f"{ficha['descripcion']} {ficha.get('motivo_no_consumo', '')}"
    inventadas = _banderas_citadas(texto) - _banderas_del_cli()
    assert inventadas == set(), (
        f"raw.{nombre} cita {sorted(inventadas)}, que el CLI no declara. Las "
        f"banderas se copian de `main.py`, no de memoria"
    )


def test_f006_r13_el_detector_de_banderas_reconoce_una_inventada() -> None:
    """Control: si no detectase, los 31 de arriba pasarían en falso."""
    assert _banderas_citadas("lanza `--full-refresh` a mano") == {"--full-refresh"}
    assert "--full-refresh" not in _banderas_del_cli()


# ---------------------------------------------------------------------------
# 3 · Qué campos propios de `raw` existen lo gobierna nuestro SQL
# ---------------------------------------------------------------------------
#
# No el catálogo de Sigrid. Nuestro SQL no correría contra una columna que no
# existe, así que cada `alias.cod` que aparece ahí es una columna real de esa
# tabla, leída SIN pasar por `con`. Es la única fuente de primera mano que
# tenemos sobre el origen, y es la que estaba sin usar cuando se inventó
# `cen.res`.

#: Los campos cuyo «¿vive en `con` o en la tabla específica?» es la duda que
#: `R-SIGRID-CON` existe para resolver.
CAMPOS_DEL_PATRON = ("cod", "res", "fec", "raz", "cif")


#: Palabras que nunca son un alias, aunque sigan a `raw.<tabla>`.
_NO_SON_ALIAS = frozenset(
    {"ON", "WHERE", "LEFT", "RIGHT", "FULL", "JOIN", "INNER", "OUTER", "CROSS",
     "GROUP", "ORDER", "UNION", "SELECT", "AND", "OR", "USING", "LIMIT", "HAVING",
     "WITH", "AS", "SET", "VALUES", "RETURNING"}
)


def sentencias(sql: str) -> list[str]:
    """Trocea un fichero SQL en sentencias, que es el ámbito de un alias.

    **Este trozo es el que estaba mal y produjo una lista incompleta.** El
    derivador mapeaba alias→tabla con un `dict` **por fichero**, y en
    `compras/01_documentos.sql` las tres tablas de línea comparten el alias `l`:

        FROM raw.ctrpro l    (línea 61)
        FROM raw.dcapro l    (línea 126)
        FROM raw.dcfpro l    (línea 179)

    Las tres proyectan `l.res AS descripcion`. El `dict` se quedaba con la
    última, así que `ctrpro.res` y `dcapro.res` desaparecían de la derivación y
    de la regla que la copia.

    Es el mismo vicio que ya apareció en `_proyeccion_de`, que leía el fichero
    entero cuando ese fichero construye **seis objetos**: aquí también hay que
    tratarlo como seis ámbitos, no como uno.
    """
    limpio = re.sub(r"--[^\n]*", " ", sql)
    return [s for s in limpio.split(";") if s.strip()]


def alias_de_raw(sentencia: str) -> dict[str, str]:
    """Alias → tabla de `raw` dentro de UNA sentencia."""
    alias: dict[str, str] = {}
    for m in re.finditer(r"\braw\.(\w+)\s+(?:AS\s+)?(\w+)\b", sentencia, re.IGNORECASE):
        if m.group(2).upper() in _NO_SON_ALIAS:
            continue
        alias[m.group(2)] = m.group(1).lower()
    return alias


@lru_cache(maxsize=1)
def campos_propios_usados() -> dict[str, tuple[str, ...]]:
    """Por tabla de `raw`, qué campos propios lee nuestro SQL directamente."""
    usos: dict[str, set[str]] = {}
    for fichero in sorted(DIR_SQL.rglob("*.sql")):
        for sentencia in sentencias(fichero.read_text(encoding="utf-8")):
            for al, tabla in alias_de_raw(sentencia).items():
                for campo in CAMPOS_DEL_PATRON:
                    if re.search(rf"\b{re.escape(al)}\.{campo}\b", sentencia):
                        usos.setdefault(tabla, set()).add(campo)
    usos.pop("con", None)
    return {t: tuple(sorted(c)) for t, c in sorted(usos.items())}


def test_f006_r9_el_derivador_de_campos_propios_encuentra_los_conocidos() -> None:
    """Control del detector, con dos casos verificados por partida doble.

    `prv.cif` y `prv.raz` los toma `maestro/02_proveedores.sql` de `raw.prv`, y
    `obrparpar.cod`/`.res` son el código y la descripción de la partida en
    `stg/04_partidas.sql`. Si el derivador dejara de verlos, la regla se quedaría
    sin su lista y nadie se enteraría.
    """
    campos = campos_propios_usados()
    assert campos.get("prv") == ("cif", "raz")
    assert campos.get("obrparpar") == ("cod", "res")
    assert "cen" not in campos, (
        "nuestro SQL no lee ningún campo propio de `raw.cen`: el nombre del "
        "centro sale de `con.res`. Fue el campo inventado de la 8ª pasada"
    )


def campos_que_declara_la_regla() -> dict[str, tuple[str, ...]]:
    """El mapa tabla -> campos que el punto 3 de la regla publica.

    Se lee de la forma `` `tabla.campo` ``, que es como la escribe el generador.
    Comparar NOMBRES no bastaba: el punto 2 nombra las diez «Propiedades de
    `con`» para otra cosa, y el test las contaba como si el punto 3 las
    declarase. Comparando el mapa entero, la confusión no cabe.
    """
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    regla = next(r for r in dicc.reglas if r.codigo == "R-SIGRID-CON")
    mapa: dict[str, set[str]] = {}
    for tabla, campo in re.findall(r"`(\w+)\.(\w+)`", regla.regla):
        # `con.res` se menciona al cierre de la regla como el nombre legible
        # que usa el datamart: es otra afirmacion, no una excepcion del punto 3.
        if campo in CAMPOS_DEL_PATRON and tabla != "con":
            mapa.setdefault(tabla, set()).add(campo)
    return {t: tuple(sorted(c)) for t, c in mapa.items()}


def test_f006_r9_la_regla_declara_exactamente_los_campos_derivados() -> None:
    """La lista se DERIVA; escrita a mano acertó 1 de 7 y se dejó 16."""
    declarados = campos_que_declara_la_regla()
    derivados = campos_propios_usados()
    assert declarados == derivados, (
        f"el punto 3 de la regla y el barrido del SQL no coinciden. "
        f"  solo en la regla: "
        f"{ {k: v for k, v in declarados.items() if derivados.get(k) != v} }; "
        f"  solo en el SQL:   "
        f"{ {k: v for k, v in derivados.items() if declarados.get(k) != v} }"
    )


def test_f006_r9_control_el_lector_de_la_regla_lee_algo() -> None:
    """Sin esto, un cambio de formato dejaría el mapa vacío y el test en verde."""
    declarados = campos_que_declara_la_regla()
    assert len(declarados) >= 10, (
        f"el lector solo encuentra {len(declarados)} tablas en la regla: o el "
        f"formato cambió, o el punto 3 se ha quedado sin lista"
    )


@lru_cache(maxsize=1)
def tablas_sin_relacion_con_con() -> tuple[str, ...]:
    """Tablas de `raw` que ningún SQL une con `raw.con`.

    Para ellas el JOIN que sugiere la regla **no existe**, así que decirles «une
    con `con` para tener el nombre» las manda a un sitio inexistente.
    """
    usadas: set[str] = set()
    con_con: set[str] = set()
    for fichero in sorted(DIR_SQL.rglob("*.sql")):
        texto = re.sub(r"--[^\n]*", " ", fichero.read_text(encoding="utf-8"))
        tablas = {m.group(1).lower() for m in re.finditer(r"\braw\.(\w+)\b", texto)}
        usadas |= tablas
        if "con" in tablas:
            con_con |= tablas
    return tuple(sorted(usadas - con_con - {"con"}))


def test_f006_r9_la_regla_avisa_de_las_tablas_que_no_cuelgan_de_con() -> None:
    """Los catálogos `aux*` no tienen ninguna relación con `con`."""
    from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    regla = next(r for r in dicc.reglas if r.codigo == "R-SIGRID-CON")
    sueltas = tablas_sin_relacion_con_con()
    assert sueltas, "el derivador no encuentra ninguna; revisar antes de fiarse"
    faltan = [t for t in sueltas if f"`{t}`" not in regla.regla]
    assert faltan == [], (
        f"la regla no avisa de que {faltan} no se unen a `con` en ningún SQL: "
        f"el JOIN que sugiere no existe para ellas"
    )


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r26_ninguna_ficha_atribuye_a_su_tabla_un_campo_no_derivado(
    nombre: str,
) -> None:
    """Una ficha tampoco puede afirmar lo que la regla ya no afirma.

    El barrido de frases rechazadas buscaba la cadena literal `cen.res`, y las
    fichas lo decían con otras palabras —«tiene un `res` propio, que es "Reparto
    nombre"»—, así que sobrevivió a la corrección de la regla. Sexto asomo del
    patrón de la copia, y esta vez cazado antes de publicarlo.

    Aquí no se busca una frase: se comprueba la **afirmación**. Si una ficha dice
    que su tabla tiene un `cod`/`res`/`fec`/`raz`/`cif` propio, el barrido del
    SQL tiene que respaldarlo.
    """
    ficha = _fichas_raw()[nombre]
    texto = f"{ficha['descripcion']} {ficha.get('motivo_no_consumo', '')}"
    respaldados = set(campos_propios_usados().get(nombre, ()))

    afirmados: set[str] = set()
    # `tabla.campo` cualificado, y la forma en prosa «un `res` propio».
    afirmados |= {
        c for t, c in re.findall(r"`(\w+)\.(\w+)`", texto)
        if t == nombre and c in CAMPOS_DEL_PATRON
    }
    afirmados |= {
        c for c in re.findall(r"`(\w+)`\s+propi", texto) if c in CAMPOS_DEL_PATRON
    }
    afirmados |= {
        c for c in re.findall(r"campos? propios?[^.]*?`(\w+)`", texto)
        if c in CAMPOS_DEL_PATRON
    }

    sin_respaldo = afirmados - respaldados
    assert sin_respaldo == set(), (
        f"raw.{nombre} atribuye a su propia tabla {sorted(sin_respaldo)} y el "
        f"barrido del SQL no lo respalda (lee {sorted(respaldados) or 'ninguno'}). "
        f"Si solo lo dice `sigrid_tablas.md`, no se afirma: ese documento no es "
        f"una fuente de la que derivar"
    )


def test_f006_r26_control_el_detector_de_atribuciones_muerde() -> None:
    """Con la frase que sobrevivió, para que no vuelva a colarse en silencio."""
    texto = 'tiene un `res` propio, que es "Reparto nombre"'
    afirmados = {c for c in re.findall(r"`(\w+)`\s+propi", texto) if c in CAMPOS_DEL_PATRON}
    assert afirmados == {"res"}
    assert "cen" not in campos_propios_usados()
