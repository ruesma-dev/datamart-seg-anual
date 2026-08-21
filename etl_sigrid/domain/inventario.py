# etl_sigrid/domain/inventario.py
"""
Qué objetos publica este repositorio, y cuáles de ellos están documentados.

Es la mitad barata de la defensa contra la desincronización (F-006, R24-R29). Un
diccionario que miente es peor que no tenerlo: el agente escribe SQL con aplomo
sobre una descripción caducada. Contra eso hay dos puertas y conviene ser honesto
sobre lo que vale cada una:

* **esta**, offline, que corre en cada `bash harness/init.sh`. No demuestra que el
  diccionario esté completo: demuestra que **nadie ha añadido un objeto al
  repositorio sin documentarlo**. Es un trinquete, y es heurístico (R29).
* **`python main.py check-diccionario`**, contra `information_schema` de la base
  real. Esa sería la verdad, y cuesta una conexión. **YA EXISTE**, es
  R28 y llega en el bloque H. Mientras tanto **no hay red de seguridad detrás de
  esta puerta**, y por eso conviene decirlo aquí en vez de dar por cubierto lo
  que no lo está.

Lo que esta puerta SÍ garantiza hoy, y no es poco: que todo objeto publicado
tiene ficha o está declarado pendiente, y que las columnas documentadas de una
tabla o de una vista son **exactamente** las que el SQL crea (lo comprueba
`tests/test_f006_fichas.py`, leyendo el `CREATE TABLE` o la proyección del
`CREATE VIEW`). Lo que NO puede ver es un objeto creado por una vía que la
expresión regular no contemple.

Dominio puro: `objetos_de_sql` recibe un mapa `ruta -> texto` ya leído, no rutas.
Quien abre ficheros es la CLI o el test, nunca este módulo.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from etl_sigrid.domain.diccionario import Diccionario

#: `CREATE [OR REPLACE] TABLE|VIEW|MATERIALIZED VIEW|FUNCTION <esquema>.<objeto>`.
#: Deliberadamente NO se ancla a principio de línea: `retenciones/00_setup.sql`
#: crea dos vistas dentro de un `EXECUTE '...'` y son objetos publicados de
#: verdad. Los comentarios se eliminan antes, así que un `CREATE` comentado no
#: entra.
_CREATE = re.compile(
    r"""
    CREATE \s+ (?: OR \s+ REPLACE \s+ )?
    (?P<clase> TABLE | MATERIALIZED \s+ VIEW | VIEW | FUNCTION ) \s+
    (?: IF \s+ NOT \s+ EXISTS \s+ )?
    (?P<esquema> [A-Za-z_][A-Za-z0-9_]* ) \s* \. \s*
    (?P<objeto>  [A-Za-z_][A-Za-z0-9_]* )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_COMENTARIO_LINEA = re.compile(r"--[^\n]*")
_COMENTARIO_BLOQUE = re.compile(r"/\*.*?\*/", re.DOTALL)

#: Cómo se llama en el diccionario cada clase de objeto de PostgreSQL.
_TIPO_POR_CLASE = {
    "TABLE": "tabla",
    "VIEW": "vista",
    "MATERIALIZED VIEW": "vista",
    "FUNCTION": "funcion",
}

#: De dónde sale el inventario de `raw`: no hay SQL que leer.
ORIGEN_RAW = "config/tables_sigrid.yaml"


@dataclass(frozen=True, slots=True)
class ObjetoPublicado:
    """Un objeto que este repositorio crea en la base, y dónde se crea."""

    esquema: str
    objeto: str
    tipo: str
    #: Ruta del fichero SQL, o `config/tables_sigrid.yaml` para `raw`.
    origen: str

    @property
    def nombre(self) -> str:
        return f"{self.esquema}.{self.objeto}"


def _sin_comentarios(texto: str) -> str:
    """Quita comentarios de bloque y de línea, en ese orden."""
    return _COMENTARIO_LINEA.sub(" ", _COMENTARIO_BLOQUE.sub(" ", texto))


