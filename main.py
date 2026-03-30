from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

app = Flask(__name__)
app.secret_key = "secret_key"


@app.context_processor
def inject_user():
    return {'user': session.get('username')}

menu = [
    {"name": "msemen kefta", "price": 620.00, "description": "msemen avec kefta"},
    {"name": "chawarma", "price": 507.99, "description": "chat avec warma"},
    {"name": "couscous royale", "price": 750.00, "description": "coucous avec sauce royale"},
    {"name": "Futu-banane", "price": 890.99, "description": "futu avec banane"},
    {"name": "street food indienne importé des rues de Mumbaï", "price": 0.50, "description": "street food indienne 100% safe"},
]

users = {}
reservations = {}
orders = {}
avis_list = []

@app.route('/')
def index():
    conn = get_db_connection()

    avis = conn.execute('SELECT * FROM avis ORDER BY id DESC').fetchall()

    if 'username' in session:
        username = session['username']
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        # Si l'utilisateur n'existe plus (DB reset), on déconnecte
        if user is None:
            session.pop('username', None)
            conn.close()
            return redirect(url_for('index'))

        user_id = user['id']

        user_orders_raw = conn.execute('SELECT * FROM orders WHERE user_id = ?', (user_id,)).fetchall()
        user_reservations = conn.execute('SELECT * FROM reservations WHERE user_id = ?', (user_id,)).fetchall()

        user_orders = []
        for order in user_orders_raw:
            plats = conn.execute('SELECT plat_name FROM order_items WHERE order_id = ?', (order['id'],)).fetchall()
            order_dict = dict(order)
            order_dict['plats'] = [p['plat_name'] for p in plats]
            user_orders.append(order_dict)

        conn.close()
        return render_template('index.html', avis_list=avis, user=username, orders=user_orders, reservations=user_reservations)

    conn.close()
    return render_template('index.html', avis_list=avis, user=None)


@app.route('/menu')
def afficher_menu():
    return render_template('menu.html', menu=menu)

@app.route('/plat/<plat_name>')
def plat_detail(plat_name):
    plat = next((p for p in menu if p["name"] == plat_name), None)
    if plat:
        return render_template('plat_detail.html', plat=plat)
    return redirect(url_for('afficher_menu'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if existing_user:
            conn.close()
            return render_template('register.html', error_message="Cette username est déjà pris.")

        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        conn.commit()
        conn.close()
        

        session['username'] = username
        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('index'))

        error_message = "Username ou mot de passe incorrect."
        return render_template('login.html', error_message=error_message)

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/reservation', methods=['GET', 'POST'])
def reservation():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (session['username'],)).fetchone()

    if request.method == 'POST':
        nom = request.form['nom']
        date = request.form['date']
        heure = request.form['heure']
        personnes = request.form['personnes']

        conn.execute('INSERT INTO reservations (user_id, nom, date, heure, personnes) VALUES (?, ?, ?, ?, ?)',
                     (user['id'], nom, date, heure, personnes))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    conn.close()
    return render_template('reservation.html')



@app.route('/commande', methods=['GET', 'POST'])
def commande():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

    if request.method == 'POST':
        plats_selectionnes = request.form.getlist('plats')
        adresse = request.form['adresse']
        telephone = request.form['telephone']

        total = sum([plat['price'] for plat in menu if plat['name'] in plats_selectionnes])

        cursor = conn.execute('INSERT INTO orders (user_id, total, adresse, telephone) VALUES (?, ?, ?, ?)',
                              (user['id'], total, adresse, telephone))
        order_id = cursor.lastrowid

        for plat_name in plats_selectionnes:
            conn.execute('INSERT INTO order_items (order_id, plat_name) VALUES (?, ?)', (order_id, plat_name))

        conn.commit()
        conn.close()

        return redirect(url_for('confirmation', order_id=order_id))

    conn.close()
    return render_template('commande.html', menu=menu)


@app.route('/confirmation/<int:order_id>')
def confirmation(order_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db_connection()

    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    order = conn.execute('SELECT * FROM orders WHERE id = ? AND user_id = ?', (order_id, user['id'])).fetchone()
    plats = conn.execute('SELECT plat_name FROM order_items WHERE order_id = ?', (order_id,)).fetchall()

    conn.close()

    if order:
        return render_template('confirmation.html', nom=username, order=order, plats=[p['plat_name'] for p in plats])

    return redirect(url_for('index'))


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        nom = request.form['nom']
        email = request.form['email']
        message = request.form['message']
        return redirect(url_for('index'))
    return render_template('contact.html')

@app.route('/ajouter_avis', methods=['POST'])
def ajouter_avis():
    nom_form = request.form.get('nom', '').strip()
    commentaire = request.form['commentaire']

    # Si l'utilisateur a écrit un nom, on l'utilise
    if nom_form:
        nom = nom_form
    # Sinon, on prend le username de session s'il existe
    elif 'username' in session:
        nom = session['username']
    # Sinon, Anonyme
    else:
        nom = "Anonyme"

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO avis (nom, message) VALUES (?, ?)',
        (nom, commentaire)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=8000)
