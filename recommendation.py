import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import nltk
from nltk.corpus import stopwords
from nltk.stem.snowball import FrenchStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial import distance
from scipy.stats import pearsonr
from collections import defaultdict

nltk.download('punkt')
nltk.download('stopwords')

def generer_recommendations(user_id=None, produits=None, top_n=4, metric='cosine'):
    """Génère des recommandations selon le type demandé"""
    if user_id:
        return get_user_based_recommendations(user_id, similarity_metric=metric)
    if produits:
        return get_item_based_recommendations(produits, top_n, similarity_metric=metric)
    return []

def get_item_based_recommendations(produits, top_n=4, similarity_metric='cosine'):
    """Recommandations basées sur les items avec TF-IDF"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="sr_new",
            user="postgres",
            password="000000"
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

      
        cursor.execute("""
            SELECT id_pdt, nom_pdt, description 
            FROM produit 
            WHERE id_pdt = ANY(%s)
        """, (produits,))
        produits_data = cursor.fetchall()

        if not produits_data:
            return []

       
        stop_words = set(stopwords.words('french'))
        stemmer = FrenchStemmer()
        processed_docs = []
        product_map = {}

        for p in produits_data:
            desc = p['description'].lower()
            tokens = nltk.word_tokenize(desc)
            stems = [stemmer.stem(t) for t in tokens if t.isalpha()]
            filtered = [w for w in stems if w not in stop_words]
            processed_docs.append(' '.join(filtered))
            product_map[p['id_pdt']] = p

      
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(processed_docs)
        
    
        if similarity_metric == 'cosine':
            sim_matrix = cosine_similarity(tfidf_matrix)
        elif similarity_metric == 'jaccard':
            sim_matrix = _jaccard_similarity(tfidf_matrix)
        elif similarity_metric == 'euclidean':
            sim_matrix = _euclidean_similarity(tfidf_matrix)
        elif similarity_metric == 'correlation':
            sim_matrix = _pearson_similarity(tfidf_matrix)
        else:
            sim_matrix = cosine_similarity(tfidf_matrix)

        recommendations = set()
        product_ids = [p['id_pdt'] for p in produits_data]

        for i, pid in enumerate(product_ids):
            similar_indices = np.argsort(-sim_matrix[i])[1:top_n+1]
            for idx in similar_indices:
                if sim_matrix[i][idx] > 0:
                    similar_id = product_ids[idx]
                    recommendations.add(similar_id)
                    cursor.execute("""
                        INSERT INTO recommendation 
                        (id_produit, id_similaire, priorite, metric)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (id_produit, id_similaire) 
                        DO UPDATE SET priorite = EXCLUDED.priorite
                    """, (pid, similar_id, sim_matrix[i][idx], similarity_metric))

        # Récupération des produits recommandés
        if recommendations:
            cursor.execute("SELECT * FROM produit WHERE id_pdt = ANY(%s)", (list(recommendations),))
            return cursor.fetchall()
        
        return []

    except Exception as e:
        print(f"Erreur item-based: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_user_based_recommendations(user_id, similarity_metric='cosine'):
    """Recommandations basées sur les utilisateurs"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="sr_new",
            user="postgres",
            password="000000"
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)


        # Construction de la matrice utilisateur-produit

        cursor.execute("SELECT id_pdt FROM produit ORDER BY id_pdt")
        all_products = [r['id_pdt'] for r in cursor.fetchall()]
        product_idx = {pid: i for i, pid in enumerate(all_products)}

        cursor.execute("SELECT id_user FROM users")
        all_users = [r['id_user'] for r in cursor.fetchall()]
        user_idx = {uid: i for i, uid in enumerate(all_users)}

        rating_matrix = np.zeros((len(all_users), len(all_products)))

        cursor.execute("SELECT id_user, id_pdt, note FROM notes")
        for r in cursor.fetchall():
            if r['id_user'] in user_idx and r['id_pdt'] in product_idx:
                rating_matrix[user_idx[r['id_user']], product_idx[r['id_pdt']]] = r['note']

       


        if similarity_metric == 'cosine':
            user_sim = cosine_similarity(rating_matrix)
        elif similarity_metric == 'jaccard':
            user_sim = _jaccard_similarity((rating_matrix > 0).astype(int))
        elif similarity_metric == 'euclidean':
            user_sim = _euclidean_similarity(rating_matrix)
        elif similarity_metric == 'correlation':
            user_sim = _pearson_similarity(rating_matrix)
        else:
            user_sim = cosine_similarity(rating_matrix)

        
        if user_id not in user_idx:
            return []

        u_idx = user_idx[user_id]
        predictions = []

        for p_idx, pid in enumerate(all_products):
            if rating_matrix[u_idx, p_idx] != 0:
                continue  

        



            similar_users = []
            for other_u in range(len(all_users)):
                if other_u == u_idx:
                    continue
                if rating_matrix[other_u, p_idx] > 0:
                    similarity = user_sim[u_idx, other_u]
                    similar_users.append((similarity, rating_matrix[other_u, p_idx]))

            if not similar_users:
                continue

         


            similar_users.sort(reverse=True)
            top_sim = [s for s,_ in similar_users[:2]]
            top_ratings = [r for _,r in similar_users[:2]]
            
            if sum(top_sim) > 0:
                pred = np.dot(top_sim, top_ratings) / sum(top_sim)
                if pred > 3:  # Seuil
                    predictions.append((pid, pred))

      


        predictions.sort(key=lambda x: -x[1])
        if predictions:
            cursor.execute("SELECT * FROM produit WHERE id_pdt = ANY(%s)", 
                         ([p[0] for p in predictions[:10]],))
            return cursor.fetchall()
        
        return []

    except Exception as e:
        print(f"Erreur user-based: {str(e)}")
        return []
    finally:
        cursor.close()
        conn.close()


def _jaccard_similarity(X):
    """Similarité de Jaccard entre les lignes"""
    intersection = X @ X.T
    union = (X + X.T > 0).sum(axis=1) - intersection
    return intersection / union

def _euclidean_similarity(X):
    """Similarité basée sur la distance euclidienne"""
    dist = distance.cdist(X, X, 'euclidean')
    return 1 / (1 + dist)

def _pearson_similarity(X):
    """Similarité par corrélation de Pearson"""
    n = X.shape[0]
    sim = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            sim[i,j] = 0.5 * (pearsonr(X[i], X[j])[0] + 1)  
    return sim