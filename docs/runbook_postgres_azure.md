<!-- docs/runbook_postgres_azure.md -->
# Runbook · Postgres del datamart en Azure

Todo lo que hay aquí lo ejecuta **una persona**, a mano, con la sesión de `az`
iniciada. Ningún agente del arnés ejecuta nada de este documento: la
implementación de F-005 dejó el código y los scripts, no tocó Azure.

> **Lo primero que hay que entender.** No se aprovisiona ningún servidor. Se
> crea la base `sigrid_dm` **dentro de `psql-albaranes-rs9k2`**, que ya sirve a
> `albaranes`, `partes`, `dedicacion`, `postventa` y `facturas`, **todas en
> uso**. Cualquier error de alcance afecta a cinco aplicaciones vivas. Eran dos
> cuando se escribió esto: la lista crece sin avisarnos, y el 2026-09-07 una
> base nueva tumbó la nocturna.

| | |
|---|---|
| Servidor | `psql-albaranes-rs9k2.postgres.database.azure.com` |
| Resource group | `rg-albaranes-dev` (`spaincentral`) — **no** es el del datamart |
| Versión / SKU | PostgreSQL 16 · `Standard_B1ms` (1 vCPU, 2 GB RAM) |
| Almacenamiento | **64 GB** (ampliado el 2026-08-29 desde 32) **compartidos** con `albaranes`, `partes`, `dedicacion`, `postventa` y `facturas` |
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
| `mcp_sigrid_dm_ro` | `LOGIN` + contraseña | Solo lectura, el ESTÁNDAR: el MCP (F-006) y Power BI. Sin `raw` ni `contabilidad_restringida` desde F-135 |
| `sigrid_dm_restringido_ro` | Grupo, `NOLOGIN` | El rol AUTORIZADO (F-135): lee la contabilidad completa, `contabilidad_restringida` |
| `mcp_sigrid_dm_total` | `LOGIN` + contraseña, solo en `kv-mcp-bbdd-dev` (`pg-password-total`) | El acceso TOTAL del MCP (F-136): miembro de los dos anteriores, sin GRANT propios y **nunca `raw`**. Alta y rotación: **§12** |

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

64 GB compartidos desde el 2026-08-29 (32 cuando se escribió este runbook y
cuando se ejecutó su puerta de T13, que por eso pide 14 GB libres). Sigrid son
~4 GB en origen, y `raw` + `stg` + `mart` con índices proyecta **10-12 GB**.

```bash
# Fotografía previa del servidor (solo lectura). Guarda las salidas.
az postgres flexible-server show -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o json
az postgres flexible-server firewall-rule list -g rg-albaranes-dev -n psql-albaranes-rs9k2 -o table

# Espacio: métrica del servidor y tamaño por base
az monitor metrics list \
  --resource $(az postgres flexible-server show -g rg-albaranes-dev -n psql-albaranes-rs9k2 --query id -o tsv) \
  --metric storage_percent --interval PT1H -o table

# psql: opciones DELANTE y la cadena de conexión al final (F-136)
psql -X -f infra/sql/03_diagnostico.sql \
     "host=psql-albaranes-rs9k2.postgres.database.azure.com dbname=postgres user=<admin> sslmode=require"
```

**Si quedan menos de 14 GB libres, PARA.** 12 GB de proyección más 2 GB de
margen. Anótalo en `progress/current.md`, marca la feature `blocked` y decide.
Ampliar almacenamiento es irreversible.

## 4. Contraseñas: generarlas y guardarlas en Key Vault

Ninguna contraseña se escribe en el repositorio, ni en `specs/`, ni en
`progress/`, ni en `.env.example`, ni en un `.ps1`.

Desde F-136 (2026-10-13) se generan y se cargan en **Windows PowerShell 5.1**,
sin que el valor pase nunca por la pantalla. Para ROTARLAS, o para dar de alta
el login total, el procedimiento completo es el de la **§12**.

