"""
app.py — Interfaz de CodificaMed (requisito 6).
Ejecutar con:   streamlit run app.py
"""
import html
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from codificador import generador_reglas, sugerir_codigos  # noqa: E402
from llm import obtener_generador  # noqa: E402
from recuperacion import Recuperador  # noqa: E402

st.set_page_config(page_title="CodificaMed", page_icon="🩺", layout="wide")

OPCIONES = {
    "Local (Ollama)": "ollama",
    "API externa (Groq)": "groq",
    "Solo reglas (sin modelo de lenguaje)": "reglas",
}


@st.cache_resource(show_spinner="Cargando el recuperador de códigos...")
def cargar_recuperador(metodo):
    return Recuperador(metodo=metodo)


@st.cache_data
def cargar_casos():
    return json.loads((RAIZ / "data" / "casos_ficticios.json").read_text(encoding="utf-8"))


def resaltar(nota, sugerencias):
    """Devuelve la nota en HTML con la evidencia de cada código resaltada (verde = confirmado, rojo = negado)."""
    tramos = []
    for s in sugerencias:
        if s["evidencia_valida"]:
            m = re.search(re.escape(s["evidencia"]), nota, re.IGNORECASE)
            if m:
                tramos.append((m.start(), m.end(), s["estado"]))
    tramos.sort()
    partes, pos = [], 0
    for ini, fin, estado in tramos:
        if ini < pos:  # tramo que se solapa con otro ya resaltado
            continue
        color = "#bdf0c8" if estado == "confirmado" else "#f6c4c4"
        partes.append(html.escape(nota[pos:ini]))
        partes.append(f'<mark style="background:{color};color:#111;padding:0 3px;border-radius:3px">'
                      f"{html.escape(nota[ini:fin])}</mark>")
        pos = fin
    partes.append(html.escape(nota[pos:]))
    return "".join(partes).replace("\n", "<br>")


# ----------------------------- Barra lateral -----------------------------
with st.sidebar:
    st.header("Configuración")
    por_defecto = {"ollama": 0, "groq": 1}.get(os.getenv("LLM_PROVIDER", "ollama").lower(), 0)
    etiqueta = st.selectbox("Modelo de lenguaje", list(OPCIONES), index=por_defecto)
    proveedor = OPCIONES[etiqueta]

    if proveedor == "ollama":
        modelo = st.text_input("Modelo de Ollama", os.getenv("OLLAMA_MODEL", "mistral"))
        os.environ["OLLAMA_MODEL"] = modelo
    elif proveedor == "groq":
        modelo = st.text_input("Modelo de Groq", os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
        os.environ["GROQ_MODEL"] = modelo

    metodos = ["embeddings", "tfidf"]
    actual = os.getenv("RECUPERADOR", "embeddings").lower()
    metodo = st.selectbox("Recuperación de candidatos", metodos, index=metodos.index(actual) if actual in metodos else 0)
    k = st.slider("Candidatos por fragmento (K)", 1, 8, 3)
    st.caption("Las sugerencias son una ayuda: el codificador humano debe validarlas.")

# ----------------------------- Pantalla principal -----------------------------
st.title("🩺 CodificaMed")
st.write("Pega una nota clínica en español y el sistema sugiere los códigos CIE-10, con la frase que los justifica.")

casos = cargar_casos()


def cargar_ejemplo():
    elegido = st.session_state.ejemplo
    st.session_state.nota = next((c["texto"] for c in casos if c["id"] == elegido), "")


st.selectbox("Cargar un caso de ejemplo (todos ficticios)", ["— escribir mi propia nota —"] + [c["id"] for c in casos],
             key="ejemplo", on_change=cargar_ejemplo)
nota = st.text_area("Nota clínica", key="nota", height=170,
                    placeholder="Ej.: Paciente con HTA y DM2. Acude por cefalea. Niega dolor torácico.")

if st.button("Sugerir códigos CIE-10", type="primary", disabled=not nota.strip()):
    inicio = time.time()
    try:
        with st.spinner("Analizando la nota..."):
            recuperador = cargar_recuperador(metodo)
            generar = generador_reglas(nota) if proveedor == "reglas" else obtener_generador(proveedor)
            r = sugerir_codigos(nota, recuperador, generar, k=k)
    except Exception as e:
        st.error(f"No se pudo procesar la nota: {type(e).__name__}: {e}")
        st.stop()
    segundos = time.time() - inicio

    if not r["respuesta_valida"]:
        st.warning("El modelo no devolvió una respuesta en el formato esperado. Prueba de nuevo o cambia de modelo.")
    elif not r["sugerencias"]:
        st.info("No se encontraron códigos aplicables en esta nota.")

    if r["sugerencias"]:
        st.subheader("Nota con la evidencia resaltada")
        st.markdown(resaltar(nota, r["sugerencias"]), unsafe_allow_html=True)
        st.caption("Verde: diagnóstico confirmado · Rojo: negado o descartado")

        st.subheader("Códigos sugeridos")
        filas = [{
            "Código": s["codigo"],
            "Descripción": s["descripcion"],
            "Estado": "✅ Confirmado" if s["estado"] == "confirmado" else "🚫 Negado",
            "Evidencia": s["evidencia"],
            "Revisar": "⚠️ Sí" if s["revisar"] else "",
        } for s in r["sugerencias"]]
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")

        if any(s["revisar"] for s in r["sugerencias"]):
            st.warning("⚠️ Las filas marcadas para revisar tienen una evidencia que no aparece en la nota "
                       "o contradicen las reglas de negación. Compruébalas antes de aceptarlas.")

    if r["inventados"]:
        st.caption(f"Códigos propuestos por el modelo y descartados por no estar entre los candidatos: {r['inventados']}")

    st.caption(f"Tiempo: {segundos:.1f} s · Candidatos recuperados: {len(r['candidatos'])} · "
               f"Modelo: {etiqueta}")

    with st.expander("Ver candidatos recuperados del catálogo"):
        st.dataframe(pd.DataFrame([{"Código": c["codigo"], "Descripción": c["descripcion"],
                                    "Similitud": c["puntaje"], "Fragmento": c["fragmento"]}
                                   for c in r["candidatos"]]), hide_index=True, width="stretch")
    with st.expander("Ver respuesta cruda del modelo"):
        st.code(r["respuesta_cruda"] or "(sin respuesta)", language="json")
