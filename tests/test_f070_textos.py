# tests/test_f070_textos.py
"""F-070 · paradas con plantilla, repositorio del ecosistema, orden de fases y guía.

`CLAUDE.md` y `CHECKPOINTS.md` son `adaptado`: un proyecto que conserve los
suyos ve un único rojo por fichero con lo que aceptar, y sus dependientes se
saltan (patrón F-059 R34). Los agentes y `SPECS.md` son `arnes_puro`. Los
textos se comparan aplanados: una frase puede partirse en dos líneas.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
AGENTES = RAIZ / ".claude" / "agents"
LEADER = AGENTES / "leader.md"
SPEC_AUTHOR = AGENTES / "spec-author.md"
IMPLEMENTER = AGENTES / "implementer.md"
REVIEWER = AGENTES / "reviewer.md"
QA = AGENTES / "qa-e2e.md"
CHECKPOINTS = RAIZ / "CHECKPOINTS.md"
SPECS = RAIZ / "specs" / "SPECS.md"
CLAUDE_MD = RAIZ / "CLAUDE.md"
GUIA = RAIZ.parent / "GUIA_INSTALACION.md"

LINEA_FINAL = "Tu OK es el permiso para integrar y desplegar; el arnés nunca despliega."
CABECERA_DECISIONES = "| Decisión | Opciones | Recomendado | Decidido |"
PREGUNTA_FRONTERA = "¿Cruza la frontera del proyecto?"
INICIO_RUESMA = "<!-- ==================== INICIO · ENTORNO DE RUESMA"
FIN_RUESMA = "<!-- ===================== FIN · ENTORNO DE RUESMA"

es_el_taller = pytest.mark.skipif(
    not (RAIZ.parent / "politica_ficheros.json").is_file(),
    reason="la guía es del taller, no del proyecto",
)


def _crudo(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _plano(texto_o_ruta: str | Path) -> str:
    texto = _crudo(texto_o_ruta) if isinstance(texto_o_ruta, Path) else texto_o_ruta
    return " ".join(texto.split())


def _seccion(texto: str, titulo: str) -> str:
    """Desde `titulo` hasta el siguiente encabezado de su mismo nivel o superior."""
    inicio = texto.index(titulo)
    nivel = titulo.split(" ", 1)[0]
    cortes = [texto.find("\n" + "#" * n + " ", inicio + len(titulo))
              for n in range(1, len(nivel) + 1)]
    cortes = [c for c in cortes if c != -1]
    return texto[inicio:min(cortes)] if cortes else texto[inicio:]


def _fila_leader(estado: str) -> str:
    return next(li for li in _crudo(LEADER).splitlines() if li.startswith(f"| `{estado}` |"))


def _plantillas() -> list[str]:
    # Las plantillas abren con «# …» dentro de su bloque: se corta solo en «## ».
    seccion = _crudo(LEADER).split("\n## Plantillas de las paradas\n", 1)[1].split("\n## ", 1)[0]
    return [trozo.split("```", 1)[0] for trozo in seccion.split("```markdown\n")[1:]]


# --- R1–R5: las paradas en leader.md ---------------------------------------------


def test_f070_r1_tres_plantillas_en_orden() -> None:
    plantillas = _plantillas()

    assert len(plantillas) == 3
    assert plantillas[0].startswith("# Resumen de la spec · F-XXX")
    assert plantillas[1].startswith("# PARADA 1 · F-XXX (sin spec)")
    assert plantillas[2].startswith("# Resumen final · F-XXX (PARADA 2)")


def test_f070_r2_el_resumen_de_la_spec_trae_decisiones_frontera_y_ok() -> None:
    plantilla = _plantillas()[0]

    assert CABECERA_DECISIONES in plantilla
    assert PREGUNTA_FRONTERA in plantilla
    assert "tu OK aprueba la spec y el plan" in _plano(plantilla)


def test_f070_r3_spec_ready_presenta_el_resumen_que_sustituye_a_la_parada_1() -> None:
    fila = _plano(_fila_leader("spec_ready"))

    assert "**resumen de la spec**" in fila and "sustituye a la PARADA 1" in fila
    assert "spec_aprobada" in fila
    assert "columna «Decidido» de `design.md`" in fila and "en el mismo commit" in fila
    assert "`in_progress`" in fila


def test_f070_r4_la_parada_1_es_solo_sin_spec() -> None:
    paradas = _plano(_seccion(_crudo(LEADER), "## Dos paradas obligatorias con el humano"))

    assert "**PARADA 1 — propuesta antes de implementar (solo `sdd: false`).**" in paradas
    assert "**Con spec (`sdd: true`), la primera parada es el resumen de la spec.**" in paradas
    assert "con `sdd: false`, **PARADA 1**" in _fila_leader("todo")
    en_curso = _fila_leader("in_progress")
    assert "sin ella no lanzas el implementer" in en_curso
    assert "PARADA 1** (solo `sdd: false`)" in en_curso


def test_f070_r5_el_resumen_final_pide_cifras_y_cierra_con_la_linea() -> None:
    plantilla = _plantillas()[2]
    plano = _plano(plantilla)

    for cifra in ("tests N/N", "cobertura", "mutantes", "supervivientes", "e2e N/N",
                  "`bash harness/init.sh`"):
        assert cifra in plano, cifra
    assert "**Listo para tu push:**" in plano
    assert [li for li in plantilla.splitlines() if li.strip()][-1] == LINEA_FINAL


# --- R6, R9: SPECS.md y spec-author.md --------------------------------------------


def _design_de_specs() -> str:
    return _plano(_seccion(_crudo(SPECS), "## 2. design.md"))


def test_f070_r6_specs_obliga_a_la_tabla_de_decisiones() -> None:
    seccion = _design_de_specs()

    assert "**Decisiones**" in seccion and CABECERA_DECISIONES in seccion
    assert "«Decidido» vacío al entregar" in seccion
    assert "lo escribe el líder con la respuesta del humano" in seccion


def test_f070_r6_el_spec_author_lo_pide_en_su_producto() -> None:
    producto = _plano(_seccion(_crudo(SPEC_AUTHOR), "## Producto"))

    assert "«Decisiones»" in producto and "«Decidido» vacío" in producto
    assert "«Frontera»" in producto and PREGUNTA_FRONTERA in producto


def test_f070_r9_specs_obliga_a_responder_la_frontera() -> None:
    seccion = _design_de_specs()

    assert "**Frontera**" in seccion and PREGUNTA_FRONTERA in seccion
    assert "sí/no" in seccion
    for cosa in ("endpoint", "tabla", "variable", "base"):
        assert cosa in seccion, cosa
    assert "qué documento del ecosistema se actualiza" in seccion


# --- R7, R8 y R30: CLAUDE.md (adaptado) -------------------------------------------

_INSTRUCCION_CLAUDE_MD = (
    "CLAUDE.md no trae lo de F-070 (primera parada con el resumen de la spec en "
    "«Ritmo de trabajo» y protocolo del repositorio del ecosistema en el bloque de "
    "Ruesma): al actualizar el arnés, acepta esos bloques del diff de CLAUDE.md"
)


def _ritmo(texto: str) -> str:
    titulo = "## Ritmo de trabajo con el humano"
    return _plano(_seccion(texto, titulo)) if titulo in texto else ""


def _bloque_ruesma(texto: str) -> str | None:
    """El bloque de Ruesma, o None si el proyecto lo borró (está fuera de Ruesma)."""
    if INICIO_RUESMA not in texto:
        return None
    return texto.split(INICIO_RUESMA, 1)[1].split(FIN_RUESMA, 1)[0]


def _motivo_claude_md_viejo(texto: str) -> str | None:
    """El rojo de R30 si este CLAUDE.md es de antes de F-070; o None."""
    ritmo_nuevo = "resumen de la spec" in _ritmo(texto) and LINEA_FINAL in _ritmo(texto)
    bloque = _bloque_ruesma(texto)
    ruesma_nuevo = bloque is None or "git pull --rebase" in bloque
    return None if ritmo_nuevo and ruesma_nuevo else _INSTRUCCION_CLAUDE_MD


_MOTIVO_CLAUDE_MD = _motivo_claude_md_viejo(_crudo(CLAUDE_MD))
claude_md_de_f070 = pytest.mark.skipif(
    _MOTIVO_CLAUDE_MD is not None, reason=_MOTIVO_CLAUDE_MD or "")


def test_f070_r30_el_claude_md_instalado_trae_paradas_y_ecosistema() -> None:
    motivo = _motivo_claude_md_viejo(_crudo(CLAUDE_MD))

    assert motivo is None, motivo


@claude_md_de_f070
def test_f070_r7_ritmo_de_trabajo_con_spec_y_linea_final() -> None:
    ritmo = _ritmo(_crudo(CLAUDE_MD))

    assert "Con spec, la primera parada es el **resumen de la spec**" in ritmo
    assert "**qué queda listo para que el humano haga push**" in ritmo
    assert LINEA_FINAL in ritmo
    # Pasada 2: la autorización de subagentes ya no da la PARADA 1 por única.
    autorizacion = _plano(_seccion(_crudo(CLAUDE_MD), "## Autorización permanente de subagentes"))
    assert ("la primera parada (el resumen de la spec, o la PARADA 1 sin spec) sigue siendo "
            "obligatoria") in autorizacion
    assert "la PARADA 1 de la sección siguiente sigue siendo obligatoria" not in autorizacion


@claude_md_de_f070
def test_f070_r8_la_regla_dura_del_push_sigue_d3() -> None:
    reglas = _plano(_seccion(_crudo(CLAUDE_MD), "## Reglas duras (no negociables)"))

    # Pasada 3: el merge a `main` se pregunta antes (humano, 2026-11-12).
    assert ("Los agentes nunca hacen `git push`: lo hace siempre un humano. Commits y merges, "
            "sí: sin preguntar, salvo el merge a `main`, que se pregunta antes (ver "
            "`leader.md`, «Commits, merges y push»). PRs, solo con petición explícita.") in reglas
    assert "Commits y merges, sí, sin preguntar" not in reglas
    assert "`git push` ni crean PRs salvo petición explícita" not in _plano(CLAUDE_MD)


@claude_md_de_f070
def test_f070_r30_un_claude_md_viejo_da_el_motivo_con_instrucciones() -> None:
    actual = _plano(CLAUDE_MD)
    viejos = (actual.replace("resumen de la spec", "x"), actual.replace(LINEA_FINAL, "y"),
              actual.replace("git pull --rebase", "z"), "")

    for viejo in viejos:
        assert _motivo_claude_md_viejo(viejo) == _INSTRUCCION_CLAUDE_MD
    sin_ruesma = actual.split(INICIO_RUESMA, 1)[0]
    assert _motivo_claude_md_viejo(sin_ruesma) is None, "fuera de Ruesma no hay rojo"
    assert "acepta esos bloques del diff de CLAUDE.md" in _INSTRUCCION_CLAUDE_MD


# --- R8: el bloque de Ruesma de CLAUDE.md ----------------------------------------


@claude_md_de_f070
def test_f070_r8_el_bloque_de_ruesma_trae_el_protocolo_compartido() -> None:
    bloque = _bloque_ruesma(_crudo(CLAUDE_MD))
    assert bloque is not None, "el payload trae el bloque de Ruesma"
    seccion = _plano(bloque.split("### El ecosistema: `azure-apps/`", 1)[1].split("### ", 1)[0])

    assert "**repositorio del ecosistema**" in seccion and "**compartido en GitHub**" in seccion
    for paso in ("`git pull --rebase` antes de editar", "**solo el documento del propio proyecto**",
                 "**commit aparte**", "**el push lo hace siempre el humano**", "**PARAR**"):
        assert paso in seccion, paso


@claude_md_de_f070
def test_f070_r8_el_bloque_de_ruesma_dice_las_cuentas_de_github() -> None:
    # OK del humano del 2026-11-12, opción (a): solo nombres de cuenta, sin correos.
    bloque = _bloque_ruesma(_crudo(CLAUDE_MD))
    assert bloque is not None, "el payload trae el bloque de Ruesma"

    assert ("Cuentas de GitHub: los repositorios viven en la organización `ruesma-dev`. Solo la "
            "cuenta `pablogris` sube directamente a `main` y `dev`; el resto entra por pull "
            "request con revisión previa de `pablogris`. El push lo hace siempre un humano."
            ) in _plano(bloque)
    assert "@" not in bloque, "el bloque de Ruesma no lleva direcciones de correo"
    assert "ruesma-dev" not in _crudo(CLAUDE_MD).split(INICIO_RUESMA, 1)[0]


# --- Pasada 3: quién hace cada merge (humano, 2026-11-12, tras la review 2) ------


def _commits_merges_y_push() -> str:
    paradas = _plano(_seccion(_crudo(LEADER), "## Dos paradas obligatorias con el humano"))
    return paradas.split("**Commits, merges y push.**", 1)[1]


def test_f070_d3_el_lider_dice_quien_hace_cada_merge() -> None:
    regla = _commits_merges_y_push()

    assert ("el de la rama de la feature a `dev` (la `RAMA_BASE`), **sin preguntar**, tras el OK "
            "del humano al resumen final") in regla
    assert "el de la rama espejo, **sin preguntar**, justo después" in regla
    assert "el de `main`, **preguntando antes** al humano" in regla
    assert "El `git push` lo hace **siempre un humano**" in regla


def test_f070_d3_la_rama_espejo_la_adelanta_el_lider() -> None:
    ramas = _plano(_seccion(_crudo(LEADER), "## Ramas"))

    assert "la adelanta el líder **sin preguntar**" in ramas
    assert "la adelanta el **humano**" not in ramas
    assert "el líder solo se lo **recuerda**" not in ramas
    assert "allí solo llegan merges" in ramas


@claude_md_de_f070
def test_f070_d3_claude_md_dev_y_main_solo_reciben_merges() -> None:
    reglas = _plano(_seccion(_crudo(CLAUDE_MD), "## Reglas duras (no negociables)"))

    assert ("Nunca commits directos a `dev` ni a `main`: allí solo llegan merges (ver "
            "`leader.md`, «Commits, merges y push»).") in reglas


CONVENTIONS = RAIZ / "docs" / "CONVENTIONS.md"
_VIEJA_CONVENTIONS = "merge a dev y PRs: siempre el humano"
_NUEVA_CONVENTIONS = "Merges: a `dev` y a la rama espejo, el líder sin preguntar"
_INSTRUCCION_CONVENTIONS = (
    "docs/CONVENTIONS.md no trae lo de F-070 (quién hace cada merge: a `dev` y a la "
    "rama espejo el líder sin preguntar, a `main` preguntando, el push siempre el "
    "humano): al actualizar el arnés, acepta la sección «Git» del diff de "
    "docs/CONVENTIONS.md"
)


def _motivo_conventions_viejo(texto: str | None) -> str | None:
    """El rojo si este CONVENTIONS.md es de antes de F-070; None si no existe."""
    if texto is None:
        return None
    plano = _plano(texto)
    nuevo = _NUEVA_CONVENTIONS in plano and _VIEJA_CONVENTIONS not in plano
    return None if nuevo else _INSTRUCCION_CONVENTIONS


def _conventions() -> str | None:
    return _crudo(CONVENTIONS) if CONVENTIONS.is_file() else None


_MOTIVO_CONVENTIONS = _motivo_conventions_viejo(_conventions())
conventions_de_f070 = pytest.mark.skipif(
    _MOTIVO_CONVENTIONS is not None, reason=_MOTIVO_CONVENTIONS or "")


def test_f070_d3_el_conventions_instalado_dice_quien_hace_cada_merge() -> None:
    motivo = _motivo_conventions_viejo(_conventions())

    assert motivo is None, motivo


@conventions_de_f070
def test_f070_d3_conventions_merges_y_push() -> None:
    texto = _conventions()
    if texto is None:
        pytest.skip("el proyecto no tiene docs/CONVENTIONS.md")
    git = _plano(_seccion(texto, "## Git"))

    assert ("Merges: a `dev` y a la rama espejo, el líder sin preguntar tras el OK del humano "
            "al resumen final; a `main`, el líder preguntando antes.") in git
    assert "Push: siempre el humano. PRs: solo con petición explícita." in git
    assert _VIEJA_CONVENTIONS not in git
    for viejo in (texto.replace(_NUEVA_CONVENTIONS, "x"), texto + _VIEJA_CONVENTIONS):
        assert _motivo_conventions_viejo(_plano(viejo)) == _INSTRUCCION_CONVENTIONS
    assert _motivo_conventions_viejo(None) is None


# --- R10–R11, R13: implementer.md ------------------------------------------------


def _documento_del_ecosistema() -> str:
    return _plano(_seccion(_crudo(IMPLEMENTER), "## Documento del ecosistema"))


def test_f070_r10_el_implementer_aplica_el_protocolo_solo_si_cruza() -> None:
    seccion = _documento_del_ecosistema()

    assert f"responde «sí» a «{PREGUNTA_FRONTERA}»" in seccion
    assert "`CLAUDE.md` declara un repositorio del ecosistema" in seccion
    for paso in ("`git pull --rebase`", "solo el documento del propio proyecto", "commit aparte",
                 "la ruta del documento y el SHA de ese commit", "**Nunca haces push**"):
        assert paso in seccion, paso


def test_f070_r11_un_conflicto_es_blocked_sin_resolverlo() -> None:
    seccion = _documento_del_ecosistema()

    assert "Si el `git pull --rebase` da conflicto" in seccion
    assert "marca la feature `blocked`" in seccion
    assert "sin resolverlo ni tocar otros documentos" in seccion


def test_f070_r13_los_genericos_no_nombran_el_repositorio_de_ruesma() -> None:
    for ruta in (IMPLEMENTER, REVIEWER, CHECKPOINTS, LEADER, SPECS, SPEC_AUTHOR):
        assert "azure-apps" not in _crudo(ruta), ruta.name
    assert "repositorio del ecosistema que declare `CLAUDE.md`" in _plano(IMPLEMENTER)


def test_f070_r12_el_reviewer_recorre_c3_quater() -> None:
    texto = _plano(REVIEWER)
    paso_6 = texto.split(" 6. Recorre lo que pide el carril", 1)[1].split(" 7. ", 1)[0]

    assert "C3 quater" in paso_6


# --- R12, R26, R29: CHECKPOINTS.md (adaptado) ------------------------------------

_INSTRUCCION_CHECKPOINTS = (
    "CHECKPOINTS.md no trae lo de F-070 (bloque «C3 quater» del documento del "
    "ecosistema y las dos pasadas, principal y de reviewer de evidencias, en C4 "
    "bis): al actualizar el arnés, acepta esos bloques del diff de CHECKPOINTS.md"
)


def _motivo_checkpoints_viejo(texto: str) -> str | None:
    """El rojo de R29 si este CHECKPOINTS.md es de antes de F-070; o None."""
    nuevo = "## C3 quater" in texto and "reviewer de evidencias" in texto
    return None if nuevo else _INSTRUCCION_CHECKPOINTS


_MOTIVO_CHECKPOINTS = _motivo_checkpoints_viejo(_crudo(CHECKPOINTS))
checkpoints_de_f070 = pytest.mark.skipif(
    _MOTIVO_CHECKPOINTS is not None, reason=_MOTIVO_CHECKPOINTS or "")


def test_f070_r29_el_checkpoints_instalado_trae_c3_quater_y_evidencias() -> None:
    motivo = _motivo_checkpoints_viejo(_crudo(CHECKPOINTS))

    assert motivo is None, motivo


def _c3_quater() -> str:
    return _plano(_seccion(_crudo(CHECKPOINTS), "## C3 quater"))


@checkpoints_de_f070
def test_f070_r12_c3_quater_con_su_na_y_sus_checkboxes() -> None:
    texto = _crudo(CHECKPOINTS)
    bloque = _c3_quater()

    assert "## C3 quater — El documento del ecosistema está al día" in texto
    assert texto.index("## C3 ter") < texto.index("## C3 quater") < texto.index("## C4 —")
    assert "es N/A" in bloque and "responde «no»" in bloque
    assert "`CLAUDE.md` no declara repositorio del ecosistema" in bloque
    for punto in ("- [ ] Solo cambia el documento del propio proyecto",
                  "- [ ] Va en un **commit aparte**", "su SHA consta en `progress/impl_F-XXX.md`",
                  "- [ ] **Ningún agente hizo push**"):
        assert punto in bloque, punto


@checkpoints_de_f070
def test_f070_r29_un_checkpoints_viejo_da_el_motivo_con_instrucciones() -> None:
    actual = _crudo(CHECKPOINTS)
    viejos = (actual.replace("## C3 quater", "## Otro"),
              actual.replace("reviewer de evidencias", "otro"), "")

    for viejo in viejos:
        assert _motivo_checkpoints_viejo(viejo) == _INSTRUCCION_CHECKPOINTS
    assert "acepta esos bloques del diff de CHECKPOINTS.md" in _INSTRUCCION_CHECKPOINTS


# --- R22–R28: orden de fases en in_review -----------------------------------------

ORDEN = ("**implementer**", "**reviewer principal**", "**`qa-e2e`**", "**Pasada de campaña**",
         "**reviewer de evidencias**")


def _orden_de_fases() -> str:
    return _plano(_seccion(_crudo(LEADER), "## Orden de fases en `in_review`"))


def _en_orden(texto: str, marcas: tuple[str, ...]) -> bool:
    posiciones = [texto.find(m) for m in marcas]
    return -1 not in posiciones and posiciones == sorted(posiciones)


def test_f070_r22_la_fila_y_la_seccion_dicen_el_mismo_orden() -> None:
    fila = _fila_leader("in_review")
    seccion = _orden_de_fases()

    assert ("reviewer principal → `qa-e2e` (si la capa aplica) → campaña (si el nivel la "
            "lanza) → reviewer de evidencias") in fila
    assert "«Orden de fases en `in_review`»" in fila
    assert _en_orden(seccion, ORDEN), seccion
    assert "## Fase QA (capa e2e)" not in _crudo(LEADER)


def test_f070_r22_qa_e2e_llega_tras_el_reviewer_principal() -> None:
    assert "con el APPROVED del reviewer principal" in _plano(QA)


def test_f070_r23_cuando_hay_reviewer_de_evidencias() -> None:
    seccion = _orden_de_fases()

    assert "con `effort` `medium`" in seccion
    assert "solo si hubo `qa-e2e` o una mutación **exigida** por el nivel" in seccion
    assert ("Sin `qa-e2e` ni mutación exigida, el APPROVED del reviewer principal lleva a "
            "`human_review`") in seccion
    assert "con el esfuerzo del reviewer principal del carril" in seccion  # D4


def test_f070_r24_el_implementer_lanza_la_campana_en_la_pasada() -> None:
    texto = _plano(IMPLEMENTER)

    assert "**no la lanzas al terminar**" in texto
    assert "**pasada de campaña**, tras el APPROVED del reviewer principal" in texto
    assert "y, si hubo `qa-e2e`, tras su verde" in texto
    assert "lanza la campaña **al terminar**" not in texto
    assert "lánzala igual al terminar" not in texto


def test_f070_r25_el_reviewer_distingue_las_dos_pasadas() -> None:
    seccion = _plano(_seccion(_crudo(REVIEWER), "## Dos pasadas: principal y de evidencias"))

    assert "«pendiente: pasada de evidencias»" in seccion and "ni `[ ]` ni N/A" in seccion
    assert "`Revisión de evidencias desde <SHA>`" in seccion
    assert "el delta desde el SHA aprobado" in seccion
    assert "toca código de producción" in seccion  # D4
    assert "reescribes `progress/review_F-XXX.md`" in seccion  # D5


def test_f070_r27_rojo_y_rechazo_de_evidencias_cuentan_en_los_ciclos() -> None:
    seccion = _orden_de_fases()

    assert "devuelve la feature a `in_progress` y **cuenta en los 2 ciclos**" in seccion
    assert "lo mismo un CHANGES_REQUESTED del reviewer de evidencias" in seccion


def test_f070_r28_express_y_documental_sin_fases_caras() -> None:
    assert ("`express` y `documental`: **sin `qa-e2e`, sin campaña y sin reviewer de "
            "evidencias**") in _orden_de_fases()


@checkpoints_de_f070
def test_f070_r26_checkpoints_orden_y_cabecera_de_c4_bis() -> None:
    texto = _crudo(CHECKPOINTS)
    plano = _plano(texto)
    orden = plano.split("Comandos de las puertas:", 1)[1].split("## C1", 1)[0]
    c4_bis = _plano(_seccion(texto, "## C4 bis"))

    assert "**`qa-e2e` antes de la campaña de mutación**" in plano
    assert _en_orden(orden, ("reviewer principal", "`qa-e2e`", "pasada de campaña",
                             "reviewer de evidencias")), orden
    assert "«Orden de fases en `in_review`»" in orden
    assert "**Dos pasadas.**" in c4_bis and "«pendiente: pasada de evidencias»" in c4_bis
    principal = c4_bis.split("**pasada principal**", 1)[1].split("**reviewer de evidencias**", 1)[0]
    for punto in ("nivel", "fase RED", "cobertura", "«Evidencias»"):
        assert punto in principal, punto
    evidencias = c4_bis.split("**reviewer de evidencias**", 1)[1].split("- [ ]", 1)[0]
    for punto in ("mutación", "RM1–RM7", "supervivientes", "capa e2e"):
        assert punto in evidencias, punto


def test_f070_r29_los_dependientes_llevan_su_marca_y_los_rojos_no() -> None:
    marcas = {"test_f070_r7_": claude_md_de_f070, "test_f070_r8_": claude_md_de_f070,
              "test_f070_r30_un_claude_md_": claude_md_de_f070,
              "test_f070_r12_c3_quater_": checkpoints_de_f070,
              "test_f070_r26_": checkpoints_de_f070,
              "test_f070_r29_un_checkpoints_": checkpoints_de_f070,
              "test_f070_d3_claude_md_": claude_md_de_f070,
              "test_f070_d3_conventions_merges": conventions_de_f070}
    for prefijo, marca in marcas.items():
        funciones = [f for n, f in globals().items() if n.startswith(prefijo) and callable(f)]
        assert funciones, prefijo
        for funcion in funciones:
            assert marca.mark in getattr(funcion, "pytestmark", []), funcion.__name__
    for rojo in (test_f070_r30_el_claude_md_instalado_trae_paradas_y_ecosistema,
                 test_f070_r29_el_checkpoints_instalado_trae_c3_quater_y_evidencias,
                 test_f070_d3_el_conventions_instalado_dice_quien_hace_cada_merge):
        assert not getattr(rojo, "pytestmark", []), rojo.__name__


# --- R31–R32: la guía y los ficheros del payload ----------------------------------


def _entrada_de_la_guia() -> str:
    texto = _plano(GUIA)
    titulo = "### Paradas, ecosistema, modelo y esfuerzo, orden de fases (F-070)"
    return texto.split(titulo, 1)[1].split(" ## ", 1)[0]


@es_el_taller
def test_f070_r31_la_guia_dice_que_aceptar_en_cada_adaptado() -> None:
    entrada = _entrada_de_la_guia()

    for fichero, rojo in (("`CHECKPOINTS.md`", "test_f070_r29_el_checkpoints_instalado_trae_c3_quater_y_evidencias"),
                          ("`CLAUDE.md`", "test_f070_r30_el_claude_md_instalado_trae_paradas_y_ecosistema"),
                          ("`.claude/settings.json`", "test_f070_r30_el_settings_instalado_trae_model_y_effortlevel")):
        assert fichero in entrada and rojo in entrada, fichero
    assert "Acepta" in entrada
    assert "la 1.9.0 llevaba `model: inherit`" in entrada
    assert "v2.1.292" in entrada
    assert "`politica_ficheros.json` e `instalar_arnes.ps1` no cambian" in entrada


@es_el_taller
def test_f070_r32_el_payload_no_gana_ni_pierde_ficheros_fuera_de_tests() -> None:
    import subprocess

    salida = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", "dev", "--", ".",
         ":(exclude)tests", ":(exclude)BACKLOG.md", ":(exclude)progress", ":(exclude)coverage.json"],
        cwd=RAIZ, capture_output=True, text=True, check=False)
    if salida.returncode != 0:
        pytest.skip("sin git o sin rama `dev`")
    estados = {linea.split("\t", 1)[0] for linea in salida.stdout.splitlines() if linea}
    assert estados <= {"M"}, salida.stdout
    assert sorted(p.name for p in (RAIZ / ".claude" / "agents").iterdir()) == [
        "implementer.md", "leader.md", "qa-e2e.md", "reviewer.md", "spec-author.md"]
    fuera = subprocess.run(["git", "diff", "--name-only", "dev", "--", "politica_ficheros.json",
                            "instalar_arnes.ps1"], cwd=RAIZ.parent, capture_output=True,
                           text=True, check=False)
    assert fuera.stdout.strip() == ""
