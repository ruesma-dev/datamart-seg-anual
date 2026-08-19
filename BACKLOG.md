<!-- BACKLOG.md -->
# Backlog

**Fichero generado por `harness/backlog.py` a partir de `harness/features.json`. No lo edites a mano**: edita el JSON y vuelve a generarlo (lo hace solo `bash harness/init.sh`).

Resumen: **25 features**, 15 abiertas, 10 terminadas.

En curso: **F-024**.

Bloqueadas: **F-003**.

## Trabajo abierto

| # | Feature | Prioridad | Estado | Rigor | Rama |
|---|---|---|---|---|---|
| F-003 | Infra: despliegue como Container Apps Job diario | 7 | bloqueada | critico | `feature/F-003-infra-caj` |
| F-023 | Cierre operativo de F-003: verificaciones de F-004 en Azure, retirada de secretos duplicados y limpieza del puesto | 8 | pendiente | estandar | `feature/F-023-cierre-operativo-f003` |
| F-024 | Coherencia del datamart ante cargas truncadas: deteccion, puerta y frescura | 9 | en curso | critico | `feature/F-024-coherencia-cargas-truncadas` |
| F-029 | La campaña de mutación no se puede creer: la vía paralela regala muertos y una interrupción deja el árbol mutado | 10 | pendiente | critico | `feature/F-029-mutacion-fiable` |
| F-011 | Carga incremental del datamart | 11 | pendiente |  | `feature/F-011-carga-incremental` |
| F-017 | Cierre mensual: incorporar los costes indirectos (CI) | 12 | pendiente |  | `feature/F-017-cierre-costes-indirectos` |
| F-022 | Desempatar versiones master duplicadas de raw.obrfasamb | 12 | pendiente | estandar | `feature/F-022-desempate-obrfasamb` |
| F-018 | Validar los numeros de cierre.fact_cierre_mensual | 13 | pendiente |  | `feature/F-018-validacion-cierre-mensual` |
| F-028 | La puerta de stg distingue un stage que no llegó a construir de uno que dejó stg a medias | 13 | pendiente | estandar | `feature/F-028-puerta-stg-distingue-fallo` |
| F-006 | MCP de bases de datos como servicio en cloud | 14 | pendiente |  | `feature/F-006-mcp-azure` |
| F-002 | PLAN_VIGENTE: serie de planificación consolidada | 15 | pendiente |  | `feature/F-002-plan-vigente` |
| F-012 | Auditoria y limpieza de Azure para reducir costes | 16 | pendiente |  | `feature/F-012-auditoria-costes-azure` |
| F-013 | Cargar los Excels auxiliares a la capa aux | 17 | pendiente |  | `feature/F-013-carga-excels-aux` |
| F-010 | Carga y mantenimiento de los Excels auxiliares en Azure | 18 | pendiente |  | `feature/F-010-carga-excels-auxiliares` |
| F-007 | Disparo manual de la actualización desde web | 19 | pendiente |  | `feature/F-007-disparo-manual-web` |

## Terminadas

| # | Feature | Prioridad | Rigor |
|---|---|---|---|
| F-001 | Comando 'version' en el CLI | 1 | estandar |
| F-009 | Inventario del entorno Azure existente | 2 | documental |
| F-005 | Postgres del datamart en Azure | 3 | critico |
| F-014 | Arnes generico versionado, reutilizable en cualquier proyecto | 4 | estandar |
| F-004 | Ejecutar el ETL en Azure sin dependencias locales | 5 | estandar |
| F-015 | Verificar que los tests son de verdad: mutacion, fase RED, cobertura y niveles de rigor | 6 | estandar |
| F-020 | Arnes multi-servicio: preparar arnes-base para monorepos de varias apps/servicios | 8 | estandar |
| F-019 | Build de stg.plan_mensual por tramos: caber en el servidor compartido | 9 | critico |
| F-016 | Refuerzo de tests para los huecos de riesgo alto de F-005 | 10 | estandar |
| F-008 | Documentación de referencia: tablas de Sigrid, landing zone de acens y sigrid-api | 20 | documental |

## Detalle

### F-003 · Infra: despliegue como Container Apps Job diario

