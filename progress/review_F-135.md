<!-- progress/review_F-135.md -->
Revisión completa (pasada 1) · diff `ffadfb2..782f226` (implementer) sobre base `main` 5f31a3d · 2026-10-11

# F-135 · Review · CHANGES_REQUESTED

**Veredicto: CHANGES_REQUESTED** por una grieta de seguridad latente que he provocado en local
(cambio 1; hoy 0 filas expuestas, medido). Los cambios 2 y 3 son menores, en el mismo viaje.

**Nivel de rigor: `critico`** (declarado): fase RED, cobertura ≥ 80 %, mutación sin supervivientes, MANUAL con comando.

## Verificación ejecutada (resultado real)

- `bash harness/init.sh` sobre `782f226`: **EXIT 0, ENTORNO LISTO**. **7.486 passed, 238 skipped, 0 failed**
  en 1.257 s. `PUERTA COBERTURA` [OK] 100,0 % (135/135). `PUERTA TAMAÑO` [OK]. Ruff con 260 avisos de deuda previa.
- **SQL en PostgreSQL 16.15 real** (contenedor desechable, `en_US.utf8`, ya borrado). He vuelto a ejecutar
  `prueba_local_sql.py` del implementer con el SQL de HEAD contra el de `ffadfb2`: **51/51 OK**. La copia
  completa es **idéntica a la `contabilidad` de hoy**: EXCEPT ALL en los dos sentidos da 0, con los mismos
  tipos y las mismas columnas en el mismo orden (el mayor lleva 3 más al final). El general sale sin CR y
  con el acumulado de lo visible, y las dos guardas de R10 saltan cuando deben.
- **Permisos en local**: `02_roles.sql` (administrador no superusuario, sobre el `02` viejo con `raw`
  concedido) deja al general con «permission denied» en `contabilidad_restringida`/`raw`, leyendo
  `contabilidad.mayor`, y al autorizado leyendo `2 | 1`; es reejecutable. `apply_grants` con el cliente
  real: 16/16 OK (noche normal SUCCESS + `verificacion = ok`; otro concedente → FAILED nombrándolo;
  `.env` viejo → FAILED sin ejecutar nada; tabla nueva sin lectura para el general).
- **Contraste en Azure (T14) repetido por mí**, en solo lectura, a las 05:3x UTC y sobre el mayor de esta
  noche: **55.519 restringidos, 8.796 asientos, 25 empresas, 0 CR visibles, 521 cuentas CR**, 6.065/11.810
  saldos. Coincide cifra a cifra con el informe (§5). El criterio V2 que se implementó es el medido: la
  spec daba 55.504 y 8.791 el 09-10, y el mayor ha crecido 945 apuntes.
- **Mutación, recálculo puro**: 7 ficheros, 530 líneas, 25 mutantes, igual que el informe y con el mismo
  texto original→mutado. No reejecutada: el informe declara 6.047 s (> 60 s).

## Lo que pedía mirar el líder

1. **Ningún camino al rol general.** Raw está fuera del bucle de `02_roles.sql`, vetado cada noche
   (tablas, USAGE y privilegio por defecto) y comprobado en el catálogo, que hace fallar el paso. No hay
   privilegios por defecto globales (solo `IN SCHEMA`) ni funciones `SECURITY DEFINER`. Ninguna vista ni
   SQL fuera de `sql/contabilidad/` lee `contabilidad_restringida`, y nada de otro esquema lee
   `contabilidad.*`. El `.env` del puesto no lista `raw` (recuento: 0) y el job no fija
   `PG_CONSUMPTION_SCHEMAS`. Los importes de lo restringido no salen: `07` solo cuenta y `06` filtra
   cada agregado. Las 521 cuentas CR están enmascaradas. **Queda un camino latente: el cambio 1.**
2. **Copia idéntica**: reproducida en local (arriba). En Azure se comprueba en el paso 7 del MANUAL.
3. **V2 = lo medido**: reproducido en Azure (arriba).
4. **MANUAL** (`impl_F-135.md` §8): el orden es correcto. Primero Power BI sin `raw` (es D3, la
   precondición que el líder llama D9), luego el disco, la línea base, `02_roles.sql`, la imagen y el job
   con el tag comprobado, el build y `apply-grants`, la comprobación de la copia frente a la línea base,
   la **prueba negativa con el login real** `mcp_sigrid_dm_ro`, la positiva y R28 al día siguiente. Los
   pasos 3-6 van el mismo día y antes de la nocturna, que es lo que cierra la ventana de una nocturna con
   la imagen vieja.
