# from cgi import print_directory
from re import L
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
from typing import List, Dict, Callable, Optional

# Handle imports for both direct execution and package import
if __name__ == "__main__":
    # When run directly, use absolute imports
    print("Running GUI Cooking Assistant directly")
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.states import StateMachine, CookingState
    from src.cooking_assistant_2 import CookingAssistant
    from src.cooking_ui import CookingUI


class GUICookingAssistant(CookingUI):
    """GUI implementation of CookingUI interface"""
    def __init__(self, root):
        self.root = root
        self.root.title("Ro[bot]atouille")
        self.root.geometry("1024x600")  # Match HTML design dimensions (7 inch screen)
        self.root.resizable(False, False)  # Fixed size for 7 inch screen
        
        # Try to detect if we're on a small screen and go fullscreen if needed
        if root.winfo_screenwidth() <= 1024:
            root.attributes('-fullscreen', True)
            
        # Colors from HTML design
        self.bg_color = "#212121"  # Background
        self.surface_color = "#2f2f2f"  # Surface (input, user messages)
        self.text_color = "#ececec"  # Text
        self.primary_color = "#19c37d"  # Primary action (send button)
        self.secondary_color = "#8e8ea0"  # Secondary
        self.border_color = "#3d3d3d"  # Borders
        
        self.root.configure(bg=self.bg_color)
        
        # Input border colors
        self.input_border_default = "#565869"
        self.input_border_active = self.primary_color
        self.current_input_border_color = self.input_border_default
        
        
        # Command history
        self.command_history = []
        self.history_index = 0
        
        # Input handling - callback-based instead of event-based
        self.current_prompt = None
        self.current_callback = None
        self.current_default = None
        
        # Cooking assistant
        self.cooking_assistant = None
        self.assistant_thread = None
        
        # Setup the GUI components
        self._setup_gui()
        
        # Show welcome message
        self.display_welcome()
        self.start_cooking_assistant()

    def _setup_gui(self):
        # Main horizontal container (like app-container in HTML)
        self.main_container = tk.Frame(self.root, bg=self.bg_color)
        self.main_container.pack(fill="both", expand=True)
        
        # Setup chat container (left side, flex: 1)
        self._setup_chat_container()
        
        # Setup ingredients sidebar (right side, 320px)
        self._setup_ingredients_sidebar()
        
    def _setup_chat_container(self):
        """Setup the main chat container (left side)"""
        # Main chat container (flex: 1)
        self.chat_container = tk.Frame(self.main_container, bg=self.bg_color)
        self.chat_container.pack(side=tk.LEFT, fill="both", expand=True)
        self.chat_container.pack_propagate(False)
        
        # Chat header (fixed height)
        self.chat_header = tk.Frame(
            self.chat_container,
            bg=self.bg_color,
            height=60,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        self.chat_header.pack(fill="x")
        self.chat_header.pack_propagate(False)
        
        self.chat_title = tk.Label(
            self.chat_header,
            text="Chat",
            font=("Open Sans", 14, "normal"),
            fg=self.text_color,
            bg=self.bg_color
        )
        self.chat_title.pack(expand=True)
        
        # Chat messages area (scrollable) with visible right border
        self.chat_messages_frame = tk.Frame(
            self.chat_container,
            bg=self.bg_color,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        self.chat_messages_frame.pack(fill="both", expand=True)
        
        # Use Canvas + Frame for scrolling messages
        self.chat_canvas = tk.Canvas(
            self.chat_messages_frame,
            bg=self.bg_color,
            highlightthickness=0,
            borderwidth=0
        )
        self.chat_scrollbar = tk.Scrollbar(
            self.chat_messages_frame,
            orient="vertical",
            command=self.chat_canvas.yview,
            width=32,
            bg=self.surface_color,  # Darker background for scrollbar
            activebackground=self.surface_color,
            troughcolor="#141414",  # Dark track background
            highlightthickness=0,
            borderwidth=0
        )
        self.chat_messages_content = tk.Frame(self.chat_canvas, bg=self.bg_color)
        
        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)
        self.chat_canvas.pack(side=tk.LEFT, fill="both", expand=True)
        # Don't pack scrollbar initially - will show when needed
        self.chat_scrollbar.pack_forget()
        
        self.chat_canvas_window = self.chat_canvas.create_window(
            (0, 0),
            window=self.chat_messages_content,
            anchor="nw"
        )
        
        self.chat_messages_content.bind("<Configure>", self._on_chat_configure)
        self.chat_canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Chat input container
        self.chat_input_container = tk.Frame(
            self.chat_container,
            bg=self.bg_color,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        self.chat_input_container.pack(fill="x", side=tk.BOTTOM)
        
        # Canvas for rounded input background
        self.input_canvas = tk.Canvas(
            self.chat_input_container,
            bg=self.bg_color,
            highlightthickness=0,
            height=64
        )
        self.input_canvas.pack(fill="x", padx=20, pady=16)  # Match HTML padding
        self.input_canvas.bind("<Configure>", self._on_input_canvas_configure)
        
        # Wrapper that will sit inside the rounded background
        self.input_wrapper = tk.Frame(
            self.input_canvas,
            bg=self.surface_color
        )
        self.input_wrapper.pack_propagate(False)
        self.input_window_margin_x = 16
        self.input_window_margin_y = 8
        self.input_canvas_window = self.input_canvas.create_window(
            self.input_window_margin_x,
            self.input_window_margin_y,
            anchor="nw",
            window=self.input_wrapper
        )
        
        # Chat input (full-width, no send button)
        self.console_input = tk.Entry(
            self.input_wrapper,
            font=("Open Sans", 12),
            bg=self.surface_color,
            fg=self.text_color,
            insertbackground=self.text_color,
            borderwidth=0,
            highlightthickness=0
        )
        self.console_input.pack(side=tk.LEFT, fill="both", expand=True, padx=14, pady=10)  # Match HTML padding
        self.console_input.insert(0, "Message Recipe Assistant...")
        self.console_input.config(fg="#8e8ea0")  # Placeholder color
        
        # Bind focus events for placeholder
        self.console_input.bind("<FocusIn>", self._on_input_focus_in)
        self.console_input.bind("<FocusOut>", self._on_input_focus_out)
        
        # Set up key bindings
        self.console_input.bind("<Return>", self.process_command)
        self.console_input.bind("<Up>", self.show_previous_command)
        self.console_input.bind("<Down>", self.show_next_command)
        
        # Store reference to console_output for backward compatibility
        self.console_output = self.chat_messages_content
        
        # Draw initial rounded background
        self.root.after(50, self._draw_input_background)
    
    def _setup_ingredients_sidebar(self):
        """Setup the ingredients sidebar (right side, 320px)"""
        # Ingredients sidebar
        self.ingredients_sidebar = tk.Frame(
            self.main_container,
            bg=self.bg_color,
            width=320
        )
        self.ingredients_sidebar.pack(side=tk.RIGHT, fill="y")
        self.ingredients_sidebar.pack_propagate(False)
        
        # Ingredients header
        self.ingredients_header = tk.Frame(
            self.ingredients_sidebar,
            bg=self.bg_color,
            height=60,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        self.ingredients_header.pack(fill="x", side=tk.TOP)
        self.ingredients_header.pack_propagate(False)
        
        self.ingredients_title = tk.Label(
            self.ingredients_header,
            text="Ingredients",
            font=("Open Sans", 14, "normal"),
            fg=self.text_color,
            bg=self.bg_color
        )
        self.ingredients_title.pack(anchor="w", padx=20, pady=16)
        
        # Ingredients list (scrollable)
        self.ingredients_list_frame = tk.Frame(self.ingredients_sidebar, bg=self.bg_color)
        self.ingredients_list_frame.pack(fill="both", expand=True, before=None)
        
        # Use Canvas + Frame for scrolling
        self.ingredients_canvas = tk.Canvas(
            self.ingredients_list_frame,
            bg=self.bg_color,
            highlightthickness=0,
            borderwidth=0
        )
        self.ingredients_scrollbar = tk.Scrollbar(
            self.ingredients_list_frame,
            orient="vertical",
            command=self.ingredients_canvas.yview,
            width=32,
            bg="#141414",  # Darker background for scrollbar
            activebackground=self.surface_color,
            troughcolor="black",  # Dark track background
            highlightthickness=0,
            borderwidth=0
        )
        self.ingredients_content = tk.Frame(self.ingredients_canvas, bg=self.bg_color)
        
        self.ingredients_canvas.configure(yscrollcommand=self.ingredients_scrollbar.set)
        self.ingredients_canvas.pack(side=tk.LEFT, fill="both", expand=True)
        # Don't pack scrollbar initially - will show when needed
        self.ingredients_scrollbar.pack_forget()
        
        self.ingredients_canvas_window = self.ingredients_canvas.create_window(
            (0, 0),
            window=self.ingredients_content,
            anchor="nw"
        )
        
        self.ingredients_content.bind("<Configure>", self._on_ingredients_configure)
        self.ingredients_canvas.bind("<Configure>", self._on_ingredients_canvas_configure)
        
        # Numeric keyboard panel (hidden by default)
        self.numeric_panel = tk.Frame(
            self.ingredients_sidebar,
            bg=self.bg_color,
            highlightbackground=self.border_color,
            highlightthickness=1
        )
        # Track visibility state
        self.numeric_keyboard_visible = False
        # Container for numeric buttons (rebuilt depending on state)
        self.numeric_panel_container = None
        # Don't pack initially - will show when needed
        
        # Initial keyboard layout (will be rebuilt dynamically when shown)
        self._setup_numeric_keyboard()

        # Timer countdown display (bottom right, below numeric keyboard)
        self.timer_panel = tk.Frame(
            self.ingredients_sidebar,
            bg=self.bg_color,
            highlightbackground=self.border_color,
            highlightthickness=1,
            height=80
        )
        self.timer_panel.pack_propagate(False)
        # Don't pack initially - will show when timer is active
        
        # Timer display container (scrollable for multiple timers)
        self.timer_container = tk.Frame(self.timer_panel, bg=self.bg_color)
        # Réduire légèrement les marges pour éviter que le texte soit coupé
        self.timer_container.pack(fill="both", expand=True, padx=16, pady=10)
        
        # Dictionary to store timer display widgets: {timer_id: {'countdown': Label, 'name': Label, 'frame': Frame}}
        self.timer_widgets = {}
        
        # Track if timer update is scheduled
        self.timer_update_job = None
        self.timer_visible = False

        # "Next" button for step execution (bottom of ingredients sidebar, hidden by default)
        # Placed in the same column as ingredients & numeric keyboard for visual consistency.
        self.next_button_container = tk.Frame(
            self.ingredients_sidebar,
            bg=self.bg_color
        )
        self.next_button = tk.Button(
            self.next_button_container,
            text="Next",
            font=("Open Sans", 12, "normal"),
            bg=self.primary_color,
            fg="#ffffff",
            activebackground=self.primary_color,
            activeforeground="#ffffff",
            borderwidth=0,
            relief=tk.FLAT,
            cursor="hand2",
            padx=24,
            pady=10,
            command=self._on_next_button_click
        )
        self.next_button.pack(side=tk.RIGHT, padx=20, pady=16)
        self.next_button_visible = False
        
        # Store reference for backward compatibility
        self.ingredients_box = self.ingredients_content
    
    def _setup_numeric_keyboard(self):
        """Prepare the numeric keyboard container (buttons are built dynamically)."""
        # Clear previous container if any
        if self.numeric_panel_container is not None:
            self.numeric_panel_container.destroy()
        
        # Numeric panel container with padding
        self.numeric_panel_container = tk.Frame(self.numeric_panel, bg=self.bg_color)
        self.numeric_panel_container.pack(fill="both", expand=True, padx=20, pady=16)

    def _build_numeric_buttons(self, labels):
        """(Re)build numeric buttons from a flat list of labels."""
        # Reset container
        self._setup_numeric_keyboard()

        button_width = 80  # Fixed pixel width

        # Arrange in two rows of up to 3 buttons each
        row1 = tk.Frame(self.numeric_panel_container, bg=self.bg_color)
        row1.pack(fill="x", pady=(0, 10))
        row2 = tk.Frame(self.numeric_panel_container, bg=self.bg_color)
        row2.pack(fill="x")

        first_row_labels = labels[:3]
        second_row_labels = labels[3:6]

        def _add_buttons(row_frame, row_labels):
            for idx, num in enumerate(row_labels):
                btn_frame = tk.Frame(row_frame, width=button_width, height=60, bg=self.bg_color)
                btn_frame.pack_propagate(False)
                btn_frame.grid(row=0, column=idx, padx=(0, 10) if idx < len(row_labels) - 1 else (0, 0), sticky="nsew")

                btn = tk.Button(
                    btn_frame,
                    text=num,
                    font=("Open Sans", 18, "normal"),
                    bg=self.surface_color,
                    fg=self.text_color,
                    activebackground="#3a3a3a",
                    activeforeground=self.text_color,
                    borderwidth=1,
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground="#565869",
                    cursor="hand2",
                    command=lambda n=num: self._on_numeric_button_click(n),
                    padx=16,
                    pady=16
                )
                btn.pack(fill="both", expand=True)

            row_frame.grid_rowconfigure(0, minsize=60)

        _add_buttons(row1, first_row_labels)
        if second_row_labels:
            _add_buttons(row2, second_row_labels)
    
    def _on_numeric_button_click(self, value: str):
        """Handle numeric button click - set value and auto-submit"""
        # Special mapping: '+' means '0' (request more recipes)
        if value == "+":
            value = "0"

        # Clear input and set the clicked value
        self.console_input.delete(0, tk.END)
        self.console_input.config(fg=self.text_color)
        self.console_input.insert(0, value)
        
        # Clear default value so it's ignored
        self.current_default = None
        
        # Auto-submit the value
        self.process_command()

    def _on_next_button_click(self):
        """UI handler for the bottom-right 'Next' button."""
        if self.cooking_assistant:
            try:
                self.cooking_assistant._button_next()
            except Exception as e:
                print(f"Error handling 'Next' button: {e}")

    # --- CookingUI extension: show/hide Next button ---
    def show_next_button(self):
        """Show the 'Next' button at the bottom of the ingredients sidebar during step execution."""
        if not self.next_button_visible:
            # Pack at the very bottom of the ingredients sidebar (below numeric keyboard if visible)
            self.next_button_container.pack(side=tk.BOTTOM, fill="x")
            self.next_button_visible = True
            self.root.update_idletasks()

    def hide_next_button(self):
        """Hide the 'Next' button when not in step execution."""
        if self.next_button_visible:
            self.next_button_container.pack_forget()
            self.next_button_visible = False
    
    def show_numeric_keyboard(self):
        """Show the numeric keyboard panel"""
        # Choose button set based on current state
        labels = ["1", "2", "3", "4", "5", ".."]
        try:
            if self.cooking_assistant and hasattr(self.cooking_assistant, "state_machine"):
                current_state = self.cooking_assistant.state_machine.current_state
                if current_state == CookingState.RECIPE_CONFIRMATION:
                    # In recipe confirmation: 1-4, '+', '?' (help/future use)
                    labels = ["1", "2", "3", "4", "+", "?"]
        except Exception as e:
            # On error, keep default labels
            print(f"Error determining state for numeric keyboard: {e}")

        # (Re)build the buttons for the current context, even if already visible
        self._build_numeric_buttons(labels)

        if not self.numeric_keyboard_visible:
            # Pack at bottom, after ingredients list
            self.numeric_panel.pack(side=tk.BOTTOM, fill="x", padx=0, pady=0)
            self.numeric_keyboard_visible = True
            # Update layout to ensure visibility
            self.root.update_idletasks()
    
    def hide_numeric_keyboard(self):
        """Hide the numeric keyboard panel"""
        if self.numeric_keyboard_visible:
            self.numeric_panel.pack_forget()
            self.numeric_keyboard_visible = False
    
    def show_timer_countdown(self):
        """Show the timer countdown panel"""
        if not self.timer_visible:
            # Pack at the bottom, after numeric keyboard if visible
            self.timer_panel.pack(side=tk.BOTTOM, fill="x", padx=0, pady=0)
            self.timer_visible = True
            # Start updating the countdown
            self._update_timer_countdown()
    
    def hide_timer_countdown(self):
        """Hide the timer countdown panel"""
        if self.timer_visible:
            self.timer_panel.pack_forget()
            self.timer_visible = False
            # Cancel any pending update
            if self.timer_update_job:
                self.root.after_cancel(self.timer_update_job)
                self.timer_update_job = None
            # Clear all timer widgets
            for timer_id in list(self.timer_widgets.keys()):
                if timer_id in self.timer_widgets:
                    widgets = self.timer_widgets[timer_id]
                    widgets['frame'].destroy()
                    del self.timer_widgets[timer_id]
    
    def _update_timer_countdown(self):
        """Update the timer countdown display (thread-safe, called from main thread)"""
        # Get the cooking assistant instance to access the timer
        if hasattr(self, 'cooking_assistant') and self.cooking_assistant:
            active_timers = self.cooking_assistant.timer.get_active_timers()
            
            if active_timers:
                # Get all active timers with their start times for sorting
                timers_with_start = []
                for timer_id, timer_info in active_timers.items():
                    # Get the original timer to access 'started' time
                    if timer_id in self.cooking_assistant.timer.active_timers:
                        started = self.cooking_assistant.timer.active_timers[timer_id]['started']
                        timers_with_start.append((timer_id, timer_info, started))
                
                # Sort by start time: oldest first (will be displayed on top)
                timers_with_start.sort(key=lambda x: x[2])
                
                # Remove widgets for timers that are no longer active
                active_timer_ids = {timer_id for timer_id, _, _ in timers_with_start}
                for timer_id in list(self.timer_widgets.keys()):
                    if timer_id not in active_timer_ids:
                        # Remove the timer widget
                        if timer_id in self.timer_widgets:
                            widgets = self.timer_widgets[timer_id]
                            widgets['frame'].destroy()
                            del self.timer_widgets[timer_id]
                
                # Update or create widgets for each active timer
                for idx, (timer_id, timer_info, started) in enumerate(timers_with_start):
                    remaining = int(timer_info['remaining'])
                    name = timer_info['name']
                    
                    # Format the time
                    hours = remaining // 3600
                    minutes = (remaining % 3600) // 60
                    seconds = remaining % 60
                    
                    if hours > 0:
                        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    else:
                        time_str = f"{minutes:02d}:{seconds:02d}"
                    
                    # Determine color based on remaining time
                    if remaining <= 60:
                        countdown_color = "#ff6b6b"  # Red for urgency
                    elif remaining <= 300:  # Less than 5 minutes
                        countdown_color = "#ffa500"  # Orange
                    else:
                        countdown_color = self.text_color
                    
                    # Create or update widget for this timer
                    if timer_id not in self.timer_widgets:
                        # Create new widget frame for this timer
                        timer_frame = tk.Frame(self.timer_container, bg=self.bg_color)
                        timer_frame.pack(fill="x", pady=(0 if idx == 0 else 8, 0), anchor="w")
                        
                        # Timer countdown text
                        countdown_label = tk.Label(
                            timer_frame,
                            text=time_str,
                            # Police légèrement réduite pour éviter les coupures
                            font=("Open Sans", 16, "bold"),
                            fg=countdown_color,
                            bg=self.bg_color
                        )
                        countdown_label.pack(anchor="w", pady=(0, 1))
                        
                        # Timer name
                        name_label = tk.Label(
                            timer_frame,
                            text=name,
                            # Police légèrement réduite pour éviter les coupures
                            font=("Open Sans", 10, "normal"),
                            fg=self.secondary_color,
                            bg=self.bg_color
                        )
                        name_label.pack(anchor="w", pady=(1, 0))
                        
                        self.timer_widgets[timer_id] = {
                            'frame': timer_frame,
                            'countdown': countdown_label,
                            'name': name_label
                        }
                    else:
                        # Update existing widget
                        widgets = self.timer_widgets[timer_id]
                        widgets['countdown'].config(text=time_str, fg=countdown_color)
                        widgets['name'].config(text=name)
                    
                    # Reorder widgets to match sorted order (oldest on top, newest on bottom)
                    widgets = self.timer_widgets[timer_id]
                    widgets['frame'].pack_forget()
                    widgets['frame'].pack(fill="x", pady=(0 if idx == 0 else 8, 0), anchor="w")
                
                # Adjust panel height based on number of timers
                num_timers = len(timers_with_start)
                base_height = 80
                height_per_timer = 60
                self.timer_panel.config(height=min(base_height + (num_timers - 1) * height_per_timer, 300))
                
                # Schedule next update in 1 second (1000ms)
                self.timer_update_job = self.root.after(1000, self._update_timer_countdown)
            else:
                # No active timers, hide the panel
                self.hide_timer_countdown()
        else:
            # No cooking assistant, hide the panel
            self.hide_timer_countdown()
    
    def _on_chat_configure(self, event):
        """Update scroll region when chat content changes"""
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        
        # Check if scrolling is needed
        bbox = self.chat_canvas.bbox("all")
        if bbox:
            content_height = bbox[3] - bbox[1]
            canvas_height = self.chat_canvas.winfo_height()
            
            if content_height > canvas_height:
                # Show scrollbar if not already visible
                if not self.chat_scrollbar.winfo_viewable():
                    self.chat_scrollbar.pack(side=tk.RIGHT, fill="y")
            else:
                # Hide scrollbar if content fits
                if self.chat_scrollbar.winfo_viewable():
                    self.chat_scrollbar.pack_forget()
        
        # Auto-scroll to bottom whenever content changes
        self.chat_canvas.yview_moveto(1.0)
    
    def _on_canvas_configure(self, event):
        """Update canvas window width when canvas is resized"""
        canvas_width = event.width
        self.chat_canvas.itemconfig(self.chat_canvas_window, width=canvas_width)
    
    def _on_ingredients_configure(self, event):
        """Update scroll region when ingredients content changes"""
        self.ingredients_canvas.configure(scrollregion=self.ingredients_canvas.bbox("all"))
        
        # Check if scrolling is needed
        bbox = self.ingredients_canvas.bbox("all")
        if bbox:
            content_height = bbox[3] - bbox[1]
            canvas_height = self.ingredients_canvas.winfo_height()
            
            if content_height > canvas_height:
                # Show scrollbar if not already visible
                if not self.ingredients_scrollbar.winfo_viewable():
                    self.ingredients_scrollbar.pack(side=tk.RIGHT, fill="y")
            else:
                # Hide scrollbar if content fits
                if self.ingredients_scrollbar.winfo_viewable():
                    self.ingredients_scrollbar.pack_forget()
    
    def _on_ingredients_canvas_configure(self, event):
        """Update canvas window width when canvas is resized"""
        canvas_width = event.width
        self.ingredients_canvas.itemconfig(self.ingredients_canvas_window, width=canvas_width)
    
    def _on_input_canvas_configure(self, event):
        """Update input canvas layout and redraw rounded background"""
        if not hasattr(self, "input_canvas_window"):
            return
        margin_x = getattr(self, "input_window_margin_x", 16)
        margin_y = getattr(self, "input_window_margin_y", 8)
        self.input_canvas.coords(self.input_canvas_window, margin_x, margin_y)
        new_width = max(event.width - 2 * margin_x, 50)
        new_height = max(event.height - 2 * margin_y, 20)
        self.input_wrapper.config(width=new_width, height=new_height)
        self._draw_input_background(self.current_input_border_color)
    
    def _draw_input_background(self, border_color=None):
        """Draw rounded background for the chat input area"""
        if not hasattr(self, "input_canvas"):
            return
        width = self.input_canvas.winfo_width()
        height = self.input_canvas.winfo_height()
        if width <= 0 or height <= 0:
            return
        
        color = border_color or self.input_border_default
        radius = 16
        self.input_canvas.delete("input_bg")
        
        try:
            from PIL import Image, ImageDraw, ImageTk
            img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle(
                [(0, 0), (width - 1, height - 1)],
                radius=radius,
                fill=self.surface_color,
                outline=color,
                width=1
            )
            photo = ImageTk.PhotoImage(img)
            self.input_canvas.create_image(0, 0, anchor="nw", image=photo, tags="input_bg")
            self.input_canvas.image = photo  # Keep reference to prevent garbage collection
        except ImportError:
            # Fallback: use regular rectangle if Pillow is not available
            self.input_canvas.create_rectangle(
                0, 0, width, height,
                fill=self.surface_color,
                outline=color,
                width=1,
                tags="input_bg"
            )
        
        # Ensure input frame stays on top of the background
        if hasattr(self, "input_canvas_window"):
            self.input_canvas.tag_raise(self.input_canvas_window)

    def _draw_rounded_rect_on_canvas(self, canvas, x1, y1, x2, y2, radius, fill):
        """Draw a rounded rectangle directly on a canvas"""
        radius = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
        # Center rectangle
        canvas.create_rectangle(
            x1 + radius,
            y1,
            x2 - radius,
            y2,
            fill=fill,
            outline=""
        )
        canvas.create_rectangle(
            x1,
            y1 + radius,
            x2,
            y2 - radius,
            fill=fill,
            outline=""
        )
        # Corners
        canvas.create_arc(
            x1,
            y1,
            x1 + 2 * radius,
            y1 + 2 * radius,
            start=90,
            extent=90,
            style="pieslice",
            fill=fill,
            outline=""
        )
        canvas.create_arc(
            x2 - 2 * radius,
            y1,
            x2,
            y1 + 2 * radius,
            start=0,
            extent=90,
            style="pieslice",
            fill=fill,
            outline=""
        )
        canvas.create_arc(
            x2 - 2 * radius,
            y2 - 2 * radius,
            x2,
            y2,
            start=270,
            extent=90,
            style="pieslice",
            fill=fill,
            outline=""
        )
        canvas.create_arc(
            x1,
            y2 - 2 * radius,
            x1 + 2 * radius,
            y2,
            start=180,
            extent=90,
            style="pieslice",
            fill=fill,
            outline=""
        )
    
    def _on_input_focus_in(self, event):
        """Handle input focus in - remove placeholder"""
        if self.console_input.get() == "Message Recipe Assistant...":
            self.console_input.delete(0, tk.END)
            self.console_input.config(fg=self.text_color)
    
    def _on_input_focus_out(self, event):
        """Handle input focus out - show placeholder if empty"""
        if not self.console_input.get():
            self.console_input.insert(0, "Message Recipe Assistant...")
            self.console_input.config(fg="#8e8ea0")
        
    
   
    
    def clear_console(self):
        """Clear the chat messages"""
        for widget in self.chat_messages_content.winfo_children():
            widget.destroy()
        # After clearing, ensure the view is reset to the top
        self.chat_canvas.yview_moveto(0)

    
    def restart(self):
        """Restart the cooking assistant - clear everything and reset to STARTING state"""
        # Stop the current assistant thread if running
        if self.cooking_assistant:
            self.cooking_assistant.stop()
        
        # Wait for the thread to finish (with timeout)
        if self.assistant_thread and self.assistant_thread.is_alive():
            self.assistant_thread.join(timeout=2.0)  # Wait up to 2 seconds
            if self.assistant_thread.is_alive():
                print("Warning: Assistant thread did not stop in time, continuing anyway...\n")
        
        # Reset assistant reference BEFORE clearing (to prevent new messages)
        self.cooking_assistant = None
        self.assistant_thread = None
        
        # Clear chat messages
        self.clear_console()
        self.root.update_idletasks()  # Force UI update
        
        # Clear ingredients panel
        self.set_ingredients("")
        
        # Hide numeric keyboard
        self.hide_numeric_keyboard()
        
        # Gantt chart is no longer in the UI (removed for chat layout)
        
        # Show welcome message
        self.display_welcome()
        self.start_cooking_assistant()
    
    def quit_application(self):
        """Exit the application"""
        if messagebox.askyesno("Quit", "Are you sure you want to quit?"):
            self.root.quit()

        
    def next_step(self):
        """Move to the next step"""
        # In the new architecture, the state machine lives inside CookingAssistant.
        # This method is a convenience hook if you later add a GUI button for "next step".
        if not self.cooking_assistant:
            self.show_text("Assistant is not running yet.\n")
            return

        # Advance the state machine and refresh the displayed steps
        self.cooking_assistant.state_machine.next_step()
        self.cooking_assistant.display_cooking_steps()
        print("Moving to next step...\n")
        
            
    def update_ingredients(self, ingredients_text):
        """Update the ingredients panel with provided text"""
        self.set_ingredients(ingredients_text)
    
    def set_ingredients(self, ingredients_text):
        """Update ingredients in the sidebar"""
        # Clear existing ingredients
        for widget in self.ingredients_content.winfo_children():
            widget.destroy()
        
        # Parse ingredients text and add as items
        lines = ingredients_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            color = "#00c853"  # green for available ingredients

            if line.startswith("missing:"):
                ingredient_text = line[len("missing:"):].strip().lstrip('•-* ').strip()
                color = "#ff8c00"  # orange for missing ingredients
            else:
                ingredient_text = line.lstrip('•-* ').strip()

            if ingredient_text:
                ingredient_item = tk.Label(
                    self.ingredients_content,
                    text=ingredient_text,
                    font=("Open Sans", 11),  # Reduced from 13
                    fg=color,
                    bg=self.bg_color,
                    anchor="w",
                    padx=32,  # Space for bullet
                    pady=2,  # Reduced from 5
                    wraplength=250,  # Force text wrapping for long ingredients (320px sidebar - 70px padding)
                    justify=tk.LEFT
                )
                ingredient_item.pack(fill="x", padx=20)
                    # # Add bullet point manually
                    # bullet = tk.Label(
                    #     self.ingredients_content,
                    #     text="-",
                    #     font=("Open Sans", 11),  # Reduced from 13
                    #     fg="#8e8ea0",
                    #     bg=self.bg_color
                    # )
                    # bullet.place(in_=ingredient_item, x=20, y=0, anchor="w")
        
        # Update scroll region
        self.root.after(10, lambda: self.ingredients_canvas.configure(
            scrollregion=self.ingredients_canvas.bbox("all")
        ))
    
    def set_gantt(self, gantt_text):
        """Gantt chart display removed in chat layout"""
        pass
        
    # We'll implement file monitoring later
    
    def display_welcome(self):
        """Display welcome message in the chat"""
        welcome_message = """ 
        =========================================
        |||r0[BOT]t@toui11e v0.000000000000011|||
        =========================================
        |||     Go delicous or get lost      |||
        =========================================
   """
        print(welcome_message)
        
    def start_cooking_assistant(self):
        """Start the cooking assistant in a separate thread"""
        if self.assistant_thread and self.assistant_thread.is_alive():
            print("Cooking assistant is already running!\n")
            return
            
        print("\n Robotatouille is starting...\n")
        print("Hello Hello")
        # Define thread function
        def run_assistant():
            try:
                self.root.after(0, lambda: print("Creating one cooking assistant...\n"))
                
                # Create the cooking assistant with self as the UI
                try:
                    self.cooking_assistant = CookingAssistant(ui=self)
                    self.root.after(0, lambda: print("Cooking assistant created successfully.\n"))
                except Exception as create_error:
                    error_msg = f"ERROR creating cooking assistant: {str(create_error)}"
                    self.root.after(0, lambda msg=error_msg: print(msg))
                    return
                
                # Create and run event loop for the async cooking assistant
                self.root.after(0, lambda: print("Starting event loop...\n"))
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    self.root.after(0, lambda: print("Running cooking assistant...\n"))
                    loop.run_until_complete(self.cooking_assistant.run())
                except Exception as run_error:
                    error_msg = f"ERROR running cooking assistant: {str(run_error)}"
                    self.root.after(0, lambda msg=error_msg: print(msg))
                finally:
                    loop.close()
                    
            except Exception as e:
                # Make sure the error is displayed in the GUI console
                error_msg = f"\nUnexpected error: {str(e)}\n"
                self.root.after(0, lambda msg=error_msg: print(msg))
                
                import traceback
                trace_msg = f"Stack trace: {traceback.format_exc()}\n"
                self.root.after(0, lambda msg=trace_msg: self.show_text(msg))
                
        # Start assistant thread
        self.assistant_thread = threading.Thread(target=run_assistant, daemon=True)
        self.assistant_thread.start()
        
        # Add additional message after starting thread
        print("Thread started, initializing Robotatouille...\n")
    
    # ========== CookingUI Interface Implementation ==========
    
    def _add_chat_message(self, text: str, is_user: bool = False, return_row: bool = False, font=None):
        """Add a message to the chat (assistant or user style)"""
        # Message row container - padding depends on message type
        message_row = tk.Frame(
            self.chat_messages_content,
            bg=self.bg_color,
            padx=20
        )
        # For user messages, simulate ~3 line breaks with extra top padding
        if is_user:
            message_row.pack(fill="x", pady=(24, 2))
        else:
            message_row.pack(fill="x", pady=2)  # Reduced for tighter line spacing after \n

        # Message content container (centered, max-width 700px equivalent)
        message_content = tk.Frame(message_row, bg=self.bg_color)
        if is_user:
            message_content.pack(side=tk.RIGHT, anchor="e")
        else:
            message_content.pack(side=tk.LEFT, anchor="w")
        
        # Message text
        if is_user:
            # User message: rounded background using canvas drawing
            bubble_canvas = tk.Canvas(
                message_content,
                bg=self.bg_color,
                highlightthickness=0,
                borderwidth=0
            )
            bubble_canvas.pack(side=tk.LEFT)
            
            padding_x = 16
            padding_y = 10
            max_width = 400
            
            text_item = bubble_canvas.create_text(
                padding_x,
                padding_y,
                text=text,
                font=("Open Sans", 12),
                fill=self.text_color,
                anchor="nw",
                width=max_width
            )
            
            bubble_canvas.update_idletasks()
            bbox = bubble_canvas.bbox(text_item)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            width = text_width + padding_x * 2
            height = text_height + padding_y * 2
            
            bubble_canvas.config(width=width, height=height)
            
            self._draw_rounded_rect_on_canvas(
                bubble_canvas,
                0,
                0,
                width,
                height,
                radius=14,
                fill=self.surface_color
            )
            
            bubble_canvas.tag_raise(text_item)
            
        else:
            # Assistant message: plain text
            # Use custom font if provided, otherwise default
            message_font = font if font else ("Open Sans", 12)
            message_text = tk.Label(
                message_content,
                text=text,
                font=message_font,
                fg=self.text_color,
                bg=self.bg_color,
                wraplength=600,  # Reduced from 700
                justify=tk.LEFT
            )
            message_text.pack()
        
        # Refresh UI and scroll to bottom
        self.root.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)
        
        # Return message_row if requested (for loading indicator)
        if return_row:
            return message_row
    
    def show_text(self, text: str):
        """Display text in the chat as assistant message"""
        if not text:
            return
        
        def render():
            cleaned = text.strip()
            if not cleaned:
                return
            lines = cleaned.split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    self._add_chat_message(line, is_user=False)
        
        if threading.current_thread() is threading.main_thread():
            render()
        else:
            self.root.after(0, render)
    
    def ask_text(self, prompt: str, callback: Callable[[str], None], default: Optional[str] = None):
        """Ask the user for text input - callback-based approach"""
        # Display the prompt
        
        self.show_text(f"{prompt}\n")
        
        # Set up the callback
        self.current_prompt = prompt
        self.current_callback = callback
        self.current_default = default
        
        # Check if we should show numeric keyboard based on state machine state
        is_numeric = False
        try:
            if self.cooking_assistant and hasattr(self.cooking_assistant, 'state_machine'):
                current_state = self.cooking_assistant.state_machine.current_state
                is_numeric = (current_state == CookingState.STARTING or 
                             current_state == CookingState.RECIPE_CONFIRMATION)
        except Exception as e:
            # If there's any error accessing state, default to hiding keyboard
            is_numeric = False
            print(f"Error checking state for numeric keyboard: {e}")
        
        if is_numeric:
            self.show_numeric_keyboard()
        else:
            self.hide_numeric_keyboard()
        
        # Show visual indicator
        self.show_input_prompt()
        
        # If there's a default, pre-fill the input
        if default:
            self.console_input.delete(0, tk.END)
            self.console_input.insert(0, default)
    
    def show_recipes(self, recipes: List[Dict[str, str]]):
        """Display a list of proposed recipes"""
        self.show_text("Voici quelques delicieuses recettes que je peux vous proposer:\n")
        for idx, recipe in enumerate(recipes, start=1):
            name = recipe.get("name", f"Recette {idx}")
            difficulty = recipe.get("difficulty", "")
            description = recipe.get("description", "")
            
            recipe_text = f"{idx}. {name}"
            if difficulty:
                recipe_text += f" (Difficulté: {difficulty})"
            recipe_text += "\n"
            # if description:
            #     recipe_text += f"   {description}\n"
            recipe_text += "\n"
            
            self.show_text(recipe_text)
    
    def show_ingredients(self, ingredients: List[Dict[str, str]]):
        """Display ingredients list"""
        ingredients_available_text = ""
        ingredients_unavailable_text = ""

        for ingredient in ingredients:
            quantity = ingredient.get("quantity", "")
            unit = ingredient.get("unit", "")
            name = ingredient.get("name", "")
            if ingredient.get("available"):
                ingredients_available_text += f"• {quantity} {unit} {name}\n"
            else:
                # Prefix with a marker so we can colorize missing items later
                ingredients_unavailable_text += f"missing: • {quantity} {unit} {name}\n"

        ingredients_text = ingredients_available_text + ingredients_unavailable_text
        
        # Update the ingredients panel
        print(("Showing the ingredients in the ingredients sidebar"))
        self.set_ingredients(ingredients_text)
        
        # # Also show in console
        # self.show_text("Ingrédients:\n\n")
        # self.show_text(ingredients_text)
    
    def show_steps(self, steps: List[str], current_step: int = 0):
        """Display cooking steps"""
        self.show_text("Étapes de préparation:\n")
        for idx, step in enumerate(steps, start=1):
            marker = "→" if idx == current_step + 1 else " "
            self.show_text(f"{marker} {idx}. {step}\n")
    
    def show_gantt(self, gantt_data: Dict):
        """Display Gantt chart data"""
        # This will be implemented when we work on Gantt chart integration
        # For now, just a placeholder
        pass
    
    def show_error(self, error_message: str):
        """Display an error message"""
        self.show_text(f"\n❌ Erreur: {error_message}\n")
    
    def show_success(self, message: str):
        """Display a success message"""
        self.show_text(f"\n✓ {message}")
    
    def show_loading(self, message: str = "Chargement..."):
        """Show a loading indicator in the chat"""
        def _show_loading_ui():
            # Create a loading message with animated dots (single persistent line)
            loading_text = message
            # Use a different font and italic (cursive) style for the loading message
            custom_font = ("Arial", 11, "italic")  # Example: cursive-like, fallback to italic if unavailable
            self._loading_message_row = self._add_chat_message(
                loading_text, is_user=False, return_row=True, font=custom_font
            )
            # Store reference to the label for animation
            self._loading_label = None
            for widget in self._loading_message_row.winfo_children():
                if isinstance(widget, tk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, tk.Label):
                            self._loading_label = child
                            break
                    if self._loading_label:
                        break
            # Start animation
            self._loading_dots = 1
            self._loading_base_text = message
            if hasattr(self, '_loading_label') and self._loading_label:
                self._animate_loading()
        
        # Ensure UI update happens on main thread
        if threading.current_thread() is threading.main_thread():
            _show_loading_ui()
        else:
            self.root.after(0, _show_loading_ui)
    
    def hide_loading(self):
        """Hide the loading indicator"""
        def _hide_loading_ui():
            # Cancel any pending animation
            if hasattr(self, '_loading_animation_id') and self._loading_animation_id:
                try:
                    self.root.after_cancel(self._loading_animation_id)
                except:
                    pass
                self._loading_animation_id = None
            
            # Remove the loading message
            if hasattr(self, '_loading_message_row') and self._loading_message_row:
                try:
                    self._loading_message_row.destroy()
                except:
                    pass
                self._loading_message_row = None
                self._loading_label = None
        
        # Ensure UI update happens on main thread
        if threading.current_thread() is threading.main_thread():
            _hide_loading_ui()
        else:
            self.root.after(0, _hide_loading_ui)
    
    def _animate_loading(self):
        """Animate loading dots"""
        if not hasattr(self, '_loading_message_row') or not self._loading_message_row:
            return
        
        # Update dots (cycle through 1, 2, 3 dots)
        self._loading_dots = (self._loading_dots % 3) + 1
        dots = "." * self._loading_dots
        
        try:
            # Update the label text
            if hasattr(self, '_loading_label') and self._loading_label:
                self._loading_label.config(text=f"{self._loading_base_text}{dots}")
        except Exception as e:
            pass
        
        # Schedule next animation
        self._loading_animation_id = self.root.after(500, self._animate_loading)
    
    # ========== Helper Methods ==========
    
    def print_to_console(self, text, end='\n'):
        """Add text to the console output (legacy method, now uses show_text)"""
        self.show_text(text + end)
        
    def show_input_prompt(self):
        """Show visual indicator that input is required"""
        self.console_input.focus_set()
    
    def hide_input_prompt(self):
        """Hide input required indicator"""
        # Nothing to do for now, kept for backward compatibility
        return
    
    def process_command(self, event=None):
        """Process the command entered in the console input"""
        command = self.console_input.get().strip()
        # Ignore placeholder text
        if not command or command == "Message Recipe Assistant...":
            return
        
        # Add to history
        self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        # Clear input field
        self.console_input.delete(0, tk.END)
        
        # Display user message in chat (always show user input)
        self._add_chat_message(command, is_user=True)
        
        # Check if we have a callback waiting (from ask_text for legacy code)
        # For the new chat loop, we always use on_user_entry via process_command
        if self.current_callback:
            # Hide the input prompt
            self.hide_input_prompt()
            # Hide numeric keyboard after input is submitted
            self.hide_numeric_keyboard()
            
            # Call the callback with the user's input (for legacy code paths)
            callback = self.current_callback
            self.current_callback = None
            self.current_prompt = None
            self.current_default = None
            
            # Execute callback (might be in a different thread, so use root.after)
            self.root.after(0, lambda: callback(command))
            return
        
        # Otherwise, handle as a regular command or chat input
        
        # Process command
        if command.lower() == "help":
            self.show_help()
        elif command.lower() == "clear":
            self.clear_console()
        elif command.lower() == "restart":
            self.restart()
        elif command.lower() == "exit" or command.lower() == "quit":
            self.quit_application()
        # elif command.lower() == "start":
        #     self.start_cooking_assistant()
        elif command.lower() == "next":
            # In the new architecture, 'next' should behave like the physical Next button:
            # signal the assistant to advance the current step if we're in STEP_EXECUTION.
            if self.cooking_assistant:
                try:
                    self.cooking_assistant._button_next()
                except Exception as e:
                    print(f"Error handling 'next' command: {e}")
            else:
                print("Assistant is not running; 'next' has no effect.")
        
        else:
            # Considérer le texte libre comme une entrée utilisateur pour la boucle de chat
            # Toute entrée qui n'est pas une commande spéciale déclenche on_user_entry
            if self.cooking_assistant:
                self.cooking_assistant.on_user_entry(command)
            else:
                print("Unknown command. Type 'help' for a list of commands.")

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
        self.start_cooking_assistant()
    
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
