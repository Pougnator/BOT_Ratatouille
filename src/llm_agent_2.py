import google.generativeai as genai
import os
from typing import List
from states import StateMachine, CookingState
from pydantic import BaseModel, Field
from google.ai.generativelanguage_v1beta.types import content
from dotenv import load_dotenv
from enum import Enum
# Charger les variables d'environnement depuis .env
load_dotenv()

# Configuration de l'API (doit être fait au niveau du module, comme dans test_gemini_functions.py)
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables. Please set it in .env file or environment.")
genai.configure(api_key=api_key)

# ============================================================================
# MODÈLES PYDANTIC - Définis en premier
# ============================================================================
class Ingredient(BaseModel):
    name: str = Field(description="Nom de l'ingrédient")
    quantity: int = Field(description="Quantité de l'ingrédient")
    unit: str = Field(description="Unité de mesure de l'ingrédient")
    available: bool = Field(description="True si l'ingrédient est disponible, False sinon")
class RecetteResume(BaseModel):
    id: str = Field(description="L'identifiant unique de la recette")
    titre: str = Field(description="Le titre de la recette")
    description_courte: str = Field(description="Une brève description de la recette")
    ingredients: List[Ingredient] = Field(description="La liste des ingrédients de la recette")
    temps_prepa_minutes: int = Field(description="Le temps de préparation de la recette en minutes")


class EtapePreparation(BaseModel):
    numero: int = Field(description="Numéro de l'étape")
    description: str = Field(description="Instruction détaillée de l'action")
    conseil: str = Field(description="Conseil technique ou gourmand pour cette étape")
    duree_estimee_minutes: int = Field(description="Temps estimé pour cette étape spécifique")
    timer_necessaire: bool = Field(description="True si un minuteur est conseillé pour cette étape")
    dependencies: List[str] = Field(description="Liste des étapes préalables à cette étape")


class RecetteSteps(BaseModel):
    titre: str = Field(description="Le nom de la recette")
    phrase_intro: str = Field(description="Une phrase courte pour introduire la recette")
    steps: List[str] = Field(description="Liste résumée des étapes")
    details_techniques: List[EtapePreparation] = Field(description="Détails techniques structurés pour l'application")
    conseil_gourmand: str = Field(description="Conseil gourmand final court à l'utilsateur sur la recette avant de passer à la préparation")

class NavigationAction(str, Enum):
    DEMARRER = "DEMARRER"
    SUIVANT = "SUIVANT"
    PRECEDENT = "PRECEDENT"
    REPETER = "REPETER"
    STOP = "STOP"


# ============================================================================
# INSTRUCTION SYSTÈME
# ============================================================================

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

