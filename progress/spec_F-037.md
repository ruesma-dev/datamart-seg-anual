<!-- progress/spec_F-037.md -->
# F-037 · Informe del spec-author (fase 1: la cartera de cobros y pagos)

Fecha: 2026-10-13. Rama `feature/F-037-tesoreria` desde `main` (`41b40f7`). Spec en
`specs/F-037-tesoreria/` (requirements 148 líneas, design 249, tasks 17 tareas).
Revisada el mismo día tras la respuesta del humano: aprobación en §3, D4 remedida en §5,
contraste ampliado y D11 nueva en §6.

Todas las cifras salen de lecturas de SOLO LECTURA contra Azure
(`main._get_pg()`, `_bootstrap_done = True`, `filas_solo_lectura`), sobre la nocturna del
2026-10-13. Solo agregados: ni nombres, ni NIF, ni identificadores de personas.

## 1. Mediciones

### Volumen y bajas
| | efectos | de baja (`con.fecbaj <> 0`) | `con.tip` del efecto |
|---|---|---|---|
| `raw.pag` | 256.952 | 89.779 (34,9 %) | 25 en todos |
| `raw.cob` | 21.914 | 8.548 (39,0 %) | 24 en todos |

`compras.vencimientos` hoy: 197.190 filas = los pagos cuyo documento origen es `con.tip = 15`
(factura de compra). Ocupa 60 MB. Base: 36 GB.

### Cómo se identifica un pago de personal (lo que pidió el humano)
- **`raw.auxnap` (naturaleza del pago) tiene tres filas: NOMINAS, EMBARGO, CUOTAS.** Es el
  identificador directo. `natide`: 0 → 219.899; NOMINAS 33.990; EMBARGO 3.062; CUOTAS 1.
- **Cuenta del efecto** (`cueide` → `con.cod`): 465 → 37.048 (todos con naturaleza), 475 → 3,
  466 → 1. Ningún 460, 461, 544 ni 640-649 en `pag`.
- **Tercero empleado** (`con.tip = 43` del `entide`; los 50 de `raw.emp` mirados son tip 43):
  33.991 efectos, todos con naturaleza.
- **Documento origen nómina** (`con.tip = 306`, códigos `NOaa…`, estados Generada/Cerrada):
  35.863 efectos, todos con naturaleza.
- **Cruce de los cuatro criterios**: el conjunto de cualquiera de ellos es EXACTAMENTE el de
  `natide <> 0`: **37.053 pagos** (32.807 cumplen los cuatro; 3.056 sin tercero empleado —
  los embargos, con tercero vacío—; 1.184 sin documento 306; 5 solo por naturaleza y cuenta;
  1 solo por naturaleza). Ningún pago fuera de ese conjunto cumple alguno.
- **Cobros**: 0 con naturaleza, 0 a tercero empleado, 0 en cuentas restringidas (todos 43x/554).
- Cuentas sin resolver: 0 (161 pagos y 60 cobros sin cuenta, `cueide = 0`).
- Importes del conjunto de personal: BAJA 11.107 (15,5 M€), REALIZADO 19.733 (34,9 M€),
  PREVISTO 6.213 (6,7 M€) con **0 vencimientos futuros**: la cartera futura no pierde nada al
  restringirlos; los 6.213 previstos son pagos de nómina pasados sin puntear.
- **Lo que se cuela** (D7 del design): 429 pagos, 1,08 M€, a 16 proveedores (tip 5) cuyo NIF
  coincide con el DNI de un empleado. Son facturas de compra; recomendado no restringirlos.
- **Remesas**: 3.921 con pagos; 997 solo de personal; **1 mixta** (2 efectos de nómina): su
  `importe_remesa` delataría esos dos (D8: a NULL en la general).

### Estado (criterio de F-094: BAJA > REALIZADO > PREVISTO)
| sentido | personal | BAJA | REALIZADO | PREVISTO | previsto con vencimiento futuro |
|---|---|---|---|---|---|
| PAGO | no | 78.672 (244,9 M€) | 127.677 (826,6 M€) | 13.550 (80,1 M€) | 7.933 (55,0 M€) |
| PAGO | sí | 11.107 | 19.733 | 6.213 | 0 |
| COBRO | — | 8.548 | 12.349 | 1.017 (40,2 M€) | 204 (18,9 M€) |

