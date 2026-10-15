# F-139 · Informe del implementer: el límite del índice de adjuntos y el contrato con `mcp-bbdd`

Spec: `specs/F-139-leer-graficos-asociados/` (aprobada el 2026-10-15; R7 enmendado ese día con la
opción A del humano). Rama `feature/F-139-leer-graficos-asociados`, rigor `estandar`. Un commit
por tarea (T1-T5); T6 es este informe y el reviewer; T7 (F-139 a `blocked`, R10) es del líder.
**Nada de SQL, ingesta ni código de producción**: el diff de producción es CERO líneas.

## Qué cambió

| Fichero | Cambio | Commit |
|---|---|---|
| `tests/test_f139_limite.py` (nuevo) | 15 tests: R1-R6 (texto de ficha, versión y arquitectura), R7 (guarda de imports por `ast`, control, dos sabotajes y la excepción única), R9 (tablas de origen) | `5f847c6` (T1) |
| `specs/F-139-…/requirements.md`, `design.md`, `tasks.md` | R7 con la excepción única de `openpyxl` (opción A del humano, 2026-10-15); tareas marcadas | `5f847c6` y siguientes |
| `config/diccionario/compras.yaml`, ficha `documento_adjuntos` | `filename_columns: ["cod"]` y el 500 (R1); párrafo «EL LIMITE (F-139)» con los > 20 MB y las 305 ofertas (R2, R4); párrafo «QUIEN PUEDE ABRIR EL FICHERO» con las cinco tablas y la regla del índice, D1 (R3). Sin columnas nuevas | `408bfb0` (T2) |
| `config/diccionario/00_global.yaml` | `version` 52 -> 53 y su entrada en la historia (R5) | `ea7335f` (T3) |
| `docs/ARCHITECTURE.md` | Punto de F-090: `filename_columns`, la guarda de imports, el límite y quién abre cada fichero (R6) | `72e5683` (T4) |
| `azure-apps/datamart_seg_anual.md` (otro repo) | Sección nueva «Abrir el original de un adjunto (contrato con `mcp-bbdd`, F-139)» con H1-H13, la SQL de H3, la tabla de familias, D1, D2 (ChatGPT), decisiones y «qué se rompe si cambia»; F-090 y «Qué rompe este proyecto a otros» apuntan a ella (R8) | `ec1e38a` en `azure-apps` (rama `master`, sin push) |
| `harness/features.json`, `BACKLOG.md`, `progress/current.md` | F-139 a `in_progress`; parada por R7 y decisión del humano | `cead411`, `5f847c6` |

**No se tocan** (design §5): el SQL, `tables_sigrid.yaml`, `domain/documento_adjuntos.py`,
`sigrid_api_client.py`, `02_roles.sql`/`apply_grants`, `requirements.txt`, `azure-apps/mcp_bbdd.md`
y `azure-apps/sigrid_api.md`.

## Decisiones de diseño y desviaciones (justificadas)

1. **R7 · la desviación que paró el trabajo.** La spec pedía que R7 pasara en RED, pero
   `etl_sigrid/application/steps/load_excel_aux_step.py` importa `openpyxl` desde F-004 (los tres
   Excels de configuración de Negocio). El implementer PARÓ (`cead411`, `progress/current.md`) y
   el humano eligió la **opción A** (2026-10-15): `openpyxl` sigue prohibida con UNA excepción
   nominal (`EXCEPCIONES` en el test). Tres tests la vigilan: la excepción no perdona otro
   fichero ni otra librería (sabotaje), hay exactamente una, y falla si sobra (el fichero
   desaparece o deja de importarla). Escrita en `requirements.md` R7, `design.md` §3 y T1.
2. **R2 · «no afirmar que la herramienta exista» se hace verificable así**: la ficha NO nombra
   `abrir_adjunto` (una IA que lee un nombre de herramienta la llama) y dice «NO ESTA DESPLEGADA».
   Cuando `mcp-bbdd` la despliegue, se cambian la ficha y `test_f139_r2_la_ficha_no_afirma_…`.
   `ARCHITECTURE.md` y `azure-apps` sí la nombran: no los lee la IA del MCP.
