<!-- specs/F-006-mcp-azure/tasks.md -->
# F-006 · El diccionario semántico del datamart — Tareas

Rama: `feature/F-006-mcp-azure`. Un commit por tarea (`F-006 Tn: ...`).
Rigor `critico`: fase RED con evidencia en `progress/impl_F-006.md`, cobertura
de las líneas cambiadas, campaña de mutación sin supervivientes injustificados,
y toda verificación `MANUAL (humano)` con su comando exacto y su resultado real.

## Reglas de hierro de esta feature

1. **Ningún agente abre conexión a la BBDD ni a Azure.** `.env` del puesto
   apunta a `psql-albaranes-rs9k2`, el servidor compartido con `albaranes` y
   `partes` **en producción**. Todo lo que exija BBDD real es `MANUAL (humano)`.
2. **🔏 FIRMA DEL HUMANO.** Las tareas marcadas con 🔏 tocan **permisos sobre el
   servidor compartido** o **crean reglas de firewall en recursos de otro
   proyecto**. No se ejecutan sin autorización explícita del humano, para esa
   acción concreta. Escribir el código que las prepara sí puede hacerse antes;
   **ejecutarlo, no**.
3. **No se arregla ninguna vista.** Escribir las fichas obliga a leer las 33
   vistas y va a destapar errores. Se anotan en `progress/impl_F-006.md` y se
   proponen como features nuevas. Arreglarlos aquí convierte una feature de
   metadato en un cambio del modelo (`design.md` §7).
4. **El trinquete solo baja.** `PENDIENTES_MAX` es una constante de
   `tests/test_f006_cobertura.py`. Cada bloque de fichas la reduce; ninguna
   tarea la sube. Al cerrar la feature vale **0**.

## Orden de los bloques y por qué

El diccionario va primero (bloques A–D), como pidió el humano. La publicación
(bloque E) se coloca justo después de `mart` y `cierre` —y no al final— para
que **el contrato con `mcp-bbdd` se ejercite pronto con contenido real**: es la
pieza que este repositorio le garantiza a otro y descubrir tarde que no encaja
sería caro. A partir de ahí, F y G son contenido puro y se pueden entregar y
revisar por separado.

---

## Fase 0 · Decisiones del humano (antes de escribir nada)

- [x] **T1**: Cerrar DA-1 a DA-6 de `requirements.md` §10 y anotar cada una con
      «CERRADA <fecha>: opción X» en ese mismo apartado. Si alguna se cierra
      distinto de la recomendación, el spec-author enmienda `design.md` **antes**
      de que empiece el bloque A.
      | Verificación: MANUAL (humano) — las seis DA tienen su línea de cierre.
- [x] **T2**: Añadir `"rigor": "critico"` a la ficha de F-006 en
      `harness/features.json` (hoy funciona por omisión).
      | Verificación: `bash harness/init.sh` en verde y `BACKLOG.md` regenerado
      mostrando el rigor.

---

## Bloque A · Andamiaje: formato, validador y puerta (sin contenido)

Entregable: se puede validar un diccionario y medir su cobertura, aunque el
diccionario esté casi vacío. **Aquí se fija el contrato del YAML.**

- [x] **T3**: `etl_sigrid/domain/diccionario.py` — entidades (`Columna`,
      `Relacion`, `Ficha`, `Regla`, `Diccionario`, `ErrorValidacion`) y
      `validar()` cubriendo R2–R7. Tests ANTES, con fase RED documentada.
      | Verificación: `pytest tests/test_f006_formato.py` en verde.
- [x] **T4**: `derivar_avisos()` (R12) y las validaciones de reglas R9 y R11 en
      el mismo módulo de dominio.
      | Verificación: `pytest tests/test_f006_reglas.py` en verde.
- [x] **T5**: Validaciones de frescura R13 y R14, con `pasos_nocturnos`
      inyectado. El test debe leer `main.build_pipeline_steps` **real**, no una
      lista copiada: si mañana `build-cierre` entra en el pipeline nocturno, el
      test tiene que cambiar de veredicto solo.
      | Verificación: `pytest tests/test_f006_frescura.py` en verde.
