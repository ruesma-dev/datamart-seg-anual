# F-006 · Lado consumidor: `mcp-bbdd` consume la enmienda del contrato

**Fecha:** 2026-08-25
**Repositorio tocado:** `C:\Users\pgris\PycharmProjects\mcp-bbdd` (rama `main`,
sin remoto). **Este repositorio no se ha tocado**: solo se ha leído el contrato
(`specs/F-006-mcp-azure/design.md` §4) y el informe de la batería
(`progress/bateria_F-006.md`).
**Base:** `sigrid_dm` en `psql-albaranes-rs9k2`, rol `mcp_sigrid_dm_ro`.
**Solo lecturas.** Diccionario leído de `_meta`, **versión 7, publicada
2026-08-22 01:07 UTC, 103 objetos, 798 columnas, 13 reglas, cobertura 100,00 %**.

---

## 1 · Qué se ha arreglado

**H-1 de la batería, bloqueante.** `_meta.diccionario_contexto` publicaba 24
entradas en cinco bloques y `contexto_bbdd()` —la llamada obligatoria de
arranque— servía dos: las reglas duras y el resumen por esquema. Los tres que
faltaban son los que hacen que un agente cualquiera pueda formular sus propias
consultas sin que nadie le sostenga la mano:

| Bloque | Qué aporta | Coste medido de su ausencia |
|---|---|---|
| `ordenes_de_magnitud` | la defensa contra una cifra absurda | pasó una respuesta de **68,7 billones de euros** cuando lo saneado eran 260,6 M€ (H-6) |
| `ejes` | los literales EXACTOS de `escenario` | inventarlos devuelve cero filas y **ningún error** |
| `convenciones` | moneda, IVA, fechas de Sigrid, UTC de `_meta` | sin ellas no se interpreta ningún importe que se devuelva |

El diccionario había cumplido su parte de la enmienda del 2026-08-22. Desde la
silla del usuario el efecto era idéntico al de no haberla escrito.

**Y la segunda cosa:** `ocultar` viajaba con la columna como clave, tal y como
§4.4 exige, y **nadie la consumía**. Ahora sí.

---

## 2 · Antes y después, medido contra el `_meta` real

Ejecutando el mismo `contexto_bbdd()` contra la misma base, con el adaptador de
antes (commit `ee7c060`, el que corrió la batería) y con el de ahora:

```
ANTES -> longitud: 14898
  'CONVENCIONES DEL DATAMART'    presente: False
  'ÓRDENES'                      presente: False
  'EJES DEL MODELO'              presente: False
  'Coste Planificado'            presente: False
  'moneda: EUR'                  presente: False
```

```
DESPUÉS (scripts/probar_contexto.py, salida literal)

Bloques publicados en _meta.diccionario_contexto: 5
  [OK            ] convenciones             5/5 entradas en las notas
  [OK            ] ejes                     3/3 entradas en las notas
  [OK            ] esquemas                 9/9 entradas en las notas
  [DESTINO PROPIO] ocultar                  3 entradas -> lista de columnas de
                                            instrumentación, la consume columna_oculta()
  [OK            ] ordenes_de_magnitud      4/4 entradas en las notas

`ocultar` publica 3 columnas: _built_at, _ingested_at, _source_tiemod
  stg.presupuesto: 12 columnas visibles, 2 apartadas
  apartadas: _built_at, _source_tiemod
  la ficha declara las columnas apartadas: OK

Tamaño de contexto_bbdd(): 20536 caracteres
  Todos los bloques publicados llegan a su destino.
```

**21 de las 24 entradas llegan ahora a la prosa de arranque; las 3 restantes
son `ocultar`, y llegan a su consumidor.** No queda ninguna sin destino.

Y en el log del arranque, que antes no contaba el contexto porque no lo leía:

```
Diccionario cargado de _meta: 103 objetos, 13 reglas, 24 entradas de contexto
en 5 bloques, 3 columnas ocultas (versión 7)
```

Muestra de lo que ve el modelo ahora y antes no veía:

