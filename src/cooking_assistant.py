import asyncio
import threading
import time
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import print as rprint

from .states import StateMachine, CookingState
from .llm_agent import LLMAgent
from .timer import CookingTimer
from .hardware_handler import HardwareHandler
from .gantt_visualizer import GanttVisualizer


class CookingAssistant:
    def __init__(self):
        self.console = Console()
        self.state_machine = StateMachine()
        self.llm_agent = LLMAgent()
        self.timer = CookingTimer(console=self.console)
        self.hardware = HardwareHandler()
        self.gantt_visualizer = GanttVisualizer(console=self.console)
        
        # Use threading Event objects for button communication
        self._next_button_event = threading.Event()
        
        # If running on a Raspberry Pi, set up button callbacks
        if self.hardware.is_raspi:
            self.console.print("[bold green]✓ Raspberry Pi detected. Setting up GPIO buttons...[/bold green]")
            self._setup_button_controls()
        
    def display_welcome(self):
        welcome_text = """
        Hello, je suis Robotatouille! 👨‍🍳
        
        Je vous aiderai à découvrir de délicieuses recettes basées sur vos ingrédients disponibles
        et vous guiderai étape par étape tout au long du processus de cuisine.
        
        Commençons!
        """
        self.console.print(Panel(welcome_text, title="🍳 Robotatouille", border_style="green"))
        
    def display_state(self):
        state_name = self.state_machine.current_state.value.replace('_', ' ').title()
        self.console.print(f"\n[bold cyan]Current State:[/bold cyan] {state_name}\n")
        
    def collect_servings(self):
        self.console.print("[bold yellow]Pour combien de personnes voulez-vous cuisiner?[/bold yellow]")
        
        while True:
            servings_input = Prompt.ask("Nombre de personnes", default="2")
            
            try:
                servings = int(servings_input)
                if servings > 0:
                    self.state_machine.set_servings(servings)
                    self.console.print(f"\n[green]✓ On cuisine pour {servings} personnes[/green]")
                    return True
                else:
                    self.console.print("[red]Veuillez entrer un nombre positif.[/red]")
            except ValueError:
                self.console.print("[red]Veuillez entrer un nombre valide.[/red]")
        
    def collect_ingredients(self):
        self.console.print("[bold yellow]Quels ingrédients avez-vous sous la main?[/bold yellow]")
        self.console.print("Entrez les ingrédients séparés par des virgules (par exemple, poulet, riz, tomates)")
        
        ingredients_input = Prompt.ask("Vos ingrédients")
        ingredients = [ing.strip() for ing in ingredients_input.split(',') if ing.strip()]
        
        if ingredients:
            self.state_machine.add_ingredients(ingredients)
            self.console.print(f"\n[green]✓ J'ai ajouté {len(ingredients)} ingrédients[/green]")
            return True
        else:
            self.console.print("[red]Aucun ingrédient fourni. Veuillez réessayer.[/red]")
            return False
            
    def propose_recipes(self):
        self.console.print("\n[bold cyan]Analyse des ingrédients et recherche de recettes...[/bold cyan]\n")
        
        # Check if there's an additional recipe request
        additional_request = self.state_machine.additional_recipe_request
        
        recipes_response = self.llm_agent.propose_recipes(
            self.state_machine.ingredients,
            self.state_machine.servings,
            additional_request
        )
        
        # Clear the additional request after using it
        self.state_machine.clear_additional_recipe_request()
        
        self.console.print(Panel(recipes_response, title="📖 Choix des recettes", border_style="blue"))
        
        self.state_machine.set_proposed_recipes(recipes_response.split('\n\n'))
        
    def confirm_recipe(self):
        self.console.print("\n[bold yellow]Quel recette voulez-vous cuisiner?[/bold yellow]")
        self.console.print("Entrez le numéro de la recette (1-3) ou le nom de la recette:")
        self.console.print("Entrez 0 + instructions additionnelles pour demander plus de recettes")
        
        choice = Prompt.ask("Votre choix")
        
        recipe_name = choice.strip()
        
        # Check if user wants more recipes
        if recipe_name.startswith('0'):
            additional_prompt = recipe_name[1:].strip()
            self.console.print("\n[cyan]Recherche de plus de recettes...[/cyan]")
            
            # Go back to the recipe proposal state
            self.state_machine.transition_to(CookingState.RECIPE_PROPOSAL)
            
            # If there's an additional prompt, store it for the LLM to use
            if additional_prompt:
                self.state_machine.additional_recipe_request = additional_prompt
                self.console.print(f"[italic]Avec précision: {additional_prompt}[/italic]")
            
            return False
        elif recipe_name:
            self.console.print(f"\n[green]✓ Recette selectionnée: {recipe_name}[/green]")
            
            recipe_data = self.llm_agent.get_recipe_steps(
                recipe_name,
                self.state_machine.ingredients,
                self.state_machine.servings
            )

            # Explain the ingredients needed in natural language
         
            ingredients_natural_list = self.llm_agent.explain_ingredients_naturally(
                self.state_machine.ingredients,
                recipe_name,
                recipe_data.get("steps", [])
            )
            self.console.print(Panel(ingredients_natural_list, title="🧾 Ingrédients", border_style="blue"))
            
            # Display ingredients in a formatted way
            ingredients_list = recipe_data.get("ingredients", [])
            if ingredients_list:
                table = Table(title="🧾 Ingredients")
                table.add_column("Quantity", style="cyan")
                table.add_column("Unit", style="green")
                table.add_column("Ingredient", style="yellow")
                table.add_column("Preparation", style="magenta")
                
                for ingredient in ingredients_list:
                    quantity = ingredient.get("quantity", "")
                    unit = ingredient.get("unit", "")
                    name = ingredient.get("name", "")
                    prep = ingredient.get("preparation", "")
                    table.add_row(quantity, unit, name, prep)
                
                self.console.print(table)
            
            # Set recipe steps and name
            steps_data = recipe_data.get("steps", [])
            
            # Extract just the description for display in steps
            steps = []
            for step in steps_data:
                if isinstance(step, dict):
                    steps.append(step.get("description", ""))
                else:
                    steps.append(step)
                    
            self.state_machine.set_recipe_steps(steps)
            self.state_machine.selected_recipe = recipe_data.get("title", recipe_name)
            
            # Store the detailed steps for Gantt chart
            self.state_machine.detailed_steps = steps_data
            
            # Generate and display Gantt chart
            gantt_data = self._generate_gantt_chart(steps_data)
            gantt_file = self._save_gantt_chart(gantt_data, recipe_data.get("title", recipe_name))
            self.console.print(Panel(f"Diagramme de Gantt généré au format JSON pour la planification\nSauvegardé dans: {gantt_file}", title="📊 Planification", border_style="green"))
            self._display_gantt_data(gantt_data)
            
            return True
        return False
        
    def display_cooking_steps(self):
        if not self.state_machine.recipe_steps:
            self.console.print("[red]Aucune étape de préparation disponible.[/red]")
            return
            
        table = Table(title=f"📋 Étapes de préparation pour {self.state_machine.selected_recipe}")
        table.add_column("Étape", style="cyan", width=8)
        table.add_column("Instruction", style="white")
        
        for idx, step in enumerate(self.state_machine.recipe_steps, 1):
            marker = "→" if idx == self.state_machine.current_step + 1 else " "
            table.add_row(f"{marker} {idx}", step)
            
        self.console.print(table)
        
    def execute_current_step(self):
        current_step = self.state_machine.get_current_step()
        
        if not current_step:
            self.console.print("[yellow]C'est fini! Il ne reste plus d'étapes![/yellow]")
            return False
            
        step_num = self.state_machine.current_step + 1
        total_steps = len(self.state_machine.recipe_steps)
        
        self.console.print(f"\n[bold green]Étape {step_num}/{total_steps}:[/bold green]")
        self.console.print(Panel(current_step, border_style="green"))
        
        # If on Raspberry Pi, display button controls guide
        if self.hardware.is_raspi:
            self.console.print("\n[dim]Contrôles physiques:[/dim]")
            self.console.print("[dim]- Bouton sur GPIO 6: Next (passer à l'étape suivante)[/dim]")
            self.console.print("[dim]- Bouton sur GPIO 19: Help (obtenir de l'aide)[/dim]")
            self.console.print("[dim]- Bouton sur GPIO 0: Back/Cancel (annuler minuteur)[/dim]")
        
        # Clear any previous button events
        self._next_button_event.clear()
        
        # Function to get console input without blocking button presses
        def get_interruptible_input():
            class InputResult:
                value = None
                
            # Create a thread to get input
            def input_thread_func():
                InputResult.value = Prompt.ask("", console=self.console).strip().lower()
                
            # Display info and prompt
            active_timers = self.timer.get_active_timers()
            if active_timers:
                self.console.print("\n[bold cyan]Active Timers:[/bold cyan]")
                for timer_id, timer_info in active_timers.items():
                    time_str = self.timer.format_time(timer_info['remaining'])
                    self.console.print(f"  ⏱️  {timer_info['name']}: {time_str} remaining")
                    
            self.console.print("\n[dim]Commandes: 'next' (continue), 'timer <duration>' (set timer), 'ask <question>' (ask for help), 'quit' (exit)[/dim]")
            
            # Start input thread
            input_thread = threading.Thread(target=input_thread_func)
            input_thread.daemon = True
            input_thread.start()
            
            # Wait for either input completion or button press
            while input_thread.is_alive():
                if self._next_button_event.is_set():
                    self._next_button_event.clear()
                    return "next"  # Simulate 'next' command
                time.sleep(0.1)  # Check 10 times per second
            
            # Input received
            return InputResult.value
            
        while True:
            # Get input (might be interrupted by button press)
            user_input = get_interruptible_input()
            
            if user_input == 'next':
                return True
            elif user_input.startswith('timer '):
                duration_str = user_input[6:].strip()
                duration_seconds = self.timer.parse_duration(duration_str)
                if duration_seconds:
                    timer_id = self.timer.start_timer(duration_seconds, f"Step {step_num}")
                    self.console.print(f"[green]✓ Timer set for {self.timer.format_time(duration_seconds)}[/green]")
                else:
                    self.console.print("[red]Durée invalide. Essayez '10 min', '30 sec', etc.[/red]")
            elif user_input.startswith('ask '):
                question = user_input[4:].strip()
                response = self.llm_agent.guide_step(current_step, question)
                self.console.print(Panel(response, title="💡 Conseil de cuisine", border_style="yellow"))
            elif user_input == 'quit':
                return False
            else:
                self.console.print("[red]Commande inconnue. Essayez 'next', 'timer <durée>', ou 'poser une <question>'[/red]")
                
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
        self.console.print("[green]✓ Button controls initialized[/green]")
    
    def _button_next(self):
        """Handler for the 'Next' button (GPIO 6)"""
        self.console.print("[bold blue]⏭️ Button pressed: Next[/bold blue]")
        # Simulate 'next' command when in step execution
        if self.state_machine.current_state == CookingState.STEP_EXECUTION:
            self.console.print("[green]Moving to next step...[/green]")
            # Signal the event to interrupt input
            self._next_button_event.set()
    
    def _button_help(self):
        """Handler for the 'Help' button (GPIO 19)"""
        self.console.print("[bold yellow]❓ Button pressed: Help[/bold yellow]")
        # Get current step if in execution mode
        if self.state_machine.current_state == CookingState.STEP_EXECUTION:
            current_step = self.state_machine.get_current_step()
            if current_step:
                response = self.llm_agent.guide_step(
                    current_step, 
                    "Explique cette étape de manière plus détaillée"
                )
                self.console.print(Panel(response, title="💡 Aide (via bouton)", border_style="yellow"))
    
    def _button_back(self):
        """Handler for the 'Back/Cancel' button (GPIO 0)"""
        self.console.print("[bold red]⏮️ Button pressed: Back/Cancel[/bold red]")
        # Different behavior depending on state
        if self.state_machine.current_state == CookingState.RECIPE_CONFIRMATION:
            # Go back to recipe proposal
            self.console.print("[yellow]Retour à la proposition de recettes...[/yellow]")
            self.state_machine.transition_to(CookingState.RECIPE_PROPOSAL)
        elif self.state_machine.current_state == CookingState.STEP_EXECUTION:
            # Cancel current timer if any
            active_timers = self.timer.get_active_timers()
            if active_timers:
                timer_id = list(active_timers.keys())[0]  # Cancel first timer
                self.timer.stop_timer(timer_id)
                self.console.print(f"[yellow]Timer '{active_timers[timer_id]['name']}' annulé[/yellow]")
    
    async def run(self):
        try:
            self.display_welcome()
            
            self.collect_servings()
            
            self.state_machine.transition_to(CookingState.INGREDIENT_COLLECTION)
            
            while True:
                self.display_state()
                
                if self.state_machine.current_state == CookingState.INGREDIENT_COLLECTION:
                    if self.collect_ingredients():
                        self.state_machine.transition_to(CookingState.RECIPE_PROPOSAL)
                        
                elif self.state_machine.current_state == CookingState.RECIPE_PROPOSAL:
                    self.propose_recipes()
                    self.state_machine.transition_to(CookingState.RECIPE_CONFIRMATION)
                    
                elif self.state_machine.current_state == CookingState.RECIPE_CONFIRMATION:
                    if self.confirm_recipe():
                        self.state_machine.transition_to(CookingState.COOKING_GUIDANCE)
                    
                elif self.state_machine.current_state == CookingState.COOKING_GUIDANCE:
                    self.display_cooking_steps()
                    self.state_machine.transition_to(CookingState.STEP_EXECUTION)
                    
                elif self.state_machine.current_state == CookingState.STEP_EXECUTION:
                    if self.execute_current_step():
                        if self.state_machine.is_cooking_complete():
                            self.state_machine.transition_to(CookingState.COMPLETED)
                        else:
                            self.state_machine.next_step()
                    else:
                        break
                        
                elif self.state_machine.current_state == CookingState.COMPLETED:
                    self.console.print("\n[bold green]🎉 Félicitations! Vous avez terminé la recette![/bold green]")
                    self.console.print(Panel("Regalez-vous et ... bon appétit bien sûr! 🍽️", border_style="green"))
                    
                    again = Prompt.ask("\nVoulez-vous cuisiner une autre chose?", choices=["yes", "no"], default="no")
                    if again == "yes":
                        self.state_machine.reset()
                        self.llm_agent.reset_conversation()
                        self.state_machine.transition_to(CookingState.INGREDIENT_COLLECTION)
                    else:
                        break
                else:
                    break
        finally:
            # Clean up hardware resources
            if self.hardware.is_raspi:
                self.hardware.cleanup()
                
            # Clean up timer resources
            self.timer.cleanup()
                
            self.console.print("\n[bold cyan]Merci d'avoir fait confiance à Robotatouille! A la prochaine! 👋[/bold cyan]")
            
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
            # Gérer les étapes qui pourraient être des chaînes de caractères plutôt que des objets
            if isinstance(step, str):
                task = {
                    "id": f"task{i+1}",
                    "name": step,
                    "start": start_time.strftime("%Y-%m-%d %H:%M"),
                    "duration": 5, # durée par défaut de 5 minutes
                    "complete": 0,
                    "predecessors": []
                }
            else:
                # Obtenir la durée ou utiliser une valeur par défaut
                duration = step.get("duration_minutes", 5)
                
                # Obtenir la description ou utiliser une chaîne vide
                name = step.get("description", f"Étape {i+1}")
                
                # Obtenir l'ID ou en générer un
                task_id = step.get("id", f"task{i+1}")
                
                # Obtenir les dépendances
                dependencies = step.get("dependencies", [])
                
                task = {
                    "id": task_id,
                    "name": name,
                    "start": start_time.strftime("%Y-%m-%d %H:%M"),
                    "duration": duration,
                    "complete": 0,
                    "predecessors": dependencies
                }
                
                # Avancer l'heure de début pour la prochaine tâche
                start_time = start_time + timedelta(minutes=duration)
            
            gantt_data["tasks"].append(task)
        
        return gantt_data
        
    def _display_gantt_data(self, gantt_data):
        """
        Affiche les données du diagramme de Gantt
        """
        import json
        from rich.syntax import Syntax
        
        # Convertir en JSON bien formaté
        gantt_json = json.dumps(gantt_data, indent=2, ensure_ascii=False)
        
        # Afficher en tant que JSON coloré
        syntax = Syntax(gantt_json, "json", theme="monokai", line_numbers=True)
        self.console.print(syntax)
        
    def _save_gantt_chart(self, gantt_data, recipe_name):
        """
        Sauvegarde le diagramme de Gantt dans un fichier JSON et génère une visualisation
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
        
        # Générer une visualisation
        try:
            visual_path = self.gantt_visualizer.process_gantt_file(filename, recipe_name)
            self.console.print(f"[green]✓ Visualisation du diagramme de Gantt sauvegardée: {visual_path}[/green]")
        except Exception as e:
            self.console.print(f"[yellow]Note: La visualisation n'a pas pu être générée: {str(e)}[/yellow]")
            
        return filename
