> # ⛔ SPEC RETIRADA el 2026-09-09, ANTES DE IMPLEMENTAR NADA
>
> El humano paró F-071 al leer esta spec: **«no vamos a borrar nada de
> momento, vamos a seguir dejando todo. Quitamos esta feature.»** La purga
> nocturna (R20) y el acotado del censo (R19) **no se hacen**. F-071 ya no
> existe en `harness/features.json`.
>
> **Esta carpeta se conserva solo por lo que costó medir**, y esa evidencia
> pasa a alimentar **F-072** (el censo semántico) y **F-073** (las tablas
> nuevas y el enriquecimiento): las cifras del §1 de `design.md`, que tres de
> los ocho campos de dirección no son dirección de la obra, y que el municipio
> y la provincia viven en `raw.auxmun` y `raw.auxpro`. **Lo que sobrevive es
> el enriquecimiento —la dirección y las marcas— sin borrar ni filtrar nada.**
>
> No implementes desde aquí. Ver `progress/current.md`.

<!-- specs/F-071-obras-sin-datos/requirements.md -->
# F-071 · Requisitos

**Marcar y declarar, no borrar.** Dos capas: la que consume la IA (marcas,
superficie por defecto, dirección y regla dura) y el censo interno de la
ventana, que la IA no ve. Detalle técnico y medidas: `design.md`.

## Cifras de partida (medidas contra Azure el 2026-09-09, solo lectura)

| qué | cuánto |
|---|---|
| `mart.v_pbi_dim_obra` / `stg.obras` | **583** |
| de ellas, con presupuesto | **498** |
| de ellas, con plan mensual | **349** |
| de ellas, con hechos en `mart.fact_seguimiento_mensual` | **349** |
| de ellas, sin presupuesto **ni** plan | **85** |
| `maestro.obras` (universo sin filtrar) | **921** |
| fichas del censo de la ventana (`_meta.obra_build`) | **921** |
| fichas del censo **fuera** de `stg.obras` | **338** |
| de esas 338, con filas en `stg.presupuesto` / `stg.plan_mensual` | **230** / **19** |
| filas huérfanas en `stg.presupuesto` / `stg.plan_mensual` | **390.028** / **82.862** |

Coinciden con lo medido el 2026-09-07 en `progress/explore_F-025_coste_fijo.md`.
Son las constantes de los tests de aceptación.

## Capa 1 · Lo que consume la IA

- **R1.** El sistema debe publicar en `mart.v_pbi_dim_obra` las columnas
  `tiene_presupuesto` y `tiene_plan_mensual`, calculadas por existencia de
  filas en `stg.presupuesto` y `stg.plan_mensual`.
- **R2.** El sistema debe publicar la vista nueva `mart.v_obras_con_datos`,
  que trae **solo** las obras con al menos un hecho en
  `mart.fact_seguimiento_mensual`, con las mismas columnas que la dimensión.
- **R3.** MIENTRAS una obra exista en `stg.obras` y no tenga datos, el sistema
  debe seguir publicándola en `mart.v_pbi_dim_obra` con sus dos marcas a
  `FALSE`: encontrable por `codigo_obra` y por `nombre_obra`.
- **R4.** SI un cambio de esta feature quitara o filtrara una fila o una
  columna de cualquier vista `v_pbi_*` existente, ENTONCES el cambio es
  incorrecto: solo se añaden columnas y objetos nuevos (F-034, Power BI).
- **R5.** El sistema debe seguir publicando **583** filas en
  `mart.v_pbi_dim_obra` y **349** obras distintas en
  `mart.fact_seguimiento_mensual` después del cambio.

## Capa 1 bis · La dirección de la obra

- **R6.** El sistema debe materializar en `stg.obras` la dirección de la obra
  leída de `raw.obr`: `dir1`, `dir2`, `codigo_postal`, `municipio`,
  `provincia` y `direccion_completa`, con **los mismos nombres y el mismo
  significado** que ya tiene `maestro.proveedores`.
- **R7.** El sistema debe publicar esas seis columnas en
  `mart.v_pbi_dim_obra`, en `mart.v_obras_con_datos` y en `maestro.obras`.
