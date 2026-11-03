"""
preprocesamiento.py
-------------------
Paso 3 de CodificaMed: preprocesar una nota clínica y detectar negaciones.

Flujo completo (lo que hace detectar_menciones):
    nota -> segmentar -> expandir abreviaturas -> normalizar -> buscar términos del
    catálogo CIE-10 -> decidir si cada término está "confirmado" o "negado".
"""

import csv
import re
import unicodedata
from pathlib import Path

# Ruta de la raíz del proyecto (la carpeta que contiene "src" y "data")
RAIZ = Path(__file__).resolve().parent.parent
RUTA_CATALOGO = RAIZ / "data" / "cie10_catalogo.csv"


# ---------------------------------------------------------------------------
# ETAPA A: normalizar el texto
# ---------------------------------------------------------------------------

def quitar_acentos(texto):
    """'Hipertensión' -> 'Hipertension'. También convierte 'ñ' en 'n'."""
    # NFD separa cada letra de su acento: 'ó' pasa a ser 'o' + marca de acento
    descompuesto = unicodedata.normalize("NFD", texto)
    # Nos quedamos con todo lo que NO sea una marca de acento (categoría "Mn")
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar(texto):
    """Pasa a minúsculas y deja un solo espacio entre palabras."""
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


# ---------------------------------------------------------------------------
# ETAPA B: expandir abreviaturas
# ---------------------------------------------------------------------------

# Las claves van en minúscula. Puedes agregar más abreviaturas aquí.
ABREVIATURAS = {
    "hta": "hipertensión arterial",
    "dm1": "diabetes mellitus tipo 1",
    "dm2": "diabetes mellitus tipo 2",
    "itu": "infección urinaria",
    "ivu": "infección urinaria",
    "iam": "infarto agudo de miocardio",
    "icc": "insuficiencia cardiaca",
    "epoc": "enfermedad pulmonar obstructiva crónica",
    "erc": "enfermedad renal crónica",
    "nac": "neumonía adquirida en la comunidad",
    "abd": "abdominal",
    "dx": "diagnóstico",
    "rx": "radiografía",
}

