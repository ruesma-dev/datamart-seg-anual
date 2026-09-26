<!-- progress/impl_F-056.md -->
# F-056 · Informe del implementer

Rama `feature/F-056-mayor-plan-contable` (desde `main` fe061b0), rigor
`critico`, spec APROBADA el 2026-09-26 con D1-D8 segun la recomendacion (T0).
Diccionario 35 -> **36**. Commits `23bcf14` (T0) .. ver `git log main..`.

## Que cambio

Esquema nuevo **`contabilidad`**, construido por el paso `build_contabilidad`
(stage `build_aux`, `depends_on = ["ingest_raw"]`, sexto build de negocio de
`run-all` entre `build_personal` y `build_cierre`; nadie depende de el).

| Fichero | Que |
|---|---|
| `sql/contabilidad/00_setup.sql` | esquema y `contabilidad.fn_fecha` |
| `sql/contabilidad/01_plan_cuentas.sql` | el plan como arbol: grupos `con.tip = 16` UNION ALL auxiliares `cua`; nivel por longitud, padre por prefijo en la misma empresa, padre declarado aparte, 4 ancestros, ruta, `clave_cuenta`; PK + unico (empresa, codigo) |
| `sql/contabilidad/02_mayor.sql` | una fila por apunte: 2 fechas, empresa del asiento, cuenta del plan, debe/haber/importe, `clase_asiento` (R18), `importe_saldo`, `saldo_acumulado`, obra por `maestro.centros_coste`, tercero; 5 indices; guarda `DO $$` de recuento |
| `sql/contabilidad/03_saldos_cuenta_mes.sql` | cuenta x empresa x ejercicio x mes desde el mayor, importe por clase y saldo a fin de mes |
| `application/steps/build_contabilidad_step.py` | el step, `SUB_PASOS` como dato, parada con el nombre del sub-paso (tambien si falta el fichero) |
| `main.py` | comando `build-contabilidad`, el paso en `build_pipeline_steps`, docstrings (seis build) |
| `config/settings.py`, `.env.example`, `domain/diccionario.py`, `infra/sql/02_roles.sql`, `docs/runbook_postgres_azure.md` | `contabilidad` en consumo, en `ESQUEMAS_DEL_DATAMART` y en las tres listas del fichero de provision (once esquemas) |
| `config/diccionario/contabilidad.yaml` | 3 fichas + la de la funcion, con claves, relaciones y las advertencias con cifra (R27-R28) |
| `config/diccionario/00_global.yaml` | version 36, esquema `contabilidad`, regla `R-SALDO-CONTABLE`; `R-FRESCURA` a seis esquemas; `R-CODIGO-POR-EMPRESA` alcanza plan y mayor |
| `config/diccionario/raw.yaml` | fichas `cua`, `asi`, `apu`, `apa` corregidas (R30) |
| `docs/ARCHITECTURE.md`, `CLAUDE.md` | el esquema, «el plan son prefijos», la clase del apunte, doce pasos |
| `specs/F-006-mcp-azure/design*.md`, `progress/current.md` | recuento del inventario (176 objetos, 1248 columnas, 79 de consumo), que exigen sus guardianes |
| tests | `tests/test_f056_contabilidad.py` (nuevo, 66 tests) y las listas cerradas de `test_f024_cli`, `test_f047_nocturna`, `test_f006_{publicacion,frescura,formato,comandos}`, `test_f057_personal`, `test_f079_stg_consultable`, `test_f108_claves_alternativas` |
| `azure-apps/datamart_seg_anual.md` | seccion del esquema y el pendiente de `mcp-bbdd` (commits `2748264`, `90d84af` en `azure-apps`) |

## Decisiones de diseno y desviaciones (detalle en `progress/current.md`)

1. **Clave de `saldos_cuenta_mes` = (cuenta_id, empresa_id, ejercicio, mes).**
   El design pedia PK sin empresa y a la vez «una fila por empresa y mes» para
   los 294 apuntes sin cuenta; medido: caen en 2-3 empresas el mismo mes en 19
   meses, asi que su PK habria tumbado el build la primera noche.
2. **Asiento por `LEFT JOIN`** (R13 prohibe filtrar; hoy 0 apuntes sin asiento).
3. La guarda R14 corre en la misma transaccion que el `CREATE`: si salta se
   deshace el fichero entero y queda el mayor anterior (mejor que el design).
4. Padre por prefijo como `LEFT JOIN` a un CTE `grupos` (= `raw.con` tip 16)
   materializado una vez y unido cinco veces (padre + 4 ancestros).
5. `plan_cuentas` declara DOS claves alternativas ((empresa, codigo) y
   `clave_cuenta`); `test_f108` pasa a contar alternativas por clave.
6. `(s.fecha IS DISTINCT FROM s.fecha_asiento)` va entre parentesis: sin ellos
   el `FROM` confundia al parser del contrato y al de la campana.
