<!-- specs/F-025-ventana-negocio-build/decisiones.md -->
# F-025 · Decisiones · CERRADAS por el humano el 2026-09-02

El principio se decidió el 2026-09-02: *«las obras que estén cerradas no se
actualizan»*, *«que no se reconstruyan, pero que no se borren, y que la
información esté consultable»*. **Ese mismo día quedaron cerradas DA-1 a DA-4.**
DA-5 quedó con la recomendación de esta spec, no como decisión del humano.
**DA-6 sí es suya: la decidió el 2026-09-04, a raíz del review, y EXIME la
campaña de mutación** (ver abajo). Censos y fuentes: `mediciones.md` y
`obras_candidatas_a_congelar.csv`.

---

## DA-1 · Qué es una obra cerrada — **DECIDIDO: tres reglas, en UNIÓN**

Se excluye de la actualización diaria toda obra que cumpla **al menos una**:

1. su estado es **EN ESTUDIO (1)**, **NO PRESENTADA (11)** o **CERRADA (25)**;
2. su código son **seis dígitos** (`codigo_obra ~ '^[0-9]{6}$'`);
3. **no tiene actividad** en los últimos 12 meses.

**Censo medido sobre el universo del código —`raw.obr JOIN raw.con`, 920 obras—:
se congelan 880 y quedan 40 en la actualización diaria**, de las cuales **38**
publican en el fact. Por regla, y sin repartir los solapes: 693 por estado, **226**
por código de seis dígitos y 872 por quietud.

La regla 1 se amplió de «25» a «1, 11 y 25» al aparecer el catálogo (DA-1 bis).
**No añade ni una obra**: las 226 EN ESTUDIO y las 2 NO PRESENTADAS caían ya por la
regla 3, porque ninguna tiene fases. El refinamiento no cambia el efecto de hoy;
deja escrito **por qué** se congela cada obra en vez de deducirlo de su quietud, y
cubre el caso futuro de una obra EN ESTUDIO que genere una fase.

### La contrapartida, con su número, sin suavizar

**Hay 48 obras con actividad en los últimos 12 meses y 8 quedan igualmente
congeladas: 7 por estar CERRADAS (estado 25) y 1 por tener código de seis dígitos
(la `180501`, que además no llega al fact). Sus datos podrán tener hasta 6 días de
antigüedad entre reconstrucciones completas.** Las ocho, con su última actividad:
`180501` 2026-07, `0669` 2026-04, `0660` y `0689` 2026-01, `0665` 2025-11, `0656` y
`0683` 2025-10, `0668` 2025-09.

Es una decisión del humano tomada **con el dato delante**: esta spec propuso un veto
—no congelar nunca una obra con actividad reciente— y lo **rechazó
explícitamente**: «pon las reglas que te he dicho».

### AVISO · la contrapartida que se le presentó al humano estaba INFLADA

**Se le dijo que 40 obras con actividad quedarían congeladas. Son 8.** Y el desglose
que acompañaba a aquel 40 —«39 CERRADAS, de las que 36 cierran en 2025-12»—
tampoco reproduce: **ninguna** de las ocho tiene su última actividad en 2025-12.

- **De dónde salía el 40:** de contar sobre `maestro.obras` con
  `coalesce(fecha_fin, fecha_inicio)` como actividad, y del CSV derivado
  `obras_candidatas_a_congelar.csv` / `obras_congeladas_F025.csv`, que asigna a 36
  obras una `ultima_actividad` de 2025-12 que `stg.fases` no confirma (la `0620`,
  por ejemplo, la tiene en 2024-01, y `raw.obrfas` igual). **El error fue de quien
  midió, no del código.**
- **De dónde sale el 8:** del universo `raw.obr JOIN raw.con` y de
  `MAX(make_date(f.anio, GREATEST(f.mes,1), 1))` sobre `stg.fases`, que es
  literalmente `postgres_client.SQL_ESTADO_OBRAS`, la consulta que el guardán
  ejecuta cada noche. **Remedido en solo lectura el 2026-09-03**, y confirmado por
  el reviewer de forma independiente.
- **La decisión del humano NO cambia:** el titular con el que decidió —**880
  congeladas y 40 en actualización diaria**— cuadra al dedillo con la medición
  buena, y la contrapartida real es **menor** que la que aceptó, nunca mayor. Lo
  que cambia es el registro, que tenía que decir la verdad.

**Y el tamaño real de la contrapartida es mucho menor de lo que parecía**, pero no
por el motivo que se escribió aquí el 2026-09-02: no es que 36 de 39 sean el cierre
anual, es que **nunca fueron 40**. Siete de las ocho son obras CERRADAS a las que se
les pasó algún mes tarde, y la octava es un estudio administrativo que el fact ni
publica.

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