- **R8.** El sistema debe componer `direccion_completa` como el texto de
  origen (`obr.dir`) cuando venga informado y, solo cuando no lo esté, como la
  composición de `dir1`, `dir2`, `codigo_postal`, `municipio` y `provincia`.
  **Nunca dos formas distintas** de decir lo mismo en la misma base.
- **R9.** El sistema debe medir, antes de publicar, cuántas de las 583 obras
  traen informado cada campo de dirección de `raw.obr`, y dejar la medición
  escrita en `specs/F-071-obras-sin-datos/mediciones.md`.
- **R10.** SI un campo de dirección viene informado en **menos de un tercio**
  de las 583 obras, ENTONCES no se publica como columna propia y el motivo
  queda escrito en `mediciones.md` y en la ficha del objeto.
- **R11.** El sistema debe declarar en la ficha de cada columna de dirección
  publicada **el porcentaje de obras que la traen informada**, con su fecha de
  medición.
- **R12.** El sistema NO debe publicar `obr.diride`, `obr.perdir` ni
  `obr.entdiride` como dirección de la obra: son director de obra, persona de
  contacto del director y dirección **del cliente** (ver `design.md` §DA-2).
- **R13.** SI la medición de R9 demuestra que la obra no tiene dirección
  utilizable en el origen, ENTONCES no se publica columna vacía alguna y se
  declara en el diccionario que el dato no existe, en vez de publicarlo.
- **R14.** El sistema debe corregir la cabecera de
  `sql/maestro/01_obras.sql`, que hoy afirma que las obras no tienen dirección
  en Sigrid.

## Capa 1 ter · El diccionario

- **R15.** El sistema debe publicar la regla dura `R-OBRA-SIN-DATOS` en
  `config/diccionario/00_global.yaml`, diciendo con qué objeto se cuenta, con
  cuál se busca, y que una obra sin datos se responde **«existe, sin datos de
  seguimiento»** y nunca «no existe».
- **R16.** El sistema debe dejar en `R-UNIVERSO-OBRA` una referencia cruzada a
  la regla nueva, para que quien lea una no ignore la otra.
- **R17.** El sistema debe actualizar las fichas de `mart.v_pbi_dim_obra`,
  `stg.obras` y `maestro.obras`, crear la de `mart.v_obras_con_datos`, y subir
  `version` en `00_global.yaml`.
- **R18.** CUANDO se pregunte al MCP «¿cuántas obras tenemos?» **sin explicarle
  nada en el prompt**, el sistema debe responder con las obras con datos o con
  las dos cifras diciendo qué es cada una, y a «¿dónde está la obra X?» debe
  responder con su dirección.

## Capa 2 · El censo de la ventana

- **R19.** El sistema debe acotar el censo de `SQL_ESTADO_OBRAS` a las fichas
  presentes en `stg.obras`, dejando fuera plantillas, códigos repetidos y
  fichas en blanco.
- **R20.** CUANDO el censo se acote, el sistema debe purgar de
  `stg.presupuesto` y de `stg.plan_mensual` las filas de obras que no están en
  `stg.obras`, de forma idempotente y **cada noche**: si no, esas filas quedan
  congeladas para siempre porque nadie las volvería a tocar.
- **R21.** El sistema debe dejar medido, con el comando `ventana-plan`, cuántas
  obras se dejan de reprocesar cada noche: censo y motivos antes y después.
- **R22.** El sistema NO debe cambiar el trato de las obras que **sí** están en
  `stg.obras` y entran por el motivo `sin_filas`: una obra a medio construir se
  sigue completando. La ventana no cambia de criterio, solo de censo.
- **R23.** SI el acotado dejara fuera del censo alguna obra que hoy tiene
  hechos en `mart.fact_seguimiento_mensual`, ENTONCES el cambio es incorrecto.

## Documentación y cierre

- **R24.** El sistema debe actualizar `docs/ARCHITECTURE.md` y
  `azure-apps/datamart_seg_anual.md` con el censo nuevo, la superficie nueva y
  la dirección publicada.
- **R25.** El sistema debe terminar con `bash harness/init.sh` en verde y con
  fase RED documentada y campaña de mutación con supervivientes analizados
  (rigor `estandar`, `CHECKPOINTS.md` C4 bis).
