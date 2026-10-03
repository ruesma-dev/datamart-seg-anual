# F-113 · Spec escrita (spec-author, 2026-10-03)

Spec en `specs/F-113-categoria-capitulo-por-prefijo/` (requirements, design,
tasks). Rama `feature/F-113-categoria-capitulo-por-prefijo` desde `main`
1bc205e. Escrita para la opción **A**; lo que cambia con B va marcado **[B]**.

## 1. Lo esencial, en cuatro líneas

- El fallo de hoy es pequeño: **3 raíces** (`AVDA_FRANCIA`, `P1414_PCI`,
  `P1414_PISCIN`), **253 partidas, 2 obras fuera del seguimiento, 0 EUR**.
  A y B lo arreglan igual.
- Sigrid **no** tiene marca de categoría: `obrparpar.tcaide` = 0 en las 395.226
  filas; `auxobrtca` son tres oficios (instalaciones, demoliciones, carpintería).
- **A = B + una regla más**: un capítulo intermedio cuyo código es *exactamente*
  `CD`, `CI` o `CP` (también `C.I.`) manda sobre la raíz para su subárbol.
  Prefijo en intermedios NO: hay 391 `CI…` y 191 `CP…` bajo raíces CD que son
  partidas de catálogo (`CI10` acero, `CPI8001` pilote CPI-8, `CP110` puerta).
- A añade 4 obras del seguimiento con un capítulo «COSTES INDIRECTOS» metido
  dentro de otra raíz; mueve **8.121 EUR de coste** (229, cierre de 2011) y
  **25.002 EUR de venta** (0462, solo en `mart`).

## 2. Medición (solo lectura, Postgres de Azure, 2026-10-03 tras la nocturna)

Transiciones respecto a hoy (`mart.fact_seguimiento_mensual`, `SUM(importe_mes)`
por escenario; «seg» = obra con filas en esa tabla):

| Obra | Seg | Capítulo que decide | Partidas | Hoy → B | Hoy → A | Importes que se mueven |
|---|---|---|---|---|---|---|
| 596085 (sin código) | no | raíz `AVDA_FRANCIA` | 221 | CI → OTRO | CI → OTRO | 0 |
| 998691 (sin código) | no | raíces `P1414_PCI`, `P1414_PISCIN` | 32 | CI → OTRO | CI → OTRO | 0 |
| 0229 NAVES SANTOS | sí | `99 > CI` «COSTES INDIRECTOS» | 95 | = | OTRO → CI | 0 (2 filas de plan a 0) |
| 229 NAVES SANTOS | sí | `TN > CI` «INDIRECTOS» | 9 | = | OTRO → CI | coste real 8.121 |
| 0462 RETAMAR | sí | `CD > C.I.` «COSTES INDIRECTOS» | 10 | = | CD → CI | venta real 25.002 |
| 0500 RETAMAR | sí | `CD > CI` «COSTES INDIRECTOS» | 11 | = | CD → CI | 0 |
| 1734235 (sin código) | no | `CD > CI`, `CD > CP` | 99 + 13 | = | CD → CI / CP | 0 |
| **Total** | | | | **253 / 2 obras** | **490 / 7 obras (4 seg)** | |

Fuera de esta tabla, **0 partidas cambian** con A ni con B. No cambian:

- Las 15 variantes de raíz por prefijo (`CD'`, `CD1`, `CD-FII`, `CD `, `CDP`,
  `CI0`, `CIA`, `CI_F1`, `CI.F2`, `CI_F2`, `CI-FII`, `CI.II`, `CIP`, `CIPD`,
  `CP.00`): todas son capítulos CD/CI/CP por su descripción. **Ninguna raíz
  contiene CD y CI a la vez.**
- Raíces numéricas (27 obras, 12 del seguimiento): siguen en CD salvo 34/99.
- Intermedios exactos que ya coinciden con su raíz (`CI > CI` en 6 obras,
  `CD > CD` en 3, `CD > F1 > CD` en 0626).

## 3. Efecto en `mart` y `cierre`

