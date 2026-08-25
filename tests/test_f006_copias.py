# tests/test_f006_copias.py
"""
Barrido de copias sobre TODO el fichero, comentarios incluidos (8ª pasada).

Van **cinco** rechazos por el mismo patrón: se corrige la afirmación donde la
señalaron y la copia sobrevive en el campo de al lado, en la ficha hermana o
—esta vez— en la **cabecera del fichero**.

El quinto caso: `config/diccionario/raw.yaml` conservaba intacta la frase que la
séptima pasada rechazó —«`cod`, `res` y `fec` viven en `con`, **no en la tabla
especifica**»— y ocho líneas después declaraba «Esta regla se publica ademas
como `R-SIGRID-CON`», presentando como la misma dos versiones que divergían.

Los barridos anteriores no podían verlo: miran el contenido **publicable**, y
`yaml.safe_load` descarta los comentarios. Es el mismo punto ciego que ya nos
costó la regla de oro escondida en una cabecera y el aviso de frescura. La
lección se repite lo bastante como para automatizarla: **una cabecera no se
publica, pero la lee quien edita el fichero**, y una cabecera que contradice a
la regla publicada es una trampa preparada para el próximo que pase.

Este fichero mira el **texto crudo**: prosa, comentarios y todo.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import re

import pytest

from etl_sigrid.domain.diccionario import Columna, Ficha, Regla
from tests._texto import contiene

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"

#: Frases que una revisión rechazó por falsas. Aparecer en CUALQUIER sitio de
#: `config/diccionario/` —incluida una cabecera— vuelve a publicar el error, o
#: se lo enseña al siguiente que edite el fichero.
#:
#: Cada entrada lleva la pasada que la rechazó, para que borrarla sea una
#: decisión consciente y no un despiste.
FRASES_RECHAZADAS = {
    "no en la tabla especifica": "7ª pasada · `obr.res` existe: es un patrón, no una ley",
    "no en la tabla específica": "7ª pasada · ídem, con tilde",
    "incremental por `tiemod`": "7ª pasada · `tiemod` no gobierna la carga",
    "--full-refresh": "8ª pasada · la bandera real es `--full`",
    "usa la ingesta incremental": "8ª pasada · el job nocturno va con `--full`",
    "no se refresca nunca": "8ª pasada · de noche sí se refresca: recarga entera",
    "cen.res": "8ª pasada · no existe; el «Reparto nombre» es de `cenrep`",
}


def _ficheros() -> list[pathlib.Path]:
    return sorted(DIR_DICCIONARIO.glob("*.yaml"))


def _texto_barrible(fichero: pathlib.Path) -> str:
    """El fichero crudo **y** el YAML ya cargado, los dos.

    Hacen falta los dos y por motivos opuestos:

    * el **crudo** conserva los comentarios, que `yaml.safe_load` descarta y que
      es donde se escondió la copia del quinto caso (la cabecera de `raw.yaml`);
    * el **cargado** conserva las frases **plegadas**. Un bloque `>-` reparte una
      frase entre dos líneas, y en el fichero crudo la cadena
      «no en la tabla especifica» puede no aparecer nunca aunque
      `yaml.safe_load` la publique entera.

    Lo demostró el reviewer en la 10ª pasada: plantó dos frases rechazadas
    plegadas como las pliega el YAML y **el barrido pasó en verde**. Es decir, la
    defensa contra el patrón que ha causado siete rechazos se saltaba por un
    salto de línea.
    """
    import yaml

    crudo = fichero.read_text(encoding="utf-8")
    try:
        cargado = str(yaml.safe_load(crudo))
    except yaml.YAMLError:
        cargado = ""
    return crudo + "\n" + cargado


@pytest.mark.parametrize("fichero", _ficheros(), ids=lambda p: p.name)
def test_f006_r26_ninguna_frase_rechazada_sobrevive_en_el_fichero(
    fichero: pathlib.Path,
) -> None:
    """Comentarios incluidos, y frases plegadas incluidas."""
    texto = _texto_barrible(fichero)
    vivas = [
        f"«{frase}» ({motivo})"
        for frase, motivo in FRASES_RECHAZADAS.items()
        if contiene(texto, frase)
    ]
    assert vivas == [], (
        f"{fichero.name} conserva {len(vivas)} frase(s) que una revisión ya "
        f"rechazó: {vivas}. Si el rechazo era el equivocado, quítala de "
        f"FRASES_RECHAZADAS con su motivo; si no, bórrala del fichero"
    )


def test_f006_r26_control_el_barrido_mira_los_comentarios() -> None:
    """Sin esto, bastaría que alguien lo cambiara a `safe_load` para cegarlo.

    Es la comprobación que faltaba: los barridos anteriores parseaban el YAML, y
    el parser tira los comentarios, así que la frase de la cabecera era invisible
    para ellos aunque estuviera a la vista de cualquiera que abriese el fichero.
    """
    raw = (DIR_DICCIONARIO / "raw.yaml").read_text(encoding="utf-8")
    primera = raw.split("\n", 1)[0]
    assert primera.startswith("#"), "la cabecera es un comentario"
    assert primera in raw, "el barrido tiene que ver el comentario, no el YAML cargado"

    import yaml

    cargado = yaml.safe_load(raw)
    assert primera[2:] not in str(cargado), (
        "el YAML cargado NO contiene la cabecera: por eso hace falta este "
        "fichero además de los barridos sobre el contenido publicable"
    )


def test_f006_r26_control_el_barrido_detecta_una_frase_plantada() -> None:
    """Control del detector: si no detectase, los de arriba pasarían en falso."""
    inventado = "# esto usa la ingesta incremental\nversion: 1\n"
    vivas = [f for f in FRASES_RECHAZADAS if f in inventado]
    assert vivas == ["usa la ingesta incremental"]


# ---------------------------------------------------------------------------
# Toda la superficie PUBLICABLE, no solo las fichas (9ª pasada)
# ---------------------------------------------------------------------------
#
# Séptimo caso del patrón de la copia, y el primero que llegó a publicarse
# después de corregido: `00_global.yaml` → `convenciones.identidad_sigrid`
# conservaba la frase rechazada en la 7ª pasada —«el código, el nombre y la
# fecha viven en `con`, no en la extensión»— **doce líneas por encima del punto
# 3 de la regla que la corrige**, y con una lista divergente: ocho tablas frente
# a diez.
#
# Los barridos anteriores miraban las fichas y las reglas. `convenciones` no es
# ninguna de las dos: entra en `global_raw`, que el dominio describe como «lo
# que se sirve tal cual». Se publica igual que lo demás.
#
# La lección, otra vez la misma: **el barrido tiene que cubrir toda la superficie
# publicable**, no la parte donde recordamos que hubo un defecto.

BLOQUES_PUBLICABLES = ("convenciones", "esquemas", "ordenes_de_magnitud", "ejes")


def _global_publicable() -> str:
    """Todo el texto del bloque global que acaba en `_meta`, sin comentarios."""
    import yaml

    datos = yaml.safe_load((DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8"))
    return str(datos)


def test_f006_r26_el_bloque_global_publicable_no_conserva_frases_rechazadas() -> None:
    """`convenciones` se publica, así que se barre como todo lo demás."""
    texto = _global_publicable()
    vivas = [
        f"«{frase}» ({motivo})"
        for frase, motivo in FRASES_RECHAZADAS.items()
        if contiene(texto, frase)
    ]
    assert vivas == [], (
        f"el bloque global publica {len(vivas)} frase(s) ya rechazada(s): {vivas}. "
        f"`global_raw` se sirve tal cual, así que un `convenciones` desfasado "
        f"llega al agente igual que una ficha"
    )


def test_f006_r26_la_convencion_de_sigrid_no_duplica_la_regla() -> None:
    """Una convención que repite una regla es una copia esperando a divergir.

    Ya divergió: la convención decía ocho tablas «propiedades de `con`» y la
    regla diez, y la convención afirmaba dónde vive cada campo cuando la regla
    ya había dejado de afirmarlo.
    """
    import yaml

    datos = yaml.safe_load((DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8"))
    convencion = str(datos["convenciones"]["identidad_sigrid"])

    assert "R-SIGRID-CON" in convencion, (
        "la convención tiene que remitir a la regla, que es la única versión"
    )
    tablas = set(re.findall(r"`(\w+)`", convencion))
    del tablas  # solo para dejar claro que no se comprueba una lista: no debe haberla
    assert "viven en `con`" not in convencion, (
        "la convención vuelve a afirmar dónde vive cada campo; eso es del punto 3 "
        "de la regla, y tenerlo en dos sitios es lo que produjo la divergencia"
    )


def test_f006_r26_control_el_barrido_ve_una_frase_plegada() -> None:
    """El experimento del reviewer, convertido en control permanente.

    Una frase partida por el ajuste de línea de un bloque `>-` **no aparece** en
    el texto crudo, y sí en lo que se publica. Si este control se rompe, el
    barrido ha vuelto a mirar solo el fichero y la defensa está desarmada.
    """
    import tempfile

    import yaml

    plegado = (
        "version: 1\n"
        "esquema: prueba\n"
        "convenciones:\n"
        "  x: >-\n"
        "    El codigo, el nombre y la fecha viven en `con`, no en la tabla\n"
        "    especifica.\n"
    )
    # En crudo la frase NO está: el salto de línea la parte.
    assert "no en la tabla especifica" not in plegado
    # Cargada, sí: es lo que llega al agente.
    assert "no en la tabla especifica" in str(yaml.safe_load(plegado))

    with tempfile.TemporaryDirectory() as tmp:
        f = pathlib.Path(tmp) / "prueba.yaml"
        f.write_text(plegado, encoding="utf-8")
        texto = _texto_barrible(f)

    vivas = [f for f in FRASES_RECHAZADAS if contiene(texto, f)]
    assert vivas == ["no en la tabla especifica"], (
        f"el barrido no ve la frase plegada: {vivas}"
    )


# ---------------------------------------------------------------------------
# El plegado como CLASE, no como caso (13ª pasada)
# ---------------------------------------------------------------------------


def test_f006_r26_control_la_comparacion_ignora_el_ajuste_de_linea() -> None:
    """El caso exacto de la 13ª pasada, con el texto real que estuvo mintiendo.

    `inventario.py` afirmaba que `check-diccionario` «está sin implementar» del
    comando que existía desde ese mismo commit, y el guardián de R28 estaba
    **verde**: buscaba la subcadena literal y el ajuste de línea partía la
    frase.
    """
    envuelto = (
        "es `python main.py check-diccionario` (R28) y **está sin\n"
        "    implementar**: llega en el bloque H."
    )
    assert "sin implementar" not in envuelto, "así estaba escrito, y así no se veía"
    assert contiene(envuelto, "sin implementar"), "normalizando, sí"


def _campos_de_prosa() -> set[str]:
    """Los campos de texto del diccionario, DERIVADOS de sus dataclases.

    Nada de enumerarlos: se preguntan a `Columna`, `Ficha` y `Regla`. Si mañana
    una ficha gana un campo de prosa, entra solo en la vigilancia.
    """
    campos: set[str] = set()
    for cls in (Columna, Ficha, Regla):
        for campo in dataclasses.fields(cls):
            tipo = str(campo.type)
            if "str" in tipo and "tuple" not in tipo:
                campos.add(campo.name)
    return campos


def _comparaciones_crudas_de_prosa() -> list[str]:
    """Sitios donde una frase de varias palabras se busca con `in` a pelo.

    El criterio, sin listas: en cualquier módulo de tests que **cargue el
    diccionario**, una comparación `"varias palabras" in x.significado` (o
    `descripcion`, `grano`, `motivo`… los campos que las dataclases declaran de
    texto) es ciega al plegado. Una sola palabra no puede partirse, así que solo
    se vigilan los literales de dos o más.
    """
    campos = _campos_de_prosa()
    sitios: list[str] = []
    for ruta in sorted((RAIZ / "tests").glob("test_*.py")):
        fuente = ruta.read_text(encoding="utf-8")
        if "cargar_diccionario" not in fuente:
            continue
        for nodo in ast.walk(ast.parse(fuente)):
            if not isinstance(nodo, ast.Compare) or len(nodo.ops) != 1:
                continue
            if not isinstance(nodo.ops[0], (ast.In, ast.NotIn)):
                continue
            izq = nodo.left
            if not (isinstance(izq, ast.Constant) and isinstance(izq.value, str)):
                continue
            if " " not in izq.value.strip():
                continue
            derecha = nodo.comparators[0]
            nombre = (
                derecha.attr
                if isinstance(derecha, ast.Attribute)
                else derecha.id
                if isinstance(derecha, ast.Name)
                else None
            )
            if nombre in campos:
                sitios.append(f"{ruta.name}:{nodo.lineno}: «{izq.value}» in {nombre}")
    return sitios


def test_f006_r26_control_el_criterio_encuentra_donde_mirar() -> None:
    """Si el barrido no viera ningún módulo, el test de abajo pasaría solo."""
    campos = _campos_de_prosa()
    assert {"significado", "descripcion", "grano", "motivo"} <= campos, (
        f"los campos de prosa derivados son {sorted(campos)}: falta alguno"
    )
    modulos = [
        r.name
        for r in (RAIZ / "tests").glob("test_*.py")
        if "cargar_diccionario" in r.read_text(encoding="utf-8")
    ]
    assert len(modulos) >= 8, f"solo {modulos} cargan el diccionario: revisar"


def test_f006_r26_ninguna_guarda_de_prosa_compara_subcadenas_crudas() -> None:
    """Que el arreglo no se quede en los sitios de hoy.

    Antes esto era una **lista de dos ficheros escrita a mano** que solo miraba
    si importaban `contiene`. No comprobaba ni una comparación, y dejaba fuera
    `test_f006_stg_trampas.py`, donde el guardián del doblado seguía buscando
    «NO esta afectada» con `in` a pelo: la misma piedra de las pasadas 8, 10, 13
    y 15, dentro del dispositivo escrito para evitarla.

    Ahora es un criterio: se derivan los campos de prosa de las dataclases del
    diccionario y se exige que ninguna comparación con literal de varias
    palabras vaya contra ellos sin `contiene`.

    **Límite declarado.** El barrido reconoce la prosa por el nombre del campo
    (`x.significado`, `significado`), así que **no ve** un texto que antes pasó
    por una variable local (`texto = f"{ficha.descripcion} {ficha.grano}"`).
    Saberlo exigiría seguir el flujo de datos y no se intenta; esos sitios se
    corrigen a mano y se declaran, en vez de fingir que están cubiertos.
    """
    crudas = _comparaciones_crudas_de_prosa()
    assert crudas == [], (
        "estas comparaciones son ciegas a una frase partida por una línea en "
        "blanco del plegado YAML; usa `tests._texto.contiene`:\n  "
        + "\n  ".join(crudas)
    )
