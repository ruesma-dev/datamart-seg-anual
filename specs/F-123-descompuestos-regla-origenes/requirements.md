<!-- specs/F-123-descompuestos-regla-origenes/requirements.md -->
# F-123 · Requisitos

Corrección de la regla de orígenes de `descompuestos` (F-097, F-120), dictada por
el humano el 2026-10-02: **Estudios es el master 0** (`MASTER_ESTUDIO`); la
«Descomposición» de coste fase 0 solo sobrevive como **respaldo** donde no hay
master 0; **coste fase 0 es la fase viva** y su descompuesto es `PLANIF_JO`.
Mediciones (2026-10-02, solo lectura) y decisiones D1-D8 con su recomendación:
`progress/spec_F-123.md`. Los requisitos marcados **[Dn]** siguen la
recomendación de esa decisión; si el humano decide otra cosa, cambian.

## Glosario

- **Master 0**: la versión 0 del master coste (ámbito 8, `fase_num` 0).
- **Obra con master 0**: la que tiene fila en `descompuestos._versiones_cargadas`
  con `fase_num = 0` (esa tabla solo guarda versiones CON descompuesto en Sigrid).
- **Fase viva**: coste fase 0 (ámbito 3, `fase_num` 0): el presupuesto de coste
  en curso, que el jefe de obra evoluciona día a día.
- **Respaldo**: la «Descomposición» de la fase viva de las partidas sin ningún
  registro enlazado a `dncpro` (el `ESTUDIO` de F-097), publicada solo donde no
  hay master 0.

## Los orígenes

- **R1.** El sistema debe publicar las líneas y el cuadre del master 0 con
  origen `MASTER_ESTUDIO`.
- **R2.** `MASTER_INICIAL` y `ESTUDIO` no deben existir como valor de `origen`
  en `descompuestos.lineas`, `descompuestos.cuadre_partida`, sus `CHECK`, las
  vistas, `ORIGENES` del dominio ni el diccionario.
- **R3.** [D2] Los orígenes deben ser exactamente `ESTUDIO_RESPALDO`,
  `PLANIF_JO`, `MASTER_ESTUDIO`, `MASTER_PRE_ABC` y `MASTER_PLANIF_JO`, iguales
  en `ORIGENES` del dominio y en los dos `CHECK` del SQL.
- **R4.** La regla de `MASTER_PRE_ABC` y `MASTER_PLANIF_JO`, los flags de
  versión y `tipo_version` no deben cambiar.
- **R5.** Cada versión del master, cuatrimestrales incluidas, debe seguir
  publicando su descompuesto troceado del texto de ESA versión (medición y
  factor de la versión, nunca de `dncpro` ni de la fase viva).

## El respaldo de Estudios

- **R6.** [D1] MIENTRAS una obra NO tiene master 0, el sistema debe publicar con
  origen `ESTUDIO_RESPALDO` (ámbito 3, fase 0) las líneas de la «Descomposición»
  de la fase viva de sus partidas sin ningún registro enlazado a `dncpro`: las
  mismas líneas y columnas que el `ESTUDIO` de F-097.
- **R7.** [D1] MIENTRAS una obra tiene master 0, el sistema NO debe publicar
  ninguna línea `ESTUDIO_RESPALDO` de esa obra, tenga o no descompuesto en el
  master 0 la partida.
- **R8.** Ninguna pareja (obra, partida) debe tener a la vez líneas
  `MASTER_ESTUDIO` y `ESTUDIO_RESPALDO`.

## La fase viva

- **R9.** El descompuesto de la fase viva debe ser solo `PLANIF_JO`, sin cambios
  respecto a F-120 (líneas, factor y cuadre).
- **R10.** El cuadre del ámbito 3 fase 0 debe tener una fila `PLANIF_JO` por
  partida hoja con precio y, [D2] SOLO en las obras sin master 0, otra
  `ESTUDIO_RESPALDO`.
- **R11.** [D2] El estado `SUSTITUIDO_POR_PLANIFICACION` debe conservarse y
  darse solo en filas `ESTUDIO_RESPALDO`: la «Descomposición» de esa partida es
  copia de la planificación y no sirve de respaldo.

## Informar de que Estudios no existe

- **R12.** [D3] El sistema debe publicar `descompuestos.estudios_partida`, una
  fila por (`obra_id`, `partida_id`) de cada partida hoja con precio de la fase
  viva o del master 0, o con líneas de Estudios, con `via_estudios` en
  (`MASTER_ESTUDIO`, `ESTUDIO_RESPALDO`, `NO_EXISTE`), `obra_tiene_master_0`,
  `num_lineas` y `motivo_no_existe`.
- **R13.** CUANDO la partida tiene líneas `MASTER_ESTUDIO`, `via_estudios` debe
  ser `MASTER_ESTUDIO`; CUANDO las tiene `ESTUDIO_RESPALDO`, `ESTUDIO_RESPALDO`;
  en ambos casos `motivo_no_existe` NULL y `num_lineas` el de ese origen.
