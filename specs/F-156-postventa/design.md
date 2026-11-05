# F-156 · Diseño: postventa entera

Mediciones: `progress/spec_F-156.md`. Requisitos y decisiones del humano (2026-11-03):
`requirements.md`. Lo que pide a `mcp-bbdd`: `pliego_mcp_bbdd.md`.

## 1. Encaje y límite del servicio

- **Ingesta** por la vía de siempre (`ingest_raw` + `tables_sigrid.yaml`, `--full` cada noche):
  13 tablas nuevas y el `where` de `rcg`/`gra` ampliado. `stream_table` compone
  `WHERE [ide] > ? AND (<where>)` y `check-raw-recuentos` cuenta con el mismo `where`.
- **Negocio**: esquemas módulo `postventa` y `postventa_restringida`, paso `build_postventa`.
  Las tablas solo leen `raw`; la única excepción es la vista de coste (§ 6, `08`), que lee
  `compras` en tiempo de consulta. Patrón de `personal`/`contabilidad`: falla solo.
- **Perfil nuevo «postventa»** (D1): un grupo y un login como los del restringido (F-141).
- **Límite**: el ETL LEE Sigrid. No es de aquí la aplicación `postventa-incidencias` (escribe
  en Sigrid y tiene su base `postventa`; su F-048 trae SU base, otra frontera: PostgreSQL no
  cruza bases) ni la herramienta del MCP (`pliego_mcp_bbdd.md`). Sin microservicio nuevo.

## 2. Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/postventa.py` | constantes y oráculos (§ 5) |
| `etl_sigrid/application/steps/build_postventa_step.py` | `BuildPostventaStep` (patrón `build_personal_step.py`: `SUB_PASOS`, `depends_on = ["ingest_raw"]`) |
| `etl_sigrid/infrastructure/postgres/sql/postventa/00_setup.sql` … `08_coste_obra.sql` | § 6 |
| `config/diccionario/postventa.yaml`, `postventa_restringida.yaml` | fichas (§ 10) |
| `tests/test_f156_dominio.py`, `_ingesta_sql.py`, `_grants.py`, `_pipeline.py`, `_diccionario.py` | § 13 |

## 3. Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `config/tables_sigrid.yaml` | + 13 tablas al final (bloque `# --- F-156`, cifras en comentario); `where` de `rcg` y `gra` con `707, 708, 47` |
| `main.py` | `BuildPostventaStep` en `run-all` tras `BuildContabilidadStep`; `"build_postventa"` en `PASOS_CON_PERMISOS`; comando `build-postventa` (copia de `build-personal`) |
| `config/settings.py`, `.env.example` | listas de R28; bloque nuevo `DEFAULT_PERFIL_POSTVENTA_*` (R29) con su comentario y sus `PG_PERFIL_POSTVENTA_*` |
| `etl_sigrid/infrastructure/postgres/grants.py` | `perfil_postventa_en_conflicto` (§ 7); reutiliza `build_perfil_restringido_statements` (ya recibe grupo y esquemas) |
| `etl_sigrid/application/steps/apply_grants_step.py` | bloque del perfil postventa DETRÁS del restringido (§ 7) |
| `etl_sigrid/domain/diccionario.py` | `ESQUEMAS_DEL_DATAMART` + los dos esquemas (18) |
| `infra/sql/02_roles.sql` | § 7 |
| `config/diccionario/raw.yaml`, `00_global.yaml` | fichas de las 13 tablas, `rcg`/`gra`, «93 tablas»; versión +1 (la siguiente libre: hoy v70), esquemas, `R-FRESCURA`, `R-PERFILES`, `R-POSTVENTA-RESTRINGIDA` |
| `docs/ARCHITECTURE.md`, `docs/runbook_postgres_azure.md`, `CLAUDE.md` | esquemas, perfil postventa (con el § de roles del runbook), censo 93 |
| tests de censo, esquemas, pasos y perfiles (`grep -rln -E "\b80\b|ESQUEMAS_DEL_DATAMART|PASOS_CON_PERMISOS|PERFIL_RESTRINGIDO" tests`) | 80 -> 93; 16 -> 18; 15 -> 16 pasos; nada más |
| `../azure-apps/datamart_seg_anual.md` (commit propio, sin push) | consume 93 tablas; expone los dos esquemas; perfil postventa; enlace al pliego |

