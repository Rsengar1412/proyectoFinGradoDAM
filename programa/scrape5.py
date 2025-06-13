#librerias
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from lxml import html
from time import sleep
from bs4 import BeautifulSoup
import requests
import os
from urllib.parse import urlparse
from pathlib import Path
from PIL import Image
import io
from PIL import features
import logging
import csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk,messagebox
from tkinter import simpledialog
import mysql.connector
import threading
import queue
import subprocess

# Configuración de Categorias y tamamó máximo del archivo CSV
CATEGORIA_PRINCIPAL = "HogarYJardin" #Categoría principal de los productos
SUBCATEGORIAS = "Alfombrillas"# Esta es la subcategoría del producoto(Accesroios > Accesrios sintron)
#PARENTESIS = "(1)" # El panrentesis lo tengo puesot para ordenar las categorías con las subcategorías cuando iva importanto las categorías en el wordpres 
# Esti es oara crear arcivos CSV que no supere el tamaño máximo de 35MB para poder inportarlos a WordPress
MAX_FILE_SIZE = 35 * 1024 * 1024  # 35MB en bytes

#Variables globales
stop_now = False  # Variable para detener el scraping
cola_que = queue.Queue()  # Cola para evitar comabdo al hilo de Selenium 
contrasena_superusuario = None  # Contraseña de superusuario para crear directorios y copiar imágenes
stop_evento = threading.Event()  # Evento para detener el scraping
total_productos = 0 # Esto es un contador para contar los porductos, solo sirve para teener un control de los productos a la hora de mostrarlo en la terminal 
pagina_actual = 1 # página en la que se encuntra el producto actual
todos_productos = []  # Lista para almacenar todos los productos
archivos_csv = []  # Lista para almacenar los nombres de los archivos CSV generados
driver = webdriver.Chrome() # Driver de  navegador Chrome o sino no funciona el scrapper
driver.close() # Cerrar el driver al inicio para evitar problemas de memoria


driver.get = None  


# Configuración de la base de datos
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'wordpress'
}

def conectar_bd():
    """Función para conectar a la base de datos"""
    try:
        conexion = mysql.connector.connect(**DB_CONFIG)
        return conexion
    except mysql.connector.Error as err:
        messagebox.showerror("Error", f"Error de conexión, no se pudo conectar a la base de datos: {err}")
        return None

#Meétod para listar las caegorías de wordpres
def obtener_categorias_wp():
    conexion = conectar_bd()
    if not conexion:
        messagebox.showerror("Error", "No se pudo conectar a la base de datos")
        return ["Sin categoría"], {}
    else:
        try:
            cursor = conexion.cursor(dictionary=True) # Use dictionary=True for easy column access by name
            #consultar SQL para obtener categorías 
            sql = """
            SELECT t.term_id, t.name, tt.parent, tt.term_taxonomy_id
            FROM wp_terms AS t
            INNER JOIN wp_term_taxonomy AS tt ON t.term_id = tt.term_id
            WHERE tt.taxonomy = 'product_cat'
            ORDER BY tt.parent, t.name;
            """
            cursor.execute(sql) # Ejecutar el cursor con la consulta SQL
            categorias = cursor.fetchall() # Obtener todas las categorías
            categorias_dict = {} # Crear un diccionario para almacenar las categorías y sus subcategorías
            
            #Crear lista para almanecar la categorías
            categorias_lista = ['(Sin categoría)']  
            #Crear una lista para almacenar las categorías
            for categoria in categorias:
                categorias_dict[categoria['term_id']] = {
                    'name': categoria['name'],
                    'parent': categoria['parent'],
                    'term_taxonomy_id': categoria['term_taxonomy_id'],
                    'children': []
                }
            # Crear un diccionario para almacenar las categorías y sus subcategorías
            for categoria_id, categoria_data in categorias_dict.items():
               if categoria_data['parent'] == 0: #Es una categoría principal 
                   categorias_lista.append(categoria_data['name']) # Añadir la categoría principal a la lista
            return categorias_lista, categorias_dict # Retornar la lista de categorías y el diccionario de categorías
        
        
        
        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error al obtener categorías: {err}")
        finally:
            if conexion and conexion.is_connected():
                if 'cursor' in locals() and cursor:
                    cursor.close()
                conexion.close()  # Cerrar la conexión a la base de datos
    return ["Sin categoría"], {}  # Retornar una lista vacía si no se pudo conectar a la base de datos
                
