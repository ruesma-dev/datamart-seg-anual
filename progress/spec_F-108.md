<!-- progress/spec_F-108.md -->
# F-108 · Spec escrita (spec-author, 2026-09-24)

Spec en `specs/F-108-claves-alternativas/` (requirements 136 lineas, design 230,
tasks 12 tareas). Rama `feature/F-108-claves-alternativas` desde `main`
(249b683). Ficha de F-108 en `harness/features.json`: `sdd: true`,
`status: spec_ready`; `BACKLOG.md` regenerado.

## Resumen del diseno

- **Ficha**: clave opcional `claves_alternativas: [[col, ...], ...]`. La valida
  el dominio (columnas documentadas, no igual a la de negocio, sin duplicados,
  nunca en funciones); la lista plana `[clave_obra]` se rechaza por ambigua.
- **Validador R5 de F-006**: `_es_unica_por` acepta una columna que sea ELLA
  SOLA una clave alternativa. Una compuesta no sirve como lado 1.
- **`check-unicidad`**: una consulta mas por clave alternativa (`tipo_clave`),
  misma forma que la de negocio, excluyendo filas con NULL en la clave. La
  consulta de la clave de negocio no cambia ni un byte. Un solo «no existe» por
  objeto.
- **Publicacion**: la clave viaja en el JSONB `ficha` solo si hay alguna; sin
  DDL. `mcp-bbdd` la lee con `.get` y la ignora sin romperse (comprobado en su
  codigo).
- **Declaradas**: `maestro.obras [[clave_obra]]`, `personal.recursos
  [[clave_recurso]]`; las cinco relaciones de `compras` por `clave_obra` pasan
  de `N:N` a `N:1`. Version del diccionario 30 -> 31.
- **Nocturna**: sin cambios. `check-unicidad` no esta en `run-all` (comprobado),
  asi que «avisa sin romper la nocturna» se cumple ya. Ningun SQL se toca.

## Medido en solo lectura (MCP, 2026-09-24)

| Clave | Filas / distintas |
|---|---|
| `maestro.obras.clave_obra` | 922 / 922 |
| `personal.recursos.clave_recurso` | 2.619 / 2.619 |
| `maestro.v_obra_fichas.clave_obra` | 922 / 922 |
| `maestro.cuentas_analiticas (empresa_id, codigo_cuenta)` | 184.234 / 184.234 (el codigo solo, 163.247) |
| `maestro.centros_coste (empresa, codigo_centro)` | 804 / 804 (el codigo solo, 655) |
| `stg.obras.codigo_obra` | 584 / 584 |
| `stg.partidas (obra_id, codigo_partida)` | 394.018 / 385.084: **NO es unica** |

## Decisiones abiertas para el humano (`design.md` §8)

- **D1**: las filas con NULL en una clave alternativa ¿se excluyen de la
  comprobacion, como haria un indice unico? Propuesta: si. La clave de negocio
  sigue agrupando los NULL como hasta ahora.
- **D2**: un KO en una clave alternativa ¿hace salir `check-unicidad` con codigo
  1, como la de negocio? Propuesta: si (es un comando manual, no esta en la
  nocturna).
- **D3**: ¿se declaran las cuatro candidatas extra (`v_obra_fichas.clave_obra`,
  `cuentas_analiticas (empresa_id, codigo_cuenta)`, `centros_coste (empresa,
  codigo_centro)`, `stg.obras.codigo_obra`)? Propuesta: si. Son unicas y sus
  fichas ya lo dicen en el texto. Si no, R22 se cae y T6 se recorta.
- **D4**: ¿sirve `mcp-bbdd` las claves alternativas al agente? Propuesta: una
  feature en `mcp-bbdd`, fuera de esta.
- **D5**: si F-095 (en curso) sube tambien la version del diccionario, la
  feature que se fusione en segundo lugar toma la siguiente.

## Hallazgo fuera de alcance (H1): conviene una feature nueva

`(obra_id, codigo_partida)` NO es unico en `stg.partidas` ni en
`mart.v_pbi_dim_partida`: se repiten 5.203 pares y sobran 8.934 filas en 159
obras (hasta 22 filas por par). Contradice tres textos publicados:
`stg.partidas.obra_id` y `mart.v_pbi_dim_partida.obra_id` («los codigos de
partida solo son unicos dentro de su obra») y
`mart.fact_seguimiento_mensual.codigo_partida` («unico por obra»). Puede tener
que ver con el colapso de capitulos en blanco de F-052, pero no se ha
investigado.

## APROBADA (humano, 2026-09-24)

Las cinco decisiones con la recomendacion: D1 las filas con NULL en una clave
alternativa se excluyen de la comprobacion; D2 una clave alternativa rota hace
salir `check-unicidad` con codigo 1, como la de negocio; D3 SI se declaran las
cuatro claves extra (`maestro.v_obra_fichas.clave_obra`,
`maestro.cuentas_analiticas (empresa_id, codigo_cuenta)`,
`maestro.centros_coste (empresa, codigo_centro)`, `stg.obras.codigo_obra`); D4
servir las claves al agente es feature aparte en `mcp-bbdd` (texto entregado al
humano para llevarlo alli); D5 quien fusione segundo con F-095 toma la version
siguiente del diccionario. El hallazgo H1 (partidas no unicas por obra y codigo)
se ficha como feature propia (F-109).
