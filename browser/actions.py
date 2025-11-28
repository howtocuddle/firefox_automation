"""
Browser Actions - Refactored
Handles interaction with page elements: click, type, scroll, etc.
"""
import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from ...safety import get_workspace_path
from .core import get_driver
from . import core
from .helpers import human_click, human_type
from .helpers import human_click, human_type
from selenium import webdriver
from . import xpath_journal


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def remove_overlays(driver):
    """Injects JS to remove annoyance overlays."""
    try:
        js_path = os.path.join(os.path.dirname(__file__), "js", "overlays.js")
        if os.path.exists(js_path):
            with open(js_path, "r") as f:
                js = f.read()
            driver.execute_script(js)
    except Exception as e:
        print(f"[Browser] Warning: Failed to remove overlays: {e}")


def resolve_som_index(payload):
    """
    Resolve SoM index to selector if payload is a digit.
    Returns: (resolved_selector, element_info, som_number)
    """
    if not payload or not payload.strip().isdigit():
        return payload, None, None
    
    index = int(payload.strip())
    if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
        element_info = core._element_map[index]
        return element_info['selector'], element_info, index
    else:
        raise ValueError(f"SoM index {index} not found in element map")


def find_element_with_context(driver, selector):
    """
    Finds an element handling context switching (iframes, shadow roots).
    Selector format: "iframe_selector >> shadow-root >> element_selector"
    """
    # Try XPath Journal first for non-complex selectors
    if ">>" not in selector and not selector.startswith("/") and not selector.startswith("#") and not selector.startswith("."):
        cached_xpath = xpath_journal.get_xpath(driver.current_url, selector)
        if cached_xpath:
            try:
                print(f"[Browser] Using cached XPath for '{selector}': {cached_xpath}")
                return driver.find_element(By.XPATH, cached_xpath)
            except:
                print(f"[Browser] Cached XPath failed for '{selector}'")

    parts = [p.strip() for p in selector.split('>>')]
    current_context = driver
    
    for i, part in enumerate(parts):
        is_last = (i == len(parts) - 1)
        
        if part == "shadow-root":
            if isinstance(current_context, webdriver.remote.webelement.WebElement):
                current_context = current_context.shadow_root
            else:
                raise Exception("Cannot switch to shadow-root: previous context is not an element")
            continue

        element = None
        
        # Try CSS
        try:
            element = current_context.find_element(By.CSS_SELECTOR, part)
        except:
            pass
        
        # Try XPath (not supported in shadow roots)
        if not element and not isinstance(current_context, webdriver.remote.shadowroot.ShadowRoot):
            try:
                element = current_context.find_element(By.XPATH, part)
            except:
                pass
        
        # Heuristics for final target
        if not element and is_last:
            try:
                xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{part.lower()}')]"
                if not isinstance(current_context, webdriver.remote.shadowroot.ShadowRoot):
                    element = current_context.find_element(By.XPATH, xpath)
            except:
                pass

        if not element:
            raise Exception(f"Could not find element: {part}")
        
        if not is_last:
            if element.tag_name.lower() in ['iframe', 'frame']:
                driver.switch_to.frame(element)
                current_context = driver
            else:
                current_context = element
        else:
            # Found final element
            # Save to journal if it was a simple search (not SoM index)
            if ">>" not in selector and not selector.startswith("/") and not selector.startswith("#") and not selector.startswith("."):
                 robust_xpath = xpath_journal.generate_robust_xpath(element, driver)
                 if robust_xpath:
                     xpath_journal.save_xpath(driver.current_url, selector, robust_xpath)
            
            return element

    return current_context


