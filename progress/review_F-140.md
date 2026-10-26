<!-- progress/review_F-140.md -->
Revisión incremental desde d6a29a6 (pasada 2) · `git diff d6a29a6..6ff734d` · HEAD `6ff734d`

# F-140 · Review · los ingredientes de la proyección de caja

- **Veredicto: APPROVED**. Los cuatro cambios de la pasada 1 están resueltos, las dos observaciones
  pedidas también, y `init.sh` sale en verde (ver abajo).
- **Nivel de rigor:** `estandar` (declarado): fase RED, cobertura ≥ 80 % y mutación analizada.
- **`bash harness/init.sh`** (lanzado por mí, tal cual, en `6ff734d`): **exit 0, `ENTORNO LISTO`**: 9.340 passed, 0 failed, 268 skipped (4.755 s); `PUERTA COBERTURA` 96,6 % (311/322); `PUERTA TAMAÑO` OK.
- Lo aprobado en la pasada 1 sigue valiendo. El delta toca `08`, una ficha, docstrings de
  `proyeccion_caja.py`, tests, documentación, `features.json` y `current.md`. No cambia ninguna firma
  pública ni el alcance medido por la campaña (recalculado: 727 líneas y 141 mutantes, como antes).

## Pasada 2 · comprobación de cada punto

1. **MANUAL en `current.md`** (C4): hecho. Diez pasos, en orden y con su comando exacto:
   - tag de vuelta atrás, imagen y job, con la comprobación de que el job apunta a ella;
   - `ingest --table auxcob/auxefc --full` y `build-tesoreria` con su duración (R27);
   - R19 con los dos logins sobre los nueve objetos;
   - las consultas de R28 (ya esperando 483, 21 y 23);
   - `publicar-diccionario` solo con la imagen en el job; `check-diccionario`, `-declarados` y `-unicidad`;
   - reinicio del MCP y R25.

   Sin secretos: el host va como `<host>` y las contraseñas se leen del vault.
2. **`features.json`** (C5): `notes` al día. D1-D19 cerradas en A, la pasada 1, P1 = (a), P2 como
   feature aparte, y T15/T16 MANUAL.
3. **`azure-apps` `995e369`** (local, sin push): la fila de `tesoreria` dice ahora que `mcp-bbdd` ya
   la tiene en su lista blanca (estándar y total, no restringido). El fallo del YAML queda exacto
   (01-07 escritos; las tablas de hipótesis, intactas), y la fila de `_obra` dice «las 23 (H17, por
   defecto)». `ARCHITECTURE.md` dice lo mismo, incluido el caso de la guarda de `08`.
4. **P1 = (a)**: `08` ya no filtra con `WHERE h.admite_obra`. `admite_obra` va ahora en los dos
   `LEFT JOIN` (manual y SIGRID), así que la hipótesis que no lo admite cae siempre a DEFECTO.
   Ficha (grano: 483 filas), `COMMENT` y test nuevo (`r5_p1a`, sin filtros por código; `r22_p1a`).
   **Lo ejecuté** en el PostgreSQL 16 local desechable (Docker `--rm`, sin Azure):
   - **23 filas por obra**;
   - H17 en `DEFECTO/DEFECTO` aunque meta a mano una fila manual de H17;
   - H11 de SIGRID = `12` (tipo `number`, ya no `12.00`), y un contrato de 1,5 meses no da valor;
   - el MANUAL sigue ganando (H11 = 7 en la obra 2).
- **H11 en meses enteros**: `CASE WHEN meses = trunc(meses) THEN meses::INTEGER END`. Uno con
  decimales cuenta como contrato sin valor y, por D18 («todos dan valor y el mismo»), la obra cae a
  DEFECTO. Coherente con la unidad MESES del catálogo.
- **ruff**: `ruff check` sobre todos los `.py` de F-140 → «All checks passed!». Los RUF002 se
  arreglan cambiando `−`/`×` por `-`/`*` solo en docstrings, sin tocar código.
- **Resumen de `R-CAJA-HIPOTESIS` y F-147**: el resumen no cambia (diff de `00_global.yaml` vacío) y
  ahora es VERDAD: `hipotesis_caja_obra` trae las 23. Volví a medir el presupuesto con la función que
  publica: **30.873** (7.431 + 15.000 + 8.442) = `PRESUPUESTO_MAX`, porque la ficha no es parte del
  enrutado más que por su clave y sus dos preguntas, y esas no cambian.
- **Mutación (RM1)**: medida en `e733268`. En producción el delta solo cambia docstrings de
  `proyeccion_caja.py` (sin mutantes nuevos: 141 igual) y `08`, que es SQL y está fuera del alcance de
  la herramienta. La campaña sigue valiendo; no se reejecuta.

## Checkpoints (pasada 2)