- [x] **T6**: `etl_sigrid/domain/inventario.py` — `objetos_de_sql`,
      `objetos_de_raw`, `evaluar_cobertura`, `formatear_cobertura` (R24–R27,
      R29). El docstring declara la heurística.
      | Verificación: `pytest tests/test_f006_cobertura.py -k dominio` en verde.
- [x] **T7**: `etl_sigrid/infrastructure/diccionario/cargador_yaml.py`
      (R1, R6, R8, y el `hash_fuente` de R22).
      | Verificación: `pytest tests/test_f006_formato.py -k cargador` en verde.
- [x] **T8**: `tests/test_f006_cobertura.py` como **puerta real** sobre el
      repositorio: inventaría `sql/**` + `config/tables_sigrid.yaml`, carga el
      diccionario real y falla si algún objeto no está documentado ni declarado
      en `pendientes`. Se crea `config/diccionario/00_global.yaml` mínimo con
      `pendientes` = **todo el inventario** y `PENDIENTES_MAX` = ese número.
      | Verificación: `bash harness/init.sh` en verde (la puerta pasa porque
      todo está declarado pendiente, y el número queda escrito en el test).

---

## Bloque B · Las reglas duras y el bloque global

Entregable: `00_global.yaml` completo. **Es la pieza de más valor por línea de
toda la feature**: son las doce reglas que impiden que un agente devuelva un
número plausible y falso.

- [x] **T9**: Las doce reglas de R9 en `00_global.yaml`, cada una con `codigo`,
      `titulo`, `severidad`, `ambito`, `regla` y `motivo` (con el incidente real
      cuando lo hay). Materia prima:
      `progress/explore_F-006_dominio_completo.md` Parte 0 y Parte 1.
      | Verificación: `pytest tests/test_f006_reglas.py` en verde (las doce
      presentes, ámbitos resolubles, severidades del vocabulario).
- [x] **T10**: Convenciones, ejes, órdenes de magnitud (R10), `ocultar` y las
      nueve entradas de `esquemas` (R4).
      | Verificación: `pytest tests/test_f006_formato.py -k global` en verde.
- [x] **T11**: Las 18 preguntas de la batería (R39) en `preguntas_aceptacion`,
      con `estado` y `bloqueada_por` donde corresponda.
      | Verificación: `pytest tests/test_f006_reglas.py -k bateria` — las 18
      ids de `requirements.md` §9 presentes y los `bloqueada_por` apuntando a
      features que existen en `harness/features.json`.

---

## Bloque C · Fichas de `mart`

Entregable: el esquema que responde más preguntas de la batería.

- [x] **T12**: `config/diccionario/mart.yaml` — las 2 tablas de hecho
      (`fact_seguimiento_mensual`, `fact_seguimiento_categoria`) con todas sus
      columnas. Bajar `PENDIENTES_MAX`.
      | Verificación: `pytest tests/test_f006_cobertura.py` en verde con el
      nuevo tope.
- [x] **T13**: Las 11 vistas de `mart` (no 9: el inventario real las cuenta) (`v_pbi_*`, `v_master_*`,
      `v_fact_periodificado`, `v_pbi_cp_tipologia`). `PENDIENTES_MAX` baja.
      | Verificación: ídem. Las preguntas P6, P8, P11 y P18 tienen ya sus
      `objetos_esperados` documentados.

## Bloque D · Fichas de `cierre`

- [x] **T14**: `config/diccionario/cierre.yaml` — `fact_cierre_mensual`, las 8
      vistas (no 6: el inventario real las cuenta) y las 3 funciones. **Todas con `refresco: manual`** (R14): `cierre`
      no está en el pipeline nocturno. `PENDIENTES_MAX` baja.
      | Verificación: `pytest tests/test_f006_frescura.py` +
      `test_f006_cobertura.py` en verde.

---

## Bloque E · Publicación en `_meta` (el contrato con `mcp-bbdd`)

Entregable: `_meta.diccionario` publicada y consultable. No toca permisos.

