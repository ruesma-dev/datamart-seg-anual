<!-- progress/review_F-153.md -->
Revisión completa (pasada 1), sobre `caebdb4`.

# F-153 · Review

**Veredicto: CHANGES_REQUESTED.** El código, el SQL, las fichas y los tests están bien: no hay que
tocarlos. Lo que falla son **los pasos MANUAL de `design.md` §9**: tres huecos, los tres en un
fichero de spec. La pasada 2 puede ser incremental y sin campaña nueva si el delta solo toca `specs/`
y `progress/`.

**Rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura y mutación, con los
supervivientes analizados. D1-D4 = A no se reabren.

## Cambios requeridos

1. **`design.md` §9, paso 4 y vuelta atrás, paso 3: falta `apply-grants` incondicional tras
   `build-compras`.** El paso 4 solo lo lanza si `column_privileges` de `mcp_sigrid_dm_ro` no da 49,
   y esa comprobación da 49 siempre: Azure tiene `ALTER DEFAULT PRIVILEGES` en `compras` solo para ese
   rol (`pg_default_acl`: `{mcp_sigrid_dm_ro=r/sigrid_dm_etl}`). El otro lector,
   `sigrid_dm_perfil_restringido_ro`, tiene hoy SELECT en `compras.albaranes` y en la vista
   (`relacl`), pero no privilegio por defecto. Tras `build-compras` pierde todo lo que `compras`
   recrea, hasta la nocturna, y el check no lo ve. `main.py` 945-950 lo dice: a mano hace falta tras
   `build-compras` suelto. La vuelta atrás no lo menciona, y tiene el mismo `DROP`.
   **Cambio:** `.venv/Scripts/python.exe main.py apply-grants` fijo tras el paso 3 de la ida y tras el
   paso 3 de la vuelta, y comprobar 49 también para `sigrid_dm_perfil_restringido_ro` (en la vuelta,
   46 para los dos).
2. **`design.md` §9, vuelta atrás, paso 2: `git switch --detach <sha del merge de F-153>^1` no sirve
   tal como se fusionará.** `main` (`7e755b3`) ES la base de la rama: un `git merge` normal hace
   fast-forward, no hay commit de merge, y un `^1` tomado sobre la punta da `caebdb4^`, con el SQL
   nuevo y la v70. El paso 3 reconstruiría lo que se quiere deshacer y el 4 publicaría v70 en vez de
   v69. **Cambio:** apuntar al último `main` sin F-153 (`7e755b3` si `main` no se mueve) o exigir
   `git merge --no-ff`, y decirlo en la cabecera de §9.
3. **`design.md` §9 no tiene paso para R19**, que dice que el coste «se recalcula en MANUAL», y el
   informe §5 lo cuenta como parte de T10. **Cambio:** medir la vista (`SELECT count(*) FROM
   compras.v_estado_documentos`, frente a los 30 s del MCP, esperado ≤ ~1 s) y la duración de
   `build-compras` contra la de la noche anterior en `_meta.etl_runs`.

`design.md` está en 250/250 líneas: hay que hacer sitio en §9 (o resumir §8), porque la puerta de
tamaño mide ese tope. Si el texto de `progress/current.md` cambia, que siga remitiendo a §9.

## Verificación independiente

- `bash harness/init.sh` sobre `caebdb4`: **ENTORNO LISTO**, exit 0; **10.103 passed, 274 skipped**,
  1 h 09 min. PUERTA COBERTURA 100,0 % (15/15). PUERTA TAMAÑO en verde.
- **Azure, solo lectura, 17:34 UTC.** Prototipo con el texto real de `13` sobre
  `compras.albaranes` + `raw.con` + `fn_estado_documento`; no se ha desplegado nada:

| Punto | Resultado |
|---|---|
| Columnas actuales de `compras.albaranes` | 46; +3 al final (`test_f128`: prefijo idéntico) |
| Grano | `raw.dca` ⋈ `raw.con`: 315.884, todos `con.tip` = 14; catálogo del 14 sin parejas repetidas; la función lleva `LIMIT 1` |
| `documento_id` único con el 14 | 0 albaranes solapan con contratos, facturas o comparativos |
| Filas 44, 15 y 46, nueva contra vista viva | `EXCEPT ALL` en los dos sentidos: **0 y 0** |
| Tipos del `UNION` | `estado_id` INT, `fecha` y `fecha_facturacion` DATE, `tipo_documento` TEXT: sin cambios en la vista |
| Orígenes del 14 | FACTURACION 235.254, ALTA 7.689, SIN_HISTORIAL 72.941 (con 0 fechas, 0 días, 0 cotas), PASO y FUERA 0 |
| `tipo_documento` | ALBARAN, PROFORMA, NOTA y OTRO llegan bien; suma por tipo igual a la ficha |
| R11 y R16 | 185 con `estfac` = 1 y estado no 10; 6.612 de 7.689 PDT anteriores a 2026 |

