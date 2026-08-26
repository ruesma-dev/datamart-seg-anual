<!-- docs/runbook_postgres_azure.md -->
# Runbook · Postgres del datamart en Azure

Todo lo que hay aquí lo ejecuta **una persona**, a mano, con la sesión de `az`
iniciada. Ningún agente del arnés ejecuta nada de este documento: la
implementación de F-005 dejó el código y los scripts, no tocó Azure.

> **Lo primero que hay que entender.** No se aprovisiona ningún servidor. Se
> crea la base `sigrid_dm` **dentro de `psql-albaranes-rs9k2`**, que ya sirve a
> `albaranes` y `partes`, **las dos en uso**. Cualquier error de alcance afecta
> a dos aplicaciones vivas.

| | |
|---|---|
| Servidor | `psql-albaranes-rs9k2.postgres.database.azure.com` |
| Resource group | `rg-albaranes-dev` (`spaincentral`) — **no** es el del datamart |
| Versión / SKU | PostgreSQL 16 · `Standard_B1ms` (1 vCPU, 2 GB RAM) |
| Almacenamiento | 32 GB **compartidos** con `albaranes` y `partes` |
| Red | Endpoint público con reglas de firewall por IP |
| HA / Backup | Sin HA · PITR 7 días, **de servidor entero** |

## 0. Prohibido sin decisión escrita y explícita

- Tocar `albaranes` o `partes`: DDL, DML, `REVOKE`, `ALTER`.
- `ALTER SYSTEM` o `az postgres flexible-server parameter set`.
- Cambiar el SKU o el almacenamiento. **Ampliar almacenamiento es
  irreversible**: el disco de un Flexible Server solo crece, nunca decrece, y
  la factura sube para siempre.
- Borrar o modificar reglas de firewall existentes.
- Reiniciar el servidor.

## 1. Autenticación: qué se decidió y por qué

**No se habilita la autenticación de Microsoft Entra en el servidor.**
Decisión del humano del 2026-08-08: habilitarla es una operación **de
servidor**, no de base, y `albaranes` y `partes` están en uso —
«podemos seguir como hasta ahora».

Se aplica el **plan B**, que es además lo que ya hacen esas dos bases: **roles
nativos de PostgreSQL con contraseña, y la contraseña en Key Vault**.

| Rol | Tipo | Para qué |
|---|---|---|
| `sigrid_dm_etl` | Grupo, `NOLOGIN` | **Propietario** de la base y de todos sus objetos |
| `sigrid_dm_app` | `LOGIN` + contraseña | El ETL: el puesto del humano y el job de F-003. Miembro de `sigrid_dm_etl` |
| `mcp_sigrid_dm_ro` | `LOGIN` + contraseña | Solo lectura, para el MCP (F-006) |

Por qué un grupo propietario y no un rol a secas: los objetos se crean siempre
como `sigrid_dm_etl` gracias a `PG_SET_ROLE`. Si mañana entra un segundo
principal —la identidad gestionada del job, o la cuenta de otro operador—
podrá recrear las vistas del primero. Sin eso, el segundo no podría hacer
`DROP` sobre lo que creó el primero, y **las vistas se recrean en cada
ejecución del ETL**.

El código admite `PG_AUTH_MODE=entra` y está probado, pero **hoy no se usa**.
Si algún día se habilita Entra en el servidor, el cambio es de configuración,
no de código.

## 2. Recuperación: el backup del servidor NO sirve para este datamart

**La recuperación de `sigrid_dm` es volver a ejecutar el ETL, no restaurar.**

No es una preferencia. El PITR de un Flexible Server restaura **el servidor
completo** a un instante pasado: restaurar `sigrid_dm` arrastraría `albaranes`
y `partes` al pasado, lo cual es inaceptable. Y no hay HA.

Para este datamart, por tanto, **el backup del servidor no es un mecanismo de
recuperación utilizable**. Lo que sí lo es: `sigrid_dm` es regenerable al
100 % desde Sigrid ejecutando el pipeline. Que nadie asuma otra cosa.

## 3. Puerta de espacio — antes de nada

32 GB compartidos. Sigrid son ~4 GB en origen, y `raw` + `stg` + `mart` con
índices proyecta **10-12 GB**.

