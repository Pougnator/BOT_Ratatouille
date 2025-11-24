import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import threading
import time
import sys
import io
import os
import asyncio
from datetime import datetime, timedelta

# Handle imports for both direct execution and package import
if __name__ == "__main__":
    # When run directly, use absolute imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.states import StateMachine, CookingState
    from src.cooking_assistant import CookingAssistant
else:
    # When imported as part of the package, use relative imports
    from .states import StateMachine, CookingState
    from .cooking_assistant import CookingAssistant

class ConsoleRedirector:
    """Redirects stdout and stdin to the GUI console"""
    def __init__(self, text_widget, gui_app):
        self.text_widget = text_widget
        self.gui_app = gui_app
        self.buffer = ""
        self.line_buffer = ""
        
    def strip_ansi_codes(self, text):
        """Remove ANSI color codes from text"""
        import re
        # This pattern matches ANSI escape codes like [32m, [0m, etc.
        ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_pattern.sub('', text)
        
    def write(self, string):
        """Write text to the console and process it for specific content types"""
        self.buffer += string
        
        # Strip ANSI color codes before displaying
        clean_string = self.strip_ansi_codes(string)
        
        # Add text to the console
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, clean_string)
        self.text_widget.see(tk.END)
        self.text_widget.config(state=tk.DISABLED)
        
        # Process the text to extract useful information
        self.line_buffer += clean_string
        
        # Check if we've received a complete line
        if '\n' in self.line_buffer:
            lines = self.line_buffer.split('\n')
            self.line_buffer = lines[-1]  # Keep the incomplete line
            
            # Process each complete line
            for line in lines[:-1]:
                self.process_line(line)
        
    def process_line(self, line):
        """Process a line of output for specific content"""
        # Check for ingredients section
        if "Ingrédients:" in line or "Ingredients:" in line:
            self.gui_app.collecting_ingredients = True
            self.gui_app.ingredients_text = line + "\n"
            return
            
        # # If we're collecting ingredients, add to the ingredients
        # if self.gui_app.collecting_ingredients:
        #     # Check if we've reached the end of ingredients section
        #     if line.strip() == "" or "Étapes" in line or "Steps" in line:
        #         self.gui_app.collecting_ingredients = False
        #         # Update ingredients display
        #         self.gui_app.root.after(0, lambda: self.gui_app.update_ingredients(self.gui_app.ingredients_text))
        #     else:
        #         self.gui_app.ingredients_text += line + "\n"
                
        # # Check for recipe steps
        # if "Étapes de préparation" in line or "Preparation Steps" in line:
        #     self.gui_app.collecting_steps = True
        #     self.gui_app.steps_text = line + "\n"
        #     return
            
        # If we're collecting steps, add to the steps
        if self.gui_app.collecting_steps:
            # Check if we've reached the end of steps section
            if line.strip() == "" and self.gui_app.steps_text.count('\n') > 3:
                self.gui_app.collecting_steps = False
                # Create simple Gantt chart for steps
                self.gui_app.root.after(0, lambda: self.gui_app.create_simple_gantt(self.gui_app.steps_text))
            else:
                self.gui_app.steps_text += line + "\n"
        
    def flush(self):
        pass
        
    def readline(self):
        """Read a line of input from the GUI"""
        # Set visual cue that we're waiting for input
        self.gui_app.root.after(0, self.gui_app.show_input_prompt)
        self.gui_app.waiting_for_input = True
        self.gui_app.input_ready.clear()
        
        # Wait for input_ready event to be set
        while not self.gui_app.input_ready.is_set():
            time.sleep(0.1)
            
        # Reset input state
        self.gui_app.waiting_for_input = False
        self.gui_app.root.after(0, self.gui_app.hide_input_prompt)
        
        input_text = self.gui_app.last_input + '\n'
        return input_text

class GUICookingAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("r0[BOT]t@toui11e")
        self.root.geometry("800x600")  # Adjusted for 800x600 display
        
        # Try to detect if we're on a small screen and go fullscreen if needed
        if root.winfo_screenwidth() <= 800:
            root.attributes('-fullscreen', True)
            
        # You cannot set a ttk style for the Toplevel/root window itself; use configure for bg color.
        # For a "black style" look, set root bg to black here (other ttk widgets can get styled separately).
        self.root.configure(bg="black")
        
        
        # Command history
        self.command_history = []
        self.history_index = 0
        
        # Input handling for redirecting to cooking assistant
        self.waiting_for_input = False
        self.input_ready = threading.Event()
        self.last_input = ""
        
        # Content tracking
        self.collecting_ingredients = False
        self.ingredients_text = "Text will be added here"
        self.collecting_steps = False
        self.steps_text = "Some text will be added here for steps"
        
        # Cooking assistant
        self.cooking_assistant = None
        self.assistant_thread = None
        
        # Setup the GUI components
        self._setup_gui()
        
        # Show welcome message
        self.display_welcome()

    def _setup_gui(self):
        # SIMPLEST APPROACH: Just use one PanedWindow with fixed sash position
        
        # Go back to using tk.PanedWindow which has better direct position control
        self.main_pane = tk.PanedWindow(self.root, orient=tk.VERTICAL, 
                                       bg="black", sashwidth=4, sashrelief=tk.RAISED)
        self.main_pane.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Create top frame for console
        self.top_pane = tk.Frame(self.main_pane, bg="black")
        
        # Create bottom frame for ingredients and gantt
        self.bottom_container = tk.Frame(self.main_pane, bg="black")
        
        # We'll add the frames with weights at the end of _setup_gui
        
        # Setup the console
        self._setup_console_pane()
        
        # Create horizontal split for bottom section - switch back to ttk.PanedWindow which supports weight
        self.bottom_pane = ttk.PanedWindow(self.bottom_container, orient=tk.HORIZONTAL)
        self.bottom_pane.pack(fill="both", expand=True)
        
        # Setup ingredients and gantt areas
        self._setup_bottom_pane()
        
        # First add the panes without weights
        self.main_pane.add(self.top_pane)
        self.main_pane.add(self.bottom_container)
        
        # Then force the sash position after a small delay to ensure the window is fully created
        def set_position():
            # Get the window height
            window_height = self.root.winfo_height()
            if window_height > 100:  # Make sure window is properly sized
                # Set the position at 60% of window height (as per your adjustment)
                sash_pos = int(window_height * 0.7)
                
                # For tk.PanedWindow, use the correct method
                self.main_pane.update()
                self.main_pane.sash_place(0, 0, sash_pos)
        
        # Call after a delay
        self.root.update()
        self.root.after(200, set_position)  # Increased delay for better reliability
        
    def _setup_console_pane(self):
        # Simplest approach - direct setup without nested frames
        
        # Use a container frame for both output and input
        self.console_container = tk.Frame(self.top_pane, bg="black")
        self.console_container.pack(fill="both", expand=True)
        
        # Set grid layout to ensure input is always visible
        self.console_container.grid_rowconfigure(0, weight=1)  # Output expands
        self.console_container.grid_rowconfigure(1, weight=0, minsize=40)  # Input has minimum height
        self.console_container.grid_columnconfigure(0, weight=1)
        
        # Console output area - now in the container
        self.console_output = scrolledtext.ScrolledText(
            self.console_container, 
            wrap=tk.WORD, 
            font=("Consolas", 11),
            bg="black", 
            fg="lime",
            insertbackground="green"
        )
        
        # Place in the first row with grid instead of pack
        self.console_output.grid(row=0, column=0, sticky="nsew", padx=5, pady=(2, 2))
        self.console_output.config(state=tk.DISABLED)  # Start disabled
        
        # Setup stdout/stdin redirection
        self.console_redirector = ConsoleRedirector(self.console_output, self)
        
        # Input area - now in the container with guaranteed space (no border)
        self.input_frame = tk.Frame(
            self.console_container, 
            bg="black",
            height=30  # Fixed height
        )
        # Place in second row with grid - this ensures it's always visible
        self.input_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.input_frame.grid_propagate(False)  # Prevent shrinking

        # For improved layout control, use grid inside the input frame
        self.input_frame.grid_columnconfigure(1, weight=1)  # Entry expands
        
        # Prompt label - use standard tk widgets for direct styling
        self.prompt_label = tk.Label(
            self.input_frame, 
            text="> ", 
            font=("Consolas", 14, "bold"),
            fg="lime",
            bg="black"
        )
        self.prompt_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        # Input waiting indicator - use standard tk widgets
        self.input_indicator = tk.Label(
            self.input_frame,
            text="[Input required]",
            font=("Consolas", 11),
            fg="lime",
            bg="black"
        )
        # Will be placed when needed using grid at column 3
        
        # Console input - use standard tk Entry for direct styling
        self.console_input = tk.Entry(
            self.input_frame, 
            font=("Consolas", 11),
            bg="black",
            fg="lime",
            insertbackground="lime"  # Cursor color
        )
        self.console_input.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Set up key bindings for input
        self.console_input.bind("<Return>", self.process_command)
        self.console_input.bind("<Up>", self.show_previous_command)
        self.console_input.bind("<Down>", self.show_next_command)
        
        # # Start button - use standard tk Button with bright colors
        # self.start_button = tk.Button(
        #     self.input_frame,
        #     text="Start Assistant",
        #     command=self.start_cooking_assistant,
        #     font=("Consolas", 10, "bold"),
        #     fg="black",
        #     bg="lime",
        #     activebackground="green",
        #     activeforeground="white"
        # )
        # self.start_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        # Focus on the input field
        self.console_input.focus_set()
        
    def _setup_bottom_pane(self):
        # Ingredients list (left)
        self.ingredients_frame = ttk.Frame(self.bottom_pane)
        
        ingredients_label = ttk.Label(self.ingredients_frame, text="Ingredients", font=("Helvetica", 12, "bold"))
        ingredients_label.pack(padx=5, pady=2)
        
        self.ingredients_box = tk.Text(self.ingredients_frame, width=30, font=("Courier", 14), bg="#f0f0f0")
        self.ingredients_box.pack(fill="both", expand=True, padx=5, pady=5)
        self.ingredients_box.config(state=tk.DISABLED)
        
        self.bottom_pane.add(self.ingredients_frame, weight=1)
        
        # Gantt chart (right) - simplified placeholder for now
        self.gantt_frame = ttk.Frame(self.bottom_pane)
        
        gantt_label = ttk.Label(self.gantt_frame, text="Recipe Timeline", font=("Helvetica", 12, "bold"))
        gantt_label.pack(padx=5, pady=5)
        
        self.gantt_box = tk.Text(self.gantt_frame, width=50, bg="black", fg="lime", font=("Courier", 12))
        self.gantt_box.pack(fill="both", expand=True, padx=5, pady=2)
        self.gantt_box.insert(tk.END, "Gantt chart will appear here")
        self.gantt_box.config(state=tk.DISABLED)
        
        self.bottom_pane.add(self.gantt_frame, weight=2)
    
   
    
    def clear_console(self):
        """Clear the console output"""
        self.console_output.delete(1.0, tk.END)
    
    def quit_application(self):
        """Exit the application"""
        if messagebox.askyesno("Quit", "Are you sure you want to quit?"):
            self.root.quit()
            
    def update_ingredients(self, ingredients_text):
        """Update the ingredients panel with provided text"""
        self.ingredients_box.config(state=tk.NORMAL)
        self.ingredients_box.delete(1.0, tk.END)
        self.ingredients_box.insert(tk.END, ingredients_text)
        self.ingredients_box.config(state=tk.DISABLED)
    
    def set_ingredients(self, ingredients_text):
        self.ingredients_box.config(state=tk.NORMAL)
        self.ingredients_box.delete(1.0, tk.END)
        self.ingredients_box.insert(tk.END, ingredients_text)
        self.ingredients_box.config(state=tk.DISABLED)
    
    def set_gantt(self, gantt_text):
        self.gantt_box.config(state=tk.NORMAL)
        self.gantt_box.delete(1.0, tk.END)
        self.gantt_box.insert(tk.END, gantt_text)
        self.gantt_box.config(state=tk.DISABLED)
        
    # We'll implement file monitoring later
    
    def display_welcome(self):
        """Display welcome message in the console"""
        welcome_message = """
   =========================================
   |||r0[BOT]t@toui11e v0.000000000000010|||
   =========================================
   |||     Type 'start' or get lost      |||
   =========================================
"""
        self.print_to_console(welcome_message)
        
    def start_cooking_assistant(self):
        """Start the cooking assistant in a separate thread"""
        if self.assistant_thread and self.assistant_thread.is_alive():
            self.print_to_console("Cooking assistant is already running!")
            return
            
        self.print_to_console("\n Robotatouille is starting...\n")
        
        # Create a new cooking assistant
        self.cooking_assistant = CookingAssistant()
        
        # Define thread function
        def run_assistant():
            # Save original stdout and stdin
            original_stdout = sys.stdout
            original_stdin = sys.stdin
            
            try:
                # Redirect stdout and stdin
                sys.stdout = self.console_redirector
                sys.stdin = self.console_redirector
                
                # Create and run event loop for the async cooking assistant
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    loop.run_until_complete(self.cooking_assistant.run())
                finally:
                    loop.close()
                    
            except Exception as e:
                self.root.after(0, lambda: self.print_to_console(f"\nError: {str(e)}\n"))
            finally:
                # Restore original stdout and stdin
                sys.stdout = original_stdout
                sys.stdin = original_stdin
                
        # Start assistant thread
        self.assistant_thread = threading.Thread(target=run_assistant, daemon=True)
        self.assistant_thread.start()
    
    def print_to_console(self, text, end='\n'):
        """Add text to the console output"""
        self.console_output.config(state=tk.NORMAL)
        self.console_output.insert(tk.END, text + end)
        self.console_output.see(tk.END)  # Scroll to the end
        self.console_output.config(state=tk.DISABLED)
        
    def show_input_prompt(self):
        """Show visual indicator that input is required"""
        self.input_indicator.grid(row=0, column=3, padx=5, pady=5)
        self.prompt_label.config(fg="orange", text=">> ")
        self.console_input.config(fg="orange")
        self.console_input.focus_set()
        
    def hide_input_prompt(self):
        """Hide input required indicator"""
        self.input_indicator.grid_forget()
        self.prompt_label.config(fg="lime", text="> ")
        self.console_input.config(fg="lime")
    
    def process_command(self, event=None):
        """Process the command entered in the console input"""
        command = self.console_input.get().strip()
        if not command:
            return
        
        # Add to history
        self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        # Clear input field
        self.console_input.delete(0, tk.END)
        
        # Echo command to output if not waiting for input
        if not self.waiting_for_input:
            self.print_to_console(f"> {command}")
            
            # Process command
            if command.lower() == "help":
                self.show_help()
            elif command.lower() == "clear":
                self.clear_console()
            elif command.lower() == "exit" or command.lower() == "quit":
                self.quit_application()
            elif command.lower() == "start":
                self.start_cooking_assistant()
            elif command.lower() == "ingredients":
                self.update_ingredients("Sample ingredients:\n- Tomatoes\n- Onions\n- Garlic\n- Basil")
            else:
                # Just echo back if no cooking assistant is running
                if not self.assistant_thread or not self.assistant_thread.is_alive():
                    self.print_to_console(f"Unknown command. Type 'help' for a list of commands.")
        else:
            # If waiting for input, pass it to the cooking assistant
            self.last_input = command
            self.input_ready.set()  # Signal that input is available
    
    def show_previous_command(self, event=None):
        """Show previous command from history when up arrow is pressed"""
        if self.command_history and self.history_index > 0:
            self.history_index -= 1
            self.console_input.delete(0, tk.END)
            self.console_input.insert(0, self.command_history[self.history_index])
        return "break"  # Prevent default behavior
    
    def show_next_command(self, event=None):
        """Show next command from history when down arrow is pressed"""
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.console_input.delete(0, tk.END)
            self.console_input.insert(0, self.command_history[self.history_index])
        elif self.history_index == len(self.command_history) - 1:
            self.history_index = len(self.command_history)
            self.console_input.delete(0, tk.END)
        return "break"  # Prevent default behavior
    
    def reset_app(self):
        # Clear console display
        self.clear_console()
        
        # Clear other displays
        self.set_ingredients("")
        self.set_gantt("")
        
        # Show welcome message again
        self.display_welcome()
    
    def create_simple_gantt(self, steps_text):
        """Create a simple Gantt chart for recipe steps"""
        gantt_text = "RECIPE TIMELINE\n"
        gantt_text += "=" * 50 + "\n\n"
        
        # Parse steps from text
        steps = []
        for line in steps_text.split("\n"):
            line = line.strip()
            if not line:
                continue
                
            # Look for numbered steps (1., 2., etc.)
            if line[0].isdigit() and ". " in line:
                step_num, step_text = line.split(". ", 1)
                if step_text:
                    steps.append(step_text)
        
        # If no steps found, show message
        if not steps:
            self.set_gantt("No recipe steps found to create timeline.")
            return
            
        # Calculate timeline
        current_time = datetime.now()
        total_duration = 0
        
        # Create timeline header
        gantt_text += "TIME ESTIMATION\n"
        
        # Add each step with a simple timeline
        for i, step in enumerate(steps):
            # Estimate duration based on step complexity
            duration = 5 + (len(step) // 20)  # Simple heuristic
            
            # Format time
            step_time = current_time + timedelta(minutes=total_duration)
            time_str = step_time.strftime("%H:%M")
            
            # Add to gantt text
            gantt_text += f"{time_str} | Step {i+1}: {step[:30]}{'...' if len(step) > 30 else ''}\n"
            
            # Add a bar representing duration
            bar = "=" * (duration // 2)  # Scale down for display
            gantt_text += f"      | {bar} ({duration} min)\n\n"
            
            total_duration += duration
        
        # Add estimated completion time
        end_time = current_time + timedelta(minutes=total_duration)
        gantt_text += f"\nEstimated completion: {end_time.strftime('%H:%M')}"
        
        # Update the Gantt chart display
        self.set_gantt(gantt_text)


def run_gui_app():
    root = tk.Tk()
    app = GUICookingAssistant(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui_app()
