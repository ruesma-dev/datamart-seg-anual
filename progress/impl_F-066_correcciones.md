<!-- progress/impl_F-066_correcciones.md -->
# F-066 · Correcciones del review (2026-09-06 / 07)

Respuesta a `progress/review_F-066.md` (**RECHAZADO**, 10 hallazgos, 4
bloqueantes). **Los siete «Cambios requeridos» están cerrados.** De las tres
observaciones, la 9 ya estaba firmada; la **8** y la **10** NO se han hecho a
propósito, por orden del líder, y quedan para fichar (ver el final).

Dos commits: `d8c73b8` (papeleo y tests) y `3115d45` (la campaña).

## Hallazgo por hallazgo

### 1 · [BLOQUEANTE] La campaña se invalidaba sola — CERRADO

Dos mitades: arreglar la causa y repetir la campaña.

**(a) El test aleatorio de F-024, ARREGLADO, no excluido.**
`tests/test_f024_dominio.py::test_f024_r1_batch_id_tiene_forma_y_es_unico`
generaba 500 `batch_id` en el mismo segundo y exigía **los 500 distintos**. Eso
es una propiedad que el código no promete: el sufijo son 6 hexadecimales
—16.777.216 valores— sacados de `secrets`, **sin registro de los ya emitidos**,
así que las repeticiones son posibles por construcción. Cuenta del cumpleaños:

    P(colisión) ≈ 1 - exp(-n²/2N) = 1 - exp(-500²/33.554.432) ≈ 0,74 %

que casa con el **0,833 %** medido por el reviewer sobre 3.000 repeticiones.
**El defecto estaba en el test**, así que `etl_sigrid/domain/` no se ha tocado.

Reescrito para comprobar lo que R1 sí garantiza: la **forma** de los 500 y que
el **espacio de sufijos es grande de verdad** —hasta 3 repeticiones toleradas,
cuando lo esperado son 0,0074, y los 16 dígitos hexadecimales presentes en la
muestra—. El docstring lleva el cálculo, el motivo y la fecha (2026-09-06).

**Remedido con el mismo método que lo delató**, 3.000 repeticiones del cuerpo
del test:

```
$ python -W ignore -c "...3.000 lotes de 500 batch_id..."
fallos en 3.000 pasadas: 0 | maximo de colisiones visto: 1
```

Con la tolerancia en 3, la probabilidad de fallo por azar baja de 0,74 % a
~1,3e-10 por pasada.

**(b) Campaña repetida entera, y VÁLIDA.**

```bash
python -m harness.mutacion --feature F-066 --base d1f56aa --workers 1
```

```
23 mutantes evaluados, 22 muertos, 1 supervivientes, 0 timeouts,
0 sin veredicto en 2072.2 s
Informe: progress/mutacion_F-066.md
```

**`progress/mutacion_F-066.md` ya NO lleva la cabecera «⚠ CAMPAÑA NO
VÁLIDA»**, que es lo que bloqueaba C4 bis y R23. Línea base **132,7 s**, verde
de punta a punta; HEAD medido `d8c73b8`; media 90,1 s por mutante; timeout
efectivo 266 s.

**El superviviente NO se reabre.** Es `bold=True -> bold=False` en
`main.py:1995`, mutante equivalente, **firmado por el humano el 2026-09-06 a
las 20:45 UTC** («firmo»), registrado en la ficha de F-066 de
`harness/features.json` (commit `5564975`). La firma queda reflejada donde el
líder pidió: **`tasks.md` nota de T12** y **`progress/mutacion_F-066.md`**.

### 2 · [BLOQUEANTE] `tasks.md`: T15 y el estado de T13/T14 — CERRADO

T15 marcada `[x]` (la hizo el líder, commit `26ce092`). Sección nueva
«Estado de las tres MANUAL» con **por qué** T13 y T14 siguen abiertas: T13 toca
`infra/` y `az` —lo autoriza el humano— y además el líder decidió con él
retrasar el despliegue a **después de la nocturna del lunes 07**, que es la
primera acotada y la que da T31b y T34 de F-025; T14 depende de esa nocturna.
Escrito también que **R19, R20 y R24 dependen de ellas** y siguen PENDIENTES.

### 3 · [BLOQUEANTE] Las `MANUAL` en `current.md` con su comando — CERRADO

Sección nueva **«F-066 · LAS VERIFICACIONES `MANUAL (humano)`, CON SU COMANDO
EXACTO (C4)»**, con la misma forma que la de F-025: tabla de estado y una
subsección por verificación con el comando literal. Las cinco: `check-raw-
recuentos` local (T9, hecha), `git -C ../azure-apps log -1 --stat` (T11,
hecha), `python main.py timings` (T13), el `az monitor metrics list ...
cpu_credits_remaining --interval PT1M` (T13) y `check-raw-recuentos` +
`check-diccionario` contra Azure (T14).

