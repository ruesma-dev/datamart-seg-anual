Revisión incremental desde fecf223 (pasada 2) · `fecf223..284cdde`; la pasada 1 fue completa (`main...6096f16`)

# F-147 · Review

- **Veredicto: APPROVED** (pasada 2). Pasada 1: CHANGES_REQUESTED por tres cambios de papeleo y de un test.
- **Nivel de rigor**: `estandar`, declarado en `harness/features.json`. Exige C1-C5, fase RED, cobertura de lo cambiado ≥ 80 % y campaña de mutación con supervivientes analizados.
- **`bash harness/init.sh`**, ejecutado ENTERO por el reviewer en cada pasada, tal cual. Pasada 2 sobre `284cdde`: exit 0, `ENTORNO LISTO`, **8.619 passed, 254 skipped, 0 failed** (2.152,8 s); `PUERTA COBERTURA` [OK] 100,0 % (45/45); `PUERTA TAMAÑO` [OK]. La pasada 1 (`6096f16`) dio lo mismo en 3.432,5 s.

## Pasada 2 · el delta `fecf223..284cdde` (4 commits, 5 ficheros, ninguno de `etl_sigrid/`)

- **Cambio 1 hecho** (`ae570b7`, `progress/current.md`, paso 6): reinicia el MCP leyendo antes la revisión activa,
  con los mismos comandos que F-146, y comprueba la cabecera «Versión 59» / «20 reglas». Orden: imagen →
  `85_update_job` → `publicar-diccionario` → `check-diccionario` → comprobación de solo lectura → reinicio → aviso y medida.
- **Cambio 2 hecho** (`ae570b7`): vuelta atrás con `DROP CONSTRAINT diccionario_reglas_resumen_check`, que lanza
  el humano. Es correcto dejar el CHECK de `entrega`, porque el `DEFAULT 'resumen'` de una imagen vieja lo cumple. `7cc95c2` aparece citado
  en `current.md` y en `impl_F-147.md`.
- **Cambio 3 hecho** (`33aa41d`): R11 exige en el resumen `({estados})`, «N dígitos» del patrón (con una guarda
  si el patrón deja de ser `^[0-9]{N}$`) y los meses. Tiene una traza RED forzada en `impl_F-147.md`.
- **Observaciones atendidas** (`a40d266`): `R-PERFILES` dice ahora «alarmas de recursos y partes» y mantiene la
  orden; recalculado: 248 caracteres. ARCHITECTURE describe bien el `DO`. La nota de `R-OBRA-ACTIVA` (NULL y `TRIM`)
  queda en el informe.
- **Lo ya aprobado sigue valiendo**: el delta no toca código, DDL ni el alcance de la mutación (RM1: el SHA medido
  `61e169f` y HEAD no difieren en ningún fichero del alcance). Medida recalculada: 29.503 (reglas 7.106) frente a un
  tope de 29.504, dentro del trinquete (holgura 1 ≤ 1.000).

## Checkpoints

