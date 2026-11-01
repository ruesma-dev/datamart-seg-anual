<!-- progress/impl_F-150.md -->
# F-150 · Informe del implementer · quinta tanda (T46-T52): el personal en dos tramos (N18)

Tandas anteriores: fase 1 en [`impl_F-150_fase1.md`](impl_F-150_fase1.md); N11-N15 en
[`impl_F-150_tanda2_3.md`](impl_F-150_tanda2_3.md); N16-N17 en
[`impl_F-150_tanda4.md`](impl_F-150_tanda4.md). Spec: `progress/spec_F-150.md` §12 (R53-R62,
diseño 12.2, tareas T46-T53). Rama `feature/F-150-receta-caja` (desde `bc4f54f`), sin push.

## 1. Qué cambió (un commit por tarea)

| Tarea | Commit | Qué |
|---|---|---|
| T46 | `bfd8b6f` | Dominio: `CUENTAS_NOMINA`, `MESES_VENTANA_NOMINA` 12, `MESES_MAX_SIN_NOMINA` 3, `MIN_PERSONAS_REPARTO` 10, `FUENTES_/MOTIVOS_REPARTO_PERSONAL`, `cuota_irpf_ss`, `reparto_pago_personal`, `partir_personal` (R53-R55) |
| T47 | `46054a8` | `00_setup`: tabla `tesoreria.reparto_pago_personal` y columnas; `07`: guarda R61, `_dev_nomina`/`_dev_ventana`/`_dev_personas` (2 sexies), `TRUNCATE`+`INSERT` del reparto, los dos tramos en la obra-mes con guarda fila a fila, `pendiente_personal_irpf_ss` en el corte, `COMMENT`s (R56-R58, R61) |
| T48 | `a046650` | `10`: `_sal_personal` con los partes del último cierre y `personal_irpf_ss_pendiente` (R59) |
| T49 | `8af41ab` | Contraste de solo lectura en Azure y sandbox (§3, §4) |
| T50 | `2f854e8` | Diccionario **v69**: ficha nueva (no recomendada, `motivo_no_consumo`), 4 columnas, textos, receta pasos 0 y 1, `R-CAJA-HIPOTESIS` (regla y ámbito); H01/H02/H06 en dos tramos (R60) |
| T51 | `b86b322` | `ARCHITECTURE.md`, `CLAUDE.md`; `azure-apps` **`499defb`** (local, sin push) |
| T52 | `aeb2c15` | Lo que cazó la línea base de la mutación (ver §2.7): la ficha del reparto dice de qué fact cuelga (F-042), inventario de F-079, recuentos v69 en `current.md`; mutación (`progress/mutacion_F-150_n18.md`) e `init.sh` |

Producción tocada: `etl_sigrid/domain/proyeccion_caja.py`, `sql/tesoreria/{00_setup,07_devengo_pendiente,
10_saldo_partida}.sql`, `config/hipotesis_caja.yaml`, `config/diccionario/{00_global,tesoreria}.yaml`.
Tests: nuevo `tests/test_f150_personal_n18.py` (≈100 casos: dominio, SQL como texto, R59); ampliados
`test_f150_{sql,diccionario,receta}.py`, `test_f140_sql.py`, `test_f141_perfil_restringido.py`.
Sin tablas de Sigrid nuevas: `raw.apu` y `raw.con` ya se ingieren. Sin dependencias nuevas.

## 2. Decisiones y desviaciones (justificadas)

1. **Dos excepciones acotadas en guardas de F-140** (`test_f140_sql.py`), con su porqué en el test:
   (a) R16 «sin aritmética de fechas» admite en `07` exactamente `INTERVAL '15 month'`, `'3 month'` y
   `'11 month'`, una vez cada uno: es la VENTANA de lectura de la contabilidad (R57, diseño 12.2
   punto 4: «build − 15 a build − 1», «`mes_hasta` − 11»), no un plazo sumado a un devengo; (b) R18
   cuenta 3 lecturas de `raw.hmores` (guarda, `_dev_personal` y `_dev_personas`, que solo CUENTA
   recursos distintos para el umbral). `10` usa `INTERVAL '2 month' - INTERVAL '1 day'` tal cual
   12.2 punto 5 (`10` no está en la lista de esa guarda).