```powershell
# Clave de 64 caracteres hexadecimales: sin + / = ' que rompan una cadena o el .env
function Nueva-Clave {
    $b = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    ($b | ForEach-Object { $_.ToString("x2") }) -join ""
}
$kv = "kv-datamart-seg-dev"
$q = @("--query", "value", "-o", "tsv")

# Guardar en Key Vault: SIEMPRE con -o none, o la CLI devuelve el valor
$v = Nueva-Clave
az keyvault secret set --vault-name $kv --name pg-sigrid-dm-app --value $v -o none
$v = Nueva-Clave
az keyvault secret set --vault-name $kv --name pg-mcp-sigrid-dm-ro --value $v -o none
$v = $null

# Releerlas a variables de entorno de ESTA sesión, sin imprimirlas: 02_roles.sql
# las lee con \getenv. TOTAL_PWD, del vault del MCP (§12).
$env:APP_PWD = az keyvault secret show --vault-name $kv --name pg-sigrid-dm-app @q
$env:MCP_PWD = az keyvault secret show --vault-name $kv --name pg-mcp-sigrid-dm-ro @q
$env:TOTAL_PWD = az keyvault secret show --vault-name kv-mcp-bbdd-dev --name pg-password-total @q
```

Tres avisos que no son formalismo:

- **`psql` con las opciones DELANTE de la cadena de conexión.** En Windows deja
  de leer opciones en cuanto encuentra la cadena: las de detrás las ignora y
  las imprime. Así se expusieron dos contraseñas el 2026-10-12, cuando
  viajaban con `-v`. Desde F-136 ninguna contraseña va en la línea de órdenes:
  `02_roles.sql` las lee del entorno con `\getenv` (psql 15 o posterior).
- `ALTER ROLE ... PASSWORD` puede quedar en el log del servidor: con
  `log_statement = none` (medido el 2026-10-12) uno correcto no llega, pero con
  `log_min_error_statement = error` uno que FALLE sí deja su texto. Por eso
  `02_roles.sql` comprueba antes lo que haría fallar (su guarda) y no se
  cambia ningún parámetro: son de servidor.
- Cada variable es opcional: la que no esté definida deja la contraseña de su
  login SIN CAMBIOS. Solo hace falta la de un login que aún no existe.

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
# Opciones DELANTE, cadena al final; las contraseñas, del entorno (\getenv)
psql -X -v ON_ERROR_STOP=1 -f infra/sql/01_create_database.sql \
     "host=<host> dbname=postgres user=<admin> sslmode=require"
psql -X -v ON_ERROR_STOP=1 -f infra/sql/02_roles.sql \
     "host=<host> dbname=sigrid_dm user=<admin> sslmode=require"
```

Qué debe salir: `sigrid_dm` con propietario `sigrid_dm_etl`, una línea
`<login>: contraseña fijada` (o `SIN CAMBIOS`) por login, los cinco roles,
`sigrid_dm_app` dentro de `sigrid_dm_etl`, **los trece esquemas** (`raw`,
`stg`, `aux`, `mart`, `_meta`, `cierre`, `compras`, `maestro`,
`retenciones`, `personal`, `contabilidad`, `contabilidad_restringida`,
`descompuestos`) y las comprobaciones de F-135 y F-136 del punto 6.

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
psql -X -f infra/sql/03_diagnostico.sql "host=<host> dbname=sigrid_dm user=<admin> sslmode=require"
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
# El rol del MCP no puede escribir (opciones DELANTE de la cadena, F-136)
psql -X -c "INSERT INTO mart.fact_seguimiento_mensual VALUES (1);" \
     "host=<host> dbname=sigrid_dm user=mcp_sigrid_dm_ro sslmode=require"   # permission denied

# Ni leer datos de las otras bases
psql -X -c "\dt" \
     "host=<host> dbname=albaranes user=mcp_sigrid_dm_ro sslmode=require"   # conecta (§5 bis), nada legible
```

**Alcance de lectura**: por decisión del humano del 2026-08-08 el MCP lee
**todos** los esquemas de `sigrid_dm`, incluidos `raw` y `stg`, no solo los
cinco de consumo. Se revisará al rediseñar el MCP en F-006. La lista efectiva
es el parámetro `PG_CONSUMPTION_SCHEMAS`: estrecharla es cambiar una variable,
no tocar código.