```bash
# Fotografía previa del servidor (solo lectura). Guarda las salidas.
az postgres flexible-server show -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o json
az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table

# Espacio: métrica del servidor y tamaño por base
az monitor metrics list \
  --resource $(az postgres flexible-server show -g rg-albaranes-dev -n psql-albaranes-rs9k2 --query id -o tsv) \
  --metric storage_percent --interval PT1H -o table

psql "host=psql-albaranes-rs9k2.postgres.database.azure.com dbname=postgres user=<admin> sslmode=require" \
     -f infra/sql/03_diagnostico.sql
```

**Si quedan menos de 14 GB libres, PARA.** 12 GB de proyección más 2 GB de
margen. Anótalo en `progress/current.md`, marca la feature `blocked` y decide.
Ampliar almacenamiento es irreversible.

## 4. Contraseñas: generarlas y guardarlas en Key Vault

Ninguna contraseña se escribe en el repositorio, ni en `specs/`, ni en
`progress/`, ni en `.env.example`, ni en un `.ps1`.

```bash
# Generar y guardar en Key Vault (ajusta el nombre del vault)
az keyvault secret set --vault-name <kv> --name pg-sigrid-dm-app --value "$(openssl rand -base64 32)"
az keyvault secret set --vault-name <kv> --name pg-mcp-sigrid-dm-ro --value "$(openssl rand -base64 32)"

# Recuperarlas a variables de entorno de ESTA sesión, para el paso siguiente
export APP_PWD=$(az keyvault secret show --vault-name <kv> --name pg-sigrid-dm-app --query value -o tsv)
export MCP_PWD=$(az keyvault secret show --vault-name <kv> --name pg-mcp-sigrid-dm-ro --query value -o tsv)
```

Dos avisos que no son formalismo:

- `ALTER ROLE ... PASSWORD` puede quedar en el log del servidor si
  `log_statement` está en `all`. Por eso las contraseñas van por **variable de
  psql desde un fichero**, nunca escritas en la línea de comandos, y por eso
  conviene comprobar el valor de `log_statement` antes (no cambiarlo: es
  parámetro de servidor).
- La contraseña del MCP **la custodia F-006**. Aquí solo se crea el rol.

## 5. Crear la base y los roles

Los scripts son idempotentes: se pueden reejecutar. Reejecutar `02_roles.sql`
es además la forma de **rotar** las contraseñas.

```powershell
# PowerShell, desde infra/
. .\00_vars.ps1
$env:PG_ADMIN_USER = "<admin del servidor>"

# 1) Plan + diagnóstico. NO escribe nada.
.\15_provision_db.ps1

# 2) Solo cuando la puerta de espacio esté pasada y las contraseñas en Key Vault
.\15_provision_db.ps1 -Ejecutar
```

O directamente con `psql`:

```bash
psql "host=<host> dbname=postgres user=<admin> sslmode=require" \
     -v ON_ERROR_STOP=1 -f infra/sql/01_create_database.sql
psql "host=<host> dbname=sigrid_dm user=<admin> sslmode=require" \
     -v ON_ERROR_STOP=1 -v app_pwd="$APP_PWD" -v mcp_pwd="$MCP_PWD" \
     -f infra/sql/02_roles.sql
```

Qué debe salir: `sigrid_dm` con propietario `sigrid_dm_etl`, los tres roles,
`sigrid_dm_app` dentro de `sigrid_dm_etl`, y **los nueve esquemas** (`raw`,
`stg`, `aux`, `mart`, `_meta`, `cierre`, `compras`, `maestro`,
`retenciones`).

**Comprobación obligatoria después**: que `albaranes` y `partes` siguen
conectando y que el listado de reglas de firewall es **exactamente** el de
antes.

### 5 bis. Riesgo aceptado: `CONNECT` a `PUBLIC` en las otras bases

Una base propia impide las **consultas** entre bases —PostgreSQL no las
permite—, pero **no impide conectar**: `CONNECT` está concedido a `PUBLIC` por
defecto. Es decir, `mcp_sigrid_dm_ro` **puede abrir sesión contra `albaranes` y
`partes` y leer su catálogo** (nombres de tablas y columnas), aunque no los
datos de sus tablas.

