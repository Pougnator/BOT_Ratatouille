"""Test script to measure LLM latency without threading, using Responses API streaming."""
import os
import time
import json
from openai import OpenAI
from dotenv import load_dotenv
from src.prompts import system_prompt, user_prompt, ingredients_str, servings
from src.prompts import RecipesList, Ingredient


# Load environment variables
load_dotenv()

# Model for latency tests with Responses API (streaming)
MODEL = "gpt-4o-mini"  # ou autre modèle Responses dispo sur ton compte

def initialize_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")
    client = OpenAI(api_key=api_key)
    return client

def test_recipe_proposal(client = None):
  

    messages = [
        {"role": "developer", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

  
    model = MODEL
    
    print("=" * 60)
    print(model)
    # Measure time (Responses API streaming - no threading)
    start_time = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] Starting LLM call...")
    

    usage = None
    # Print response progressively as events arrive (simple case: text deltas)
    
    def streaming_call():
        full_text = []
        print("Sending stream request...")
        stream = client.responses.create(
            model=model,
            input=messages,
            reasoning={"effort": "low"},
            # input = "Write a one-sentence bedtime story about a unicorn.",
            # max_output_tokens=1000,
            stream=True,
        )



        print("Streaming response...")
        for event in stream:
            if getattr(event, "type", None) == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                # Dans ce flux, delta est déjà une chaîne (voir la console)
                text_piece = str(delta)
                print(text_piece, end="", flush=True)
                full_text.append(text_piece)
        return full_text
    
    def non_streaming_call():
        response = cresponse = client.responses.parse(

            model=model,
            input=messages,
            # reasoning={"effort": "low"},
            # input = "Write a one-sentence bedtime story about a unicorn.",
            # max_output_tokens=1000,
            stream=False,
            text_format=RecipesList
        )
        print(response.output_text)
        return True

    non_streaming_call()
     

    end_time = time.time()
    total_time = end_time - start_time

    # assistant_message = "".join(full_text)

    print(f"\n[{time.strftime('%H:%M:%S')}] LLM streaming completed")
    print()
    print("RESULTS:")
    print("-" * 60)
    print(f"Total time: {total_time:.2f}s")
    
    if usage:
        tokens_per_sec = usage.completion_tokens / total_time if total_time > 0 else 0
        print(f"Input tokens: {usage.prompt_tokens}")
        print(f"Output tokens: {usage.completion_tokens}")
        print(f"Total tokens: {usage.total_tokens}")
        print(f"Speed: {tokens_per_sec:.1f} tokens/s")
    
    print()
    print("Response :")
    print("-" * 60)
    # print(str(assistant_message))
    print()
    
   
    
    return total_time, usage

if __name__ == "__main__":
    print("\nRunning latency test (no threading)...\n")
    
    # Run test multiple times to see variance
    client = initialize_client()
    times = []
    for i in range(3):
        print(f"\n>>> Test run {i+1}/3 <<<\n")
        total_time, usage = test_recipe_proposal(client)
        times.append(total_time)
        if i < 2:
            print("\nWaiting 0.2 seconds before next test...\n")
            time.sleep(0.2)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Runs: {len(times)}")
    print(f"Average time: {sum(times)/len(times):.2f}s")
    print(f"Min time: {min(times):.2f}s")
    print(f"Max time: {max(times):.2f}s")
    print("=" * 60)

