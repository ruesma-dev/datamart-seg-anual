<!-- specs/F-025-ventana-negocio-build/decisiones.md -->
# F-025 · Decisiones · CERRADAS por el humano el 2026-09-02

El principio se decidió el 2026-09-02: *«las obras que estén cerradas no se
actualizan»*, *«que no se reconstruyan, pero que no se borren, y que la
información esté consultable»*. **Ese mismo día quedaron cerradas DA-1 a DA-4.**
DA-5 y DA-6 no se preguntaron: quedan con la recomendación de esta spec, no como
decisión del humano. Censos y fuentes: `mediciones.md` y
`obras_candidatas_a_congelar.csv`.

---

## DA-1 · Qué es una obra cerrada — **DECIDIDO: tres reglas, en UNIÓN**

Se excluye de la actualización diaria toda obra que cumpla **al menos una**:

1. su estado es **EN ESTUDIO (1)**, **NO PRESENTADA (11)** o **CERRADA (25)**;
2. su código son **seis dígitos** (`codigo_obra ~ '^[0-9]{6}$'`);
3. **no tiene actividad** en los últimos 12 meses.

**Censo medido sobre las 920 obras de `maestro.obras`: se congelan 880 y quedan 40
en la actualización diaria**, de las cuales **38** publican en el fact.

La regla 1 se amplió de «25» a «1, 11 y 25» al aparecer el catálogo (DA-1 bis).
**No añade ni una obra**: las 226 EN ESTUDIO y las 2 NO PRESENTADAS caían ya por la
regla 3, porque ninguna tiene fases. El refinamiento no cambia el efecto de hoy;
deja escrito **por qué** se congela cada obra en vez de deducirlo de su quietud, y
cubre el caso futuro de una obra EN ESTUDIO que genere una fase.

### La contrapartida, con su número, sin suavizar

**Hay 80 obras con actividad en los últimos 12 meses y 40 quedan igualmente
congeladas: 39 por estar CERRADAS y 1 por tener código de seis dígitos. Sus datos
podrán tener hasta 6 días de antigüedad entre reconstrucciones completas.**

Es una decisión del humano tomada **con ese dato delante**: esta spec propuso un
veto —no congelar nunca una obra con actividad reciente— y lo **rechazó
explícitamente**: «pon las reglas que te he dicho».

**Y el tamaño real de la contrapartida es mucho menor de lo que parecía.** De esas
39 obras cerradas con actividad, **36 tienen su última actividad en 2025-12**, que
es el cierre anual, y solo **4** tienen algo posterior (dos en 2026-03, una en
2026-04 y una en 2026-07, la más reciente). No son obras vivas: son obras cerradas a
las que se les pasó el cierre del año. Recuento hecho sobre
`obras_candidatas_a_congelar.csv`.

**Consecuencia de diseño (§3.1 de `design.md`):** la firma del origen deja de ser un
mecanismo de **rescate** —reconstruir la obra que cambió— y pasa a ser de
**denuncia**: la nombra y espera al domingo. Rescatarla contradiría esta decisión.

### Formulación en negativo: elegida a propósito

Se le planteó al humano la alternativa **en positivo** —«solo se actualizan a diario
las **EN CURSO (15)** y las **ADJUDICADAS DEFINITIVAMENTE (9)**»—, explicándole su
ventaja: sería más robusto ante una obra TERMINADA, PARADA o RECIBIDA que cerrara un
mes tarde, porque una lista de estados que se actualizan es cerrada y una lista de
estados que se congelan hay que ir ampliándola. Respondió: **«déjalo en negativo»**.

Queda como **alternativa no elegida**, con la ventaja a la vista, por si algún día
se cambia el criterio. **No se implementa.**

## DA-1 bis · El catálogo de estados: **ENCONTRADO Y VERIFICADO**

Localizado en `azure-apps/sigrid_tablas.md` y confirmado contra Sigrid por
`sigrid-api` en solo lectura el **2026-09-02**: vive en **`conest`** («Tipos de
Estados de Conceptos»), el tipo de las obras es el **42** y se llega por `con.est`.