- [x] **T15**: `etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql`
      con el DDL exacto de `design.md` §4 (tres tablas + `_meta.v_diccionario`),
      idempotente, con el comentario de cabecera sobre `DROP VIEW` y
      `apply-grants` (R23).
      | Verificación: `pytest tests/test_f006_publicacion.py -k ddl` — el
      fichero existe, no contiene ningún `DROP TABLE` ni `DROP VIEW`, y los dos
      JOIN de la vista son `LEFT`.
- [x] **T16**: `etl_sigrid/infrastructure/postgres/diccionario_sql.py`
      (constructores puros) y los métodos `publicar_diccionario` y
      `list_objetos_catalogo` de `PostgresClient` (R17, R18, R22).
      | Verificación: `pytest tests/test_f006_publicacion.py` con doble de
      cliente — el reemplazo va en **una sola transacción** y no hay `DROP`.
- [x] **T17**: `PublicarDiccionarioStep` (R19, R21) y su inserción en
      `build_pipeline_steps` **entre `BuildMartStep` y `ApplyGrantsStep`** (R20).
      | Verificación: `pytest tests/test_f006_publicacion.py -k pipeline` — el
      orden es el exigido y un diccionario inválido devuelve `FAILED` **sin
      llamar a ningún método de escritura** del cliente.
- [x] **T18**: Comando `python main.py publicar-diccionario`, por los helpers
      `_arrancar_ejecucion` / `_ejecutar_paso` de F-024.
      | Verificación: `pytest tests/test_f006_publicacion.py -k cli` con
      `CliRunner` y dobles de `main.get_settings` y `main._get_pg`.
- [ ] **T19**: Publicar contra la BBDD real y comprobar el contrato.
      | Verificación: MANUAL (humano) —
      `python main.py publicar-diccionario`, y después, con `psql`:
      `SELECT esquema, objeto, refresco, avisos FROM _meta.diccionario ORDER BY 1,2;`
      `SELECT * FROM _meta.diccionario_publicacion;`
      `SELECT objeto, ultimo_ok_finished_at FROM _meta.v_diccionario WHERE esquema='cierre';`
      Salida real pegada en `progress/impl_F-006.md`.

---

## Bloque F · Fichas del resto de esquemas de consumo

- [x] **T20**: `config/diccionario/compras.yaml` — 7 tablas, 4 vistas, 3
      funciones. Reglas obligadas en el ámbito: `R-ABONO-NEGATIVO`,
      `R-LINEA-ID-NO-UNICA`, `R-COMPRAS-SIN-IVA`, `R-COMPRAS-TIPO-DOC`.
      `PENDIENTES_MAX` baja.
      | Verificación: `pytest tests/test_f006_cobertura.py` en verde; P1, P5,
      P12, P14 y P16 con sus objetos documentados.
- [x] **T21**: `config/diccionario/retenciones.yaml` — 2 tablas y 7 vistas, con
      `R-RETENCION-NO-JOIN-LINEAS` en el ámbito y la nota de que
      `v_src_lineas_venta` está **siempre vacía** por diseño (`dvfpro` no se
      ingiere). `PENDIENTES_MAX` baja.
      | Verificación: ídem; P2 y P13 documentadas.
- [x] **T22**: `config/diccionario/maestro.yaml` — 3 vistas y 1 función.
      **Terreno virgen: el prototipo no lo cubre en absoluto.** Con la trampa de
      `importe_contratado` (con IVA) y la de `raw.obrprv`, vacía en Ruesma.
      `PENDIENTES_MAX` baja.
      | Verificación: ídem; P9 documentada.

## Bloque G · Fichas de las capas internas y de origen

- [x] **T23**: `config/diccionario/stg.yaml` — 7 tablas, 1 vista, 3 funciones.
      `consumo_recomendado: false` con `motivo_no_consumo` (R3) apuntando a
      `R-VERSION-MASTER`: consultar `stg.plan_mensual` sin filtrar versión
      multiplica los importes. `PENDIENTES_MAX` baja.
      | Verificación: `pytest tests/test_f006_cobertura.py` en verde; P10
      documentada.
- [x] **T24**: `config/diccionario/aux.yaml` (1 objeto, hoy vacío por diseño) y
      `config/diccionario/_meta.yaml` (6 objetos, `refresco: operacion`/
      `estatico` donde corresponda). `PENDIENTES_MAX` baja.
      | Verificación: ídem; **P15 documentada**, que es la prueba de R15 y R16.
