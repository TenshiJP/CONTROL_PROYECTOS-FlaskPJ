#Libs
from flask import Flask, render_template, request, redirect, url_for, flash, Response, session
from flask_mysqldb import MySQL
from openpyxl import Workbook
from config import Config
from functools import wraps
import io
from models.proyecto import insert_proyecto, get_projects 
from models.empleado import insert_empleado, get_uuid_empleado
from models.tarea import insert_tarea, get_job
from models.unidad import get_unit, get_tipos_unidad

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'

# Configuración de la base de datos
app.config.from_object(Config)
mysql = MySQL(app)


#filtrado de datos para lista y DonwloadExcel
def get_filtered_data(filtro, estados):
    inicio = filtro[2] + "-" + filtro[1] + "-" + filtro[0]
    fin = filtro[5] + "-" + filtro[4] + "-" + filtro[3]
    opciones = []
    sql = "SELECT * FROM VW_DATA_INSTALADORES"

    if inicio != "--" and fin != "--":
        opciones.append("FECHA BETWEEN %s AND %s")
    if filtro[6] is not None and filtro[6] != "":
        opciones.append("EMPLEADO = %s")
    if filtro[7] is not None and filtro[7] != "":
        opciones.append("PROYECTO = %s")
    if estados:
        estados = [estado for estado in estados if estado.strip() != '']
        estados_condition = " OR ".join(["ESTADO = %s" for estado in estados])
        opciones.append(f"({estados_condition})")

    where_clause = " AND ".join(opciones)
    if where_clause:
        sql += " WHERE " + where_clause

    try:
        cur = mysql.connection.cursor()
        cur.execute(sql, (inicio, fin, filtro[6], filtro[7], *estados))
        rows = cur.fetchall()
        cur.close()
        
        if rows:
            totales = calcular_totales(rows)
            precio_total = calcular_precio_total(totales)
        else:
            totales = [0, 0, 0, 0, 0, 0]
            precio_total = 0

        return rows, totales, filtro, estados, precio_total

    except mysql.Error as e:
        print(f'Error al obtener los datos de la base de datos: {str(e)}')
        return None, None, None, None, None

def calcular_totales(rows):
    total_liquido = sum([row[8] for row in rows])  # La columna 8 representa Liquido
    total_descuentos = sum([row[7] for row in rows])  # La columna 7 representa Descuentos
    total_total_iva = sum([row[12] for row in rows])  # La columna 12 representa Total con IVA
    total_isr = float(total_liquido) * 0.05
    total_iva = float(total_liquido) * 0.12
    total_facturar = float(total_liquido) + total_isr + total_iva
    totales = [("{:.2f}".format(total_descuentos)), ("{:.2f}".format(total_liquido)), ("{:.2f}".format(total_isr)), ("{:.2f}".format(total_iva)), ("{:.2f}".format(total_facturar)), ("{:.2f}".format(total_total_iva))] 
    return totales

def calcular_precio_total(totales):
    total_liquido = float(totales[1])
    total_descuentos = float(totales[0])
    precio_total = total_liquido - total_descuentos
    return precio_total

#Protector de rutas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

#Root
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        username = request.form['username']
        password = request.form['password']
        try:
            cur.execute("SELECT USUARIO, PASS FROM USUARIO WHERE USUARIO = %s", (username,))
            account = cur.fetchone()
            if account:
                if account[1] == password:
                    print('Usuario ha iniciado sesión')
                    session['username'] = username
                    return redirect(url_for('index')) 
                else:
                    note = 'La contraseña no es válida'
                    return render_template('login.html', note=note) 
            else:
                print('No existe el usuario')
                note = 'Las credenciales no son correctas'
                return render_template('login.html', note=note)    
        except Exception as e:
            print(f'Error al consultar la BD: {str(e)}')
            note = 'Error de conexión en los servicios'
            return render_template('login.html', note=note)
    return render_template('login.html')        

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/')
# @login_required
def index():
    return render_template('index.html')