### 4 · [BLOQUEANTE] `current.md` purgado y sin encabezado duplicado — CERRADO

De **1.263 a 513 líneas**. Fuera: los tres bloques «Estado a las …» de sesiones
anteriores, «Estado del 2026-09-01», F-042, F-047, las fases 1 y 2 de F-052, la
spec histórica de F-025, la spec histórica de F-066 y la cola de trabajo
caducada («ninguna feature `in_progress`», 31 abiertas). Dentro, porque sigue
vivo: F-066, F-025 y F-052 (`blocked`), el estado del servidor con el comando
de créditos, y la guía completa de la fase 7 de F-025. El **encabezado de F-066
duplicado** (líneas 32 y 42) es ahora uno solo. Cabecera nueva que dice qué se
purgó y dónde vive.

**El test que vigila los recuentos del diccionario NO se ha roto**:
`test_f006_los_recuentos_de_current_son_los_de_hoy` exige que 130 objetos, 822
columnas y 47 de consumo estén en el fichero, y que no aparezcan «102 objetos»
ni «793 columnas». El párrafo con esos tres números se conservó entero y a
propósito. Verificado antes de commitear:
`tests/test_f006_contexto.py tests/test_documentos_del_arnes.py
tests/test_f015_alcance.py` → **48 passed**.

### 5 · La base de la campaña, escrita — CERRADO

`progress/mutacion_F-066.md` lleva ahora, justo bajo la cabecera, el comando
entero con `--base d1f56aa` y la explicación: con el valor por defecto
(`--base dev`) el merge-base es `cd18e096` —esta rama nace de la de F-025 sin
fusionar— y salen **2.904 líneas y 247 mutantes en 11 ficheros**, que son los
de F-025. La base elegida es la correcta; ahora quien recalcule no puede
leerla como un recorte. La misma advertencia está en la nota de T12.

### 6 · R12 sin test trazable — CERRADO

`tests/test_f066_ingesta_raw.py`, tres tests nuevos:

* `test_f066_r12_ninguna_tabla_de_raw_se_aplaza_como_pendiente[00_global.yaml]`
* `test_f066_r12_ninguna_tabla_de_raw_se_aplaza_como_pendiente[objetos_pendientes.yaml]`
* `test_f066_r12_las_cincuenta_y_seis_tablas_tienen_ficha_escrita`

El par es deliberado: la primera sola pasaría también en el mundo en que faltan
fichas y nadie las declaró pendientes, que es peor que aplazarlas. Y se mira
objeto a objeto, no `== []`, para que siga diciendo la verdad sobre `raw` el
día que otra feature aplace legítimamente algo de `stg` o `mart`.

### 7 · `dncpro`: 286.428 frente a 286.432 — CERRADO, medido

Medido contra Sigrid el 2026-09-07, solo lectura por `sigrid-api`:

```
$ python -c "... api.leer_sql('SELECT COUNT(*) AS n FROM [dbo].[dncpro]') ..."
dncpro 286432
```

**La buena es 286.432**, que es la que ya decían `mediciones.md`,
`config/tables_sigrid.yaml` y la ficha de `raw.dncpro`. Los dos sitios con la
cifra mala eran `design.md` §1 y R9 de `requirements.md`: corregidos, con nota
en `design.md` de que se remidió y por qué. **Los tres sitios cuadran.**

## Fase RED de lo escrito en esta sesión

Los tests de R12 se comprobaron **en rojo antes de valer**, inyectando la
violación que persiguen (una entrada `raw.conest` en `objetos_pendientes.yaml` y
la ficha de `conest` renombrada en `raw.yaml`):

```
$ python -m pytest tests/test_f066_ingesta_raw.py -q -k r12
E  AssertionError: objetos_pendientes.yaml aplaza fichas de `raw` con el
   trinquete de pendientes, y R12 lo prohíbe: ['raw.conest']
E  AssertionError: tablas de `raw` sin ficha y sin aplazar: ['conest']
FAILED ...::test_f066_r12_ninguna_tabla_de_raw_se_aplaza_como_pendiente[objetos_pendientes.yaml]
FAILED ...::test_f066_r12_las_cincuenta_y_seis_tablas_tienen_ficha_escrita
2 failed, 1 passed, 312 deselected in 0.39s
```