```
ÓRDENES DE MAGNITUD DE REFERENCIA. Contrasta contra ellos TODA cifra antes de
darla: si tu resultado se sale por varios órdenes, lo que está mal es la
consulta, no la empresa. Ojo: hoy solo cubren `retenciones`; que un importe de
otro esquema no tenga aquí su referencia no lo hace correcto.
  - Retenido VIVO a proveedores, pendiente de devolver, en toda la empresa: del
    orden de 34.700.000 EUR (criterio: saldo_vivo)
  ...

EJES DEL MODELO. Los literales son EXACTOS y van tal cual en el WHERE:
inventarlos devuelve cero filas y ningún error, que es la forma más cara de
equivocarse.
  - escenario: Coste Real, Coste Planificado, Venta Real, Venta Planificada. ...
```

---

## 3 · Decisiones de diseño

### 3.1 · El orden de las notas está en un solo sitio, y es explícito

`_ORDEN_DE_LAS_NOTAS` es la única lista que decide qué se sirve y en qué orden.
Las convenciones y los órdenes de magnitud van **antes** de las trece reglas
duras: son cortos y condicionan la lectura de todo lo que venga después. El
estado operativo va al final porque matiza una respuesta, no la cambia.

### 3.2 · Lo que no esté repartido se sirve igual

Es el punto que evita la quinta repetición del mismo fallo. Un bloque nuevo que
este servidor no conozca **se sirve al final, sin encuadrar**, y se avisa en el
log. Fallar abierto: mejor que el modelo lea un bloque sin maquetar a que no lo
lea. La alternativa —callarlo hasta que alguien le escriba su epígrafe— es
exactamente lo que ya ha pasado cuatro veces en esta feature.

### 3.3 · El `texto` publicado se inyecta tal cual

Lo dice §4.4 y se respeta: aquí solo se compone el **epígrafe** que encuadra
cada bloque. Recomponer el contenido es la vía directa a que la versión del ETL
y la del MCP acaben diciendo cosas distintas, que es lo que ya pasó con el
resumen por esquema.

### 3.4 · `ocultar`: se cablea el gancho de columna que §4.4 pedía

El contrato avisaba de que `esta_oculta()` recibe una **tabla** y que la lista
es de **columnas**, así que compararlas no oculta nada. Se ha añadido
`columna_oculta(tabla, columna)` al puerto —**no abstracto**, porque es una
capacidad opcional: el proveedor YAML responde `False` y sigue funcionando— y
el catálogo lo aplica al montar la ficha de una tabla.

Dos decisiones que no son obvias:

- **Una clave primaria nunca se aparta**, aunque el diccionario la liste. Si no,
  la ficha declararía un grano que sus propias columnas no sostienen y el modelo
  escribiría el JOIN a ciegas. Un filtro cosmético no puede llevarse por delante
  la identidad de la fila.
- **Las columnas apartadas se dicen.** Una columna que desaparece sin
  explicación reaparece en un `SELECT *` y se usa sin saber qué es. Literal de
  la ficha real de `stg.presupuesto`:

  > Esta tabla tiene además 2 columnas de instrumentación del ETL
  > (`_source_tiemod`, `_built_at`) que NO son dato de negocio: registran cuándo
  > se cargó o se construyó la fila. No las uses para responder ni las metas en
  > un GROUP BY.

**Nada que cambiar en el contrato.** La forma publicada (una fila por columna,
la columna como `clave`) es exactamente la que hacía falta. No se pide ninguna
enmienda.

### 3.5 · `origen: bbdd` pasa a ser lo normal

Deja de ser la opción y pasa a ser el valor por defecto de `config/config.yaml`.
Volver al YAML local sigue siendo cambiar esa línea. Se ha anotado además, con
su motivo, que poner `MCP_DICCIONARIO_ORIGEN` en el `.env` **no funciona**: se
lee con `os.getenv()` y ese fichero solo alimenta el prefijo `PG_`.

### 3.6 · Un aviso que se añadió sobre la marcha

El bloque `esquemas` publicado documenta nueve esquemas, `raw` incluido, y
`raw` **no está autorizado** en `esquemas_permitidos`. Al empezar a servir ese
bloque, el modelo lee sobre un esquema que no puede consultar. El epígrafe lo
dice ahora explícitamente: *«que un esquema esté documentado no implica que esté
autorizado»*. Y el resumen local se retituló de `ESQUEMAS DOCUMENTADOS` a
`ESTADO POR ESQUEMA`, porque dos secciones con el mismo título se leen como una
repetida y la segunda se salta.

---

## 4 · Ficheros tocados (todos en `mcp-bbdd`)

