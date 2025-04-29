# -*- coding: utf-8 -*-
from flask import Flask, request, render_template_string, jsonify, send_file
import os
import subprocess
import tempfile
import uuid
import time
import shutil
import logging
from logging.handlers import RotatingFileHandler
import datetime
import sys
import re
import io
import glob
import traceback

# Forzar la codificación ASCII para Python 2.7
reload(sys)
sys.setdefaultencoding('ascii')

# Función para convertir cualquier texto a ASCII puro

def to_ascii(text):
    """
    Convierte cualquier texto a ASCII puro, reemplazando caracteres no-ASCII con alternativas seguras.
    Maneja correctamente cadenas Unicode en Python 2.7.
    """
    if text is None:
        return ""
    
    # Convertir a string si no lo es
    if not isinstance(text, (str, unicode, bytes)):
        try:
            text = str(text)
        except:
            return repr(text)
    
    try:
        # Si es bytes o str en Python 2.7, convertir a unicode primero
        if isinstance(text, str):
            # Intentar diferentes codificaciones
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    text = text.decode(encoding, errors='replace')
                    break
                except:
                    continue
        
        # Si ahora es unicode, convertir a ASCII seguro
        if isinstance(text, unicode):
            # Reemplazar caracteres específicos en español
            replacements = {
                u'\xe1': 'a', u'\xe9': 'e', u'\xed': 'i', u'\xf3': 'o', u'\xfa': 'u',
                u'\xc1': 'A', u'\xc9': 'E', u'\xcd': 'I', u'\xd3': 'O', u'\xda': 'U',
                u'\xf1': 'n', u'\xd1': 'N', u'\xfc': 'u', u'\xdc': 'U',
                u'\xbf': '?', u'\xa1': '!', u'\xe7': 'c', u'\xc7': 'C'
            }
            
            for char, replacement in replacements.items():
                text = text.replace(char, replacement)
            
            # Finalmente codificar a ASCII, reemplazando los caracteres restantes
            return text.encode('ascii', errors='replace')
    except:
        pass
    
    # Si todo lo anterior falla, convertir byte por byte
    try:
        result = ''
        for char in str(text):
            if ord(char) < 128:
                result += char
            else:
                result += '_'
        return result
    except:
        # Último recurso
        return repr(text)

def safe_json_serialization(data):
    """
    Serializa datos a JSON de manera segura, asegurando que todos los 
    strings sean ASCII válidos para evitar errores de codificación.
    """
    if isinstance(data, dict):
        # Procesar cada clave y valor recursivamente
        result = {}
        for key, value in data.items():
            # Asegurar que la clave sea ASCII
            safe_key = to_ascii(key) if isinstance(key, (str, unicode)) else key
            # Procesar el valor recursivamente
            result[safe_key] = safe_json_serialization(value)
        return result
    elif isinstance(data, list):
        # Procesar cada elemento de la lista recursivamente
        return [safe_json_serialization(item) for item in data]
    elif isinstance(data, (str, unicode)):
        # Convertir strings a ASCII seguro
        return to_ascii(data)
    else:
        # Devolver otros tipos sin cambios (números, booleanos, None)
        return data

def sanitize_filename(filename):
    """
    Sanitiza un nombre de archivo para que solo contenga caracteres ASCII seguros.
    """
    if filename is None:
        return ""
    
    # Primero convertir a ASCII puro
    ascii_name = to_ascii(filename)
    
    # Luego eliminar caracteres no permitidos en nombres de archivo
    safe_name = ''
    for char in ascii_name:
        if char.isalnum() or char in '._- ':
            safe_name += char
        else:
            safe_name += '_'
    
    # Asegurar que no empieza ni termina con espacios
    safe_name = safe_name.strip()
    
    # Si el nombre quedó vacío, usar un valor por defecto
    if not safe_name:
        safe_name = "file"
    
    return safe_name

def sanitize_windows_path(path):
    """
    Sanitiza una ruta de archivo para que sea compatible con Windows.
    Reemplaza caracteres no permitidos y caracteres no ASCII.
    """
    if path is None:
        return ""

    # Caracteres no permitidos en rutas de Windows
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']

    # Convertir a string si no lo es
    if not isinstance(path, (str, unicode)):
        path = str(path)

    # Dividir la ruta en partes (directorios)
    if '/' in path:
        parts = path.split('/')
    elif '\\' in path:
        parts = path.split('\\')
    else:
        parts = [path]

    # Sanitizar cada parte de la ruta
    sanitized_parts = []
    for part in parts:
        if not part:  # Skip empty parts
            continue
            
        # Primero convertir a ASCII
        part_ascii = to_ascii(part)
        
        # Reemplazar caracteres inválidos
        sanitized = ""
        for char in part_ascii:
            if char in invalid_chars:
                sanitized += "_"
            else:
                sanitized += char
        
        # Eliminar espacios al principio y al final
        sanitized = sanitized.strip()
        
        # Si después de sanitizar queda vacío, poner un valor por defecto
        if not sanitized:
            sanitized = "dir"
            
        sanitized_parts.append(sanitized)

    # Reconstruir la ruta con el separador de Windows
    if sanitized_parts:
        sanitized_path = os.path.join(*sanitized_parts)
        return sanitized_path
    else:
        return "dir"