def objetos_de_sql(textos: Mapping[str, str]) -> list[ObjetoPublicado]:
    """Inventario de objetos a partir de los textos SQL del repositorio.

    **Es una heurística, y hay que decirlo** (R29): lee SQL con expresiones
    regulares, no consulta el catálogo. Reconoce `CREATE [OR REPLACE]
    TABLE|VIEW|MATERIALIZED VIEW|FUNCTION <esquema>.<objeto>`, ignorando los
    comentarios, y también los `CREATE` envueltos en un `EXECUTE '...'`. Aun así
    puede no ver un objeto creado por una vía que la expresión no contemple.

    Por eso `raw` NO se inventaría de aquí: sus 31 tablas las crea
    `ensure_raw_table` desde Python y no hay SQL que leer. Se inventarían con
    `objetos_de_raw` desde `config/tables_sigrid.yaml`.

    La comprobación contra `information_schema`, que sería la única fuente que
    dice la verdad, es `python main.py check-diccionario` (R28) y **está sin
    implementar**: llega en el bloque H. Hasta entonces esta heurística es lo
    único que hay.

    Recibe `ruta -> texto` para que quien lea ficheros sea infraestructura. El
    resultado sale ordenado y deduplicado por `esquema.objeto`: el mismo
    repositorio produce siempre el mismo inventario. Cuando un objeto aparece en
    dos ficheros —`aux.periodificacion_partida` se crea en `auxiliar/` y en
    `mart/`— gana el primero en orden alfabético de ruta.
    """
    encontrados: dict[str, ObjetoPublicado] = {}
    for ruta in sorted(textos):
        for coincidencia in _CREATE.finditer(_sin_comentarios(textos[ruta])):
            clase = " ".join(coincidencia.group("clase").upper().split())
            objeto = ObjetoPublicado(
                esquema=coincidencia.group("esquema").lower(),
                objeto=coincidencia.group("objeto").lower(),
                tipo=_TIPO_POR_CLASE[clase],
                origen=ruta,
            )
            encontrados.setdefault(objeto.nombre, objeto)
    return [encontrados[nombre] for nombre in sorted(encontrados)]


def objetos_de_raw(tablas: Sequence[Mapping[str, object]]) -> list[ObjetoPublicado]:
    """Inventario de `raw` a partir de las entradas de `config/tables_sigrid.yaml`.

    Se usa `target_table` y no `source_table`: lo que se publica en la base es el
    nombre destino. Una entrada sin destino se ignora en vez de reventar; el YAML
    lo valida la ingesta, no esta puerta.
    """
    encontrados: dict[str, ObjetoPublicado] = {}
    for tabla in tablas:
        destino = tabla.get("target_table")
        if not isinstance(destino, str) or not destino.strip():
            continue
        objeto = ObjetoPublicado(
            esquema="raw", objeto=destino.strip().lower(), tipo="tabla", origen=ORIGEN_RAW
        )
        encontrados.setdefault(objeto.nombre, objeto)
    return [encontrados[nombre] for nombre in sorted(encontrados)]