2. **Empresa de la cuenta**: `_dev_nomina` toma la empresa de `raw.con.emp` de la cuenta (12.2 punto 1:
   «la cuenta: `con.tip = 17`, `cod`, `emp`»); el mayor usa la del asiento. Iguales en la empresa 1:
   la suma reproduce al décimo la medida de la spec (§3).
3. **Sin IRPF o sin SS en la ventana** (suma NULL) → `CUOTA_FUERA_DE_RANGO` (DEFECTO), igual que el
   dominio (`None` → `None`): pesimista para la caja, nunca una cuota parcial inventada.
4. **El reparto se publica tras la guarda D6** y antes de `devengo_pendiente_partida`: la obra-mes lo
   lee por `empresa_id` (`LEFT JOIN`, `COALESCE(cuota, 0)`: una obra sin empresa iría al defecto).
5. **Ficha nueva no recomendada** (spec 12.2 punto 7) con `motivo_no_consumo` obligatorio (R3 del
   diccionario): la cuota ya va aplicada en la obra-mes; la ficha está para leer la `fuente`.
6. Las fichas de N18 entraron en T50, no con el SQL: entre T47 y T50 la puerta del diccionario
   (`test_f006_*`, `test_f024_cli` `run-all`) estaba en rojo por `reparto_pago_personal` sin ficha.
   Se cerró en T50; cada tarea pasó su propia verificación.
7. **La primera campaña de mutación abortó con la línea base en rojo** (3 tests que T50 no corrió):
   `test_f006_r19_un_consumidor_del_fact_…[tesoreria.reparto_pago_personal]` (la ficha no decía que
   cuelga de `mart.fact_seguimiento_mensual` ni lo de F-042), `test_f079_r3_el_inventario_…` (un no
   recomendado nuevo sin inventariar) y `test_f006_los_recuentos_de_current_…` (2240 columnas).
   Arreglados en `aeb2c15` (texto, inventario `GRUPO_F_F140`, recuentos); la segunda campaña, en verde.
8. Paso 1 de la receta: «sin IVA, retención, documento, plazo ni fraccionamiento» en vez de «H03 … H24»
   (R60): el test r2 exige que cada paso nombre solo sus hipótesis.

**PARADA (T49)**: ninguna sobre importes. Un recuento se aparta > 5 % de la referencia de R62
(personas 245 frente a ~273) y está explicado: ver §3. Lo dejo dicho para el reviewer y el humano.

## 3. Contraste de SOLO LECTURA en Azure (T49, 31-10, 23:03-23:25 UTC)

`_bootstrap_done = True` y `filas_solo_lectura` (transacción READ ONLY), los `SELECT` de `07` (2 sexies,
pasos 5 y 6) y `10` (R59) como CTE, sin `INSERT` (`az_n18.py` en el scratchpad). `raw` de la ingesta
del 31-10 y la `tesoreria` de esa nocturna (que ya lleva N16: `importe_pendiente_personal`).

| Pieza (R62, §12.0) | Spec | Medido | Desvío |
|---|---|---|---|
| Reparto empresa 1: fuente, meses, ventana | `CONTABILIDAD`, 12 | **`CONTABILIDAD`, 12, 2025-10 a 2026-09** | — |
| `cuota_irpf_ss` | ~0,442 (± 0,02) | **0,441909** (`cuota_neto` 0,558091) | 0 % |
| Abonos neto / IRPF / SS (miles EUR, solo para el contraste) | 7.715,3 / 2.143,0 / 3.966,1 | **7.715,3 / 2.143,0 / 3.966,1** | 0 % |
| `personas_con_partes` | ~273 | **245** | −10 % (explicado abajo) |
| Σ personal / neto / IRPF + SS, 21 obras (M EUR) | 5,65 / ~3,15 / ~2,50 | **5,6481 / 3,1521 / 2,4959** | < 0,2 % |
| Filas con neto + irpf_ss ≠ personal | 0 | **0** (465 filas COSTE) | — |
| 0686 2026-11: personal / neto / IRPF + SS | 0,210 / ~0,117 / ~0,093 | **0,2104 / 0,1174 / 0,0930** | 0 % |
| Saldo: `personal_irpf_ss_pendiente` Σ | ~0,12 | **0,1234** (cierre 2026-10: 0,1067 de 0,2414; 2026-09: 0,0167 de 0,0378) | +3 % |
| Saldo: obras con > 0 | ~18 | **17** (18 obras con cierre 09 o 10; una con 0 partes en octubre) | explicado |
| Saldo 0686 | ~0,029 | **0,0289** (partes de octubre 0,0654) | 0 % |
| Coste del reparto (incluye las personas) | ~15 s | **18,4 s** | — |