#Método para obtner la subcategorías 
def obtener_subcategorias_wp():
    conexion = conectar_bd()
    if not conexion:
        messagebox.showerror("Error", "No se pudo conectar a la base de datos")
        return ["Sin subcategoría"], {}
    else:
        try: 
            cursor = conexion.cursor(dictionary=True)  # Use dictionary=True for easy column access by name
            # Consultar SQL para obtener subcategorías
            sql = """
            SELECT t.term_id, t.name, tt.parent, tt.term_taxonomy_id, parent.name AS parent_name
            FROM wp_terms AS t
            INNER JOIN wp_term_taxonomy AS tt ON t.term_id = tt.term_id
            LEFT JOIN wp_terms AS parent ON tt.parent = parent.term_id
            WHERE tt.taxonomy = 'product_cat' AND tt.parent != 0
            ORDER BY tt.parent, t.name;
            """
            cursor.execute(sql)  # Ejecutar el cursor con la consulta SQL
            subcategorias = cursor.fetchall()  # Obtener todas las subcategorías
            # Crear un diccionario para almacenar las subcategorías
            subcategorias_dict = {}
            subcategorias_lista = ["Sin subcategoría"]
            for subcategoria in subcategorias:
                subcategorias_dict[subcategoria['term_id']] = subcategoria
                #Añadir a la lista de visualizacion con formatao Categoria > subcategoría
                parent_name = subcategoria['parent_name'] if subcategoria['parent_name'] else "Desconocido"
                display_name = f"{subcategoria['name']}"
                subcategorias_lista.append(display_name)
                
            return subcategorias_lista, subcategorias_dict  # Retornar la lista de subcategorías y el diccionario de subcategorías
        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error al obtener subcategorías: {err}")
        finally:
            if conexion and conexion.is_connected():
                if 'cursor' in locals() and cursor:
                    cursor.close()
                conexion.close()  # Cerrar la conexión a la base de datos
        return ["Sin subcategoría"], {}  # Retornar una lista vacía si no se pudo conectar a la base de datos

#Metodo para cerrar todo el porgrama y cerrar el navegador
def cerrar(ventana):
    if driver:
        try:
            driver.quit()
        except Exception as e:
            print(f"Error al cerrar el navegador: {e}")
    print("Cerrando el programa...")
    ventana.destroy()  # Cerrar la ventana actual
   