- [x] **T25**: `config/diccionario/raw.yaml` — 31 fichas **a nivel de objeto**
      (DA-2), todas `consumo_recomendado: false` con `motivo_no_consumo`
      apuntando a `azure-apps/sigrid_tablas.md`. Incluye la regla de oro de
      Sigrid (`ide` universal, `cod`/`res`/`fec` viven en `con`, `con.nom` no
      existe). **`PENDIENTES_MAX` = 0.**
      | Verificación: `pytest tests/test_f006_cobertura.py` en verde con
      `pendientes` **vacía** (R27).

---

## Bloque H · La puerta absoluta y el chequeo contra la base real

- [ ] **T26**: Comando `python main.py check-diccionario` (R28): compara contra
      `information_schema`, lista objetos sin ficha y fichas huérfanas, sale con
      código 1 si hay discrepancias.
      | Verificación: `pytest tests/test_f006_cobertura.py -k check_cli` con
      doble de cliente.
      |
      | **AMPLIACIÓN decidida el 2026-08-20 (cuarta review): la comprobación de
      UNICIDAD de la clave de negocio va aquí.** La puerta offline solo puede
      comprobar la mitad derivable —que la clave no nombre columnas fuera del
      `GROUP BY`—; la otra mitad, «la clave es demasiado corta», exige saber si
      una columna depende funcionalmente de otra y eso no está en el texto.
      Contra la base real se resuelve entero y barato, con una consulta por
      objeto que tenga `clave_negocio` no vacía:
      |
      | ```sql
      | SELECT count(*) FROM (
      |     SELECT <clave_negocio> FROM <esquema>.<objeto>
      |     GROUP BY <clave_negocio> HAVING count(*) > 1
      | ) AS duplicadas;
      | ```
      |
      | Si devuelve algo distinto de 0, la clave declarada **no identifica una
      | fila** y la ficha miente. Se prefiere esta forma a
      | `count(*) - count(DISTINCT (...))` porque agrupa los NULOS como un valor
      | más, que es como se comportan en un JOIN, y porque devuelve CUÁNTAS
      | claves están duplicadas, que es lo accionable. Es una agregación por
      | objeto sobre tablas ya construidas: unas decenas de consultas baratas.
      | Ojo con `raw` y con las fichas de clave vacía: se saltan, no tienen clave
      | que comprobar.
- [ ] **T27**: Ejecutar el chequeo contra la base real y cerrar las
      discrepancias que aparezcan (la puerta offline es heurística: R29).
      | Verificación: MANUAL (humano) — `python main.py check-diccionario`
      termina con código 0. Salida real en `progress/impl_F-006.md`.
- [ ] **T28**: Regla nueva en `docs/CONVENTIONS.md`: quien añade o cambia un
      objeto publicado actualiza su ficha en el mismo trabajo.
      | Verificación: `pytest tests/test_f006_docs.py -k convenciones`.

---

## Bloque I · 🔏 El rol de lectura y los `REVOKE`

**Todo este bloque toca permisos sobre el servidor compartido.** El código se
escribe libremente; la ejecución contra Azure necesita firma.

- [ ] **T29**: `build_readonly_grant_statements(..., revocar_en=())` (R31) y el
      cálculo de la lista en `apply_readonly_grants` con `ESQUEMAS_SISTEMA`
      (R33). Función pura, probada sin BBDD, incluido el **orden** de las tres
      sentencias de revocación.
      | Verificación: `pytest tests/test_f006_grants.py` en verde; en particular
      que `public`, `pg_catalog`, `information_schema` y `pg_toast` **nunca**
      aparecen en un `REVOKE`.
- [ ] **T30**: `PG_REVOKE_FUERA_DE_CONSUMO` en `config/settings.py` con default
      `False` (R32) y su paso desde `ApplyGrantsStep`.
      | Verificación: `pytest tests/test_f006_grants.py -k apagado` — con el
      default, la lista de sentencias no contiene ni un `REVOKE`.