estado **bloqueada** · prioridad 7 · rigor `critico` · SDD sí · rama `feature/F-003-infra-caj`

Completar infra/ para desplegar el ETL como Azure Container Apps Job programado (nocturno, siempre --full) en rg-seguimiento-dev, escribiendo contra el Postgres de F-005. Dockerfile ya en raíz y scripts PowerShell esbozados en infra/ con varios TODO por cerrar (ACR, host de Postgres, secretos). Secretos en Key Vault, nunca en el repo. Incluye observabilidad: logs consultables y aviso ante fallo del job.

### F-023 · Cierre operativo de F-003: verificaciones de F-004 en Azure, retirada de secretos duplicados y limpieza del puesto

estado **pendiente** · prioridad 8 · rigor `estandar` · SDD no · rama `feature/F-023-cierre-operativo-f003`

Lo que quedo abierto al completar la tanda 2 de F-003 el 2026-08-17 (job nocturno creado, probado y con alerta verificada). Tres bloques: (1) las tres verificaciones MANUAL heredadas de F-004 (leer los Excels desde el blob 'aux' de stdatamartsegdev desde el puesto, desde el job con identidad gestionada, y la prueba negativa de permisos), que exigen ANTES subir los tres Excels al contenedor 'aux', asignar al humano el rol Storage Blob Data Reader sobre la cuenta y cambiar las AUX_EXCEL_* de infra/env/dev.json a URIs de blob (hoy apuntan a rutas locales de OneDrive: el job las trata como no configuradas); (2) retirar las copias viejas de pg-sigrid-dm-app y pg-mcp-sigrid-dm-ro en kv-albaranes-rs9k2 (el job ya usa kv-datamart-seg-dev y tiene ejecucion correcta) — borrado en un recurso de albaranes, requiere OK explicito del humano; (3) limpieza del puesto: linea de hosts (68.221.140.205), reglas de firewall del puesto en psql-albaranes-rs9k2 (datamart-puesto-pgris-2026-08-17-rango, y ClientPgris / FirewallIPAddress_2026-6-16 SOLO si el humano confirma que nadie mas las usa) y decidir si SIGRID_API_PAGE_SIZE=50000 se queda en los .env. Con los tres bloques hechos, F-003 pasa por el reviewer y se marca done. NO incluye la carga de los Excels a tablas aux.* (eso es F-013).

### F-024 · Coherencia del datamart ante cargas truncadas: deteccion, puerta y frescura

estado **en curso** · prioridad 9 · rigor `critico` · SDD sí · rama `feature/F-024-coherencia-cargas-truncadas`

Origen: la primera carga real desde el job (2026-08-18) murio por DeadlineExceeded a las 2 h justas, en el tramo 39/60 del stage. No hubo dano porque mart no se toco, pero destapo tres huecos: (1) una muerte EXTERNA del proceso (kill por deadline, OOM, reinicio del nodo) deja en _meta.etl_runs una fila RUNNING huerfana para siempre, y timings miente; (2) nada impide que stage/mart se construyan sobre un raw MEZCLADO (tablas de ejecuciones distintas, tras una ingesta parcial seguida de otro fallo), que es incoherencia silenciosa: cuadros que no cuadran y nadie que lo sepa; (3) el consumidor (Power BI, MCP) no tiene forma de saber si lo que ve es de esta noche o de hace tres dias. Se DESCARTA hacer atomico el pipeline entero: una transaccion de 3 h en el B1ms es justo lo que reventó el 09-ago y F-019 lo troceo a proposito. La coherencia se garantiza por verificacion y visibilidad: (a) al arrancar, run-all marca ABORTED las filas RUNNING de ejecuciones anteriores con motivo; (b) puerta antes de stage: FAILED explicito y ruidoso si la ultima ingesta de cada tabla no pertenece a la misma ejecucion (raw incoherente); (c) frescura visible: fecha del ultimo build_mart COMPLETO consultable desde las vistas de consumo, y alerta si supera un umbral. La alerta actual ya cubre los fallos internos (run-all sale 1 si un paso falla; verificado); la muerte externa la cubre (a)+(b).

