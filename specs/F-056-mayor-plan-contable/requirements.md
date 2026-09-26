<!-- specs/F-056-mayor-plan-contable/requirements.md -->
# F-056 · Requisitos (EARS)

El mayor contable y el plan de cuentas como árbol, sobre los `raw` que ingirió
F-066. Rigor `critico`. Cifras medidas en SOLO LECTURA el 2026-09-26 (08:40-09:00
UTC, `raw` de la nocturna de esa noche): detalle y consultas en
`progress/spec_F-056.md`. Lo marcado **[Dn]** depende de una decisión abierta del
humano (`design.md` §Decisiones); los requisitos están escritos con la opción
recomendada.

## Esquema y paso

- **R1.** El sistema debe construir el esquema `contabilidad` con un paso propio
  `build_contabilidad` (stage `build_aux`) dentro de `run-all`, después de
  `build_personal` y antes de `build_cierre`, con `depends_on = ["ingest_raw"]`. [D5]
- **R2.** El SQL de `contabilidad` solo debe leer `raw.*` y la vista
  `maestro.centros_coste`; nada de `stg`, `mart`, `cierre`, `compras`,
  `retenciones` ni `personal`.
- **R3.** CUANDO falla un sub-paso o falta su fichero SQL, el paso debe acabar
  `FAILED` con el nombre del sub-paso en el mensaje y NO ejecutar los siguientes.
- **R4.** El sistema debe ofrecer el comando suelto `python main.py
  build-contabilidad`, que marca las ejecuciones huérfanas antes de escribir
  (R4 de F-024) y NO publica el diccionario.
- **R5.** Ningún otro paso debe declarar `build_contabilidad` en su `depends_on`:
  si falla, la noche sigue y `R-FRESCURA` avisa.

## Plan de cuentas: `contabilidad.plan_cuentas` (tabla)

- **R6.** Debe haber una fila por grupo del plan (`raw.con` con `tip = 16`,
  44.778) y por cuenta auxiliar (`raw.cua`, que son `con.tip = 17`, 34.196), de
  todas las empresas y sin filtrar altas ni bajas. [D1]
- **R7.** `cuenta_id` (el `con.ide`) debe ser clave primaria y
  `(empresa_id, codigo_cuenta)` debe ser única (`R-CODIGO-POR-EMPRESA`); la
  clave legible `clave_cuenta = '<empresa>-<codigo>'`.
- **R8.** El `nivel` debe salir de la forma del código: longitud 1, 2, 3 y 4 →
  niveles 1 a 4 (GRUPO, SUBGRUPO, CUENTA, SUBCUENTA); fila de `cua` → nivel 5
  (CUENTA_AUXILIAR), la única imputable (`es_imputable`).
- **R9.** `cuenta_padre_id` debe ser el grupo de la MISMA empresa cuyo código es
  el prefijo inmediato (nivel 2-4: el código sin su último dígito; nivel 5: los 4
  primeros dígitos). Nivel 1 y cuentas sin ese prefijo → NULL. Nunca un padre de
  otra empresa. [D7]
- **R10.** Para el nivel 5 debe publicarse además `cuenta_padre_declarada_id`
  (`cua.padide`, NULL si 0) y `padre_declarado_difiere` (TRUE cuando no coincide
  con el padre por prefijo: 6 cuentas medidas).
- **R11.** Cada fila debe llevar `ruta_codigos` (`'4 > 43 > 430 > 4308 >
  4308000197'`), los identificadores de sus ancestros por nivel
  (`grupo_id`, `subgrupo_id`, `cuenta_3_id`, `subcuenta_id`) y `grupo_pgc`
  (primer dígito).
- **R12.** Cada fila debe llevar `empresa_id` (`con.emp`), `empresa_nombre`
  (`raw.auxemp.res` por `numemp`), `nombre_cuenta` (`con.res`), `fecha_baja` y
  `es_activa`.

## Mayor: `contabilidad.mayor` (tabla, una fila por apunte) [D2]

- **R13.** Debe haber exactamente una fila por fila de `raw.apu`, sin filtrar
  ninguna (2.166.701), con `apunte_id` como clave primaria.
- **R14.** SI el número de filas de `contabilidad.mayor` difiere del de
  `raw.apu` al terminar el sub-paso, ENTONCES el build debe fallar con un
  mensaje que dé las dos cifras.
- **R15.** `fecha` debe ser `apu.fec` como `DATE`, y `fecha_asiento` la del
  asiento por los dos saltos (`apu.asiide` → `raw.con.fec`); `fecha_difiere`
  marca las 297 filas en que no coinciden. `ejercicio` y `mes` salen de `fecha`. [D6]
- **R16.** `empresa_id` debe ser la empresa del ASIENTO (`raw.con.emp` por
  `asiide`); cuenta, código, nombre y `clave_cuenta` salen de
  `contabilidad.plan_cuentas`. Un `cueide = 0` (294 filas, importe cero) deja la
  cuenta a NULL y no se pierde.
- **R17.** `debe`, `haber` e `importe = debe - haber` deben publicarse como
  `NUMERIC(18,2)` (positivo = saldo deudor).
