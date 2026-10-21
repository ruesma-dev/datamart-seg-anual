<!-- progress/impl_F-146.md -->
# F-146 · El perfil restringido no ve NADA de contabilidad · informe del implementer

Rama `feature/F-146-restringido-sin-contabilidad` (desde `main` `66d33a6`). `sdd=false`: el encargo
son la `description` y los `acceptance` de `harness/features.json`. Rigor `estandar`.

## Qué cambió

| Commit | Tarea |
|---|---|
| `843a75b` T1 | `tests/test_f146_restringido_sin_contabilidad.py` (22 tests), en RED |
| `3187d06` T2 | `config/settings.py`, `.env.example`, `infra/sql/02_roles.sql`, comentarios de `grants.py` y `apply_grants_step.py`; tests de F-141 al día |
| `552fd46` T3 | diccionario v58: `00_global.yaml` (`R-PERFIL-RESTRINGIDO`, `R-CONTABILIDAD-RESTRINGIDA`, historia) y `contabilidad.yaml` |
| `0314381` T3b | `tests/test_f128_restringida.py`: un test de F-128 robusto al merge (desviación, abajo) |
| `f2e923b` T4 | `docs/ARCHITECTURE.md` y `docs/runbook_postgres_azure.md` |
| `716e1b4` T2b | `02_roles.sql` sin la palabra «nueve» (la prohíbe el test R25 de F-057; la cazó el `init.sh` final) |
| `b583c7d` T5 | este informe y la entrada de `progress/current.md` |
| `7f30fb6` T6a | AMPLIACIÓN: tests de los adjuntos convertidos, en RED |
| `0eaf3f4` T6b | AMPLIACIÓN: ficha de `compras.documento_adjuntos`, entrada v58, ARCHITECTURE, tests de F-139 |
| `azure-apps` `79bb47b` | solo `datamart_seg_anual.md` (fila del restringido, sección F-141 + párrafo F-146, «Lo que NO lee», E2). Sin push |
| `azure-apps` `eda420c` | solo `datamart_seg_anual.md`: contrato de adjuntos (estado F-028, tabla de piezas, H6, H8, H11, H13). Sin push |

- **Configuración**: `DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS` =
  `mart,cierre,compras,maestro,retenciones,descompuestos,stg,aux,_meta` (sin `contabilidad`) y
  `DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES = ""`. Igual en `.env.example`, con el porqué.
- **`apply_grants`: sin cambio de lógica.** Lo ajeno al perfil sale del CATÁLOGO
  (`esquemas_ajenos`), así que `contabilidad`, fuera de la lista, se le veta entero (tablas, USAGE y
  privilegio por defecto, `build_veto_statements`) exactamente como `tesoreria` y `personal`, y la
  postcondición (`lecturas_indebidas`) pregunta por él. Solo docstrings/comentarios citan F-146.
- **`02_roles.sql`** (5 quinquies a y b): nueve esquemas en los tres arrays, fuera el bucle
  `excluida_r`, cabecera y comentario al día; comprobación final con `contabilidad` en el grupo
  que debe salir `f` y `apuntes_restringidos_mes` entre las `has_table_privilege`.
- **Diccionario v58**: las CUATRO fichas de tabla de `contabilidad` empiezan por «**No disponible
  para el perfil restringido** (…F-146, `R-PERFIL-RESTRINGIDO`): ese perfil no lee nada del esquema
  `contabilidad`; … «permission denied» … responde que el perfil no lo incluye» (`plan_cuentas` y
  `apuntes_restringidos_mes` nuevas; `mayor` y `saldos_cuenta_mes` citan F-141 y F-146).
  `R-PERFIL-RESTRINGIDO`: ámbito `contabilidad` (en vez de sus dos tablas), la regla dice «MENOS el
  esquema `contabilidad` entero (…)», el «SI lee» ya no nombra contabilidad, el motivo cita la
  decisión del 2026-10-21. `R-CONTABILIDAD-RESTRINGIDA`: «…y tampoco la general (`contabilidad`)
  desde F-146». Cabecera de `contabilidad.yaml` y entrada `# version 58 (F-146, …)`.

## AMPLIACIÓN T6 (orden del humano del 2026-10-21, «arregla ya el diccionario»)

Aviso formal de `mcp-bbdd`: su F-028 (nuestra F-142) está desplegada y verificada desde las 13:26
UTC (`ca-mcp-bbdd-dev--0000023`, imagen `r20261021-1510`). Misma v58, sin subir versión.

