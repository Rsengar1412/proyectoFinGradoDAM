# Proyecto Fin de Grado DAM - Web de scrapeo Aliexpress y Gestión de Productos

Este poryecto consiste en uan simulación educativa de uan tienda onlien simial a AlieExpress. Integra scraping web con Python, gestión de porducot mediante una aplicación de escritorio y una tienda online desarrollado en WordPress con Woocomerce. Todo ello con el objetivo de comprender los flujops de trabajo reales de un sistema eComerce.

## Autor

- ""Nombre:"" Ricardo Senra García
- ""Tutor:"" Jose Luís Boa Salas
- ""Curso:"" Desarrollod de Aplicaciones Multiplataforma (DAM)
- ""Centro:"" I.E.S Delgado Hernández
- ""Fecha:"" 2024/2025

---

 ## Tecnología utilizadas
 - **Frontend & CMS**: WordPress + WooComerce + Elementor
 - **Backend (gestión y scraping)**: Python
 - **Base de datos**: MySQL (XAMPP)
 - **Scraping web**: BEautifulSoup, Requests
 - **Gestión de imágenes**: AVIZ -> JPG
 - **Otros**: Stripe, Paypal, SMTP, CSV

 ---

## Objetivo del poryecto

1. Crear una tienda online simulada basada en AliExpress.
2. Desarrollar una palicaciónd e escitorio paradministar los porductos.
3. Implementar scraping web para extraer porductos reales de Aliexpress.
4. Auotmatizar la importación de porductos a WooComerce via CSV
5. Integrar pasas seguaro y recuperación de contraseá 

---

## Funciomaito Principales
### Web eComerce (WordPress + Woocomerce)
- Buscar productos, añadir al carrito y comrpar con stipe o Paypal
- Añadir reseñas y recuperar contraseña por email
- Inegracioón con plugins: Elementor, WP Mail SMTP, Image Optimizer, entre otros.

### Aplicación de Escritorio (Python)
- Listado, busqueda, modificación y eliminación de productos.
- Importación desde CSV y manual
- Ajsute de precios según infglación.
- Interfaz amigable conectada a la base de datos de WooComerce.

### Scraping web (Python)
- Obtención de porductos desde Aliexpress
- Convesiónd e imágenes '.avif' a '.jpg'
- Almacenamiento en CSV para importar en WooComerce.