| est | cod | Significado | Obras |
|---|---|---|---|
| 1 | EST | EN ESTUDIO | 226 |
| 9 | ADD | ADJUDICADA DEFINITIVAMENTE | 33 |
| 11 | NPR | NO PRESENTADA | 2 |
| 15 | ECU | EN CURSO | 176 |
| 17 | PAR | PARADA | 7 |
| 19 | TER | TERMINADA | 2 |
| 21 | REP | RECIBIDA PROVISIONAL | 3 |
| 23 | RED | RECIBIDA DEFINITIVAMENTE | 4 |
| **25** | **CER** | **CERRADA** | **465** |
| 999 | PLT | PLANTILLA | 1 |

(3 PRESENTADA, 5 PRESENTADA CON ACLARACIONES, 7 ADJUDICADA PROVISIONAL y 13 NO
ADJUDICADA existen en el catálogo y hoy no tienen ninguna obra.)

**Esto retira un riesgo**: «25 = CERRADA» **no es una suposición nuestra**, está
verificado, y no hace falta preguntar a nadie. Lo que sí deja es una **tarea de
documentación**: la ficha de `maestro.obras.estado_id` en
`config/diccionario/maestro.yaml` afirma hoy que «su catálogo no se ingiere, así que
hay códigos sin nombre», y eso ha dejado de ser cierto. Se corrige en esta feature
—es barata, la lee el MCP y esta feature usa el estado como criterio— y **enlaza con
F-054**, la feature de conocimiento de negocio.

## DA-2 · `build_presupuesto` — **DECIDIDO: SÍ se acota**

Contra la recomendación de esta spec. `stg.presupuesto` (13,8 M filas) pasa a
construirse solo para las obras vivas, con el mismo patrón que `plan_mensual`:
marcador de filtro, `DELETE` de lo que se va a reinsertar y **nada de `TRUNCATE`**.

**Lo que rompe, y cómo se resuelve.** `stg.presupuesto` era la fuente barata de la
firma del origen: si deja de reconstruirse entera, deja de servir como señal. La
firma se traslada a **`raw`**, que la ingesta sí sigue trayendo completo cada
noche, en un sub-paso propio de solo lectura. Alternativas y coste: **§3 de
`design.md`**; la medición que decide su forma final es **T3**.

## DA-3 · Las administrativas — **DECIDIDO: SÍ se congelan**

**222 obras con código de seis dígitos y NINGUNA llega al fact** (0 de 222): son
presupuestos y estudios de 2009-2015. Ahorro sin riesgo de negocio. Es la regla 2
de DA-1, y por eso el criterio no necesita una lista de códigos administrativos
que mantener.

## DA-4 · Reconstrucción completa — **DECIDIDA: SEMANAL, los DOMINGOS**

Disparada desde `run-all` por antigüedad registrada, no desde un cron nuevo: un
cron aparte es lo que se olvida (lección de F-047, y del cron de F-052 que sigue
desactivado). De aquí sale el **«hasta 6 días»** de DA-1.

---

## DA-5 y DA-6 · Sin pronunciamiento del humano

Quedan con la recomendación de esta spec. **No son decisiones suyas**; si al
revisar quiere otra cosa, cambian sin discusión.

- **DA-5 · El guardián avisa y no bloquea**, como `check-cobertura` de F-052.
  Contrapartida heredada: al no bloquear, la alerta de fallo del job no se
  dispara, y la regla nueva de Azure es la **única** vía por la que el guardián se
  hace oír. Sin desplegarla, es mudo.
- **DA-6 · Campaña de mutación sobre `domain/ventana.py` además de las cinco
  huellas.** Hay dominio nuevo y mutable —clasificación, firma, sello— y un
  superviviente ahí es una obra que se congela cuando no debía. Si el humano la
  exime, por escrito, como en F-042 y F-052.

## Lo que NO se decide aquí

- **El tamaño del servidor.** Esta feature reduce el trabajo; si el `B1ms` se
  queda corto, es una decisión que afecta a `albaranes` y `partes`.
- **Reactivar el cron de la nocturna** (desactivado desde el 2026-09-01): es
  trabajo de F-052 y va con su imagen nueva.
- **`stg.obras.activa`**, hoy `TRUE` literal y visible en Power BI. Rellenarlo con
  la ventana sería gratis y cambiaría un dato que alguien puede estar filtrando.
