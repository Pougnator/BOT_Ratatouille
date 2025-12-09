import google.generativeai as genai
import os

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

print("🔍 MODÈLES DISPONIBLES :")
for m in genai.list_models():
    # On filtre pour ne garder que ceux qui font du chat (generateContent)
    if 'generateContent' in m.supported_generation_methods:
        # On nettoie le nom (on enlève 'models/')
        clean_name = m.name.replace("models/", "")
        print(f"👉 '{clean_name}'")