**Las 245 personas**: medido aparte (solo lectura, 23:25 UTC) sobre la ventana 2025-10..2026-09: 273
recursos PERSONA internos con partes en TODAS las obras; **245** en obras de la empresa 1 y **28** en
obras de la empresa 28 (ninguno sin obra ni sin ficha). La spec contó las 273 sin filtrar empresa; el
diseño (12.2 punto 4) dice «por la empresa de la obra (`maestro.v_obra_fichas`)», que es lo
implementado y lo correcto (la cuota es POR EMPRESA). No cambia ninguna cifra: el umbral es 10.

## 4. Verificación semántica del SQL (Postgres 16 desechable, tipos reales de Azure)

`sandbox_n18.py` (scratchpad; docker `postgres:16` en el 55434, ya parado) sobre el fixture de N16-N17
(`sandbox_n16_n17.py`), con `raw.apu` de Azure (`hab`/`deb` `double precision`, `fec`/`cla`/`cueide`
`integer`, `res` `varchar`) y `raw.con` (`cod` `varchar`, `tip`/`emp` `integer`), consultados en
`information_schema` el 31-10. Oráculo: el dominio. **61 comprobaciones OK, 0 fallos**:
- Reparto = `reparto_pago_personal` del dominio en 7 escenarios: 12 meses (`CONTABILIDAD`, cuota
  0,428407), idempotente, **9 personas → `POCAS_PERSONAS`** y **10 → `CONTABILIDAD`**, 5 meses →
  `CONTABILIDAD_PARCIAL`, última nómina en build − 4 → `SIN_NOMINA_RECIENTE` (ventana y personas
  vacías), neto negativo → `CUOTA_FUERA_DE_RANGO`. El ruido no cuenta: cierre (`cla` 3 y por
  concepto), apertura (`cla` −1 y «ASIENTO DE APERTURA» en mayúsculas), regularización, el debe, la
  subcuenta 4652000001, la empresa 28 (fuera del devengo) y el mes del build; los céntimos de un
  `double` (0,004) se castean por fila; una bonificación negativa de SS sí cuenta.
- Obra-mes: los dos tramos = `partir_personal` fila a fila, suma exacta, VENTA sin tramos; corte =
  Σ de la obra-mes.
- Guardas: `raw.apu` vacía y `raw.con` sin las tres cuentas → `RAISE` con su motivo y las filas de
  ayer intactas; la guarda fila a fila salta con un neto alterado en 0,01 («… no cuadra en sus dos
  tramos: 25.41 + 19.04 frente a 44.44»).
- `10` (R59), dos vueltas: cierre en build − 1 → pendiente (0,441909 × 1.333,33 = 589,21); cierre en
  build − 2 → 0; sin cierre → NULL; empresa sin reparto → 0; `personal_coste_partes` intacto; sin
  `tesoreria.reparto_pago_personal`, la guarda de entrada de `10` falla.
- Corrió con `CURRENT_DATE` = 2026-10-31 (build de octubre).

## 5. Fase RED (comando exacto y salida real del fallo)

Desde la raíz del repo; trazas completas en el scratchpad (`red_t46.txt`, `red_t47.txt`, `red_t48.txt`).

- T46 (R53-R55): `.venv/Scripts/python.exe -m pytest tests/test_f150_personal_n18.py -k "r53 or r54 or r55" -q -p no:cacheprovider` →
  `E       AttributeError: module 'etl_sigrid.domain.proyeccion_caja' has no attribute 'cuota_irpf_ss'`
  (12), `... has no attribute 'partir_personal'. Did you mean: 'cuota_personal'?` (28),
  `... 'reparto_pago_personal'` (9), `... 'CUENTAS_NOMINA'` (1) … **50 failed in 1.46s**.
