<!-- progress/impl_F-107.md -->
# F-107 · Informe del implementer · contrapartidas del recurso y catalogo de cuentas analiticas

Rama `feature/F-107-contrapartidas-cuentas-analiticas` (desde `main` 8516878,
con F-101 y F-102). `sdd: false`, rigor `estandar`. Tareas derivadas de los
cuatro `acceptance`, un commit por tarea (T1 `430ec5d` ... T6 `653c11e`).
`azure-apps`: commit local `6af6e2c` (sin push).

## Que cambio

| Fichero | Cambio |
|---|---|
| `config/tables_sigrid.yaml` | Entra `caa` entera (`ide`, sin `tiemod`, sin WHERE ni exclusiones) |
| `sql/personal/00_setup.sql` | `personal.recursos` gana `centro_coste_contrapartida_id` y `cuenta_analitica_contrapartida_id` (BIGINT), al final del `CREATE TABLE` y con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (patron F-101/F-102, nunca DROP) |
| `sql/personal/01_recursos.sql` | `NULLIF(r.cenconide, 0)` y `NULLIF(r.caaconide, 0)` al final del INSERT; ningun JOIN ni WHERE nuevo; cabecera y `COMMENT` explican que la contrapartida es del RECURSO |
| `sql/maestro/06_cuentas_analiticas.sql` (nuevo) | Vista `maestro.cuentas_analiticas`: `raw.caa JOIN raw.con` (codigo, descripcion, empresa, baja) + `LEFT JOIN raw.con` por `padide` (codigo y nombre del padre); nivel, centro y partida con NULLIF 0; sin WHERE |
| `application/steps/build_maestros_step.py` | Sub-paso `cuentas_analiticas`, el ULTIMO, contando filas de la vista |
| `config/diccionario/raw.yaml` | Ficha `raw.caa`; cabecera «Son 70 tablas» |
| `config/diccionario/maestro.yaml` | Ficha `maestro.cuentas_analiticas` (12 columnas, 3 relaciones, casamiento medido, las tres cuentas del correo) |
| `config/diccionario/personal.yaml` | `recursos`: parrafo «la contrapartida es del recurso, no por tipo de hora», dos columnas y dos relaciones N:1; `recursos_tipos_hora`: aviso de que ahi no esta la contrapartida y relacion `cuenta_analitica_id -> maestro.cuentas_analiticas` |
| `config/diccionario/00_global.yaml` | Version 30; «las 70 tablas»; `R-CODIGO-POR-EMPRESA` alcanza a `maestro.cuentas_analiticas` (con la cifra en `motivo`); textos de los esquemas `maestro` y `personal` |
| `docs/ARCHITECTURE.md` | 70 tablas; bullet de F-107 con el orden de despliegue; matiz a la frase «`res.cenconide` no participa» |
| `specs/F-006-mcp-azure/design_detalle.md` | Enmienda: 165 objetos, 1097 columnas, 73 de consumo |
| `azure-apps/datamart_seg_anual.md` | 70 tablas, columnas nuevas de `personal.recursos`, seccion de F-107 con dependencia de despliegue |
| Tests | `tests/test_f107_contrapartidas_cuentas.py` (34 tests, R1-R4); ajustes en F-057, F-066, F-073, F-074, F-102 (abajo) |

## Lo medido (solo lectura, 2026-09-24)

Contra **Sigrid** por `sigrid-api` (`leer_sql`, validador de solo lectura):

- `caa`: **184.234** filas, 9 columnas int/float, todas `con.tip = 19`. `deb`,
  `hab`, `rep`, `prpide`, `prbide` = 0 en todas. Niveles 1-5 (68 / 63 / 3.872 /
  179.965 / 266). `padide` informado en 181.758: 181.754 a `cag` y **4 a otra
  `caa`** (empresa 18); los 181.758 tienen fila en `con`. `cenide` informado en
  181.806, 0 huerfanos. 1 cuenta de baja.
- Codigo: 0 repetidos dentro de una empresa, **14.063** repetidos entre
  empresas, 163.247 distintos. 146.238 cuentas de la empresa 1, 26.684 de la 28.
- Leer `caa` entera por `stream_table`: **4,3 s**, una pagina.
- Las tres del correo: 496869 = `00000.CIMO02` JEFE DE OBRA, 496923 =
  `00000.CICO01` COMBUSTIBLES-GASOIL, 496935 = `00000.CICO13` TELEFONO MOVIL
  (empresa 1, nivel 4, centro 496688, padres `00000.CIMO` / `00000.CICO`).
- **Contrapartidas** (`res`, 2.619 recursos): `cenconide` y `caaconide`
  informadas en **1.979**, siempre juntas; **8** centros y **847** cuentas
  distintas; 0 huerfanas contra `cen` y `caa`; 0 de otra empresa que el
  recurso; la cuenta es del mismo centro que `cenconide` en los 1.979. 1.875
  apuntan a 'CP' CENTRO PERSONAL (empresa 1). El lider midio 9 centros y 848
  cuentas: hoy son 8 y 847 (la cifra se mueve con las altas y bajas).
