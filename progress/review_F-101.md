<!-- progress/review_F-101.md -->
Revisión completa (pasada 1) · `git diff main...HEAD` (base a64da18, HEAD d28179c)

# F-101 · Review (reviewer, 2026-09-23)

**Veredicto: CHANGES_REQUESTED** (RECHAZADO). SQL y tests correctos; falla una
**premisa sobre datos personales** con la que el humano aprobó D-3, y es falsa.
Tres cambios abajo, ninguno toca SQL.

**Rigor:** `estandar` (declarado). Exige RED, cobertura >= 80 % y mutación.

## Verificado por mí

- `bash harness/init.sh` tal cual: **ENTORNO LISTO**, exit 0; `5112 passed, 189 skipped` en 1.604,66 s; ruff 232 (deuda previa).
- **RED reproducida**: `git archive 4233c72` al scratchpad y `pytest
  tests/test_f101_cabecera_parte.py` -> `45 failed, 5 passed, 1 skipped` (el skip
  es R30, sin `azure-apps` al lado). Cuadra con 46/5; ahí no existían los SQL.
- **Mutación, cero legítimo**: `alcance_de_feature('F-101', base='main')` -> 38
  líneas (29 `build_personal_step.py`, 9 `main.py`), como el informe;
  `generar_mutantes` -> 0. **Control** sobre los ficheros enteros: 12 y 949
  mutantes: el generador funciona, el cero es por diseño (datos y docstrings).
- **Anchuras** contra `sigrid_tablas.md`: `con.cod` 24/`VARCHAR(24)`, `con.res`
  128/128, `conest.res` 48/128, `auxhor.cod` 16/16, `auxhor.res` 48/64. Nada trunca.
- **Privilegios del rol del MCP**, por el propio conector (solo lectura):
  `mcp_sigrid_dm_ro` tiene `SELECT` en `raw.hmores` y `raw.con`, no en
  `raw.reshor`. Ver cambio 1.

## Las siete desviaciones: las siete ACEPTADAS

1. **Agregado en vez de LATERAL**: semánticamente idéntico (mismas líneas con
   cabecera en `hmo`, mismo FILTER con los dos `NULLIF`), misma fuente
   `raw.hmores`, sin índice en `raw`; el EXPLAIN es coherente. R10 fija la forma.
2. `00_global.yaml` 27 -> 28, por el merge de main.
3. **`ALTER ... ADD COLUMN IF NOT EXISTS`**: necesario. El INSERT lleva lista de
   columnas, así que el orden físico distinto no importa; sin DROP, sin perder GRANT.
4. **`raw.yaml` y `test_f066`**: técnicamente como F-074 con `prvcer`; pero ahí
   se escribe parte de la afirmación falsa del cambio 1.
5. Nombre medido fuera de SQL y diccionario: correcto; es el criterio del cambio 2.
6. `reshor` al día (8.968/2.064), con fecha. 7. `N:N` recurso: `check-relaciones`
   usa `EXISTS` y solo da KO con cobertura 0.

## Los cuatro focos del encargo

- **Datos personales**: `prenom` no está en ningún texto ejecutable ni columna de
  ficha (R22); `personal.yaml` solo dice que el precio de NOMINA no se publica.
  Ningún objeto nuevo sale de `personal`. **Pero `hmores.tex` también queda en
  `raw.hmores`, legible por el rol** (cambio 1).
- **Veto de F-057**: en pie. `02_partes_lineas.sql` no nombra `raw.hmo`; el
  código llega por `LEFT JOIN raw.con c ON c.ide = l.hmoide` (`test_f057_r12` y
  `test_f101_r14`, independientes).
- **`azure-apps` 87dc629**: correcto, sin push, árbol limpio: 3 -> 5 objetos,
  cuatro trampas, `hmores.tex` en «Qué consume». No dice que `tex` queda en `raw`.

## Checkpoints

- **C1** [x] init.sh · [x] ficheros del arnés.
- **C2** [x] una `in_progress` · [x] rama `hotfix/F-101-...`, la que declara
  `features.json` · [ ] `current.md` conserva «Decisiones abiertas… antes de
  implementar» y «pasa a `spec_ready`», obsoletos (cambio 3) · [x] history.
- **C3** [x] hexagonal: solo SQL `NN_nombre.sql` en `sql/personal/` y la tabla
  `SUB_PASOS` · [x] primera línea con ruta · [x] sin prints/TODOs/secretos ni
  dependencias nuevas · [x] Sigrid: R-SIGRID-CON, 0 -> NULL; sin `amb`/`fas`.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [x] R1–R30 trazados (tabla abajo; R29 lo comprueba) · [x] sin red ni
  BBDD · [ ] MANUAL en `current.md` sin comando exacto, solo «M1-M10» (cambio 3)
  · [x] dobles: `execute_sql_file` y `count_rows` existen en `PostgresClient`.