- T47 (R56-R58, R61): `.venv/Scripts/python.exe -m pytest tests/test_f150_personal_n18.py -k "r56 or r57 or r58 or r61" -q -p no:cacheprovider` →
  `E       AssertionError: falta el INSERT de tesoreria.reparto_pago_personal`;
  R58: `E       AssertionError: assert ['importe_ret...nte_personal'] == ['importe_pen...onal_irpf_ss']`;
  R61: `E       assert "to_regclass('raw.apu') IS NULL" in " DO $$ BEGIN IF to_regclass('mart.fact_seguimiento_mensual') ..."`
  … **15 failed, 11 passed, 50 deselected in 0.76s** (los 11 en verde: el `CREATE TABLE` ya escrito
  en `00_setup` y los nombres sin importes).
- T48 (R59): `.venv/Scripts/python.exe -m pytest tests/test_f150_saldo.py tests/test_f150_personal_n18.py -k r59 -q -p no:cacheprovider` →
  `E       AssertionError: assert 'iva_repercut...rado_hasta_4m' == 'personal_irpf_ss_pendiente'`
  … **4 failed, 8 passed, 120 deselected in 0.64s** (los 8: la condición de fecha, pura).

Después, las mismas órdenes: **50 passed**; **466 passed** (T47 con `test_f150_sql.py`,
`test_f140_sql.py`, `test_f150_personal.py`, `test_f150_contrato_compra.py`, `test_f150_saldo.py`);
**431 passed** (T48); T50: **557 passed** (diccionario, receta, hipótesis, F-141, F-147, F-140,
F-006 y `test_f024_cli.py`).

## 6. Verificaciones MANUAL pendientes y qué falta

- **T53, redespliegue** (humano, tras APROBADO y merge): pasos con comando exacto en
  `progress/current.md`, sección «F-150 · Redespliegue MANUAL de N18 (T53)». N11-N17 ya está en
  `main` y en Azure (el 31-10 `devengo_pendiente_obra_mes` ya tiene `importe_pendiente_personal` y el
  MCP sirve la v68): este despliegue es solo el de N18, con la **v69**.
- **R31** con el MCP en la 0686: noviembre ~0,117 el 30-11 y ~0,093 el 31-12, con la `fuente`.
- **Para validar por el humano** (de la spec, no bloquean): la cuota medida 0,442 (55,8 / 15,5 /
  28,7) frente a su 51 / 15 / 34; el saldo de partida también cambia (~0,12 M EUR); el defecto sin
  contabilidad es N16 (todo en el mes); el umbral de 10 personas. Y la referencia de 273 personas
  de R62, que son 245 por empresa (§3).
- Fuera de alcance: la caja proyectada (F-151), la caja del CP (F-154), una cuota por obra (la nómina
  contable es de la empresa), la empresa 39 (sin 4652: iría a DEFECTO si llegara a tener devengo).
- Falta: review (C1-C4 sobre T46-T52) y el despliegue.

## Evidencias

| Evidencia | Valor real |
|---|---|
| `bash harness/init.sh` (al final, sobre `ad35ecc`) | **verde**, código 0, «ENTORNO LISTO. Puedes trabajar.»: **10.042 passed**, 274 skipped, 2.570 warnings |
| Tiempo de la suite | 2.747,60 s (0:45:47), con cobertura |
| Cobertura de las líneas cambiadas | `PUERTA COBERTURA`: **100,0 %** (30/30, umbral 80 %, nivel estandar; diff desde `c9e4bbecba`, merge-base con `main`) |
| Tamaño | `PUERTA TAMAÑO`: requirements 150/150, design 250/250, impl 155/220 (antes de esta tabla), review 129/140 |
| Mutación incremental (`python -m harness.mutacion --feature F-150 --base bc4f54f --max-mutantes 8 --workers 3 --timeout 3000`, sobre `aeb2c15`) | 83 líneas de `proyeccion_caja.py`, 28 generados, **8 evaluados: 8 muertos, 0 supervivientes, 0 timeouts** (5.948,4 s; base 1.227-1.244 s por worker). Sin supervivientes que analizar. Informe: `progress/mutacion_F-150_n18.md`. El SQL no se muta: lo cubren los literales y la sandbox |
| Verificación semántica del SQL | `07` y `10`: **61 OK, 0 fallos** (Postgres 16.15, tipos de Azure) |
