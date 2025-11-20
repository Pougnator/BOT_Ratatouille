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
        system_prompt = """Tu es un chef de cuisine d'un grand restaurant excellent en cuisine et en recettes. À partir des ingrédients fournis, 
        suggère 4 recettes différentes, delicieuses et qui donnent envie. N'hésites pas à utiliser les recettes de marmitton ou autres sites populaires de recettes. 
        Pour chaque recette, indique :
        1. Nom de la recette, comme si on était dans un restaurant étoilé, penses à un nom qui donne envie et qui est unique. Si c'est une recette d'un pays particulier, utilises le nom original de cette recette dans son pays d'origine.
        Par exemple: au lieu de dire **Riz sauté aux œufs et tomates** tu vas dire **Fanqie Chao Fan - Riz sauté aux œufs et tomates**
        2. Brief description
        3. Difficulty level (Easy/Medium/Hard)
        The first recipe should use all of the ingredients provided. 
        The other recipes could be gradually more flexible, but must be delicious and use at least some of the ingredients provided. They could also could also incorporate some additional but very common ingredients.
        Also try to make sure that the reciepies you propose have some variety in terms of geographic origin, like french, italian, japanese, etc.  At least one of the recipes should be non european.
        Try to think about what region in the country the recipe is from, because different regions also introduce variety in terms of ingredients and cooking techniques. You can tell a bit about the region in the description of the recipe.
        The recipes should be in French.
        
        Format your response as a numbered list."""
        
        long_term_memory = "You will exclude the following ingredients from the reciepe: meat, ognions. Also, I don't have an oven so you will exclude recipes that require an oven "
        user_prompt = f"I have these ingredients: {ingredients_str}. I'm cooking for {servings} people."
        
        system_prompt += long_term_memory
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
        system_prompt = """Tu es un chef francais, amoureux de la cuisine et de recettes du monde. Tu es un expert très amical et sympatique en cuisine et en recettes. Tu es capable de créer des recettes à partir d'ingrédients et de les détailler en étapes de cuisine.
        
        KEY REQUIREMENTS:
        1. Break down each cooking action into atomic, granular steps (e.g., 'éplucher les carottes', 'couper les patates en dés', etc.).
        2. Make sure each step focuses on ONE specific action. 
        N'oublie pas que les étapes de cuisine sont des actions très précises et détaillées.
        Par exemple la pluspart d'éléments doivent être épluchés et/ou coupés avant d'être utilisés. 
        Assures toi que ces étapes, si nécessaires, sont incluses dans les étapes de la recette.
        3. Use precise French cooking terminology.
        4. ABSOLUMENT CRITIQUE : Crée des dépendances logiques détaillées et précises entre les étapes dans le tableau "dependencies".
           - CHAQUE étape qui transforme ou utilise un ingrédient DOIT dépendre des étapes qui ont préparé cet ingrédient.
           - Si un ingrédient doit être lavé, épluché, coupé ou préparé, alors TOUTES les étapes ultérieures utilisant cet ingrédient DOIVENT lister ces étapes de préparation comme dépendances.
           - Par exemple, si l'étape 3 utilise des carottes qui ont été épluchées à l'étape 1 et coupées à l'étape 2, l'étape 3 DOIT avoir ["1", "2"] comme dépendances.
           - TOUTES les étapes de cuisson DOIVENT dépendre des étapes de préparation correspondantes.
           - La chaîne de dépendances doit être complète et ininterrompue tout au long de la recette.
           - La cuisson d'un ingrédient ne peut pas commencer avant que sa préparation ne soit terminée.
           - Sois extrêmement minutieux - même les dépendances évidentes doivent être explicitement listées.
           - Les tâches parallèles (qui peuvent être effectuées simultanément avec différents ingrédients) ne doivent PAS dépendre les unes des autres.
        
        Example dependency structure:
        Step 1: "Laver les carottes" - Pas de dépendance
        Step 2: "Éplucher les carottes" - Depend de l'étape 1 (dependencies: ["1"])
        Step 3: "Couper les carottes en dés" - Depends on step 2 (dependencies: ["2"])
        Step 4: "Porter l'eau à ébullition" - No dependencies, can be done in parallel with steps 1 and 2 and 3
        Step 5: "Ajouter les pâtes dans l'eau bouillante" - Depends on step 4 (dependencies: ["4"])
        Step 6: "Ajouter les carottes aux pâtes" - Depends on steps 3 and 5 (dependencies: ["3", "5"])"""
        
        user_prompt = f"""Give me a recipe for {recipe_name} for {servings} people using these ingredients: {ingredients_str}.
        
ABSOLUTELY CRITICAL: Les dépendances logiques entre les étapes doivent être COMPLÈTES et PRÉCISES!

Pour chaque étape, pose-toi ces questions:
1. Quels ingrédients sont utilisés dans cette étape?
2. Quelles étapes préalables ont préparé ou transformé ces ingrédients?
3. Est-ce que TOUTES ces étapes préalables sont listées comme dépendances?

Exemple détaillé - une recette de risotto:
1. "Éplucher les oignons" (id: "1") - Pas de dépendance: []
2. "Hacher finement les oignons" (id: "2") - Dépend de l'étape 1: ["1"] 
3. "Laver le riz" (id: "3") - Pas de dépendance: []
4. "Chauffer l'huile d'olive dans une poêle" (id: "4") - Pas de dépendance: []
5. "Faire revenir les oignons dans l'huile" (id: "5") - Dépend des étapes 2 ET 4: ["2", "4"]
6. "Ajouter le riz dans la poêle et le nacrer" (id: "6") - Dépend des étapes 3 ET 5: ["3", "5"]

RAPPEL: Chaque fois qu'un ingrédient est utilisé, TOUTES les étapes de sa préparation doivent être des dépendances!

Ces relations de dépendance sont ESSENTIELLES pour générer un diagramme de Gantt précis et utile!"""
        
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
                                    "description": "IDs of ALL prerequisite steps that MUST be completed before this one. CRITICAL: This should be EXHAUSTIVE - include ALL steps that prepared ingredients used in this step. An ingrédient cannot be used before ALL its preparation steps are completed. DO NOT MISS ANY DEPENDENCY!"
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
        
    # Fonction de raccourcissement des étapes supprimée
