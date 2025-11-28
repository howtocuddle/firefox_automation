"""
Browser High-Level Interface
Handles JSON action sequences and session commands.
"""
import time
import json
from .core import get_driver
from .dispatcher import browser_automation
from .autonomous import autonomous_browser
from .helpers import human_click

def browser(goal: str, mode: str = "normal_research") -> str:
    """
    Autonomous Web Browser.
    
    Give a high-level goal (e.g., "Find the cheapest flight to Tokyo") and the browser will:
    1. Navigate and interact with the web autonomously
    2. Use vision (Set-of-Marks) to understand page state
    3. Return a summary of actions and results
    
    Args:
        goal (str): The objective to achieve.
        mode (str): "normal_research" (default).
    """
    
    # Mode 1: JSON Action Sequence
    if goal.strip().startswith('{'):
        print(f"\n[Browser] Detected JSON action sequence. Parsing...")
        
        # Ensure browser is open first
        if not get_driver():
            print("[Browser] Opening browser...")
            browser_automation("open")
        
        # Parse and execute each action
        results = []
        # Split by '}{'  to separate JSON objects
        action_strings = goal.replace('}{', '}|||{').split('|||')
        
        for i, action_str in enumerate(action_strings):
            try:
                cmd = json.loads(action_str.strip())
                action = cmd.get("action")
                payload = cmd.get("payload", "")
                
                print(f"\n[Browser] Action {i+1}/{len(action_strings)}: {action.upper()} -> {payload}")
                result = browser_automation(action, payload)
                print(f"[Browser] Result: {result}")
                results.append(f"{i+1}. {action}({payload}) -> {result}")
                
                # Wait between actions
                time.sleep(1.5)
                
            except Exception as e:
                error_msg = f"{i+1}. Error parsing/executing action '{action_str}': {e}"
                print(f"[Browser] {error_msg}")
                results.append(error_msg)
        
        return "\n".join(results)
    
    # Mode 2: Session Commands (NEW)
    # Simple text commands for ReAct loop integration
    # Mode 2: Session Commands (NEW)
    # Simple text commands for ReAct loop integration
    else:
        goal_lower = goal.lower().strip()
        
        print(f"\n[Browser] Received goal: {goal}")
        
        # Helper to check if string looks like a URL
        def is_url(s):
            return "http" in s or "www." in s or (".com" in s or ".org" in s or ".net" in s or ".io" in s)

        # Open/Visit URL
        # Only treat as command if it looks like a URL AND has no spaces (simple command)
        # We calculate potential_url first to check conditions
        parts = goal.split(None, 1)
        potential_url = parts[1].strip() if len(parts) > 1 else ""
        is_simple_url = (goal_lower.startswith("open ") or goal_lower.startswith("visit ")) and \
                        " " not in potential_url and \
                        is_url(potential_url)

        if is_simple_url:
            # Ensure browser is open
            if not get_driver():
                print("[Browser] Opening new browser instance...")
                browser_automation("open")
            
            print(f"[Browser] Executing direct navigation to: {potential_url}")
            
            browser_automation("visit", potential_url)
            time.sleep(2)  # Wait for page load
            return browser_automation("snap")
        
        # Web Search
        elif goal_lower.startswith("search ") or goal_lower.startswith("google "):
            if not get_driver():
                browser_automation("open")
            
            query = goal.split(None, 1)[1] if len(goal.split(None, 1)) > 1 else ""
            print(f"[Browser] Executing web search for: {query}")
            
            browser_automation("web_search", query)
            time.sleep(2)
            return browser_automation("snap")
        
        # Click
        elif goal_lower.startswith("click "):
            if not get_driver():
                return "Error: No browser open. Use 'open <url>' first."
            
            target = goal.split(None, 1)[1] if len(goal.split(None, 1)) > 1 else ""
            print(f"[Browser] Executing click on: {target}")
            
            result = browser_automation("click", target)
            time.sleep(1.5)
            snap = browser_automation("snap")
            return f"{result}\n\n{snap}"
        
        # Type
        elif goal_lower.startswith("type "):
            if not get_driver():
                return "Error: No browser open. Use 'open <url>' first."
            
            payload = goal.split(None, 1)[1] if len(goal.split(None, 1)) > 1 else ""
            print(f"[Browser] Executing type: {payload}")
            
            result = browser_automation("type", payload)
            time.sleep(0.5)
            snap = browser_automation("snap")
            return f"{result}\n\n{snap}"
        
        # Scroll
        elif goal_lower in ["scroll", "scroll down"]:
            print("[Browser] Scrolling down")
            browser_automation("scroll")
            time.sleep(0.5)
            return browser_automation("snap")
        
        elif goal_lower in ["scroll up", "scroll top"]:
            print("[Browser] Scrolling to top")
            browser_automation("scroll", "top")
            time.sleep(0.5)
            return browser_automation("snap")
        
        elif goal_lower == "scroll bottom":
            print("[Browser] Scrolling to bottom")
            browser_automation("scroll", "bottom")
            time.sleep(0.5)
            return browser_automation("snap")
        
        # Snap
        elif goal_lower == "snap":
            print("[Browser] Taking snapshot")
            return browser_automation("snap")
        
        # Close
        elif goal_lower in ["close", "quit", "exit"]:
            print("[Browser] Closing browser")
            return browser_automation("close")
        
        # Back/Forward/Reload
        elif goal_lower == "back":
            print("[Browser] Navigating back")
            browser_automation("back")
            time.sleep(1)
            return browser_automation("snap")
            
        elif goal_lower == "forward":
            print("[Browser] Navigating forward")
            browser_automation("forward")
            time.sleep(1)
            return browser_automation("snap")
            
        elif goal_lower in ["reload", "refresh"]:
            print("[Browser] Reloading page")
            browser_automation("reload")
            time.sleep(1.5)
            return browser_automation("snap")
        
        # Mode 3: Autonomous SoM-Based Browsing
        # If goal doesn't match any session command, treat as autonomous goal
        else:
            print(f"[Browser] No direct command matched. Activating Autonomous Mode for: {goal}")
            return autonomous_browser(goal)
