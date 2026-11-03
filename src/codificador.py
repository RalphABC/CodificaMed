"""
codificador.py
--------------
Paso 5 de CodificaMed: une todo el pipeline.

    nota -> candidatos (embeddings) -> LLM elige y clasifica -> validación -> sugerencias

El LLM solo puede elegir entre los candidatos recuperados del catálogo, y cada
respuesta se valida: no se aceptan códigos inventados ni evidencias que no estén
en la nota. Además se compara con las reglas de negación del Paso 3; si
discrepan, la sugerencia se marca para que el codificador humano la revise.
"""

import json
import re
import sys

from llm import obtener_generador, modelo_actual, proveedor_actual
from preprocesamiento import detectar_menciones, normalizar, quitar_acentos
from recuperacion import Recuperador

PROMPT_SISTEMA = """Eres un codificador clínico experto en CIE-10. Recibes una nota clínica en español
y una lista de CÓDIGOS CANDIDATOS. Debes decidir cuáles aplican a la nota.

Reglas:
1. Usa SOLO códigos de la lista de candidatos. Nunca inventes códigos.
2. Incluye un código solo si la nota menciona explícitamente esa condición o síntoma.
3. Estado "confirmado": la condición está presente o fue diagnosticada.
4. Estado "negado": la nota la niega o la descarta ("niega", "sin", "no refiere", "afebril", "se descarta").
5. En "evidencia" copia, tal cual aparece en la nota, la frase corta que justifica el código.
6. Si ningún candidato aplica, devuelve una lista vacía.

Responde ÚNICAMENTE con JSON en este formato:
{"codigos": [{"codigo": "J18.9", "estado": "confirmado", "evidencia": "frase de la nota"}]}

Ejemplo:
Nota: "Paciente con tos y fiebre. Niega disnea. Se descarta tuberculosis."
Respuesta: {"codigos": [{"codigo": "R05", "estado": "confirmado", "evidencia": "tos"},
{"codigo": "R50.9", "estado": "confirmado", "evidencia": "fiebre"},
{"codigo": "R06.0", "estado": "negado", "evidencia": "Niega disnea"},
{"codigo": "A15.0", "estado": "negado", "evidencia": "Se descarta tuberculosis"}]}"""


def _armar_prompt_usuario(nota, candidatos):
    lineas = [f"- {c['codigo']}: {c['descripcion']}" for c in candidatos]
    return "CÓDIGOS CANDIDATOS:\n" + "\n".join(lineas) + f'\n\nNOTA CLÍNICA:\n"""{nota}"""'


def _extraer_json(texto):
    """Convierte la respuesta del modelo en un diccionario, aunque venga con texto alrededor."""
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        coincidencia = re.search(r"\{.*\}", texto, re.DOTALL)
        if coincidencia:
            try:
                return json.loads(coincidencia.group())
            except json.JSONDecodeError:
                pass
    return None


def _limpiar(texto):
    return quitar_acentos(normalizar(texto))


def generador_reglas(nota):
    """
    Línea base SIN modelo de lenguaje: responde usando únicamente las reglas del Paso 3.
    Tiene la misma forma que un LLM (recibe prompts y devuelve JSON), así se puede
    usar en su lugar en sugerir_codigos().
    """
    codigos = [{"codigo": m["codigo"], "estado": m["estado"], "evidencia": m["evidencia"]}
               for m in detectar_menciones(nota)]
    return lambda sistema, usuario: json.dumps({"codigos": codigos})


def sugerir_codigos(nota, recuperador, generar=None, k=3):
    """
    Devuelve un diccionario con:
      sugerencias : lista de {codigo, descripcion, estado, evidencia, evidencia_valida, revisar}
      inventados  : códigos que el modelo propuso y NO estaban entre los candidatos (descartados)
      respuesta_valida : False si el modelo no devolvió un JSON utilizable
      respuesta_cruda  : el texto original del modelo (útil para depurar)
      candidatos  : los códigos que se recuperaron del catálogo y se le ofrecieron al modelo
    """
    generar = generar or obtener_generador()
    candidatos = recuperador.buscar(nota, k=k)
    permitidos = {c["codigo"]: c for c in candidatos}

    cruda = generar(PROMPT_SISTEMA, _armar_prompt_usuario(nota, candidatos))
    datos = _extraer_json(cruda)
    if not isinstance(datos, dict) or not isinstance(datos.get("codigos"), list):
        return {"sugerencias": [], "inventados": [], "respuesta_valida": False,
                "respuesta_cruda": cruda, "candidatos": candidatos}

    reglas = {m["codigo"]: m["estado"] for m in detectar_menciones(nota, recuperador.catalogo)}
    nota_limpia = _limpiar(nota)

    sugerencias, inventados, vistos = [], [], set()
    for item in datos["codigos"]:
        if not isinstance(item, dict):
            continue
        codigo = str(item.get("codigo", "")).strip()
        estado = str(item.get("estado", "")).strip().lower()
        evidencia = str(item.get("evidencia", "")).strip()

        if codigo not in permitidos:
            inventados.append(codigo)
            continue
        if estado not in ("confirmado", "negado") or codigo in vistos:
            continue
        vistos.add(codigo)

        evidencia_valida = bool(evidencia) and _limpiar(evidencia) in nota_limpia
        discrepa_reglas = codigo in reglas and reglas[codigo] != estado
        sugerencias.append({
            "codigo": codigo,
            "descripcion": permitidos[codigo]["descripcion"],
            "estado": estado,
            "evidencia": evidencia,
            "evidencia_valida": evidencia_valida,
            "revisar": (not evidencia_valida) or discrepa_reglas,
        })

    return {"sugerencias": sugerencias, "inventados": inventados,
            "respuesta_valida": True, "respuesta_cruda": cruda, "candidatos": candidatos}


if __name__ == "__main__":
    # Uso rápido:  python src/codificador.py "Paciente con fiebre y tos. Niega disnea."
    nota = " ".join(sys.argv[1:]) or "Paciente de 62 años con HTA y DM2. Acude por cefalea. Niega dolor torácico."
    print(f"Proveedor: {proveedor_actual()} | Modelo: {modelo_actual()}\n")
    resultado = sugerir_codigos(nota, Recuperador())
    if not resultado["respuesta_valida"]:
        print("El modelo no devolvió JSON válido:\n", resultado["respuesta_cruda"])
    for s in resultado["sugerencias"]:
        marca = "  (REVISAR)" if s["revisar"] else ""
        print(f"{s['codigo']:7} {s['estado']:11} {s['descripcion']}\n        evidencia: {s['evidencia']}{marca}")
    if resultado["inventados"]:
        print("\nCódigos inventados descartados:", resultado["inventados"])