- [ ] **T31**: `DEFAULT_CONSUMPTION_SCHEMAS` pasa a los siete de consumo (R30)
      y `infra/sql/02_roles.sql` deja de conceder `raw` y `stg`, con el
      comentario actualizado.
      | Verificación: `pytest tests/test_f006_grants.py -k consumo` +
      `pytest tests/test_f005_grants.py` (no regresión).
- [ ] **T32** 🔏: **Verificar que Power BI no lee de `stg` ni de `raw`** (R34).
      Hoy `mcp_sigrid_dm_ro` es el único rol de lectura y lo usan los dos
      consumidores.
      | Verificación: MANUAL (humano) — revisar los orígenes de los informes
      publicados y, contra la base:
      `SELECT usename, application_name, query FROM pg_stat_activity WHERE usename='mcp_sigrid_dm_ro';`
      durante un refresco. Veredicto escrito en `progress/impl_F-006.md`.
- [ ] **T33** 🔏: (solo si T32 sale limpia; si no, DA-3 = B y se entrega a
      F-034) Activar `PG_REVOKE_FUERA_DE_CONSUMO=true` y ejecutar
      `python main.py apply-grants`.
      | Verificación: MANUAL (humano) — antes y después:
      `SELECT nspname, has_schema_privilege('mcp_sigrid_dm_ro', nspname, 'USAGE') FROM pg_namespace WHERE nspname IN ('raw','stg','mart','cierre','compras','maestro','retenciones','aux','_meta');`
      Debe pasar de `t` a `f` en `raw` y `stg`, y seguir en `t` en los siete
      restantes. **Rollback**: `PG_REVOKE_FUERA_DE_CONSUMO=false`, restaurar la
      lista antigua en `PG_CONSUMPTION_SCHEMAS` y `apply-grants`.
- [ ] **T34** 🔏: Comprobar que **Power BI sigue refrescando** y que el MCP
      sigue leyendo, después de T33.
      | Verificación: MANUAL (humano) — un refresco completo de los informes y
      una consulta del MCP a `mart` y a `_meta.v_diccionario`. Resultado real
      anotado.

---

## Bloque J · 🔏 Conectividad y documentación del ecosistema

- [ ] **T35**: `docs/runbook_postgres_azure.md` — procedimiento del firewall
      para el entorno del MCP (R35–R37): IP de salida estática, entorno **sin
      VNet**, que no sirve perseguir la IP del puesto (D11) y que no se debe
      depender de la regla que autoriza a cualquier recurso de Azure. Enlaza los
      nombres de parámetro de `infra/README.md:153-170`, no los copia.
      | Verificación: `pytest tests/test_f006_docs.py -k firewall`.
- [ ] **T36**: `docs/ARCHITECTURE.md` — sección «El datamart se explica solo
      (F-006)».
      | Verificación: `pytest tests/test_f006_docs.py -k arquitectura`.
- [ ] **T37**: `azure-apps/datamart_seg_anual.md` (repositorio `azure-apps`) —
      R38: `_meta.v_diccionario` y las tres tablas como superficie expuesta, el
      rol estrechado, y corregir que el MCP ya no es «un cliente de escritorio».
      **En este mismo trabajo**, como manda `CLAUDE.md`.
      | Verificación: MANUAL (humano) — commit local en `azure-apps` con el
      documento actualizado.
- [ ] **T38** 🔏: (cuando el MCP tenga entorno desplegado, y **solo entonces**)
      Crear la regla de firewall para su IP de salida. Es una escritura sobre un
      recurso de otro proyecto (`rg-albaranes-dev`).
      | Verificación: MANUAL (humano) —
      `az containerapp env show ... --query properties.staticIp -o tsv` y
      `az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table`
      mostrando la regla nueva. **Si el entorno del MCP no existe todavía, esta
      tarea se entrega a `mcp-bbdd` y se anota como tal: no bloquea el cierre de
      F-006.**

---

## Bloque K · La batería de aceptación (criterio de éxito)

