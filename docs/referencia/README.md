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

Cabecera recomendada:

```markdown
<!-- docs/referencia/NN_tema.md -->
# Título

> Origen: <fichero o sistema de procedencia> · Fecha del documento: AAAA-MM-DD
> Convertido a Markdown el AAAA-MM-DD.
```
