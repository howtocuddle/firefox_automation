import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .. import core
from .utils import resolve_som_index, find_element_with_context, click_by_coordinates
from ..helpers import human_click, human_type

def click(driver, payload):
    if not payload:
        return "Error: Element to click required."
    
    try:
        selector, element_info, som_number = resolve_som_index(payload)
    except ValueError as e:
        return f"Error: {e}"
    
    el = None
    use_coordinates = bool(element_info)
    
    # Coordinate-based click for SoM numbers
    if use_coordinates:
        expected_text = element_info.get('text', '').strip()
        print(f"[Browser] Click target {som_number}: {element_info.get('tag')} at center ({element_info.get('center', {}).get('x')}, {element_info.get('center', {}).get('y')}) - '{expected_text[:30]}'")
        
        success, el, msg = click_by_coordinates(driver, element_info, som_number)
        
        if not success:
            print(f"[Browser] {msg}, falling back to selector")
            use_coordinates = False
        else:
            print(f"[Browser] Found element at coordinates: {msg}")
    
    # Fallback to selector-based
    if not el:
        try:
            el = find_element_with_context(driver, selector)
            
            # Verify text if we have expectation
            if element_info:
                expected_text = element_info.get('text', '').strip()
                current_text = (el.text or el.get_attribute('value') or el.get_attribute('aria-label') or '').strip()
                
                if expected_text and current_text:
                    t1 = expected_text.lower()[:20]
                    t2 = current_text.lower()[:20]
                    if t1 not in t2 and t2 not in t1:
                        return f"Error: DOM Mismatch. Expected '{expected_text}', found '{current_text}'. Please SNAP again."
        except Exception as e:
            return f"Error finding element: {e}"
    
    # Capture state before click
    try:
        pre_state = {
            'text': el.text,
            'class': el.get_attribute('class'),
            'aria-label': el.get_attribute('aria-label'),
            'aria-expanded': el.get_attribute('aria-expanded'),
            'outerHTML': el.get_attribute('outerHTML')[:200],
            'title': driver.title
        }
    except:
        pre_state = {}

    # Perform click
    try:
        clicked = False
        method = "selector-based"
        
        if human_click(el):
            clicked = True
            method = "coordinate-based" if use_coordinates else "selector-based"
        else:
            # Fallback to JS Click
            print(f"[Browser] Human click failed for {payload}, trying JS click...")
            driver.execute_script("arguments[0].click();", el)
            clicked = True
            method = "JS Fallback"
        
        if clicked:
            # Wait for potential state change (increased for SPAs like Spotify)
            time.sleep(2.0)
            
            # Check state after click
            change_detected = False
            change_details = []
            try:
                # Re-fetch element if stale, or use current reference
                post_state = {
                    'text': el.text,
                    'class': el.get_attribute('class'),
                    'aria-label': el.get_attribute('aria-label'),
                    'aria-expanded': el.get_attribute('aria-expanded'),
                    'title': driver.title # Check if page title changed
                }
                
                # Check element attributes
                for key in ['text', 'class', 'aria-label', 'aria-expanded']:
                    val_before = pre_state.get(key)
                    val_after = post_state.get(key)
                    if val_before != val_after:
                        change_detected = True
                        v1 = str(val_before)[:20] if val_before else "None"
                        v2 = str(val_after)[:20] if val_after else "None"
                        change_details.append(f"{key}: '{v1}' -> '{v2}'")
                
                # Check page title
                title_before = pre_state.get('title')
                title_after = post_state.get('title')
                if title_before != title_after:
                    change_detected = True
                    change_details.append(f"Title: ...{str(title_before)[-10:]} -> ...{str(title_after)[-10:]}")
                    
            except:
                # Element likely stale (removed from DOM) -> Success!
                change_detected = True
                change_details.append("Element removed/stale")
            
            status = f" (State Changed: {', '.join(change_details)})" if change_detected else " (No State Change Detected)"
            return f"Clicked {payload} ({method}){status}"
        
        return f"Failed to click {payload}"

    except Exception as e:
        # Fallback to JS Click on error
        try:
            print(f"[Browser] Click error: {e}, trying JS click...")
            driver.execute_script("arguments[0].click();", el)
            return f"Clicked {payload} (JS Fallback after error)"
        except Exception as js_e:
            return f"Error clicking {payload}: {e} (JS fallback also failed: {js_e})"

