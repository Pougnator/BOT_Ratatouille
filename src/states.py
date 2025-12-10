from enum import Enum
from typing import Optional


class CookingState(Enum):
    STARTING = "starting"
    INGREDIENT_COLLECTION = "ingredient_collection"
    RECIPE_PROPOSAL = "recipe_proposal"
    RECIPE_CONFIRMATION = "recipe_confirmation"
    COOKING_GUIDANCE = "cooking_guidance"
    STEP_EXECUTION = "step_execution"
    COMPLETED = "completed"


class StateMachine:
    def __init__(self):
        self.current_state = CookingState.STARTING
        self.servings = 2
        self.ingredients = []
        self.proposed_recipes = []
        self.selected_recipe = None
        self.current_step = 0
        self.recipe_steps = []
        self.detailed_steps = []  # Pour stocker les étapes détaillées au format JSON pour le diagramme de Gantt
        self.additional_recipe_request = None
        
    def transition_to(self, new_state: CookingState):
        old_state = self.current_state
        self.current_state = new_state
        print(f"\n[SYSTEME] 🔄 CHANGEMENT D'ÉTAT : {old_state.value} → {new_state.value}")
        
    def set_servings(self, servings: int):
        self.servings = servings
        
    def add_ingredients(self, ingredients: list):
        self.ingredients.extend(ingredients)
        
    def set_proposed_recipes(self, recipes: list):
        self.proposed_recipes = recipes
        
    def select_recipe(self, recipe_title: str):
        if recipe_title:
            self.selected_recipe = recipe_title
            return True
        else:
            return False
        
    def set_recipe_steps(self, steps: list):
        self.recipe_steps = list(steps)  # Create a new list from steps
        self.current_step = 0
        
    def next_step(self):
        """Advance to the next recipe step, if any.
        
        Returns True if we successfully moved to the next step,
        False if there are no more steps.
        """
        if self.current_step < len(self.recipe_steps) - 1:
            print(f"Moving to next step: {self.current_step}, total steps: {len(self.recipe_steps)}")
            self.current_step += 1
            return True

        print("No more steps to move to")
        return False
    
    def previous_step(self):
        """Go back to the previous recipe step, if any.
        
        Returns True if we successfully moved to the previous step,
        False if we're already at the first step.
        """
        if self.current_step > 0:
            print(f"Moving to previous step: {self.current_step}, total steps: {len(self.recipe_steps)}")
            self.current_step -= 1
            return True

        print("Already at the first step")
        return False
        
    def get_current_step(self) -> Optional[str]:
        """Return the current step description, or None if out of range."""
        if 0 <= self.current_step < len(self.recipe_steps):
            print(f"Getting current step: {self.current_step}, total steps: {len(self.recipe_steps)}")
            return self.recipe_steps[self.current_step]
        print("No current step (index out of range)")
        return None
        
    def is_cooking_complete(self) -> bool:
        """Return True when the last step has been executed."""
        if not self.recipe_steps:
            return True
        return self.current_step >= len(self.recipe_steps) - 1
        
    def reset(self):
        self.__init__()
        
    def clear_additional_recipe_request(self):
        self.additional_recipe_request = None
