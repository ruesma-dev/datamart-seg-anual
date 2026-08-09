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

# F-015 · CERRADA (2026-08-09) — pendientes elevados al humano

Implementada y **APROBADA** por el reviewer a la primera
(`progress/review_F-015.md`). Resumen en `progress/history.md`. Quedan
cuatro cosas del humano, ninguna bloqueante:

1. **MANUAL de R20** — verificar el portado a `arnes-base` 1.2.0:

   ```
   git -C C:/Users/pgris/PycharmProjects/arnes-base log --oneline -5
   grep ARNES_VERSION C:/Users/pgris/PycharmProjects/arnes-base/arnes-base/harness/VERSION
   grep -rl "mutacion" C:/Users/pgris/PycharmProjects/arnes-base/arnes-base/harness/
   grep -n "mutaci" C:/Users/pgris/PycharmProjects/arnes-base/GUIA_INSTALACION.md | head
   ```

   Resultado esperado (ya contrastado por implementer y reviewer): commit
   `5006ee8`, `ARNES_VERSION=1.2.0`, herramientas presentes, guía con sección.
2. **Decisión** — ¿feature de refuerzo de tests para los 6 huecos de riesgo
   alto que la línea base destapó en F-005 (55/101 mutantes vivos, detalle en
   `progress/mutacion_F-005.md`)? El más serio: ningún test fija el valor por
   defecto de `auto_create_db`.
3. **Decisión** — las 9 features no empezadas heredan rigor `critico` por
   omisión; decidir el `rigor` de cada una al abrirla.
4. **Decisión** — automejora del reviewer propuesta en
   `progress/review_F-015.md` § 6: que verifique siempre los totales de
   mutación de forma independiente. Si se aprueba, se porta a `arnes-base`.