Navigation pas à pas :
Quand tu es dans l'état COOKING_GUIDANCE ou STEP_EXECUTION, tu peux utiliser la fonction navigation_pas_a_pas pour guider l'utilisateur :
- Si l'utilisateur dit "ok", "go", "commence", "démarre", "c'est parti" ou exprime qu'il veut commencer la préparation, appelle navigation_pas_a_pas avec l'action DEMARRER.
- Si l'utilisateur dit "suivant", "next", "étape suivante", appelle navigation_pas_a_pas avec l'action SUIVANT.
- Si l'utilisateur dit "précédent", "back", "étape précédente", appelle navigation_pas_a_pas avec l'action PRECEDENT.
- Si l'utilisateur dit "répète", "repeat", "encore", appelle navigation_pas_a_pas avec l'action REPETER.
- Si l'utilisateur dit "stop", "arrête", appelle navigation_pas_a_pas avec l'action STOP.
"""


# ============================================================================
# FONCTIONS STANDALONE - Pour Google Generative AI
# ============================================================================

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

def lancer_minuteur(duree_secondes: int, label: str):
    """
    Lance un minuteur pour une étape de cuisson.
    
    Args:
        duree_secondes: Durée du minuteur en secondes
        label: Nom/description du minuteur
    """
    print(f"\n[SYSTEME] ⏱️ TIMER LANCÉ : {duree_secondes} secondes pour '{label}'")
    return f"Minuteur de {duree_secondes} secondes lancé pour '{label}'."

def valider_et_detaille_recette(id_recette: str, recette_detaillee: RecetteSteps):
    """
    Valide le choix de l'utilisateur et génère les étapes détaillées, ainsi qu'une phrase d'introduction de la recette et un conseil gourmand final.
    Change l'état vers 'cooking_guidance'.
    
    Note: Cette fonction ne devrait pas modifier l'état directement.
    Le changement d'état devrait être géré dans cooking_assistant_2.py.
    """
    # Cette fonction est uniquement utilisée comme signature pour Google Generative AI
    # Le traitement réel se fait dans get_response() de LLMAgent
    return "Recette validée et étapes de récette générées et affichés au client"

def navigation_pas_a_pas(action: NavigationAction):
    """
    Fonction pour contrôler l'affichage des étapes.
    À appeler UNIQUEMENT si l'utilisateur confirme vouloir commencer ou continuer le guidage pas à pas de la recette.
    Args:
        action: L'action à effectuer en fonction de la voloté de l'utilisateur (START, SUIVANT, PRECEDENT, STOP)
    Returns:
        La réponse à l'action
    """
    #Ici on gère la navigation pas à pas lorsque nous sommes dans l'état COOKING_GUIDANCE
    #Si l'utilisateur confirme avoir terminé une étape, ou bien qu'il veut passer à l'étape suivante, on passe à l'étape suivante
    if action == NavigationAction.SUIVANT:
        return "next_step"
# ============================================================================
# CLASSE LLM AGENT
# ============================================================================

class LLMAgent:
    def __init__(self, state_machine=None):
        # Stocker la référence au state_machine pour déterminer quels outils sont disponibles
        self.state_machine = state_machine
        
        # Outils de base toujours disponibles
        self.base_tools = [propose_recipe_options, lancer_minuteur, valider_et_detaille_recette]
        
        # Outils conditionnels (disponibles selon l'état)
        self.conditional_tools = {
            CookingState.COOKING_GUIDANCE: [navigation_pas_a_pas],
            CookingState.STEP_EXECUTION: [navigation_pas_a_pas],
        }
        
        # Construire la liste d'outils initiale
        tools_list = self._get_tools_for_current_state()
        
        # Stocker la liste d'outils actuelle pour comparaison
        self.current_tools = tools_list
        
        # On initialise le modèle avec les outils
        self.model = genai.GenerativeModel(
            'gemini-2.5-pro',
            tools=tools_list,
            system_instruction=instruction_chef
        )
        
        # Initialiser le chat
        self.chat = None
        # On démarre le chat en mode automatique (le modèle gère l'appel)
        self.chat = self.model.start_chat(enable_automatic_function_calling=False)
    
    def _get_tools_for_current_state(self):
        """
        Construit la liste d'outils en fonction de l'état actuel.
        Cette méthode lit self.state_machine.current_state à chaque appel,
        donc elle reflète toujours l'état actuel, même si l'état a changé depuis l'init.
        """
        tools = list(self.base_tools)
        
        if self.state_machine:
            # Lire l'état actuel (pas l'état à l'init)
            current_state = self.state_machine.current_state
            # Ajouter les outils conditionnels pour l'état actuel
            if current_state in self.conditional_tools:
                tools.extend(self.conditional_tools[current_state])
        
        return tools
    
    def _update_tools_if_needed(self):
        """Met à jour le chat avec les outils appropriés si l'état a changé."""
        if not self.state_machine:
            return
        
        current_tools = self._get_tools_for_current_state()
        # Vérifier si les outils ont changé en comparant les noms des fonctions
        current_tool_names = {tool.__name__ for tool in current_tools}
        previous_tool_names = {tool.__name__ for tool in self.current_tools}
        
        # Si les outils sont différents, recréer le modèle et le chat
        if current_tool_names != previous_tool_names:
            # Sauvegarder l'historique du chat pour le restaurer
            chat_history = []
            if self.chat and hasattr(self.chat, 'history'):
                chat_history = list(self.chat.history)  # Copier l'historique
            
            # Recréer le modèle avec les nouveaux outils
            self.model = genai.GenerativeModel(
                'gemini-2.5-pro',
                tools=current_tools,
                system_instruction=instruction_chef
            )
            
            # Mettre à jour la liste d'outils actuelle
            self.current_tools = current_tools
            
            # Recréer le chat en préservant l'historique
            self.chat = self.model.start_chat(
                history=chat_history,
                enable_automatic_function_calling=False
            )
            
            print(f"[SYSTEME] 🔧 Outils mis à jour pour l'état {self.state_machine.current_state.value}: {[tool.__name__ for tool in current_tools]} (historique préservé: {len(chat_history)} messages)")

    def get_response(self, user_input: str):
        # Mettre à jour les outils si l'état a changé depuis le dernier appel
        # Cette vérification se fait à chaque interaction, donc les outils sont toujours à jour
        self._update_tools_if_needed()
        
        structured_data = None
        response_text = None
        response = self.chat.send_message(user_input)
        for part in response.candidates[0].content.parts:
             # Cas A : Le modèle veut appeler une fonction (C'est ce qu'on veut !)
            if part.function_call:
                fn_name = part.function_call.name
                fn_args = part.function_call.args

                #Si la fonction est la liste de proposition de recettes
                if fn_name == 'propose_recipe_options':
                    print(f"\n[SYSTEME] 📋 PROPOSITION DE RECETTES demandée par le LLM")
                    structured_data = {
                        "conseil": fn_args.get("conseil_general"),
                        "recettes": []
                    }
                    # On boucle sur la liste des recettes proposées par l'IA
                    # (fn_args est un objet spécial Map de Google, on le transforme en dict)
                    for recette in fn_args.get("options"):
                        ingredients = recette.get("ingredients") or []
                        # Normaliser les ingrédients en dict {name, quantity, unit}
                        ingredients_norm = []
                        for ing in ingredients:
                            try:
                                ingredients_norm.append({
                                    "name": ing.get("name"),
                                    "quantity": ing.get("quantity"),
                                    "unit": ing.get("unit"),
                                    "available": ing.get("available"),
                                })
                            except Exception as e:
                                print(f"[SYSTEME] 🔴 Erreur lors de la normalisation des ingrédients: {e}")
                                continue
                            

                 

                        structured_data["recettes"].append({
                            "id": recette.get("id"),
                            "titre": recette.get("titre"),
                            "ingredients": ingredients_norm,
                            "temps_prepa_minutes": recette.get("temps_prepa_minutes"),

                            # "difficulte": recette.get("difficulte"),
                            # "calories_par_pers": recette.get("calories_par_pers")
                        })
                    print(f"[SYSTEME] ✓ {len(structured_data['recettes'])} recettes préparées pour affichage")
                elif fn_name == 'lancer_minuteur':
                    # Détecter l'appel de lancer_minuteur et préparer les données pour l'event
                    duree_secondes = fn_args.get("duree_secondes")
                    label = fn_args.get("label")
                    print(f"\n[SYSTEME] ⏱️ TIMER LANCÉ : {duree_secondes} secondes pour '{label}'")
                    structured_data = {
                        "timer_started": True,
                        "duree_secondes": duree_secondes,
                        "timer_name": label
                    }
                elif fn_name == 'valider_et_detaille_recette':
                    id_recette = fn_args.get("id_recette")
                    print(f"\n[SYSTEME] 🔒 VALIDATION DE RECETTE : {id_recette}")
                    recette_detaillee = fn_args.get("recette_detaillee")
                    structured_data = {
                        "recipe_confirmed": True,  # Flag pour indiquer que la recette est confirmée
                        "id_recette": id_recette,
                        "titre": recette_detaillee.get("titre") if recette_detaillee else None,
                        "phrase_intro": recette_detaillee.get("phrase_intro") if recette_detaillee else None,
                        "conseil_gourmand": recette_detaillee.get("conseil_gourmand") if recette_detaillee else None,
                        "steps": recette_detaillee.get("steps") if recette_detaillee else None,
                        "details_techniques": []
                    }
                     # On boucle sur la liste des détails techniques
                    if recette_detaillee and recette_detaillee.get("details_techniques"):
                        for detail in recette_detaillee.get("details_techniques"):
                            structured_data["details_techniques"].append({
                                "numero": detail.get("numero"),
                                "description": detail.get("description"),
                                "conseil": detail.get("conseil"),
                                "duree_estimee_minutes": detail.get("duree_estimee_minutes"),
                                "timer_necessaire": detail.get("timer_necessaire"),
                                "dependencies": detail.get("dependencies", [])
                            })
                    print(f"[SYSTEME] ✓ Recette validée avec {len(structured_data['details_techniques'])} étapes détaillées")
                elif fn_name == 'navigation_pas_a_pas':
                    action = fn_args.get("action")
                    print(f"\n[SYSTEME] 🧭 NAVIGATION PAS À PAS : {action}")
                    structured_data = {
                        "navigation_action": action
                    }
                    # Déterminer l'action à effectuer
                    if action == NavigationAction.SUIVANT:
                        structured_data["next_step"] = True
                    elif action == NavigationAction.PRECEDENT:
                        structured_data["previous_step"] = True
                    elif action == NavigationAction.DEMARRER:
                        structured_data["start_cooking"] = True
                    elif action == NavigationAction.STOP:
                        structured_data["stop_cooking"] = True
                    elif action == NavigationAction.REPETER:
                        structured_data["repeat_step"] = True
            # Cas B : Le modèle répond du texte (Erreur ou blabla)
            elif part.text:
                response_text = part.text
                
        # Retourner toujours un tuple, même si on n'a que des function_call sans texte
        return structured_data, response_text

    def notify_llm_function_completed(self, output_message: str, function_name: str):
        """
        Notifie le LLM qu'une fonction a été exécutée avec succès.
        C'est essentiel pour maintenir le contexte de conversation.
        
        Args:
            output_message: Message décrivant ce qui s'est passé (ex: "Les recettes ont été affichées")
            function_name: Nom de la fonction qui a été appelée (ex: "propose_recipe_options")
        
        Returns:
            La réponse du modèle après avoir reçu la notification
        """
        # On construit la réponse de la fonction pour l'IA
        function_response = {
            "output": output_message
        }

        # On renvoie ça à l'IA pour clore le tour de parole
        # Le modèle attend cette réponse pour savoir que la fonction a été exécutée
        response_post_fonction = self.chat.send_message(
            content.Content(
                parts=[
                    content.Part(
                        function_response=content.FunctionResponse(
                            name=function_name,
                            response=function_response
                        )
                    )
                ]
            )
        )
        
        return response_post_fonction


if __name__ == "__main__":
    agent = LLMAgent()
    data, response_txt = agent.get_response("Je veux une recette de poulet avec des pommes de terre")
    print("Data: ", data)
    print("Response: ", response_txt)
    data, response_txt = agent.get_response("Deux personnes? J'ai des tomates aussi")
    print("Data: ", data)
    print("Response: ", response_txt)
    print(response_txt)
    notify_response = agent.notify_llm_function_completed("Les recettes ont été affichées à l'utilisateur. Il est en train de réfléchir", "propose_recipe_options")
    data, response_txt = agent.get_response("Je veux plus de details sur la première recette")
    print("Data: ",data)
    print("Response: ", response_txt)
    
    data, response_txt = agent.get_response("En fait je n'ai plus de poulet, mais j'ai du toffu")
    print("Data: ", data)
    print("Response: ", response_txt)