<!-- docs/ARCHITECTURE.md -->
# Arquitectura · datamart-seg-anual

ETL Sigrid → PostgreSQL → Power BI para el seguimiento económico mensual de
obras. Microservicio único; se despliega como job programado en Azure.

## Hexagonal + pipeline

- `etl_sigrid/domain/` — entidades puras (TableSpec, ColumnSpec, StepResult,
  StepStatus). CERO imports de infraestructura.
- `etl_sigrid/application/` — `Orchestrator` ejecuta una lista de steps.
  Cada step hereda de `steps/base.py::PipelineStep` y recibe/enriquece un
  contexto. Steps actuales: ingest_raw, load_excel_aux, build_stg, build_mart,
  build_maestros, build_cierre.
- `etl_sigrid/infrastructure/` — adaptadores: `sigrid/sigrid_api_client.py`
  (HTTP a sigrid-api), `postgres/postgres_client.py`, SQL por capas en
  `postgres/sql/`, logging estructurado.
- Punto de entrada: `main.py` (click). El pipeline se compone en main, no
  dentro de los steps.

## Capas PostgreSQL (¡no existe capa en `public`!)

`raw` → `stg` → `mart` (+ `cierre` para cierres mensuales y planif vs real).
Módulos adicionales: `compras`, `maestro`, `retenciones`, `personal`,
`contabilidad`, `tesoreria`, `descompuestos`, `auxiliar`. SQL numerado `NN_nombre.sql` y
ejecutado en orden dentro de cada capa.

**`personal` (F-057, 2026-09-18) es el único esquema con datos personales**
—nombre, NIF y DNI, publicados con autorización expresa del responsable del
dato—, y es un esquema propio precisamente por eso: los permisos de PostgreSQL
se dan POR ESQUEMA, así que dar o quitar el acceso a estos datos es un `GRANT`
y no una lista de tablas que mantener (F-087). **Power BI SÍ ve `personal`**:
lo decidió el humano el 2026-09-22, y corrige la idea inicial de F-057 («Power
BI sí, datos de personal no»). El esquema propio sigue sirviendo para poder
quitárselo a un rol concreto sin trocear permisos. El segundo motivo es que no
bloquea: metido dentro de `build_stg`, un fallo de su SQL dejaría al `mart`
sin construir esa noche.

**`contabilidad` (F-056, 2026-09-26) es el mayor y el plan de cuentas**, y es
esquema módulo por los mismos dos motivos: permisos por esquema y no bloquear
(`build_contabilidad` solo depende de `ingest_raw` y nadie depende de él). Lee
`raw` y la vista `maestro.centros_coste`, nada más. Tres tablas:
`contabilidad.plan_cuentas` (el plan FINANCIERO como árbol, de las 38
empresas), `contabilidad.mayor` (una fila por apunte de `raw.apu`, 2,17 M, con
una guarda que hace fallar el paso si el recuento no es el del origen) y
`contabilidad.saldos_cuenta_mes` (cuenta × empresa × ejercicio × mes, desde el
mayor). El mayor se MATERIALIZA porque `raw.apu` no tiene índice por cuenta y se
recrea cada noche: como vista, cualquier agregado de empresa o año pasaría de
la ventana de 30 s del MCP.

**Desde F-135 (2026-10-11) la contabilidad son DOS esquemas**, por la misma
razón de fondo: los permisos de PostgreSQL se dan por esquema, así que lo que el
rol general no debe leer vive físicamente en otro que nunca se le concede.
`contabilidad_restringida` lleva la contabilidad COMPLETA —las tres tablas de
F-056 con las mismas filas, columnas y cifras, y en el mayor tres columnas más:
`restringido`, `motivo_restriccion` y `saldo_acumulado_visible`— y solo la lee
el grupo `sigrid_dm_autorizado_ro` (NOLOGIN; sus miembros los decide Negocio).
`contabilidad` pasa a ser la GENERAL, la que leen el MCP y Power BI: sin los
apuntes de PERSONAL (los asientos de nómina enteros y las cuentas de
trabajadores: 55.504 apuntes, el 2,55 %, criterio en
`domain/restriccion_personal.py`), con las 521 cuentas de personal enmascaradas
en el plan, el saldo acumulado recalculado sobre lo visible (el del completo
delataría lo restringido en las cuentas mixtas), `incompleto` en los saldos y
`contabilidad.apuntes_restringidos_mes` con solo recuentos de lo que falta. Las
generales siguen materializadas y con los índices de siempre; un `DO` al final
de `05_mayor_general.sql` hace fallar el paso si se cuela un apunte de cuenta
restringida o si general más restringidos no suman el completo. Regla dura
`R-PERFILES`: el mayor completo se lee solo de
`contabilidad_restringida` y los dos esquemas nunca se suman.

**`tesoreria` (F-037, fase 1, 2026-10-13) es la cartera de cobros y pagos**:
una fila por EFECTO de `raw.pag` (PAGO) y `raw.cob` (COBRO), tal cual, con su
estado PREVISTO/REALIZADO/BAJA (precedencia de F-094, igual en los dos
sentidos: la baja gana y `est = 10` sin fecha real es REALIZADO), su signo de
caja (`importe_flujo`), la obra por el centro de coste (y, desde F-140, en los
pagos sin centro, por su factura: `obra_via`) y la marca
`previsto_antiguo` (PREVISTO vencido hace más de 2 años: deuda sin puntear, no
caja). Mismo patrón de DOS esquemas que la contabilidad:
`tesoreria_restringida.efectos` es la cartera COMPLETA con `restringido` y
`motivo_restriccion` (los pagos de nómina, embargo y cuota: 37.053; criterio en
`domain/tesoreria.py`, que importa el de cuentas de F-135), y solo la lee el
autorizado y el total; `tesoreria.efectos` es la GENERAL, sin ellos, con una
guarda `DO` que recalcula el criterio desde `raw` y hace fallar el paso si se
cuela uno, y `tesoreria.efectos_restringidos_mes` cuenta lo que falta (sin
importes). **Las tablas no se dropean** (`CREATE TABLE IF NOT EXISTS` +
`TRUNCATE` + `INSERT`, patrón de `personal`): `compras.vencimientos` de F-080 es
desde F-037 una VISTA de `tesoreria.efectos` (pago y factura de compra, mismas
columnas), y un `DROP ... CASCADE` se la llevaría cada noche. `build_tesoreria`
solo depende de `ingest_raw`, va delante de `build_compras` en la lista y nadie
lo declara en su `depends_on`: si falla, su `TRUNCATE` se deshace y compras lee
la cartera de ayer. Es cartera, no devengo. Reglas duras `R-TESORERIA-ESTADO`
y `R-PERFILES`.

**Los ingredientes de la caja futura (F-140, 2026-10-25), en el mismo esquema.**
El ETL **no** convierte devengo en caja: publica lo necesario para que lo haga
quien consulta, declarando sus hipótesis (regla dura `R-CAJA-HIPOTESIS`).

- **Lo pactado**: `tesoreria.plazos_forma_pago` (vista: las formas de pago de
  `auxpag` y de cobro de `auxcob`, con la fórmula de plazo leída por tres
  funciones `fn_plazo_*` que replican `domain/proyeccion_caja.py`),
  `tesoreria.condiciones_contrato_compra` (por contrato de `raw.ctr`: forma de
  pago, días fijos del proveedor, retención de garantía) y
  `tesoreria.condiciones_contrato_cliente` (por contrato de `raw.obrctr`).
- **El devengo pendiente** (`07_devengo_pendiente.sql`, una transacción con
  tablas temporales y `ANALYZE`: sin estadísticas el planificador elegía bucles
  anidados y tardaba 875 s): para la última versión master V de cada obra con
  meses planificados tras su último cierre, lo pendiente se descuenta **por
  partida** de lo ejecutado desde que V entró en vigor
  (`tesoreria.devengo_pendiente_partida`), se reparte por mes según el plan de V
  (`tesoreria.devengo_pendiente_obra_mes`; una guarda `DO` exige que la suma
  cuadre) y se resume por obra con su frontera con la cartera
  (`tesoreria.devengo_corte_obra`: `cartera_viva` y
  `cartera_emitida_tras_cierre`, para no contar dos veces lo ya emitido). Lee
  `stg.plan_mensual` y `mart.fact_seguimiento_mensual` de la misma noche:
  `build_stg` y `build_mart` van delante, y la reanudación de F-148 lo sabe
  (`LECTURAS_PARA_REANUDAR`).
- **Las hipótesis**: las 30 (H01-H30 desde F-150) viven en `config/hipotesis_caja.yaml`, que
  mantiene Control de Costes y aprueba el humano; `build_tesoreria` lo valida
  (`infrastructure/config/hipotesis_caja_yaml.py`) justo antes de cargarlo y,
  si tiene errores, el paso queda FAILED con la lista: lo de `01`-`07` (cartera,
  condiciones y devengo) ya está escrito con los datos de hoy, y lo que NO se
  escribe son las tres tablas de hipótesis, que se quedan como estaban (si el
  fallo es una obra del YAML que no existe, la guarda de `08` salta con el
  catálogo y la sección manual ya cargados y `hipotesis_caja_obra` es la de
  ayer). Se publican en `tesoreria.hipotesis_caja` (catálogo, todas
  `validado` falso hoy), `tesoreria.hipotesis_caja_manual` (la sección `obras`)
  y `tesoreria.hipotesis_caja_obra` (las 30 en cada obra, con su nivel: MANUAL >
  SIGRID > DEFECTO; SIGRID para H09-H11, de los contratos con el cliente, y desde
  F-150 H12, el tipo de IVA de la ficha de la obra).
- Ingesta: `auxcob` y `auxefc` entran a `raw` (78 tablas).

**La receta de la caja (F-150, 2026-10-28), en el mismo esquema.** Sigue sin
haber caja proyectada (F-151); lo que cambia es que la IA combina los
ingredientes SIEMPRE en el mismo orden y con el dato del contrato:

- **La receta** vive en la ficha de `tesoreria.hipotesis_caja` (excepción
  acotada D1 de `docs/CONVENTIONS.md`): ocho pasos (`PASOS_RECETA` del
  dominio: SALDO, DEVENGO, DOCUMENTO, COEFICIENTES, PLAZO, RETENCION, IVA,
  CARTERA; el SALDO es el paso 0) y
  cada hipótesis declara el suyo (`paso_receta`, obligatorio: sin él el YAML no
  valida). Las 30 incluyen los perfiles `PERFIL_MESES` (pares `[meses, %]` que
  reparten el importe entero: H03, H08, H24, H25), el hueco de facturación (H26)
  y la antigüedad de los albaranes que dejan de ser caja (H27).
- **El contrato de cada partida** (`raw.obrparpar.ctride`): `06` lee su
  `coestr` (líneas `CODIGO|etiqueta|valor||base`, por código, con
  `tesoreria.fn_coeficientes`; `COEF_DESADJ` en cascada, `RET*` aparte) y su IVA
  (`raw.iva`). `07` da a cada partida de venta su `coeficiente_venta`: el del
  contrato, si no `importe_oficial / importe` del master 9 y si no del 11 en la
  versión V (`stg.presupuesto`); una partida de venta con pendiente y sin
  ninguno tumba el paso (D6). La obra-mes suma el pendiente con coeficientes, el
  IVA y la retención del contrato, y las bases sin ese dato (para H12 y H10).
- **El hueco de facturación** (`devengo_corte_obra`, N9): por obra, la venta
  real a origen con coeficientes (la partida sin coeficiente, con la media
  ponderada de su obra, `MEDIA_OBRA`) menos lo facturado (`raw.dvf.totbas` por
  el centro de coste de la obra), con suelo 0; lo facturado por delante se
  publica aparte y no se cobra. IVA y retención del hueco, por el peso de cada
  contrato.
- Ingesta: `iva` entera y `dvf` con la lista blanca `include_columns` (9 de sus
  151 columnas): 80 tablas.
- **Los albaranes netos por proveedor** (N11, 29-10): `09_albaranes_pendientes.sql`,
  el último sub-paso, publica `tesoreria.albaranes_pendientes_neto`: lo pendiente
  de facturar de las obras de la receta NETO por (obra, proveedor), con lo
  sobrefacturado compensando primero lo más antiguo (FIFO, `neto_fifo` del
  dominio) y suelo 0. **Lee `raw.dca`, `raw.dcapro` y `raw.con`, no `compras`**:
  `compras` se construye DESPUÉS de `tesoreria` y daría el pendiente de la víspera.
  La fórmula del pendiente es una **copia deliberada** de la de
  `compras/01_documentos.sql`, atada por un test que compara el texto (como
  `tesoreria.fn_fecha` y `fn_serie`).
- **El coste proporcional no es caja de la obra** (N12): la receta lo excluye por
  `categoria` (H02 ya no tiene clave `CP`) y `07` publica en `devengo_corte_obra`
  la parte CP de la cartera de pago, por la categoría de las partidas de la
  factura de cada efecto (`raw.dcfpro`, también copia deliberada: `compras` aún no
  está construido). Su caja es F-154. **El personal** (N13) va por el devengo del
  recurso: la receta no suma nóminas de la cartera.
- **El saldo de partida** (N14, 30-10): `10_saldo_partida.sql`, tras los
  albaranes, publica `tesoreria.saldo_partida_obra`, una fila por obra de la
  receta: lo cobrado y pagado REALIZADO de `tesoreria.efectos` (CON IVA), los
  pagarés agrupados por sus ORIGINALES (de BAJA con `estado_codigo` 14: H29 lo
  declara como hipótesis que rompe `R-TESORERIA-ESTADO`), la cuota CP de lo
  pagado (como en `07`) y el personal por el coste de sus partes (`raw.hmores`,
  PERSONA interna) hasta el último cierre, para no contarlo dos veces con el
  devengo. La cuenta del saldo es del paso 0 de la receta (H28).

