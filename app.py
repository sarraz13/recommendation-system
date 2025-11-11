
from flask import Flask, render_template, request, redirect, url_for, session, flash
from recommendation import generer_recommendations, get_user_based_recommendations, get_item_based_recommendations
  # Include the item-based function
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection, assign_product_images
import psycopg2

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Changer en prod

# ----------- Authentification utilisateur -----------
@app.route('/set_metric', methods=['POST'])
def set_metric():
    if request.method == 'POST':
        metric = request.form['metric']
        session['current_metric'] = metric
        flash(f"Métrique de similarité changée en : {metric}", "info")
    return redirect(request.referrer or url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = None
        cur = None
        try:
            conn = get_connection()
            cur = conn.cursor()

            # Vérification explicite de l'existence
            cur.execute("SELECT id_user FROM users WHERE login = %s", (username,))
            if cur.fetchone():
                flash(" Ce nom d'utilisateur est déjà utilisé", "error")
                return redirect(url_for('register'))

            # Création du compte
            hashed_pw = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (login, password, email, date_inscription) VALUES (%s, %s, %s, NOW()) RETURNING id_user",
                (username, hashed_pw, f"{username}@example.com")
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            
            # Connexion automatique après inscription
            session['user_id'] = user_id
            session['username'] = username
            flash(" Inscription réussie !", "success")
            return redirect(url_for('index'))

        except Exception as e:
            if conn:
                conn.rollback()
            flash(f" Erreur lors de l'inscription : {str(e)}", "error")
            app.logger.error(f"Register error: {str(e)}")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id_user, password FROM users WHERE login = %s", (username,))
        user = cur.fetchone()

        if user and check_password_hash(user[1], password_input):
            session['user_id'] = user[0]
            session['username'] = username
            flash(" Connexion réussie !")
            return redirect(url_for('index'))
        else:
            flash(" Identifiants incorrects.")
        
        cur.close()
        conn.close()
    return render_template('login.html')


@app.route('/product/<int:product_id>/rate', methods=['POST'])
def noter_produit(product_id):
    if "user_id" not in session:
        flash("Vous devez être connecté pour noter.", "error")
        return redirect(url_for('login'))

    try:
        note = int(request.form.get("note"))
        user_id = session["user_id"]
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Debug: Afficher les valeurs reçues
        print(f"Tentative d'insertion : user_id={user_id}, product_id={product_id}, note={note}")
        
        cur.execute("""
            INSERT INTO notes (id_user, id_pdt, note)
            VALUES (%s, %s, %s)
            ON CONFLICT (id_user, id_pdt)
            DO UPDATE SET note = EXCLUDED.note
        """, (user_id, product_id, note))
        
        conn.commit()
        flash(" Note enregistrée avec succès !", "success")
    except Exception as e:
        conn.rollback()
        print(f"Erreur lors de l'enregistrement : {e}")
        flash(" Échec de l'enregistrement de la note.", "error")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('product_details', product_id=product_id))


@app.route('/logout')
def logout():
    session.clear()
    flash("🔒 Déconnecté avec succès.")
    return redirect(url_for('login'))


# ----------- Pages principales -----------

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Utilise la métrique de session ou 'cosine' par défaut
    current_metric = session.get('current_metric', 'cosine')
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM produit")
    produits = cur.fetchall()

    # Passez la métrique aux fonctions de recommandation
    produits_similaires = get_item_based_recommendations(
        [p['id_pdt'] for p in produits],
        similarity_metric=current_metric
    )
    
    produits_recommande = []
    if 'user_id' in session:
        produits_recommande = get_user_based_recommendations(
            session['user_id'],
            similarity_metric=current_metric
        )
    
    cur.close()
    conn.close()

    return render_template(
        "index.html",
        produits=produits,
        produits_similaires=produits_similaires,
        produits_recommande=produits_recommande,
        current_metric=current_metric
    )

@app.route('/user/<int:user_id>')
def user_recommendation(user_id):
    if 'user_id' not in session or session['user_id'] != user_id:
        flash("⚠️ Accès refusé.")
        return redirect(url_for('login'))

    conn = get_connection()
    cur = conn.cursor()

    product_id = 9583  # À adapter
    cur.execute("""
    SELECT p.nom_pdt, r.priorite, p2.nom_pdt AS produit_similaire
    FROM recommendation r
    JOIN produit p ON r.id_produit = p.id_pdt
    JOIN produit p2 ON r.id_similaire = p2.id_pdt
    WHERE r.id_produit = %s
    """, (product_id,))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("user.html", user_id=user_id, recommendations=results)

@app.route('/product/<int:product_id>')
def product_details(product_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get product info
    cur.execute("SELECT * FROM produit WHERE id_pdt = %s", (product_id,))
    produit = cur.fetchone()

    # Get rating stats
    cur.execute("""
        SELECT COUNT(*) AS total_votes, COALESCE(AVG(note), 0) AS moyenne
        FROM notes
        WHERE id_pdt = %s
    """, (product_id,))
    note_stats = cur.fetchone()

    # Get similar products from recommendation table
    current_metric = session.get('current_metric', 'cosine')
    cur.execute("""
    SELECT p.* 
    FROM recommendation r
    JOIN produit p ON r.id_similaire = p.id_pdt
    WHERE r.id_produit = %s AND r.metric = %s
    ORDER BY r.priorite DESC
    LIMIT 4
    """, (product_id, current_metric))
    produits_similaires = cur.fetchall()
    

    # Get user-based recommendations
    produits_recommande = []
    if 'user_id' in session:
        user_id = session['user_id']
        produits_recommande = get_user_based_recommendations(user_id)
        print(produits_recommande)
    cur.close()
    conn.close()

    return render_template(
        'product_details.html',
        produit=produit,
        note_stats=note_stats,
        produits_similaires=produits_similaires,
        produits_recommande=produits_recommande
    )



@app.route('/admin/generate_recommendations')
def generate_recommendations():
    generer_recommendations(top_n=4)
    return "✅ Recommandations générées avec succès !"


if __name__ == '__main__':
    app.run(debug=True, port=8000)
