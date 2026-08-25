<!-- progress/review_F-006.md -->
# F-006 · Review — el diccionario semántico (resumen)

> El detalle íntegro de las dieciséis pasadas —hallazgos, citas de código,
> experimentos y discusión— vive en
> [`review_F-006_detalle.md`](review_F-006_detalle.md) (4918 líneas). **Este
> fichero es el índice de entrada**: veredicto vigente, checkpoints, hallazgos
> abiertos y qué falta para cerrar. Los enlaces apuntan a secciones del anexo.

## Veredicto vigente

**RECHAZADO**, decimosexta pasada (la última; sin fecha en cabecera, posterior al
2026-08-21). Nivel de rigor `critico`.

Es, a la vez, **la mejor tanda de las dieciséis** en contenido: la formulación
del aviso de doblado es exacta, `ocultar` viaja usable, `_ACUMULADAS` se deriva
de verdad y por primera vez una comprobación ataca la clase y no el caso. Lo que
bloquea **no es el contenido publicado, son los instrumentos**: la puerta de
mutación del arnés declara «0 supervivientes» sin medir nada (demostrado con
control), el guardián de coherencia tiene tres vías de evasión —una lo deja
inerte hoy— y la corrección 22 → 9 llegó a la cabecera y no a las fichas de
columna.

