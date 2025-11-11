import os
from PIL import Image
import matplotlib.pyplot as plt
from db import get_connection


image_folder = "templates/img"

output_folder = "sauvegardes_images"
os.makedirs(output_folder, exist_ok=True)


for filename in os.listdir(image_folder):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        try:
            # Chemin complet de l'image
            img_path = os.path.join(image_folder, filename)
            
            # Ouvrir l'image
            img = Image.open(img_path)
            
            # Afficher l'image
            plt.figure(figsize=(10, 6))
            plt.imshow(img)
            plt.title(f"Affichage de : {filename}")
            plt.axis('off')
            plt.show()
            
           
            new_size = (img.width // 2, img.height // 2)  
            img_resized = img.resize(new_size)
            
            # Chemin de sauvegarde
            save_path = os.path.join(output_folder, f"resized_{filename}")
            img_resized.save(save_path)
            print(f"Image sauvegardée : {save_path}")
            
        except Exception as e:
            print(f"Erreur avec le fichier {filename}: {str(e)}")