| Fichero | Qué |
|---|---|
| `config/config.yaml` | `origen: bbdd` por defecto + nota sobre `MCP_DICCIONARIO_ORIGEN` |
| `infrastructure/diccionario/diccionario_postgres.py` | reparto explícito y composición de las notas; `_como_json`, que se usaba y **no existía** (`NameError` en la primera carga con contexto) |
| `domain/ports/proveedor_diccionario.py` | `columna_oculta()`, no abstracto |
| `domain/entities.py` | `TablaInfo.columnas_ocultas` |
| `application/services/servicio_catalogo.py` | aplica el gancho al montar la ficha; nunca a una PK |
| `interface_adapters/mcp/presentadores.py` | la nota al pie que declara lo apartado |
| `interface_adapters/mcp/fabrica.py` | el contenedor expone el pool (lo usa la verificación) |
| `scripts/probar_contexto.py` | **nuevo**, el verificador |

Cuatro commits locales, ninguno con `git add -A`; `.env` y
`claude_desktop_config.json` verificados como ignorados antes de cada uno. Sin
`push` ni PR.

---

## 5 · Verificación

**Hecha contra el `_meta` real**, no razonada. El verificador
(`scripts/probar_contexto.py`) **no lleva escrita la lista de bloques que
espera**: la lee de la base y exige que cada uno llegue a algún sitio. Y la lee
**por el pool, no por el adaptador**: preguntarle cuántos bloques hay al mismo
código que se los estaba dejando sería preguntarle al acusado.

| Qué | Resultado |
|---|---|
| `contexto_bbdd()` contra `_meta` v7 | los 5 bloques publicados llegan a su destino, `exit 0` |
| Entradas que llegan a la prosa | 21/21 de los cuatro bloques de prosa |
| `ocultar` sobre `stg.presupuesto` | 2 columnas apartadas, 12 visibles, declaradas en la ficha |
| `ocultar` sobre `stg.obras` | 1 columna apartada, 4 visibles, declarada |
| Tamaño de `contexto_bbdd()` | 14.898 → **20.536** caracteres |
| Proveedor YAML | hereda `columna_oculta()` → `False`; sin regresión |
| Importación del servidor MCP y del verificador | OK |

Prueba adicional **sin base**, con un `_meta` simulado construido con el propio
`filas_contexto()` de este repositorio (las 24 filas reales): la composición sale
idéntica, y con un bloque desconocido inyectado se sirve al final con su aviso
en el log.

### Lo que NO se ha verificado

- **No se ha probado dentro de Claude Escritorio.** Todo va por la fábrica y los
  mismos servicios que usan las herramientas del servidor, pero el protocolo MCP
  no se ha ejercitado. Queda como verificación **MANUAL** pendiente.
- **No se ha vuelto a pasar la batería de 18 preguntas.** Este trabajo arregla
  H-1; que eso cambie las respuestas de P6, P8, P11 y P12 es lo esperado, pero
  no está medido.
- Al empezar, el puerto 5432 del servidor no era alcanzable desde este puesto
  (la IP pública `62.174.237.73` no está en las reglas del cortafuegos, que
  llevan una por día hasta el 2026-08-20). Se recuperó solo antes de tener que
  tocar nada; **no se ha modificado ninguna regla de Azure**. Si vuelve a fallar,
  ahí está el motivo.

---

## 6 · Lo que sigue abierto (no es de este trabajo)

- **H-6 sigue vivo a medias.** Los órdenes de magnitud ya llegan, pero **solo
  cubren `retenciones`**: cuatro entradas, las cuatro del mismo esquema. No hay
  ninguna referencia para `compras`, `mart` ni `cierre`, que es donde salió la
  cifra de 68,7 billones. El epígrafe lo advierte al modelo, pero **la solución
  es publicar órdenes de magnitud de esos esquemas**, y eso se hace en
  `config/diccionario/00_global.yaml` de este repositorio.
- **H-2, H-3, H-4, H-5** son del lado del diccionario y del ETL. Intactos.
- La ficha de `_meta.diccionario_contexto` declara «~21 filas» y tiene **24**, y
  el valor `ocultar` de su columna `bloque` no está en la lista de `valores
  posibles` de esa misma columna. Dos erratas de la propia ficha, de este
  repositorio.
- **Nada de proveedores intragrupo** (H-1 de P1: el mayor proveedor de la empresa
  es la propia empresa). Sigue sin declararse en ninguna parte.