| | Punto | Estado |
|---|---|---|
| C1 | `init.sh` exit 0; ficheros del arnés presentes | [x] |
| C2 | una sola `in_progress` (F-147); rama `feature/F-147-…`; `current.md` de la sesión; `done` en `history.md` | [x] |
| C3 | hexagonal: `presupuesto_contexto` recibe los textos ya hechos, el dominio no importa infra; SQL en `ddl/`; primera línea con ruta; sin prints, secretos ni dependencias nuevas | [x] |
| C3 | semántica Sigrid: `fas`, mes/origen y versiones master siguen dichas en sus reglas (`R-FAS-AMBIGUO`, `R-IMPORTE-MES`, `R-VERSION-MASTER`) | [x] |
| C3 bis | no toca `docs/referencia/` | N/A (justificado: ningún fichero de `docs/referencia/` en el diff) |
| C4 | R1-R20 con tests `test_f147_rN_*` en verde; R21-R23 son documentación y despliegue (verificación de `tasks.md`: lectura del reviewer / MANUAL), leídos abajo | [x] |
| C4 | tests sin red ni BBDD (fixtures; el DDL se comprueba como texto) | [x] |
| C4 | MANUAL en `progress/current.md` con su comando exacto | [x] (pasada 2: reinicio del MCP y vuelta atrás añadidos) |
| C4 | dobles de test comparados con el original | [x] (puerta automática de `init.sh`, sin dobles nuevos) |
| C4 bis | `rigor` declarado | [x] |
| C4 bis | fase RED con traza real (T3, T5, T7) | [x] |
| C4 bis | cobertura de lo cambiado | [x] [OK] 100,0 % (45/45, umbral 80 %) |
| C4 bis | mutación: totales recalculados por el reviewer | [x] 213 líneas, 31 mutantes, muestra de 20 con la semilla `20260820` |
| C4 bis | muertos comprobados | [x] campaña NO reejecutada: 12.173 s (3 h 23 min) según el informe; recálculo puro + RM1-RM6 |
| C4 bis | coste por mutante = 12.173 × 3 ÷ 20 = 1.826 s ≥ 1 s | [x] |
| C4 bis | sin «CAMPAÑA NO VÁLIDA», «Sin veredicto (base rota)» = 0 | [x] |
| C4 bis | RM1 SHA medido `61e169f…`; de ahí a HEAD solo `tests/`, `progress/`, `specs/` | [x] |
| C4 bis | RM2 media 608,7 × 3 workers = 1.826 s frente a líneas base 1.773-1.799 s | [x] coherente |
| C4 bis | RM5 | N/A (justificado: rigor `estandar` y ningún superviviente declarado equivalente) |
| C4 bis | RM6 | N/A (justificado: no se quitó ninguna guarda; el superviviente se mató reforzando un test) |
| C4 bis | campaña manual | N/A (justificado: la automática dio 31 mutantes) |
| C4 bis | superviviente analizado (`diccionario.py:1353`, hueco real, test reforzado) | [x] |
| C4 bis | «Evidencias» con los cuatro números y los workers (3) | [x] |
| C4 ter | rutas sensibles | N/A (justificado: no existe `harness/rutas_sensibles.json`) |
| C5 | `tasks.md` todo `[x]`; un commit `F-147 Tn:` por tarea (T1 es MANUAL, cerrada dentro del commit de T2) | [x] |
| C5 | sin temporales sin trackear; `features.json` real (`in_progress` hasta el cierre) | [x] |

## Lo comprobado (resumen; el detalle, en los ficheros citados)

- **Las 21 reglas** (`config/diccionario/00_global.yaml` l.707-1470) contra `revision_reglas.md`, una a una:
  los resúmenes son los decididos, palabra por palabra salvo dos recortes para caber en 250 (`R-VENTA-COEFICIENTES`
  y `R-PERFILES`). Todos son orden con columnas exactas. `R-PERFILES` dice, desde la pasada 2,
  «alarmas de recursos y partes» (la tabla decía solo «recursos»; las dos van a `compras_restringida`).
- **El detalle llegó a las fichas**: las 18 fichas del inventario «sin empresa ni obra» de la v58 dicen «mezcla
  las 38 empresas», con su camino comprobado donde lo había (`compras.vencimientos` → `tesoreria.efectos`;
  retenciones por `retenciones.movimientos`; la obra de cabecera y el 4 % en `compras.facturas`/`albaranes`); la
  cuenta bancaria y «no reconstruirla desde `v_facturas_pago`» en `compras_restringida.yaml`; recuentos de lo
  restringido en `contabilidad.saldos_cuenta_mes` y `tesoreria.efectos`; coste de consulta en `stg.plan_mensual`,
  `compras.fact_compras_linea` y `mart.v_fact_periodificado`; 0581/0606/0671/0720 ya estaban en `stg.obras`.
  Los demás objetos sin empresa siguen cubiertos por la frase general de la regla y de su resumen.
- **`R-COMPRAS-SIN-IVA`**, `convenciones.importes_iva` y la cabecera de `compras.yaml`: dicen líneas sin IVA y
  `total_factura`/`total_documento`/`total_a_pagar` + `importe_contratado` con IVA; las tres columnas existen en
  las fichas de `compras.facturas` y `compras.albaranes`.
- **`R-OBRA-ACTIVA`** contra `config/business_rules.yaml` §`ventana` (`[1, 11, 25]`, `^[0-9]{6}$`, 12),
  `domain/ventana.py` (`motivo_de_congelacion`, `meses_transcurridos`) y `SQL_ESTADO_OBRAS`: misma
  `MAX(make_date(anio, GREATEST(mes,1), 1))` con `anio BETWEEN 1990 AND 2100`, misma resta en meses enteros, `<= 12`
  (justo 12 cuenta) e INNER JOIN = «sin fases, congelada». Diferencias inocuas hoy (41 = 41 medido): NULL en `estado_id` y sin `TRIM`, anotadas en `impl_F-147.md`.
