<!-- progress/impl_F-140.md -->
# Informe del implementer · F-140 · Los ingredientes de la proyección de caja

Rama `feature/F-140-proyeccion-caja-ingredientes`. Spec `specs/F-140-proyeccion-caja-ingredientes/`
(D1-D19 cerradas, todas A, D10 incluida). Rigor `estandar`. Diccionario v61 -> **v62**.

## Qué cambió

**El ETL no pasa devengo a caja**: publica los ingredientes y las hipótesis, y la regla dura
`R-CAJA-HIPOTESIS` obliga a quien proyecte a declarar las 23 con valor y nivel.

| Tarea | Commit | Qué |
|---|---|---|
| T1 | `89c1657` | `domain/proyeccion_caja.py`: fórmula de plazo (`leer_formula_plazo`), pendiente y sobre-ejecutado por partida, reparto al céntimo |
| T2 | `02a7a63` | Mismo módulo: catálogo, valores por obra, precedencia MANUAL > SIGRID > DEFECTO |
| T3 | `9278f12` | `config/hipotesis_caja.yaml` (H01-H23, todas `validado: false`) y su lector `infrastructure/config/hipotesis_caja_yaml.py` |
| T4 | `eb2c928` | `00_setup.sql`: `fn_plazo_reconocido/_dias/_dias_retencion` y las 8 tablas (`CREATE TABLE IF NOT EXISTS`, sin DROP ni GRANT) |
| T5 | `f93481c` | `04_plazos_forma_pago.sql` (vista), `05_condiciones_contrato_compra.sql`, `06_condiciones_contrato_cliente.sql` |
| T6 | `1b8aece` | Cascada de obra de los pagos sin centro (contrato > cabecera > líneas) con `obra_via`; dominio `obra_del_efecto` |
| T7 | `58d2b03` | `07_devengo_pendiente.sql`: partida, obra-mes (guarda de la suma) y corte por obra con la frontera con la cartera |
| T8 | `dd953a6` | Carga del YAML en `build_tesoreria` (`PostgresClient.cargar_hipotesis_caja`, `hipotesis_caja_sql.py`) y `08_hipotesis_caja_obra.sql` |
| T9 | `0933056` | `SUB_PASOS` completos, docstring, `LECTURAS_PARA_REANUDAR["build_tesoreria"]`, tests de F-037/F-148 |
| T10 | `db091f7`, `01cc541` | `auxcob` y `auxefc` en `tables_sigrid.yaml` (78 tablas), fichas en `raw.yaml`, recuentos (el segundo commit, dos tests de F-095/F-097 que aún decían 76) |
| T11 | `0992abf` | Diccionario v62 (ver abajo) |
| T12 | `e733268` | `docs/ARCHITECTURE.md`, `CLAUDE.md` (mapa) y `azure-apps/datamart_seg_anual.md` (commit local `7f84d73` en `azure-apps`) |
| T13 | este informe | Contraste de solo lectura (tabla abajo) |
| T14 | `5c8ccf2` | Campaña de mutación y test nuevo para su superviviente (`progress/mutacion_F-140.md`) |

**T11, diccionario v62**: fichas de las 8 tablas, la vista y las 3 funciones de `tesoreria`
(cada tabla/vista con el aviso de F-141 en la primera línea, `clave_negocio` y dos preguntas
que enrutan; la manual y las funciones, `consumo_recomendado: false`); `obra_via` y el
`obra_id` nuevo en las dos fichas de `efectos`, sin «la fase 2 no existe»; remisiones en
`compras.formas_pago` y `compras.contratos`; `R-CAJA-HIPOTESIS` (bloqueante, entrega
`resumen`, 230 caracteres) y `R-TESORERIA-ESTADO` remite a ella; `para_que_sirve` de
`tesoreria` (318); `R-SIGRID-CON` punto 3 gana `auxcob.cod/res`, `auxefc.res`, `obrctr.cod/res`
(lo exige el barrido derivado de `test_f006_fuente_que_gobierna`). Recuentos: **248 objetos,
2143 columnas, 122 de consumo**, 22 reglas en el YAML (21 publicadas).

**Presupuesto de F-147 SUBIDO** de 29.504 a **30.873** con su motivo en
`tests/test_f147_presupuesto_contexto.py`: reglas 7.431 (+325, `R-CAJA-HIPOTESIS`), enrutado
15.000 (+1.099, las nueve fichas recomendadas nuevas), bloques 8.442 (-9). La v61 medía 29.458.