## 4. Ficheros que NO se tocan

- `sql/compras/14_documento_adjuntos.sql`: su `JOIN raw.con … tip IN (12, 14, 15, 44, 46)` ya
  filtra; con `rcg`/`gra` más anchos da las mismas filas (test que lo fija).
- `sql/compras/12_documento_procesos.sql` y `13_estado_documentos.sql`: el histórico de
  postventa es suyo. `ingest_raw_step.py`, `sigrid_api_client.py`, `objetos_pendientes.yaml`,
  `reanudacion.py` (las tablas solo leen `raw`; la vista no necesita reanudación).

## 5. Dominio · `etl_sigrid/domain/postventa.py`

`TIPO_UNIDAD = 707`, `TIPO_INCIDENCIA = 708`, `TIPO_TAREA = 47`; `ESTADOS_ABIERTOS = (1, 3)`,
`ESTADOS_RESOLUCION = (5, 7, 9)`, `ESTADO_CERRADA = 9`; `CLASE_FIN_GARANTIA = {"0001":
"fecfin1", "0002": "fecfin2"}`; `GRATIPIDE_REPARACION = 35`; `FAMILIAS_ADJUNTOS`;
`ORIGENES_FECHA = ("PASO", "CIERRE_APLICACION", "ALTA", "SIN_HISTORIAL")`;
`TEXTO_CIERRE_APLICACION = "Cerrar parte (postventa-incidencias)"`; `COLUMNAS_PER` y
`COLUMNAS_PER_PROHIBIDAS`; `LIGAS_COSTE = ("PARTIDA", "ANCESTRO", "SIN_OBRA")`.
Funciones puras: `fin_garantia`, `dentro_garantia`, `familia_adjunto(tip, gratipide)`,
`origen_fecha(estado, destino_ultimo_paso, momento_ultimo_paso, momento_cierre_aplicacion)`,
`enmascarar(texto)`, `obra_de_partida(codigo) -> str | None` (cifras iniciales, 3 o 4, a 4 con
ceros: `0561 ` -> `0561`, `0593B` -> `0593`, `626` -> `0626`, `CI.1.2` -> None) y
`liga_coste(cadena_de_codigos)` (la partida y sus ancestros, del más cercano al más lejano).

## 6. SQL · `sql/postventa/` (`DROP … CASCADE` + `CREATE`, como `compras`)

- **`00_setup.sql`**: `CREATE SCHEMA IF NOT EXISTS` de los dos; `postventa.fn_fecha(int)`
  (copia de `compras.fn_sigrid_date`, test de texto), `postventa.fn_momento(fec, hor)` (regla
  de hora de `12_documento_procesos.sql`), `postventa.fn_enmascarar(text)` con `regexp_replace`
  (`[6-9]\d{8}`, `[6-9]\d{2} \d{2} \d{2} \d{2}` -> `[TELEFONO]`; `[^\s@]+@[^\s@]+\.[^\s@]+` ->
  `[CORREO]`), `postventa.fn_obra_de_partida(text)` (la de `obra_de_partida`).
- **`01_unidades.sql`** -> `postventa.unidades` (PK `unidad_id`): `raw.upv u JOIN raw.con cu ON
  cu.ide = u.ide` (código, nombre, estado por `raw.conest` (707, `cu.est`), empresa), obra por
  `u.obride` -> `raw.con`, `LEFT JOIN raw.prmtpl`, fechas con `fn_fecha`, `tiene_propietario`.
  Sin `restel`, `resele`, `peride`, `cliide`. **`postventa.oficios_obra`**: `raw.obrofc` +
  `raw.auxofc` + proveedor (`raw.prv`/`raw.con`).
- **`02_incidencias.sql`**: guarda R12 (`DO`); `postventa.incidencias` (PK `incidencia_id`):
  `raw.rcp r JOIN raw.con c ON c.ide = r.ide AND c.tip = 708` (las 1.502 cabeceras sin `rcp`
  no entran) `JOIN postventa.unidades`, `LEFT JOIN raw.auxrcp/auxtrcp/auxofc`, `raw.conext`
  (`RCPCLI`, `valt`), `fn_enmascarar(c.res)`, `fn_enmascarar(r.tex)`, R8.
  `forma_comunicacion_codigo` = `rcptip` (solo el 1 tiene nombre: `ESCRITA`).
  **`postventa.incidencia_intervinientes`**: `raw.rcpint JOIN postventa.incidencias` (fuera
  los 1.499 huérfanos) + `oficios_obra`; `causante = cauave <> 0`.