- **Ficha de `compras.documento_adjuntos`**: «lo entrega SIN CONVERTIR… llegan como binario, y
  convertirlos es F-142» pasa a «**LO QUE LE LLEGA A LA IA** (F-028 de `mcp-bbdd`, desplegada el
  2026-10-21; nuestra F-142)»: ningún fichero dentro de la respuesta; TEXTO por página (PDF,
  ofimática que Microsoft Graph convierte a PDF —`.doc`, `.docx`, `.xlsx` pequeños…—, texto
  extraído en el servidor de lo que Graph no convierte —`.msg`, `.xlsx` grandes…—); escaneos e
  imágenes como IMAGEN; `paginas` (10 primeras por defecto, `paginas="11-20"` para seguir); el
  documento 24 h en un SharePoint propio con enlace solo para quien lo pidió. COMO LO PIDE (la
  pareja, el respaldo con la empresa 1, `SIN_BINARIO`, `ORIGEN_AMBIGUO`) intacto.
- **v58**: su entrada cuenta las dos cosas (restringido sin contabilidad + adjuntos convertidos).
  Las entradas de v53/v54 no se tocan: son historia.
- **ARCHITECTURE** (el límite de F-139) y **`azure-apps`** (estado F-028 con las cuatro pruebas de
  `mcp-bbdd`, H6 nuevo, H8, H11 con la excepción de las 24 h, H13 resuelto; H5 intacto). Nada
  inventado: solo lo del aviso, contrastado con `azure-apps/mcp_bbdd.md` (§ de `abrir_adjunto`),
  que no se toca (además tenía cambios de otra sesión sin commitear; no se han añadido).
- **Desviación**: tres tests de F-139 (`test_f139_r2_la_ficha_declara_el_limite`,
  `…_nombra_la_herramienta_desplegada`, `test_f139_r6_…`) EXIGÍAN «SIN CONVERTIR», «como binario»,
  «imagenes se ven directamente» y «sin convertir»: ahora exigen «F-028», «TEXTO por pagina» y
  «como IMAGEN», y `SIN CONVERTIR`/`como binario` pasan a la lista de caducados.
- **No hecho**: nuestra F-142 sigue `pending` en `features.json`; cerrarla o reescribirla es del líder.

RED (`pytest tests/test_f146_restringido_sin_contabilidad.py -k t6 --tb=line`, antes de T6b):

```
FF.FFF                                                                   [100%]
E   AssertionError: la ficha de documento_adjuntos no dice «F-028»
E   AssertionError: la ficha aún da por vigente: ['SIN CONVERTIR', 'como binario']
E   AssertionError: la entrada de la v58 no dice «F-028»
E   AssertionError: : el datamart publica el ÍNDICE; abrir el ORIGINAL ... y lo entrega sin convertir. ...
    assert not ['sin convertir']
E   AssertionError: ['sin convertir', 'incrustad', 'incrustad']
5 failed, 1 passed, 22 deselected in 2.78s
```

El que pasa en RED es `test_f146_t6_la_clave_y_el_respaldo_no_cambian`: es la guarda de lo que NO
se toca. GREEN: F-146 + F-139 + F-145 + F-141, **234 passed**.

## Decisiones de diseño

1. **La lista de excluidas queda VACÍA, no «como red».** Con las dos de contabilidad dentro, R7 de
   F-141 (`excluidas_invalidas`) las rechaza por ser de un esquema que no se le concede y la
   nocturna terminaría en FAILED sin ejecutar nada; lo demuestra `test_f146_r1_la_lista_de_
   excluidas_queda_vacia`. El mecanismo sigue (para objetos de esquemas que SÍ ve). La red para el
   mayor analítico de F-127: si nace en `contabilidad`, el veto del esquema; si nace en otro esquema
   del perfil, el vigilante «mayor» o su exclusión explícita. El comentario de `settings.py` (el de
   F-127 incluido) y ARCHITECTURE lo dicen.
2. **Sin guarda nueva contra un `.env` que vuelva a listar `contabilidad`.** Las de F-141 (R5) no la
   prohíben (está en el consumo); `tesoreria` y `personal` tampoco tienen una. El job no fija estas
   variables (test de F-141 R1) ni el `.env` del puesto (comprobado: no tiene claves
   `PG_PERFIL_RESTRINGIDO_*`). Lo avisa `.env.example`. Si el reviewer la quiere, es una línea en
   `_PerfilRestringido.guarda` y queda fuera del encargo.
