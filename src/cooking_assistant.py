import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import print as rprint

from .states import StateMachine, CookingState
from .llm_agent import LLMAgent
from .timer import CookingTimer


class CookingAssistant:
    def __init__(self):
        self.console = Console()
        self.state_machine = StateMachine()
        self.llm_agent = LLMAgent()
        self.timer = CookingTimer()
        
    def display_welcome(self):
        welcome_text = """
        Welcome to your AI Cooking Assistant! 👨‍🍳
        
        I'll help you discover delicious recipes based on your available ingredients
        and guide you step-by-step through the cooking process.
        
        Let's get started!
        """
        self.console.print(Panel(welcome_text, title="🍳 Cooking Assistant", border_style="green"))
        
    def display_state(self):
        state_name = self.state_machine.current_state.value.replace('_', ' ').title()
        self.console.print(f"\n[bold cyan]Current State:[/bold cyan] {state_name}\n")
        
    def collect_servings(self):
        self.console.print("[bold yellow]How many people are you cooking for?[/bold yellow]")
        
        while True:
            servings_input = Prompt.ask("Number of servings", default="2")
            
            try:
                servings = int(servings_input)
                if servings > 0:
                    self.state_machine.set_servings(servings)
                    self.console.print(f"\n[green]✓ Cooking for {servings} people[/green]")
                    return True
                else:
                    self.console.print("[red]Please enter a positive number.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a valid number.[/red]")
        
    def collect_ingredients(self):
        self.console.print("[bold yellow]What ingredients do you have?[/bold yellow]")
        self.console.print("Enter ingredients separated by commas (e.g., chicken, rice, tomatoes)")
        
        ingredients_input = Prompt.ask("Your ingredients")
        ingredients = [ing.strip() for ing in ingredients_input.split(',') if ing.strip()]
        
        if ingredients:
            self.state_machine.add_ingredients(ingredients)
            self.console.print(f"\n[green]✓ Added {len(ingredients)} ingredients[/green]")
            return True
        else:
            self.console.print("[red]No ingredients provided. Please try again.[/red]")
            return False
            
    def propose_recipes(self):
        self.console.print("\n[bold cyan]Analyzing your ingredients and finding recipes...[/bold cyan]\n")
        
        recipes_response = self.llm_agent.propose_recipes(
            self.state_machine.ingredients,
            self.state_machine.servings
        )
        
        self.console.print(Panel(recipes_response, title="📖 Recipe Suggestions", border_style="blue"))
        
        self.state_machine.set_proposed_recipes(recipes_response.split('\n\n'))
        
    def confirm_recipe(self):
        self.console.print("\n[bold yellow]Which recipe would you like to cook?[/bold yellow]")
        self.console.print("Enter the recipe number (1-3) or type the recipe name:")
        
        choice = Prompt.ask("Your choice")
        
        recipe_name = choice.strip()
        
        if recipe_name:
            self.console.print(f"\n[green]✓ Selected recipe: {recipe_name}[/green]")
            
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
            self.console.print(Panel(ingredients_natural_list, title="🧾 Ingredients", border_style="blue"))
            
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
            steps = recipe_data.get("steps", [])
            self.state_machine.set_recipe_steps(steps)
            self.state_machine.selected_recipe = recipe_data.get("title", recipe_name)
            
            return True
        return False
        
    def display_cooking_steps(self):
        if not self.state_machine.recipe_steps:
            self.console.print("[red]No recipe steps available.[/red]")
            return
            
        table = Table(title=f"📋 Cooking Steps for {self.state_machine.selected_recipe}")
        table.add_column("Step", style="cyan", width=8)
        table.add_column("Instruction", style="white")
        
        for idx, step in enumerate(self.state_machine.recipe_steps, 1):
            marker = "→" if idx == self.state_machine.current_step + 1 else " "
            table.add_row(f"{marker} {idx}", step)
            
        self.console.print(table)
        
    def execute_current_step(self):
        current_step = self.state_machine.get_current_step()
        
        if not current_step:
            self.console.print("[yellow]No more steps![/yellow]")
            return False
            
        step_num = self.state_machine.current_step + 1
        total_steps = len(self.state_machine.recipe_steps)
        
        self.console.print(f"\n[bold green]Step {step_num}/{total_steps}:[/bold green]")
        self.console.print(Panel(current_step, border_style="green"))
        
        while True:
            active_timers = self.timer.get_active_timers()
            if active_timers:
                self.console.print("\n[bold cyan]Active Timers:[/bold cyan]")
                for timer_id, timer_info in active_timers.items():
                    time_str = self.timer.format_time(timer_info['remaining'])
                    self.console.print(f"  ⏱️  {timer_info['name']}: {time_str} remaining")
            
            self.console.print("\n[dim]Commands: 'next' (continue), 'timer <duration>' (set timer), 'ask <question>' (ask for help), 'quit' (exit)[/dim]")
            user_input = Prompt.ask("").strip().lower()
            
            if user_input == 'next':
                return True
            elif user_input.startswith('timer '):
                duration_str = user_input[6:].strip()
                duration_seconds = self.timer.parse_duration(duration_str)
                if duration_seconds:
                    timer_id = self.timer.start_timer(duration_seconds, f"Step {step_num}")
                    self.console.print(f"[green]✓ Timer set for {self.timer.format_time(duration_seconds)}[/green]")
                else:
                    self.console.print("[red]Invalid duration. Try '10 min', '30 sec', etc.[/red]")
            elif user_input.startswith('ask '):
                question = user_input[4:].strip()
                response = self.llm_agent.guide_step(current_step, question)
                self.console.print(Panel(response, title="💡 Cooking Tip", border_style="yellow"))
            elif user_input == 'quit':
                return False
            else:
                self.console.print("[red]Unknown command. Try 'next', 'timer <duration>', or 'ask <question>'[/red]")
                
    async def run(self):
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
                self.console.print("\n[bold green]🎉 Congratulations! You've completed the recipe![/bold green]")
                self.console.print(Panel("Enjoy your delicious meal! 🍽️", border_style="green"))
                
                again = Prompt.ask("\nWould you like to cook another recipe?", choices=["yes", "no"], default="no")
                if again == "yes":
                    self.state_machine.reset()
                    self.llm_agent.reset_conversation()
                    self.state_machine.transition_to(CookingState.INGREDIENT_COLLECTION)
                else:
                    break
            else:
                break
                
        self.console.print("\n[bold cyan]Thank you for using the Cooking Assistant! Happy cooking! 👋[/bold cyan]")