- **R18.** `clase_asiento` debe evaluarse en este orden, con comparación de
  texto sin distinguir mayúsculas y SIN usar `asi.ori` (vale 0 en 788.326 de
  788.328):
  `CIERRE` si `apu.cla = 3` o el concepto empieza por «asiento de cierre»;
  `SALDO_INICIAL` si es apertura (`cla = -1` o «asiento de apertura…») y esa
  cuenta no tiene CIERRE en el ejercicio anterior; `APERTURA` el resto de
  aperturas; `REGULARIZACION` si `cla = 1` o «asiento de regulariz…»;
  `NORMAL` lo demás.
- **R19.** `importe_saldo` debe valer `importe` en NORMAL, REGULARIZACION y
  SALDO_INICIAL, y 0 en CIERRE y APERTURA.
- **R20.** `saldo_acumulado` debe ser la suma de `importe_saldo` de la cuenta
  hasta el apunte inclusive, en el orden `fecha`, `codigo_asiento`, `posicion`,
  `apunte_id`.
- **R21.** La obra debe salir SOLO de `apu.cenide` traducido por
  `maestro.centros_coste` (`centro_coste_id`, `obra_id`, `codigo_obra`,
  `clave_obra`). Sin centro, o con centro que no es obra → NULL; no se reparte
  ni se busca por otra vía. El SQL no debe nombrar `apu.obr` ni el campo de obra
  de `cen`.
- **R22.** `tercero_id` debe ser `NULLIF(apu.empide, 0)` con su
  `tercero_nombre` (`raw.con.res`).
- **R23.** Deben publicarse también `codigo_asiento` (`con.cod` del asiento),
  `posicion`, `concepto`, `documento`, `punteo` y `clase_origen` (`apu.cla`
  literal).
- **R24.** Ninguna unión del mayor debe multiplicar filas: cada una va por clave
  primaria o contra un conjunto pre-agregado con una fila por clave.

## Saldos: `contabilidad.saldos_cuenta_mes` (tabla) [D3]

- **R25.** Debe haber una fila por cuenta, ejercicio y mes con algún apunte
  (~400.316), construida desde `contabilidad.mayor`, con `empresa_id`,
  `num_apuntes`, `debe`, `haber`, `importe_apertura` (APERTURA + SALDO_INICIAL),
  `importe_movimiento` (NORMAL), `importe_regularizacion`, `importe_cierre`,
  `importe_saldo` y `saldo_acumulado` (fin de mes).
- **R26.** La suma de `importe_saldo` de `saldos_cuenta_mes` por cuenta debe
  igualar la de `contabilidad.mayor`, y su último `saldo_acumulado` el último
  del mayor.

## Diccionario y propagación

- **R27.** `config/diccionario/contabilidad.yaml` debe tener ficha de los tres
  objetos con grano, `clave_negocio`, `claves_alternativas`, `relaciones`
  (a `maestro.obras`, `maestro.centros_coste`, `plan_cuentas`) y columnas.
- **R28.** Las fichas deben decir, con cifra: que el plan FINANCIERO no es el
  analítico de `maestro.cuentas_analiticas`; que contabilidad y analítica
  persiguen cosas distintas (F-063); que una operación deja varios apuntes
  (factura, remesa, totales); que sumar CIERRE o APERTURA duplica; y la
  cobertura de obra por grupo del PGC.
- **R29.** `00_global.yaml` debe ganar la entrada del esquema `contabilidad`,
  la regla dura `R-SALDO-CONTABLE` y `version` + 1; `pendientes` no crece.
- **R30.** Las fichas de `raw.cua`, `raw.asi`, `raw.apu` y `raw.apa` deben dejar
  de afirmar que la fecha del apunte exige dos saltos y que la jerarquía del
  plan son las cuentas de `cua`.
- **R31.** `contabilidad` debe entrar en `ESQUEMAS_DEL_DATAMART`,
  `DEFAULT_CONSUMPTION_SCHEMAS` y `.env.example`; `apply_grants` lo concede sin
  lista escrita a mano y `check-declarados` recorre `sql/contabilidad`.
- **R32.** `docs/ARCHITECTURE.md`, `CLAUDE.md` y
  `azure-apps/datamart_seg_anual.md` deben describir el esquema nuevo en el
  mismo trabajo, y el informe debe dejar escrito el cambio que necesita
  `mcp-bbdd` (lista blanca) para que el MCP lo vea.

## Verificación contra la base (MANUAL, humano)

- **R33.** El mayor de la cuenta `1-4308000197` (AHORRAMAS, S.A., Retenciones)
  debe devolver sus 641 apuntes de 2009 a 2026, la apertura 2026 de 727.529,01
  y un saldo final de 1.189.275,13 (cifras del 2026-09-26; se remiden el día).
- **R34.** La subcuenta `1-434` en 2026, sumando sus cuentas auxiliares sin
  CIERRE, debe dar el saldo 5.345.557,80 de la captura de Juan Romero.
- **R35.** El coste del paso (minutos y MB) debe medirse en su primera
  ejecución y anotarse en el informe, con el SKU del servidor ese día.
- **R36.** Todo requisito R1-R32 debe tener al menos un test offline
  `test_f056_rN_*` en `tests/test_f056_contabilidad.py` (texto del SQL sin
  comentarios, YAML, cableado del step), sin red ni BBDD.
