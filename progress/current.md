<!-- progress/current.md -->
# Trabajo en curso

> ## ⚠ LEE ESTO PRIMERO: `.env` APUNTA A AZURE
>
> Desde el 2026-08-09, `.env` está configurado contra
> **`psql-albaranes-rs9k2`**, el servidor compartido que sirve también a
> `albaranes` y `partes` en producción. **NO** apunta al Postgres local.
>
> Consecuencia inmediata: `check-pg`, `status`, `run-all` y cualquier cosa que
> abra conexión **van contra Azure**. Antes de lanzar nada que escriba,
> asegúrate de que es lo que quieres. Para volver a local, el humano guardó
> copia en `.env.local.bak`.
>
> Los tests de pytest **no** tocan red ni BBDD, así que `harness/init.sh`
> sigue siendo seguro de ejecutar.
>
> Datos útiles de entorno para no redescubrirlos:
> - `psql.exe` está en `C:\Program Files\PostgreSQL\16\bin` (no está en el
>   `PATH` por defecto). No hace falta instalar nada.
> - Las contraseñas del datamart están en **`kv-albaranes-rs9k2`**, secretos
>   `pg-sigrid-dm-app` y `pg-mcp-sigrid-dm-ro`. Nunca en ficheros del repo.
> - Al conectar con `psql`, **las opciones van ANTES** de la cadena de
>   conexión: este build deja de parsearlas tras el primer argumento
>   posicional.
> - Los ID de recurso de Azure se rompen en Git Bash por la conversión de
>   rutas: usa la forma `--resource NOMBRE --resource-group ... --resource-type ...`.

# F-004 · IMPLEMENTADA (2026-08-09) — pendiente de revisión

Las 11 tareas de `specs/F-004-etl-sin-dependencias-locales/tasks.md` hechas y
marcadas, un commit por tarea, en `feature/F-004-etl-sin-dependencias-locales`.
Informe completo: **`progress/impl_F-004.md`**. Campaña de mutación:
`progress/mutacion_F-004.md`.

`bash harness/init.sh` **en verde (exit 0)**: 221 tests, 2,85 s; cobertura de
líneas cambiadas **98,2 %** (umbral 80); mutación **92,6 %** (27 mutantes, 2
supervivientes, los dos equivalentes por construcción y razonados).

El step `load_excel_aux` ya resuelve los tres Excels desde **ruta local o URI
de blob** (`https://<cuenta>.blob.core.windows.net/...`), autentica con
`DefaultAzureCredential` —sin claves, sin cadenas de conexión y **rechazando**
las URIs con SAS sin filtrar el token en el mensaje—, lee **en memoria** y
valida con openpyxl. **No carga nada a `aux.*`.** F-004 no ha aprovisionado
nada en Azure ni ha ejecutado `python main.py` (la carga de F-005 estaba
corriendo). `features.json` sigue en `in_progress`: lo mueve el líder tras el
APROBADO del reviewer.

## Verificaciones MANUAL (humano) de F-004 · BLOQUEADAS hasta F-003

Las tres necesitan la storage account y el contenedor `aux`, que **crea
F-003**. No bloquean el cierre de F-004; sí deben ejecutarse antes de dar por
buena la lectura de blobs en Azure.

1. Con `az login` activo y el rol `Storage Blob Data Reader` sobre la cuenta,
   apuntar la variable al blob real y ejecutar:
   `python main.py load-aux`
   Esperado: `SUCCESS` y, en el detalle, `origen=blob` con las hojas del libro.
2. Desde el Container Apps Job, con identidad gestionada:
   `az containerapp job start -n <job> -g <rg>` y buscar en los logs el evento
   `aux_file_read`. Esperado: los tres ficheros leídos y **ninguna ruta local**.
3. Prueba negativa del mensaje de permisos: retirar temporalmente el rol,
   ejecutar `python main.py load-aux` y comprobar que el error dice qué rol
   falta y qué hacer. **Volver a asignarlo después.**

## Decisión abierta DA-1 · ¿quién carga los Excels a `aux.*`?