#Métod para pediro la categoria y subcategoría del porducot y tmabié pedir la url del producto
def entorno_grafico():
     # Variables para alamcer el resultado 

 #Crear ventana para configurar el scrapper
    ventana = tk.Toplevel()
    ventana.title("Configuración del Scrapper")
    ventana.geometry("500x500")
    
    #Crear frame principal
    frame = ttk.Frame(ventana)
    frame.pack(fill='both', expand=True)
    
    #Título
    ttk.Label(frame, text="Configuración del Scrapper", 
              font=('Arial', 14, 'bold')).pack(pady=10)
    #Url a scrapear
    ttk.Label(frame, text="URL a scrapear:").pack(pady=5)
    url = tk.StringVar(value="https://es.aliexpress.com/w/wholesale-Alfombrillas.html")
    url_entry = ttk.Entry(frame, width=60, textvariable=url)
    url_entry.pack(fill='x', pady=5)
    
    #Categoría principal
    ttk.Label(frame, text="Categoría principal:").pack(pady=5)
    #Crear lista de categorías
    categoria_lista, categorias_map = obtener_categorias_wp()
    #Crear un combobox para seleccionar la categoría
    categoria_comobobox = ttk.Combobox(frame, values=categoria_lista, width=37, state='readonly')
    if categoria_lista:
        categoria_comobobox.set(categoria_lista[0])  # Establecer la primera categoría como predeterminada
    categoria_comobobox.pack(pady=5)
    
    
    #Subcategoría
    ttk.Label(frame, text="Subcategoría:").pack(pady=5)
    #Crear un combobox para seleccionar la subcategoría
    subcategoria_comboborx = ttk.Combobox(frame, width=37, state='readonly')
    subcategoria_comboborx.set("(Sin subcategoría)")
    subcategoria_comboborx.pack(pady=5)
    
    #Función para actualizar las subcategorías basadasen la categoráis seleccionada
    def actualizar_subcategorías(event):
        #Obtener la categoría seleccionada
        categoria_seleccionada = categoria_comobobox.get()
        
        #S seleccionar "(Sin categoría)" si se selecciona "(Sin categoría)"
        if categoria_seleccionada == "Sin categoría" or categoria_seleccionada == "(Sin categoría)":
            subcategoria_comboborx.config(values=["(Sin subcategoría)"])
            subcategoria_comboborx.set("(Sin subcategoría)")
            return
        
        #Ontener el id de la categoría seleccionada
        categoria_id = None
        for cat_id, cat_data in categorias_map.items():
            if cat_data['name'] == categoria_seleccionada:
                categoria_id = cat_id
                break
        
        if categoria_id is None:
            return
            
        # Obtener las subcategorías de esta categoría
        subcat =[]
        for cat_id, cat_data in categorias_map.items():
            if cat_data['parent'] == categoria_id:
                subcat.append(cat_data['name'])
        
        #Si hay subcategorías, agregalas al combobox
        if subcat:
            subcategoria_comboborx.config(values=['(Sin subcategoría)'] + subcat)
            subcategoria_comboborx.set('(Sin subcategoría)')
        else:
            #Si no hay subcategorías, mostrar "(Sin subcategoría)"
            subcategoria_comboborx.config(values=["(Sin subcategoría)"])
            subcategoria_comboborx.set("(Sin subcategoría)")
    
    #Vincular el evento de selección de categoría al combobox
    categoria_comobobox.bind("<<ComboboxSelected>>", actualizar_subcategorías)
    
    #funcion para iniciar el scrapper
    def iniciar_scraper(url_value, categoria_seleccionada, subcategoria_seleccionada):
        
        global contrasena_superusuario
        
        
        #Actualizar variables globales
        global CATEGORIA_PRINCIPAL, SUBCATEGORIAS, PARENTESIS, driver, scraping,stop_evento
        stop_evento.clear()  # Limpiar el evento de parada
        scraping = True  # Indicar que el scraper está en ejecución
        CATEGORIA_PRINCIPAL = categoria_seleccionada
        SUBCATEGORIAS = subcategoria_seleccionada
       # PARENTESIS = parentesis_var.get()
        
        #Cerrar la ventana modal
        #ventana.after(0, ventana.destroy)
        
        # erinciar para evitar problemas
        pagina_actual = 1  # Reiniciar el número de página actual
        todos_productos = []  # Limpiar la lista de productos
          #Crear un nuevo driver y dirigirse a la URL
        driver = webdriver.Chrome()
        driver.get(url_value)
        #Inciicar el driver y comenzar el screpaing
        while True:
            if not scraping:
                break
            try:
          

            
            # Llamar directamente a la función 
                productos_pagina = scrapear_pagina(driver)
                
            
            # Agregar los producto a la klista global
               
                todos_productos.extend(productos_pagina)
            
              # Verificar si hay siguiente página
                if not pasar_a_siguiente_pagina(driver):
                    print("No hay más páginas disponibles o se alcanzó el final.")
                    break
              
                pagina_actual += 1  # Incrementar el número de página actual
                sleep(3)  # Esperar un poco antes de continuar
                
            
                
            except Exception as e:
                #messagebox.showerror("Error", f"Error al iniciar el scraping: {e}")
                print(f"Error al iniciar el scraping: {e}")
            
            
        # Generar CSV con todos los productos 
        if todos_productos:
            print("\nGenerando archivo CSV final...")
            archivo_final = generar_csv_wordpress(todos_productos)
            if archivo_final:
                print(f"Archivo CSV generado: {archivo_final}")
                #messagebox.showinfo("CSV generado", f"El archivo CSV se ha generado correctamente: {archivo_final}")
            else:
                print("Error al generar el archivo CSV final")
                #messagebox.showinfo("Error", "No se pudo generar el archivo CSV final.")
        driver.quit()
   
   #Método para parar el scraper
    def parar_scraper():
        #Enviar comando a la cola de comandos
        try:
            global scraping, driver, stop_evento
            print("Deteniendo el scraper...")  # Para depuración
            # Premro establecer las banderas para detern la ejecución
            scraping = False
            stop_evento.set()  # Establecer el evento de detención
            cola_que.put("STOP")
            
            # Pequeña pausa par apermitr que los hilos ntone la señal de parada
            sleep(0.5)
            #Cerrar la ventana modal
            if driver:
                try:
                    driver.quit()
                    driver = None  # Limpiar el driver
                    print("Driver cerrado correctamente")
                except Exception as e:
                    print("Error al cerrar el driver: {e}")
            
            #mensaje informativo
            messagebox.showinfo("Scraper detenido", "El scraper se ha detenido correctamente.")
            
           
            
        except Exception as e:
            print(f"Error al detener el scraper: {e}")
            messagebox.showerror("Error", f"Error al detener el scraper: {e}")
    
    def preparar_scraper():
        """Función que pide la contraseña antes de iniciar el scraper"""
        # Obtener valores
        url_value = url.get()
        cat = categoria_comobobox.get()
        subcat = subcategoria_comboborx.get()
        
        # Validar URL
        if not url_value.startswith("https://") and not url_value.startswith("http://"):
            messagebox.showinfo("Error", "La URL debe comenzar con 'https://' o 'http://'")
            return
        
        # Pedir contraseña en el hilo principal
        global contrasena_superusuario
        contrasena_superusuario = simpledialog.askstring("Contraseña", 
                                                       "Introduce tu contraseña de super usuario", 
                                                       show='*')
        
        if not contrasena_superusuario:
            messagebox.showerror("Error", "Se requiere contraseña de superusuario")
            return
        
        # Iniciar el hilo del scraper   
        threading.Thread(target=iniciar_scraper, 
                       args=(url_value, cat, subcat), 
                       daemon=True).start()
    try:        
            #Boton para iniciar el scrapper
            btm_iniciar = ttk.Button(frame, text="Iniciar Scraper", command=lambda: preparar_scraper())
            btm_iniciar.pack(pady=5)
            #Botón para  cancelar la ventana
            btn_cancelar = ttk.Button(frame, text="Cancelar", command= lambda: threading.Thread(  cerrar(ventana), daemon=True).start())
            btn_cancelar.pack(pady=5)
            btn_parar = ttk.Button(frame, text="Parar Scraper", command= lambda: threading.Thread( parar_scraper(), daemon=True).start())
            btn_parar.pack(pady=5)                     
    
            #Acer la ventana modal
            ventana.grab_set()
            ventana.wait_window()  # Esperar a que se cierre la ventana modal
    
    except Exception as e:
            print(f"Error en el hilo del scraper: {e}")
            messagebox.showerror("Error", f"Error en el hilo del scraper: {e}")
            
    
  
    
    
   