def hover(driver, payload):
    if not payload:
        return "Error: Element to hover required."
    
    try:
        selector, element_info, som_number = resolve_som_index(payload)
    except ValueError as e:
        return f"Error: {e}"
    
    el = None
    use_coordinates = bool(element_info) and bool(element_info.get('center'))
    
    # Strategy 1: Coordinate-based hover (JS simulation)
    if use_coordinates:
        center = element_info.get('center', {})
        x, y = center.get('x'), center.get('y')
        print(f"[Browser] Hovering coordinates ({x}, {y}) for {payload}...")
        
        # Use JS to simulate mouseover at coordinates
        js_hover = f"""
        var el = document.elementFromPoint({x}, {y});
        if (el) {{
            var ev = new MouseEvent('mouseover', {{
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': {x},
                'clientY': {y}
            }});
            el.dispatchEvent(ev);
            
            var ev2 = new MouseEvent('mouseenter', {{
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': {x},
                'clientY': {y}
            }});
            el.dispatchEvent(ev2);
            
            var ev3 = new MouseEvent('mousemove', {{
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': {x},
                'clientY': {y}
            }});
            el.dispatchEvent(ev3);
            return true;
        }}
        return false;
        """
        if driver.execute_script(js_hover):
             return f"Hovered {payload} (Coordinates)"
    
    # Strategy 2: Selector-based hover
    try:
        el = find_element_with_context(driver, selector)
        action_chains = webdriver.ActionChains(driver)
        action_chains.move_to_element(el).perform()
        return f"Hovered over {payload}"
    except Exception as e:
        # Fallback: JS dispatchEvent on element
        if el:
            print(f"[Browser] Hover failed, trying JS dispatchEvent on element...")
            driver.execute_script("""
                var ev = new MouseEvent('mouseover', { 'view': window, 'bubbles': true, 'cancelable': true });
                arguments[0].dispatchEvent(ev);
            """, el)
            return f"Hovered {payload} (JS Fallback)"
        return f"Error hovering {payload}: {e}"

def focus(driver, payload):
    if not payload:
        return "Error: Element to focus required."
    
    try:
        selector, element_info, som_number = resolve_som_index(payload)
    except ValueError as e:
        return f"Error: {e}"
    
    el = None
    use_coordinates = bool(element_info) and bool(element_info.get('center'))
    
    # Strategy 1: Coordinate-based click to focus
    if use_coordinates:
        print(f"[Browser] Focusing via coordinates for {payload}...")
        success, hit_el, msg = click_by_coordinates(driver, element_info, som_number)
        if success and hit_el:
            try:
                # Just a gentle click to focus
                driver.execute_script("arguments[0].focus();", hit_el)
                return f"Focused {payload} (Coordinates)"
            except:
                pass
    
    # Strategy 2: Selector-based focus
    try:
        el = find_element_with_context(driver, selector)
        driver.execute_script("arguments[0].focus();", el)
        return f"Focused {payload}"
    except Exception as e:
        return f"Error focusing {payload}: {e}"