F-004 deja los tres libros **leídos y validados**, no volcados. Motivo: las
tablas destino no existen (`aux` solo tiene `periodificacion_partida`, vacía) y
**el esquema de los tres Excel no está en el repositorio** —columnas, hojas,
claves— ni las reglas que los mapean a `mart`. Inventarlo sería inventar el
modelo de datos de Negocio. Necesita decisión del humano y feature propia.

## Dependencia de F-004 hacia F-003

Si el job **no** usa identidad *system-assigned*, F-003 debe inyectar
`AZURE_CLIENT_ID` en el entorno del contenedor: `DefaultAzureCredential` lo lee
solo, pero alguien tiene que ponerlo. Y la identidad necesita el rol
`Storage Blob Data Reader` sobre la cuenta.

## Hallazgo para F-016 (refuerzo de los tests de F-005)

`test_f005_r21_barrido_de_secretos_en_el_arbol` da **falso positivo con rutas
largas**: su patrón de base64 (`[A-Za-z0-9+/]{24,}`) casó con
`sigrid/infrastructure/excel/` al añadir una línea a `docs/ARCHITECTURE.md` y
puso `init.sh` en rojo. No se ha tocado el test de otra feature: se reformuló
la frase. Conviene exigir contexto de asignación o excluir cadenas con varias
barras.

---

**F-005 · Fase 2 en ejecución contra Azure.** Pasos 3 a 7 y 11 hechos el
2026-08-09. El 8 (carga inicial) está **corriendo ahora**: el primer intento
murió el 2026-08-09 a las 11:46 por un corte de red local del puesto (el
`COPY` de `obrparpre` colgado 9 min y luego `getaddrinfo failed`; el servidor
estaba bien) y el humano la relanzó. Los pasos 9 y 10 dependen del 8.

## Lo ejecutado contra Azure

| Paso | Estado |
|---|---|
| 3 · Puerta de espacio | **PASA**: 4,14 GiB usados de 32; **27,86 GiB libres** (exige ≥14) |
| 4 · Contraseñas en Key Vault | Hecho: `pg-sigrid-dm-app` y `pg-mcp-sigrid-dm-ro` en `kv-albaranes-rs9k2` |
| 5 · Base y roles | Hecho: `sigrid_dm`, 3 roles, 9 esquemas, todos propiedad de `sigrid_dm_etl` |
| 6 · Firewall | Añadida `datamart-puesto-pgris-2026-08-09`; las 3 reglas previas, intactas |
| 7 · `.env` | Hecho y verificado por el humano el 2026-08-09 |
| 8 · Carga inicial | **EN CURSO** (relanzada tras el corte de red del primer intento) |
| 9 · Medición y veredicto del SKU | Pendiente del 8 |
| 10 · Verificación de vistas | Pendiente del 8 |
| 11 · Frontera de seguridad | Hecho, ver abajo |

**Fotografía previa** (antes de tocar nada): `Standard_B1ms`, PG 16.14, 32 GB,
auto-grow **deshabilitado**, sin HA, backup 7 días, `log_statement=none`.
Reglas de firewall previas: `AllowAzureServices`, `FirewallIPAddress_2026-6-16`,
`ClientPgris`. Bases previas: `albaranes`, `partes`.

## Frontera de seguridad, medida

- `sigrid_dm_app` conecta y `SET ROLE sigrid_dm_etl` funciona
  (`current_user=sigrid_dm_etl`, `session_user=sigrid_dm_app`). Crea y borra.
- `mcp_sigrid_dm_ro` **no puede escribir**: `permission denied`.
- `mcp_sigrid_dm_ro` **sí puede conectarse a `albaranes`** —riesgo aceptado el
  2026-08-08 al descartar `REVOKE CONNECT`— y **no puede leer sus datos**
  (`permission denied for table`). Lo que sí ve, cuantificado: **14 nombres de
  tabla y 450 de columna** vía `pg_catalog`, que no filtra por privilegios.
  `information_schema` sí filtra y le devuelve 0.

## Defecto encontrado y corregido

