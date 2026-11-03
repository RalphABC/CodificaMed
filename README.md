# CodificaMed

Prototipo que recibe una **nota clínica en texto libre (español)** y sugiere los **códigos CIE-10** correspondientes, mostrando **qué frase de la nota justifica cada código**. Distingue un diagnóstico **confirmado** de uno **negado o descartado** ("niega fiebre", "se descarta neumonía").

Proyecto de la materia *Base de Conocimiento* (ESPOCH - FIE - EIS), unidad de Procesamiento de Lenguaje Natural. Desarrollado siguiendo las 6 fases de CRISP-ML(Q).

> **Aviso:** es un prototipo académico. Todos los casos de prueba son **ficticios**; no se usó ninguna historia clínica real. Las sugerencias deben ser validadas por un codificador humano.

## Cómo funciona

```
Nota clínica → Preprocesamiento → Recuperación (embeddings) → Modelo de lenguaje → Validación → Códigos + evidencia
                (siglas, negación)   (candidatos del CIE-10)    (Ollama o Groq)     (anti-invención)
```

1. **Preprocesamiento** (`src/preprocesamiento.py`): normaliza el texto, expande abreviaturas (HTA, DM2, ITU…), segmenta y detecta negación con reglas tipo NegEx.
2. **Recuperación** (`src/recuperacion.py`): compara cada fragmento de la nota con el catálogo CIE-10 usando embeddings multilingües (RAG). Incluye TF-IDF como línea base.
3. **Modelo de lenguaje** (`src/llm.py`): elige entre los candidatos y clasifica cada uno como confirmado o negado. Es **intercambiable por configuración**: modelo local (Ollama) o API externa (Groq).
4. **Validación** (`src/codificador.py`): descarta códigos inventados, comprueba que la evidencia exista en la nota y compara con las reglas de negación; si algo no cuadra, marca la sugerencia como **"revisar"**.

## Requisitos