@dataclass(frozen=True, slots=True)
class InformeCobertura:
    """Qué le falta al diccionario respecto de lo que el repositorio publica."""

    #: Publicado y sin ficha, sin estar declarado pendiente. **Bloqueante** (R25).
    sin_ficha: tuple[ObjetoPublicado, ...] = ()
    #: Con ficha y sin objeto en el inventario. **Bloqueante**: describe humo.
    fichas_huerfanas: tuple[str, ...] = ()
    #: Columnas sin `significado` dentro de la superficie de consumo (R26).
    columnas_sin_significado: tuple[str, ...] = ()
    #: Lo mismo fuera de la superficie de consumo: **aviso**, no fallo (R26).
    avisos_columnas: tuple[str, ...] = ()
    #: Lo que el propio diccionario reconoce que aún no ha escrito (R27).
    pendientes_declarados: tuple[str, ...] = ()
    #: Declarado pendiente y ya documentado: el trinquete solo baja (R27).
    pendientes_ya_documentados: tuple[str, ...] = ()
    #: Declarado pendiente y que no existe en el inventario: infla el trinquete.
    pendientes_fantasma: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Verde solo si no hay ningún hueco bloqueante.

        `avisos_columnas` NO cuenta: fuera de la superficie de consumo no se
        exige ninguna columna descrita (R26), y meter ahí las ~800 columnas de
        Sigrid convertiría la puerta en un muro que nadie levantaría.
        """
        return not (
            self.sin_ficha
            or self.fichas_huerfanas
            or self.columnas_sin_significado
            or self.pendientes_ya_documentados
            or self.pendientes_fantasma
        )

def evaluar_cobertura(
    dicc: Diccionario,
    inventario: Sequence[ObjetoPublicado],
    pendientes: Sequence[str],
) -> InformeCobertura:
    """Cruza el diccionario contra el inventario y dice qué falta.

    Umbrales, y por qué esos: **100 % de objetos** con ficha y **100 % de
    columnas descritas dentro de la superficie de consumo**; fuera de ella, cero
    exigido. Un umbral porcentual del 95 % permite justamente que la columna que
    falte sea la importante, porque nadie audita cuál es el 5 %. Acotar el 100 %
    a `consumo_recomendado: true` hace el trabajo finito y pone la decisión donde
    debe estar: en una decisión editorial visible en el diff.

    `pendientes` es el trinquete que permite entregar por bloques (R27). Se le
    exige coherencia en los dos sentidos: un pendiente ya documentado o que no
    existe **rompe la puerta**, porque un trinquete que no baja no es un
    trinquete.
    """
    documentados = set(dicc.por_nombre)
    publicados = {o.nombre: o for o in inventario}
    tolerados = set(pendientes)

    sin_ficha = tuple(
        publicados[nombre]
        for nombre in sorted(publicados)
        if nombre not in documentados and nombre not in tolerados
    )
    huerfanas = tuple(sorted(documentados - set(publicados)))

    faltan: list[str] = []
    avisos: list[str] = []
    for ficha in sorted(dicc.fichas, key=lambda f: f.nombre):
        destino = faltan if ficha.consumo_recomendado else avisos
        if ficha.tipo != "funcion" and not ficha.columnas:
            destino.append(f"{ficha.nombre}: ninguna columna documentada")
        for columna in ficha.columnas:
            if not (columna.significado or "").strip():
                destino.append(f"{ficha.nombre}.{columna.nombre}: sin significado")

    return InformeCobertura(
        sin_ficha=sin_ficha,
        fichas_huerfanas=huerfanas,
        columnas_sin_significado=tuple(faltan),
        avisos_columnas=tuple(avisos),
        pendientes_declarados=tuple(sorted(tolerados)),
        pendientes_ya_documentados=tuple(sorted(tolerados & documentados)),
        pendientes_fantasma=tuple(sorted(tolerados - set(publicados))),
    )


def formatear_cobertura(informe: InformeCobertura) -> str:
    """Informe legible: qué falta, dónde está y qué hacer con ello."""
    if informe.ok and not informe.avisos_columnas and not informe.pendientes_declarados:
        return "Cobertura del diccionario: OK. Todo objeto publicado tiene ficha."

    lineas: list[str] = []
    lineas.append(
        "Cobertura del diccionario: OK con pendientes declarados."
        if informe.ok
        else "Cobertura del diccionario: KO."
    )

    if informe.sin_ficha:
        lineas.append(
            "  · publicados y SIN ficha (el agente los verá en el catálogo e "
            "inventará su significado):"
        )
        for objeto in informe.sin_ficha:
            lineas.append(f"      {objeto.nombre}  [{objeto.tipo}]  {objeto.origen}")
        lineas.append(
            "    Escribe su ficha en config/diccionario/<esquema>.yaml, o "
            "declárala en `pendientes` de 00_global.yaml si va en otro bloque."
        )

    if informe.fichas_huerfanas:
        lineas.append("  · con ficha y sin objeto publicado (describen humo):")
        lineas.extend(f"      {nombre}" for nombre in informe.fichas_huerfanas)

    if informe.columnas_sin_significado:
        lineas.append("  · dentro de la superficie de consumo, sin describir:")
        lineas.extend(f"      {item}" for item in informe.columnas_sin_significado)

    if informe.pendientes_ya_documentados:
        lineas.append(
            "  · declarados en `pendientes` y ya documentados: bórralos de la "
            "lista, el trinquete solo baja:"
        )
        lineas.extend(f"      {n}" for n in informe.pendientes_ya_documentados)

    if informe.pendientes_fantasma:
        lineas.append("  · declarados en `pendientes` y que no existen:")
        lineas.extend(f"      {n}" for n in informe.pendientes_fantasma)

    if informe.pendientes_declarados:
        lineas.append(
            f"  · pendientes declarados: {len(informe.pendientes_declarados)} "
            f"(el trinquete solo baja; al cerrar F-006 debe valer 0)"
        )

    if informe.avisos_columnas:
        lineas.append(
            f"  · aviso, fuera de la superficie de consumo: "
            f"{len(informe.avisos_columnas)} objeto(s)/columna(s) sin describir. "
            f"No bloquea."
        )

    return "\n".join(lineas)
