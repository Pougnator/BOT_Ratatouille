import platform
import time
import threading
from typing import Callable, Dict, Optional


class HardwareHandler:
    """
    A class to handle Raspberry Pi GPIO buttons if running on a Raspberry Pi.
    Otherwise, this will be a no-op class.
    """
    def __init__(self):
        self.is_raspi = self._check_if_raspberry_pi()
        self.gpio = None
        self.button_pins = [6, 19, 0]  # GPIO pins to use as buttons
        self.button_callbacks: Dict[int, Callable] = {}
        self.button_states = {pin: False for pin in self.button_pins}
        self.running = False
        self.polling_thread = None
        
        if self.is_raspi:
            self._setup_gpio()
    
    def _check_if_raspberry_pi(self) -> bool:
        """Check if the current system is a Raspberry Pi."""
        # Check if running on Linux
        if platform.system() != 'Linux':
            return False
            
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
            # Check for 'Raspberry Pi' in the hardware or model name
            return ('Raspberry Pi' in cpuinfo or 
                    'BCM' in cpuinfo or 
                    'Broadcom' in cpuinfo)
        except Exception:
            return False
    
    def _setup_gpio(self) -> None:
        """Setup GPIO if running on a Raspberry Pi."""
        try:
            import RPi.GPIO as GPIO
            self.gpio = GPIO
            
            GPIO.setmode(GPIO.BCM)
            # Configure the pins as inputs with pull-up resistors
            for pin in self.button_pins:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                
            print("[green]✓ GPIO setup successful[/green]")
        except ImportError:
            print("[yellow]RPi.GPIO module not available[/yellow]")
            self.is_raspi = False
        except Exception as e:
            print(f"[red]Error setting up GPIO: {str(e)}[/red]")
            self.is_raspi = False
    
    def register_button_callback(self, pin: int, callback: Callable) -> bool:
        """
        Register a callback function for a specific button pin.
        
        Args:
            pin: The GPIO pin number
            callback: The function to call when the button is pressed
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_raspi or pin not in self.button_pins:
            return False
            
        self.button_callbacks[pin] = callback
        return True
    
    def start_polling(self) -> None:
        """Start polling the buttons in a separate thread."""
        if not self.is_raspi or not self.gpio:
            return
            
        self.running = True
        self.polling_thread = threading.Thread(target=self._poll_buttons)
        self.polling_thread.daemon = True
        self.polling_thread.start()
    
    def stop_polling(self) -> None:
        """Stop the button polling thread."""
        self.running = False
        if self.polling_thread:
            self.polling_thread.join(timeout=1.0)
    
    def _poll_buttons(self) -> None:
        """Poll the buttons and trigger callbacks when pressed."""
        while self.running:
            for pin in self.button_pins:
                if not self.gpio:
                    continue
                    
                # Read the current state (GPIO.LOW = pressed with pull-up)
                current_state = not self.gpio.input(pin)
                
                # If button is pressed (state changed from False to True)
                if current_state and not self.button_states[pin]:
                    self.button_states[pin] = True
                    # Call the registered callback if any
                    if pin in self.button_callbacks:
                        try:
                            self.button_callbacks[pin]()
                        except Exception as e:
                            print(f"Error in button callback: {e}")
                # Button released
                elif not current_state and self.button_states[pin]:
                    self.button_states[pin] = False
            
            # Short sleep to prevent high CPU usage
            time.sleep(0.1)
    
    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        self.stop_polling()
        if self.is_raspi and self.gpio:
            self.gpio.cleanup()