3. **El fake de F-141 ahora filtra los vigilados por esquema**, como el SQL real
   (`SQL_OBJETOS_VIGILADOS` solo busca en los esquemas del perfil): sin eso, `contabilidad.mayor`
   del fake habría hecho fallar el camino normal sin exclusiones.

## Desviación respecto al encargo (justificada)

`tests/test_f128_restringida.py::test_f128_r22_ficheros_de_permisos_sin_cambios_respecto_a_main`
comparaba `main...HEAD` sobre `settings.py`, `grants.py` y `02_roles.sql`: solo era cierto en la
rama de F-128 y pone en rojo a cualquier feature posterior que los cambie con motivo (esta). Ahora,
si `main` ya tiene `Merge F-128` (`a24bf34`), comprueba el diff de ESE merge contra su primer padre
(vacío: verificado); si no, lo de antes. Misma garantía, robusta al merge, como los tests de
versión de F-141/F-144/F-145. Anotado en `progress/current.md`.

## Fase RED (requisitos centrales)

Comando: `.venv/Scripts/python.exe -m pytest tests/test_f146_restringido_sin_contabilidad.py -q
--tb=line -p no:cacheprovider -W ignore::DeprecationWarning -k "r1_contabilidad_no or r1_la_lista
or r2_la_nocturna or r2_una_tabla or r4_02"` (antes de T2):

```
FFFFF                                                                    [100%]
E   AssertionError: assert 'contabilidad' not in ['mart', 'cierre', 'compras', 'maestro', 'retenciones', 'contabilidad', ...]
tests\test_f146_restringido_sin_contabilidad.py:63: AssertionError: assert 'contabilidad' not in [...]
E   AssertionError: assert 'contabilidad...os_cuenta_mes' == ''
tests\test_f146_restringido_sin_contabilidad.py:82: AssertionError: assert 'contabilidad...os_cuenta_mes' == ''
E   AssertionError: el perfil restringido 'sigrid_dm_perfil_restringido_ro' tiene objetos con «mayor» en el nombre sin excluir: contabilidad.mayor_analitico. Ya se le han revocado; si son el mayor analítico (F-127), añádelos a PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES (F-141).
    assert 'FAILED' == 'SUCCESS'
tests\test_f146_restringido_sin_contabilidad.py:192: AssertionError: el perfil restringido ... contabilidad.mayor_analitico ...
E   AssertionError: (la misma, en test_f146_r2_una_tabla_nueva_de_contabilidad_no_le_llega)
tests\test_f146_restringido_sin_contabilidad.py:216: AssertionError: ...
E   assert (<re.Match object; ... match="FOREACH esquema_r IN ARRAY ARRAY[\n        'mart'> and "'contabilidad'" not in "..."
      "'contabilidad'" is contained here:
        nciones', 'contabilidad',
tests\test_f146_restringido_sin_contabilidad.py:274: assert ...
FAILED tests/test_f146_restringido_sin_contabilidad.py::test_f146_r1_contabilidad_no_esta_entre_los_esquemas_del_perfil
FAILED tests/test_f146_restringido_sin_contabilidad.py::test_f146_r1_la_lista_de_excluidas_queda_vacia
FAILED tests/test_f146_restringido_sin_contabilidad.py::test_f146_r2_la_nocturna_le_veta_contabilidad_entera
FAILED tests/test_f146_restringido_sin_contabilidad.py::test_f146_r2_una_tabla_nueva_de_contabilidad_no_le_llega
FAILED tests/test_f146_restringido_sin_contabilidad.py::test_f146_r4_02_roles_no_le_concede_contabilidad
5 failed, 17 deselected in 0.41s
```

El tercer y cuarto fallo son el riesgo que motiva la feature, medido: con `contabilidad` en la
lista, una tabla nueva `contabilidad.mayor_analitico` se le CONCEDÍA y solo la frenaba el vigilante
por nombre (con otro nombre, le habría llegado en silencio). La campaña completa en RED (antes de
T2): `18 failed, 4 passed in 1.09s`; los 13 restantes eran diccionario, docs y `azure-apps`.

## Fase GREEN

- `pytest tests/test_f146_restringido_sin_contabilidad.py`: **22 passed in 0.90s** (28 con T6).
- F-141 + F-146 + F-128 restringida + F-135 + F-136: **322 passed** (antes del arreglo de T3b,
  `test_f128_r22_ficheros_…` era el único rojo).
