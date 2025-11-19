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
        system_prompt = """You are a helpful cooking assistant. Provide a detailed recipe with ingredients and very detailed step-by-step instructions.
        
        KEY REQUIREMENTS:
        1. Break down each cooking action into atomic, granular steps (e.g., 'éplucher les carottes', 'couper les patates en dés', etc.).
        2. Make sure each step focuses on ONE specific action.
        3. Use precise French cooking terminology.
        4. MOST IMPORTANT: Create logical dependencies between steps by listing prerequisite steps in the "dependencies" array.
           - If step B can only be done after step A is completed, then step B should have step A's ID in its dependencies array.
           - For example, if step 3 (id: "3") requires steps 1 and 2 to be completed first, its dependencies would be ["1", "2"].
           - Be precise about logical dependencies - for example, water must be boiling before pasta can be added to it.
           - Parallel tasks (that can be done simultaneously) should NOT depend on each other.
        
        Example dependency structure:
        Step 1: "Éplucher les carottes" - No dependencies, can be done first
        Step 2: "Couper les carottes en dés" - Depends on step 1 (dependencies: ["1"])
        Step 3: "Porter l'eau à ébullition" - No dependencies, can be done in parallel with steps 1 and 2
        Step 4: "Ajouter les pâtes dans l'eau bouillante" - Depends on step 3 (dependencies: ["3"])
        Step 5: "Ajouter les carottes aux pâtes" - Depends on steps 2 and 4 (dependencies: ["2", "4"])"""
        
        user_prompt = f"""Give me a recipe for {recipe_name} for {servings} people using these ingredients: {ingredients_str}.
        
CRITICAL: Make sure to include logical dependencies between the steps!

For example, if your recipe has these steps:
1. "Éplucher les pommes de terre" (id: "1")
2. "Couper les pommes de terre en dés" (id: "2")
3. "Faire bouillir l'eau dans une casserole" (id: "3")
4. "Cuire les pommes de terre dans l'eau bouillante" (id: "4")

Then the dependencies should be:
- Step 1 has no dependencies: []
- Step 2 depends on step 1: ["1"]
- Step 3 has no dependencies: []
- Step 4 depends on steps 2 AND 3: ["2", "3"]

This is essential for creating an accurate timeline!"""
        
        recipe_function = [{
            "name": "format_recipe",
            "description": "Format a cooking recipe with ingredients and detailed steps with logical dependencies between steps",
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
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "description": "Unique identifier for this step"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Detailed description of the cooking action, very specific and granular"
                                },
                                "duration_minutes": {
                                    "type": "number",
                                    "description": "Estimated duration in minutes to complete this step"
                                },
                                "dependencies": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    },
                                    "description": "IDs of steps that must be completed before this one. IMPORTANT: This should almost never be empty - most cooking steps depend on previous steps!"
                                }
                            },
                            "required": ["id", "description", "duration_minutes"]
                        },
                        "description": "Detailed step-by-step cooking instructions, each step should be a specific, atomic action"
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
