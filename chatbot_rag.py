# senacit_chatbot.py

import os
import time # Para añadir un pequeño delay si es necesario en el futuro
from dotenv import load_dotenv # Para manejar la API key de forma segura

# --- Cargadores de Documentos ---
from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader

# --- Divisor de Texto ---
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- Modelo de Embeddings ---
from langchain_community.embeddings import SentenceTransformerEmbeddings

# --- Almacén Vectorial ---
from langchain_community.vectorstores import Chroma

# --- LLM (Hugging Face) ---
from langchain_huggingface import HuggingFaceEndpoint

# --- Prompts y Cadenas ---
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Cargar variables de entorno desde un archivo .env si existe
load_dotenv()

# ---- CONFIGURACIÓN ----
# Ruta a la carpeta con tus documentos de las instituciones
DATA_PATH = "datos_instituciones"
# Ruta para guardar/cargar la base de datos vectorial persistente
DB_VECTOR_PATH = "db_vectorial_senacit" # Nombre específico para esta base de datos

# Nombre del modelo de embedding de Sentence Transformers (multilingüe bueno para español)
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2" # Modelo popular y eficiente
# O para mejor rendimiento en multilingüe/español: "paraphrase-multilingual-MiniLM-L12-v2"

# --- Configuración para Hugging Face API ---
# ¡¡¡IMPORTANTE!!! Reemplaza esto con tu API Key real de Hugging Face
# O mejor, configúrala como una variable de entorno HUGGINGFACEHUB_API_TOKEN
# y el script la leerá automáticamente si usas load_dotenv() y os.getenv()
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACEHUB_API_TOKEN", "TU_HUGGINGFACE_API_KEY_AQUI")

# Repositorio del modelo en Hugging Face Hub para usar con la Inference API
# HF_MODEL_REPO_ID = "mistralai/Mistral-7B-Instruct-v0.2"
HF_MODEL_REPO_ID = "google/gemma-2b-it" # Modelo más ligero para empezar

# ---- 1. CARGA Y PROCESAMIENTO DE DOCUMENTOS ----
def cargar_y_dividir_documentos(data_path):
    """Carga documentos PDF y TXT de la ruta especificada y los divide en chunks."""
    print(f"Buscando documentos en: {data_path}")
    
    # Configuración de DirectoryLoader para cargar múltiples tipos de archivos
    # Puedes añadir más loaders y globs si tienes otros formatos (ej. CSV, DOCX)
    # Para CSVs/DOCX, necesitarías instalar `pandas` y `python-docx` y usar `CSVLoader`, `UnstructuredWordDocumentLoader`
    
    loaders = [
        DirectoryLoader(
            data_path,
            glob="**/*.pdf", # Patrón para archivos PDF
            loader_cls=PyPDFLoader,
            show_progress=True,
            use_multithreading=True,
            recursive=True # Busca en subdirectorios
        ),
        DirectoryLoader(
            data_path,
            glob="**/*.txt", # Patrón para archivos TXT
            loader_cls=TextLoader,
            loader_kwargs={'encoding': 'utf-8'},
            show_progress=True,
            use_multithreading=True,
            recursive=True
        )
    ]

    documentos_cargados = []
    for loader in loaders:
        try:
            documentos_cargados.extend(loader.load())
        except Exception as e:
            print(f"Error cargando con {loader.glob}: {e}")

    if not documentos_cargados:
        print("¡Advertencia! No se cargaron documentos. Verifica la ruta y el contenido de la carpeta 'datos_instituciones'.")
        return []

    print(f"Cargados {len(documentos_cargados)} documentos en total.")

    # Dividir en chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,  # Tamaño del chunk en caracteres
        chunk_overlap=200, # Solapamiento entre chunks para mantener contexto
        length_function=len,
        add_start_index=True, # Útil para referenciar el origen del chunk
    )
    chunks = text_splitter.split_documents(documentos_cargados)
    print(f"Documentos divididos en {len(chunks)} chunks.")
    return chunks