- **B**: ningún importe (las dos obras no tienen filas en `mart` ni en
  `stg.plan_mensual`); solo cambia la `categoria` de sus partidas.
- **A**: `mart.fact_seguimiento_categoria`: 229 pasa 8.121 EUR de Coste Real de
  OTRO a CI; 0462 pasa 25.002 EUR de Venta Real de CD a CI. **Cierre**: solo
  229 (cierres 2011-01 a 2011-03): INDIRECTOS sube y BENEFICIO baja hasta
  8.121 EUR (hoy ese coste no entra en ningún concepto). 0462 y 0500 tienen
  cierre (2015-16) pero sin coste movido; la VENTA del cierre no va por
  categoría. En la dimensión CI del cierre, esas obras enseñan como grupo el
  segundo escalón (`CI`, `C.I.`): declarado, no se corrige.

## 4. Consultas de la comprobación dirigida (T12, solo lectura)

```sql
-- categorías por obra de las 7 obras (comparar con la tabla de §2)
SELECT p.obra_id, p.categoria, count(*) FROM stg.partidas p
WHERE p.obra_id IN (SELECT obra_id FROM stg.obras WHERE codigo_obra IN ('0229','229','0462','0500'))
   OR p.obra_id IN (596085, 998691, 1734235)
GROUP BY 1, 2 ORDER BY 1, 2;
-- 0 partidas con esas raíces en CI
SELECT count(*) FROM stg.partidas WHERE categoria = 'CI'
  AND capitulo_raiz_cod IN ('AVDA_FRANCIA', 'P1414_PCI', 'P1414_PISCIN');
-- 229 en el cierre y 0462 en mart
SELECT anio_mes, concepto, ejecutado_origen FROM cierre.fact_cierre_mensual
WHERE codigo_obra = '229' ORDER BY 1, 2;
SELECT categoria, escenario, sum(importe_mes) FROM mart.fact_seguimiento_categoria
WHERE codigo_obra = '0462' GROUP BY 1, 2 ORDER BY 1, 2;
```

## 5. Decisiones del humano

- **D1 · A o B.** Recomendada **A**: es su criterio («medirlo por el PADRE»),
  arregla lo mismo que B y además clasifica bien 4 obras del seguimiento cuyo
  capítulo «COSTES INDIRECTOS» cuelga de otra raíz; la regla queda en dos
  líneas (raíz por prefijo, intermedio por código exacto, manda el más cercano).
  Elegir B solo si se prefiere no mover nada con importe (B mueve 0 EUR).
- **D2 · Contraste antes/después.** Recomendado el **ligero**: la propuesta en
  solo lectura antes de desplegar, partida a partida y sobre el mismo `raw`
  (T5), y la comprobación dirigida tras la nocturna (T12). El **completo** de
  F-042 (huellas + job puntual sin ingesta, ~3 h de CPU del servidor
  compartido; T13-T15) da la misma información para un efecto de 8.121 EUR en
  una obra de 2011. Si se elige el completo, T10 se sustituye por T13-T15.

## 6. Relación con F-111 (spec_ready, sin implementar)

Sin ficheros de código comunes. Se cruzan en la `version` del diccionario y en
las cifras de la dimensión CI de F-111 (138 de sus filas eran de la obra de
`AVDA_FRANCIA`, que F-113 saca de CI). **Ninguna espera a la otra**; si F-113
entra antes, F-111 remide su dimensión CI al implementarse.

## 7. Hallazgo (no es de esta feature)

- **H1.** En OTRO quedan 11,6 M EUR de coste real de 28 obras del seguimiento,
  que el cierre no cuenta en DIRECTOS/INDIRECTOS/GENERALES: sobre todo la raíz
  `PD` «PROMOCIÓN DELEGADA» (0655 6,1 M; 0631 1,1 M; 0601 0,9 M; 0584 0,8 M) y
  `MP` «MODIFICACIONES PROYECTO» de 0644 (2,6 M). Puede ser deliberado; si no
  lo es, merece ficha propia.

## 8. `features.json`

`acceptance` de F-113 ajustados a la medición (sin tocar `status`).
