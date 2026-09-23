<!-- progress/current.md -->
# Estado actual · 2026-09-09 (miercoles; F-025, F-068 y F-066 cerradas)

> **PURGADO tres veces.** C2 pide que este fichero describa **solo la sesion
> activa**. El 2026-09-06 bajo de 1.263 a 638 lineas; el 2026-09-09 (pasada 3
> del review de F-066) se le quitaron las 253 lineas de la fase 7 de F-025; y
> hoy, al cerrar F-066, se retiran sus tres secciones y la de la averia
> nocturna del 07, ya resuelta. **Nada se pierde**: F-025, F-068 y F-066 tienen
> su resumen en `progress/history.md`, y el detalle vive en los informes
> `impl_*`/`review_*`/`incidencia_*` de `progress/` y en las specs.

## 2026-09-22 · F-094 DESPLEGADA (tag `r20260922-2350`)

Imagen **`acralbaranesdev.azurecr.io/datamart-seg-anual:r20260922-2350`**,
publicada y confirmada en el job con `az containerapp job show`: imagen correcta,
cron intacto (`0 0 * * *`), 1 reintento, timeout 25.200 s. Sustituye a
`r20260922-1158` (F-057). **Ojo con la cabecera de `85_update_job.ps1`**: anuncia
un tag calculado con la hora (`r20260922-2353`) que NO existe; el bueno es el que
dice «Imagen nueva» y el que confirma `job show`.

`main` con los cuatro merges pasa `init.sh` con **5.043 tests en verde** (4 h 17
min, maquina compartida con los subagentes); el unico KO es la regla «no se
trabaja en main», esperable.

**La nocturna del 23 construira `retenciones` con el estado saneado y la obra
real, y publicara el diccionario 26.** Despues hay que **reiniciar el MCP** (su
cache, F-089) o seguira sirviendo los 34,7 M EUR falsos. **`git push origin main`
SIGUE PENDIENTE**: lo bloqueo el clasificador de permisos, no el humano.

## F-094 · CERRADA (done, 2026-09-22) · QUEDAN LAS VERIFICACIONES MANUAL DEL HUMANO

Rama `feature/F-094-retenciones-estado-vivo`, `sdd=false`, rigor `estandar`.
Informe: `progress/impl_F-094.md`.

- **Estado de PROVEEDOR** en `retenciones.movimientos`: de la ficha `raw.con`
  del propio efecto. BAJA (`fecbaj <> 0` o `est` 14/15) > LIQUIDADA (`fecrea`
  o `est` 10) > VIVA. Medido en solo lectura: **VIVA 8.345.506,03 € (7.752)**,
  LIQUIDADA 12.754.011,79 (2.368), BAJA 18.691.779,56 (15.511); FERMALUX
  64.201,96. No se borran filas (25.631).
- **CLIENTE sin cambios** en el estado (criterio de `pag` no vale en `cob`).
- Diccionario `version` 26: **158 objetos, 1022 columnas, 69 de consumo**
  (+7 columnas: `estado_sigrid`, `fecha_baja` y `centro_coste_id` en
  `movimientos`, y `num_bajas`/`importe_baja` en las vistas de entidad y
  resumen).
- Ampliacion aprobada el 2026-09-22 (H6 de F-095, absorbe el resto de F-045):
  `obra_id` es la obra real via `maestro.centros_coste` y el centro se publica
  en `centro_coste_id`. Medido: 262 de 262 `obra_id` casan en `maestro.obras`
  (antes 0 de 262); mismas 533 filas sin obra. F-045 queda para retirar como
  absorbida (lo hace el lider).

### Verificaciones MANUAL (humano), en este orden

Copiadas de `progress/impl_F-094.md` §«Verificaciones MANUAL pendientes». Dos
de ellas (2 y 3) cierran el acceptance 4. **El orden importa: build → checks →
publicar.**

1. `python main.py build-retenciones`
2. `python main.py check-unicidad` — las claves de `retenciones` deben salir
   OK. **El comando sigue saliendo con código 1** por
   `cierre.v_pbi_planif_vs_real`, que es F-051 y previo: no es de F-094.
3. `python main.py check-relaciones` — `obra_id -> maestro.obras.obra_id` debe
   dar **262 de 262** (antes, con la relacion vieja, 0 de 261) y
   `centro_coste_id -> maestro.centros_coste` completo. **Si se lanza ANTES del
   build sale KO**: la relacion nueva se comprueba contra la tabla vieja.
4. `python main.py publicar-diccionario`
5. Consultas de contraste tras el build (cifras del 2026-09-22; se moveran con
   la ingesta):
   ```sql
   SELECT sentido, estado, count(*), sum(importe) FROM retenciones.movimientos GROUP BY 1,2 ORDER BY 1,2;
   -- PROVEEDOR VIVA 7.752 / 8.345.506,03 · LIQUIDADA 2.368 / 12.754.011,79 · BAJA 15.511 / 18.691.779,56
   SELECT saldo_vivo, importe_liquidado, importe_baja FROM retenciones.v_pbi_retencion_entidad
    WHERE sentido='PROVEEDOR' AND entidad_id=1958815;          -- 64.201,96 · 17.246,76 · 17.246,76
   SELECT * FROM retenciones.v_pbi_retencion_resumen;          -- num_movimientos = vivas+liquidadas+bajas
   SELECT count(DISTINCT m.obra_id), count(DISTINCT o.obra_id)
     FROM retenciones.movimientos m LEFT JOIN maestro.obras o USING (obra_id);   -- 262 · 262
   ```
6. Por el MCP, tras `publicar-diccionario`: `contexto_bbdd` debe servir la
   **version 26** y ya no los 34,7 M€. **Reiniciar antes el MCP**: cachea el
   diccionario hasta reiniciar (F-089).
7. Aplicar en `azure-apps/datamart_seg_anual.md` (no commiteado alli) el
   parrafo propuesto en `progress/impl_F-094.md` §«`azure-apps/datamart_seg_anual.md`»,
   tras la linea 447: `obra_id` pasa a ser la obra de `maestro.obras` (el
   centro va en `centro_coste_id`), rompe a quien uniera `obra_id` con
   `cierre.v_pbi_cierre_cabecera.centro_coste_ide`, PROVEEDOR gana `BAJA` y
   las columnas nuevas.

## F-051 · SPEC APROBADA, `spec_ready` (2026-09-22)

Rama `feature/F-051-nombre-mes-real` (desde `chore/fichas-2026-09-22`), rigor
`critico`, prioridad 1. **Aprobada** con D1–D9 y el matiz de D5 (texto ilegible →
fecha FIN, en todas las fases: 34 cambian de mes, 8 con dinero). Entregado
`specs/F-051-nombre-mes-real/` (requirements 150/150, design 250/250, 22 tareas)
y **resumen con toda la línea base medida en `progress/spec_F-051.md`**. La ficha
recoge las tres decisiones del humano del 22-09 y lo confirmado por Juan Romero.

Qué decide: cada fila real en el mes de su TEXTO, decidido una sola vez en
`stg.plan_mensual.anio_mes` y leído por `mart` y `cierre`; fase de rango → todo
al mes del texto con filas de relleno a 0 desde `fecini`, sin pisar meses con
cierre propio; vista `v_pbi_planif_vs_real` blindada. Comprobado en Sigrid que
`obrfasamb` no guarda periodo por ámbito: la fase es por obra.

**Decisiones tomadas (D1–D9, `design.md` §10)**: qué es «un mes
que ya tiene datos», F-042 sobre el mes del texto, qué partidas llevan relleno
(~1,34 M filas), parser nuevo solo en `stg` (rango → último mes, años 00–19,
«2.013»), sin texto → mes de `fecfin`, nada de relleno tras el mes del texto,
exención de mutación como F-042, publicar `es_relleno`, y reducir F-050 +
fichar los 5 huecos de numeración de Sigrid (0371: +4,29 M€ en `mart`): la
ficha propuesta, lista para el líder, en `progress/spec_F-051.md` §9.

`bash harness/init.sh` en el worktree del spec-author sale en rojo por entorno,
no por la spec: `test_f006_t26_cli_dry_run_no_toca_la_base` necesita el `.env`,
que el worktree no tiene, y la puerta de cobertura mide los cambios de
`chore/fichas-2026-09-22` frente a `main`. La puerta de tamaño de F-051, en OK.

## F-057 · IMPLEMENTADA, PENDIENTE DE REVIEW (2026-09-18)

Rama `feature/F-057-recursos-empleados-partes`, `sdd=true`, rigor `estandar`,
prioridad 1. Sigue `in_progress`: el cierre lo hace el lider tras el APROBADO.

**Informe del implementer: `progress/impl_F-057.md`.** El esquema `personal`
queda construido en el repositorio con sus cuatro objetos, los doce puntos de
propagacion cerrados y la suite offline de 68 tests en verde. **Lo que NO se ha
hecho, y es deliberado: construir en la base.** Contra Sigrid y el Postgres de
produccion solo lecturas; las cifras de la spec quedan como verificacion MANUAL
del humano (T23 y T24), con sus comandos exactos en el informe.

**El diccionario del arbol sube a 158 objetos, 1015 columnas y 69 fichas de
consumo**, y su `version` de 24 a **25**: los tres objetos publicados
(`personal.recursos` con 17 columnas, `personal.partes_lineas` con 16 y
`personal.v_pbi_horas_obra_mes` con 10) mas la funcion local
`personal.fn_fecha`, que no es de consumo. `pendientes` sigue vacio: aqui no se
aplaza ninguna ficha.

Dos reglas duras cambian de alcance y hay que saberlo antes de leer un dato:
`R-FRESCURA` pasa de cuatro esquemas a **cinco** --`build_personal` tampoco es
dependencia de ningun paso, asi que puede quedarse atras sin tumbar la noche--
y `R-SIGRID-CON` gana `auxhor`, `auxrestip`, `hmores` y `res` en su lista de
campos que el ETL lee sin pasar por `con`.

**Desviacion unica respecto al diseno, y su motivo**: `02_partes_lineas.sql` NO
lee `raw.hmo`. El diseno la lista entre sus fuentes, pero R12 y D2 mandan que
la obra salga de la LINEA y la cabecera no aporta ninguna columna publicada
--`parte_id` ya viene en `hmores.hmoide`--. Un JOIN sin uso a la cabecera es
justo por donde se cuela la atribucion equivocada, asi que se veta con un test.

### La spec, tal y como se aprobo (2026-09-18)



Rama `feature/F-057-recursos-empleados-partes`, `sdd=true`, rigor `estandar`,
prioridad 1. Sigue `in_progress`: la spec no cambia el estado.

Entregado `specs/F-057-recursos-empleados-partes/` (requirements 150/150, design
246/250, 25 tareas). **Resumen y cifras: `progress/spec_F-057.md`.**

Tres objetos a construir en un **esquema modulo propio `personal`**, hermano de
`compras`, `maestro` y `retenciones`: `personal.recursos`,
`personal.partes_lineas` y `personal.v_pbi_horas_obra_mes`. Nada de ingesta
(F-066 y F-074 ya la hicieron).

**EL HALLAZGO**: la unidad de `hmores.can` la fija **`auxhor.medide`**
(1 HORA, 2 DIA, 3 MES, 19 ud), **no `auxhor.ext`, que esta a cero en las 60
filas**. Sumar `can` en bruto da 1.837.201,23 mezclando 1.249.038,44 horas con
18.009,38 meses, 4.225,46 dias y kilometros. El **71,7 % del euro (70,46 M de
98,28 M) esta en las lineas de MES**, no en las de hora.

**Decisiones**: el eje es el RECURSO (la relacion `res`-`emp` no es 1:1 en
ninguna direccion: 824 de 2.618 y 805 de 1.354, con 797 reciprocos y 3 recursos
compartiendo `conide`); la obra se ata por `hmores.obride` de la LINEA (769
lineas contradicen su cabecera) y **`maestro.centros_coste` de F-073 no se usa
porque la trampa de `apu`/F-045 no aplica aqui**; «en rojo» = `con.fecbaj > 0` y
es BANDERA, no filtro, porque filtrar el hecho borraria el **43,2 % de las
horas** (539.774,87 h de 287 recursos de baja).

**DATOS PERSONALES**: se publican **nombre y DNI**, autorizado por el humano el
2026-09-18 («el dni puede salir, no es un problema») y citado en el requisito
R7. Sin ofuscacion ni hash. El resto de la ficha de `emp` (Seguridad Social,
banco, domicilio, nacimiento, sexo, estado civil, contacto, credenciales) NO
sube.

### DECIDIDO por el humano el 2026-09-18: esquema modulo, no `stg`

Deje abierto `stg` vs esquema propio y el humano eligio **`personal`**. Razon
decisiva: **los permisos se dan por esquema**, y F-087 crea un rol para Power BI
con acceso solo a los esquemas de consumo; con nombre y DNI en un esquema
propio, «Power BI si, datos de personal no» es un `GRANT`. Segunda razon: **no
bloquea** —`build_stg` es la puerta de F-024 y un fallo ahi deja al `mart` sin
construir; un modulo falla solo y `R-FRESCURA` avisa—.

El SQL no cambia; cambia donde vive. `build_personal` va detras de
`build_retenciones` y delante de `build_cierre`, con
`depends_on = ["build_stg"]` (lee `stg.obras`) y **sin que ningun paso lo
declare como dependencia**. La propagacion son **doce puntos, uno por tarea**
(T10-T20): step, orquestador, tres puntos de `main.py`, `apply_grants` +
`DEFAULT_CONSUMPTION_SCHEMAS` + `.env.example`, `ESQUEMAS_DEL_DATAMART`,
`check-declarados`, `check-unicidad`, `check-relaciones`,
`config/diccionario/personal.yaml` y los tests de cada uno.