- **`reshor.caaide`**: 3.199 de 8.968 filas, 50 cuentas, 0 huerfanas, 0 de
  otra empresa. `res.caaide` vale 0 en todas.
- **`hmores.caaide`** (la cuenta de la linea de parte): 310.552 de 331.002
  lineas, 3.782 cuentas. **No** se publica (ver «Fuera de alcance»).

Contra el **Postgres de produccion**, `filas_solo_lectura` (transaccion
`READ ONLY` con `statement_timeout`), sin escribir nada:

- El SELECT del nuevo `01_recursos.sql` contado: **2.619 filas, 2.619
  `recurso_id`, 1.979 / 1.979 contrapartidas, 8 centros, 847 cuentas**;
  `personal.recursos` hoy tiene 2.619 filas: no se pierde ni se multiplica ninguna.
- El cuerpo de `maestro.cuentas_analiticas` con `raw.caa` sustituida por un
  CTE con 4 cuentas medidas en Sigrid y `raw.con` real: devuelve las tres del
  correo con su padre ('MANO DE OBRA INDIRECTA', 'CONSUMOS') y la cuenta de la
  empresa 18 cuyo padre es otra `caa`. El SQL compila y resuelve contra `raw.con`.
- Nota de transparencia: abrir `_get_pg()` ejecuta el bootstrap idempotente del
  cliente (`CREATE SCHEMA IF NOT EXISTS` sobre esquemas que ya existen): no-op.

## Decisiones de diseno

1. **Contrapartida sin JOIN en `personal`**: solo los dos ids; el nombre del
   centro y de la cuenta se resuelven por relacion en `maestro`. Garantiza una
   fila por `raw.res` y no anade dependencias a `build_personal`.
2. **`maestro.cuentas_analiticas` es VISTA** como el resto de `maestro`, y va
   **la ultima** en `build_maestros`: si `raw.caa` no existe, falla solo ella.
3. **El padre se nombra desde `raw.con`** (`codigo_cuenta_padre`,
   `descripcion_cuenta_padre`), sin ingerir `cag`: el padre es un `cag` (o una
   `caa` en 4 casos) y ambos son `con`. Es algo mas de lo que pedia la
   descripcion («cuenta padre»), pero su id solo no se puede traducir.
4. **Nombres** `codigo_cuenta` / `descripcion_cuenta` siguiendo `codigo_centro`,
   `codigo_obra`. No se publica clave legible `<empresa>-<codigo>` (no pedida):
   la ficha y la regla obligan a cruzar con `empresa_id`.
5. **`partida_presupuestaria_id`** se publica (pedida) aunque esta vacia hoy;
   la ficha lo dice. `deb`, `hab`, `rep`, `prbide` no (no pedidos, 0 en todas).

## Desviaciones y tests de otras features tocados (sin cambiar lo que vigilan)

- **`test_f057_r13_no_usa_centro_de_coste`** vetaba `cenconide` en todo
  `01_recursos.sql`. Su motivo (R13: el centro no atribuye obra) sigue: ahora
  descuenta exactamente UNA proyeccion literal
  `NULLIF(r.cenconide, 0) AS centro_coste_contrapartida_id` y veta cualquier
  otro uso; en `02_partes_lineas.sql` no admite ninguno.
- **F-102**: `test_f102_r13/r14` (censo «== 69») pasan a «>= 69»; `r20`
  (version «== 29») a «>= 29»; `r26/r27` («las tres al final») quitan antes
  por la cola las dos de F-107 (`_sin_posteriores`, que exige que esten);
  `r28/r29` dejan de buscar el literal «69 tablas» (lo vigilan F-066/F-074 y
  `test_f107_r4_*` con 70). Mismo tratamiento que F-102 dio a F-080.
- `TOTAL_TABLAS` 69 -> 70 en F-066 y F-074; `FICHEROS_MAESTRO` de F-073 gana
  `06_cuentas_analiticas.sql`.
- `current.md` lleva los recuentos 165/1097/73 que exige
  `test_f006_los_recuentos_de_current_son_los_de_hoy`.

## Fuera de alcance / pendiente

- **`personal.partes_lineas` no gana cuenta analitica.** La descripcion pedia
  la relacion «si trae cuenta», y hoy no la publica; el origen si la tiene
  (`hmores.caaide`, 93,8 % de las lineas). Anadirla toca el hecho de 331.000
  filas y sus guardas: **propuesta para el humano, feature aparte**.
- `cag` (grupos analiticos, 18.499) no se ingiere: su codigo y nombre ya salen
  de `con`; su jerarquia propia (padre del padre) no esta.
- La lista «Diez tablas son Propiedades de `con`» de `R-SIGRID-CON` no incluye
  `caa` (tampoco `res`): no se toca, es deuda previa de esa regla.
- **MANUAL del humano** (M1-M8 en `progress/current.md`, con comando y
  resultado esperado): ingesta de `caa`, builds, recuentos, casamiento,
  `check-*`, `publicar-diccionario` (version 30) y reinicio del MCP. Push de la
  rama y de `azure-apps`: del humano.

## Fase RED