- **`R-ALBARAN-ABSURDO`**: sin cifras medidas; albarán, líneas, `< 1e8` y «mil millones»; regla+motivo = 345.
- **Contrato con `mcp-bbdd`** contra su código (`mcp-bbdd/infrastructure/diccionario/diccionario_postgres.py`,
  solo lectura): lee `diccionario_reglas` con columnas explícitas (l.118-120) y `diccionario_publicacion` igual
  (l.124); nada usa `SELECT *` ni compara `n_reglas` con las filas; ningún código suyo cita un código retirado
  (solo dos comentarios de su `config.yaml`, fuera de alcance por spec). Las columnas nuevas van al final y el
  INSERT las lleva al final. `fuera_mcp` sin fila y `n_reglas` = publicadas (20): verificado con el cargador.
  `R-PERFILES` `entera`, regla+motivo = 967, y su ámbito incluye objetos que el restringido lee
  (`compras.documento_alarmas`, `retenciones.apuntes_contables`…): un filtro «por ámbito legible» la sigue sirviendo.
- **DDL** (`ddl/01_diccionario.sql`): `ADD COLUMN` y `ADD CONSTRAINT … NOT VALID` solo si faltan; `VALIDATE`
  solo si `NOT convalidated` y ninguna fila lo incumple, así que **no puede fallar** ni bloquear lectores
  (`SHARE UPDATE EXCLUSIVE`); con todo validado no corre ningún `ALTER` (R5). Se valida en la publicación
  siguiente a la primera (la nocturna). Comprobado en Azure en SOLO LECTURA (`_bootstrap_done = True`): PG 16.15
  (el `DEFAULT` constante no reescribe), y `_meta.diccionario_reglas` es de `sigrid_dm_etl`, el mismo login del
  `.env` que publica: el `ALTER` y el `VALIDATE`, que exigen ser dueño, no fallarán por permisos. `filas_reglas`
  hace `strip()` antes de insertar, así que `btrim` y `len` miden lo mismo. **Una imagen anterior a F-147 no
  puede publicar con el CHECK puesto**: el MANUAL lo dice, para la ida y (pasada 2) para la vuelta.
- **Puerta de tamaño**: fórmula de R17 en `presupuesto_contexto`; recalculada por el reviewer: reglas 7.107,
  enrutado 13.901, bloques 8.496 = **29.504 = `PRESUPUESTO_MAX`**; falla por encima y con holgura > 1.000.
- **`azure-apps`**: `db0b5c5` y `7cc95c2` (el segundo corrige 29.513 → 29.504), los dos solo
  `datamart_seg_anual.md`; describen columnas, semántica, `fuera_mcp`, 2 preguntas y el reparto con F-029 (R21).
  Árbol de `azure-apps` limpio.

## Trazabilidad (requisito → test)

| Req | Tests (`tests/`) |
|---|---|
| R1 | `test_f147_resumen_reglas.py::test_f147_r1_*` (4) |
| R2 | `…::test_f147_r2_*` (6, incluido el que ata 250 al CHECK) |
| R3 | `…::test_f147_r3_*` (2) |
| R4 | `…::test_f147_r4_*` (3) |
| R5 / pet. A | `…::test_f147_r5_*`, `…::test_f147_a_*` (5) |
| R6 / pet. C | `…::test_f147_r6_*` (4) |
| R7 | `test_f147_contenido.py::test_f147_r7_*` (10) |
| pet. B | `…::test_f147_b_r_perfiles_es_corta_y_su_ambito_la_deja_ver_al_restringido` |
| R8 | `…::test_f147_r8_*` (2, barrido del árbol) |
| R9 | `…::test_f147_r9_*` (8) |
| R10 / R11 | `…::test_f147_r10_*`, `…::test_f147_r11_*` (pasada 2: el resumen, atado entero) |
| R12 / R13 / R14 | `…::test_f147_r12_*`, `…r13_*`, `…r14_*` |
| R15 / R16 | `…::test_f147_r15_*`, `…r16_*` |
| R17-R20 | `test_f147_presupuesto_contexto.py` (14) |
| R21, R22, R23 | sin test por diseño (T13/T14: lectura del reviewer y MANUAL); leídos: correctos |


## Cambios requeridos

Ninguno. Los tres de la pasada 1 (MANUAL: reinicio del MCP y vuelta atrás; R11 sobre el resumen) están aplicados (ver arriba).

## Observaciones (no bloquean)

- Las fichas de `raw` derivan el aviso `R-SIGRID-CON`, que ya no tiene fila. No hace daño (el MCP no admite `raw`),
  pero conviene decírselo a `mcp-bbdd` para su F-029: un código de `avisos` sin regla publicada.

## Automejora (propuesta, no aplicada)

- `CHECKPOINTS.md` C4, punto MANUAL: cuando una feature publica metadatos y hay consumidores que cachean, su MANUAL
  debe listar el reinicio del consumidor. Para este repositorio: «si cambia `_meta.diccionario*`, reiniciar la
  revisión del MCP leyendo antes la activa» en `leader.md` o en la plantilla del MANUAL.
