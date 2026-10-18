<!-- progress/review_F-144.md -->
Revisión incremental desde 7c0a4f0 (pasada 2) · delta `7c0a4f0..98050ca` (commit 98050ca, T6)

# F-144 · Review · regla `R-EMPRESA-POR-DEFECTO`

## Pasada 2 · Veredicto: APPROVED (aprobado hasta 98050ca)

- **Rigor:** `estandar` (declarado). Fase RED de la pasada 2 con salida real (`18 failed, 14
  passed`); cobertura N/A con motivo impreso; mutación N/A (el delta solo toca YAML y tests:
  alcance sigue vacío). Lo aprobado en la pasada 1 no se relee: el delta no lo invalida.
- **init.sh entero:** VERDE, `8257 passed, 249 skipped` en 1369,71 s, cobertura N/A, tamaño OK, exit 0.
- **Cambio requerido 1 (a), (b), (c): resuelto.**
  - (a) Las listas son exactas: recalculadas por mí sobre las fichas de los 9 esquemas del
    `ambito` (sin funciones): 25 con `empresa_id`/`empresa`, 12 con solo `obra_id`, 33 sin
    ninguna. Coinciden objeto a objeto con la regla. Ningún esquema fuera del `ambito` tiene
    columna de empresa. `compras_restringida` entra en el `ambito` con razón (su único objeto
    no tiene empresa y la regla tiene que llegar a él para avisar).
  - (b) Para los objetos sin empresa ni `obra_id` la regla dice que el criterio NO se aplica,
    que la cifra mezcla todas las empresas, la frase que dice la IA y que NO dice «he supuesto
    Construcciones Ruesma». Nombra los 8 del review y 7 más, y cubre el resto con «los demás».
  - (c) `personal.partes_lineas` sustituye a «los partes de `personal`»; `partes` queda como cabecera.
- **Cruces propuestos, verificados en el SQL:** `compras.vencimientos` es `SELECT efecto_id AS
  vencimiento_id … FROM tesoreria.efectos WHERE sentido = 'PAGO' AND es_factura_compra`
  (`sql/compras/05_vencimientos.sql:57-92`); `tesoreria.efectos.efecto_id` es `PRIMARY KEY`
  (`sql/tesoreria/00_setup.sql:148`) y `empresa_id = c.emp` (`01_efectos_completo.sql:72`).
  `retenciones.movimientos.obra_id` es la obra de `maestro.obras` (`01_movimientos.sql:111,212`)
  y `compras.fact_compras_linea.obra_id` es el `ide` de la ficha de obra (`02_fact_linea.sql`),
  la misma clave que `maestro.obras.obra_id` (`01_obras.sql:71`). El único cruce no verificado
  (contar facturas/albaranes por sus líneas) la regla lo declara sin camino comprobado.
- **El test nuevo muerde** (sabotajes míos sobre una copia en el scratchpad, 32 passed de base):
  `empresa_id` plantado en `compras.facturas` → 2 failed (lista exacta y «sin empresa de
  verdad»); quitar «y NO dice «he supuesto…»» → 1 failed; objeto nuevo con `obra_id` en
  `personal` → 1 failed (lista de solo obra); sacar `compras.facturas` del tramo → 1 failed;
  sacar `compras_restringida` del `ambito` → 2 failed.
- **Checkpoints:** los de la pasada 1 siguen igual; `C3 semántica Sigrid` pasa a `[x]`. C5: commit
  `F-144 T6:`; `current.md` e `impl_F-144.md` al día.
- **Observación, no bloquea:** `compras.comparativo_*` (`comparativo_id` → `comparativos.empresa_id`)
  y `compras.contrato_lineas` (`contrato_id` → `contratos.obra_id`) tienen un cruce que la regla no
  nombra: la IA dirá «mezcla» donde podría filtrar. Conservador y honesto; si se quiere, feature aparte.

## Pasada 1 (revisión completa · `main...HEAD` = `d3b2869..48787dd`)
- **Veredicto:** CHANGES_REQUESTED
- **Nivel de rigor:** `estandar` (declarado en `features.json`): exige fase RED, cobertura,
  mutación muestreada (20, semilla 20260820) y la sección «Evidencias».
- **init.sh:** VERDE en esta pasada: `8239 passed, 249 skipped` en 1672,85 s, `ENTORNO LISTO` (exit 0). El verde no quita el cambio requerido: el hueco es de texto y ningún test lo mira.

