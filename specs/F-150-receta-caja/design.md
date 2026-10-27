# F-150 · Diseño (la receta de la caja, fase 1)

Mediciones: `progress/spec_F-150.md`. Requisitos: `requirements.md`. Decisiones CERRADAS por el
humano el 27-10: §9 (D1-D10; D8 y D9 dentro del alcance). Parte de F-140 desplegada (v62).

## 1. Encaje y límite

Amplía `tesoreria` (F-140) sin objetos nuevos: columnas en el catálogo, el devengo y los
contratos con el cliente, una ficha con la RECETA y una regla que remite a ella. Sin caja
proyectada: el ETL publica ingredientes (el coeficiente es un DATO) y la IA aplica las hipótesis
en vivo, en el orden de la receta, declarándolas todas.

```
stg.presupuesto (9 y 11, versión V) ─► coeficiente por partida ─► devengo_pendiente_partida
                                                                   └► devengo_pendiente_obra_mes
raw.obrctr.impadj ─► condiciones_contrato_cliente.importe_adjudicado ─► H10 SIGRID por peso (08)
config/hipotesis_caja.yaml (+paso_receta, PERFIL_MESES, H24, H25) ─► hipotesis_caja(_obra)
config/diccionario/tesoreria.yaml: ficha de hipotesis_caja = LA RECETA ◄─ R-CAJA-HIPOTESIS
```

**Fronteras.** F-151 (`fn_caja_proyectada`) ejecutará esta receta; aquí no se calcula caja ni se
escribe un `aplicar_perfil`. F-040 (ventas y certificaciones): el IMPORTE a certificar del ámbito
9, su ejecutado (ámbito 5) y el IVA leído de `obrctr.ivaide` son suyos (D2, D8). F-099: el
coeficiente por CONTRATO; aquí, el de la partida. F-030: ver D1. No se toca `sigrid-api` ni el
MCP (`describir_tabla` ya sirve la `descripcion` entera).

## 2. Ficheros

**Modificar**
- `etl_sigrid/domain/proyeccion_caja.py` (§4).
- `config/hipotesis_caja.yaml`: `paso_receta` en las 23; H03 y H08 a `PERFIL_MESES`; H24, H25;
  textos de H10, H12 y H15 (§6); cabecera (campos, unidad nueva, cómo se da el 10 % por obra).
- `etl_sigrid/infrastructure/config/hipotesis_caja_yaml.py` y
  `etl_sigrid/infrastructure/postgres/hipotesis_caja_sql.py`: leer y cargar `paso_receta`.
- `sql/tesoreria/00_setup.sql` (al final, idempotente): `ALTER TABLE tesoreria.hipotesis_caja
  ALTER COLUMN unidad TYPE VARCHAR(20)` (`PERFIL_MESES` tiene 12) y `ADD COLUMN IF NOT EXISTS
  paso_receta VARCHAR(12)`; en `devengo_pendiente_partida`, `ADD COLUMN IF NOT EXISTS
  coeficiente_venta NUMERIC(12,6)`, `fuente_coeficiente VARCHAR(13)`,
  `pendiente_con_coeficientes NUMERIC(18,2)`; en `devengo_pendiente_obra_mes`,
  `importe_pendiente_con_coeficientes NUMERIC(18,2)` y `coeficiente_venta NUMERIC(12,6)`; en
  `condiciones_contrato_cliente`, `importe_adjudicado NUMERIC(18,2)`.
- `sql/tesoreria/06_condiciones_contrato_cliente.sql`: `o.impadj AS importe_adjudicado` (§5 bis).
- `sql/tesoreria/07_devengo_pendiente.sql` (§5).
- `sql/tesoreria/08_hipotesis_caja_obra.sql`: solo la rama H10 del bloque SIGRID y el `COMMENT`
  («25», la regla de H10) (§5 bis). H03/H08/H24/H25 no tienen valor SIGRID: el `CROSS JOIN` con
  el catálogo ya publica las 25 por obra.
