import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    return psycopg2.connect(
        dbname='SR',
        user='postgres',
        password='szbn12345?',
        host='localhost',
        port='5432'
    )

def assign_product_images():
    """Associe automatiquement les images aux produits en utilisant le nom complet"""
    print("⏳ Début de l'association des images...")
    
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Créer le dossier des images
        image_dir = os.path.abspath(os.path.join('static', 'images', 'products'))
        os.makedirs(image_dir, exist_ok=True)
        print(f"📁 Dossier images: {image_dir}")

        # 2. Récupérer tous les produits
        cur.execute("SELECT id_pdt, nom_pdt FROM produit")
        products = {p['nom_pdt']: p['id_pdt'] for p in cur.fetchall()}
        print(f"🛒 {len(products)} produits dans la base")

        # 3. Associer chaque image à son produit
        for filename in os.listdir(image_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                try:
                    # Retirer l'extension pour avoir le nom brut
                    product_name = os.path.splitext(filename)[0]
                    
                    # Trouver l'ID correspondant au nom du produit
                    product_id = products.get(product_name)
                    
                except Exception as e:
                    print(f"⚠️ Erreur avec {filename}: {str(e)}")
                    continue
        
        conn.commit()
        
    except Exception as e:
        print(f" Erreur critique: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()