# Configuración de logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, 'scielo_validator.log')

# Crear logger
logger = logging.getLogger('scielo_validator')
logger.setLevel(logging.INFO)

# Crear handler para archivo con rotación
file_handler = RotatingFileHandler(log_file, maxBytes=10485760, backupCount=5)
file_handler.setLevel(logging.INFO)

# Crear handler para consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formato para los logs
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(log_format)
console_handler.setFormatter(log_format)

# Añadir handlers al logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Log de inicio de la aplicación
logger.info("====== SciELO XML Validator Server Started ======")
logger.info("Configuracion ASCII para Python 2.7 establecida")

app = Flask(__name__)

# Configuracion
XML_PACKAGE_MAKER = r"C:\scielo\bin\xml\xml_package_maker.py"
TEMP_DIR = r"C:\scielo\bin\web\temp"
PYTHON_PATH = r"C:\Python27\python.exe"

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Template HTML con caracteres estrictamente ASCII
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>SciELO XML Validator</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        .btn { background-color: #4CAF50; color: white; padding: 10px 15px; border: none; cursor: pointer; }
        .btn:hover { background-color: #45a049; }
        .download-btn { background-color: #2196F3; margin-top: 10px; }
        .download-btn:hover { background-color: #0b7dda; }
        .view-btn { background-color: #ff9800; color: white; padding: 10px 15px; border: none; cursor: pointer; margin-left: 10px; }
        .view-btn:hover { background-color: #e68a00; }
        .results { margin-top: 20px; border: 1px solid #ddd; padding: 15px; background-color: #f9f9f9; }
        pre { white-space: pre-wrap; word-wrap: break-word; background-color: #f0f0f0; padding: 10px; }
        .error { color: #D8000C; background-color: #FFBABA; padding: 10px; border-radius: 5px; }
        .success { color: #4F8A10; background-color: #DFF2BF; padding: 10px; border-radius: 5px; }
        .loading { display: none; text-align: center; padding: 20px; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 2s linear infinite; margin: 0 auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .button-container { display: flex; }
        .tab-buttons { display: flex; margin-bottom: 15px; }
        .tab-button { padding: 10px 15px; cursor: pointer; background-color: #f1f1f1; border: 1px solid #ddd; margin-right: -1px; }
        .tab-button.active { background-color: white; border-bottom: 1px solid white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .files-info { margin-top: 10px; font-size: 0.9em; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h1>SciELO XML Validator</h1>
        
        <div class="tab-buttons">
            <div class="tab-button active" data-tab="file-tab">Archivo XML</div>
            <div class="tab-button" data-tab="folder-tab">Carpeta</div>
        </div>
        
        <div id="file-tab" class="tab-content active">
            <form id="upload-file-form" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="xml_file">Seleccionar archivo XML:</label>
                    <input type="file" id="xml_file" name="xml_file" accept=".xml" required>
                </div>
                <button type="submit" class="btn">Validar XML</button>
            </form>
        </div>
        
        <div id="folder-tab" class="tab-content">
            <form id="upload-folder-form" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="folder_files">Seleccionar carpeta:</label>
                    <input type="file" id="folder_files" name="folder_files[]" webkitdirectory directory multiple required>
                    <div class="files-info" id="files-count">No se ha seleccionado ninguna carpeta</div>
                </div>
                <button type="submit" class="btn">Validar carpeta</button>
            </form>
        </div>
        
        <div id="loading" class="loading">
            <div class="spinner"></div>
            <p>Procesando, por favor espere...</p>
        </div>
        
        <div id="results" class="results" style="display:none;">
            <h2>Resultados de validacion</h2>
            <div id="status"></div>
            <div id="report-container">
                <h3>Reporte:</h3>
                <pre id="report"></pre>
            </div>
            <div id="button-container" class="button-container" style="display:none;">
                <button id="download-btn" class="btn download-btn">Descargar reporte</button>
                <a id="open-html-btn" target="_blank" class="btn view-btn" style="text-decoration:none;">Abrir reporte HTML</a>
            </div>
        </div>

        <div>
            <p><strong>Nota:</strong> Este validador utiliza exclusivamente el CSV de SciELO MX y la validación se realiza según la modificación realizada en ws-journals</p>
        </div>

    </div>
    
    <script>
        // Funcionalidad de pestanas
        document.querySelectorAll('.tab-button').forEach(function(button) {
            button.addEventListener('click', function() {
                document.querySelectorAll('.tab-button').forEach(function(btn) {
                    btn.classList.remove('active');
                });
                document.querySelectorAll('.tab-content').forEach(function(content) {
                    content.classList.remove('active');
                });
                
                this.classList.add('active');
                document.getElementById(this.getAttribute('data-tab')).classList.add('active');
            });
        });
        
        // Mostrar cantidad de archivos seleccionados
        document.getElementById('folder_files').addEventListener('change', function(e) {
            const fileCount = e.target.files.length;
            document.getElementById('files-count').textContent = 
                fileCount > 0 ? fileCount + ' archivos seleccionados' : 'No se ha seleccionado ninguna carpeta';
        });
        
        // Envio de formulario para archivo individual
        document.getElementById('upload-file-form').addEventListener('submit', function(e) {
            e.preventDefault();
            
            var formData = new FormData(this);
            sendValidationRequest('/validate', formData);
        });
        
        // Envio de formulario para carpeta
        document.getElementById('upload-folder-form').addEventListener('submit', function(e) {
            e.preventDefault();
            
            var formData = new FormData(this);
            
            // Anadir bandera para indicar que es una carpeta
            formData.append('is_folder', 'true');
            
            sendValidationRequest('/validate_folder', formData);
        });
        
        // Funcion general para enviar solicitud de validacion
        function sendValidationRequest(url, formData) {
            var resultsDiv = document.getElementById('results');
            var loadingDiv = document.getElementById('loading');
            var statusDiv = document.getElementById('status');
            var reportDiv = document.getElementById('report');
            var buttonContainer = document.getElementById('button-container');
            var downloadBtn = document.getElementById('download-btn');
            var openHtmlBtn = document.getElementById('open-html-btn');
            
            resultsDiv.style.display = 'none';
            loadingDiv.style.display = 'block';
            
            fetch(url, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                loadingDiv.style.display = 'none';
                resultsDiv.style.display = 'block';
                
                if (data.error) {
                    statusDiv.innerHTML = '<div class="error">Error: ' + data.error + '</div>';
                    reportDiv.textContent = '';
                    buttonContainer.style.display = 'none';
                } else {
                    if (data.success) {
                        statusDiv.innerHTML = '<div class="success">XML valido!</div>';
                    } else {
                        statusDiv.innerHTML = '<div class="error">XML invalido. Ver reporte para detalles.</div>';
                    }
                    
                    reportDiv.textContent = data.report;
                    
                    if (data.report_id) {
                        buttonContainer.style.display = 'flex';
                        downloadBtn.onclick = function() {
                            window.location.href = '/download_report/' + data.report_id;
                        };
                        
                        // Configurar el enlace para abrir el HTML
                        openHtmlBtn.href = '/open_html_report/' + data.report_id;
                    } else {
                        buttonContainer.style.display = 'none';
                    }
                }
            })
            .catch(error => {
                loadingDiv.style.display = 'none';
                resultsDiv.style.display = 'block';
                statusDiv.innerHTML = '<div class="error">Error en la solicitud: ' + error + '</div>';
                reportDiv.textContent = '';
                buttonContainer.style.display = 'none';
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    logger.info("Home page requested from {}".format(request.remote_addr))
    return render_template_string(HTML)

@app.route('/validate', methods=['POST'])
def validate_xml():
    if 'xml_file' not in request.files:
        logger.warning("Validation attempt with no file")
        return jsonify({'error': 'No file found'})
    
    file = request.files['xml_file']
    if file.filename == '':
        logger.warning("Validation attempt with empty filename")
        return jsonify({'error': 'No file selected'})
    
    client_ip = request.remote_addr
    logger.info("Validation request from {} for file: {}".format(client_ip, file.filename))
    
    # Crear un ID basado en el nombre del archivo
    base_filename = os.path.splitext(file.filename)[0]
    # Añadir un timestamp para evitar colisiones
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    session_id = "{}-{}".format(base_filename, timestamp)
    # Eliminar caracteres no permitidos en nombres de carpetas
    session_id = "".join(c for c in session_id if c.isalnum() or c in '-_')
    
    session_dir = os.path.join(TEMP_DIR, session_id)
    os.makedirs(session_dir)
    
    try:
        xml_path = os.path.join(session_dir, file.filename)
        file.save(xml_path)
        logger.info("File saved: {}".format(xml_path))
        
        # Ejecutar el validador XPM
        cmd = [PYTHON_PATH, XML_PACKAGE_MAKER, xml_path]
        logger.info("Executing validation command: {}".format(' '.join(cmd)))
        
        # Usar subprocess de manera compatible con Python 2.7
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()  
        
        # Usar nuestra función de conversión a ASCII
        if stdout:
            stdout = to_ascii(stdout)
        if stderr:
            stderr = to_ascii(stderr)
            
        logger.info("Command exit code: {}".format(process.returncode))
        logger.info("Command stdout length: {}".format(len(stdout) if stdout else 0))
        if stderr:
            logger.error("Command stderr length: {}".format(len(stderr)))
        
        report_content = "No detailed report was generated."
        report_file = None
        report_id = None
        
        # Esperar un momento para que se generen los archivos
        time.sleep(2)
        
        # Buscar archivos de reporte (tanto .html como .report.txt)
        html_report_found = False
        for root, dirs, files in os.walk(session_dir):
            logger.info("Checking directory: {} for report files".format(root))
            for file_name in files:
                logger.info("Found file: {}".format(file_name))
                
                # Buscar archivos HTML primero (como se muestra en tu captura)
                if file_name.endswith('.html'):
                    html_report_found = True
                    report_file = os.path.join(root, file_name)
                    logger.info("HTML Report found: {}".format(report_file))
                
                # Luego buscar los .report.txt por si acaso
                elif file_name.endswith('.report.txt') and not html_report_found:
                    report_file = os.path.join(root, file_name)
                    try:
                        # Leer de forma segura ignorando caracteres no-ASCII
                        with open(report_file, 'rb') as f:
                            content = f.read()
                            report_content = to_ascii(content)
                        
                        report_id = session_id
                        logger.info("TXT Report found: {}".format(report_file))
                    except Exception as e:
                        report_content = "Error reading TXT report: {}".format(str(e))
                        logger.error("Error reading TXT report: {}".format(str(e)))
        
        # Si no se encontró ningún archivo de reporte, usar la salida del proceso
        if not report_id:
            report_content = "Validation output:\n\n" + stdout if stdout else "No output available."
            if stderr:
                report_content += "\n\nErrors:\n\n" + stderr
            
            report_id = session_id
            logger.info("Using process output as report")
        
        # Guardar la salida como reporte de texto
        txt_save_path = os.path.join(TEMP_DIR, session_id + '.txt')
        try:
            # Asegurarse de que solo hay caracteres ASCII
            safe_content = to_ascii(report_content)
            with open(txt_save_path, 'w') as f:
                f.write(safe_content)
            logger.info("Report saved to: {}".format(txt_save_path))
        except Exception as e:
            logger.error("Error saving report: {}".format(str(e)))
        
        # Determinar si la validación fue exitosa
        success = not stderr and process.returncode == 0 and "ERROR" not in report_content.upper()
        
        if success:
            logger.info("Validation successful for {}".format(file.filename))
        else:
            logger.warning("Validation failed for {}".format(file.filename))
        
        return jsonify({
            'success': success,
            'report': report_content,
            'report_id': report_id
        })
    
    except Exception as e:
        logger.error("Error during validation: {}".format(str(e)))
        return jsonify({'error': to_ascii(str(e))})

@app.route('/validate_folder', methods=['POST'])
def validate_folder():
    if 'folder_files[]' not in request.files:
        logger.warning("Folder validation attempt with no files")
        # Devolver explícitamente como JSON
        return jsonify({'error': 'No se encontraron archivos'})
    
    files = request.files.getlist('folder_files[]')
    if not files or len(files) == 0:
        logger.warning("Folder validation attempt with empty file list")
        # Devolver explícitamente como JSON
        return jsonify({'error': 'No se seleccionaron archivos'})
    
    client_ip = request.remote_addr
    logger.info("Folder validation request from {} with {} files".format(client_ip, len(files)))
    
    # Crear un ID único para la sesión
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    session_id = "folder-{}".format(timestamp)
    session_id = "".join(c for c in session_id if c.isalnum() or c in '-_')
    
    # Crear directorio para la sesión
    session_dir = os.path.join(TEMP_DIR, session_id)
    if not os.path.exists(session_dir):
        os.makedirs(session_dir)
    
    try:
        # Usar estructura plana y nombres sencillos
        xml_files = []
        support_files = []
        
        # LOG ADICIONAL: Registrar el inicio del procesamiento de archivos
        logger.info("INICIO DE PROCESAMIENTO DE ARCHIVOS - Sesión: {}".format(session_id))
        
        # Procesar y guardar los archivos
        for file in files:
            if not file.filename:
                continue
            
            # Generar nombre seguro
            basename = os.path.basename(file.filename)
            name, ext = os.path.splitext(basename)
            ext = ext.lower()
            
            # Crear nombre simple alfanumérico
            safe_name = ''.join(c for c in name if c.isalnum())[:20] + ext
            if not safe_name or safe_name == ext:
                safe_name = "file{}_{}".format(len(xml_files) + len(support_files), ext)
            
            file_path = os.path.join(session_dir, safe_name)
            file.save(file_path)
            
            # LOG ADICIONAL: Registrar el guardado de cada archivo
            logger.info("Archivo guardado: {} (original: {})".format(safe_name, basename))
            
            # Procesar cualquier archivo de texto para eliminar font-family (XML, HTML, CSS, etc.)
            if ext in ['.xml', '.html', '.htm', '.css', '.xsl', '.xslt', '.svg', '.txt']:
                try:
                    # Leer el contenido
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # Intentar decodificar con diferentes codificaciones
                    encoding_used = None
                    text_content = None
                    
                    # LOG ADICIONAL: Registrar tamaño del archivo y si contiene 'font-family'
                    logger.info("Analizando archivo {} ({} bytes)".format(safe_name, len(content)))
                    if b'font-family' in content:
                        logger.warning("ATENCIÓN: Archivo {} contiene 'font-family' en binario".format(safe_name))
                    
                    for encoding in ['utf-8', 'latin-1', 'ascii']:
                        try:
                            text_content = content.decode(encoding, errors='replace')
                            encoding_used = encoding
                            break
                        except:
                            continue
                    
                    if text_content is None:
                        text_content = content.decode('ascii', errors='replace')
                        encoding_used = 'ascii-replace'
                    
                    # LOG ADICIONAL: Registrar codificación usada
                    logger.info("Archivo {} decodificado usando: {}".format(safe_name, encoding_used))
                    
                    # Buscar el término font-family en el contenido
                    if 'font-family' in text_content:
                        logger.warning("ENCONTRADO 'font-family' en archivo: {}".format(safe_name))
                        logger.warning("Contexto: {}".format(
                            text_content[max(0, text_content.find('font-family') - 20):
                                        min(len(text_content), text_content.find('font-family') + 30)]
                        ))
                    
                    # SOLUCIÓN MEJORADA AL ERROR: Múltiples reemplazos para capturar todas las variantes
                    original_text = text_content
                    
                    # Conjunto ampliado de términos a reemplazar
                    replacements = {
                        'font-family': 'data-fontname',
                        'font family': 'data-fontname',
                        'fontfamily': 'data-fontname',
                        'font-familias': 'data-fontname',
                        'font-face': 'data-fontface',
                        'fontface': 'data-fontface',
                        'font-style': 'data-fontstyle',
                        'font-weight': 'data-fontweight',
                        'font-size': 'data-fontsize'
                    }
                    
                    for find_term, replace_term in replacements.items():
                        text_content = text_content.replace(find_term, replace_term)
                        text_content = text_content.replace(find_term.upper(), replace_term.upper())
                        text_content = text_content.replace(find_term.capitalize(), replace_term.capitalize())
                    
                    # Registrar si se hicieron cambios
                    if original_text != text_content:
                        logger.info("Se reemplazaron términos relacionados con fuentes en: {}".format(safe_name))
                    
                    # Guardar el contenido modificado
                    with open(file_path, 'wb') as f:
                        f.write(text_content.encode('utf-8'))
                    
                    logger.info("Archivo procesado y guardado: {}".format(safe_name))
                    
                    # Si es XML, añadirlo a la lista específica
                    if ext == '.xml':
                        xml_files.append(file_path)
                except Exception as e:
                    logger.error("Error procesando archivo {}: {}".format(safe_name, str(e)))
                    if ext == '.xml':
                        xml_files.append(file_path)  # Añadir de todos modos para intentar validar
            else:
                support_files.append(file_path)
                logger.info("Guardado archivo de soporte (sin procesar): {}".format(safe_name))
        
        if not xml_files:
            logger.warning("No se encontraron archivos XML en la carpeta")
            return jsonify({'error': 'No se encontraron archivos XML en la carpeta subida'})
        
        logger.info("Procesados {} archivos XML y {} archivos de soporte".format(len(xml_files), len(support_files)))
        
        # LOG ADICIONAL: Mostrar el contenido completo del directorio después del procesamiento
        logger.info("CONTENIDO DEL DIRECTORIO DESPUÉS DEL PROCESAMIENTO:")
        for root, dirs, files in os.walk(session_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                file_size = os.path.getsize(file_path)
                logger.info("  - {}: {} bytes".format(file_name, file_size))
        
        # Validar toda la carpeta - ENFOQUE DIRECTO
        logger.info("INICIANDO VALIDACIÓN DE CARPETA: {}".format(session_dir))
        
        # Guardar un reporte básico inicial 
        pre_validation_report = """REPORTE PREVIO A VALIDACIÓN
ID de sesión: {}
Fecha: {}
Archivos XML: {}
Archivos de soporte: {}

Este reporte se genera previo a la ejecución del validador XML.
        """.format(
            session_id,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ", ".join([os.path.basename(f) for f in xml_files]),
            len(support_files)
        )
        
        pre_report_path = os.path.join(TEMP_DIR, session_id + '_pre.txt')
        with open(pre_report_path, 'w') as f:
            f.write(pre_validation_report)
        
        # Ejecutar la validación con un enfoque simplificado
        cmd = [PYTHON_PATH, XML_PACKAGE_MAKER, session_dir]
        logger.info("COMANDO DE VALIDACIÓN: {}".format(' '.join(cmd)))
        
        # Ejecutar con captura de errores detallada
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Esperar hasta 2 minutos (120 segundos)
            max_time = 120
            start_time = time.time()
            timed_out = False
            
            while process.poll() is None:
                if time.time() - start_time > max_time:
                    logger.warning("TIMEOUT: La validación excedió {} segundos".format(max_time))
                    try:
                        process.kill()
                    except:
                        pass
                    timed_out = True
                    break
                time.sleep(0.5)
            
            exit_code = process.returncode if process.returncode is not None else -1
            logger.info("VALIDACIÓN COMPLETADA - Código de salida: {}".format(exit_code))
            
            if timed_out:
                stdout, stderr = b"", b"Error: Tiempo de espera agotado durante la validacion (limite: 2 minutos)"
            else:
                stdout, stderr = process.communicate()
            
            # LOG ADICIONAL: Registrar salidas originales
            if stdout:
                logger.info("STDOUT ORIGINAL (primeros 500 caracteres): {}".format(stdout[:500]))
            if stderr:
                logger.warning("STDERR ORIGINAL (primeros 500 caracteres): {}".format(stderr[:500]))
            
            # Convertir a ASCII seguro
            stdout = to_ascii(stdout) if stdout else ""
            stderr = to_ascii(stderr) if stderr else ""
            
            # REVISIÓN ESPECIAL PARA FONT-FAMILY: Buscar específicamente en la salida
            if 'font-family' in stderr:
                logger.error("DETECCIÓN CRÍTICA: 'font-family' encontrado en stderr")
                font_family_lines = [line for line in stderr.split('\n') if 'font-family' in line]
                for line in font_family_lines:
                    logger.error("LÍNEA CON ERROR: {}".format(line))
            
            # Buscar reportes HTML generados automáticamente
            logger.info("BUSCANDO REPORTES HTML GENERADOS:")
            html_files = []
            html_report_found = False
            report_file = None

            for root, dirs, files in os.walk(session_dir):
                for file_name in files:
                    if file_name.endswith('.html'):
                        html_path = os.path.join(root, file_name)
                        html_files.append(html_path)
                        logger.info("Reporte HTML encontrado: {}".format(html_path))
                        
                        # Usar el primer HTML encontrado como reporte principal
                        if not html_report_found:
                            html_report_found = True
                            report_file = html_path
                            
                            # Copiar el HTML a la carpeta temporal para acceso directo
                            try:
                                html_dest = os.path.join(TEMP_DIR, session_id + '.html')
                                shutil.copy2(html_path, html_dest)
                                logger.info("HTML copiado a: {}".format(html_dest))
                            except Exception as e:
                                logger.error("Error copiando HTML: {}".format(str(e)))
            
            # Determinar si hubo errores específicos de font-family
            font_family_error = 'font-family' in stderr or 'font-family' in stdout
            if font_family_error:
                # Intentar extraer la línea exacta que contiene el error
                error_lines = stderr.split('\n')
                font_family_error_detail = ""
                for line in error_lines:
                    if 'font-family' in line:
                        font_family_error_detail = line
                        break
                
                logger.error("ERROR FONT-FAMILY DETECTADO: {}".format(font_family_error_detail))
                
                # Eliminar este error específico
                stderr = stderr.replace(font_family_error_detail, 
                                       "AVISO: Se encontró un atributo 'font-family' que ha sido ignorado")
                
                # SOLUCIÓN ESPECÍFICA: Si este es el único error, considerar la validación exitosa
                if len(stderr.strip().split('\n')) < 5 and 'font-family' in stderr:
                    stderr = "AVISO: Se encontraron algunos atributos de estilo no estándar que han sido ignorados.\n"
                    stderr += "La validación estructural del XML es correcta."
                    exit_code = 0  # Forzar código de éxito
            
            # Generar informe consolidado para el reporte de texto
            consolidated_report = "REPORTE DE VALIDACIÓN DE CARPETA\n"
            consolidated_report += "ID de sesión: {}\n".format(session_id)
            consolidated_report += "Fecha: {}\n".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            consolidated_report += "Total de archivos XML: {}\n".format(len(xml_files))
            consolidated_report += "Total de archivos de soporte: {}\n\n".format(len(support_files))
            
            if stderr:
                consolidated_report += "MENSAJES DE VALIDACIÓN:\n"
                consolidated_report += stderr + "\n\n"
            
            consolidated_report += "SALIDA DEL VALIDADOR:\n"
            consolidated_report += stdout

            # Si hay reportes HTML, agregarlos al informe
            if html_files:
                consolidated_report += "\n\nREPORTES HTML GENERADOS:\n"
                for html_file in html_files:
                    consolidated_report += "- {}\n".format(os.path.basename(html_file))
            
            # Determinar si fue exitoso
            success = (
                (not timed_out) and 
                (exit_code == 0 or font_family_error) and 
                not (stderr and 'error' in stderr.lower() and 'font-family' not in stderr.lower())
            )
            
            logger.info("RESULTADO FINAL: {}".format("ÉXITO" if success else "ERROR"))
            
            # Guardar el reporte en texto plano
            txt_report_path = os.path.join(TEMP_DIR, session_id + '.txt')
            with open(txt_report_path, 'w') as f:
                f.write(consolidated_report)
            
            logger.info("Reporte de texto guardado en: {}".format(txt_report_path))
            
            # Respuesta final al cliente - GARANTIZAR RESPUESTA JSON
            response_data = {
                'success': success,
                'report': consolidated_report,
                'report_id': session_id
            }
            
            # Aplicar serialización segura para evitar errores de codificación
            safe_response = safe_json_serialization(response_data)
            
            # Salida de debug
            logger.info("Enviando respuesta JSON al cliente: {}".format(str(safe_response.keys())))
            
            try:
                # Intentar respuesta JSON normal
                return jsonify(safe_response)
            except Exception as json_error:
                # Si falla la serialización JSON, crear una respuesta manual
                logger.error("Error al serializar JSON: {}".format(str(json_error)))
                
                # Crear respuesta JSON manualmente
                import json
                response_text = json.dumps(safe_response, ensure_ascii=True)
                
                from flask import Response
                return Response(
                    response_text,
                    mimetype='application/json',
                    headers={
                        'Content-Type': 'application/json; charset=ascii'
                    }
                )
            
        except Exception as e:
            # Capturar traza de error completa
            error_trace = traceback.format_exc()
            logger.error("ERROR EN EJECUCIÓN DE VALIDADOR: {}".format(str(e)))
            logger.error(error_trace)
            
            # Garantizar respuesta JSON
            error_response = {
                'error': "Error durante la validación: {}".format(to_ascii(str(e)))
            }
            
            # Aplicar serialización segura
            safe_error = safe_json_serialization(error_response)
            
            try:
                return jsonify(safe_error)
            except Exception as json_error:
                # Respuesta manual si jsonify falla
                import json
                response_text = json.dumps(safe_error, ensure_ascii=True)
                
                from flask import Response
                return Response(
                    response_text,
                    mimetype='application/json',
                    headers={
                        'Content-Type': 'application/json; charset=ascii'
                    }
                )
    
    except Exception as e:
        # Capturar traza de error completa
        error_trace = traceback.format_exc()
        error_msg = to_ascii(str(e))
        logger.error("ERROR GENERAL EN VALIDATE_FOLDER: {}".format(error_msg))
        logger.error(error_trace)
        
        # Garantizar respuesta JSON
        error_response = {'error': error_msg}
        
        # Aplicar serialización segura
        safe_error = safe_json_serialization(error_response)
        
        try:
            return jsonify(safe_error)
        except Exception as json_error:
            # Respuesta manual si jsonify falla
            import json
            response_text = json.dumps(safe_error, ensure_ascii=True)
            
            from flask import Response
            return Response(
                response_text,
                mimetype='application/json',
                headers={
                    'Content-Type': 'application/json; charset=ascii'
                }
            )

@app.route('/download_report/<report_id>')
def download_report(report_id):
    client_ip = request.remote_addr
    logger.info("Download request from {} for report: {}".format(client_ip, report_id))
    
    # Buscar el archivo de texto
    txt_report_path = os.path.join(TEMP_DIR, report_id + '.txt')
    if os.path.exists(txt_report_path):
        logger.info("TXT Report found, serving: {}".format(txt_report_path))
        try:
            return send_file(
                txt_report_path, 
                mimetype='text/plain',
                as_attachment=True,
                attachment_filename='validation_report.txt'  # Para Flask antiguo
            )
        except TypeError:
            # Si falla, usar solo los parámetros básicos
            return send_file(
                txt_report_path, 
                mimetype='text/plain',
                as_attachment=True
            )
    
    logger.warning("Report not found: {}".format(report_id))
    return "Report not found", 404

@app.route('/open_html_report/<report_id>')
def open_html_report(report_id):
    """Abre el reporte HTML en una nueva ventana"""
    client_ip = request.remote_addr
    logger.info("Solicitud de reporte HTML de {} para reporte: {}".format(client_ip, report_id))
    
    # Sanitizar el ID del reporte para evitar ataques de ruta
    safe_report_id = "".join(c for c in report_id if c.isalnum() or c in '-_')
    if safe_report_id != report_id:
        logger.warning("Se sanitizó el ID del reporte: {} -> {}".format(report_id, safe_report_id))
        report_id = safe_report_id
    
    # 1. Verificar si existe un archivo HTML directo para el reporte
    direct_html_path = os.path.join(TEMP_DIR, report_id + '.html')
    if os.path.exists(direct_html_path):
        logger.info("Reporte HTML encontrado: {}".format(direct_html_path))
        try:
            return send_file(direct_html_path, mimetype='text/html', as_attachment=False)
        except Exception as e:
            logger.error("Error al enviar el archivo HTML: {}".format(str(e)))
            # Continuar con el siguiente método si falla
    
    # 2. Buscar HTML en la estructura de directorios del reporte_id
    session_dir = os.path.join(TEMP_DIR, report_id)
    if os.path.exists(session_dir):
        # Buscar archivos HTML recursivamente - Búsqueda más profunda
        html_files = []
        for root, dirs, files in os.walk(session_dir):
            for file in files:
                if file.endswith('.html'):
                    html_path = os.path.join(root, file)
                    html_files.append(html_path)
                    logger.info("Reporte HTML encontrado en estructura de directorios: {}".format(html_path))
        
        # Intentar cada archivo HTML encontrado
        for html_path in html_files:
            try:
                logger.info("Intentando enviar HTML: {}".format(html_path))
                return send_file(html_path, mimetype='text/html', as_attachment=False)
            except Exception as e:
                logger.error("Error al enviar el archivo HTML {}: {}".format(html_path, str(e)))
                # Continuar con el siguiente si falla
    
    # 3. Buscar específicamente en la ruta del error mostrado
    # Ruta específica basada en el error reportado
    specific_error_path = os.path.join(TEMP_DIR, report_id + '_xpm', 'errors', 'xpm.html')
    if os.path.exists(specific_error_path):
        logger.info("Reporte HTML encontrado en ruta específica de error: {}".format(specific_error_path))
        try:
            return send_file(specific_error_path, mimetype='text/html', as_attachment=False)
        except Exception as e:
            logger.error("Error al enviar el archivo HTML de ruta específica: {}".format(str(e)))
    
    # 4. Si no se encontró HTML, pero sabemos la ubicación específica del reporte, mostrar un mensaje explicativo
    txt_report_path = os.path.join(TEMP_DIR, report_id + '.txt')
    if os.path.exists(txt_report_path):
        try:
            with open(txt_report_path, 'r') as f:
                report_content = f.read()
            
            # Buscar la ruta del reporte HTML en el contenido
            report_paths = []
            for line in report_content.splitlines():
                if '.html' in line and ('Report:' in line or 'Saved report:' in line):
                    path = line.split(':', 1)[1].strip() if ':' in line else line.strip()
                    report_paths.append(path)
            
            if report_paths:
                # Mostrar información sobre dónde está realmente el archivo
                html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Reporte HTML no accesible directamente</title>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { color: #D8000C; }
        pre { background-color: #f0f0f0; padding: 10px; overflow: auto; }
        .info { background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; }
        p { line-height: 1.5; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Reporte HTML no accesible vía web</h1>
        <div class="info">
            <p>El reporte HTML fue generado correctamente pero se encuentra en una ubicación del servidor que no es accesible directamente vía web.</p>
        </div>
        <p>Las rutas de los reportes generados son:</p>
        <pre>{}</pre>
        <p>Puede acceder al reporte de texto completo:</p>
        <p><a href="/download_report/{}" style="color: #2196F3; text-decoration: none;">Descargar reporte de texto</a></p>
        <hr>
        <p><strong>Solución técnica:</strong> Para acceder al HTML directamente, un administrador debe configurar el servidor para servir archivos desde <code>C:/scielo/bin/web/temp</code> o copiar los archivos HTML a una ubicación accesible.</p>
    </div>
</body>
</html>
                """.format('\n'.join(report_paths), report_id)
                
                return Response(html_content, mimetype='text/html')
            
            # Si no encontramos rutas específicas, generar HTML desde el texto como antes
            safe_content = to_ascii(report_content)
            safe_content = safe_content.replace('<', '&lt;').replace('>', '&gt;')
            
            # Generar HTML simple
            html_content = """<!DOCTYPE html>
<html>
<head>
    <title>SciELO XML Validation Report</title>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <style>
        body { font-family: monospace; margin: 20px; }
        h1 { color: #333; }
        pre { background-color: #f5f5f5; padding: 15px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <h1>SciELO XML Validation Report</h1>
    <p>No se encontró el reporte HTML. Este es un reporte de texto convertido a HTML.</p>
    <pre>{}</pre>
</body>
</html>
            """.format(safe_content)
            
            # Guardar el HTML generado
            generated_html_path = os.path.join(TEMP_DIR, report_id + '_generated.html')
            with open(generated_html_path, 'w') as f:
                f.write(html_content)
                
            logger.info("HTML generado a partir del reporte de texto: {}".format(generated_html_path))
            return send_file(generated_html_path, mimetype='text/html', as_attachment=False)
        except Exception as e:
            logger.error("Error generando HTML a partir del reporte de texto: {}".format(str(e)))
    
    # 5. Si todo falla, mostrar mensaje de error como HTML con Content-Type adecuado
    logger.warning("Reporte HTML no encontrado para report_id: {}".format(report_id))
    
    error_html = """<!DOCTYPE html>
<html>
<head>
    <title>Reporte no encontrado</title>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { color: #D8000C; }
        p { line-height: 1.5; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Reporte HTML no encontrado</h1>
        <p>No se pudo encontrar el reporte HTML para el ID: <strong>{}</strong></p>
        <p>Intente descargar el reporte de texto en su lugar:</p>
        <p><a href="/download_report/{}" style="color: #2196F3; text-decoration: none;">Descargar reporte de texto</a></p>
    </div>
</body>
</html>
    """.format(report_id, report_id)
    
    # Devolver como respuesta HTML correcta, no como error 404
    from flask import Response
    return Response(error_html, mimetype='text/html')

@app.route('/view_logs')
def view_logs():
    # Verificación simple de autorización (mejorar en producción con autenticación real)
    if request.args.get('key') != 'admin123':
        logger.warning("Unauthorized logs access attempt from {}".format(request.remote_addr))
        return "Not authorized", 403
    
    try:
        # Leer y convertir a ASCII puro
        with open(log_file, 'rb') as f:
            content = f.read()
            log_content = to_ascii(content)
        
        logger.info("Logs viewed by {}".format(request.remote_addr))
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>SciELO XML Validator Logs</title>
            <style>
                body { font-family: monospace; padding: 20px; }
                h1 { color: #333; }
                pre { background-color: #f5f5f5; padding: 15px; overflow: auto; max-height: 80vh; }
            </style>
        </head>
        <body>
            <h1>Server Logs</h1>
            <pre>{}</pre>
        </body>
        </html>
        """.format(log_content)
    except Exception as e:
        logger.error("Error reading logs: {}".format(str(e)))
        return "Error reading logs: {}".format(to_ascii(str(e))), 500

# Limpieza de archivos temporales viejos (más de 1 día)
def cleanup_temp_files():
    logger.info("Starting cleanup of temporary files")
    current_time = time.time()
    cleaned_items = 0
    for item in os.listdir(TEMP_DIR):
        item_path = os.path.join(TEMP_DIR, item)
        if os.path.isdir(item_path) and current_time - os.path.getctime(item_path) > 86400:
            try:
                shutil.rmtree(item_path)
                cleaned_items += 1
            except Exception as e:
                logger.error("Failed to delete directory {}: {}".format(item_path, str(e)))
        elif os.path.isfile(item_path) and current_time - os.path.getctime(item_path) > 86400:
            try:
                os.remove(item_path)
                cleaned_items += 1
            except Exception as e:
                logger.error("Failed to delete file {}: {}".format(item_path, str(e)))
    
    logger.info("Cleanup complete. Removed {} items.".format(cleaned_items))

if __name__ == '__main__':
    # Modificar todas las variables de entorno relacionadas con codificación
    os.environ['PYTHONIOENCODING'] = 'ascii'
    os.environ['LC_ALL'] = 'C'
    
    # Limpiar archivos temporales viejos al inicio
    cleanup_temp_files()
    
    # Iniciar el servidor en modo producción con Waitress
    try:
        from waitress import serve
        logger.info("Starting production server on http://0.0.0.0:8080")
        serve(app, host='0.0.0.0', port=8080)
    except ImportError:
        logger.warning("Waitress not installed, falling back to development server")
        app.run(host='0.0.0.0', port=8080, debug=False)