**`descompuestos` (F-097, 2026-09-28) es de qué se compone cada partida**, por
ORIGEN, y es el primer esquema del datamart que NO se reconstruye de cero:
ver «Los descompuestos: el primer esquema incremental», más abajo.

## Semántica Sigrid imprescindible (fuente de bugs si se ignora)

- Ámbitos: amb=3 Coste Real, amb=7 Venta Real, amb=8 Master Coste,
  amb=11 Master Venta.
- Master (amb 8/11): `fas` = número de VERSIÓN; planif explosionada.
- Reales (amb 3/7): `fas` = MES; fas=0 = Previsto (foto viva),
  fas=1..N cierres mensuales; planif NO explosionada;
  importe del mes = diferencia con el mes anterior de la serie de la partida
  (ver «La serie real es densa», F-118).
- **EL MES DE UN CIERRE REAL LO DA SU TEXTO (F-051, absorbida en F-118).** El
  mes de cada fila real de `stg.plan_mensual` es `stg.fn_mes_de_fase`: manda el
  texto de la fase (`obrfas.res`, «Agosto 2026»), aunque discrepe de las fechas
  o caiga fuera de ellas; un rango («Enero 2020-Abril 2020») se lee por su
  ÚLTIMO mes; «Mayo-17», «AGOSTO17» y «Abril 2.013» se leen como mes y año; si
  el texto no se entiende, manda el mes de la fecha fin, luego el de inicio y
  por último el `ano`/`mes` que archiva Sigrid. La regla vive UNA vez, en `stg`:
  `mart` y `cierre` leen `anio_mes` sin recalcularlo (`cierre.fn_mes_de_fase`
  la envuelve) y el oráculo `domain/mes_fase.py` la repite token a token para
  `check-mes-fase`. Una fase de RANGO (fecha fin en un mes posterior a su
  inicio) lleva todo su dinero al mes del texto, y los meses desde su inicio
  hasta el anterior al texto reciben filas de RELLENO (`es_relleno`, movimiento
  0, acumulado del cierre anterior), nunca en un mes con cierre propio ni
  después del texto. El parser de las versiones master
  (`cierre.fn_parse_mes_fase`) no cambia.
- **DOS CIERRES EN UN MISMO MES: manda el moderno (F-042).** 22 obras tienen
  dos fases que Sigrid guarda con el mismo `ano` y el mismo `mes` (21 sobre el
  mes del texto). `stg` conserva **una sola**: la de `fas` más alto **entre las
  que tienen el acumulado distinto de cero** (si todas están a cero, la más
  alta). El cierre descartado sigue en `raw` y en `stg.fases`; lo que no tiene
  es fila en `stg.plan_mensual`. `version` conserva el número de fase original,
  con huecos. (F-042 renumeraba un orden interno para el `LAG`; F-118 lo retira:
  la serie densa ya no mira el número de fase.)
- **LA SERIE REAL ES DENSA: LO QUE DESAPARECE SE DESHACE (F-118, F-103
  absorbida).** `importe_mes` de una fila real es su acumulado menos el del mes
  anterior DE LA SERIE DE LA PARTIDA, que recorre sin huecos todos los meses
  del ámbito desde su alta: en un cierre, la fila de Sigrid o, si la partida ya
  no está, acumulado 0 en una fila de DESHACER (`es_deshacer`: anula el
  acumulado anterior, una sola por salida) y, si vuelve, resta contra ese 0;
  en un relleno, el acumulado anterior. Antes se restaba solo si la fila
  anterior era de la fase consecutiva y si no se publicaba el acumulado entero:
  la 0709 daba 319.492,30 € de venta en agosto de 2026 donde el cierre da
  377.492,30, y el número de fase que Sigrid se salta (0371 f27→f29, 0404,
  0455, 0562, 0606) publicaba el acumulado entero. Una fase de la obra sin
  ninguna fila de un ámbito NO es cierre de ese ámbito (Sigrid no abrió esa
  fase de venta en 11 obras de 2010-2020): no deshace nada. Invariante:
  `SUM(importe_mes)` de una partida = su acumulado en el último cierre del
  ámbito de la obra (0 si salió), en TODAS las series; lo comprueba
  `check-cierres` sin apartar ninguna, y `domain/serie_real.py` es el oráculo.
  En `cierre`, un concepto sin filas en un mes con cierre de otro concepto
  conserva el ejecutado a origen del mes anterior.
- **LA VENTA DEL CIERRE VA SIN COEFICIENTES (F-118, D6).** `impcoe`
  (`stg.presupuesto.importe_oficial`) es la venta con los coeficientes del
  contrato con el cliente, y solo existe en los master de venta (11) y de
  certificación (9): la venta real no los guarda. El cierre, el beneficio y el
  análisis usan `importe`, sin coeficientes, como el ejecutado y el coste; la
  venta con coeficientes, lo que se factura, se publica aparte
  (`final_importe_con_coeficientes` y las columnas `_con_coeficientes` de la
  cabecera) y nunca se mezcla (regla dura `R-VENTA-COEFICIENTES`). El
  coeficiente es del CONTRATO, no de la obra, y no vive en ninguna tabla: el
  desglose por contrato es F-099.
- **UN CAPÍTULO PUEDE NO TENER CÓDIGO, Y ESO NO PUEDE CORTAR EL ÁRBOL
  (F-052).** En `raw.obrparpar` hay capítulos cuyo `cod` es la **cadena vacía**
  —no NULL: `length(cod) = 0`—, típicamente porque alguien montó el árbol por
  fases de obra y dejó el código en blanco. Hasta el 2026-08-31 el recorrido de
  `stg/04_partidas.sql` se negaba a **descender a través** de ellos y amputaba
  el subárbol entero: tres capítulos así en la obra 0599 se llevaron por delante
  **1.323 partidas**, 2.624.793,46 € de coste directo y el 100 % de su venta, y
  el datamart publicó durante años un margen del 66,3 % donde el real era del
  1,8 %. La regla es: **el código vacío decide QUÉ SE PUBLICA, no POR DÓNDE SE
  DESCIENDE**. El capítulo en blanco se atraviesa y se colapsa —sus hijos
  cuelgan del ancestro publicado más cercano, y ni `ruta_capitulos` ni `nivel`
  avanzan al pasar por él—, así que se mantiene el invariante
  `cardinality(string_to_array(ruta_capitulos, ' > ')) = nivel + 1`.
- **Y la cadena de `padide` puede dar vueltas.** Hay 12 partidas en ciclo vivas
  —dos auto-bucles y un bucle mutuo—, así que cualquier recorrido del árbol
  necesita corta-ciclos: array de visitados **más** tope de profundidad. Sin él,
  relajar el filtro de código vacío es un `WITH RECURSIVE` infinito dentro de
  una nocturna de 3 h 45.
- **El código de partida no es único ni dentro de su obra (F-109).** Medido el
  2026-09-25: 5.202 pares `(obra_id, codigo_partida)` repetidos, 8.933 filas de
  más, 158 obras, y cada copia es una partida activa y distinta. Tres causas
  explican casi todo: **un contrato o expediente por copia** (el jefe de obra
  abre un capítulo por contrato con el cliente, `obrctr`, o por expediente,
  `obrctrexp`, y repite dentro los códigos), **el mismo subárbol copiado bajo
  capítulos hermanos** (vivienda tipo, bloque, parcela o fase) y **raíces
  paralelas** (fases con raíz propia, `CD`/`CD-FII`, o una raíz duplicada); el
  resto son erratas y copias pegadas dos veces. Ni el contrato desambigua
  (4.437 siguen repetidos) ni `ruta_capitulos` es clave (155). **Se une y se
  cuenta por `partida_id`, nunca por obra + código**: ese JOIN infla el coste
  real de la 0437 de 883.460,55 € a 3.474.491,83 €. Agrupar por código es
  válido si se quiere sumar todas las copias del concepto, y se dice; ante el
  usuario, la partida se identifica por su ruta de capítulos. Es la regla
  `R-PARTIDA-CODIGO-NO-UNICO`. Dos vistas resuelven aún el NOMBRE de un
  capítulo por código (`mart.v_pbi_dim_partida_niveles` y la dimensión CI de
  `cierre`): lo arregla F-111.
- **`hmores.can` NO SON HORAS, Y EL CLASIFICADOR NO ES EL QUE PARECE (F-057).**
  La cantidad de una línea de parte de trabajo trae HORA, DIA, MES o UD en el
  mismo campo, y lo que lo decide es **`auxhor.medide`** (1 HORA, 2 DIA, 3 MES,
  19 UD). **No es `auxhor.ext`**, que se llama «Extra» y está **a cero en las 60
  filas del catálogo**: quien lo mire concluirá que el catálogo no distingue
  unidades y sumará en bruto. `SUM(can)` sin filtrar da **1.837.201,23**
  mezclando 1.249.038,44 horas con 18.009,38 meses, 4.225,46 días y kilómetros.
  Y el reverso, que se olvida: el **71,7 % del euro está en las líneas de MES**
  —el coste de estructura de obra—, así que las horas tampoco son el coste de
  personal completo. `personal.v_pbi_horas_obra_mes` lleva el corte cableado
  para que la trampa no se pueda cometer desde la superficie de consumo.
  `auxmed` (38 filas) no se ingiere: la unidad se traduce con un `CASE`, y la
  rama `ELSE 'DESCONOCIDA'` es el seguro de que una unidad nueva en origen se
  vea en vez de colarse como horas.
- **En los partes de trabajo la obra la manda la LÍNEA, no la cabecera
  (F-057).** `hmores.obride` está informado en el 99,58 % de las 330.638
  líneas, y en 769 discrepa de la obra de su cabecera `hmo`. La trampa de `apu`
  —atribuir por centro de coste, que es la pregunta abierta de F-045— **no
  aplica aquí**: el parte trae la obra, así que `maestro.centros_coste` y
  `res.cenconide` no participan en la atribución, y los dos identificadores
  están vetados por test en el SQL de `personal`. Única excepción, de F-107:
  `res.cenconide` se publica en `personal.recursos` como lo que es —el centro
  de CONTRAPARTIDA del recurso— en una sola proyección que el test descuenta.
- **LA CONTRAPARTIDA ES DEL RECURSO Y LAS CUENTAS SE TRADUCEN EN `maestro`
  (F-107).** El parte CARGA a la obra; la ficha del recurso declara contra qué
  centro de coste y qué cuenta analítica se ABONA (`res.cenconide`,
  `res.caaconide`, informadas en 1.979 de 2.619 recursos). `reshor` no tiene
  contrapartida. `personal.recursos` publica los dos identificadores sin unir
  nada, y `maestro.cuentas_analiticas` (`sql/maestro/06_cuentas_analiticas.sql`,
  sobre `raw.caa` + `raw.con`, `tip = 19`) los traduce: 184.234 cuentas, el
  código único solo dentro de su empresa (`R-CODIGO-POR-EMPRESA`). La cuenta
  de CARGO de cada línea va en `personal.partes_lineas.cuenta_analitica_id`
  (`hmores.caaide`, 93,8 % de las líneas). **Orden de
  despliegue**: `06_cuentas_analiticas.sql` lee `raw.caa`, que crea
  `ingest_raw`; por eso es el ÚLTIMO sub-paso de `build_maestros`, y un
  `build-maestros` a mano antes de la primera ingesta con esta versión falla
  solo en él (`python main.py ingest --table caa --full` antes). `personal` no
  gana dependencias: `raw.res` ya se ingería.
- **LA OBRA Y EL RECURSO SON DE UNA EMPRESA (F-102).** En Sigrid el mismo
  código existe una vez por empresa —Ruesma (1), Porsan (28), cada UTE— y es la
  misma obra vista desde cada una, **sin consolidar** (modelo del humano del
  2026-09-23). Medido: 922 fichas de obra para 846 códigos y 2.618 recursos
  para 2.504 códigos; dentro de una empresa el código es único. Por eso **el
  código solo no identifica nada**: se cruza siempre con `empresa_id`
  (`con.emp`, nombre en `raw.auxemp` por `numemp`) o por la clave legible
  `<empresa>-<código>` —`clave_obra` en `maestro.obras` y en las vistas de
  `compras` con obra, `clave_recurso` en `personal.recursos`—. `obra_id` sigue
  siendo la clave técnica y los hechos llevan la ficha de SU empresa: no se
  traducen. `maestro.v_obra_fichas` (en `sql/maestro/00_setup.sql`, lee solo
  `raw`) decide la **ficha de Ruesma** de cada código (`es_ficha_principal`:
  empresa 1 → `conext` cod 15 → cierres → `tiemod` → `ide` DESC, nunca «`ide`
  menor») y la publica en `maestro.obras` como referencia
  (`obra_principal_id`), que no sirve para agregar hechos de otras empresas.
  Regla dura `R-CODIGO-POR-EMPRESA`. **`stg.obras` NO la usa**: sigue eligiendo
  una ficha por código como hasta hoy y difiere en 0581, 0606, 0671 y 0720;
  pasar el seguimiento a la ficha de Ruesma y traer las demás empresas como
  obras propias es **F-106**.
- `obr.ide = con.ide` (obra hereda de concepto). El nombre legible está en
  `con.res`. `con.nom` NO existe.
- En `raw.obrfas` el campo de fase se llama `fasnum`; en `raw.obrparpre` se
  llama `fas`. No confundirlos.
- Versión de master vigente por obra: campo extendido `cod='15'` en `conext`.
- `importe_origen = round(can * round(precio, decp), deci)`;
  `importe_mes` = diferencia entre orígenes consecutivos.
  REGLA: `importe_mes` jamás se suma entre meses distintos en vistas para
  Power BI; `importe_origen` es acumulado.