- `config/diccionario/tesoreria.yaml`: la receta en `hipotesis_caja` (§3) y su columna
  `paso_receta`; columnas nuevas de las dos `devengo_*` y de `condiciones_contrato_cliente`; la
  regla de H10 en `hipotesis_caja_obra`; «23» -> «25» donde se cuente.
- `config/diccionario/00_global.yaml`: `R-CAJA-HIPOTESIS` (§7), `R-VENTA-COEFICIENTES` (`ambito`
  + las dos `devengo_*`; la excepción del contraste de H12, §7), `version` 62 -> 63.
- Tests que fijan F-140: `test_f140_hipotesis.py` (valores de H03/H08, rango `1..26`, sentidos),
  `test_f140_paso.py` (`23` -> `25`), `test_f140_sql.py` (`23` -> `25`, columnas de `06` y `07`,
  la rama H10 de `08`), `test_f140_diccionario.py` (la ficha «dice las 23» -> 25).
- `docs/CONVENTIONS.md` y `docs/ARCHITECTURE.md` (excepción de D1, el coeficiente, H10 por peso),
  `CLAUDE.md` (mapa: 25 hipótesis, la receta), `azure-apps/datamart_seg_anual.md` (columnas
  nuevas y la receta); commit local en `azure-apps`, sin push.

**Crear**: `tests/test_f150_{receta,coeficiente,perfil,sql,diccionario,h10,iva}.py`.

**No se tocan**: `sql/stg/*`, `sql/mart/*` (el 9 NO entra en `stg.plan_mensual`: D2), `01`-`05`,
permisos (`grants.py`, roles: el esquema ya se concede entero), `main.py`,
`domain/diccionario.py` (la receta va en `descripcion`), `tests/test_f147_presupuesto_contexto.py`
salvo que la medida baje más de 1.000 (no pasará: −9). No se fija el IVA de ninguna obra (D8).

## 3. La receta (texto de la ficha de `tesoreria.hipotesis_caja`, tras su párrafo actual)

El implementer la copia tal cual (puede ajustar la redacción sin perder ninguna pieza que fijan
los tests de R3-R5 y R28). Va en `descripcion`, que `describir_tabla` sirve entera y F-147 no mide.

> **LA RECETA: DE DEVENGO A CAJA, EN ESTE ORDEN** (F-150). Cada hipótesis dice en `paso_receta`
> en qué paso se aplica; decláralas TODAS con valor y nivel (`R-CAJA-HIPOTESIS`). COSTE se paga
> (PAGO) y VENTA se cobra (COBRO). Los perfiles (`PERFIL_MESES`, pares `[meses, porcentaje]` que
> suman 100) reparten el importe ENTERO: `[[0, 100]]` es todo en el mes de partida y
> `[[1, 50], [2, 50]]`, la mitad uno y dos meses después. Redondea solo al final.
> 1. DEVENGO: el del mes, `importe_pendiente` de `tesoreria.devengo_pendiente_obra_mes` (H18; o
>    `importe_plan_restante`), lo retrasado sin perfil según H19, situado el día H23. Sin IVA.
> 2. DOCUMENTO: el devengo de cada mes se factura (pago, perfil H03) o se certifica (cobro,
>    perfil H08). Su mes es el del IVA del paso 6.
> 3. COEFICIENTES (solo cobro): se certifica y se cobra CON coeficientes:
>    `importe_pendiente_con_coeficientes` (por partida, `pendiente_con_coeficientes` de
>    `tesoreria.devengo_pendiente_partida`), nunca un coeficiente medio de obra; jamás la compares
>    con el coste ni con lo ejecutado (`R-VENTA-COEFICIENTES`).
> 4. PLAZO: desde el documento, la forma de pago del contrato (H01, `condiciones_contrato_compra`;
>    con varios vencimientos, H15) o, sin contrato, la de su categoría (H02), con los días fijos y
>    meses sin pago del proveedor (H04) y el retraso real (H05); el cobro, a H09
>    (`condiciones_contrato_cliente`) y menos la morosidad H22. Cada vencimiento se reparte en
>    meses con el perfil H24 (pago) o H25 (cobro).
> 5. RETENCIÓN: se descuenta de cada pago o cobro el porcentaje H06 (proveedor) o H10 (cliente)
>    sobre la base SIN IVA, y se devuelve según H07 o H11.
> 6. IVA: cada documento lleva el IVA H12 (venta) o H13 (compra) sobre su base, que se cobra o
>    paga con sus vencimientos; la liquidación con Hacienda (repercutido menos soportado, por el
>    mes del documento) va según H14. **Si H12 sale DEFECTO, contrástalo** (la vivienda va al
>    10 %): `e` = los efectos COBRO de la obra en `tesoreria.efectos`, no BAJA, cobrados o no
>    (CON IVA; solo lo cobrado se retrasa); `p` = su venta producida (`mart.fact_seguimiento_mensual`,
>    «Venta Real», `importe_mes`) hasta el mes del último efecto; `k` = Σ con / Σ sin coeficientes
>    de la obra en `devengo_pendiente_obra_mes`. IVA implícito = `e / (p × k) − 1`: desde el 17 %,
>    H12 casa; hasta el 14 %, apunta al 10 %: avísalo y pide el valor; entre medias o sin `p`,
>    `e` o `k`, «sin contraste». Es una prueba: ese cociente no se enseña ni se suma.
> 7. CARTERA, SIN DUPLICAR: suma lo PREVISTO vivo de `tesoreria.efectos` en su vencimiento (H16;
>    el previsto antiguo, H17) y los albaranes sin facturar (H20), y quita del devengo del primer
>    mes pendiente lo emitido tras el cierre (H21, `cartera_emitida_tras_cierre`, que va CON IVA).

