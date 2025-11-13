import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional


class CookingTimer:
    def __init__(self):
        self.active_timers = {}
        self.timer_count = 0
        
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
            
    async def start_timer(self, duration_seconds: int, name: Optional[str] = None) -> int:
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