- Suites de diccionario y restringidas (52 ficheros `f006`, `f037`, `f056`, `f128`, `f135`, `f138`,
  `f139`, `f144`, `f145`, …): **3116 passed, 251 skipped** con solo el rojo de F-128 que arregla T3b.
- `pytest -k "r30 or azure_apps"`: **79 passed** (R30 de F-141 en verde con `azure-apps` `79bb47b`).

## Verificaciones MANUALES pendientes (tras APROBADO y merge)

La secuencia completa, con comandos, está en `progress/current.md` (entrada de F-146): imagen, job
ANTES de publicar y de `apply-grants` (con la imagen vieja, la nocturna le DEVOLVERÍA `contabilidad`
cada noche), `publicar-diccionario` (v58), `check-diccionario`, `apply-grants` (humano),
`has_table_privilege` por perfil (restringido `f` en todo `contabilidad` y CERO tablas legibles
del esquema; estándar y total iguales que antes), reinicio del MCP (leer antes la revisión activa)
y aviso a `mcp-bbdd`. Nada de esto se ha hecho: ni Azure, ni Postgres, ni `.env`, ni push.

## Fuera del alcance

- `retenciones` (con `retenciones.apuntes_contables`): sigue en el perfil (test
  `test_f146_r1_retenciones_sigue_dentro`). Perfiles estándar y total: sin cambio (test R3).
- `mcp-bbdd`: sin cambio de código. Su `azure-apps/mcp_bbdd.md` ~l.924 dice «sin el mayor
  contable»: es suyo de actualizar (no se toca desde aquí; se les avisa en el paso 8).
- `specs/F-141-*` no se reescriben (son la historia de F-141).

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados (`bash harness/init.sh` final) | ver «Resultado de `init.sh`» abajo |
| Tests de la feature | 28 nuevos (22 + 6 de T6, 28 passed); F-141 actualizados: 143 passed; F-139: 3 actualizados |
| Cobertura de las líneas cambiadas | `PUERTA COBERTURA: N/A` en el `init.sh` inicial; ver el final abajo. Las 32 líneas de producción tocadas son constantes de cadena, comentarios y docstrings |
| Mutantes generados / supervivientes | `python -m harness.mutacion --feature F-146`: **CERO mutantes** («3 ficheros, 32 líneas de producción… no llevan código mutable»; no escribe informe). Evidencia sustituta, 4 mutantes MANUALES, los 4 cazados (abajo) |
| Tiempo de la suite | `init.sh` inicial: 8486 passed, 254 skipped en 4090,64 s (1:08:10), máquina compartida con campañas de otros proyectos |

**Mutantes manuales** (cada uno contra F-141 + F-146 + F-128 restringida + F-135 + F-136, y
`git checkout` después):

| Mutante | Resultado |
|---|---|
| M1 `contabilidad` de vuelta en `DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS` | 8 failed, 314 passed: cazado |
| M2 lista y exclusiones de F-141 (`contabilidad.mayor,contabilidad.saldos_cuenta_mes`) | 8 failed: cazado |
| M3 sin `retenciones` en la lista (lo que queda FUERA) | 6 failed: cazado |
| M4 `'contabilidad'` de vuelta en el veto del administrador de `02_roles.sql` (5 quinquies b) | 1 failed (`test_f146_r4_02_roles_no_le_concede_contabilidad`): cazado |

M4 solo lo caza el test nuevo: el de F-141 (`test_f141_r22_el_veto_sale_del_catalogo…`) comprueba
que el veto excluye los esquemas del perfil, no que no excluya ninguno más.

## Resultado de `init.sh`

- Inicial (antes de escribir nada): 8486 passed, 254 skipped en 4090,64 s; ENTORNO LISTO.
- Tras T1-T5, primer intento: ROJO, `test_f057_r25_el_fichero_de_provision_trae_los_diez_esquemas`
  (`02_roles.sql` no puede decir «nueve»: lo había escrito en dos comentarios). Corregido en T2b.
- Tras T1-T5, segundo intento: **8510 passed, 254 skipped en 1604,03 s (26:44)**; `PUERTA
  COBERTURA: 100.0% de 1 líneas cambiadas cubiertas (1/1)`; `PUERTA TAMAÑO: impl 149/220`;
  ENTORNO LISTO.
- Final, con T6: FINAL_PENDIENTE