`est = 10` («Pagado»/«Cobrado») sin `fecrea`: 41.884 pagos (312,4 M€) y 2.106 cobros
(467,2 M€). Sin el `est` en el criterio, todos contarían como previstos.

**Contraste con la contabilidad general** (`contabilidad.mayor`, `importe_saldo`): saldo de
40+41 = −78,8 M€ frente a 80,1 M€ de PAGO previsto; saldo de 43 = +47,5 M€ frente a
40,2 M€ de COBRO previsto. **Con las bajas de cobro sumadas serían 385,4 M€**: en cobros la
baja también es fantasma en el conjunto. Excepción medida: cobros previstos CON retención,
2,2 M€ sin baja y 19,9 M€ de baja; F-094 vio 13,8 M€ en la contabilidad de retención de
cliente, así que ahí la baja puede no ser fantasma (declarado en D2, no resuelto).

### Obra, empresa, cobertura
- `cenide` informado: 201.791 pagos y 17.342 cobros; con obra por `maestro.centros_coste`
  (805 centros, 805 claves, sin ambigüedad): **200.143 pagos (77,9 %) y 17.102 cobros (78,0 %)**.
- Empresa (`con.emp` del efecto): 0 vacíos; 36 empresas en pagos, 26 en cobros.
- Documento origen: pagos 197.190 facturas de compra, 35.863 nóminas, 23.897 sin documento
  (22.707 no personales, 167,2 M€: pagos sueltos, nuevos para el datamart), 2 otros.
  Cobros: 20.420 con documento `tip = 11`, 1.493 sin documento. `raw.rco` NO se ingiere: las
  279 remesas de cobro solo tienen código (de `con`).
- 111.450 pagos traen cuenta bancaria del tercero: no se publica (R9).

### Coste en la ventana
- Nocturna del 13-10: **4 h 52 min** (292 min); `build_compras` 1.058 s,
  `build_retenciones` 227 s, `build_contabilidad` 1.087 s.
- La unión `pag ∪ cob` con todas las uniones del diseño: **278.866 filas en 2,0 s** (lectura).
- Estimado: **+1-3 min y +0,2 GB**. Se mide en el primer build manual (R29, T13).

## 2. Lo que la spec decide (opción recomendada en cada D; aprobación en §3)

D1 `tesoreria` tabla única y `compras.vencimientos` vista suya (0 personales en facturas de
compra) · D2 bajas publicadas y marcadas, mismo criterio en los dos sentidos, regla dura ·
D3 esquema propio `tesoreria_restringida` · D4 obra solo por el puente centro → obra ·
D5 cobros publicados ya con su cobertura declarada · D6 el estándar ve solo recuentos ·
D7 unión de los cuatro criterios + fallo cerrado; los 429 autónomos-empleados quedan
visibles · D8 `importe_remesa` NULL en la remesa mixta · D9 `build_tesoreria` delante de
compras sin `depends_on` · D10 nombres.

Hallazgo de diseño que condiciona D1: si `tesoreria.efectos` se recreara con `DROP ...
CASCADE` cada noche, se llevaría la vista `compras.vencimientos` y todo lo que cuelga de ella.
Por eso las tablas de `tesoreria` siguen el patrón de `personal` (`CREATE IF NOT EXISTS` +
`TRUNCATE` + `INSERT`, R14).

## 3. Aprobación del humano (2026-10-13) y lo que queda abierto

Cita, transmitida por el líder: «la obra se puede sacar de los contratos, revisa si asi ayuda
a machear mas obras. amplia la explicacion del contraste con contabilidad. puede ser que
venga de que los efectos antiguos no estaban bien (nos paso antes con las retenciones) lo
demas ok».

- **APROBADAS con la opción A**: D1, D2, D3, D5, D6, D7, D8, D9 y D10.
- **D4 remedida** (§5): el contrato no ayuda (+6 efectos). Sigue abierta con la
  recomendación A (solo el centro).
- **D11 NUEVA** (§6): columna `previsto_antiguo` (más de 2 años vencido sin puntear) y regla
  dura. Recomendación A; la decide el humano.
