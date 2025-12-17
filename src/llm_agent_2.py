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
    titre: str = Field(description="Le titre de la recette")
    description_courte: str = Field(description="Une brève description de la recette")
    temps_prepa_minutes: int = Field(description="Le temps de préparation de la recette en minutes")

class RecetteDetails(BaseModel):
    name: str = Field(description="Le nom de la recette")
    ingredients: List[Ingredient] = Field(description="La liste des ingrédients de la recette")
    difficulty: str = Field(description="La difficulité de la recette")
    calories: int = Field(description="Le nombre de calories de la recette par portion")
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



# ============================================================================
# INSTRUCTION SYSTÈME
# ============================================================================

instruction_chef = """
Rôle : Tu es un Assistant Chef Cuisinier expert et créatif. Tu aimes des recettes de cuisines du monde entier, variées et délicieuses.
Objectif : Tu aides l'utilisateur à cuisiner avec ce qu'il a dans son frigo.

#Déroulement#:
La conversation va se dérouler en plusieurs états : "starting", "ingredient_collection", "recipe_proposal", "recipe_preview", "step_execution", "completed".
Tu seras averti de chaque changement d'état.

### RÈGLES D'OR ET PRIORITÉS ###

1.  **PRIORITÉ ABSOLUE À LA DEMANDE UTILISATEUR :** Avant de décider d'une action, analyse si l'utilisateur donne de nouveaux ingrédients ou s'il réagit à une proposition existante.

2.  **INTERDICTION D'ÉCRITURE :**
    * Ne JAMAIS écrire une recette complète ou une liste d'ingrédients détaillée dans le chat.
    * Ne JAMAIS répéter une proposition de recette que tu viens de faire.

3.  **DÉCLENCHEURS DE FONCTIONS (Logique stricte) :**

    * **CAS A : L'utilisateur donne des ingrédients / change d'avis sur les ingrédients / change le nombre de personnes.**
        -> Action : Tu DOIS appeler `propose_recipe_options`.
        -> Exemple : "J'ai du poulet", "En fait on est 3", "Je n'ai plus de lait".

    * **CAS B : L'utilisateur demande des précisions sur une des options proposées.**
        -> Indice : Il utilise des mots comme "la première", "la 2ème", "celle au curry", "plus de détails".
        -> Action : Tu DOIS appeler `more_details_on_recipe` (avec le numéro ou le nom).
        -> INTERDICTION : N'appelle PAS `propose_recipe_options` ici.
        -> INTERDICTION : N'appelle PAS `get_detailed_quantities`.

    * **CAS C : L'utilisateur valide/choisit une recette pour cuisiner.**
        -> Action : Tu DOIS appeler `valider_et_detaille_recette`.

    * **CAS D : L'utilisateur demande un minuteur.**
        -> Action : Tu DOIS appeler `lancer_minuteur`.

    * **CAS E : L'utilisateur demande explicitement de lancer la fonction get_ingredients_quantities pour une ou plusieurs recettes.**
        -> Action : Tu DOIS appeler `get_ingredients_quantities`.
        -> INTERDICTION : Tu n'appelleras pas 'get_ingredients_quantities' si l'utilisateur ne te demande pas explicitement de lancer cette fonction, en citant le nom de la fonction.

4.  **Navigation pas à pas :**
    * N'utilise `navigation_pas_a_pas` QUE dans les états "RECIPE_PREVIEW" ou "STEP_EXECUTION".
    * Si l'utilisateur dit "commencer", "go", "c'est parti" -> Action : `navigation_pas_a_pas` (DEMARRER).
    * Si l'utilisateur dit "suivant" -> Action : `navigation_pas_a_pas` (SUIVANT).
    * Si l'utilisateur dit "précédent" -> Action : `navigation_pas_a_pas` (PRECEDENT).

### Consignes de génération (Tone & Style) ###
1.  Par défait généres 4 suggestions variées lors de l'appel à `propose_recipe_options`. Mais ce nombre peut varier en fonction de la demande de l'utilisateur.
2.  Propose des recettes variées géographiquement et gustativement.
3.  Sois alléchant dans le titre et la description courte.
4.  Si tu viens d'afficher des recettes via une fonction, ne les résume pas à nouveau dans ta réponse textuelle. Invite plutôt l'utilisateur à en choisir une.

### Exemples de dialogue (Few-Shot) ###

Exemple 1:

Utilisateur : "Je veux une recette de poulet avec des pommes de terre."
Assistant : Bonjour ! C'est un duo classique et très réconfortant. Pour que je puisse ajuster les quantités et vous proposer les meilleures idées, pour combien de convives cuisinez-vous aujourd'hui ?
Utilisateur :"Deux personnes? J'ai des tomates aussi"
Assistant : C'est noté ! Du poulet, des pommes de terre et des tomates pour 2 personnes. C'est une base excellente qui offre plein de possibilités, du mijoté au rôti. Laissez-moi vous proposer 4 options variées pour sublimer ces ingrédients.
fonction propose_recipe_options lancée
Utilisateur :"Je veux plus de details sur la première recette"
Assistant : La premère recette est une délicieuse recette de poulet au curry avec des pommes de terre et des tomates. Très simple à faire elle ne demande que 20 minutes de préparation.  Vous auriez besoin d'une poele et d'une casserole. L'ingrédient magique de cette recette est le curry, car il sublime les saveurs des tomates et des pommes de terre. 

Utilisateur :"En fait je n'ai plus de poulet, mais j'ai du toffu"
Assistant : Aucun souci ! La cuisine, c'est aussi savoir s'adapter. Le tofu est une excellente alternative qui va très bien absorber les saveurs des tomates et accompagner les pommes de terre. Je change mon fusil d'épaule et je vous propose 4 nouvelles idées végétariennes et gourmandes.
fonction propose_recipe_options lancée
Utilisateur :"Dis moi en plus sur la deuxième recette"
Assistant : Celle-ci est très intéressante pour travailler la texture du tofu et le rendre gourmand. C'est une très ancienne recette indienne qui utilise le tofu, le concombre, le gingembre et la cibulette. Fait interessant, elle était servie à Buddah lors de son séjour dans la capitale Népalaise. 


Exemple 2:

Voici la simulation du dialogue :
Utilisateur :"J'ai des pommes de terre et du fenouil, proposes moi des recettes pour 3 personnes"
Assistant : Bonjour ! Pommes de terre et fenouil, c'est un mariage très élégant, le côté anisé du fenouil réveille la douceur de la pomme de terre. Pour 3 personnes, c'est parfait. Laissez-moi vous proposer 4 idées pour sublimer ce duo.
fonction propose_recipe_options lancée
Utilisateur :"Ah attends, en fait j'ai aussi des oeufs et du curry"
Assistant : Ça change tout, et en bien ! Le curry fonctionne à merveille avec le fenouil, et les œufs vont nous permettre d'avoir un plat complet et riche en protéines. Je mets à jour mes suggestions pour intégrer ces nouvelles saveurs épicées.
fonction propose_recipe_options lancée
Utilisateur :"Finalement on sera 5."
Assistant : C'est noté, on agrandit la tablée ! Avec 5 convives, on va privilégier des plats conviviaux ou faciles à partager. Je réajuste les quantités et le type de recettes pour que tout le monde se régale.
fonction propose_recipe_options lancée
Utilisateur :"Par quoi est-ce que je peux remplacer le premier ingrédient de la première recette"
Assistant : Si vous parlez des pommes de terre, vous pouvez très bien les remplacer par de la patate douce pour un résultat plus sucré qui s'accorde divinement avec le curry, ou même par du chou-fleur pour une version plus légère et "low carb". Le temps de cuisson sera juste un peu plus court !
Utilisateur :"Ok partons sur la deuxième recette finalement"
Assistant : Excellent choix ! C'est une recette savoureuse qui fait toujours l'unanimité. Je valide ce choix et je vous détaille tout ce qu'il faut savoir pour la réussir (ingrédients précis et étapes).
fonction valider_et_detaille_recette lancée


Exemple 3:
Utilisateur: "Salut Chef, je veux faire des pâtes ce soir, j'ai de la crème, des champignons et du parmesan."
Assistant : "Bonjour ! Un trio gagnant pour un dîner réconfortant. Pâtes, crème et champignons, c'est l'assurance d'une sauce onctueuse. Pour combien de personnes dois-je calibrer les recettes ?"
Utilisateur :"Nous sommes 2."
Assistant : "C'est noté, un dîner en tête-à-tête ou entre amis. Voici 4 variations autour de vos ingrédients pour sublimer vos pâtes."
fonction propose_recipe_options lancée
Utilisateur :"Ah par contre, je n'ai vraiment pas le temps, il me faut quelque chose de prêt en 15 min max."
Assistant : "Entendu ! On passe en mode "cuisine express". Je filtre mes idées pour ne garder que celles qui cuisent pendant que l'eau des pâtes bout. Voici 4 nouvelles propositions ultra-rapides."
fonction propose_recipe_options lancée
Utilisateur :"J'aime bien la deuxième recette, on part là-dessus."
Assistant : "Très bon choix pour un repas rapide et savoureux. Je vous prépare la liste précise et les étapes de réalisation."
fonction valider_et_detaille_recette lancée


Exemple 4:
Utilisateur:"Salut Chef, je veux faire des pâtes ce soir, j'ai de la crème, des champignons et du parmesan."
Assistant : "Bonjour ! Un trio gagnant pour un dîner réconfortant. Pâtes, crème et champignons, c'est l'assurance d'une sauce onctueuse. Pour combien de personnes dois-je calibrer les recettes ?"
Utilisateur :"Nous sommes 2."
Assistant : "C'est noté, un dîner en tête-à-tête ou entre amis. Voici 4 variations autour de vos ingrédients pour sublimer vos pâtes.
fonction propose_recipe_options lancée

Utilisateur :"Ah par contre, je n'ai vraiment pas le temps, il me faut quelque chose de prêt en 15 min max."
Assistant : "Entendu ! On passe en mode "cuisine express". Je filtre mes idées pour ne garder que celles qui cuisent pendant que l'eau des pâtes bout. Voici 4 nouvelles propositions ultra-rapides."
fonction propose_recipe_options lancée

"""


