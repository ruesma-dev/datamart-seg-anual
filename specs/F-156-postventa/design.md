# F-156 · Diseño: postventa entera

Mediciones: `progress/spec_F-156.md`. Requisitos y decisiones: `requirements.md`. Lo marcado
**[D1=A]** solo se implementa si el humano autoriza los datos personales (D1).

## 1. Encaje y límite del servicio

- **Ingesta** por la vía de siempre (`ingest_raw` + `tables_sigrid.yaml`, `--full` cada noche):
  12 tablas nuevas (13 con [D1=A]) y el `where` de `rcg`/`gra` ampliado. `stream_table` compone
  `WHERE [ide] > ? AND (<where>)` y `check-raw-recuentos` cuenta con el mismo `where`.
- **Negocio**: esquema módulo nuevo `postventa` (+ `postventa_restringida` [D1=A]) con su paso
  `build_postventa`, que SOLO lee `raw`: no depende de `stg`, `mart`, `maestro` ni `compras`
  (estados y fechas con SQL propio). Patrón de `personal`/`contabilidad`: falla solo.
- **Límite**: el ETL LEE (solo lecturas de Sigrid). Es postventa de las obras de la empresa,
  dato de seguimiento y explotación, y cabe aquí. Lo que NO es de aquí: la aplicación
  `postventa-incidencias` (escribe en Sigrid y tiene su base `postventa`; su F-048 trae SU
  base al datamart y es otra frontera: PostgreSQL no cruza bases), y la herramienta del MCP
  (`mcp-bbdd`, § 11). No se propone microservicio nuevo.

## 2. Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/postventa.py` | constantes y oráculos (§ 5) |
| `etl_sigrid/application/steps/build_postventa_step.py` | `BuildPostventaStep` (patrón `build_personal_step.py`: `SUB_PASOS`, `depends_on = ["ingest_raw"]`) |
| `etl_sigrid/infrastructure/postgres/sql/postventa/00_setup.sql` … `07_restringida.sql` | § 6 |
| `config/diccionario/postventa.yaml` · `postventa_restringida.yaml` [D1=A] | fichas (§ 9) |
| `tests/test_f156_dominio.py` · `test_f156_ingesta_sql.py` · `test_f156_grants.py` · `test_f156_pipeline.py` · `test_f156_diccionario.py` | § 13 |

## 3. Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `config/tables_sigrid.yaml` | + 12 (13) tablas al final, bloque `# --- F-156`, cifras en comentario; `where` de `rcg` y `gra` con `707, 708, 47` |
| `main.py` | `BuildPostventaStep` en `_pasos_run_all` tras `BuildContabilidadStep`; `"build_postventa"` en `PASOS_CON_PERMISOS`; comando `build-postventa` (copia de `build-personal`) |
| `config/settings.py`, `.env.example` | `postventa` en `DEFAULT_CONSUMPTION_SCHEMAS` y `DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS`; [D1=A] `postventa_restringida` en `DEFAULT_VETOED_SCHEMAS` y `DEFAULT_RESTRICTED_SCHEMAS`; una línea por lista en sus comentarios |
| `etl_sigrid/domain/diccionario.py` | `ESQUEMAS_DEL_DATAMART` + `postventa` (+ `postventa_restringida`), y su comentario |
| `infra/sql/02_roles.sql` | lo de F-138 § Permisos para `postventa_restringida` [D1=A]; `postventa` en las listas de consumo y del perfil restringido que el fichero comprueba |
| `config/diccionario/raw.yaml` | fichas de las 12 (13) tablas; `rcg`/`gra` con el filtro nuevo; «Son 92 (93) tablas» |
| `config/diccionario/00_global.yaml` | esquemas, `version` +1 (la siguiente libre: hoy v70 en el árbol de F-153), nota, `R-FRESCURA` (ámbito y texto), `R-POSTVENTA-RESTRINGIDA` [D1=A], censo de `raw` |
| `docs/ARCHITECTURE.md`, `CLAUDE.md` (mapa) | capa y párrafo de `postventa`; censo 92 (93); `log` filtrado; «Lo que Sigrid NO guarda» + unidades de venta vacías y sin coste por incidencia |
| tests que fijan el censo 80, las listas de esquemas y los pasos de `run-all` (`grep -rln` de § 13) | 80 -> 92 (93); 16 -> 17 (18) esquemas; 15 -> 16 pasos; nada más |
| `../azure-apps/datamart_seg_anual.md` (commit propio, sin push) | consume 92 (93) tablas; expone `postventa`; pliego D2 (§ 11) |

