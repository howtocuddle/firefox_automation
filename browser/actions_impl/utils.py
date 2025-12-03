import time
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .. import core
from .. import xpath_journal
from ..helpers import human_click

def remove_overlays(driver):
    """Injects JS to remove annoyance overlays."""
    try:
        driver.execute_script("""
            document.querySelectorAll('.overlay, .modal, .popup, .cookie-banner, #onetrust-banner-sdk').forEach(el => el.remove());
        """)
    except:
        pass

def resolve_som_index(payload):
    """
    Resolve SoM index to selector if payload is a digit.
    Returns: (resolved_selector, element_info, som_number)
    """
    if not payload:
        raise ValueError("Payload required")
        
    parts = payload.split('|')
    selector = parts[0].strip()
    
    element_info = {}
    som_number = None
    
    # Check if it's a SoM index (digits)
    if selector.isdigit():
        idx = int(selector)
        som_number = idx
        if hasattr(core, '_element_map') and idx in core._element_map:
            element_info = core._element_map[idx]
            # Use the xpath from the map if available, fallback to stored selector
            if 'xpath' in element_info:
                selector = f"xpath:{element_info['xpath']}"
            else:
                selector = element_info.get('selector', selector)
        else:
            # If not in map, maybe it's a raw index? 
            # But we can't do much without the map.
            # Assume it might be a frame index or something else if context implies,
            # but for now, treat as error or raw selector?
            # Actually, if it's just a number and not in map, it's likely invalid.
            pass

    return selector, element_info, som_number

def find_element_with_context(driver, selector):
    """
    Finds an element handling context switching (iframes, shadow roots).
    Selector format: "iframe_selector >> shadow-root >> element_selector"
    """
    # Check XPath Journal first
    if selector.startswith("xpath:") or (not selector.isdigit() and ">>" not in selector):
         # Try to find in journal if it looks like a semantic name (not implemented here, but logic exists)
         pass

    if ">>" in selector:
        parts = selector.split(">>")
        current_context = driver
        
        for i, part in enumerate(parts):
            part = part.strip()
            if i == len(parts) - 1:
                # Last part is the element
                if part.startswith("xpath:"):
                    return current_context.find_element(By.XPATH, part[6:])
                return current_context.find_element(By.CSS_SELECTOR, part)
            
            # Context switching
            if part == "shadow-root":
                # Shadow root of previous element? 
                # Actually shadow root is usually attached to an element.
                # Syntax: host_element >> shadow-root >> target
                # So current_context is the host.
                current_context = driver.execute_script("return arguments[0].shadowRoot", current_context)
            else:
                # Find frame or host
                if part.startswith("xpath:"):
                    el = current_context.find_element(By.XPATH, part[6:])
                else:
                    el = current_context.find_element(By.CSS_SELECTOR, part)
                
                if el.tag_name == "iframe":
                    driver.switch_to.frame(el)
                    current_context = driver
                else:
                    current_context = el
        return current_context
    
    # Simple selector
    if selector.startswith("xpath:"):
        return driver.find_element(By.XPATH, selector[6:])
    return driver.find_element(By.CSS_SELECTOR, selector)

def click_by_coordinates(driver, element_info, som_number):
    """
    Click element using exact coordinates from SoM data.
    Returns: (success: bool, element: WebElement, message: str)
    """
    if not element_info or 'center' not in element_info:
        return False, None, "No coordinates available"
        
    x, y = element_info['center']['x'], element_info['center']['y']
    
    # Scroll to view if needed (simple check)
    # driver.execute_script(f"window.scrollTo({x}, {y})") 
    
    try:
        # Use elementFromPoint to get the actual element at coordinates
        el = driver.execute_script(f"return document.elementFromPoint({x}, {y});")
        if el:
            # Try human click first
            if human_click(el):
                return True, el, f"Clicked coordinates ({x}, {y}) for #{som_number}"
            else:
                # JS Fallback
                driver.execute_script("arguments[0].click();", el)
                return True, el, f"JS Clicked coordinates ({x}, {y}) for #{som_number}"
        else:
            return False, None, f"No element found at ({x}, {y})"
    except Exception as e:
        return False, None, f"Error clicking coordinates: {e}"