**226 obras con código de seis dígitos y NINGUNA llega al fact** (0 de 226,
recomprobado el 2026-09-03 sobre el universo del código `raw.obr JOIN raw.con`
contra `stg.obras`, que es el `INNER JOIN` por el que pasa el fact): son
presupuestos y estudios de 2009-2015. **Eran 222 en la primera medición**, hecha
sobre `maestro.obras`; el recuento bueno es 226 y la conclusión no cambia. Ahorro sin riesgo de negocio. Es la regla 2
de DA-1, y por eso el criterio no necesita una lista de códigos administrativos
que mantener.

## DA-4 · Reconstrucción completa — **DECIDIDA: SEMANAL, los DOMINGOS**

Disparada desde `run-all` por antigüedad registrada, no desde un cron nuevo: un
cron aparte es lo que se olvida (lección de F-047, y del cron de F-052 que sigue
desactivado). De aquí sale el **«hasta 6 días»** de DA-1.

---

## DA-5 · Sin pronunciamiento del humano

Queda con la recomendación de esta spec. **No es decisión suya**; si al revisar
quiere otra cosa, cambia sin discusión.

- **DA-5 · El guardián avisa y no bloquea**, como `check-cobertura` de F-052.
  Contrapartida heredada: al no bloquear, la alerta de fallo del job no se
  dispara, y la regla nueva de Azure es la **única** vía por la que el guardián se
  hace oír. Sin desplegarla, es mudo.

## DA-6 · La campaña de mutación — **EXENTA por el humano el 2026-09-04**

Esta spec propuso la campaña sobre `domain/ventana.py` —dominio nuevo y mutable
(clasificación, firma, sello), donde un superviviente es una obra que se congela
cuando no debía— y **se autoconcedió el recorte del alcance**, que en rigor
`critico` no le corresponde: `rigor.json` fija `max_mutantes: null`, o sea *la
campaña entera*, y solo el humano puede eximirla por escrito. El review de la
pasada 2 lo detectó, recalculó el alcance con `harness.alcance` —**10 ficheros,
2.610 líneas, 219 mutantes**, de los que la campaña midió **83, uno solo de los
diez**— y planteó la disyuntiva: extenderla o eximirla.

**El humano exime. No se extiende la campaña.** Registrado también en la ficha de
`harness/features.json` y en T26.

**Y queda dicho sin suavizar lo que eso significa**, que es lo que el reviewer
necesita para declararlo N/A con conocimiento y lo que tiene que leer quien venga
después: **el código que decide QUÉ SE BORRA en cada tramo —
`build_stg_step.py`, donde vive `componer_borrado_derivado`, 34 mutantes— NO ha
pasado por mutación.** Tampoco `main.py` (37), `postgres_client.py` (31, con
`SQL_ESTADO_OBRAS`), `ventana_sql.py` (15) ni `cobertura.py` (6).

Lo que lo cubre en su lugar, por orden de fuerza:

1. **La prueba de las cinco huellas de T27/T30, con tolerancia CERO** —cinco
   antes, cinco después, y *una sola diferencia PARA la feature*—. Es la que
   demuestra de verdad que no se pierde una fila, y ninguna campaña de mutación
   da esa garantía sobre el dato publicado.
2. Los tests de `tests/test_f025_build.py`, escritos en RED antes del código
   (traza en `progress/impl_F-025.md`).
3. La **cobertura de las líneas cambiadas**: **91,7 %** (578/630) medido por
   `bash harness/init.sh`, sobre el umbral del 80 % de `critico`.

**Precedente**: el humano ya eximió la campaña en **F-042** y en **F-052**, y en
los dos casos la sustituyó por revisión de datos antes/después. Aquí es la misma
sustitución, con la diferencia de que la revisión de datos —la fase 7— **está
pendiente de ejecutar**: la exención vale, pero **T27/T30 dejan de ser una
comprobación más y pasan a ser la red única**.

## Lo que NO se decide aquí

- **El tamaño del servidor.** Esta feature reduce el trabajo; si el `B1ms` se
  queda corto, es una decisión que afecta a `albaranes` y `partes`.
- **Reactivar el cron de la nocturna** (desactivado desde el 2026-09-01): es
  trabajo de F-052 y va con su imagen nueva.
- **`stg.obras.activa`**, hoy `TRUE` literal y visible en Power BI. Rellenarlo con
  la ventana sería gratis y cambiaría un dato que alguien puede estar filtrando.