- Python 3.10 o superior (probado con 3.12).
- [Ollama](https://ollama.com/download) para el modelo local, con un modelo descargado (probado con `mistral`).
- Una clave gratuita de [Groq](https://console.groq.com) para la API externa (opcional si solo usas el modelo local).
- Conexión a internet la primera vez: se descarga el modelo de embeddings (unos 450 MB).

## Instalación

```powershell
git clone https://github.com/RalphABC/CodificaMed.git
cd CodificaMed
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

En Linux o macOS, activa el entorno con `source .venv/bin/activate`.

## Configuración

1. Copia la plantilla de configuración:

   ```powershell
   copy .env.example .env
   ```

2. Edita `.env`. Lo importante:

   | Variable | Para qué sirve |
   | --- | --- |
   | `LLM_PROVIDER` | `ollama` (local) o `groq` (API externa) |
   | `OLLAMA_MODEL` | Modelo local, por ejemplo `mistral` |
   | `GROQ_API_KEY` | Tu clave de Groq (**solo en `.env`, nunca en el repositorio**) |
   | `GROQ_MODEL` | Modelo de Groq, por ejemplo `openai/gpt-oss-120b` |
   | `RECUPERADOR` | `embeddings` (principal) o `tfidf` (línea base, sin descargas) |
   | `TOP_K_CANDIDATES` | Candidatos por fragmento (por defecto 3) |

3. Para el modelo local, descarga el modelo y deja Ollama en ejecución:

   ```powershell
   ollama pull mistral
   ```

El archivo `.env` está en `.gitignore`; solo se sube `.env.example`, sin claves reales.

## Uso

### Interfaz web

```powershell
streamlit run app.py
```

Se abre en el navegador. Pega una nota (o elige uno de los 30 casos de ejemplo), selecciona el modelo en el panel lateral y pulsa **Sugerir códigos CIE-10**. Verás la nota con la evidencia resaltada (verde = confirmado, rojo = negado), la tabla de códigos y, si corresponde, la marca **⚠️ revisar**.

### Línea de comandos

```powershell
python src/codificador.py "Paciente con fiebre y tos. Niega disnea."
```

## Evaluación

Todos los comandos se ejecutan desde la carpeta raíz del proyecto.

```powershell
# Línea base sin modelo de lenguaje (solo reglas)
python evaluation/evaluar_sistema.py --proveedor reglas

# Modelo local
python evaluation/evaluar_sistema.py --proveedor ollama --modelo mistral

# API externa
python evaluation/evaluar_sistema.py --proveedor groq

# Tabla comparativa de todos los resultados guardados
python evaluation/comparar_resultados.py
```

Cada ejecución guarda su resultado en `evaluation/resultados/`. Con `--limite 3` se hace una prueba rápida que no guarda nada.

Otras comprobaciones:

| Comando | Qué hace |
| --- | --- |
| `python evaluation/validar_datos.py` | Verifica que todos los códigos de los casos existan en el catálogo |
| `python evaluation/probar_preprocesamiento.py` | Pruebas de negación (12 oraciones cortas y los 30 casos) |
| `python evaluation/probar_codificador.py` | Pruebas de las validaciones con un modelo simulado |
| `python evaluation/evaluar_recuperacion.py` | Recall@K de TF-IDF y embeddings |
| `python evaluation/verificar_catalogo.py` | Compara el catálogo con la lista oficial de la OMS (requiere `pip install simple-icd-10`) |

## Resultados

Sobre los 30 casos ficticios (58 códigos confirmados y 15 negados), con recuperación por embeddings y K = 3:

| Configuración | Precisión | Recall | F1 | Negaciones detectadas | s/nota |
| --- | --- | --- | --- | --- | --- |
| Solo reglas | 0.903 | 0.966 | 0.933 | 12/15 | 0.06 |
| Local: Mistral 7B (Ollama) | 0.831 | 0.845 | 0.838 | 2/15 | 16.2 |
| API: gpt-oss-120b (Groq) | 0.934 | 0.983 | 0.958 | 10/15 | 5.83 |

La API supera al modelo local con claridad, pero solo por muy poco a las reglas; con 30 casos esa diferencia no es concluyente. El análisis completo está en el informe ejecutivo (carpeta `report/`).

## Estructura del proyecto

```
CodificaMed/
├── app.py                      Interfaz (Streamlit)
├── requirements.txt
├── .env.example                Plantilla de configuración (sin claves)
├── data/
│   ├── cie10_catalogo.csv      Catálogo CIE-10 (78 códigos, con sinónimos y siglas)
│   └── casos_ficticios.json    30 notas clínicas ficticias con códigos esperados
├── src/
│   ├── preprocesamiento.py     Normalización, siglas, segmentación, negación
│   ├── recuperacion.py         Embeddings y TF-IDF sobre el catálogo
│   ├── llm.py                  Proveedores intercambiables (Ollama, Groq)
│   └── codificador.py          Pipeline completo y validaciones
├── evaluation/                 Scripts de evaluación y pruebas
│   └── resultados/             Resultados guardados de cada modelo
└── report/                     Informe ejecutivo
```

## Datos

- `data/casos_ficticios.json`: 30 notas inventadas, con abreviaturas, errores de tipeo, negaciones y diagnósticos descartados. Cada nota trae sus códigos confirmados y negados.
- `data/cie10_catalogo.csv`: subconjunto de 78 códigos frecuentes. Se contrastó con la lista de la OMS (CIE-10, edición 2019): 76 coinciden exactamente. **A90 y A91 (dengue)** siguen la CIE-10 de EE. UU. y España (base de CodiEsp); la OMS los reemplazó por A97.x.
- **Etiquetado:** un síntoma se codifica si la nota lo menciona explícitamente. Las etiquetas no se modificaron después de ver los resultados de los modelos.

## Limitaciones

- Catálogo reducido (78 de más de 14 000 códigos) y solo 30 casos ficticios, escritos con el vocabulario del catálogo: las métricas son optimistas y no se pueden extrapolar a notas reales.
- Las reglas no detectan negaciones implícitas ("función renal normal") ni términos ausentes del catálogo.
- La comparación local frente a API mezcla el tamaño del modelo con el tipo de despliegue (120 000 millones de parámetros frente a 7 000 millones).
- No se evaluó con el corpus público CodiEsp.
- Con una API externa, el texto de la nota sale del equipo; un uso real con datos de pacientes exigiría el modelo local o un acuerdo de tratamiento de datos.

## Metodología

Se siguieron las 6 fases de CRISP-ML(Q): comprensión del negocio y de los datos, ingeniería de datos, ingeniería del modelo, evaluación, despliegue, y monitoreo y mantenimiento. El detalle de cada fase está en el informe ejecutivo.