Comando: `python -m pytest tests/test_f107_contrapartidas_cuentas.py -q -p no:cacheprovider`
sobre el arbol de `main` + el fichero de tests (commit T1 `430ec5d`):
**33 failed, 1 passed** (el que pasa se explica abajo). Traza de los centrales
(`-k "salen_del_recurso or caa_se_ingiere or publica_sus_columnas or construye_la_ultima or tres_cuentas_del_correo and 496869"`):

```
E       AssertionError: R1
E       assert 'NULLIF(r.cenconide, 0) AS centro_coste_contrapartida_id' in " TRUNCATE TABLE personal.recursos; INSERT INTO personal.recursos ( recurso_id, codigo_recurso, nombre_recurso, clase,...UNA empresa (F-102): el codigo se repite entre empresas, y la clave legible unica es clave_recurso = empresa-codigo.';"
E       AssertionError: caa declarada una vez (R2)
E       assert 0 == 1
E       AssertionError: SQL no encontrado: ...\sql\maestro\06_cuentas_analiticas.sql
E       AssertionError: assert ('estados_doc...ocumento.sql') == ('cuentas_ana...aliticas.sql')
E       AssertionError: no hay ficha de maestro.cuentas_analiticas
FAILED tests/test_f107_contrapartidas_cuentas.py::test_f107_r1_salen_del_recurso_con_nullif_cero
FAILED tests/test_f107_contrapartidas_cuentas.py::test_f107_r2_caa_se_ingiere_entera
FAILED tests/test_f107_contrapartidas_cuentas.py::test_f107_r2_la_vista_publica_sus_columnas_en_orden
FAILED tests/test_f107_contrapartidas_cuentas.py::test_f107_r2_el_paso_de_maestros_la_construye_la_ultima
FAILED tests/test_f107_contrapartidas_cuentas.py::test_f107_r3_las_tres_cuentas_del_correo_estan_traducidas[496869-00000.CIMO02-JEFE DE OBRA]
5 failed, 29 deselected in 0.75s
```

El unico que pasaba en RED es `test_f107_r1_no_se_une_nada_nuevo_y_no_se_pierden_filas`:
es un guarda de NO regresion (ningun JOIN nuevo), verde por construccion antes y
despues. Tras T2-T6: **34 passed**.

## Evidencias

- **`bash harness/init.sh`** tal cual, al cerrar (tras el commit T7): **ENTORNO
  LISTO**, exit 0. `[OK] pytest en verde`, `[OK] PUERTA COBERTURA`, `[OK]
  PUERTA TAMAÑO: F-107 dentro de los topes (impl 144/220)`, `[OK] Rama actual`;
  avisos previos: ruff 232 (deuda previa) y la feature `blocked` F-052.
- **Tests**: **5.295 passed, 193 skipped, 0 failed** (al arrancar: 5.246 /
  191). `tests/test_f107_contrapartidas_cuentas.py`: **34 passed**.
- **Tiempo de la suite**: **1.445,00 s (24 min 05 s)**, el que imprime pytest
  dentro de `init.sh`; al arrancar la sesion fueron 569,94 s. La diferencia es
  la maquina: habia otros procesos Python de otras sesiones en marcha. `init.sh`
  se lanzo en primer plano; el Bash de la sesion lo movio a segundo plano al
  agotar sus 600 s y se espero a su final.
- **Cobertura de lineas cambiadas**: **94,7 %** (968/1022, umbral 80 %),
  `PUERTA COBERTURA`. Se mide contra `dev`, que va por detras de `main`: la
  cifra es la misma que la de F-102 porque incluye lineas de otras features.
  F-107 solo cambia 14 lineas Python de produccion (la entrada nueva de
  `SUB_PASOS` y el docstring), cubiertas por `test_f073_build_maestros_*` y
  `test_f107_r2_el_paso_de_maestros_la_construye_la_ultima`.
- **Mutacion**: `python -m harness.mutacion --feature F-107 --base main` ->
  **CERO MUTANTES**: «el alcance tiene 14 linea(s) de produccion pero no se ha
  generado ni un mutante» (son cadenas y una declaracion de dato); la
  herramienta no escribe `progress/mutacion_F-107.md` a proposito. Evidencia
  sustitutiva, **mutacion a mano** de esa entrada, una a una y restaurando con
  `git checkout`, contra `tests/test_f073_pipeline.py` +
  `tests/test_f107_contrapartidas_cuentas.py`: `sql_file` a `06_cuentas.sql`
  -> 4 failed; `target_table` a `cuentas` -> 1 failed; `name` a `cuentas` -> 1
  failed; borrar el sub-paso entero -> 3 failed. **4 generados, 4 muertos, 0
  supervivientes.** El SQL y el YAML no son mutables por la herramienta: los
  vigilan los 34 tests de texto (con la fase RED de arriba) y las lecturas en
  solo lectura contra la base.
- **Lo que no se ha verificado aqui**: el DDL real (crear la vista y anadir las
  columnas escribe en el Postgres compartido) ni `raw.caa` ingerida: M1-M8 de
  `progress/current.md`, del humano.