Restaurados los dos ficheros: `3 passed`. Del test de F-024 la fase RED es al
revés y está arriba: la traza que lo condenaba es el 0,833 % medido por el
reviewer, y la prueba del arreglo son los **0 fallos en 3.000 pasadas**.

## Evidencias

| Evidencia | Valor | De dónde sale |
|---|---|---|
| `bash harness/init.sh` | **exit 0** · «ENTORNO LISTO» | ejecución del 2026-09-07 |
| Tests ejecutados | **3.871 passed, 159 skipped**, 0 fallos | ídem |
| Tiempo de la suite | **293,40 s** (con medición de cobertura) | ídem |
| Cobertura de líneas cambiadas | **92,5 %** (662/716, umbral 80, nivel crítico) | `PUERTA COBERTURA` |
| Puerta de tamaño | req 128/150, design 218/250, impl 219/220, review 140/140 | `PUERTA TAMAÑO` |
| Mutantes generados / evaluados | **23 / 23** | `progress/mutacion_F-066.md` |
| Muertos / supervivientes / timeouts | **22 / 1 / 0**, y **0 sin veredicto** | ídem |
| Campaña válida | **sí**: sin cabecera «CAMPAÑA NO VÁLIDA» | ídem |
| Tiempo de la campaña | **2.072,2 s**, 1 worker, HEAD `d8c73b8` | ídem |
| Línea base de la campaña | **132,7 s**, verde al arrancar y al terminar | ídem |
| Tests propios de F-066 | **345** (315 + 30), 3 más que antes | los dos ficheros |
| Tests de F-024 | **43**, con el reescrito dentro | `tests/test_f024_dominio.py` |
| Estabilidad del test reescrito | **0 fallos / 3.000 pasadas** (antes 25) | medición propia |
| `dncpro` en Sigrid | **286.432** filas | `COUNT(*)` por `sigrid-api` |

Análisis del único superviviente: **completo y firmado** en
`progress/mutacion_F-066.md`. Ninguna sección queda en `PENDIENTE`.

## Ficheros tocados

| Fichero | Qué |
|---|---|
| `tests/test_f024_dominio.py` | el test aleatorio, reescrito (H1) |
| `tests/test_f066_ingesta_raw.py` | tres tests de R12 (H6) |
| `specs/F-066.../design.md` | `dncpro` 286.432 + nota de la remedición (H7) |
| `specs/F-066.../requirements.md` | R9: `dncpro` 286.432 (H7) |
| `specs/F-066.../tasks.md` | T15 `[x]`, estado de T13/T14, nota de T12 (H2, H1, H5) |
| `progress/current.md` | MANUAL con comando, purga, encabezado único (H3, H4) |
| `progress/mutacion_F-066.md` | campaña nueva + `--base` + firma (H1, H5) |
| `progress/impl_F-066.md` | deja de decir que la campaña es inválida |
| `progress/review_F-066.md` | añadido a git (venía sin seguir) |

Sin cambios en `etl_sigrid/`, `main.py`, `config/`, `infra/` ni dependencias.

## Lo que NO se ha hecho, y hay que fichar

* **Observación 8 · la puerta de dobles solo cubre `PostgresClient`.**
  `ApiDoble` queda fuera de `test_f025_contrato_cliente.py`; habría que
  generalizarla a los dos clientes y **portarla a `arnes-base`**, más anotar
  `api` en `_contar_en_sigrid`. **No hecha por orden del líder**: es mejora del
  arnés y cruza la frontera del proyecto. **Para fichar.**
* **Observación 10 · F-044 y F-047 están `done` sin resumen en
  `history.md`.** Deuda previa, ajena a F-066, y `history.md` lo escribe el
  líder. **No hecha por orden del líder. Para fichar.**
* **Observación 9** ya estaba cerrada: es la firma del superviviente.
* **La automejora que propuso el reviewer** —que el informe de mutación imprima
  el comando exacto con su `--base`, y que `reviewer.md` avise de que un
  worktree nuevo no hereda `.env`— tampoco se ha aplicado: es `arnes-base`.
  El hallazgo 5 se ha cerrado escribiendo la base a mano, que es el parche, no
  la cura. **Para fichar.**

## Lo que sigue faltando para cerrar F-066

**T13 y T14**, y con ellas **R19, R20 y R24**. No dependen de código: hace
falta que el humano autorice el despliegue de la imagen y que corra la nocturna
que carga las 8 tablas grandes y recarga `dcf`. El líder ya decidió que eso va
**después de la nocturna del lunes 07**, para no contaminar la medición de
F-025 y F-065. Los comandos están en `progress/current.md`.