# ============================================================================
# FONCTIONS STANDALONE - Pour Google Generative AI
# ============================================================================

def propose_recipe_options(
    options: List[RecetteResume], 
    conseil_general: str
):
    """
    Utiliser cette fonction pour proposer 1 à 5 choix de recettes basées sur les ingrédients de l'utilisateur, pour un nombre de personnes fourni.
    Par défaut propose 4 recettes, sauf si l'utilisateur demande un nombre de recettes différent. 

    Args:
        options: Une liste d'objets recettes résumés.
        conseil_general: Un petit texte d'intro ou de conseil sur les ingrédients fournis (ex: "Vos tomates semblent mûres, profitez-en !").
    """
    # Dans la vraie vie, ici tu ne fais rien d'autre que retourner les données 
    # pour que ton Front-End les affiche.
    return "Options de recettes envoyées au client."

def more_details_on_recipe(
    recipe_name: str,
    recipe_details: str):

    """
    Utiliser cette fonction pour donner plus de détails ou explications sur une recette donnée.

    Args:
        recipe_name: Nom de la recette
        recipe_details: Un petit texte qui détaille la recette, explique rapidement ses ingrédients (pas besoin d'une liste detailée d'ingrédients ici) et les principales étapes de préparation.
        Et précise pourquoi cette recette est délicieuse, et comment l'améliorer d'avantage encore. 
    """
    return "Détails de la recette générés"
