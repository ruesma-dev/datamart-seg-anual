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

## Donde vive: el esquema modulo `personal`

Decision del humano del 2026-09-18, frente a meterlo en `stg`. Dos motivos:

1. **No bloquea.** `build_stg` es la puerta de F-024: un fallo del SQL de
   personal dentro de `build_stg` dejaria al `mart` sin construir esa noche. Un
   esquema modulo falla solo y `R-FRESCURA` avisa al consumidor.
2. **Los permisos se dan por esquema**, y ese fue el argumento decisivo. F-087
   crea un rol propio para Power BI con acceso a los esquemas de consumo; con
   nombre y DNI en un esquema propio, «Power BI si, datos de personal no» es un
   `GRANT`. Mezclados en `stg` —que ademas F-079 declaro consultable— habria que
   trocear permisos tabla a tabla. **CORREGIDO EL 2026-09-22: Power BI SI ve
   `personal`** (humano); el rol de F-087 lo incluye. Se deja como registro.

Efecto colateral aceptado: `personal.v_pbi_horas_obra_mes` **no lleva datos
personales** pero vive en el esquema restringible. Si algun dia Power BI
necesita las horas sin las personas, esa vista se mueve a `mart` y es un
fichero; no se parte el esquema por adelantado.

## Ficheros a crear

1. **`sql/personal/00_setup.sql`** — `CREATE SCHEMA IF NOT EXISTS personal`,
   `personal.fn_fecha(BIGINT) RETURNS DATE` (local, como
   `compras.fn_sigrid_date`, para no depender de `stg`) y los dos
   `CREATE TABLE IF NOT EXISTS` con sus indices.
2. **`sql/personal/01_recursos.sql`** — `TRUNCATE` + `INSERT` de
   `personal.recursos`. Lee `raw.res`, `raw.con`, `raw.auxrestip`, `raw.emp`.
3. **`sql/personal/02_partes_lineas.sql`** — `TRUNCATE` + `INSERT` de
   `personal.partes_lineas`. Lee `raw.hmores`, `raw.hmo`, `raw.auxhor` y
   `stg.obras` (marca de universo).
4. **`sql/personal/03_views.sql`** — `personal.v_pbi_horas_obra_mes`.
5. **`etl_sigrid/application/steps/build_personal_step.py`** — capa
   application. Plantilla exacta: `build_retenciones_step.py` (131 lineas), con
   su `_SubStep`, su tupla `SUB_PASOS` a nivel de modulo (es DATO, y sustituirla
   es lo unico que permite testear el guardian de `target_schema`) y su
   `run()` que deja fila en `_meta.etl_runs`.
   `name = "build_personal"`, `stage = "build_aux"`,
   `depends_on = ["build_stg"]`.
6. **`config/diccionario/personal.yaml`** — YAML de esquema nuevo, con las tres
   fichas, su `clave_negocio` y sus `relaciones`.
7. **`tests/test_f057_personal.py`** — suite offline (R28).

Todas las rutas SQL cuelgan de
`etl_sigrid/infrastructure/postgres/sql/`.

## Ficheros a modificar (la propagacion, que es donde se olvidan las cosas)

- **`etl_sigrid/domain/diccionario.py`** — `personal` en
  `ESQUEMAS_DEL_DATAMART`. Sin esto, `check-declarados` no mira el esquema y el
  validador del diccionario (R4) no exige su entrada.
- **`config/settings.py`** — `personal` en `DEFAULT_CONSUMPTION_SCHEMAS`.
  `raw.emp` y `raw.res` siguen en `DEFAULT_EXCLUDED_TABLES` (F-068) y ahi se
  quedan: lo que se abre es la capa curada, no la copia del origen.
