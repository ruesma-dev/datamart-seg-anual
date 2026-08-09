<!-- progress/mutacion_F-003.md -->
# F-003 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-003` el 2026-08-10 00:17.

## Alcance

Origen del diff: **rama** (`79c48e2bce795458e8a581e5fb86dfa17d28646d` .. `feature/F-003-infra-caj`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 1 |
| **Total** | **1** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 0 |
| Mutantes evaluados | 0 |
| Muertos | 0 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Tiempo total | 0.0 s |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.


---

## Análisis del 0/0 (añadido por el implementer; el nivel `critico` exige justificar todo N/A)

**No hay supervivientes porque no hay mutantes, y no hay mutantes porque F-003
no añade código Python de producción.** El alcance calculado por
`harness.alcance` es una única línea, `config/settings.py:40`, y es una línea de
**docstring**: se cambió la referencia a `infra/20_build_image.ps1`, que dejó de
existir, por `infra/70_build_image.ps1`. Ahí no hay operador, literal numérico,
condición ni retorno que mutar.

El entregable real de la feature son 13 scripts PowerShell, un fichero de datos
JSON y documentación, y la herramienta —por decisión explícita de F-015, en
`harness/alcance.es_produccion`— solo considera código de producción los `.py`
fuera de `tests/`, `specs/`, `progress/` y `docs/`.

Lo que sustituye a la campaña, y lo que el reviewer debe juzgar en su lugar,
está en `progress/impl_F-003.md` §3 y §8: 30 tests trazables sobre los `.ps1` y
el JSON (análisis textual e introspección de `config/settings.py`), con la fase
RED demostrada con salida real —el barrido encontró de verdad el ID de
suscripción y la contraseña de marcador que arrastraba el `infra/` viejo—.

Mejora posible del arnés, anotada y **no** ejecutada aquí: extender la mutación
a ficheros que no son Python (invertir un `false` en el JSON de entorno, quitar
un `--allow-shared-key-access false` de un script) sería la forma de tener una
puerta de verdad sobre este tipo de entregable.