Cerrar esa rendija exigiría `REVOKE CONNECT ON DATABASE albaranes FROM PUBLIC`,
que **toca otra base**. El humano lo descartó el 2026-08-08 por el mismo motivo
que Entra: no romper aplicaciones en uso.

**Queda como riesgo aceptado y anotado.** Si en algún momento el catálogo de
`albaranes` (que contiene precios de proveedor y datos bancarios) se considera
sensible por sí mismo, la conversación a tener es sobre ese `REVOKE`, con el
diagnóstico de `datacl` del bloque 2 de `03_diagnostico.sql` delante.

## 6. Firewall

El servidor ya tiene la IP pública de la sede y una regla de puesto individual.
**Primero se comprueba si la IP ya está cubierta**; solo se crea regla si no lo
está. La convención de nombre fechado que sigue vale para servicios y sedes; el
puesto de trabajo es la excepción y tiene su propio procedimiento en **6 bis**.

```bash
az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table
# Solo si hace falta: una IP por regla (start == end), con el nombre fechado
az postgres flexible-server firewall-rule create -g rg-albaranes-dev --server-name psql-albaranes-rs9k2 \
  --name <uso>-<origen>-<AAAA-MM-DD> --start-ip-address <IP> --end-ip-address <IP>
az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table
```

> **Ojo a la asimetria entre subcomandos, que muerde y ya costo media hora el
> 2026-08-19.** En `create`, `update` y `delete` el servidor va en
> `--server-name`/`-s` y la regla en `--name`/`-n`; **`--rule-name` no existe**
> en esta CLI y devuelve «unrecognized arguments». En `list`, en cambio, el
> `-n` **si** es el servidor y esta bien: no lo corrijas. Estos comandos
> estaban escritos con `--rule-name` hasta el 2026-08-19 y **no ejecutaban**.

El listado posterior debe contener **exactamente** las reglas anteriores más la
nueva. Ninguna preexistente puede quedar modificada ni eliminada.

**La regla del MCP no es la de un puesto de trabajo.** F-006 cambió el
2026-08-08: el MCP pasa a ser un servicio en cloud, multi-base, en su propio
repositorio. Lo que necesitará es la **IP de salida del entorno de Container
Apps** donde se despliegue, no la IP de un PC. No se crea aquí: se crea cuando
ese entorno exista y se conozca su IP estática de salida (**6 ter**).

**Estas reglas caducan de hecho.** Una regla de IP deja de servir en cuanto la
IP de salida cambia —un reinicio del router, un cambio de operador, un portátil
en otra red— y entonces el síntoma es un *timeout* de conexión, no un error de
permisos. Procedimiento de retirada, que hay que aplicar sin esperar a que
moleste:

- cuando un puesto o servicio deje de necesitar acceso, **borra su regla** con
  `az postgres flexible-server firewall-rule delete -g <grupo> --server-name <servidor> --name <nombre>`;
- revisa el listado cada vez que pases por este runbook y borra las que no
  reconozcas: el nombre lleva fecha justamente para eso. La excepción, otra vez,
  es la regla única del puesto de **6 bis**, que no caduca porque se reescribe.

### 6 bis. El puesto: una regla única, sin fecha, que se reescribe

Es la **única** excepción al nombre fechado, y conviene entender por qué antes
de replicarla. La IP pública del puesto de trabajo **rota cada pocos minutos**
(el operador da direccionamiento **CGNAT**, compartido y sin garantía de
permanencia): durante una sola tanda de F-006 hubo que rehacer la autorización
**seis veces**. Con la convención fechada, eso deja seis reglas muertas en un
servidor de producción compartido, que es exactamente lo que nadie va a
auditar dentro de seis meses.

Así que el puesto tiene **una regla única y sin fecha**, `datamart-puesto-pgris`,
y lo que se hace con ella es que **se reescribe** con la IP del momento: no se
crean reglas nuevas por cada IP, y no se tocan las ajenas. `psql-albaranes-rs9k2`
lo comparten `albaranes` y `partes`, las dos **en producción**; sus reglas no
son nuestras y borrarlas o modificarlas los deja fuera.