- **`03_tareas.sql`** -> `postventa.tareas` (PK `tarea_id`): `raw.tar t JOIN raw.con ct ON
  ct.ide = t.ide AND ct.tip = 47 JOIN postventa.incidencias ON incidencia_id = t.rcpide`, estado
  (47), `LEFT JOIN raw.tarres` (una por tarea) -> `oficios_obra`, `empleado_id = NULLIF(t.empide,
  0)`, `fn_enmascarar(t.tex)`.
- **`04_procesos.sql`** -> `postventa.incidencia_procesos` (PK `paso_id`): `UNION ALL` de
  `raw.rac r JOIN raw.con c ON c.ide = r.conide AND c.tip IN (707, 708, 47)` (`origen = 'RAC'`,
  `proceso = r.res`, `usuario = NULLIF(BTRIM(r.usu), '')`, `paso_id = 'RAC-' || r.ide`) y
  `raw.log l JOIN raw.con c ON c.tip = l.tip AND c.cod = l.cod AND c.emp = l.emp` (`origen =
  'CIERRE_APLICACION'`, origen NULL, destino 9, `usuario = l.usu`, `paso_id = 'LOG-' ||
  l.ide`); estados por `raw.conest` (tipo, est) con id, código y nombre; `usuario_nombre` por
  `LEFT JOIN raw.usu ON usu.cod = usuario` (`res`, como `compras.documento_procesos`);
  `es_ultimo` por `ROW_NUMBER()` sobre `momento DESC, paso_id DESC`.
- **`05_estado.sql`** -> vista `postventa.v_estado_incidencias`: último paso (con su `usuario`
  como `cambiado_por`), último cierre de aplicación y primer paso a 5/7/9 por `LATERAL`;
  `CASE` de R15; R16 con `CURRENT_DATE`. Vista: los días no envejecen.
- **`06_adjuntos.sql`**: guarda R21; `postventa.documento_adjuntos` (PK `adjunto_id` =
  `rcg.ide`): `raw.rcg r JOIN raw.con c ON c.ide = r.con AND c.tip IN (707, 708, 47) JOIN
  raw.gra g ON g.ide = r.gra LEFT JOIN raw.auxgra a ON a.ide = g.gratipide`; `familia` por el
  `CASE` de `familia_adjunto`; `extension` y `clase_fichero` con las MISMAS expresiones que
  `compras/14` (test de texto); `empresa_repositorio = g.emp` entera.
- **`07_restringida.sql`**: `postventa_restringida.contactos_incidencia` (incidencia,
  `propietario_id`, `propietario_nombre` = `con.res` del `cliide`, `reclamante_*` y
  `contacto_*` de `raw.per`: nombre, teléfono, teléfono 2, correo), `contactos_unidad` (unidad,
  propietario, persona de contacto, `restel`, `resele`, `avi_*`, `hor_*`, `texohor`) y `textos`
  (`documento_id`, `tipo_documento_codigo`, textos íntegros). Lee `raw` y `postventa`.
- **`08_coste_obra.sql`**: `postventa.partida_obra_origen` (PK `partida_id`): las partidas de
  `raw.obrparpar` de las obras tipo 42 con `POSTVENTA` en `res` o `cod ILIKE 'POSTV%'`; CTE
  recursiva hacia `padide` (tope 10 niveles) y la primera con `fn_obra_de_partida` que case
  con una obra de SU empresa (`raw.con` tipo 42, `BTRIM(cod)`); `liga` y `obra_origen_id`/
  `codigo`. Vista `postventa.v_coste_obra`: `compras.factura_lineas fl JOIN compras.facturas f
  USING (factura_id) JOIN postventa.partida_obra_origen p ON p.partida_id = fl.partida_id`,
  por obra de postventa, obra de origen, `liga` y `date_trunc('month', f.fecha_factura)`, con
  `SUM(fl.importe)` y líneas. **Aviso**: `build-compras` suelto la tira (`DROP … CASCADE`);
  `run-all` la rehace porque `postventa` va detrás. Medido: 6,7 s la agregación entera.

