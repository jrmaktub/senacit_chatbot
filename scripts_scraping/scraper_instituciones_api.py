# Ubicación: scripts_scraping/scraper_instituciones_api.py

import asyncio
import os
import re
from pathlib import Path # Usaremos Path para construir rutas absolutas más fácilmente
from urllib.parse import urlparse

# Importar clases necesarias de crawl4ai
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
# Si necesitaras filtros o scorers más avanzados, los importarías de:
# from crawl4ai.deep_crawling.filters import DomainFilter, FilterChain
# from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer

# --- Configuración General ---
TARGET_URL = "https://www.ine.gob.hn/"
# Para un rastreo más completo, podrías aumentar estos valores gradualmente:
MAX_PAGES_TO_CRAWL = 75  # Aumentado un poco para más cobertura
MAX_CRAWL_DEPTH = 4      # Un nivel más de profundidad
USER_AGENT = f"senacit_chatbot Scraper/1.0 (Proyecto Educativo; {os.getenv('USER_EMAIL', 'jhramirezrojas@gmail.com')})" # Usa tu email

# --- Configuración de Rutas de Salida ---
# El script está en 'scripts_scraping', así que subimos un nivel para 'crawl_output'
PROJECT_ROOT = Path(__file__).resolve().parent.parent # Raíz del proyecto 'senacit_chatbot'
OUTPUT_BASE_DIR = PROJECT_ROOT / "crawl_output" / "ine"
MARKDOWN_OUTPUT_DIR = OUTPUT_BASE_DIR / "markdown_content"
PDF_OUTPUT_DIR = OUTPUT_BASE_DIR / "downloaded_pdfs" # Carpeta destino para PDFs

# --- Crear directorios de salida ---
os.makedirs(MARKDOWN_OUTPUT_DIR, exist_ok=True)
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

# --- Función Auxiliar para Nombres de Archivo ---
def sanitize_filename(url_or_filename, is_url=True, target_extension=None):
    """Crea un nombre de archivo seguro y corto a partir de una URL o nombre de archivo."""
    original_filename_for_ext = url_or_filename if not is_url else urlparse(url_or_filename).path

    if is_url:
        parsed_url = urlparse(url_or_filename)
        # Incluir el host y el path para mayor unicidad, evitar que solo se use el nombre del archivo
        path_part = (parsed_url.netloc + parsed_url.path).strip('/')
        if not path_part: # Si el path está vacío (ej. solo el dominio)
            path_part = parsed_url.netloc
        sanitized = path_part.replace('/', '_').replace('\\', '_')
    else:
        sanitized = os.path.basename(url_or_filename)

    sanitized = re.sub(r'[\\/*?:"<>|]', '_', sanitized)
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Reemplaza múltiples puntos seguidos por uno solo, pero no los puntos de la extensión
    name_part, ext_part = os.path.splitext(sanitized)
    name_part = re.sub(r'\.+', '_', name_part)
    sanitized = name_part + ext_part

    # Forzar extensión si se proporciona y no coincide
    if target_extension:
        name_without_ext, current_ext = os.path.splitext(sanitized)
        if not current_ext.lower() == target_extension.lower():
            sanitized = name_without_ext + target_extension
    
    max_len = 150 # Longitud máxima permitida para nombres de archivo
    if len(sanitized) > max_len:
        name_part, ext_part = os.path.splitext(sanitized)
        if len(ext_part) < 10 and ext_part: # Extensión razonable
             sanitized = name_part[:max_len - len(ext_part)] + ext_part
        else: # Sin extensión o extensión muy larga
             sanitized = sanitized[:max_len]
             if target_extension and not sanitized.endswith(target_extension): # Re-asegurar extensión
                 sanitized = sanitized[:max_len - len(target_extension)] + target_extension


    return sanitized or "default_filename"