5. **`progress/` sin datos personales**: barrido (€, `[0-9]{8}[A-Z]`, nombres) de `impl`, `mutacion` y el
   diff de `current.md`: solo recuentos; el único importe es de 4 proveedores (spec ya aprobada).
6. **Escrituras en Azure del implementer: ninguna.** T14 usó `filas_solo_lectura` con
   `_bootstrap_done = True` (lo he comprobado en su script). **Aviso sobre mí mismo:** mi primera lectura
   de `_meta.etl_runs` se hizo sin desactivar el bootstrap del cliente. Ejecutó contra Azure el DDL
   idempotente de siempre (`CREATE SCHEMA/TABLE IF NOT EXISTS`, `CREATE OR REPLACE VIEW` de `_meta` con
   `00_meta.sql`, que no cambia respecto a `main`), lo mismo que corre cualquier comando del CLI. Fue un
   no-op de hecho, pero fue DDL y lo declaro. El resto de mis lecturas fueron READ ONLY y sin bootstrap.
   No hice ningún GRANT ni REVOKE.

## Checkpoints

**C1** [x] `init.sh` termina con exit 0 · [x] existen los ficheros del arnés.
**C2** [x] solo F-135 está `in_progress` · [x] la rama es la de la feature · [x] `current.md` abre con la sesión
activa · N/A `history.md`: la feature no está `done`.
**C3** [x] hexagonal: el dominio es puro (`test_f135_r1_el_dominio_no_importa_infraestructura`), el SQL está en
`sql/contabilidad/` con `NN_` y los permisos van en infrastructure · [x] primera línea con la ruta en los 11
ficheros nuevos · [x] sin `print`, TODO, secretos ni dependencias nuevas · [x] semántica de Sigrid: `importe_saldo`
y la clase (R-SALDO-CONTABLE) se conservan; `clase_bruta = 'NORMAL'` equivale a `clase_asiento = 'NORMAL'`.
**C3 bis** N/A: `docs/referencia/` no cambia.
**C4** [ ] **R23 sin test trazable** (cambio 3). El resto de R1-R24 sí lo tiene, y R25-R28 son MANUAL ·
[x] tests sin red ni BBDD · [x] las MANUAL están en `impl_F-135.md` §8 con comando exacto, y `current.md` remite
allí (mismo criterio aceptado en F-085 y F-132) · [x] dobles: la puerta de dobles de `init.sh` está en verde.
**C4 bis** [x] `rigor` declarado · [x] **fase RED** con salida real de T1-T11 (§3) · [x] cobertura 100 % ·
[x] mutación recalculada (arriba) · [x] muertos comprobados: no se reejecuta porque la campaña pasa de 60 s.
Uso el recálculo puro más RM1-RM6 · [x] coste por mutante: 6.047 × 4 / 25 = 968 s, frente a una línea base
de unos 978 s · [x] sin «⚠ CAMPAÑA NO VÁLIDA», «Sin veredicto» = 0, línea base en verde (4 workers) ·
[x] **RM1**: se midió sobre `6ff4f16`. Desde ahí solo cambian `progress/` y `tasks.md`, y el alcance sobre
HEAD es el mismo · [x] **RM2**: 25 × 241,9 = 6.047. La media × W (968 s) cuadra con la base y cuadra con el
reloj: `mutacion2.log` va de las 05:04 a las 06:45 · [x] **RM3**: ningún equivalente muerto.
`frozen=False` y `slots=False` los mata con razón el barrido `test_f006_dataclasses_inmutables.py` ·
N/A **RM5**: no hay supervivientes ni equivalentes declarados · [x] **RM6**: no se quitó ninguna guarda ·
N/A campaña manual: la automática dio 25 · [x] 0 supervivientes · [x] «Evidencias» con los cuatro números
y los workers (§7) · [x] ningún N/A sin motivo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] T1-T14 y T19 en `[x]` con commit `F-135 Tn:` (T13-T14 van juntos y T10 en dos commits, se acepta).
T15-T18 son MANUAL y siguen en `[ ]`, como deben · [x] `git status` limpio · [x] `features.json` en `in_progress`.

## Cobertura · requisito → test (`tests/test_f135_*`)