#Lista instaladores
@app.route('/lista', methods=['GET', 'POST'])
# @login_required
def lista():
    # Obtener los valores de los filtros
    iday = request.form.get('iday', '')
    imes = request.form.get('imes', '')
    iyear = request.form.get('iyear', '')
    fday = request.form.get('fday', '')
    fmes = request.form.get('fmes', '')
    fyear = request.form.get('fyear', '')
    empleado = request.form.get('employee', '')
    proyecto = request.form.get('project', '')
    estados = request.form.getlist('estado',)
    filtro = [iday, imes, iyear, fday, fmes, fyear, empleado, proyecto]

    # Verificar si los filtros están vacíos tanto por POST como por GET
    if all(element == '' for element in filtro) and all(estado == '' for estado in estados):
        iday = request.args.get('iday', '')
        imes = request.args.get('imes', '')
        iyear = request.args.get('iyear', '')
        fday = request.args.get('fday', '')
        fmes = request.args.get('fmes', '')
        fyear = request.args.get('fyear', '')
        empleado = request.args.get('employee', '')
        proyecto = request.args.get('project', '')
        estados = request.args.getlist('estados',)
        filtro = [iday, imes, iyear, fday, fmes, fyear, empleado, proyecto]

         # Crear un objeto filtro con las variables recopiladas
    class Filtro:
        def __init__(self, iday, imes, iyear, fday, fmes, fyear, empleado, proyecto):
            self.iday = iday
            self.imes = imes
            self.iyear = iyear
            self.fday = fday
            self.fmes = fmes
            self.fyear = fyear
            self.empleado = empleado
            self.proyecto = proyecto

    filtro_obj = Filtro(iday, imes, iyear, fday, fmes, fyear, empleado, proyecto)

    try:
        rows, totales, filtro, estados, precio_total = get_filtered_data(filtro_obj, estados)
         # Validar los datos obtenidos y realizar cálculos si es necesario
        if rows:
            return render_template('datos-instaladores.html', instaladores=rows, totales=totales, filtro=filtro, estados=estados, precio_total=precio_total)
        else:
            return render_template('datos-instaladores.html', instaladores=[], totales=[0, 0, 0, 0, 0, 0], filtro=filtro, estados=estados, precio_total=0)
    except Exception as e:
        print(f'Error al cargar los registros: {str(e)}')
        return render_template('error-bd.html')
        