- **C1** `[x]` init.sh en verde. `[x]` existen los ficheros base.
- **C2** `[x]` una sola `in_progress`. `[x]` rama `feature/F-140-…`. `[x]` `current.md`: la sección
  activa es F-140, y el resto son MANUAL vivos de features cerradas, que no añade F-140. `[x]`
  history: F-140 aún no está `done`.
- **C3** `[x]` hexagonal. `[x]` primera línea con la ruta. `[x]` sin prints ni secretos. `[x]`
  semántica Sigrid.
- **C3 bis** N/A: no entra ningún documento externo.
- **C4** `[x]` trazabilidad (tabla abajo). `[x]` tests sin red ni BBDD. `[x]` **MANUAL con su comando
  exacto** (resuelto). `[x]` dobles (`_PgFalso` con las firmas del cliente real, más la comprobación
  automática).
- **C4 bis** `[x]` rigor declarado. `[x]` RED con salida real. `[x]` cobertura. `[x]` mutación con el
  recálculo independiente (727 líneas, 141 mutantes) y el superviviente reproducido (3 failed). La
  campaña no se reejecutó: 6.448,8 s, más de 60. `[x]` coste por mutante 644,8 s. `[x]` sin «⚠
  CAMPAÑA NO VÁLIDA». `[x]` RM1, RM2 y RM6. RM5: N/A por nivel `estandar`. Campaña manual: N/A (fue
  automática). `[x]` superviviente analizado. `[x]` «Evidencias» con W = 2.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5** `[x]` `tasks.md`: T1-T14 y T17 `[x]`, con un commit por tarea. T15 y T16 son MANUAL (humano)
  por el diseño (§8). `[x]` sin temporales (solo este informe, sin trackear). `[x]` **`features.json`
  al día** (resuelto).

## Cobertura · requisito → test (`tests/test_f140_*`)

| Requisito | Tests |
|---|---|
| R1 | 9 |
| R2 | 28 + 3 del superviviente |
| R3 | 15 + la guarda de `08` |
| R4 | 3 |
| R5 | 15: orden del `CASE` = dominio, y P1-a |
| R6 | 1 |
| R7 | 4 |
| R8 | 8: regex del SQL = las del dominio |
| R9 | 4 |
| R10 | 6 |
| R11 | 3 |
| R12 | 8 |
| R13 | 3 |
| R14 | 16, al céntimo |
| R15 | 3 |
| R16 | 6 + `sin_aritmetica_de_fechas` |
| R17 | 17 + F-037 `r8` |
| R18 | 30: 6 patrones × 5 SQL |
| R20 | 2 + F-037 y F-148 |
| R21 | 4 + los recuentos de 78 |
| R22 | 10 |
| R23 | 2 |
| R24 | 2 + F-147 |
| R26 | docs |
| R29 | `init.sh` |
| R19, R25, R27, R28 | MANUAL, con sus comandos en `current.md` (T15, T16) |

## Pasada 1 (`d6a29a6`, CHANGES_REQUESTED) · resumen

- **Cambios requeridos**:
  1. las MANUAL sin su comando exacto en `current.md` (C4);
  2. `notes` de `features.json` con «D10 abierta» (C5);
  3. `azure-apps` contradictorio («el MCP no ve `tesoreria`») e inexacto («falla sin escribir»);
  4. aplicar la decisión de P1.
- **P1** (decisión del humano: (a)): el resumen de `R-CAJA-HIPOTESIS` manda declarar todas las de
  `hipotesis_caja_obra`, que traía 22 (sin H17). **P2** (feature aparte, no bloquea): el devengo de
  VENTA es SIN coeficientes y lo que se cobra va CON coeficientes; ninguna hipótesis convierte una
  en otra. **La registra el líder tras el merge.**
- **Verificado en la pasada 1 y dado por bueno**:
  - la fórmula de `07` frente al §4.3, paso a paso y contra el dominio;
  - el SQL `00`/`04`-`08` ejecutado en el PostgreSQL local con datos a mano: reparto al céntimo, sin
    perfil, sobre-ejecución, versión equivocada ignorada, adelantado/retrasado, real a origen,
    frontera, SIGRID, guarda de `08`, `tip = 43`, garantía de clase 4/5;
  - la frontera con la cartera, sin duplicar (solo solapa lo emitido tras el cierre, aparte y
    descontado por H21);
  - las temporales con `ANALYZE`: patrón ya en producción, y una transacción por fichero;
  - las desviaciones aceptadas; los tests de otras features, exigidos por F-140;
  - el presupuesto de F-147 medido; perfiles, `R-SIGRID-CON` y secretos, limpios.
- **Observaciones que siguen abiertas, sin bloquear**:
  - la guarda de `08` corre con el catálogo ya cargado (es el orden del diseño, y ahora documentado);
  - `06` publica `retencion_concepto` aunque la fuente sea `COEGAR`;
  - las partidas de `07` difieren de la §5 de la spec, pero los importes casan;
  - el tiempo real de `07` en Azure queda para R27 (T15).