**Con dos excepciones, y son TEMPORALES (F-068, 2026-09-07)**: `raw.emp` y
`raw.res` traen datos personales de empleados (DNI, Seguridad Social, cuenta
bancaria, NIF, credenciales) y el rol tiene el `SELECT` revocado sobre ellas.
La lista es `PG_EXCLUDED_TABLES`, y la aplica el propio `apply_grants` cada
noche: no se puede hacer a mano, porque el `GRANT ... ON ALL TABLES IN SCHEMA
raw` de la nocturna siguiente devolvería el permiso. El humano ya decidió
volver a concederlas cuando el MCP tenga control por usuario.

Para comprobar que la revocación está puesta (cero filas es lo correcto):

```sql
SELECT table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'mcp_sigrid_dm_ro'
  AND table_schema = 'raw'
  AND table_name IN ('emp', 'res');
```

## 12. Rotación de contraseñas y alta del login total (F-136)

Una sola sesión de **Windows PowerShell 5.1**, **de día** y sin imprimir nunca un
valor. Rota las contraseñas de `sigrid_dm_app` y `mcp_sigrid_dm_ro`, expuestas
en la terminal el 2026-10-12, y da de alta `mcp_sigrid_dm_total`, el acceso
TOTAL del MCP: lee lo de `mcp_sigrid_dm_ro` más `contabilidad_restringida`, y
**nunca `raw`**. Elegir quién conecta con él es la F-008 de `mcp-bbdd`.

Reglas de esta sección, todas aprendidas en la incidencia del 2026-10-12:

- `psql` con las **opciones delante** y la cadena de conexión al final: en
  Windows deja de leer opciones tras la cadena, las ignora y las imprime.
- Ninguna contraseña en la línea de órdenes de `psql`: `02_roles.sql` las lee
  del entorno con `\getenv`.
- `az keyvault secret set` siempre con `-o none` (si no, la CLI devuelve el
  valor) y `az keyvault secret show` siempre asignado a una variable.
- **El vault antes que la base**: si la sesión muere a medias, el valor bueno
  ya está en el vault y P3 + P4 lo recargan.

| Secreto | Login | Quién lo usa |
|---|---|---|
| `kv-datamart-seg-dev/pg-sigrid-dm-app` | `sigrid_dm_app` | el job (referencia al vault), el `.env` del puesto y `.env.azure.bak` |
| `kv-datamart-seg-dev/pg-mcp-sigrid-dm-ro` | `mcp_sigrid_dm_ro` | copia de referencia; Power BI lo tiene tecleado |
| `kv-mcp-bbdd-dev/pg-password` | `mcp_sigrid_dm_ro` | el MCP en Azure y el `.env` de `mcp-bbdd`. El MISMO valor que el anterior |
| `kv-mcp-bbdd-dev/pg-password-total` | `mcp_sigrid_dm_total` | el MCP, cuando despliegue su F-008. Solo en este vault |

### P0 · Puerta (solo lectura)

Entre las 07:00 y las 21:00 UTC (lejos de la nocturna de las 00:00), sin
ninguna ejecución del job en curso, con el job ya en la imagen que lleva F-136,
`psql` 15 o posterior y el rol `Key Vault Secrets Officer` en los dos vaults
(si un `set` responde `Forbidden`, se para aquí).

```powershell
$rgJ = "rg-datamart-seg-dev"
$job = "caj-datamart-seg-dev"
[DateTime]::UtcNow.ToString("HH:mm")
az containerapp job execution list -g $rgJ -n $job -o table
az containerapp job show -g $rgJ -n $job --query "properties.template.containers[0].image" -o tsv
psql --version
```

### P1 · Variables

Desde la raíz del repositorio, en la rama o la versión que lleva F-136.