3. **R5 · «sube respecto a `main`»** con el patrón de F-090/F-138: `version >= 53` y la entrada
   «version 53 (F-139» en la historia. Comparar contra `git show main:` en vivo rompería el test
   el día del merge (las dos serían 53).
4. **R7 · el barrido**: `ast` sobre `etl_sigrid/**/*.py` y `main.py`; cuenta `import x`,
   `from x import y` como `x` y `x.y` (así `from google import genai` es `google.genai`), por
   prefijo de módulo completo (`pypdfium` no es `pypdf`, `docxtpl_falso` no es `docx`); las
   relativas no cuentan. Un control comprueba que el barrido lee ≥ 50 ficheros y ve `click` y
   `structlog`, para que el test no pase en vacío.
5. **R9 · el test nombra el contrato**: si falta una tabla, una columna o la relación, el mensaje
   dice «rompe el contrato de `abrir_adjunto` con `mcp-bbdd` (azure-apps/…, F-139 R8): avisa a su
   dueño». Además comprueba que el `porque` de cada relación filtra su `familia`.
6. **R8 (MANUAL) sin test automático**, como dice la spec. En `azure-apps` se escribe el pliego
   entero, no un resumen: es lo que leerá quien implemente en `mcp-bbdd`. Sin secretos: el vault
   se nombra como «el vault de `mcp-bbdd`», sin nombre de recurso.
7. **Ficha (texto ASCII como el resto de `compras.yaml`)**: «pidase SIEMPRE con
   `filename_columns: ["cod"]`» va en el párrafo de «EL FICHERO NO ESTA EN EL DATAMART», que ya
   explicaba cómo pedirlo. El párrafo viejo «abrirlo es cosa de `sigrid-api` (o de una
   herramienta del MCP o de un portal…)» se sustituye por el límite de F-139.

## Fase RED (obligatoria, rigor `estandar`)

Tests escritos ANTES de tocar ficha, versión y arquitectura. Primera ejecución (antes de la
decisión sobre R7), `python -m pytest tests/test_f139_limite.py -p no:cacheprovider -q --tb=line`:

```
8 failed, 5 passed in 4.57s
...: AssertionError: este ETL publica el índice, no lee documentos (F-139: la apertura es de `mcp-bbdd`): ['etl_sigrid/application/steps/load_excel_aux_step.py: openpyxl']
```

Tras la opción A (misma orden, salida filtrada a las líneas de fallo; RED de T1, commit `5f847c6`):

```
tests\test_f139_limite.py:84: AssertionError: la ficha no dice «filename_columns: ["cod"]» (R1)
tests\test_f139_limite.py:96: AssertionError: la ficha no dice «mcp-bbdd» (R2)
tests\test_f139_limite.py:117: AssertionError: R3
tests\test_f139_limite.py:127: AssertionError: la regla del índice (D1) no dice «LA MISMA REGLA VALE PARA ESTE INDICE» (R3)
tests\test_f139_limite.py:139: AssertionError: la ficha no dice «17 ficheros» (R4)
tests\test_f139_limite.py:149: AssertionError: F-139 sube la versión a 53
tests\test_f139_limite.py:170: AssertionError: el punto de F-090 de ARCHITECTURE.md no dice «F-139» (R6)
7 failed, 8 passed in 5.14s
```

R5 falló con `assert 52 >= 53`. Pasaban, como pide T1: R2 «no nombra `abrir_adjunto`», los cinco
de R7 y los dos de R9. Verde tras cada tarea:

- T2: `-k "r1 or r2 or r3 or r4 or r9"` -> `8 passed, 7 deselected`; `test_f090_diccionario.py` 22 passed.
- T3: `-k "r5 or version or r24"` sobre F-139, F-138 y F-090 -> `19 passed`.
- T4: `test_f139_limite.py` + `test_f090_diccionario.py` + `test_f006_docs.py` -> `51 passed`.
- Tests del diccionario (`test_f006_*.py` y `test_f*_diccionario.py`, sobre T2): `2753 passed, 246 skipped` en 1.019,7 s.

## Sabotajes manuales (los dientes de R7 y R9; árbol restaurado con `git checkout` tras cada uno)

| Sabotaje | Resultado |
|---|---|
| M1: la relación del índice con `compras.albaranes.albaran_id` pasa a `albaran_idx` | `test_f139_limite.py:330: … el índice no se relaciona con compras.albaranes.albaran_id: rompe el contrato de abrir_adjunto …` (1 failed) |
| M4: la columna `oferta_id` se renombra en la ficha | `:327: … no existe compras.comparativo_ofertas.oferta_id (OFERTA): rompe el contrato …` (1 failed) |
| M2: `load_excel_aux_step.py` deja de importar `openpyxl` | `:302: la excepción de R7 para etl_sigrid/application/steps/load_excel_aux_step.py sobra: ya no importa openpyxl; quítala` (1 failed) |
| M3: `import openpyxl` en `steps/base.py` | `:227: … ['etl_sigrid/application/steps/base.py: openpyxl']` (1 failed) |

## Verificaciones MANUAL pendientes

- **R8 / T5** (humano): `git -C C:\Users\pgris\PycharmProjects\azure-apps log -1 --stat` debe
  mostrar `ec1e38a` (1 fichero, +122 -3) y `grep -n "abrir_adjunto" datamart_seg_anual.md` lo
  encuentra (4 apariciones). Sin push.
- **Publicar el diccionario v53** en Azure (`publicar-diccionario`) es escritura: la autoriza el
  humano al desplegar. Hasta entonces el MCP sigue sirviendo la v52.
- **T7 (líder)**: F-139 a `blocked` con el motivo de R10 tras el APROBADO; entregar el pliego
  H1-H13 a `mcp-bbdd` y la propuesta del 500 (`X-Document-Filename` sin codificar) a `sigrid-api`.

## Fuera de alcance (spec §C)

Extraer o contrastar contenido; convertir formatos (F-142); caché; el perfil restringido y la
aplicación de D1 (F-141); arreglar el 500 en `sigrid-api`; abrir desde el portal; implementar
`abrir_adjunto` (es de `mcp-bbdd`).

## Incidencias de la sesión

- El primer `bash harness/init.sh` de precondición se DETUVO a medio pytest al aparecer el choque
  de R7 (hasta ahí todo `[OK]`). Un segundo lanzamiento con redirección a fichero se canceló a los
  segundos para relanzarlo limpio, como pide CLAUDE.md; al limpiar sus procesos se pararon los
  `init.sh` creados en los últimos 5 minutos (3 procesos; por la hora, los de esta sesión).

## Evidencias

`bash harness/init.sh` (tal cual, en primer plano, 2026-10-16, sobre `8d2b3c7` + este informe sin
versionar), exit 0:

```
8080 passed, 249 skipped, 2119 warnings in 4165.68s (1:09:25)
[OK] pytest en verde (con medición de cobertura)
[AVISO] ruff: 277 avisos (deuda previa, no bloquea).
[OK] PUERTA COBERTURA: N/A (F-139 no cambia líneas Python de producción frente a main)
[OK] PUERTA TAMAÑO: F-139 dentro de los topes (requirements 135/150, design 136/250, impl 121/220)
[OK] Rama actual: feature/F-139-leer-graficos-asociados
ENTORNO LISTO. Puedes trabajar.
```

| Evidencia | Valor medido |
|---|---|
| Tests ejecutados | Suite entera: **8080 passed, 249 skipped, 0 failed**. De F-139: **15** (`tests/test_f139_limite.py`), 15 passed |
| Cobertura de las líneas cambiadas | **N/A**: 0 líneas Python de producción cambiadas frente a `main` (línea `PUERTA COBERTURA`) |
| Mutantes generados / supervivientes | **No aplica, 0 juzgados**: `python -m harness.mutacion --feature F-139` sale con código 3, «ALCANCE VACÍO en F-139: ni una línea de producción que mutar» (todo es documentación, tests y spec), y no escribe `progress/mutacion_F-139.md`. Los dientes de los tests se miden con los sabotajes de arriba (4 de 4 cazados) y los dos tests de sabotaje de R7 |
| Tiempo de la suite | **4.165,68 s (1 h 09 min)** con cobertura, en una máquina ocupada por otras suites; `test_f139_limite.py` solo, 5,1-5,8 s |

**Después de este `init.sh`** se arreglaron los 2 avisos de ruff que añadía el test nuevo (de 275
a 277): `columna` sin usar -> `_columna` y `RUF005` (desempaquetado). Sin cambio de
comportamiento: `python -m ruff check tests/test_f139_limite.py` -> «All checks passed!» y
`python -m pytest tests/test_f139_limite.py` -> `15 passed`. El reviewer vuelve a pasar `init.sh`.

Una ejecución anterior de `init.sh` (15-10) murió al 68 % de pytest con `fork: Resource
temporarily unavailable` (0xC000026B, recursos de la máquina), sin fallo de test: por eso se
relanzó.