Tests de otras features ajustados (el cambio es de F-140, no un parche): `test_f037_diccionario`
(`obra_via` al final; la ficha ya no niega la fase 2, remite a `devengo_corte_obra`),
`test_f079_stg_consultable` (las 3 funciones en el grupo B, `hipotesis_caja_manual` en un grupo F
nuevo), `test_f141_perfil_restringido` (`NO_DISPONIBLES` con los 9 objetos),
`test_f147_contenido` (`R-CAJA-HIPOTESIS` en el conjunto), y los de T9/T10 ya commiteados.

## Decisiones y desviaciones (justificadas)

1. **07 con tablas temporales `ON COMMIT DROP` y `ANALYZE`** tras cada una. Sin estadísticas el
   planificador elegía bucles anidados: 875 s en solo lectura; sin ellos, ~208 s.
2. **La carga del YAML** necesita `PostgresClient.cargar_hipotesis_caja` (una transacción) y el
   módulo `infrastructure/postgres/hipotesis_caja_sql.py`, fuera de la lista de ficheros del
   diseño: el paso no puede escribir parámetros desde un `.sql`.
3. **SIGRID en H09-H11**: H09 solo con fórmula reconocida de UN vencimiento; las tres solo si
   TODOS los contratos con el cliente de la obra dan valor y el mismo. Si no, DEFECTO.
4. **Valores en JSONB** (`valor_defecto`, `opciones`, `valor`): una hipótesis puede ser número,
   booleano, opción o mapa de días. `fecha_validacion` va como columna aparte de `validado`.
5. **05 usa la fórmula de `auxpag`**, no `ctr.pagfor`; el primer mes pendiente es el mínimo
   mes planificado posterior al cierre; un perfil futuro con total ≤ 0 cuenta como sin perfil.
6. **La CTE de T6 publica `factura_id`** (no `documento_id`) y su alias de `raw.dcf` es `fc`:
   el guardián de nulos de `test_f006_fichas` lee la PRIMERA proyección de cada nombre del
   fichero y acusaba a la ficha de `tesoreria_restringida.efectos` (`documento_id`,
   `codigo_documento`). Sin cambio de resultado.
7. Tres tests propios ajustados al escribir 07 (`\binterval\b`, `ON COMMIT DROP`, literales de
   `to_regclass`). `main.py` no se toca: el docstring de `build-tesoreria` sigue citando 4 SQL.
8. Partidas de 07: 20.565 de coste y 18.997 de venta frente a 20.842/18.524 de la spec (§5);
   los importes casan con §5 al céntimo de M EUR. Se reporta, no bloquea.

## T13 · Contraste de solo lectura (Azure y Sigrid, 2026-10-25)

Ejecutado sin escribir: los `SELECT` de 04-08 en transacción READ ONLY; `auxcob`/`auxefc` aún no
están en Azure (T15) y viajaron leídos de Sigrid como `VALUES`; las funciones, inlinadas.

| Objeto | Resultado real |
|---|---|
| 04 `plazos_forma_pago` | 122 formas (70 PAGO, 52 COBRO), **122 reconocidas**, 42 con retención, 0 sin medio; **0 discrepancias SQL/dominio** fila a fila |
| 05 `condiciones_contrato_compra` | 19.170 contratos (PK única), 19.161 reconocidos, 9 sin forma, 6.647 con `NR`, 6.358 con garantía (27 clase 4, 6.331 clase 5), 14.657 con días fijos, 10 sin obra, 0 sin estado, 705,47 M EUR base; 0 de tercero empleado |
| 06 `condiciones_contrato_cliente` | 970 contratos (PK única), 450 obras, 705 reconocidos, 265 sin forma, 500 COEGAR + 25 RECARGO, 0 sin empresa |
| 07 `devengo_*` | COSTE 21 obras, 20.565 partidas, restante 113,98, pendiente **133,20** M EUR; VENTA 21, 18.997, 115,42, **132,37**. Guarda de la suma 0 fallos, 0 sin categoría, 0 PK duplicadas |
| 07 frontera | cartera viva 36,44 (coste) / 21,31 (venta) M EUR; emitida tras cierre 0,89 / 0,00 |
| 08 `hipotesis_caja_obra` | Tras P1-a (2026-10-26): **483 filas = 21 obras x 23 hipótesis** (antes 462, sin H17), 0 PK duplicadas, 0 sin clave. SIGRID: H09 16 obras (0/30/60 días), H10 16 (2,5/3/5 %), H11 4 (12/3/5 meses) |
| T6 cascada | +4 CONTRATO, +107 FACTURA_CABECERA, +2 FACTURA_LINEAS; pagos no de baja con obra 86,87 % -> 86,95 %; 17.152 siguen sin obra |