## 4. Ficheros que NO se tocan

- `sql/compras/14_documento_adjuntos.sql`: su `JOIN raw.con … tip IN (12, 14, 15, 44, 46)`
  ya filtra; con `rcg`/`gra` más anchos sigue dando las mismas filas (test que lo fija).
- `sql/compras/12_documento_procesos.sql` y `13_estado_documentos.sql`: el histórico de
  postventa es suyo y no se mezcla con el de compras.
- `grants.py` y `apply_grants_step.py`: van por listas desde F-135/F-136/F-141; con `settings`
  cambiado conceden, vetan y verifican solos. `OBJETO_ADJUNTOS` sigue siendo el de compras.
- `ingest_raw_step.py`, `sigrid_api_client.py`, `objetos_pendientes.yaml`, `reanudacion.py`
  (`build_postventa` solo lee `raw`: no entra en `LECTURAS_PARA_REANUDAR`).

## 5. Dominio · `etl_sigrid/domain/postventa.py`

`TIPO_UNIDAD = 707`, `TIPO_INCIDENCIA = 708`, `TIPO_TAREA = 47`;
`ESTADOS_ABIERTOS = (1, 3)`, `ESTADOS_RESOLUCION = (5, 7, 9)`, `ESTADO_CERRADA = 9`;
`CLASE_FIN_GARANTIA = {"0001": "fecfin1", "0002": "fecfin2"}`; `GRATIPIDE_REPARACION = 35`;
`FAMILIAS_ADJUNTOS = ("INCIDENCIA", "REPARACION", "UNIDAD", "TAREA")`;
`ORIGENES_FECHA = ("PASO", "CIERRE_APLICACION", "ALTA", "SIN_HISTORIAL")`;
`TEXTO_CIERRE_APLICACION = "Cerrar parte (postventa-incidencias)"`;
`COLUMNAS_PER = ("ide", "nom", "tel", "tel2", "ele")`; `COLUMNAS_PER_PROHIBIDAS`.
Funciones puras: `fin_garantia(clase, fechas) -> date | None`, `dentro_garantia(alta, fin)`,
`familia_adjunto(tip, gratipide) -> str`, `origen_fecha(estado, destino_ultimo_paso,
momento_ultimo_paso, momento_cierre_aplicacion) -> str` (orden de R15),
`enmascarar(texto) -> str` (R13).

## 6. SQL · `sql/postventa/` (todo `DROP … CASCADE` + `CREATE`, como `compras`)

- **`00_setup.sql`**: `CREATE SCHEMA IF NOT EXISTS postventa` (y `postventa_restringida`
  [D1=A]); `postventa.fn_fecha(int)` (AAAAMMDD, 0 -> NULL; copia de `compras.fn_sigrid_date`
  atada por test de texto), `postventa.fn_momento(fec, hor)` (regla de hora de
  `12_documento_procesos.sql`), `postventa.fn_enmascarar(text)` con `regexp_replace`:
  `[6-9]\d{8}` y `[6-9]\d{2} \d{2} \d{2} \d{2}` -> `[TELEFONO]`; `[^\s@]+@[^\s@]+\.[^\s@]+`
  -> `[CORREO]`.
- **`01_unidades.sql`** -> `postventa.unidades` (PK `unidad_id` = `upv.ide`): `raw.upv u JOIN
  raw.con cu ON cu.ide = u.ide` (código `cu.cod`, nombre `cu.res`, estado por `raw.conest`
  (707, `cu.est`), empresa `cu.emp`), obra por `u.obride` -> `raw.con` (código y empresa),
  `LEFT JOIN raw.prmtpl` (código y nombre de tipología), fechas con `fn_fecha`,
  `tiene_propietario = u.cliide > 0`. Sin `restel`, `resele`, `peride`, `cliide`.
  **`postventa.oficios_obra`**: `raw.obrofc` + `raw.auxofc` + `raw.prv`/`raw.con` del proveedor.