- **`.env.example`** — misma lista en `PG_CONSUMPTION_SCHEMAS`.
- **`main.py`, tres puntos**: (a) comando `build-personal` suelto, junto a
  `build-compras`/`build-retenciones`; (b) `BuildPersonalStep(settings)` en
  `build_pipeline_steps`, **detras de `BuildRetencionesStep` y delante de
  `BuildCierreStep`** — el orden efectivo lo garantiza `depends_on`, la
  posicion es legibilidad; (c) el docstring de `run-all` y su recuento de los
  build de negocio, que hoy dice «cuatro».
- **`etl_sigrid/application/orchestrator.py`** — se **verifica** que el orden
  topologico coloca `build_personal` despues de `build_stg` sin tocar codigo: el
  orquestador es generico. Si el test demuestra que hace falta un cambio, se
  hace; si no, la tarea cierra con el test como prueba.
- **`etl_sigrid/application/steps/apply_grants_step.py`** — se **verifica** que
  concede el esquema nuevo leyendo `consumption_schema_list`, sin lista escrita
  a mano.
- **`config/diccionario/00_global.yaml`** — subir `version` (24 -> 25) y anadir
  la entrada del esquema `personal` en su bloque de esquemas. `pendientes` esta
  vacio y se queda vacio.
- **`docs/ARCHITECTURE.md`** — el esquema `personal` en la lista de modulos, y
  el parrafo de la unidad de `hmores.can` (`auxhor.medide`, no `ext`).
- **`CLAUDE.md`** — la linea del mapa de `sql/` gana `personal/`.
- **`azure-apps/datamart_seg_anual.md`** — el datamart expone un esquema nuevo
  con datos personales: se actualiza en este mismo trabajo, no despues.

## Ficheros que NO se tocan (los colindantes que tientan)

- `config/tables_sigrid.yaml` — **no se ingiere nada**. Ver D5.
- `sql/stg/*` y `sql/mart/*` — ni una linea. En particular `01_ddl.sql` de `stg`
  y `build_stg_step.py`, que era el diseno anterior y ya no.
- `sql/maestro/04_centros_coste.sql` — F-073 no participa (R13).
- `config/objetos_pendientes.yaml` — los tres objetos se construyen aqui.
- `check-unicidad` y `check-relaciones` (el codigo): se alimentan del
  diccionario, asi que cubren `personal` en cuanto `personal.yaml` declara
  `clave_negocio` y `relaciones`. Lo que hay que escribir es el YAML, no el
  comando — y un test que lo demuestre.

## Objetos publicados

### `personal.recursos` (TABLA) — grano: una fila por `raw.res` (2.618)