```powershell
$env:PG_ADMIN_USER = "<administrador del servidor>"
$kvDm  = "kv-datamart-seg-dev"
$kvMcp = "kv-mcp-bbdd-dev"
$pgh   = "psql-albaranes-rs9k2.postgres.database.azure.com"
$dsn   = "host=$pgh dbname=sigrid_dm user=$env:PG_ADMIN_USER sslmode=require"
$roles = "infra\sql\02_roles.sql"
$q     = @("--query", "value", "-o", "tsv")
# 64 caracteres hexadecimales: sin + / = ' que rompan una cadena de conexión o el .env
function Nueva-Clave {
    $b = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    ($b | ForEach-Object { $_.ToString("x2") }) -join ""
}
```

### P2 · El vault primero

Tres valores nuevos, en memoria. El del estándar va a los DOS vaults con el
mismo valor. Hasta que P4 termine, no se reinicia nada: el job y el MCP leerían
un valor que la base aún no tiene.

```powershell
$v = Nueva-Clave
az keyvault secret set --vault-name $kvDm --name pg-sigrid-dm-app --value $v -o none
if ($LASTEXITCODE -ne 0) { throw "P2: pg-sigrid-dm-app" }
$v = Nueva-Clave
az keyvault secret set --vault-name $kvDm --name pg-mcp-sigrid-dm-ro --value $v -o none
if ($LASTEXITCODE -ne 0) { throw "P2: pg-mcp-sigrid-dm-ro" }
az keyvault secret set --vault-name $kvMcp --name pg-password --value $v -o none
if ($LASTEXITCODE -ne 0) { throw "P2: pg-password" }
$v = Nueva-Clave
az keyvault secret set --vault-name $kvMcp --name pg-password-total --value $v -o none
if ($LASTEXITCODE -ne 0) { throw "P2: pg-password-total" }
$v = $null
```

### P3 · Releer del vault al entorno

Lo que se lleva a la base es lo que hay en el vault, no lo que había en memoria.

```powershell
$env:APP_PWD = az keyvault secret show --vault-name $kvDm --name pg-sigrid-dm-app @q
$env:MCP_PWD = az keyvault secret show --vault-name $kvMcp --name pg-password @q
$env:TOTAL_PWD = az keyvault secret show --vault-name $kvMcp --name pg-password-total @q
$copia = az keyvault secret show --vault-name $kvDm --name pg-mcp-sigrid-dm-ro @q
if ($copia -ne $env:MCP_PWD) { throw "P3: las dos copias del estándar no coinciden" }
$copia = $null
foreach ($n in "APP_PWD", "MCP_PWD", "TOTAL_PWD") {
    if ((Get-Item "Env:$n").Value.Length -ne 64) { throw "P3: $n no mide 64" }
}
```

### P4 · La base

`psql` pide la contraseña del administrador (no se ve al teclearla).

```powershell
psql -X -v ON_ERROR_STOP=1 -f $roles $dsn
```

Esperado: `sigrid_dm_app: contraseña fijada` y lo mismo para `mcp_sigrid_dm_ro` y
`mcp_sigrid_dm_total`; `COMMIT`; los cinco roles con `rolsuper = f`; el total con
exactamente dos pertenencias (`hereda = t`, `set_role = f`), `raw = f`,
`contabilidad_restringida = t`, `contabilidad = t`, `conecta = t` y cero filas
de privilegios propios; y las comprobaciones de F-135. Desde aquí, cada cliente
con el valor viejo falla al abrir conexión: P6, P7 y P8 sin pausa.

### P5 · Fuera del entorno

```powershell
Remove-Item Env:APP_PWD, Env:MCP_PWD, Env:TOTAL_PWD
```

### P6 · El MCP

Grupo y nombre en `azure-apps/mcp_bbdd.md`. Lee `pg-password` por referencia al
vault al arrancar: se reinicia su revisión activa y se comprueba que responde.
Si su log dice `password authentication failed`, la referencia aún sirve la
versión vieja: esperar un par de minutos y reiniciar otra vez.

```powershell
$rgM = "rg-mcp-bbdd-dev"
$app = "ca-mcp-bbdd-dev"
$rev = az containerapp show -g $rgM -n $app --query properties.latestReadyRevisionName -o tsv
az containerapp revision restart -g $rgM -n $app --revision $rev -o none
az containerapp logs show -g $rgM -n $app --tail 50
```