```bash
# 1) La IP de salida de ahora mismo
curl -s https://api.ipify.org

# 2) Reescribirla. Si la regla aún no existiera, el mismo comando con `create`.
az postgres flexible-server firewall-rule update -g rg-albaranes-dev --server-name psql-albaranes-rs9k2 --name datamart-puesto-pgris --start-ip-address <IP> --end-ip-address <IP>

# 3) El listado posterior debe ser el de antes, con esa única regla movida
az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table
```

**`-n` es el nombre de la REGLA; el servidor va en `--server-name`.** Los
nombres de parámetro son los que explica `infra/README.md` («Ojo con los
nombres de los parámetros del `create`») y **no se copian aquí**: `--rule-name`
no existe y devuelve «unrecognized arguments», y en el `list` de la tercera
línea `-n` **sí** es el servidor. Es la asimetría de la CLI, no un descuido.

**Y esta vía no sirve para un servicio desplegado.** Funciona solo porque hay
una persona delante relanzando el comando antes de cada tanda. Un job o un
contenedor no pueden perseguir una IP que rota: necesitan lo de 6 ter.

### 6 ter. El entorno del MCP: IP de salida estática (F-006)

**La regla del MCP no se crea persiguiendo ninguna IP.** El patrón bueno ya
está probado con el ETL: el entorno de Container Apps `cae-datamart-seg-dev` se
creó **sin integración de red virtual a propósito**, y es esa decisión —y no
otra— la que le da **IP de salida estática**; su autorización en el firewall es
la regla `caj-datamart-seg-dev`. El MCP repite el patrón: entorno propio sin
VNet, se lee su `properties.staticIp` y se crea **una** regla con el nombre del
entorno.

```bash
az containerapp env show -g <rg del MCP> -n <entorno> --query properties.staticIp -o tsv
az postgres flexible-server firewall-rule create -g rg-albaranes-dev --server-name psql-albaranes-rs9k2 --name <entorno> --start-ip-address <IP> --end-ip-address <IP>
az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table
```

Tres advertencias que no son formalismo:

- **Se escribe sobre un recurso de otro proyecto.** `rg-albaranes-dev` no es del
  datamart. La autorización la da el humano recurso a recurso y **la ejecuta
  él**; ningún agente del arnés lanza esto.
- **No se depende de la regla que autoriza a cualquier recurso de Azure.** El
  servidor tiene una, y autoriza también a suscripciones ajenas. Que el MCP
  conecte gracias a ella no significa que esté autorizado: significa que la
  puerta está abierta para todos. Ver `infra/README.md`.
- **Mientras el entorno del MCP no exista, esta regla no se crea.** Hoy el MCP
  corre en el puesto y entra por la de 6 bis, que es también el motivo de que
  «un MCP que use cualquiera desde cualquier puesto» siga sin estar cumplido.

## 7. Configuración del ETL contra Azure

En el `.env` del puesto (o en las variables del job de F-003):

```
PG_HOST=psql-albaranes-rs9k2.postgres.database.azure.com
PG_PORT=5432
PG_DB=sigrid_dm
PG_USER=sigrid_dm_app
PG_PASSWORD=            # desde Key Vault, NUNCA escrita en el repositorio
PG_SSLMODE=require
PG_AUTH_MODE=password
PG_AUTO_CREATE_DB=false
PG_SET_ROLE=sigrid_dm_etl
PG_READONLY_ROLE=mcp_sigrid_dm_ro
```

Las tres que importan y por qué:

- **`PG_AUTO_CREATE_DB=false`**: el auto-bootstrap del ETL se conecta a la base
  `postgres` y ejecuta `CREATE DATABASE` si la suya no existe. Contra un
  servidor de producción compartido, eso es un fallo esperando a ocurrir. Con
  `false`, si la base no está, el ETL falla y remite a este runbook.
- **`PG_SET_ROLE=sigrid_dm_etl`**: sin esto los objetos nacen con otro
  propietario y el siguiente proceso no puede recrearlos.
- **`PG_SSLMODE=require`**: contra un host de Azure, la configuración **aborta**
  si se pone `disable`, `allow` o `prefer`. El endpoint es público.