def get_ingredients_quantities(
    details: List[RecetteDetails]
    ):

    """
    Utiliser cette fonction uniquement quand l'utilisateur cite explicitement le nom de la fonction dans sa requête.


    Args: 
        
        details: Une liste d'objets recettes détaillés avec les champs ingrédients, difficulité et calories par portion.
    """
    return "Détails des recettes générés et affichés à l'utilisateur"

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
    Change l'état vers 'cooking_guidance'. Ne doit être appelée que dans l'état RECIPE_PROPOSAL.
    
    """
    # Cette fonction est uniquement utilisée comme signature pour Google Generative AI
    # Le traitement réel se fait dans get_response() de LLMAgent
    return "Recette validée et étapes de récette générées et affichés au client"

def navigation_pas_a_pas(action: NavigationAction):
    """
    Fonction pour contrôler l'affichage des étapes. Pas besoin d'ajouter du texte supplémentaire dans la réponse.
    À appeler UNIQUEMENT si l'utilisateur confirme vouloir commencer ou continuer le guidage pas à pas de la recette.
    Args:
        action: L'action à effectuer en fonction de la voloté de l'utilisateur (START, SUIVANT, PRECEDENT, STOP)
    
    """
    
   
    return "New action infered from user input"
# ============================================================================
# CLASSE LLM AGENT
# ============================================================================

class LLMAgent:
    def __init__(self, state_machine=None):
        # Stocker la référence au state_machine pour déterminer quels outils sont disponibles
        self.state_machine = state_machine
        
        # Outils de base toujours disponibles
        self.base_tools = [propose_recipe_options, get_ingredients_quantities, lancer_minuteur, valider_et_detaille_recette, navigation_pas_a_pas]
        
        # # Construire la liste d'outils initiale
        # tools_list = self._get_tools_for_current_state()
        
        # # Stocker la liste d'outils actuelle pour comparaison
        # self.current_tools = tools_list
        
        # On initialise le modèle avec les outils
        self.model = genai.GenerativeModel(
            'gemini-2.5-pro',
            tools=self.base_tools,
            system_instruction=instruction_chef
        )
        
        # Initialiser le chat
        self.chat = None
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
        # self._update_tools_if_needed()
        
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
                    if structured_data is None:
                        structured_data = {}
                    # Initialiser seulement la partie liée aux recettes pour ne pas écraser d'autres infos
                    if "recettes" not in structured_data:
                        structured_data["conseil"] = fn_args.get("conseil_general")
                        structured_data["recettes"] = []
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
                    if structured_data is None:
                        structured_data = {}
                    structured_data["timer_started"] = True
                    structured_data["duree_secondes"] = duree_secondes
                    structured_data["timer_name"] = label
             
                elif fn_name == 'get_ingredients_quantities':
                    print(f"\n[SYSTEME] 🔍 QUANTITÉS D'INGRÉDIENTS demandées par le LLM")
                    # Préparer / compléter une structure de données pour détailler chaque recette
                    if structured_data is None:
                        structured_data = {}
                    if "recipe" not in structured_data:
                        structured_data["recipe"] = []
                    details_list = fn_args.get("details") or []
                    for recipe in details_list:
                        name = recipe.get("name")
                        difficulty = recipe.get("difficulty")
                        calories = recipe.get("calories")
                        ingredients = recipe.get("ingredients") or []
                        ingredients_norm = []
                        for ingredient in ingredients:
                            ingredients_norm.append({
                                "name": ingredient.get("name"),
                                "quantity": ingredient.get("quantity"),
                                "unit": ingredient.get("unit"),
                                "available": ingredient.get("available"),
                            })
                        structured_data["recipe"].append({
                            "name": name,
                            "difficulty": difficulty,
                            "calories": calories,
                            "ingredients": ingredients_norm
                        })

                              
                elif fn_name == 'more_details_on_recipe':
                    print(f"\n[SYSTEME] 🔍 DETAILS DE LA RECETTE demandés par le LLM")
                    recipe_name = fn_args.get("recipe_name")
                    recipe_details = fn_args.get("recipe_details")
                    if structured_data is None:
                        structured_data = {}
                    structured_data["recipe_name"] = recipe_name
                    structured_data["recipe_details"] = recipe_details
                   
                    
                elif fn_name == 'valider_et_detaille_recette':
                    id_recette = fn_args.get("id_recette")
                    print(f"\n[SYSTEME] 🔒 VALIDATION DE RECETTE : {id_recette}")
                    recette_detaillee = fn_args.get("recette_detaillee")
                    if structured_data is None:
                        structured_data = {}
                    structured_data["recipe_confirmed"] = True  # Flag pour indiquer que la recette est confirmée
                    structured_data["id_recette"] = id_recette
                    structured_data["titre"] = recette_detaillee.get("titre") if recette_detaillee else None
                    structured_data["phrase_intro"] = recette_detaillee.get("phrase_intro") if recette_detaillee else None
                    structured_data["conseil_gourmand"] = recette_detaillee.get("conseil_gourmand") if recette_detaillee else None
                    structured_data["steps"] = recette_detaillee.get("steps") if recette_detaillee else None
                    if "details_techniques" not in structured_data:
                        structured_data["details_techniques"] = []
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
                    if structured_data is None:
                        structured_data = {}
                    structured_data["navigation_action"] = action
                    # Déterminer l'action à effectuer
                    if action == NavigationAction.SUIVANT:
                        structured_data["next_step"] = True
                    elif action == NavigationAction.PRECEDENT:
                        structured_data["previous_step"] = True
                    elif action == NavigationAction.DEMARRER:
                        structured_data["start_cooking"] = True
            
            # Cas B : Le modèle répond du texte (Erreur ou blabla)
            elif part.text:
                response_text = part.text
                
        # Retourner toujours un tuple, même si on n'a que des function_call sans texte
        return structured_data, response_text

    def notify_llm_without_response(self, notification_message: str):
        """
        Notifie le LLM qu'une notification a été envoyée sans attendre de réponse. Ne réponds pas.
        Args:
            notification_message: Message à envoyer au LLM
        """
        self.chat.send_message(notification_message)



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
    print("----------Je veux une recette de poulet avec des pommes de terre----------")
    print("Data: ", data)
    print("Response: ", response_txt)
    data, response_txt = agent.get_response("Deux personnes? J'ai des tomates aussi")
    print("----------Deux personnes? J'ai des tomates aussi----------")
    print("Data: ", data)
    print("Response: ", response_txt)
    
    notify_response = agent.notify_llm_function_completed("Les recettes ont été affichées à l'utilisateur. Il est en train de réfléchir", "propose_recipe_options")
    print("----------Je veux plus de details sur la première recette----------")
    data, response_txt = agent.get_response("Je veux plus de details sur la première recette")
    print("Data: ",data)
    print("Response: ", response_txt)
    
    data, response_txt = agent.get_response("En fait je n'ai plus de poulet, mais j'ai du toffu")
    print("----------En fait je n'ai plus de poulet, mais j'ai du toffu, changes les recettes----------")
    print("Data: ", data)
    print("Response: ", response_txt)

    data, response_txt = agent.get_response("Dis mois en plus sur la deuxième recette")
    print("----------Dis mois en plus sur la deuxième recette----------")
    print("Data: ", data)
    print("Response: ", response_txt)