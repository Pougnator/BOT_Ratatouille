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
        
    def get_response(self, user_input: Optional[str] = None, system_prompt: Optional[str] = None) -> str:
        if system_prompt:
            self.add_system_message(system_prompt)
            
        if user_input:
            self.add_user_message(user_input)
            
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.conversation_history,
                temperature=0.7,
                max_tokens=1000
            )
            
            assistant_message = response.choices[0].message.content
            if assistant_message is None:
                assistant_message = "No response from LLM"
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
        except Exception as e:
            return f"Error communicating with LLM: {str(e)}"
            
    def propose_recipes(self, ingredients: list) -> str:
        ingredients_str = ", ".join(ingredients)
        system_prompt = """You are a helpful cooking assistant. Based on the ingredients provided, 
        suggest 3 different recipes. For each recipe, provide:
        1. Recipe name
        2. Brief description
        3. Difficulty level (Easy/Medium/Hard)
        Format your response as a numbered list."""
        
        user_prompt = f"I have these ingredients: {ingredients_str}. What recipes can I make?"
        
        return self.get_response(user_prompt, system_prompt)
        
    def get_recipe_steps(self, recipe_name: str, ingredients: list) -> list:
        ingredients_str = ", ".join(ingredients)
        system_prompt = """You are a helpful cooking assistant. Provide clear, step-by-step cooking 
        instructions for the requested recipe. Each step should be concise and actionable. 
        Include timing information where relevant. Format as a numbered list with one step per line."""
        
        user_prompt = f"Give me detailed cooking steps for {recipe_name} using these ingredients: {ingredients_str}"
        
        response = self.get_response(user_prompt, system_prompt)
        
        steps = []
        for line in response.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                clean_step = line.lstrip('0123456789.-• ').strip()
                if clean_step:
                    steps.append(clean_step)
                    
        return steps if steps else [response]
        
    def guide_step(self, step_description: str, user_question: Optional[str] = None) -> str:
        if user_question:
            system_prompt = f"""You are guiding someone through this cooking step: {step_description}
            Answer their question helpfully and concisely."""
            return self.get_response(user_question, system_prompt)
        else:
            return f"Current step: {step_description}\n\nType 'next' to continue, or ask a question about this step."
            
    def reset_conversation(self):
        self.conversation_history = []