## 7. Permisos y perfil postventa

- **Listas** (R28): `postventa` es consumo (estándar, Power BI, total) y del restringido;
  `postventa_restringida`, vetado al general y restringido (autorizado y total por pertenencia).
- **Perfil postventa** (R29-R30): `DEFAULT_PERFIL_POSTVENTA_SCHEMAS` = la del restringido +
  `postventa_restringida`, EXPLÍCITA (como F-141: un esquema nuevo no le llega solo).
  `perfil_postventa_en_conflicto` (pura, antes de conectar): FAILED si grupo o login coinciden
  con otro rol, si la lista no es la del restringido + exactamente los `*_restringida` de
  postventa, o si alguno de esos no está en lo vetado y lo restringido. Bloque de
  `apply_grants` DETRÁS del restringido: `build_perfil_restringido_statements(grupo_postventa,
  …)` (USAGE + SELECT, privilegio por defecto en REVOKE), veto de `esquemas_ajenos`, búsqueda
  de vistas que filtran (`EXCEPCIONES_FILTRACION_RESTRINGIDO`, las mismas), verificación y
  pertenencias (login solo miembro de su grupo); su resultado en el MISMO mensaje que los otros
  (`verificacion_postventa`, `pertenencias_postventa`). Grupo vacío: no se mira; ausente: aviso.
- **`02_roles.sql`**: `\getenv postventa_pwd POSTVENTA_PWD`; `CREATE ROLE
  mcp_sigrid_dm_postventa LOGIN` y `sigrid_dm_perfil_postventa_ro NOLOGIN` si no existen (guarda
  como F-141 si falta la variable), contraseña solo si viene, `GRANT CONNECT`, pertenencia
  `WITH INHERIT TRUE, SET FALSE`; `postventa_restringida`: `CREATE SCHEMA` con `SET ROLE
  sigrid_dm_etl`, en los `ARRAY` de vetados del 5 ter, `GRANT` + `ALTER DEFAULT PRIVILEGES` al
  autorizado; punto **5 sexies** (copia del 5 quinquies para el grupo postventa); comprobaciones
  finales con su columna.
- **Qué crea el humano en Azure** (sin secretos aquí): genera una contraseña, la guarda en
  `kv-mcp-bbdd-dev` como `pg-password-postventa`, la exporta a `POSTVENTA_PWD` en su sesión y
  corre `02_roles.sql` (crea grupo y login, § 12 paso 2). El job NO lleva variables nuevas.
- **`abrir_adjunto`** (D9): `REPARACION` apunta a `postventa_restringida`: el restringido y el
  estándar reciben PERMISO_DENEGADO; postventa y total la abren. Las FILAS del índice (nombre,
  quién lo subió) sí las ven todos: la regla D1 de F-139 sigue sin aplicar; lo dice la ficha.

## 8. Histórico: qué hay de quién y cuándo (medido)

`rac` trae fecha, hora y login en el 100 % de los pasos (708 37.669, 47 1.156, 707 923); el
login casa con `usu` en 36.451 de 708 (96,8 %), 1.156 y 923. Los 659 cierres de la aplicación
traen login (3 distintos, todos en `usu`). Lo que NO hay: los cambios sin proceso (borrados por
«Deshacer») y el 708 en `SAT` sin pasos (2.015, fecha del alta, sin autor de cambio).

## 9. Decisiones descartadas

- D1-B (fuera) y dejarlos en `postventa` con `REVOKE` por columna (el total hereda del estándar).
- D4: atribuir el coste de las obras `POSTV*` a incidencias (Sigrid no lo liga: `tar.costot` 0,
  `hmores.taride` 0); meter los partes en la vista (el restringido no ve `personal`: la guarda de
  F-141 la revocaría y la noche fallaría); tabla en vez de vista (necesitaría `compras` de la
  misma noche y la reanudación de F-148).
