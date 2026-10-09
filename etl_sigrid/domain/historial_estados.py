# etl_sigrid/domain/historial_estados.py
"""
Lo que queda de la FOTO DIARIA de estados de F-067 mientras se retira (F-132,
Fase B, rama BORRAR, decisión del humano del 2026-10-09).

`build_compras` ya no toma la foto: `11_historial_estados.sql`, su sub-paso y
el oráculo (`aplicar_foto`, `resumir_foto`, `Tramo`) se han borrado. La época
de Delphi, que sigue usando `compras.fn_sigrid_tiempo`, vive ahora en
`domain/fecha_delphi.py`.

Quedan solo las constantes que leen el contraste (`contraste_estados_sql.py`)
y `reset-compras` (`compras_reset_sql.py`), que se retiran en la tarea
siguiente (T18) junto con este módulo.

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

#: Los tipos de documento (`con.tip`) que fotografiaba la foto: contrato y factura.
TIPOS_HISTORIAL: tuple[int, ...] = (44, 15)

#: Por qué se cerraba un tramo: el documento cambió de estado, o ya no estaba.
MOTIVOS_CIERRE: tuple[str, ...] = ("CAMBIO", "DESAPARECIDO")

#: Las dos tablas de la foto, que `reset-compras` aún conserva hasta T18.
TABLAS_PERSISTENTES: tuple[str, ...] = ("historial_estados", "historial_estados_fotos")
