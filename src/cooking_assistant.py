import asyncio
import threading
import time
from .states import StateMachine, CookingState
from .llm_agent import LLMAgent
from .timer import CookingTimer
from .hardware_handler import HardwareHandler
from .plotly_gantt import PlotlyGanttVisualizer
from .cooking_ui import CookingUI


class CookingAssistant:
    def __init__(self, ui: CookingUI):
        # We now always assume a UI implementation is provided
        self.ui = ui

        self.state_machine = StateMachine()
        self.llm_agent = LLMAgent()

        # Timer and hardware no longer depend on a console
        self.timer = CookingTimer(console=None)
        self.hardware = HardwareHandler()
        self.gantt_visualizer = PlotlyGanttVisualizer(console=None)
        
        # Use threading Event objects for button communication
        self._next_button_event = threading.Event()
        
        # Flag to signal the assistant to stop
        self._should_stop = threading.Event()
        
        # If running on a Raspberry Pi, set up button callbacks
        if self.hardware.is_raspi:
            print("✓ Raspberry Pi detected. Setting up GPIO buttons...\n")
            self._setup_button_controls()
    
    def stop(self):
        """Signal the assistant to stop gracefully"""
        self._should_stop.set()
        
    def display_welcome(self):
        welcome_text = """
Hello, je suis Robotatouille!
Je vous aiderai à découvrir de délicieuses recettes basées sur vos ingrédients disponibles et vous guiderai étape par étape tout au long du processus de cuisine. Commençons!
"""
        self.ui.show_text(welcome_text)
        
    def display_state(self):
        state_name = self.state_machine.current_state.value.replace('_', ' ').title()
        print(f"\nCurrent State: {state_name}\n")
    
    async def collect_servings(self):
        """Collect number of servings - async version using UI callbacks"""
        def handle_servings_input(input_text: str):
            try:
                servings = int(input_text) 
                if servings > 0:
                    self.state_machine.set_servings(servings)
                    self.ui.show_success(f"On cuisine pour {servings} personnes")
                    # Signal that we're done
                    self._servings_collected.set()
                else:
                    self.ui.show_error("Veuillez entrer un nombre positif.")
                    # Ask again
                    self.ui.ask_text("Nombre de personnes: ", handle_servings_input)
            except ValueError:
                self.ui.show_error("Veuillez entrer un nombre valide.")
                # Ask again
                self.ui.ask_text("Nombre de personnes: ", handle_servings_input)
        
        # self.ui.show_text("Pour combien de personnes voulez-vous cuisiner?\n")
        self._servings_collected = threading.Event()
        self.ui.ask_text("Pour combien de personnes voulez-vous cuisiner?", handle_servings_input)
        
        # Wait for the callback to complete
        while not self._servings_collected.is_set():
            await asyncio.sleep(0.1)
    
    async def collect_ingredients(self):
        """Collect ingredients - async version using UI callbacks"""
        def handle_ingredients_input(input_text: str):
            ingredients = [ing.strip() for ing in input_text.split(',') if ing.strip()]
            if ingredients:
                self.state_machine.add_ingredients(ingredients)
                self.ui.show_success(f"J'ai ajouté {len(ingredients)} ingrédients")
                self._ingredients_collected.set()
            else:
                self.ui.show_error("Aucun ingrédient fourni. Veuillez réessayer.")
                # Ask again
                self.ui.ask_text("Vos ingrédients", handle_ingredients_input)
        
        self.ui.show_text("Quels ingrédients avez-vous sous la main?")
        # self.ui.show_text("Entrez les ingrédients séparés par des virgules (par exemple: oeufs, riz, tomates)")
        self._ingredients_collected = threading.Event()
        self.ui.ask_text("Entrez les ingrédients séparés par des virgules (par exemple: oeufs, riz, tomates)", handle_ingredients_input)
        
        # Wait for the callback to complete
        while not self._ingredients_collected.is_set():
            await asyncio.sleep(0.1)
            
    def propose_recipes(self):
        self.ui.show_text("\nAnalyse des ingrédients et recherche de recettes...\n")
        
        # Check if there's an additional recipe request
        additional_request = self.state_machine.additional_recipe_request
        
        # Show loading indicator
        self.ui.show_loading("Recherche de recettes...")
        
        try:
            recipes_response = self.llm_agent.propose_recipes(
                self.state_machine.ingredients,
                self.state_machine.servings,
                additional_request
            )
        finally:
            # Hide loading indicator
            self.ui.hide_loading()
        
        # Clear the additional request after using it
        self.state_machine.clear_additional_recipe_request()
        
        # Extract recipes list from response
        recipes_list = recipes_response.get("recipes", [])
        
        # Use UI method to display recipes
        self.ui.show_recipes(recipes_list)
            
        # Store recipes for selection
        self.state_machine.set_proposed_recipes(recipes_list)
        
    async def confirm_recipe(self):
        """Confirm recipe selection - async version using UI callbacks"""
        txt_confirm_recipe = """
        Quel recette voulez-vous cuisiner? 
        Entrez le numéro de la recette (1-4). Entrez 0 + instructions additionnelles pour demander plus de recettes
        """
        # self.ui.show_text("\nQuel recette voulez-vous cuisiner?\n")
        # self.ui.show_text("Entrez le numéro de la recette (1-4) ou le nom de la recette:\n")
        # self.ui.show_text("Entrez 0 + instructions additionnelles pour demander plus de recettes\n")
        
        # 1) On demande la saisie et on l'affiche dans l'UI (géré par ask_text / process_command)
        # 2) Une fois la saisie faite, on traite le choix de recette ici (sans callback spécifique coté UI)

        # Valeur et résultat du choix
        self._recipe_choice_result = False
        self._recipe_choice_value = None

        # Event pour synchroniser la coroutine avec la réponse de l'utilisateur
        self._recipe_confirmed = threading.Event()

        def _on_user_input(value: str):
            """Callback générique interne : stocke la valeur et réveille la coroutine.
            On ne fait AUCUN traitement de recette ici pour éviter tout effet visuel étrange.
            """
            self._recipe_choice_value = value
            self._recipe_confirmed.set()

        # Demander le texte à l'utilisateur ; l'UI gère l'affichage de la bulle de réponse
        self.ui.ask_text(txt_confirm_recipe, _on_user_input)

        # Attendre que l'utilisateur ait répondu
        while not self._recipe_confirmed.is_set():
            await asyncio.sleep(0.1)

        # Maintenant seulement, traiter le choix de recette
        self._recipe_choice_result = self._process_recipe_choice(self._recipe_choice_value)

        # Retourner le résultat du traitement
        return self._recipe_choice_result
    
    def _process_recipe_choice(self, choice: str):
        """Process the recipe choice (shared logic for UI and CLI)"""
        if not choice:
            print("Veuillez entrer un numéro de recette.")
            return False

        choice_str = choice.strip()

        # If the choice is a number, it is a recipe index. So it should be between 1 and 4
        # In which case we use it to select the recipe from the proposed recipes list
        if choice_str.isdigit():
            recipe_index = int(choice_str) - 1
            if 0 <= recipe_index < len(self.state_machine.proposed_recipes):
                # Récupérer le contenu de la recette choisie
                recipe_content = self.state_machine.proposed_recipes[recipe_index]
                self.state_machine.selected_recipe = recipe_content
                recipe_name = recipe_content.get("name", "Error: Recipe name not found")
            else:
                self.ui.show_error(f"Numéro de recette invalide. Veuillez choisir une recette de 1 à {len(self.state_machine.proposed_recipes)}")
                return False
        
        # If the choice is not a number, it is either an additional prompt (starting with 0)
        # or a question to the assistant.
        else:
            # Check if user wants more recipes (0 + optional extra prompt)
            if choice_str.startswith('0'):
                additional_prompt = choice_str[1:].strip()
                self.ui.show_text("\nRecherche de plus de recettes...\n")
                
                # Go back to the recipe proposal state
                self.state_machine.transition_to(CookingState.RECIPE_PROPOSAL)
                
                # If there's an additional prompt, store it for the LLM to use
                if additional_prompt:
                    self.state_machine.additional_recipe_request = additional_prompt
                    self.ui.show_text(f"Trouves d'autres recettes differentes de celles déjà proposées, avec précision: {additional_prompt}\n")
                else:
                    self.state_machine.additional_recipe_request = "Trouve des recettes differentes de celles déjà proposées"
                return False
            else:
                self.ask_question(choice_str)
                return False
        
        # À partir d'ici, on sait qu'on a une recette valide avec:
        # - recipe_content : le dictionnaire de la recette choisie
        # - recipe_name    : le nom de la recette
        
        # Get recipe steps from LLM
        # Small heading before loading indicator
        self.ui.show_text("\nPréparation")
        self.ui.show_loading("Préparation de la recette...")
        
        try:
            # Use the ingredients specific to the chosen recipe (from LLM proposal)
            recipe_ingredients = recipe_content.get("ingredients", [])
            recipe_data = self.llm_agent.get_recipe_steps(
                recipe_name,
                recipe_ingredients,
                self.state_machine.servings
            )
        finally:
            # Hide loading indicator
            self.ui.hide_loading()
        
        # Handle case where recipe_data might be a JSON string
        if isinstance(recipe_data, str):
            import json
            try:
                recipe_data = json.loads(recipe_data)
            except json.JSONDecodeError:
                self.ui.show_error("Erreur lors du parsing de la recette.")
                return False

        # Display ingredients
        ingredients_list = recipe_data.get("ingredients", [])
        if ingredients_list:
            self.ui.show_ingredients(ingredients_list)
        
        # Set recipe steps and name
        steps_data = recipe_data.get("steps", [])
        
        # Extract just the description for display in steps
        steps = []
        for step in steps_data:
            if isinstance(step, dict):
                steps.append(step.get("description", ""))
            else:
                steps.append(step)
        
        # Store steps in state machine (display_cooking_steps will show them when entering COOKING_GUIDANCE)
        self.state_machine.set_recipe_steps(steps)
        self.state_machine.selected_recipe = recipe_data.get("title", recipe_name)
        
        # Store the detailed steps for Gantt chart
        self.state_machine.detailed_steps = steps_data
        
        # Générer le diagramme de Gantt (uniquement à partir des descriptions d'étapes)
        # Éviter de passer l'objet recipe_data complet qui peut corrompre le JSON
        steps_for_gantt = []
        for i, step in enumerate(steps_data):
            if isinstance(step, dict):
                # Créer une copie simplifiée de l'étape pour éviter la corruption
                steps_for_gantt.append({
                    "id": step.get("id", str(i+1)),
                    "description": step.get("description", ""),
                    "duration_minutes": step.get("duration_minutes", 5),
                    "dependencies": step.get("dependencies", [])
                })
            else:
                # Pour les étapes en chaîne de caractères
                steps_for_gantt.append({
                    "id": str(i+1),
                    "description": str(step),
                    "duration_minutes": 5,
                    "dependencies": []
                })
        
        gantt_data = self._generate_gantt_chart(steps_for_gantt)
        recipe_title = recipe_data.get("title", recipe_name)
        gantt_file = self._save_gantt_chart(gantt_data, recipe_title)
        
        # Créer la visualisation Plotly interactive
        result = self.gantt_visualizer.process_gantt_file(
            gantt_file,
            recipe_name=recipe_title
        )
        
        print("\n Diagramme de Gantt généré\n")
        print(gantt_data)
        
        # Display steps immediately after receiving them
        self.ui.show_text("\n✓ Recette préparée avec succès!\n")
        self.display_cooking_steps()
        
        return True
        
    def display_cooking_steps(self):
        if not self.state_machine.recipe_steps:
            self.ui.show_error("Aucune étape de préparation disponible.")
            return
        
        # Use UI method to show steps
        self.ui.show_steps(self.state_machine.recipe_steps, current_step=self.state_machine.current_step)
        
    def execute_current_step(self):
        current_step = self.state_machine.get_current_step()
        
        if not current_step:
            self.ui.show_text("C'est fini! Il ne reste plus d'étapes!\n")
            return False
            
        step_num = self.state_machine.current_step + 1
        total_steps = len(self.state_machine.recipe_steps)
        
        self.ui.show_text(f"\nÉtape {step_num}/{total_steps}:\n")
        self.ui.show_text(f"{current_step}\n")
        
        # If on Raspberry Pi, display button controls guide
        if self.hardware.is_raspi:
            print(
                "\nContrôles physiques:\n"
                "- Bouton sur GPIO 6: Next (passer à l'étape suivante)\n"
                "- Bouton sur GPIO 19: Help (obtenir de l'aide)\n"
                "- Bouton sur GPIO 0: Back/Cancel (annuler minuteur)\n"
            )
        
        # Clear any previous button events
        self._next_button_event.clear()
        
        # Function to get input without blocking button presses (CLI legacy, now simplified for UI)
        def get_interruptible_input():
            # For now, in UI mode, we only support 'next' via button;
            # you can later extend this to use UI.ask_text if needed.
            while True:
                if self._next_button_event.is_set():
                    self._next_button_event.clear()
                    return "next"
                time.sleep(0.1)
            
        while True:
            # Get input (might be interrupted by button press)
            user_input = get_interruptible_input()
            
            if user_input == 'next':
                return True
          
            # In UI-only mode, other text commands are not handled here yet
                
    def _setup_button_controls(self):
        """Set up button controls for GPIO pins."""
        # GPIO 6: Next button (move to next step)
        self.hardware.register_button_callback(6, self._button_next)
        
        # GPIO 19: Ask for help button
        self.hardware.register_button_callback(19, self._button_help)
        
        # GPIO 0: Back/Cancel button
        self.hardware.register_button_callback(0, self._button_back)
        
        # Start polling the buttons
        self.hardware.start_polling()
        print("✓ Button controls initialized\n")
    
    def _button_next(self):
        """Handler for the 'Next' button (GPIO 6)"""
        print("Button pressed: Next\n")
        # Simulate 'next' command when in step execution
        if self.state_machine.current_state == CookingState.STEP_EXECUTION:
            print("Moving to next step...\n")
            # Signal the event to interrupt input
            self._next_button_event.set()
    
    def _button_help(self):
        """Handler for the 'Help' button (GPIO 19)"""
        self.ui.show_text("❓ Bouton d'aide pressé. Posez votre question.\n")
        
        # Utilise le même pattern que pour confirm_recipe :
        # 1) Le callback UI ne fait que stocker la valeur
        # 2) Le traitement (appel LLM + mise à jour UI) est fait ensuite,
        #    en dehors du contexte du callback, pour éviter les glitches.
        import threading

        self._help_question_value = None
        self._help_question_event = threading.Event()

        def _on_question(value: str):
            self._help_question_value = value
            self._help_question_event.set()

        # Demander la question à l'utilisateur
        self.ui.ask_text("Votre question", _on_question)

        def _process_help_question():
            # Attendre la saisie utilisateur
            self._help_question_event.wait()
            question = (self._help_question_value or "").strip()
            if question:
                self.ask_question(question)

        # Lancer le traitement dans un thread séparé pour ne pas bloquer l'UI
        threading.Thread(target=_process_help_question, daemon=True).start()
    
    def _button_back(self):
        """Handler for the 'Back/Cancel' button (GPIO 0)"""
        self.ui.show_text("⏮️ Button pressed: Back/Cancel\n")
        # Different behavior depending on state
        if self.state_machine.current_state == CookingState.RECIPE_CONFIRMATION:
            # Go back to recipe proposal
            self.ui.show_text("Retour à la proposition de recettes...\n")
            self.state_machine.transition_to(CookingState.RECIPE_PROPOSAL)
        elif self.state_machine.current_state == CookingState.STEP_EXECUTION:
            # Cancel current timer if any
            active_timers = self.timer.get_active_timers()
            if active_timers:
                timer_id = list(active_timers.keys())[0]  # Cancel first timer
                self.timer.stop_timer(timer_id)
                self.ui.show_text(f"Timer '{active_timers[timer_id]['name']}' annulé\n")

    def ask_question(self, question: str):
        """Handle a general cooking question in any state (from button or console)."""
        # Build a general context string based on what we know
        context_parts = []

        # Selected recipe
        if self.state_machine.selected_recipe:
            context_parts.append(f"Recette sélectionnée: {self.state_machine.selected_recipe}")

        # Ingredients
        if self.state_machine.ingredients:
            ing_list = ", ".join(self.state_machine.ingredients)
            context_parts.append(f"Ingrédients disponibles: {ing_list}")

        # Current step (if any)
        current_step = self.state_machine.get_current_step()
        if current_step:
            context_parts.append(f"Étape en cours: {current_step}")

        # Fallback generic context
        if not context_parts:
            context_parts.append("Contexte: Assistant de cuisine Robotatouille.")

        context = "\n".join(context_parts)

        try:
            # Show loading indicator
            self.ui.show_loading("Recherche d'une réponse...")
            
            # Reuse guide_step as a generic Q&A with this context
            response = self.llm_agent.guide_step(context, question)
            self.ui.show_text(f"\n💡 Conseil de cuisine:\n{response}\n")
        except Exception as e:
            self.ui.show_error(f"Erreur lors de la demande d'aide: {e}")
        finally:
            # Hide loading indicator
            self.ui.hide_loading()
    
    async def run(self):
        try:
            self.display_welcome()
            
            await self.collect_servings()
            
            if self._should_stop.is_set():
                return
            
            self.state_machine.transition_to(CookingState.INGREDIENT_COLLECTION)
            
            while True:
                # Check if we should stop
                if self._should_stop.is_set():
                    break
                    
                self.display_state()
                
                if self.state_machine.current_state == CookingState.INGREDIENT_COLLECTION:
                    await self.collect_ingredients()
                    self.state_machine.transition_to(CookingState.RECIPE_PROPOSAL)
                        
                elif self.state_machine.current_state == CookingState.RECIPE_PROPOSAL:
                    self.propose_recipes()
                    self.state_machine.transition_to(CookingState.RECIPE_CONFIRMATION)
                    
                elif self.state_machine.current_state == CookingState.RECIPE_CONFIRMATION:
                    if await self.confirm_recipe():
                        self.state_machine.transition_to(CookingState.COOKING_GUIDANCE)
                    
                elif self.state_machine.current_state == CookingState.COOKING_GUIDANCE:
                    # Steps are already affichées, préparer l'UI pour l'exécution
                    if hasattr(self.ui, "show_next_button"):
                        self.ui.show_next_button()
                    self.state_machine.transition_to(CookingState.STEP_EXECUTION)
                    
                elif self.state_machine.current_state == CookingState.STEP_EXECUTION:
                    if self.execute_current_step():
                        if self.state_machine.is_cooking_complete():
                            print("Cooking complete\n")
                            self.state_machine.transition_to(CookingState.COMPLETED)

                        else:
                            self.state_machine.next_step()
                    else:
                        # Sortie anticipée de l'exécution des étapes -> masquer le bouton Next
                        if hasattr(self.ui, "hide_next_button"):
                            self.ui.hide_next_button()
                        break
                        
                elif self.state_machine.current_state == CookingState.COMPLETED:
                    # Fin de recette -> masquer le bouton Next
                    if hasattr(self.ui, "hide_next_button"):
                        self.ui.hide_next_button()
                    self.ui.show_text("\n🎉 Félicitations! Vous avez terminé la recette!\n")
                    self.ui.show_text("Regalez-vous et ... bon appétit bien sûr! 🍽️\n")
                    # For now, just break - we can add "cook again" functionality later
                    break
                else:
                    break
        finally:
            # Clean up hardware resources
            if self.hardware.is_raspi:
                self.hardware.cleanup()
                
            # Clean up timer resources
            self.timer.cleanup()
            self.ui.show_text("\nMerci d'avoir fait confiance à Robotatouille! A la prochaine! 👋\n")
            
    def _generate_gantt_chart(self, steps_data):
        """
        Génère des données au format Gantt Project à partir des étapes détaillées
        """
        import json
        from datetime import datetime, timedelta
        
        # Initialiser les données de base du projet Gantt
        gantt_data = {
            "tasks": [],
            "resources": [],
            "roles": []
        }
        
        # Définir la date et heure de début (maintenant)
        start_time = datetime.now()
        
        # Pour chaque étape, créer une tâche Gantt
        for i, step in enumerate(steps_data):
            # Extraire les informations nécessaires en s'assurant que les données sont valides
            step_id = str(step.get("id", f"task{i+1}")) if isinstance(step, dict) else f"task{i+1}"
            
            # S'assurer que le nom de la tâche est une chaîne courte (pas un objet JSON complet)
            if isinstance(step, dict):
                step_name = str(step.get("description", f"Étape {i+1}"))
            else:
                step_name = str(step)[:100]  # Limiter la longueur à 100 caractères
                
            # Tâche standardisée
            task = {
                "id": step_id,
                "name": step_name,
                "start": start_time.strftime("%Y-%m-%d %H:%M"),
                "duration": step.get("duration_minutes", 5) if isinstance(step, dict) else 5,
                "complete": 0,
                "predecessors": step.get("dependencies", []) if isinstance(step, dict) else []
            }
            # Avancer l'heure de début pour la prochaine tâche
            if isinstance(step, dict):
                duration = step.get("duration_minutes", 5)
            else:
                duration = 5
                
            start_time = start_time + timedelta(minutes=duration)
            
            gantt_data["tasks"].append(task)
        
        return gantt_data
        
    # Méthode d'affichage du Gantt supprimée
        
    def _save_gantt_chart(self, gantt_data, recipe_name):
        """
        Sauvegarde le diagramme de Gantt dans un fichier JSON
        """
        import json
        import os
        from datetime import datetime
        
        # Créer un dossier pour les diagrammes s'il n'existe pas
        gantt_dir = "gantt_charts"
        os.makedirs(gantt_dir, exist_ok=True)
        
        # Générer un nom de fichier basé sur le nom de la recette et la date
        safe_name = "".join([c if c.isalnum() else "_" for c in recipe_name])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{gantt_dir}/{safe_name}_{timestamp}.json"
        
        # Écrire les données au format JSON
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(gantt_data, f, indent=2, ensure_ascii=False)
            
        return filename