### F-029 · La campaña de mutación no se puede creer: la vía paralela regala muertos y una interrupción deja el árbol mutado

estado **pendiente** · prioridad 10 · rigor `critico` · SDD sí · rama `feature/F-029-mutacion-fiable`

Dos defectos de harness/mutacion.py descubiertos el 2026-08-19 durante T19 de F-024, los dos con el mismo efecto: la campaña de mutacion es la evidencia que el arnes exige en nivel critico, y hoy no es de fiar. (1) LA VIA PARALELA DECLARA MUERTOS MUTANTES QUE ESTAN VIVOS: la misma feature, el mismo arbol y el mismo dia dio '108 generados, 108 muertos, 0 supervivientes' en 270,9 s con hasta 16 worktrees, y '108 generados, 106 muertos, 2 supervivientes' en 1047,1 s con --workers 1. Los dos supervivientes son bold=True -> bold=False en dos click.secho de main.py (564 y 567); NINGUN test de la suite menciona 'bold' (grep -rn sin resultados) y aplicando la mutacion a mano la suite pasa entera, asi que esos mutantes no pueden morir: el cero era falso y el 106/2 es el bueno. Un '0 supervivientes' es exactamente el numero que nadie vuelve a mirar, y el arnes lo exige para cerrar una feature critica. (2) UNA INTERRUPCION DEJA EL ARBOL MUTADO: con --workers 1 la campaña muta el arbol de trabajo real, y si el proceso muere -o lo matan- el mutante en curso se queda aplicado. Observado dos veces el mismo dia: '==' por '!=' en etl_sigrid/domain/coherencia.py (la puerta que protege build_mart) y 'not veredicto.faltantes' por 'veredicto.faltantes' en frescura.py. El riesgo no es perder la campaña: es COMMITEAR UN MUTANTE creyendo que es codigo, que es lo que habria pasado con un 'git add .' en ese minuto. Agravante observado: un agente que se cae por un error de API deja la campaña huerfana y corriendo, y quien intente sanear el arbol restaura el mutante que se estaba evaluando y contamina el recuento sin saberlo. Es una mejora del ARNES, no del ETL: por la regla de propagacion de CLAUDE.md va tambien a arnes-base en el mismo trabajo, porque afecta a todos los proyectos que lo lleven. (3) MIENTRAS LA CAMPAÑA CORRE, CUALQUIER OTRA VERIFICACION SOBRE EL ARBOL MIENTE: con el arbol mutado, un bash harness/init.sh lanzado en paralelo sale EN ROJO con un test fallando que no tiene nada que ver con lo que se esta verificando. Observado el mismo 2026-08-19, minutos despues de los otros dos: el lider ejecuto init.sh para validar un cambio del backlog y se lo encontro rojo por el mutante en curso del reviewer. Con dos agentes trabajando a la vez -que es el modo normal de este arnes- eso significa que la puerta que decide si una feature puede cerrarse da falsos negativos, y que la reaccion natural (restaurar el fichero) contamina la campaña del otro.

### F-011 · Carga incremental del datamart

estado **pendiente** · prioridad 11 · SDD sí · rama `feature/F-011-carga-incremental`

Hoy el job nocturno ejecuta siempre --full. Conseguir que las cargas que no sean la inicial sean rapidas. HALLAZGO QUE CONDICIONA EL DISENO (F-009): Sigrid NO tiene una marca de ultima modificacion fiable — en el diccionario 'fecalt' aparece en 16 tablas, 'fecmod' en 3 y 'sello' en 2 — asi que no hay watermark directo y hay que construirlo. Palancas: ventana de negocio (ejercicio en curso y obras abiertas, con recarga completa semanal), altas nuevas por el 'ide' autoincremental, y un watermark propio mantenido por el ETL en _meta. Sospecha a verificar antes de disenar nada: el cuello de botella puede no estar en la base sino en la extraccion, porque sigrid-api limita a 1000 filas por peticion y el balanceador corta a los 230 s; encaja con que el intento de abril muriera en la ingesta. La spec debe empezar por medir, no por optimizar.

### F-017 · Cierre mensual: incorporar los costes indirectos (CI)

