<!-- progress/review_F-037.md -->
Revisión completa (pasada 1) · `main...19e020d` · 2026-10-14

# F-037 · Review · CHANGES_REQUESTED

**Veredicto: CHANGES_REQUESTED (RECHAZADO)**. Hay dos cambios y los dos son de evidencia, no de código.
El código, el SQL, los permisos y el diccionario los doy por buenos. El primero es duro: el informe de
mutación lleva la cabecera **«⚠ CAMPAÑA NO VÁLIDA»**, y C4 bis y `reviewer.md` mandan rechazar sin más
análisis. Mi reverificación independiente (RM4) da **45 de 45 muertos**, así que lo que hay que repetir es
la campaña para tener un informe válido. Ningún test nuevo hace falta.

**Nivel de rigor: `critico`** (declarado en `features.json`). Exige fase RED, cobertura ≥ 80 % de lo
cambiado, campaña completa con cero supervivientes y las MANUAL con su comando exacto.

## Verificación ejecutada (resultado real)

- `bash harness/init.sh` sobre `19e020d`, árbol principal: **EXIT 0, ENTORNO LISTO**: **7.826 passed, 242 skipped, 0
  failed** en 1.247 s. `PUERTA COBERTURA` [OK] 100,0 % (136/136); `PUERTA TAMAÑO` [OK]; ruff, 271 avisos de deuda previa.
- **Recálculo puro de la mutación**: `generar_mutantes` sobre los 2 ficheros declarados (157 + 194 líneas)
  da **12 + 33 = 45**, con los mismos operadores y textos que el informe. Coincide.
- **RM4 · Reevaluación de los 45 sobre una COPIA** (`git archive HEAD` en mi scratchpad, sin tocar el árbol).
  Cada mutante se aplicó y se corrieron `test_f037_{dominio,paso,sql}` y `test_f006_dataclasses_inmutables`,
  con `__pycache__` purgado cada vez. Base: **370 passed**. Resultado: **45/45 con al menos 1 fallo** (de 1
  a 43 fallos), unos 4 s cada uno. Los dos `timeout` de la campaña (`tesoreria.py:192` `is None` y `:193`
  `or`) dan **3 y 5 fallos**. Los tres de las banderas de `@dataclass` solo los mata la guarda de F-006,
  como dice el informe. Reproducidas al pie de la letra más de dos filas del informe del implementer.
- **SQL ejecutado en PostgreSQL 16 local** (contenedor desechable, ya borrado), con un `raw` de juguete:
  un caso por motivo, 4751 frente a 4753, BAJA con `fecrea`, `est` 10 sin fecha, `est` 14, previsto de
  2020, remesa mixta, cobro con obra y la TABLA de F-080 con una vista colgando.
  - Motivos y precedencia como el dominio. Los cinco casos de personal salen restringidos, y el 4751, que
    no lo es, sale visible. `previsto_antiguo` solo en el PREVISTO de 2020.
  - `importe_remesa` sale a NULL en la general para la remesa mixta. En la completa se conserva.
  - Los recuentos sin importes cuadran.
  - **05**: el `DO` borra la tabla con CASCADE y crea la vista. Los 31 tipos de la vista son
    **idénticos** a `COLUMNAS_TABLA_F080`.
  - **Segunda noche** (00-03 otra vez, y 05 sobre la vista): la vista sobrevive al `TRUNCATE` y no cae
    nada por CASCADE.
  - **Guarda R12**: con un empleado forzado a `restringido = false`, 02 lanza `RAISE` («1 efectos de
    personal; no se publica»). La transacción se deshace y la general se queda con las 7 filas de antes,
    sin el empleado.
- **Azure**: `connection timeout` desde este puesto (IP fuera del firewall, memoria «IP del puesto»). No
  he vuelto a medir las cifras de T12, y valen las del implementer. Tampoco cargaba el MCP.

## Lo que no puede fallar (pedido del líder)