## Lo que está bien

- La regla cumple la decisión del humano al pie de la letra: CRITERIO GENERAL, `empresa_id = 1`,
  la IA lo DICE (con frase modelo), excepciones (otra empresa —Porsan 28—, varias, grupo, UTE) y
  «nunca se suman empresas sin decirlo». Bloqueante, justo detrás de `R-CODIGO-POR-EMPRESA`, que
  remite a ella. Coherente con `R-CODIGO-POR-EMPRESA` (Ruesma 1, Porsan 28, 38 empresas).
- Columnas comprobadas contra los YAML del diccionario (cobertura 100 %): `empresa_id` en los 25
  objetos que cita el informe y `empresa` solo en `maestro.centros_coste`; ni `stg`, `mart`,
  `cierre`, `descompuestos` ni `aux_` tienen columna de empresa. Cuadra con la medición en Azure.
- **Tests R29 de F-141 (punto 2): no se debilitan.** `main` lleva `version: 54` (comprobado con
  `git show main:...`) y el viejo `>= version_de_main + 1` solo podía ser cierto dentro de la rama
  de F-141: en `main` daba 54 >= 55, rojo. El nuevo fija `VERSION_F141 = 54`: la versión no baja de
  la de F-141 y la historia conserva `# version 54 (F-141, `. Es el patrón de F-139 (`>= 53`,
  `tests/test_f139_limite.py:158-160`). La exigencia «sube en uno respecto a main» la lleva ahora,
  para F-144, `test_f144_version_55_y_su_entrada_de_cabecera`.
- **Versión y reglas (punto 3):** v54 → v55 con su entrada de cabecera; reglas 26 en `main` → 27
  (contado en el YAML). Ningún test cuenta reglas a mano: todos comparan con `len(dicc.reglas)`.

## Cambio requerido

1. **`config/diccionario/00_global.yaml`, regla `R-EMPRESA-POR-DEFECTO`, frase «La columna se
   llama `empresa_id` en `maestro`, `compras`, `retenciones`, …»: no es exacta, y el hueco es justo
   el que la regla quiere cerrar.** En `compras` solo 6 objetos de ~45 tienen `empresa_id` (las
   `v_pbi_*`, `v_control_forma_pago`, `comparativos`); en `retenciones`, 4 de 16. Hay objetos
   publicados que **mezclan todas las empresas y no tienen ni empresa ni `obra_id`**, así que ni
   la vía de la columna ni la de «los hechos que solo llevan `obra_id`» los cubre:
   - `compras.facturas`, `compras.albaranes`, `compras.vencimientos`, `compras.v_facturas_pago`,
     `compras.documento_alarmas` (y `compras_restringida.documento_alarmas`), entre otros
     (en `sql/compras/01_documentos.sql` no hay filtro de empresa);
   - `retenciones.v_pbi_retencion_entidad`, `v_pbi_retencion_resumen` y `v_pbi_retenciones_vivas`
     (esta última solo trae `codigo_obra`, que `R-CODIGO-POR-EMPRESA` prohíbe usar a solas);
   - `personal.partes` (lleva `obra_cabecera_id`, no `obra_id`; la regla dice «los partes de
     `personal`» cuando son `personal.partes_lineas` las que llevan `obra_id`).
   Con el texto actual, a «¿cuántas facturas entraron en septiembre?» la IA no encuentra
   `empresa_id` en `compras.facturas`, no filtra y aun así dice «he supuesto Construcciones
   Ruesma»: la cifra de las 38 empresas presentada como de Ruesma, que es exactamente el fallo
   «plausible y falso» que la regla nació para evitar.
   **Qué pedir:** (a) sustituir la lista por esquemas por «en los objetos que la tienen» o por la
   lista exacta; (b) añadir una frase para los objetos SIN empresa ni `obra_id`: mezclan todas las
   empresas; se filtra cruzando con sus líneas o su obra (p. ej. `documento_id` → `*_lineas.obra_id`
   → `maestro.obras.empresa_id = 1`, o `retenciones.movimientos` en vez de las `v_pbi_*` agregadas)
   y, si no se puede, la respuesta dice que la cifra es de todas las empresas y NO dice «he supuesto
   Ruesma»; (c) corregir «los partes de `personal`» por `personal.partes_lineas`.
   **Test:** ampliar `test_f144_la_regla_dice_lo_que_decidio_el_humano` (o uno nuevo) que fije la
   frase de los objetos sin empresa; mejor aún, un test que recorra las fichas de los esquemas del
   `ambito` y compruebe que todo objeto sin `empresa`/`empresa_id`/`obra_id` está nombrado en la
   regla o cae bajo la frase general, para que el siguiente objeto publicado no reabra el hueco.