`infra/sql/02_roles.sql` hacía `ALTER ROLE ... WITH NOSUPERUSER ...` y **falla
contra Azure**: el administrador de un Flexible Server no es superusuario, y
PostgreSQL exige el atributo SUPERUSER para cambiarlo aunque sea para ponerlo
a NO. Contra un PostgreSQL local no fallaba porque allí el admin sí lo es:
este fichero **solo podía romperse contra Azure**, y solo al ejecutarlo.

Corregido quitando `NOSUPERUSER`, que era redundante: `CREATE ROLE` ya crea
sin superusuario, y así se verificó (`rolsuper = f` en los tres roles).

## Lo que falta

1. **`.env` · HECHO y verificado** el 2026-08-09. Los once valores correctos:
   host de Azure, `sigrid_dm`, `sigrid_dm_app`, contraseña de 32 caracteres
   que coincide con Key Vault, `sslmode=require`, **`PG_AUTO_CREATE_DB=False`**,
   `SET ROLE` y rol de solo lectura. `check-pg` responde PostgreSQL **16.14**
   (Azure; el local es 16.4). La contraseña está tipada como `SecretStr`, así
   que no puede colarse en un log.
2. **Carga inicial · PENDIENTE, la lanza el humano**:
   `python main.py run-all --full`. El `apply-grants` final no es opcional.
   Puede tardar: ~4 GB a través de una API que sirve 1.000 filas por petición,
   contra un servidor de 1 vCPU. Es repetible: si hay que abortarla porque
   `albaranes` o `partes` se resienten, se relanza sin más.
3. **Pasos 9 y 10, del líder, en cuanto termine la carga**: medición con
   `python main.py timings` y **veredicto explícito sobre si `Standard_B1ms`
   aguanta** —es la entrada de F-011—, y comparación de la huella de vistas
   local contra Azure con el mes cerrado que fije el humano.

## Nota sobre dónde viven las contraseñas

Se han guardado en **`kv-albaranes-rs9k2`** porque el vault propio del
datamart (`kv-datamart-seg-dev`) **lo crea F-003 y todavía no existe**. Es una
decisión de conveniencia, no de diseño: **F-003 debe moverlas** a su vault y
actualizar la referencia. Anotado para que no se quede así por inercia.

---

# F-015 · CERRADA (2026-08-09) — pendientes resueltos el mismo día

Implementada y **APROBADA** por el reviewer a la primera
(`progress/review_F-015.md`). Resumen en `progress/history.md`. Los cuatro
pendientes que elevó, cerrados por el humano el 2026-08-09:

1. **MANUAL de R20 · VERIFICADO por el humano**: los cuatro comandos
   devolvieron lo esperado (commit `5006ee8`, `ARNES_VERSION=1.2.0`,
   herramientas presentes, guía con la sección de mutación en su línea 287).
2. **Refuerzo de F-005 · SÍ**: creada **F-016** (`sdd=false`, rigor
   `estandar`, prioridad 9) para los 6 huecos de riesgo ALTO. Los de riesgo
   medio y bajo quedan como deuda anotada en `progress/mutacion_F-005.md`.
3. **Rigor de las 9 features sin abrir**: se decidirá al abrir cada una;
   mientras tanto heredan `critico`, que es el comportamiento buscado.
4. **Automejora del reviewer · APROBADA y aplicada**: `reviewer.md` (paso 4
   de la validación de rigor) y `CHECKPOINTS.md` (C4 bis) exigen ahora
   verificar los totales de mutación de forma independiente. Portada a
   `arnes-base` **1.2.1**.

# Rumbo confirmado por el humano (2026-08-09): el ETL debe correr en Azure

Nuevo orden de prioridades de las features abiertas: **F-004** (ETL sin
dependencias locales, spec_ready) → **F-003** (Container Apps Job nocturno
`--full` + disparo manual, spec_ready) → **F-016** (refuerzo tests F-005) →
**F-011** (incremental) → resto. La spec de F-003 exige F-004 y F-005
cerradas antes de su T1. Siguiente paso: aprobar la spec de F-004.

Modelos de agentes: el humano decidió dejar implementer y reviewer fijados a
`opus`; leader y spec-author siguen en `inherit`.