- **Orden de R7:** leído en SQL y dominio, es el mismo, incluida la cota solo en `FUERA_DE_PROCESO`.
- **La vista no lee `raw`:** confirmado en el texto; R9 lo fija un test. R8 también: el `LEFT JOIN`
  a `documento_procesos` queda igual.
- **Sin ambigüedades nuevas:** `02`, `03`, `06` y `15` no usan `estado` sin cualificar.
- **`publicar-diccionario`:** `DELETE` + `INSERT`, sin tope de versión, con fichas de
  `RAIZ/config/diccionario`: del árbol local, y bajar a v69 funciona. Los scripts de `infra/`,
  `check-*`, `--timeout`, `filas_solo_lectura` y `_bootstrap_done` existen tal como los cita §9.
- **Fichas v70:** versión 70 con nota; 256 objetos y 2.243 columnas (test); R11-R13 cubiertos,
  sin frases de «tres familias» vigentes. `azure-apps` `076f669` recoge el cambio (local, sin push).

## Mutación

Tiempo total 8.599 s: **campaña no reejecutada: 2 h 23 min según el informe.** Recálculo puro:
alcance 56 líneas y **9 mutantes**, igual que el informe.

- **RM1:** medido en `ddb84fc`; `ddb84fc..HEAD` solo toca `progress/` y `tasks.md`: alcance intacto.
- **RM2:** 955,5 × 9 = 8.599 s; base ~1.800 s. Coste por mutante 2.866 s con 3 workers. Coherente.
- **RM3:** los 9 cambian comportamiento; ninguno es equivalente.
- **RM4:** los 9 reproducidos sobre copia en el scratchpad con `test_f153_dominio` y
  `test_f132_dominio`: **los 9 mueren** (de 3 a 17 fallos; base limpia 52 passed). Disipa el aviso de
  falsos muertos del modo paralelo. Árbol limpio después.
- **RM5:** N/A, rigor `estandar`. **RM6:** N/A, no se quitó ninguna guarda.
- La mutación solo alcanza Python: el SQL lo defienden tests de texto y el prototipo de arriba.

## Checkpoints

- **C1** `[x]` init.sh exit 0 · `[x]` ficheros del arnés.
- **C2** `[x]` una `in_progress` · `[x]` rama correcta · `[x]` `current.md` describe la sesión, con
  el mismo criterio que la review de F-150 (arrastra secciones antiguas, deuda previa) · N/A
  `history.md`: la feature no es `done`.
- **C3** `[x]` hexagonal: dominio puro, SQL en `compras/` · `[x]` primera línea · `[x]` sin prints,
  TODOs ni secretos · `[x]` semántica Sigrid: pareja tipo-estado, sin importes ni ámbitos en juego.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** `[x]` requisitos trazables (tabla) · `[x]` sin red ni BBDD · `[ ]` **MANUAL listadas con su
  comando exacto: incompletas y con uno incorrecto** (cambios 1-3) · `[x]` dobles: sin dobles nuevos.
- **C4 bis** `[x]` rigor declarado · `[x]` fase RED con trazas reales · `[x]` cobertura · `[x]`
  mutación, totales verificados · `[x]` muertos comprobados · `[x]` tiempo coherente · `[x]` 0
  supervivientes · `[x]` «Evidencias» con los cuatro números y workers.
- **C5** `[x]` `tasks.md` T1-T9 y T11 `[x]` con commits `F-153 Tn:`; T10 abierta es correcto: es el
  despliegue, tras el merge. `test_f073` fuera de la lista de §2, justificado (el hash lo exige).

## Cobertura

| Requisito | Test |
|---|---|
| R1-R4 | `test_f153_sql::r1`, `r2` (2), `r3`, `r4`; `test_f128_sql::r10` |
| R5-R7 | `test_f153_sql::r5` (2), `r6`, `r7` (3); `test_f153_dominio::r7_*` |
| R8, R9 | `test_f153_sql::r8`, `r9`; `test_f153_dominio::r8_*` |
| R10 | `test_f153_sql::r10` (2); `test_f153_dominio::r10_*` |
| R11-R14 | `test_f153_diccionario::r11_*`, `r12_*`, `r13_*`, `r14_*` |
| R15 | `test_f153_diccionario::r15` (se salta sin `azure-apps`) |
| R16-R19 | MANUAL, T10 (R19 sin paso: cambio 3) |
| R20 | `init.sh` y esta review |

## Automejora (propuesta, no aplicada)

En `CHECKPOINTS.md` C4: toda receta MANUAL con `build-*` suelto lleva `apply-grants` fijo, y una
vuelta atrás no se ancla en `<merge>^1` si la rama puede entrar por fast-forward.