- **C4 bis** [x] rigor · [x] RED real y reproducida · [x] cobertura [OK] 94,7 % (968/1022; medida contra `dev`, arrastra lineas de `main`) ·
  N/A `mutacion_F-101.md`: la herramienta no lo escribe con 0 generados (exit 3);
  cero verificado por recálculo y control · N/A reejecución, coste por mutante,
  NO VÁLIDA, RM1, RM2, RM6, supervivientes: no hay mutantes · N/A RM5 por nivel
  · N/A campaña manual: no se hizo, y lo cambiado es SQL/YAML, cubierto por
  tests de texto y el step contra doble · [x] «Evidencias» (sin workers: no hubo campaña).
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5** [x] T1–T13 `[x]` con `F-101 Tn:` (T13 en cinco commits) · [x] árbol
  limpio · [x] `features.json` `in_progress`, correcto antes del APROBADO.

## Requisito -> test (`test_f101_` omitido)

R1 `r1_ddl_partes`, `r1_ddl_partes_indices`, `r1_partes_una_fila_por_parte` · R2
`r2_codigo_parte_desde_con_cod` · R3 `r3_ficha_codigo_parte_no_es_clave` · R4
`r4_descripcion_*` · R5 `r5_fecha_anio_y_mes`, `r5_ficha_*` · R6 `r6_obra_y_centro_*`,
`r6_ficha_*` · R7 `r7_estado_*` · R8 `r8_activo_*` · R9 `r9_fecha_modificacion_*`,
`r9_ficha_*` · R10 `r10_recuento_*`, `r10_ficha_*` · R11 `r11_*` · R12 `r12_*` · R13
`r13_codigo_parte_en_la_linea`, `r13_*_tabla_que_ya_existe` · R14 `r14_*` · R15
`r15_*` · R16 `r16_texto_linea_publicado`, `r16_ficha_*` · R17 `r17_ddl_tipos_hora`,
`r17_*_una_fila_por_reshor` · R18–R25 `r18_*`…`r25_*` (uno o dos cada uno) · R26
`r26_step_seis_*`, `r26_step_encadena_*`, `r26_personal_sigue_sin_dependientes` ·
R27 `r27_check_declarados_*`, `r27_sin_pendientes_nuevos` · R28 siete `r28_*` · R29
`r29_*` · R30 `r30_azure_apps_*`. Todos en verde en la suite de init.sh.

## Cambios requeridos

1. **`hmores.tex` no vive solo en `personal`.** Queda también en `raw.hmores`, y
   `mcp_sigrid_dm_ro` tiene `SELECT` sobre ella (medido; `raw.reshor` está
   revocada por nómina, F-068/F-074, `raw.hmores` no). D-3 se aprobó con la
   premisa de design §8 «texto libre con nombres de persona (queda en
   `personal`)», y el repo lo afirma como hecho: `config/tables_sigrid.yaml`,
   bloque `hmores` («se publica solo en el esquema `personal`, el
   restringible») y `personal.yaml`, `texto_linea` («otra razón para que viva en
   este esquema, el restringible»). Revocar `personal` no retiraría ese texto.
   Atenuante que el humano debe saber: los nombres ya son legibles por el rol
   en `raw.con.res` (de ahí sale `personal.recursos.nombre_recurso`); lo nuevo es
   el texto libre. **Acción**: volver al humano con dos opciones y aplicar la
   elegida — (a) `raw.hmores` a `DEFAULT_EXCLUDED_TABLES` (`config/settings.py`,
   mecanismo F-068), su ficha en `raw.yaml` como las de `reshor`/`emphis` y un
   test que fije la exclusión; o (b) aceptar la exposición por escrito—. En
   ambos casos: corregir las dos frases citadas; que la ficha de `raw.hmores`
   (`raw.yaml`, «Se trae entera desde F-101») avise de que `tex` puede llevar
   nombres **ahí**; y reflejarlo en `azure-apps/datamart_seg_anual.md` (commit
   en ese repo, sin push).
2. **Nombre de persona sacado de Sigrid versionado en la spec**: [un nombre y dos
   apellidos, redactado al commitear] en `specs/F-101-cabecera-del-parte/requirements.md:78`,
   `design.md:195` y `progress/spec_F-101.md:34`. Es contenido de `hmores.tex`,
   lo que la desviación 5 evita en SQL y diccionario. Sustituirlo por «un nombre
   y dos apellidos». El historial lo conserva desde fd4f706: reescribirlo o no
   lo decide el humano antes del merge.
3. **`progress/current.md`**: listar M1–M10 con su comando exacto (M9 antes que
   M1) y retirar el bloque de decisiones abiertas y la frase «pasa a
   `spec_ready`».

## Observaciones (no bloquean)

- Ficha `partes_lineas`: «769 líneas (0,23 %) … (remedido: 615 líneas de 14
  partes)», dos cifras publicadas sin explicar la deriva. Mejor solo 615, con fecha.
- `04_recursos_tipos_hora.sql:8` y el docstring de `test_f101_r25` nombran a una
  persona por el desfase de su precio; bastaría el código MO/0306.
- `tipo_hora_de_baja` saldría NULL si `auxhor.fecbaj` fuese NULL con fila (hoy entero).
- M9 antes que M1 bien señalado: sin `tex` ingerido, `build-personal` a mano
  falla en `l.tex`; la nocturna ingiere antes.

## Automejora (propuesta, no aplicada)

Casilla en C3: «si se ingiere en `raw` una columna con datos personales,
comprobar `has_table_privilege` del rol de consumo sobre esa tabla». El diseño
razonó por esquemas (`personal` restringible); los privilegios de `raw` son por tabla.
