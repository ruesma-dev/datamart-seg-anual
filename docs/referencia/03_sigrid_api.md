<!-- docs/referencia/03_sigrid_api.md -->
# sigrid-api — vive en `azure-apps/`, no aquí

> Este documento **se eliminó de este repositorio el 2026-08-08** y queda solo
> como puntero, para que nadie vuelva a copiarlo.

La documentación del microservicio `sigrid-api` está en:

**`C:\Users\pgris\PycharmProjects\azure-apps\sigrid_api.md`**

## Por qué no está aquí

Se incorporó por la mañana una copia de 515 líneas fechada en junio. Ese
mismo día resultó que la copia viva en `azure-apps/` tenía **890 líneas** y
era de hoy. Dos copias del mismo documento, y la de aquí nacía desfasada.

La regla, en `CLAUDE.md` y en `azure-apps/README.md`: **el dueño del
documento es el proyecto que describe**, y desde otros repositorios se enlaza
en vez de copiar.

## Lo que hay que saber sin abrir el otro repositorio

- `sigrid-api` es el **único** punto de acceso a la base de datos de Sigrid.
  Nadie se conecta por SQL directo: todo pasa por esa API.
- Es a quien llama `etl_sigrid/infrastructure/sigrid/`.
- **Desde este proyecto, solo lecturas.** Los endpoints de escritura que
  documenta no se usan desde este ETL (regla dura de `CLAUDE.md`).
- **Límites que condicionan nuestra ingesta**: máximo **1.000 filas por
  petición** y **230 s** de corte del balanceador. Con ~4 GB en origen, es el
  cuello de botella probable del ETL. Ver F-011.