Detalle de 07 (adelantado/retrasado, sobre-ejecutado, sin perfil): `progress/current.md`.

## Fase RED (trazas reales, salida de pytest antes del código)

Comandos: `.venv/Scripts/python.exe -m pytest -q <fichero>` sobre el test de cada tarea.

**T1** · `tests/test_f140_dominio.py` (dominio con `raise NotImplementedError`):
```
    def es_columna_de_caja(nombre):
>       raise NotImplementedError
E       NotImplementedError
FAILED tests/test_f140_dominio.py::test_f140_r7_formula_reconocida[120 450R-dias4-450]
FAILED tests/test_f140_dominio.py::test_f140_r8_formula_no_reconocida[30R 450R]
FAILED tests/test_f140_dominio.py::test_f140_r12_pendiente_y_sobre_ejecutado[plan0-ejecutado0-pendiente0-sobre0]
66 failed, 1 passed in 0.95s
```
**T2** · `tests/test_f140_hipotesis.py`:
```
    def construir_catalogo(filas):
>       raise NotImplementedError
ERROR tests/test_f140_hipotesis.py::test_f140_r3_campo_desconocido_y_fila_que_no_es_un_mapa
95 failed, 25 errors in 2.00s
```
**T4** · `tests/test_f140_sql.py` (sin funciones ni tablas en `00_setup.sql`):
```
E       AssertionError: falta el CREATE TABLE IF NOT EXISTS de tesoreria.hipotesis_caja
E       AssertionError: falta el CREATE TABLE IF NOT EXISTS de tesoreria.hipotesis_caja_obra
37 failed, 1 passed in 0.77s
```
**T6** · dominio y SQL de la cascada: `ERROR tests/test_f140_dominio.py` (colección: no existía
`obra_del_efecto`) `1 error in 0.49s`; y la parte SQL, `6 failed`.
**T7** · `tests/test_f140_sql.py` (sin `07`):
```
E       AssertionError: SQL no encontrado: ...\sql\tesoreria\07_devengo_pendiente.sql
32 failed, 36 passed, 71 deselected in 1.97s
```
**T8** · `tests/test_f140_paso.py`:
```
E   ImportError: cannot import name 'hipotesis_caja_sql' from 'etl_sigrid.infrastructure.postgres'
ERROR tests/test_f140_paso.py
134 deselected, 1 error in 1.58s
```
**T11** · `tests/test_f140_diccionario.py` contra el diccionario de HEAD (antes de T11), con
`DICC` apuntado a una copia `git show HEAD:...`, `-k "not docs"`:
```
E       KeyError: 'devengo_corte_obra'
E       KeyError: 'plazos_forma_pago'
E       KeyError: 'hipotesis_caja_obra'
40 failed, 3 deselected in 17.74s
```
**T12** · los tres de documentos, en rojo antes de editar: `ARCHITECTURE.md no dice
«tesoreria.devengo_corte_obra»`, `CLAUDE.md no dice «F-140»`, `azure-apps no dice
«tesoreria.devengo_corte_obra»` (`3 failed, 40 passed`).

En verde tras cada tarea (`git log`: un commit por tarea con su verificación).

## Review pasada 1 (CHANGES_REQUESTED) · correcciones (2026-10-26)

Decisiones del humano: **P1 = (a)**; P2 (venta con y sin coeficientes) = feature aparte, no se
toca aquí. Un commit por cambio:

| Commit | Cambio |
|---|---|
| `e4ea3b3` | P1-a: `08` publica las 23 hipótesis por obra; `admite_obra` ya no filtra filas, va en los dos `LEFT JOIN` (H17 siempre DEFECTO). H11 de SIGRID en meses ENTEROS (`x.meses::INTEGER` si no tiene decimales; con decimales, no es valor). Ficha de `hipotesis_caja_obra` (las 23, 483 filas) y tests nuevos: `test_f140_r5_p1a_se_publican_las_23_y_la_que_no_admite_obra_va_a_defecto`, `test_f140_r22_p1a_la_ficha_de_hipotesis_por_obra_dice_las_23` |
| `2e555c5` | Los 6 avisos nuevos de ruff (4 RUF002 en `proyeccion_caja.py`, E741 y B905 en `test_f140_paso.py`) |
| `51459f9` | `current.md`: las MANUAL de T15 y T16 con su comando exacto, en orden (pasos 0-10) |
| `a2e349b` | `features.json`: `notes` al día (D1-D19 cerradas en A); `python -I harness/backlog.py` sin cambios en `BACKLOG.md` |
| `9826318` | `ARCHITECTURE.md`: si el YAML no valida, 01-07 ya están escritos; lo que no se escribe son las tablas de hipótesis |
| azure-apps `995e369` | La fila «MCP y Power BI» de `tesoreria` (el MCP ya la ve) y el mismo matiz del YAML (local, sin push) |

