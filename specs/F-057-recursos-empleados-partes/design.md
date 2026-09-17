<!-- specs/F-057-recursos-empleados-partes/design.md -->
# F-057 · Diseno tecnico

Todo lo numerico de aqui se **midio contra Sigrid vivo el 2026-09-18** por
`sigrid-api` en solo lectura. Nada se supone.

## El hallazgo que cambia el diseno

`hmores.can` **no son horas**. Su unidad la fija el tipo de hora, y el
clasificador **no es `auxhor.ext`** —que esta a cero en las 60 filas del
catalogo, asi que quien lo mire concluye que no clasifica nada— sino
**`auxhor.medide`**, una referencia a `auxmed` (38 filas):

| `medide` | unidad | lineas | cantidad | euros | % del dinero |
|---|---|---|---|---|---|
| 1 | HORA | 241.004 | 1.249.038,44 h | 24.837.178,20 | 25,3 % |
| 2 | DIA | 9.723 | 4.225,46 d | 1.809,20 | 0,0 % |
| 3 | MES | 36.034 | 18.009,38 m | 70.458.900,29 | **71,7 %** |
| 19 | UD | 43.867 | 565.927,95 ud | 2.977.303,43 | 3,0 % |
| — | (sin catalogo) | 10 | 0 | 0 | 0 % |

`SUM(can)` en bruto da 1.837.201,23 sumando horas de albanil con meses de jefe
de obra, dias de vacaciones y kilometros. Con el corte de `medide = 1` salen
**1.249.038,44 horas**, que es la cifra que esta feature existe para publicar.
Los 14 conceptos de HORA cubren 369 obras y 445 recursos, **todos de `cla = 1`**;
los MES son el grueso del euro porque ahi vive el coste de estructura de obra
(MES JEFE DE OBRA solo, 18,80 M EUR).

## Ficheros a crear

1. **`etl_sigrid/infrastructure/postgres/sql/stg/09_recursos.sql`**
   `TRUNCATE` + `INSERT` de `stg.recursos`. Lee `raw.res`, `raw.con`,
   `raw.auxrestip` y `raw.emp`. Capa: infrastructure.
2. **`etl_sigrid/infrastructure/postgres/sql/stg/10_partes_lineas.sql`**
   `TRUNCATE` + `INSERT` de `stg.partes_lineas`. Lee `raw.hmores`, `raw.hmo`,
   `raw.auxhor`, `raw.con` + `raw.obr` (para la marca de universo de obra).
3. **`etl_sigrid/infrastructure/postgres/sql/mart/07_horas_personal.sql`**
   `DROP VIEW IF EXISTS` + `CREATE VIEW mart.v_pbi_horas_obra_mes`.
4. **`tests/test_f057_personal.py`** — suite offline (R25).

## Ficheros a modificar

- **`sql/stg/01_ddl.sql`** — dos `CREATE TABLE IF NOT EXISTS` mas sus indices,
  al final del fichero. No se toca nada de lo existente.
- **`etl_sigrid/application/steps/build_stg_step.py`** — dos `_SubStep` nuevos
  **al final** de la lista, despues de `build_plan_mensual`:
  `_SubStep("build_recursos", "09_recursos.sql", "stg", "recursos")` y
  `_SubStep("build_partes_lineas", "10_partes_lineas.sql", "stg",
  "partes_lineas")`. **No entran en `FICHEROS_DEL_SELLO`** (ese sello es de la
  ventana de obras de F-025 y no tiene nada que ver con estos dos) ni llevan
  marcador de tramo ni puerta de disco: son `INSERT ... SELECT` planos sobre
  330.638 filas, sin recursion, sin `unnest` y sin explosion.
- **`config/diccionario/stg.yaml`** — fichas de `stg.recursos` y
  `stg.partes_lineas`.
- **`config/diccionario/mart.yaml`** — ficha de `mart.v_pbi_horas_obra_mes`.
- **`config/diccionario/00_global.yaml`** — subir `version` (24 -> 25). La lista
  de pendientes esta vacia y se queda vacia.
- **`docs/ARCHITECTURE.md`** — parrafo corto en la seccion de semantica Sigrid
  con la regla de la unidad (`auxhor.medide`, no `ext`).

## Ficheros que NO se tocan (los colindantes que tientan)

- `config/tables_sigrid.yaml` — **no se ingiere nada**. Ver «Riesgos», D5.
- `sql/stg/03_obras.sql` … `08_plan_mensual.sql` — ni una linea.
- `sql/maestro/04_centros_coste.sql` — F-073 no participa (R13).
- `sql/mart/01_ddl.sql`, `02_build_fact.sql`, `03_agg_categoria.sql` — la vista
  nueva va en fichero propio y no cuelga de `mart.fact_seguimiento_*`.