### P7 · El puesto

El humano pone el valor nuevo en el `PG_PASSWORD` del `.env` del datamart por el
portapapeles, sin verlo; si el historial del portapapeles (Win+V) está activo,
borra después esa entrada. Borra `.env.azure.bak` (D12): es una copia muerta con
la contraseña vieja de `sigrid_dm_app`. Lo mismo con el `.env` de `mcp-bbdd`,
que usa el estándar (`$kvMcp`, `pg-password`).

```powershell
$v = az keyvault secret show --vault-name $kvDm --name pg-sigrid-dm-app @q
Set-Clipboard -Value $v
$v = $null
# pegar en PG_PASSWORD del .env y guardar; después vaciar el portapapeles
Set-Clipboard -Value " "
python main.py check-pg
Remove-Item .env.azure.bak
```

### P8 · Power BI

En el servicio, en cada modelo semántico que lea `sigrid_dm`: Configuración →
Credenciales del origen de datos → `mcp_sigrid_dm_ro` con el valor nuevo (por el
portapapeles, como en P7, desde `pg-mcp-sigrid-dm-ro`); después «Actualizar
ahora» y comprobar que termina bien. Lo mismo en los Power BI Desktop que tengan
la credencial guardada (Configuración del origen de datos → Editar permisos).

### P9 · La vieja ya no entra

La versión ANTERIOR de cada secreto rotado tiene que ser rechazada. Si P2 se
repitió, la que vale es la de antes de la primera vez. Las versiones se ordenan
en PowerShell: nunca con un `--query` que lleve `&`, `|` o `(`, que rompen `az.cmd`.

