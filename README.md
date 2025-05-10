# SciELO Validator Web

## Descripción

SciELO Validator Web es una aplicación web desarrollada para facilitar la validación de documentos XML según los estándares específicos de SciELO México. Esta herramienta está diseñada para editores, autores y profesionales que trabajan con documentos científicos y necesitan asegurar que sus archivos XML cumplan con las especificaciones requeridas para su publicación en la biblioteca científica SciELO.

El validador implementa una interfaz web amigable que permite a los usuarios:

- Validar archivos XML individuales
- Validar carpetas completas que contengan múltiples documentos XML y sus archivos asociados
- Visualizar reportes detallados de validación
- Descargar informes para referencia futura

## Características

- **Interfaz web intuitiva**: Diseño simple y claro que facilita el proceso de validación
- **Validación individual o por lotes**: Posibilidad de procesar un solo archivo o una carpeta completa
- **Informes detallados**: Generación de reportes HTML y de texto con información completa sobre errores y advertencias
- **Procesamiento asíncrono**: Manejo eficiente de archivos grandes sin bloquear la interfaz
- **Sanitización automática**: Corrección automática de problemas comunes en archivos XML
- **Seguridad mejorada**: Manejo seguro de archivos y validación de entradas para prevenir vulnerabilidades

## Especificaciones técnicas

- Desarrollado en Python utilizando el framework Flask
- Compatible con Python 2.7 (requerido por las dependencias de SciELO)
- Utiliza el paquete de validación oficial de SciELO (packtools)
- Implementa manejo de codificación ASCII para máxima compatibilidad
- Diseñado para funcionar en entornos Windows donde está instalado el software de SciELO

## Uso

Puede implementar esta herramienta en un servidor Windows. Si requiere uso de una implementación existente debe solicitarse a través de nuestro correo de contacto. Para solicitar acceso o reportar problemas, por favor contacte a:

**Email**: contact@paideiastudio.net

## Notas importantes

Este validador utiliza exclusivamente el CSV de SciELO MX y la validación se realiza según la modificación realizada en C:/scielo/bin/xml/app_modules/app/ws/ws-journals. Los resultados de la validación son específicos para los estándares de SciELO México y pueden no aplicar a otras instalaciones de SciELO con diferentes configuraciones.

## Agradecimientos

Desarrollado por Patricio Pantaleo para Paideia Studio para facilitar el proceso editorial de revistas científicas mexicanas que publican en SciELO.