- `config/settings.py` / `DEFAULT_EXCLUDED_TABLES` — `raw.emp` y `raw.res`
  siguen fuera del rol del MCP (F-068). Lo que publica esta feature son objetos
  de `stg` y `mart`, que el rol si lee, y eso es exactamente lo buscado: el
  agente pregunta por la capa curada, no por la copia del origen.
- `config/objetos_pendientes.yaml` — los tres objetos se construyen aqui, no se
  declaran pendientes.

## Objetos publicados

### `stg.recursos` (TABLA) — grano: una fila por `raw.res` (2.618)

```
recurso_id BIGINT PK        res.ide  (= con.ide, propiedad de con 1:1)
codigo_recurso VARCHAR(24)  con.cod
nombre_recurso VARCHAR(255) con.res      -- DATO PERSONAL en las personas
clase VARCHAR(8)            CASE res.cla WHEN 1 'PERSONA' WHEN 0 'CONSUMO'
                                         WHEN 2 'MEDIO' ELSE 'OTRO' END
tipo_recurso_id BIGINT      res.restipide
tipo_recurso VARCHAR(64)    auxrestip.res   -- 'OFIC. 1a ALBANIL', 'GRUAS'...
activo BOOLEAN              (con.fecbaj = 0)          -- criterio Juan Romero
fecha_baja DATE             stg.fn_sigrid_date_to_date(con.fecbaj)
nif VARCHAR(24)             res.cif          -- DATO PERSONAL (autorizado)
empleado_id BIGINT          emp.ide via res.conide    -- 824 de 2.618
dni VARCHAR(24)             emp.dni          -- DATO PERSONAL (autorizado)
nombre_pila VARCHAR(64)     emp.nomnom
apellido1 / apellido2       emp.nomape1 / emp.nomape2
es_externo BOOLEAN          (res.prvide <> 0)
proveedor_id BIGINT         NULLIF(res.prvide, 0)
_built_at TIMESTAMP
```

`auxrestip` **no clasifica por si sola**: hay un JEFE DE GRUPO con `cla = 0` y
un CONSUMOS TELEFONO MOVIL con `cla = 2`, y 492 personas y 48 medios no tienen
tipo. **Manda `cla`**; el tipo es descriptivo.

El `LEFT JOIN` a `emp` va por `res.conide` y **tiene que ser
`LEFT JOIN LATERAL (... ORDER BY e.ide LIMIT 1)`**, igual que en
`maestro/04_centros_coste.sql`: hoy 3 recursos comparten `conide` y un `JOIN`
desnudo multiplicaria esas filas. El grano no puede depender de la suerte.

Indice: `(clase, activo)` y `(empleado_id)`.

### `stg.partes_lineas` (TABLA) — grano: una fila por `raw.hmores` (330.638)

```
linea_id BIGINT PK          hmores.ide
parte_id BIGINT             hmores.hmoide     -- 100 % informado
recurso_id BIGINT           hmores.reside     -- 330.628 de 330.638
obra_id BIGINT              NULLIF(hmores.obride, 0)   -- LA LINEA (R12)
en_seguimiento BOOLEAN      EXISTS obra en stg.obras
partida_id BIGINT           NULLIF(hmores.paride, 0)   -- 302.575
fecha DATE                  stg.fn_sigrid_date_to_date(hmores.fec)
anio INTEGER / mes INTEGER  hmores.ano / hmores.mes
tipo_hora_id BIGINT         hmores.horide
tipo_hora VARCHAR(64)       auxhor.res
unidad VARCHAR(12)          CASE auxhor.medide WHEN 1 'HORA' WHEN 2 'DIA'
                              WHEN 3 'MES' WHEN 19 'UD' ELSE 'DESCONOCIDA' END
cantidad NUMERIC(18,2)      hmores.can    -- NO SUMAR SIN FILTRAR unidad
precio NUMERIC(18,4)        hmores.pre
importe NUMERIC(18,2)       hmores.tot    -- con signo (9.119 negativas)
_built_at TIMESTAMP
```

`en_seguimiento` se resuelve con `EXISTS (SELECT 1 FROM stg.obras o WHERE
o.obra_id = ...)`, no replicando los filtros de `03_obras.sql`: duplicar esa
lista de codigos administrativos es como se desincronizan dos verdades. Por eso
los dos sub-pasos nuevos van **despues** de `build_obras` en la lista del step.

Indices: `(obra_id, anio, mes)`, `(recurso_id)`, `(partida_id)`, `(unidad)`.

### `mart.v_pbi_horas_obra_mes` (VISTA)

Grano: obra x ano x mes x tipo de recurso. `WHERE pl.unidad = 'HORA'`, cableado
en la vista. Columnas: `obra_id`, `codigo_obra`, `nombre_obra`, `anio`, `mes`,
`tipo_recurso`, `es_externo`, `recursos` (`COUNT(DISTINCT recurso_id)`),
`horas` (`SUM(cantidad)`), `importe` (`SUM(importe)`).