7. Consecuencia del esquema nuevo no listada en la spec: `infra/sql/02_roles.sql`
   (tres listas a mano, lo destapo F-057) y el runbook pasan a once esquemas.

## Fase RED (T1, commit `3d2a646`)

Tests escritos antes que el codigo. Comando y salida real:

```
$ python -m pytest tests/test_f056_contabilidad.py -q -p no:cacheprovider -W ignore
...
FAILED tests/test_f056_contabilidad.py::test_f056_r13_una_fila_por_apunte_sin_filtrar
FAILED tests/test_f056_contabilidad.py::test_f056_r18_saldo_inicial_por_anti_join_de_cierres
FAILED tests/test_f056_contabilidad.py::test_f056_r32_documentacion - Asserti...
60 failed, 2 passed in 3.42s
```

Las dos que pasaban: `r31_apply_grants_sin_lista_a_mano` (verifica codigo que
no se toca) y `r36_un_test_por_requisito` (meta). Trazas de los centrales:

```
$ python -m pytest "...::test_f056_r9_padre_por_prefijo_dentro_de_la_empresa" \
  "...::test_f056_r14_guarda_de_recuento_con_las_dos_cifras" \
  "...::test_f056_r18_saldo_inicial_por_anti_join_de_cierres" \
  "...::test_f056_r3_un_fallo_sale_con_su_nombre_y_para" \
  "...::test_f056_r1_orden_en_run_all" "...::test_f056_r29_global_esquema_regla_y_version" --tb=line
E   AssertionError: SQL no encontrado: ...\sql\contabilidad\01_plan_cuentas.sql
tests\test_f056_contabilidad.py:217: ImportError: cannot import name 'build_contabilidad_step' from 'etl_sigrid.application.steps'
E   AssertionError: run-all construye la contabilidad (R1)
    assert 'build_contabilidad' in ['ingest_raw', 'load_excel_aux', 'build_stg', 'build_mart', 'build_maestros', 'build_compras', ...]
E   assert 35 == 36
6 failed in 1.27s
```

Despues, verde por tareas (T2-T17, un commit cada una). El contrato expresion
a expresion se genero con el parser del propio test sobre el SQL ya escrito y
se reviso contra R6-R26 linea a linea (igual que F-095); los tests semanticos
son los que dan el RED. Los cuatro tests del step de T21 (log, sub-paso a medio
configurar, `SUB_PASOS` inmutable) se escribieron DESPUES del step, para matar
los mutantes de la herramienta: su «RED» es la campana (seccion Evidencias).

## Verificado contra la base (SOLO LECTURA, 2026-09-26, SELECT equivalente al build)

Los tres `CREATE` convertidos en `SELECT` (`fn_fecha` -> `retenciones.fn_sigrid_date`,
el plan y el mayor como CTE), sobre el `raw` de la nocturna del 26:

| Comprobacion | Resultado |
|---|---|
| plan por nivel | 321 / 2.673 / 15.017 / 26.767 / 34.196; 38 empresas; `padre_declarado_difiere` = 6; 17 auxiliares sin grupo de prefijo |
| `1-4308000197` | ruta `4 > 43 > 430 > 4308 > 4308000197`, padre 536484 (4308) |
| mayor | **2.166.701** filas (= `raw.apu`); NORMAL 2.056.147, CIERRE 52.414, APERTURA 52.413, REGULARIZACION 4.294, **SALDO_INICIAL 1.433**; `fecha_difiere` **297**; 294 sin cuenta; obra 1.161.574; tercero 1.030.078 |
| C1 `1-4308000197` | **641** apuntes, 2009-01-31 a 2026-09-21, saldo **1.189.275,13**, apertura 2026 **727.529,01**; quitando solo CIERRE: 7.742.538,38 |
| C2 subcuenta 434, 2026, sin CIERRE | **5.345.557,80** (= la captura) |
| saldos | 400.342 filas, clave unica, suma de `importe_saldo` = la del mayor (-3.108.795,83) |
| obra por grupo PGC | 6: 90,3 % (425.520/471.188); 7: 61,4 %; 4: 46,8 %; 5: 24,5 %; 1: 18,4 %; 2: 9,6 %; 3: 0,1 % |

**Coste (R35, solo la lectura)**: plan 15-22 s; plan+mayor con ventana 77-85 s;
las tres 126 s. Escritura e indices no se pueden medir sin escribir: estimado
**4-6 min** y **~1,2 GB** (mayor ~0,65 GB + 5 indices ~0,45 GB; base 27 GB de
64). **SKU hoy: `Standard_B2s`** (Burstable, 64 GB), leido con
`az postgres flexible-server list`: la bajada a B1ms sigue sin hacerse. La
nocturna del 26 duro 00:00 -> 04:07 UTC.

## Fuera del alcance (spec)

