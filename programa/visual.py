import csv
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import filedialog
from PIL import Image, ImageTk
import mysql.connector
import os
import subprocess
import sys
import datetime
import shutil
import scrape5 
import threading

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

def obtener_productos():
    """Función para obtener todos los productos de la base de datos"""
    conexion = conectar_bd()
    if conexion:
        try:
            cursor = conexion.cursor()
            sql = """
            SELECT 
                p.ID,
                p.post_title AS Nombre,
                pm_precio.meta_value AS Precio,
                pm_stock.meta_value AS Stock,
                GROUP_CONCAT(DISTINCT t.name) AS Categorias
            FROM wp_posts p
            LEFT JOIN wp_postmeta pm_precio ON p.ID = pm_precio.post_id 
                AND pm_precio.meta_key = '_regular_price'
            LEFT JOIN wp_postmeta pm_stock ON p.ID = pm_stock.post_id 
                AND pm_stock.meta_key = '_stock'
            LEFT JOIN wp_term_relationships tr ON p.ID = tr.object_id
            LEFT JOIN wp_term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id 
            LEFT JOIN wp_terms t ON tt.term_id = t.term_id
            WHERE p.post_type = 'product' AND p.post_status = 'publish'
            GROUP BY p.ID
            """
            cursor.execute(sql)
            productos = cursor.fetchall()
            return productos
        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"Error al obtener productos: {err}")
            return None
        finally:
            conexion.close()

def crear_tabla(ventana):
    """Función para crear la tabla de productos"""
    # Crear frame para la tabla
    frame = ttk.Frame(ventana)
    frame.pack(expand=True, fill='both', padx=10, pady=10)

    # Crear tabla
    columnas = ('ID', 'Nombre', 'Precio', 'Stock', 'Categorias')
    tabla = ttk.Treeview(frame, columns=columnas, show='headings')

    # Configurar columnas
    for col in columnas:
        tabla.heading(col, text=col)
        if col == 'ID':
            tabla.column(col, width=50)
        elif col == 'Nombre':
            tabla.column(col, width=300)
        else:
            tabla.column(col, width=100)

    # Añadir scrollbar
    scrollbar = ttk.Scrollbar(frame, orient='vertical', command=tabla.yview)
    tabla.configure(yscrollcommand=scrollbar.set)

    # Empaquetar elementos
    tabla.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')

    return tabla

def cargar_datos_tabla(tabla, productos):
    """Función para cargar los datos en la tabla"""
    # Limpiar tabla
    for item in tabla.get_children():
        tabla.delete(item)

    # Insertar nuevos datos
    for producto in productos:
        tabla.insert('', 'end', values=(
            producto[0],  # ID
            producto[1],  # Nombre
            f"€{producto[2]}" if producto[2] else "N/A",  # Precio
            producto[3] if producto[3] else "N/A",  # Stock
            producto[4] if producto[4] else "Sin categoría"  # Categorías
        ))

# Función para poder modificar los porductos 
def modificar_producto(tabla):
    """Función para modificar un producto seleccionado"""
    #1 Verificar si hay un producto seleccionado
    seleccion = tabla.selection()
    if not seleccion:
        messagebox.showwarning("Advertencia", "Seleccione un producto para modificar.")
        return
    #2 Obtener datos el producto seleccionado
    producto = tabla.item(seleccion[0])['values']
    
    #3 Crear ventana de modificación
    ventana_modificar = tk.Toplevel()
    ventana_modificar.title("Modificar Producto")
    ventana_modificar.geometry("400x300")
    
    #4 Crear campos para editar
    ttk.Label(ventana_modificar, text="ID:").pack(pady=5)
    id_entry = ttk.Entry(ventana_modificar)
    id_entry.insert(0, producto[0])
    id_entry.config(state='readonly') #El ID no se puede modificar
    id_entry.pack(pady=5)
    
    ttk.Label(ventana_modificar, text="Nombre:").pack(pady=5)
    nombre_entry = ttk.Entry(ventana_modificar)
    nombre_entry.insert(0, producto[1])
    nombre_entry.pack(pady=5)
    
    ttk.Label(ventana_modificar, text="Precio:").pack(pady=5)
    precio_entry = ttk.Entry(ventana_modificar) #
    precio_entry.insert(0, producto[2])
    precio_entry.pack(pady=5)
    
    ttk.Label(ventana_modificar, text="Stock:").pack(pady=5)
    stock_entry = ttk.Entry(ventana_modificar)
    stock_entry.insert(0, producto[3])
    stock_entry.pack(pady=5)
    
    #5 Función para guardar cambios
    def guardar_cambios():
        """Función para guardar los cambios realizados en el producto"""
        id_producto = id_entry.get()
        nombre = nombre_entry.get()
        precio = precio_entry.get().replace('€', '').strip()  # Eliminar el símbolo € y espacios en blanco de el precio
        stock = stock_entry.get()

        # Validar campos
        if not nombre or not precio or not stock:
            messagebox.showwarning("Advertencia", "Todos los campos son obligatorios.")
            return

        # Actualizar producto en la base de datos
        conexion = conectar_bd()
        if conexion:
            try:
                #Conexión a la base de datos
                cursor = conexion.cursor()
                #Actualizar nombre
                sql = """
                UPDATE wp_posts 
                SET post_title = %s 
                WHERE ID = %s
                """
                cursor.execute(sql, (nombre, id_producto))
                #Actualizar precio
                sql_meta = """
                UPDATE wp_postmeta 
                SET meta_value = %s 
                WHERE post_id = %s AND meta_key = '_regular_price'
                """
                cursor.execute(sql_meta, (precio, id_producto))
                
                #Actualizar también el campo _price
                sql_meta = """
                UPDATE wp_postmeta
                SET meta_value = %s
                WHERE post_id = %s AND meta_key = '_price'
                """
                cursor.execute(sql_meta, (precio, id_producto))
                
                #Actualizar stock
                sql_meta = """
                UPDATE wp_postmeta
                SET meta_value = %s
                WHERE post_id = %s AND meta_key = '_stock'
                """
                cursor.execute(sql_meta, (stock, id_producto))
                
                conexion.commit()
                messagebox.showinfo("Éxito", "Producto modificado correctamente.")
            except mysql.connector.Error as err:
                messagebox.showerror("Error", f"Error al modificar producto: {err}")
            finally:
                conexion.close()
        
        ventana_modificar.destroy()
    #6 Botón para guardar cambios
    ttk.Button(ventana_modificar, text="Guardar Cambios", command=guardar_cambios).pack(pady=10)