def right_click(driver, payload):
    if not payload:
        return "Error: Selector or index required."
    
    try:
        selector, element_info, som_number = resolve_som_index(payload)
    except ValueError as e:
        return f"Error: {e}"
    
    el = None
    use_coordinates = bool(element_info) and bool(element_info.get('center'))
    
    # Strategy 1: Coordinate-based right click (JS simulation)
    if use_coordinates:
        center = element_info.get('center', {})
        x, y = center.get('x'), center.get('y')
        print(f"[Browser] Right-clicking coordinates ({x}, {y}) for {payload}...")
        
        # Use JS to simulate contextmenu at coordinates
        js_rclick = f"""
        var el = document.elementFromPoint({x}, {y});
        if (el) {{
            var ev = new MouseEvent('contextmenu', {{
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': {x},
                'clientY': {y},
                'button': 2
            }});
            el.dispatchEvent(ev);
            return true;
        }}
        return false;
        """
        if driver.execute_script(js_rclick):
             return f"Right-clicked {payload} (Coordinates)"
    
    # Strategy 2: Selector-based right click
    try:
        el = find_element_with_context(driver, selector)
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el)
        time.sleep(0.5)
        
        actions = webdriver.ActionChains(driver)
        actions.context_click(el).perform()
        time.sleep(1.0)
        return f"Right-clicked {payload}"
    except Exception as e:
        # Fallback: JS dispatchEvent on element
        if el:
            print(f"[Browser] Right-click failed, trying JS dispatchEvent on element...")
            driver.execute_script("""
                var ev = new MouseEvent('contextmenu', { 'view': window, 'bubbles': true, 'cancelable': true, 'button': 2 });
                arguments[0].dispatchEvent(ev);
            """, el)
            return f"Right-clicked {payload} (JS Fallback)"
        return f"Error right-clicking: {e}"

def type_text(driver, payload):
    if '|' not in payload:
        return "Error: Format is 'selector|text' or 'selector|text|ENTER'"
    
    parts = payload.split('|')
    press_enter = len(parts) == 3 and parts[2].strip().upper() == "ENTER"
    
    sel = parts[0].strip()
    text = parts[1]
    
    try:
        selector, element_info, som_number = resolve_som_index(sel)
    except ValueError as e:
        return f"Error: {e}"
    
    try:
        # Strategy 1: Coordinate-based click & focus (User Request)
        target_el = None
        use_coordinates = bool(element_info) and bool(element_info.get('center'))
        
        if use_coordinates:
            print(f"[Browser] Type: Clicking coordinates for {sel} before typing...")
            success, hit_el, msg = click_by_coordinates(driver, element_info, som_number)
            if success and hit_el:
                # Click to focus
                try:
                    human_click(hit_el)
                    time.sleep(1.0) # Increased wait for animations/expansion
                    target_el = driver.switch_to.active_element
                    print(f"[Browser] Type: Clicked coordinates, active element is now: {target_el.tag_name} (visible: {target_el.is_displayed()})")
                except Exception as e:
                    print(f"[Browser] Type: Failed to click/focus via coordinates: {e}")
        
        # Strategy 2: Selector-based find (Fallback or if no coords)
        if not target_el:
            el = find_element_with_context(driver, selector)
        
        # Check if element is actually an input/textarea
        effective_el = target_el if target_el else el
        tag = effective_el.tag_name.lower()
        is_input = tag in ['input', 'textarea'] or effective_el.get_attribute('contenteditable') == 'true'
        
        print(f"[Browser] Target element is {tag}, is_input={is_input}")
        
        # If not an input, try to find one inside
        if not is_input:
            try:
                inputs = effective_el.find_elements(By.TAG_NAME, "input")
                print(f"[Browser] Found {len(inputs)} descendant inputs.")
                if inputs:
                    visible_inputs = [i for i in inputs if i.is_displayed()]
                    if visible_inputs:
                        target_el = visible_inputs[0]
                        print(f"[Browser] Target {sel} is not an input. Found visible descendant input: {target_el.get_attribute('outerHTML')[:100]}")
                        is_input = True
                    else:
                        search_inputs = [i for i in inputs if i.get_attribute('name') == 'q' or i.get_attribute('type') == 'search']
                        if search_inputs:
                            target_el = search_inputs[0]
                            print(f"[Browser] Target {sel} is not an input. Found hidden search descendant input: {target_el.get_attribute('outerHTML')[:100]}")
                            is_input = True
            except Exception as e:
                print(f"[Browser] Error searching for descendant inputs: {e}")
        
        # If still not an input, we might need to click it to focus, then type into active element
        if not is_input:
            print(f"[Browser] Target {sel} ({tag}) is not an input. Clicking to focus, then typing into active element...")
            try:
                if not use_coordinates:
                    el.click()
                    time.sleep(0.5)
                
                active = driver.switch_to.active_element
                if active.tag_name.lower() in ['input', 'textarea'] or active.get_attribute('contenteditable') == 'true':
                    target_el = active
                    print(f"[Browser] Switched to active element: {target_el.tag_name}")
                else:
                    print(f"[Browser] Active element {active.tag_name} is not an input. Staying with original target.")
            except Exception as e:
                print(f"[Browser] Failed to switch to active element: {e}")
        
        # Now type into target_el
        if human_type(target_el, text):
            if press_enter:
                time.sleep(0.5)
                target_el.send_keys(Keys.ENTER)
                return f"✓ Typed '{text}' and pressed ENTER into {sel} (via {target_el.tag_name})"
            
            final_value = target_el.get_attribute('value') or target_el.text or ''
            return f"✓ Typed '{text}' into {sel}. Current value: '{final_value}'"
        else:
            # Fallback to JS Type on target_el
            print(f"[Browser] Human type failed, trying JS type on {target_el.tag_name}...")
            safe_text = json.dumps(text)
            driver.execute_script(f"""
                arguments[0].value = {safe_text};
                arguments[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                arguments[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
            """, target_el)
            if press_enter:
                 try:
                    target_el.send_keys(Keys.ENTER)
                 except:
                    driver.execute_script("if(arguments[0].form) arguments[0].form.submit();", target_el)
            return f"✓ Typed '{text}' into {sel} (JS Fallback)"
    except Exception as e:
        return f"Error typing into {sel}: {e}"