```
recurso_id BIGINT PK        res.ide  (= con.ide, propiedad de con 1:1)
codigo_recurso VARCHAR(24)  con.cod
nombre_recurso VARCHAR(255) con.res      -- DATO PERSONAL en las personas
clase VARCHAR(8)            CASE res.cla WHEN 1 'PERSONA' WHEN 0 'CONSUMO'
                                         WHEN 2 'MEDIO' ELSE 'OTRO' END
tipo_recurso_id BIGINT      res.restipide
tipo_recurso VARCHAR(64)    auxrestip.res   -- 'OFIC. 1a ALBANIL', 'GRUAS'...
activo BOOLEAN              (con.fecbaj = 0)          -- criterio Juan Romero
fecha_baja DATE             personal.fn_fecha(con.fecbaj)
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

Indices: `(clase, activo)` y `(empleado_id)`. `clave_negocio`: `recurso_id`.

### `personal.partes_lineas` (TABLA) — grano: una fila por `raw.hmores` (330.638)

```
linea_id BIGINT PK          hmores.ide
parte_id BIGINT             hmores.hmoide     -- 100 % informado
recurso_id BIGINT           hmores.reside     -- 330.628 de 330.638
obra_id BIGINT              NULLIF(hmores.obride, 0)   -- LA LINEA (R12)
en_seguimiento BOOLEAN      EXISTS obra en stg.obras
partida_id BIGINT           NULLIF(hmores.paride, 0)   -- 302.575
fecha DATE                  personal.fn_fecha(hmores.fec)
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
o.obra_id = ...)`, no replicando los filtros de `stg/03_obras.sql`: duplicar esa
lista de codigos administrativos es como se desincronizan dos verdades. Es la
unica lectura fuera de `raw`, y es la que fija `depends_on = ["build_stg"]`.

Indices: `(obra_id, anio, mes)`, `(recurso_id)`, `(partida_id)`, `(unidad)`.
`clave_negocio`: `linea_id`. Relaciones declaradas: `obra_id -> maestro.obras`,
`partida_id -> stg.partidas`, `recurso_id -> personal.recursos`.

### `personal.v_pbi_horas_obra_mes` (VISTA)

Grano: obra x ano x mes x tipo de recurso. `WHERE pl.unidad = 'HORA'`, cableado
en la vista. Columnas: `obra_id`, `codigo_obra`, `nombre_obra`, `anio`, `mes`,
`tipo_recurso`, `es_externo`, `recursos` (`COUNT(DISTINCT recurso_id)`),
`horas` (`SUM(cantidad)`), `importe` (`SUM(importe)`).

**No lleva nombre ni DNI.** No por privacidad —estan autorizados y viven en
`personal.recursos`— sino porque es un agregado: el nombre a este grano solo
produce filas de una persona disfrazadas de agregado.

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
tiene columna de baja— y vive en `personal.recursos.activo`.

**D4 · Datos personales: se publican nombre y DNI.** Autorizado por el humano el
2026-09-18 («el dni puede salir, no es un problema»). No se disena ofuscacion,
hash, truncado ni tabla aparte. Lo que **no** sube es el resto de la ficha de
`emp` (Seguridad Social, banco, domicilio, nacimiento, sexo, estado civil,
contacto, credenciales). La ficha del diccionario declara que el objeto contiene
datos personales, y el esquema propio es lo que hace que ese limite se pueda
imponer con un `GRANT` (F-087).

**D5 · `auxmed` no se ingiere; la unidad va en un `CASE`.** Alternativa
descartada: anadir `auxmed` (38 filas) a `config/tables_sigrid.yaml`. Costaria
tocar la ingesta, `check-raw-recuentos` y la ficha de `raw` para traducir cuatro
literales estables (HORA, DIA, MES, ud), y esta feature no es de ingesta.
Precedente en el repositorio: `stg/02_ambitos.sql` clasifica un catalogo de
`raw` con un `CASE`. El seguro es R17: un `medide` distinto sale como
`DESCONOCIDA` y el test-guarda falla.

**D6 · Si sube a la superficie de consumo: si.** El objetivo de fondo del
proyecto es que Negocio pregunte por el MCP, y las dos preguntas del criterio 4
de la ficha tienen respuesta hoy mismo: 20 anos de historia (2002-2026), **100 %
de `paride` existe y es de la misma obra** (302.575 de 302.575) y **94,9 % del
euro en obras del seguimiento**. Dejarlo sin publicar «hasta que haya un caso de
uso escrito» seria construir el dato y esconderlo.

**D7 · Coste en la nocturna.** Dos `INSERT ... SELECT` de 2.618 y 330.638 filas,
unos 60 MB: el 0,24 % de los 25 GB de la base, del orden de segundos frente a
las 3 h 45 de ventana. Con el esquema modulo, ademas, **un fallo no arrastra a
nadie**: `build_personal` no es `depends_on` de ningun paso.

**D8 · Lo que esta feature NO responde, y hay que declararlo.** El coste de
personal por obra **completo** no es `SUM(importe)` de HORA: el 71,7 % del euro
esta en las lineas de MES (estructura de obra). La vista publica horas; el euro
total por obra sale de `personal.partes_lineas` sin filtrar unidad, y eso lo
dice la ficha. Pasar de horas a euros con el precio de coste por recurso
(`raw.reshor`, 8.949 filas) es F-061, no esto.
