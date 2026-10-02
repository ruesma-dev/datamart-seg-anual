<!-- progress/spec_F-123.md -->
# F-123 · Resumen de la spec, mediciones y decisiones abiertas

**Segunda versión (2026-10-02).** La primera (respaldo `ESTUDIO_RESPALDO`, tabla
`estudios_partida`, motivos de «no existe», D1-D8) la rechazó el humano por
complicada y dictó la regla simple. Spec: `specs/F-123-descompuestos-regla-origenes/`
(requirements R1-R24, design, tasks T1-T19). Las mediciones son las de la
primera versión, **2026-10-02** en solo lectura contra Azure por el MCP
(diccionario v39, sello `7cad480aee614b2a`, 3.025 versiones cargadas en 197
obras); no se ha vuelto a medir. Solo se ha escrito en este repositorio.

## 0 · En una frase

Donde la obra tiene master 0 con descompuesto (170 obras), Estudios es el master
0 y su origen pasa de `MASTER_INICIAL` a `MASTER_ESTUDIO`; `ESTUDIO` se publica
como hoy solo en las 44 obras sin él; vista nueva `v_pbi_master_estudio`; y el
diccionario (v40) explica la fase viva. Solo cambia el esquema `descompuestos`.

## 1 · Qué sale respecto a la primera versión

Fuera: `ESTUDIO_RESPALDO`, `descompuestos.estudios_partida` y `resolver_estudios`,
los motivos de `NO_EXISTE`, el renombrado de `lineas_estudio`, el cambio de
`v_pbi_estudio`, el fichero `07` y el octavo sub-paso, la regla aparte
`R-FASE-VIVA` y los cambios de `R-FAS-AMBIGUO`/`stg.yaml`. «No existe» = el
cuadre del origen de Estudios en `SIN_DESCOMPUESTO`, como ya hoy.

## 2 · Foto de hoy (el «antes» de T14)

| Origen | Líneas | Obras | Partidas | Versiones |
|---|---|---|---|---|
| ESTUDIO | 99.049 | 174 | 35.523 | — |
| PLANIF_JO | 288.960 | 246 | 111.392 | — |
| MASTER_INICIAL | 107.061 | 170 | 36.355 | 170 |
| MASTER_PRE_ABC | 1.794.624 | 173 | 76.931 | 1.665 |
| MASTER_PLANIF_JO | 2.497.224 | 59 | 45.233 | 1.190 |

Cuadre (CUADRA / NO_CUADRA / SIN_DESCOMPUESTO / SUSTITUIDO): ESTUDIO 9.433 /
20.786 / 113.428 / 5.923 (149.570) · PLANIF_JO 79.692 / 14.776 / 55.102 ·
MASTER_INICIAL 34.174 / 675 / 54.299 · MASTER_PRE_ABC 635.328 / 11.812 / 368.250
· MASTER_PLANIF_JO 792.922 / 12.301 / 246.232.

Las 35.523 partidas con ESTUDIO: 26.959 en obras con master 0 y descompuesto en
él (26.833, el 99,5 %, mismas líneas y misma suma por unidad); 1.758 que no
existen en el master 0; 249 con precio y sin descompuesto en él; 13 con precio 0;
1.863 en 11 obras con master pero sin versión 0 con descompuesto (0713); 4.681 en
33 obras sin ningún master. Hay 44 obras sin master 0 (11 + 33), no «33 con la
0713 dentro»: la 0713 tiene 10 versiones del master, ninguna la 0.

## 3 · Previsión del «después»

| | Líneas | Obras | Partidas |
|---|---|---|---|
| `MASTER_ESTUDIO` | 107.061 | 170 | 36.355 |
| `ESTUDIO` | 11.783 | 44 | 6.544 |
| Estudios en total (las dos vistas) | 118.844 | 214 | 42.899 |
| Dejan de publicarse como `ESTUDIO` | 87.266 | 130 | 28.979 |

De las 28.979: 26.959 pasan a `MASTER_ESTUDIO` con las mismas líneas; 2.020 se
quedan sin Estudios (1.758 no están en el master 0; 249 + 13 salen en el cuadre
`MASTER_ESTUDIO` como `SIN_DESCOMPUESTO`). Cuadre `ESTUDIO`: 51.206 filas (2.710
CUADRA, 2.654 NO_CUADRA, 45.739 SIN_DESCOMPUESTO, 103 SUSTITUIDO); el de
`MASTER_ESTUDIO`, el mismo de `MASTER_INICIAL`. `PLANIF_JO` y el resto del master,
igual. (Las líneas que dejan de publicarse salen por diferencia, 99.049 − 11.783.)

## 4 · Mediciones del master (R24)

`sum(importe_total)` de las líneas frente a `stg.presupuesto.importe` de la misma
fila, en las partidas CUADRA:

