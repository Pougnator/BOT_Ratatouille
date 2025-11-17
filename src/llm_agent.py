import os
from openai import OpenAI
from typing import Optional


class LLMAgent:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        self.client = OpenAI(api_key=api_key)
        self.conversation_history = []
        
    def add_system_message(self, content: str):
        self.conversation_history.append({
            "role": "system",
            "content": content
        })
        
    def add_user_message(self, content: str):
        self.conversation_history.append({
            "role": "user",
            "content": content
        })
        
    def get_response(self, user_input: Optional[str] = None, system_prompt: Optional[str] = None, functions=None) -> str:
        if system_prompt:
            system_prompt += "\n\nRéponds toujours en français, quelle que soit la langue de la question."
            self.add_system_message(system_prompt)
        else:
            # If no system prompt was provided, add a default French instruction
            self.add_system_message("Réponds toujours en français, quelle que soit la langue de la question.")
            
        if user_input:
            self.add_user_message(user_input)
            
        try:
            # Build request parameters
            params = {
                "model": "gpt-4o-mini",
                "messages": self.conversation_history,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            # Add functions if provided
            if functions:
                params["functions"] = functions
                params["function_call"] = {"name": functions[0]["name"]}
            
            response = self.client.chat.completions.create(**params)
            
            # Check if response is a function call
            message = response.choices[0].message
            
            if hasattr(message, "function_call") and message.function_call:
                # Extract structured function response
                assistant_message = message.function_call.arguments
                self.conversation_history.append({
                    "role": "assistant",
                    "content": str(assistant_message),
                    "function_call": {
                        "name": message.function_call.name,
                        "arguments": message.function_call.arguments
                    }
                })
                return assistant_message
            else:
                # Normal text response
                assistant_message = message.content
                if assistant_message is None:
                    assistant_message = "No response from LLM"
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                return assistant_message
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"
            
    def propose_recipes(self, ingredients: list, servings: int = 2, additional_request: str = None) -> str:
        ingredients_str = ", ".join(ingredients)
        system_prompt = """You are a helpful cooking assistant. Based on the ingredients provided, 
        suggest 3 different recipes. For each recipe, provide:
        1. Recipe name
        2. Brief description
        3. Difficulty level (Easy/Medium/Hard)
        The first recipe should use all of the ingredients provided. 
        The other recipes could be gradually more flexible, but must be delicious and use at least some of the ingredients provided. 
        The third recipe could also incorporate some additional but very common ingredients.
        The recipes should be in French.
        Format your response as a numbered list."""
        
        user_prompt = f"I have these ingredients: {ingredients_str}. I'm cooking for {servings} people."
        
        # Add any additional recipe request criteria
        if additional_request:
            user_prompt += f" {additional_request}"
        else:
            user_prompt += " What recipes can I make?"
        
        return self.get_response(user_prompt, system_prompt)

    def explain_ingredients_naturally(self, ingredients: list, recipe_name: str, recipe_steps: list) -> str:
        system_prompt = "You are a helpful cooking assistant. Explain the ingredients I need for a recipe in a natural way that is easy to understand."
        user_prompt = f"I have these ingredients: {ingredients}. I'm cooking the folowing recipe: :{recipe_name} and i am using the following steps: {recipe_steps}. Please use a concise and natural language to summarise the list of ingredients and the quantities i need"
        return self.get_response(user_prompt, system_prompt)
        

    def get_recipe_steps(self, recipe_name: str, ingredients: list, servings: int = 2) -> dict:
        ingredients_str = ", ".join(ingredients)
        system_prompt = "You are a helpful cooking assistant. Provide a detailed recipe with ingredients and steps."
        
        user_prompt = f"Give me a recipe for {recipe_name} for {servings} people using these ingredients: {ingredients_str}."
        
        recipe_function = [{
            "name": "format_recipe",
            "description": "Format a cooking recipe with ingredients and steps",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the recipe"
                    },
                    "ingredients": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "quantity": {
                                    "type": "string",
                                    "description": "The quantity of the ingredient (e.g., '2', '1/4', '3-4')"
                                },
                                "unit": {
                                    "type": "string",
                                    "description": "The unit of measurement (e.g., 'cup', 'tablespoon', 'piece')"
                                },
                                "name": {
                                    "type": "string",
                                    "description": "The name of the ingredient"
                                },
                                "preparation": {
                                    "type": "string",
                                    "description": "Optional preparation instruction (e.g., 'diced', 'minced')"
                                }
                            },
                            "required": ["name"]
                        },
                        "description": "List of ingredients with quantities adjusted for the number of servings"
                    },
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Step-by-step cooking instructions, each step should be concise and actionable"
                    },
                    "prep_time_minutes": {
                        "type": "integer",
                        "description": "Estimated preparation time in minutes"
                    },
                    "cook_time_minutes": {
                        "type": "integer",
                        "description": "Estimated cooking time in minutes"
                    }
                },
                "required": ["title", "ingredients", "steps"]
            }
        }]
        
        response = self.get_response(user_prompt, system_prompt, functions=recipe_function)
        
        # Parse the JSON response
        import json
        try:
            recipe_data = json.loads(response)
            return recipe_data
        except json.JSONDecodeError:
            # Fallback to text parsing if JSON parsing fails
            steps = []
            for line in str(response).split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    clean_step = line.lstrip('0123456789.-• ').strip()
                    if clean_step:
                        steps.append(clean_step)
            
            return {"title": recipe_name, "ingredients": [], "steps": steps if steps else [str(response)]}
        
    def guide_step(self, step_description: str, user_question: Optional[str] = None) -> str:
        if user_question:
            system_prompt = f"""You are guiding someone through this cooking step: {step_description}
            Answer their question helpfully and concisely."""
            return self.get_response(user_question, system_prompt)
        else:
            return f"Current step: {step_description}\n\nType 'next' to continue, or ask a question about this step."
            
    def reset_conversation(self):
        self.conversation_history = []
