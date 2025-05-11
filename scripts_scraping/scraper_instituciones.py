import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from urllib.parse import urljoin, urlparse

# Carpeta base donde se guardarán los datos scrapeados para el chatbot
BASE_OUTPUT_FOLDER = "../datos_instituciones" # Sube un nivel y entra a datos_instituciones
HEADERS = {
    'User-Agent': 'SENACITChatbotScraper/1.0 (Proyecto Educativo; tu_email@example.com)'
}

def ensure_dir_and_get_path(institution_name, filename):
    """Asegura que el directorio de la institución exista y devuelve la ruta completa del archivo."""
    institution_folder = os.path.join(BASE_OUTPUT_FOLDER, institution_name.lower().replace(" ", "_"))
    os.makedirs(institution_folder, exist_ok=True)
    # Limpiar nombre de archivo
    clean_filename = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in filename)
    # Evitar nombres de archivo excesivamente largos
    if len(clean_filename) > 100:
        name, ext = os.path.splitext(clean_filename)
        clean_filename = name[:95-len(ext)] + ext

    return os.path.join(institution_folder, clean_filename)

def download_file(url, institution_name, filename_override=None):
    """Descarga un archivo (PDF, CSV, etc.) de una URL."""
    try:
        # Si la URL no tiene esquema (http/https), intentar añadirlo
        if not urlparse(url).scheme:
            print(f"URL sin esquema detectada: {url}. Intentando con https://")
            url = "https://" + url.lstrip('/') # Asegurar que no haya doble // al inicio si ya tenía uno

        response = requests.get(url, headers=HEADERS, stream=True, timeout=30)
        response.raise_for_status() # Lanza error para códigos 4xx/5xx

        if filename_override:
            output_filepath = ensure_dir_and_get_path(institution_name, filename_override)
        else:
            # Intentar obtener nombre del Content-Disposition header
            content_disposition = response.headers.get('content-disposition')
            filename_from_header = None
            if content_disposition:
                filenames = requests.utils.parse_header_links(f'filename="{content_disposition}"')
                if filenames and 'filename*' in filenames[0]: # Prioridad a filename* si tiene codificación
                     filename_from_header = filenames[0]['filename*']
                elif filenames and 'filename' in filenames[0]:
                     filename_from_header = filenames[0]['filename']

            if filename_from_header:
                 output_filepath = ensure_dir_and_get_path(institution_name, filename_from_header)
            else: # Si no, usar la última parte de la URL
                 output_filepath = ensure_dir_and_get_path(institution_name, url.split('/')[-1].split('?')[0] or "descarga.dat")


        with open(output_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Descargado: {output_filepath}")
        time.sleep(1) # Pausa
        return output_filepath
    except requests.exceptions.MissingSchema:
        print(f"Error de URL inválida (MissingSchema): {url}. Asegúrate que la URL es completa (ej. http:// o https://).")
    except requests.exceptions.RequestException as e:
        print(f"Error descargando {url}: {e}")
    return None

def extract_text_from_page(url, institution_name, filename_prefix="pagina_"):
    """Extrae texto de una página HTML y lo guarda en un archivo TXT."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # --- LÓGICA DE EXTRACCIÓN DE TEXTO (MUY ESPECÍFICA DEL SITIO) ---
        # Intenta encontrar etiquetas comunes de contenido principal.
        # ¡DEBERÁS AJUSTAR ESTO PARA CADA SITIO!
        main_content_selectors = ['article', 'main', '.main-content', '#content', '.entry-content', '.post-content', '.articulo-contenido']
        content_element = None
        for selector in main_content_selectors:
            if selector.startswith('.'): # clase CSS
                content_element = soup.find(class_=selector[1:])
            elif selector.startswith('#'): # id CSS
                content_element = soup.find(id=selector[1:])
            else: # etiqueta HTML
                content_element = soup.find(selector)

            if content_element:
                break

        if not content_element: # Si no se encuentra, tomar todo el body (puede ser ruidoso)
            content_element = soup.body

        if content_element:
            text = content_element.get_text(separator='\n', strip=True)
            # Generar nombre de archivo basado en la URL
            parsed_url = urlparse(url)
            filename_base = os.path.basename(parsed_url.path) or parsed_url.netloc
            output_filepath = ensure_dir_and_get_path(institution_name, f"{filename_prefix}{filename_base}.txt")

            with open(output_filepath, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"Texto extraído de {url} y guardado en: {output_filepath}")
            time.sleep(1) # Pausa
            return output_filepath
        else:
            print(f"No se pudo extraer contenido principal de {url}")

    except requests.exceptions.RequestException as e:
        print(f"Error obteniendo HTML de {url}: {e}")
    return None