### Lo que sigue abierto

**Declarado y no resuelto a proposito**: el coste de personal por obra COMPLETO
no es la suma de las horas; el 71,7 % del euro son lineas de MES. Pasar de horas
a euros con `raw.reshor` es F-061.

## F-084 · IMPLEMENTACION ENTREGADA (2026-09-16)

Rama `feature/F-084-estado-del-contrato`, rigor `estandar`, `sdd=false`.
Informe: `progress/impl_F-084.md`. Cinco tareas, un commit cada una.

**QUE SE PUBLICA**: `compras.contratos` gana tres columnas al final —
`estado_id`, `estado_codigo` y `estado`—, leidas de `con.est` con `tip = 44` y
traducidas por la pareja (tipo, estado). Las **doce** de siempre no se tocan:
verificado en solo lectura columna a columna contra la tabla viva, **0 filas
que no casan de 18.978**, y 18.978 `contrato_id` distintos.

**LA DECISION DE DISENO (criterio 6)**: la traduccion del estado **se factoriza
en vez de duplicarse**. Vive una sola vez en
`compras.fn_estado_documento(p_tip, p_est)` (`compras/00_setup.sql`) y la
llaman los dos bloques, CONTRATOS con 44 y FACTURAS con 15. Lo que se gana no
son lineas: **el tipo de documento pasa a ser argumento obligatorio**, asi que
la union «solo por estado_id» ya no se puede escribir. Los cuatro tests de
F-083 que miraban el texto del lateral se adaptan al sitio nuevo sin aflojar
ninguna garantia.

**LO QUE NO SE PUEDE RESPONDER, y la ficha lo declara**: la ANTIGUEDAD del
estado. Se listan los **818** contratos en «Enviado» (de 567 proveedores y 241
obras), pero no cuanto llevan: el datamart no guarda cuando cambio el estado
—la foto diaria es de **F-067**— y `con.tiemod` es la ultima modificacion del
DOCUMENTO, que **no es la fecha del cambio de estado** y ademas vive en `raw`,
que el MCP no ve. **Por eso F-084 no publica ninguna columna de antiguedad.**
Si el humano prefiere publicar el proxy, es una linea de SQL y una de ficha.

**EL HALLAZGO**: el circuito de firma NO sirve para el contrato. De las 70.346
firmas de `raw.confir` hay **CERO de contrato** (comparativos 66.060, facturas
3.452, obras 796); en el origen tampoco estan. Escrito en la ficha y en la
cabecera del SQL.

**MANUAL PENDIENTE (lo hace el humano)**: `python main.py build-compras`, luego
`python main.py status` y `python main.py publicar-diccionario`. `build-compras`
es la unica verificacion real del CUERPO de la funcion —aqui solo se pudo
validar el parseo, en transaccion READ ONLY— y lo unico que confirma el grano
en la base. Despues, por el MCP y sin explicarle nada: «que contratos estan
enviados y sin firmar» debe dar los 818; y «cuantos llevan mas de tres semanas
enviados» debe responder que **no se puede saber**.

## F-083 · IMPLEMENTACION ENTREGADA (2026-09-16)

Rama `feature/F-083-estado-de-la-factura`, rigor `estandar`, `sdd=false`.
Informe: `progress/impl_F-083.md`. Cinco tareas, un commit cada una.

**QUE SE PUBLICA**: `compras.facturas` gana cinco columnas al final —
`estado_id`, `estado_codigo`, `estado` (el del DOCUMENTO en su circuito de
aprobacion, leido de `con.est` con `tip = 15` y traducido por la pareja
(tipo, estado)), `fecha_factura` (`dcf.fecdoc`) y `fecha_alta` (`con.fec`)—.
**Las diez de siempre, intactas y en su orden**, `fecha` incluida.

**VERIFICACIONES MANUALES PENDIENTES — LAS EJECUTA EL HUMANO**, porque
construir contra Azure no lo autoriza un agente. En este orden:

```
python main.py build-compras
python main.py check-unicidad
python main.py publicar-diccionario
```

`check-unicidad` es el que confirma en la base lo que aqui solo se pudo
comprobar sobre el SELECT en solo lectura: que `factura_id` sigue siendo
clave y que la traduccion del estado no ha multiplicado ni una fila.

y despues, por el MCP y **sin explicarle nada en el prompt** (criterio 6):
«de las facturas vencidas y sin pagar, cuales estan contabilizadas sin
aprobar, cuales retenidas y cuales rechazadas». La respuesta correcta tiene
que distinguir el estado de la FACTURA del `estado_pago` del efecto y decir
que en FRARET (retenida) no hay ninguna.

**LO QUE HAY QUE SABER Y NO SE VE EN EL DIFF**: el estado **no esta en `dcf`**,
esta en `con.est`; **el literal del estado NO es unico** (`REC` y `REC_ADM` se
llaman los dos «Recibida»), asi que se filtra por `estado_codigo`; y las dos
fechas **se separan en el 77,8 % de las facturas**, con `fecha_factura`
tecleada a mano y con valores absurdos que no se filtran.

## F-073 · IMPLEMENTACION ENTREGADA (2026-09-10)

Rama `feature/F-073-tablas-nuevas-y-enriquecimiento`, rigor `estandar`,
`sdd=true`. Informe: `progress/impl_F-073.md`. Las 21 tareas de `tasks.md`,
hechas y con un commit cada una.

**QUE SE PUBLICA**: `maestro.centros_coste` (el puente centro de coste -> obra,
804 filas y 683 con obra), `maestro.estados_documento` (las 193 de `conest`),
`compras.formas_pago` (las 69 de `auxpag` con su medio) y `maestro.obras` con
once columnas nuevas -direccion, municipio y provincia con su id, el estado ya
traducido y las dos marcas-. **No se toca `compras.contratos` ni
`compras.facturas`**: ese cableado es F-067 y F-080.

**LO QUE HAY QUE SABER Y NO SE VE EN EL DIFF:**

* `build_maestros` **ahora depende de `build_stg`**. Si `build_stg` falla, el
  orquestador marca `build_maestros` como SKIPPED, cosa que antes no pasaba. Es
  asumible porque los seis objetos de `maestro` son vistas.
* **La direccion viene informada en un tercio de las obras** (dir1 33,1 %,
  municipio 31,9 %, provincia 33,2 %, dir2 5,1 %). No es un fallo del ETL: la
  ficha lo declara y «no consta» es la respuesta correcta para dos de cada tres.
* `tiene_seguimiento` se mide en `stg.plan_mensual` y es **superconjunto** del
  hecho: 368 con plan frente a 349 con filas en `mart.fact_seguimiento_mensual`,
  **19 de diferencia y ninguna al reves**.
* **`config/tables_sigrid.yaml` se equivocaba** al decir que el nombre del medio
  de pago es `auxefp.est`: `est` viene vacio o nulo en las 10 filas y el nombre
  esta en `res`. Medido el 2026-09-10, fuera del alcance de F-073 y **corregido
  el 2026-09-11 por F-081**, que ademas encontro la misma mentira en la entrada
  de `cen`. Ver la seccion de F-081 al final de este fichero.

### VERIFICACIONES MANUAL (humano) PENDIENTES DE F-073

Ningun agente las ejecuta: las tres primeras dependen de que el build haya
corrido contra Azure, y publicar es una escritura. **En este orden**, y la 2 no
significa nada antes de la 1.

1. **Construir los objetos nuevos.** Sin esto no existen en la base y todo lo
   de abajo mide el mundo de ayer.

       python main.py build-maestros
       python main.py build-compras

2. **Los recuentos de las tres vistas nuevas**, en solo lectura. Los valores
   esperados estan medidos contra `raw` el 2026-09-10 (T1 y T2 del informe):

       SELECT COUNT(*) AS filas,
              COUNT(DISTINCT centro_coste_id) AS centros,
              COUNT(obra_id) AS con_obra
       FROM maestro.centros_coste;
       -- esperado: 804 / 804 / 683

       SELECT COUNT(*) FROM maestro.estados_documento;   -- esperado: 193
       SELECT COUNT(*) FROM compras.formas_pago;         -- esperado: 69
       SELECT COUNT(*) FROM maestro.obras;               -- esperado: 921

3. **Que `maestro.obras` no ha perdido ninguna columna** (R18). Las diez de
   siempre siguen, y ahora son 21:

       SELECT column_name FROM information_schema.columns
       WHERE table_schema = 'maestro' AND table_name = 'obras'
       ORDER BY ordinal_position;
       -- esperado: 21 columnas, y entre ellas obra_id, codigo_obra,
       -- nombre_obra, estado_id, fecha_alta, fecha_baja, es_activa,
       -- cliente_id, codigo_cliente y nombre_cliente

4. **Las dos puertas del diccionario:**

       python main.py check-declarados
       python main.py check-diccionario

   Las dos con **codigo 0**. `check-diccionario` tiene que ver **142 fichas y
   142 objetos**, biyeccion exacta.

5. **Publicar el diccionario (version 19, hash `7f5e890fd5f7`).** Es una
   **escritura contra Azure**: la autoriza el humano, no un agente. Lo publicado
   hoy es la version 18.

   > **CORREGIDO EL 2026-09-17, y las dos mitades de esta frase han caducado.**
   > Lo encontro el reviewer de F-084. (a) La version publicada **no es la 18**:
   > el 2026-09-16 la nocturna dejo la **21** y el trabajo de F-083 la subio a la
   > **23**. (b) Y lo mas importante: **publicar ya no es una escritura que
   > autorice el humano caso por caso**, porque desde **F-047**
   > `publicar_diccionario` es un paso de `run-all` y **la nocturna publica
   > sola**. Lo que sigue necesitando autorizacion expresa es publicar **a mano y
   > fuera de la ventana**. Esta nota se queda aqui en vez de borrar el parrafo,
   > porque el parrafo es el registro de lo que se penso entonces.

       python main.py publicar-diccionario

6. **LA PRUEBA DE QUE EL PUENTE RESUELVE F-045.** Es la razon por la que
   `maestro.centros_coste` existe, y es solo lectura. `retenciones.movimientos`
   trae 261 valores distintos en `obra_id` que en realidad son centros de coste:

       SELECT COUNT(DISTINCT m.obra_id) AS valores,
              COUNT(DISTINCT c.centro_coste_id) AS casan
       FROM retenciones.movimientos m
       LEFT JOIN maestro.centros_coste c ON c.centro_coste_id = m.obra_id;
       -- esperado: 261 / 261

   **F-073 no toca `sql/retenciones/**`**: arreglar `movimientos.obra_id` con
   este puente es F-045. Aqui solo se comprueba que el puente le sirve.

## F-080 · NACE EL 2026-09-10 DEL CORREO DE JUAN ROMERO (lo mas nuevo)

Rama `feature/F-080-vencimientos-forma-pago-y-texto-factura`, prioridad 7,
rigor `estandar`, `sdd=true`. Fichada en `4871f89`. **SPEC ESCRITA el
2026-09-10 en `specs/F-080-vencimientos-forma-pago-y-texto-factura/`
(148 / 217 / 29 tareas). ESPERA APROBACION DEL HUMANO: es la PARADA 1, no se
escribe una linea de codigo hasta entonces.**

Correo de Juan Romero (Dir. Admon y Control de Costes) del 2026-09-10,
«PETICIONES (TEXTO Y VENCIMIENTOS/FORMAS PAGO)», con dos capturas de la ficha
de factura de compra: quiere leer la pestaña TEXTO, acceder a la pestaña
VENCIMIENTOS y cruzar el vencimiento con la forma de pago del contrato.

**EL HALLAZGO QUE CAMBIA LA PREMISA, medido contra Sigrid ese dia en solo
lectura: el texto NO esta en `dcf.tex`.** Esta en el memo de la superclase
`con.tex`. `dcf.tex` viene informado en **474 de 165.658** facturas (0,3 %);
`con.tex` para `tip = 15`, en **108.445 de 165.658** (65,5 %). La factura de
la captura (`con.cod` FR26/06051, `ide` 2776822) tiene 797 bytes en `con.tex`
y NULL en `dcf.tex`. **Derivarlo por el nombre del campo habria salido falso**:
es el error de F-006 otra vez, el que vigila
`tests/test_f006_fuente_que_gobierna.py`.

`con.tex` esta **excluido hoy** de la ingesta con el comentario «texto libre
largo, no lo usamos en seguimiento», que es justo lo que la peticion
desmiente. El precedente de como se revierte esta hecho una vez: `prvcer.tex`
en F-074.

**Lo demas medido, y esta todo en la ficha de `harness/features.json` y en
`progress/explore_F-080_*.md`:** `con.tex` entero pesa 33,7 MB (30,6 MB si
solo facturas y contratos); `raw.pag` ya se ingiere entero, con 255.001
efectos y el 99,99 % de las facturas cubiertas, asi que **los vencimientos no
cuestan ingesta**; faltan dos catalogos, `auxnap` (3 filas) y `auxban`
(1.666); y `contex` (2.855 filas) **no es** la pestaña Texto.

**TRAMPA A NO REPETIR**: `pag.fecrea = 0` NO significa «vivo». Son 158.503
efectos, el 62 %, e incluyen vencimientos pasados sin puntear. La cartera viva
que midio F-037 son 10.607 pagos.

