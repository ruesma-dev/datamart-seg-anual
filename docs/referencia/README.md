<!-- docs/referencia/README.md -->
# Información adicional de referencia

Documentación de apoyo que **no** describe el código de este repositorio,
sino el negocio y el sistema origen: manuales de Sigrid, criterios de cierre
mensual, definiciones contables, especificaciones que llegan de fuera.

Sirve para responder «¿por qué el ETL hace esto?» cuando la respuesta no
está en el código sino en una norma de negocio.

## Qué va aquí y qué no

| Aquí | No aquí |
|---|---|
| Manuales y documentación de Sigrid | Arquitectura del ETL → `docs/ARCHITECTURE.md` |
| Criterios de negocio (cierre, periodificaciones, tipologías) | Convenciones de código → `docs/CONVENTIONS.md` |
| Documentos que llegan en PDF, Word o Excel, convertidos a Markdown | Especificaciones de features → `specs/` |
| Capturas o extractos de informes de referencia | Notas de trabajo de una sesión → `progress/` |

### Documentación compartida por varios proyectos: una sola copia

Si un documento describe algo **común a varios repositorios** —el diccionario
de una base de datos que todos consumen, la API de un servicio compartido, el
diseño de red de la organización— **no va aquí**: va al repositorio de
documentación del ecosistema (en el entorno de Ruesma, `azure-apps/`) como
única copia, y en este directorio queda solo un **puntero** de pocas líneas
con la ruta, el motivo y lo imprescindible para no tener que abrir el otro
repositorio. Dos copias del mismo documento divergen siempre; el puntero
evita además arrastrar ficheros de megas a cada proyecto que instale el arnés.
Convención del puntero: mismo nombre `NN_tema.md`, título terminado en
«— vive en `<repositorio>`, no aquí» y una nota fechada de cuándo se movió.

## Índice

| Fichero | Qué es |
|---|---|
| `01_sigrid_tablas.md` | Diccionario de la BBDD de Sigrid: tablas, campos, tipos e índices. Referencia del sistema origen y base para auditar `config/tables_sigrid.yaml`. |
| `02_azure_landing_zone_acens.md` | Diseño de la Landing Zone de Azure entregado por acens. Contexto del despliegue (F-005, F-003, F-006). **Versión redactada**: sin rangos de red ni correos. |
| `03_sigrid_api.md` | **Puntero, no documento.** La documentación de `sigrid-api` vive en `azure-apps/sigrid_api.md`; aquí solo queda lo imprescindible y el enlace. |
| `04_azure_inventario_dev.md` | Inventario de la suscripción Azure «Ruesma» tomado con `az` (solo lectura) el 2026-08-08: resource groups, red, almacenamiento, secretos y bases de datos, contrastado con el diseño de acens. **Versión redactada**: sin IDs de suscripción/tenant, sin IPs ni rangos de red, sin valores de secretos. |
| `05_caso_obrfasamb_version_duplicada.md` | Caso de datos del sistema origen: versiones master guardadas dos veces en `obrfasamb` (obras 0694 y 0697), que el ETL duplica en `stg.plan_mensual`. Con receta SQL para replicarlo. Motivó la enmienda de R13 en F-019 y la feature F-022. |

## Formato

Todo en **Markdown**. Los documentos que lleguen en PDF u ofimática se
convierten al entrar con la herramienta MCP `markitdown` (ver la regla en
`CLAUDE.md`), para que sean legibles, buscables con grep y diffeables entre
versiones, y para que el resultado sea el mismo lo convierta quien lo
convierta.

Convención de nombres: `NN_tema.md` cuando haya un orden natural de lectura,
o `tema.md` si no. El original queda **fuera del repositorio**: aquí solo
entra el Markdown. Anota en la cabecera de cada fichero de dónde salió y de
qué fecha es, porque un manual desactualizado que parece vigente hace más
daño que no tenerlo.

Cabecera obligatoria. La primera línea del bloque de origen es siempre la
misma; la segunda depende de cómo llegó el documento.

**Caso 1 — llegó en PDF u ofimática y se convirtió:**

```markdown
<!-- docs/referencia/NN_tema.md -->
# Título

> Origen: <fichero o sistema de procedencia> · Fecha del documento: AAAA-MM-DD
> Convertido a Markdown el AAAA-MM-DD con la herramienta MCP `markitdown`.
> El original vive fuera del repositorio.
```

**Caso 2 — llegó ya en Markdown:**

```markdown
> Origen: <fichero o sistema de procedencia> · Fecha del documento: AAAA-MM-DD
> Incorporado a `docs/referencia/` el AAAA-MM-DD.
> Llegó ya en Markdown: no requirió conversión con `markitdown`.
```

No escribas «convertido» si no hubo conversión: la trazabilidad de cómo entró
un documento es justo lo que un reviewer no puede reconstruir después.

**Tercer bloque, obligatorio si se ha redactado algo.** Cuando el documento
traiga material sensible que se sustituya por marcadores, dilo en la cabecera
y di exactamente qué se sustituyó:

```markdown
> **Redactado.** Se han sustituido por marcadores <qué: rangos de red, IDs de
> suscripción, correos…>. El detalle está en el original, fuera del repositorio.
```

Si el original impone restricciones de uso (confidencialidad de un proveedor,
por ejemplo), cítalas también en la cabecera.

## Antes de commitear un documento nuevo

El checkpoint **C3 bis** de `CHECKPOINTS.md` es la lista de verificación
formal, y el reviewer la recorre. En resumen: cabecera con origen y fecha,
original fuera del repositorio (compruébalo también en el historial, no solo
en el árbol), barrido de datos sensibles ejecutado y anotado, y lo redactado
declarado en la cabecera.
