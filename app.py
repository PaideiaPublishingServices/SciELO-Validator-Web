from flask import Flask, request, render_template_string, jsonify, send_file
import os
import subprocess
import tempfile
import uuid
import shutil
import time

app = Flask(__name__)

# Configuración
XML_PACKAGE_MAKER = r"C:\SciELO_XPM\xml\xml_package_maker.py"
TEMP_DIR = r"C:\SciELO_XPM\web\temp"
PYTHON_PATH = r"C:\Python27\python.exe"

# Crear directorio temporal si no existe
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# HTML para la página principal
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SciELO XML Validator</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="file"] { border: 1px solid #ddd; padding: 10px; width: 100%; box-sizing: border-box; }
        .btn { background-color: #4CAF50; color: white; padding: 12px 20px; border: none; cursor: pointer; font-size: 16px; }
        .btn:hover { background-color: #45a049; }
        .results { margin-top: 20px; border: 1px solid #ddd; padding: 15px; background-color: #f9f9f9; white-space: pre-wrap; }
        .error { color: #D8000C; background-color: #FFD2D2; padding: 10px; margin: 10px 0; }
        .success { color: #4F8A10; background-color: #DFF2BF; padding: 10px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>SciELO XML Validator</h1>
        <form id="upload-form" enctype="multipart/form-data">
            <div class="form-group">
                <label for="xml_file">Seleccione archivo XML:</label>
                <input type="file" id="xml_file" name="xml_file" accept=".xml" required>
            </div>
            <button type="submit" class="btn">Validar XML</button>
        </form>
        <div id="loading" style="display:none; margin-top: 20px;">
            <p>Procesando, por favor espere...</p>
        </div>
        <div class="results" id="results" style="display:none;"></div>
    </div>

    <script>
        document.getElementById('upload-form').addEventListener('submit', function(e) {
            e.preventDefault();
            
            var formData = new FormData(this);
            var resultsDiv = document.getElementById('results');
            var loadingDiv = document.getElementById('loading');
            
            resultsDiv.style.display = 'none';
            loadingDiv.style.display = 'block';
            
            fetch('/validate', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                loadingDiv.style.display = 'none';
                resultsDiv.style.display = 'block';
                
                if (data.error) {
                    resultsDiv.innerHTML = '<div class="error">Error: ' + data.error + '</div>';
                } else {
                    var content = '<h2>Resultado de la validación:</h2>';
                    if (data.success) {
                        content += '<div class="success">XML válido</div>';
                    } else {
                        content += '<div class="error">XML inválido</div>';
                    }
                    
                    content += '<h3>Reporte:</h3><pre>' + data.report + '</pre>';
                    resultsDiv.innerHTML = content;
                    
                    if (data.report_url) {
                        content += '<p><a href="' + data.report_url + '" target="_blank">Descargar reporte completo</a></p>';
                    }
                }
            })
            .catch(error => {
                loadingDiv.style.display = 'none';
                resultsDiv.style.display = 'block';
                resultsDiv.innerHTML = '<div class="error">Error en la solicitud: ' + error + '</div>';
            });
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/validate', methods=['POST'])
def validate_xml():
    if 'xml_file' not in request.files:
        return jsonify({'error': 'No se encontró el archivo'})
    
    file = request.files['xml_file']
    if file.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'})
    
    # Crear un directorio único para esta validación
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(TEMP_DIR, session_id)
    os.makedirs(session_dir)
    
    try:
        # Guardar el archivo XML
        xml_path = os.path.join(session_dir, file.filename)
        file.save(xml_path)
        
        # Ejecutar el validador XPM en modo validación
        cmd = [PYTHON_PATH, XML_PACKAGE_MAKER, "--validate", xml_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Buscar archivos de reporte generados
        report_content = "No se generó un reporte detallado."
        report_path = None
        
        # Esperar un momento para que se generen los archivos de reporte
        time.sleep(1)
        
        # Buscar archivos con extensión .xml.report.txt
        for root, dirs, files in os.walk(session_dir):
            for file_name in files:
                if file_name.endswith('.report.txt'):
                    report_path = os.path.join(root, file_name)
                    with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
                        report_content = f.read()
        
        # Determinar si la validación fue exitosa
        success = "ERROR" not in report_content.upper() and result.returncode == 0
        
        return jsonify({
            'success': success,
            'output': result.stdout,
            'report': report_content,
            'session_id': session_id
        })
    
    except Exception as e:
        return jsonify({'error': str(e)})

# Iniciar el servidor cuando se ejecuta el script
if __name__ == '__main__':
    from waitress import serve
    print("Servidor iniciado en http://0.0.0.0:8080")
    serve(app, host='0.0.0.0', port=8080)