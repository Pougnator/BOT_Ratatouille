"""Abstract interface for cooking assistant UI implementations"""
from abc import ABC, abstractmethod
from typing import List, Dict, Callable, Optional


class CookingUI(ABC):
    """Abstract interface that CookingAssistant uses to interact with the UI"""
    
    @abstractmethod
    def show_text(self, text: str):
        """Display text in the console/output area"""
        pass
    
    @abstractmethod
    def ask_text(self, prompt: str, callback: Callable[[str], None], default: Optional[str] = None):
        """
        Ask the user for text input
        
        Args:
            prompt: The prompt/question to display
            callback: Function to call with the user's response
            default: Optional default value
        """
        pass
    
    @abstractmethod
    def show_recipes(self, recipes: List[Dict[str, str]]):
        """
        Display a list of proposed recipes
        
        Args:
            recipes: List of recipe dicts with keys: name, description, difficulty
        """
        pass
    
    @abstractmethod
    def show_ingredients(self, ingredients: List[Dict[str, str]]):
        """
        Display ingredients list
        
        Args:
            ingredients: List of ingredient dicts with keys: quantity, unit, name, preparation
        """
        pass
    
    @abstractmethod
    def show_steps(self, steps: List[str], current_step: int = 0):
        """
        Display cooking steps
        
        Args:
            steps: List of step descriptions
            current_step: Index of the current step (0-based)
        """
        pass
    
    @abstractmethod
    def show_gantt(self, gantt_data: Dict):
        """
        Display Gantt chart data
        
        Args:
            gantt_data: Dictionary containing Gantt chart information
        """
        pass
    
    @abstractmethod
    def show_error(self, error_message: str):
        """Display an error message"""
        pass
    
    @abstractmethod
    def show_success(self, message: str):
        """Display a success message"""
        pass
    
    @abstractmethod
    def show_loading(self, message: str = "Chargement..."):
        """Show a loading indicator"""
        pass
    
    @abstractmethod
    def hide_loading(self):
        """Hide the loading indicator"""
        pass

    # Optional: controls specific to step execution UI (e.g., "Next" button)
    def show_next_button(self):
        """Optionally show a 'Next' control in the UI (default: no-op)."""
        pass

    def hide_next_button(self):
        """Optionally hide the 'Next' control in the UI (default: no-op)."""
        pass

