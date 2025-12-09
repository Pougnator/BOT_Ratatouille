import google.generativeai as genai
import os
import typing
from typing import List, TypedDict
from states import StateMachine, CookingState
from google.ai.generativelanguage_v1beta.types import content
from pydantic import BaseModel, Field
from typing import List
import time
import json
from pprint import pprint
from google.generativeai.types import generation_types

DEBUG = True


class RecetteResume(BaseModel):
    id: str = Field(description="L'identifiant unique de la recette")
    titre: str = Field(description="Le titre de la recette")
    description_courte: str = Field(description="Une brève description de la recette")
    ingredients_complets: List[str] = Field(description="La liste des ingrédients complets de la recette")
    ingredients_manquants: List[str] = Field(description="La liste des ingrédients manquants de la recette")
    temps_prepa_minutes: int = Field(description="Le temps de préparation de la recette en minutes")
    # difficulte: str = Field(description="Le niveau de difficulté de la recette")
    # calories_par_pers: int = Field(description="Le nombre de calories par personne de la recette")

# NOUVEAU : On définit la structure d'une étape proprement
class EtapePreparation(BaseModel):
    numero: int = Field(description="Numéro de l'étape")
    description: str = Field(description="Instruction détaillée de l'action")
    duree_estimee_minutes: int = Field(description="Temps estimé pour cette étape spécifique")
    timer_necessaire: bool = Field(description="True si un minuteur est conseillé pour cette étape")

class RecetteSteps(BaseModel):
    titre: str = Field(description="Le nom de la recette")
    steps: List[str] = Field(description="Liste résumée des étapes")
    # ICI : On utilise une vraie liste d'objets, pas une string JSON
    details_techniques: List[EtapePreparation] = Field(description="Détails techniques structurés pour l'application")


state_machine = StateMachine()

# 1. D'abord, tu mets ton prompt dans une variable propre
instruction_chef = """
Rôle : Tu es un Assistant Chef Cuisinier expert et créatif. Tu aimes des recettes de cuisines du monde entier, variées et délicieuses.
Objectif : Tu aides l'utilisateur à cuisiner avec ce qu'il a dans son frigo.

Règle d'OR :
Lorsque l'utilisateur te donne une liste d'ingrédients et un nombre de personnes, tu ne dois PAS écrire de recettes en texte.
Tu DOIS impérativement appeler la fonction propose_recipe_options.
Si l'utilisateur te demande des details sur une recettes, tu n'appelles PAS de fonction. Tu réponds simplement en texte.
Si l'utilisateur choisit une recette, tu DOIS impérativement appeler la fonction valider_et_detaille_recette. 
Consignes de génération :
1. Génère toujours 4 suggestions variées.
2. Le champ ingredients_complets doit être une liste JSON stricte et fiable.
3. N'invente pas d'ingrédients majeurs si l'utilisateur ne les a pas.
4. Sois alléchant dans le titre et la description_courte.
5. Tu n'est pas obligé de proposer des recettes avec tous les ingrédients fournis. Ce qui prime est la qualité des recettes et leur variété.

Lorsque l'utilisateur te demande de lancer un minuteur, tu DOIS impérativement appeler la fonction lancer_minuteur.
"""
def valider_et_detaille_recette(id_recette: str, recette_detaillee: RecetteSteps):
    """
    Valide le choix de l'utilisateur et génère les étapes détaillées.
    Change l'état vers 'cooking_guidance'.
    """
    current_state = state_machine.current_state
    
    # GARDE-FOU : On ne peut pas valider si on n'a pas d'abord cherché
    if current_state == CookingState.COOKING_GUIDANCE:
        return {"erreur": "Une recette est déjà en cours ! Demande à l'utilisateur s'il veut l'annuler d'abord."}
        
    state_machine.current_state = CookingState.COOKING_GUIDANCE
    print(f"\n[SYSTEME] Verrouillage de la recette {id_recette}. Passage en mode CUISSON.")
    
    return { "Recette validée et étapes de récette générées et affichés au client"
        
    }



# Voici la fonction principale que l'outil va appeler
def propose_recipe_options(
    options: List[RecetteResume], 
    conseil_general: str
):
    """
    
    Utiliser cette fonction pour proposer 3 à 5 choix de recettes basées sur les ingrédients de l'utilisateur, pour un nombre de personnes fourni.
    
    Args:
        options: Une liste d'objets recettes résumés.
        conseil_general: Un petit texte d'intro ou de conseil sur les ingrédients fournis (ex: "Vos tomates semblent mûres, profitez-en !").
    """
    # Dans la vraie vie, ici tu ne fais rien d'autre que retourner les données 
    # pour que ton Front-End les affiche.
    return "Options de recettes envoyées au client."

def lancer_minuteur(duree_minutes: int, label: str):
    """
    Lance un minuteur pour une étape de cuisson.
    """
    
    print(f"\n[SYSTEME] ⏱️ TIMER LANCÉ : {duree_minutes} minutes pour '{label}'")
    return {"status": "Succès", "message": f"Le minuteur de {duree_minutes} min sonnera à la fin."}


# Configuration (assure-toi d'avoir ta clé API)
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# On met la fonction dans une liste d'outils
tools_list = [propose_recipe_options, lancer_minuteur, valider_et_detaille_recette]

