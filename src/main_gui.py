import tkinter as tk
import os
from dotenv import load_dotenv
from src.gui_cooking_assistant import GUICookingAssistant

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Check if API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY not found in environment or .env file")
        print("Please add your OpenAI API key to a .env file in the project root")
        print("Format: OPENAI_API_KEY=your_api_key_here")
        return
    
    root = tk.Tk()
    app = GUICookingAssistant(root)
    root.mainloop()

if __name__ == "__main__":
    main()