#
# Métod para generar el archivo CSV 
# Est archivo contará  una variables
# productos: En este parámetro se encuentra todos los productos que hemos encontrado en la web que hemos scrapeado
# Estos producto están guardado en un array#
def generar_csv_wordpress(productos):
    """
    Generar múltiples CSV compatibles con WordPress,
    limitado cada uno"""
    global contrasena_superusuario
   
    try:
        # si no se introduce la contraseña, se retorna None
        if not contrasena_superusuario:
            messagebox.showerror("Error", "Se requiere contraseña de superusuario para crear directorios y copiar imágenes")
            return None
        #timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        #Nombre del archivo CSV
        nombre_archivo = f"productos_wp_{CATEGORIA_PRINCIPAL}_{SUBCATEGORIAS}.csv"
        
       
        
       #
       # Sistema para reemplazar las tildes y los espacio,
       # lo que hace es coger la categoría y la subcategoría 
       # lee el texto y reemplaza todo lo que es espacios y tildes#
        categoria_segura = CATEGORIA_PRINCIPAL.replace(" ", "_").replace("ó", "o").replace("í", "i").replace("á", "a").replace("é", "e").replace("ú", "u")
        subcategoria_segura = SUBCATEGORIAS.replace(" ", "_").replace("ó", "o").replace("í", "i").replace("á", "a").replace("é", "e").replace("ú", "u")
        
        
        #Obtner ruta absoluta del directorio actual como en la que nos encontramos 
        
        directorio_actual = os.path.dirname(os.path.abspath(__file__))
        #Obtener la ruta de la carpeta de imágenes
        carpeta_imagenes = os.path.join(directorio_actual, 'imagenes')
        #Ruta basde de XAMPP WordPress
        ruta = "/opt/lampp/htdocs/wordpress"
        #Variable para guardar la ruta de las imagenes
        ruta_imagens = f"{ruta}/wp-content/uploads/imagenes_aliexpres/{categoria_segura}/{subcategoria_segura}/"
        #print(f"Ruta de imágenes: creada {ruta_imagens}")
        #messagebox.showinfo("Ruta de imágenes", f"Ruta de imágenes creada: {ruta_imagens}")
        print(f"Ruta de imágenes: {ruta_imagens}")
    
        # Usar la contraseña con sudo -S (leer desde stdin)
        subprocess.run('sudo -S mkdir -p /opt/lampp/htdocs/wordpress/wp-content/uploads/imagenes_aliexpres', shell=True, check=True, input=contrasena_superusuario.encode())
        ruta_escapada = ruta_imagens.replace("(", "\\(").replace(")", "\\)")
        subprocess.run(f'sudo -S mkdir -p {ruta_escapada}', shell=True, check=True, input=contrasena_superusuario.encode())
        
        #os.system(f'sudo mkdir -p /opt/lampp/htdocs/wordpress/wp-content/uploads/imagenes_aliexpres')
        #os.system(f"sudo mkdir -p {ruta_imagens}")
    
        #Los permiso se le dará con nautilos , com oque en ubuntu le daremso permiso total a las carpetas en ubuntu.
      
        
        ##
        # Bucle que copia las imagenes a la carpeta de Wordpres #
        for producto in productos:
            # Verificar si la imagen existe y es válida
            if producto.get('imagen_path') and os.path.exists(producto['imagen_path']):
                # Copiar la imagen a la carpeta de WordPress
                nombre_imagen = os.path.basename(producto['imagen_path'])
                destino_imagen = os.path.join(ruta_imagens, nombre_imagen)
                #Copiar al imagen a la carpeta de wordpress
                os.system(f'sudo cp "{producto["imagen_path"]}" "{destino_imagen}"')
                # Cambiar permisos de la imagen
                os.system(f'sudo chown www-data:www-data "{destino_imagen}"')
                # Cambiar permisos de la imagen 
                os.system(f'sudo chmod 644 "{destino_imagen}"')
                
                #Actualizar la ruta de la imagen en el producto
                #Esto lo que va a hacer en la ruta de la imagen que se entutra el porducot ese ya que no se puede poner una ruta web porque no la lee wordpres
                producto['imagen_wordpress'] = f"http://localhost/wordpress/wp-content/uploads/imagenes_aliexpres/{categoria_segura}/{subcategoria_segura}/{nombre_imagen}"
        #Estructura del CSV de WordPress
        fieldnames = [
           'ID','Tipo','SKU','GTIN, UPC, EAN o ISBN','Nombre','Publicado',
           '¿Está destacado?','Visibilidad en el catálogo','Descripción corta',
           'Descripción','Día en que empieza el precio rebajado',
           'Día en que termina el precio rebajado','Estado del impuesto',
           'Clase de impuesto','¿Existencias?','Inventario',
           'Cantidad de bajo inventario','¿Permitir reservas de productos agotados?',
           '¿Vendido individualmente?','Peso (kg)','Longitud (cm)',
           'Anchura (cm)','Altura (cm)','¿Permitir valoraciones de clientes?',
           'Nota de compra','Precio rebajado','Precio normal','Categorias',
           'Etiquetas','Clase de envío','Imágenes','Límite de descargas',
           'Días de caducidad de la descarga','Superior','Productos agrupados',
           'Ventas dirigidas','Ventas cruzadas','URL externa',
           'Texto del botón','Posición','Marcas'
        ]
        
        #
        # Creación del archivo CSV con todos los parámetos que necesitamos .
        # #
        with open(nombre_archivo, 'w', newline='', encoding='utf-8') as csvfile:
          
        
            #Escribir el CSV
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
             #Escribir la cabecera del CSV
            writer.writeheader()
            
            #
            # Bucle que escibe todos los productos que hemos encontrados #
            for idx, producto in enumerate(productos):
            #Usar la ruta local de la imagen guardada
            #Crear descripción con imagen incrustada
                imagen_path = producto.get('imagen_path', '')
                if imagen_path:
                # Convertir la ruta de la imagen a una URL relativa
                    nombre_imagenes = os.path.basename(imagen_path)
                    ruta_relativa = f"wp-content/uploads/imagenes_aliexpres/{categoria_segura}/{subcategoria_segura}/{nombre_imagenes}"
                else:
                    #Si no hay imagen, usar una ruta vacía
                    ruta_relativa = ''
                    
                    #Copiamos todos los producot en el CSV con la estrucuta que necesita wordpress
                row = {
                        'ID': '',
                        'Tipo': 'simple',
                        'SKU': '',
                        'GTIN, UPC, EAN o ISBN': '',
                        'Nombre': producto.get('titulo', ''),
                        'Publicado': 1,
                        '¿Está destacado?': 0,
                        'Visibilidad en el catálogo': 'visible',
                        'Descripción corta': producto.get('titulo', ''),  # Incluir imagen en la descripción corta
                        'Descripción': producto.get('titulo', ''),        # Incluir imagen en la descripción principal 
                        'Día en que empieza el precio rebajado': '',
                        'Día en que termina el precio rebajado': '',
                        'Estado del impuesto': 'taxable',
                        'Clase de impuesto': '',
                        '¿Existencias?': 1,
                        'Inventario': 100,
                        'Cantidad de bajo inventario': '',
                        '¿Permitir reservas de productos agotados?': 0,
                        '¿Vendido individualmente?': 0,
                        'Peso (kg)': '',
                        'Longitud (cm)': '',
                        'Anchura (cm)': '',
                        'Altura (cm)': '',
                        '¿Permitir valoraciones de clientes?': 1,
                        'Nota de compra': '',
                        'Precio rebajado': '',
                        'Precio normal': producto.get('precio', '').replace('€', '').strip(), #Precio normal en euro 
                        'Categorias': f"{CATEGORIA_PRINCIPAL} > {SUBCATEGORIAS}", #Ruta de la categoría
                        'Etiquetas': '',
                        'Clase de envío': '',
                        'Imágenes': producto.get('imagen_wordpress', ''),  # Usar URL directa de la imagen
                        'Límite de descargas': '',
                        'Días de caducidad de la descarga': '',
                        'Superior': '',
                        'Productos agrupados': '',
                        'Ventas dirigidas': '',
                        'Ventas cruzadas': '',
                        'URL externa': '',
                        'Texto del botón': '',
                        'Posición': 0,
                        'Marcas': ''
                    }
                writer.writerow(row) #Escribir el producto en el CSV
                #Actualizar el contador de productos  
            print(f"Archivo CSV generado: {nombre_archivo}")
            #Retornar el nombre del archivo
        return nombre_archivo
    except Exception as e:
        # Manejo de errores al generar el CSV
        print(f"Error al generar CSV: {e}")
        return None


