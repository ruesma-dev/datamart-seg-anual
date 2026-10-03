# F-113 · Requisitos · la categoría CD/CI/CP sale del capítulo, no de letras sueltas

> Spec-author, 2026-10-03. Mediciones y comparación A frente a B:
> `progress/spec_F-113.md`. Rigor `critico`.
>
> La spec está escrita para la **opción A** (recomendada, criterio del humano).
> **Si el humano elige B**, se suprimen R4 y R5 (y sus tests): la rama
> recursiva hereda la categoría del padre sin mirar el código del hijo.

## Contexto (una línea)

`stg/04_partidas.sql` decide la categoría con `LIKE '%CD%'`, `'%CI%'`, `'%CP%'`
sobre el código de la raíz: `AVDA_FRANCIA`, `P1414_PCI` y `P1414_PISCIN` caen en
CI (253 partidas, 2 obras fuera del seguimiento, 0 EUR). Sigrid no trae marca
usable: `obrparpar.tcaide` vale 0 en las 395.226 filas y `auxobrtca` son tres
oficios (instalaciones, demoliciones, carpintería).

## Regla de la raíz (A y B)

- **R1.** El sistema debe clasificar el capítulo raíz por el **prefijo** de su
  código en mayúsculas: empieza por `CD` → CD; por `CI` → CI; por `CP` → CP.
  Ninguna regla de categoría busca las letras en mitad del código.
  *Test*: `AVDA_FRANCIA`, `P1414_PCI`, `P1414_PISCIN`, `LEV.PISC` → OTRO; las 15
  variantes medidas (`CD'`, `CD1`, `CD-FII`, `CD `, `CDP`, `CI0`, `CIA`, `CI_F1`,
  `CI.F2`, `CI_F2`, `CI-FII`, `CI.II`, `CIP`, `CIPD`, `CP.00`) → su categoría de
  hoy, y `cd`/`ci`/`cp` en minúsculas igual que en mayúsculas.
- **R2.** MIENTRAS el código de la raíz no empiece por CD/CI/CP, el sistema debe
  mantener la regla de hoy: numérico puro (`^[0-9]+$`) distinto de `34` y `99`
  → CD; el resto → OTRO.
- **R3.** El sistema debe asignar a cada partida la categoría que le llega por
  herencia desde su raíz (R1-R2), salvo lo que dice R4.

## Herencia por el capítulo ancestro (solo A)

- **R4.** CUANDO un capítulo **no raíz** tiene un código que, en mayúsculas y sin
  puntos ni espacios, es **exactamente** `CD`, `CI` o `CP`, el sistema debe
  asignar esa categoría a ese capítulo y a todo su subárbol. Si en la cadena hay
  varios, manda el **más cercano** a la partida.
  *Test*: `CD > CI > CI.01` → CI; `99 > CI > CI.1` → CI; `CD > C.I. > CI.01` →
  CI; `CD > CP > X` → CP; `CI > CI > CI` → CI; `CD > F1 > CD` → CD;
  `CD > CI > CD > 01` → CD.
- **R5.** SI el código de un capítulo no raíz solo **empieza** por CD/CI/CP sin
  ser exactamente uno de ellos, ENTONCES el sistema NO debe cambiar la categoría
  heredada. *Test*: `CD > 02 > CI10`, `CD > 02 > CI-0036`, `CD > 07 > CP110`,
  `CD > AE04 > CPI8001`, `CD > 45 > CIMENT`, `113 > CIERRE`, `CI > CI.7 > CP.10`,
  `OTROS > CI.05.00` → la categoría de su raíz (son códigos de partida de
  catálogo: 391 `CI…` y 191 `CP…` medidos bajo raíces CD).

## Árbol (A y B)

- **R6.** CUANDO el recorrido atraviesa un capítulo sin código (colapsado,
  F-052), el sistema debe pasar a sus hijos la categoría del padre sin cambiarla.
- **R7.** El sistema debe calcular la categoría dentro del `WITH RECURSIVE`
  existente, en sus dos ramas, con la misma columna en la misma posición; el
  corta-ciclos y el tope de 40 saltos (F-052) no cambian.
- **R8.** El sistema NO debe cambiar ninguna otra columna ni el número de filas
  de `stg.partidas`: mismas `partida_id`, `codigo_partida`, `capitulo_padre_id`,
  `capitulo_raiz_id`, `capitulo_raiz_cod`, `ruta_capitulos`, `nivel`, `activa`.

## Dominio y SQL dicen lo mismo

- **R9.** El sistema debe tener la regla en Python puro
  (`etl_sigrid/domain/categoria_partida.py`), y `construir_arbol` de
  `domain/arbol_partidas.py` debe publicar `categoria` en cada `Partida` con ella.
- **R10.** Los literales del SQL (prefijos, lista exacta `CD`/`CI`/`CP`,
  `'34'`, `'99'`, caracteres que se quitan) deben ser los del dominio; un test
  textual los cruza y falla si divergen.
- **R11.** SI `stg/04_partidas.sql` contiene un `LIKE '%` dentro de la regla de
  categoría, ENTONCES un test debe fallar (trinquete).

## Contraste y despliegue

- **R12.** ANTES de desplegar, la consulta del árbol nuevo ejecutada como
  `SELECT` en transacción READ ONLY contra Azure debe reproducir la tabla de
  transiciones de `progress/spec_F-113.md` §2 (A: 490 partidas, 7 obras; B: 253,
  2), con 0 cambios fuera de esas obras.
- **R13.** DESPUÉS de reconstruir, `stg.partidas` debe tener por obra las
  categorías de R12, y el efecto en importes debe ser solo: 229 coste real hasta
  8.121 EUR de OTRO a CI (cierre 2011-01..03: INDIRECTOS sube y BENEFICIO baja
  lo mismo); 0462 venta real 25.002 EUR de CD a CI en `mart` (el cierre no
  cambia). En B, ningún importe. Verificación MANUAL (humano).

## Documentación

- **R14.** Las fichas que explican `categoria` (`stg.yaml`: `partidas` y nota 4
  de cabecera; `mart.yaml`: las seis columnas `categoria`; `raw.yaml`:
  `obrparpar` y `auxobrtca`) deben describir la regla nueva y dejar de decir
  «heurística sobre el código del capítulo raíz»; la de `auxobrtca` deja de
  llamarlo «catálogo bueno sin usar» y dice lo medido (`tcaide` = 0, tres
  oficios). `version` de `00_global.yaml` sube en 1.
- **R15.** `README.md` §6.3 y §5.3.1 y el comentario de `auxobrtca` en
  `config/tables_sigrid.yaml` deben decir la regla nueva y lo medido.
- **R16.** La cabecera de `stg/04_partidas.sql` debe explicar la regla (raíz por
  prefijo, intermedio por código exacto, el más cercano manda) y por qué no
  prefijo en los intermedios (códigos de catálogo `CI10`, `CPI8001`).
