import asyncio
import os
from dotenv import load_dotenv
from src.cooking_assistant import CookingAssistant


def main():
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please set your OpenAI API key to use this application.")
        return
        
    assistant = CookingAssistant()
    asyncio.run(assistant.run())


if __name__ == "__main__":
    main()