- Fuera del repositorio, sin cambios: lista blanca de `mcp-bbdd`; comprobar en el despliegue
  que el job no fija `PG_*_SCHEMAS`.

## 4. Texto de las decisiones tal como se presentaron (D1-D10, antes de la aprobación)

**D1 · `compras.vencimientos`.** (A) **Recomendada**: `tesoreria` tabla única de efectos y
`compras.vencimientos` vista suya con las mismas columnas (0 efectos de personal en facturas
de compra, medido: no pierde ni una fila). (B) Dejar la tabla de F-080 y que `tesoreria`
publique solo los demás efectos y una vista unión: dos SQL con la misma lógica de efecto,
que es la duplicación que F-073 vino a evitar. (C) Dos tablas paralelas: descartada.

**D2 · Bajas** (`con.fecbaj`: 89.779 pagos y 8.548 cobros, 35 %). (A) **Recomendada**:
se publican todas, marcadas (`estado_tesoreria = 'BAJA'`, `efecto_anulado`), con la regla
dura `R-TESORERIA-ESTADO`, y el mismo criterio en los dos sentidos. Lo respalda el contraste:
PAGO previsto 80,1 M€ frente a 78,8 M€ del saldo 40+41; COBRO previsto 40,2 M€ frente a
47,5 M€ del 43, cuando con las bajas serían 385 M€. Se declara la excepción medida: en
cobros CON retención las bajas son 19,9 M€ y F-094 vio que la contabilidad sostiene 13,8 M€
de retención de cliente, así que ahí la baja puede no ser fantasma (queda para otra feature).
(B) No publicar las bajas: rompería `compras.vencimientos` (sus 76 k anulados son contrato
de F-080). (C) En cobros ignorar `fecbaj` como hace `retenciones`: 325 M€ fantasma.

**D3 · Dónde vive lo restringido.** (A) **Recomendada**: esquema propio
`tesoreria_restringida`, el patrón «módulo + `_restringida`», legible para la IA y con
permisos por esquema; cuesta tocar `settings`, `02_roles.sql`, `ESQUEMAS_DEL_DATAMART` y el
contrato del MCP. (B) Dentro de `contabilidad_restringida` (`efectos_tesoreria`): 0 cambios
de permisos, pero un módulo escribiría en el esquema de otro y el nombre mentiría.

**D4 · Obra.** (A) **Recomendada**: solo el puente centro → obra (78 %), sin elaborar más.
(B) La cascada de `retenciones` con respaldo por líneas del documento: más cobertura en
facturas sin centro, más SQL y más dependencias (`v_src_lineas_*`); es fase 2.

**D5 · Cobros sin F-040.** (A) **Recomendada**: publicarlos ya, con la cobertura declarada
(21.914 efectos; 204 previstos futuros por 18,9 M€; sin documento de venta ni CIF).
(B) Esperar a F-040 (prioridad 48).

**D6 · Qué ve el estándar de lo restringido.** (A) **Recomendada**: solo recuentos
(`efectos_restringidos_mes`), como D5 de F-135. (B) Importe por empresa y mes: es la nómina
neta mensual, lo que se protege. (C) Nada: leería una cartera recortada sin saberlo.

**D7 · Criterio de personal.** (A) **Recomendada**: la unión de los cuatro criterios más
el fallo cerrado (hoy idéntica a `natide <> 0`: 37.053), para que restrinja de más si un día
divergen. (B) Solo `natide <> 0`: más simple, sin red si alguien olvida la naturaleza.
**Lo que se queda visible, medido**: 429 pagos (1,08 M€) a 16 proveedores cuyo NIF es el de
un empleado (autónomos que también son o fueron empleados). Son facturas de compra que
`compras.facturas` ya enseña; restringir su efecto no protegería nada y quitaría filas a
`compras.vencimientos`. Recomendado no restringirlos; si el humano dice que sí, es un quinto
criterio (cruce con `raw.emp`) y `compras.vencimientos` pierde esas filas.

**D8 · Remesa mixta.** (A) **Recomendada**: `importe_remesa` a NULL en la general (1 remesa
hoy, también en `compras.vencimientos`). (B) Recalcularla con lo visible: un número que no
es el de Sigrid con el nombre del de Sigrid.

