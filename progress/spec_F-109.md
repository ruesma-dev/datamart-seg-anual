<!-- progress/spec_F-109.md -->
# F-109 · Spec escrita (spec-author, 2026-09-25)

Spec en `specs/F-109-partidas-codigo-no-unico/` (requirements 128 lineas, design
221, tasks 11 tareas; `python -m harness.tamano --feature F-109` dentro de
topes). Rama `feature/F-109-partidas-codigo-no-unico` desde `main` (323910f), en
un worktree aparte mientras F-108 sigue en el arbol principal. Ficha:
`sdd: true`, `status: spec_ready`; `BACKLOG.md` regenerado.

## Que son las repeticiones (medido en solo lectura, 2026-09-25)

MCP y consultas `SET TRANSACTION READ ONLY` desde el scratchpad (lo que pasaba de
30 s). Hoy: **5.202 pares, 8.933 filas de mas, 158 obras** (92 del seguimiento,
2.177 pares); la ficha decia 5.203/8.934/159 el dia 24. Identico en
`mart.v_pbi_dim_partida`. Todas son partidas activas y distintas (`partida_id`).

| Tipo | Pares | Filas de mas | Obras | Que es |
|---|---|---|---|---|
| D misma raiz, otro capitulo | 2.713 | 6.043 | 135 | subarbol copiado por bloque/portal (0560: `1.1.3.2` bajo 11 capitulos) |
| B otra raiz | 2.340 | 2.739 | 19 | arboles por fase con raiz propia (0444 `CD`/`CD-FII`, `CI`/`CI-FII`) o raiz que copia un capitulo (0515 `2` y `CD > 2`) |
| A misma ruta | 149 | 151 | 23 | hermanas homonimas: `N/A`, `----------`, codigo de solo espacios, erratas (0510 `04.04.14` x2), raices duplicadas |

**Descartado con el dato**: codigos vacios (el filtro los quita; si hay 2 de
solo espacios), versiones, coste/venta (`tipvis` distinto en 8 pares;
`parcoside`/`parvenide` 0), copias MenfisNet (`parideori` 0), copias por empresa
(el par vive dentro de un `obra_id`, que es una ficha: `R-CODIGO-POR-EMPRESA` no
aplica) y **el colapso de F-052: 0 de las 14.135 filas implicadas esta
colapsada**.

## Quien une por (obra, codigo) y si duplica

- **Hoy ningun importe se duplica dentro del repositorio**: todo el SQL que suma,
  Power BI y las relaciones del diccionario van por `partida_id`.
- **El riesgo, medido**: unir el hecho con la dimension por `(obra, codigo)`
  infla el Coste Real historico en +12.108.634,53 EUR (47 obras) y la Venta Real
  en +13.145.742,76 (53). **Obra 0437: 883.460,55 -> 3.474.491,83 EUR (x3,9)**;
  por `partida_id` o por `(obra, ruta)`, exacto. El MCP escribe SQL libre y hoy el
  diccionario le dice que el codigo es unico.
- **Donde muerde hoy, sin euros: los nombres.** `mart.v_pbi_dim_partida_niveles`
  resuelve el nombre de cada escalon por `(obra, codigo)` con `MAX`: 10.593 filas
  (4.657 del seguimiento) ensenan algun escalon con el nombre de otra partida.
  `cierre.v_pbi_dim_subcategoria_ci` y el detalle CI agrupan por codigo: 22 filas
  con nombre ajeno, y las dos fases de 0444 caen en el mismo grupo `CI.1`.

**Clave legible**: `(obra_id, ruta_capitulos)` es CASI unica (155 pares, 162
filas, 25 obras; 38 pares en 21 obras del seguimiento); `pos` no la completa.
Solo `partida_id` es unico.

## Que propone la spec

Solo texto de diccionario, una regla dura, una entrada en `ARCHITECTURE.md` y
tests offline; **ningun SQL se toca**. Las tres fichas que mienten
(`stg.partidas.obra_id`, `mart.v_pbi_dim_partida.obra_id`,
`mart.fact_seguimiento_mensual.codigo_partida`) se corrigen, y un test barre
todas las fichas para que ninguna vuelva a decirlo. Trinquete sobre `sql/**`:
solo dos ficheros resuelven algo por `(obra_id, codigo_partida)`.

## Decisiones abiertas para el humano (`design.md` §8)

- **D1 · clave legible**: propuesta **(a) ninguna; `partida_id` es la unica
  clave** y `ruta_capitulos` se documenta como direccion CASI unica. No se
  publica columna ni se declara clave alternativa de F-108 (hoy daria KO
  permanente en `check-unicidad`). Alternativas (b) `(obra_id, ruta)` si Negocio
  limpia en Sigrid los 38 pares del seguimiento; (c) clave sintetica: descartada.
- **D2 · regla dura `R-PARTIDA-CODIGO-NO-UNICO`** (bloqueante, siete fichas en su
  ambito): propuesta **si**, por el caso 0437.
- **D3 · nombres por codigo en niveles y cierre CI**: propuesta **(a)
  documentarlo aqui y fichar una feature nueva** que resuelva el nombre por el
  ancestro (toca SQL de `mart` y `cierre` y etiquetas del Arbol Presupuesto). Que
  Negocio diga tambien si fundir las fases de 0444 en `CI.1` es lo que quiere.
- **D4 · version del diccionario**: la siguiente a la de `main` al fusionar (33
  hoy; 34 si F-108 fusiona antes).
- **D5 · 2 codigos de solo espacios**: propuesta **corregir solo el texto** de la
  ficha; cambiar el filtro tocaria el arbol de F-052.

Las cifras de este informe son una foto del 2026-09-25: Sigrid las mueve cada
noche (ya cambiaron en uno desde el dia 24).