Con F-151 la regla mandará usar la función; esta receta quedará para los cálculos especiales.

## 4. Dominio (`domain/proyeccion_caja.py`, sin infraestructura)

- `PASOS_RECETA = ("DEVENGO", "DOCUMENTO", "COEFICIENTES", "PLAZO", "RETENCION", "IVA",
  "CARTERA")`. `paso_receta` pasa a `_CAMPOS_OBLIGATORIOS`; `_errores_de_fila` rechaza uno fuera
  de la lista. `Hipotesis` gana `paso_receta: str = ""` AL FINAL; `construir_catalogo` lo rellena.
- `UNIDADES` += `"PERFIL_MESES"`; `_error_de_valor` llama a `_error_de_perfil(valor)`: lista no
  vacía de pares `[meses, porcentaje]` (lista o tupla de 2); `meses` entero (no booleano) entre 0 y
  `MAX_MESES_PERFIL = 120`, estrictamente crecientes; `porcentaje` número > 0 y <= 100 con 2
  decimales como mucho; suma exacta 100 (con `Decimal(str(p))`). Cada fallo, su mensaje. Vale para
  `valor_defecto` y para la sección `obras` (mismo `_error_de_valor`).
- `FUENTES_COEFICIENTE = ("CERTIFICACION", "VENTA")`; `AMBITO_COEFICIENTE = {"CERTIFICACION": 9,
  "VENTA": 11}`. `coeficiente_venta(importe_cert, oficial_cert, importe_venta, oficial_venta) ->
  tuple[Decimal | None, str | None]`: el del 9 si su importe no es `None` ni 0, si no el del 11,
  si no `(None, None)`; `oficial` `None` -> el propio importe; `ROUND(oficial / importe, 6)`.
- `importe_con_coeficiente(importe, coeficiente) -> Decimal`: `_redondear(importe × coeficiente)`.
  El reparto en meses del importe con coeficientes es el MISMO `repartir_pendiente` de F-140.