def click_by_coordinates(driver, element_info, som_number):
    """
    Click element using exact coordinates from SoM data.
    Returns: (success: bool, element: WebElement, message: str)
    """
    viewport_coords = element_info.get('viewportCoords', {})
    center = element_info.get('center', {})
    expected_text = element_info.get('text', '').strip()
    
    if not (center.get('x') and center.get('y')):
        return False, None, "No coordinates available"
    
    center_x = viewport_coords.get('centerX', center.get('x'))
    center_y = viewport_coords.get('centerY', center.get('y'))
    
    find_script = f"""
    var el = document.elementFromPoint({center_x}, {center_y});
    if (!el) return null;
    window._agentClickTarget = el;
    return {{
        tag: el.tagName,
        text: (el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || '').substring(0, 100),
        rect: el.getBoundingClientRect()
    }};
    """
    
    found_info = driver.execute_script(find_script)
    
    if not found_info:
        return False, None, f"No element at coordinates ({center_x}, {center_y})"
    
    element = driver.execute_script("return window._agentClickTarget;")
    found_text = found_info.get('text', '').strip()
    
    # Verify text match (relaxed)
    if expected_text and found_text:
        t1 = expected_text.lower()[:30]
        t2 = found_text.lower()[:30]
        
        if t1 not in t2 and t2 not in t1:
            print(f"[Browser] Warning: Text mismatch at ({center_x}, {center_y}). Expected '{expected_text[:30]}', found '{found_text[:30]}'. Proceeding anyway.")
            
    return True, element, f"{found_info.get('tag')} - '{found_text[:40]}'"


# ============================================================================
# MAIN ACTION HANDLER
# ============================================================================