- Fechas Sigrid: enteros YYYYMMDD; 0 = NULL.
- La ingesta nocturna SIEMPRE `--full` (el cursor incremental por `ide`
  pierde los UPDATE).
- Palabra reservada `real` en vistas de `cierre` → siempre entre comillas.
- **La retención de proveedor la manda la contabilidad (F-095).** El saldo vivo
  es `retenciones.saldo_contable` (proveedor × obra, con una fila sin obra por
  proveedor); `retenciones.movimientos` (los efectos) es el detalle, y el cuadre
  entre los dos, `retenciones.v_cuadre_proveedor`. Cuatro cosas del origen que
  lo sostienen:
  - Las cuentas de retención son las que declara el proveedor en
    `prv.cueretide` (1:1), **nunca por prefijo**: 4038 y 4128 se escapaban.
  - Cada ejercicio cierra y reabre esas cuentas (~52 M € por lado): la clase
    del apunte separa `CIERRE`, `APERTURA`, `SALDO_INICIAL`, `ALTA` y `BAJA`, y
    el saldo es la suma de las tres últimas. La apertura de 2008 no tiene cierre
    previo —es la historia anterior a Sigrid, 642.775,50 €— y por eso es
    `SALDO_INICIAL` y cuenta; la regla es por cuenta, no por fecha.
  - Desde 2016 el alta no lleva centro de coste en el apunte: la obra sale de
    `raw.rac` (asiento → factura → sus efectos) y, si no, del propio efecto o
    del proveedor con una sola obra; siempre por `maestro.centros_coste`.
  - El vencimiento cuenta desde el **fin de obra** (decisión del humano del
    2026-09-22), nunca desde la factura: inicio de garantía
    (`obrctr.fecinigar` / `obr.garfecini`) o, si no hay, el último día del mes
    siguiente al último mes con importe planificado de la **última versión
    cuatrimestral** de la obra (F-110, decisión del humano del 2026-09-25:
    `mart.master_versiones_tipadas` dice qué versión y `stg.plan_mensual` qué
    meses); si tampoco, sin fecha. Más el plazo del cliente (`plaret` →
    `plagar` → 12). Las dos tablas son de la **misma noche**: en `run-all`,
    `build_stg` y `build_mart` corren antes que `build_retenciones`, sin
    declararlos en `depends_on` (si fallan, se usan las de la noche anterior).
    El último cierre con movimiento (`cierre.fact_cierre_mensual`) se publica
    solo como columna informativa, con **una noche de desfase** porque
    `build_cierre` corre después, y ya no interviene en el vencimiento.
    `retenciones.fin_obra` y `retenciones.v_retencion_contable_obra`.
- **El plan de cuentas son prefijos, dentro de la empresa (F-056).** Los grupos
  del plan son las filas de `con.tip = 16` (1 a 4 dígitos: grupo, subgrupo,
  cuenta, subcuenta; son la tabla `cug` de Sigrid, que no se ingiere) y las
  cuentas auxiliares, `cua` (`con.tip = 17`, 10 dígitos, las únicas con
  apuntes). El padre de un nodo es el grupo de su MISMA empresa cuyo código es
  su prefijo inmediato: el 100 % de los grupos lo tiene, y el padre declarado
  por Sigrid falta en el 22,5 % de los grupos. Sin `WITH RECURSIVE`: la
  profundidad la fija la longitud del código. No confundir con el plan
  ANALÍTICO de `maestro.cuentas_analiticas` (`caa`).
