from datetime import datetime, timedelta
from typing import Optional, Dict, Callable
import threading
import time
from rich.console import Console


class CookingTimer:
    def __init__(self, console=None):
        self.active_timers = {}
        self.timer_count = 0
        self.console = console or Console()
        self.timer_thread = None
        self.running = False
        self.timer_expired_callbacks: Dict[int, Callable] = {}
        
        # Start the timer monitoring thread
        self._start_timer_thread()
        
    def parse_duration(self, duration_str: str) -> Optional[int]:
        duration_str = duration_str.lower().strip()
        
        try:
            if 'hour' in duration_str or 'hr' in duration_str:
                hours = int(''.join(filter(str.isdigit, duration_str)))
                return hours * 3600
            elif 'min' in duration_str:
                minutes = int(''.join(filter(str.isdigit, duration_str)))
                return minutes * 60
            elif 'sec' in duration_str:
                seconds = int(''.join(filter(str.isdigit, duration_str)))
                return seconds
            else:
                minutes = int(duration_str)
                return minutes * 60
        except ValueError:
            return None
            
    def start_timer(self, duration_seconds: int, name: Optional[str] = None) -> int:
        self.timer_count += 1
        timer_id = self.timer_count
        
        if name is None:
            name = f"Timer {timer_id}"
            
        end_time = datetime.now() + timedelta(seconds=duration_seconds)
        self.active_timers[timer_id] = {
            'name': name,
            'duration': duration_seconds,
            'end_time': end_time,
            'started': datetime.now()
        }
        
        # Print a message when a timer is started
        time_str = self.format_time(duration_seconds)
        self.console.print(f"\n[bold blue]⏱️ Timer started: {name} for {time_str}[/bold blue]")
        
        return timer_id
        
    def get_remaining_time(self, timer_id: int) -> Optional[int]:
        if timer_id not in self.active_timers:
            return None
            
        timer = self.active_timers[timer_id]
        remaining = (timer['end_time'] - datetime.now()).total_seconds()
        return max(0, int(remaining))
        
    def is_timer_done(self, timer_id: int) -> bool:
        remaining = self.get_remaining_time(timer_id)
        if remaining is None:
            return False
        return remaining <= 0
        
    def stop_timer(self, timer_id: int) -> bool:
        if timer_id in self.active_timers:
            del self.active_timers[timer_id]
            return True
        return False
        
    def get_active_timers(self) -> dict:
        active = {}
        for timer_id, timer in self.active_timers.items():
            remaining = self.get_remaining_time(timer_id)
            if remaining and remaining > 0:
                active[timer_id] = {
                    'name': timer['name'],
                    'remaining': remaining
                }
        return active
        
    def format_time(self, seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
            
    def _start_timer_thread(self):
        """Start the timer monitoring thread."""
        self.running = True
        self.timer_thread = threading.Thread(target=self._monitor_timers)
        self.timer_thread.daemon = True
        self.timer_thread.start()
        
    def _monitor_timers(self):
        """Monitor active timers and trigger alerts when they expire."""
        expired_timers = set()
        last_update_time = datetime.now()
        countdown_interval = 5  # Show countdown every 5 seconds
        
        while self.running:
            current_time = datetime.now()
            
            # Check for expired timers
            for timer_id, timer in list(self.active_timers.items()):
                if timer_id in expired_timers:
                    continue  # Already processed this expired timer
                    
                if current_time >= timer['end_time']:
                    # Timer expired!
                    try:
                        # Print the notification to the console
                        self.console.print(f"\n[bold yellow]⏰ TIMER EXPIRED: {timer['name']} is done![/bold yellow]")
                        
                        # Call the callback if one is registered
                        if timer_id in self.timer_expired_callbacks:
                            self.timer_expired_callbacks[timer_id]()
                            
                        # Mark as expired so we don't notify again
                        expired_timers.add(timer_id)
                    except Exception as e:
                        print(f"Error in timer callback: {e}")
            
            # Display countdown updates at regular intervals
            time_since_update = (current_time - last_update_time).total_seconds()
            if time_since_update >= countdown_interval:
                active_timers_count = len(self.get_active_timers())
                
                if active_timers_count > 0:
                    self.console.print("\n[bold cyan]⏳ TIMER UPDATE:[/bold cyan]")
                    for timer_id, timer_info in self.get_active_timers().items():
                        time_str = self.format_time(timer_info['remaining'])
                        self.console.print(f"  [bold blue]⏳ {timer_info['name']}: [bold yellow]{time_str}[/bold yellow] remaining[/bold blue]")
                    
                last_update_time = current_time
            
            # Sleep for a short time to prevent high CPU usage
            time.sleep(0.5)  # Check timers twice per second
            
    def register_expired_callback(self, timer_id: int, callback: Callable) -> bool:
        """Register a callback function for a timer expiration."""
        if timer_id not in self.active_timers:
            return False
            
        self.timer_expired_callbacks[timer_id] = callback
        return True
        
    def cleanup(self):
        """Clean up timer resources."""
        self.running = False
        if self.timer_thread:
            self.timer_thread.join(timeout=1.0)