`raw.apa` (F-061), la vista de saldos por nodo (F-058), la convergencia con
F-095 (D8, ficha aparte), ingerir `cug` (D7), descuadres (F-064).

## Lo que falta: verificaciones MANUAL (humano / lider tras el APROBADO)

Escrituras contra Azure: las autoriza el humano. En orden:

1. **Build** (T22): `python main.py build-contabilidad`. Esperado: `SUCCESS`,
   filas ~79.000 + ~2,17 M + ~400.000. Medir: `python main.py timings --last 5`
   (minutos por paso) y
   `SELECT relname, pg_size_pretty(pg_total_relation_size(oid)) FROM pg_class WHERE relnamespace = 'contabilidad'::regnamespace AND relkind = 'r';`
   (esperado ~1,2 GB en total), mas `pg_database_size` antes y despues.
2. **C1** `SELECT count(*), min(fecha), max(fecha), sum(importe_saldo) FROM contabilidad.mayor WHERE empresa_id = 1 AND codigo_cuenta = '4308000197';`
   -> 641 / 2009-01-31 / 2026-09-xx / 1.189.275,13 (a 26-09; se remide).
3. **C2** `SELECT sum(importe) FROM contabilidad.mayor m JOIN contabilidad.plan_cuentas p USING (cuenta_id) WHERE p.empresa_id = 1 AND p.codigo_cuenta LIKE '434%' AND m.ejercicio = 2026 AND m.clase_asiento <> 'CIERRE';`
   -> 5.345.557,80 (si no hay apuntes nuevos en la 434).
4. **C3** `SELECT (SELECT count(*) FROM contabilidad.mayor) = (SELECT count(*) FROM raw.apu);` -> `true`.
5. **C4** (con la desviacion 1: la cuenta 0 de los saldos es el NULL del mayor)
   `SELECT cuenta_id FROM (SELECT COALESCE(cuenta_id, 0) cuenta_id, sum(importe_saldo) s FROM contabilidad.mayor GROUP BY 1) a FULL JOIN (SELECT cuenta_id, sum(importe_saldo) s FROM contabilidad.saldos_cuenta_mes GROUP BY 1) b USING (cuenta_id) WHERE a.s IS DISTINCT FROM b.s;`
   -> 0 filas.
6. T24: `python main.py check-declarados` (todo lo declarado existe, sale 0),
   `check-unicidad` (plan: PK y las dos alternativas OK), `check-relaciones`
   (las nuevas unen), `check-diccionario`; despues `apply-grants` (debe listar
   `contabilidad`; si el job de Azure fija `PG_CONSUMPTION_SCHEMAS` a mano,
   anadirlo alli), `publicar-diccionario` (version 36) e imagen nueva del job.
7. **`mcp-bbdd`** (otro repositorio, T19): en `config/config.yaml`, bajo
   `seguridad.esquemas_permitidos`, anadir `- contabilidad` DETRAS de
   `- personal` (su `tests/test_f015_esquema_personal.py` exige que `personal`
   siga justo detras de `retenciones`); desplegar su imagen y reiniciar. Sin
   eso el MCP rechaza el esquema «fuera del ambito».

## Evidencias

| Evidencia | Valor (medido) |
|---|---|
| Tests ejecutados | `bash harness/init.sh`: **RESUMEN_TESTS** (antes de F-056, en `main`: 5562 passed, 203 skipped). La suite propia: `tests/test_f056_contabilidad.py` 66 passed en ~2 s |
| Skips nuevos | +4, todos N/A legitimos de `test_f006_fichas.py`: 3 × «el GROUP BY de este objeto no es derivable» (las tres tablas) y 1 × «saldos_cuenta_mes no lee directamente de raw» (lee del mayor) |
| Cobertura de lineas cambiadas | **LINEA_COBERTURA** |
| Mutacion, herramienta (Python) | **12 generados, 12 muertos, 0 supervivientes** (campana completa, 2 workers, 1961,6 s, SHA `7f71b1e`) |
| Mutacion, sistematica (SQL + propagacion) | **233 generados, 233 muertos, 0 supervivientes** (229 en la primera pasada sobre `3c67936`; los 4 supervivientes, documentales, muertos en la pasada 2 sobre `5150061` tras reforzar los tests; 2724,6 s con 4 workers). 43 los mata solo el contrato expresion a expresion: detalle en `progress/mutacion_F-056.md` |
| Tiempo de la suite | **TIEMPO_SUITE** (con medicion de cobertura) |
| Coste del build (R35) | NO medido: es escritura contra Azure (T22, MANUAL). Solo lectura: 126 s el SELECT de las tres tablas; estimado 4-6 min y ~1,2 GB; SKU `Standard_B2s` |

Detalle de las dos campanas, con la tabla de los 233 mutantes y el analisis de
los cuatro supervivientes de la primera pasada: `progress/mutacion_F-056.md`.