#Funcion para poder buscar los porductos
def buscar_productos(tabla):
    """Función para buscar porductos con filtros"""
    
    #Crear ventana para la busqueda de porductos
    ventana_buscar = tk.Toplevel()
    ventana_buscar.title("Buscar Productos")
    ventana_buscar.geometry("400x300")
    
    #Crear frame para los criterios de busqueda
    frame_busqueda = ttk.Frame(ventana_buscar, padding='10')
    frame_busqueda.pack(expand=True, fill='both')
    
    #Crear combobox para seleccionar el tipo de búsuqed
    ttk.Label(frame_busqueda, text="Buscar por:").pack(pady=5)
    tipo_busqueda = ttk.Combobox(frame_busqueda, values=["Nombre", "Precio", "Stock", "Categorias"], state='readonly')
    
    #Seleccionar el tipo de busqueda
    tipo_busqueda.set("Nombre")
    tipo_busqueda.pack(pady=5)
    
    #Crear campo de entrada para el valor de busqueda
    ttk.Label(frame_busqueda, text="Valor:").pack(pady=5)
    valor_entry = ttk.Entry(frame_busqueda)
    valor_entry.pack(pady=5)
    #Crear frame para los botones
    def ejecutar_busqueda():
        tipo = tipo_busqueda.get() #Obtener el tipo de busqueda
        valor = valor_entry.get() #Obtener el valor de busqueda
        
        #Validar el tipo de busqueda
        if not valor:
            messagebox.showwarning("Advertencia", "Ingrese un valor para buscar")
            return
        
        #Construir consulta SQL según el tipo de busqueda
        sql = """
        SELECT 
            p.ID,
            p.post_title AS Nombre,
            pm_precio.meta_value AS Precio,
            pm_stock.meta_value AS Stock,
            GROUP_CONCAT(DISTINCT t.name) AS Categorias
        FROM wp_posts p
        LEFT JOIN wp_postmeta pm_precio ON p.ID = pm_precio.post_id 
            AND pm_precio.meta_key = '_regular_price'
        LEFT JOIN wp_postmeta pm_stock ON p.ID = pm_stock.post_id 
            AND pm_stock.meta_key = '_stock'
        LEFT JOIN wp_term_relationships tr ON p.ID = tr.object_id
        LEFT JOIN wp_term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id 
        LEFT JOIN wp_terms t ON tt.term_id = t.term_id
        WHERE p.post_type = 'product' AND p.post_status = 'publish'
        """
        # si el tipo de busqueda es un nombre
        # se agrega la condicion a la consulta SQL
        if tipo == "Nombre":
            sql += " AND p.post_title LIKE %s"
            param = f"%{valor}%"
        # si el tipo de busqueda es un precio
        # se agrega la condicion a la consulta SQL
        elif tipo == "Precio":
            sql += " AND pm_precio.meta_value = %s"
            param = valor
        # si el tipo de busqueda es un stock
        # se agrega la condicion a la consulta SQL
        elif tipo == "Stock":
            sql += " AND pm_stock.meta_value = %s"
            param = valor
        # si el tipo de busqueda es una categoria
        # se agrega la condicion a la consulta SQL
        elif tipo == "Categorias":
            sql += " AND t.name LIKE %s"
            param = f"%{valor}%"
        # sql grupo por ID
        sql += " GROUP BY p.ID"
        
        #Ejecutar la consulta SQL
        conexion = conectar_bd() #Conexión a la base de datos
        #si la conexion es correcta
        if conexion:
            try:
                #Cursor para ejecutar la consulta
                cursor = conexion.cursor()
                #Ejecutar la consulta con el parametro de busqueda
                cursor.execute(sql, (param,))
                #Obtener los resultados
                productos = cursor.fetchall()
                
                #Limpiar la tabla
                for item in tabla.get_children():
                    tabla.delete(item)
                
                #Cargar los datos en la tabla
                for producto in productos:
                    tabla.insert('', 'end', values=(
                        producto[0],  # ID
                        producto[1],  # Nombre
                        f"€{producto[2]}" if producto[2] else "N/A",  # Precio
                        producto[3] if producto[3] else "N/A",  # Stock
                        producto[4] if producto[4] else "Sin categoría"  # Categorías
                    ))
            except mysql.connector.Error as err:
                messagebox.showerror("Error", f"Error al buscar productos: {err}")
            finally:
                conexion.close()
        # Botones
        #Boton para cerrar la ventana de busqueda
    #Botones para la busqueda
    
    frame_botones = ttk.Frame(frame_busqueda)
        #boton paddy = 20
    frame_botones.pack(pady=20)
        #Boton para cerrar la ventana de busqueda
    ttk.Button(frame_botones, text="Buscar", 
                   command=ejecutar_busqueda).pack(side='left', padx=5)
         #Boton para cancelar la ventana de la busqueda
    ttk.Button(frame_botones, text="Cancelar", 
                   command=ventana_buscar.destroy).pack(side='left', padx=5)

# Obtener una lista de la categorías de Wordpress
def obtener_categorias_wp():
    
    conexion = conectar_bd()
    if not conexion:
        messagebox.showerror("Error Conexión", "No se pudo conectar a la base de datos para cargar categorías.")
        return ["(Sin categoría)"], {}
    else:
        try:
            cursor = conexion.cursor(dictionary=True) # Use dictionary=True for easy column access by name
            
            # Consulta SQL para obtener categorías y subcategorías
            sql = """
                SELECT t.term_id, t.name, tt.parent, tt.term_taxonomy_id
                FROM wp_terms AS t
                INNER JOIN wp_term_taxonomy AS tt ON t.term_id = tt.term_id
                WHERE tt.taxonomy = 'product_cat'
                ORDER BY tt.parent, t.name;
            """
            cursor.execute(sql) # Execute el cursor con la consulta SQL
            categorias = cursor.fetchall() # Obtener todas las categorías
            # Crear un diccionario para almacenar las categorías y sus subcategorías
            categorias_dict = {}
            
            #Crear lista para almacenar las categorías
            categorias_list = ['(Sin categoría)']
            # Crear una lista para almacenar las categorías
            for categoria in categorias:
                categorias_dict[categoria['term_id']] = {
                    'name': categoria['name'],
                    'parent': categoria['parent'],
                    'term_taxonomy_id': categoria['term_taxonomy_id'],
                    'children': []
                }
            # Ahora que todas las categorías estan creadas, agregar las relaciones padre-hijo
            for categoria_id, categoria_data in categorias_dict.items():
                if categoria_data['parent'] == 0:  # Es una categoría principal
                    categorias_list.append(categoria_data['name'])
            return categorias_list, categorias_dict
               
                                               
            
            
        except mysql.connector.Error as err:
            messagebox.showerror("Error Categorías", f"Error al obtener categorías de WordPress: {err}")
        finally:
            if conexion and conexion.is_connected():
                if 'cursor' in locals() and cursor:
                    cursor.close()
                conexion.close()  
    return ['(Sin categiría)'], {}  # En caso de error, devolver listas vacías 
# Método para obtener subcategorías de Wordpress
def obtener_subcategorias_wp():
    conexion = conectar_bd()
    if not conexion:
        messagebox.showerror("Error Conexión", "No se pudo conectar a la base de datos para cargar subcategorías.")
        return ['(Sin subcategoría)'], {}
    else:
        try:
            cursor = conexion.cursor(dictionary=True) # Use dictionary=True for easy column access by name
            
            # Consulta SQL para obtener subcategorías
            sql = """
                SELECT t.term_id, t.name, tt.parent, tt.term_taxonomy_id, 
                parent.name AS parent_name
                FROM wp_terms AS t
                INNER JOIN wp_term_taxonomy AS tt ON t.term_id = tt.term_id
                LEFT JOIN wp_terms AS parent ON tt.parent = parent.term_id
                WHERE tt.taxonomy = 'product_cat' AND tt.parent != 0
                ORDER BY tt.parent, t.name;
            """
            cursor.execute(sql) # Execute el cursor con la consulta SQL
            subcategorias = cursor.fetchall() # Obtener todas las subcategorías
            # Crear un diccionario para almacenar las subcategorías
            subcategorias_dict = {}
            subcategorias_list = ['Sin subcategoría']
            for subcategoria in subcategorias:
                subcategorias_dict[subcategoria['term_id']] = subcategoria
                #Añadir a la lista de visualizacion con formatao Categoria > subcategoría
                parent_name = subcategoria['parent_name'] if subcategoria['parent_name'] else "Desconocido"
                display_name = f"{subcategoria['name']}"
                subcategorias_list.append(display_name)
           
            
            return subcategorias_list, subcategorias_dict
        except mysql.connector.Error as err:
            messagebox.showerror("Error Categorías", f"Error al obtener subcategorías de WordPress: {err}")
        finally:
            if conexion and conexion.is_connected():
                if 'cursor' in locals() and cursor:
                    cursor.close()
                conexion.close()  
    return ['(Sin subcategoría)'], {}  # En caso de error, devolver listas vacías  

