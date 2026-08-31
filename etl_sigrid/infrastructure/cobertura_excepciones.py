# etl_sigrid/infrastructure/cobertura_excepciones.py
"""
F-052 · Lectura de `config/cobertura_excepciones.yaml` (R16).

Es el adaptador que convierte el YAML en objetos de dominio. Vive en
`infrastructure` y no en `domain` por la razón de siempre: el dominio no lee
ficheros. Mismo papel que `cargar_pendientes_construccion` hace con
`config/objetos_pendientes.yaml`, y mismo criterio duro:

**Un fichero ausente NO se traga.** Devolver «ninguna excepción» sería la
dirección segura para la puerta —más estricta, no menos— pero convertiría
«alguien borró la configuración» en «todo declarado», y ése es justo el modo de
fallo que esta feature existe para impedir. Una clave `excepciones:` ausente o
nula sí vale y significa lista vacía: es como se escribe «no hay ninguna».
"""

from __future__ import annotations

from pathlib import Path

import yaml

from etl_sigrid.domain.cobertura import Excepcion

#: La raíz del repositorio, tres niveles por encima de este fichero.
_RAIZ = Path(__file__).resolve().parents[2]

YAML_EXCEPCIONES = _RAIZ / "config" / "cobertura_excepciones.yaml"

#: Las claves que una entrada puede declarar. Cualquier otra es un error: un
#: `motivo:` mal escrito como `motivos:` dejaría la excepción sin porqué y el
#: `yaml.safe_load` no diría nada.
_CLAVES = frozenset(
    {"tipo", "motivo", "codigo_obra", "patron_nombre", "ambito_id", "feature"}
)


def cargar_excepciones(ruta: Path | None = None) -> tuple[Excepcion, ...]:
    """Los descartes aceptados, validados al leerlos.

    La validación la hace `Excepcion.__post_init__`: tipo conocido, exactamente
    una forma de identificar a la obra y motivo escrito. Fallar aquí es fallar
    al arrancar el comando, que es cuando alguien está mirando.
    """
    ruta = YAML_EXCEPCIONES if ruta is None else ruta
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}

    excepciones: list[Excepcion] = []
    for entrada in datos.get("excepciones") or ():
        sobrantes = set(entrada) - _CLAVES
        if sobrantes:
            raise ValueError(
                f"{ruta.name}: la excepcion {entrada!r} declara claves que nadie "
                f"lee: {', '.join(sorted(sobrantes))}"
            )
        excepciones.append(
            Excepcion(
                tipo=str(entrada.get("tipo", "")),
                motivo=str(entrada.get("motivo", "")),
                codigo_obra=entrada.get("codigo_obra"),
                patron_nombre=entrada.get("patron_nombre"),
                ambito_id=entrada.get("ambito_id"),
                feature=entrada.get("feature"),
            )
        )
    return tuple(excepciones)
