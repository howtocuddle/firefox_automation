import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .utils import resolve_som_index, find_element_with_context

def scroll(driver, payload):
    if not payload:
        payload = "next"
    
    payload_lower = payload.lower().strip()
    
    try:
        page_info = driver.execute_script("""
            return {
                scrollTop: window.scrollY,
                scrollHeight: document.documentElement.scrollHeight,
                viewportHeight: window.innerHeight,
                clientHeight: document.documentElement.clientHeight
            };
        """)
        
        scroll_top = page_info['scrollTop']
        scroll_height = page_info['scrollHeight']
        viewport_height = page_info['viewportHeight']
        
        # Calculate pages (90% viewport overlap)
        page_height = int(viewport_height * 0.9)
        total_pages = max(1, (scroll_height - viewport_height) // page_height + 1)
        current_page = max(1, scroll_top // page_height + 1)
        
        new_scroll_top = scroll_top
        
        # Handle commands
        if payload_lower in ["up", "prev", "previous"]:
            target_page = max(1, current_page - 1)
            new_scroll_top = (target_page - 1) * page_height
            msg = f"Scrolled to page {target_page} of {total_pages}"
            
        elif payload_lower in ["down", "next"]:
            target_page = min(total_pages, current_page + 1)
            new_scroll_top = (target_page - 1) * page_height
            msg = f"Scrolled to page {target_page} of {total_pages}"
            
        elif payload_lower == "top":
            new_scroll_top = 0
            msg = "Scrolled to top (page 1)"
            
        elif payload_lower == "bottom":
            new_scroll_top = scroll_height
            msg = f"Scrolled to bottom (page {total_pages})"
            
        elif payload_lower.startswith("page "):
            try:
                target_page = int(payload_lower.split()[1])
                target_page = max(1, min(target_page, total_pages))
                new_scroll_top = (target_page - 1) * page_height
                msg = f"Scrolled to page {target_page} of {total_pages}"
            except (IndexError, ValueError):
                return "Error: Invalid page number format. Use 'page N'"
                
        elif payload_lower.isdigit():
            target_page = int(payload_lower)
            target_page = max(1, min(target_page, total_pages))
            new_scroll_top = (target_page - 1) * page_height
            msg = f"Scrolled to page {target_page} of {total_pages}"
        
        else:
            # Scroll to element
            try:
                selector, _, _ = resolve_som_index(payload)
            except ValueError as e:
                return f"Error: {e}"
            
            el = find_element_with_context(driver, selector)
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el)
            time.sleep(0.5)
            
            new_scroll = driver.execute_script("return window.scrollY;")
            new_page = max(1, new_scroll // page_height + 1)
            return f"Scrolled to element {payload} (now on page {new_page} of {total_pages})"
        
        # Perform scroll
        driver.execute_script(f"window.scrollTo({{top: {new_scroll_top}, behavior: 'smooth'}});")
        time.sleep(0.5)
        
        # Check if actually scrolled
        actual_scroll = driver.execute_script("return window.scrollY;")
        if abs(actual_scroll - scroll_top) < 10 and payload_lower in ["down", "next"]:
            msg += " (Already at end of page)"
        
        return msg
        
    except Exception as e:
        return f"Error scrolling: {e}"

def scroll_element(driver, payload):
    if '|' not in payload:
        return "Error: Format is 'selector|direction'. Direction: up, down, left, right, top, bottom."
    
    parts = payload.split('|', 1)
    sel = parts[0].strip()
    direction = parts[1].strip().lower()
    
    try:
        selector, _, _ = resolve_som_index(sel)
        element = find_element_with_context(driver, selector)
        
        script = ""
        if direction == "down": script = "arguments[0].scrollBy({top: 300, behavior: 'smooth'});"
        elif direction == "up": script = "arguments[0].scrollBy({top: -300, behavior: 'smooth'});"
        elif direction == "left": script = "arguments[0].scrollBy({left: -300, behavior: 'smooth'});"
        elif direction == "right": script = "arguments[0].scrollBy({left: 300, behavior: 'smooth'});"
        elif direction == "top": script = "arguments[0].scrollTo({top: 0, behavior: 'smooth'});"
        elif direction == "bottom": script = "arguments[0].scrollTo({top: arguments[0].scrollHeight, behavior: 'smooth'});"
        else: return f"Error: Unknown direction '{direction}'"
        
        driver.execute_script(script, element)
        time.sleep(0.5)
        return f"✓ Scrolled element {sel} {direction}"
    except Exception as e:
        return f"Error scrolling element: {e}"

def switch_frame(driver, payload):
    try:
        # If payload is an index
        if payload.isdigit():
            driver.switch_to.frame(int(payload))
            return f"✓ Switched to frame index {payload}"
        
        # If payload is a selector
        selector, _, _ = resolve_som_index(payload)
        element = find_element_with_context(driver, selector)
        driver.switch_to.frame(element)
        return f"✓ Switched to frame {payload}"
    except Exception as e:
        return f"Error switching frame: {e}"

def switch_default_content(driver, payload):
    try:
        driver.switch_to.default_content()
        return "✓ Switched to default content (main page)"
    except Exception as e:
        return f"Error: {e}"

def new_tab(driver, payload):
    url = payload if payload else "about:blank"
    try:
        driver.execute_script(f"window.open('{url}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        return f"✓ Opened new tab: {url}"
    except Exception as e:
        return f"Error opening tab: {e}"

def switch_tab(driver, payload):
    try:
        if not payload.isdigit():
            return "Error: Tab index required (0-based)."
        idx = int(payload)
        handles = driver.window_handles
        if 0 <= idx < len(handles):
            driver.switch_to.window(handles[idx])
            return f"✓ Switched to tab {idx} ({driver.title})"
        else:
            return f"Error: Invalid tab index {idx}. Open tabs: {len(handles)}"
    except Exception as e:
        return f"Error switching tab: {e}"

def open_in_new_tab(driver, payload):
    if not payload:
        return "Error: Element to open required."
    
    try:
        selector, element_info, som_number = resolve_som_index(payload)
    except ValueError as e:
        return f"Error: {e}"
    
    try:
        el = find_element_with_context(driver, selector)
        
        # Strategy 1: If it's a link with href, just open the URL
        href = el.get_attribute('href')
        if href:
            driver.execute_script(f"window.open('{href}', '_blank');")
            time.sleep(1.0)
            return f"✓ Opened link {href} in new tab (Total tabs: {len(driver.window_handles)})"
        
        # Strategy 2: Ctrl+Click (for non-links or JS links)
        actions = webdriver.ActionChains(driver)
        # Try CONTROL (Windows/Linux)
        actions.key_down(Keys.CONTROL).click(el).key_up(Keys.CONTROL).perform()
        
        # Wait a bit
        time.sleep(1.0)
        
        return f"✓ Opened {payload} in new tab (Total tabs: {len(driver.window_handles)})"
    except Exception as e:
        return f"Error opening in new tab: {e}"

def close_tab(driver, payload):
    try:
        idx = int(payload) if payload and payload.isdigit() else None
        handles = driver.window_handles
        
        if idx is not None:
            if 0 <= idx < len(handles):
                driver.switch_to.window(handles[idx])
                driver.close()
                # Switch to last tab if available
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[-1])
                return f"✓ Closed tab {idx}"
            else:
                return f"Error: Invalid tab index {idx}"
        else:
            # Close current
            driver.close()
            if driver.window_handles:
                driver.switch_to.window(driver.window_handles[-1])
            return "✓ Closed current tab"
    except Exception as e:
        return f"Error closing tab: {e}"

def list_tabs(driver, payload):
    try:
        handles = driver.window_handles
        current = driver.current_window_handle
        tabs = []
        for i, h in enumerate(handles):
            driver.switch_to.window(h)
            prefix = "*" if h == current else " "
            tabs.append(f"{prefix} [{i}] {driver.title} - {driver.current_url}")
        
        # Switch back to original
        driver.switch_to.window(current)
        return "\n".join(tabs)
    except Exception as e:
        return f"Error listing tabs: {e}"