def clear(driver, payload):
    if not payload:
        return "Error: Selector required"
    
    try:
        selector, _, _ = resolve_som_index(payload)
    except ValueError as e:
        return f"Error: {e}"
    
    try:
        element = find_element_with_context(driver, selector)
        element.clear()
        
        if element.get_attribute('contenteditable') == 'true':
            driver.execute_script("arguments[0].textContent = '';", element)
        
        return f"✓ Cleared {payload}"
    except Exception as e:
        return f"Error clearing {payload}: {e}"

def drag_and_drop(driver, payload):
    if '|' not in payload:
        return "Error: Format is 'source|target'"
    
    source_sel, target_sel = payload.split('|', 1)
    
    try:
        source_selector, _, _ = resolve_som_index(source_sel.strip())
        target_selector, _, _ = resolve_som_index(target_sel.strip())
    except ValueError as e:
        return f"Error: {e}"
    
    try:
        source = find_element_with_context(driver, source_selector)
        target = find_element_with_context(driver, target_selector)
        
        action_chains = webdriver.ActionChains(driver)
        action_chains.drag_and_drop(source, target).perform()
        time.sleep(0.5)
        return f"✓ Dragged to target"
    except Exception as e:
        return f"Error: {e}"

def upload_file(driver, payload):
    if '|' not in payload:
        return "Error: Format is 'selector|filepath'"
    
    sel, filepath = payload.split('|', 1)
    filepath = filepath.strip()
    
    if not os.path.exists(filepath):
        return f"Error: File not found at {filepath}"
    
    try:
        selector, _, _ = resolve_som_index(sel.strip())
    except ValueError as e:
        return f"Error: {e}"
    
    try:
        el = find_element_with_context(driver, selector)
        el.send_keys(filepath)
        return f"✓ Uploaded {filepath}"
    except Exception as e:
        return f"Error uploading: {e}"
