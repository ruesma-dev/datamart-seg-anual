<!-- progress/current.md -->
# Estado actual

## F-006 · El diccionario semántico del datamart — `in_progress`

Rama `feature/F-006-mcp-azure`. **Bloques A, B, C y D terminados** (T3 a T14),
con `bash harness/init.sh` en verde: 1052 tests, cobertura de líneas cambiadas
98,8 % y campaña de mutación con **0 supervivientes de 112 mutantes**.

Informe completo: `progress/impl_F-006.md`.
Campaña de mutación: `progress/mutacion_F-006.md`.

### Qué hay ya

- **Andamiaje** (bloque A): `etl_sigrid/domain/diccionario.py` (entidades y
  validador), `etl_sigrid/domain/inventario.py` (inventario y cobertura),
  `etl_sigrid/infrastructure/diccionario/cargador_yaml.py`, y la puerta de
  cobertura en `tests/test_f006_cobertura.py`, que corre en cada `init.sh`.
- **Bloque global** (bloque B): `config/diccionario/00_global.yaml` con las doce
  reglas duras, los órdenes de magnitud, las convenciones, los nueve esquemas y
  las 18 preguntas de la batería de aceptación.
- **Fichas**: `mart.yaml` (13 objetos) y `cierre.yaml` (12 objetos).

El trinquete `PENDIENTES_MAX` está en **73** de 98 objetos y solo baja.

### Lo siguiente

Bloque E (`tasks.md` T15–T19): la publicación en `_meta`, que es el contrato con
el repositorio `mcp-bbdd`. Después F y G (el resto de fichas), y solo entonces
los bloques 🔏 de permisos y firewall, que necesitan firma del humano.

### Avisos que no hay que perder

- **`build-compras` y `build-retenciones` no registran paso en `_meta.etl_runs`**:
  su fecha de build no es consultable por SQL. Afecta a T20, T21 y al valor real
  de `_meta.v_diccionario`.
- El inventario real son **98 objetos**, no «más de 80», y `cierre` tiene **8
  vistas**, no 6: conviene enmendar `design.md` §5.1 y `tasks.md` T14.
- El ejemplo de ficha de `design.md` §3.3 usa nombres de columna y literales de
  escenario **que no existen** en el SQL. Las fichas usan los reales.

### Nada de esto se ha tocado

Permisos, `REVOKE`, firewall, Azure y cualquier conexión a la base. Tampoco
`main.py`, `config/settings.py`, `grants.py`, `postgres_client.py` ni ningún SQL
de negocio.