estado **pendiente** · prioridad 12 · SDD sí · rama `feature/F-017-cierre-costes-indirectos`

Anadida el 2026-08-09 a peticion del humano ('avanzar con cierre mensual, tabla de CI'; CI = costes indirectos, confirmado). Avanzar el cierre mensual incorporando el tratamiento de los costes indirectos a la capa cierre (cierre.fact_cierre_mensual y sus vistas). Contexto existente: el CLI ya tiene inspect-indirectos-detalle e inspect-generales-detalle, config/business_rules.yaml define reglas de negocio, y el mapeo de proporcionales por obra vive en el Excel mapeo_proporcionales que F-004 dejo legible (su carga a aux.* es F-013, posible dependencia). El alcance exacto -que conceptos de indirecto entran, como se reparten a obra/mes y como se reflejan en la tabla principal- lo fija la spec con el humano.

### F-022 · Desempatar versiones master duplicadas de raw.obrfasamb

estado **pendiente** · prioridad 12 · rigor `estandar` · SDD sí · rama `feature/F-022-desempate-obrfasamb`

Creada el 2026-08-13 al cerrar el T11 de F-019 (opción C del humano). En raw.obrfasamb hay versiones master guardadas DOS veces con el mismo número: obra 0694 (2403576) versión 26, creada el 20/07/2026 y el 23/07/2026; obra 0697 (2491656) versión 13, creada el 22/07/2026 y el 23/07/2026. En las cuatro parejas (ámbitos 8 y 11) el segundo registro es del 23/07 con ides consecutivos 29977-29985: parece una misma acción en Sigrid ese día. El join de stg/08_plan_mensual.sql por (obride, amb, fas) duplica entonces TODAS las posiciones de esas versiones (30.860 filas gemelas): (1) el plan master de esas versiones queda contado DOS veces en stg.plan_mensual; (2) las ventanas ROWS/LAG por posicion_mes quedan subespecificadas ante el empate y el reparto de pct entre gemelas depende del plan de ejecución (causa del FALLO inicial del checksum de T11, ver enmienda de R13). Caso completo con receta de replicación en docs/referencia/05_caso_obrfasamb_version_duplicada.md. ANTES de implementar hay una pregunta de negocio: ¿el doble guardado es un error de uso de Sigrid (corregir allí) o debe el ETL desempatar (p. ej. quedarse con la fec de creación más reciente por (obride, amb, fas))? Tras decidir, el arreglo probable es un dedupe determinista en la subconsulta fa de 08_plan_mensual.sql, que elimina a la vez el doble conteo y el no determinismo, y re-verificar con el criterio canónico de la R13 enmendada.

### F-018 · Validar los numeros de cierre.fact_cierre_mensual

estado **pendiente** · prioridad 13 · SDD sí · rama `feature/F-018-validacion-cierre-mensual`

Anadida el 2026-08-09 a peticion del humano ('revisar cierre mensual, tabla principal'; alcance confirmado: validar sus numeros). Contrastar los importes que produce cierre.fact_cierre_mensual (ejecutado origen/anterior/mes, final con su trazabilidad master/fase_0, pendiente, variacion) contra Sigrid y los criterios de cierre del negocio, sobre meses cerrados de obras representativas elegidas por el humano. Documentar cada desviacion con su causa (dato origen, regla de negocio o defecto del SQL) y corregir las que procedan. La spec debe fijar con el humano que obras y meses son el patron de contraste y cual es la tolerancia aceptable.

### F-028 · La puerta de stg distingue un stage que no llegó a construir de uno que dejó stg a medias

estado **pendiente** · prioridad 13 · rigor `estandar` · SDD no · rama `feature/F-028-puerta-stg-distingue-fallo`

