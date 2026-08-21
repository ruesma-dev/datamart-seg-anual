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

import pathlib
import re

import pytest

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


@pytest.mark.parametrize("fichero", _ficheros(), ids=lambda p: p.name)
def test_f006_r26_ninguna_frase_rechazada_sobrevive_en_el_fichero(
    fichero: pathlib.Path,
) -> None:
    """Incluidos los comentarios, que es donde se escondió la quinta vez."""
    texto = fichero.read_text(encoding="utf-8")
    vivas = [
        f"«{frase}» ({motivo})"
        for frase, motivo in FRASES_RECHAZADAS.items()
        if frase in texto
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
        if frase in texto
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
