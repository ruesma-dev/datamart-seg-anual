<!-- BACKLOG.md -->
# Backlog

**Fichero generado por `harness/backlog.py` a partir de `harness/features.json`. No lo edites a mano**: edita el JSON y vuelve a generarlo (lo hace solo `bash harness/init.sh`).

Resumen: **22 features**, 12 abiertas, 10 terminadas.

Bloqueadas: **F-003**.

## Trabajo abierto

| # | Feature | Prioridad | Estado | Rigor | Rama |
|---|---|---|---|---|---|
| F-003 | Infra: despliegue como Container Apps Job diario | 7 | bloqueada | critico | `feature/F-003-infra-caj` |
| F-025 | Ventana de negocio: acotar el build de stg y mart a lo que se mueve | 10 | pendiente | critico | `feature/F-025-ventana-negocio-build` |
| F-011 | Carga incremental del datamart | 11 | spec lista | critico | `feature/F-011-carga-incremental` |
| F-017 | Cierre mensual: incorporar los costes indirectos (CI) | 12 | pendiente |  | `feature/F-017-cierre-costes-indirectos` |
| F-022 | Desempatar versiones master duplicadas de raw.obrfasamb | 12 | pendiente | estandar | `feature/F-022-desempate-obrfasamb` |
| F-018 | Validar los numeros de cierre.fact_cierre_mensual | 13 | pendiente |  | `feature/F-018-validacion-cierre-mensual` |
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

### F-025 · Ventana de negocio: acotar el build de stg y mart a lo que se mueve

estado **pendiente** · prioridad 10 · rigor `critico` · SDD sí · rama `feature/F-025-ventana-negocio-build`

Extraida de F-011 el 2026-08-18 por decision del humano: la definicion de 'obra abierta' (DA-1 de F-011) queda SIN DECIDIR y es de Negocio, asi que el bloque C de F-011 sale de aquella feature y se hace mas adelante en esta. Motivo de peso para priorizarla: la medicion de la carga del 18-ago demuestra que build_stg se lleva 111 de los 165 min (67 %) y build_mart 21 (13 %), mientras la ingesta son 33 (20 %); acotar el build rinde mas que la ingesta incremental. Cambia QUE VE Power BI, no solo cuanto tarda, asi que exige prueba de equivalencia como la que hizo F-019 con el troceado. No se toca el build por tramos de F-019 sin esa prueba. Por DA-5 de F-011 va con prioridad por encima del bloque B de F-011 si la medicion lo confirma.

### F-011 · Carga incremental del datamart

estado **spec lista** · prioridad 11 · rigor `critico` · SDD sí · rama `feature/F-011-carga-incremental`

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