Descubierto el 2026-08-19 ejecutando T18 de F-024 (muerte externa controlada) y anotado en progress/manual_F-024_fase_c.md. Cuando `python main.py stage` se niega a construir porque la puerta de raw da KO, falla en 5,2 s con rows=0 y NO toca stg: no hay TRUNCATE ni build. Pero deja en _meta.etl_runs una fila build_stg en FAILED, y con eso la puerta de stg que protege a build_mart declara stg incoherente: 'el ultimo stage no llego a terminar y stg puede estar mezclado'. El veredicto es conservador y protege lo que debe, pero confunde dos situaciones muy distintas: (a) el stage ni empezó, y stg sigue siendo exactamente el del ultimo build completo, que puede ser perfectamente bueno; y (b) el stage murió a mitad de un build y stg si esta mezclado. Consecuencia practica del empate: tras cualquier muerte en la puerta hay que rehacer stage entero -1 h 51 en Azure segun la carga del 19-ago- aunque stg estuviera intacto. La informacion para distinguirlos YA ESTA en la tabla: en el caso (a) el sub-paso que fallo es build_stg.puerta_raw, una puerta y no un build, y ningun sub-paso de construccion llego a iniciarse. NO es un fallo de F-024 ni la debilita: es una mejora de precision del diagnostico que ahorra trabajo real.

### F-006 · MCP de bases de datos como servicio en cloud

estado **pendiente** · prioridad 14 · SDD sí · rama `feature/F-006-mcp-azure`

REFORMULADA 2026-08-08. D4 cerrada: el MCP esta en C:/Users/pgris/PycharmProjects/mcp-bbdd, es un prototipo local (arquitectura hexagonal, pipeline de validacion de solo lectura, servicio de catalogo) y NO es un repositorio git. El humano decide que deje de ser local: debe estar en cloud y ser accesible desde otros equipos sin que su PC este encendido. Y sera multi-base: ademas de sigrid_dm, posiblemente albaranes, partes y otras. Por eso vive en SU PROPIO repositorio y su propio servicio, no dentro de este proyecto. Alcance: rediseno como servidor MCP remoto sobre HTTP desplegado en Container Apps, con autenticacion Entra y autorizacion por grupo, registro de conexiones con lista blanca de esquemas por base, credenciales desde Key Vault y nunca en disco, y auditoria de quien consulta que. Conserva el pipeline de validacion de solo lectura del prototipo, que es la parte bien resuelta. Esta feature la ejecuta el arnes de ESE repositorio: aqui solo queda lo que toque a sigrid_dm (rol de solo lectura y regla de firewall para la IP de salida del entorno).

### F-002 · PLAN_VIGENTE: serie de planificación consolidada

estado **pendiente** · prioridad 15 · SDD sí · rama `feature/F-002-plan-vigente`

Implementar la serie PLAN_VIGENTE en capa cierre: para meses pasados, datos de fase 0 (Previsto); para meses futuros, la última versión del master vigente (conext cod='15'). Exponer vista para Power BI. Respetar semántica importe_origen/importe_mes.

### F-012 · Auditoria y limpieza de Azure para reducir costes

estado **pendiente** · prioridad 16 · SDD no · rama `feature/F-012-auditoria-costes-azure`

Revisar todo lo desplegado en la suscripcion Ruesma, cuantificar en que se va el gasto y retirar lo que no sirve. Parte del inventario de F-009 (docs/referencia/04_azure_inventario_dev.md), que ya identifico recursos huerfanos: el resto de rg-sigridetl-dev-data tras borrar su base (Function App sin funciones, storage, Key Vault, Log Analytics, App Insights), un Recovery Services vault que no protege ningun elemento, y rg-pericial-bc en westeurope, fuera de la region unica del diseno. La auditoria es de solo lectura; CADA borrado necesita aprobacion explicita del humano, recurso a recurso.

### F-013 · Cargar los Excels auxiliares a la capa aux

estado **pendiente** · prioridad 17 · SDD sí · rama `feature/F-013-carga-excels-aux`

FEATURE FUTURA, aplazada por el humano el 2026-08-08. Volcar a la base los tres Excels auxiliares que F-004 deja leidos y validados, creando las tablas destino de la capa aux y definiendo las reglas de negocio que las relacionan con mart. Estructura ya inspeccionada: TipoCoste 108 filas (ide, Nombre, subtipo, tipo); TipoPartida 864 filas (codigo partida, codigo obra, ide_tipo, ide); mapeo_proporcionales 2408 filas (codigo_obra, ide, tipo de coste, porcentaje). Son ~3400 filas en total, asi que el reto no es el volumen sino acordar el modelo destino y para que se usa cada columna. Propuesta del lider, pendiente de acordar: aux.tipo_coste, aux.tipo_partida y aux.mapeo_proporcionales con carga replace transaccional.