# --- Función Principal Asíncrona del Scraper ---
async def scrape_ine_website():
    print(f"--- Iniciando crawling del INE ({TARGET_URL}) ---")
    # Convertir Path objects a strings para pasarlos a crawl4ai, que espera strings para rutas
    markdown_save_path_str = str(MARKDOWN_OUTPUT_DIR)
    pdf_download_path_str = str(PDF_OUTPUT_DIR) # Esta es la ruta que queremos que use crawl4ai

    print(f"Guardando Markdown en: {markdown_save_path_str}")
    print(f"Configurando descargas de PDF para ir a: {pdf_download_path_str}")

    # 1. Configuración del Navegador/Crawler
    browser_config = BrowserConfig(
        user_agent=USER_AGENT,
        accept_downloads=True,          # ¡CLAVE! Habilita las descargas
        downloads_path=pdf_download_path_str # ¡CLAVE! Especifica dónde Playwright/navegador debe guardar
        # headless=True, # Puedes añadir True para correr sin ver el navegador, False para verlo (útil para debug)
    )

    # 2. Configuración de la Estrategia de Deep Crawl
    bfs_strategy = BFSDeepCrawlStrategy(
        max_depth=MAX_CRAWL_DEPTH,
        max_pages=MAX_PAGES_TO_CRAWL,
        include_external=False  # Para no salir de ine.gob.hn
    )
    
    # 3. Configuración de la Ejecución del Crawl
    run_config = CrawlerRunConfig(
        deep_crawl_strategy=bfs_strategy,
        # No necesitamos `download_media_types` aquí si `accept_downloads`
        # en BrowserConfig funciona para los enlaces directos a PDFs.
        # `crawl4ai` debería descargar archivos si `accept_downloads` es True
        # y el servidor envía la cabecera Content-Disposition o el tipo de contenido es application/pdf.
        # El parámetro `wait_for` podría ser útil si las descargas se inician con JS y tardan:
        # wait_for=5 # (en segundos) Esperar a que las acciones JS inicien descargas (no lo usamos ahora)
    )

    # Imprimir configuración para verificación
    print("\n--- Configuración Aplicada ---")
    print(f"BrowserConfig:")
    print(f"  - User Agent: {browser_config.user_agent}")
    print(f"  - Accept Downloads: {browser_config.accept_downloads}")
    print(f"  - Downloads Path (Destino de Playwright): {browser_config.downloads_path}")
    print(f"BFSDeepCrawlStrategy:")
    print(f"  - Max Depth: {bfs_strategy.max_depth}")
    print(f"  - Max Pages: {bfs_strategy.max_pages}")
    print(f"  - Include External: {bfs_strategy.include_external}")
    print(f"CrawlerRunConfig:")
    print(f"  - Target URL (en arun): {TARGET_URL}")

    # 4. Inicializar y Ejecutar el Crawler
    crawler = AsyncWebCrawler(config=browser_config) # Se pasa la config del navegador aquí
    results = []
    try:
        print("\nIniciando crawler.arun()... (Esto puede tomar varios minutos)")
        # Pasar TARGET_URL como primer argumento y run_config para esta ejecución específica
        results = await crawler.arun(TARGET_URL, config=run_config)
    except Exception as e:
        print(f"Error crítico durante el crawling: {e}")

    # 5. Procesar y Guardar Resultados
    print(f"\n--- Crawling finalizado. Procesando {len(results)} resultados ---")
    saved_md_count = 0
    confirmed_pdf_count = 0

    if not results:
        print("ADVERTENCIA: La lista de resultados está vacía. No se procesaron páginas.")

    for i, result in enumerate(results):
        if not result or not hasattr(result, 'success') or not hasattr(result, 'url'):
            print(f"Resultado {i+1} inválido o incompleto, saltando.")
            continue

        if result.success:
            print(f"[{i+1}/{len(results)}] Procesando URL OK: {result.url}")
            
            # Guardar Markdown si existe
            if hasattr(result, 'markdown') and result.markdown:
                # Usar la URL original para el nombre del archivo Markdown
                md_filename = sanitize_filename(result.url, is_url=True, target_extension=".md")
                filepath_md = os.path.join(MARKDOWN_OUTPUT_DIR, md_filename)
                try:
                    with open(filepath_md, "w", encoding="utf-8") as f:
                        f.write(result.markdown)
                    saved_md_count += 1
                except Exception as e:
                    print(f"  * Error guardando markdown para {result.url}: {e}")

            # Revisar result.downloaded_files que contiene las RUTAS donde el navegador guardó los archivos
            if hasattr(result, 'downloaded_files') and result.downloaded_files:
                print(f"  -> Archivos reportados en result.downloaded_files para {result.url}:")
                for downloaded_file_path_str in result.downloaded_files:
                    downloaded_file_path = Path(downloaded_file_path_str) # Convertir a objeto Path
                    print(f"     - Ruta reportada: '{downloaded_file_path_str}'")
                    
                    # Verificar si es un PDF y si el archivo realmente existe en esa ruta
                    if downloaded_file_path.suffix.lower() == '.pdf':
                        if downloaded_file_path.exists():
                            # Como configuramos downloads_path a nuestro PDF_OUTPUT_DIR,
                            # el archivo ya debería estar en el lugar correcto.
                            print(f"       -> PDF Confirmado en (debería ser la carpeta destino): {downloaded_file_path}")
                            confirmed_pdf_count += 1
                        else:
                            print(f"       -> ADVERTENCIA: PDF reportado en '{downloaded_file_path_str}' pero NO ENCONTRADO en disco.")
                    else:
                        print(f"       -> Archivo descargado (no PDF): {downloaded_file_path_str}")
            # Considerar si una URL que es un PDF directo (ej. result.url.endswith('.pdf'))
            # pero no aparece en result.downloaded_files debe ser manejada de otra forma.
            # Por ahora, confiamos en que `accept_downloads=True` y la navegación directa a una URL PDF
            # hará que aparezca en `result.downloaded_files`.
            elif result.url.lower().endswith(".pdf"):
                 print(f"  -> URL es un PDF directo: {result.url}, pero no se reportó en result.downloaded_files.")


        else:
            error_msg = getattr(result, 'error_message', 'Error desconocido')
            print(f"[{i+1}/{len(results)}] Procesando URL ERROR: {result.url} - {error_msg}")

    print(f"\n--- Proceso Completo ---")
    print(f"Archivos Markdown guardados: {saved_md_count} en {str(MARKDOWN_OUTPUT_DIR)}")
    print(f"Archivos PDF confirmados en la carpeta de destino: {confirmed_pdf_count} en {str(PDF_OUTPUT_DIR)}")

# --- Punto de Entrada para Ejecutar el Script ---
if __name__ == "__main__":
    # Intenta obtener el email de una variable de entorno o usa el default
    user_email_for_agent = os.getenv('USER_EMAIL', 'jhramirezrojas@gmail.com')
    USER_AGENT = f"senacit_chatbot Scraper/1.0 (Proyecto Educativo; {user_email_for_agent})"
    print(f"Usando User-Agent: {USER_AGENT}")
    
    asyncio.run(scrape_ine_website())