**Riesgo abierto que resuelve la spec**: `raw.con` tiene 2.185.737 filas y se
ingiere entera cada noche. Traer una columna memo puede obligar a bajar su
`page_size`, como `obrparpre.planif`. **Se mide antes de desplegar.**

**DECISIONES DEL HUMANO, para que nadie las reabra**: feature nueva y acotada
(no repartir entre F-067 y F-037); el texto se guarda entero **y ademas**
parseado en una vista; se publica para facturas y contratos; y **el riesgo de
datos personales del texto lo descarto expresamente** («no me preocupa el tema
riesgos de datos, ignoralo»).

**FRONTERA**: la cartera completa de cobros y pagos sigue siendo F-037 fase 1.
Deuda declarada: cuando llegue F-037 se decide si absorbe el objeto de
vencimientos o lo deja como vista suya.

### Lo que decide la spec de F-080, y las cinco decisiones abiertas

**Cinco objetos nuevos en `compras`**, todos detras de `04_formas_pago` de
F-073: `vencimientos` (tabla, PK `vencimiento_id`, una fila por efecto de
`raw.pag` de una factura de compra), `v_facturas_pago` (vista, una fila por
factura, con la forma de pago resuelta contra `compras.formas_pago` y el
resumen de efectos), `v_control_forma_pago` (vista, **una fila por par
factura-contrato**, con el mismo enlace que ya usa `v_pbi_contrato_consumo`),
`documento_texto` (tabla, el memo integro de `tip` 15 y 44) y
`v_documento_comentarios` (vista, un comentario por fila). Tres ficheros SQL
nuevos: `05_vencimientos.sql`, `06_pago_factura.sql`, `07_texto.sql`. **No se
tocan `01_documentos.sql`, `02_fact_linea.sql` ni `03_views.sql`**, que son de
F-067.

**El parseo del memo va en SQL**, con los dos literales medidos escritos una
sola vez en `etl_sigrid/domain/texto_comentarios.py` como oraculo ejecutable
(patron F-052: `arbol_partidas.py` + `test_f052_sql.py`). Lo que no casa con el
sello se publica igual, entero, con `sello_reconocido` en falso.

**El coste de ventana se mide en dos tiempos antes de desplegar**: medicion A
en solo lectura contra Sigrid (segundos y bytes por pagina de `con` con y sin
`tex`, a 10.000 y 5.000 filas) y medicion B, MANUAL, comparando la fila
`ingest_raw.con` de `_meta.etl_runs` antes y despues.

**LAS CINCO DECISIONES ABIERTAS** (detalle en el cierre de `tasks.md`):

1. **Presupuesto de ventana nocturna**: no existe escrito. La spec propone
   **4 h** (hoy 3 h 25 min, antes de F-025 4 h 52). Es el numero con el que se
   juzga si hay que bajar el `page_size` de `con`.
2. **Corte de rendimiento de la vista de comentarios**: la spec propone **30 s**
   para un recorrido completo antes de materializarla como tabla.
3. **`codigo_efecto` (`FR26/06051_01`)**: no consta que Sigrid lo almacene. Se
   deriva con `row_number()` por `pag.ide`, y **solo se publica si reproduce**
   los codigos de la captura del correo; si no, se publica solo el ordinal y
   hay que decirselo a Juan Romero.
4. **F-080 va DETRAS de F-073**: `compras.formas_pago` es precondicion dura y,
   si no esta, la feature se marca `blocked` en vez de duplicar la dimension.
   Por eso a F-080 le toca la **version 20** del diccionario (F-073 reserva la
   19). Adelantarla obliga a reabrir las dos cosas.
5. **El banco de la rejilla**: `auxban` da nombre a banco y sucursal, pero la
   tabla de previsiones/remesas bancarias sigue sin identificar. Conviene
   decirselo a Administracion con la entrega.

## LO PRIMERO AL RETOMAR (sesion reiniciada el 2026-09-10)

**F-073 tiene su spec escrita y ESPERA APROBACION DEL HUMANO.** Se le
corrigio el 2026-09-10 (`47c02d4`) una afirmacion que daba por buena: R23 y la
tabla de `design.md` §1 decian que el cableado de forma de pago y estado a
`compras.contratos` **y** `compras.facturas` era el criterio 1 de `acceptance`
de F-067. Ese criterio nombra **solo los contratos**; el de facturas es el 5, y
no menciona la forma de pago. **El alcance de F-073 no cambia.**
`specs/F-073-tablas-nuevas-y-enriquecimiento/` (114 / 201 / 29 lineas, 21
tareas). Nada de codigo hasta que el humano apruebe: es la PARADA 1.

**Las tres decisiones que el humano tiene que aprobar**, tal como las dejo el
spec-author:

1. **La frontera con las ocho features ya fichadas**: *F-073 publica
   DIMENSIONES y el MAESTRO DE OBRA; la feature de dominio publica su HECHO y
   hace el CABLEADO*. Se queda con **cuatro objetos**: `maestro.centros_coste`
   (el puente centro -> obra), `maestro.obras` enriquecida (direccion y
   marcas), `maestro.estados_documento` (desde `conest`) y
   `compras.formas_pago` (desde `auxpag` y `auxefp`). **No duplica ninguna
   ficha**: el cableado de `conest` y `auxpag` a `compras.contratos` y
   `compras.facturas` es literalmente el criterio 1 de `acceptance` de F-067 y
   se queda alli.
2. **Las marcas leen de `stg`, no de `mart`**, y hay que aprobar su
   consecuencia: `mart/01_ddl.sql` dropea `mart.fact_seguimiento_mensual` con
   `CASCADE` y destruiria la vista de `maestro` la noche siguiente (es el
   incidente de F-047). Por eso **`build_maestros` pasa a depender de
   `build_stg`**: un fallo de `build_stg` ahora se lleva por delante tambien
   los maestros.
3. **El criterio 2 de la `acceptance` esta reformulado a proposito.** Con
   **294 de 921 municipios informados** no se puede exigir esa cobertura: R11 y
   R12 obligan a publicar el porcentaje en la ficha y a que **«no consta» sea
   la respuesta correcta para dos de cada tres obras**.

**Cifras medidas por el spec-author el 2026-09-10**, sobre las 921 fichas de
`maestro.obras`: **728 con presupuesto, 368 con plan mensual, 349 con hecho,
193 sin nada**. La diferencia entre plan y hecho son **19 obras**, y la ficha
del diccionario las declara.

**OJO, Y ESTO NO SE VE SI NO SE DICE: hay OTRA SESION DE CLAUDE trabajando en
este mismo repositorio.** Se llama `powerbi` y lleva **F-078** (la vista
`mart.v_pbi_cp_tipologia` que cuelga Power BI). Consecuencias practicas: los
numeros de feature se pisan -F-078 lo cogio ella, por eso el trabajo del
diccionario acabo siendo F-079-, y **NUNCA se hace `git add -A`**: el
2026-09-09 su trabajo se colo dentro de un commit de esta sesion.

**PENDIENTE SIN URGENCIA**: `python main.py check-raw-recuentos` sobre las 65
tablas, que no se ha lanzado desde que entraron las nueve de F-074.

## EL DESPLIEGUE DEL 09-SEP Y SU VERIFICACION (hecha el 2026-09-10)

**Desplegada la imagen `r20260910-0102`** a las 23:03 UTC del 09-sep, con
autorizacion expresa del humano, y el cron intacto (`0 0 * * *`). Llevaba
dentro F-074 (las nueve tablas) y F-079 (el diccionario version 18).

**VERIFICADO el 2026-09-10 a las 07:20 UTC, tras la nocturna
`caj-datamart-seg-dev-29816640` (00:00 -> 03:24 UTC, `Succeeded`):**

* **Las nueve tablas entraron**, con los tamaños que la medicion predecia:
  `dcaprodes` 851.195, `ctrprodes` 424.488, **`pro` 55.179** -la unica cuyo
  tamaño no conociamos, asi que **el producto ya tiene nombre en el
  datamart**-, `reshor` 8.949, `emphis` 1.633, `auxhor` 60, `cet` 40,
  `auxrestip` 37 y `auxdpt` 7.
* **`check-diccionario` en verde**: **139 fichas y 139 objetos**, biyeccion
  exacta, y **lo publicado ES lo del arbol (version 18, hash 4af4c3bb60d4)**.
  Las dos discrepancias de la noche anterior quedan cerradas.
* **La noche duro 3 h 25 min**, nueve minutos mas que la anterior: eso es lo
  que cuestan 1,34 M de filas nuevas. Sigue muy por debajo de las 4 h 52 de
  antes de F-025.
* **PENDIENTE, sin urgencia**: `check-raw-recuentos` sobre las 65 tablas.

**HALLAZGO DEL DESPLIEGUE, para revisar sin prisa**: el job **no declara**
`PG_DISCO_TOTAL_GB` ni `PG_EXCLUDED_TABLES`. Funciona porque el valor por
defecto de `config/settings.py` es el correcto en las dos, pero el
comportamiento depende de ese defecto y no de una declaracion explicita. Es la
misma fragilidad que en agosto dejo la puerta de disco midiendo contra 32 GB
durante nueve dias.

## POR DONDE SE SIGUE EN LA PROXIMA SESION (leer esto primero)

**F-025, F-068, F-066 y F-072 estan CERRADAS**, y **F-071 esta RETIRADA** (ver
su seccion abajo: no se borra nada). El censo de F-072 quedo `done` en
`e52c5f9`, y **su primer descendiente, F-074, esta en curso**. Lo abierto es el
backlog, mas F-052, que sigue `blocked` y ya no espera a nadie.

| Prioridad | Feature | Estado | Que es |
|---|---|---|---|
| 4 | **F-072** | `done` (`e52c5f9`) | El censo semantico: que hay dentro de las 31 tablas que se ingieren cada noche y no consume nadie. Entregable: `progress/explore_F-072_catalogo.md` + cuatro informes de bloque. **De aqui salen F-073 y F-074.** |
| 5 | **F-073** | `pending` | Construir con lo que el censo encontro: tablas procesadas nuevas y enriquecimiento de las actuales, **sin borrar ni filtrar nada**. |
| 6 | **F-074** | **en curso, implementacion entregada** | La ingesta que el censo destapa: **9 tablas** que faltan, la carga incremental falsa de `com`/`comlin`/`comprv` y el `tex` excluido de `prvcer`. Informe: `progress/impl_F-074.md`. |
| 7 | **F-070** | `pending`, spec escrita | Auditar la **calidad** de las fichas del diccionario, acotada a los ocho esquemas que el MCP lee. |
| 8 | **F-034** | `pending` | Power BI deja de leer de local y pasa a leer el datamart de Azure. |

Detras, F-057 (9) y F-056 (10), las dos ya sin ingesta dentro porque F-066 se
la llevo, y las dos **con su ficha corregida por el censo**.

**LO QUE F-074 DECIDIO, Y POR QUE NO ES LO QUE LA PROPUESTA DECIA.** La
propuesta que llego al implementer era «recarga completa nocturna de las cuatro
pequeñas (`cet`, `pro`, `reshor`, `emphis`) y carga por `ide` para las dos
grandes», porque **solo 3 de las 9 tienen `tiemod`** --`auxdpt`, `auxhor`,
`auxrestip`-- y se daba por hecho que las otras seis cargarian por `MAX(ide)` y
que **una fila modificada en el origen no volveria a bajar nunca**.

**Esa premisa es falsa, y esta comprobado en la fuente que gobierna el hecho.**
El `CMD` del `Dockerfile` arranca `run-all --full`, o sea `TRUNCATE` y recarga
entera de **todas** las tablas cada noche (`ingest_raw_step.py`, lineas 271-275).
`incremental_column` **no es un interruptor de modo de carga**: lo unico que
decide es si `copy_rows` rellena `_source_tiemod` con el sello del origen. La
carga por `MAX(ide)` solo ocurre lanzando `ingest` a mano **sin** `--full`.

Es el error exacto que F-006 cometio dos veces seguidas --su septima pasada lo
derivo de `tables_sigrid.yaml` y su octava de `ingest_raw_step.py`, y las dos
salieron falsas-- y para el que existe `tests/test_f006_fuente_que_gobierna.py`.

**Consecuencia**: no hace falta recarga completa por tabla, el ETL no sabe
hacerla y F-074 **no la inventa**. Las seis quedan con `incremental_column:
null` **declarado y explicado en el propio YAML**, no solo en un informe.

**Coste medido de las nueve**: 1.341.365 filas nuevas por noche, **+155 MB**
estimados sobre los 25 GB actuales (disco de 64 GB, +0,6 %) y **+3 a 6 min** de
ventana sobre las 3 h 45 de hoy. El 95 % de eso son `dcaprodes` (850.985) y
`ctrprodes` (424.475).

**F-052 sigue `blocked`** y su desbloqueo ya no depende de F-025. Ver su seccion
abajo: es volver a su rama y relanzar `check-cobertura` alli.

## LO QUE LAS TRES FEATURES CERRADAS DEJAN VIVO

Su resumen esta en `progress/history.md`. Aqui solo lo que sigue pendiente de
alguien:

1. **`infra/sql/02_roles.sql` no lo ejecuta ningun test** (de F-068): solo se
   comprueba su texto, y esta corregido en dos sitios que solo prueba `psql`.
   **Antes de volver a provisionar un rol desde cero, ejecutarlo contra una base
   de prueba.**