def perform_action(action: str, payload: str = None) -> str:
    driver = get_driver()
    if not driver:
        return "Error: Browser not open."

    # Auto-remove overlays before any action
    remove_overlays(driver)
    driver.switch_to.default_content()

    # ========================================================================
    # ELEMENT FINDING
    # ========================================================================
    
    if action == "find_element":
        if not payload:
            return "Error: Text to find required."
        
        script = f"""
        var text = "{payload.lower()}";
        var elements = document.querySelectorAll('a, button, input, textarea, [role="button"]');
        var found = [];
        
        for (var i=0; i<elements.length; i++) {{
            var el = elements[i];
            var elText = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('alt') || '').toLowerCase();
            
            if (elText.includes(text) && el.offsetParent !== null) {{
                var selector = el.tagName.toLowerCase();
                if (el.id) selector += '#' + el.id;
                else if (el.className && typeof el.className === 'string') {{
                    var classes = el.className.split(' ').filter(c => c.length > 0 && !c.includes(':'));
                    if (classes.length > 0) selector += '.' + classes.slice(0, 2).join('.');
                }}
                
                found.push({{
                    tag: el.tagName,
                    text: elText.substring(0, 50),
                    selector: selector,
                    rect: el.getBoundingClientRect()
                }});
            }}
        }}
        return found;
        """
        
        try:
            results = driver.execute_script(script)
            if not results:
                return f"No elements found containing '{payload}'"
            
            output = [f"Found {len(results)} elements matching '{payload}':"]
            for i, res in enumerate(results[:10]):
                output.append(f"{i+1}. {res['tag']}: {res['text']} -> {res['selector']}")
            
            return "\\n".join(output)
        except Exception as e:
            return f"Error finding element: {e}"

    # ========================================================================
    # CLICKING & INTERACTION
    # ========================================================================
    
    elif action == "click":
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
                    # Note: el might be stale if page changed, which is a BIG change
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
                            # Truncate long text
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

    elif action == "hover":
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

    elif action == "focus":
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

    elif action == "right_click":
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

    # ========================================================================
    # SCROLLING (Page-Based)
    # ========================================================================
    
    elif action == "scroll":
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

    # ========================================================================
    # TEXT INPUT
    # ========================================================================
    
    elif action == "type":
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
            # If we have SoM coordinates, click there first to ensure the right element is focused
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
            # If target_el was set by click, use it. Otherwise use el.
            effective_el = target_el if target_el else el
            tag = effective_el.tag_name.lower()
            is_input = tag in ['input', 'textarea'] or effective_el.get_attribute('contenteditable') == 'true'
            
            print(f"[Browser] Target element is {tag}, is_input={is_input}")
            
            # If not an input, try to find one inside
            if not is_input:
                try:
                    # Search inside effective_el (which might be the container)
                    inputs = effective_el.find_elements(By.TAG_NAME, "input")
                    print(f"[Browser] Found {len(inputs)} descendant inputs.")
                    if inputs:
                        # Prioritize visible inputs, but accept hidden ones if they look like search
                        visible_inputs = [i for i in inputs if i.is_displayed()]
                        if visible_inputs:
                            target_el = visible_inputs[0]
                            print(f"[Browser] Target {sel} is not an input. Found visible descendant input: {target_el.get_attribute('outerHTML')[:100]}")
                            is_input = True
                        else:
                            # Check for search inputs even if hidden
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
                    # Only click if we haven't already clicked via coordinates
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
                driver.execute_script(f"""
                    arguments[0].value = "{text}";
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

    elif action == "clear":
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

    # ========================================================================
    # FORM ELEMENTS
    # ========================================================================
    
    elif action == "select":
        if '|' not in payload:
            return "Error: Format is 'selector|option'"
        
        sel, option = payload.split('|', 1)
        sel = sel.strip()
        option = option.strip()
        
        try:
            selector, _, _ = resolve_som_index(sel)
        except ValueError as e:
            return f"Error: {e}"
        
        try:
            element = find_element_with_context(driver, selector)
            
            if element.tag_name.lower() != 'select':
                return f"Error: Element is not a <select> dropdown"
            
            select = Select(element)
            
            # Try: visible text → value → index
            # Try 1: Exact visible text
            try:
                select.select_by_visible_text(option)
                return f"✓ Selected '{option}' from dropdown"
            except:
                pass

            # Try 2: Exact value
            try:
                select.select_by_value(option)
                return f"✓ Selected '{option}' (by value)"
            except:
                pass
                
            # Try 3: Case-insensitive / Partial match on Text
            options = select.options
            option_lower = option.lower()
            
            # 3a. Case-insensitive exact text
            for opt in options:
                if opt.text.strip().lower() == option_lower:
                    select.select_by_visible_text(opt.text)
                    return f"✓ Selected '{opt.text}' (case-insensitive match for '{option}')"
            
            # 3b. Partial match text (starts with)
            for opt in options:
                if opt.text.strip().lower().startswith(option_lower):
                    select.select_by_visible_text(opt.text)
                    return f"✓ Selected '{opt.text}' (partial match for '{option}')"
            
            # 3c. Partial match text (contains)
            for opt in options:
                if option_lower in opt.text.strip().lower():
                    select.select_by_visible_text(opt.text)
                    return f"✓ Selected '{opt.text}' (fuzzy match for '{option}')"

            # Try 4: Index
            if option.isdigit():
                try:
                    idx = int(option)
                    select.select_by_index(idx)
                    return f"✓ Selected option {idx} (by index)"
                except:
                    pass

            # Failed
            options_text = [opt.text for opt in options]
            return f"✗ Option '{option}' not found. Available: {', '.join(options_text[:10])}"
        except Exception as e:
            return f"Error selecting: {e}"

    elif action == "checkbox":
        parts = payload.split('|') if '|' in payload else [payload, 'toggle']
        sel = parts[0].strip()
        action_type = parts[1].strip().lower() if len(parts) > 1 else 'toggle'
        
        try:
            selector, _, _ = resolve_som_index(sel)
        except ValueError as e:
            return f"Error: {e}"
        
        try:
            element = find_element_with_context(driver, selector)
            
            if element.get_attribute('type') != 'checkbox':
                return f"Error: Not a checkbox"
            
            is_checked = element.is_selected()
            
            if action_type == 'toggle':
                element.click()
                return f"✓ Toggled checkbox to {'checked' if not is_checked else 'unchecked'}"
            elif action_type in ['check', 'true', 'on', '1']:
                if not is_checked:
                    element.click()
                return f"✓ Checked"
            elif action_type in ['uncheck', 'false', 'off', '0']:
                if is_checked:
                    element.click()
                return f"✓ Unchecked"
            else:
                return f"Error: Invalid action '{action_type}'"
        except Exception as e:
            return f"Error: {e}"

    # ========================================================================
    # TAB MANAGEMENT
    # ========================================================================

    elif action == "new_tab":
        url = payload if payload else "about:blank"
        try:
            driver.execute_script(f"window.open('{url}', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            return f"✓ Opened new tab: {url}"
        except Exception as e:
            return f"Error opening tab: {e}"

    elif action == "switch_tab":
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

    elif action == "open_in_new_tab":
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

    elif action == "close_tab":
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

    elif action == "list_tabs":
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

    # ========================================================================
    # SYSTEM & DEBUG
    # ========================================================================

    elif action == "get_clipboard":
        try:
            # Try Tkinter (cross-platform)
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            content = root.clipboard_get()
            root.destroy()
            return f"Clipboard: {content}"
        except:
            try:
                # Try JS (requires permission/focus)
                content = driver.execute_script("return navigator.clipboard.readText();")
                return f"Clipboard (JS): {content}"
            except Exception as e:
                return f"Error reading clipboard: {e}"

    elif action == "get_console_logs":
        try:
            # Check if driver supports log_types
            if hasattr(driver, 'get_log'):
                logs = driver.get_log('browser')
            else:
                return "Error: Driver does not support console logs."
                
            if not logs:
                return "No console logs."
            
            # Filter severe errors
            errors = [l for l in logs if l['level'] == 'SEVERE']
            output = [f"Found {len(logs)} logs ({len(errors)} errors):"]
            for l in logs[-10:]: # Last 10
                output.append(f"[{l['level']}] {l['message']}")
            return "\n".join(output)
        except Exception as e:
            return f"Error getting logs: {e}"

    elif action == "handle_alert":
        cmd = payload.lower().strip() if payload else "accept"
        try:
            alert = driver.switch_to.alert
            text = alert.text
            if cmd == "accept":
                alert.accept()
                return f"✓ Accepted alert: {text}"
            elif cmd == "dismiss":
                alert.dismiss()
                return f"✓ Dismissed alert: {text}"
            else:
                return f"Error: Unknown alert action '{cmd}'"
        except Exception as e:
            return f"No alert found or error: {e}"

    elif action == "set_zoom":
        try:
            level = payload.strip()
            # Validate level (0.1 to 5.0)
            try:
                val = float(level)
                if not (0.1 <= val <= 5.0): raise ValueError
            except:
                return "Error: Zoom level must be between 0.1 and 5.0"
            
            driver.execute_script(f"document.body.style.zoom = '{level}';")
            return f"✓ Set zoom to {level}"
        except Exception as e:
            return f"Error setting zoom: {e}"

    elif action == "check_downloads":
        # Assuming downloads go to ~/Downloads or configured dir
        # We need to know where the browser downloads to.
        # For now, we'll check ~/Downloads
        try:
            import os
            dl_dir = os.path.expanduser("~/Downloads")
            if not os.path.exists(dl_dir):
                return "Error: Downloads directory not found."
            
            files = sorted(os.listdir(dl_dir), key=lambda x: os.path.getmtime(os.path.join(dl_dir, x)), reverse=True)
            return f"Recent downloads:\n" + "\n".join(files[:5])
        except Exception as e:
            return f"Error checking downloads: {e}"

    # ========================================================================
    # MODERN INTERACTIONS
    # ========================================================================

    elif action == "scroll_element":
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

    elif action == "switch_frame":
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

    elif action == "switch_default_content":
        try:
            driver.switch_to.default_content()
            return "✓ Switched to default content (main page)"
        except Exception as e:
            return f"Error: {e}"

    elif action == "media_control":
        if '|' not in payload:
            return "Error: Format is 'selector|action'. Action: play, pause, mute, unmute, seek <sec>."
        
        parts = payload.split('|', 1)
        sel = parts[0].strip()
        cmd_part = parts[1].strip().lower()
        
        try:
            selector, _, _ = resolve_som_index(sel)
            element = find_element_with_context(driver, selector)
            
            if cmd_part == "play": driver.execute_script("arguments[0].play();", element)
            elif cmd_part == "pause": driver.execute_script("arguments[0].pause();", element)
            elif cmd_part == "mute": driver.execute_script("arguments[0].muted = true;", element)
            elif cmd_part == "unmute": driver.execute_script("arguments[0].muted = false;", element)
            elif cmd_part.startswith("seek "):
                sec = float(cmd_part.split(' ')[1])
                driver.execute_script(f"arguments[0].currentTime = {sec};", element)
            else: return f"Error: Unknown media command '{cmd_part}'"
            
            return f"✓ Media control '{cmd_part}' executed on {sel}"
        except Exception as e:
            return f"Error media control: {e}"

    elif action == "fill_form":
        import json
        try:
            data = json.loads(payload)
            results = []
            success_count = 0
            
            for sel, val in data.items():
                try:
                    # Determine action based on element type or value
                    # We'll use a heuristic: try to find element and check type
                    # But perform_action calls find_element internally.
                    # We can recursively call perform_action!
                    
                    # Heuristic:
                    # If val is 'check'/'uncheck' -> checkbox
                    # If val is 'true'/'false' -> checkbox
                    # If val is in ['play', 'pause'] -> media? No, unlikely in form.
                    
                    # Better: Find element first to check type
                    real_sel, _, _ = resolve_som_index(sel)
                    elem = find_element_with_context(driver, real_sel)
                    tag = elem.tag_name.lower()
                    type_attr = elem.get_attribute('type')
                    
                    res = ""
                    if tag == 'select':
                        res = perform_action("select", f"{sel}|{val}")
                    elif type_attr in ['checkbox']:
                        res = perform_action("checkbox", f"{sel}|{val}")
                    elif type_attr in ['radio']:
                        # Radio usually needs clicking the specific value
                        # If val is 'click' or empty, just click.
                        res = perform_action("radio", sel)
                    else:
                        # Default to type
                        # Handle contenteditable? perform_action("type") should handle it (we'll update it)
                        res = perform_action("type", f"{sel}|{val}")
                    
                    if "Error" in res or "✗" in res:
                        results.append(f"Failed {sel}: {res}")
                    else:
                        success_count += 1
                        
                except Exception as e:
                    results.append(f"Error {sel}: {e}")
            
            summary = f"Filled {success_count}/{len(data)} fields."
            if results:
                summary += " Issues: " + "; ".join(results)
            return summary
            
        except json.JSONDecodeError:
            return "Error: Payload must be valid JSON string."
        except Exception as e:
            return f"Error filling form: {e}"

    # ========================================================================
    # SEARCH & FIND
    # ========================================================================

    elif action == "find_on_page":
        if not payload or '|' not in payload:
            return "Error: Format is 'type|query'. Types: text, link, button, input, any."
        
        parts = payload.split('|', 1)
        search_type = parts[0].strip().lower()
        query = parts[1].strip().lower()
        
        if not query:
            return "Error: Query cannot be empty."

        try:
            # JavaScript to find, filter, and rank elements
            results = driver.execute_script("""
                const type = arguments[0];
                const query = arguments[1];
                const results = [];
                
                function isVisible(elem) {
                    if (!elem) return false;
                    const style = window.getComputedStyle(elem);
                    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                    const rect = elem.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }
                
                function getSoMID(elem) {
                    return elem.getAttribute('data-som-id') || null;
                }
                
                const allElems = document.querySelectorAll('*');
                
                for (let elem of allElems) {
                    if (!isVisible(elem)) continue;
                    
                    let match = false;
                    let text = elem.innerText || elem.textContent || "";
                    text = text.trim().replace(/\\s+/g, ' ');
                    const textLower = text.toLowerCase();
                    
                    // Filter by type
                    if (type === 'link' && elem.tagName !== 'A') continue;
                    if (type === 'button' && elem.tagName !== 'BUTTON' && elem.getAttribute('role') !== 'button') continue;
                    if (type === 'input' && elem.tagName !== 'INPUT' && elem.tagName !== 'TEXTAREA') continue;
                    if (type === 'text' && (elem.tagName === 'SCRIPT' || elem.tagName === 'STYLE' || elem.children.length > 0)) continue; // Leaf nodes for text
                    
                    // Match query
                    if (textLower.includes(query)) {
                        match = true;
                    } else if (type === 'input' || type === 'any') {
                        const placeholder = elem.getAttribute('placeholder') || "";
                        if (placeholder.toLowerCase().includes(query)) match = true;
                        const value = elem.value || "";
                        if (value.toLowerCase().includes(query)) match = true;
                    }
                    
                    if (match) {
                        // Scoring
                        let score = 0;
                        if (textLower === query) score += 100; // Exact match
                        else if (textLower.startsWith(query)) score += 50; // Starts with
                        else score += 10; // Contains
                        
                        if (type === 'text') {
                            // Prefer longer context for text (up to a limit)
                            score += Math.min(text.length, 200) / 10;
                        }
                        
                        results.push({
                            id: getSoMID(elem),
                            tag: elem.tagName,
                            text: text.substring(0, 100) + (text.length > 100 ? "..." : ""),
                            score: score
                        });
                    }
                }
                
                // Sort by score desc
                results.sort((a, b) => b.score - a.score);
                return results.slice(0, 20);
            """, search_type, query)
            
            if not results:
                return f"No results found for '{query}' (type: {search_type})."
            
            output = [f"Found {len(results)} matches for '{query}':"]
            for res in results:
                som_id = f"[{res['id']}]" if res['id'] else "[No ID]"
                output.append(f"- {som_id} {res['tag']}: \"{res['text']}\"")
                
            return "\n".join(output)
            
        except Exception as e:
            return f"Error finding on page: {e}"

    elif action == "radio":
        try:
            selector, _, _ = resolve_som_index(payload.strip())
        except ValueError as e:
            return f"Error: {e}"
        
        try:
            element = find_element_with_context(driver, selector)
            
            if element.get_attribute('type') != 'radio':
                return f"Error: Not a radio button"
            
            if not element.is_selected():
                element.click()
                value = element.get_attribute('value') or 'unknown'
                return f"✓ Selected radio (value: {value})"
            return "Radio already selected"
        except Exception as e:
            return f"Error: {e}"

    elif action == "slider":
        if '|' not in payload:
            return "Error: Format is 'selector|value'"
        
        sel, value = payload.split('|', 1)
        
        try:
            selector, _, _ = resolve_som_index(sel.strip())
        except ValueError as e:
            return f"Error: {e}"
        
        try:
            element = find_element_with_context(driver, selector)
            
            if element.get_attribute('type') != 'range':
                return f"Error: Not a range slider"
            
            driver.execute_script(
                f"arguments[0].value = '{value.strip()}'; "
                "arguments[0].dispatchEvent(new Event('input')); "
                "arguments[0].dispatchEvent(new Event('change'));",
                element
            )
            return f"✓ Set slider to {value.strip()}"
        except Exception as e:
            return f"Error: {e}"

    elif action == "datepicker":
        if '|' not in payload:
            return "Error: Format is 'selector|YYYY-MM-DD'"
        
        sel, date_value = payload.split('|', 1)
        
        try:
            selector, _, _ = resolve_som_index(sel.strip())
        except ValueError as e:
            return f"Error: {e}"
        
        try:
            element = find_element_with_context(driver, selector)
            elem_type = element.get_attribute('type')
            
            if elem_type not in ['date', 'datetime-local', 'time', 'month', 'week']:
                return f"Error: Not a date/time input"
            
            element.clear()
            driver.execute_script(
                f"arguments[0].value = '{date_value.strip()}'; "
                "arguments[0].dispatchEvent(new Event('input')); "
                "arguments[0].dispatchEvent(new Event('change'));",
                element
            )
            return f"✓ Set {elem_type} to {date_value.strip()}"
        except Exception as e:
            return f"Error: {e}"

    elif action == "colorpicker":
        if '|' not in payload:
            return "Error: Format is 'selector|#RRGGBB'"
        
        sel, color = payload.split('|', 1)
        
        try:
            selector, _, _ = resolve_som_index(sel.strip())
        except ValueError as e:
            return f"Error: {e}"
        
        try:
            element = find_element_with_context(driver, selector)
            
            if element.get_attribute('type') != 'color':
                return f"Error: Not a color picker"
            
            driver.execute_script(
                f"arguments[0].value = '{color.strip()}'; "
                "arguments[0].dispatchEvent(new Event('input')); "
                "arguments[0].dispatchEvent(new Event('change'));",
                element
            )
            return f"✓ Set color to {color.strip()}"
        except Exception as e:
            return f"Error: {e}"

    elif action == "get_value":
        try:
            selector, _, _ = resolve_som_index(payload.strip())
        except ValueError as e:
            return f"Error: {e}"
        
        try:
            element = find_element_with_context(driver, selector)
            tag = element.tag_name.lower()
            elem_type = element.get_attribute('type')
            
            if tag == 'input':
                if elem_type == 'checkbox':
                    value = "checked" if element.is_selected() else "unchecked"
                elif elem_type == 'radio':
                    value = f"selected: {element.get_attribute('value')}" if element.is_selected() else "not selected"
                else:
                    value = element.get_attribute('value') or ''
            elif tag == 'select':
                select = Select(element)
                value = select.first_selected_option.text
            elif tag == 'textarea':
                value = element.get_attribute('value') or element.text
            else:
                value = element.text or element.get_attribute('value') or element.get_attribute('textContent') or ''
            
            return f"Value: {value}"
        except Exception as e:
            return f"Error: {e}"

    elif action == "submit":
        try:
            selector, _, _ = resolve_som_index(payload.strip())
        except ValueError as e:
            return f"Error: {e}"
        
        try:
            element = find_element_with_context(driver, selector)
            
            if element.tag_name.lower() == 'form':
                form = element
            else:
                form = driver.execute_script("return arguments[0].closest('form');", element)
                if not form:
                    return "Error: No form found"
            
            form.submit()
            time.sleep(1)
            return "✓ Submitted form"
        except Exception as e:
            return f"Error: {e}"

    elif action == "drag_and_drop":
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

    # ========================================================================
    # FILE OPERATIONS
    # ========================================================================
    
    elif action == "upload_file":
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

    elif action == "check_downloads":
        try:
            download_dir = get_workspace_path()
            files = sorted(
                os.listdir(download_dir),
                key=lambda x: os.path.getmtime(os.path.join(download_dir, x)),
                reverse=True
            )
            
            if not files:
                return "No files in download directory."
            
            result = "Downloads:\n"
            for f in files[:10]:
                path = os.path.join(download_dir, f)
                size = os.path.getsize(path)
                result += f"- {f} ({size} bytes)\n"
            return result
        except Exception as e:
            return f"Error checking downloads: {e}"

    # ========================================================================
    # KEYBOARD OPERATIONS
    # ========================================================================
    
    elif action == "press_key":
        if not payload:
            return "Error: Key required (e.g., 'enter', 'ctrl+t')"
        
        payload_lower = payload.lower()
        
        # Special browser commands
        if payload_lower == "ctrl+t":
            driver.execute_script("window.open('', '_blank');")
            time.sleep(0.5)
            driver.switch_to.window(driver.window_handles[-1])
            return "Opened new tab"
        
        elif payload_lower == "ctrl+w":
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                return "Closed tab"
            return "Cannot close only tab"
        
        elif payload_lower in ["ctrl+r", "f5"]:
            driver.refresh()
            time.sleep(1)
            return "Refreshed page"
        
        elif payload_lower in ["backspace", "alt+left"]:
            driver.back()
            time.sleep(1)
            return "Navigated back"
        
        elif payload_lower == "alt+right":
            driver.forward()
            time.sleep(1)
            return "Navigated forward"
        
        elif payload_lower == "escape":
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            return "Pressed Escape"
        
        # Standard key mapping
        key_map = {
            "space": Keys.SPACE,
            "enter": Keys.ENTER,
            "return": Keys.RETURN,
            "tab": Keys.TAB,
            "backspace": Keys.BACKSPACE,
            "delete": Keys.DELETE,
            "left": Keys.LEFT,
            "right": Keys.RIGHT,
            "up": Keys.UP,
            "down": Keys.DOWN,
            "page_up": Keys.PAGE_UP,
            "page_down": Keys.PAGE_DOWN,
            "home": Keys.HOME,
            "end": Keys.END,
        }
        
        if payload_lower in key_map:
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(key_map[payload_lower])
                return f"Pressed {payload}"
            except Exception as e:
                return f"Error: {e}"
        
        return f"Unknown key: {payload}"

    elif action == "quick_find":
        if not payload:
            return "Error: Text required"
        
        # Handle "text|true" for links_only
        links_only = False
        text = payload
        if "|" in payload:
            parts = payload.split("|")
            text = parts[0]
            if len(parts) > 1 and parts[1].strip().lower() == "true":
                links_only = True
        
        try:
            trigger_key = "'" if links_only else "/"
            actions = webdriver.ActionChains(driver)
            actions.send_keys(trigger_key).perform()
            time.sleep(0.2)
            actions.send_keys(text).perform()
            
            mode_str = "Links" if links_only else "Text"
            return f"Quick Find ({mode_str}): '{text}'"
        except Exception as e:
            return f"Error: {e}"

    # No action matched
    return None