### F-010 · Carga y mantenimiento de los Excels auxiliares en Azure

estado **pendiente** · prioridad 18 · SDD sí · rama `feature/F-010-carga-excels-auxiliares`

Mecanismo para que una persona de negocio suba y actualice los Excels auxiliares (TipoPartida, TipoCoste, mapeo_proporcionales) en Azure sin pasar por un técnico ni por un despliegue: a través de la app web de F-007 o del sistema equivalente que se diseñe. Incluye autorización de quién puede subir, validación del fichero antes de aceptarlo (columnas esperadas), versionado o histórico de la subida, y visibilidad de qué versión está usando el ETL. F-004 no depende de esta feature: para F-004 basta con que el ETL lea del blob, aunque el fichero se suba a mano.

### F-007 · Disparo manual de la actualización desde web

estado **pendiente** · prioridad 19 · SDD sí · rama `feature/F-007-disparo-manual-web`

Más adelante, no ahora. Botón en una app web (o sistema equivalente) para que usuarios autorizados lancen una actualización total o parcial del datamart bajo demanda, además de la nocturna programada. Requiere autenticación y autorización (Entra ID), disparo del Container Apps Job con parámetros de alcance, control de ejecuciones concurrentes y visibilidad del estado de la ejecución. Depende de que el ETL admita alcance parcial por CLI.

### F-001 · Comando 'version' en el CLI

estado **terminada** · prioridad 1 · rigor `estandar` · SDD no · rama `feature/F-001-cli-version`

Añadir 'python main.py version' que imprima la versión del ETL, la fecha de build y el tag de imagen (si viene por entorno). Feature de calentamiento del arnés y, a la vez, herramienta de diagnóstico imprescindible para saber qué imagen corre en Azure.

### F-009 · Inventario del entorno Azure existente

estado **terminada** · prioridad 2 · rigor `documental` · SDD no · rama `feature/F-009-inventario-azure`

Antes de añadir la base de datos del datamart, revisar qué hay ya montado en Azure y dejarlo documentado: suscripción y resource groups, redes virtuales y peerings, VPN gateway y su estado, Azure Firewall, storage accounts, Key Vaults, registros de contenedores, y qué contienen hoy rg-seguimiento-dev y rg-sigrid-dev-data-api. Sirve para no duplicar infraestructura ni contradecir el diseño de la landing zone de acens, y para cerrar decisiones abiertas del bloque Azure.

### F-005 · Postgres del datamart en Azure

estado **terminada** · prioridad 3 · rigor `critico` · SDD sí · rama `feature/F-005-postgres-azure`

CORREGIDO 2026-08-08 tras el inventario de F-009: NO se aprovisiona ningun servidor. Se reutiliza psql-albaranes-rs9k2 (PostgreSQL 16, Standard_B1ms, 32 GB), que ya sirve a albaranes y partes, creando dentro la base sigrid_dm. Cubre: esquemas por capa, un rol de grupo propietario para el ETL (sigrid_dm_etl) y un rol de solo lectura para el MCP (mcp_sigrid_dm_ro), reglas de firewall, carga inicial completa con medicion de tiempos por paso, y verificacion de que las vistas de consumo responden igual que en local. Autenticacion: el humano descarto el 2026-08-08 habilitar Entra en el servidor porque es una operacion de servidor que afectaria a albaranes y partes, ambas en uso; se aplica el plan B previsto en la spec, roles nativos con contrasena en Key Vault, igual que hacen esas dos bases. El modo PG_AUTH_MODE=entra queda implementado y probado pero inactivo. Puertas bloqueantes: comprobar espacio libre antes de la carga y desactivar el auto-bootstrap PG_AUTO_CREATE_DB contra un servidor compartido de produccion.

### F-014 · Arnes generico versionado, reutilizable en cualquier proyecto

estado **terminada** · prioridad 4 · rigor `estandar` · SDD no · rama `feature/F-014-arnes-generico`