| Punto | Resultado |
|---|---|
| Ningún pago de personal en `tesoreria.efectos` ni en `compras.vencimientos` | [x] La general es `WHERE NOT restringido`, y `restringido` es `motivo IS NOT NULL` (nunca NULL). La guarda recalcula los cuatro criterios y la cuenta sin resolver desde `raw` (probada). La vista lee la GENERAL (`test_f037_r15_..._filtra`: «tesoreria_restringida» prohibido en 05). Fallo cerrado de la cuenta comprobado |
| El estándar sin acceso a `tesoreria_restringida` | [x] `settings` y `.env.example`: vetada y restringida, no en consumo. `02_roles.sql`: en los dos vetos al estándar (con privilegio por defecto), **no** en el veto al total, concedida al autorizado, y en las comprobaciones finales. `apply_grants` sin cambios (es de listas). Tests r20-r22 y F-135/F-136 adaptados |
| CREATE IF NOT EXISTS + TRUNCATE sin CASCADE | [x] Ningún `DROP` en `tesoreria/` (test r14). Probado en local en dos noches |
| `previsto_antiguo` y su regla dura (D11) | [x] Dominio con la frontera `<` y el 29-F; SQL con `COALESCE(..., FALSE)`; R-TESORERIA-ESTADO dice que el flujo de caja es `PREVISTO AND NOT previsto_antiguo` |
| Obra solo por el centro (D4-A) | [x] Solo `maestro.centros_coste` por `cenide`; ni `ctride` ni líneas (test r8) |
| Diccionario v51 | [x] `version: 51` sobre 50. Esquemas en el global y en `ESQUEMAS_DEL_DATAMART`. R-FRESCURA ampliada, R-TESORERIA-ESTADO y R-TESORERIA-RESTRINGIDA. `compras.vencimientos` como vista. Sin datos personales (test r27) |
| `BACKLOG.md` y `features.json` tras el `stash` | [x] Frente a `main` solo cambia F-037 (`pending` → `in_progress` y «en curso»). `stash@{0}` es el de F-025, anterior y ajeno. Árbol limpio |

## Desviaciones del implementer (las 12): ACEPTADAS

1 (`fn_fecha` copia de `fn_sigrid_date`), 2 (alias `p`) y 3 (dos CTE: no pueden discrepar) mejoran la
spec. 4 (fechas crudas para el estado) es correcta: una fecha inválida no cambia el estado. 5
(`centro_coste_id` como F-080) es necesaria para R15. 6 (`empresa_id` 0) es coherente con la PK. 7
(`paso_etl` en `build_compras`, frescura declarada en la ficha y en R-FRESCURA) es razonable. 8 (regla
hermana) la design lo dejaba al implementer. 9: `test_f047_steps` no aplica por `stage == name`, y los
pasos se fijan en `test_f047_nocturna` y `test_f037_paso`. 10 y 11 son cosméticas («al menos 50»). 12
(sin guarda contra `raw` en 01): el `JOIN` interno perdería un efecto sin ficha, pero en la dirección
segura (no puede filtrar personal al general), y hoy son 0.

## Checkpoints

**C1** [x] init.sh exit 0 (ver arriba) · [x] ficheros del arnés presentes.
**C2** [x] una sola `in_progress` · [x] rama `feature/F-037-tesoreria` · [x] `current.md` de la sesión
activa · [x] las `done`, en `history.md` (sin cambios aquí).
**C3** [x] Hexagonal: dominio puro (test r1); el SQL en `sql/tesoreria/` con `NN_`; el paso en
`application/steps`. [x] Primera línea con la ruta (py, sql, yaml, tests). [x] Sin `print`, sin secretos
y sin dependencias nuevas. [x] Semántica Sigrid: el efecto se lee de `con`, el estado con el `tip` de su
sentido y las bajas marcadas. `amb`/`fas` no aplican.
**C3 bis** N/A: no toca `docs/referencia/`.
**C4** [x] Trazabilidad: cada requisito tiene su test. R16, R23, R29 y R30 son MANUAL, como declara la
spec (tabla abajo). [x] Sin red ni BBDD en los unit tests. **[ ] Las MANUAL no están listadas en
`progress/current.md` con su comando exacto**: solo dice «Pendiente MANUAL: T13-T16 (…)», sin comandos
(cambio 2). [x] Dobles: la puerta automática de `init.sh` en verde. `FakePg` de `test_f037_paso` solo
usa `execute_sql_file` y `count_rows`, que existen.
**C4 bis** [x] `rigor: critico` declarado. [x] Fase RED con trazas reales de T1-T9. [x] Cobertura:
`PUERTA COBERTURA` [OK] 100 % de 136. [x] Recálculo puro de los totales coincide (45). [x] «Tiempo
total» de 23.686 s, por encima de 60 s: la campaña no se reejecuta, y en su lugar va el RM4 de arriba.
[x] Coste por mutante: 23.686 × 4 / 45 = 2.105 s, por encima de un segundo y de la línea base, no por
debajo; cuadra con la suspensión que declara el informe. **[ ] El informe lleva «⚠ CAMPAÑA NO VÁLIDA»**
(cambio 1). [x] RM1: SHA medido `8ee5e35`; desde entonces solo cambian `progress/` y `tasks.md`, nada
del alcance. [x] RM2: media × W = 2.105 s frente a una base de 715 s. Es más, no un salto a la baja: no
hay invención. [x] RM3: ningún mutante equivalente salió muerto (los 45 cambian el comportamiento).
N/A RM5: no hay equivalentes declarados. N/A RM6: no se quitó ninguna guarda. [ ] Tabla de la campaña
manual: la reverificación en serie no trae una fila por mutante, solo 5 con texto. El punto es del caso
«0 mutantes», pero el criterio es el mismo; queda cubierto si se cumple el cambio 1. [x] Sin
supervivientes PENDIENTE. [x] «Evidencias» con los cuatro números y los workers (4).
**C4 ter** N/A: no hay `harness/rutas_sensibles.json` declarado.
**C5** [x] T1-T12 y T17 en `[x]`, con un commit por tarea (T11-T12 juntos, aceptado). T13-T16 son
MANUAL y van después del review (design §7): N/A justificado. [x] Sin temporales. [x] `features.json`
real (`in_progress`).