2. **La revocacion de datos personales del MCP es TEMPORAL** (F-068): vuelve en
   cuanto el MCP tenga control por usuario. Decision del humano, escrita en
   cinco sitios para que nadie la lea como permanente.
3. **El umbral de tolerancia de `check-raw-recuentos`** (F-066): 0,05 % de
   `obrparpre` son ~6.940 filas. **Revisarlo si baja `page_size` o aparece una
   tabla mayor.**
4. **F-069**, fichada: `harness/mutacion.py` no muta constantes `float` ni la
   division. Uno de los seis sitios ciegos es `TOLERANCIA_DERIVA_PCT = 0.05`, el
   numero del que depende entero el criterio de F-066.
5. **F-065** mide el bloat sostenido tras siete noches acotadas (de F-025, T33).
6. **Un superviviente de mutacion de F-025, aceptado y YA FICHADO como
   **F-077** (prioridad 12, commit `7d2d8b9`), hallado por F-074: `main.py:543`, el `is_flag` de
   `--reconstruir-todo` en `run-all`. Sin el, click infiere `BOOL` y
   `run-all --reconstruir-todo` sale con **exit 2** —medido—; la nocturna
   (`run-all --full`) y el rebuild del domingo por antiguedad **no se enteran**.
   Lo dejan vivo sus propios tests, T15 de `tests/test_f025_cli.py`, que
   comprueban que la cadena salga en `--help` y que el callback la cablee, pero
   **no invocan la opcion por el parser de click**. El arreglo, tres lineas, esta
   escrito en `progress/mutacion_F-074.md` §8. **F-074 no lo tapa: no es su
   codigo ni su fichero de tests**, y por eso salio a ficha propia. El reviewer
   reprodujo las cinco invocaciones de click antes de aprobar.

**El diccionario del árbol está en 154 objetos, 972 columnas y 66 fichas de
consumo** —lo último es F-084: `compras.contratos` gana **tres columnas**
(`estado_id`, `estado_codigo`, `estado`) y aparece **un objeto nuevo**, la
función auxiliar `compras.fn_estado_documento`, que no es de consumo (por eso
las fichas de consumo siguen en 66). Antes de F-084 eran 153 / 969 / 66, con
las cinco columnas de F-083 en `compras.facturas`
(`estado_id`, `estado_codigo`, `estado`, `fecha_factura`, `fecha_alta`): no
añadía objetos, solo ensanchaba uno que ya existía. Antes de F-083 eran 964, y
F-078 había añadido las **tres tablas** de CP por tipología
(`mart.master_versiones_tipadas`, `mart.master_vigente_anual`,
`mart.fact_cp_tipologia`, 23 columnas) y sube `mart.v_pbi_cp_tipologia` a la
superficie de consulta, que es lo que explica las cuatro fichas de consumo
nuevas. Antes estaba en 150 / 941 / 62, y eran 142 / 852 / 57 al cerrar F-073,
cuando F-080 añadió los **cinco objetos** de `compras` (`vencimientos`,
`v_facturas_pago`, `v_control_forma_pago`, `documento_texto`,
`documento_comentarios`, 89 columnas) más las **tres tablas nuevas de `raw`**
(`auxnap`, `auxban`, `rpa`, sin columnas por la convención de `raw`); antes de
eso eran 139 / 822 / 54 hasta F-073 y 47 fichas de consumo hasta F-079, que
subió los siete objetos de `stg` a la superficie de consulta— y el árbol declara
**versión 24**. Lo publicado en `_meta` es la **versión
18** (hash `4af4c3bb60d4`, publicada el 2026-09-10): publicar contra Azure es una
escritura y la autoriza el humano, no un agente. El commit de cierre del 04
se llevó por delante esta frase y dejó `init.sh` en rojo: el test
`test_f006_los_recuentos_de_current_son_los_de_hoy` existe justo para que estos
recuentos no envejezcan en silencio. **Si vuelves a reescribir la cabecera de
este fichero, los tres números se quedan.**

## F-079 · todo lo publicado es consultable (implementación entregada)

Rama `feature/F-079-todo-lo-publicado-es-consultable`, rigor `estandar`,
`sdd=false`. Informe: `progress/impl_F-079.md`.

Los **siete objetos de `stg`** que no son funciones —`plan_mensual`,
`presupuesto`, `partidas`, `obras`, `fases`, `version_master_vigente`,
`ambitos`— y la entrada del esquema `stg` en `00_global.yaml` pasan a
`consumo_recomendado: true` y pierden su `motivo_no_consumo`. **Las cuatro
advertencias de corrección que viajaban ahí dentro se mueven a la `descripcion`
de su ficha** (versiones master, `stg.obras.activa`, la resolución GLOBAL de
`version_master_vigente` y `stg.ambitos.uso_seguimiento`), y las dos primeras
siguen llegando además por las reglas duras `R-VERSION-MASTER` y
`R-OBRA-ACTIVA`. Las 11 funciones `fn_*` y los 9 objetos rotos, vacíos o de
instrumentación **no se tocan**: ahí el aviso es un hecho, no una preferencia.

**Diccionario del árbol en versión 18, `hash_fuente` `4af4c3bb60d4`. Publicado
en `_meta`: sigue la 16, hash `9140b14dc991`.** Ese par de hashes es lo que
distingue «publicado» de «publicado de verdad» después del paso 1 de abajo.

### VERIFICACIONES MANUAL (humano) PENDIENTES DE F-079

Las tres escriben contra Azure o dependen de que la escritura haya ocurrido, así
que **ningún agente puede ejecutarlas**. En este orden:

1. **Publicar el diccionario.**
   `python main.py publicar-diccionario`
   Sin esto el MCP sigue leyendo la versión 16 y `stg` le seguirá pareciendo
   desaconsejado: *el repositorio en verde no es producción*.
2. **Comprobar que lo publicado es lo del árbol.**
   `python main.py check-diccionario`
   Se espera **exit code 0**, biyección exacta y que la versión publicada pase a
   ser la **18**.
3. **Preguntar al MCP, sin explicarle nada en el prompt**, algo que solo `stg`
   puede responder —el ámbito de certificación de una obra, que está en
   `stg.presupuesto` y en ningún sitio aguas abajo— y comprobar que **enruta a
   `stg`**. Es el criterio 6 de `acceptance` y es la única prueba de que el
   cambio surtió efecto donde importa.

## VERIFICACIONES MANUAL (humano) PENDIENTES DE F-074

Ninguna la puede ejecutar un agente: **todas escriben contra Azure o dependen de
que la imagen nueva se haya desplegado y la nocturna haya corrido**. Van en este
orden, y la 2 no significa nada antes de la 1.

1. **Desplegar la imagen y dejar correr una nocturna.** Sin eso, las nueve
   tablas no existen en `raw` y las comprobaciones de abajo miden el mundo de
   ayer. Recordatorio de `progress/` : la nocturna llego a correr una imagen de
   diez dias antes sin que nadie lo notara, asi que **comprobar el tag de la
   imagen del job**, no solo que el repositorio este en verde.

2. **Que la ingesta trajo lo que debia**, con las nueve dentro:

       python main.py check-raw-recuentos

   Tiene que salir con **codigo 0**. Es el criterio 4 de `acceptance`. Manda 65
   consultas de recuento a Sigrid, nueve mas que antes.

3. **Que el rol del MCP NO lee la nomina.** Es el criterio 3, y **no vale
   suponerlo**: F-068 existe porque un `ALTER DEFAULT PRIVILEGES` reponia el
   permiso en silencio. Contra el Postgres de Azure, en solo lectura:

       SELECT table_name, grantee, privilege_type
       FROM information_schema.table_privileges
       WHERE table_schema = 'raw'
         AND table_name IN ('emp','res','reshor','emphis')
         AND grantee = 'mcp_sigrid_dm_ro';

   El resultado correcto es **cero filas**. Si aparece alguna, la revocacion no
   sobrevivio a la noche.

4. **Que el diccionario del arbol casa con el catalogo real:**

       python main.py check-diccionario

5. **Publicar el diccionario** (version 17, con las nueve fichas nuevas). Es una
   **escritura contra Azure**: la autoriza el humano, no un agente.

       python main.py publicar-diccionario

## Estado del servidor · sigue en B2s TEMPORALMENTE

`psql-albaranes-rs9k2`, **`Standard_B2s`** desde el 2026-09-05 a las 17:21 UTC.
**La bajada a `Standard_B1ms` sigue pendiente, con fecha limite 2026-09-20**
anotada en `azure-apps/` para preguntar si se olvido. Al bajar, el saldo de
creditos se resetea a 60.

**LOS 144 CREDITOS ERAN FALSOS** (corregido el 2026-09-05). La tabla oficial de
la serie Bv1 da para el `B1ms`: baseline 20 % de 1 vCPU, **12 creditos/hora** con
la CPU ociosa y **288 de tope**; el `B2s` da 24/h y **576**. La metrica lo
confirma: el servidor ha estado a 300 el 8-ago y 277 el 15-ago. Consecuencia:
cuando el saldo marca 57 no estamos al 40 % del deposito, sino al 20 %. **Todas
las cuentas de creditos anteriores al 05-sep estan hechas sobre un techo
equivocado.**

**Como se consulta el saldo de verdad**, que tambien costo descubrirlo: hay que
pedirlo con **`--interval PT1M`** y una ventana corta. Con `PT15M` la API
devuelve los primeros puntos del rango y parece que la metrica lleva 13 horas de
retraso; no es cierto, llega al minuto.

```bash
az monitor metrics list --resource psql-albaranes-rs9k2 --resource-group rg-albaranes-dev \
  --resource-type Microsoft.DBforPostgreSQL/flexibleServers \
  --metric cpu_credits_remaining --interval PT1M --aggregation Average \
  --start-time $(date -u -d '-50 minutes' +%Y-%m-%dT%H:%M:%SZ) -o tsv
```

**Que costaria tener mas** (precios reales de Spain Central, EUR, 730 h/mes,
consultados el 05-sep en la API de tarifas de Azure):

| via | que da | coste |
|---|---|---|
| esperar | ~12 creditos/h con el servidor ocioso; lleno en ~19 h | 0 € |
| **B2s** permanente | 2 vCPU, 4 GB · 24 creditos/h, tope 576 · IOPS 1.280 | 49,86 €/mes frente a 12,48 → **+37,38 €/mes** |
| B2s solo de noche | lo mismo durante la ventana | ~**+12,3 €/mes** |
| General Purpose D2ds_v5 | 2 vCPU, 8 GB, **sin creditos** | 132,86 €/mes → **+120,38 €/mes** |

En Spain Central **solo existen B1ms y B2s** en Burstable: el salto siguiente es
ya General Purpose. Y ojo con escalar: **reinicia el servidor** —compartido con
albaranes, partes, remesas, el portal y facturas— y **probablemente resetea el
saldo de creditos**; eso habria que medirlo antes de fiarse.

**El disco esta en 64 GB** desde el 2026-08-29, y el job lo declara desde el
07-sep (`PG_DISCO_TOTAL_GB`). Durante nueve dias la puerta de F-019 midio contra
32 GB y veia un 74,32 % donde la ocupacion real es del 37,16 %: aborta al 80 %,
asi que estaba a menos de seis puntos de tumbar la nocturna cada noche sin que
nada estuviera mal. Detalle en `progress/impl_disco_64gb.md` y
`progress/incidencia_nocturna_20260907.md`.

## F-052 · SIGUE BLOQUEADA, y el motivo REAL no era el que se penso

Su unico pendiente es certificar `check-cobertura` en verde. Lanzado el 04 sobre
`stg` ya completa: **58 combinaciones miradas, 37 cubiertas** —antes decia CERO,
asi que **el guardian ya no miente**, que era el bloqueo de verdad— pero sale
**KO** con 20 obras invisibles y 294 filas huerfanas.

**Y eso tiene explicacion, comprobada:** el `check-cobertura` se lanzo desde la
rama de F-025, que **NO contiene los cinco commits de cierre de F-052**
(`ec516bd`..`fa2312c`, que viven solo en `feature/F-052-partidas-huerfanas`).
El fichero de excepciones de esa rama es el viejo: **10 entradas y con los
`tipo` sin corregir**. En la rama de F-052 estan las 23 y los tipos arreglados.

**Como se cierra F-052:** volver a su rama, relanzar `check-cobertura
--timeout 900` **alli**, y si da codigo 0, al reviewer y a `done`. **No se
mezclan las dos ramas** sin decidirlo. Ojo con F-071 y F-053, que tocan
`stg.obras` y su desempate `rn=1`.

## F-072 · CERRADA · el censo semantico de las 31 tablas que nadie consume

**F-071 ESTA RETIRADA.** El humano la paro el 2026-09-09 al leer su spec:
«**no vamos a borrar nada de momento, vamos a seguir dejando todo. Quitamos
esta feature.**» Ya no esta en `harness/features.json`. Su carpeta
`specs/F-071-obras-sin-datos/` se conserva con un banner de RETIRADA, solo por
lo que costo medir. **No se implementa nada de ella.**

**Lo que NO se hace, y conviene que quede escrito para que nadie lo reproponga
dentro de tres meses:** no se borran las 472.890 filas huerfanas de
`stg.presupuesto` (390.028) y `stg.plan_mensual` (82.862); **no se acota el
censo de la ventana**, que era precisamente lo que las dejaba huerfanas; y no
se filtra ni se oculta ninguna obra en ninguna vista. El marcado de obras sin
datos sobrevive **como enriquecimiento**, no como filtro.