- **`02_incidencias.sql`**: guarda R12 (`DO`); `postventa.incidencias` (PK `incidencia_id` =
  `rcp.ide`): `raw.rcp r JOIN raw.con c ON c.ide = r.ide AND c.tip = 708` (las 1.502 cabeceras
  sin `rcp` no entran), `JOIN postventa.unidades` (obra y empresa por la unidad),
  `LEFT JOIN raw.auxrcp/auxtrcp/auxofc`, `raw.conext` (`cod = 'RCPCLI'`, `valt`),
  `fn_enmascarar(c.res)` y `fn_enmascarar(r.tex)`, `fin_garantia_clase` y `dentro_garantia`
  (R8). `forma_comunicacion_codigo` = `rcptip`, sin nombre salvo el 1 (`ESCRITA`).
  **`postventa.incidencia_intervinientes`**: `raw.rcpint i JOIN postventa.incidencias`
  (deja fuera los 1.499 huérfanos) + `raw.obrofc`/`auxofc`/proveedor; `causante = cauave <> 0`.
- **`03_tareas.sql`** -> `postventa.tareas` (PK `tarea_id`): `raw.tar t JOIN raw.con ct ON
  ct.ide = t.ide AND ct.tip = 47 JOIN postventa.incidencias ON incidencia_id = t.rcpide`,
  estado por `raw.conest` (47), `LEFT JOIN raw.tarres` (una por tarea, medido) ->
  `oficios_obra`; `empleado_id = NULLIF(t.empide, 0)`; `fn_enmascarar(t.tex)`.
- **`04_procesos.sql`** -> `postventa.incidencia_procesos` (PK `paso_id`): `UNION ALL` de
  `raw.rac r JOIN raw.con c ON c.ide = r.conide AND c.tip IN (707, 708, 47)` (`origen = 'RAC'`,
  `proceso = r.res`, `paso_id = 'RAC-' || r.ide`) y `raw.log l JOIN raw.con c ON c.tip =
  l.tip AND c.cod = l.cod AND c.emp = l.emp` (`origen = 'CIERRE_APLICACION'`,
  `estado_origen` NULL, destino 9, `paso_id = 'LOG-' || l.ide`); estados por `raw.conest`
  con la pareja; `usuario` el login; `es_ultimo` por `ROW_NUMBER()` sobre `momento DESC, paso_id DESC`.
- **`05_estado.sql`** -> vista `postventa.v_estado_incidencias` (una fila por incidencia):
  último paso, último cierre de aplicación y primer paso a 5/7/9 por `LATERAL`; `CASE` de R15;
  `en_estado_desde`, `abierta`, `fecha_resolucion`, `dias_hasta_resolucion`, `dias_abierta`
  y `dias_en_estado` con `CURRENT_DATE` (R16). Vista y no tabla: los días no envejecen.
- **`06_adjuntos.sql`**: guarda R21; `postventa.documento_adjuntos` (PK `adjunto_id` =
  `rcg.ide`): `raw.rcg r JOIN raw.con c ON c.ide = r.con AND c.tip IN (707, 708, 47) JOIN
  raw.gra g ON g.ide = r.gra LEFT JOIN raw.auxgra a ON a.ide = g.gratipide`; `familia` por
  el `CASE` de `familia_adjunto`; `incidencia_id`/`unidad_id`/`tarea_id` según el tipo;
  `extension` y `clase_fichero` con las MISMAS expresiones que `compras/14` (test de texto);
  `empresa_repositorio = g.emp` entera. [D1=B] `WHERE familia <> 'REPARACION'`.
