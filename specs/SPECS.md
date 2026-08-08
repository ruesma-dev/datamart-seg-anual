<!-- specs/SPECS.md -->
# Formato de especificaciones (SDD)

Cada feature con `sdd: true` tiene una carpeta `specs/F-XXX-slug/` con tres
ficheros. El spec-author los crea; el humano los aprueba; el implementer los
ejecuta; el reviewer valida contra ellos.

## 1. requirements.md — notación EARS

Cada requisito con id `R1, R2...` y una de estas plantillas:

- **Ubicuo**: "El sistema debe <comportamiento>."
- **Dirigido por evento**: "CUANDO <evento>, el sistema debe <respuesta>."
- **Dirigido por estado**: "MIENTRAS <estado>, el sistema debe <respuesta>."
- **Comportamiento no deseado**: "SI <condición de error>, ENTONCES el sistema
  debe <respuesta>."
- **Opcional**: "DONDE <feature está activa>, el sistema debe <respuesta>."

Regla de oro: cada R se traduce a >= 1 test. Si no puedes imaginar el test,
el requisito está mal escrito.

Ejemplo:
> R1. CUANDO el usuario ejecuta `python main.py version`, el sistema debe
> imprimir la versión semántica y salir con código 0.

## 2. design.md — diseño técnico

Secciones obligatorias:

- **Ficheros a crear** (ruta exacta) y **ficheros a modificar** (ruta + qué
  cambia).
- **Ficheros que NO se tocan** (los colindantes que podrían tentarte).
- **Clases/funciones**: firma y responsabilidad, capa hexagonal a la que
  pertenecen (domain / application / infrastructure).
- **SQL** (si aplica): capa (`stg`/`mart`/`cierre`/...), numeración del
  fichero siguiendo la convención `NN_nombre.sql`, tablas/vistas afectadas.
- **Riesgos y decisiones**: alternativas descartadas y por qué.

## 3. tasks.md — lista de tareas atómicas

```
- [ ] T1: <acción concreta>  |  Verificación: <test o comando>
- [ ] T2: ...
```

- Ordenadas por dependencia. Tests antes o junto a la implementación.
- Cada tarea = un commit (`F-XXX Tn: ...`).
- La última tarea es siempre: "Ejecutar `bash harness/init.sh` en verde".
- Si algo solo puede verificarse contra BBDD real, marcarlo
  `Verificación: MANUAL (humano)` y describir el comando exacto.