- **H10 (D9)**: `PESO_MINIMO_RETENCION = Decimal(50)`; `valor_h10_sigrid(contratos) -> tuple[Decimal
  | None, str | None]`, `contratos` = pares `(retencion_porcentaje, importe_adjudicado)` de una
  obra. (1) Todos con valor y el mismo -> ese, `MOTIVO_H10_UNICO` (F-140). (2) Si no: «con
  retención» = porcentaje > 0; si dan un único valor y `100 × Σ adjudicado con retención / Σ
  adjudicado` >= 50 (adjudicado `None` = 0; denominador <= 0 -> nada) -> ese, `MOTIVO_H10_PESO`.
  (3) Si no, `(None, None)`. `resolver_hipotesis` no cambia de orden (MANUAL > SIGRID > DEFECTO).
- **H12 (D8)**: `UMBRAL_IVA_GENERAL = Decimal(17)`, `UMBRAL_IVA_REDUCIDO = Decimal(14)`;
  `contraste_iva_venta(emitido, producido, coeficiente) -> tuple[Decimal | None, str]`: IVA
  implícito `100 × (e / (p × k) − 1)` a 2 decimales y veredicto `GENERAL` (>= 17), `REDUCIDO`
  (<= 14), `SIN_CONTRASTE` (entre medias, o `p`/`k` `None` o <= 0, o `e` <= 0). La usa T11 para
  medir; la receta lleva los mismos umbrales (test que cruza texto y constantes).

El SQL no llama a Python: lleva los literales (`'CERTIFICACION'`, `'VENTA'`, `9`, `11`, `ROUND(…,
6)`, el orden del `COALESCE`, el `50`, los dos motivos) y `test_f150_sql.py` / `test_f150_h10.py`
los comparan con el dominio (patrón de F-135).

## 5. SQL: `07_devengo_pendiente.sql`

En la misma transacción, sin cambiar los pasos de F-140 salvo para añadir columnas:
- **2 bis · `_dev_coef`** (tras `_dev_plan`): por (obra, partida) de VENTA, desde `stg.presupuesto
  pp JOIN _dev_version v ON pp.obra_id = v.obra_id AND pp.ambito_id IN (9, 11) AND pp.fase_num =
  v.version_master WHERE v.concepto = 'VENTA'`: `SUM(importe)` y `SUM(importe_oficial)` de cada
  ámbito (`FILTER`); coeficiente del 9 si su importe no es 0, si no el del 11 (`ROUND(oficial /
  importe, 6)`), y `fuente_coeficiente`. `ANALYZE`. Índice `idx_pres_obra_amb` (R9).
- **4 · `_dev_partida`** gana `coeficiente_venta`, `fuente_coeficiente` y
  `pendiente_con_coeficientes = ROUND(pendiente * coeficiente_venta, 2)` (NULL en COSTE).
  **Guarda** `DO`: partida VENTA con `pendiente > 0` sin coeficiente -> `RAISE` con su recuento
  (D6; hoy 0: el plan de V sale del importe del 11 en V).
- **5 · `_dev_reparto`** gana `pendiente_con_coef`: en `partes`, `ROUND(d.pendiente_con_coeficientes
  * pr.importe_mes / d.total_perfil, 2)` y el resto al último mes (mismo `ROW_NUMBER`); en
  `sin_perfil`, entero al primer mes. `devengo_pendiente_obra_mes` suma
  `importe_pendiente_con_coeficientes` (NULL en COSTE) y `coeficiente_venta = ROUND(con / sin,
  6)` (NULL si `importe_pendiente` = 0). **La guarda de la suma** se extiende: por (obra,
  concepto) VENTA, la suma mensual con coeficientes iguala la de la partida al céntimo.
- `COMMENT ON TABLE` de las dos, al día. Ninguna columna nueva casa con `PATRON_COLUMNA_DE_CAJA`.

Coste estimado +10-60 s sobre los 118,9 s de `devengo_pendiente` (26-10); se mide (R21).

## 5 bis. H10 por peso del adjudicado (D9): `06` y `08`

- `06`: `o.impadj AS importe_adjudicado` (`raw.obrctr` ya ingiere `impadj`; solo excluye `tex` y
  `obs`). Sin IVA, tal cual Sigrid; la ficha lo dice y `agregacion: suma` por obra.