- **`07_restringida.sql`** [D1=A]: `postventa_restringida.contactos_incidencia` (incidencia,
  `propietario_id`, `propietario_nombre` = `con.res` del `cliide`, `reclamante_*` y
  `contacto_*` de `raw.per`: nombre, teléfono, teléfono 2, correo),
  `postventa_restringida.contactos_unidad` (unidad, propietario, persona de contacto,
  `restel`, `resele`, `avi_*`, `hor_*`, `texohor`) y `postventa_restringida.textos`
  (`documento_id`, `tipo_documento_codigo`, `descripcion`, `descripcion_larga`, `texto`
  íntegros). Solo lee `raw` y `postventa`.

## 7. Permisos

Patrón F-138: `postventa` es un esquema de consumo más (estándar, Power BI, total por
pertenencia y, D3, perfil restringido: su grupo tiene el privilegio por defecto en REVOKE,
así que tras un build suelto hace falta `apply-grants`). [D1=A] `postventa_restringida`:
vetado al general (lo revoca `apply_grants` y FALLA si lo sigue leyendo) y restringido (lo
lee `sigrid_dm_autorizado_ro`; el total por pertenencia). `02_roles.sql`: `CREATE SCHEMA` con
`SET ROLE sigrid_dm_etl`, los dos `ARRAY` de vetados del 5 ter, `GRANT USAGE` + `SELECT ON
ALL TABLES` + `ALTER DEFAULT PRIVILEGES` al autorizado y las comprobaciones finales.
Guardas de F-141: la de vistas que leen lo no visto no salta (nada de `postventa` lee
`postventa_restringida`); el índice de adjuntos de postventa no cae en
`origenes_de_adjuntos_sin_leer` (es de compras) y su regla por familia se declara (R22).

## 8. Decisiones y alternativas (para la PARADA 1)

- **D1** A/B en `requirements.md`. B pierde «quién reclamó» y «cómo contactar», pero el
  análisis (por obra, unidad, oficio, plazo) queda entero. Descartado: dejarlos en
  `postventa` con `REVOKE` por columna (el total hereda del estándar; F-138 § Permisos).
- **D2** `mcp-bbdd` es otro repositorio (§ 11): no se toca desde aquí.
- **D3** Restringido sí: sus reglas quitan mayor, cartera y personal; postventa no es nada
  de eso. Alternativa: fuera de su lista (se le veta solo).
- **D4** Medido: `tar.costot` = 0, `hmores.taride` = 0, sin contrato ni pedido por tarea.
  Atribuir coste de las obras `POSTV*` a incidencias sería inventarlo. Si se quiere el
  coste de postventa por obra cruzado con incidencias, feature aparte sobre `mart`.
- **D5** Incremental: sin `tiemod` en las tablas de propiedades y la nocturna es `--full`;
  ahorraría segundos a cambio de un mecanismo nuevo (F-097). Créditos de CPU: < 1 min de
  cómputo ligero sobre una noche de horas; no mueve la hucha del B1ms/B2s.
- **D6** Solo lee `raw`: cualquier posición tras `ingest_raw` vale; tras `contabilidad`
  por legibilidad (el último build de `raw` puro) y lejos de `cierre`, que dropea en cascada.
- **D7** Partir (F-156a datos + histórico; F-156b adjuntos + restringida): el tamaño no lo pide.
- **D8** B (sin `log`): los 658 cierres de la aplicación saldrían `SIN_HISTORIAL` y
  crecerían cada semana (la aplicación cierra sin `rac`). Traer `dbo.log` entero (F-105)
  es otra feature: 8,6 M filas con texto libre.
- **D9** Alternativa: todo `INCIDENCIA` y abrible por el estándar: entregaría DNI
  manuscritos a la IA sin autorización.
- **D10** Alternativas: texto íntegro en `postventa` (16 textos con teléfono o correo hoy)
  o sin texto (pierde «qué falla»). La máscara es heurística: lo declara la ficha.

## 9. Fichas del diccionario