- **La clase del apunte contable (F-056) no está entera en `apu.cla`.** 3 es
  cierre, -1 apertura y 1 regularización, pero los cierres de 2020, las
  aperturas de 2021 y 290 regularizaciones vienen con 0; por eso
  `contabilidad.mayor.clase_asiento` combina `cla` con el concepto ('Asiento de
  cierre…', sin distinguir mayúsculas). Una apertura sin cierre de ESA cuenta
  el ejercicio anterior es `SALDO_INICIAL` (1.433 apuntes, 1.315 de 2008) y
  cuenta; `CIERRE` y `APERTURA` no se suman nunca (`R-SALDO-CONTABLE`). La
  fecha del mayor es `apu.fec` (la del asiento difiere en 297 apuntes de 2017)
  y la obra sale solo del centro del apunte por `maestro.centros_coste`.
- **EL COMPARATIVO TRAE OFERTAS INVENTADAS, Y SUS IMPORTES SON SIN IVA
  (F-038).** `compras.comparativos` y `compras.comparativo_ofertas`
  (`sql/compras/08_comparativos.sql`) leen `com`, `comprv`, `dco`, `dcopro`,
  `comlin` y `confir`. Cuatro cosas del origen que hay que saber:
  - **Ofertas ficticias.** Dentro de un comparativo hay ofertas de proveedores
    inventados (OBJETIVO, OFICINA TÉCNICA, PLANIFICACIÓN cuatrimestral, fase 0
    o ABC): 32.896 de 71.302, el 45 % del ofertado. Ficticia = CIF falso
    (`A99999999`, `A00000000`) o CIF vacío y nombre de familia; con CIF real,
    nunca. El CIF solo cubre el 30 %, así que la familia la da el **nombre de
    la oferta** (`dco.entres`) normalizado. La regla vive una vez en
    `domain/comparativos.py` y `compras.fn_familia_ficticia` lleva sus mismos
    literales (test). Las ficticias se publican, marcadas, y no entran nunca en
    las ofertas reales, la mínima, la máxima ni el `ahorro_concurso`.
  - **Sin IVA: `dco.totbas`, nunca `dco.totdoc`.** El proveedor es
    `dco.entide` (99,86 %), nunca `comprv.prvide` (18 %). `dcopro.tot = can ×
    pre`: el precio ya es neto y `dto` no se vuelve a aplicar.
  - **El adjudicado atípico es un corte, no una lista:** `comlin.can × pre`
    mayor que 10 veces la mayor oferta y que 100.000 € (52 comparativos, 602,5
    M€ de 1.246,2). Se marca (`adjudicado_atipico`) y no se borra; los
    umbrales viven en el dominio.
  - **El contrato sale de `comlin.ctride`** (18.633 comparativos), no de
    `ctr.comide` (56 %): un contrato viene de varios comparativos (3.960), y un
    comparativo con dos contratos hace fallar el build (guarda `RAISE
    EXCEPTION`, hoy 0 casos). La fecha de aprobación es la de la última firma
    solo cuando `con.est` es el `estfin` de su circuito.
  - **Fase 2 (`09_comparativos_detalle.sql`): `dcopro.dto` es TEXTO** con coma
    decimal y negativos (recargos), convertido por `compras.fn_porcentaje_dto`
    con el patrón del dominio. La base del coste objetivo lee
    `descompuestos.lineas` —el único SQL fuera de `sql/descompuestos/` que lo
    hace— y `build_compras` corre ANTES que `build_descompuestos`: usa el
    descompuesto de la noche anterior (la primera ABC y el master 0 están
    congelados). Regla D4: la primera ABC si casa; si no, la versión anterior
    más reciente que case; nunca una posterior; sin ABC, solo Estudios.
- **LA FOTO DIARIA DE ESTADOS DE F-067, RETIRADA POR F-132 (Fase B,
  2026-10-09).** F-067 montó una foto diaria de `con.est` de contratos y
  facturas (`sql/compras/11_historial_estados.sql`), guardada por tramos en las
  dos primeras tablas PERSISTENTES de `compras` (`historial_estados` e
  `historial_estados_fotos`), creyendo que Sigrid no fechaba el cambio de
  estado. F-085 lo desmintió el 2026-10-07 (la fecha está en `rac`, punto
  siguiente), F-132 publicó la antigüedad del estado desde ahí y, tras
  contrastar la foto con `rac` dos noches (492 cambios, 0 discrepancias), el
  humano decidió BORRARLA. Lo que queda en la arquitectura:
  - **`compras` vuelve a reconstruirse entero cada noche**: ya no existe
    `11_historial_estados.sql` ni su sub-paso (el hueco en la numeración se
    deja: renumerar cambiaría los nombres de `12` y `13`), y
    `python main.py reset-compras` borra todas sus vistas, tablas y funciones
    sin tirar el esquema (un test veta cualquier `DROP SCHEMA` de `compras` en
    el código del repositorio).
  - **Las dos tablas se borran UNA vez, a mano**, con
    `python main.py retirar-foto-estados --confirmar` (`retirar_foto_sql.py`, el
    único fichero de `etl_sigrid/` que las nombra, y un test lo veta): un
    `DROP TABLE IF EXISTS` de las dos en una transacción, sin `CASCADE` y con
    `lock_timeout`, y una relectura que lo comprueba. Sin `--confirmar` lee en
    READ ONLY y dice qué borraría. Va DESPUÉS de desplegar la imagen que ya no
    toma la foto: con la imagen vieja, la nocturna las volvería a crear.
  - **Lo que se pierde**: lo único que la foto veía y `rac` no, la noche en que
    se DESHIZO un paso (~9 al día). Hasta F-105 (`dbo.log`) no está en el
    datamart.
- **LO QUE F-067 DEJÓ Y NO ERA LA FOTO** sigue vigente:
  - **`con.tiemod` es una fecha de Delphi** (días desde 1899-12-30, hora en la
    parte decimal; `compras.fn_sigrid_tiempo`, con la época en
    `domain/fecha_delphi.py`). SQL Server la lee con época
    1900-01-01 y da dos días más. Se publica como
    `contratos.fecha_ultima_modificacion` y **no** es la fecha del cambio de
    estado: la firma no la mueve.
  - **El código 2 y la necesidad** (`cod2`, `dncide`, `dncproide`) van al final
    de las tres tablas de líneas; `compras.necesidades` es el DPC de la obra.
    En `descompuestos`, `necesidad_id` entra solo en dos VISTAS, por
    subconsulta a `raw.dncpro`: tocar `lineas` o el sello retrocearía el master.
- **QUIÉN APROBÓ QUÉ Y CUÁNDO SALE DE `rac`, EL REGISTRO DE PROCESOS (F-085).**
  `sql/compras/12_documento_procesos.sql` publica `compras.documento_procesos`:
  una fila por paso de factura, contrato, comparativo y obra (~1,01 M), con el
  proceso, los estados de origen y destino traducidos por la pareja tipo-estado
  (`fn_estado_documento`), el login y el nombre (`raw.usu`, casado en mayúsculas
  y sin espacios), la fecha y la hora, el `orden` en su documento, `es_ultimo`,
  `encaja_con_anterior` y los días desde el paso anterior. Se reconstruye cada
  noche. La regla (familias, orden, hora válida,
  login) vive una vez en `domain/documento_procesos.py` y el SQL lleva sus
  literales (test). Es historia NETA: «Deshacer proceso» borra el paso.
  - **Los datos personales se quedan en `personal`**: `compras` publica login y
    nombre; el empleado y el DNI van en `personal.usuarios_sigrid`
    (`personal/06_usuarios_sigrid.sql`), bajo el GRANT por esquema de F-057.
  - **`raw.usu` no trae ninguna credencial**: la lista de las seis vive en el
    dominio (`COLUMNAS_CREDENCIALES_USU`) y un test falla si alguna deja de
    estar en `exclude_columns`. Ni `dbo.log` (F-105), ni `conpro`, ni `rol`
    entran.
- **LA ANTIGÜEDAD DEL ESTADO SALE DE `rac` (F-132).**
  `sql/compras/13_estado_documentos.sql` crea `compras.v_estado_documentos`:
  una fila por contrato, factura y comparativo con su estado (el de la
  cabecera) y desde cuándo está en él, del ÚLTIMO paso de
  `compras.documento_procesos`. `origen_fecha` dice de dónde sale la fecha:
  PASO (al segundo, el 99,4 %), ALTA (sin pasos y en un estado inicial: el día
  de alta) o FUERA_DE_PROCESO (sin fecha, con la cota `cambio_posterior_a`).
  Historia NETA: un paso deshecho no se fecha. Va DETRÁS de `12` en
  `build_compras` porque el `DROP ... CASCADE` de `12` tira la vista cada noche. La regla
  (familias, estados iniciales, orígenes) vive en `domain/estado_documentos.py`
  y el SQL lleva sus literales (test). No lee la foto de F-067: durante la
  Fase A se contrastó con ella (`python main.py contraste-estados`, de solo
  lectura y ya retirado) y la Fase B la borró (punto de la foto, arriba).
- **EL ÍNDICE DE DOCUMENTOS ADJUNTOS SALE DE `rcg` Y `gra` (F-090).**
  `sql/compras/14_documento_adjuntos.sql`, el último sub-paso de
  `build_compras`, publica `compras.documento_adjuntos`: una fila por fichero
  adjunto (la pestaña «Gráficos asociados» de Sigrid) a una factura, contrato,
  comparativo, oferta o albarán (~199.042), con el nombre del fichero, su clase
  por EXTENSIÓN, la fecha de alta, el login de quien lo subió y
  `cod_repositorio`. Las familias y las extensiones viven una vez en
  `domain/documento_adjuntos.py` y el SQL y los filtros de ingesta llevan sus
  literales (test). Una guarda falla si más del 1 % de los enlaces no encuentra
  su gráfico (ingesta a medias). No toca `compras.facturas` ni ningún otro
  objeto: se cruza con ellos por `documento_id` y `comparativo_id`.
  - **El fichero NO se replica**: vive en la base documental de Sigrid,
    `ruesma_rep` (~81 GB solo en compras, más que el disco de 64 GB), y lo
    sirve `sigrid-api` con `documents/read` y la pareja
    (`empresa_repositorio`, `cod_repositorio`), siempre con
    `filename_columns: ["cod"]`: sin ello responde HTTP 500 a los nombres
    documentales no ASCII (5,7 % de los enlaces, medido el 2026-10-15). Este
    ETL no lee `ruesma_rep` ni importa librerías de documentos o de IA (test de
    F-139, con la única excepción de `openpyxl` en el paso de F-004).
  - **El límite (F-139)**: el datamart publica el ÍNDICE; abrir el ORIGINAL
    para una IA es `abrir_adjunto`, de `mcp-bbdd` (su F-023, desplegada el
    2026-10-17), que lo pide a `sigrid-api`. Desde su F-028 (nuestra F-142,
    desplegada el 2026-10-21) ningún fichero viaja dentro de la respuesta: a la
    IA le llega texto por página (PDF, ofimática que Microsoft Graph convierte a
    PDF y, de lo que Graph no convierte, texto extraído en el servidor), las
    páginas escaneadas y las imágenes como imagen, con el parámetro `paginas`
    (por defecto las 10 primeras), y el documento queda 24 h en un sitio de
    SharePoint propio con un enlace solo para quien lo pidió. Desde su
    F-025 lo pide por la pareja: con una empresa distinta de la 1 y un 400, una
    sola segunda petición con la 1 y el mismo `cod`; con la empresa nula, la
    única petición va directamente con la 1; con la empresa 1, el 400 es
    `SIN_BINARIO`, sin segunda petición. `empresa_repositorio` tiene que
    llegarle ENTERA (F-145). Abrirlo desde un portal, trabajo de `portal`. El contrato
    (H1-H13) está en `azure-apps/datamart_seg_anual.md`.
  - **Quién abre cada fichero**: quien pueda leer la tabla de origen de su
    familia (FACTURA `facturas`, CONTRATO `contratos`, COMPARATIVO
    `comparativos`, OFERTA `comparativo_ofertas`, ALBARAN `albaranes`, todas en
    `compras`); lo decide PostgreSQL con el login del perfil. La misma regla
    vale para las filas del índice. Hoy estándar y total leen las cinco y no
    cambia nada; la aplicará el perfil restringido (F-141). Renombrar una de
    esas tablas o claves rompe el contrato (lo vigila un test).
- **LAS ALARMAS Y LA MARCA «LIQUIDATORIA» SALEN DE `conala` (F-138).** En
  Sigrid la factura liquidatoria no es un campo: es una ALARMA de texto libre
  pegada al documento. `sql/compras/15_alarmas_liquidatoria.sql`, el último
  sub-paso de `build_compras` y una sola transacción, publica en DOS esquemas
  (patrón de F-135 y F-037): `compras_restringida.documento_alarmas`, todas las
  alarmas (~45.750) con `restringido` y `motivo_restriccion`, y la general
  `compras.documento_alarmas`, sin las de recursos (33) y partes de trabajo
  (35), que nombran trabajadores y bajas (D9: solo el perfil total). Sobre la
  general, `compras.documento_liquidatoria` (la marca de cada factura,
  albarán, proforma y nota: la clase de mayor precedencia entre sus alarmas,
  NEGADA > LIQUIDATORIA > CARTA_LIQUIDACION > DUDOSA > REMITE, y el memo
  aparte), `compras.contrato_liquidacion` (una fila por contrato: ¿se han
  terminado sus facturas?, con la cadena factura -> contrato de
  `v_pbi_contrato_consumo`) y `compras.facturas_tras_liquidacion` (el aviso de
  las que llegan después). La regla de texto (traducción, patrones sin ``,
  precedencia) vive una vez en `domain/liquidatoria.py` y el SQL lleva sus
  literales (test); dos guardas `DO` hacen fallar el paso si `raw.conala` no
  trae alarmas de factura o si la general lleva una alarma restringida. No toca
  `compras.facturas` ni `compras.albaranes` (D7).
- **LA CABECERA DE FACTURA Y ALBARÁN: `totdoc`, `tot`, `totpag` Y `reccla`
  (F-128).** `dcf.totdoc` (y `dca.totdoc`) es el total CON IVA y ANTES de
  retenciones (= `totbas + totiva`); `tot` y `totpag` son el mismo número en el
  100 % (Sigrid los documenta distintos): lo que se paga. Se publica `totpag`
  (`total_a_pagar`). La retención es `totdoc − totpag` y es exactamente la suma
  de `cuo` de los recargos (`dcfrec`, `dcarec`) de clase `reccla` 3 (fiscal), 4
  y 5 (garantía sobre total y sobre base); 0 = recargo (`imprec`), 1 =
  descuento (`impdes`). **`RETESP` es la trampa**: un concepto de garantía dado
  de alta como DESCUENTO (clase 1): baja la base y no entra en `totdoc − totpag`,
  aunque su asiento vaya a la cuenta de retención. Por decisión del humano
  (D2-B) NO es garantía: las funciones `fn_es_retencion_garantia` miran solo
  `reccla` (4 y 5). La retención del albarán y la de su factura son la misma y
  no se suman. El cuadre por factura (`retenciones.retencion_factura`) lee solo
  `raw` y `retenciones`. La CUENTA BANCARIA del proveedor de cada documento
  (`ban*`) va a `compras_restringida.documento_cuenta_bancaria` (solo perfil
  total, D4-B): `compras_restringida` guarda ya alarmas y cuentas.

## Acceso a datos

- Sigrid solo vía sigrid-api (`POST /api/sql/read`), nunca conexión directa.
  Tope duro 10.000 filas/petición; timeout de red efectivo 230 s.
- Solo LECTURA de Sigrid desde este proyecto. Las escrituras del datamart van
  al PostgreSQL propio (local en dev, Flexible Server en Azure).
- **Los tres Excels auxiliares de Negocio (F-004)** se leen de una ruta del
  sistema de ficheros **o** de Azure Blob Storage, y lo decide la FORMA del
  valor de `AUX_EXCEL_*`: una URI
  `https://<cuenta>.blob.core.windows.net/<contenedor>/<blob>` va a Blob
  Storage; cualquier otra cosa, al disco. No hay variable de modo que mantener
  coherente. La autenticación es `DefaultAzureCredential` —identidad
  gestionada en el job, sesión de `az` en el puesto—, con el rol
  `Storage Blob Data Reader` sobre la cuenta: **ni cadenas de conexión, ni
  claves, ni SAS** (una URI con query string se rechaza al arrancar el paso).
  El contenido se obtiene **en memoria**, sin ficheros temporales, porque el
  contenedor no tiene dónde escribirlos. Puerto y adaptadores en el paquete,
  bajo `infrastructure/excel/`; el step `load_excel_aux` no sabe de
  Azure. Hoy **lee y valida, no carga** a `aux.*`: las tablas destino y el
  esquema de los libros no están definidos todavía.

### Qué se copia de Sigrid: 80 tablas, y qué NO está ahí (F-066, F-074, F-080, F-102, F-107, F-095, F-085, F-090, F-138, F-140, F-150)

`config/tables_sigrid.yaml` declara **80 tablas**: eran 31, F-066 las dejó en 56
el 2026-09-06, F-074 sumó nueve más el 2026-09-09, F-080 otras tres el
2026-09-11 —`auxnap`, `auxban` y `rpa`, el bloque de pago del efecto y las
remesas—, F-102 una el 2026-09-23 —`auxemp`, las 38 empresas del grupo, que da
nombre a la empresa de cada obra y de cada recurso— y F-107 otra el 2026-09-24
—`caa`, las 184.234 cuentas analíticas, que traduce la contrapartida del recurso
y la cuenta de su ficha de tipos de hora; leerla entera cuesta 4,3 s—, F-095 otra
el 2026-09-24 —`rac`, el registro de procesos de Sigrid y el único enlace
documento -> asiento, que entró filtrada a `asiide <> 0` (755.086 de 2.505.089
filas) y que **F-085 trae entera desde el 2026-10-07** (2.517.791 filas, sin su
texto libre `tex`: los pasos de comprobar y aprobar son el historial de procesos
que publica `compras.documento_procesos`)— y F-085 la última, `usu`, los 233
usuarios de Sigrid **sin credenciales, sin DNI y sin correo** (diez columnas
excluidas; la lista de credenciales vive una vez en
`domain/documento_procesos.py` y un test falla si alguna entra), que traduce el
login a persona en `compras.documento_procesos` (nombre) y en
`personal.usuarios_sigrid` (empleado y DNI). F-090 suma las dos últimas el
2026-10-09, `rcg` y `gra`, los «Gráficos asociados» de Sigrid (el enlace
documento -> fichero y el fichero), **filtradas en origen** a las cinco
familias de compras (199.042 de 289.451 enlaces: fuera nóminas, DNI y demás
adjuntos de personal) y **sin binario** (`gra` sin `ima`, `pul`, `tex` ni
`cam`); `auxgra` no entra. F-138 suma las dos últimas el 2026-10-14,
`conala` (las alarmas de los documentos, 45.747 filas en ~2 s) y `auxala` (sus
4 tipos): `conala` **filtrada en origen con una lista EXPLÍCITA de 17
familias** (falla cerrada ante una familia nueva) que deja fuera la 43,
empleados. Además de recuperar la columna `con.tex` (el memo del documento,
informado en el 65,5 % de las facturas; traerlo cuesta +26 % de tiempo de
lectura sobre `con`, medio minuto de la ventana nocturna). F-140 suma las dos
últimas el 2026-10-25, `auxcob` (las 52 formas de COBRO, a donde apunta
`obrctr.pagide`) y `auxefc` (sus 8 medios): la pareja de `auxpag`/`auxefp` en el
lado del cliente, enteras y con `tiemod`, para leer la fórmula de plazo del
contrato con el cliente (`tesoreria.plazos_forma_pago`). F-150 suma las dos
últimas el 2026-10-28, `iva` (el catálogo de tipos de IVA, entero) y `dvf` (las
facturas de venta), de la que **solo se traen 9 de sus 151 columnas** —la
cabecera— con la lista blanca `include_columns` del ingestor: lo facturado
al cliente que necesita el hueco de facturación de H26.
Las 25 que entraron el primer día vienen en tres grupos, y ninguna se supuso: todo lo
que sigue se midió contra Sigrid ese día por `sigrid-api` en solo lectura.

- **Personal** — `res` (2.610 recursos), `emp` (1.352 empleados), `hmo` (6.850
  cabeceras de parte) y **`hmores` (328.760 líneas)**. Las horas están en
  `hmores`, no en `hmo`: en la cabecera el recurso viene informado en 6 filas de
  6.850. Es la corrección que hace posible «horas por obra».
- **Contabilidad** — `cua` (34.139 cuentas), `asi` (783.386 asientos), **`apu`
  (2.154.543 apuntes)** y `apa` (709.403 líneas de desglose). `apu` es la tabla
  más grande del datamart, por encima de `con`.
- **Compras y proveedor** — la cadena entera necesidad (`dnc`, `dncpro`) →
  comparativo (ya estaba) → oferta (`dco`, `dcopro`, `dcorec`) → contrato (ya
  estaba), más condiciones (`ctrrec`, `dcfrec`, `dcarec`, `auxpag`, `auxefp`),
  firmas (`confir`, `deffir`), estados (`conest`) y proveedor (`conact`,
  `auxpronat`, `prvcer`, `prvobrpag`).

**Las nueve de F-074** salen del censo de F-072, que encontró tablas del origen
sin las cuales la mitad de lo que ese censo propone construir no se puede
escribir. Medidas contra Sigrid el 2026-09-09, ninguna supuesta:

- **Catálogos que traducen** — `auxhor` (60 conceptos de hora; sin ella `hmores`
  es ilegible, porque el catálogo mezcla horas de verdad con «mes vehículo» y
  «consumos teléfono»), `auxrestip` (37 tipos de recurso: de las 2.610 filas de
  `res` solo 1.353 son personas), `auxdpt` (7 departamentos) y `cet` (40 centros
  de trabajo). **La columna `cod` que el documento de Sigrid atribuye a `cet` no
  existe en la base**: cualquier unión con ella va por `ide`.
- **Maestro y nómina** — `pro` (55.179 artículos: hoy el producto **no tiene
  nombre** en el datamart pese a que lo referencian `dcopro` al 99,9 % y
  `dncpro` al 95,4 %), `reshor` (8.949 filas de precio de coste por recurso y
  tipo de hora, el multiplicador que a F-061 le falta para pasar de horas a
  euros) y `emphis` (1.633 filas, 1.017 empleados, de 1989 a 2026: el único
  sitio de Sigrid con histórico laboral de verdad).
- **Trazabilidad línea a línea** — `dcaprodes` (850.985 filas, albarán →
  factura) y `ctrprodes` (424.475, contrato → albarán o factura). Son el 95 % de
  lo que esta tanda añade, y sustituyen la aproximación por `linoriide` que hoy
  hace el esquema `compras`.

**Lo que cuesta**: 1.341.365 filas nuevas por noche, unos **155 MB** estimados
sobre los 25 GB que ocupa hoy la base en un disco de 64 GB (+0,6 %), y unos
**3 a 6 minutos** más de ventana sobre las 3 h 45 actuales, medidos a 10.000
filas de `dcaprodes` en 0,7 s y de `ctrprodes` en 0,5 s por la pasarela. Cabe,
pero el margen antes de la jornada ya era mínimo.

**`reshor` y `emphis` son datos de nómina** y quedan fuera del alcance del rol
del MCP por el mecanismo de F-068, como `emp` y `res`. De `cet` se excluyen en
origen el DNI y el nombre del representante legal.

**F-074 arregló además dos declaraciones falsas del mismo fichero**: `com`,
`comlin` y `comprv` declaraban `incremental_column: tiemod` y **esa columna no
existe en Sigrid** (error 42S22 contra `INFORMATION_SCHEMA`), con
`_source_tiemod` a NULL en sus 287.673 filas; y `prvcer` excluía `tex`, que es
el único campo que dice de qué es cada certificado porque la tabla no tiene
campo de tipo. `obrprv` **se queda** pese a tener 0 filas: dos SQL de `maestro/`
construyen el vínculo obra-proveedor por otra vía precisamente porque está
vacía, y `check-raw-recuentos` es lo único que diría que ha dejado de estarlo.

**`incremental_column` no es un interruptor de modo de carga**, y confundirlo lo
ha sido dos veces: lo único que decide es si `copy_rows` rellena
`_source_tiemod`. Quién decide cómo se carga es el `CMD` del `Dockerfile`, que
arranca `run-all --full`, o sea `TRUNCATE` y recarga entera de **todas** las
tablas cada noche. Por eso «esta tabla no tiene `tiemod`» significa «su fila de
`raw` no lleva sello de origen», y no «lo modificado no vuelve a bajar»: eso
solo es cierto lanzando `ingest` a mano sin `--full`.

**El mapa de `con.tip`**, verificado por recuento y necesario para leer `raw`:
5 proveedor, 12 oferta de compra, 14 albarán, 15 factura, 16 cuenta del plan,
20 asiento, 33 recurso, 42 obra, 43 empleado, 44 contrato, 46 comparativo.

**Ninguna de las cuatro tablas de contabilidad tiene columna de última
modificación**, así que la carga incremental por columna de corte no existe para
ellas: van enteras. Da igual en la práctica —la nocturna es `--full`— pero
importa si alguien intenta acortarla. `apu` se trae entera y sin filtro:
partirla por empresa ahorra ≤ 10 % y exige subconsulta, y por ejercicio, ≤ 15 %.

**`raw.emp` y `raw.res` llevan datos personales completos**, por decisión
explícita del humano del 2026-09-06 frente a la propuesta de excluir 72
columnas: DNI, número de la Seguridad Social, cuenta bancaria, domicilio,
contacto, fecha de nacimiento y credenciales de acceso. Solo se excluye lo
binario y el texto ilimitado, que es criterio técnico. **La ficha de cada una
declara qué contiene**.

**El MCP ya no las lee, y eso es TEMPORAL (F-068, 2026-09-07).** Hasta esa
fecha `mcp_sigrid_dm_ro` alcanzaba `raw` entero y las dos tablas eran legibles
por cualquier cuenta del tenant. El humano decidió quitarle el permiso —«de
momento quita el permiso. Cuando pongamos límites o guardarraíles por usuario,
habrá que volver a ponerlo para algunos usuarios»—, así que **no es una
prohibición permanente**: es un tapón mientras el MCP no distinga QUIÉN
pregunta, y su reversión ya está decidida para cuando exista ese control.

Cómo se sostiene, que es la parte que no se ve: `GRANT SELECT ON ALL TABLES IN
SCHEMA` no sabe saltarse una tabla, y `apply_grants` lo reaplica cada noche. Por
eso la revocación **no es una orden suelta contra la base** —esa duraría hasta
la nocturna siguiente— sino parte del propio paso: concede el esquema, revoca
las tablas de `PG_EXCLUDED_TABLES` y cambia el `ALTER DEFAULT PRIVILEGES` de
`raw` de `GRANT` a `REVOKE`, para que una tabla recreada tampoco nazca legible.
La lista es `DEFAULT_EXCLUDED_TABLES` en `config/settings.py`, y ahí está
escrita la condición para levantarla.

**Desde F-135 (2026-10-11) `raw` entero queda fuera del rol general**, vetado y
no solo sin conceder: además de esas cuatro tablas trae el mayor, 37.048
efectos de pago de nómina de 1.015 trabajadores con su cuenta bancaria
(`raw.pag`), los repartos analíticos de los apuntes de personal (`raw.apa`), sus
cabeceras (`raw.con`, `raw.asi`), `raw.rac` y `raw.hmores`. Lo sostiene
`apply_grants` cada noche con `PG_VETOED_SCHEMAS` (ver «El datamart en Azure»).
`PG_EXCLUDED_TABLES` se conserva tal cual: vuelve a valer el día que `raw` se
devuelva, y para eso hay que deshacer antes el veto.

**Lo que Sigrid NO guarda**, medido dos veces y escrito aquí para que nadie
vuelva a buscarlo:

- **El histórico de cambios de estado SÍ está, en `rac`** (corregido por F-085
  el 2026-10-07; aquí se decía lo contrario). La tabla de auditoría (`concam`)
  registra 1,5 M de cambios de forma de pago y de fecha de factura desde 2017 y
  **ni uno solo del campo de estado**, y por eso se concluyó que no existía;
  pero `rac`, el registro de procesos, guarda cada paso con su estado de origen
  y de destino, su usuario, su fecha y su hora desde 2008. Lo publica
  `compras.documento_procesos`, con los estados traducidos **por tipo de
  documento** (`conest`: la misma cifra significa cosas distintas en un
  contrato y en una factura). Es la historia NETA: «Deshacer proceso» borra el
  paso; la bruta está en `dbo.log` (F-105). Desde F-132 la antigüedad del
  estado sale de aquí (`compras.v_estado_documentos`), y la foto diaria de
  F-067 se retiró (F-132, Fase B, 2026-10-09).
- **Los contratos no pasan por el circuito de firma** (`confir`): sus 69.993
  firmas son de comparativos, facturas y obras, y las de factura vienen sin
  fecha. `PFfir` y `logfirdoc`, donde el backlog esperaba encontrarlo, están
  vacías, como otras 17 candidatas que por eso no se ingieren.
- **La penalización del contrato no existe como campo**, y la actividad del
  proveedor no es `act` (vacía) sino `conact` → `auxpronat`.

`python main.py check-raw-recuentos` compara, tabla a tabla y con el mismo
filtro, el `COUNT(*)` de Sigrid con el de `raw`. Es de solo lectura, va fuera de
`run-all` y sale con código 1 también cuando Sigrid **no pudo** contestar: «no
he podido mirar» no es «está bien».

**La tolerancia tiene dirección** (corregido el 2026-09-08, tras la primera
medición real). Exigir igualdad exacta era inalcanzable: Sigrid es un ERP vivo
y el datamart una foto, así que cinco horas después de la ingesta 25 de 56
tablas tenían filas de más —4.883 sobre 25.287.500, un 0,0193 %— y ninguna de
menos. Ahora las filas **de más** en Sigrid son deriva normal y se aceptan
mientras no pasen de `--tolerancia-pct` (0,05 % por defecto, relativo a cada
tabla); las filas de **menos** son alarma inmediata, sea de una fila, porque
eso no lo hace el paso del tiempo sino un borrado en origen, una ingesta
duplicada o una carga equivocada. `AUSENTE EN RAW` y `SIN MEDIR` siguen siendo
fallo con cualquier tolerancia.

### El datamart en Azure (F-005)

- **No hay servidor propio.** La base `sigrid_dm` vive dentro de
  `psql-albaranes-rs9k2.postgres.database.azure.com` (`rg-albaranes-dev`,
  PostgreSQL 16, `Standard_B1ms`, **64 GB** desde el 2026-08-29; antes 32), que
  ya sirve a `albaranes`, `partes`, `dedicacion`, `postventa` y `facturas`,
  **todas en uso** —la última apareció sola el 2026-09-07 y tumbó una
  nocturna—. Base propia y no esquema compartido: PostgreSQL
  no permite consultas entre bases, y esa es la frontera que impide que el rol
  de lectura vea `albaranes`.
- **Siete roles.** `sigrid_dm_etl` (grupo `NOLOGIN`) es el propietario de todo;
  `sigrid_dm_app` (login, contraseña en Key Vault) es el que usa el ETL y es
  miembro del grupo; `mcp_sigrid_dm_ro` (login) es el rol GENERAL (estándar) de
  solo lectura, el del MCP y hoy también el de Power BI; desde F-135
  `sigrid_dm_autorizado_ro` (grupo `NOLOGIN`) es el rol AUTORIZADO que lee la
  contabilidad completa (F-141 lo renombró: su nombre anterior decía
  «restringido» y es el que ve MÁS); desde F-136 `mcp_sigrid_dm_total` (login,
  contraseña SOLO en `kv-mcp-bbdd-dev/pg-password-total`) es el acceso TOTAL del
  MCP: miembro de los dos anteriores (`WITH INHERIT TRUE, SET FALSE`,
  punto 5 quater de `02_roles.sql`), lee lo de ambos y NUNCA `raw` (decisión del humano
  del 2026-10-12: «siempre fuera»), sin ningún GRANT propio; y desde F-141 el
  perfil RESTRINGIDO (administrativos), que ve MENOS que el estándar: el grupo
  `sigrid_dm_perfil_restringido_ro` (`NOLOGIN`, lleva los permisos) y su login
  `mcp_sigrid_dm_restringido` (contraseña SOLO en
  `kv-mcp-bbdd-dev/pg-password-restringido`), miembro solo del grupo (punto 5
  quinquies). Autenticación por contraseña: habilitar Entra es una operación de
  servidor y se descartó para no tocar las otras dos bases. El modo
  `PG_AUTH_MODE=entra` existe en el código, probado, pero inactivo.
- **`PG_SET_ROLE=sigrid_dm_etl`** en cada sesión: los objetos deben tener
  siempre el mismo dueño, porque las vistas se recrean en cada ejecución y
  quien no es dueño no puede hacer `DROP`.
- **`PG_AUTO_CREATE_DB=false`** contra Azure: el ETL no ejecuta
  `CREATE DATABASE` ni abre la base admin en un servidor de producción
  compartido. La base la crea el humano con `infra/sql/`.
- **Los permisos de lectura se reaplican en cada ejecución** (paso
  `apply_grants` y comando `apply-grants`): siete ficheros SQL recrean vistas
  con `DROP VIEW ... CASCADE` y un `DROP` se lleva los `GRANT`.
- **Qué lee cada rol, desde F-135.** El GENERAL (`mcp_sigrid_dm_ro`) lee los
  esquemas de `PG_CONSUMPTION_SCHEMAS` —`mart`, `cierre`, `compras`,
  `maestro`, `retenciones`, `personal`, `contabilidad` (la general),
  `tesoreria` (la general, F-037), `descompuestos`, `stg`, `aux` y `_meta`— y
  NO lee los de `PG_VETOED_SCHEMAS`: `contabilidad_restringida`,
  `tesoreria_restringida`, `compras_restringida` (F-138) y `raw`. El
  AUTORIZADO (`sigrid_dm_autorizado_ro`) lee `contabilidad_restringida`,
  `tesoreria_restringida` y `compras_restringida` (`PG_RESTRICTED_SCHEMAS`);
  el total, las tres por pertenencia. El dueño y el administrador lo leen todo, como
  siempre. `apply_grants`, cada noche y en este orden: (1) si un esquema está a
  la vez en consumo y en vetados —un `.env` viejo que aún lista `raw`— o el del
  autorizado no está vetado, FAILED sin ejecutar nada; (2) concede al general,
  y DETRÁS le veta los esquemas vetados (tablas, USAGE y privilegio por
  defecto); (3) concede al autorizado si existe (si no, avisa y sigue); (4)
  pregunta al catálogo (`has_schema_privilege`, `has_table_privilege`) si el
  general aún lee algo vetado o excluido, y si lo lee, FAILED con la lista: una
  concesión que la nocturna no puede revocar (a PUBLIC, o de otro concedente)
  no pasa inadvertida. `infra/sql/02_roles.sql` hace lo mismo al provisionar,
  como administrador y como `sigrid_dm_etl` (punto 5 ter).
- **El login total en `apply_grants`, desde F-136.** Lo nombra `PG_TOTAL_ROLE`
  (por defecto `mcp_sigrid_dm_total`; el job no lleva variables nuevas) y lo que
  no lee nunca, `PG_TOTAL_VETOED_SCHEMAS` (`raw`). Antes de abrir conexión,
  FAILED si el total coincide con otro rol o si un esquema suyo vetado no está
  vetado al general, o está en lo restringido o en el consumo (lo heredaría por
  pertenencia). Con conexión, DESPUÉS de las concesiones: no le concede nada,
  le veta `raw` (tablas, USAGE y privilegio por defecto), pregunta al catálogo
  si lee algo de `raw` o de `PG_EXCLUDED_TABLES` (FAILED con la lista, en un
  único mensaje con la del general si los dos leen algo; `verificacion_total`)
  y si le falta USAGE en algún esquema de consumo o restringido (solo aviso,
  `acceso_total`: leer de menos no expone nada). Si el total no existe, avisa y
  sigue. La nocturna no puede darle las pertenencias (no tiene ADMIN OPTION
  sobre los grupos): eso es `02_roles.sql`, que corre el humano (runbook §12).
- **El perfil restringido en `apply_grants`, desde F-141.** Regla del humano:
  «ven como el estándar, menos el mayor, menos el mayor analítico, menos la
  cartera de cobros (pero sí a retenciones)» y «personal también quítalo, y
  saldos cuenta también». Lo nombran `PG_PERFIL_RESTRINGIDO_GROUP` y
  `PG_PERFIL_RESTRINGIDO_LOGIN`; lee `PG_PERFIL_RESTRINGIDO_SCHEMAS` (lista
  EXPLÍCITA: el consumo menos `tesoreria`, `personal` y, desde F-146,
  `contabilidad` entera) menos `PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES` (vacía
  desde F-146: hasta entonces, `contabilidad.mayor` y
  `contabilidad.saldos_cuenta_mes`); el job no lleva variables nuevas. **F-146
  (decisión del humano del 2026-10-21): nada de contabilidad.** Con el esquema
  en la lista le quedaban el plan de cuentas y los recuentos de apuntes de
  personal, y toda tabla nueva de `contabilidad` le llegaría sola; fuera de la
  lista, se le veta entera desde el catálogo como `tesoreria` y `personal`, sin
  código nuevo en el paso. La lista de excluidas no puede quedarse «como red»
  con las dos de contabilidad: la guarda de objetos excluidos rechaza los de un
  esquema que no se le concede. `retenciones` sigue siendo suyo. Antes de
  abrir conexión, FAILED si `PG_RESTRICTED_ROLE` trae el nombre retirado del
  autorizado, si el grupo o el login coinciden con otro rol, si sus esquemas no
  son del consumo o están vetados o restringidos, si falta `_meta`, si un objeto
  excluido está mal escrito o si leería `compras.documento_adjuntos` sin sus
  documentos de origen (F-139, D1). Su bloque es el ÚLTIMO y no cambia nada de lo
  anterior: le concede lo suyo con el privilegio por defecto SIEMPRE en REVOKE
  (lo que nazca no lo lee hasta que la nocturna lo ha mirado), le veta todo
  esquema del CATÁLOGO que no es suyo (hoy `contabilidad`, `tesoreria`,
  `personal`, `raw` y las `*_restringida`; mañana, cualquiera que nadie haya
  listado) y busca en el
  catálogo, vista sobre vista (`pg_rewrite` + `pg_depend`), las vistas suyas que
  leen lo que no ve: una vista se ejecuta con los permisos de su dueño, y es la
  trampa de dar esquemas sueltos. Salvo `raw` (lo leen las vistas curadas) y las
  tres vistas de pago de `compras` (`vencimientos`, `v_facturas_pago`,
  `v_control_forma_pago`: «compras debe poder verse», excepción NOMINAL en
  `EXCEPCIONES_FILTRACION_RESTRINGIDO`, con un test que falla si sobra), cada una
  se le REVOCA y el paso termina en FAILED (`filtraciones_restringido`); igual
  con un objeto con «mayor» en el nombre sin excluir (`vigilados_restringido`).
  Después pregunta al catálogo si el grupo o el login leen algo de lo que no
  deben (`verificacion_restringido`) y si el login es miembro de algo más que su
  grupo, o el grupo de algo (`pertenencias_restringido`): FAILED en el mismo
  mensaje que el estándar y el total. Grupo vacío: nada; grupo o login ausentes,
  o una excepción que ya no lee la cartera (`excepciones_sobrantes`): aviso.
  `02_roles.sql` hace lo mismo al provisionar (punto 5 quinquies: la mitad del
  dueño, como `sigrid_dm_etl`, y la del administrador, con la pertenencia).
  Sin `personal` siguen visibles los logins y nombres de usuarios de Sigrid de
  `compras.documento_procesos`, `documento_alarmas.creada_por` y
  `documento_adjuntos.subido_por`: el humano lo aceptó («deja visible compras»).
  La guarda solo ve vistas y nombres: una TABLA nueva con datos del mayor o de
  la cartera en un esquema del perfil la vería; la regla `R-PERFILES`
  del diccionario y este aviso son la mitigación.
- **El mayor analítico y F-127.** Hoy no está publicado (es `raw.apa`, 709.403
  filas). Si F-127 lo publica en `contabilidad`, el perfil restringido no lo ve
  (F-146: esquema vetado entero). Si lo publica en un esquema del perfil, su spec
  TIENE que añadirlo a `PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES` si su nombre no
  lleva «mayor»: con «mayor» en el nombre y sin excluir, la nocturna se lo
  revoca al perfil restringido y falla, pero con otro nombre nadie lo vería.
- **Lo que NO es de este repositorio** (F-135, F-136): que el MCP conecte con
  el login total según quién pregunta (por oid, fuera de todo repositorio) y que
  su lista blanca admita `contabilidad_restringida`, `tesoreria_restringida` y
  `compras_restringida` (F-138),
  y `tesoreria` en las dos conexiones (`mcp-bbdd`, su F-008, con el contrato en
  `azure-apps/datamart_seg_anual.md`): hasta entonces el MCP no ve la cartera; y que Power BI tenga rol
  propio (F-087). Hasta entonces el login total existe pero ningún cliente lo
  usa: nadie lee lo que no debía, y quien debe verlo lo tiene en Sigrid. Lo
  mismo con el login del perfil restringido (F-141): elegirlo según quién
  pregunta es de `mcp-bbdd`, con el contrato E1-E8 en
  `azure-apps/datamart_seg_anual.md` (por defecto restringido, nunca hacia
  arriba). Power BI no entra en F-141.
- **La recuperación es volver a ejecutar el ETL, no restaurar**: el PITR es de
  servidor entero y arrastraría `albaranes` y `partes` al pasado.
- Procedimiento completo: `docs/runbook_postgres_azure.md`.

### El build de `stg.plan_mensual` va por tramos (F-019)

El 2026-08-09 ese build llenó el disco del servidor compartido: la explosión
del `planif` con `CROSS JOIN LATERAL unnest(...)` sobre 13,76 M filas derramó
16+ GB de temporales, la ocupación llegó al 93,4 % y Azure dejó el servidor en
solo-lectura diez minutos, con `albaranes` y `partes` en producción. En local
no pasaba porque sobra RAM.

Desde F-019, el sub-paso `build_plan_mensual` **no se ejecuta de una pasada**:

- **Corte por obra.** Ninguna ventana del SQL cruza obras (particionan por
  `presupuesto_id` o por la terna obra-partida-ámbito), así que ejecutar el
  mismo statement con un filtro de obras disjunto y completo da exactamente
  las mismas filas. La equivalencia es estructural, no casual.
- **Quién hace qué.** `domain/tramos.py` planifica (función pura: pesos por
  obra + tope), `build_stg_step` orquesta y `postgres_client` mide y ejecuta.
  El fichero SQL lleva un marcador que el step sustituye por las obras del
  tramo, **en las dos ramas** (master amb 8/11 y reales amb 3/7); filtrar solo
  una duplicaría la otra. **El vaciado de la tabla lo hacía el step una vez,
  antes del primer tramo; desde F-025 ya no existe** —ver la sección siguiente:
  cada tramo borra las obras que va a reinsertar, en su misma transacción—.
- **Una transacción por tramo**, para que el pico de temporales de un tramo no
  se apile con el del siguiente.
- **Puerta de disco antes de CADA tramo**: se mide la ocupación del servidor
  (suma de `pg_database_size` de todas las bases) y, si supera el límite, el
  build **para** y marca FAILED. Si la medición falla, también para: seguir a
  ciegas es lo que provocó el incidente. **Hasta F-025 el aborto además vaciaba
  la tabla**; ya no, porque vaciarla destruiría las 880 obras congeladas.
- **Tres settings**, todos con default y sin secretos: `PG_TRAMO_MAX_FILAS`
  (1 000 000), `PG_DISCO_TOTAL_GB` (64, el disco de hoy) y
  `PG_DISCO_LIMITE_PCT` (80). Un
  máximo enorme reproduce el comportamiento antiguo si alguna vez hiciera
  falta diagnosticar, sin conservar una rama de código con el arma cargada.
- Cada tramo deja su fila en `_meta.etl_runs`, así que `python main.py timings`
  desglosa el coste real tramo a tramo.

### La ventana de negocio: no todas las obras se reconstruyen (F-025)

La nocturna del **2026-09-02 murió** por `replicaTimeout` en el tramo 5 de 60 y
dejó `stg.plan_mensual` truncada al **21,6 %**. La causa, medida: el
`Standard_B1ms` es *burstable*, agotó sus 144 créditos de CPU a las 04:15 UTC y
Azure lo capó al 20 % de un núcleo; cada tramo pasó de **1,57 min** a **40,77**.
Y se reconstruían **920 obras** cada noche cuando solo **48** habían tenido
actividad en los últimos doce meses. Esto no fue una mejora de rendimiento: fue
la reparación de una avería.

Desde F-025, `06_presupuesto.sql` y `08_plan_mensual.sql` se construyen **solo
para las obras vivas**. Lo importante no es cuáles, sino **cómo se escribe**.

#### El borrado se DERIVA de lo que se escribe (y esto cambia una invariante)

El `TRUNCATE` global desapareció de las dos tablas. En su lugar, **cada tramo
borra exactamente las obras que va a reinsertar, en su misma transacción**:

```sql
DELETE FROM stg.plan_mensual WHERE obra_id = ANY (ARRAY[...]::BIGINT[]);
INSERT INTO stg.plan_mensual ... AND pp.obra_id = ANY (ARRAY[...]::BIGINT[]);
```

Las dos listas se componen **del mismo dato**, así que no pueden
desincronizarse: es imposible borrar una obra que luego no se reescriba. El
`DELETE` va por índice —`idx_plan_mensual_obra_amb` e `idx_pres_obra_amb`
empiezan los dos por `obra_id`, verificado contra `pg_indexes`—, así que no
barre la tabla.

**Eso invierte la invariante de aborto de F-019.** Allí, parar dejaba la tabla
**vacía**, porque una tabla a medias era indistinguible de una completa. Ya no
aplica: lo que queda tras un fallo no es media tabla, son **obras enteras con su
última versión buena**, y vaciarlas destruiría las 880 congeladas. Quien impide
que `build_mart` construya sobre un stage a medias sigue siendo **la puerta de
F-024**, que no se toca.

Y repara la avería de paso: la noche del 02-sep habría terminado con cinco obras
al día y el resto con el dato de anoche —coherente— en vez de con la tabla al
21,6 %. **Vale por sí solo aunque el acotado no ahorrase nada.**

#### Quién se congela, y quién decide

El criterio lo fijó el humano el 2026-09-02 y son **tres reglas en unión**:
estado **EN ESTUDIO (1), NO PRESENTADA (11) o CERRADA (25)**; código de **seis
dígitos**; o **sin actividad en 12 meses**. Censo: **880 congeladas, 40 vivas**.
Vive en `config/business_rules.yaml`, bloque `ventana:`, y se evalúa en dominio
puro (`domain/ventana.py`): cambiarlo no toca código.

Por encima hay tres mecanismos que **solo añaden** obras, nunca quitan:

- **Reconstrucción completa** (domingos, por antigüedad registrada desde
  `run-all`, no por un cron nuevo: un cron aparte es lo que se olvida).
- **Sello del SQL**: si `06`/`08` cambian, esa noche entran **todas**. Sin esto,
  un arreglo como el de F-052 solo alcanzaría a las 40 vivas y las otras 880
  seguirían publicando lo de antes, **en silencio**.
- **Obra sin construir**: sin filas o sin registro. Completar no es actualizar.

La asimetría es deliberada: equivocarse por exceso cuesta CPU una noche;
equivocarse por defecto deja un dato viejo publicado.

#### La firma DENUNCIA, no rescata

La decisión congela **8 obras con actividad reciente** —7 CERRADAS y 1 de seis
dígitos, de 48 con actividad; remedido el 2026-09-03— y acepta hasta **6 días**
de antigüedad. Cuando el origen de una obra congelada cambia, el sistema **la
nombra y la deja congelada**: rescatarla contradiría esa decisión. La firma se
calcula sobre **`raw`** —lo único que la ingesta sigue trayendo completo— en un
sub-paso propio tras `ingest_raw`, porque `stg.presupuesto` dejó de
reconstruirse entera y con ello dejó de servir como señal.

#### De cuándo es el dato de cada obra

`_meta.obra_build` (una fila por obra: firmas, sello, `batch_id`,
`construido_at`, motivo) y `_meta.v_frescura_obra`, hermana de `_meta.v_frescura`
pero al grano de obra. Es la respuesta consultable a *«¿de cuándo es esto?»*, y
la leen igual el MCP y Power BI. `construido_at` **solo se mueve cuando la obra
se reconstruye de verdad**: moverlo al congelar sería mentir sobre la frescura,
que es el dato por el que existe la vista.

#### El guardián

`check-ventana` corre al final de `run-all`, **avisa y no bloquea**, y mira las
cuatro maneras de que una obra congelada envejezca sin que nadie se entere:
firma divergente, congelada sin filas, sello no vigente y completa vencida.
Marcador `[F025-VENTANA-KO]`; **sin desplegar
`infra/97_create_alert_ventana.ps1` es mudo**, y ese es el precio declarado de
no bloquear.

**Un verde sobre cero obras es un KO.** Confundir «no hay nada malo» con «no he
podido mirar» es el modo de fallo exacto que estos guardianes existen para
eliminar, y le pasó de verdad a `check-cobertura` el 02-sep, con
`stg.plan_mensual` truncada: las dos consultas devolvieron cero filas y dijo OK.
Se arregló en F-025, y `check-ventana` nació con la regla puesta.

#### Cuatro ajustes, y la ventana nace apagada

`PG_VENTANA_ACTIVA` (**false** por defecto), `PG_VENTANA_MESES` (12),
`PG_VENTANA_DIA_COMPLETA` (6 = domingo) y `PG_VENTANA_RESCATE` (off). Mientras
esté apagada, el contenido publicado es exactamente el de hoy; lo que **no**
vuelve es el `TRUNCATE`, porque borrar y reescribir todas las obras deja el
mismo resultado y además sobrevive a un tramo que falle.

### Coherencia ante cargas truncadas (F-024)

El 2026-08-18 la primera carga real lanzada desde el job murió por
`DeadlineExceeded` a las dos horas justas, en el tramo 39/60 del stage. `mart`
no llegó a tocarse, así que las vistas siguieron enseñando el build anterior
completo; pero `_meta.etl_runs` se quedó con dos filas `RUNNING` huérfanas para
siempre y `stg.plan_mensual` a medias. Destapó tres huecos: una muerte externa
del proceso no deja rastro honesto, nada impide construir sobre un `raw`
MEZCLADO, y el consumidor no tiene forma de saber si lo que ve es de anoche o
de hace tres días.

**No se hace nada atómico.** Una transacción de tres horas en el `B1ms` es
exactamente lo que reventó el 09-ago, y F-019 la troceó a propósito. La
coherencia se garantiza por **verificación** y **visibilidad**:

- **Identidad de ejecución.** Todo comando que ESCRIBE genera un `batch_id`
  (`YYYYMMDDTHHMMSSZ-xxxxxx`, dominio puro en `domain/ejecucion.py`) y lo
  estampa en cada fila que deja en `_meta.etl_runs`. El formato se ordena
  cronológicamente **como texto**, así que un `ORDER BY batch_id` sale ordenado
  sin parsear nada. El histórico anterior queda con `batch_id` a `NULL`: la
  columna se **añade**, la tabla no se recrea.
- **Filas huérfanas → `ABORTED`.** Al arrancar, antes de ejecutar ningún paso,
  todo comando que escribe cierra las filas que siguen en `RUNNING` con el
  motivo, la ejecución que las marcó y la hora. Toda `RUNNING` que exista al
  arrancar es de otro proceso por definición. Si la marca falla, se avisa y se
  **continúa**: es contabilidad, y el paso siguiente fallará por sí mismo si la
  BBDD no está.
- **Dos puertas, ambas ANTES de escribir nada.** `build_stg` exige que TODAS
  las tablas declaradas en `tables_sigrid.yaml` provengan del **mismo** batch
  terminado en `SUCCESS`; `build_mart` exige que la fila más reciente de
  `build_stg%` sea el **paso** completo, no un sub-paso ni un tramo. El
  veredicto es dominio puro (`domain/coherencia.py`) y queda registrado en
  `_meta.etl_runs` (`build_stg.puerta_raw`, `build_mart.puerta_stg`) pase lo
  que pase. Que vayan primero no es un detalle de orden: `stg` empieza con
  `TRUNCATE` y `mart/01_ddl.sql` con un `DROP`, y eso no se deshace porque el
  step devuelva `FAILED` después.
- **`--sin-puerta`, solo en los comandos sueltos.** `stage` y `build-mart` la
  admiten; `run-all` **no**, porque a medianoche no hay nadie delante para
  valorar si saltársela es razonable. Con la opción, la puerta se evalúa
  igualmente y su fila queda `SKIPPED` con el veredicto dentro: lo que esa fila
  cuenta es que el build se hizo **sin** puerta, no lo que la puerta habría
  dictaminado.
- **Dos vistas en `_meta`**, derivadas de la tabla que ya escriben todos los
  pasos, sin tablas nuevas que mantener: `v_raw_state` (de qué carga viene cada
  tabla de `raw`) y `v_frescura` (último OK y último intento por paso, **por
  separado**: un `build_mart` que falló esta noche deja `mart` con lo de ayer y
  el consumidor necesita las dos noticias). Las leen por igual la puerta, el
  MCP y Power BI. Ninguna toca `raw`, `stg` ni `mart`: cero coste sobre el
  servidor compartido.
- **Diagnóstico y alerta.** `check-coherencia` y `check-frescura` son de solo
  lectura (`timings` también: ve las huérfanas y **avisa**, no las marca). Y
  `infra/95_create_alert_frescura.ps1` crea una regla de consulta programada
  que dispara si en `frescuraUmbralHoras` (30) no hay ninguna línea de log del
  job diciendo que `build_mart` terminó en `SUCCESS`. Vigila desde **fuera**
  del ETL, así que «el job no lo hizo» dispara igual que «el job murió».

**La ingesta hace commit por PÁGINA, no por tabla** (DA-8, confirmado el
2026-08-18). Desde F-148 lo hace por **una conexión por tabla**: la
`SesionDeCarga` (`sesion_carga.py`) abre la conexión en la primera página y
la reutiliza para todas, con `COPY` + `COMMIT` por página; antes cada página
abría la suya (~3.500 aperturas por noche contra el Postgres compartido, y
en las nocturnas del 17 al 23 de octubre hubo aperturas colgadas hasta 130 s). La
transacción sigue siendo por página, así que la consecuencia para cualquier
post mortem no cambia: una muerte a mitad de tabla la deja **truncada y
parcial**, no intacta. Si la conexión se rompe a mitad de una página, la
sesión cuenta las filas del rango de ids de esa página para saber si el
`COMMIT` llegó (0: no llegó; todas: sí; otra cifra: error, «página ambigua»),
reconecta y reintenta hasta 3 veces; un error que no es de conexión hace
`ROLLBACK` y propaga. Cada página deja `ingest_pagina` en el log (`http_s`,
`pg_connect_s`, `copy_s`, `reintentos`) y el paso, `conexiones_abiertas` en
su `metadata`. La puerta de F-024 no depende de nada de esto: la marca de
«tabla ingerida» solo se escribe cuando la tabla termina en `SUCCESS`, así
que una tabla parcial queda con su última fila en `RUNNING` → `ABORTED` y la
puerta la rechaza igual.

**Toda conexión lleva `connect_timeout` y keepalives** (F-148). Sin
`connect_timeout`, psycopg 3 espera 130 s por apertura; ahora son 15
(`PG_CONNECT_TIMEOUT_S`), con `keepalives` 30/10/3 y `tcp_user_timeout` 60 s
para que un flujo que la red deje caer en silencio durante las esperas a
`sigrid-api` se detecte en un minuto y no en los ~15 de la retransmisión de
TCP. La apertura se reintenta (`reintento_conexion.py`, hasta
`PG_CONNECT_INTENTOS` = 4, espera exponencial 2-30 s) SOLO ante errores
transitorios —sin `sqlstate`, clase `08`, `53300`, `57P03`—; la autenticación
fallida, el rol o la base inexistentes fallan a la primera. El `SET ROLE` no
se reintenta. Una apertura de más de 2 s o con reintento deja
`pg_conexion_lenta`.

### El datamart se explica solo (F-006)

El datamart publica **su propia semántica dentro de la base**: qué significa
cada objeto y cada columna, qué grano tiene, qué trampas hay que respetar al
leerlo y qué preguntas de negocio contesta. No es documentación para personas:
es un **contrato de datos** que un agente conectado por MCP lee por SQL, sin
poder preguntarle a nadie si algo no encaja.

- **La fuente son los YAML de `config/diccionario/`**: uno por esquema —los
  de `ESQUEMAS_DEL_DATAMART`— más `00_global.yaml`, que lleva las reglas duras
  transversales, los ejes, las convenciones de nombre y la batería de preguntas
  de aceptación. Están en este repositorio a propósito: qué significa
  `mart.fact_seguimiento_mensual` lo sabe quien escribió el SQL que la
  construye, y cualquier otro sitio se desincroniza. Por eso la ficha se
  actualiza en el mismo trabajo que el objeto (`docs/CONVENTIONS.md`).
- **El paso `publicar_diccionario`** los carga, valida, deriva los avisos y los
  escribe. Va dentro de `run-all`, **entre los cuatro build de negocio y
  `apply_grants`**, y ese orden no es cosmético: `apply_grants` concede `SELECT` sobre lo que hay
  en `_meta` en ese instante, así que publicar después dejaría las tablas del
  contrato colgando solo de los privilegios por defecto. Suelto, el comando es
  `python main.py publicar-diccionario`.
- **El contrato en `_meta` son cuatro tablas y una vista.** `_meta.diccionario`
  (una fila por objeto documentado, con la ficha entera en `JSONB` y en
  columnas lo que se filtra barato); `_meta.diccionario_reglas` (las reglas
  duras que no son de ningún objeto en particular);
  `_meta.diccionario_contexto` (los bloques de contexto, que crecen **por
  filas**, no por columnas); y `_meta.diccionario_publicacion`, una única fila
  con `version`, `hash_fuente` y los recuentos. Encima, `_meta.v_diccionario`
  es la vista plana que consulta el cliente.
- **La publicación es atómica**: `DELETE` + `INSERT` dentro de UNA transacción,
  así que quien consulte mientras se publica ve el diccionario anterior
  completo o el nuevo completo, nunca uno a medias. **Nunca `DROP` ni
  `TRUNCATE`**, y nunca quitar o reordenar columnas de la vista: eso exige un
  `DROP VIEW`, y un `DROP` se lleva por delante los `GRANT` del rol de lectura.
  Las reglas de compatibilidad completas están en la cabecera de
  `etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql`.
- **Quien lo consume es `mcp-bbdd`**, un servicio con su propio repositorio, y
  lo hace **por SQL** con el rol de solo lectura `mcp_sigrid_dm_ro`. No hay API
  que versionar ni fichero que exportar: la base es la interfaz, y por eso un
  cambio en esas cinco formas es un cambio de API.
- **Dónde está la línea**: el MCP sabe de transporte, permisos, auditoría y
  multi-base; el significado del dato es del dueño del dato. Por eso el
  diccionario vive aquí y el servidor MCP no. Y el diccionario describe lo que
  el dato **es**, no cómo se decide con él: un procedimiento de negocio es otro
  repositorio.
- **Presupuesto del contexto (F-147).** `contexto_bbdd()` de `mcp-bbdd` se
  sirve ENTERO en cada conversación, y crecía en silencio (~86.000 caracteres
  con la v58). Desde la v59 **toda regla dura lleva `resumen`** —la orden corta,
  de 40 a 250 caracteres, que basta sola— y una **`entrega`**: `resumen` (se
  sirve el resumen; `regla` y `motivo` son el detalle para `describir_tabla`),
  `entera` (se sirve entera siempre: `R-PERFILES`, que trata de lo que el perfil
  NO ve) o `fuera_mcp` (no se publica: `R-SIGRID-CON`, guía del ETL). Las dos
  columnas van AL FINAL de `_meta.diccionario_reglas`, con `CHECK` en la base y
  un `DO` que solo hace `ALTER` si faltan (no en cada publicación). El enrutado sirve las 2
  primeras `ejemplos_preguntas` de cada ficha (`MAX_PREGUNTAS_ENRUTADO`) y cada
  `para_que_sirve` de esquema cabe en 350. **La puerta**:
  `tests/test_f147_presupuesto_contexto.py` mide desde los YAML lo que se
  servirá entero (reglas, enrutado y bloques de `_meta.diccionario_contexto`) y
  falla por encima de `PRESUPUESTO_MAX` o con más de 1.000 de holgura
  (trinquete). Cómo se compone lo servido es de `mcp-bbdd` (su F-029); cuánto se
  publica, de aquí.
- **La frescura no se declara, se une.** El `paso_etl` de cada ficha casa con
  `_meta.v_frescura.paso` (F-024), así que el consumidor sabe de cuándo es lo
  que está mirando sin tener que creerse un texto escrito a mano.
- **Verificación**: `python main.py check-diccionario` contrasta el diccionario
  del árbol contra el catálogo real de la base en las dos direcciones —objeto
  publicado sin ficha, ficha sin objeto, tipo que no casa— y avisa si lo
  publicado va por detrás del repositorio. La puerta offline de
  `bash harness/init.sh` solo puede exigir ficha **o** pendiente declarado.
- **Claves alternativas (F-108).** Además de su `clave_negocio`, una ficha
  puede declarar `claves_alternativas: [[col, ...], ...]`: otras combinaciones
  de columnas que TAMBIÉN identifican una fila, como `clave_obra` en
  `maestro.obras` (cuya clave de negocio sigue siendo `obra_id`). El validador
  del diccionario acepta una alternativa de UNA columna como lado 1 de una
  relación —por eso las relaciones de `compras` por `clave_obra` son `N:1`—, y
  `python main.py check-unicidad` la comprueba contra la base igual que la de
  negocio, sin contar las filas con la clave a NULL; una rota sale con código 1.
  Es un aviso de auditoría y no un índice único: un duplicado no tumba la
  nocturna. Se publican dentro del `JSONB` de la ficha, sin DDL.

Lo que este proyecto **expone al ecosistema** y quién lo consume está en
`azure-apps/datamart_seg_anual.md`, y no se duplica aquí.

### Los descompuestos: el primer esquema incremental (F-097)

**Qué es cada pestaña de Sigrid, en el dato.** En la partida hay dos pestañas
en COSTE (ámbito 3) y una en MASTER COSTE (ámbito 8):

| Pestaña | Tabla de Sigrid | Origen publicado en `descompuestos.lineas` |
|---|---|---|
| COSTE «Descomposición» | `obrparpre.des`, ámbito 3 fase 0 | `ESTUDIO` (Estudios, solo en las obras sin master 0) |
| COSTE «Planificación compras» | `dncpro` de la necesidad de la obra (`obr.dncide`) | `PLANIF_JO` (la del jefe de obra) |
| MASTER COSTE «Descomposición» | `obrparpre.des`, ámbito 8, una copia por versión | `MASTER_ESTUDIO` (v0: Estudios donde hay master 0), `MASTER_PRE_ABC`, `MASTER_PLANIF_JO` (desde la primera ABC) |

**La regla de Estudios (F-123, decidida por el humano el 2026-10-02).** Coste
fase 0 es la **fase viva**: el presupuesto de coste que el jefe de obra
evoluciona día a día, sin historia; su descompuesto es la planificación de
compras (`PLANIF_JO`), y su «Descomposición» ya no es Estudios (donde hay master
0 repetía la versión 0 en el 99,5 % de las partidas, o ya no cuadraba con su
precio). Así que **Estudios es el master 0**: en las obras con versión 0 del
master con descompuesto (fila con `fase_num = 0` en `_versiones_cargadas`, 170
el 2026-10-02) se publica `MASTER_ESTUDIO` y NO `ESTUDIO`; solo en las obras sin
master 0 (44) se publica `ESTUDIO` como antes. Se decide por obra y contra
`_versiones_cargadas`, no contra `lineas`, porque `02` corre antes que `03`.
Consumo: `v_pbi_estudio` (solo `ESTUDIO`) y `v_pbi_master_estudio`
(`MASTER_ESTUDIO`), con las mismas 21 columnas: juntas son Estudios entero. El
cambio de nombre del master 0 lo migra un bloque `DO` de `02_lineas_coste.sql`
(cambia los dos `CHECK` y las filas ya cargadas, una sola vez, sin `DROP` de
las tablas); y como el literal vive en `03`, cambia el sello y retrocea todo.

No hay tabla de líneas de descompuesto: el de Estudios y el del master son
TEXTO. **El formato del `des`**: registros que empiezan por `~D|`, separados
por salto de línea, con campos separados por `|` (19 a 38 campos). Posiciones
base 0: 1 código, 2 descripción, 3 precio, 4 cantidad total, 5 unidad, 7 código
alternativo (= `dncpro.cod2`), 11 código de naturaleza, 14 «factor x rendimiento»,
16 tipo, 17 naturaleza, 36 enlace a `dncpro.ide`. El texto largo del campo 9
puede traer saltos de línea dentro, así que se parte por «salto seguido de
`~<letra>|`» y nunca por cualquier salto. **El campo 14 no es el rendimiento a
secas** (F-120, medido el 2026-10-01 en 4,5 M registros): es un número cuando la
línea no tiene FACTOR y `<factor>x<rendimiento>` cuando lo tiene (`1.22x0.003`,
`0.99765x-0.15`, `-23.05x`; el orden, comprobado contra `dncpro.faccan` y
`canren`). Se publica `factor` (1 sin factor, NULL sin campo) y el rendimiento
limpio, e `importe_unitario` = factor x rendimiento x precio; `cantidad_total`
(campo 4) ya lleva el factor. PLANIF_JO lo toma de `dncpro.factip`/`faccan`. **La «Descomposición» de COSTE se reescribe con la
planificación**: si un registro trae el campo 36, esa partida ya no es Estudios
(7.866 de 42.958), no sale como `ESTUDIO` y el cuadre la marca
`SUSTITUIDO_POR_PLANIFICACION`. El troceado es UNA función SQL
(`descompuestos.fn_trocear`) con su espejo en Python
(`domain/descompuestos.trocear_des`) para probarlo sin base; contrastados en
2.700 filas reales de Sigrid el 2026-09-28, sin una diferencia.

**Por qué no va en `tables_sigrid.yaml`.** El master son 3.023 versiones y
2,14 GB de texto. La nocturna es `run-all --full`, que trunca `raw`: una entrada
del YAML releería los 2,14 GB cada noche (65-94 min). Así que el texto vive en
el propio esquema —`descompuestos._des_texto` y el control
`descompuestos._versiones_cargadas`—, que nada trunca, y lo mantiene un paso
propio, `ingest_descompuestos`, INCREMENTAL por versión:

1. **La huella de todas las versiones en una consulta** (24-27 s): por
   (obra, versión) filas, bytes y un `CHECKSUM_AGG` del texto (SQL Server 2012:
   `HASHBYTES` solo admite 8.000 bytes, así que es el primer y el último tramo
   más la longitud, `can` y `pre`).
2. **El ámbito 3 entero** cada noche (21,5 MB), en una sustitución.
3. **Releer**: las versiones no cargadas, **la vigente de cada obra siempre**
   (la huella es ciega a un cambio en mitad de un `des` de más de 16.000
   bytes) y las de huella distinta; **borrar** las que Sigrid ya no tiene.
   Todo dentro de un tope de 300 MB por noche (`DESCOMPUESTOS_PRESUPUESTO_MB`),
   del que el ámbito 3 consume primero; lo que no cabe, a la noche siguiente.
4. **Cada versión en UNA transacción** (`PostgresClient.reemplazar_filas`:
   `DELETE` + `COPY` + fila de control), leída por el índice `oaf` de Sigrid y
   paginada de 1.000 en 1.000. Si el recuento no es el de su huella, no se
   escribe —queda la copia anterior— y el paso termina `FAILED` al final, lo
   que salta `build_descompuestos` esa noche.

`build_descompuestos` trocea después solo las versiones cuyo **sello** (el hash
de `00_setup.sql`, `01_troceado.sql` y `03_lineas_master.sql`; `00` entra con
F-120 porque `fn_num` decide el rendimiento) no es el vigente —las releídas
esta noche, o todas si cambia el SQL—, por lotes de hasta 300 MB, cada lote una
transacción con sus líneas y su cuadre. Los flags de versión (`es_vigente`,
`es_ultima`, la primera ABC) cambian sin que cambie el texto: se actualizan
solo en las versiones cuya huella de atributos no es la aplicada. ESTUDIO,
PLANIF_JO, `descompuestos.elementos` y el cuadre del ámbito 3 se rehacen
enteros cada noche.

**La primera carga es MANUAL** (`python main.py ingest-descompuestos
--sin-tope` y `build-descompuestos --sin-tope`, 1,5-2 h de lectura; el troceado
de la del 2026-09-29 tardó 916,9 s en 7 lotes, 15 min 17 s el paso entero),
fuera de la nocturna y mirando antes los créditos de CPU del servidor. Un
cambio del SQL del sello retrocea TODO lo cargado sin releer Sigrid: F-120 lo
hace de una vez con `build-descompuestos --sin-tope` + `apply-grants`, y
**siempre después de desplegar la imagen** (al revés, la imagen vieja ve otro
sello, retrocea hacia atrás y su `CREATE OR REPLACE FUNCTION fn_trocear` falla
contra la función nueva). Sin la primera carga, la nocturna completaría el
master sola a 300 MB por noche (unas 8 noches) y, mientras tanto, el master de
`descompuestos.lineas` estaría INCOMPLETO; en producción la primera carga se
hizo el 2026-09-29. **Si el estado se corrompe**: vaciar
`descompuestos._versiones_cargadas` y relanzar la primera carga. Espacio
estimado: 2,5-4,2 GB (27 de 64 GB el 2026-09-26).

**`obrparpre` no tiene `tiemod`**: 22 columnas en Sigrid, ninguna es `tiemod`
(medido el 2026-09-27). La entrada del YAML lo declaraba y la ingesta lo
degradaba a NULL en silencio; desde F-097 declara `incremental_column: null`.
Otras 13 entradas tienen el mismo defecto (F-115).

### La nocturna construye TODO el datamart, y lo demuestra (F-047)

Hasta el 2026-08-28 `run-all` construía `raw → stg → mart` y nada más.
`cierre`, `compras`, `maestro` y `retenciones` se lanzaban a mano y podían
estar desfasados semanas. F-057 añadió el quinto, `build_personal`, que nació
ya dentro, F-056 el sexto, `build_contabilidad`, F-097 el séptimo,
`build_descompuestos`, con su propia ingesta `ingest_descompuestos` delante, y
F-037 el octavo, `build_tesoreria`, delante de `build_compras` (su
`compras.vencimientos` es una vista de `tesoreria.efectos`; sin `depends_on`).
Los quince pasos de hoy, en orden:

```
ingest_raw → load_excel_aux → build_stg → build_mart
           → build_maestros → build_tesoreria → build_compras → build_retenciones
           → build_personal → build_contabilidad
           → ingest_descompuestos → build_descompuestos → build_cierre
           → publicar_diccionario → apply_grants
```

- **`build_cierre` va después de `build_mart`, y es una dependencia de
  DESTRUCCIÓN, no de datos.** `mart/03_agg_categoria.sql` dropea
  `mart.fact_seguimiento_categoria` con `CASCADE`, y
  `cierre.v_pbi_planif_vs_real` cuelga de esa tabla en `pg_depend`: la
  nocturna la **destruía** cada noche y nadie la recreaba. Está declarado en
  `BuildCierreStep.depends_on`, no confiado al orden de la lista: un
  comentario se borra, el orden topológico obedece.
- **`apply_grants` sigue siendo el último.** Los siete build recrean vistas
  con `DROP` + `CREATE` y un `DROP` se lleva los `GRANT`. Y **no** depende de
  ellos a propósito: si `build_cierre` falla una noche, los permisos del MCP
  se reaplican igual. El precio es que un esquema puede quedarse atrás sin
  tumbar la carga, y por eso la regla dura `R-FRESCURA` del diccionario manda
  citar la frescura DEL PASO, no la del pipeline.
- **Permisos tras cada build, sin esperar al final** (F-148). Una noche que
  moría a medias dejaba esquemas sin `GRANT` hasta la noche siguiente
  (2026-10-20). Ahora `run-all` aplica los permisos completos —la lógica
  íntegra de `ApplyGrantsStep`, con sus vetos— tras cada uno de los diez build
  de `PASOS_CON_PERMISOS` que se EJECUTA, vaya bien o mal, y graba la fila
  `apply_grants.tras_<paso>`. Si fallan, aviso `permisos_tras_paso_fallidos`
  y la noche sigue; el `apply_grants` final sigue siendo el que decide.
- **El reintento del job reanuda, no repite** (F-148). El job tiene
  `replicaRetryLimit` 1 y la segunda réplica empezaba de cero (el 22-10 la
  noche terminó a las 04:31). Ahora `run-all` lee
  `CONTAINER_APP_JOB_EXECUTION_NAME`, que comparten las dos réplicas, y el
  sufijo del `batch_id` sale de su SHA-256: la segunda réplica encuentra el
  lote de la primera (de las últimas 8 h), lo **adopta** y omite lo que ya
  quedó en `SUCCESS`: un paso, si sus dependencias también se omiten
  (`apply_grants` nunca), y cada tabla de `raw` ya cargada. Lo que un paso lee
  sin declararlo también cuenta, solo para omitir (`LECTURAS_PARA_REANUDAR`):
  si se rehace `build_stg` o `build_mart`, se rehacen las retenciones, que leen
  los dos para el fin de obra (F-110, D4). Como el lote es el
  mismo, la puerta de `build_stg` ve un solo lote. Un paso omitido no graba
  fila: `v_frescura` sigue diciendo cuándo se construyó de verdad. Sin la
  variable (el puesto, los comandos sueltos) todo es como antes.
- **Los siete registran paso** en `_meta.etl_runs` con el `batch_id` de la
  noche. `build-compras` y `build-retenciones` no lo hacían —ejecutaban SQL en
  línea, sin step—, así que su fecha de build no era consultable por SQL
  mientras el diccionario mandaba citarla.
- **Coste medido** (2026-08-21, con el disco vigilado): +37,5 min sobre 2 h 46,
  de los que `build_cierre` se lleva el 74 %. El disco no se movió (57,92 % →
  57,93 % sobre un límite del 80 %): estos cuatro reconstruyen desde `raw` y
  `stg`, no acumulan como `plan_mensual`. `build_personal` entró después y su
  coste está estimado, no medido: dos `INSERT ... SELECT` de 2.618 y 330.638
  filas, unos 60 MB, del orden de segundos frente a las 3 h 45 de ventana.
  `build_contabilidad` (F-056) tampoco está medido en build todavía: el SELECT
  entero de las tres tablas lee en 126 s en solo lectura (2026-09-26), y con
  la escritura y los índices se estima en 4-6 min y ~1,2 GB; se mide en su
  primera ejecución. `build_tesoreria` (F-037), tampoco: el SELECT de la
  cartera completa lee 278.866 filas en 2-9 s en solo lectura (2026-10-13), y
  con los dos `INSERT` y sus índices se estima en +1-3 min y +0,2 GB; se mide
  en el primer build manual del despliegue (R29).

**El guardián.** `run-all` termina contrastando **lo que el SQL del
repositorio declara crear** contra `information_schema`, y sale con código 1
si falta algo. Es la pregunta que no hacía nadie: la puerta de `init.sh`
compara el SQL contra las fichas y `check-diccionario` compara las fichas
contra la base, y por el hueco entre las dos se coló F-047 durante semanas.
Suelto es `python main.py check-declarados`, de solo lectura. Lo que
legítimamente aún no toca construir se declara en
`config/objetos_pendientes.yaml`, mismo patrón y mismo trinquete que
`pendientes` en el diccionario: **objeto construido o pendiente declarado**, y
la lista solo baja.

## Infra

- `Dockerfile` en raíz. `infra/` con scripts PowerShell 5.1 (UTF-8 BOM, CRLF)
  numerados por orden de ejecución. Procedimiento y datos están separados:
  **los nombres de recurso viven solo en `infra/env/<entorno>.json`** y ningún
  `.ps1` escribe uno. Montar `sta` o `pro` es copiar ese fichero y ejecutar con
  `-Entorno <nombre>`; `00_vars.ps1` lo carga, lo valida y aborta antes de la
  primera llamada a `az` si falta un valor. Lo verifican los tests
  `test_f003_r1..r11` sin tocar Azure.
- **Ni la suscripción ni ningún secreto están en el repositorio.** La
  suscripción sale de `$env:AZ_SUBSCRIPTION_ID` o del contexto de `az`.
- `infra/sql/` contiene la provisión de `sigrid_dm` (base, roles, diagnóstico).
  Se ejecuta a mano con `psql`, nunca desde el ETL: usa bloques `$$`, que el
  troceador de sentencias de `postgres_client.py` no sabe manejar.
- Destino: **Container Apps Job programado** (`0 0 * * *` UTC desde el
  2026-09-06, antes `0 2 * * *`; siempre
  `run-all --full`) en un resource group propio del datamart, región
  `spaincentral`, con entorno **sin integración de red virtual** — así tiene IP
  de salida estática, que es lo que se autoriza en el firewall del Postgres.
  Tags de imagen fechados (`rYYYYMMDD-HHmm`), nunca reescritos.
- **Sin contraseñas en el job.** Corre con una **identidad gestionada asignada
  por el usuario** que tiene exactamente tres permisos: bajar la imagen del
  registro, leer el único secreto (la clave de `sigrid-api`) del Key Vault del
  proyecto y leer los Excels auxiliares del blob. Esa misma identidad es la que
  `AZURE_CLIENT_ID` señala dentro del contenedor.
- Orden de ejecución, pasos que exigen autorización del humano y consulta de
  logs: `infra/README.md`.
