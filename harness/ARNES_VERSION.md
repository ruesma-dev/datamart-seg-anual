<!-- harness/ARNES_VERSION.md -->
# Version del arnes instalada en este repositorio

Lo escribe `instalar_arnes.ps1`. **No lo edites a mano.**

| Dato | Valor |
|---|---|
| Version del arnes | `1.5.1` |
| Fecha de la version | 2026-08-18 |
| Instalado/actualizado el | 2026-08-18 |
| Modo | actualizar (fichero a fichero, ver notas) |
| Origen | `arnes-base` |

> **Nota de esta actualizacion (2026-08-18).** El repositorio venia de un
> arnes anterior al versionado y la actualizacion se aplico fichero a fichero
> en lugar de con el instalador: en modo actualizar habria arrastrado
> `.pytest_cache/` y pisado `progress/current.md` e `history.md`, que son la
> memoria del proyecto. Se conservaron ademas `harness/features.json`,
> `docs/ARCHITECTURE.md` y `scripts/mantener_despierto.ps1` (este ultimo solo
> difiere en finales de linea), y se fusionaron a mano `harness/init.sh`,
> `CHECKPOINTS.md`, `CLAUDE.md`, `docs/CONVENTIONS.md` y
> `docs/referencia/README.md`, que llevan contenido propio del proyecto.

Para actualizar a una version posterior, desde el repositorio `arnes-base`:

```powershell
.\instalar_arnes.ps1 -Destino "C:\Users\pgris\PycharmProjects\datamart-seg-anual" -Modo actualizar
```

Antes de aceptar cambios, lee `GUIA_INSTALACION.md` en `arnes-base`: los
ficheros con marcas de adaptacion llevan contenido propio de este proyecto y
casi siempre hay que conservarlos, no sobrescribirlos.

> **Nota de la 1.5.1 (2026-08-18).** Mejora nacida en este repositorio y
> portada a `arnes-base` en el mismo trabajo (commit `11f24fb` alli): repetir
> una campania de mutacion ya no borra el analisis de los supervivientes.
> Ficheros que entran: `harness/mutacion.py`, `harness/VERSION` y
> `tests/test_mutacion_informe.py`.