#Método para verificar y gestionar las imagenes
# Este métoddo se encarga de verficar si la imagne existen en el servidor
# ya que si no lo esta, causa problemas al importar la imagne y no se muestra
# por eso esot se engarga de verificar si la imagen existe en el servidor
def verificar_imagen_wordpress(ruta_imagen):
    """
    Verifica si una imagen está dentro del directorio de WordPress.
    Si no lo está, pregunta al usuario si desea copiarla.
    
    Args:
        ruta_imagen (str): Ruta completa de la imagen
    
    Returns:
        tuple: (nueva_ruta, ruta_relativa) donde nueva_ruta es la ruta actualizada
               y ruta_relativa es la ruta relativa para WordPress
    """
    # Directorio base de uploads de WordPress
    wp_uploads_dir = "/opt/lampp/htdocs/wordpress/wp-content/uploads"
    
    # Verificar si la imagen ya está en el directorio de WordPress
    if wp_uploads_dir in ruta_imagen:
        # Ya está en WordPress, solo extraer la ruta relativa
        ruta_relativa = ruta_imagen.replace(wp_uploads_dir + '/', '')
        return ruta_imagen, ruta_relativa
    
    # La imagen está fuera de WordPress, preguntar si desea importarla
    respuesta = messagebox.askyesno(
        "Imagen externa", 
        "La imagen seleccionada no está en el directorio de WordPress.\n"
        "¿Desea copiarla al directorio de uploads de WordPress?"
    )
    # si la respuesta es afirmativa
    if respuesta:
        
        # Crear estrcutura de directorios por año y mes
        año_actual = datetime.datetime.now().strftime("%Y")
        mes_actual = datetime.datetime.now().strftime("%m")
        
        # Direcctorio para productos importados manualmente
        directorio_destino = f"/opt/lampp/htdocs/wordpress/wp-content/uploads/importados-manuales/{año_actual}/{mes_actual}"
        
        #Crear directorio si no existe
        if not os.path.exists(directorio_destino):
            os.makedirs(directorio_destino)
        
        #Copiar la imagen en el directorio de WordPress
        nombre_imagen = os.path.basename(ruta_imagen)
        nueva_ruta = f"{directorio_destino}/{nombre_imagen}"
        
        try:
            # Copiar la imagen al nuevo directorio
            shutil.copy2(ruta_imagen, nueva_ruta)
            
            # Establecer permisos de lectura y escritura para el nuevo archivo
            os.chmod(nueva_ruta, 0o666)
            
            # Crear la ruta relativa para WordPress
            ruta_relativa = nueva_ruta.replace('/opt/lampp/htdocs/wordpress/wp-content/uploads/importados-manuales/', '')
            
            # Mostrar mensaje de éxito al importar la imagen
            messagebox.showinfo("Éxito", f"Imagen importada con éxito: {nueva_ruta}")
            
            return nueva_ruta, ruta_relativa
        except Exception as e:
            messagebox.showerror("Error", f"Error al copiar la imagen: {e}")
            return None, None
    else:
        # Si el usuario no desea copiar la imagen, devolver None
        messagebox.showinfo("Advertencia", "La imagen no será visible en WordPress porque no se ha copiado.")
        return None, None
        