| Qué | CUADRA | A 5 céntimos | Al 1 por mil (mín. 1 EUR) |
|---|---|---|---|
| Master 0, todas las obras | 34.174 | 26.534 (77,6 %) | 33.076 (96,8 %) |
| 0713 · Cuatrimestral (1 versión) | 1.872 | 1.724 | 1.861 (99,4 %) |
| 0713 · ABC (2) | 3.713 | 3.489 | 3.705 (99,8 %) |
| 0713 · Planif Inicial (1) | 1.849 | 1.755 | 1.847 (99,9 %) |
| 0713 · Cierre mensual (6) | 10.766 | 9.843 | 10.658 (99,0 %) |
| 0726 · Cierre mensual (2) | 2.498 | 2.390 | 2.466 (98,7 %) |

El master entero por `tipo_version` no cabe en el tiempo del MCP: T17, por `psql`
(tras el despliegue, con `MASTER_ESTUDIO`):

```sql
WITH s AS (SELECT presupuesto_id, min(tipo_version) AS tipo_version, sum(importe_total) AS suma
           FROM descompuestos.lineas WHERE ambito_id = 8 GROUP BY 1)
SELECT s.tipo_version, count(*) AS cuadra,
       count(*) FILTER (WHERE abs(s.suma - p.importe) <= greatest(1, abs(p.importe) * 0.001)) AS coincide
FROM s JOIN descompuestos.cuadre_partida c ON c.presupuesto_id = s.presupuesto_id
                                          AND c.ambito_id = 8 AND c.estado = 'CUADRA'
JOIN stg.presupuesto p ON p.presupuesto_id = s.presupuesto_id GROUP BY 1 ORDER BY 1;
```

## 5 · Aviso a Juan Romero y Elena Díaz (T13, antes de desplegar)

> Cambia la lectura de `descompuestos` (fecha: la del despliegue). Estudios es el
> master 0: el origen `MASTER_INICIAL` pasa a llamarse `MASTER_ESTUDIO`, y en
> `elementos` la columna `lineas_master_inicial` pasa a `lineas_master_estudio`.
> El origen `ESTUDIO` solo se publica ya en las obras sin master 0 con
> descompuesto (44, la 0713 entre ellas); en las demás, Estudios es
> `MASTER_ESTUDIO`. Vista nueva `v_pbi_master_estudio`, con las mismas columnas
> que `v_pbi_estudio`: juntas son Estudios entero. Filtrar por el nombre antiguo
> devuelve 0 filas sin error. `PLANIF_JO` y los otros orígenes del master no
> cambian.

## 6 · Testigos (R23)

- **0726** (obra 2817778), partida 419079: hoy 10 líneas y 134,35 por unidad en
  ESTUDIO, en MASTER_INICIAL (v0) y en MASTER_PRE_ABC (v1). Después: 10 en
  `MASTER_ESTUDIO` y ninguna en `ESTUDIO`.
- **0713** (obra 2645007): ninguna versión 0. 687 partidas y 1.774 líneas
  `ESTUDIO`: después, las mismas, y ninguna `MASTER_ESTUDIO`.

## 7 · Decisiones abiertas (recomendación en negrita)

- **D1 · Dónde se explica la fase viva.** **Dentro de `R-DESCOMPUESTO-ORIGEN`**,
  sin regla nueva ni tocar `R-FAS-AMBIGUO`/`stg.yaml` (ya dice «Previsto vivo»).
  Texto propuesto: «Coste fase 0 (ámbito 3, `fase_num` 0) es la FASE VIVA: el
  presupuesto de coste que el jefe de obra evoluciona día a día, sin historia.
  Su descompuesto es la planificación de compras (`PLANIF_JO`). Estudios es el
  master 0 (`MASTER_ESTUDIO`, con la medición de Estudios); solo en las obras sin
  master 0 se publica `ESTUDIO`, la «Descomposición» de la fase viva, con precios
  de Estudios y medición actual.» Alternativa: regla propia `R-FASE-VIVA`, más
  visible para quien consulte `stg.presupuesto`, a cambio de tocar dos YAML más.
- **D2 · Power BI.** **`v_pbi_estudio` sigue siendo solo `ESTUDIO` y la nueva
  `v_pbi_master_estudio` lleva sus mismas 21 columnas** (se unen sin más; cada
  obra está en una sola). Alternativa: copiar las columnas de
  `v_pbi_master_planif_jo` (con `fase_num` y flags de versión, constantes en la
  versión 0).

## 8 · Avisos para el implementer y el reviewer

- `02` corre antes que `03`: «obra con master 0» se decide contra
  `_versiones_cargadas` (`fase_num = 0`), no contra `lineas`.
- `lineas` y `cuadre_partida` persisten: los `CHECK` no los cambia `CREATE TABLE
  IF NOT EXISTS`; hace falta el bloque `DO` (único sitio con `MASTER_INICIAL`).
- `test_f120_factor.py` fija la versión 39 y la nota D7 de F-120: reescribirlos.
- El MCP cachea el diccionario: sin reiniciarlo sigue sirviendo la v39.
- Imagen ANTES del build contra Azure: la imagen vieja falla contra el `CHECK`
  nuevo.

## 9 · Lo que queda MANUAL del humano

T13 aviso · T14 foto de antes · T15 imagen · T16 `build-descompuestos
--sin-tope` + `apply-grants` · T17 foto de después, testigos y R24 por `psql` ·
T18 `publicar-diccionario` (v40) y reinicio del MCP.