@app.route('/datos-instaladores', methods=['GET', 'POST']) 
# @login_required
def download_excel():
    # Filtros
    sql = "SELECT * FROM VW_DATA_INSTALADORES "
    iday = request.form.get('iday', '')
    imes = request.form.get('imes', '')
    iyear = request.form.get('iyear', '')
    inicio = iyear+"-"+imes+"-"+iday
    fday = request.form.get('fday', '')
    fmes = request.form.get('fmes', '')
    fyear = request.form.get('fyear', '')
    fin = fyear+"-"+fmes+"-"+fday
    empleado = request.form.get('employee', '')
    proyecto = request.form.get('project', '')
    estados = request.form.getlist('estado',) 
    opciones = []
    filtro = [iday, imes, iyear, fday, fmes, fyear, empleado, proyecto]
    #Validación por medio de la URL
    if all(element == '' for element in filtro) and all(estado == '' for estado in estados):
        iday = request.args.get('iday', '')
        imes = request.args.get('imes', '')
        iyear = request.args.get('iyear', '')
        fday = request.args.get('fday', '')
        fmes = request.args.get('fmes', '')
        fyear = request.args.get('fyear', '')
        empleado = request.args.get('employee', '')
        proyecto = request.args.get('project', '')
        estados = request.args.getlist('estados',)
        inicio = iyear+"-"+imes+"-"+iday
        fin = fyear+"-"+fmes+"-"+fday
        filtro = [iday, imes, iyear, fday, fmes, fyear, empleado, proyecto]
        #print("Otro manera")

    #Condiciones    
    if inicio != "--" and fin != "--":
        opciones.append("FECHA >= '" + inicio + "' AND FECHA <= '" + fin + "'")
    if empleado is not None and empleado != "":
        opciones.append("EMPLEADO = '" + empleado + "'")
    if proyecto is not None and proyecto != "":
        opciones.append("PROYECTO = '" + proyecto + "'")
    if estados:
        estados = [estado for estado in estados if estado.strip() != '']
        estados_condition = " OR ".join(["ESTADO = '" + estado + "'" for estado in estados])
        opciones.append(f"({estados_condition})")

    # Construir la cláusula WHERE
    where_clause = " AND ".join(opciones)
    if where_clause:
        sql += " WHERE " + where_clause

    try:
        # Crear un nuevo libro de trabajo de Excel
        wb = Workbook()
        ws = wb.active
        # Realizar la consulta a la base de datos
        cur = mysql.connection.cursor()
        cur.execute(sql)
        #print(sql)
        rows = cur.fetchall()
        cur.close()
        # Comprobar que hay resultados
        if rows is not None:
            # Agregar los encabezados de la tabla manualmente
            headers = ["NOMBRE", "PROYECTO", "DESCRIPCION DE TRABAJO", "PRECIO UNITARIO", "CANTIDAD", "UNIDAD", "DESCUENTOS", "LIQUIDO A RECIBIR", "ISR", "IVA", "TOTAL A FACTURAR", "TOTAL A FACTURAR APOYO CON IVA", "ESTADO", "FECHA"]
            ws.append(headers)
            # Agregar los datos de la tabla
            for row in rows:
                ws.append(row[1:])
            ws.append([])
            # Agregar los totales al final de las columnas
            total_liquido = sum([row[8] for row in rows])  # La columna 7 representa Liquido
            total_descuentos = sum([row[7] for row in rows])  # La columna 6 representa Descuentos
            total_total_iva = sum([row[12] for row in rows])  # La columna 11 representa Total con IVA
            total_isr = float(total_liquido) * 0.05
            total_iva = float(total_liquido) * 0.12
            total_facturar = float(total_liquido) + total_isr + total_iva
            precio_total = float(total_liquido - total_descuentos)
            footers = ["", "", "", "", "", "SUMATORIAS:", total_descuentos, total_liquido, total_isr, total_iva, total_facturar, total_total_iva]
            ws.append(footers)
            ws.append(["", "", "", "", "", "MONTO TOTAL:","",precio_total])
            # Crear un objeto de BytesIO para almacenar los datos del archivo Excel
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            # Crear una respuesta HTTP con el archivo Excel
            response = Response(output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response.headers["Content-Disposition"] = "attachment; filename=datos_instaladores.xlsx"
            return response
        else:
            flash('No hay datos para exportar.', 'info')
            print('No hay datos para exportar.')
            return redirect(url_for('index'))
    except Exception as e:
        print(f'Error al exportar los datos: {str(e)}')
        return render_template('error-bd.html')

@app.route('/list-units', methods=['GET', 'POST'])
# @login_required
def lista_units():
    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT * FROM UNIDAD")
        rows = cur.fetchall()
        cur.close()
        return render_template('units/list-units.html', unidades=rows)
    except Exception as e:
        print(f'Error al exportar los datos: {str(e)}')
        return render_template('error-bd.html')

#RUTAS
@app.route('/new-project', methods=['GET'])
def show_unidades():
    lista_unidades = get_tipos_unidad()
    return render_template('projects/new-project.html', unidades=lista_unidades)

@app.route('/new-job', methods=['GET'])
# @login_required
def show_projects():
    lista_proyectos = get_projects()
    lista_unidades = get_tipos_unidad()
    return render_template('jobs/new-job.html', proyectos=lista_proyectos, unidades=lista_unidades)

@app.route("/edit-job/<int:id>")
# @login_required
def edit_job(id):
    job = get_job(id)
    lista_unidades = get_tipos_unidad()
    if job["DESCUENTO"] is not None and float(job["DESCUENTO"]) > 0:
        descuento = "Si"
    else:
        descuento = "No"
    return render_template('jobs/edit-job.html', job=job, descuento=descuento, unidades=lista_unidades) 

@app.route('/new-unit', methods=['GET'])
# @login_required
def new_unit():
    return render_template('units/new-unit.html')

@app.route("/edit-unit/<int:id>")
# @login_required
def edit_unit(id):
    unidad = get_unit(id)
    return render_template('units/edit-unit.html', unidad=unidad)

@app.route('/destroy-unit/<int:id>')
# @login_required
def destroy_unit(id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("DELETE FROM UNIDAD WHERE UUID = %s", (str(id), ))
        cur.close()
        mysql.connection.commit()
        return redirect(url_for('lista_units'))
    except Exception as e:
        print(f'Error al eliminar la unidad de medida: {str(e)}')
        return render_template('error-bd.html')

@app.route('/destroy-job/<int:id>')
# @login_required
def destroy_job(id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE TAREA SET ESTADO='ELIMINADO' WHERE UUID = %s", (str(id), ))
        cur.close()
        mysql.connection.commit()
        return redirect(url_for('lista'))
    except Exception as e:
        print(f'Error al eliminar la tarea: {str(e)}')
        return render_template('error-bd.html')


@app.route('/job_autorizado/<int:id>')
# @login_required
def job_autorizado(id):
    # Recibir los parámetros de filtro
    iday = request.args.get('iday')
    imes = request.args.get('imes')
    iyear = request.args.get('iyear')
    fday = request.args.get('fday')
    fmes = request.args.get('fmes')
    fyear = request.args.get('fyear')
    employee = request.args.get('employee')
    project = request.args.get('project')
    estados = request.args.getlist('estados', )
    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE TAREA SET ESTADO='autorizado' WHERE UUID = %s", (str(id), ))
        cur.close()
        mysql.connection.commit()
        return redirect(url_for('lista', iday=iday, imes=imes, iyear=iyear, fday=fday, fmes=fmes, fyear=fyear, employee=employee, project=project, estados=estados))
    except Exception as e:
        print(f'Error al actualizar el estado de la tarea {str(e)} a "autorizado"')
        return render_template('error-bd.html')
    
@app.route('/job_pendiente/<int:id>')
# @login_required
def job_pendiente(id):
    # Recibir los parámetros de filtro
    iday = request.args.get('iday')
    imes = request.args.get('imes')
    iyear = request.args.get('iyear')
    fday = request.args.get('fday')
    fmes = request.args.get('fmes')
    fyear = request.args.get('fyear')
    employee = request.args.get('employee')
    project = request.args.get('project')
    estados = request.args.getlist('estados', )

    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE TAREA SET ESTADO='PENDIENTE' WHERE UUID = %s", (str(id), ))
        cur.close()
        mysql.connection.commit()
        return redirect(url_for('lista', iday=iday, imes=imes, iyear=iyear, fday=fday, fmes=fmes, fyear=fyear, employee=employee, project=project, estados=estados))
    except Exception as e:
        print(f'Error al actualizar el estado de la tarea {str(e)} a "PENDIENTE"')
        return render_template('error-bd.html')
    
@app.route('/job_nulo/<int:id>')
# @login_required
def job_nulo(id):
    # Recibir los parámetros de filtro
    iday = request.args.get('iday')
    imes = request.args.get('imes')
    iyear = request.args.get('iyear')
    fday = request.args.get('fday')
    fmes = request.args.get('fmes')
    fyear = request.args.get('fyear')
    employee = request.args.get('employee')
    project = request.args.get('project')
    estados = request.args.getlist('estados', )
    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE TAREA SET ESTADO='-' WHERE UUID = %s", (str(id), ))
        cur.close()
        mysql.connection.commit()
        return redirect(url_for('lista', iday=iday, imes=imes, iyear=iyear, fday=fday, fmes=fmes, fyear=fyear, employee=employee, project=project, estados=estados))
    except Exception as e:
        print(f'Error al actualizar el estado de la tarea {str(e)} a "sin estado"')
        return render_template('error-bd.html')

#FORM'S INSERT
@app.route('/insert_project', methods=['POST'])
# @login_required
def new_project():
    if request.method == 'POST':
        try:
            empleado = request.form['empleado']
            proyecto = request.form['project']
            descripcion = request.form['descripcion']
            precio_unitario = float(request.form['precio'])
            cantidad = float(request.form['cantidad'])
            unidad = request.form['unit']
            if (request.form['descuento']) == "Si":
                descuento = precio_unitario * cantidad
                liquido = 0
                isr = 0
                iva = 0
                total_facturar = 0
                total_iva = 0
            else:
                descuento = 0.0
                liquido = precio_unitario * cantidad
                isr = liquido * 0.05
                iva = liquido * 0.12
                total_facturar = liquido + isr + iva
                total_iva = liquido + iva
            estado = request.form['estado']
            if (estado is None or estado  == ''):
                estado = "-"
            fecha = request.form['fecha']
            cur = mysql.connection.cursor()
            proyecto_id = insert_proyecto(cur, proyecto)
            uuid_empleado = get_uuid_empleado(cur, empleado)
            if uuid_empleado is None:
                uuid_empleado = insert_empleado(cur, empleado)
            insert_tarea(cur, proyecto_id, uuid_empleado, descripcion, precio_unitario, cantidad, unidad, descuento, liquido, total_facturar, isr, iva, total_iva, estado, fecha)
            cur.close()
            mysql.connection.commit()
            print('El proyecto se ha insertado con éxito')
            flash('El proyecto se ha insertado con éxito', 'success')
        except Exception as e:
            return render_template('error-bd.html')
    return render_template('insert-ok.html')

@app.route('/insert_job', methods=['POST'])
# @login_required
def new_job():
    if request.method == 'POST':
        try:
            empleado = request.form['empleado']
            proyecto = request.form['project']
            descripcion = request.form['descripcion']
            precio_unitario = float(request.form['precio'])
            cantidad = float(request.form['cantidad'])
            unidad = request.form['unit']
            if (request.form['descuento']) == "Si":
                descuento = precio_unitario * cantidad
                liquido = 0
                isr = 0
                iva = 0
                total_facturar = 0
                total_iva = 0
            else:
                descuento = 0.0
                liquido = precio_unitario * cantidad
                isr = liquido * 0.05
                iva = liquido * 0.12
                total_facturar = liquido + isr + iva
                total_iva = liquido + iva
            estado = request.form['estado']
            if (estado is None or estado  == ''):
                estado = "-"
            fecha = request.form['fecha']
            cur = mysql.connection.cursor()
            uuid_empleado = get_uuid_empleado(cur, empleado)
            if uuid_empleado is None:
                uuid_empleado = insert_empleado(cur, empleado)
            insert_tarea(cur, proyecto, uuid_empleado, descripcion, precio_unitario, cantidad, unidad, descuento, liquido, total_facturar, isr, iva, total_iva, estado, fecha)
            cur.close()
            mysql.connection.commit()
            print('El trabajo se ha insertado con éxito')
            flash('El trabajo se ha insertado con éxito', 'success')
        except Exception as e:
            return render_template('error-bd.html')
    return redirect(url_for('lista'))

@app.route('/insert_unit', methods=['POST'])
# @login_required
def insert_unit():
    if request.method == 'POST':
        tipo_unidad = request.form['type-unit']
        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO UNIDAD (TIPO) VALUES (%s)", (tipo_unidad,))
            cur.close()
            mysql.connection.commit()
            print("Nueva unidad agregada")
            flash('Nueva unidad agregada', 'success')
        except Exception as e:  
            return redirect(url_for('lista_units'))
    return render_template('insert-ok.html')

#FORM'S UPDATE
@app.route('/update_job', methods=['POST'])
# @login_required
def update_job():
    #Variables
    uuid = request.form['uuid']
    descripcion = request.form['descripcion']
    precio_unitario = float(request.form['precio'])
    cantidad = float(request.form['cantidad'])
    unidad = request.form['unit']
    unidades = get_tipos_unidad()
    for value, data in unidades.items():
        if (data == unidad):
            unidad = value
    if (request.form['descuento']) == "Si":
        descuento = precio_unitario * cantidad
        liquido = 0
        isr = 0
        iva = 0
        total_facturar = 0
        total_iva = 0
    else:
        descuento = 0.0
        liquido = precio_unitario * cantidad
        isr = liquido * 0.05
        iva = liquido * 0.12
        total_facturar = liquido + isr + iva
        total_iva = liquido + iva
    estado = request.form['estado']
    fecha = request.form['fecha']
    try:
        #Consulta
        cur = mysql.connection.cursor()
        cur.execute("UPDATE TAREA SET DESCRIPCION=%s, PRECIO_UNITARIO=%s, CANTIDAD=%s, UUID_UNIDAD=%s, DESCUENTO=%s, LIQUIDO_RECIBIR=%s, TOTAL=%s, ISR=%s, IVA=%s, TOTAL_IVA=%s, ESTADO=%s, FECHA=%s WHERE UUID = %s",
            (descripcion, precio_unitario, cantidad, unidad, descuento, liquido, total_facturar, isr, iva, total_iva, estado, fecha, uuid))
        cur.close()
        mysql.connection.commit()
        print('Tarea actualizada')
    except Exception as e:
        return render_template('error-bd.html')
    return redirect(url_for('lista'))

@app.route('/update_unit', methods=['POST'])
# @login_required
def update_unit():
    #Variables
    uuid = request.form['uuid']
    tipo = request.form['tipo']
    try:
        #Consulta
        cur = mysql.connection.cursor()
        cur.execute("UPDATE UNIDAD SET TIPO=%s WHERE UUID = %s",
            (tipo, uuid))
        cur.close()
        mysql.connection.commit()
        print('Unidad de Medida Actualizada')
    except Exception as e:
        return render_template('error-bd.html')
    return redirect(url_for('lista_units'))

if __name__ == '__main__':
    app.run(debug=True)