- D5 incremental (sin `tiemod` en tablas de propiedades; < 1 min de cómputo ligero por noche,
  no mueve los créditos del B1ms/B2s). D7 partir en dos. D8 sin `log` (658 `SIN_HISTORIAL`
  que crecen; `dbo.log` entero es F-105). D10 texto íntegro en el general o sin texto.

## 10. Fichas del diccionario

`postventa.yaml`: `para_que_sirve` (≤ 350 caracteres) y los objetos (`unidades`,
`oficios_obra`, `incidencias`, `incidencia_intervinientes`, `tareas`, `incidencia_procesos`,
`v_estado_incidencias`, `documento_adjuntos`, `partida_obra_origen`, `v_coste_obra`, funciones),
relaciones, trampas (R33), coste (los partes en `personal`, cómo cruzarlos; obras `0004` sin
partidas) y `ejemplos_preguntas` (R34; las 2 primeras enrutan). Vigilar `PRESUPUESTO_MAX` (F-147)
y no citar reglas `fuera_mcp` (F-149). `postventa_restringida.yaml`: tres fichas con la
autorización; `R-POSTVENTA-RESTRINGIDA` (bloqueante: por defecto `postventa`; la restringida,
solo perfiles postventa y total; nunca se suman). `R-PERFILES` gana el cuarto perfil.

## 11. Riesgos

- **El dato lo escribe otra aplicación**: si `postventa-incidencias` cambia el texto de su
  `log`, sus cierres caen a `SIN_HISTORIAL` sin error (test del literal, cifra del paso 7).
- **`raw.log` es un recorte** con nombre genérico; F-105 lo ampliará en la misma tabla.
- **Máscara heurística** (D10) y **código de partida como obra**: errata posible (`0561 `),
  la ficha lo dice; `SIN_OBRA` se publica, no se esconde.
- **Un cuarto perfil** multiplica las guardas: va por las funciones de F-141, sin copia.
- **`check-declarados`/`check-diccionario` dan 1** entre el merge y los pasos MANUAL; **el MCP
  no ve nada** hasta el pliego. **F-153 `in_progress`**: no se implementa hasta su cierre.

## 12. Pasos MANUAL (tras APROBADO y merge a `main`; los lanza el humano)

Fuera de 00:00-05:00 UTC, desde la raíz. `<PY>` = `.venv/Scripts/python.exe`; `<Q>` = `<PY> -c
"import main, sys; pg = main._get_pg(); pg._bootstrap_done = True;
print(pg.filas_solo_lectura(sys.argv[1], 60))" "<consulta>"`; `$dsn`, la del administrador
(cabecera de `02_roles.sql`). Vuelta atrás del código: el SHA de `main` del paso 0 (hoy `9dcd0aa`).

0. Tag actual: `az containerapp job show -n caj-datamart-seg-dev -g rg-datamart-seg-dev
   --query "properties.template.containers[0].image" -o tsv` y `git rev-parse main` (anotar
   los dos; el SHA era `9dcd0aa` el 2026-11-05: si `main` se movió, vale el nuevo). Compras:
   `<Q> "SELECT count(*) FROM raw.rcg r JOIN raw.con c ON c.ide = r.con AND c.tip IN (12, 14, 15, 44, 46)"`.
1. `powershell -NoProfile -File infra/70_build_image.ps1` y `powershell -NoProfile -File
   infra/85_update_job.ps1 -Tag <tag nuevo>`; el `az` del paso 0 acaba en él.
2. Contraseña en `kv-mcp-bbdd-dev/pg-password-postventa`, exportada a `POSTVENTA_PWD`; `psql -X
   -v ON_ERROR_STOP=1 -f infra/sql/02_roles.sql $dsn` → «mcp_sigrid_dm_postventa: contraseña fijada».
3. `<PY> main.py ingest --table <t> --full` para `upv`, `rcp`, `rcpint`, `tar`, `tarres`,
   `obrofc`, `auxrcp`, `auxtrcp`, `auxofc`, `prmtpl`, `auxgra`, `log`, `per`; después `rcg` y
   `gra`, en ese orden. `<PY> main.py check-raw-recuentos` → sin filas de menos; el recuento de
   compras del paso 0, igual.
4. `<PY> main.py build-postventa` → SUCCESS (anotar duración) y `<PY> main.py apply-grants` →
   `verificacion`, `verificacion_total`, `verificacion_restringido`, `verificacion_postventa` ok.