`postventa.yaml`: `para_que_sirve` del esquema (≤ 350 caracteres) y 9 objetos —`unidades`,
`oficios_obra`, `incidencias`, `incidencia_intervinientes`, `tareas`, `incidencia_procesos`,
`v_estado_incidencias`, `documento_adjuntos` y las tres funciones—, con relaciones (por
`incidencia_id`, `unidad_id`, `obra_id` + `empresa_id`), las trampas de R29, el coste (R30) y
`ejemplos_preguntas` (R31; las 2 primeras enrutan: «incidencias abiertas por obra y oficio»,
«tiempo medio de resolución»). Vigilar `PRESUPUESTO_MAX` (F-147) y no citar reglas
`fuera_mcp` (F-149). `postventa_restringida.yaml` [D1=A]: tres fichas con la autorización
(quién y fecha) y `R-POSTVENTA-RESTRINGIDA` (bloqueante: por defecto `postventa`; la
restringida solo para el total, nunca se suman). `raw.yaml`: fichas de las tablas nuevas con
qué traen y qué NO (columnas fuera de `per`, `log` reducido a cierres de la aplicación).

## 10. Riesgos

- **El dato lo escribe otra aplicación** (`postventa-incidencias`, cierres y partes): si
  cambia el texto de su `log`, los cierres caen a `SIN_HISTORIAL` sin error. Mitigación:
  test con el literal y ficha que lo dice; cifra de control en el paso MANUAL 7.
- **`raw.log` es un nombre genérico** y F-105 querrá `dbo.log` entero: la ficha dice que es
  un recorte y F-105 lo ampliará en la misma tabla.
- **Máscara incompleta** (D10): formatos raros de teléfono pasan; residual y declarado.
- **`check-declarados` y `check-diccionario` dan 1** entre el merge y los pasos MANUAL.
- **El MCP no ve nada** hasta el pliego D2: nadie debe dar la feature por usable en la IA
  antes; sí en Power BI.
- **F-153 está `in_progress`**: F-156 no se implementa hasta que F-153 cierre.

## 11. Pliego para `mcp-bbdd` (D2; se escribe en `azure-apps/datamart_seg_anual.md`)

P1. `seguridad.esquemas_permitidos` + `postventa` (y `postventa_restringida` [D1=A], al final,
común a los perfiles como las otras `*_restringida`). P2. `adjuntos.indice` pasa a admitir
una LISTA de índices (`compras.documento_adjuntos` y `postventa.documento_adjuntos`, mismas
columnas; `adjunto_id` = `rcg.ide`, único entre los dos), cada uno con sus `origenes` (R22).
P3. Reinicio tras publicar el diccionario. Lo implementa y prueba `mcp-bbdd` en su propia
feature; aquí solo queda el contrato. Lo pide el humano en ese repositorio.

## 12. Pasos MANUAL (tras APROBADO y merge a `main`; los lanza el humano)

Fuera de 00:00-05:00 UTC, desde la raíz. `<PY>` = `.venv/Scripts/python.exe`; `<Q>` = `<PY> -c
"import main, sys; pg = main._get_pg(); pg._bootstrap_done = True;
print(pg.filas_solo_lectura(sys.argv[1], 60))" "<consulta>"`; `$dsn`, la del administrador
(cabecera de `02_roles.sql`). Vuelta atrás del código: la punta de `main` previa al merge.

0. Tag actual: `az containerapp job show -n caj-datamart-seg-dev -g rg-datamart-seg-dev
   --query "properties.template.containers[0].image" -o tsv` (anotarlo).
1. `powershell -NoProfile -File infra/70_build_image.ps1` (tag nuevo) y `powershell
   -NoProfile -File infra/85_update_job.ps1 -Tag <tag nuevo>`; el `az` del paso 0 acaba en él.
2. [D1=A] `psql -X -v ON_ERROR_STOP=1 -f infra/sql/02_roles.sql $dsn` ANTES del build.
3. Ingesta: `<PY> main.py ingest --table <t> --full` para `upv`, `rcp`, `rcpint`, `tar`,
   `tarres`, `obrofc`, `auxrcp`, `auxtrcp`, `auxofc`, `prmtpl`, `auxgra`, `log` ([D1=A] `per`),
   y después `rcg` y `gra` (en ese orden). `<PY> main.py check-raw-recuentos` → sin filas de menos.
4. `<PY> main.py build-postventa` → SUCCESS (anotar duración) y `<PY> main.py apply-grants`
   → `verificacion`, `verificacion_total`, `verificacion_restringido` ok.