Comprobación: `python main.py check-pg`.

## 8. Carga inicial

```bash
python main.py check-pg
python main.py run-all --full
python main.py build-cierre
python main.py build-maestros
python main.py build-compras
python main.py build-retenciones
python main.py apply-grants
```

**El `apply-grants` final no es opcional.** `run-all` compone solo
`ingest → load_aux → stage → build_mart → apply_grants`; `cierre`, `compras`,
`maestro` y `retenciones` van en comandos aparte y **también recrean vistas con
`DROP VIEW ... CASCADE`**. Un `DROP` se lleva los `GRANT` por delante, así que
sin ese último `apply-grants` el MCP se queda sin ver esas cuatro capas.

## 9. Medición y veredicto sobre el SKU

```bash
python main.py timings --last 1
psql "host=<host> dbname=sigrid_dm user=<admin> sslmode=require" -f infra/sql/03_diagnostico.sql
```

Escribe `progress/medicion_carga_inicial.md` con la tabla de tiempos por paso,
el tamaño final por esquema y **una conclusión explícita**: `Standard_B1ms`
aguanta, o hay que escalar. Ese fichero es la entrada de F-011.

Contexto para interpretar los números: es un SKU *Burstable*. Agota créditos de
CPU, así que una carga larga puede empezar rápida y caer a la línea base a
mitad de ejecución; si los tiempos por paso crecen según avanza la noche, esa
es la explicación. Escalar el SKU es una operación en caliente con un
reinicio, no una migración.

## 10. Verificación de que las vistas responden igual que en local

Con el **mismo commit** del repositorio a los dos lados:

```bash
# Antes de tocar Azure, contra el Postgres local
python main.py fingerprint-views --out progress/fingerprint_local.csv --periodo-hasta AAAA-MM
# Después de la carga, contra Azure
python main.py fingerprint-views --out progress/fingerprint_azure.csv --periodo-hasta AAAA-MM
python main.py compare-fingerprints progress/fingerprint_local.csv progress/fingerprint_azure.csv
```

Criterio, y por qué no es «que dé lo mismo»: Sigrid está vivo y las dos
capturas no son del mismo instante.

| Bloque | Criterio |
|---|---|
| estructura | idéntica; cualquier diferencia de nombre, orden o tipo es **FALLO** |
| cerrado · `COUNT(*)` | exacto; cualquier diferencia es **FALLO** |
| cerrado · sumas | `abs(a-b) <= max(0,01, abs(a)*1e-9)` |
| vivo | las diferencias se informan como **AVISO** |

`AAAA-MM` es el último mes **cerrado**, que lo fija el humano. Los meses
cerrados son inmutables por definición de negocio (`fas=1..N` son cierres), y
por eso ahí la igualdad exacta significa algo. El bloque vivo cambia entre
capturas; ahí cae también `mart.v_pbi_dim_fecha`, que se genera con
`CURRENT_DATE` y difiere **por construcción** según el día.

El comando sale con código distinto de 0 si hay algún FALLO.

Y por último, lo que ninguna huella comprueba: **abrir el informe de Power BI
contra `sigrid_dm` en Azure y refrescarlo** sin errores de origen de datos ni
columnas ausentes.

## 11. Comprobación de la frontera de seguridad

```bash
# El rol del MCP no puede escribir
psql "host=<host> dbname=sigrid_dm user=mcp_sigrid_dm_ro sslmode=require" \
     -c "INSERT INTO mart.fact_seguimiento_mensual VALUES (1);"   # permission denied

# Ni leer datos de las otras bases
psql "host=<host> dbname=albaranes user=mcp_sigrid_dm_ro sslmode=require" \
     -c "\dt"    # conecta (ver §5 bis) pero ninguna tabla debe ser legible
```

**Alcance de lectura**: por decisión del humano del 2026-08-08 el MCP lee
**todos** los esquemas de `sigrid_dm`, incluidos `raw` y `stg`, no solo los
cinco de consumo. Se revisará al rediseñar el MCP en F-006. La lista efectiva
es el parámetro `PG_CONSUMPTION_SCHEMAS`: estrecharla es cambiar una variable,
no tocar código.