# Metodo para escrapear la pagina actual
#driver: Es el driver de selenium que se encarga de abrir el navegador y navegar por la web
#scroll_attempts: Número de intentos de scroll
#scroll_pause_time: Tiempo de espera entre cada intento de scroll
#scroll_step: Paso de scroll
def scrapear_pagina(driver, scroll_attempts=200, scroll_pause_time=0, scroll_step=80):
    """
    Método para realizar el scroll en la página actual y extraer los productos.
    """
    #Lista para almacenar productos de la pagina actual
    productos_pagina = []
    
    print("\n" + "="*50)
    print(f"INICIANDO SCRAPING DE LA PÁGINA {pagina_actual}")
    print("="*50 + "\n")
     #Obtener el html de la página 
     
   
    
   
    #Iniciar el scroll desde el principio de la página
    current_scroll_attempts = 0
    #Obtener la altura inicial de la página
    last_height = driver.execute_script("return document.body.scrollHeight")
   
    #
    # Mientras que el scroll no alla llegado al limite de intento del scroll
    # no se realiza el scroll
    
    while current_scroll_attempts < scroll_attempts:
        #Posicion inicial del scroll
        current_scroll_position = 0

        # Ekecitañ eñ scroll en pequeños pasos como poco a poco 
        while current_scroll_position < last_height:
            #Desplazarse en la página 
            current_scroll_position += scroll_step
            #Ejecutar el scroll
            driver.execute_script(f"window.scrollTo(0, {current_scroll_position});")
            #sleep(scroll_pause_time)
            
            #Verificar si el botón "Siguiente" es visible
            try:
                #Obtener el la bariable el boton Siguente
                #Esto es un comando xpad que estaba en la página de la web, como que si cambia esto no funciona 
                next_button = driver.find_element(By.XPATH, '//li[contains(@class, "comet-pagination-next") and @aria-disabled="false"]')
                #Ejecutar el scroll hasta el botón "Siguiente"
                #Esto es para que el scroll se detenga cuando el botón siguiente se encuentre en la pantalla
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
               # print("Botón 'Siguiente' encontrado durante el scroll.")
               # return  # Detener el scroll si se encuentra el botón
            except:
               # print("No se encontró el botón 'Siguiente' durante el scroll.")
                pass

        new_height = driver.execute_script("return document.body.scrollHeight")
        #Si la pagian a llebado al final y no se han cargado más productos
        if new_height == last_height:
            #Hacer un último intento de espera para asegurar que todo se cargó
            sleep(1)
            final_height = driver.execute_script("return document.body.scrollHeight")
            
            if final_height == last_height:
                print("No se cargaron más productos. Finalizando scroll.")
                break
            else:
                # Si la altura cambió después de esperar, continuar scrolling
                last_height = final_height

        last_height = new_height
        current_scroll_attempts += 1
        print(f"Intento de scroll {current_scroll_attempts}: Altura actual = {last_height}")

    sleep(2)  # Esperar a que se carguen los productos
    # Verificar cuántos producotos hay en la página
    tree = html.fromstring(driver.page_source)
    soup = BeautifulSoup(driver.page_source, 'html.parser')  # Crear objeto BeautifulSoup
    
    #Intentar direrentes selectores hasta encotriar productos
    products = []
    # 1. Intentar con XPath
    xpath_selectors = [
        '//div[contains(@class,"manhattan--container")]',
    '//div[contains(@class,"search-item-card-wrapper-gallery")]',
    '//div[contains(@class,"JIIxO")]//div[contains(@class,"manhattan--container")]',
    '//div[contains(@class,"list--gallery")]//div[contains(@class,"gallery--galleryWrapper")]'
    ]
    
    for selector in xpath_selectors:
        products = tree.xpath(selector)
        if products:
            print(f"Encontrados {len(products)} productos con selector XPath: {selector}")
            break
    
    # 2. Si no se encontraron productos con XPath, intentar con BeautifulSoup
    if not products:
        soup_selectors = [
       'div.list--gallery a.multi--container',
        'div.JIIxO a.multi--container',
        'div.SearchProductFeed--gallery',
        'div.card-container'
        ]
        
        for selector in soup_selectors:
            products = soup.select(selector)
            if products:
                print(f"Encontrados {len(products)} productos con selector BeautifulSoup: {selector}")
                break
    
    if not products:
        print("No se encontraron productos con ningún selector")
        products = []  # Asegurar que products sea una lista vacía si no se encuentra nada  
        
    #Muestro el prodccto de la pagina actual
    for idx, product in enumerate(products, 1):
        try:

            #ID automatico que le doy para saber cuantos porducot se ha obtenido de la página.
              print(f"\nProducto {idx}:")
              
              # Obtener el HTML del producto actual
              producto_soup = BeautifulSoup(driver.page_source, 'html.parser')
            
           
            
            # Obtener título
              title = product.xpath('.//h3/text()')
              title = title[0].strip() if title else "N/A"
              print(f"Título = {title}")
                              
            # Obtener solo el texto del precio
              #precio_spans = product.xpath('.//div[contains(@class, "l5_k6")]//span/text()')
              precio_spans = product.xpath('.//div[contains(@class, "lj_k1")]/span/text()')
              
              if not precio_spans:
                  precio_spans = product.xpath('.//div[contains(@class, "kr_kj")]/span/text()')
              precio = ''.join(precio_spans) if precio_spans else "N/A"
              print(f"Precio = {precio}")
                 
              
             #Conseguir la imagen del porducto
              #image = product.xpath('.//img[@class="kc_cs product-img")]/@src')
              image = product.xpath('.//img[contains(@class, "kc_cs") and contains(@class, "product-img")]/@src')
             
              if not image:
                image = product.xpath('.//img[class= "kc_cs product-img"]/@src')
            
              if not image:
                  image = product.xpath('.//img[contains(@class, "multi--img")]/@src')
           
              if not image:
                  image = product.xpath('.//div[contains(@class, "kc_jx kc_kt")]/img/@src')
   
              if not image:
                    image = product.xpath('.//div[contains(@class, "kc_ko")]/div/a/div/img/@src')
           
              if not image:
                    image = product.xpath('/html/body/div[2]/div[1]/div/div/div[2]/div/div[2]/div/div/a/div[1]/img/@src')
           
              if not image:
                  image = product.xpath('.//img/@src')
            
              #Obtenenr url del la imagen
              imagen_url = image[0] if image else None
              if imagen_url:
                  if imagen_url.startswith('//'):
                      imagen_url = 'https:' + imagen_url
                  ruta_guardado = descargar_imagen(imagen_url, idx, title, pagina_actual)
                  print(f"Imagen = {imagen_url}")
                  print(f"Imagen guardada en: {ruta_guardado}")
              else:
                  print("No se encontró URL de imagen")
        
       
           
            
           
          #Guardar dato del producto en un array 
              producto_data = {
              'titulo': title,
              'precio': precio,
              'imagen_url': imagen_url,
              'imagen_path': ruta_guardado if ruta_guardado else ''
          }
              #Guardar el producto en la lista de productos de la página
              productos_pagina.append(producto_data)
            
         # Excepciones para errores
        except Exception as e:
            print(f"{idx}. [Error al obtener título]") #Mensaje de error si no se encuentra el título
            print(f"Precio: [Error al obtener precio]") #Mensaje de error si no se encuentra el precio
            print(f"Precio: [Error al obtener precio] - {e}") #Mensaje de error si no se encuentra el precio
            print(f"\nError en Producto {idx}:") #Mensaje de error si no se encuentra el producto
            print(f"Tipo de error: {type(e).__name__}")
            print(f"Mensaje de error: {str(e)}")
            print(f"Línea del error: {e.__traceback__.tb_lineno}")
            print(f"Error al obtener imagen del producto: {e}")#Mensaje de error si no se encuentra la imagen
            print(f" Error de porductos acumulados: {e}") #Mensaje de error si no se encuentra el producto
            print("-" * 50)
    # Mostrar resumen de la página con todos los productos encontrados
    num_products = len(products)
    print("\n" + "-"*50)
    print(f"RESUMEN PÁGINA {pagina_actual}:")
    print(f"Total de productos encontrados: {len(productos_pagina)}")
    print("-"*50 + "\n")
    
  #Retornar la lista de productos de la página actual
    return productos_pagina