**EL HECHO QUE ABRE F-072**, medido el 2026-09-09 cruzando
`config/tables_sigrid.yaml` contra todo el SQL de
`etl_sigrid/infrastructure/postgres/sql/`:

| tablas ingeridas cada noche | las consume algun build | **no las consume nadie** |
|---|---|---|
| 56 | 25 | **31** |

Las 31: `apa`, `apu`, `asi`, `auxefp`, `auxobrtca`, `auxpag`, `auxpronat`,
`com`, `comlin`, `comprv`, `conact`, `conest`, `confir`, `ctrrec`, `cua`,
`dcarec`, `dcfprodes`, `dcfrec`, `dco`, `dcopro`, `dcorec`, `deffir`, `dnc`,
`dncpro`, `emp`, `hmo`, `hmores`, `obrprv`, `prvcer`, `prvobrpag`, `res`. Se
ingieren cada noche, ocupan disco y **la IA no las ve**, porque el MCP solo lee
las capas procesadas.

**EL PLAN, EN DOS FEATURES**, aprobado por el humano:

* **F-072 (`done`, prioridad 4)** — entender. Catalogo tabla por tabla: que
  es, grano, volumen, **% informado columna a columna**, por donde se une, y
  que preguntas de negocio permitiria responder que hoy no se pueden
  responder. **Solo lectura de principio a fin.** Cuatro bloques tematicos,
  un informe `progress/explore_F-072_*.md` por bloque, mas un catalogo que los
  une y los enruta a las features de construccion.
* **F-073 (pendiente, prioridad 5)** — construir. **Su contenido lo fija
  F-072.** Lo unico que ya se sabe que entra es la direccion de la obra en la
  capa de consumo y las marcas de obra con/sin datos. Buena parte del resto
  caera en features de dominio que YA existen en el backlog: F-055, F-056,
  F-057, F-058, F-067, F-038, F-037 y F-040.

**EL TOPE DE LA PASARELA ESTABA MAL EN MI CABEZA, y lo corrigio el humano.**
`azure-apps/sigrid_api.md` §4.1: la instancia `dev` tiene `MAX_ALLOWED_ROWS` en
**500.000**, no en 1.000 (ese es el tope por codigo, que dev sobreescribe), y
`MAX_QUERY_TIMEOUT_SECONDS` en **230**. Los 230 s **si** son un techo duro: es
el balanceador de Azure y subir el ajuste no da mas tiempo. El cliente es
`SigridApiClient.leer_sql(sql, parameters, max_rows)`.

**HALLAZGOS DE F-071 QUE SOBREVIVEN** (medidos, no supuestos): de los ocho
campos de direccion de `raw.obr`, **tres no son la direccion de la obra**
—`diride` es el **director de obra**, `perdir` su **persona de contacto** y
`entdiride` la direccion **del cliente**—; y los dos ejes de agrupacion que
faltaban, **municipio** y **provincia**, viven en `raw.auxmun` y `raw.auxpro`
via `obr.munide` y `obr.proide`. Lo demas, en
`specs/F-071-obras-sin-datos/design.md` §1.

## F-073 · SPEC ESCRITA (spec-author, 2026-09-10)

`specs/F-073-tablas-nuevas-y-enriquecimiento/` con los tres ficheros:
requirements 114/150, design 201/250, tasks 21 tareas.

**LA FRONTERA QUE TRAZA, y es lo que el humano tiene que aprobar.** Regla:
*F-073 publica DIMENSIONES y el MAESTRO DE OBRA; la feature de dominio publica
su HECHO y hace el CABLEADO*. Se queda con cuatro objetos —`maestro.centros_coste`
(el puente centro de coste -> obra), `maestro.obras` enriquecida,
`maestro.estados_documento` (`conest`, 193 filas) y `compras.formas_pago`
(`auxpag` + `auxefp`)— y deja fuera todo lo demas del censo. No duplica ninguna
ficha: el cableado de `conest` y `auxpag` a `compras.contratos` y
`compras.facturas` es literalmente el criterio 1 de `acceptance` de **F-067**.

**MEDIDO HOY, 2026-09-10, por el MCP y en solo lectura** (justifica las marcas):
sobre las 921 fichas de `maestro.obras`, **728 (79,0 %) tienen filas en
`stg.presupuesto`**, **368 (39,9 %) en `stg.plan_mensual`**, **349 (37,9 %) en
`mart.fact_seguimiento_mensual`** y **193 (21,0 %) no tienen ninguna de las dos**.
La diferencia plan/hecho son **19 obras, y ninguna al reves**.

**DECISIONES ABIERTAS QUE NECESITAN AL HUMANO:**

1. **La frontera con F-067** (arriba). Si el humano prefiere que las dos
   dimensiones vayan enteras a F-067, F-073 se queda solo con el puente y la
   obra, y hay que quitar R19-R23 y las tareas T5, T6, T9, T10.
2. **Las marcas leen de `stg`, no de `mart`** (DA-1 del diseño). `mart/01_ddl.sql`
   dropea `mart.fact_seguimiento_mensual` con CASCADE, asi que una vista de
   `maestro` colgada de ahi la destruye la nocturna siguiente —el incidente
   literal de F-047—. Coste declarado: `tiene_seguimiento` es superconjunto del
   hecho en 19 obras, y la ficha lo dice.
3. **`build_maestros` pasa a depender de `build_stg`** (DA-3). Consecuencia real:
   si `build_stg` falla, el orquestador marca `build_maestros` como SKIPPED, cosa
   que hoy no pasa. Es inocuo porque los cuatro objetos de `maestro` son vistas,
   pero cambia la conducta de la noche y conviene que este aprobado.

**LO QUE LA SPEC REFORMULA A PROPOSITO**: el criterio 2 de la `acceptance` de
F-073 exige que «donde esta la obra X» se responda sin explicar nada. Con
294/921 municipios y 305/921 direcciones informadas, eso no lo da el origen. La
spec lo convierte en R11 y R12: se publica igual, la ficha **declara el
porcentaje informado** y «no consta» es la respuesta correcta para dos de cada
tres obras. Ningun criterio exige cobertura minima.

## F-081 · IMPLEMENTACION ENTREGADA (2026-09-11) · las dos deudas del review de F-073

Rama `feature/F-081-deudas-review-F-073`, rigor `estandar`, `sdd=false`: el
contrato son los siete criterios `acceptance` de la ficha. Informe completo:
`progress/impl_F-081.md`.

**QUE CAMBIA**: `config/tables_sigrid.yaml` deja de mentir sobre que columna da
el nombre (`auxefp` -> `res`, y la entrada de `cen`, que atribuia a la tabla una
columna `res` **que no existe en Sigrid**); un test nuevo lo impide en el
futuro comparando el yaml con el SQL que publica el dato; y dos tests nuevos
cierran los dos huecos de mutacion que dejo F-073. **Ni `ventana_sql.py` ni
`build_stg_step.py` se tocan**: un agujero de test se tapa con tests.

**NO HAY VERIFICACIONES MANUAL.** Nada de lo cambiado altera lo que corre de
noche: el yaml solo cambia comentarios, el SQL de formas de pago solo su
cabecera, y la ficha del diccionario se republica sola con la version 20.

### CONSULTA AL HUMANO (no bloquea, pero conviene mirarla)

**La campana de mutacion de F-073 dio un SUPERVIVIENTE FALSO.** Su
superviviente numero 1 -`build_stg_step.py:732`, `and` -> `or`- **no sobrevive**:
medido el 2026-09-11 contra la suite entera y con los argumentos del propio
arnes (`-x -q --tb=no -p no:cacheprovider`), muere en 157,7 s a manos de
`test_f025_r10_las_sobrantes_solo_se_miran_en_la_reconstruccion_completa`, un
test que ya existia **byte a byte** en el commit que midio la campana
(`b6eda79`) y que no ha cambiado desde entonces. El informe de F-073 declara
`Timeouts: 0` y `base rota: 0`, asi que no fue ninguna de las dos cosas.

Importa porque un superviviente falso **manda a alguien a escribir tests para
un agujero que no existe**, y porque la confianza en el resto de veredictos de
la campana depende de saber por que paso. Auditar `harness/mutacion.py` no es
de esta feature -y el arnes es generico: la correccion iria a `arnes-base`-,
asi que queda como decision del humano.

## DECISION DEL HUMANO (2026-09-11): EL DESPLIEGUE ESPERA A F-080

**No se despliega F-073 + F-081 por separado.** El humano decidio esperar a que
F-080 cierre y **hacer un solo despliegue con las tres**. Se le expuso el
argumento contrario —que F-080 es el unico de los tres cambios con riesgo sobre
la ventana nocturna, y que desplegar junto impide atribuir una noche larga— y
aun asi prefiere tocar produccion una sola vez. **No lo repropongas.**

**Que implica, y conviene tenerlo presente:**

* **Nada de F-073 ni de F-081 existe hoy en la base.** El MCP no ve
  `maestro.centros_coste`, `maestro.estados_documento`, `compras.formas_pago` ni
  las once columnas nuevas de `maestro.obras`. Las verificaciones MANUAL de las
  dos features **siguen pendientes** y no se pueden ejecutar hasta el
  despliegue.
* **La nocturna sigue corriendo la imagen vieja cada noche**, que es lo
  correcto: no rompe nada y republica el diccionario que esa imagen lleva
  dentro.
* **Cuando se despliegue, el diccionario ira a la version 21** (19 de F-073, 20
  de F-081, 21 de F-080) y se publica **una sola vez**.
* **El despliegue se simplifica**: con F-080 cerrada, el arbol vuelve a estar
  limpio y **ya no hace falta el `git worktree`** que se necesitaba para no
  empaquetar el trabajo a medias. Se construye desde el directorio de siempre.

**La guia de despliegue, en cuatro comandos** (`infra/README.md` §«Despliegue
habitual»), y **por este orden**:

```powershell
powershell -NoProfile -File infra\05_check_prereqs.ps1   # solo lectura; si falla, PARA
powershell -NoProfile -File infra\70_build_image.ps1     # construye en Azure, tag rAAAAMMDD-hhmm
powershell -NoProfile -File infra\85_update_job.ps1      # el job pasa a usarla
az containerapp job show -g rg-datamart-seg-dev -n caj-datamart-seg-dev \
  --query "properties.template.containers[0].image" -o tsv
```

**El cuarto comando no es opcional**: la nocturna llego a correr una imagen de
diez dias antes sin que nadie lo notara. El tag que devuelva tiene que ser el
que imprimio el segundo.

Despues de la primera nocturna con la imagen nueva van, en este orden,
`check-raw-recuentos`, `check-declarados`, `check-diccionario` y, por ultimo,
`publicar-diccionario`, que es **la unica escritura** y la autoriza el humano.

## F-080 · IMPLEMENTACION ENTREGADA (2026-09-14) · VERIFICACIONES MANUAL

Rama `feature/F-080-vencimientos-forma-pago-y-texto-factura`, rigor `estandar`,
`sdd=true`. Informe: `progress/impl_F-080.md`. Las 29 tareas de `tasks.md`
hechas, con un commit cada una; T0 bis queda abierta a proposito porque es
MANUAL del humano. **`bash harness/init.sh` en verde, exit 0**: 4.677 tests
pasan, 179 saltados, 520,6 s con medicion de cobertura, y PUERTA COBERTURA
[OK] 93,9 % (825/879).

**EL CIERRE (T24-T29) DESTAPO SEIS COSAS, y conviene saberlas:** el portero
corre `pytest -x`, asi que el primer fallo escondia a otros cuatro. Dos eran de
F-080 --las fichas de `pagfor`/`pagtex` prometian un NULL que el SQL nunca
producia (arreglado con `NULLIF(x, '')`, medido: 1 NULL y 7 vacios de 165.802
filas de `dcf`), y el grano de `v_control_forma_pago` no nombraba
`contrato_id`-- y tres eran recuentos viejos: `TOTAL_TABLAS` de F-066 en 65
cuando son 68, el punto 3 de `R-SIGRID-CON` sin `auxban.res` ni `auxnap.res`, y
el inventario de `design_detalle.md` de F-006 en 142 objetos cuando son 150. La
sexta: `compras.documento_comentarios` habia dejado de ser LEGIBLE para el
guardian de proyecciones de F-006 y por tanto de estar vigilado; las ramas del
sello pasan a un CTE y no cambia ni una columna publicada.

**LA MUTACION NECESITO DOS CAMPANAS.** La canonica
(`progress/mutacion_F-080.md`) no juzga a F-080: su alcance son 3.789 lineas
calculadas contra un `dev` con 242 commits de retraso, solo 15 de sus 303
mutantes caen en `texto_comentarios.py` y el muestreo de 20 no cogio ninguno;
sus 6 supervivientes son de F-025 (dos, los mismos que ya senalo F-073) y van
analizados igual. La dirigida a los dos modulos de F-080 sin muestreo
(`progress/mutacion_F-080_modulos.md`) evalua los 27 y deja **1 superviviente,
que era un hueco real: una fecha imposible dentro del sello (`31/02/2026`)
estaba probada en el SQL y NO en el oraculo**. Tapado con
`test_f080_r25_una_fecha_que_no_existe_no_cuenta_como_sello`, y comprobado
mutante en mano que lo mata.

**DEUDA DECLARADA PARA EL DESPLIEGUE**: `azure-apps/datamart_seg_anual.md` dice
que el ETL ingiere **56 tablas** de Sigrid. Ya estaba viejo antes de F-080
(F-074 lo dejo en 65 sin tocarlo) y F-080 lo deja en **68**. Se actualiza al
desplegar, que es cuando la cifra se vuelve cierta en Azure.