- [ ] **T39**: Ejecutar las 18 preguntas de `requirements.md` §9 contra el
      diccionario publicado (DA-4: con el prototipo `mcp-bbdd` local apuntado a
      Azure) y anotar, pregunta a pregunta, qué objetos usó la respuesta y qué
      advertencias citó.
      | Verificación: MANUAL (humano) — tabla de resultados en
      `progress/impl_F-006.md`. **Criterio de cierre (R41): las 13
      respondibles, bien; las 5 bloqueadas, contestadas con un «no puedo, y
      este es el motivo» correcto.** Atención especial a las cuatro preguntas
      trampa (P9, P10, P11, P16): si el agente cae en alguna, **la ficha
      correspondiente está mal escrita** y se corrige antes de cerrar.
- [ ] **T40**: Corregir las fichas que la batería haya delatado y republicar.
      | Verificación: `pytest tests/test_f006_cobertura.py` en verde +
      `python main.py publicar-diccionario` (MANUAL, humano).

---

## Cierre

- [ ] **T41**: Campaña de mutación del rigor `critico`.
      | Verificación: `python -m harness.mutacion --feature F-006`, cero
      supervivientes sin justificación escrita y aceptada por el humano
      (informe en `progress/mutacion_F-006.md`).
- [ ] **T42**: Ejecutar `bash harness/init.sh` en verde.
      | Verificación: `bash harness/init.sh` con exit code 0.

---

## Resumen de las tareas que necesitan firma 🔏

| Tarea | Qué toca | Riesgo si sale mal |
|---|---|---|
| **T32** | Lectura de `pg_stat_activity` en el servidor compartido | Ninguno: solo lectura. La firma es por el acceso, no por el efecto |
| **T33** | **`REVOKE` sobre `mcp_sigrid_dm_ro`** en `sigrid_dm` | Power BI deja de refrescar **en silencio**. Rollback: una variable de entorno y `apply-grants` |
| **T34** | Refresco real de Power BI | Ninguno: verificación |
| **T38** | **Regla de firewall en `rg-albaranes-dev`**, recurso de otro proyecto | Superficie de red abierta de más. Se crea con nombre del entorno y se revisa en la lista |

Ninguna otra tarea escribe contra producción. T19, T27 y T40 escriben en
`_meta` de `sigrid_dm` —tres tablas propias de esta feature, creadas por ella—
y no tocan datos de negocio ni permisos.

---

## Deuda declarada al aprobar la undécima pasada (T43)

Condición del APROBADO: la deuda va aquí **con dueño y con línea**, no como
«pendiente» genérico. El argumento del reviewer para no seguir puliendo es el
que la ordena: **cerrar seis defectos de matiz en la décima pasada generó tres
nuevos de la misma clase**, así que otra ronda no acerca al objetivo, solo
cambia qué frase está mal. Lo que no está medido es el riesgo grande: que un
agente encuentre la ficha, reciba las trece reglas y responda.

### D1 · Décimo caso de la copia, donde el barrido no llega

**Dónde**: `tests/test_f006_stg_trampas.py:151-163`, docstring de
`test_f006_r26_anio_y_mes_nunca_son_nulos_y_la_ficha_lo_dice`. Conserva el
ejemplo «una fase con `anio = 0` entra igual», que es **el mismo que se corrigió
en la ficha** (defecto 6 de la décima): `make_date` aborta el build.

**Por qué se escapó**: el barrido de frases rechazadas
(`tests/test_f006_copias.py`) mira **solo `config/diccionario/*.yaml`**, crudo y
cargado. Un docstring de test no es superficie publicable, así que queda fuera
por diseño.

**¿Ampliarlo a los docstrings es viable?** Sí técnicamente —es abrir
`tests/*.py` y aplicar el mismo `FRASES_RECHAZADAS`— pero **no conviene**, y por
la misma razón por la que el `motivo` de una regla puede citar la formulación
equivocada: un docstring que explica un error **tiene que nombrarlo**. Barrerlos
produciría falsos positivos en todos los tests que documentan por qué existen,
que son la mayoría de los que se han escrito en estas cuatro pasadas.

**Dueño: revisión humana.** Es prosa explicativa que no llega al agente. Lo
accionable es corregir ese docstring concreto, que sí describe mal el mecanismo.

### D2 · Referencia posicional en una ficha

