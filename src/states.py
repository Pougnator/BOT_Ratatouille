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
        self.additional_recipe_request = None
        
    def transition_to(self, new_state: CookingState):
        self.current_state = new_state
        
    def set_servings(self, servings: int):
        self.servings = servings
        
    def add_ingredients(self, ingredients: list):
        self.ingredients.extend(ingredients)
        
    def set_proposed_recipes(self, recipes: list):
        self.proposed_recipes = recipes
        
    def select_recipe(self, recipe_index: int):
        if 0 <= recipe_index < len(self.proposed_recipes):
            self.selected_recipe = self.proposed_recipes[recipe_index]
            return True
        return False
        
    def set_recipe_steps(self, steps: list):
        self.recipe_steps = steps
        self.current_step = 0
        
    def next_step(self):
        if self.current_step < len(self.recipe_steps) - 1:
            self.current_step += 1
            return True
        return False
        
    def get_current_step(self) -> Optional[str]:
        if 0 <= self.current_step < len(self.recipe_steps):
            return self.recipe_steps[self.current_step]
        return None
        
    def is_cooking_complete(self) -> bool:
        return self.current_step >= len(self.recipe_steps) - 1
        
    def reset(self):
        self.__init__()
        
    def clear_additional_recipe_request(self):
        self.additional_recipe_request = None