Extraer de este proyecto un arnes generico que se pueda instalar en cualquier repositorio, nuevo o en marcha, y que sea VERSIONADO para que las mejoras se propaguen. Ya existe C:/Users/pgris/PycharmProjects/arnes-base con un snapshot del 2026-08-08 a las 13:01 y un instalar_arnes.ps1 que copia sin pisar lo existente; el problema es que NO es un repositorio git y ya nacio obsoleto: le faltan las cinco mejoras de esa misma tarde (regla de las dos paradas con el humano en CLAUDE.md/leader.md/implementer.md, C3 bis de CHECKPOINTS.md para documentos que entran de fuera, la nota sobre como revisar features sdd=false, el .gitignore que bloquea originales en PDF y ofimatica, y las convenciones de docs/referencia). Cinco mejoras perdidas en una tarde: eso es lo que esta feature tiene que dejar de pasar.

### F-004 · Ejecutar el ETL en Azure sin dependencias locales

estado **terminada** · prioridad 5 · rigor `estandar` · SDD sí · rama `feature/F-004-etl-sin-dependencias-locales`

CORREGIDO 2026-08-08 tras la spec: la premisa anterior era falsa. LoadExcelAuxStep NO lee hoy ficheros locales: es un stub que devuelve SKIPPED, y las variables AUX_EXCEL_* existen en config/settings.py pero nadie las lee, asi que el pipeline no esta roto hoy en un contenedor por este motivo. La feature construye la CAPACIDAD de lectura: que el step resuelva los tres Excels auxiliares indistintamente desde ruta local o desde Azure Blob Storage con identidad gestionada, los abra y valide que son legibles. NO los carga a aux.*: las tablas destino no existen y el esquema de los ficheros no esta en el repositorio (ver DA-4.1). Incluye auditar el resto de steps en busca de dependencias del sistema de ficheros local.

### F-015 · Verificar que los tests son de verdad: mutacion, fase RED, cobertura y niveles de rigor

estado **terminada** · prioridad 6 · rigor `estandar` · SDD sí · rama `feature/F-015-verificar-tests`

Hoy el arnes comprueba que los tests PASAN, pero nada comprueba que sean tests de verdad. Un test que pasa siempre es peor que no tener test: da falsa tranquilidad y ademas cuesta mantenerlo. Adoptado del arnes de Uncle Bob (github.com/betta-tech/harness-sdd, rama uncle-bob-harness) y de la skill old-coder (github.com/AmazingAng/old-coder), cuya tesis es que el humano no revisa codigo sino evidencias: un plan de pruebas antes y un informe con numeros reales despues. Precedente propio: el implementer de F-005 inyecto una contrasena falsa en .env.example para comprobar que el barrido de secretos saltaba. Eso ya es mutation testing sobre un test; esta feature lo generaliza. NO se adopta Gherkin: ya tenemos requisitos EARS con test trazable (test_fXXX_rN_*), que da la misma trazabilidad sin un tercer artefacto que mantener. NO se adopta que el reviewer pueda podar features: las features salen de decisiones de negocio del humano. Es una mejora GENERICA: se porta a arnes-base en el mismo trabajo.

### F-020 · Arnes multi-servicio: preparar arnes-base para monorepos de varias apps/servicios

estado **terminada** · prioridad 8 · rigor `estandar` · SDD sí · rama `feature/F-020-arnes-multiservicio`

Creada el 2026-08-10 a peticion del humano, con prioridad maxima tras F-003. Motivo: las apps del ecosistema (albaranes, partes, portal) estan hoy repartidas en varios repos por servicio (albaranes son 6: infra, ingesta email, api, persistencia...) y van a unificarse en UN monorepo por app via git subtree, con UN arnes en la raiz que cubra features que cruzan servicios. El arnes actual asume un unico proyecto Python en la raiz: harness/init.sh hace un solo compileall/pytest, y hay que adaptarlo para descubrir y validar varios servicios (cada uno con su venv, sus tests y posiblemente lenguajes distintos), degradando con elegancia en los que no sean Python. Alcance: (1) init.sh multi-servicio en arnes-base, configurable (p. ej. clave services en un fichero del arnes o autodescubrimiento por subcarpetas con marcador), (2) verificar que harness/alcance-cobertura-mutacion funcionan con rutas de subcarpetas de servicios (trabajan sobre git diff contra dev con rutas relativas a la raiz, en principio si), (3) instalador y GUIA_INSTALACION.md actualizados con el camino monorepo multi-servicio, (4) subida de version del arnes (1.3.0) y prueba real contra una estructura de varios servicios (fixture o el piloto de albaranes), (5) este repositorio datamart NO cambia de estructura: solo recibe la mejora de init.sh si le aplica. La migracion de cada app a monorepo (subtrees, pipelines, azure-apps) NO es de esta feature: es trabajo en los repos de cada app, con esta feature como prerrequisito.

