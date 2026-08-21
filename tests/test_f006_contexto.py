# tests/test_f006_contexto.py
"""
Que NADA publicable del bloque global se quede sin viajar (enmienda 2026-08-22).

Es la **tercera** vez que información importante no llega al agente, y las tres
se descubrieron por casualidad:

1. La **regla de oro de Sigrid**, escrita en un comentario YAML. Los comentarios
   no se publican: el MCP no la habría visto nunca.
2. El **aviso de frescura**, en una cabecera de fichero. Igual.
3. **`convenciones` y `ordenes_de_magnitud`**, que el prototipo local servía
   enteros y que `_meta` no publicaba. Salió al implementar el proveedor que lee
   de la base, no de una revisión nuestra.

Tres veces el mismo patrón: alguien escribe algo valioso en un sitio que no
viaja, y nadie se entera hasta que falla en otro repositorio. Así que la
decisión deja de ser implícita: **toda clave del bloque global tiene que estar
clasificada**, publicada o excluida con su razón, y esto lo comprueba.
"""

from __future__ import annotations

import json
import pathlib
from functools import lru_cache

import pytest
import yaml

from etl_sigrid.domain.diccionario import CONTEXTO_NO_PUBLICADO, CONTEXTO_PUBLICADO
from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
from etl_sigrid.infrastructure.postgres.diccionario_sql import filas_contexto

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"


@lru_cache(maxsize=1)
def _dicc():
    return cargar_diccionario(DIR_DICCIONARIO)[0]