# Llamar a la función para scrapear la página actual
# Esperar a que se cargue la página actual
#Método para convertir la imagen a JPG
def convertir_a_jpg(image_buffer):
    """
    Convierte una imagen desde cualquier formato a JPG usnado memoria RAM.
    Retorna un objeto ByesIO con la imagen convertida
    """
    try:
        #Importar soporte para AVIF si es necesario
        from pillow_avif import register_avif_opener
        register_avif_opener()
        #Crear un buffer de memoria para la imagne convretida
        output_buffer = io.BytesIO()
        
        #Abrir la imagne dede los datos en meoria
        with Image.open (image_buffer) as img:
            #Forzar carga de la imagen
            img.load()
            
            #Convertir a RGB si es necesario
            if img.mode in ('RGBA', 'P', 'LA', 'CMYK', 'RGBA;8'):
                img = img.convert('RGB')
            
            #Guardar como JPG en el buffer de memoria
            img.save(output_buffer, format='JPEG', quality=95, optimize=True)
        
        #Regresar al inicio del buffer
        output_buffer.seek(0)
        return output_buffer
    except Exception as e:
        print(f"Error en la conversión: {e}")
        #Intentar método alternativo
        try:
            from PIL import ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            
            with Image.open(image_buffer) as img:
                img = img.convert('RGB')
                output_buffer = io.BytesIO()
                img.save(output_buffer, format='JPEG', quality=25, optimize=True)
                output_buffer.seek(0)
                return output_buffer
        except Exception as e2:
            print(f"Error en método alternativo: {e2}")
            return None
        return None