- `08`, rama H10 del bloque SIGRID: por obra, `CASE` (1) la regla de F-140 sin cambios; (2) si no,
  `count(DISTINCT valor) FILTER (WHERE valor > 0) = 1` y `100 * SUM(adj) FILTER (WHERE valor > 0)
  / NULLIF(SUM(adj), 0) >= 50` (con `COALESCE(adj, 0)`) -> ese valor; motivo por rama (`CASE`),
  los dos literales = `MOTIVO_H10_UNICO` / `MOTIVO_H10_PESO`. H09 y H11 no cambian.
- Esperado (`progress/spec_F-150.md` §6): 3 obras pasan de DEFECTO 0 a OBRA/SIGRID 5; las 16 de
  F-140 siguen igual. Lo contrasta T11 en solo lectura.

## 6. El catálogo (`config/hipotesis_caja.yaml`)

`paso_receta` de las 25: DEVENGO H18, H19, H23 · DOCUMENTO H03, H08 · COEFICIENTES ninguna (el
coeficiente es dato) · PLAZO H01, H02, H04, H05, H09, H15, H22, H24, H25 · RETENCION H06, H07,
H10, H11 · IVA H12, H13, H14 · CARTERA H16, H17, H20, H21.

| Código | Cambio | Unidad | Defecto (equivale a F-140) | `fuente_defecto` |
|---|---|---|---|---|
| H03 | Perfil del mes de devengo a la factura del proveedor | PERFIL_MESES | `[[0, 100]]` | todo en el mes de devengo (propuesta, sin medir) |
| H08 | Perfil del mes de producción a la certificación | PERFIL_MESES | `[[1, 100]]` | todo al mes siguiente (propuesta, sin medir) |
| H24 | NUEVA · Reparto en meses de cada vencimiento de PAGO | PERFIL_MESES | `[[0, 100]]` | sin reparto; Sigrid no lo guarda (6 contratos con varios vencimientos) |
| H25 | NUEVA · Reparto en meses de cada vencimiento de COBRO | PERFIL_MESES | `[[0, 100]]` | sin reparto; 0 contratos con el cliente con varios vencimientos |

Las cuatro `validado: false`, `admite_obra: true`; H24 y H25 con `ingrediente:
tesoreria.plazos_forma_pago`. Ejemplos en la cabecera: certificar la mitad al mes siguiente y la
otra a los dos meses es `[[1, 50], [2, 50]]` en H08; cobrar cada certificación en dos plazos, el
primero a los tres meses, `[[3, 50], [4, 50]]` en H25. H03/H08 mueven el DOCUMENTO (y su IVA);
H24/H25 solo el dinero. Un inicio diferido es un primer par con `meses` > 0.

Textos (valores sin cambio): **H10** `fuente_defecto` añade la regla del peso (≥ 50 % del
adjudicado, D9). **H12** (D8) `fuente_defecto`: «Tipo general. Sigrid no da el 10 % de la
vivienda (`impiva / impadj`: 21 % en 5 obras, 0 % en 13, 10 % en ninguna): Control de Costes lo
fija por obra en `obras`; si sale DEFECTO, la receta (paso 6) lo contrasta». La cabecera del YAML
da el ejemplo `{clave_obra, codigo: H12, valor: 10, motivo: vivienda, fecha}` SIN ninguna obra
real: la lista de obras de vivienda es MANUAL (Control de Costes, T16). **H15** (D10)
`descripcion` añade: «solo formas de Sigrid con varios vencimientos; con uno, no aplica».

## 7. El diccionario y el presupuesto de F-147

`R-CAJA-HIPOTESIS` · `resumen` (223 caracteres, hoy 230): «No hay caja proyectada: sigue la
receta de la ficha de `tesoreria.hipotesis_caja`, sin repetir la cartera, y declara TODAS las
hipótesis de `tesoreria.hipotesis_caja_obra` con valor y nivel: DEFECTO, OBRA o USUARIO
(manda).» «Sin IVA el devengo» pasa al paso 1 de la receta. `regla`: empieza por «Sigue la
RECETA de la ficha de `tesoreria.hipotesis_caja`, en su orden» y conserva lo demás; `motivo`
gana la frase de F-150 (la IA improvisaba el orden). `ambito` sin cambios.