**QUE SE PUBLICA**: `compras.vencimientos` (los 195.510 efectos de pago de las
facturas de compra), `compras.v_facturas_pago` (forma de pago + resumen de
efectos, una fila por factura), `compras.v_control_forma_pago` (factura contra
contrato, una fila por par), `compras.documento_texto` (el memo integro) y
`compras.documento_comentarios` (el memo partido, un comentario por fila). En
`raw` entran tres tablas nuevas (`auxnap`, `auxban`, `rpa`) y **`con.tex`**.

**LAS TRES COSAS QUE HAY QUE SABER Y NO SE VEN EN EL DIFF:**

* **Sumar los importes de todos los efectos de una factura los cuenta hasta
  tres veces.** El efecto que se dividio sigue en la tabla ANULADO junto a sus
  hijos, y el estado no lo distingue. Se filtra con `efecto_anulado = false`.
  Sobre `FR25/04222`: 92.478,49 filtrando, **288.123,92 sin filtrar**.
* **`fecha_real` vacia no significa «vivo»** (61,8 % de los efectos de factura),
  y **`orden` 1 de `documento_comentarios` es el comentario MAS RECIENTE**.
* **No se publica el enlace del efecto hijo a su efecto de origen**: `pag.padide`
  vale 0 en los 255.148 efectos. Igual que `con.serie`, de ahi que la serie se
  derive con `compras.fn_serie`.

### VERIFICACIONES MANUAL (humano) PENDIENTES DE F-080

Ningun agente las ejecuta: todas menos la 0 necesitan que el build haya corrido
contra la base, la 1 es una ESCRITURA y publicar el diccionario tambien.
**En este orden**, y de la 2 en adelante nada significa nada sin la 1.

0. **T0 bis · que la dimension de F-073 esta construida** (R20). Si no lo esta,
   todo lo que toque `v_facturas_pago` espera a la primera nocturna con la
   imagen nueva; el desarrollo no espera.

       SELECT count(*) FROM compras.formas_pago;   -- esperado: 69

1. **T7 · Medicion B del coste de ventana** (R4b). **Es una ESCRITURA.** Trae
   `con.tex` por primera vez:

       python main.py ingest --table con --full
       python main.py timings --last 10

   Y se compara la duracion de `ingest_raw.con` con las noches anteriores. El
   contraste con el presupuesto de referencia de 4 h esta en
   `progress/impl_F-080.md` §T8: con la medicion A delante, la ventana pasa de
   3 h 25 min a **~3 h 26 min**, con unos 34 min de margen. **No es una puerta**:
   si la medicion B lo desmintiera, se avisa por escrito y la feature sigue.

2. **Construir los objetos nuevos.** Sin esto no existen y todo lo de abajo mide
   el mundo de ayer:

       python main.py build-compras

3. **Los recuentos de los cinco objetos y de las tres tablas de `raw`.** Solo
   lectura. Los esperados estan medidos contra Sigrid el 2026-09-11 (T1, T2 y T4
   del informe), asi que una diferencia pequeña es el sistema vivo y una grande
   es un fallo:

       SELECT count(*) AS efectos,
              count(DISTINCT factura_id) AS facturas
       FROM compras.vencimientos;
       -- esperado: ~195.510 efectos / ~165.737 facturas

       SELECT count(*) FROM compras.v_facturas_pago;        -- esperado: ~165.759
       SELECT count(*) FROM compras.v_control_forma_pago;   -- ~80.400 pares
       SELECT count(*) FROM compras.documento_texto;        -- esperado: ~110.141
       SELECT count(*) FROM compras.documento_comentarios;  -- > documento_texto

       SELECT count(*) FROM raw.auxnap;   -- esperado: 3
       SELECT count(*) FROM raw.auxban;   -- esperado: 1.690
       SELECT count(*) FROM raw.rpa;      -- esperado: 3.919

   `v_control_forma_pago` no tiene esperado medido: las facturas CON contrato son
   ~80.435 (165.759 menos las 85.324 sin contrato) y el grano es el par, asi que
   la cifra tiene que ser **igual o algo mayor** que esa. Si es mucho mayor, el
   `DISTINCT` del enlace no esta haciendo su trabajo.

4. **El reparto de `estado_pago` contra los 10 estados** (R10). Lo medido el
   2026-09-11 sobre los efectos de factura: 10 Pagado 106.262 · 14 Agrupados
   55.476 · 2 Aprobado 20.848 · 1 Pendiente 10.436 · 5 En cartera 2.319 · 3
   Emitido 169. Si sale algun `estado_pago` a NULL, hay un estado fuera de
   catalogo y hay que mirarlo:

       SELECT estado_pago_codigo, estado_pago, count(*) AS efectos
       FROM compras.vencimientos
       GROUP BY 1, 2
       ORDER BY efectos DESC;

5. **El recuento de anulados** (R39, R40). Es la cifra de la que depende que los
   importes agregados sean ciertos:

       SELECT count(*) AS efectos,
              count(*) FILTER (WHERE efecto_anulado) AS anulados,
              round(100.0 * count(*) FILTER (WHERE efecto_anulado) / count(*), 1)
                  AS pct
       FROM compras.vencimientos;
       -- esperado: ~195.510 / ~76.215 / ~39,0

   Y la comprobacion que lo cierra, sobre la factura de la captura del correo:

       SELECT codigo_efecto, estado_pago, efecto_anulado, importe
       FROM compras.vencimientos
       WHERE codigo_factura = 'FR25/04222'
       ORDER BY codigo_efecto;
       -- esperado: 8 efectos, 3 con efecto_anulado cierto (los tres «Aprobado»),
       -- y los cinco vivos sumando 92.478,49

       SELECT num_efectos, num_efectos_anulados, importe_efectos_vivos
       FROM compras.v_facturas_pago
       WHERE codigo_factura = 'FR25/04222';
       -- esperado: 8 / 3 / 92.478,49  <-- el numero de la cabecera de Sigrid

6. **Efectos en remesa** (R41), y que el codigo de la remesa se resuelve:

       SELECT count(*) FILTER (WHERE remesa_id IS NOT NULL)      AS en_remesa,
              count(*) FILTER (WHERE codigo_remesa IS NOT NULL)  AS con_codigo
       FROM compras.vencimientos;
       -- esperado: ~40.090 / ~40.090 (los dos iguales: si el segundo es 0, el
       -- JOIN a raw.con de la remesa no esta resolviendo)

7. **LA PRUEBA RECONSTRUCTIVA DEL MEMO** (R26). Es la que hace innecesario
   fiarse del parseo: si el memo se reconstruye, no se ha tirado nada. Primero
   sobre una muestra:

       SELECT t.documento_id, t.codigo_documento, t.num_comentarios,
              t.texto = string_agg(c.bloque, E'\n --------------------------------- \n'
                                   ORDER BY c.orden) AS reconstruye
       FROM compras.documento_texto t
       JOIN compras.documento_comentarios c ON c.documento_id = t.documento_id
       GROUP BY t.documento_id, t.codigo_documento, t.num_comentarios, t.texto
       LIMIT 20;

   Y despues sobre el total:

       SELECT count(*) AS documentos,
              count(*) FILTER (WHERE NOT reconstruye) AS no_reconstruyen
       FROM (
           SELECT t.documento_id,
                  t.texto = string_agg(c.bloque,
                      E'\n --------------------------------- \n' ORDER BY c.orden)
                      AS reconstruye
           FROM compras.documento_texto t
           JOIN compras.documento_comentarios c ON c.documento_id = t.documento_id
           GROUP BY t.documento_id, t.texto
       ) x;

   **`no_reconstruyen` NO tiene que ser 0 necesariamente**: el separador se
   reconoce con tolerancia (tres guiones o mas) y ahi arriba se recompone con el
   canonico de 33, asi que un memo con otra longitud de separador sale como que
   no reconstruye sin que se haya perdido nada. Lo que **si** tiene que ser 0 es
   el invariante fuerte, que no depende del separador:

       SELECT count(*) FROM (
           SELECT t.documento_id
           FROM compras.documento_texto t
           JOIN compras.documento_comentarios c ON c.documento_id = t.documento_id
           GROUP BY t.documento_id, t.texto
           HAVING regexp_replace(t.texto, '\r?\n *-{3,} *\r?\n', '', 'g')
               <> string_agg(c.bloque, '' ORDER BY c.orden)
       ) x;
       -- esperado: 0. Si no lo es, los documentos que salgan tienen un bloque
       -- en blanco (que se tira a proposito) y hay que mirarlos uno a uno antes
       -- de dar el parseo por bueno.

   Y de paso, cuantos bloques no casan con el sello, que es la cifra que la ficha
   promete declarar cuando se mida:

       SELECT count(*) FILTER (WHERE NOT sello_reconocido) AS sin_sello,
              count(*) AS bloques
       FROM compras.documento_comentarios;

8. **Las tres puertas del diccionario y la publicacion.** `check-unicidad` lee
   las `clave_negocio` de las fichas nuevas, asi que comprueba de verdad el grano
   de los cinco objetos:

       python main.py check-unicidad
       python main.py check-declarados
       python main.py check-diccionario

   Las tres con **codigo 0**, y `check-diccionario` tiene que ver **150 fichas y
   150 objetos**, biyeccion exacta. Y despues, la unica escritura:

       python main.py publicar-diccionario

   **Version 21.** Lo publicado hoy es la 18.

### T27 · LA BATERIA DE TRES PREGUNTAS AL MCP (MANUAL, humano) · R34

Es la prueba de aceptacion de verdad de esta feature: si el diccionario esta
bien escrito, el MCP contesta **sin que se le explique nada en el prompt**. Se
le pregunta tal cual, en lenguaje natural, **sin nombrar tablas ni columnas y
sin darle pistas**, y se pegan sus respuestas aqui debajo.

**Antes de preguntar**: el MCP lee el diccionario publicado en `_meta`, no el
del arbol, asi que esto no significa nada hasta que `publicar-diccionario`
(verificacion 8 de arriba) haya corrido. Con la version 18 publicada, el MCP no
sabe que estos objetos existen.

1. **«Cuando vence la factura FR25/04222 y esta pagada?»**
   Lo que tiene que hacer bien: ir a `compras.vencimientos` o a
   `compras.v_facturas_pago`, y **no sumar los ocho efectos**: si contesta un
   importe de 288.123,92 en vez de 92.478,49, la ficha de la anulacion no ha
   servido de nada y hay que reescribirla. Tambien es correcto que avise de que
   tres efectos estan anulados.

2. **«Que dice el texto de la ultima factura que tenga una retencion?»**
   Lo que tiene que hacer bien: ir a `compras.documento_texto` o a
   `compras.documento_comentarios` --y NO a `raw.dcf.tex`, que esta informado en
   el 0,3 %--, y si cita «el ultimo comentario», que sea el de `orden = 1` y no
   el del `orden` mas alto.

3. **«Que facturas no cuadran con la forma de pago de su contrato?»**
   Lo que tiene que hacer bien: usar `compras.v_control_forma_pago`, **decir que
   la mitad de las facturas de compra no cuelgan de ningun contrato** y por lo
   tanto no estan en la comparacion, y no confundir «falta el dato en un lado»
   con «no coinciden» (para eso esta `forma_pago_comparable`).

**Si el MCP falla una, el problema es la ficha, no la pregunta.** La respuesta
se pega aqui con la fecha, y lo que haya que corregir del diccionario entra como
deuda de F-080 antes de cerrarla.

## DESPLIEGUE DEL 2026-09-15 · imagen `r20260915-1014`

**Hecho por el humano**, con las tres features ya cerradas y aprobadas:
**F-073**, **F-081** y **F-080**. Antes del despliegue se fusionaron las tres a
`main` en el commit de merge `c3baf88` (la rama de F-080 las contenia
encadenadas) y el humano hizo `git push origin main`.

| paso | resultado |
|---|---|
| `70_build_image.ps1` | imagen `acralbaranesdev.azurecr.io/datamart-seg-anual:r20260915-1014`, construida en ACR en 43 s |
| `85_update_job.ps1` | job apuntado; imagen anterior era `r20260910-0102` |
| Verificacion del job | `az containerapp job show` devuelve **`...:r20260915-1014`**, disparo `Schedule` |

**La comprobacion del job NO es opcional y por eso esta aqui**: la nocturna
llego a correr una imagen de diez dias antes sin que nadie lo notara.

**OJO CON UN FALSO SUSTO DEL SCRIPT**: la cabecera de `85_update_job.ps1`
imprime un tag calculado con la hora actual (`r20260915-1017`), que **no es el
que aplica**. El aplicado es el de «Imagen nueva» y el que devuelve `az`.

**`bash harness/init.sh` sobre `main` sale en ROJO por una sola razon, y no es
del codigo**: la ultima comprobacion del arnes prohibe que los agentes trabajen
en `main`. Lo que importa salio verde: **4.677 pasan, 179 saltados, 0 fallos**.

### PENDIENTE: la primera nocturna con esta imagen

**Decision del humano sobre CUANDO correrla.** Se le advirtio de que lanzarla a
mediodia compite por los creditos de CPU del `psql-albaranes-rs9k2`, que es
**compartido** con albaranes, partes, remesas, el portal y facturas: dia y noche
gastan la misma hucha y, a cero, todo va unas cinco veces mas lento.

Cuando la nocturna haya corrido, **en este orden**:

