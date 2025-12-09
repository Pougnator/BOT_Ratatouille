from prompts import system_prompt, user_prompt, RecipesList
from google import genai
import os
from dotenv import load_dotenv
from typing import Optional
import json
import time

class LLMAgent:

   
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"
        self.llm_config = genai.types.GenerateContentConfig(
            thinking_config=genai.types.ThinkingConfig(thinking_budget=512)
        )
        self.system_prompt = system_prompt
        self.conversation_history = []
        self.chat = None  # Will be created when needed
       
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
        
    def get_response(self, user_input: str = "", system_prompt: str = "", structured_format=None, model: Optional[str] = None) -> str:
        """Get response from Gemini API using chat."""
        # Use instance model if not specified
        model_to_use = model or self.model
        
        try:
            # Prepare config with structured output if needed
            config = genai.types.GenerateContentConfig(
                thinking_config=genai.types.ThinkingConfig(thinking_budget=512)
            )
            if structured_format:
                config.response_mime_type = "application/json"
                config.response_json_schema = structured_format.model_json_schema()
            else: 
                config.response_mime_type = "text/plain"
                config.response_json_schema = None

            full_prompt = system_prompt + "\n\n" + user_input
        
            # Measure LLM call time
            start_time = time.time()
            response = self.client.models.generate_content(model = model_to_use,  contents = full_prompt, config = config)
            llm_time = time.time() - start_time
            print(f"[TIMING] LLM call ({model_to_use}): {llm_time:.2f}s")
            
            message = response.text
            
            if structured_format:
                response_dict = json.loads(message)
                return response_dict
            else:
                return message
        
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"
            
    def propose_recipes(self, ingredients: list, servings: int = 2, additional_request: str = None) -> str:
        start_time = time.time()
        ingredients_str = ", ".join(ingredients)
        user_prompt = f"J'ai les ingrédients suivants : {ingredients_str}. Je cuisine pour {servings} personnes."
        if additional_request:
            user_prompt += f" {additional_request}"
        else:
            user_prompt += " Quelles recettes peux-tu me proposer ? Sois concis."
        
       
        saved_history = self.conversation_history.copy()
        self.conversation_history = []
        
        try:
            response = self.get_response(user_prompt, self.system_prompt, structured_format=RecipesList, model=None)
            total_time = time.time() - start_time
            print(f"[TIMING] propose_recipes total: {total_time:.2f}s")
            return response
        except Exception as e:
            print(f"Error in propose_recipes: {e}")
            return {"recipes": []}
        finally:
            self.conversation_history = saved_history

    # def explain_ingredients_naturally(self, ingredients: list, recipe_name: str, recipe_steps: list) -> str:
    #     system_prompt = "You are a helpful cooking assistant. Explain the ingredients I need for a recipe in a natural way that is easy to understand."
    #     user_prompt = f"I have these ingredients: {ingredients}. I'm cooking the folowing recipe: :{recipe_name} and i am using the following steps: {recipe_steps}. Please use a concise and natural language to summarise the list of ingredients and the quantities i need"
    #     return self.get_response(user_prompt, system_prompt)
        

    def get_recipe_steps(self, recipe_name: str, ingredients: list, servings: int = 2) -> dict:
        start_time = time.time()
        # Ingredients are expected to be the structured list coming from recipe proposals:
        # [{"name": ..., "quantity": ..., "unit": ..., "preparation": ...}, ...]
        def _fmt_ing(ing) -> str:
            # Ingredients MUST be dicts in the expected structured format.
            if isinstance(ing, dict):
                name = str(ing.get("name", "")).strip()
                qty = str(ing.get("quantity", "")).strip()
                unit = str(ing.get("unit", "")).strip()
                prep = str(ing.get("preparation", "")).strip()
                parts = []
                if qty:
                    parts.append(qty)
                if unit:
                    parts.append(unit)
                if name:
                    parts.append(name)
                base = " ".join(parts).strip() or name or "ingrédient"
                if prep:
                    return f"{base} ({prep})"
                return base
            # If we ever get here, it means the calling code passed a wrong format.
            raise TypeError(f"Invalid ingredient format in get_recipe_steps: expected dict, got {type(ing).__name__} -> {ing!r}")

        ingredients_str = ", ".join(_fmt_ing(i) for i in ingredients)
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
1. Quels ingrédients sont utilisés dans cette étape? N'oublies pas d'inclure les epices et les condiments, avec les quanités associés.
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

Ces relations de dépendance sont ESSENTIELLES pour générer un diagramme de Gantt précis et utile!

IMPORTANT: N'oublie pas que les épices et les condiments sont aussi très important, même si l'utilisateur ne va que très rarement les entrer dans la liste d'ingrédients disponibles.
Donc n'hésite pas à les inclure toi même dans les recettes que tu proposes. Les épices et les condiments sont l'âme de la cuisine.
Il est crucial de les inclure dans les recettes que tu proposes, car elles font toute la saveur. Soit également très précis sur les quantités de chaque condiments, et mesures cette quantité en grammes.
Par exemple: piment de cayenne 10g, poivre noir 3g, poudre de curry 30g, etc 

Certains ingrédients peuvent être optionnels pour rendre la recette encore plus délicieuse. Tu dois les mentionner avec le prefixe (optionnel: )

"""

        
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

        try:
            recipe_data = json.loads(response)
            total_time = time.time() - start_time
            print(f"[TIMING] get_recipe_steps total: {total_time:.2f}s")
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
        self.chat = None  # Reset chat to start fresh conversation
        
    # Fonction de raccourcissement des étapes supprimée


if __name__ == "__main__":
    agent = LLMAgent()
    ingredients = ["carottes", "oignons", "riz", "huile d'olive", "eau"]
    recipes = agent.propose_recipes(ingredients)
    try:
        response_dict = recipes
        for recipe in response_dict["recipes"]:
            print(recipe["recipe_name"] + " - " + recipe["recipe_difficulty"])
            ingredients_text = ""
            for ingredient in recipe["recipe_ingredients"]:
                ingredients_text += ingredient["name"] + " " + str(ingredient["quantity"]) + " " + ingredient["units"] + ", "
            print(ingredients_text)
            print("--" * 60 + "\n")
    except Exception as e:
        print(f"Error in reading recipes: {e}")
    
    # Format conversation history and recipes for context
    history_str = json.dumps(agent.conversation_history, ensure_ascii=False, indent=2)
    recipes_str = json.dumps(recipes, ensure_ascii=False, indent=2)
    total_conversation_history = f"Voici l'historique de nos conversations: {history_str}\n\nRéponse de l'agent (recettes): {recipes_str}"
    # response = agent.get_response(user_input = 'Dis mois en plus sur la premiere recette', system_prompt = total_conversation_history)
    # print(response)
    chat = agent.client.chats.create(model = "gemini-2.5-flash")
    print("-" * 40)
    print("Dis moi en plus sur la premiere recette")
    chat_response = chat.send_message('Dis moi en plus sur la premiere recette' + "\n\n" + total_conversation_history)
    print(chat_response.text)
    print("-" * 40)
    print("Et dis moi en un peu sur la deuxième")
    chat_response = chat.send_message('Et dis moi en un peu sur la deuxième')
    print(chat_response.text)     
    message3 = "Tu peux me décrire la deuxième recette en détail"
    print("-"*60)
    chat_response = chat.send_message(message3)
    print(chat_response.text)
    