#Método para guardar la imagen del producto
def descargar_imagen(url, producto_id, titulo, pagina_actual):
  """
  Descargar una imagen y la convierte a JPG antes de guardarla"""
  try:
      carpeta_imagenes = Path('imagenes')
      carpeta_imagenes.mkdir(exist_ok=True)
      
      formato_nombre = f"{pagina_actual}-{producto_id}"
      
      headers = {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
          'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
      }
      
      response = requests.get(url, headers=headers, stream=True)
      if response.status_code == 200:
          #Crear buffer con la imagen descargada
          image_buffer = io.BytesIO(response.content)
          
          #Converti a JPG
          jpg_buffer = convertir_a_jpg(image_buffer)
          
          if jpg_buffer:
              # Guardar el JPG convertido 
              ruta_completa = carpeta_imagenes / f"{formato_nombre}.jpg"
              with open(str(ruta_completa), 'wb') as f:
                  f.write(jpg_buffer.getvalue())
              print(f"Imagen convertida y guardada exitosamente en: {ruta_completa}")
              return str(ruta_completa)
          else:
              print("Error en la conversión de la imagen")
              return None
      else:
          print(f"Error al descargar la imagen: {response.status_code}")
          return None
          
  except Exception as e:
      print(f"Error general: {e}")
      return None