```
python main.py check-raw-recuentos    # 68 tablas, ocho mas que antes
python main.py check-declarados
python main.py check-diccionario
python main.py publicar-diccionario   # UNICA escritura; sube a la version 21
```

Y las verificaciones MANUAL propias de cada feature, ya anotadas mas arriba:
las de F-073 (recuentos 804/683, 193, 69, 921 y las 21 columnas, mas la prueba
del puente 261/261) y las de F-080 (T0 bis, T7, T26 y T27).

## F-078 · MATERIALIZAR FactCPTipologia (en curso, 2026-09-15)

Rama `feature/F-078-materializar-cp-tipologia`, rigor `critico`, `sdd=false`.
Informe: `progress/impl_F-078.md`, con el plan de tareas numerado.

**HAY UNA NOCTURNA EN CURSO** (job lanzado a mano con la imagen
`r20260915-1014`, `run-all --full`, unas 3 h 30). Por eso el implementer **no
ejecuta ninguna escritura contra Azure**: `build_mart` dropea y reconstruye, y
cruzarse con la nocturna es buscarse un problema. La autorizacion del humano del
2026-09-09 para construir las tres tablas a mano es ANTERIOR a esta nocturna.

### VERIFICACIONES MANUAL (humano) · cuando la nocturna haya TERMINADO

En este orden y con el codigo de la rama ya en el arbol:

```
python main.py build-mart              # construye las tres tablas nuevas
python main.py check-cp-tipologia      # las cifras no cambian: diferencias = 0
python main.py inspect-cp-tipologia --obra <obra> --anio 2025
python main.py check-declarados
python main.py check-diccionario
python main.py publicar-diccionario    # sube a la version 22
```

Lo que hay que ANOTAR de cada una (criterios 3 y 4 de la ficha, que no se
demuestran afirmando): el **tiempo** que tarda el sub-paso `cp_tipologia` de
`build-mart` (lo imprime el log `mart_substep_done`) y sus filas, el **numero de
diferencias** que dice `check-cp-tipologia` —tiene que ser **0**— y el tiempo de
un `SELECT * FROM mart.v_pbi_cp_tipologia` contra Azure. Falta ademas abrir el
`.pbix` y refrescar **FactCPTipologia** sin tocar una linea del `.pq`
(criterio 2), y que `check-diccionario` de biyeccion exacta con **153 fichas y
153 objetos** (criterio 6).

**DOS AVISOS SOBRE `check-cp-tipologia`, que no son cosmeticos.** (1) Recalcula
la vista de antes, que es *la consulta que no terminaba en 60 s*: con
`--obra <obra>` se desploma y sirve de sonda antes de lanzarla entera. (2) Hay
que lanzarlo **el mismo dia** en que se construyo la tabla: la mitad izquierda
evalua `CURRENT_DATE` ahora y la derecha lo lleva **congelado del build**, asi
que si entre medias cambia el mes, las dos cortan en meses distintos y las
diferencias que salgan son legitimas. Ese congelado es el **unico** cambio de
semantica de la feature y esta escrito en el SQL, en la ficha y en el `--help`.

El detalle completo --decisiones, riesgos y evidencias-- en
`progress/impl_F-078.md`.

## F-078 · LAS VERIFICACIONES MANUAL, EJECUTADAS EL 2026-09-15 CON SU RESULTADO REAL

El review (pasada 1) devolvio **CHANGES_REQUESTED** sin un solo defecto de
codigo: faltaba **evidencia** de seis criterios. El humano **autorizo de nuevo
la escritura** esa tarde —la del 2026-09-09 habia caducado con la nocturna— y se
ejecutaron, en este orden y contra el Postgres de Azure.

**Contexto**: la nocturna `caj-datamart-seg-dev-4kvgq5q` (imagen
`r20260915-1014`) habia terminado a las 11:44 UTC, `Succeeded`, en **3 h 22
min**, y con `check-declarados` y `check-diccionario` en verde sobre `main`
(150/150, version 21).

### 1 · `python main.py build-mart` — criterios 1 y 4

| sub-paso | duracion | filas |
|---|---|---|
| `build_fact` | 1.157,74 s | 5.367.594 |
| `agg_categoria` | 92,65 s | 24.805 |
| **`cp_tipologia` (el nuevo)** | **1.162,06 s** | **1.740** |
| **total `build_mart`** | **2.414,6 s** | 5.394.139 |

**El paso nuevo cuesta 19 min 22 s**, casi lo mismo que el hecho principal, y
eso con solo 1.740 filas escritas: el coste no esta en escribir, esta en
calcular la version vigente y el corte temporal. **La ventana nocturna pasa de
3 h 22 min a ~3 h 41 min**, aun por debajo de las 4 h de referencia, pero el
margen baja de 38 a ~19 min. **Es el intercambio acordado**: ese calculo dejaba
de pagarse en cada consulta.

### 2 · `python main.py build-cierre` — obligatorio y NO opcional

`mart/01_ddl.sql` y `mart/03_agg_categoria.sql` hacen `DROP TABLE … CASCADE`, y
`cierre/06_views_planif_vs_real.sql` lee de `mart.fact_seguimiento_categoria`.
**Reconstruir el mart a solas deja el cierre roto** —el incidente de F-047 en
pequeño—. Ejecutado despues: `[SUCCESS] build_cierre rows=16.972
duration=2.943,0 s`.

### 3 · `python main.py check-cp-tipologia` — EL CRITERIO 3, EL QUE MANDA

* **Sonda previa** (`--obra 650280`): `OK 23 filas y CERO diferencias`, en 3 s.
* **Comparacion completa**, 14:31:01 → 14:59:53 UTC (**28 min 52 s**):
  **`OK 1740 filas y CERO diferencias: materializar no cambio ninguna cifra`**.

### 4 · Cronometro de la consulta — criterios 4 y 8

| consulta | resultado |
|---|---|
| `SELECT * FROM mart.v_pbi_cp_tipologia` | **1.740 filas en 0,81 s** |
| `count(*)` de `mart.v_master_versiones_tipadas` | 4.415 filas en 0,21 s |
| `count(*)` de `mart.v_master_vigente_anual` | 748 filas en 0,26 s |

Antes **no terminaba** y colgaba Power BI. La ventana de 30 s del MCP deja de
ser un problema por un factor de ~37.

### 5 · Las dos puertas — criterios 6 y 7

* `check-declarados`: **153 declarados / 153 construidos**, salida **0**, con
  `config/objetos_pendientes.yaml` **vacio**.
* `check-diccionario`: **153 fichas / 153 objetos**, biyeccion exacta. Primero
  salio **KO con codigo 1** porque el arbol iba por la **22** y lo publicado era
  la **21**; tras `publicar-diccionario` (199 filas, 964 columnas, 16 reglas,
  hash `89d29bab993c`) repite en verde con **codigo 0**.

**AVISO DE METODO, para no repetirlo**: los primeros `EXIT=$?` que se leyeron
venian **despues de una tuberia a `tail`**, asi que eran el codigo de `tail` y
no del comando. Los codigos de arriba estan medidos sin tuberia.

### Lo que sigue pendiente de F-078

El criterio 2 exige que **Power BI cargue `FactCPTipologia` con el `.pq` actual
sin tocar una linea**, y eso **solo lo puede probar el humano** abriendo su
informe. Es lo unico que ningun comando puede demostrar.

## 2026-09-16 · F-083 cerrada: el criterio 6 verificado por el MCP

El reviewer dio **APROBADO** en la pasada 1 dejando abierto el **criterio 6**,
que no lo cierra ningun comando: hay que preguntarle al MCP, sin explicarle
nada, lo que Juan Romero no podia preguntar. Hecho el 2026-09-16.

Antes se publico el diccionario: **version 23**, hash `cdbbe0996c67`, **153
objetos y 969 columnas**, y `check-diccionario` repitio en verde con **codigo
0** (medido sin tuberia).

La pregunta, tal cual, agrupando las facturas vencidas y sin pagar por el
estado de la FACTURA (no por el del efecto):

```sql
SELECT f.estado, count(DISTINCT v.factura_id) AS facturas,
       round(sum(v.importe), 2) AS importe_pendiente
FROM compras.vencimientos v
JOIN compras.facturas f ON f.factura_id = v.factura_id
WHERE v.efecto_anulado = false
  AND v.fecha_vencimiento < current_date
  AND v.estado_pago_codigo <> 10
GROUP BY f.estado ORDER BY sum(v.importe) DESC
```

Reparto real: **5.233 «Aprobado pago» (26.873.652 EUR)**, 382 «Fra. GG
Contabilizada», 106 «Aprobada Jefe de grupo», 49 «Contabilizada», **26
«Rechazada»**, 26 «Recibida», 16 «Aprobada por jefe de obra» y 15 «Aprobada
Administracion». Eso es exactamente lo que el correo pedia y antes no se podia
separar del estado del efecto.

**Aviso que queda en la ficha**: hay dos parejas de estados casi homonimos
—`APR`/`APR_DG` ambos «Aprobado pago», `REC`/`REC_ADM` ambos «Recibida»—, asi
que **se filtra por mnemonico, nunca por el literal**.

## 2026-09-16 · Despliegue de F-083

Imagen construida: **`acralbaranesdev.azurecr.io/datamart-seg-anual:r20260916-2212`**.
Es el tag que tiene que verse en los logs del job y en `python main.py version`.

`85_update_job.ps1 -Tag r20260916-2212` lanzado a las **20:13 UTC**, con **3 h 46
min de margen** frente al cron de las 00:00 UTC. La leccion de F-078 —la
nocturna del 16 corrio con la imagen vieja y deshizo la feature— no se repite
esta vez.

## 2026-09-17 · F-084 verificada en la base, y el MCP que sirve un diccionario viejo

El humano ejecuto las tres verificaciones MANUAL que ningun agente puede hacer.

**`build-compras`: exit 0, 233,9 s, 3.136.919 filas.** El sub-paso `documentos`
tardo 88,3 s. **Es la unica validacion real del CUERPO de
`compras.fn_estado_documento`**: hasta aqui solo se habia validado que el parser
la aceptaba.

**El grano, medido por el MCP contra la tabla construida**: `compras.contratos`
publica **18.994 filas / 18.994 `contrato_id` distintos**, y **18.994 con estado
(el 100 %)**. El lateral no multiplica. Los siete estados del tipo 44 suman
exactamente 18.994: FIR 13.475, TER 3.179, **EPF 808**, PFP 576, RFP 548, COMD
232, RES 176.

**Las cifras bailaron respecto a lo que midieron los agentes el 16-09** —18.978
filas y 818 enviados— **porque la nocturna del 17 reingirio**: 16 contratos
nuevos y diez que se firmaron. Es la tabla viva, no la feature. `status`
confirma que `raw.ctr` tiene **18.994**, las mismas.

**`publicar-diccionario`: version 24**, hash `292f63baaf51`, **154 objetos, 972
columnas**, cobertura 100 %.

### EL HALLAZGO: el servidor MCP cachea el diccionario (ficha F-089)

Publicada la 24, se pregunto por las dos vias **en el mismo minuto**:

* **Por SQL (`_meta.v_diccionario`)**: `compras.contratos` con **15 columnas** y
  las tres nuevas con su significado entero, el aviso de filtrar por
  `estado_codigo` y los `ejemplos_preguntas` con el OJO de la pregunta trampa.
  **Correcto.**
* **Por `describir_tabla` del MCP**: **12 columnas** y las tres nuevas con el
  significado **vacio**. Llamado **dos veces despues** de publicar.

El servidor leyo el diccionario al arrancar y no lo vuelve a mirar. **La
nocturna publica cada madrugada, asi que la deriva es diaria y silenciosa**, y
la propia cabecera del servidor lo delata: anuncia la **version 12** del
2026-09-03 con 103 objetos cuando la base va por la **24** con 154. **Catorce
dias desfasado sin que nadie lo notara.**

**No es un fallo de F-084**: el dato esta publicado y verificado por SQL. Pero
obliga a **reiniciar el MCP a mano** para ver cualquier ficha nueva, y rompe la
verificacion «se responde por el MCP» de toda feature que publique diccionario.

## 2026-09-17 · F-084 desplegada

Imagen: **`acralbaranesdev.azurecr.io/datamart-seg-anual:r20260917-1359`**,
confirmada en el job a las **12:02 UTC**, con doce horas de margen frente al
cron. Hacia falta desplegar aunque F-084 solo toque SQL: `compras/00_setup.sql`
y `compras/01_documentos.sql` **viajan dentro de la imagen**, y sin el tag nuevo
la nocturna habria reconstruido `compras.contratos` **sin la columna de estado**,
deshaciendo lo construido a mano. Es lo que paso con F-078 el 16-09.

**AVISO SOBRE LA SALIDA DE `85_update_job.ps1`, para no volver a dudar**: su
cabecera anuncia una `Imagen` que **NO es la que se despliega**.
`infra/00_vars.ps1:189` calcula `$TAG` con `Get-Date` **cada vez que se carga**,
asi que a las 14:00 locales la cabecera dijo `r20260917-1400`, un tag que no
existe en el registro, mientras se desplegaba `r20260917-1359`. Lo que vale es
la linea **`Imagen nueva`** y la tabla de confirmacion. Cosmetico, pero despista
justo en el momento de comprobar un despliegue.

## 2026-09-22 · F-057 verificada en la base por el humano

Las verificaciones MANUAL que ningun agente puede hacer, en este orden:

* **`build-personal`: 7,2 s**, 2.618 recursos y **330.853 lineas de parte** (330.638
  en la medicion de la spec: la diferencia son partes nuevos de la nocturna).