```powershell
function Version-Anterior($kv, $nombre) {
    $js = az keyvault secret list-versions --vault-name $kv --name $nombre -o json
    $vs = ($js -join "`n") | ConvertFrom-Json
    ($vs | Sort-Object { [DateTime]$_.attributes.created } -Descending)[1].id
}
$dsnApp = "host=$pgh dbname=sigrid_dm user=sigrid_dm_app sslmode=require"
$dsnMcp = "host=$pgh dbname=sigrid_dm user=mcp_sigrid_dm_ro sslmode=require"
$env:PGPASSWORD = az keyvault secret show --id (Version-Anterior $kvDm pg-sigrid-dm-app) @q
psql -X -c "SELECT 1" $dsnApp
$env:PGPASSWORD = az keyvault secret show --id (Version-Anterior $kvMcp pg-password) @q
psql -X -c "SELECT 1" $dsnMcp
Remove-Item Env:PGPASSWORD
```

Esperado en los dos: `password authentication failed`.

### P10 · Negativa y positiva del total

Con el login total real (R26 y R27). Al acabar, se cierra la ventana: así no
queda ninguna variable de esta sesión.

```powershell
$dsnT = "host=$pgh dbname=sigrid_dm user=mcp_sigrid_dm_total sslmode=require"
$env:PGPASSWORD = az keyvault secret show --vault-name $kvMcp --name pg-password-total @q
foreach ($t in "apu", "pag", "asi", "rac", "hmores", "con", "apa") {
    psql -X -c "SELECT 1 FROM raw.$t LIMIT 1" $dsnT
}
psql -X -c "CREATE TABLE contabilidad.f136_x (x int)" $dsnT
psql -X -c "SELECT count(*) FROM contabilidad_restringida.mayor" $dsnT
psql -X -c "SELECT count(*) FROM contabilidad.mayor" $dsnT
Remove-Item Env:PGPASSWORD
psql -X -c "SELECT count(*) FROM raw.apu" $dsn
```

Esperado: `permission denied for schema raw` en las siete de `raw`;
`permission denied for schema contabilidad` en el `CREATE TABLE`; el recuento de
`contabilidad_restringida.mayor` igual al de `raw.apu` (este, como
administrador y en el mismo momento); `contabilidad.mayor` legible.

### P11 · La nocturna, a mano

```powershell
python main.py apply-grants
```

Esperado: SUCCESS y, en su fila de `_meta.etl_runs`, `verificacion`,
`verificacion_total` y `acceso_total` a `ok`.

### P12 · El job

Una ejecución puntual de `check-pg` con su secreto (no toca la programada); si
no, la nocturna siguiente. **Al día siguiente**, sin hacer nada a mano, la
nocturna tiene que dejar `apply_grants` en SUCCESS con los tres `ok` (R29).

**Con `--yaml`, nunca con `--command`/`--args`**: sin `--image` esta CLI falla
(«must have an 'Image' property», medido el 2026-10-02), con `--image` se pierden
las variables y los secretos del job, y una ejecución que ignorase los cambios
lanzaría la nocturna COMPLETA de día. Se toma la plantilla del job, se cambia
solo el comando del contenedor y se lanza con ella. El fichero no lleva ningún
valor secreto (solo `secretRef`) y se borra al acabar. Si `check-pg` da
`password authentication failed`, la referencia al vault sin versión aún sirve
la anterior: puede tardar del orden de 30 minutos; se repite después.

```powershell
# las claves a null estorban al --yaml: se quitan (también dentro de los contenedores)
function Sin-Nulos($o) {
    foreach ($p in @($o.PSObject.Properties)) {
        if ($null -eq $p.Value) { $o.PSObject.Properties.Remove($p.Name); continue }
        if ($p.Value -is [PSCustomObject]) { Sin-Nulos $p.Value }
        foreach ($e in @($p.Value)) { if ($e -is [PSCustomObject]) { Sin-Nulos $e } }
    }
}
$js = az containerapp job show -g $rgJ -n $job --query properties.template -o json
$tpl = ($js -join "`n") | ConvertFrom-Json
Sin-Nulos $tpl
$c = $tpl.containers[0]
$c | Add-Member -Force -NotePropertyName command -NotePropertyValue @("python")
$c | Add-Member -Force -NotePropertyName args -NotePropertyValue @("main.py", "check-pg")
$yaml = Join-Path $env:TEMP "f136_check_pg.yaml"
# JSON es YAML válido; WriteAllText escribe UTF-8 SIN BOM (Out-File de PS 5.1 lo pondría)
[IO.File]::WriteAllText($yaml, ($tpl | ConvertTo-Json -Depth 20))
az containerapp job start -g $rgJ -n $job --yaml $yaml -o none
Remove-Item $yaml
az containerapp job execution list -g $rgJ -n $job -o table
```

```sql
-- al día siguiente, con cualquier login que lea _meta
SELECT started_at, status, metadata->>'verificacion' AS verificacion,
       metadata->>'verificacion_total' AS verificacion_total,
       metadata->>'acceso_total' AS acceso_total
FROM _meta.etl_runs
WHERE step = 'apply_grants'
ORDER BY started_at DESC
LIMIT 3;
```

### P13 · Las copias muertas

Las copias de F-005 en el vault de `albaranes` ya son valores muertos. Se listan
por NOMBRE; borrarlas pide autorización expresa del humano en ese momento
(vault de otro proyecto, D12).

```powershell
az keyvault secret list --vault-name kv-albaranes-rs9k2 --query "[].name" -o tsv
```

### Vuelta atrás

- **P2 o P3 fallan**: la base no ha cambiado. Se repite desde P2 (o desde P3 si
  el vault ya tiene los cuatro); la versión vieja sigue en el vault por si hiciera
  falta volver.
- **P4 falla**: si fue en la guarda, la base no ha cambiado; si fue después, los
  `ALTER ROLE` van antes del `BEGIN` y pueden haber entrado. En los dos casos se
  repite P4 con el entorno aún cargado: el fichero es reejecutable.
- **Se perdió la sesión entre P2 y P6**: P1 + P3 + P4 recargan del vault, que
  siempre tiene el valor bueno, y se sigue en P5.
- **Un cliente no conecta tras P6-P8**: tiene el valor viejo. El bueno está en el
  vault; nunca se vuelve a la contraseña expuesta.
