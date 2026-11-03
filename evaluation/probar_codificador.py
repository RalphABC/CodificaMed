"""
Prueba el codificador SIN usar un modelo real: un "modelo falso" devuelve respuestas
preparadas para comprobar que las validaciones funcionan.
Uso:  python evaluation/probar_codificador.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from codificador import sugerir_codigos  # noqa: E402
from recuperacion import Recuperador  # noqa: E402

recuperador = Recuperador(metodo="tfidf")  # sin descargas, basta para probar la lógica
NOTA = "Paciente con fiebre y tos. Niega disnea. Se descarta tuberculosis."


def falso(respuesta):
    return lambda sistema, usuario: respuesta if isinstance(respuesta, str) else json.dumps(respuesta)


def verificar(nombre, condicion):
    print(("OK     " if condicion else "FALLA  ") + nombre)
    return condicion


ok = True

# 1) Respuesta correcta
r = sugerir_codigos(NOTA, recuperador, falso({"codigos": [
    {"codigo": "R50.9", "estado": "confirmado", "evidencia": "fiebre"},
    {"codigo": "R06.0", "estado": "negado", "evidencia": "Niega disnea"},
    {"codigo": "A15.0", "estado": "negado", "evidencia": "Se descarta tuberculosis"},
]}))
ok &= verificar("respuesta correcta: 3 sugerencias", len(r["sugerencias"]) == 3)
ok &= verificar("respuesta correcta: ninguna marcada para revisar", not any(s["revisar"] for s in r["sugerencias"]))

# 2) Código inventado (no existe entre los candidatos)
r = sugerir_codigos(NOTA, recuperador, falso({"codigos": [
    {"codigo": "Z99.9", "estado": "confirmado", "evidencia": "fiebre"},
    {"codigo": "R50.9", "estado": "confirmado", "evidencia": "fiebre"},
]}))
ok &= verificar("código inventado descartado", r["inventados"] == ["Z99.9"] and len(r["sugerencias"]) == 1)

# 3) Evidencia que no está en la nota
r = sugerir_codigos(NOTA, recuperador, falso({"codigos": [
    {"codigo": "R50.9", "estado": "confirmado", "evidencia": "temperatura de 39 grados"},
]}))
s = r["sugerencias"][0]
ok &= verificar("evidencia falsa -> evidencia_valida=False y revisar=True", (not s["evidencia_valida"]) and s["revisar"])

# 4) El modelo contradice las reglas de negación (dice confirmado algo que la nota niega)
r = sugerir_codigos(NOTA, recuperador, falso({"codigos": [
    {"codigo": "R06.0", "estado": "confirmado", "evidencia": "Niega disnea"},
]}))
ok &= verificar("discrepancia con reglas -> revisar=True", r["sugerencias"][0]["revisar"])

# 5) Respuesta que no es JSON
r = sugerir_codigos(NOTA, recuperador, falso("Lo siento, no puedo ayudar."))
ok &= verificar("respuesta sin JSON -> respuesta_valida=False", r["respuesta_valida"] is False)

# 6) JSON rodeado de texto
r = sugerir_codigos(NOTA, recuperador, falso('Aquí está: {"codigos": [{"codigo": "R05", "estado": "confirmado", "evidencia": "tos"}]} Listo.'))
ok &= verificar("JSON con texto alrededor se extrae", len(r["sugerencias"]) == 1)

print("\nTodo correcto." if ok else "\nHay pruebas que fallan.")
