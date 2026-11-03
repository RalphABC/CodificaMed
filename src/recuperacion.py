"""
recuperacion.py
---------------
Paso 4 de CodificaMed: dado un texto clínico, recuperar los códigos CIE-10
"candidatos" más parecidos del catálogo (la R de RAG = Retrieval).

Cada término del catálogo (descripciones y sinónimos) se convierte en un vector.
Cada fragmento de la nota también. Los vectores cercanos (similitud coseno alta)
indican significado parecido, aunque las palabras no sean idénticas.

Dos métodos intercambiables (variable RECUPERADOR en .env):
    - "embeddings": modelo multilingüe de sentence-transformers (el método principal)
    - "tfidf":      n-gramas de letras con scikit-learn (línea base, no descarga nada)
"""

import os
import re

from preprocesamiento import cargar_catalogo, preparar_segmento, segmentar

# Si existe python-dotenv, carga las variables del archivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MODELO_POR_DEFECTO = "paraphrase-multilingual-MiniLM-L12-v2"

# Palabras y signos donde se parte un segmento en fragmentos más pequeños.
# Así "niega fiebre y tos" se convierte en "niega fiebre" + "tos".
_SEPARADORES = re.compile(r",|\b(?:y|e|ni|con|pero|aunque|por|tras)\b")


def fragmentar(texto):
    """Parte un segmento ya normalizado en fragmentos cortos (uno por posible hallazgo)."""
    fragmentos = [f.strip() for f in _SEPARADORES.split(texto)]
    return [f for f in fragmentos if len(f) >= 3]


class Recuperador:
    def __init__(self, catalogo=None, metodo=None):
        self.catalogo = catalogo if catalogo is not None else cargar_catalogo()
        self.metodo = (metodo or os.getenv("RECUPERADOR", "embeddings")).lower()

        # Una fila por cada término del catálogo: (término, código)
        self._terminos = [(t, cod) for cod, d in self.catalogo.items() for t in d["terminos"]]
        textos = [t for t, _ in self._terminos]

        if self.metodo == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._vectorizador = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
            self._matriz = self._vectorizador.fit_transform(textos)
        elif self.metodo == "embeddings":
            from sentence_transformers import SentenceTransformer
            self._modelo = SentenceTransformer(os.getenv("EMBEDDING_MODEL", MODELO_POR_DEFECTO))
            self._matriz = self._modelo.encode(textos, normalize_embeddings=True)
        else:
            raise ValueError(f"Método desconocido: {self.metodo!r} (usa 'tfidf' o 'embeddings')")

    def _similitudes(self, fragmentos):
        """Matriz [fragmento x término] con la similitud coseno de cada par."""
        if self.metodo == "tfidf":
            consulta = self._vectorizador.transform(fragmentos)
            return (consulta @ self._matriz.T).toarray()
        consulta = self._modelo.encode(fragmentos, normalize_embeddings=True)
        return consulta @ self._matriz.T

    def buscar(self, texto, k=None, umbral=0.0):
        """
        Devuelve los códigos candidatos de una nota, del más al menos parecido.
        k      = cuántos códigos se conservan POR FRAGMENTO (por defecto TOP_K_CANDIDATES)
        umbral = similitud mínima para aceptar un candidato
        """
        if k is None:
            k = int(os.getenv("TOP_K_CANDIDATES", "3"))

        mejores = {}  # código -> diccionario con su mejor coincidencia
        for seg in segmentar(texto):
            fragmentos = fragmentar(preparar_segmento(seg["texto"]))
            if not fragmentos:
                continue
            sims = self._similitudes(fragmentos)

            for i, fragmento in enumerate(fragmentos):
                # Para cada código nos quedamos con su término más parecido
                por_codigo = {}
                for j, (_, codigo) in enumerate(self._terminos):
                    por_codigo[codigo] = max(por_codigo.get(codigo, 0.0), float(sims[i][j]))

                top = sorted(por_codigo.items(), key=lambda par: par[1], reverse=True)[:k]
                for codigo, puntaje in top:
                    if puntaje <= umbral:
                        continue
                    if codigo not in mejores or puntaje > mejores[codigo]["puntaje"]:
                        mejores[codigo] = {
                            "codigo": codigo,
                            "descripcion": self.catalogo[codigo]["descripcion"],
                            "puntaje": round(puntaje, 4),
                            "fragmento": fragmento,
                            "evidencia": seg["texto"],
                        }
        return sorted(mejores.values(), key=lambda c: c["puntaje"], reverse=True)
