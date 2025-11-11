import psycopg2
import random
from datetime import datetime, timedelta
from faker import Faker
import numpy as np
from decimal import Decimal


DB_CONFIG = {
    'dbname': 'SR',
    'user': 'postgres',
    'password': 'szbn12345?',  
    'host': 'localhost',
    'client_encoding': 'utf8'
}


fake = Faker()
random.seed(42) 

def recreate_tables(conn):
    """Recrée les tables users et notes"""
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS notes, users CASCADE")
        
        cur.execute("""
        CREATE TABLE users (
            id_user SERIAL PRIMARY KEY,
            login VARCHAR(50) UNIQUE,
            password VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            date_inscription TIMESTAMP
        )
        """)
        
        cur.execute("""
        CREATE TABLE notes (
            id_note SERIAL PRIMARY KEY,
            id_user INTEGER REFERENCES users(id_user),
            id_pdt INTEGER,
            note INTEGER CHECK (note BETWEEN 1 AND 5),
            date_note TIMESTAMP,
            CONSTRAINT unique_user_product UNIQUE (id_user, id_pdt)
        )
        """)
        conn.commit()

def generate_users(conn, num_users=100):
    """Génère des utilisateurs avec des comportements prix définis"""
    groups = [
        ('budget', 0.4, (0, 300)),   
        ('standard', 0.4, (200, 800)), 
        ('premium', 0.2, (600, 9999))  
    ]
    
    with conn.cursor() as cur:
        for i in range(1, num_users + 1):
            # Choix du groupe
            rand = random.random()
            for group in groups:
                if rand < group[1]:
                    groupe = group[0]
                    price_range = group[2]
                    break
                rand -= group[1]
            
            # Données utilisateur
            login = f"user_{i}"
            email = f"user_{i}@example.com"
            date_inscription = fake.date_time_between(start_date='-2y', end_date='now')
            
            cur.execute(
                "INSERT INTO users (login, password, email, date_inscription) VALUES (%s, %s, %s, %s)",
                (login, "hashed_password_123", email, date_inscription)
            )
        conn.commit()
    return groups

def generate_notes(conn, groups):
    """Génère des notes basées sur les préférences de prix des groupes"""
    with conn.cursor() as cur:
        # Récupère tous les produits avec leur prix
        cur.execute("SELECT id_pdt, prix FROM produit")
        products = cur.fetchall()
        
        # Récupère tous les utilisateurs
        cur.execute("SELECT id_user, email FROM users")
        users = cur.fetchall()
        
        for user_id, email in users:
            # Détermine le groupe de l'utilisateur
            user_num = int(email.split("@")[0].split("_")[1])
            group_index = min(int(user_num / (100 / len(groups))), len(groups)-1)
            price_range = groups[group_index][2]
            
            # Convertit le price_range en Decimal pour les calculs
            price_min = Decimal(str(price_range[0]))
            price_max = Decimal(str(price_range[1]))
            
            # Sélectionne des produits aléatoires mais biaisés
            eligible_products = []
            for p in products:
                prix = p[1] if isinstance(p[1], Decimal) else Decimal(str(p[1]))
                if price_min <= prix <= price_max:
                    eligible_products.append((p[0], float(prix)))  # Convertit en float pour les calculs
            
            # Si pas assez de produits dans la fourchette, élargir
            if len(eligible_products) < 5:
                eligible_products = [(p[0], float(p[1] if isinstance(p[1], Decimal) else Decimal(str(p[1])))) for p in products]
            
            num_notes = random.randint(10, 20)
            selected_products = random.sample(eligible_products, min(num_notes, len(eligible_products)))
            
            for id_pdt, prix in selected_products:
                # Calcul de la note basée sur la compatibilité prix/groupe
                mid_range = (price_min + price_max) / 2
                price_diff = abs(Decimal(str(prix))) - mid_range
                range_width = price_max - price_min
                
                if range_width > 0:
                    base_note = 5 - float(price_diff / range_width) * 4
                else:
                    base_note = 3  # Valeur par défaut si la fourchette est trop petite
                
                note = int(np.clip(np.random.normal(base_note, 0.7), 1, 5))
                
                date_note = fake.date_time_between(
                    start_date=datetime.now() - timedelta(days=365),
                    end_date='now'
                )
                
                cur.execute(
                    "INSERT INTO notes (id_user, id_pdt, note, date_note) VALUES (%s, %s, %s, %s)",
                    (user_id, id_pdt, note, date_note)
                )
        conn.commit()

def main():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("Tables recréées avec succès")
        
        groups = generate_users(conn)
        print(f"{len(groups)} groupes d'utilisateurs créés")
        
        generate_notes(conn, groups)
        print("Notes générées avec comportements prix")
        
    except Exception as e:
        print(f"Erreur : {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()