5. Cifras con `<Q>`: `postventa.incidencias` ~22.180, `unidades` 1.328, `tareas` ~13.770;
   `SELECT familia, count(*) FROM postventa.documento_adjuntos GROUP BY 1` → INCIDENCIA ~10.030,
   REPARACION ~4.430, UNIDAD ~830, TAREA ~700.
6. `<Q> "SELECT liga, round(sum(importe)) FROM postventa.v_coste_obra GROUP BY 1"` → R27.
7. `<Q> "SELECT origen_fecha, count(*), count(en_estado_desde), count(cambiado_por) FROM
   postventa.v_estado_incidencias GROUP BY 1"` → R17; cronometrar (≤ ~1 s; el MCP corta a 30 s).
8. `<PY> main.py publicar-diccionario` (versión nueva); `check-diccionario` (antes da 1, lo
   esperado), `check-declarados` y `check-unicidad --timeout 300` → OK.
9. Enviar `pliego_mcp_bbdd.md` a `mcp-bbdd`; desplegado allí, `az containerapp revision restart -g
   rg-mcp-bbdd-dev -n ca-mcp-bbdd-dev --revision <latestReadyRevisionName> -o none` y pruebas por perfil.
10. Primera nocturna: `<PY> main.py timings` (ingesta nueva y `build_postventa`).

**Vuelta atrás** (en este orden):

1. `powershell -NoProfile -File infra/85_update_job.ps1 -Tag <tag del paso 0>`, comprobado con el `az` del paso 0.
2. `git switch --detach <SHA de main del paso 0>` (hoy `9dcd0aa`).
3. `psql -X -v ON_ERROR_STOP=1 -c "SET ROLE sigrid_dm_etl; DROP SCHEMA IF EXISTS
   postventa_restringida CASCADE; DROP SCHEMA IF EXISTS postventa CASCADE; DROP TABLE IF EXISTS
   raw.upv, raw.rcp, raw.rcpint, raw.tar, raw.tarres, raw.obrofc, raw.auxrcp, raw.auxtrcp,
   raw.auxofc, raw.prmtpl, raw.auxgra, raw.log, raw.per;" $dsn` y, como administrador (no es
   superusuario: sin el GRANT, «permission denied to drop objects», probado en PG16), `psql -X -v
   ON_ERROR_STOP=1 -c "DROP ROLE IF EXISTS mcp_sigrid_dm_postventa; GRANT sigrid_dm_perfil_postventa_ro
   TO CURRENT_USER WITH INHERIT TRUE; DROP OWNED BY sigrid_dm_perfil_postventa_ro; DROP ROLE IF
   EXISTS sigrid_dm_perfil_postventa_ro;" $dsn`.
4. `<PY> main.py ingest --table rcg --full` y `--table gra --full` (el `where` viejo).
5. `<PY> main.py publicar-diccionario` (fichas del árbol local) y `<PY> main.py apply-grants`;
   `check-declarados` → OK. Borrar el secreto `pg-password-postventa` si ya no se usará.
6. `git switch main`; si `mcp-bbdd` ya tenía el pliego, su propia vuelta atrás allí.

## 13. Tests de humo (sin red ni BBDD)

- `test_f156_dominio.py`: ramas y orden de `origen_fecha`, `fin_garantia`, `familia_adjunto`,
  `enmascarar`, `obra_de_partida` (los casos de § 5) y `liga_coste`.
- `test_f156_ingesta_sql.py`, sobre el TEXTO del YAML y del SQL: R1-R4, R7-R16, R19-R21,
  R25-R26; literales del dominio en el SQL; `fn_fecha`/`extension`/`clase_fichero` iguales a
  los de compras; compras con sus cinco tipos; R11/R24 por nombres de columna; sin `personal.`
  en `08`.
- `test_f156_grants.py`: R28-R31 (listas de `settings`, `.env.example`, `02_roles.sql`;
  `perfil_postventa_en_conflicto` y el bloque de `apply_grants` con dobles, sin BBDD).
- `test_f156_pipeline.py`: R32. `test_f156_diccionario.py`: R22-R23, R33-R34; `valores` contra
  el dominio.
