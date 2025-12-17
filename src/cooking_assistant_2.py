import asyncio
import threading
import time
from pprint import pprint
from typing import Any
from states import StateMachine, CookingState
from llm_agent_2 import LLMAgent
from timer import CookingTimer
from hardware_handler import HardwareHandler
from plotly_gantt import PlotlyGanttVisualizer
from cooking_ui import CookingUI


class CookingAssistant:
    def __init__(self, ui: CookingUI):
        # We now always assume a UI implementation is provided
        self.ui = ui

        self.state_machine = StateMachine()
        self.agent = LLMAgent(state_machine=self.state_machine)

        # Timer and hardware no longer depend on a console
        self.timer = CookingTimer(console=None)
        self.hardware = HardwareHandler()
        self.gantt_visualizer = PlotlyGanttVisualizer(console=None)
     
        
        # Flag to signal the assistant to stop
        self._should_stop = threading.Event()
        
        # ========================================================================
        # EVENTS - For LLM function callbacks and user interactions
        # ========================================================================
        # Centralized event registry - all events declared here
        self._events = {
            'ingredients_available': threading.Event(),  # When propose_recipe_options is called
            'recipe_confirmed': threading.Event(),  # When valider_et_detaille_recette is called
            'timer_started': threading.Event(),  # When lancer_minuteur is called
            'user_input': threading.Event(),  # When user provides text input
        }
        
        # Storage for values associated with events
        self._event_data = {
            'ingredients_available': None,  # Stores data from propose_recipe_options
            "missing_ingredients": None,  # Stores data from ingredients_selected
            'recipe_confirmed': None,  # Stores data from valider_et_detaille_recette
            'timer_started': None,  # Stores data from lancer_minuteur
            'user_input': None,  # Stores user text input
        }
        # Storage for ingredients data
        self.ingredients_data = {
            'id_recette': None,
            'ingredients': [],  # List of dicts with keys: name, quantity, unit, available
            
        }
        
        
        # If running on a Raspberry Pi, set up button callbacks
        if self.hardware.is_raspi:
            print("✓ Raspberry Pi detected. Setting up GPIO buttons...\n")
            self._setup_button_controls()
    
    def _reset_events(self):
        """Reset all events and associated data values for a new session."""
        # Clear all events
        for event in self._events.values():
            event.clear()
        
        # Reset all stored values
        for key in self._event_data:
            self._event_data[key] = None
    
    def stop(self):
        """Signal the assistant to stop gracefully"""
        self._should_stop.set()
        
    def display_welcome(self):
        welcome_text = """
Yo la mif, je suis Robotatouille!
Je vous aiderai à découvrir de délicieuses recettes basées sur vos ingrédients disponibles et vous guiderai étape par étape tout au long du processus de cuisine. Commençons!
"""
        self.ui.show_text(welcome_text)
        


    def on_user_entry(self, input_text: str):
        """Handle user input - store it and signal the event"""
        print(f"User input: {input_text}")
        self._event_data['user_input'] = input_text  # Store the input value
        self._events['user_input'].set()  # Signal that user input has been received
    
    def _display_recipes(self, recipes_data: dict):
        """Display recipes in a nicely formatted way.
        
        Args:
            recipes_data: Dictionary containing 'conseil' and 'recettes' keys
        """
        # Display recipes nicely formatted
        if recipes_data.get('recettes'):
            self.ui.show_text("\n Voici les recettes que je vous propose :")
            
            for idx, recette in enumerate(recipes_data['recettes'], start=1):
                # Recipe header
                recipe_text = ""
                recipe_text += f"{idx}. {recette.get('titre', 'Recette sans titre')}"
                temps = recette.get('temps_prepa_minutes')
                recipe_text += f" - {temps} minutes "
                print("saving the recipes")
                self.state_machine.set_proposed_recipes(recipes_data['recettes'])
                   
               
              
                recipe_text += f"-"*120 + "\n"
                
                self.ui.show_text(recipe_text)

  
     
    def _display_recipe_steps(self, recipe_data: dict):
        """Display recipe steps in a nicely formatted way.
        
        Args:
            recipe_data: Dictionary containing decoded recipe data with:
                - 'titre': Recipe title
                - 'steps': List of step summaries
                - 'details_techniques': List of detailed step dictionaries
        """
        if not recipe_data:
            return
        

        # Display recipe title
        titre = recipe_data.get('titre', 'Recette')
        self.ui.show_text(f"{titre}")
        if recipe_data.get('phrase_intro'):
            self.ui.show_text(f"{recipe_data.get('phrase_intro')}")
        
        # Display step summaries
        steps = recipe_data.get('steps', [])
       
        for idx, step in enumerate(steps, start=1):
            self.ui.show_text(f"  {int(idx)}. {step}")
        self.ui.show_text("")
        
        if recipe_data.get('conseil_gourmand'):
            self.ui.show_text(f"{recipe_data.get('conseil_gourmand')}")
        
       


    
    def get_detailed_ingredients(self, list_of_recipes: list):
        data, text_response = self.agent.get_response("donne moi la liste des ingrédients detaillées pour toutes les recettes de la liste suivante: " + str(list_of_recipes))
        return data

    def notify_llm_with_loading(self, loading_message: str, notification_message: str, function_name: str = None):
        
        self.ui.show_loading(loading_message)
        try:
            if function_name is None:
                self.agent.notify_llm_without_response(notification_message)
            else:
                self.agent.notify_llm_function_completed(notification_message, function_name)
        finally:
            self.ui.hide_loading()
            self.ui.show_text(f"\n :)")
        
    def display_cooking_steps(self):
        if not self.state_machine.recipe_steps:
            self.ui.show_error("Aucune étape de préparation disponible.")
            return
        
        # Use UI method to show steps
        self.ui.show_steps(self.state_machine.recipe_steps, current_step=self.state_machine.current_step)
        
    def execute_current_step(self):
        current_step = self.state_machine.get_current_step()
        print(f"Current step: {current_step}")
        
        if not current_step:
            self.ui.show_text("C'est fini! Il ne reste plus d'étapes!\n")
            return False
            
        step_num = self.state_machine.current_step + 1
        total_steps = len(self.state_machine.recipe_steps)
        
        self.ui.show_text(f"\nÉtape {step_num}/{total_steps}:\n")
        self.ui.show_text(f"{current_step['description']}\n")
        self.ui.show_text(f"{current_step['conseil']}\n")
         # Show loading indicator
        notification_message = (
            f"[Systeme][INFO CONTEXTE - NE PAS REPONDRE] "
            f"On vient d'afficher le texte {current_step['description'] + current_step['conseil']} "
            f"dans le cadre de l'étape {step_num} de la recette selectionnée. "
            f"On attends la confirmation de l'utilisateur pour passer à l'étape suivante."
        )
        print("Notifying the llm of the cooking step we just displayed")    
        self.notify_llm_with_loading("Il faut tenir au courant le modèle de l'étape en cours...", notification_message)
        # self.ui.show_loading("Il faut tenir au courant le modèle de l'étape en cours...")
        
       
        print("Notification complete, now checking if need timer")
        if current_step.get('timer_necessaire'):
            step_time = current_step.get('duree_estimee_minutes')
            self.ui.show_text(f"Voulez-vous lancer un timer pour cette étape? \n")
            self.agent.notify_llm_without_response(
                f"[Système][INFO CONTEXTE - NE PAS REPONDRE] "
                f"L'utilisateur a reçu la question : 'Voulez-vous lancer un timer de {step_time} pour cette étape ?' "
                f"Ne réponds pas, attends sa prochaine entrée. Si l'utilisateur veut un timer tu le lancera. Sinon, tu attends les prochains instructions."
            )
        else: print("Timer not needed")
           
        
        # If on Raspberry Pi, display button controls guide
        if self.hardware.is_raspi:
            print(
                "\nContrôles physiques:\n"
                "- Bouton sur GPIO 6: Next (passer à l'étape suivante)\n"
                "- Bouton sur GPIO 19: Help (obtenir de l'aide)\n"
                "- Bouton sur GPIO 0: Back/Cancel (annuler minuteur)\n"
            )
        

        
      
                
    def _setup_button_controls(self):
        """Set up button controls for GPIO pins."""
      
        
 
        
        # Start polling the buttons
        self.hardware.start_polling()
        print("✓ Button controls initialized\n")
    
 

 
    async def run(self):
        """Main chat loop - standard pattern for conversational UI."""
        # self.display_welcome()
        
        # Reset all events for a new run session
        self._reset_events()
        
        # Initial message to start the conversation
        try:
            self.ui.show_loading("Initialisation...")
            data, text_response = self.agent.get_response(
                "Tu as déjà été introduit comme Ratatouille, un assistant de cuisine intelligent et très gourmand. "
                "A toi maintenant de demander à l'utilisateur de quels ingrédients il/elle dispose et pour combien de personnes il/elle veut cuisiner"
            )
        finally:
            self.ui.hide_loading()
        
        if text_response:
            # Just show the prompt - process_command will handle input via on_user_entry
            self.ui.show_text(f"{text_response}\n")
        
        # Main chat loop - standard pattern
        ###########################################################################################################
        while True:
            # Check if we should stop
            if self._should_stop.is_set():
                break
            # Wait for user input (standard async pattern)
            while not self._events['user_input'].is_set():
                await asyncio.sleep(0.1)
            # Retrieve the user input value
            user_input = self._event_data['user_input']
            # Reset the event and value for next iteration
            self._events['user_input'].clear()
            self._event_data['user_input'] = None
            if not user_input:
                continue
            print(f"User said: {user_input}")
            # Get LLM response with loading indicator
            try:
                self.ui.show_loading("Recherche d'une réponse...")
                data, text_response = self.agent.get_response(user_input)
            finally:
                self.ui.hide_loading()
            # Handle structured data (function calls)
            if data:
                # Handle different types of structured responses
                if 'details' in data:
                    print("ingredient details found in data")
                    print(data["details"])
                if 'conseil' in data:
                    self.ui.show_text(data['conseil'])
                if 'recettes' in data:  # propose_recipe_options was called
                    self._event_data['ingredients_available'] = data
                    self._events['ingredients_available'].set()
                    # Display recipes using dedicated method
                    self._display_recipes(data)
                    
                    # Stocker la liste complète des recettes proposées dans la state machine
                    self.state_machine.set_proposed_recipes(data.get("recettes", []))
                    
                    # Transition vers RECIPE_PROPOSAL
                    self.state_machine.transition_to(CookingState.RECIPE_PROPOSAL)
                    self.agent.notify_llm_without_response(
                        f"[Systeme][INFO CONTEXTE - NE PAS REPONDRE] On passe à l'état {self.state_machine.current_state.value}"
                    )
                    self.agent.notify_llm_function_completed(
                        "Les recettes ont été affichées à l'utilisateur. Il est en train de réfléchir et va choisir une recette.",
                        "propose_recipe_options"
                    )
                    
                    # Demander au LLM de générer les quantités d'ingrédients pour chaque recette proposée
                    recepies_list = [recipe.get("titre") for recipe in self.state_machine.proposed_recipes]
                    print(f"Recipes list: {recepies_list}")
                    prompt_ingredients = (
                        "Pour chacune des recettes suivantes, tu dois IMPÉRATIVEMENT appeler la fonction "
                        "get_ingredients_quantities.\n"
                        "Pour chaque recette, tu construis un objet RecetteDetails avec :\n"
                        "- name = titre de la recette\n"
                        "- ingredients = une liste d'ingrédients avec quantité et unité\n"
                        "- difficulty et calories adaptés\n"
                        "Ne réponds PAS en texte libre, utilise uniquement get_ingredients_quantities.\n"
                        f"Liste des recettes : {recepies_list}"
                    )
                    ingredients_data, _ = self.agent.get_response(prompt_ingredients)
                    # ingredients_data is a dict with key "recipe" containing a LIST of
                    # detailed recipe dicts:
                    # {"recipe": [{"name", "difficulty", "calories", "ingredients": [...]}, ...]}
                    if ingredients_data and "recipe" in ingredients_data:
                        detailed_ingredients = ingredients_data["recipe"]
                        self.state_machine.add_ingredients(detailed_ingredients)
                        print("Ingredient quantities generated by LLM:")
                        pprint(self.state_machine.ingredients)
                       
                    else:
                        # Unexpected format – log for debugging but don't crash the flow
                        print("Unexpected ingredients_data format returned by LLM:", ingredients_data)
                if 'timer_started' in data and data.get('timer_started'):
                    # Lancer le minuteur avec les données reçues
                    duree_secondes = data.get('duree_secondes')
                    timer_name = data.get('timer_name', 'Minuteur')
                    
                    if duree_secondes:
                        timer_id = self.timer.start_timer(duree_secondes, timer_name)
                        # Stocker les données complètes avec le timer_id généré
                        self._event_data['timer_started'] = {
                            'timer_id': timer_id,
                            'duree_secondes': duree_secondes,
                            'timer_name': timer_name
                        }
                        self._events['timer_started'].set()
                        # Afficher le décompte du minuteur dans l'UI
                        if hasattr(self.ui, 'show_timer_countdown'):
                            self.ui.show_timer_countdown()
                        self.agent.notify_llm_function_completed("Le minuteur a été lancé", "lancer_minuteur")
                if 'recipe_confirmed' in data and data.get('recipe_confirmed'):
                    #sauvegarder l'id de la recette dans la machine à états
                    self.state_machine.select_recipe(data.get('titre'))
                    
                    # valider_et_detaille_recette was called
                    # Decode the recipe steps data according to RecetteSteps and EtapePreparation models
                    decoded_recipe = {
                        'id_recette': data.get('id_recette'),
                        'titre': data.get('titre'),
                        'phrase_intro': data.get('phrase_intro'),
                        'conseil_gourmand': data.get('conseil_gourmand'),
                        'steps': data.get('steps', []),  # List of step summaries
                        'details_techniques': []
                    }
                    
                    # Decode each EtapePreparation from details_techniques
                    if data.get('details_techniques'):
                        for detail in data.get('details_techniques', []):
                            decoded_step = {
                                'numero': detail.get('numero'),
                                'description': detail.get('description'),
                                'conseil': detail.get('conseil', ''),
                                'duree_estimee_minutes': detail.get('duree_estimee_minutes', 0),
                                'timer_necessaire': detail.get('timer_necessaire', False),
                                'dependencies': detail.get('dependencies', [])
                                
                            }
                            decoded_recipe['details_techniques'].append(decoded_step)
                    
                    # Store the decoded recipe data
                    self._event_data['recipe_confirmed'] = decoded_recipe
                    self._events['recipe_confirmed'].set()
                    
                    
                  
                    
                    # Display the recipe steps nicely in the UI
                    self._display_recipe_steps(decoded_recipe)
                    recipe_name = self.state_machine.selected_recipe
                    # Retrieve the detailed ingredients for the selected recipe
                    ingredients = self.state_machine.get_ingredients_for_recipe(recipe_name)
                    self.ui.show_ingredients(ingredients)
                    # Transition vers RECIPE_PREVIEW (le log sera fait par transition_to)
                    self.state_machine.transition_to(CookingState.RECIPE_PREVIEW)
                    self.agent.notify_llm_without_response(f"[Systeme][INFO CONTEXTE - NE PAS REPONDRE] On passe à l'état {self.state_machine.current_state.value}")
                    self.agent.notify_llm_function_completed("La recette a été confirmée et les étapes détaillées ont été générées", "valider_et_detaille_recette")
                # Gérer la navigation pas à pas
                if 'navigation_action' in data and self.state_machine.current_state != CookingState.RECIPE_PROPOSAL:
                    action = data.get('navigation_action')
                    if data.get('next_step'):
                        if self.state_machine.next_step():
                           self.execute_current_step()
                       
                        self.agent.notify_llm_function_completed(f"Passage à l'étape suivante", "navigation_pas_a_pas")
                    elif data.get('previous_step'):
                        if self.state_machine.previous_step():
                            self.execute_current_step()
                        self.agent.notify_llm_function_completed(f"Retour à l'étape précédente", "navigation_pas_a_pas")
                    elif data.get('start_cooking'):
                        if self.state_machine.current_state == CookingState.RECIPE_PREVIEW:
                            self.state_machine.transition_to(CookingState.STEP_EXECUTION)
                            self.agent.notify_llm_without_response(f"[Systeme][INFO CONTEXTE - NE PAS REPONDRE] On passe à l'état {self.state_machine.current_state.value}")
                            cooking_steps = []
                            recipe_data = self._event_data.get('recipe_confirmed', {})
                            for step in recipe_data.get('details_techniques', []):
                                cooking_steps.append(step)
                            self.state_machine.set_recipe_steps(cooking_steps)
                            self.execute_current_step()
                        else: 
                            data, text_response = self.agent.get_response("Nous ne sommes pas dans l'état RECIPE_PREVIEW. On ne peut pas démarrer la préparation.")
                            if text_response:
                                self.ui.show_text(f"{text_response}\n")
                        self.agent.notify_llm_function_completed("Démarrage de la préparation", "navigation_pas_a_pas")
                    elif data.get('stop_cooking'):
                        self.state_machine.transition_to(CookingState.RECIPE_PREVIEW)
                        self.agent.notify_llm_without_response(f"[Systeme][INFO CONTEXTE - NE PAS REPONDRE] On passe à l'état {self.state_machine.current_state.value}")
                        self.agent.notify_llm_function_completed("Arrêt de la préparation", "navigation_pas_a_pas")
                    elif data.get('repeat_step'):
                        self.execute_current_step()
                        self.agent.notify_llm_function_completed("Répétition de l'étape actuelle", "navigation_pas_a_pas")
                elif 'navigation_action' in data and self.state_machine.current_state == CookingState.RECIPE_PROPOSAL:
                    print("Navigation function called during a wrong state - ignoring it")
                    self.agent.notify_llm_function_completed("Navigation function called during a wrong state - ignoring it", "navigation_pas_a_pas")
            # Display text response - process_command will handle next input via on_user_entry
            if text_response:
                self.ui.show_text(f"{text_response}\n")
                
            
   