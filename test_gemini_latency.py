"""Test script to measure Google Gemini latency with the same recipe prompt.

Requires:
- python -m pip install google-generativeai python-dotenv
- GOOGLE_API_KEY set in your environment or .env file
"""
import json
import os
import time
from dotenv import load_dotenv
from src.prompts import system_prompt, user_prompt, ingredients_str, servings
from google import genai

from typing import List
from src.prompts import RecipesList


load_dotenv()
GEMINI_MODEL = "gemini-2.5-flash"
myconfig = genai.types.GenerateContentConfig(
        thinking_config=genai.types.ThinkingConfig(thinking_budget=512) )# Disables thinking
myconfig.response_mime_type = "application/json"
myconfig.response_json_schema = RecipesList.model_json_schema()
# myconfig.tools = [
#             {"google_search": {}},
#             {"url_context": {}}]
       

def configure_gemini():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment")
    client = genai.Client(api_key=api_key)
    return client


def test_gemini_latency(stream: bool = False, client = None):
    """Run one latency test on Gemini with or without streaming."""
   
  

   

    print("=" * 60)
    print(f"TEST Gemini ({'streaming' if stream else 'non-streaming'})")
    print("=" * 60)
    print(f"Model: {GEMINI_MODEL}")
    print()

    full_prompt = system_prompt + "\n\n" + user_prompt

    start_time = time.time()

  
    print("[NON-STREAM] Starting generate_content...\n")
    response = client.models.generate_content(model = GEMINI_MODEL, contents = full_prompt, config = myconfig)
    response_text = response.text
    # print(type(response_text))
    response_dict = json.loads(response_text)
    # recipe = RecipesList.model_validate_json(response_text)
    
    # response_dict is a dict with a "recipes" key containing the list
    recipes_list = response_dict.get("recipes", [])
    for recipe in recipes_list:
        print(recipe["recipe_name"] + " - " + recipe["recipe_difficulty"])
        ingredients_text = ""  # Initialize before the loop
        for ingredient in recipe["recipe_ingredients"]:
            ingredients_text += ingredient["name"] + " " + str(ingredient["quantity"]) + " " + ingredient["units"] + ", "
        print(ingredients_text)
        print("--" * 60 + "\n")
    usage = getattr(response, "usage_metadata", None)
    
    # print(response_text)

    total_time = time.time() - start_time

    print("\n" + "-" * 60)
    print(f"Total time: {total_time:.2f}s")
    if usage:
        prompt_tokens = getattr(usage, "prompt_token_count", None)
        output_tokens = getattr(usage, "candidates_token_count", None)
        total_tokens = getattr(usage, "total_token_count", None)
        print(f"Prompt tokens: {prompt_tokens}")
        print(f"Output tokens: {output_tokens}")
        print(f"Total tokens: {total_tokens}")
        if output_tokens and total_time > 0:
            speed = output_tokens / total_time
            print(f"Speed: {speed:.1f} tokens/s")

    print("=" * 60)
    return total_time, usage


if __name__ == "__main__":
    full_prompt = system_prompt + "\n\n" + user_prompt
    print("\nRunning Gemini latency tests (no threading)...\n")
    print(full_prompt)
    client = genai.Client()
    # Run a few non-streaming tests
    times = []
    for i in range(3):
        print(f"\n>>> Gemini non-stream run {i+1}/3 <<<\n")
        t, _ = test_gemini_latency(stream=False, client=client)
        times.append(t)
        if i < 2:
            print("\nWaiting 0.5 seconds before next test...\n")
            time.sleep(0.5)

    print("\n" + "=" * 60)
    print("NON-STREAM SUMMARY")
    print("=" * 60)
    print(f"Runs: {len(times)}")
    print(f"Average time: {sum(times)/len(times):.2f}s")
    print(f"Min time: {min(times):.2f}s")
    print(f"Max time: {max(times):.2f}s")
    print("=" * 60)