#Método para importar porductos 
def importar_productos(tabla):
    """Función para importar productos desde CSV o manual
     Crea una ventana pra iportar porducot dos formas
     1. Desde un archivo CSV
     2. Manualmente mediante un formulario
    
    """
    #Crear ventana para importar porductos
    ventana_importar = tk.Toplevel()
    ventana_importar.title("Importar Productos")
    ventana_importar.geometry("400x200")
    
    #Método para importar porductos desde un archivo CSV
    def importar_csv():
        """Función para importar productos desde archivo CSV
        
         El porceso realiza lo siguiente:
         1. El usuario seleciona un archivo CSV:
         2. El archivo se lee línea por línea
         3. Cada linea representa un porducot con atributos: Nombre, precio, Stcok, categoria, imagen...
         4. Se inserta el porducto en la tabla 'wp_posts' como tipo 'product'
         5. Se inserta metadaso en 'wp_postmeta' para el porducto
         6. Se vincula a categorías y subcategorías en 'wp_term_relationships'
         7. Se guarda imagen destacada porducto en 'wp_posts' como 'attachment'
         8. Se actualiza visualmente una tabla en la interfaz gráfica
        """
        #Mostrar ventana para seleccionar archivo CSV
        archivo_csv = filedialog.askopenfilename(
            title="Seleccionar archivo CSV",
            filetypes=[("CSV files", "*.csv")]
        )
    
        #Si no se selecciona el archivo, se cancela la operación
        if not archivo_csv:
            return
        
        try:
            #Conexión con la base de datos
            conexion = conectar_bd()
            if conexion:
                cursor = conexion.cursor()
                productos_importados = 0 # Contador de filas importadas
            
                # Abrir y leer el archivo CSV
                with open(archivo_csv, 'r', encoding='utf-8') as csvfile:
                    # Usar DictReader en lugar de reader
                    # Leer el archivo usando encabezados
                    reader = csv.DictReader(csvfile) 
                
                    # Leer cada fila del archivo CSV
                    for row in reader:
                        try:
                            # Obtener valores usando nombres de columnas
                            nombre = row.get('Nombre', '') # Nombre del producto
                            
                            #Intentar obtener la descripción y descripcion corta del csv
                            descripcion = row.get("Descripción", ' Descripción detallada del porducto') # Descripción del producto
                            descripcion_corta = row.get("Descripción corta", '') # Descripción corta del producto
                            
                            precio = row.get('Precio normal', '') # Precio del producto
                            stock = row.get('Inventario', '') # Stock del producto
                            categoria = row.get('Categorias', '') # Categoría del producto
                            imagen = row.get('Imágenes', '') # Imagen del producto

                            # Si no hay nombre, saltamos esta fila
                            if not nombre:  
                                continue
                            
                            # Limpiar caracteres como € y espacios
                            precio = precio.replace('€', '').strip()
                            stock = stock.strip()
                        
                        # Insertar producto como entrad de tipo 'product'
                            sql = """
                        INSERT INTO wp_posts (
                            post_title,      #Titulo visible del porducto 
                            post_type,      # Tipo de entrada ('product' para WooCommerce)
                            post_status,    # Estado de publicacion ('publish' para publicar inmediatamente el producto)
                            post_content,   # Descripción larga del porducto
                            post_excerpt,   # Descripción corta del porducto
                            to_ping,        # Para pingear el producto
                            pinged,         # Para pingear el producto
                            post_content_filtered,  # Para filtrar el producto
                            post_date,      # Fecha de creación del producto
                            post_date_gmt,  # Fecha de creación del producto en formato GMT
                            post_modified,  # Fecha de modificación del producto
                            post_modified_gmt,  # Fecha de modificación del producto en formato GMT
                            post_name,           # Slug para la URL
                            guid,                # URL única del producto
                            comment_status,      # Estado de comentarios
                            ping_status ,         # Estado de ping
                            menu_order,           # Orden de menú
                            post_password         # Contraseña del producto
                            )VALUES (
                            %s,                  # nombre
                            'product',           # tipo
                            'publish',           # estado
                            %s,                  # descripcion
                            %s,                  # excerpt
                            '',                  #to_ping
                            '',                  #pinged
                            %s,                  #filtered
                            NOW(),               # fecha
                            NOW(),               # fecha GMT
                            NOW(),               # modificado
                            NOW(),               # modificado GMT
                             %s,                # slug
                             %s,                # guid
                            'open',             # comment_status
                            'closed',             # ping_status
                            '0',                # menu_order
                            ''                  # post_password
                            )
                            """
                            #Generar el slug y guid
                            # Convierte el nombre del prducto a minúsculas
                            tem_slug = nombre.lower()
                            #Reemplazar acentos comunes (puedes expandir esta lista)
                            replacements = {
                                'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n',
                                'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u'
                            }
                            # Bucle que reemplaza los caracteres acentuados por los no acentuados
                            for acented_char, unaccented_char in replacements.items():
                                tem_slug = tem_slug.replace(acented_char, unaccented_char)
                            
                            # Sustituye espacios y caracteres especiales por guiones para generar el slug y que no haya problemas con la URL
                            nombre_slug = tem_slug.lower().replace(' ', '-').replace('/', '-').replace('(', '').replace(')', '')
                            
                            #Eliminar caracteres no alfanuméricos excepto guiones
                            nombre_slug = ''.join(c for c in nombre_slug if c.isalnum() or c == '-')
                            #Eliminar múltiples guiones seguidos
                            while '--' in nombre_slug:
                                nombre_slug = nombre_slug.replace('--', '-')
                            nombre_slug = nombre_slug.strip('-')  # Eliminar guiones al inicio y al final
                            # Crear la URL única del producto
                            guid = f"http://localhost/wordpress/?product={nombre_slug}"
                          
                            
                            cursor.execute(sql, (nombre, descripcion,descripcion_corta,'', nombre_slug, guid))
                            # Obtener el ID del producto insertado
                            producto_id = cursor.lastrowid # Id generado del producto
                        
                            # Insertar metadatos esenciales de WooCommerce

                            sql_meta_woocommerce = """
                                INSERT INTO wp_postmeta (post_id, meta_key, meta_value)
                                VALUES
                                (%s, '_product_type', 'simple'),  # Tipo de porducto (simple para WooCommerce)
                                (%s, '_visibility', 'visible'),   # El porducto será visible en la tienda 
                                (%s, '_stock_status', 'instock'), # Estado del inventario: en stock
                                (%s, '_regular_price', %s),       # Precio normal (sin descuento)
                                (%s, '_price', %s),               # Precio actual (con descuento si aplica)
                                (%s, '_manage_stock', 'yes'),     # WooCommerce gestionará el stock
                                (%s, '_stock', %s),               # Cantidad disponible del producto
                                (%s, '_downloadable', 'no'),      # No es un porducto descargable
                                (%s, '_virtual', 'no'),           # No es un producto virtual( requiere de envío)
                                (%s, '_featured', 'no'),          # No es un porducto destacado
                                (%s, 'total_sales', '0')          # Ventas totales (inicialmente 0)
                                """
                            # Ejecutar la consulta para insertar los metadatos de la sentencia SQL
                            cursor.execute(sql_meta_woocommerce, (
                                    producto_id, producto_id, producto_id,
                                    producto_id, precio,
                                    producto_id, precio,
                                    producto_id,
                                    producto_id, stock,
                                    producto_id, producto_id, producto_id,
                                    producto_id
                                ))
                        #  Añadir el porducto a la taxonomía de porductos
                        ##
                        # Woocomerce usa taxonomía para clasificar y agrupar contenido: Las más comunes son:
                        # 'category' -> categorías de posts
                        # 'post_tag' -> etiquetas de posts
                        # 'product_cat' -> categoría de productos
                        # 'product_type' -> tipo de porductos(WooCommerce)
                        # 
                        # En Woocomerce, cada porducto debe tenenr al menos un ataxonomía 'porduct_type'. Por defecto, los 
                        # tipos más comunes son :
                        # simple -> producto simple (sin descuento)
                        # variable -> producto variable (con descuento)
                        # external -> producto externo (requiere de envío)
                        # grouped -> producto agrupado (requiere de envío)
                            sql_taxonomia = """
                            INSERT INTO wp_term_relationships (object_id, term_taxonomy_id)
                            VALUES (%s, 
                            (SELECT term_taxonomy_id FROM wp_term_taxonomy WHERE taxonomy = 'product_type' AND term_id =
                            (SELECT term_id FROM wp_terms WHERE name = 'simple' LIMIT 1) LIMIT 1))
                            """
                            cursor.execute(sql_taxonomia, (producto_id,))
                            # Categoría
                            if categoria:
                                #separar la categorúa y subcategoría
                                # Ejemplo: "Electrónica > Móviles"
                                #Lo que va a hacer es separa Electrónica por un lado y Móviles por el otro
                                categoria = categoria.split(' > ')
                                #Crea variable para almacenar el nombre de la categoría principal
                                categoria_principal = categoria[0].strip()
                                #Crea variable para almacenar el nombre de la subcategoría
                                subcategoria = categoria[1].strip() if len(categoria) > 1 else None
                                
                                #Si si existe una subcategoría 
                                if subcategoria:
                                    
                                
                                #Consulta para buscar categoría y subcategoría en Wordpress
                                    sql_categoria = """
                                SELECT
                                t1.term_id as cat_id,                # Id de la categoría principal
                                t1.name as categoria_principal,      # Nombre de la categoría principal
                                t2.term_id as subcat_id,             # Id de la subcategoría (puede ser NULL)
                                t2.name as subcategoria,             # Nombre de la subcategoría (puede ser NULL)
                                tt2.term_taxonomy_id as taxonomy_id  # Id de la taxonomía de la subcategoría
                                FROM wp_terms t1
                                JOIN wp_term_taxonomy tt1 ON t1.term_id = tt1.term_id
                                LEFT JOIN wp_term_taxonomy tt2 ON tt1.term_id = tt2.parent
                                LEFT JOIN wp_terms t2 ON tt2.term_id = t2.term_id
                                WHERE t1.name = %s 
                                AND tt1.taxonomy = 'product_cat'
                                AND (t2.name LIKE %s OR %s IS NULL)
                                """
                                    # Ejecutar la consulta para buscar la categoría y subcategoría
                                    cursor.execute(sql_categoria, (categoria_principal, subcategoria, subcategoria))
                                    resultado = cursor.fetchone()
                                   # Si encontramos la categoría/subcategoría
                                    if resultado:
                                    #Si encontramos la categoría/subcategoría, insertamos el producto
                                    
                                    # Inserción de la relación con el producto
                                    # Si existe una subcategoría, usar su taxonomy_id, sino usar el de la categoría principal
                                    # Si no, se usa el term_id de al categoría principal
                                    # Esto relaciona el porducot con esa categoría (o subcategoría si existe) con la tabla "wp_term_relationships"
                                        sql = """
                                    INSERT INTO wp_term_relationships (object_id, term_taxonomy_id)
                                    VALUES (%s, %s)
                                    """
                                    
                                    #Si hay sucategoría, usar su taxonomy_id, sino usar el de la categoría principal
                                        taxonomy_id = resultado[2] if subcategoria and resultado[2] else resultado[0]
                                        #Insertar la relación entre el producto y la categoría
                                        cursor.execute(sql, (producto_id, taxonomy_id))
                                    
                                    #Actualizar contador de la categoría
                                        sql_update_count = """
                                    UPDATE wp_term_taxonomy 
                                    SET count = count + 1 
                                    WHERE term_taxonomy_id = %s 
                                    """
                                        cursor.execute(sql_update_count, (taxonomy_id,))
                                    
                                       # productos_importados += 1
                                    else:
                                        # Si no se encuentra la categoría, imprimir un mensaje
                                        print(f"Categoría no encontrada: {categoria_principal} > {subcategoria if subcategoria else ''}")   
                        
                                productos_importados += 1
                        
                            # Imagen  si existe
                            if imagen:
                                #imprimir prueba para ver si existe la imagn
                                print(f"Imagen: {imagen}")
                                
                                try:
                                #Insertar la imagen como un nuvo post de tipo 'attachment'
                                    sql_imagen = """
                            INSERT INTO wp_posts (
                                post_author,            # ID del autor (por defecto 1)
                                post_date,              # Feca de creación de la imagen
                                post_date_gmt,          # Fecha de creación en formato GMT
                                post_title,             # nombre de la imagen
                                post_status,            # Estado del post: 'inherit' porque es hipo de un porducto
                                comment_status,         # Estado de los comentarios 'open' para permitir comentarios
                                ping_status,            # Estaod de lso pings (también irelevante, poer se incluye)
                                post_name,              # Slug de la imagen (nomrmalmente el mismo que post_tile)
                                post_modified,          # FEcha de modificación
                                post_modified_gmt,      # Fecha de modificación en GMT
                                post_parent,            # Id del porducto al que está imagen pertenece
                                guid,                   # URL única de la imagen
                                post_type,              # Tipo de contenido: 'attachment' indica que es una imagen
                                post_mime_type,         # Tipo MiNE  del archivo, ej. 'image/jpeg' 
                                post_content,           # Añadir post_content para evitar error
                                post_excerpt,           # Añadir post_excerpt
                                to_ping,                # Añadir to_ping
                                pinged,                 # Añadir pinged
                                post_content_filtered   # Añadir post_content_filtered
                                ) VALUES (
                                1,                 # post_author: administrador
                                NOW(),             # post_date: fecha actual
                                NOW(),             # post_date_gmt: fecha GMT
                                %s,                # post_title: nombre de la imagen
                                'inherit',         #post_status: hereda el estdo del porducto padre
                                'open',            # coment_status: abierto (por compatibilidad)
                                'closed',          # ping_status: cerrado (por compatibilidad)
                                %s,                # post_name: slug de la imagen
                                NOW(),             # post_modified: fecha actual
                                NOW(),             # post_modified_gmt: fecha GMT
                                %s,                # post_parent: id del producto relacionado
                                %s,                # guid: URL de la imagen
                                'attachment',      # post_type: tipo 'attachment¡ para archivos multimedia
                                'image/jpeg',      # post_mime_type: tip MIME del archivo (puede cambiar según el archivo real)
                                '',                # post_content: vacio
                                '',                # post_excerpt: vacio
                                '',                # to_ping: vacio
                                '',                # pinged: vacio
                                ''                 # post_content_filtered: vacio
                            )
                            """
                                #Obtener el nombre del archivo de la URL
                                    imagen_nombre = os.path.basename(imagen)
                                #Cursor para ejecutar la consulta
                                    cursor.execute(sql_imagen, (
                                    imagen_nombre,
                                    imagen_nombre,
                                    producto_id,
                                    imagen
                                ))
                                #Obtener el ID de la imagen insertada
                                    imagen_id = cursor.lastrowid
                                except mysql.connector.Error as err:
                                    # Manejar errores de inserción para la imagen 
                                    print("Error IMG:", f"Error al insertar imagen: {err}")
                                    continue
                                
                                try:
                                #Relacionar la imagen con el producto
                                # el porducto tendrá como imagne destacada la imagne recién insertada 
                                # la imagen tendrá como datos la ruta del archivo dentro del directorio "wp-content/uploads"
                                    sql_meta_imagen = """
                            INSERT INTO wp_postmeta (
                                post_id,
                                meta_key,
                                meta_value
                            ) VALUES (%s, '_thumbnail_id', %s),
                            (%s, '_wp_attached_file', %s)
                            """
                            #obtener la ruta relativa del archivo eliminado la parte inicial de la URL completa 
                                    ruta_relativa = imagen.replace('http://localhost/wordpress/wp-content/uploads/', '')
                                #Insertar la relación entre el producto y la imagen
                                # Esto vincula la imagen al producto como imagen destacada
                                # y también almacena la ruta del archivo en la base de datos
                                    cursor.execute(sql_meta_imagen,(
                                    producto_id,
                                    imagen_id,
                                    imagen_id,
                                    ruta_relativa   
                                    ))
                                
                                except mysql.connector.Error as err:
                                    messagebox.showerror("ErrorIMG3:", f"Error al insertar imagen relacionado: {err}")
                                    continue
                        except Exception as e:
                            # Manejar errores de inserción
                            # Imprimir el error y continuar con la siguiente fila
                            print(f"Error en fila: {e}")
                            continue
                # Guardar cambios en la base de datos
                conexion.commit()
                messagebox.showinfo("Éxito", f"Se importaron {productos_importados} productos")
            
                # Actualizar la tabla visual si se importaron porductos
                productos = obtener_productos()
                if productos:
                    cargar_datos_tabla(tabla, productos)
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al importar: {e}")
        finally:
            if conexion:
                conexion.close() #Cerrar conexión a la base de datos
  
    #Método para importar porductos manualmente
    def importar_manual():
        #Crear ventana para entrada manual
        ventana_manual = tk.Toplevel()
        ventana_manual.title("Importar Producto Manual")
        ventana_manual.geometry("450x650")
        
        #Campos del formulario
        #Nombre del producto
        ttk.Label(ventana_manual, text="Nombre:").pack(pady=5)
        nombre_entry = ttk.Entry(ventana_manual, width=40)
        nombre_entry.pack(pady=5)
        
        #Descripción del producto
        ttk.Label(ventana_manual, text="Descripción:").pack(pady=5)
        descripcion_entry = tk.Text(ventana_manual, width=40, height=5)
        descripcion_entry.pack(pady=5)
        
        #Descripción corta del producto
        ttk.Label(ventana_manual, text="Descripción corta:").pack(pady=5)
        descripcion_corta_entry = tk.Text(ventana_manual, width=40, height=2)
        descripcion_corta_entry.pack(pady=5)
        
        #Precio del producto
        ttk.Label(ventana_manual, text="Precio:").pack(pady=5)
        precio_entry = ttk.Entry(ventana_manual, width=40)
        precio_entry.pack(pady=5)
        
        #Stock del producto
        ttk.Label(ventana_manual, text="Stock:").pack(pady=5)
        stock_entry = ttk.Entry(ventana_manual, width=40)
        stock_entry.pack(pady=5)
        
        #Categoría del producto
        ttk.Label(ventana_manual, text="Categoría:").pack(pady=5)
        
        # Crear lista de categorías
        categorias_display_list, categorias_map = obtener_categorias_wp()
        # Crear un combobox para seleccionar la categoría
        categoria_combobox = ttk.Combobox(ventana_manual, values=categorias_display_list, width=37, state='readonly')
        if categorias_display_list:
            categoria_combobox.set(categorias_display_list[0]) # Set default to "(Sin categoría)"
        categoria_combobox.pack(pady=5)
        
        #Suncategoría del producto
        ttk.Label(ventana_manual, text="Subcategoría:").pack(pady=5)
        # Combobox para subcategorías (inicalmente vacío)
        subcategoria_combobox = ttk.Combobox(ventana_manual, width=37, state='readonly')
        subcategoria_combobox.set("(Sin subcategoría)")
        subcategoria_combobox.pack(pady=5)
        
        #Función para actuaizar las subcategoría basadas en al categorías seleccionada
        def actualizar_subcategorias(event):
            #Obtener la categoría seleccionada
            categoria_seleccionada = categoria_combobox.get()
            
            #Si selecciona "(Sin categoría)", no se muestran subcategorías
            if categoria_seleccionada == "(Sin categoría)":
                subcategoria_combobox.config(values=["(Sin subcategoría)"])
                subcategoria_combobox.set("(Sin subcategoría)")
                return
            
             #Obtener el Id de la categoría seleccionada 
            categoria_id = None
            for cat_id, cat_data in categorias_map.items():
                if cat_data['name'] == categoria_seleccionada:
                    categoria_id = cat_id
                    break
            if categoria_id is None:
                return
            
            #Obtener las subcategorías de esta categoría
            subcats = []
            for cat_id, cat_data in categorias_map.items():
                if cat_data['parent'] == categoria_id:
                    subcats.append(cat_data['name'])
            
            #Si hay subcategorías, agregalas al combobos
            if subcats:
                subcategoria_combobox.config(values=['(Sin subcategorías)'] + subcats)
                subcategoria_combobox.set('(Sin subcategoría)')
            else:
                #Si no hay subcategorías, mostrar "(Sin subcategoría)"
                subcategoria_combobox.config(values=["(Sin subcategoría)"])
                subcategoria_combobox.set("(Sin subcategoría)")
        #Vincular el evento de selección de categoría al combobox
        categoria_combobox.bind("<<ComboboxSelected>>", actualizar_subcategorias)
            
        
        # Imagen del porducto
        ttk.Label(ventana_manual, text="Imagen:").pack(pady=5)
        imagen_entry = ttk.Entry(ventana_manual, width=40)
        imagen_entry.pack(pady=5)
        
        #Boton para seleccionar la imagen
       
        def seleccionar_imagen():
            #Funcion para selecionar imagne del prducto
            ruta_imagen = filedialog.askopenfilename(
                title= "Seleccionar imagen del producto",
                filetypes=[("Archivos de imagen", "*.jpg")]
            )
            
            
    
    
            if ruta_imagen:  # Si se seleccionó una imagen
                imagen_entry.delete(0, tk.END)  # Borrar contenido actual
                imagen_entry.insert(0, ruta_imagen)  # Insertar nueva ruta
                
        ttk.Button(ventana_manual, text="Seleccionar Imagen", command=seleccionar_imagen).pack(pady=5)
        
        
        #Método para guardar producto
        def guardar_producto():
            #nombre del producto
            nombre = nombre_entry.get().strip()
            #Descripción del producto
            descripcion = descripcion_entry.get("1.0", tk.END).strip()
            #Descripción corta del producto
            descripcion_corta = descripcion_corta_entry.get("1.0", tk.END).strip()
            #Precio del producto
            precio = precio_entry.get()
            #Stock del producto
            stock = stock_entry.get()
            #Imagen del producto
            imagen_local = imagen_entry.get().strip()
            #Categoría del producto
            categoria_principal = categoria_combobox.get()
            #Subcategoría del producto
            subcategoria = subcategoria_combobox.get()
            
            #Validar campos
            if not nombre or not precio or not stock or not imagen_local or not descripcion or not descripcion_corta:
                messagebox.showwarning("Advertencia", "Nombre, Precio, Stock, Imagen y Descripción son obligatorios.")
                return
            #Validar precio y stock
            try:
                precio = float(precio)
                stock = int(stock)
            except ValueError:
                messagebox.showwarning("Advertencia", "Precio debe ser un número y Stock un entero.")
                return
            #Validar imagen
            if not os.path.isfile(imagen_local):
                messagebox.showwarning("Advertencia", "La imagen no existe.")
                return
            #Validar la extensión de la imagen
            _, extension = os.path.splitext(imagen_local)
            if extension.lower() not in ['.jpg', '.jpeg', '.png']:
                messagebox.showwarning("Advertencia", "La imagen debe ser JPG o PNG.")
                return
            
            
            #Generar slug y guid para el porducto 
            tem_slug = nombre.lower()
            #Reemplazar acentos comunes (puedes expandir esta lista)
            replacements = {
                'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n',
                'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u'
            }
            # Bucle que reemplaza los caracteres acentuados por los no acentuados
            for acented_char, unaccented_char in replacements.items():
                tem_slug = tem_slug.replace(acented_char, unaccented_char)
            # Sustituye espacios y caracteres especiales por guiones para generar el slug y que no haya problemas con la URL
            nombre_slug = tem_slug.lower().replace(' ', '-').replace('/', '-').replace('(', '').replace(')', '')
            #Eliminar caracteres no alfanuméricos excepto guiones
            nombre_slug = ''.join(c for c in nombre_slug if c.isalnum() or c == '-')
            #Eliminar múltiples guiones seguidos
            while '--' in nombre_slug:
                nombre_slug = nombre_slug.replace('--', '-')
            nombre_slug = nombre_slug.strip('-')
            # Crear la URL única del producto
            guid = f"http://localhost/wordpress/?product={nombre_slug}"
            
            #Cponección con la base de datos
            conexion = None
            
            try:
                #Conexión con la base de datos
                conexion = conectar_bd()
                #si la conexion es correcta
                if conexion:
                    cursor = conexion.cursor()
                    #Insertar producto en Woocommerce
                    sql = """
                    INSERT INTO wp_posts (
                        post_author,
                        post_date,
                        post_date_gmt,
                        post_content,
                        post_title,
                        post_excerpt,
                        post_status,
                        comment_status,
                        ping_status,
                        post_password,
                        post_name,
                        to_ping,
                        pinged,
                        post_modified,
                        post_modified_gmt,
                        post_content_filtered,
                        post_parent,
                        guid,
                        menu_order,
                        post_type,
                        post_mime_type
                        )
                        VALUES (
                            1,
                            NOW(),
                            NOW(),
                            '',
                            %s,
                            %s,
                            'publish',
                            'open',
                            'closed',
                            '',
                            %s,
                            '',
                            '',
                            NOW(),
                            NOW(),
                            '',
                            0,
                            %s,
                            0,
                            'product',
                            ''
                            )
                    """
                    #Ejecutar la consulta SQL
                    cursor.execute(sql, (
                        nombre, descripcion_corta, 
                        nombre_slug, guid
                        ))
                    #Obtener el ID del producto insertado
                    producto_id = cursor.lastrowid
                    
                    #Insertar metadatos en Woocommerce
                    meta_values = [
                        (producto_id, '_product_type', 'simple'),
                        (producto_id, '_visibility', 'visible'),
                        (producto_id, '_stock_status', 'instock' if stock > 0 else 'outofstock'),
                        (producto_id, '_regular_price', str(precio)),
                        (producto_id, '_price', str(precio)),
                        (producto_id, '_manage_stock', 'yes'),
                        (producto_id, '_stock', str(stock)),
                        (producto_id, '_downloadable', 'no'),
                        (producto_id, '_virtual', 'no'),
                        (producto_id, '_featured', 'no'),
                        (producto_id, 'total_sales', '0')
                        ]
                    sql_meta_woocommerce = "INSERT INTO wp_postmeta (post_id, meta_key, meta_value) VALUES (%s, %s, %s)"
                    cursor.executemany(sql_meta_woocommerce, meta_values)
                    
                    #Añadir el producto a la taxonomía 'product_type' = 'simple'
                    sql_taxonomia = """
                    INSERT INTO wp_term_relationships (object_id, term_taxonomy_id)
                    VALUES (%s, 
                    (SELECT term_taxonomy_id FROM wp_term_taxonomy tt JOIN wp_terms t ON tt.term_id = t.term_id 
                     WHERE tt.taxonomy = 'product_type' AND t.name = 'simple' LIMIT 1))
                    """
                    cursor.execute(sql_taxonomia, (producto_id,))
                    
                    #Asignar categoría (si no es "Sin categoría")
                    if categoria_principal != "(Sin categoría)":
                        #Buscar la categoría seleccionada en la base de datos
                        sql_categoria = """
                        SELECT tt.term_taxonomy_id
                        FROM wp_terms t
                        JOIN wp_term_taxonomy tt ON t.term_id = tt.term_id
                        WHERE t.name = %s AND tt.taxonomy = 'product_cat'
                        """
                        # Ejecutar la consulta para buscar la categoría
                        # y obtener el ID de la categoría
                        # y subcategoría
                        # Si no hay subcategoría, solo buscar la categoría principal
                        # Si hay subcategoría, buscar la subcategoría
                        # y la categoría principal
                        # Si no se encuentra la subcategoría, buscar solo la categoría principal
                        cursor.execute(sql_categoria, (categoria_principal,))
                        resultado = cursor.fetchone()
                        #Si se encutnra la categoría
                        if resultado:
                            term_taxonomy_id = resultado[0]
                            #Asignar categoría al porducto 
                            sql_rel = "INSERT INTO wp_term_relationships (object_id, term_taxonomy_id) VALUES (%s, %s)"
                            cursor.execute(sql_rel, (producto_id, term_taxonomy_id))
                            #Actualizar contador de la categoría
                            sql_update_count = "UPDATE wp_term_taxonomy SET count = count + 1 WHERE term_taxonomy_id = %s"
                            cursor.execute(sql_update_count, (term_taxonomy_id,))
                        else:
                            # Si no se encuentra la categoría, imprimir un mensaje
                            print(f"Categoría no encontrada: {categoria_principal}")
                    #Asignar subcategoría (si no es "Sin subcategoría") 
                    if subcategoria != "(Sin subcategoría)":
                        #Buscar la subcategoría seleccionada en la base de datos
                        sql_subcategoria = """
                        SELECT tt.term_taxonomy_id
                        FROM wp_terms t
                        JOIN wp_term_taxonomy tt ON t.term_id = tt.term_id
                        WHERE t.name = %s AND tt.taxonomy = 'product_cat'
                        """
                        # Ejecutar la consulta para buscar la subcategoría
                        cursor.execute(sql_subcategoria, (subcategoria,))
                        resultado_subcat = cursor.fetchone()
                        #Si se encutnra la subcategoría
                        if resultado_subcat:
                            term_taxonomy_id_subcat = resultado_subcat[0]
                            #Asignar subcategoría al porducto 
                            sql_rel_subcat = "INSERT INTO wp_term_relationships (object_id, term_taxonomy_id) VALUES (%s, %s)"
                            cursor.execute(sql_rel_subcat, (producto_id, term_taxonomy_id_subcat))
                            #Actualizar contador de la subcategoría
                            sql_update_count_subcat = "UPDATE wp_term_taxonomy SET count = count + 1 WHERE term_taxonomy_id = %s"
                            cursor.execute(sql_update_count_subcat, (term_taxonomy_id_subcat,))
                        else:
                            # Si no se encuentra la subcategoría, imprimir un mensaje
                            print(f"Subcategoría no encontrada: {subcategoria}")
    
                    # Manejo de al imagen
                    if imagen_local and os.path.exists(imagen_local):
                        try:
                            
                            # Imprimir la ruta de la imagen
                            print(f"Imagen: {imagen_local}")
                            # Obtner la ruta donde está la imagen
                            # Obtener la ruta de la imagen
                            url_imagen = imagen_local+"/"
                            # Obtener la ruta relativa de la imagen
                            imagen_file = os.path.basename(imagen_local)
                            
                            
                                
                               
                            #Insertar la imagen como un nuevo post de tipo 'attachment'
                            sql_imagen = """
                            INSERT INTO wp_posts (
                                post_author,
                                post_date,
                                post_date_gmt,
                                post_title,
                                post_status,
                                comment_status,
                                ping_status,
                                post_name,
                                post_modified,
                                post_modified_gmt,
                                post_parent,
                                guid,
                                post_type,
                                post_mime_type,
                                post_content,     # Asegúrate de incluir este campo
                                post_excerpt,
                                to_ping,
                                pinged,
                                post_content_filtered
                            ) VALUES (
                                1, 
                                NOW(),
                                NOW(),
                                %s, 
                                'inherit',
                                'open', 
                                'closed',
                                %s, 
                                NOW(),
                                NOW(),
                                %s, 
                                %s, 
                                'attachment',
                                'image/jpeg',
                                '',
                                '',
                                '',
                                '',
                                ''
                                
                            )
                            """
                            cursor.execute(sql_imagen, (
                                imagen_file,
                                imagen_file,
                                producto_id,
                                imagen_file
                            ))
                            # Obtener el ID de la imagen insertada
                            imagen_id = cursor.lastrowid
                            
                            #obtener la ruta relativa del archivo elinando la parte inicial de la URL completa
                            ruta_relativa = imagen_local.replace('http://localhost/wordpress/wp-content/uploads/', '')
                            
                            # Relacionar la imagen con el producto
                            sql_meta_imagen = """
                            INSERT INTO wp_postmeta (post_id, meta_key, meta_value)
                            VALUES (%s, '_thumbnail_id', %s),
                                      (%s, '_wp_attached_file', %s)
                             """
                            cursor.execute(sql_meta_imagen, (
                                producto_id,
                                imagen_id,
                                imagen_id,
                                ruta_relativa
                            ))
                             
                           
                        except Exception as e:
                            # Manejar errores de inserción para la imagen
                            print("Error al insertar imagen:", e)
                            
            # HAcer commint de lso cambios
                conexion.commit()
                            # Mostrar mensaje de éxito
                messagebox.showinfo("Éxito", "Producto guardado con éxito.")
                            
                            #Actualizar la tabla principal
                productos_actualizados = obtener_productos()
                if productos_actualizados:
                    cargar_datos_tabla(tabla, productos_actualizados)
                            
                            
                            #Ventana para cerrar la importación manual
                ventana_manual.destroy()         
            except mysql.connector.Error as err:
                messagebox.showerror("Error", f"Error al importar producto: {err}")
            finally:
                #si la conexion es correcta
                if conexion:
                    conexion.close()
                    
        #Boton para guardar producto
        ttk.Button(ventana_manual, text="Guardar Producto", command=guardar_producto).pack(pady=10)
   
    #Botones para importar
    frame_botones = ttk.Button(ventana_importar, text = "Importar desde CSV", command = importar_csv).pack(pady=10)
    ttk.Button(ventana_importar, text = "Importar Manual", command = importar_manual).pack(pady=10)
    