# On initialise le modèle avec les outils
model = genai.GenerativeModel(
        'gemini-2.5-flash',
        tools=tools_list,
        system_instruction=instruction_chef
    )

# On vérifie chaque partie de la réponse
def verify_response(response):
    data_pour_frontend = None
    response_text = None
    
    for part in response.candidates[0].content.parts:
        
        # Cas A : Le modèle veut appeler une fonction (C'est ce qu'on veut !)
        if part.function_call:
            fn_name = part.function_call.name
            fn_args = part.function_call.args
            
            if fn_name == 'propose_recipe_options':
                # BINGO ! On a nos données.
                
                # 1. On convertit les arguments en dictionnaire Python propre
                # (fn_args est un objet spécial Map de Google, on le transforme en dict)
                data_pour_frontend = {
                    "conseil": fn_args.get("conseil_general"),
                    "recettes": []
                }
                
                # On boucle sur la liste des recettes proposées par l'IA
                for recette in fn_args.get("options"):
                    data_pour_frontend["recettes"].append({
                        "id": recette.get("id"),
                        "titre": recette.get("titre"),
                        "ingredients": recette.get("ingredients_complets"),
                        "ingredients_manquants": recette.get("ingredients_manquants"),
                        "temps_prepa_minutes": recette.get("temps_prepa_minutes"),
                        # "difficulte": recette.get("difficulte"),
                        # "calories_par_pers": recette.get("calories_par_pers")
                    })
            
            elif fn_name == 'valider_et_detaille_recette':
                print("-" * 40)
                print(f"Recette detaillee: {fn_args.get('recette_detaillee')}")
                recette_detaillee = fn_args.get("recette_detaillee")
                data_pour_frontend = {
                    "id_recette": fn_args.get("id_recette"),
                    "titre": recette_detaillee.get("titre") if recette_detaillee else None,
                    "steps": recette_detaillee.get("steps") if recette_detaillee else None,
                    "details_techniques": []
                }
                
                # On boucle sur la liste des détails techniques
                if recette_detaillee and recette_detaillee.get("details_techniques"):
                    for detail in recette_detaillee.get("details_techniques"):
                        data_pour_frontend["details_techniques"].append({
                            "numero": detail.get("numero"),
                            "description": detail.get("description"),
                            "duree_estimee_minutes": detail.get("duree_estimee_minutes"),
                            "timer_necessaire": detail.get("timer_necessaire")
                        })

        # Cas B : Le modèle répond du texte (Erreur ou blabla)
        elif part.text:
            print("Texte reçu :", part.text)
            response_text = part.text
            
    return data_pour_frontend, response_text



def recipes_displayed(output_message: str):
    # On construit la réponse de la fonction pour l'IA
    function_response = {
        "output": output_message
    }

    # On renvoie ça à l'IA pour clore le tour de parole
    response_post_fonction = chat.send_message(
        content.Content(
            parts=[
                content.Part(
                    function_response=content.FunctionResponse(
                        name="propose_recipe_options",
                        response=function_response
                    )
                )
            ]
        )
    )
   
    return response_post_fonction
# On démarre le chat en mode automatique (le modèle gère l'appel)
chat = model.start_chat(enable_automatic_function_calling=False)
    
chat_response = chat.send_message('Hello, comment ca va?')
print(chat_response.text)
if DEBUG:
    start_time = time.time()
chat_response = chat.send_message('Oui je veux une recette pour deux personnes, jai des tomates et des carottes')
if DEBUG:
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")
recipe_data, response_text = verify_response(chat_response)
print("-" * 40)
print("Recipe data")
pprint(recipe_data)
print("recipe text")
print(response_text)
response_post_fonction = recipes_displayed("Les recettes ont été affichées à l'utilisateur. Il est en train de réfléchir")


chat_response = chat.send_message('Dis mois en plus sur la première')
print(chat_response.text)
if DEBUG:
    start_time = time.time()

try:
    chat_response = chat.send_message("En fait je n'ai plus de carottes, mais j'ai des pommes de terre")
except generation_types.StopCandidateException as e:
    print("\n🚨 ERREUR MALFORMED DÉTECTÉE 🚨")
    print("Voici ce que le modèle a essayé de générer avant de mourir :")
    
    # L'objet 'e' contient parfois le candidat fautif
    # On essaie d'accéder aux parts brutes
    try:
        # On regarde le premier candidat (celui qui a échoué)
        candidate = chat.last.candidates[0] # ou e.args[0] selon la version
        
        for part in candidate.content.parts:
            if part.function_call:
                print(f"Fonction visée : {part.function_call.name}")
                print("Arguments bruts (tels que parsés par Google) :")
                print(part.function_call.args)
            else:
                print("Texte brut :", part.text)
                
    except Exception as inner_e:
        print(f"Impossible de lire le candidat : {inner_e}")
        # Si on n'arrive pas à lire l'objet structuré, on affiche le dump brut
        print("Dump de l'erreur :", e)

if DEBUG: 
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")
recipe_data, response_text = verify_response(chat_response)
print("-" * 40)
print("Recipe data")
pprint(recipe_data)
print("recipe text")
print(response_text)
chat_response = chat.send_message("Je veux partir sur la deuxième")
recipe_data, response_text = verify_response(chat_response)
print("-" * 40)
print("Recipe data")
pprint(recipe_data)
print("recipe text")
print(response_text)
chat_response = chat.send_message('Tu peux mettre un timer de 10 min stp?')
