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

**F-005 · Fase 2 en ejecución contra Azure.** Pasos 3 a 6 y 11 hechos el
2026-08-09. Faltan el 7 y el 8, que dependen del humano, y el 9 y el 10, que
dependen del 8.

## Lo ejecutado contra Azure

| Paso | Estado |
|---|---|
| 3 · Puerta de espacio | **PASA**: 4,14 GiB usados de 32; **27,86 GiB libres** (exige ≥14) |
| 4 · Contraseñas en Key Vault | Hecho: `pg-sigrid-dm-app` y `pg-mcp-sigrid-dm-ro` en `kv-albaranes-rs9k2` |
| 5 · Base y roles | Hecho: `sigrid_dm`, 3 roles, 9 esquemas, todos propiedad de `sigrid_dm_etl` |
| 6 · Firewall | Añadida `datamart-puesto-pgris-2026-08-09`; las 3 reglas previas, intactas |
| 7 · `.env` | **PENDIENTE DEL HUMANO** (regla dura: los agentes no tocan `.env`) |
| 8 · Carga inicial | Pendiente del paso 7 |
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

# F-015 · Implementada (2026-08-09, implementer) — pendiente de review

**Estado:** las 16 tareas de `specs/F-015-verificar-tests/tasks.md` en `[x]`,
un commit por tarea, `bash harness/init.sh` en verde con la puerta de
cobertura nueva ejecutándose de verdad. **Informe completo:
`progress/impl_F-015.md`.** Nivel de rigor declarado: `estandar`.

## Evidencias, en una línea cada una

| Evidencia | Valor |
|---|---|
| Tests | **166 pasan**, 0 fallan (101 nuevos), en **1,2 s** |
| Cobertura de líneas cambiadas | **97,5 %** (538/552, umbral 80 %) |
| Mutación de F-015 | 175 mutantes, **13 supervivientes** (92,6 %) |
| Mutación de F-005 (línea base) | 101 mutantes, **55 supervivientes** (45,5 %) |

## Lo que hay que saber sin leer el informe

- **La línea base de F-005 destapó 6 huecos de riesgo alto.** El más
  incómodo: el valor por defecto de `auto_create_db` —la puerta bloqueante
  que la propia F-005 declaró contra el servidor compartido de producción—
  **no lo fija ningún test**, ni en `config/settings.py` ni en
  `postgres_client.py`. Tampoco el autocommit de la conexión administrativa,
  ni la comparación de huellas de `fingerprint.py`, ni la detección de un
  paso fallido en `main.py`. Detalle en `progress/mutacion_F-005.md`. **No se
  han parcheado**: los tests de F-005 son el objeto de la medición.
- **La campaña sobre F-015 se ejecutó dos veces**: 37 supervivientes la
  primera, 13 tras añadir tests. Los 24 huecos cerrados no los había visto ni
  la fase RED ni el 96,7 % de cobertura de entonces.
- **La campaña de F-005 se ejecutó en un `git worktree` aparte**, no en el
  árbol vivo, porque había una carga `run-all --full` corriendo contra Azure
  desde este mismo directorio y la mutación escribe ficheros en disco. Se
  añadió la opción `--raiz` a la herramienta para poder hacerlo.
- **Novedad que afecta a todo trabajo futuro**: `bash harness/init.sh` ahora
  ejecuta la suite bajo `coverage` y **falla** si la cobertura de las líneas
  que cambia la feature en curso baja del 80 %. Hace falta
  `pip install -r requirements-dev.txt` (dependencia nueva: `coverage>=7.4`).
- **`arnes-base` está en 1.2.0** con todo esto portado (commit local
  `5006ee8`, sin push).

## Pendiente del humano

1. **MANUAL de R20**: los cuatro comandos de verificación del portado a
   `arnes-base`, listados en `progress/impl_F-015.md` § 6 con el resultado ya
   obtenido.
2. **Decisión**: ¿se abre una feature de refuerzo de tests para los 6 huecos
   de riesgo alto de F-005?
3. **Decisión**: las 9 features aún no empezadas no declaran `rigor` y por
   tanto heredan `critico` (el más exigente). Es lo correcto por diseño, pero
   conviene decidirlo antes de abrir cada una, no descubrirlo.

---

# F-015 · Spec escrita (2026-08-09, spec-author)

Escrita `specs/F-015-verificar-tests/` (`requirements.md` con R1–R20 en EARS,
`design.md`, `tasks.md` T1–T16). Sin tocar código, `features.json` ni commits.
Piezas: mutador propio del arnés sobre las líneas del diff contra `dev`
(`python -m harness.mutacion --feature F-XXX` → `progress/mutacion_F-XXX.md`),
puerta de cobertura de líneas cambiadas en `init.sh` con umbral en
`harness/rigor.json`, niveles de rigor en `CHECKPOINTS.md` (+ C4 bis) con
default el más exigente, fase RED y sección «Evidencias» en el implementer,
reviewer validando contra el nivel, línea base sobre F-005 (alcance
reconstruido desde el merge `c7500d4`) y portado a `arnes-base` con versión
`1.2.0`.

## Decisiones abiertas que el humano debe validar (design.md, antes de implementar)

- **DA-1** Herramienta de mutación: se propone mutador propio mínimo (stdlib,
  `ast`); mutmut descartado (sin soporte Windows), cosmic-ray descartado
  (demasiado peso para portarlo a arnes-base).
- **DA-2** Umbral de cobertura de líneas cambiadas: propuesta **80 %**.
- **DA-3** Niveles de rigor: `documental` / `estandar` / `critico`, default
  `critico` para quien no declare.
- **DA-4** Rigor retroactivo: F-001 `estandar`, F-008 `documental`, F-009
  `documental`, F-005 `critico`, F-014 `estandar`, F-015 `estandar`.
- **DA-5** Línea base F-005: si la campaña supera ~45 min, ¿muestra
  reproducible con semilla o campaña completa aunque tarde horas?
- **DA-6** Dependencia nueva `coverage>=7.4` en `requirements-dev.txt`.