#Método para modificar productos 
def eliminar_productos(tabla):
    """Función para eliminar productos seleccionados"""
    # Verificar si hay un producto seleccionado 
    seleccion = tabla.selection()
    if not seleccion:
        messagebox.showwarning("Advertencia", "Seleccione un producto para eliminar.")
        return
    # Confirmar la eliminación
    respuesta = messagebox.askyesno("Confirmar", "¿Está seguro de que desea eliminar el producto seleccionado?")
    if respuesta:
        # Obtener el ID del producto seleccionado
   
        producto_id = tabla.item(seleccion[0])['values'][0]
        
        # Conexión a la base de datos
        conexion = conectar_bd()
        try:
            if conexion:
                cursor = conexion.cursor()
                # Eliminar el producto de la base de datos
                sql_eliminar_producto = "DELETE FROM wp_posts WHERE ID = %s"
                cursor.execute(sql_eliminar_producto, (producto_id,))
                
                # Eliminar los metadatos del producto
                sql_eliminar_meta = "DELETE FROM wp_postmeta WHERE post_id = %s"
                cursor.execute(sql_eliminar_meta, (producto_id,))
                
                # Eliminar las relaciones del producto con las categorías
                sql_eliminar_relacion = "DELETE FROM wp_term_relationships WHERE object_id = %s"
                cursor.execute(sql_eliminar_relacion, (producto_id,))
                
                # Hacer commit de los cambios
                conexion.commit()
                
                # Actualizar la tabla visual
                productos_actualizados = obtener_productos()
                if productos_actualizados:
                    cargar_datos_tabla(tabla, productos_actualizados)
                # Mostrar mensaje de éxito
                messagebox.showinfo("Éxito", "Producto eliminado con éxito.")
        except mysql.connector.Error as err:
            # Manejar errores de eliminación
            print("Error al eliminar producto:", err)
            #Mostrar mensaje de error a eliminar el producto
            messagebox.showerror("Error", f"Error al eliminar producto: {err}")
        finally:
            if conexion:
                # Cerrar la conexión a la base de datos
                conexion.close()  
        # Seleccionar el porducto de la tabla para actualizar la tabla visual
        seleccion = tabla.selection()
    elif  not seleccion:
        # Si no hay producto seleccionado, mostrar un mensaje de advertencia
        messagebox.showwarning("Advertencia", "Seleccione un producto para modificar.")
        return