# \b = "límite de palabra": evita reemplazar 'itu' dentro de otra palabra.
# Ordenamos de la clave más larga a la más corta por seguridad.
_PATRON_ABREV = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(ABREVIATURAS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def expandir_abreviaturas(texto):
    """Devuelve (texto_expandido, lista_de_cambios). Ej.: 'HTA' -> 'hipertensión arterial'."""
    cambios = []

    def reemplazar(coincidencia):
        original = coincidencia.group(1)
        expandida = ABREVIATURAS[original.lower()]
        cambios.append((original, expandida))
        return expandida

    return _PATRON_ABREV.sub(reemplazar, texto), cambios


# ---------------------------------------------------------------------------
# ETAPA C: segmentar la nota
# ---------------------------------------------------------------------------

def segmentar(texto):
    """
    Divide la nota en segmentos usando punto, punto y coma o salto de línea.
    Guarda el texto ORIGINAL y su posición (inicio, fin) para poder mostrarlo
    después como "evidencia" en la interfaz.
    """
    segmentos = []
    for m in re.finditer(r"[^.;\n]+", texto):
        if m.group().strip():
            segmentos.append({"texto": m.group().strip(), "inicio": m.start(), "fin": m.end()})
    return segmentos


# ---------------------------------------------------------------------------
# ETAPA D: detección de negación (idea de NegEx)
# ---------------------------------------------------------------------------

# Palabras que niegan lo que viene DESPUÉS de ellas. Van sin acentos porque
# el texto se compara ya sin acentos. Las frases largas van primero.
DISPARADORES = [
    "no hay evidencia de", "no refiere", "no presenta", "se descarta", "ausencia de",
    "negativo para", "descarta", "niega", "sin", "no",
]

# Palabras que CORTAN el alcance de la negación: lo que viene después ya no está negado.
TERMINADORES = ["pero", "aunque", "excepto", "presenta", "refiere", "con"]

# Palabras que niegan lo que está justo ANTES: "neumonía descartada"
_PATRON_POST = re.compile(r"\s*(descartad[oa]s?|negativ[oa]s?)\b")

_PATRON_DISPARADOR = re.compile(r"\b(?:" + "|".join(DISPARADORES) + r")\b")
_PATRON_TERMINADOR = re.compile(r"\b(?:" + "|".join(TERMINADORES) + r")\b")

# Máximo de palabras permitidas entre el disparador y el término negado
VENTANA = 6


def _preparar_para_negacion(texto):
    """'afebril' equivale a 'sin fiebre'; 'sin embargo' es un conector, no una negación."""
    texto = texto.replace("sin embargo", "pero")
    texto = re.sub(r"\bafebril\b", "sin fiebre", texto)
    return texto


def preparar_segmento(texto):
    """Pipeline completo para un segmento: expandir -> normalizar -> sin acentos -> ajustes."""
    expandido, _ = expandir_abreviaturas(texto)
    return _preparar_para_negacion(quitar_acentos(normalizar(expandido)))


def esta_negado(texto, inicio, fin):
    """
    Decide si el término que ocupa texto[inicio:fin] está negado.
    'texto' debe estar ya normalizado y sin acentos.
    """
    antes = texto[:inicio]

    # Buscamos el ÚLTIMO disparador que aparece antes del término
    ultimo = None
    for m in _PATRON_DISPARADOR.finditer(antes):
        ultimo = m
    if ultimo is not None:
        entre = antes[ultimo.end():]  # lo que hay entre el disparador y el término
        corta = _PATRON_TERMINADOR.search(entre)
        cerca = len(entre.split()) <= VENTANA
        if not corta and cerca:
            return True

    # Negación posterior: "neumonía descartada"
    if _PATRON_POST.match(texto[fin:]):
        return True
    return False


# ---------------------------------------------------------------------------
# Catálogo y búsqueda de términos
# ---------------------------------------------------------------------------

def cargar_catalogo(ruta=RUTA_CATALOGO):
    """Lee el CSV y devuelve {codigo: {"descripcion": ..., "terminos": [...]}}."""
    catalogo = {}
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            desc = fila["descripcion"]
            candidatos = [desc, desc.split(",")[0]]  # 'Neumonía, no especificada' -> 'Neumonía'
            candidatos += [re.sub(r"\s*\(.*?\)", "", c) for c in candidatos]  # quita paréntesis
            candidatos += fila["sinonimos"].split(";")
            terminos = {quitar_acentos(normalizar(c)) for c in candidatos if c.strip()}
            catalogo[fila["codigo"]] = {"descripcion": desc, "terminos": sorted(terminos)}
    return catalogo


def _construir_indice(catalogo):
    """Lista de (término, código) ordenada del término más largo al más corto."""
    indice = [(t, cod) for cod, datos in catalogo.items() for t in datos["terminos"]]
    indice.sort(key=lambda par: len(par[0]), reverse=True)
    return indice


def detectar_menciones(texto, catalogo=None):
    """
    Busca en la nota los términos del catálogo y marca cada uno como
    'confirmado' o 'negado'. Devuelve una lista de diccionarios con:
    codigo, termino, estado y evidencia (el segmento original).
    """
    if catalogo is None:
        catalogo = cargar_catalogo()
    indice = _construir_indice(catalogo)

    menciones = []
    for seg in segmentar(texto):
        t = preparar_segmento(seg["texto"])

        ocupados = []  # posiciones ya usadas por un término más largo
        for termino, codigo in indice:
            for m in re.finditer(r"\b" + re.escape(termino) + r"\b", t):
                if any(m.start() < f and m.end() > i for i, f in ocupados):
                    continue
                ocupados.append((m.start(), m.end()))
                menciones.append({
                    "codigo": codigo,
                    "termino": termino,
                    "estado": "negado" if esta_negado(t, m.start(), m.end()) else "confirmado",
                    "evidencia": seg["texto"],
                })
    return menciones
