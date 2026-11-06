"""Auditor: comprueba que un texto redactado por la IA NO contenga nada que no este en sus fuentes.

Es codigo determinista, no IA. Un texto con problemas "duros" no puede aprobarse (si lo escribio la IA).
Comprobaciones duras (bloquean):
  * cifras: todo numero del texto debe aparecer en las fuentes; tambien las cifras en palabras
  * entidades: nombres propios y siglas (palabras con mayuscula que no abren frase) deben estar en las fuentes
  * tecnologias y organizaciones conocidas: no pueden aparecer si las fuentes no las mencionan
  * afirmaciones: liderazgo, cargos de direccion, titulos, premios... solo si estan en las fuentes
  * forma: no vacio, sin marcas de formato ni marcadores, longitud maxima
Avisos (informan, no bloquean): palabras nuevas, adjetivos de autoelogio.

LIMITES conocidos: el nombre propio que abre una frase no se compara (se cubren las marcas y empresas
mas comunes con una lista); el auditor reduce el riesgo, no lo elimina. La aprobacion del usuario es
la ultima barrera.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.modules.extraction.evidence import normalize

MAX_NUEVAS = 12

TECNOLOGIAS = frozenset(
    """python java javascript typescript sql mysql postgresql postgres mongodb oracle sqlite aws azure gcp
    docker kubernetes linux git github gitlab jenkins react angular vue nodejs node django flask fastapi spring
    excel tableau sap salesforce jira scrum kanban pandas numpy tensorflow pytorch spark hadoop kafka redis
    terraform ansible php ruby rust swift kotlin android ios figma photoshop autocad matlab powershell bash
    html css graphql rest api devops cloud blockchain""".split()
)
ORGANIZACIONES = frozenset(
    """google microsoft amazon meta apple ibm intel nvidia tesla netflix facebook twitter linkedin uber
    spotify accenture deloitte mckinsey oracle samsung huawei""".split()
)
# Afirmaciones que solo son validas si las fuentes las contienen.
AFIRMACIONES = frozenset(
    """lider liderazgo lidere lidero liderar liderando lideraba dirigi dirigio dirigir dirigiendo gerente
    gerencia director directora jefe jefa coordinador coordinadora supervisor supervisora senior junior experto
    experta especialista certificado certificada certificacion certificaciones master maestria doctor doctora
    doctorado premio premiado premiada galardonado galardonada pionero pionera mejor
    duplico duplicar duplicando duplique triplico triplicar triplicando triplique""".split()
)
RAIZ = 5  # las afirmaciones se comparan por raiz para cubrir conjugaciones (lidere/lidero)
EXACTAS = frozenset({"mejor"})  # «mejor» no se respalda con «mejora» o «mejoré»
NUMEROS_EN_PALABRAS = frozenset(
    """dos tres cuatro cinco seis siete ocho nueve diez once doce quince veinte treinta cuarenta cincuenta
    sesenta setenta ochenta noventa cien ciento mil millon millones doble triple mitad decena decenas
    docena centenar""".split()
)
AUTOELOGIO = frozenset(
    """amplia solida extensa destacada excelente experimentado experimentada altamente reconocido reconocida
    sobresaliente excepcional brillante""".split()
)
# Palabras funcionales o muy generales que no deben avisarse como "nuevas".
COMUNES = frozenset(
    """para como entre sobre desde hasta durante mediante cuando donde tambien ademas cada otros otras
    este esta estos estas esos esas ellos ellas tiene tener tienen tuvo siendo sido sera fueron habia
    donde dentro fuera mismo misma mismos mismas nuestro nuestra equipo equipos proyecto proyectos
    trabajo trabajos experiencia profesional profesionales area areas nivel diferentes diversos diversas
    proceso procesos tareas tarea gestion apoyo resultados resultado empresa empresas actualmente
    responsable responsables mediante mejora mejoras""".split()
)

_PLACEHOLDER = re.compile(r"[<>{}\[\]*`]|^\s*#+\s|lorem ipsum|\bxxx+\b|\btbd\b|\bpor definir\b", re.I | re.M)
_NUMERO = re.compile(r"\d+(?:[.,]\d+)*")
_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\wÁÉÍÓÚÜÑáéíóúüñ&+#.-]*|\d+(?:[.,]\d+)*")


@dataclass(frozen=True)
class Issue:
    tipo: str  # vacio | longitud | formato | cifra_nueva | cifra_en_palabras | entidad_nueva | tecnologia_nueva | afirmacion_sin_respaldo
    detalle: str

    def as_dict(self) -> dict:
        return {"tipo": self.tipo, "detalle": self.detalle}


@dataclass
class AuditResult:
    issues: list[Issue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def _tokens(texto: str) -> set[str]:
    return set(normalize(texto).split())


def _inicia_frase(texto: str, pos: int) -> bool:
    previo = texto[:pos].rstrip(" \t•*-–—\"'(")
    return not previo or previo[-1] in ".!?:;\n"


def auditar(texto: str, fuentes: Iterable[str], *, max_chars: int, min_chars: int = 10) -> AuditResult:
    r = AuditResult()
    texto = texto or ""
    limpio = texto.strip()
    if not limpio:
        r.issues.append(Issue("vacio", "El texto está vacío."))
        return r
    if len(limpio) < min_chars:
        r.issues.append(Issue("longitud", f"Demasiado corto (mínimo {min_chars} caracteres)."))
    if len(limpio) > max_chars:
        r.issues.append(Issue("longitud", f"Demasiado largo: {len(limpio)} de {max_chars} caracteres."))
    if _PLACEHOLDER.search(limpio):
        r.issues.append(Issue("formato", "Contiene marcas de formato o marcadores sin completar."))

    src = _tokens(" \n ".join(fuentes))
    ya: set[tuple[str, str]] = set()

    def avisar(tipo: str, valor: str, detalle: str) -> None:
        if (tipo, valor) not in ya:
            ya.add((tipo, valor))
            r.issues.append(Issue(tipo, detalle))

    # 1) cifras
    for num in _NUMERO.findall(limpio):
        for parte in re.split(r"[.,]", num):
            if parte and parte not in src:
                avisar("cifra_nueva", parte, f"La cifra «{num}» no aparece en tus datos.")
    out_tokens = normalize(limpio).split()
    for t in out_tokens:
        if t in NUMEROS_EN_PALABRAS and t not in src:
            avisar("cifra_en_palabras", t, f"La cantidad «{t}» no aparece en tus datos.")

    # 2) entidades: mayusculas que no abren frase, siglas y mezclas letra-numero
    for m in _PALABRA.finditer(limpio):
        palabra = m.group(0).strip(".-&+#")
        if not palabra or palabra[0].isdigit():
            continue
        es_sigla = len(palabra) >= 2 and palabra.isupper()
        es_nombre = palabra[0].isupper() and not _inicia_frase(limpio, m.start())
        mezcla = any(c.isdigit() for c in palabra)
        if es_sigla or es_nombre or mezcla:
            faltan = [p for p in normalize(palabra).split() if len(p) > 1 and p not in src]
            if faltan:
                avisar("entidad_nueva", palabra.lower(), f"«{palabra}» no aparece en tus datos.")

    # 3) tecnologias, organizaciones y afirmaciones (tambien en minusculas y al inicio de frase)
    raices_src = {s[:RAIZ] for s in src}  # «Lideré» en tus datos respalda «Lideró» en el texto
    vistas: set[str] = set()
    for t in out_tokens:
        if t in vistas or t in src:
            continue
        vistas.add(t)
        if t in TECNOLOGIAS or t in ORGANIZACIONES:
            avisar("tecnologia_nueva", t, f"«{t}» no aparece en tus datos.")
        elif t in AFIRMACIONES and (t in EXACTAS or t[:RAIZ] not in raices_src):
            avisar("afirmacion_sin_respaldo", t, f"«{t}» es una afirmación que no aparece en tus datos.")

    # 4) avisos informativos
    nuevas: list[str] = []
    for t in dict.fromkeys(out_tokens):
        if len(t) >= 5 and not t.isdigit() and t not in src and t not in COMUNES and t not in nuevas:
            if t in AUTOELOGIO:
                r.warnings.append(
                    f"«{t}» es un adjetivo de autoelogio que no está en tus datos; considera quitarlo."
                )
            else:
                nuevas.append(t)
    if nuevas:
        r.warnings.append("Palabras que no estaban en tus datos: " + ", ".join(nuevas[:MAX_NUEVAS]) + ".")
    return r