#Método para poder ajustar el precio del producto dependiendo de la inflación que halla en ese monento 
#Este método sirve tanto para aumentar la inflación como para disminuirla 
def ajustar_precio_inflacion(tabla):
     #Crear ventana para ajustar el precio
    ventana_inflacion = tk.Toplevel()
    ventana_inflacion.title("Ajustar Precio por Inflación")
    ventana_inflacion.geometry("300x200")
    
    #Crear frame para los controles
    frame = ttk.Frame(ventana_inflacion)
    frame.pack(expand=True, fill='both')
    
    #Etiqueta informativa de los ajuste de información 
    ttk.Label(frame, text="Ajuste de precio según inflación:", font=('Arial', 12, 'bold')).pack(pady=10)
    ttk.Label(frame, text="Ingrese el porcentaje de inflación:", font=('Arial', 10)).pack(pady=5)
    
    #Entrada para el porcentaje de inflación
    porcentaje_var = tk.StringVar()
    porcentaje_entry = ttk.Entry(frame, width=10, textvariable=porcentaje_var)
    porcentaje_entry.pack(pady=5)
    
    #Radio buttons para seleccionar aumento o disminución de la inflación 
    tipo_ajuste = tk.StringVar(value="aumento")
    frame_radio = ttk.Frame(frame)
    frame_radio.pack(pady=10)
    
    ttk.Radiobutton(frame_radio, text="Aumento", variable=tipo_ajuste, value="aumento").pack(side='left', padx=5)
    ttk.Radiobutton(frame_radio, text="Disminución", variable=tipo_ajuste, value="disminucion").pack(side='left', padx=5)
    
    #Función para aplicar el ajuste
    def aplicar_ajuste():
        try:
            #Obtener el porcentaje y validarlo
            porcentaje = float(porcentaje_var.get().replace(',', '.'))
            if porcentaje < 0:
                messagebox.showwarning("Advertencia", "El porcentaje no puede ser negativo.")
                return
            #Confirmar la operación
            operacion = "aumento" if tipo_ajuste.get() == "aumento" else "disminucion"
            respuesta = messagebox.askyesno("Confirmar", f"¿Está seguro de que desea aplicar un {operacion} del {porcentaje}% a los precios?")
            
            if not respuesta:
                return
            
            #Conectar a la base de datos
            conexion = conectar_bd()
            if not conexion:
                return
            try:
                cursor = conexion.cursor()
                #Obtner todo losproductos con sus precios actuales
                sql_select = """
                SELECT post_id, meta_value
                FROM wp_postmeta
                WHERE meta_key = '_price'
                """
                cursor.execute(sql_select)
                productos = cursor.fetchall()
                
                #Factor de multiplicación según tipo de ajuste
                factor = 1 + (porcentaje / 100) if tipo_ajuste.get() == "aumento" else 1 - (porcentaje / 100)
                
                #Actualizar los precio de cada producto
                productos_actualizados = 0
                
                for producto in productos:
                    producto_id = producto[0]
                    precio_actual = float(producto[1])
                    nuevo_precio = round(precio_actual * factor, 2)
                    
                    #Actualizar precio regular
                    sql_update_regular = """
                    UPDATE wp_postmeta
                    SET meta_value = %s
                    WHERE post_id = %s AND meta_key = '_price'
                    """
                    cursor.execute(sql_update_regular, (str(nuevo_precio), producto_id))
                    
                    #Actualizar precio actual
                    sql_update_price = """
                    UPDATE wp_postmeta
                    SET meta_value = %s
                    WHERE post_id = %s AND meta_key = '_regular_price'
                    """
                    cursor.execute(sql_update_price, (str(nuevo_precio), producto_id))
                    
                    productos_actualizados += 1
                
                #Confirmar cambios
                conexion.commit()
                
                #Mostrar mensaje de éxito
                messagebox.showinfo("Operación exitosa", f"Se han {operacion}do los precios de {productos_actualizados} productos.")
                
                #Actualizar la tabla
                productos_actualizados = obtener_productos()
                if productos_actualizados:
                    cargar_datos_tabla(tabla, productos_actualizados)
                
                #Cerrar ventana
                ventana_inflacion.destroy()
                
            except mysql.connector.Error as err:
                messagebox.showerror("Error", f"Error al actualizar precios: {err}")
                if conexion:
                    conexion.rollback()
            finally:
                if conexion:
                    conexion.close()
                    
        except ValueError:
            messagebox.showwarning("Advertencia", "Ingrese un porcentaje válido (número).")
    
    #Botones
    frame_botones = ttk.Frame(frame)
    frame_botones.pack(pady=10)
    ttk.Button(frame_botones, text="Aplicar", command=aplicar_ajuste).pack(side='left', padx=5)
    ttk.Button(frame_botones, text="Cancelar", command=ventana_inflacion.destroy).pack(side='left', padx=5)