* **`check-declarados`: 158 / 158**, los 154 anteriores mas los cuatro de
  `personal`.
* **`check-unicidad`**: los tres objetos de `personal` en **OK**. Sale con codigo 1
  por **`cierre.v_pbi_planif_vs_real` (F-051)**, con las mismas 204 combinaciones y
  472 filas de siempre: no es de F-057. Subida a prioridad 1 por el humano ese dia.
* **`check-relaciones`**: las **seis** relaciones de `personal` unen; la de recursos
  hacia partes al 50 %, legitimo (no todos los recursos imputan horas). El codigo 1
  lo dan dos timeouts y cuatro avisos preexistentes, ninguno de F-057.
* **`publicar-diccionario`: version 25**, 158 objetos, 1.015 columnas, contexto de
  **30 filas** (la cifra que el diccionario decia mal como 29).
* **`apply-grants`: 35 permisos con `personal` incluido**, y `raw.emp`, `raw.res`,
  `raw.reshor` y `raw.emphis` **excluidas** del rol del MCP.

**INCIDENTE QUE NO DEBE REPETIRSE**: el primer `apply-grants` dio permiso solo a
**nueve** esquemas, sin `personal`, porque **el `.env` local del humano fijaba
`PG_CONSUMPTION_SCHEMAS` con la lista antigua** y manda sobre el valor por defecto
del codigo. El humano lo corrigio y el segundo salio bien. En Azure no pasa: el job
no fija la variable. **Leccion**: una lista escrita en dos sitios diverge; lo
correcto es no fijarla en el `.env` y dejar que mande el defecto del codigo.

**LO QUE SIGUE FUERA DE ESTE REPOSITORIO**: el servidor MCP tiene **su propia lista
blanca de esquemas**. Consultado el 2026-09-22, responde «el esquema 'personal' esta
fuera del ambito autorizado. Esquemas disponibles: _meta, aux, cierre, compras,
maestro, mart, retenciones, stg». Los `GRANT` de la base ya estan; lo que falta es
anadir `personal` a esa lista, y ese servidor no vive aqui (misma frontera que
F-089).

## >>> PARA RETOMAR LA PROXIMA SESION (escrito el 2026-09-22 al cerrar F-057) <<<

**Ninguna feature en curso.** F-057 cerrada y mergeada. Cola por prioridad:
**F-051 (p1)** · F-055 y **F-093 (p2, empatadas)** · F-038 (p4) · F-089 (p6).

### 1 · URGENTE: fichar lo que salio el 2026-09-22 (el humano no dio aun el OK)

Todo **medido**, con su informe en `progress/`; falta escribir las fichas. Se
propusieron estas prioridades y el humano **no las confirmo todavia**:

| | que | prioridad propuesta | informe |
|---|---|---|---|
| 🔴 | **Retenciones infladas x4**: arreglo inmediato de lo publicado | 3 | `explore_retenciones_contabilidad_fin_obra.md` |
| 🔴 | **El filtro del 250 %** (`stg/08_plan_mensual.sql:515`) | 5 | `explore_bug_plan_mensual_meses.md` |
| 🟠 | Retenciones desde la contabilidad, con fin de obra y plazo (amplia F-059) | 8 | idem retenciones |
| 🟠 | El cierre de gestion en el diccionario | 8 | (ver abajo) |
| 🟠 | Las condiciones del contrato: forma de pago y retencion (sale de F-067) | 9 | `explore_organigrama_y_forma_pago.md` |
| 🟠 | El organigrama de obra: delegado, jefe de grupo, jefe de obra | 9 | idem |
| 🟡 | Conciliar IMPORTES entre capas (el guardian que habria cazado el 250 %) | 10 | — |
| ⚪ | Publicacion atomica del cierre | 20 | — |

**Las dos rojas son datos MAL publicados hoy en produccion**:
* **Retenciones**: `retenciones.movimientos` da **35,5 M EUR vivos a proveedor; son
  ~8,35 M**. El estado sale solo de `fecrea` y no mira `fecbaj` ni `est`: cuenta los
  originales agrupados Y el agrupador (doble conteo) y lo ya pagado. **El orden de
  magnitud falso (34,7 M) esta escrito en `contexto_bbdd`, que lee el MCP.** La
  contabilidad cuadra al centimo con lo vivo real en FERMALUX (64.201,96).
* **250 %**: el filtro borra la subida y conserva la bajada. **89 M EUR ausentes en
  `stg`**, **46.889 EUR en `mart` vigente**. El filtro SI caza basura (68,4 M EUR de 29
  series absurdas en origen), pero incluso ahi deja el total mal: quitar el descarte y
  MARCAR, no borrar. **Toca la version 28 de la 0686 que Juan valido**: avisarle.

**Decisiones del humano que siguen abiertas**:
* Retenciones: **que fecha es «fin de obra»** (fin real cubre solo el 25 % del
  importe vivo; 85 obras cerradas no tienen fin real) y **que plazo** (hoy Sigrid
  aplica factura + 15 meses en el 97,8 %; la garantia del cliente, 12 meses, no es la
  del subcontrato).
* Organigrama: **dos preguntas a Juan** —que campo es para el «jefe de obra» (el
  candidato es el tecnico responsable, pero en 160 de 479 obras es un jefe de grupo) y
  si el «agente» (`obr.ageide`, 471 obras) es el jefe de grupo (coincide en 34 de 36)—.
  **No publicar el codigo del agente**: en 17 tiene formato de n.º de la Seg. Social.

**Cierre de gestion, ya decidido por el humano**: `importe` (sin coeficientes) es la
venta de gestion e `importe_oficial` (con) la oficial; **el diccionario de
`stg.presupuesto.importe_oficial` dice hoy «Es la columna de VENTA» a secas y hay que
corregirlo**. Los historicos son las versiones `Cierre mensual`: no se guarda nada,
solo se documenta; los ocho cierres sin version mensual se marcan provisionales.

### 2 · Pendientes fuera de este repositorio

* **`mcp-bbdd`**: anadir `personal` a `servidor.esquemas_permitidos` en
  `config/config.yaml` y desplegar. El humano tiene el encargo redactado.
* **Sistemas**: la raiz fisica del repositorio documental, para F-090.

### 3 · Deudas del lider

* **Portar a `arnes-base`** dos mejoras de F-057 que valen para cualquier proyecto
  (regla de propagacion obligatoria, NO hecho aun): (a) **para cerrar un conjunto,
  lista blanca**, y una lista negra se valida contra los nombres reales del origen;
  (b) **si una feature cambia la cardinalidad de algo citado en prosa, se busca el
  numero viejo solo** (`\bnueve\b`), no la frase. Van a `CHECKPOINTS.md` C4.
* **Purgar este `current.md`** de las secciones de features ya cerradas (pedido por
  el reviewer de F-057, cambio 8).

## 2026-09-22 · F-057 desplegada

Imagen **`acralbaranesdev.azurecr.io/datamart-seg-anual:r20260922-1158`**,
confirmada en el job con `az containerapp job show` (la cabecera de
`85_update_job.ps1` anunciaba `r20260922-1200`, que es el tag calculado con la hora
y no existe: lo que vale es «Imagen nueva»). La nocturna del 23 construira
`personal` y publicara el diccionario 25. Sustituye a `r20260917-1359`.

## 2026-09-22 · F-095 · SPEC ESCRITA (spec-author), pendiente de aprobacion

Entregado `specs/F-095-retenciones-contabilidad-fin-obra/` (requirements
150/150, design 242/250, 26 tareas). **Resumen, hallazgos y consultas:
`progress/spec_F-095.md`.** La ficha sigue `pending`; va detras de F-094
(precondicion escrita en la spec).

**Decisiones que necesita validar el humano antes de implementar** (opciones,
cobertura medida y recomendacion en `design.md` §Decisiones para el humano):
H1 que fecha es fin de obra y que hacer con las 83 obras terminadas sin ella;
H2 que plazo se suma (falta que Negocio fije el valor fijo); H3 obra de las
bajas sin centro (4,27 M€); H4 ingerir `rac` (filtrada o entera, a acordar con
F-091); H5 lado cliente fuera o dentro; H6 retirar F-059 y F-045; H7 como se
presentan los 3,28 M€ que no cuadran.

**Aviso para F-094**: en `cob` el criterio de `pag` («viva de verdad») da 2,12 M€
frente a 13,81 M€ de saldo contable de cliente: no se traslada tal cual.

### F-095 · decisiones del humano incorporadas (2026-09-22, segunda pasada)

H1-H7 contestadas e incorporadas a la spec (detalle en `progress/spec_F-095.md`).
Fin de obra = inicio de garantia, con respaldo «ultimo cierre con movimiento + 1
mes»: 97,0 % del vivo con fecha, 17 obras sin ella. Plazo `plaret` -> `plagar` ->
12. F-059 se retira como absorbida; el resto de F-045 lo hace F-094. La spec ya
no tiene decisiones abiertas: queda la aprobacion del humano y que F-094 este
`done`.

## 2026-09-23 · F-102 · SPEC ESCRITA (spec-author), pendiente de aprobacion

Entregado `specs/F-102-obra-duplicada-empresa-28/` (requirements 137/150, design
250/250, 17 tareas) en la rama `hotfix/F-102-obra-duplicada-empresa-28`, desde
`main` y en worktree aislado (F-101 sigue en el arbol principal; la spec no toca
ninguno de sus ficheros). Ficha `sdd: true`, `spec_ready`. **Resumen, hallazgos y
consultas: `progress/spec_F-102.md`.**

**Hallazgo que cambia el alcance**: `stg.obras` elige hoy la ficha sin datos en
0720 (la copia vacia de la empresa 28), 0252 y 0517, y `mart`/`cierre` pierden
esas tres obras enteras. La empresa 28 es PORSAN E HIJOS CONSTRUCCIONES SL.
`condir` si se ingiere y no aporta ninguna direccion de obra.

**Decisiones que necesita validar el humano antes de implementar** (opciones y
recomendacion en `design.md` §8): D1 ranking de la ficha principal (la
recomendada arregla las tres obras y por eso cambia lo publicado en `mart` y
`cierre`); D2 no reescribir el `obra_id` de las copias y traducir al leer; D3
ingerir `auxemp` para el nombre de la empresa; D4 el aviso a `facturas` lo lleva
el humano con el texto que deja el implementer.

### F-102 · decisiones del humano incorporadas (2026-09-23, segunda pasada)

D1: **la ficha principal es la de Construcciones Ruesma** (empresa 1 primero,
luego `conext 15`, cierres, `tiemod`, `ide`). Medido: frente a hoy cambian 0720
(entra en `mart`), **0581 (sale de `mart`/`cierre`: 85.524 y 76 filas)**, **0606
(se reduce: de 279.817 filas de plan a 1.097)** y 0671 (sin efecto); 0252 y 0517
siguen fuera de `mart` como hoy. **Ese riesgo esta pendiente de aceptacion
expresa del humano: T0 bloquea la implementacion hasta entonces.** D2 (A) y D3
aprobadas. D4: `facturas` es independiente, sin aviso; en su lugar entra el
repaso de `compras` (las cinco vistas de consumo con obra ganan
`obra_principal_id`) y de toda ficha con relacion a `maestro.obras.obra_id`
(`personal`, despues de F-101). Detalle: `progress/spec_F-102.md`.

### F-102 · tercera decision (2026-09-23): `personal.recursos`

Absorbe el correo de Juan Romero («codigo_recurso no es unico»): el codigo es
unico por empresa (61 repetidos, 0 dentro de una empresa). `personal.recursos`
ganara `empresa_id` y `nombre_empresa`, y su ficha la clave legible (`empresa_id`,
`codigo_recurso`). **Depende de que F-101 este fusionado en `main`** (T16-T17).
**Abierta D5**: marca de «misma persona en otra empresa»; recomendado no
publicarla (solo 13 de 91 casan por NIF exacto). Siguen pendientes: aceptar el
riesgo de D1 (0581 sale de `mart`/`cierre`, 0606 se reduce) y D5.

### F-102 · decisiones FINALES (2026-09-23): SUSTITUYEN lo anterior

Modelo del humano: las obras son por empresa (misma obra vista desde cada
empresa, sin consolidar). F-102 solo publica **identificadores**: `clave_obra` y
`clave_recurso` (`<empresa>-<codigo>`, medidas unicas: 922/922 y 2.618/2.618),
`empresa_id`, `nombre_empresa` y la ficha de Ruesma (`es_ficha_principal`,
`obra_principal_id`) en `maestro.obras`, mas `obra_principal_id` en las cinco
vistas de consumo de `compras`. **`stg.obras` NO cambia** (0581 y 0606 no
pierden datos); difiere de la marca en 0581, 0606, 0671 y 0720, y lo resuelve
**F-106** (ficha pendiente del lider). La vista va a `maestro.v_obra_fichas`, no
a `stg`. D2 A, D3 si, D4 sin aviso a `facturas`, D5 A. La parte de
`personal.recursos` sigue dependiendo de F-101 en `main`. Sin decisiones
abiertas: `progress/spec_F-102.md`.

**SPEC APROBADA (humano, 2026-09-23)** con un ultimo ajuste: las cinco vistas de
`compras` publican `empresa_id` y `clave_obra`, **no** `obra_principal_id`, que
queda solo en `maestro.obras` como referencia (no se consolida). Lineas de fichas
no Ruesma en `fact_compras_linea`: 91.431; 84.233 (31,77 M€) con codigo
compartido con Ruesma.
