# Ubicación: scripts_scraping/scraper_instituciones_api.py

import asyncio
import os
import re
from urllib.parse import urlparse

# --- Importaciones Corregidas ---
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

# --- Configuración General ---
TARGET_URL = "https://www.ine.gob.hn/"
MAX_PAGES_TO_CRAWL = 50
MAX_CRAWL_DEPTH = 3
DOWNLOAD_EXTENSIONS = ['.pdf'] # Usado para verificar en los resultados, no para configurar crawl4ai
USER_AGENT = f"senacit_chatbot Scraper/1.0 (Proyecto Educativo; jhramirezrojas@gmail.com)"

# --- Configuración de Rutas de Salida ---
OUTPUT_BASE_DIR = "../crawl_output/ine"
MARKDOWN_OUTPUT_DIR = os.path.join(OUTPUT_BASE_DIR, "markdown_content")
PDF_OUTPUT_DIR = os.path.join(OUTPUT_BASE_DIR, "downloaded_pdfs") # Carpeta destino para PDFs

# --- Crear directorios de salida ---
os.makedirs(MARKDOWN_OUTPUT_DIR, exist_ok=True)
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True) # Asegurarse que existe la carpeta destino de PDFs

# --- Función Auxiliar para Nombres de Archivo ---
def sanitize_filename(url_or_filename):
    """Crea un nombre de archivo seguro y corto a partir de una URL o nombre de archivo."""
    if '://' in url_or_filename:
        parsed_url = urlparse(url_or_filename)
        path_part = (parsed_url.netloc + parsed_url.path).strip('/') or parsed_url.netloc
        sanitized = path_part.replace('/', '_').replace('\\', '_')
    else:
        sanitized = os.path.basename(url_or_filename)

    sanitized = re.sub(r'[\\/*?:"<>|]', '_', sanitized)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = re.sub(r'\.+', '_', sanitized)
    max_len = 150
    if len(sanitized) > max_len:
        name, ext = os.path.splitext(sanitized)
        if len(ext) < 10:
             sanitized = name[:max_len - len(ext)] + ext
        else:
             sanitized = sanitized[:max_len]
    return sanitized or "default_filename"

# --- Función Principal Asíncrona del Scraper ---
async def scrape_ine_website():
    print(f"--- Iniciando crawling del INE ({TARGET_URL}) ---")
    # Usar path absoluto para asegurar que downloads_path sea correcto
    pdf_download_path = os.path.abspath(PDF_OUTPUT_DIR)
    print(f"Guardando resultados en: {os.path.abspath(OUTPUT_BASE_DIR)}")
    print(f"Descargas configuradas para ir a: {pdf_download_path}")


    # 1. Configuración del Crawler (Ajustes globales - usando BrowserConfig)
    #    Añadimos accept_downloads y downloads_path según la documentación
    browser_config = BrowserConfig(
        user_agent=USER_AGENT,
        accept_downloads=True,       # <-- Habilitar descargas
        downloads_path=pdf_download_path # <-- Especificar carpeta destino
        # request_delay eliminado, confiamos en default
    )

    # 2. Configuración de la Estrategia de Deep Crawl
    bfs_strategy = BFSDeepCrawlStrategy(
        max_depth=MAX_CRAWL_DEPTH,
        max_pages=MAX_PAGES_TO_CRAWL,
        include_external=False
    )
    print("Configuración de BFSDeepCrawlStrategy:")
    print(f" - max_depth: {bfs_strategy.max_depth}")
    print(f" - max_pages: {bfs_strategy.max_pages}")
    print(f" - include_external: {bfs_strategy.include_external}")

    # 3. Configuración de la Ejecución del Crawl (Pasando la estrategia)
    #    Ya no necesita parámetros de descarga aquí
    run_config = CrawlerRunConfig(
        deep_crawl_strategy=bfs_strategy
        # url se pasa a arun()
        # request_delay eliminado
        # download_media_types eliminado
    )

    # Imprimir configuración para verificación
    print("Configuración de BrowserConfig:")
    print(f" - User Agent: {browser_config.user_agent}")
    print(f" - Accept Downloads: {browser_config.accept_downloads}")
    print(f" - Downloads Path: {browser_config.downloads_path}")
    print("Configuración de CrawlerRunConfig:")
    print(f" - Deep Crawl Strategy Configurado: True (BFS)") # Simplificado


    # 4. Inicializar y Ejecutar el Crawler (Pasando BrowserConfig)
    crawler = AsyncWebCrawler(config=browser_config)
    results = []
    try:
        print("\nIniciando crawler.arun()...")
        # Pasar TARGET_URL como primer argumento y run_config
        results = await crawler.arun(TARGET_URL, config=run_config)
    except Exception as e:
        print(f"Error crítico durante el crawling: {e}")


    # 5. Procesar y Guardar Resultados
    print(f"\n--- Crawling finalizado. Procesando {len(results)} resultados ---")
    saved_md_count = 0
    saved_pdf_count = 0

    if not results:
        print("ADVERTENCIA: La lista de resultados está vacía. No se procesaron páginas.")

    for i, result in enumerate(results):
        if not result or not hasattr(result, 'success') or not hasattr(result, 'url'):
            print(f"Resultado {i+1} inválido o incompleto, saltando.")
            continue

        if result.success:
            print(f"[{i+1}/{len(results)}] Procesando URL OK: {result.url}")
            base_filename = sanitize_filename(result.url)

            # Guardar Markdown si existe
            if hasattr(result, 'markdown') and result.markdown:
                filepath_md = os.path.join(MARKDOWN_OUTPUT_DIR, base_filename + ".md")
                try:
                    with open(filepath_md, "w", encoding="utf-8") as f:
                        f.write(result.markdown)
                    saved_md_count += 1
                except Exception as e:
                    print(f"  * Error guardando markdown para {result.url}: {e}")

            # --- Lógica de PDFs Actualizada ---
            # Revisar result.downloaded_files que contiene las rutas donde YA se guardaron
            if hasattr(result, 'downloaded_files') and result.downloaded_files:
                print(f"  -> Archivos descargados detectados para {result.url}:")
                for file_path in result.downloaded_files:
                    # Verificar si es PDF y si la ruta es válida
                    if file_path and isinstance(file_path, str) and file_path.lower().endswith('.pdf'):
                         # El archivo ya debería estar en PDF_OUTPUT_DIR
                         
                         print(f"     - Verificando existencia de: '{file_path}'")
                         
                         # Solo necesitamos contarlo y confirmar
                         if os.path.exists(file_path):
                              print(f"     - PDF Confirmado en: {file_path}")
                              saved_pdf_count += 1
                         else:
                              print(f"     - ADVERTENCIA: Archivo PDF reportado pero no encontrado en: {file_path}")
                    # else: # Podrías añadir lógica para otros tipos de archivo si los esperas
                    #    print(f"     - Otro archivo descargado: {file_path}")

        else:
            error_msg = getattr(result, 'error_message', 'Error desconocido')
            print(f"[{i+1}/{len(results)}] Procesando URL ERROR: {result.url} - {error_msg}")

    print(f"\n--- Proceso Completo ---")
    print(f"Archivos Markdown guardados: {saved_md_count} en {os.path.abspath(MARKDOWN_OUTPUT_DIR)}")
    # Cambiar el mensaje final de PDFs para reflejar que contamos los archivos detectados en la carpeta destino
    print(f"Archivos PDF detectados/contados: {saved_pdf_count} en {os.path.abspath(PDF_OUTPUT_DIR)}")

# --- Punto de Entrada para Ejecutar el Script ---
if __name__ == "__main__":
    asyncio.run(scrape_ine_website())