- **R14.** SI la partida no tiene líneas de ninguno de los dos, ENTONCES
  `via_estudios` debe ser `NO_EXISTE`, `num_lineas` 0 y `motivo_no_existe`:
  `MASTER_0_SIN_DESCOMPUESTO` (obra con master 0, partida con precio en él),
  `PARTIDA_FUERA_DEL_MASTER_0` (obra con master 0, partida que no está en él),
  `SUSTITUIDO_POR_PLANIFICACION` (obra sin master 0, «Descomposición» copiada de
  la planificación) o `SIN_DESCOMPUESTO` (obra sin master 0, sin texto).
- **R15.** Una función pura del dominio, `resolver_estudios(...)`, debe aplicar
  R13-R14 con la misma regla que el SQL (espejo, probado sin base de datos).

## Consumo

- **R16.** [D4] `descompuestos.v_pbi_estudio` debe publicar Estudios ya
  resuelto: las líneas `MASTER_ESTUDIO` y `ESTUDIO_RESPALDO`, con sus columnas
  de hoy en el mismo orden y `origen` como ÚLTIMA columna (`CREATE OR REPLACE
  VIEW` solo admite columnas nuevas al final).
- **R17.** `v_pbi_planif_jo` y `v_pbi_master_planif_jo` no deben cambiar.
- **R18.** [D4] `descompuestos.elementos` debe contar las líneas por origen en
  `lineas_estudio_respaldo`, `lineas_planif_jo`, `lineas_master_estudio`,
  `lineas_master_pre_abc` y `lineas_master_planif_jo`; `lineas_estudio` y
  `lineas_master_inicial` dejan de existir.

## Migración de lo ya cargado

- **R19.** CUANDO `build_descompuestos` corre sobre una base con los orígenes de
  F-120, el sistema debe, sin `DROP` ni `TRUNCATE` de `lineas` ni de
  `cuadre_partida`: pasar a `MASTER_ESTUDIO` las filas `MASTER_INICIAL` de las
  dos tablas, borrar las `ESTUDIO` y sustituir los dos `CHECK` de origen.
- **R20.** La migración debe ser idempotente: una segunda ejecución no debe
  fallar ni volver a crear los `CHECK` si ya admiten los orígenes nuevos.
- **R21.** `descompuestos._des_texto` no debe perder el texto del ámbito 3 ni
  `ingest_descompuestos` dejar de traerlo: `ingest_descompuestos_step.py` no se
  toca, y ningún SQL de la carpeta hace `DELETE`, `DROP` ni `TRUNCATE` de
  `_des_texto` ni de `_versiones_cargadas`.
- **R22.** [D5] El sello de troceado cambia (deja de ser `7cad480aee614b2a`):
  el retroceo de las versiones cargadas no debe releer Sigrid ni tocar
  `_des_texto`, y debe dejar las mismas líneas del master que había, salvo el
  origen del master 0.

## Documentación

- **R23.** [D6] `config/diccionario/00_global.yaml` debe tener una regla
  `R-FASE-VIVA` que explique qué es la fase viva (coste fase 0, la que el jefe de
  obra evoluciona día a día; sin historia; su descompuesto es `PLANIF_JO`; las
  fotos fijas son las versiones del master y Estudios es la 0), y
  `R-FAS-AMBIGUO` y las dos menciones de «Previsto vivo» de `stg.yaml` deben
  remitir a ella.
- **R24.** `R-DESCOMPUESTO-ORIGEN`, la entrada `descompuestos` de `esquemas` y
  las fichas de `descompuestos.yaml` (`lineas`, `cuadre_partida`, `elementos`,
  `v_pbi_estudio` y la nueva `estudios_partida`) deben describir la regla nueva:
  Estudios es `MASTER_ESTUDIO` con la medición de Estudios; `ESTUDIO_RESPALDO`
  tiene precios de Estudios pero medición VIVA y solo existe en obras sin master
  0; dónde mirar si Estudios no existe.
- **R25.** `version` de `00_global.yaml` debe subir de 39 a 40.
- **R26.** `docs/ARCHITECTURE.md` (tabla de pestañas y orígenes, respaldo y
  fase viva), `CLAUDE.md` (mapa: orígenes de `descompuestos/`), la ayuda de
  `build-descompuestos` en `main.py` y `azure-apps/datamart_seg_anual.md` deben
  decir la regla nueva; ninguno debe nombrar `MASTER_INICIAL` como origen vigente.

## Verificación contra la base (MANUAL del humano)

- **R27.** Antes y después del despliegue debe medirse cuántas partidas y obras
  tienen Estudios por cada vía (previsión en `progress/spec_F-123.md` §3:
  `MASTER_ESTUDIO` 36.355 partidas en 170 obras; `ESTUDIO_RESPALDO` 6.544 en 44).
- **R28.** Testigos: la 0726 (obra 2817778), partida 419079, debe salir en
  `v_pbi_estudio` con 10 líneas `MASTER_ESTUDIO` que suman 134,35 por unidad y
  ninguna `ESTUDIO_RESPALDO`; la 0713 (obra 2645007) no debe tener ninguna línea
  `MASTER_ESTUDIO` y debe tener sus 687 partidas (1.774 líneas) como
  `ESTUDIO_RESPALDO`.
- **R29.** Debe quedar medido, por `tipo_version`, en cuántas partidas CUADRA
  del master `sum(importe_total)` coincide con `stg.presupuesto.importe` de su
  versión (medido en parte: `progress/spec_F-123.md` §4).