**No lleva nombre ni DNI.** No por privacidad —estan autorizados y viven en
`stg.recursos`— sino porque es un agregado: el nombre a este grano solo produce
filas de una persona disfrazadas de agregado. Quien quiera la persona va a
`stg.recursos`, que es donde esta y esta declarado.

## Riesgos y decisiones

**D1 · El eje es el RECURSO, no el empleado.** La relacion no es 1:1 en ninguna
direccion (R6). El hecho cuelga de `hmores.reside`, informado en 330.628 de
330.638; `emp` entra como atributo opcional del 31,5 % de los recursos. **`emp`
no se publica como dimension de plantilla**: 62 de sus 152 columnas vienen
vacias y su valor es agregado (rotacion, plantilla por departamento), que es
otra feature. Descartado hacer `emp` el maestro: dejaria fuera a los 530
recursos-persona sin ficha y a los 1.264 que no son personas.

**D2 · La obra sale de la linea.** Descartado `hmo` (la cabecera): 769 lineas
contradicen a su cabecera y la linea es la que lleva la partida. Descartado
`maestro.centros_coste`: la trampa de `apu`/F-045 no existe aqui porque
`hmores` trae la obra. Se deja escrito para que F-045 no herede una respuesta
que no es suya.

**D3 · El criterio de Juan Romero es bandera, no filtro.** Es la decision con
mas dinero detras: filtrar por `activo` en el hecho borraria **539.774,87 h
(43,2 %)** de 287 recursos. «En rojo» se traduce a `con.fecbaj > 0` —`res` no
tiene columna de baja— y vive en `stg.recursos.activo`.

**D4 · Datos personales: se publican nombre y DNI.** Autorizado por el humano el
2026-09-18 («el dni puede salir, no es un problema»). No se disena ofuscacion,
hash, truncado ni tabla aparte. Lo que **no** sube es el resto de la ficha de
`emp` (Seguridad Social, banco, domicilio, nacimiento, sexo, estado civil,
contacto, credenciales): la autorizacion es de nombre y DNI. La ficha del
diccionario declara que el objeto contiene datos personales.

**D5 · `auxmed` no se ingiere; la unidad va en un `CASE`.** Alternativa
descartada: anadir `auxmed` (38 filas) a `config/tables_sigrid.yaml`. Costaria
tocar la ingesta, `check-raw-recuentos` y la ficha de `raw` para traducir cuatro
literales estables (HORA, DIA, MES, ud), y esta feature tiene mandato de `stg` y
`mart`, no de ingesta. Precedente en el repositorio: `stg/02_ambitos.sql`
clasifica un catalogo de `raw` con un `CASE`. El seguro es R17: un `medide`
distinto sale como `DESCONOCIDA` y el test-guarda falla.

**D6 · Si sube a la superficie de consumo: si, con una sola vista.** El objetivo
de fondo del proyecto es que Negocio pregunte por el MCP, y las dos preguntas
del criterio 4 de la ficha tienen respuesta hoy mismo: 20 anos de historia
(2002-2026), 100 % de enganche con `stg.partidas` y 94,9 % del euro en obras del
seguimiento. Dejarlo en `stg` «hasta que haya un caso de uso escrito» seria
construir el dato y esconderlo. La vista existe porque la trampa de la unidad
(R18) merece un objeto donde no se pueda cometer.

**D7 · Coste en la nocturna.** Dos `INSERT ... SELECT` de 2.618 y 330.638 filas,
unos 60 MB. Es el 0,24 % de los 25 GB de la base y del orden de segundos frente
a las 3 h 45 de ventana. **El riesgo real es otro**: `build_stg` es la puerta de
F-024, asi que un fallo en estos dos sub-pasos impide construir `mart`. Se
mitiga poniendolos los ultimos —despues de `build_plan_mensual`, que es lo
critico— y manteniendo el SQL sin recursion, sin `unnest` y sin ventanas. Se
descarto un esquema modulo propio (`personal`, no bloqueante como `compras`)
porque el criterio de aceptacion de la ficha dice «escrito en stg»; si el humano
prefiere el modulo, el SQL se mueve tal cual y solo cambia el step.

**D8 · Lo que esta feature NO responde, y hay que declararlo.** El coste de
personal por obra **completo** no es `SUM(importe)` de HORA: el 71,7 % del euro
esta en las lineas de MES (estructura de obra). La vista publica horas; el euro
total por obra sale de `stg.partes_lineas` sin filtrar unidad, y eso lo dice la
ficha. Pasar de horas a euros con el precio de coste por recurso (`raw.reshor`,
8.949 filas) es F-061, no esto.