**Dónde**: `config/diccionario/stg.yaml:598`. Dice que `make_date` está «unas
líneas más abajo» y en `stg/08_plan_mensual.sql` está **nueve líneas arriba** de
la referencia. **Dueño: implementer**, un cambio de dos palabras. Nota de
método: las referencias posicionales a otro fichero envejecen solas; lo robusto
es nombrar la construcción, no dónde está.

### D3 · Un recuento nuevo a mano, y la solución ya se sabe

**Dónde**: `tests/test_f006_fichas.py:615`, mensaje de
`test_f006_r2_control_se_localiza_donde_se_puebla_cada_tabla_de_stg`: dice «al
menos cinco tablas» y son **seis** (`fases`, `obras`, `partidas`,
`plan_mensual`, `presupuesto`, `version_master_vigente`).

**Dueño: implementer.** Y la lección ya está aprendida en esta misma tanda: **no
se corrige el número, se deriva**. El aserto debe comparar contra el conjunto
que el propio localizador calcula, no contra una constante escrita al lado.

### D4 · Tres correcciones sin guarda de regresión

Están bien hoy y **nada impide que vuelvan atrás en verde**:

| Corrección | Por qué no la cubre ningún detector |
|---|---|
| La mitad **CLIENTE** de `entidad_cif` (literal `NULL::VARCHAR(24)`) en sus cuatro fichas | el detector de atribución busca frases de «valor vacío»; volver a la explicación de una sola mitad no las usa |
| La **caracterización por familias** de las columnas excluidas en las 31 fichas de `raw` («6 de direcciones, 2 de observaciones…») | los tests comprueban el **número** y que lo citado esté excluido, no que la caracterización sea cierta |
| `maestro.proveedores_obra.cif` | lleva `NULLIF(TRIM(...))`, así que **los dos** guardianes lo saltan: el de nulos porque el NULL es posible, y el de atribución porque la proyección no es desnuda |

**Dueño: implementer**, si el humano decide otra ronda. No bloquean.

### D5 · La zona que el reviewer declara NO FIABLE

Con estas palabras, porque es lo que hay que leer antes de fiarse del
diccionario:

> **Las afirmaciones sobre el origen que NO se derivan de este repositorio no
> son fiables.** Alcanza al **punto 2 de `R-SIGRID-CON`** —las diez tablas
> «Propiedades de `con`»— y a todo lo que dependa de
> `azure-apps/sigrid_tablas.md`. Esa fuente **ya produjo dos afirmaciones
> falsas** (`cen.res`, que es de `cenrep`; y una lista de excepciones con una
> acertada de siete), y no se deja segmentar de forma fiable.

**Fuera de esa zona, el resto se considera fiable**: las **47 fichas de la
superficie de consumo** están verificadas y con su mecanismo escrito.

**Dueño: humano.** Decidir si el punto 2 se recorta, se marca como no verificado
o se verifica contra la base real en T27, que es la única fuente que lo
zanjaría.

### D6 · Deuda anterior, que sigue viva

| Qué | Dónde | Dueño |
|---|---|---|
| **Multifuente**: el detector de `COALESCE` cuenta **dos alias**, no si resuelven al mismo objeto | `tests/test_f006_fichas.py` | implementer |
| **Menores 5, 6 y 7** de la quinta pasada | `progress/review_F-006.md` | implementer |
| **F-041**: la campaña de mutación no borra `__pycache__` ni limpia worktrees, y cuenta los timeouts aparte de los supervivientes | `harness/mutacion.py`, y a `arnes-base` por la regla de propagación | fuera de F-006 |
| **Comentarios del SQL que mienten**: `06_presupuesto.sql` dice `ROUND(can, decc)` y el código no lo hace | `sql/stg/06_presupuesto.sql` | **F-025**; el guardián de F-011 impide tocarlo desde aquí, con razón |
| `config/tables_sigrid.yaml` dice «catálogo estable, refresco completo» en 13 tablas y no gobierna ninguna recarga | `config/tables_sigrid.yaml` | implementer |

- [ ] **T43**: Registrar esta deuda —hecho— y **decidir con el humano** cuáles de
      D1–D6 entran antes de la batería y cuáles se quedan declaradas.
      | Verificación: esta sección existe con dueño y línea por entrada.