**D9 · Orden con compras.** (A) **Recomendada**: delante en la lista, sin `depends_on`.
(B) `build_compras` depende de `build_tesoreria`: un fallo de tesorería tumbaría compras.

**D10 · Nombres.** `tesoreria.efectos`, `estado_tesoreria` (`PREVISTO`/`REALIZADO`/`BAJA`), `importe_flujo`.

## 5. D4 remedida: ¿la obra del contrato ayuda? (2026-10-13, solo lectura)

Pregunta del humano: «la obra se puede sacar de los contratos, revisa si así ayuda a machear
más obras». **Respuesta medida: no ayuda.** Se probó en cascada, solo cuando el centro no da
obra, con los mismos enlaces que ya usan `compras.fact_compras_linea` (F-067) y
`compras.v_control_forma_pago` (F-080): contrato de la cabecera (`dcf.ctride`, 86.515 de
167.211 facturas lo traen) y contratos de las líneas (directo, por albarán o por línea de
albarán) → `compras.contratos.obra_id` (19.101 de 19.111 contratos con obra, todas en
`maestro.obras`). Después, la obra de la cabecera (`dcf.obride`) y la de las líneas
(`factura_lineas.obra_id`, el respaldo de F-094).

| pagos no personales (219.899) | efectos | importe | cartera viva futura (7.933, 55,0 M€) |
|---|---|---|---|
| 1 · centro → obra | 200.143 (91,0 %) | 1.024,9 M€ | 7.665 · 52,9 M€ (96,6 %) |
| 2 · contrato | 6 | 0,07 M€ | 0 |
| 3 · cabecera / líneas | 112 (+3 con varias obras) | 0,26 M€ | 0 |
| sin obra | 19.635 | 126,4 M€ | 268 · 2,1 M€ |

Por qué no hay más: los pagos sin obra son 12.891 sin documento (94,4 M€: pagos sueltos),
1.612 facturas imputadas a centros de estructura (códigos `GG`, `0001`, `0003`...: 22,2 M€;
no son de obra y no deben tenerla) y 5.129 facturas sin centro, sin contrato y sin obra en
cabecera ni líneas (9,7 M€). Los 37.053 de personal no tienen obra (ni deben).

**Ambigüedades y discrepancias** (cuando hay dos fuentes): contrato ≠ centro en 323 efectos;
25 efectos con centro cuyas facturas cuelgan de contratos de varias obras; cabecera ≠ centro
en 495 de 190.255 (0,26 %). Manda el centro: es la imputación del propio efecto.

**Cobros**: ninguna vía. Las facturas de venta no se ingieren (F-040; los cobros cuelgan de
documentos `tip = 11` sin tabla en `raw`); `con.obr` está vacío en todos los documentos y
efectos de `pag` y `cob`; y «cliente con una sola obra en `maestro.obras`» resolvería 38
cobros sin centro (ninguno previsto), una conjetura y no un dato. Cobertura actual de cobros:
17.102 de 21.914 (78,0 %), y de la cartera viva futura, 201 de 204.

**Recomendación**: A, solo el centro. El contrato añade 6 efectos y exigiría escribir una
regla de precedencia para 323 discrepancias.

## 6. El contraste con la contabilidad, ampliado

**Hipótesis del humano**: los efectos antiguos no se mantuvieron bien (previstos sin puntear,
bajas fantasma), como pasó con las retenciones. **Precedente**: F-094 (`progress/history.md`,
«Retenciones infladas 4,3 veces»): el estado leía solo `fecrea` y contaba vivos los agrupados
y anulados; y `progress/explore_retenciones_contabilidad_fin_obra.md`: por proveedor cuadraban
1.027 de 1.268, pero «los grandes descuadran (historia anterior a 2016, prescripciones,
reclasificaciones)». Aquí las bajas ya están fuera (criterio F-094); lo que queda son los
previstos viejos.

### El previsto por antigüedad (hoy, sin personal)
| | futuro | vencido < 1 año | 1-2 años | 2-5 años | > 5 años |
|---|---|---|---|---|---|
| PAGO | 7.933 · 55,0 M€ | 2.278 · 20,4 M€ | 969 · 0,8 M€ | 1.093 · 0,7 M€ | 1.268 · 3,1 M€ |
| COBRO | 204 · 18,9 M€ | 298 · 15,6 M€ | 115 · 3,5 M€ | 171 · 2,0 M€ | 227 · 0,2 M€ |

