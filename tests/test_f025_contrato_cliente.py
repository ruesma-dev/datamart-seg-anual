# tests/test_f025_contrato_cliente.py
"""
F-025 · El contrato de `PostgresClient`, comprobado en las DOS direcciones:
lo que producción le pide y lo que los dobles de test le imitan.

**Por qué existe este fichero.** La noche del 2026-09-05 la nocturna murió con
`AttributeError: 'PostgresClient' object has no attribute
'fetch_filas_por_obra'` sobre 3.308 tests en verde. El método se añadió a los
IMITADORES y no al IMITADO: tres dobles de `tests/` lo declaraban y devolvían
un valor plausible, así que el step lo llamaba tan tranquilo y nadie lo notó
hasta producción. Cuatro pasadas de reviewer tampoco lo cazaron, porque leer el
test da coherencia y leer el step también: la incoherencia SOLO aparece al
cruzar los dos ficheros, que es justo lo que hace este módulo.

**Cómo encuentra los dobles.** No hay lista escrita a mano —envejecería—: se
recorre `tests/` con `ast` y se toma por doble de `PostgresClient` toda clase
(anidada incluida) que declare al menos `UMBRAL_PARECIDO` métodos públicos con
nombre de la API real. Un doble que imita el cliente siempre pasa ese listón, y
una clase que no lo imita no llega a él por casualidad.

**Qué se exige.**

1. Todo método público del doble existe en el cliente real. La excepción es
   la ayuda de test —un espía como `escrituras` o `cierre_de`, que no imita
   nada—, y para que valga hay que DECLARARLA en `AYUDAS_DEL_DOBLE` dentro de
   la propia clase: así añadir un método sin querer sale en rojo, y añadirlo a
   propósito cuesta una línea que dice por qué.
2. El doble no acepta llamadas que el cliente real rechazaría: ni más
   parámetros posicionales, ni un parámetro que el real declara `keyword-only`
   pasado como posicional, ni nombres distintos en el mismo hueco. Esa
   dirección es la peligrosa: el test pasa y producción revienta.

3. Y la dirección contraria, que es la que de verdad murió esa noche: **todo
   lo que el código de producción invoca sobre un `PostgresClient` existe en
   `PostgresClient`**. Se leen con `ast` las funciones cuyo parámetro está
   anotado `PostgresClient` y se cruzan sus accesos a atributo contra la clase.
   Esto habría dado rojo aunque ningún doble hubiera declarado el fantasma.

**Lo que este control NO alcanza**, dicho para que nadie lo dé por más de lo
que es: un doble declarado `(*args, **kwargs)` acepta cualquier cosa por
definición, así que un nombre de argumento mal escrito en producción seguiría
pasando sus tests; y el barrido de producción solo ve lo que llega por un
parámetro ANOTADO, no un cliente que viaje dentro de una estructura sin tipo.
Se comprueba lo comprobable —el nombre del método y la forma de la firma—, no
la semántica.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent

#: Dónde vive el código que llama al cliente. `tests/` queda fuera a propósito:
#: los dobles los juzgan los otros dos tests, con su propia regla.
FUENTES_DE_PRODUCCION = ("etl_sigrid", "main.py")

#: Métodos públicos con nombre de la API real que hacen falta para considerar
#: que una clase de test IMITA a `PostgresClient`. Dos ya es mucha casualidad.
UMBRAL_PARECIDO = 2

#: El nombre del sobre por el que un doble declara sus ayudas de test.
DECLARACION_DE_AYUDAS = "AYUDAS_DEL_DOBLE"


def api_real() -> dict[str, inspect.Signature]:
    """Los métodos públicos del cliente de verdad, con su firma."""
    return {
        nombre: inspect.signature(funcion)
        for nombre, funcion in inspect.getmembers(
            PostgresClient, predicate=inspect.isfunction
        )
        if not nombre.startswith("_")
    }


def _ayudas_declaradas(clase: ast.ClassDef) -> frozenset[str]:
    """Lo que la clase declara como ayuda de test y no como imitación."""
    for nodo in clase.body:
        if not isinstance(nodo, ast.Assign):
            continue
        if not any(
            isinstance(destino, ast.Name) and destino.id == DECLARACION_DE_AYUDAS
            for destino in nodo.targets
        ):
            continue
        valor = nodo.value
        if isinstance(valor, ast.Call):  # frozenset({...}) / set([...])
            valor = valor.args[0] if valor.args else ast.Tuple(elts=[])
        if isinstance(valor, ast.Set | ast.Tuple | ast.List):
            return frozenset(
                e.value for e in valor.elts if isinstance(e, ast.Constant)
            )
    return frozenset()


def _metodos_publicos(clase: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {
        nodo.name: nodo
        for nodo in clase.body
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef)
        and not nodo.name.startswith("_")
    }


def dobles_del_cliente() -> list[tuple[Path, ast.ClassDef]]:
    """Todas las clases de `tests/` que imitan a `PostgresClient`."""
    real = api_real()
    encontrados: list[tuple[Path, ast.ClassDef]] = []
    for fichero in sorted(RAIZ.glob("test_*.py")):
        arbol = ast.parse(fichero.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.ClassDef):
                continue
            publicos = set(_metodos_publicos(nodo))
            if len(publicos & set(real)) >= UMBRAL_PARECIDO:
                encontrados.append((fichero, nodo))
    return encontrados


def _huecos(firma: inspect.Signature) -> tuple[list[str], list[str]]:
    """Los nombres del real por posición y los que exige por palabra clave."""
    posicionales = [
        p.name
        for p in firma.parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.name != "self"
    ]
    solo_clave = [
        p.name for p in firma.parameters.values() if p.kind == p.KEYWORD_ONLY
    ]
    return posicionales, solo_clave


def desajuste_de_firma(metodo: ast.FunctionDef, real: inspect.Signature) -> str | None:
    """Qué acepta el doble que el cliente real NO aceptaría. `None` si nada."""
    argumentos = metodo.args
    posicionales = [p.arg for p in argumentos.posonlyargs + argumentos.args][1:]
    solo_clave = [p.arg for p in argumentos.kwonlyargs]
    reales_pos, reales_clave = _huecos(real)

    if len(posicionales) > len(reales_pos):
        sobrantes = posicionales[len(reales_pos):]
        cola = (
            f" ({', '.join(sobrantes)} es solo-clave en el real)"
            if set(sobrantes) <= set(reales_clave)
            else ""
        )
        return (
            f"acepta {len(posicionales)} posicionales y el cliente real "
            f"{len(reales_pos)}{cola}"
        )
    for indice, (nombre, esperado) in enumerate(zip(posicionales, reales_pos)):
        if nombre != esperado:
            return (
                f"el posicional {indice} se llama {nombre!r} y en el cliente "
                f"real {esperado!r}"
            )
    intrusos = sorted(set(solo_clave) - set(reales_clave))
    if intrusos:
        return f"declara solo-clave que el cliente real no tiene: {intrusos}"
    return None


def _ficheros_de_produccion() -> list[Path]:
    ficheros: list[Path] = []
    for nombre in FUENTES_DE_PRODUCCION:
        ruta = REPO / nombre
        ficheros += [ruta] if ruta.is_file() else sorted(ruta.rglob("*.py"))
    return ficheros


def _anotado_como_cliente(anotacion: ast.expr | None) -> bool:
    """Si esa anotación dice `PostgresClient`, escrita como se escriba."""
    if isinstance(anotacion, ast.Name):
        return anotacion.id == "PostgresClient"
    if isinstance(anotacion, ast.Attribute):
        return anotacion.attr == "PostgresClient"
    if isinstance(anotacion, ast.Constant) and isinstance(anotacion.value, str):
        return "PostgresClient" in anotacion.value
    return False


def usos_del_cliente_en_produccion() -> dict[str, list[str]]:
    """Qué atributo se pide a un `PostgresClient`, y desde dónde."""
    usos: dict[str, list[str]] = {}
    for fichero in _ficheros_de_produccion():
        arbol = ast.parse(fichero.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            argumentos = nodo.args
            clientes = {
                a.arg
                for a in argumentos.posonlyargs + argumentos.args + argumentos.kwonlyargs
                if _anotado_como_cliente(a.annotation)
            }
            if not clientes:
                continue
            for hijo in ast.walk(nodo):
                if (
                    isinstance(hijo, ast.Attribute)
                    and isinstance(hijo.value, ast.Name)
                    and hijo.value.id in clientes
                ):
                    sitio = f"{fichero.relative_to(REPO).as_posix()}:{hijo.lineno}"
                    usos.setdefault(hijo.attr, []).append(sitio)
    return usos


def test_f025_produccion_no_llama_a_nada_que_el_cliente_no_tenga() -> None:
    """La comprobación que habría evitado la nocturna del 2026-09-05.

    No depende de que exista un doble ni de que haya un test del step: cruza lo
    que el código ESCRIBE contra lo que la clase TIENE.
    """
    existentes = {n for n in dir(PostgresClient) if not n.startswith("_")}
    usos = usos_del_cliente_en_produccion()

    # Control del control: si el barrido dejara de ver los steps, esto pasaría
    # en vacío. Los steps del build piden bastante más de veinte cosas.
    assert len(usos) >= 20, f"el barrido apenas encontró usos: {sorted(usos)}"
    assert "fetch_filas_por_obra" in usos

    fantasmas = [
        f"{atributo} · {', '.join(sitios)}"
        for atributo, sitios in sorted(usos.items())
        if atributo not in existentes
    ]
    assert not fantasmas, (
        "producción llama a lo que PostgresClient no tiene:\n" + "\n".join(fantasmas)
    )


def test_f025_el_barrido_encuentra_los_dobles_conocidos() -> None:
    """Control del propio control: si la detección dejara de encontrar dobles,
    los dos tests de abajo pasarían sin comprobar nada."""
    nombres = {clase.name for _, clase in dobles_del_cliente()}

    assert {"PgVentana", "PgFalso"} <= nombres
    assert len(nombres) >= 10


def test_f025_ningun_doble_declara_un_metodo_que_el_cliente_real_no_tiene() -> None:
    """El fallo del 2026-09-05, convertido en rojo automático."""
    real = api_real()
    fantasmas: list[str] = []
    for fichero, clase in dobles_del_cliente():
        ayudas = _ayudas_declaradas(clase)
        for nombre, nodo in _metodos_publicos(clase).items():
            if nombre in real or nombre in ayudas:
                continue
            fantasmas.append(
                f"{fichero.name}:{nodo.lineno} {clase.name}.{nombre} no existe "
                f"en PostgresClient"
            )

    assert not fantasmas, "métodos fantasma:\n" + "\n".join(fantasmas)


def test_f025_ningun_doble_acepta_llamadas_que_el_cliente_real_rechazaria() -> None:
    """Un doble más permisivo que el original deja pasar la llamada que
    producción no podrá hacer: es el mismo modo de fallo, un piso más abajo."""
    real = api_real()
    desajustes: list[str] = []
    for fichero, clase in dobles_del_cliente():
        for nombre, nodo in _metodos_publicos(clase).items():
            if nombre not in real:
                continue
            queja = desajuste_de_firma(nodo, real[nombre])
            if queja:
                desajustes.append(
                    f"{fichero.name}:{nodo.lineno} {clase.name}.{nombre} {queja}"
                )

    assert not desajustes, "firmas incompatibles:\n" + "\n".join(desajustes)


@pytest.mark.parametrize(
    "fuente",
    [
        "class D:\n    AYUDAS_DEL_DOBLE = frozenset({'x'})\n",
        "class D:\n    AYUDAS_DEL_DOBLE = ('x',)\n",
        "class D:\n    AYUDAS_DEL_DOBLE = ['x']\n",
        "class D:\n    AYUDAS_DEL_DOBLE = {'x'}\n",
    ],
)
def test_f025_la_declaracion_de_ayudas_se_lee_escrita_como_se_escriba(
    fuente: str,
) -> None:
    """Cuatro formas de escribir lo mismo; el sobre no puede depender de ellas."""
    clase = ast.parse(fuente).body[0]
    assert isinstance(clase, ast.ClassDef)
    assert _ayudas_declaradas(clase) == frozenset({"x"})


def test_f025_sin_declaracion_no_hay_ayudas() -> None:
    clase = ast.parse("class D:\n    pass\n").body[0]
    assert isinstance(clase, ast.ClassDef)
    assert _ayudas_declaradas(clase) == frozenset()