## Checkpoints

| | Estado | Nota |
|---|---|---|
| C1 init.sh exit 0 | [x] | exit 0, ver arriba |
| C1 ficheros base | [x] | |
| C2 una sola `in_progress` | [x] | F-144 |
| C2 rama correcta | [x] | `feature/F-144-empresa-por-defecto` |
| C2 current.md solo la sesión activa | [x] | entrada nueva de F-144 encima; lo anterior es previo a esta rama |
| C2 `done` con history | [x] | F-144 no se marca `done` |
| C3 hexagonal | N/A | sin código de producción: solo YAML del diccionario y tests |
| C3 primera línea con ruta | [x] | el test nuevo; el YAML ya la tenía |
| C3 sin prints/secretos | [x] | ni nombres de personas ni secretos; solo nombres de empresa ya publicados |
| C3 semántica Sigrid | [ ] | cambio requerido 1: la regla no es exacta con dónde hay empresa |
| C3 bis (documentos de fuera) | N/A | no entra ningún documento externo |
| C4 cada `acceptance` con test | [x] | ver tabla de cobertura |
| C4 tests sin red ni BBDD | [x] | solo leen el árbol |
| C4 MANUAL listadas | [x] | `impl_F-144.md` §«Verificaciones MANUAL pendientes» |
| C4 dobles vs original | N/A | no hay dobles de test |
| C4 bis rigor declarado | [x] | `estandar` |
| C4 bis fase RED | [x] | salida real: `14 failed in 1.72s` y el R29 en rojo antes del arreglo |
| C4 bis cobertura | [x] | `PUERTA COBERTURA` N/A con motivo impreso: sin líneas Python de producción |
| C4 bis mutación | [x] | N/A justificado: alcance vacío recalculado (`alcance_de_feature('F-144', base='main').lineas == {}`); control: `generar_mutantes` sobre el test nuevo da 10, el generador funciona y el cero es por diseño. Dientes: dos sabotajes manuales |
| C4 bis muertos comprobados / tiempo / NO VÁLIDA / RM1 / RM2 / RM6 / campaña manual / supervivientes | N/A | no hay campaña: alcance vacío (arriba) |
| C4 bis RM5 | N/A | rigor `estandar` |
| C4 bis «Evidencias» | [x] | los cuatro números |
| C4 ter rutas sensibles | N/A | no hay `harness/rutas_sensibles.json`: la puerta no se declara en este repositorio |
| C5 tasks.md | N/A | sdd=false; commits `F-144 Tn:` T1–T5 contra los `acceptance` |
| C5 sin temporales | [x] | `git status` limpio |
| C5 features.json real | [x] | `in_progress` |

## Cobertura · acceptance → test

| Acceptance | Test |
|---|---|
| Regla existe, bloqueante, `empresa_id = 1`, decirlo, excepciones | `test_f144_la_regla_existe_y_es_bloqueante`, `test_f144_la_regla_dice_lo_que_decidio_el_humano`, `test_f144_el_motivo_cita_la_orden_del_humano`, `test_f144_el_ambito_alcanza_a_todo_esquema_con_empresa[×8]` |
| `R-CODIGO-POR-EMPRESA` remite; versión +1 | `test_f144_el_codigo_por_empresa_remite_a_la_nueva`, `test_f144_version_55_y_su_entrada_de_cabecera`, `test_f144_la_regla_va_junto_a_la_del_codigo_por_empresa` |
| Tests de diccionario existentes en verde | suite completa de `init.sh` (`test_f006_*`, `test_f141_*` incluidos) |
| init.sh verde y APROBADO; publicar tras merge | init.sh arriba; publicación MANUAL tras el merge |

## Automejora (propuesta, no aplicada)

- `CHECKPOINTS.md` C4: una regla dura que dice «en TODO objeto que tenga X» debería traer un test
  que recorra las fichas y compruebe el universo, no solo la presencia de frases. Aquí habría
  cazado los objetos sin empresa.
