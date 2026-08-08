<!-- progress/current.md -->
# Trabajo en curso

(vacío — ninguna feature en ejecución)

F-009 cerrada el 2026-08-08, resumen en `progress/history.md`.

## Pendiente de decisión del humano

1. **Borrado del stack abandonado** (`rg-sigridetl-dev-data`). El humano
   confirmó que no es ninguna de las tres apps en producción —albaranes y
   partes usan PostgreSQL en `psql-albaranes-rs9k2`; remesas no tiene base— y
   autorizó eliminarlo. Falta cerrar dos cosas antes de ejecutarlo:
   - **Alcance**: solo la base, el servidor SQL, o el resource group entero
     (10 recursos). Recomendación del líder: el resource group entero.
   - **¿Leer antes `etl.etl_run` y `etl.etl_table_run`?** Son 28 filas de
     telemetría con `status` y `message`: la única respuesta que queda a «por
     qué se paró», y el borrado la destruye. Ver **D7**.
2. **Diseño del despliegue en Azure**, propuesto por el líder y pendiente de
   confirmación para pasarlo al `spec-author`. Resumen abajo.
3. **La regla de firewall `dev-puesto-pgris-2026-08-08`** sigue puesta en
   `sql-sigridetl-dev-8yv7pj`. Decidir si se retira — irrelevante si se borra
   el resource group entero.

## Diseño de despliegue propuesto (pendiente de confirmación)

No inventar infraestructura: el datamart es la cuarta pieza de un patrón que
ya funciona en producción con albaranes, partes y remesas.

- **Reutilizar** `psql-albaranes-rs9k2` creando la base `sigrid_dm`, y
  `acralbaranesdev` como registro de imágenes.
- **Crear** `rg-datamart-seg-dev` con su Container Apps Job, entorno, Key
  Vault, Log Analytics y una storage account con contenedor `aux` para los
  Excels auxiliares (cierra la parte que faltaba de D5).
- **Base propia, no esquema compartido**: PostgreSQL no permite consultas
  entre bases, así que el rol de solo lectura del MCP no puede ver
  `albaranes`, que contiene precios de proveedor y datos bancarios. Es una
  frontera real, no de disciplina. Si algún día hace falta cruzar datos entre
  proyectos, `postgres_fdw` dentro del mismo servidor.
- **Sin contraseñas**: identidad gestionada con `AcrPull`, `Key Vault Secrets
  User` y autenticación Entra contra PostgreSQL.
- **D1 → opción A** (endpoint público con reglas de firewall), que es lo que
  ya hace el servidor compartido para dos proyectos. La opción B parte de
  cero: no hay ni un private endpoint ni una zona DNS privada en toda la
  suscripción, y la VPN punto a sitio no está configurada.
- **D3 → parametrizar entorno desde el principio**, desplegar solo `dev`.
- **D6 → `0 2 * * *` UTC** y alerta de fallo por Azure Monitor al canal de
  correo que ya usan las alertas de coste de la landing zone.
- **No renombrar el servidor**: un Flexible Server no se puede renombrar, su
  nombre es su endpoint DNS. Se hará el día que otro motivo obligue a
  recrearlo, migrando las tres bases de una vez.

### Riesgos anotados

- `Standard_B1ms`: 1 vCPU y 2 GB de RAM para las transformaciones de `mart` y
  `cierre`. El job es nocturno y no compite con las apps, y escalar el SKU es
  un reinicio, no una migración — pero hay que medirlo en la primera carga.
- 32 GB compartidos con `albaranes` y `partes`. Sigrid son ~4 GB en origen,
  pero `raw` + `stg` + `mart` con índices puede irse a 10-12 GB. Comprobar
  espacio libre antes de la carga inicial. El almacenamiento solo crece.
- Sin HA y con 7 días de backup: la recuperación es «volver a ejecutar el
  ETL», no «restaurar». Asumible para un datamart regenerable.

### Cargas incrementales — hallazgo que condiciona F-004

**Sigrid no tiene marca de última modificación fiable**: en el diccionario,
`fecalt` aparece en 16 tablas, `fecmod` en 3 y `sello` en 2. No hay watermark
para un incremental directo. Palancas alternativas: ventana de negocio
(ejercicio en curso y obras abiertas, con recarga completa semanal) y altas
nuevas por `ide` autoincremental.

Sospecha a verificar: el cuello de botella probablemente **no** sea la base
sino la extracción — `sigrid-api` limita a 1.000 filas por petición y el
balanceador corta a los 230 s. Encaja con que el intento de abril muriera en
la ingesta.

**Recomendación: no construir el incremental todavía.** Instrumentar la
primera carga completa con tiempos por paso y por tabla, y decidir con
números.