def hilo_scraper():
     # Llamar al método ejecutar_scraper par acrear un hilo
     hilo_scraper = threading.Thread(target=scrape5.main)
     hilo_scraper.start()
        

def crear_ventana_principal():
    """Función principal que crea la ventana"""
    # Crear ventana principal
    ventana = tk.Tk()
    ventana.title("Gestor de Productos WooCommerce")
    ventana.geometry("1000x600")

    #Crear contador porductos totales
    frame_contador = ttk.Frame(ventana)
    frame_contador.pack(fill='x', padx=10, pady=5)
    
    #Creación del logo 
    try:
        #Rut de la imagen del logo
        logo_ruta = "logo-aliexpress.jpg"
        #Cargar la imagn 
        logo_original = Image.open(logo_ruta)
        #Redimensionar la imagen
        # Redimensionar la imagen con el tamaó de 100x50 píxeles y imagen antialias
        # Image.ANTIALIAS es una opción de redimensionado que mejora la calidad de la imagen
        logo_redimencionado = logo_original.resize((100,100), Image.ANTIALIAS) 
        # Crear un objeto PhotoImage a partir de la imagen redimensionada
        logo_imagen = ImageTk.PhotoImage(logo_redimencionado)
        
        # Crear un label para mostrar la imagen
        label_logo = ttk.Label(frame_contador, image=logo_imagen)
        label_logo.image = logo_imagen  # Mantener una referencia a la imagen
        label_logo.pack(side='right', padx=5)  # Agregar el label a la ventana
    except Exception as e:
        print(f"Error al cargar la imagen: {e}")
        
        #Crear el titulo de la ventana 
    frame_titulo = ttk.Frame(frame_contador)
    frame_titulo.pack(fill='x', padx=10, pady=5)
    
    #Titulo principal
    titulo_label = ttk.Label(frame_titulo, text="Gestor de Productos WooCommerce", 
                             font=('Arial', 16, 'bold'))
    titulo_label.pack(pady=5)
    
    #Lavel para mostrar el contador
    label_contador = ttk.Label(frame_contador, text="Total de productos ", font=('Arial', 10, 'bold'))
    label_contador.pack(side='left', padx=10)
    #Actualizar el contador con el nuemro de porducto 
    total_producto = len(obtener_productos())
    label_contador.config(text=f"Total de productos: {total_producto}")
    # Crear tabla
    tabla = crear_tabla(ventana)

    # Crear botones
    frame_botones = ttk.Frame(ventana)
    frame_botones.pack(fill='x', padx=10, pady=5)
    
    # Botón para modificar producto
    ttk.Button(frame_botones, text="Modificar Producto", command=lambda: modificar_producto(tabla)).pack(side='left', padx=5)
    
    # Botón para buscar productos
    ttk.Button(frame_botones, text="Buscar Producto", command=lambda: buscar_productos(tabla)).pack(side='left', padx=5)

    def actualizar():
        """Función para actualizar la tabla"""
        productos = obtener_productos()
        if productos:
            cargar_datos_tabla(tabla, productos)

    # Añadir botones
    ttk.Button(frame_botones, text="Actualizar", command=actualizar).pack(side='left', padx=5)
    # Botón para importar productos
    ttk.Button(frame_botones, text="Importar Productos", command=lambda: importar_productos(tabla)).pack(side='left', padx=5)
    #Boton para eliminar porductos
    ttk.Button(frame_botones, text="Eliminar Productos", command=lambda: eliminar_productos(tabla)).pack(side='left', padx=5)
    #Boton para ajustar el precio de los productos
    ttk.Button(frame_botones, text="Ajustar Precio por Inflación", command=lambda: ajustar_precio_inflacion(tabla)).pack(side='left', padx=5)
    #Boton para ejecutar el scraper
    ttk.Button(frame_botones, text="Ejecutar Scraper", command=lambda: threading.Thread(target=scrape5.main(), daemon=True).start()).pack(side='left', padx=5)
    
    
    # Cargar datos iniciales
    productos = obtener_productos()
    if productos:
        cargar_datos_tabla(tabla, productos)

    return ventana

def main():
    """Función principal para ejecutar la aplicación"""
    # Crear la ventana principal
    ventana = crear_ventana_principal()
    
    # Iniciar el bucle principal de la ventana
    ventana.mainloop()
 

if __name__ == "__main__":
    main()
    
   