#Método para pasar a la siguiente página
def pasar_a_siguiente_pagina(driver):
    try:
        # Esperar a que el botón "Siguiente" esté disponible y hacer clic en él
        next_button = WebDriverWait(driver, 10).until(
            #EC.element_to_be_clickable((By.XPATH, '//a[contains(@class, "next-pagination-item") and not(contains(@class, "next-pagination-disabled"))]'))
            EC.presence_of_element_located((By.XPATH, '//li[contains(@class, "comet-pagination-next") and @aria-disabled="false"]'))
            #EC.element_to_be_clickable((By.XPATH, '//button[contains(@class="next-pagination-item-link")]'))    
        )
       
        #Encontrar el botón dentro del <li>
   # Encontrar el botón dentro del li
        next_button = next_button.find_element(By.TAG_NAME, 'button')
        
        # Asegurarse de que el botón es visible
        driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
        sleep(1)
        
        # Intentar diferentes métodos de clic
        try:
            next_button.click()
        except:
            try:
                driver.execute_script("arguments[0].click();", next_button)
            except:
                # Si los otros métodos fallan, usar Actions
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(driver)
                actions.move_to_element(next_button).click().perform()
        
        print("Pasando a la siguiente página...")
        sleep(3)  # Esperar a que la nueva página cargue
        
        return True
        
    
 
    except Exception as e:
        print(f"Error al pasar de página: {str(e)}")
        return False  # Si los otros métodos fallan, usar Actions


# Inicializar el contador
def main(cancelado=None):
    #variables globales para almacenar la categoría principal, subcategorías, paréntesis y el driver de Selenium
    global CATEGORIA_PRINCIPAL, SUBCATEGORIAS, PARENTESIS, driver, todos_productos 
    
   # Iniciar el entorno gráfico para configurar el scrapper
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal

    #varibels de control par ale screping    
    todos_productos = []
    
    #Mostrar la ventana de configuración
    entorno_grafico()
    
    #El resto del proceso se maneja dentro de entorno_grafico()
    
    #Una vez que se cierra entorno_grafico, cerramos la aplicación Tkinter
    root.destroy()
    
    

if __name__ == "__main__":
    main()