# ---- 2. CREACIÓN DE EMBEDDINGS Y ALMACÉN VECTORIAL ----
def obtener_vectorstore(chunks, embedding_model_name, db_path):
    """Crea un nuevo vectorstore o carga uno existente si ya está persistido."""
    print(f"Inicializando modelo de embeddings: {embedding_model_name}")
    # Usar CPU explícitamente si no se tiene GPU o para asegurar consistencia
    embeddings_model = SentenceTransformerEmbeddings(
        model_name=embedding_model_name,
        model_kwargs={'device': 'cpu'} 
    )
    
    if os.path.exists(db_path) and os.listdir(db_path):
        print(f"Cargando VectorStore existente desde: {db_path}")
        vectorstore = Chroma(
            persist_directory=db_path,
            embedding_function=embeddings_model
        )
    else:
        if not chunks:
            print("No hay chunks para procesar. No se creará un nuevo VectorStore.")
            return None
        print(f"Creando nuevo VectorStore en: {db_path}")
        os.makedirs(db_path, exist_ok=True)
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings_model,
            persist_directory=db_path
        )
        # No es necesario llamar a vectorstore.persist() explícitamente con Chroma.from_documents
        # si persist_directory está configurado, pero no hace daño.
        print("Nuevo VectorStore creado y persistido.")
    print("VectorStore listo.")
    return vectorstore

# ---- 3. CONFIGURACIÓN DEL LLM (Usando Hugging Face API) ----
def inicializar_llm_huggingface(api_key, repo_id):
    """Inicializa el LLM usando la API de Hugging Face."""
    if not api_key or api_key == "TU_HUGGINGFACE_API_KEY_AQUI":
        print("Error: HUGGINGFACEHUB_API_TOKEN no configurado.")
        print("Por favor, consigue una API key de Hugging Face (huggingface.co/settings/tokens)")
        print("y configúrala en el script o como variable de entorno HUGGINGFACEHUB_API_TOKEN.")
        return None
    
    try:
        print(f"Inicializando LLM desde Hugging Face Hub: {repo_id}")
        llm = HuggingFaceEndpoint(
            repo_id=repo_id,
            huggingfacehub_api_token=api_key,
            temperature=0.2,       # Más bajo para respuestas más factuales y menos creativas
            max_new_tokens=1024,   # Máximo de tokens a generar en la respuesta
            # client= # puedes pasar un cliente HTTPX aquí si necesitas config avanzada
        )
        # Prueba rápida para ver si el endpoint responde (opcional, pero útil)
        try:
            llm.invoke("Hola, ¿cómo estás?") 
            print(f"LLM ({repo_id}) contactado exitosamente vía Hugging Face API.")
        except Exception as e_invoke:
            print(f"Error al probar invocación del LLM ({repo_id}): {e_invoke}")
            print("Verifica tu API key, el repo_id del modelo y tu conexión a internet.")
            print("Asegúrate que el modelo elegido es compatible con la Inference API gratuita.")
            return None
        return llm
    except Exception as e_init:
        print(f"Error al inicializar HuggingFaceEndpoint para {repo_id}: {e_init}")
        return None

