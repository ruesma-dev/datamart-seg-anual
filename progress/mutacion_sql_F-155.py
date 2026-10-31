# progress/mutacion_sql_F-155.py
"""Mutación MANUAL del SQL de F-155 contra la sandbox (`harness.mutacion` solo muta Python).

Cada mutante cambia UNA expresión de 08, 09 o 14, ejecuta los tests de sandbox de
`tests/test_f155_ofertas_compartidas.py` y restaura el fichero (también si falla).
Uso: F155_SANDBOX_DSN=postgresql://... python progress/mutacion_sql_F-155.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"

MUTANTES = [
    ("M1 08 orden del comparativo ASC", "08_comparativos.sql",
     "COALESCE(q.comide = cl.comide, FALSE) DESC", "COALESCE(q.comide = cl.comide, FALSE) ASC"),
    ("M2 08 desempate por la ultima invitacion", "08_comparativos.sql",
     "FALSE) DESC, q.ide\n", "FALSE) DESC, q.ide DESC\n"),
    ("M3 08 B por documento otra vez", "08_comparativos.sql",
     "li ON li.invitacion_id = p.ide", "li ON li.invitacion_id = (SELECT min(x.ide) FROM raw.comprv x WHERE x.docide = p.docide)"),
    ("M4 09 orden del comparativo ASC", "09_comparativos_detalle.sql",
     "COALESCE(o.comparativo_id = cl.comparativo_id, FALSE) DESC",
     "COALESCE(o.comparativo_id = cl.comparativo_id, FALSE) ASC"),
    ("M5 09 desempate por la ultima invitacion", "09_comparativos_detalle.sql",
     "FALSE) DESC, o.invitacion_id\n", "FALSE) DESC, o.invitacion_id DESC\n"),
    ("M6 09 objetivo sin comparativo en el JOIN", "09_comparativos_detalle.sql",
     "cp.comparativo_id = ob.comparativo_id AND cp.oferta_id", "cp.comparativo_id IS NOT NULL AND cp.oferta_id"),
    ("M7 14 primera invitacion -> ultima", "14_documento_adjuntos.sql",
     "ORDER BY q.docide, q.ide\n", "ORDER BY q.docide, q.ide DESC\n"),
]


def main() -> int:
    vivos = 0
    for nombre, fichero, viejo, nuevo in MUTANTES:
        ruta = SQL / fichero
        original = ruta.read_bytes()
        texto = original.decode("utf-8")
        assert texto.count(viejo) == 1, f"{nombre}: el texto a mutar no es único"
        try:
            ruta.write_bytes(texto.replace(viejo, nuevo).encode("utf-8"))
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                 "tests/test_f155_ofertas_compartidas.py", "-k", "sandbox"],
                cwd=RAIZ, capture_output=True, text=True,
            )
        finally:
            ruta.write_bytes(original)
        muerto = r.returncode != 0
        vivos += not muerto
        print(f"{'MUERTO' if muerto else 'VIVO  '} {nombre}: {r.stdout.strip().splitlines()[-1]}")
    print(f"{len(MUTANTES)} mutantes, {len(MUTANTES) - vivos} muertos, {vivos} supervivientes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