Por año de vencimiento, el PAGO previsto con vencimiento ≤ 2015 son 504 efectos (2,69 M€),
497 de ellos creados antes de 2016. Por año de creación del efecto, lo creado antes de 2016
sigue previsto en 524 pagos (2,70 M€) y 110 cobros (0,35 M€). Por estado de Sigrid, lo
vencido hace más de 2 años está en Pendiente (1,19 M€), Aprobado (2,44 M€), Emitido, En
cartera y 4 Remesados (0,15 M€, todos de más de 5 años).

### Por qué PAGO cuadra «casi» (80,1 frente a 78,8 M€): dos errores que se compensan
- **(+) Previsto antiguo que la contabilidad no sostiene.** Cuadre por CUENTA del efecto
  (`pag.cueide`, la auxiliar del proveedor) contra su saldo (`importe_saldo`): **815 cuentas
  cuadran al céntimo (8,2 M€)**; **223 cuadran al céntimo solo si se quitan sus previstos
  vencidos hace más de 2 años (2,77 M€)**; 166 tienen previsto y saldo 0 (7,05 M€); 434 tienen
  saldo y ningún previsto; 625 descuadran (61,8 M€ previstos frente a 39,0 de saldo). Las 223
  son la hipótesis del humano, medida.
- **(−) Saldo sin efecto**: anticipos (407, 0,70 M€), 415 (0,56), 419 (0,23) y facturas aún sin efecto.
- **Por qué no se puede cuadrar cuenta a cuenta**: al emitir un pagaré la deuda pasa de
  400/410 a 401/411 (5,36 + 24,27 = 29,6 M€ de saldo) y el efecto conserva su cuenta de origen
  (77,1 de los 80,1 M€ previstos llevan cuenta 400, 403 o 410). Lo previsto Emitido/En
  cartera/Remesado son 34,3 M€; lo Pendiente/Aprobado, 45,7 M€ frente a 400+403+410 = 47,2 M€.
  Por eso el contraste honrado es el del grupo 40+41 entero, con estas dos partidas explicadas.
- Sin el antiguo (> 2 años): 76,2 M€ frente a 78,8 M€; la diferencia restante (−2,6 M€) es
  saldo sin efecto, no efecto sin saldo.

### Por qué COBRO no cuadra (40,2 frente a 47,5 M€)
- 433 (clientes empresas del grupo) y 434 (asociadas) suman **12,0 M€** de saldo y solo
  **1,1 M€** de efectos: se facturan sin generar efecto de cobro. Es la mayor parte del hueco.
- 430: 34,1 M€ de saldo frente a 37,8 M€ de efectos; la diferencia se parece al previsto
  vencido hace más de 2 años (2,2 M€).
- Las bajas de cobro (345 M€ pendientes) son fantasma en el conjunto (con ellas, 385 M€
  frente a 47,5); la excepción de los cobros con retención sigue declarada (D2, F-094).

### Otro hallazgo con fecha: `est = 10` sin fecha real, desde 2020
41.884 pagos (312,4 M€) y 2.106 cobros (467,2 M€) están Pagados/Cobrados en Sigrid SIN
`fecrea`; por año de vencimiento son 23 pagos y 4 cobros antes de 2020 y miles cada año
después (pagos: 350 en 2020, 6.920 en 2021, 8.174 en 2024). Es un cambio de práctica (el pago
por remesa marca el estado y no puntea la fecha), no un error antiguo: por eso el estado lee
`est` y la ficha dirá que `fecha_real` vacía no significa pendiente.

### Recomendación nueva (D11, la decide el humano)
**A**: columna `previsto_antiguo` (PREVISTO vencido hace más de 2 años a la fecha del build:
hoy 2.361 pagos, 3,9 M€, y 398 cobros, 2,2 M€) + regla dura: un flujo de caja usa `PREVISTO
AND NOT previsto_antiguo`; lo antiguo es deuda por depurar en Sigrid. B: solo la regla.
C: un estado `SOSPECHOSO` (descartada: reclasifica un hecho de Sigrid). Umbral: 2 años, el
que hace cuadrar las 223 cuentas.
