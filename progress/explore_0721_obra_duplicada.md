# Exploración · 0721 Las Tablas: el datamart no trae su presupuesto

- Fecha: 2026-11-11, después de la nocturna `20261111T000022Z-b97406`.
- Líder, solo lectura: lecturas en Azure con `filas_solo_lectura` y en Sigrid con
  `SigridApiClient.leer_sql`.
- Incidencia: la reporta Control de Costes (Elena) el 2026-11-11.

## Hechos

En Sigrid hay **dos fichas de obra con el código 0721** y el mismo nombre. Las dos son
`con.tip` 42 y `est` 15.

| `ide` | Alta (`con.fec`) | `conext` 15 (vigente) | `obrfasamb` | `obrparpre` (Sigrid) | `obrparpar` (Sigrid) | En `stg.obras` |
|---|---|---|---|---|---|---|
| **2759553** | 2026-05-20 | **no** (tiene 5, 10, 20 y 25) | 28 cabeceras (ámbitos 8, 9 y 11 en v0 y v1, del 16-07-2026) | 9.200 | 1.278 | **no** |
| 2855829 | 2026-10-19 | no | 0 | 0 | 0 | **sí** |

En el datamart, la ficha con datos (2759553) sí llega a `raw` y a `stg`: 9.165 líneas en
`raw.obrparpre` y en `stg.presupuesto`, y 1.256 en `stg.partidas`. Pero no está en
`stg.obras`. Por eso Elena, que busca por el `obra_id` de `stg.obras` (2855829), no ve nada.
Además, `mart.master_versiones_tipadas` no tiene ninguna versión de la 0721: el reparto de
`stg.plan_mensual` solo trabaja con las obras del censo.

## Causa

`stg/03_obras.sql:84-125` deja UNA ficha por código. El orden es este:
1. La marcada en `conext` con `cod = '15'`.
2. Si no hay marca, la de `con.tiemod` más reciente.
3. Si sigue el empate, el `ide` más alto.

Ninguna de las dos fichas de la 0721 tiene la marca 15, así que gana la más reciente: la vacía
del 19-10.

Las demás obras recientes también tienen una segunda ficha posterior: 0693 a 0699, 0704 a
0713, 0720 y 0724. En todas ellas, la ficha con datos sí tiene la marca 15. La 0721 es la
única de las recientes sin marca en ninguna de sus dos fichas.

## Lo que queda fuera por el mismo mecanismo (no es nuevo)

Fichas con presupuesto que no están en `stg.obras` porque otra ficha de su código ganó el
desempate: 0252, 0272, 0309, 0455, 0517 (158.737 líneas), 0581, 0606 (1562946, la del
hallazgo 3d de la 0698), 0671 y **0721**. Los códigos de 6 cifras (`0902xx`, `1501xx`, …)
quedan fuera por la regla de los 5 dígitos, que es intencionada. Hoy hay 59 códigos con más
de una ficha.

## Opciones

- **A · En Sigrid (sin código):** marcar la ficha 2759553 como vigente (`conext` 15), como
  están las demás obras. Si la del 19-10 es un alta duplicada por error, darla de baja. La
  nocturna siguiente ya elige la buena. Hay que confirmar con Control de Costes qué es la
  ficha del 19-10.
- **B · En el datamart (hotfix):** en el desempate sin marca 15, poner por delante la ficha
  que tiene presupuesto (`obrfasamb` u `obrparpre`) y solo después `tiemod`. Antes de
  cambiar nada hay que medir qué otros códigos cambiarían de ficha elegida: 0252, 0517, 0581,
  0671… Cambiar la obra elegida de una obra cerrada mueve sus cifras históricas.
- Recomendación: A, y B como hotfix para que una ficha vacía nueva no vuelva a tapar a la buena.

## Ampliación del 2026-11-11 (aviso de Juan)

- La ficha 2855829 es de la **empresa 28 (PORSAN)**: `con.emp = 28`. La 2759553 es de
  Construcciones Ruesma (`con.emp = 1`, es decir, 1-0721).
- Los duplicados son casi siempre de PORSAN: 48 fichas de la empresa 28 comparten código
  con una obra de Ruesma. Solo en la 0721 gana la de PORSAN, porque la ficha de Ruesma no
  tiene la marca `conext` 15.
- **Medido el desempate nuevo** (marca 15, luego «tiene cabecera de máster» en `obrfasamb`,
  luego `tiemod` y `ide`) frente al de hoy, sobre todos los códigos: **solo cambia la 0721**
  (2855829 → 2759553). Las demás obras se quedan con la misma ficha.