@lru_cache(maxsize=1)
def _claves_del_global() -> tuple[str, ...]:
    datos = yaml.safe_load(
        (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    )
    return tuple(datos)


def test_f006_r28_toda_clave_del_global_esta_decidida() -> None:
    """Ni una sola sin clasificar. Si se añade una nueva, esto salta."""
    decididas = set(CONTEXTO_PUBLICADO) | set(CONTEXTO_NO_PUBLICADO)
    sin_decidir = [k for k in _claves_del_global() if k not in decididas]

    assert sin_decidir == [], (
        f"{sin_decidir} del bloque global no está ni publicado ni declarado como "
        f"excluido. Decídelo en `CONTEXTO_PUBLICADO` o en `CONTEXTO_NO_PUBLICADO`: "
        f"un hueco olvidado es lo que ya nos pasó tres veces"
    )


def test_f006_r28_ninguna_clave_esta_en_las_dos_listas() -> None:
    solapadas = set(CONTEXTO_PUBLICADO) & set(CONTEXTO_NO_PUBLICADO)
    assert solapadas == set(), f"{solapadas} están en las dos listas"


def test_f006_r28_lo_excluido_lleva_su_motivo() -> None:
    """Un hueco declarado sin razón es un hueco olvidado con mejor presentación."""
    mudos = [k for k, v in CONTEXTO_NO_PUBLICADO.items() if len(str(v).strip()) < 20]
    assert mudos == [], f"{mudos} se excluyen sin explicar por qué"


def test_f006_r28_ocultar_se_queda_fuera_por_la_razon_cierta() -> None:
    """La razón que hubo escrita aquí era FALSA, y este test la respaldaba.

    Decía que `motivo_no_consumo` lo sustituía. No puede:
    `motivo_no_consumo` es de **objeto** y `ocultar` son **columnas**. Y el test
    solo comprobaba que la cadena apareciese, así que dio por buena una
    justificación inventada —exactamente lo que esta feature existe para
    impedir, cometido dentro de ella—.

    Lo verificado el 2026-08-22 en `mcp-bbdd`: el único gancho es
    `esta_oculta(tabla.nombre_completo)`, que recibe un nombre de **tabla**, así
    que la lista de columnas **nunca ocultó nada en ningún proveedor**.
    """
    assert "ocultar" in CONTEXTO_NO_PUBLICADO
    motivo = CONTEXTO_NO_PUBLICADO["ocultar"]

    assert "esta_oculta" in motivo, "la razón tiene que citar el gancho real"
    assert "TABLA" in motivo, "y decir que el gancho es de tabla, no de columna"
    assert "2026-08-22" in motivo, "la decisión va fechada para poder revisarla"
    assert "hueco es real" in motivo, (
        "un hueco declarado tiene que reconocerse como hueco: la necesidad "
        "existe aunque el mecanismo no exista todavía"
    )
    assert "motivo_no_consumo" not in motivo, (
        "vuelve la justificación falsa: `motivo_no_consumo` es de objeto y esto "
        "son columnas, así que no puede sustituirla ni en principio"
    )


# ---------------------------------------------------------------------------
# Las filas que se publican
# ---------------------------------------------------------------------------


def test_f006_r28_se_publica_una_fila_por_entrada() -> None:
    filas = filas_contexto(_dicc())
    global_raw = _dicc().global_raw

    esperadas = sum(len(global_raw[b]) for b in CONTEXTO_PUBLICADO if b in global_raw)
    assert len(filas) == esperadas, "una fila por entrada, ni más ni menos"
    assert len(filas) >= 20, f"solo {len(filas)} filas de contexto"


@pytest.mark.parametrize("bloque", sorted(CONTEXTO_PUBLICADO))
def test_f006_r28_cada_bloque_publicado_tiene_filas(bloque: str) -> None:
    filas = [f for f in filas_contexto(_dicc()) if f[0] == bloque]
    assert filas, f"`{bloque}` está en CONTEXTO_PUBLICADO y no publica ninguna fila"


def test_f006_r28_la_clave_identifica_una_fila() -> None:
    """Es la PK de la tabla: si colisionara, el `INSERT` reventaría al publicar."""
    filas = filas_contexto(_dicc())
    claves = [(f[0], f[1]) for f in filas]
    assert len(claves) == len(set(claves)), "hay (bloque, clave) repetidos"


def test_f006_r28_el_texto_se_puede_inyectar_tal_cual() -> None:
    """`texto` es lo que el agente recibe: no puede venir vacío ni a medias."""
    for bloque, clave, _orden, texto, _datos in filas_contexto(_dicc()):
        assert texto.strip(), f"{bloque}.{clave} publica un texto vacío"
        assert len(texto) > 5, f"{bloque}.{clave}: «{texto}»"


def test_f006_r28_los_datos_son_json_valido() -> None:
    for bloque, clave, _orden, _texto, datos in filas_contexto(_dicc()):
        json.loads(datos)  # revienta si no lo es


def test_f006_r28_los_ordenes_de_magnitud_llevan_su_cifra() -> None:
    """Son los que permiten detectar una respuesta absurda: sin la cifra, no sirven.

    Existen para que no se repita lo de los 38,9 M€ en una sola obra.
    """
    filas = [f for f in filas_contexto(_dicc()) if f[0] == "ordenes_de_magnitud"]
    assert filas, "no se publica ningún orden de magnitud"
    for _b, clave, _o, texto, datos in filas:
        entrada = json.loads(datos)
        assert entrada.get("valor_aproximado"), f"{clave} sin cifra"
        assert "del orden de" in texto, f"{clave}: el texto no da la magnitud"
        assert entrada.get("unidad"), f"{clave} sin unidad"


def test_f006_r28_los_ejes_publican_los_literales_exactos() -> None:
    """El agente los va a poner en un `WHERE`: inventarlos da cero filas sin error."""
    filas = [f for f in filas_contexto(_dicc()) if f[0] == "ejes"]
    assert filas
    todos = " ".join(f[3] for f in filas)
    for literal in ("COSTE", "VENTA", "REAL", "PLANIFICADO"):
        assert literal in todos, f"falta el literal `{literal}`"


def test_f006_r28_las_convenciones_dicen_moneda_e_iva() -> None:
    filas = {f[1]: f[3] for f in filas_contexto(_dicc()) if f[0] == "convenciones"}
    assert "moneda" in filas
    assert "EUR" in filas["moneda"]
    assert any("iva" in k.lower() for k in filas), "el IVA tiene que estar"


def test_f006_r28_control_el_generador_no_publica_en_vacio() -> None:
    """Si `CONTEXTO_PUBLICADO` se vaciara, los tests de arriba pasarían solos."""
    assert len(CONTEXTO_PUBLICADO) >= 4
    filas = filas_contexto(_dicc())
    assert len({f[0] for f in filas}) == len(CONTEXTO_PUBLICADO)


# ---------------------------------------------------------------------------
# Los recuentos del estado, derivados (14ª pasada)
# ---------------------------------------------------------------------------
#
# `progress/current.md` describe el ESTADO, así que sus cifras tienen que ser
# las de hoy. Caducaron dos veces —decían 102/793/47 cuando ya eran 103/798/48—
# y la segunda vez el propio reviewer copió las viejas **en el informe donde
# reprochaba justo eso**. No es casualidad: a mano no funciona.
#
# No se puede derivar el texto de un documento en prosa, pero sí **comprobarlo**,
# que es lo que impide que envejezca en silencio.


def test_f006_los_recuentos_de_current_son_los_de_hoy() -> None:
    texto = (RAIZ / "progress" / "current.md").read_text(encoding="utf-8")
    dicc = _dicc()

    objetos = len(dicc.fichas)
    columnas = sum(len(f.columnas) for f in dicc.fichas)
    consumo = sum(1 for f in dicc.fichas if f.consumo_recomendado)

    # Solo la sección de estado: más abajo hay historia, y la historia se queda.
    estado = texto.split("### El contrato creció")[0]

    for valor, que in ((objetos, "objetos"), (columnas, "columnas"), (consumo, "de consumo")):
        assert str(valor) in estado, (
            f"`current.md` no dice el número real de {que} ({valor}). Los "
            f"recuentos a mano caducan: ya lo hicieron dos veces"
        )
    for viejo in ("102 objetos", "793 columnas"):
        assert viejo not in estado, f"«{viejo}» es un recuento caducado"
