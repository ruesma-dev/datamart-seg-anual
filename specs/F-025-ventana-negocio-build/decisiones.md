<!-- specs/F-025-ventana-negocio-build/decisiones.md -->
# F-025 · Decisiones abiertas · Las cierra el humano

El **principio** ya está decidido (2026-09-02): *«las obras que estén cerradas no
se actualizan»*, *«que no se reconstruyan, pero que no se borren, y que la
información esté consultable»*. Lo que sigue abierto es **el criterio concreto** y
cinco cosas más. Censos y fuentes: `mediciones.md`.

---

## DA-1 · ¿Qué es una obra cerrada? — **LA PRIMERA**

Es la decisión que hizo que esta feature exista: viene sin cerrar desde el
2026-08-18 (DA-1 de F-011). Es de **Negocio**, no técnica.

| | Criterio | Congela | Riesgo medido |
|---|---|---|---|
| **(a)** | **Actividad**: sin fase cerrada en 12 meses | **322** de 583 | Ninguno de congelar algo vivo. Congela obras que podrían moverse por master sin cerrar mes: lo cubre la firma de origen |
| (a') | Actividad a 24 meses | 289 | Más conservador, **21,9 puntos menos de ahorro** |
| **(b)** | **Marca de Sigrid**: `maestro.obras.estado_id = 25` | 462 | **7 obras con estado 25 cerraron un mes en los últimos 12**. Su catálogo NO está ingerido, así que el significado de `25` es una suposición |
| **(c)** | **Fecha real de fin** (`obrctr.fecreafin`, vía `cierre.v_pbi_cierre_cabecera`) | 247 | Falla en los dos sentidos: **6** con fin real siguen cerrando meses y **298** paradas hace años no tienen fin real |
| **(d)** | **(a) + veto**: actividad a 12 meses, y nunca una obra `estado_id = 15` (EN CURSO) | **319** | Ninguno; el veto rescata 3 obras |

**Recomendación: (d).** La actividad es un hecho medido en nuestro propio dato; la
marca de Sigrid, una interpretación de un catálogo que no tenemos. Por eso la marca
solo **veta** —puede sacar obras de la lista de congeladas, nunca meterlas—.

**Y el criterio no es lo que garantiza la corrección**: la garantía es la **firma
del origen** (§3 de `design.md`), que reconstruye cualquier obra cuyos datos hayan
cambiado aunque el criterio la diera por cerrada. Un criterio demasiado agresivo
cuesta trabajo de más; nunca publica dato viejo. Esto es lo que permite elegir
(d) sin miedo.

**Nota para Negocio:** una obra congelada **sigue publicándose entera**. Lo único
que deja de ocurrir es que sus cifras se recalculen cada noche desde Sigrid.

---

## DA-2 · ¿Se acota también `build_presupuesto`?

`stg.presupuesto` son **13,8 M filas** y hoy hace `TRUNCATE` + `INSERT` completo,
sin marcador de filtro. Acotarla ahorraría parte de los ~16 min que quedan de
`build_stg` fuera de `plan_mensual`.

**Recomendación: NO**, y no solo por alcance: `stg.presupuesto` es **la fuente de
la firma de origen**. Si deja de reconstruirse entera cada noche, se pierde la
señal barata que detecta que una obra congelada cambió, y habría que ir a `raw`
—que es justo lo que se quiere evitar—. Se reevalúa con los números de T1.

---

## DA-3 · Las ~104 obras que se construyen y el fact descarta

El build recorre **687 obras** (`stg.presupuesto`) y `mart/02_build_fact.sql` hace
`INNER JOIN stg.obras` (583): del orden de **104 obras administrativas** se
explotan en `stg.plan_mensual` cada noche y **no llegan a ninguna consulta**.

**Recomendación: congelarlas también**, con el mismo mecanismo y sin borrar nada.
Son ahorro sin riesgo de negocio. Falta saber cuánto pesan (T1). Alternativa
descartada: excluirlas del build **borrando** sus filas, que contradice la orden
del humano.

---

## DA-4 · Cadencia y día de la reconstrucción completa

La red de seguridad de R25. La noche que toque **cuesta lo que cuesta hoy** (~3 h
45 y los 144 créditos), así que la cadencia es un compromiso entre coste y
antigüedad máxima de una laguna.

| Opción | Antigüedad máxima de un dato divergente |
|---|---|
| Semanal (sábado) | 7 días |
| Quincenal | 15 días |
| Mensual | 30 días |

**Recomendación: semanal, en sábado**, y revisar a quincenal o mensual cuando el
guardián lleve varias semanas sin denunciar nada. El disparo va **dentro de
`run-all`** por antigüedad registrada, no en un cron nuevo: un cron aparte es lo
que se olvida (lección de F-047, y del cron de F-052 que sigue desactivado).

---

## DA-5 · ¿El guardián bloquea o avisa?

**Recomendación: avisa y no bloquea**, igual que `check-cobertura` de F-052
(DA-4). Contrapartida conocida y heredada: al no bloquear, la alerta de fallo del
job no se dispara, y **la regla nueva de Azure es la única vía por la que el
guardián se hace oír**. Si no se despliega, es mudo.

---

## DA-6 · ¿Campaña de mutación o revisión de datos ampliada?

En F-052 el humano eximió la mutación a cambio de cuatro huellas. Aquí hay dominio
Python nuevo y mutable (`domain/ventana.py`: la clasificación, la firma, el sello),
y un superviviente ahí significa una obra congelada que debía reconstruirse.

**Recomendación: las dos.** Las cinco huellas son obligatorias por R21-R22, y la
mutación se limita a `domain/ventana.py`, que es barata de cubrir. Si el humano la
exime, que sea por escrito, como en F-042 y F-052.

---

## Lo que NO se decide aquí

- **El tamaño del servidor.** Esta feature reduce el trabajo; si el `B1ms` se
  queda corto, es una decisión que afecta a `albaranes` y `partes`.
- **Reactivar el cron de la nocturna** (desactivado desde el 2026-09-01 por
  F-052): es trabajo de F-052 y va con su imagen nueva.
- **`stg.obras.activa`**, que hoy es `TRUE` literal y llega a Power BI. Rellenarlo
  con la ventana sería gratis y cambiaría un dato que alguien puede estar
  filtrando: si Negocio lo quiere, es un cambio propio con su aviso.
