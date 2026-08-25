<!-- progress/parada_2026-08-22_limite_gasto.md -->
# PARADA · 2026-08-22 · límite de gasto mensual — LÉEME ANTES DE RETOMAR

Los tres subagentes en curso (implementer, reviewer y el de `mcp-bbdd`) se
cortaron **a la vez** por límite de gasto de la cuenta, no por un fallo del
trabajo. Esto es lo que quedó y cómo se retoma.

## Estado del árbol: VERDE y consistente

`bash harness/init.sh` en verde: **1985 tests**, cobertura 98,3 %.
Rama `feature/F-006-mcp-azure`, último commit `f30baaa`, **árbol limpio**.

El implementer cayó a mitad de editar `config/diccionario/retenciones.yaml` y
ese cambio parcial **dejaba 8 tests en rojo**. Se revirtió del árbol y se
preservó de dos formas, porque tenía trabajo bueno dentro:

- **`progress/pendiente_T40_retenciones.diff`** (versionado, es la copia buena).
- Un `git stash` de la sesión, que es volátil y **no hay que confiar en él**.

## Lo que estaba haciendo cada uno

| Agente | Iba por | Dónde retomar |
|---|---|---|
| **implementer** | **T40**: corregir lo que delató la batería | El encargo completo, abajo |
| **reviewer** | Cerrar el informe de la 17.ª pasada: qué queda aprobado y qué deuda viaja | `progress/review_F-006.md` |
| **`mcp-bbdd`** | Que `contexto_bbdd()` sirva los tres bloques que se deja | Su repo, cambios sin commitear en `config/config.yaml` y `diccionario_postgres.py` |

## El dato que el implementer alcanzó a dejar antes de caer

**`codigo_obra` se repite en `maestro.obras`: 918 filas, 843 valores distintos.**
Es decir, **no hay join limpio por código de obra** en ese maestro, y el
validador que lo señalaba tenía razón. Hay que tenerlo en cuenta al corregir la
relación de `retenciones` — la salida no puede ser «usa `codigo_obra` en vez de
`obra_id`», porque ese tampoco identifica una obra.

## T40 · lo que la batería delató y falta por corregir

Informe completo en `progress/bateria_F-006.md`. Recuento: 11 RESPONDIDA,
4 CON DUDA, 1 NO RESPONDIDA, 2 RECHAZADA CORRECTAMENTE.

1. **Relación falsa** (empezada, es el diff preservado):
   `retenciones.movimientos.obra_id` **no une con `maestro.obras.obra_id`,
   0 de 256**. Es el `ide` del **centro de coste** (0655 = 1990274 allí,
   1990273 en el resto). El JOIN devuelve cero filas en silencio. Revisar
   además **todas** las relaciones declaradas y derivar la comprobación.
2. **Afirmación falsa medida**: «`compras.contratos.descripcion` suele nombrar
   el oficio» es **5 de 18.879 (0,03 %)**; en el 87,5 % es el nombre del
   proveedor.
3. **`maestro.obras.es_activa` es TRUE en 918/918** (`fecha_baja` nunca se
   informa). `R-OBRA-ACTIVA` aparta de la trampa de `stg.obras.activa` y empuja
   a la gemela, que miente igual.
4. **No existe noción de coste de consulta**: `mart.v_master_vigente_anual`
   agota los 30 s **con `LIMIT 5`** y está marcada como recomendada.
5. **68,7 billones de euros** en `v_pbi_albaranes_sin_facturar` por dos líneas
   de un albarán de 2021 (saneado: 260,6 M€). Los órdenes de magnitud existían
   para cazarlo y no llegaron al agente.

## Lo que la batería SÍ demostró, y conviene no perder de vista

`R-IMPORTE-MES` evitó errores de **8,4×** y **12.993×**; `R-VERSION-MASTER`, de
**28,1×**; `R-COMPRAS-TIPO-DOC`, de **2,96×**. Las dos preguntas imposibles se
**rechazaron con el motivo exacto**, que era el comportamiento buscado.

## Deuda abierta que no bloquea

- **F-041 (prioridad 2)**: la puerta de mutación **no comprueba nada** —cuenta
  cualquier `returncode != 0` como mutante muerto sobre una suite ya roja en el
  worktree—. Mientras no se arregle, **ningún número de mutación de este
  repositorio es evidencia**. Hay un superviviente real conocido:
  `and`→`or` en `diccionario_sql.py:297`.
- **F-042**: la clave rota del fact y el agregado doblado (39,07 M€ en 8 obras).
- **F-044 (prioridad 1, tras el MCP)**: los cuatro build a la nocturna. Ya
  medido: **37,5 min**, el disco no se mueve (57,92 → 57,93 %).
- La deuda declarada en `specs/F-006-mcp-azure/tasks.md`, sección «Deuda
  declarada».