# ---- 4. CREACIÓN DE LA CADENA RAG ----
def crear_cadena_rag(retriever, llm):
    """Crea la cadena RAG (Retrieval Augmented Generation)."""
    
    # Plantilla de prompt mejorada
    template = """Eres un asistente virtual especializado en la información de las siguientes instituciones hondureñas:
    Instituto Nacional de Estadística (INE), Secretaría de Finanzas (SEFIN) a través de su portal de Datos Abiertos de Honduras Inversiones, 
    Observatorio Nacional de la Violencia (IUDPAS - UNAH), Subsecretaría de Seguridad, y Honducompras (ONCAE).

    Tu tarea es responder preguntas ÚNICAMENTE basándote en el siguiente contexto extraído de documentos de estas instituciones.
    Analiza el contexto cuidadosamente antes de responder.
    Si la información para responder la pregunta no se encuentra explícitamente en el contexto proporcionado, 
    responde de manera clara: "Con base en la información que tengo disponible de las instituciones mencionadas, no puedo responder a esa pregunta."
    No intentes inventar respuestas ni utilices conocimiento externo a este contexto.
    Sé conciso, preciso y profesional en tus respuestas. Si el contexto es extenso, resume la información pertinente.
    Si la pregunta es un saludo o no requiere búsqueda de información, responde amablemente.

    Contexto Proporcionado:
    {context}

    Pregunta del Usuario:
    {question}

    Respuesta Detallada y Basada en el Contexto:"""
    
    prompt = ChatPromptTemplate.from_template(template)

    def format_docs_with_source(docs):
        # Incluye el nombre del archivo fuente si está disponible en los metadatos
        formatted_docs = []
        for i, doc in enumerate(docs):
            source_info = doc.metadata.get('source', 'Fuente desconocida')
            # Limpiar un poco el path de la fuente para mejor legibilidad
            source_info = os.path.basename(source_info) 
            formatted_docs.append(f"-- Inicio Contexto {i+1} (Fuente: {source_info}) --\n{doc.page_content}\n-- Fin Contexto {i+1} --")
        return "\n\n".join(formatted_docs) if formatted_docs else "No se encontró contexto relevante."

    rag_chain = (
        {"context": retriever | format_docs_with_source, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain

# ---- FUNCIÓN PRINCIPAL ----
def main():
    print("Iniciando Chatbot RAG para Instituciones de SENACIT...")

    # ---- PASO 1: Cargar y dividir documentos (solo si es necesario) ----
    # Se crean los chunks solo si la base de datos no existe.
    # Si quieres regenerar la base de datos (ej. si actualizas los documentos),
    # borra la carpeta DB_VECTOR_PATH antes de ejecutar.
    chunks_para_vectorstore = []
    if not os.path.exists(DB_VECTOR_PATH) or not os.listdir(DB_VECTOR_PATH):
        print("Base de datos vectorial no encontrada o vacía. Procesando documentos...")
        chunks_para_vectorstore = cargar_y_dividir_documentos(DATA_PATH)
        if not chunks_para_vectorstore:
            print("No se pudieron procesar documentos. El chatbot no podrá funcionar correctamente sin datos.")
            print(f"Asegúrate de tener archivos PDF o TXT en la carpeta: ./{DATA_PATH}/")
            # Podríamos decidir salir aquí si no hay datos para indexar la primera vez.
            # return
    else:
        print(f"Usando base de datos vectorial existente en ./{DB_VECTOR_PATH}/")


    # ---- PASO 2: Obtener VectorStore (crear o cargar) y Retriever ----
    vectorstore = obtener_vectorstore(chunks_para_vectorstore, EMBEDDING_MODEL_NAME, DB_VECTOR_PATH)
    
    if vectorstore is None:
        print("Error: No se pudo inicializar el VectorStore. El chatbot no puede continuar.")
        print(f"Si es la primera ejecución, asegúrate de tener documentos en ./{DATA_PATH}/")
        return

    # Configurar el retriever para buscar los 'k' chunks más relevantes
    retriever = vectorstore.as_retriever(
        search_type="similarity", # Otros tipos: "mmr" (Maximal Marginal Relevance)
        search_kwargs={"k": 3}     # Número de chunks a recuperar. Ajusta según necesidad.
    )
    print("Retriever configurado.")

    # ---- PASO 3: Inicializar el LLM ----
    llm = inicializar_llm_huggingface(HUGGINGFACE_API_KEY, HF_MODEL_REPO_ID)
    if llm is None:
        print("Error: No se pudo inicializar el LLM. El chatbot no puede continuar.")
        return
    print("LLM inicializado.")

    # ---- PASO 4: Crear la cadena RAG ----
    rag_chain = crear_cadena_rag(retriever, llm)
    print("Cadena RAG creada. Chatbot listo para recibir preguntas.")

    # ---- PASO 5: Ciclo de interacción con el usuario ----
    print("\n--- ChatSENACIT ---")
    print("Hola! Soy un asistente virtual con información sobre instituciones hondureñas.")
    print("Escribe tu pregunta o 'salir' para terminar la conversación.")
    
    while True:
        try:
            user_query = input("\nTú: ")
            if user_query.lower().strip() == 'salir':
                print("Asistente: Ha sido un placer ayudarte. ¡Hasta pronto!")
                break
            if not user_query.strip():
                continue
            
            print("Asistente (pensando...):")
            # Aquí podrías añadir un indicador de carga si la respuesta tarda mucho
            
            start_time = time.time()
            response = rag_chain.invoke(user_query)
            end_time = time.time()
            
            print(f"\nAsistente: {response}")
            print(f"(Respuesta generada en {end_time - start_time:.2f} segundos)")

        except KeyboardInterrupt:
            print("\nAsistente: Conversación interrumpida. ¡Adiós!")
            break
        except Exception as e:
            print(f"\nError inesperado durante la conversación: {e}")
            # Podrías añadir más manejo de errores específicos aquí
            # Por ejemplo, si la API de Hugging Face da un error de cuota.
            # Considera reintentar o informar al usuario.
            print("Intentaré continuar. Si el problema persiste, revisa la configuración o los logs.")

    print("--- Chatbot Finalizado ---")

if __name__ == "__main__":
    # Antes de correr main(), podrías crear las carpetas si no existen
    os.makedirs(DATA_PATH, exist_ok=True)
    # os.makedirs(DB_VECTOR_PATH, exist_ok=True) # `obtener_vectorstore` ya lo hace si es necesario

    # Coloca tus archivos PDF y TXT en la carpeta "datos_instituciones"
    # Crea un archivo ".env" en la misma carpeta que este script con tu API key:
    # HUGGINGFACEHUB_API_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    
    main()