**RED de P1-a y H11** (`pytest tests/test_f140_sql.py -k "p1a or d18_de_donde"` con el `08`
anterior, guardado con `git stash`):
```
E       AssertionError: ningún filtro deja fuera hipótesis del catálogo
E           h.codigo WHERE h.admite_obra;
E       AssertionError: H11
```
Con el `08` nuevo, `2 passed`. **Presupuesto de F-147 remedido**: 30.873 (reglas 7.431, enrutado
15.000, bloques 8.442), igual que antes; el `resumen` de `R-CAJA-HIPOTESIS` no cambia.
**Contraste de solo lectura de `08` repetido** (Azure y Sigrid, mismo método que T13): 483 filas,
21 obras, 23 códigos, 0 PK duplicadas; SIGRID igual (H11 = 12/3/5 meses).

## Fuera del alcance y pendiente

- **T15 y T16 son MANUALES (humano)**: desplegar la imagen, `ingest` de `auxcob`/`auxefc`,
  `build-tesoreria` con su duración (R27); R19 y R28 con los dos perfiles; `publicar-diccionario`,
  `check-diccionario`, `check-declarados`, `check-unicidad`; reiniciar el MCP y la prueba R25 en
  conversación nueva. Nada de eso se ha hecho: ninguna escritura contra Azure ni Sigrid.
- No hay caja proyectada (por diseño). Las 23 hipótesis siguen sin validar por Negocio.
- `mcp-bbdd` no cambia su lista blanca (`tesoreria` ya está); solo reiniciarse con la v62.

## Evidencias

Medidas reales, no estimadas.

| Evidencia | Valor |
|---|---|
| Tests ejecutados (`bash harness/init.sh`, con cobertura, 2026-10-26, HEAD `ae806aa`, tras la pasada 1 del review) | **9.340 passed, 0 failed, 268 skipped** en 3.803,86 s (+2 tests de P1-a; antes de la review, 9.338 en `898771a`) |
| Tests de F-140 | `test_f140_dominio`, `_hipotesis` (+3 del superviviente), `_sql`, `_paso`, `_diccionario`: en verde dentro de la suite |
| Cobertura de las líneas cambiadas | **96,6 %** (311/322 líneas cambiadas, umbral 80 %): línea `PUERTA COBERTURA` de `init.sh` |
| Mutación (`python -m harness.mutacion --feature F-140 --workers 2 --timeout 2400`) | **141 generados, 20 evaluados (muestreo `estandar`, semilla 20260820), 19 muertos, 1 superviviente, 0 timeouts**, 6.448,8 s. El superviviente era un hueco real: test nuevo que lo mata (verificado a mano, `3 failed` con el mutante). Análisis en `progress/mutacion_F-140.md` |
| Tiempo de la suite | 3.803,86 s con cobertura (`init.sh`, tras la review; 4.077,49 s antes); 1.324,66 s sin ella; línea base de la campaña 777,7 y 785,8 s por worktree |
| `bash harness/init.sh` final | **Verde** (`ENTORNO LISTO`, exit 0) en `ae806aa`: pytest 9.340 passed, `PUERTA COBERTURA` 96,6 % (311/322), `PUERTA TAMAÑO` (requirements 146/150, design 240/250, impl 193/220, review 140/140), ruff 275 avisos de deuda previa (281 antes: los 6 de F-140, corregidos) |

**Nota sobre la campaña**: el primer intento con 4 workers y el timeout automático abortó
(«LÍNEA BASE SIN TERMINAR»: la suite limpia no cabe en 600 s con 4 suites compitiendo). Se
relanzó con 2 workers y `--timeout 2400`, como indica el propio mensaje del arnés.
Los muertos de una campaña paralela no se reverificaron en serie: rigor `estandar`, no `critico`.