### F-019 · Build de stg.plan_mensual por tramos: caber en el servidor compartido

estado **terminada** · prioridad 9 · rigor `critico` · SDD sí · rama `feature/F-019-plan-mensual-por-tramos`

Creada el 2026-08-09: es la OPCION B elegida por el humano tras el incidente de esa noche (ver current.md): stg/08_plan_mensual.sql explota raw.obrparpre (13,76 M filas) con CROSS JOIN LATERAL unnest(...) y en el Standard_B1ms (2 GB RAM) derrama 16+ GB de temporales al disco compartido de 32 GB, que se llego a llenar al 93,4% y puso el servidor en solo-lectura 10 minutos afectando potencialmente a albaranes y partes. Objetivo: reescribir el build de plan_mensual por tramos (por obra, ejercicio u otro corte que la spec justifique con numeros) para acotar el pico de temporales y WAL, de forma que el build completo quepa con margen en el servidor actual. La spec debe empezar midiendo (tamano del resultado final, pico por tramo estimado) y fijar un limite de seguridad de disco. Incluye la verificacion en Azure (relanzar stage + build-mart + apply-grants, ejecucion del humano) que completa el paso 8 de F-005, y desbloquea armar la programacion del job de F-003. Descartadas por ahora: opcion A (crecer disco, irreversible y sobre servidor compartido) y opcion C (subir SKU).

### F-016 · Refuerzo de tests para los huecos de riesgo alto de F-005

estado **terminada** · prioridad 10 · rigor `estandar` · SDD no · rama `feature/F-016-refuerzo-tests-f005`

Creada el 2026-08-09 por decision del humano tras la linea base de mutacion de F-015 (progress/mutacion_F-005.md): 101 mutantes sobre las lineas de F-005, 55 supervivientes (45,5%), de los que 6 son de riesgo ALTO. F-005 esta declarada rigor critico y hoy no pasaria su propio nivel. Esta feature cierra SOLO los 6 huecos de riesgo alto: (1) el valor por defecto de auto_create_db en config/settings.py y postgres_client.py, la puerta bloqueante contra el servidor compartido de produccion; (2) el autocommit de la conexion administrativa, sin el que CREATE DATABASE falla; (3) la igualdad de textos y la clasificacion de una diferencia como FALLO en fingerprint.py; (4) la deteccion de un paso fallido del pipeline en main.py, que invertida daria por buena una ejecucion fallida. Los 27 huecos de riesgo medio y los 14 de riesgo bajo quedan fuera como deuda anotada.

### F-008 · Documentación de referencia: tablas de Sigrid, landing zone de acens y sigrid-api

estado **terminada** · prioridad 20 · rigor `documental` · SDD no · rama `feature/F-008-docs-referencia-sigrid-acens`

Incorporar a docs/referencia/ tres documentos que hoy viven fuera del repositorio: (1) la información de tablas del sistema origen Sigrid, base para entender y auditar la ingesta y config/tables_sigrid.yaml; (2) el documento de acens sobre cómo han montado la landing zone de Azure, contexto necesario para el bloque F-005/F-003; (3) la documentación del microservicio sigrid-api, único punto de acceso a la BBDD de Sigrid y a quien llama etl_sigrid/infrastructure/sigrid/. Los dos primeros llegan en PDF y se convierten con la herramienta MCP markitdown según la regla de CLAUDE.md; el tercero llega ya en Markdown. Los originales NO se versionan.