## Cobertura requisito → test

| Req. | Test |
|---|---|
| R1, R3, R4, R25 bis | `test_f037_dominio` (r1_*, r3_*, r4_*, r25bis_*) |
| R2 | `test_f037_dominio::r2_la_regex_es_la_de_f135`, `test_f037_sql::r2_*`, `r12_la_guarda_recalcula` |
| R5-R9 | `test_f037_sql::r5_*`, `r6_*`, `r7_*`, `r8_la_obra_sale_solo_del_centro`, `r9_*` |
| R10-R14 | `test_f037_sql::r10_*`, `r11_*`, `r12_*` (3), `r13_*`, `r14_*` |
| R15, R16 | `test_f037_sql::r15_*` (lista y tipos), `r16_*`, `test_f080_sql::r7_..._vista`, `r8_...`; recuento MANUAL |
| R17, R18 | `test_f037_paso::r17_*`, `r18_*` |
| R19 | `test_f037_diccionario::r19_check_declarados_*`, `r19_check_unicidad_*` |
| R20-R22 | `test_f037_grants::r20_*`, `r21_*`, `r22_*` |
| R23, R29 | MANUAL (T13, T14 y T16) |
| R24-R27, R30 | `test_f037_diccionario::r24_*`, `r25_*`, `r26_*`, `r27_*`, `r30_*`; contraste MANUAL |
| R28 | `test_f037_diccionario::docs_*` y `azure-apps` `a781704` (local, sin push) |
| R31 | `bash harness/init.sh` |

## Cambios requeridos

1. **Repetir la campaña de mutación hasta tener un informe VÁLIDO**: `python -m harness.mutacion --feature
   F-037`, con el mismo alcance (`build_tesoreria_step.py` y `domain/tesoreria.py`), en una ventana sin
   suspensión de la máquina. Bajar los workers (`--workers 2`) para que la línea base de cierre no expire
   (es lo que pide la propia herramienta). `progress/mutacion_F-037.md` tiene que salir **sin** la cabecera
   «⚠ CAMPAÑA NO VÁLIDA», con 45 generados y 0 supervivientes, y con el SHA de HEAD de ese momento.
   Ningún código cambia: mi RM4 da 45/45. Lo que falta es la evidencia de la herramienta, no la del
   implementer.
2. **`progress/current.md`**, en la entrada de F-037 del 2026-10-14: listar las MANUAL con su **comando
   exacto**, que hoy solo están en `tasks.md` y en `impl_F-037.md`:
   - T13: el orden de design §7 y el comando de cada paso.
   - T14: las cuatro consultas, con su resultado esperado.
   - T15: `publicar-diccionario` y los tres `check-*`.
   - T16: la repetición de la negativa.

**Observación, sin cambio exigido.** El `INSERT` de 01 y 02 no se ha ejecutado nunca contra datos
reales: T12 corrió el `SELECT`. Los `VARCHAR` vienen de F-080 y de `raw.con`. El primer build de T13 lo
prueba, y si fallara, la transacción deja todo como estaba. **Pasada 2: incremental desde `19e020d`.**

**Automejora (propuesta, no aplicada).** C4 bis podría admitir, en `critico`, que una campaña «NO
VÁLIDA» **solo por expiración** (base rota = 0) se cierre con una reverificación en serie. La condición:
una fila por mutante, reproducida entera por el reviewer sobre una copia (aquí, 4 min frente a horas).
Que lo decida el humano.
