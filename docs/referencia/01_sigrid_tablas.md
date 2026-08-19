<!-- docs/referencia/01_sigrid_tablas.md -->
# Estructura de la base de datos de Sigrid — vive en `azure-apps/`, no aquí

> Este documento **se movió fuera de este repositorio el 2026-08-18** y queda
> solo como puntero, para que nadie vuelva a copiarlo.

El diccionario completo de la BBDD de Sigrid (tablas, campos, tipos, índices
y relaciones; 380 páginas del «AUTODOCUMENTADOR ESTRUCTURA BASE DE DATOS
SIGRID v.20240618», documento del 2024-11-06, convertido con `markitdown`)
está en:

**`C:\Users\pgris\PycharmProjects\azure-apps\sigrid_tablas.md`**

## Por qué no está aquí

Los seis proyectos del ecosistema (`albaranes`, `partes`, `portal`,
`remesas`, `sigrid-api` y este) trabajan contra la misma base de Sigrid, así
que el diccionario es **documentación del ecosistema, no de un proyecto**:
igual que `sigrid_api.md`, vive en `azure-apps/` como única copia y desde
cada repositorio se enlaza. Dos copias divergen siempre (ya pasó con
`sigrid_api.md`: 515 líneas contra 890).

## Lo que hay que saber sin abrir el otro repositorio

- Es la referencia para entender qué significa cada columna que ingerimos y
  la base para auditar `config/tables_sigrid.yaml` (las 31 tablas del ETL).
- Describe la **estructura** (qué tablas y campos existen), no el significado
  de negocio ni cómo se combinan para el cierre: eso vive en las cabeceras de
  los SQL (`stg/08_plan_mensual.sql`, `cierre/02_build_fact.sql`), en
  `config/business_rules.yaml` y en las specs.
- Casos concretos de datos del origen documentados en este proyecto:
  `05_caso_obrfasamb_version_duplicada.md`.