| Req. | Tests |
|---|---|
| R1, R3 | `dominio::r1_*` (6), `dominio::r3_*` (3) |
| R2, R7 | `dominio::r2_*` (8), `dominio::r7_*` (6), `sql::r7_la_cuenta_gana_al_asiento` |
| R4 | `sql::r4_*` (3), `dominio::r1_la_regex_del_sql_se_construye_desde_la_tupla` |
| R5, R6 | `sql::r5_*` (9), `sql::r6_la_guarda_de_recuento_va_sobre_el_completo`, `test_f056_*` adaptados |
| R8-R14 | `sql::r8_*`, `r9_*`, `r10_*`, `r11_*` (2), `r12_*`, `r13_*`, `r14_*` (2), `sub_pasos_*` (2) |
| R15-R18 | `grants::r15_*` (4), `r16_*` (4), `r17_*` (4), `r18_*`, `cliente_*` (7), `paso_*` (4) |
| R19, R20 | `grants::r19_*` (2), `settings_*` (5), `grants::r20_*` (8) |
| R21, R22 | `sql::r21_retenciones_declara_la_excepcion`, `sql::r22_*`, `sql::diccionario_*` (5) |
| R23 | **ninguno** (cambio 3) |
| R24 | `sql::docs_*` (2) |
| R25-R28 | MANUAL (§8 pasos 8, 9 y 11) |

## Cambios requeridos

1. **El criterio se abre en silencio cuando la cuenta no resuelve en el plan.**
   `02_mayor.sql:168` decide CR solo por `pc.codigo_cuenta`, que viene del `LEFT JOIN` de la línea 171.
   Si un apunte trae `cuenta_id` y esa cuenta no está en `contabilidad_restringida.plan_cuentas` (una
   auxiliar en `raw.con` sin su fila en `raw.cua`, o una carga desfasada entre `cua` y `apu`), el apunte
   queda `codigo_cuenta = NULL`, `restringido = false` y pasa al general. La guarda R10
   (`05_mayor_general.sql:87-91`) no lo ve, porque también mira `codigo_cuenta`.
   **Lo he reproducido** en PostgreSQL 16 local con una 465 sin fila en `cua`: el apunte de la 465 y su
   banco salen en `contabilidad.mayor` con su concepto y su importe. En Azure hoy hay **0**: 0 de 2.176.231
   apuntes con `cuenta_id` sin código, 0 en `raw.apu` sin resolver y 0 códigos de nivel 5 con forma
   rara. Pero nada garantiza ese invariante.
   **Se pide fallar cerrado** y probarlo con un contrato en `test_f135_sql.py`, junto a `r10`:
   - opción (a), la mínima: añadir a la guarda de `05` `count(*) WHERE cuenta_id IS NOT NULL AND
     codigo_cuenta IS NULL` = 0, o `RAISE`;
   - opción (b): restringir esos apuntes en `02`, con `COALESCE(..., s.cuenta_id IS NOT NULL)`, y
     reflejarlo en el oráculo de dominio.
   No cambia ninguna cifra de hoy ni el alcance Python de la campaña. El SQL no se muta, así que no hay
   que repetirla.
2. **`azure-apps/datamart_seg_anual.md`, sección «La información de personal… (F-135, 2026-10-11)»
   (línea 403) y las filas 130-131.** Describen el estado como vigente y no llevan la línea de estado que
   tienen las demás secciones. Hay que añadir **«Estado: implementada en la rama, SIN DESPLEGAR»**
   (pendientes T15-T18) y cambiarla a DESPLEGADA en T15. Es la regla de `azure-apps`: un documento que
   parece vigente sin serlo hace daño. Commit local, sin push.
3. **R23 sin test.** Hay que añadir `test_f135_r23_*`. El test lee la entrada F-127 de
   `harness/features.json` y comprueba cuatro cosas:
   - que cita `apuide`, `conide`, la contrapartida (`cuenta_analitica_contrapartida_id`) y
     `sigrid_dm_restringido_ro`;
   - que cita la cifra «100.502 de las 716.007»;
   - que su `status` no ha cambiado.

**Observación (no bloquea):** al MANUAL §8 paso 8 se pueden sumar `raw.asi` y `raw.rac` (D3).

## Automejora (propuesta, no aplicada)

- `build_postgres_client` ejecuta el bootstrap (DDL) antes de la primera lectura, también para un
  diagnóstico por `filas_solo_lectura` (me pasó a mí). Propongo un cliente de solo lectura sin bootstrap
  y que `reviewer.md` lo exija para leer de Azure. Vale para cualquier proyecto: portar a `arnes-base`.
