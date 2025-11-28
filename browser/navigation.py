"""
Browser Navigation
Handles URL navigation, search, and tab management
"""
import time
from urllib.parse import quote_plus
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .core import get_driver, open_browser, log_url
from .helpers import human_click

def perform_navigation(action: str, payload: str = None) -> str:
    driver = get_driver()
    
    # Auto-restart if session is lost and action requires browser
    if not driver and action not in ["open", "close", "nuke"]:
        restart_res = open_browser()
        driver = get_driver()
        if not driver:
            return f"Error: Browser session was lost and failed to restart. Reason: {restart_res}"
        
        # If the action was just to check something, we can proceed, 
        # but if it was interaction, we are now on a blank page.
        if action == "visit":
            # We can proceed with visit
            pass
        else:
            return "Browser session was lost and has been restarted (fresh state). Please retry your command."

    if action == "visit":
        if not payload: return "Error: URL required."
        
        # Enforce protocol
        if not payload.startswith("http"):
            payload = "https://" + payload
            
        try:
            driver.get(payload)
            log_url(payload, driver.title)
            return f"Visited {payload}. Title: {driver.title}"
        except Exception as e:
            return f"Error visiting: {e}"

    elif action == "web_search":
        if not payload:
            return "Error: Query required."
        
        # Default to DuckDuckGo for privacy, but this is just a default implementation
        # The agent can also just use 'visit https://google.com' directly
        if "duckduckgo.com" not in driver.current_url:
            driver.get("https://duckduckgo.com")
            time.sleep(1)
        
        try:
            search_box = driver.find_element(By.NAME, "q")
            search_box.clear()
            search_box.send_keys(payload)
            search_box.send_keys(Keys.RETURN)
            time.sleep(2)
            log_url(driver.current_url, f"Search: {payload}")
            
            return f"Searched web for: {payload}"
        except Exception as e:
            return f"Error searching: {e}"

    elif action == "reload":
        try:
            driver.refresh()
            return "Refreshed page."
        except Exception as e:
            return f"Error refreshing: {e}"

    elif action == "back":
        try:
            driver.back()
            return "Navigated back."
        except Exception as e:
            return f"Error navigating back: {e}"

    elif action == "forward":
        try:
            driver.forward()
            return "Navigated forward."
        except Exception as e:
            return f"Error navigating forward: {e}"

    elif action == "new_tab":
        try:
            target_url = payload if payload else "about:blank"
            
            # Enforce protocol for non-special URLs
            if target_url != "about:blank" and not target_url.startswith("http"):
                target_url = "https://" + target_url
                
            driver.switch_to.new_window('tab')
            driver.get(target_url)
            return f"Opened new tab: {target_url}"
        except Exception as e:
            return f"Error opening new tab: {e}"

    elif action == "change_tab":
        try:
            # Payload should be index (0-based)
            idx = int(payload)
            handles = driver.window_handles
            if 0 <= idx < len(handles):
                driver.switch_to.window(handles[idx])
                return f"Switched to tab {idx} - {driver.title}"
            else:
                return f"Error: Tab index {idx} out of range (0-{len(handles)-1})"
        except Exception as e:
            return f"Error switching tab: {e}"

    elif action == "close_tab":
        try:
            driver.close()
            # Switch to last tab if any remain
            if len(driver.window_handles) > 0:
                driver.switch_to.window(driver.window_handles[-1])
            return "Closed tab."
        except Exception as e:
            return f"Error closing tab: {e}"

    elif action == "get_tabs":
         try:
             handles = driver.window_handles
             current = driver.current_window_handle
             tabs_info = []
             for i, h in enumerate(handles):
                 driver.switch_to.window(h)
                 tabs_info.append(f"[{i}] {driver.title} ({driver.current_url}) {'*' if h == current else ''}")
             
             # Switch back to original
             driver.switch_to.window(current)
             return "\n".join(tabs_info)
         except Exception as e:
             return f"Error getting tabs: {e}"

    return None