5. Compras intacto (R4), antes del paso 3 y después: `<Q> "SELECT count(*) FROM raw.rcg r JOIN
   raw.con c ON c.ide = r.con AND c.tip IN (12, 14, 15, 44, 46)"` → la misma cifra (~201.000).
6. Cifras con `<Q>` (cambian poco cada noche): `SELECT count(*) FROM postventa.incidencias`
   → ~22.180; `postventa.unidades` → 1.328; `postventa.tareas` → ~13.770; `SELECT familia,
   count(*) FROM postventa.documento_adjuntos GROUP BY 1` → INCIDENCIA ~10.030, REPARACION
   ~4.430 ([D1=B] 0), UNIDAD ~830, TAREA ~700.
7. `<Q> "SELECT origen_fecha, count(*), count(en_estado_desde) FROM
   postventa.v_estado_incidencias GROUP BY 1"` → R17; cronometrar (≤ ~1 s, ventana del MCP 30 s).
8. `<PY> main.py publicar-diccionario` (versión nueva); `check-diccionario` (antes de este
   paso da 1, lo esperado), `check-declarados` y `check-unicidad --timeout 300` → OK.
9. Pedir en `mcp-bbdd` el pliego § 11 y, desplegado, reiniciar el MCP: `az containerapp show
   -g rg-mcp-bbdd-dev -n ca-mcp-bbdd-dev --query properties.latestReadyRevisionName -o tsv` y
   `az containerapp revision restart -g rg-mcp-bbdd-dev -n ca-mcp-bbdd-dev --revision
   <revision> -o none`; las tres preguntas de R31 por el MCP; anotarlo en `progress/impl_F-156.md`.
10. Primera nocturna: `<PY> main.py timings` (ingesta nueva y `build_postventa`).

**Vuelta atrás** (en este orden):

1. `powershell -NoProfile -File infra/85_update_job.ps1 -Tag <tag del paso 0>`, comprobado con el `az` del paso 0.
2. `git switch --detach <punta de main previa al merge>`.
3. `psql -X -v ON_ERROR_STOP=1 -c "SET ROLE sigrid_dm_etl; DROP SCHEMA IF EXISTS
   postventa_restringida CASCADE; DROP SCHEMA IF EXISTS postventa CASCADE; DROP TABLE IF
   EXISTS raw.upv, raw.rcp, raw.rcpint, raw.tar, raw.tarres, raw.obrofc, raw.auxrcp,
   raw.auxtrcp, raw.auxofc, raw.prmtpl, raw.auxgra, raw.log, raw.per;" $dsn`.
4. `<PY> main.py ingest --table rcg --full` y `--table gra --full` (el `where` viejo).
5. `<PY> main.py publicar-diccionario` → la versión anterior (fichas del árbol local) y
   `<PY> main.py apply-grants`; `check-declarados` → OK.
6. `git switch main`; si `mcp-bbdd` ya tenía el pliego, revertirlo allí (su propia vuelta atrás).

## 13. Tests de humo (sin red ni BBDD)

- `test_f156_dominio.py`: cada rama de `origen_fecha` y su orden, `fin_garantia` por clase,
  `familia_adjunto`, `enmascarar` (teléfonos seguidos y en grupos, correos, texto limpio).
- `test_f156_ingesta_sql.py`, sobre el TEXTO del YAML y del SQL: R1-R4, R7-R12, R14-R15,
  R19-R21; literales del dominio en el SQL; `fn_fecha`/`extension`/`clase_fichero` iguales a
  los de compras; compras sigue con cinco tipos; R11/R24 por nombres de columna.
- `test_f156_grants.py`: R25-R26 (listas de `settings`, `.env.example`, `02_roles.sql`).
- `test_f156_pipeline.py`: R27-R28 (posición, `depends_on`, nadie depende, `PASOS_CON_PERMISOS`).
- `test_f156_diccionario.py`: R22, R29-R31; ficha por objeto declarado; `valores` contra el dominio.
- Al día: `grep -rln -E "\b80\b|ESQUEMAS_DEL_DATAMART|PASOS_CON_PERMISOS" tests` (censo,
  esquemas y pasos), sin borrar lo que defienden.