**La batería de las 18 preguntas SÍ puede lanzarse ya**: nada de lo que bloquea
el APROBADO bloquea la batería
([anexo](review_F-006_detalle.md#la-batería--sí-lanzadla-y-lo-que-falta-se-corrige-mientras-corre)).

### Evolución de las rondas

| # | Fecha | Veredicto | Eje |
|---|---|---|---|
| 1 | 20-ago | RECHAZADO | 10 defectos en 25 fichas; la puerta de cobertura no protege |
| 2 | 20-ago | APROBADO | Los 10 cerrados; 4 arrastres antes de publicar en `_meta` |
| 3 | 20-ago | RECHAZADO | `compras`/`retenciones`: claves compuestas y `agregacion` falsos |
| 4 | 20-ago | RECHAZADO | Defectos cerrados en un campo y vivos en el campo vecino |
| 5 | 20-ago | RECHAZADO | Grano derivado: el defecto era sistemático, no puntual |
| 6 | 20-ago | **APROBADO** | Bloques A–D, E y F parcial (49 fichas) |
| 7 | 20-ago | RECHAZADO | Diccionario completo (53 objetos más): `raw` y `stg` con fichas falsas |
| 8 | 21-ago | RECHAZADO | Regla de oro y carga de `raw`: una falsedad sustituida por otra |
| 9 | 21-ago | RECHAZADO | Bug del derivador (alias `l` machacado) y copia superviviente |
| 10 | 21-ago | RECHAZADO | Vicio de fondo cerrado; 2 defectos en superficie de consumo |
| 11 | 21-ago | **APROBADO** | Los seis cerrados; punto de rendimientos decrecientes |
| 12 | 21-ago | RECHAZADO | Primera contra la base real: `READ ONLY` inexistente, evidencia recortada |
| 13 | 21-ago | RECHAZADO | Guardián verde sobre afirmación falsa; código muerto nuevo |
| 14 | s/f | RECHAZADO | Campaña de mutación caducada; `importe_origen` doblado |
| 15 | s/f | RECHAZADO | El aviso bajó a la columna, la cabecera sigue tranquilizando |
| 16 | s/f | **RECHAZADO (vigente)** | La puerta de mutación no mide nada |

Patrón recurrente, escrito por el propio reviewer: **rectificó seis veces un
APROBADO ya emitido** por emitir antes de que volviera la auditoría que él mismo
encargaba, y por verificar lo que la tanda dice haber hecho en vez de lo que se
le escapó. El diagnóstico de fondo de las dieciséis: *el problema nunca han sido
los datos, sino los instrumentos que decían que los datos estaban bien*.

## Recorrido de `CHECKPOINTS.md` (decimosexta pasada)

| CP | Estado | Motivo |
|---|---|---|
| **C1** Entorno en verde | CUMPLE | `init.sh` verde: 1982 pasados, 124 saltados, cobertura 98,1 % de 979 líneas |
| **C2** Trazabilidad requisito → test | **NO CUMPLE** | Mitad del guardián de coherencia inerte; el arreglo de `ocultar` no lo protege ningún test; `_acumuladas_de` pierde `can_origen` en silencio |
| **C3** Diff conforme al diseño | CUMPLE | Solo los ficheros previstos; `design.md` §4.4 actualizado (su §159 se contradice: menor) |
| **C3 bis** Sin secretos ni prints | CUMPLE | Sin GUID ni correo en el árbol |
| **C4** Convenciones y veracidad | **NO CUMPLE** | Remisión a una consulta que da otro número; tres fichas de columna con el «22» mal atribuido; dos de los tres números sin consulta publicada |
| **C4 bis** Campaña de mutación | **NO CUMPLE** | La puerta no mide: en worktree detached la suite ya está roja antes de mutar y `returncode != 0` cuenta como mutante muerto |
| **C4 ter** Cero supervivientes | **NO CUMPLE** | Al menos un superviviente real (`diccionario_sql.py:297`, `and`→`or`), declarado muerto por las dos campañas |
| **C5** Tareas y commits | CUMPLE PARCIAL | Reserva: `azure-apps` no recoge `ocultar` (R38 pedía el mismo trabajo). Las verificaciones MANUAL (T19, T27, T29–T34) siguen abiertas **por diseño** — N/A para el reviewer, las ejecuta el humano |

El reviewer **rectifica en la propia pasada** los C4 bis y C4 ter que había puesto
en verde: su recálculo confirmaba el **conteo** de mutantes (254, exacto), no el
**veredicto** de cada uno
([anexo](review_F-006_detalle.md#checkpoints)).

## Hallazgos abiertos (bloquean el cierre)

| # | Hallazgo | Estado | Anexo |
|---|---|---|---|
| H1 | **La puerta de mutación del arnés falla en verde.** Falta línea base verde y veredicto por comparación de tests fallidos, no por `returncode`. **Es fallo del arnés, no de F-006**: afecta a `arnes-base` y a las campañas de F-003/004/005/011/015/016/019/020/024 lanzadas en paralelo con «0 supervivientes» | Abierto · GRAVE | [§GRAVE](review_F-006_detalle.md#grave--la-puerta-de-mutación-del-arnés-da-0-supervivientes-sin-comprobar-nada) |
| H2 | **Mutante vivo conocido**: `diccionario_sql.py:297` (`and`→`or`) sobrevive a la suite completa; ningún test cubre `_clave_de` con entradas de tipo cadena | Abierto · GRAVE | [§GRAVE](review_F-006_detalle.md#grave--la-puerta-de-mutación-del-arnés-da-0-supervivientes-sin-comprobar-nada) |
| H3 | **El guardián de coherencia tiene tres vías de evasión** (otra redacción no listada; frase partida por línea en blanco del plegado YAML; y el salvoconducto evaluado sobre toda la cabecera, que lo deja inerte hoy) | Abierto · GRAVE | [§Guardián](review_F-006_detalle.md#el-guardián-de-coherencia-atacado-corta-el-caso-real-y-tiene-tres-puertas) |
| H4 | **El 22 → 9 no viajó**: las tres fichas de columna (`fact_seguimiento_categoria.importe_origen`, `…_raw`, `v_pbi_fact_categoria.importe_origen`) conservan «22 obras», la cifra mal atribuida | Abierto · MEDIA | [§Motivo 3](review_F-006_detalle.md#motivo-3--la-corrección-22--9-llegó-a-un-sitio-y-no-a-los-otros) |
| H5 | **Remisión falsa publicada al agente**: «la consulta que da ese numero esta en el grano de `mart.fact_seguimiento_mensual`» apunta a una consulta que devuelve 8.778 y 9 obras, no el doblado | Abierto · MEDIA | [§Motivo 3](review_F-006_detalle.md#y-una-afirmación-falsa-publicada-al-agente) |

### Abiertos de higiene (no bloquean)

| # | Hallazgo | Anexo |
|---|---|---|
| h6 | Falta publicar la consulta del «37 celdas / 39,07 M€» y la del «22 obras» | [§Motivo 3](review_F-006_detalle.md#motivo-3--la-corrección-22--9-llegó-a-un-sitio-y-no-a-los-otros) |
| h7 | `_acumuladas_de` pierde `can_origen` (no declara `unidad`); el control ancla solo 2 de 4 y un solo objeto | [§`_ACUMULADAS`](review_F-006_detalle.md#_acumuladas-derivada-de-verdad--con-una-pérdida-silenciosa) |
| h8 | El guardián hermano se relajó a aceptar cualquiera de tres cadenas: un objeto puede citar el número de otro y pasar | [§Guardián hermano](review_F-006_detalle.md#y-el-guardián-hermano-se-relajó-en-esta-misma-tanda) |
| h9 | `azure-apps/datamart_seg_anual.md` no recoge `ocultar` en el contrato ampliado (R38) | [§`ocultar`](review_F-006_detalle.md#ocultar--viaja-usable-y-resuelve-lo-que-planteé) |
| h10 | `design.md:159` describe `ocultar` como «patrones fnmatch» y contradice a su §4.4 | [§`ocultar`](review_F-006_detalle.md#ocultar--viaja-usable-y-resuelve-lo-que-planteé) |
| h11 | El doblado sigue vivo **en la base**: el diccionario avisa bien, el número seguirá mal hasta arreglar el build (recogido en F-042 como dato erróneo) | [§Batería](review_F-006_detalle.md#la-batería--sí-lanzadla-y-lo-que-falta-se-corrige-mientras-corre) |

### Resueltos

**Unos 55 hallazgos cerrados y verificados a lo largo de las pasadas 1 a 16** —los
10 de la primera, los 5 de la tercera, los 6 de la cuarta y quinta, los 10 de la
séptima, los defectos de `raw`/regla de oro de la octava, los 5 de la novena, los
6 de la décima, los 5 de la duodécima y los 4 de la decimotercera—, cada uno con
su comprobación contra el SQL en el anexo. Ninguno vuelve a abrirse.

## Qué falta para APROBADO (palabras del reviewer)

**Bloqueantes**

1. **Arreglar la puerta de mutación** (línea base verde obligatoria + veredicto
   por comparación con los tests que ya fallaban) y **relanzar la campaña** para
   saber cuántos supervivientes hay de verdad. Hoy se conoce uno; no se sabe si
   son diez. La corrección va a `harness/mutacion.py` **y a `arnes-base`** por la
   regla de propagación.
2. **Cerrar el mutante conocido**: un test que compruebe `_clave_de` con entradas
   de tipo cadena, que es lo que hace `ocultar` usable.
3. **Quitar el salvoconducto** del guardián de coherencia, normalizar antes de
   comparar (`tests/_texto.py::normalizado()`, que ya existe) y sustituir la lista
   de frases a mano por un criterio, como ya se hizo con `_ACUMULADAS`.
4. **Propagar el 22 → 9** a las tres fichas de columna y corregir la remisión «la
   consulta que da ese numero está en el grano de…».

**De higiene, no bloqueantes:** h6 a h10 de la tabla anterior.

**Automejoras propuestas y no aplicadas**
([anexo](review_F-006_detalle.md#automejora-que-propongo-no-aplico)): línea base
verde en la puerta de mutación (urgente, va a `arnes-base`); que todo guardián
nuevo venga con **su intento de evasión** además de su control anti-vacío; y que
los tests que comparan prosa normalicen el marcado.