`R-VENTA-COEFICIENTES` · `ambito` + las dos `devengo_*`; `regla` gana al final la ÚNICA excepción
(D8): «el contraste de H12 del paso 6 de la receta, que solo da un veredicto sobre el IVA y no
enseña, suma ni compara ninguna cifra de venta». `resumen` sin cambios (F-147 no se mueve).

Fichas: `hipotesis_caja` (receta, columna `paso_receta` con sus 7 `valores`, grano «25»; sus
`ejemplos_preguntas` empiezan por «Como se pasa paso a paso el devengo de una obra a caja», 54
caracteres frente a los 56 de la que sustituye en el segundo puesto); `hipotesis_caja_obra`
(«25», 525 filas esperadas, la regla de H10); `condiciones_contrato_cliente.importe_adjudicado`;
las dos `devengo_*` con sus columnas nuevas (unidad EUR, `suma` en los importes, `no_sumable` en
el coeficiente, `nulo_significa`: COSTE o sin pendiente) y la advertencia de
`R-VENTA-COEFICIENTES`. Presupuesto: 30.873 − 7 − 2 = **30.864**: baja 9, sin tocar el tope.

## 8. Despliegue (MANUAL, tras el review) y riesgos

Imagen con tag fechado y job apuntado (`infra/85_update_job.ps1`); `build-tesoreria` desde el
puesto (R21); contraste R20; `publicar-diccionario` con la imagen ya en el job;
`check-diccionario`, `check-declarados`, `check-unicidad`; reiniciar el MCP; R22 en conversación
nueva. DDL aditivo: la vuelta atrás es el tag `r20261026-2111`.

**Riesgos.** (1) La IA no abre la ficha: el `resumen` y la `regla` la nombran. (2) Doble reparto
(`30 60 90` y H24): la receta los compone; la ficha de H24 lo advierte. (3) Tests de F-140 que
fijan 23, H03/H08 y la rama H10: se actualizan en su tarea, con el porqué en el commit. (4) **El
contraste de H12 puede no discriminar** (`k` es el del pendiente; el cobro de la obra puede no
estar todo en su `obra_id`; el retraso del cobro): T11 lo mide en las 21 obras ANTES de T9; si
las 5 obras con `impiva` al 21 % no salen `GENERAL`, el implementer PARA y el líder lo vuelve a
proponer al humano (no se ajustan umbrales a ojo). (5) H10 por peso usa `impadj` sin IVA y sin
modificados: basta para un umbral del 50 % (medido 99,5-100 %).

## 9. Decisiones cerradas (el humano, 2026-10-27)

- **D1 · A.** La receta en la ficha, con excepción acotada en las convenciones: sin objeto nuevo.
- **D2 · A.** El 9 da solo el coeficiente (11 de respaldo): el importe a certificar es F-040.
- **D3 · A.** El 9 en la misma versión V: existe en las 21 obras y no mezcla versiones.
- **D4 · A.** Obra-mes con importe con coeficientes y cociente: cuadra y vale en las 5 mixtas.
- **D5 · A.** `PERFIL_MESES`, H03/H08 a perfil, H24/H25: documento e IVA aparte del dinero.
- **D6 · A.** Partida de venta pendiente sin coeficiente: falla cerrado (hoy 0).
- **D7 · A.** Resumen nuevo de `R-CAJA-HIPOTESIS` (223 caracteres): la IA ve la receta siempre.
- **D8 · A, DENTRO de F-150.** Control de Costes fija el 10 % por obra en `obras` (MANUAL, T16)
  y la receta contrasta H12 con lo cobrado frente a la venta producida (§3 paso 6, §4, §7).
- **D9 · A.** H10 SIGRID por peso ≥ 50 % de los contratos con retención (§5 bis): 3 obras a OBRA.
- **D10 · A.** H15 se queda, solo para formas con varios vencimientos: retirarla rompe la lista.
