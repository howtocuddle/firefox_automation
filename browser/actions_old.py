"""
Browser Actions
Handles interaction with page elements: click, type, scroll, etc.
"""
import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from ...safety import get_workspace_path
from .core import get_driver
from . import core # Import module to access mutable globals like _element_map
from .helpers import human_click, human_type

from selenium import webdriver

def remove_overlays(driver):
    """Injects JS to remove annoyance overlays."""
    try:
        js_path = os.path.join(os.path.dirname(__file__), "js", "overlays.js")
        if os.path.exists(js_path):
            with open(js_path, "r") as f:
                js = f.read()
            driver.execute_script(js)
            # print("[DEBUG] Overlay script executed.")
        else:
            print(f"[Browser] Warning: Overlay script not found at {js_path}")
    except Exception as e:
        print(f"[Browser] Warning: Failed to remove overlays: {e}")

def find_element_with_context(driver, selector):
    """
    Finds an element handling context switching (iframes, shadow roots).
    Selector format: "iframe_selector >> shadow-root >> element_selector"
    """
    parts = [p.strip() for p in selector.split('>>')]
    current_context = driver
    
    for i, part in enumerate(parts):
        is_last = (i == len(parts) - 1)
        
        if part == "shadow-root":
            # Switch to shadow root of the PREVIOUS element
            # Note: Selenium doesn't "switch" to shadow root like a frame.
            # We must have the host element from the previous step.
            # But our loop structure means 'current_context' is the element from previous step.
            if isinstance(current_context, webdriver.remote.webelement.WebElement):
                current_context = current_context.shadow_root
            else:
                raise Exception("Cannot switch to shadow-root: previous context is not an element")
            continue

        # Find element in current context
        element = None
        
        # 1. Try CSS
        try:
            element = current_context.find_element(By.CSS_SELECTOR, part)
        except:
            pass
        
        # 2. Try XPath (only if context is driver or element, not shadow root)
        # ShadowRoot in Selenium 4+ supports find_element(By.CSS_SELECTOR) but NOT XPath usually
        if not element and not isinstance(current_context, webdriver.remote.shadowroot.ShadowRoot):
            try:
                element = current_context.find_element(By.XPATH, part)
            except:
                pass
        
        # 3. Try Text/Attributes (Heuristic)
        if not element and is_last:
             # Only apply heuristics for the final target
             # (Same heuristics as perform_action)
             try:
                 xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{part.lower()}')]"
                 if not isinstance(current_context, webdriver.remote.shadowroot.ShadowRoot):
                     element = current_context.find_element(By.XPATH, xpath)
             except:
                 pass

        if not element:
            raise Exception(f"Could not find element: {part} in context {type(current_context)}")
        
        if not is_last:
            # If this is an iframe, switch to it
            if element.tag_name.lower() == 'iframe' or element.tag_name.lower() == 'frame':
                driver.switch_to.frame(element)
                current_context = driver # Reset context to driver (now inside frame)
            else:
                # It's a shadow host or just a container
                current_context = element
        else:
            return element

    return current_context

def perform_action(action: str, payload: str = None) -> str:
    driver = get_driver()
    if not driver:
        return "Error: Browser not open."

    # Auto-remove overlays before any action
    remove_overlays(driver)
    
    # Always switch to default content first to ensure we start from top
    driver.switch_to.default_content()

    if action == "find_element":
        if not payload: return "Error: Text to find required."
        
        # JS to find element by text content
        script = f"""
        var text = "{payload.lower()}";
        var elements = document.querySelectorAll('a, button, input, textarea, [role="button"]');
        var found = [];
        
        for (var i=0; i<elements.length; i++) {{
            var el = elements[i];
            var elText = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('alt') || '').toLowerCase();
            
            if (elText.includes(text) && el.offsetParent !== null) {{
                // Generate a unique selector
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

    elif action == "click":
        if not payload: return "Error: Element to click required."
        
        expected_text = None
        element_info = None
        use_coordinate_click = False
        
        # Resolve numeric index
        if payload.isdigit():
            index = int(payload)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                element_info = core._element_map[index]
                expected_text = element_info.get('text', '').strip()
                use_coordinate_click = True  # Use coordinates for SoM clicks
                print(f"[Browser] Click target {index}: {element_info.get('tag')} at center ({element_info.get('center', {}).get('x')}, {element_info.get('center', {}).get('y')}) - '{expected_text[:30]}'")
            else:
                return f"Error: Index {index} not found in element map."

        try:
            el = None
            
            # For SoM number clicks, use coordinates to find the EXACT element
            if use_coordinate_click and element_info:
                center = element_info.get('center', {})
                viewport_coords = element_info.get('viewportCoords', {})
                
                if center.get('x') and center.get('y'):
                    # Use JavaScript to find element at exact coordinates
                    # We use viewport coordinates (relative to current view) for elementFromPoint
                    center_x = viewport_coords.get('centerX', center.get('x'))
                    center_y = viewport_coords.get('centerY', center.get('y'))
                    
                    find_script = f"""
                    var el = document.elementFromPoint({center_x}, {center_y});
                    if (!el) return null;
                    
                    // Store reference for Python
                    window._agentClickTarget = el;
                    
                    return {{
                        tag: el.tagName,
                        text: (el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || '').substring(0, 100),
                        rect: el.getBoundingClientRect()
                    }};
                    """
                    
                    found_info = driver.execute_script(find_script)
                    
                    if found_info:
                        # Verify this is the correct element by checking text
                        found_text = found_info.get('text', '').strip()
                        
                        # Get the element from stored reference
                        el = driver.execute_script("return window._agentClickTarget;")
                        
                        if expected_text and found_text:
                            t1 = expected_text.lower()[:30]
                            t2 = found_text.lower()[:30]
                            
                            # Check if texts match (partial match allowed)
                            if t1 not in t2 and t2 not in t1:
                                print(f"[Browser] DOM Mismatch at coordinates ({center_x}, {center_y})")
                                print(f"[Browser]   Expected: '{expected_text[:50]}'")
                                print(f"[Browser]   Found: '{found_text[:50]}'")
                                return f"Error: DOM Mismatch. Element {index} at ({center_x},{center_y}) has changed. Expected '{expected_text[:30]}', found '{found_text[:30]}'. Please SNAP again."
                        
                        print(f"[Browser] Found element at coordinates: {found_info.get('tag')} - '{found_text[:40]}'")
                    else:
                        print(f"[Browser] No element found at coordinates ({center_x}, {center_y}), falling back to selector")
                        use_coordinate_click = False
            
            # Fallback: use selector-based finding (for non-SoM clicks or if coordinate click failed)
            if not el:
                selector = element_info['selector'] if element_info else payload
                el = find_element_with_context(driver, selector)
                
                # Verify text match if we have an expectation
                if expected_text:
                    current_text = (el.text or el.get_attribute('value') or el.get_attribute('aria-label') or '').strip()
                    if expected_text and current_text:
                        t1 = expected_text.lower()[:20]
                        t2 = current_text.lower()[:20]
                        if t1 not in t2 and t2 not in t1:
                            print(f"[Browser] Warning: DOM Mismatch for click. Expected '{expected_text}', found '{current_text}'")
                            return f"Error: DOM Mismatch. Element text changed from '{expected_text}' to '{current_text}'. Please SNAP again."

            # Human-like click
            if human_click(el):
                method = "coordinate-based" if use_coordinate_click else "selector-based"
                return f"Clicked {payload} ({method})"
            else:
                return f"Failed to click {payload} (human_click failed)"
                
        except Exception as e:
            return f"Error clicking {payload}: {e}"

    elif action == "hover":
        if not payload: return "Error: Element to hover required."
        
        if payload.isdigit():
            index = int(payload)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                element_info = core._element_map[index]
                payload = element_info['selector']

        try:
            el = find_element_with_context(driver, payload)
            
            action_chains = webdriver.ActionChains(driver)
            action_chains.move_to_element(el).perform()
            return f"Hovered over {payload}"
        except Exception as e:
            return f"Error hovering {payload}: {e}"

    elif action == "focus":
        if not payload: return "Error: Element to focus required."
        
        if payload.isdigit():
            index = int(payload)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                element_info = core._element_map[index]
                payload = element_info['selector']

        try:
            el = find_element_with_context(driver, payload)
            driver.execute_script("arguments[0].focus();", el)
            return f"Focused {payload}"
        except Exception as e:
            return f"Error focusing {payload}: {e}"

    elif action == "scroll":
        # Page-based scrolling system
        # payload can be: "page 1", "page 2", "next", "prev", "up", "down", "top", "bottom"
        if not payload: 
            payload = "next"  # Default to next page
        
        payload_lower = payload.lower().strip()
        
        try:
            # Get page dimensions
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
            
            # Calculate total pages (viewport-sized chunks)
            # We use 90% of viewport height per page to ensure some overlap
            page_height = int(viewport_height * 0.9)
            total_pages = max(1, (scroll_height - viewport_height) // page_height + 1)
            current_page = max(1, scroll_top // page_height + 1)
            
            new_scroll_top = scroll_top
            
            # Handle different scroll commands
            if payload_lower in ["up", "prev", "previous"]:
                # Go to previous page
                target_page = max(1, current_page - 1)
                new_scroll_top = (target_page - 1) * page_height
                msg = f"Scrolled to page {target_page} of {total_pages}"
                
            elif payload_lower in ["down", "next"]:
                # Go to next page
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
                # Direct page navigation: "page 3"
                try:
                    target_page = int(payload_lower.split()[1])
                    if target_page < 1:
                        target_page = 1
                    elif target_page > total_pages:
                        target_page = total_pages
                    
                    new_scroll_top = (target_page - 1) * page_height
                    msg = f"Scrolled to page {target_page} of {total_pages}"
                except (IndexError, ValueError):
                    return f"Error: Invalid page number format. Use 'page N' where N is a number."
                    
            elif payload_lower.isdigit():
                # Also accept just the number: "3" means page 3
                target_page = int(payload_lower)
                if target_page < 1:
                    target_page = 1
                elif target_page > total_pages:
                    target_page = total_pages
                
                new_scroll_top = (target_page - 1) * page_height
                msg = f"Scrolled to page {target_page} of {total_pages}"
            else:
                # Try scrolling to element (if payload is selector or index)
                if payload.isdigit():
                    index = int(payload)
                    if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                        payload = core._element_map[index]['selector']
                
                el = find_element_with_context(driver, payload)
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el)
                time.sleep(0.5)
                
                # Recalculate page after scroll
                new_scroll = driver.execute_script("return window.scrollY;")
                new_page = max(1, new_scroll // page_height + 1)
                return f"Scrolled to element {payload} (now on page {new_page} of {total_pages})"
            
            # Perform the scroll
            driver.execute_script(f"window.scrollTo({{top: {new_scroll_top}, behavior: 'smooth'}});")
            time.sleep(0.5)
            
            # Check if we actually scrolled
            actual_scroll = driver.execute_script("return window.scrollY;")
            if abs(actual_scroll - scroll_top) < 10 and payload_lower in ["down", "next"]:
                msg += " (Already at end of page)"
            
            return msg
            
        except Exception as e:
            return f"Error scrolling: {e}"

    elif action == "right_click":
        if not payload: return "Error: Selector or index required."
        
        # Resolve numeric index
        if payload.isdigit():
            index = int(payload)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                payload = core._element_map[index]['selector']
        
        try:
            el = find_element_with_context(driver, payload)
            # Scroll to element
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el)
            time.sleep(0.5)
            
            # Right click
            actions = webdriver.ActionChains(driver)
            actions.context_click(el).perform()
            time.sleep(1.0) # Wait for menu
            return f"Right-clicked {payload}"
        except Exception as e:
            return f"Error right-clicking: {e}"

            try:
                el = driver.find_element(By.LINK_TEXT, payload)
            except:
                pass
                
        # 3. Try Partial Link Text
        if not el:
            try:
                el = driver.find_element(By.PARTIAL_LINK_TEXT, payload)
            except:
                pass
        
        # 4. Try XPath for text content
        if not el:
            try:
                xpath = f"//*[contains(text(), '{payload}')]"
                el = driver.find_element(By.XPATH, xpath)
            except:
                pass

        if not el:
             return f"Error: Could not find element to focus: {payload}"

        # LEARN: If we found the element via fallback, generate and save robust XPath
        if not cached_xpath:
            try:
                from .xpath_journal import extract_element_name, generate_robust_xpath, save_xpath
                new_xpath = generate_robust_xpath(el, driver)
                if new_xpath:
                    # Try to get a semantic name (e.g. "Login") instead of just the selector
                    # If payload was a number or selector, we prefer the extracted name
                    semantic_name = extract_element_name(el)
                    
                    # If the payload looks like a name (not a selector/number), use it. 
                    # Otherwise prefer the extracted semantic name.
                    save_key = payload
                    if not payload.isalpha() or len(payload) > 20: # Heuristic: payload is likely a selector or number
                         save_key = semantic_name or payload
                    
                    if save_key:
                        save_xpath(driver.current_url, save_key, new_xpath)
            except Exception as e:
                print(f"[Browser] Failed to learn XPath: {e}")

        try:
            # Scroll and Focus
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el)
            time.sleep(0.2)
            driver.execute_script("arguments[0].focus();", el)
            
            result_msg = f"Focused {payload}"
            
            if chained_action == "ENTER":
                time.sleep(0.2)
                el.send_keys(Keys.ENTER)
                result_msg += " and pressed ENTER"
            elif chained_action == "CLICK":
                time.sleep(0.2)
                el.click()
                result_msg += " and CLICKED"
            elif chained_action == "RIGHT_CLICK":
                time.sleep(0.2)
                actions = webdriver.ActionChains(driver)
                actions.context_click(el).perform()
                result_msg += " and RIGHT CLICKED"
            
            return result_msg
        except Exception as e:
            return f"Error focusing: {e}"

    elif action == "type":
        if '|' not in payload: return "Error: 'selector|text'"
        
        # Check for optional ENTER flag
        parts = payload.split('|')
        if len(parts) == 3 and parts[2].strip().upper() == "ENTER":
            sel, text, _ = parts
            press_enter = True
        else:
            sel, text = parts[0], parts[1]
            press_enter = False
            
        sel = sel.strip()
        
        # 0. Check XPath Journal first
        from .xpath_journal import get_xpath, save_xpath, generate_robust_xpath, extract_element_name
        cached_xpath = get_xpath(driver.current_url, sel)
        if cached_xpath:
            try:
                print(f"[Browser] Using cached XPath for '{sel}': {cached_xpath}")
                el = driver.find_element(By.XPATH, cached_xpath)
                if human_type(el, text):
                    if press_enter:
                        time.sleep(0.5)
                        el.send_keys(Keys.ENTER)
                        return f"✓ Typed '{text}' into {sel} (via cached XPath)"
                    return f"✓ Typed '{text}' into {sel} (via cached XPath)"
            except Exception as e:
                print(f"[Browser] Cached XPath failed: {e}")
                # Fall through to normal search logic

        # Resolve numeric index to selector if possible
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                element_info = core._element_map[index]
                print(f"[Browser] Type target found in map: {index} -> {element_info.get('tag')} ({element_info.get('selector')})")
                sel = element_info['selector']
            else:
                return f"Error: Index {index} not found in element map."

        try:
            el = None
            
            # Use new context-aware finder
            try:
                el = find_element_with_context(driver, sel)
            except Exception as e:
                # print(f"Context find failed: {e}")
                pass

            # Fallback to old heuristics if simple selector and context find failed
            if not el and ">>" not in sel:
                # 1. Try finding input/textarea by attributes (id, name, placeholder, aria-label)
                # CRITICAL: Exclude submit/button/hidden/image inputs to avoid typing into buttons (like Google's btnK)
                try:
                    # Case-insensitive partial match for placeholder/aria-label often helps
                    # We strictly filter out non-text types
                    xpath = f"//input[(not(@type) or @type='text' or @type='search' or @type='email' or @type='password' or @type='url' or @type='tel' or @type='number') and (contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}') or contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}') or contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}') or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}'))]"
                    el = driver.find_element(By.XPATH, xpath)
                except:
                    pass
            
                # 2. Try textarea if input failed
                if not el:
                    try:
                        xpath = f"//textarea[contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}') or contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}') or contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}') or contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}')]"
                        el = driver.find_element(By.XPATH, xpath)
                    except:
                        pass
                
                # 3. Try contenteditable elements (divs, spans)
                if not el:
                     try:
                        xpath = f"//*[@contenteditable='true' and (contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel.lower()}'))]"
                        el = driver.find_element(By.XPATH, xpath)
                     except:
                        pass
            
            # 4. Last resort: If selector is "search" or "q", try generic search box
            if not el and sel.lower() in ["search", "q", "query"]:
                try:
                    el = driver.find_element(By.NAME, "q")
                except:
                    pass

            if not el:
                return f"✗ Error: Could not find element '{sel}' to type into. Tried CSS, ID, Name, Placeholder, Aria-Label."

            # LEARN: If we found the element via fallback, generate and save robust XPath
            if not cached_xpath:
                try:
                    new_xpath = generate_robust_xpath(el, driver)
                    if new_xpath:
                        # Try to get a semantic name (e.g. "Search") instead of just the selector
                        semantic_name = extract_element_name(el)
                        
                        # If the selector looks like a name (not a CSS selector), use it.
                        # Otherwise prefer the extracted semantic name.
                        save_key = sel
                        if not sel.isalpha() or len(sel) > 20: # Heuristic
                            save_key = semantic_name or sel
                        
                        if save_key:
                            save_xpath(driver.current_url, save_key, new_xpath)
                except Exception as e:
                    print(f"[Browser] Failed to learn XPath: {e}")
            if human_type(el, text):
                # Press Enter if requested
                if press_enter:
                    time.sleep(0.5)
                    el.send_keys(Keys.ENTER)
                    return f"✓ Typed '{text}' and pressed ENTER into {sel}"
                
                # Verify the value was set
                final_value = el.get_attribute('value') or el.text or ''
                return f"✓ Successfully typed '{text}' into {sel}. Current value: '{final_value}'"
            else:
                return f"✗ Error: Failed to type into {sel}"
        except Exception as e:
            return f"✗ Error finding element '{sel}' to type: {e}"

    elif action == "fill_form":
        try:
            import json
            form_data = json.loads(payload)
            results = []
            for selector, value in form_data.items():
                # Reuse type logic for each field
                res = perform_action("type", f"{selector}|{value}")
                results.append(f"{selector}: {res}")
            return "\\n".join(results)
        except Exception as e:
            return f"Error filling form: {e}"

    elif action == "form_fill":
        if '|' not in payload: return "Error: 'selector|text'"
        sel, text = payload.split('|', 1)
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel.strip())
            # Ensure element is visible and clear it
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el)
            time.sleep(0.5)
            el.clear()
            
            if human_type(el, text):
                return f"Filled form field {sel} with '{text}'"
            else:
                return f"Error filling form field {sel}"
        except Exception as e:
            return f"Error filling form: {e}"

    elif action == "upload_file":
        if '|' not in payload: return "Error: 'selector|filepath'"
        sel, filepath = payload.split('|', 1)
        filepath = filepath.strip()
        
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
            
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel.strip())
            el.send_keys(filepath)
            return f"Uploaded {filepath} to {sel}"
        except Exception as e:
            return f"Error uploading file: {e}"

    elif action == "check_downloads":
        # List files in download directory
        download_dir = get_workspace_path()
        try:
            files = sorted(os.listdir(download_dir), key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
            if not files:
                return "No files in download directory."
            
            result = "Downloads:\n"
            for f in files[:10]: # Top 10 recent
                path = os.path.join(download_dir, f)
                size = os.path.getsize(path)
                result += f"- {f} ({size} bytes)\n"
            return result
        except Exception as e:
            return f"Error checking downloads: {e}"





    elif action == "press_key":
        if not payload: return "Error: Key name required (e.g., 'space', 'enter', 'ctrl+t', 'f5')."
        
        payload_lower = payload.lower()
        
        # Special browser commands that need direct execution
        # These don't work well with normal key sending, so we use JS/driver methods
        if payload_lower == "ctrl+t":
            # Open new tab
            try:
                driver.execute_script("window.open('', '_blank');")
                time.sleep(0.5)
                driver.switch_to.window(driver.window_handles[-1])
                return "Opened new tab and switched to it"
            except Exception as e:
                return f"Error opening new tab: {e}"
        
        elif payload_lower == "ctrl+w":
            # Close current tab
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    return "Closed current tab"
                else:
                    return "Cannot close the only tab"
            except Exception as e:
                return f"Error closing tab: {e}"
        
        elif payload_lower in ["ctrl+r", "f5"]:
            # Refresh page
            try:
                driver.refresh()
                time.sleep(1)
                return "Refreshed page"
            except Exception as e:
                return f"Error refreshing: {e}"
        
        elif payload_lower in ["ctrl+shift+r", "ctrl+f5", "shift+f5"]:
            # Hard refresh (clear cache)
            try:
                driver.execute_script("location.reload(true);")
                time.sleep(1)
                return "Hard refreshed page (cleared cache)"
            except Exception as e:
                return f"Error hard refreshing: {e}"
        
        elif payload_lower in ["backspace", "alt+left"]:
            # Go back
            try:
                driver.back()
                time.sleep(1)
                return "Navigated back"
            except Exception as e:
                return f"Error going back: {e}"
        
        elif payload_lower == "alt+right":
            # Go forward
            try:
                driver.forward()
                time.sleep(1)
                return "Navigated forward"
            except Exception as e:
                return f"Error going forward: {e}"
        
        elif payload_lower == "ctrl+l":
            # Focus address bar
            try:
                driver.execute_script("window.location.href = window.location.href;")
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.CONTROL + "l")
                return "Focused address bar"
            except Exception as e:
                return f"Error focusing address bar: {e}"
        
        elif payload_lower == "ctrl+plus" or payload_lower == "ctrl+=":
            # Zoom in
            try:
                driver.execute_script("document.body.style.zoom = (parseFloat(document.body.style.zoom || 1) + 0.1);")
                return "Zoomed in"
            except Exception as e:
                return f"Error zooming in: {e}"
        
        elif payload_lower == "ctrl+minus" or payload_lower == "ctrl+-":
            # Zoom out
            try:
                driver.execute_script("document.body.style.zoom = (parseFloat(document.body.style.zoom || 1) - 0.1);")
                return "Zoomed out"
            except Exception as e:
                return f"Error zooming out: {e}"
        
        elif payload_lower == "ctrl+0":
            # Reset zoom
            try:
                driver.execute_script("document.body.style.zoom = 1;")
                return "Reset zoom to 100%"
            except Exception as e:
                return f"Error resetting zoom: {e}"
        
        elif payload_lower == "f11":
            # Fullscreen toggle
            try:
                driver.fullscreen_window()
                return "Toggled fullscreen"
            except Exception as e:
                return f"Error toggling fullscreen: {e}"
        
        elif payload_lower == "ctrl+shift+t":
            # Reopen last closed tab (not really possible in Selenium, simulate with message)
            return "Ctrl+Shift+T (reopen closed tab) - Note: Not supported in automation. Recommend opening URL directly."
        
        elif payload_lower == "ctrl+tab":
            # Switch to next tab
            try:
                handles = driver.window_handles
                current = driver.current_window_handle
                current_idx = handles.index(current)
                next_idx = (current_idx + 1) % len(handles)
                driver.switch_to.window(handles[next_idx])
                return f"Switched to next tab ({next_idx + 1}/{len(handles)})"
            except Exception as e:
                return f"Error switching tabs: {e}"
        
        elif payload_lower == "ctrl+shift+tab":
            # Switch to previous tab
            try:
                handles = driver.window_handles
                current = driver.current_window_handle
                current_idx = handles.index(current)
                prev_idx = (current_idx - 1) % len(handles)
                driver.switch_to.window(handles[prev_idx])
                return f"Switched to previous tab ({prev_idx + 1}/{len(handles)})"
            except Exception as e:
                return f"Error switching tabs: {e}"
        
        elif payload_lower == "ctrl+d":
            # Bookmark (not applicable in automation)
            return "Ctrl+D (bookmark) - Not applicable in automated browsing"
        
        elif payload_lower == "ctrl+f" or payload_lower == "f3":
            # Find in page - use browser's native find
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.CONTROL + "f")
                return "Opened find dialog (Ctrl+F)"
            except Exception as e:
                return f"Error opening find: {e}"
        
        elif payload_lower == "ctrl+g":
            # Find next
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.CONTROL + "g")
                return "Find next (Ctrl+G)"
            except Exception as e:
                return f"Error find next: {e}"
        
        elif payload_lower == "ctrl+h":
            # History (open history sidebar - not useful in automation)
            return "Ctrl+H (history) - Not useful in automated browsing"
        
        elif payload_lower == "ctrl+u":
            # View page source
            try:
                driver.execute_script("window.open('view-source:' + window.location.href, '_blank');")
                time.sleep(0.5)
                driver.switch_to.window(driver.window_handles[-1])
                return "Opened page source in new tab"
            except Exception as e:
                return f"Error viewing source: {e}"
        
        elif payload_lower == "ctrl+shift+i":
            # Developer tools (not controllable via Selenium)
            return "Ctrl+Shift+I (dev tools) - Cannot be controlled via automation"
        
        elif payload_lower == "ctrl+s":
            # Save page
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.CONTROL + "s")
                time.sleep(0.5)
                return "Triggered save page dialog (Ctrl+S)"
            except Exception as e:
                return f"Error saving page: {e}"
        
        elif payload_lower == "ctrl+p":
            # Print
            try:
                driver.execute_script("window.print();")
                time.sleep(0.5)
                return "Opened print dialog (Ctrl+P)"
            except Exception as e:
                return f"Error opening print dialog: {e}"
        
        elif payload_lower == "ctrl+shift+delete":
            # Clear browsing data (cannot automate)
            return "Ctrl+Shift+Delete (clear data) - Cannot be automated. Use driver.delete_all_cookies() instead."
        
        elif payload_lower == "escape":
            # Exit fullscreen or close dialogs
            try:
                body = driver.find_element(By.TAG_NAME, "body")
                body.send_keys(Keys.ESCAPE)
                return "Pressed Escape"
            except Exception as e:
                return f"Error pressing Escape: {e}"
        
        # Standard key mapping for other keys
        key_map = {
            "space": Keys.SPACE,
            "enter": Keys.ENTER,
            "return": Keys.RETURN,
            "tab": Keys.TAB,
            "escape": Keys.ESCAPE,
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
            "k": "k",
            "j": "j",
            "l": "l",
            "f": "f",
            "t": "t",
            "w": "w",
            "ctrl": Keys.CONTROL,
            "control": Keys.CONTROL,
            "alt": Keys.ALT,
            "shift": Keys.SHIFT,
            "cmd": Keys.COMMAND,
            "meta": Keys.META,
        }
        
        try:
            # Parse key combination
            keys_to_press = []
            parts = payload_lower.split('+')
            
            for part in parts:
                part = part.strip()
                if part in key_map:
                    keys_to_press.append(key_map[part])
                elif len(part) == 1:
                    keys_to_press.append(part)
                else:
                    return f"Error: Unknown key '{part}'"
            
            # Send keys to body element (more reliable than ActionChains for shortcuts)
            body = driver.find_element(By.TAG_NAME, "body")
            
            # Build chord string for send_keys
            if len(keys_to_press) == 1:
                # Single key
                body.send_keys(keys_to_press[0])
            else:
                # Key chord (e.g., Ctrl+K)
                chord_keys = keys_to_press[:-1]  # All modifier keys
                final_key = keys_to_press[-1]     # The letter/action key
                
                # Build chord
                chord = "".join(chord_keys) + final_key
                body.send_keys(chord)
            
            return f"Pressed keys: {payload}"
            
        except Exception as e:
            return f"Error pressing keys: {e}"


    elif action == "quick_find":
        if not payload: return "Error: Text to find required."
        
        # Check for links_only flag (format: "text|links_only")
        links_only = False
        text = payload
        if "|" in payload:
            parts = payload.split("|")
            text = parts[0]
            if len(parts) > 1 and parts[1].strip().lower() == "true":
                links_only = True
        
        try:
            # Firefox Quick Find shortcuts
            # / = Quick Find (text)
            # ' = Quick Find (links only)
            trigger_key = "'" if links_only else "/"
            
            actions = webdriver.ActionChains(driver)
            actions.send_keys(trigger_key).perform()
            time.sleep(0.2)
            actions.send_keys(text).perform()
            
            mode_str = "Links only" if links_only else "Text"
            return f"Quick Find ({mode_str}): Typed '{text}'. Check screenshot for highlights."
        except Exception as e:
            return f"Error performing Quick Find: {e}"

    elif action == "select":
        """Select from dropdown/select element. Format: 'selector|value' or 'index|value'"""
        if '|' not in payload:
            return "Error: Format is 'selector|option_text' or 'index|option_value'"
        
        sel, option = payload.split('|', 1)
        sel = sel.strip()
        option = option.strip()
        
        # Resolve numeric index
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                sel = core._element_map[index]['selector']
        
        try:
            from selenium.webdriver.support.ui import Select
            element = find_element_with_context(driver, sel)
            
            # Ensure it's a select element
            if element.tag_name.lower() != 'select':
                return f"Error: Element {sel} is not a <select> dropdown"
            
            select = Select(element)
            
            # Try different selection methods
            try:
                # Try by visible text first
                select.select_by_visible_text(option)
                return f"✓ Selected '{option}' from dropdown {sel}"
            except:
                try:
                    # Try by value
                    select.select_by_value(option)
                    return f"✓ Selected '{option}' (by value) from dropdown {sel}"
                except:
                    # Try by index if option is a number
                    if option.isdigit():
                        select.select_by_index(int(option))
                        return f"✓ Selected option {option} (by index) from dropdown {sel}"
                    else:
                        # List available options
                        options_text = [opt.text for opt in select.options]
                        return f"✗ Could not find option '{option}'. Available: {', '.join(options_text[:10])}"
        
        except Exception as e:
            return f"Error selecting from dropdown {sel}: {e}"
    
    elif action == "checkbox":
        """Toggle or set checkbox. Format: 'selector' (toggle) or 'selector|check' or 'selector|uncheck'"""
        parts = payload.split('|') if '|' in payload else [payload, 'toggle']
        sel = parts[0].strip()
        action_type = parts[1].strip().lower() if len(parts) > 1 else 'toggle'
        
        # Resolve numeric index
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                sel = core._element_map[index]['selector']
        
        try:
            element = find_element_with_context(driver, sel)
            
            if element.get_attribute('type') != 'checkbox':
                return f"Error: Element {sel} is not a checkbox"
            
            is_checked = element.is_selected()
            
            if action_type == 'toggle':
                element.click()
                new_state = "checked" if not is_checked else "unchecked"
                return f"✓ Toggled checkbox {sel} to {new_state}"
            elif action_type in ['check', 'true', 'on', '1']:
                if not is_checked:
                    element.click()
                    return f"✓ Checked checkbox {sel}"
                return f"Checkbox {sel} already checked"
            elif action_type in ['uncheck', 'false', 'off', '0']:
                if is_checked:
                    element.click()
                    return f"✓ Unchecked checkbox {sel}"
                return f"Checkbox {sel} already unchecked"
            else:
                return f"Error: Invalid action '{action_type}'. Use 'check', 'uncheck', or 'toggle'"
        
        except Exception as e:
            return f"Error with checkbox {sel}: {e}"
    
    elif action == "radio":
        """Select radio button. Format: 'selector' or 'index'"""
        sel = payload.strip()
        
        # Resolve numeric index
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                sel = core._element_map[index]['selector']
        
        try:
            element = find_element_with_context(driver, sel)
            
            if element.get_attribute('type') != 'radio':
                return f"Error: Element {sel} is not a radio button"
            
            if not element.is_selected():
                element.click()
                value = element.get_attribute('value') or 'unknown'
                return f"✓ Selected radio button {sel} (value: {value})"
            else:
                return f"Radio button {sel} already selected"
        
        except Exception as e:
            return f"Error selecting radio button {sel}: {e}"
    
    elif action == "slider":
        """Set range slider value. Format: 'selector|value' or 'index|value'"""
        if '|' not in payload:
            return "Error: Format is 'selector|value' or 'index|value'"
        
        sel, value = payload.split('|', 1)
        sel = sel.strip()
        value = value.strip()
        
        # Resolve numeric index
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                sel = core._element_map[index]['selector']
        
        try:
            element = find_element_with_context(driver, sel)
            
            if element.get_attribute('type') != 'range':
                return f"Error: Element {sel} is not a range slider"
            
            # Set value via JavaScript (more reliable than send_keys for sliders)
            driver.execute_script(f"arguments[0].value = '{value}'; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'));", element)
            
            return f"✓ Set slider {sel} to {value}"
        
        except Exception as e:
            return f"Error setting slider {sel}: {e}"
    
    elif action == "datepicker":
        """Set date input. Format: 'selector|YYYY-MM-DD' or 'index|YYYY-MM-DD'"""
        if '|' not in payload:
            return "Error: Format is 'selector|YYYY-MM-DD' or 'index|YYYY-MM-DD'"
        
        sel, date_value = payload.split('|', 1)
        sel = sel.strip()
        date_value = date_value.strip()
        
        # Resolve numeric index
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                sel = core._element_map[index]['selector']
        
        try:
            element = find_element_with_context(driver, sel)
            
            elem_type = element.get_attribute('type')
            if elem_type not in ['date', 'datetime-local', 'time', 'month', 'week']:
                return f"Error: Element {sel} is not a date/time input (type: {elem_type})"
            
            # Clear and set value
            element.clear()
            driver.execute_script(f"arguments[0].value = '{date_value}'; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'));", element)
            
            return f"✓ Set {elem_type} input {sel} to {date_value}"
        
        except Exception as e:
            return f"Error setting date {sel}: {e}"
    
    elif action == "colorpicker":
        """Set color picker value. Format: 'selector|#RRGGBB' or 'index|#RRGGBB'"""
        if '|' not in payload:
            return "Error: Format is 'selector|#RRGGBB' or 'index|#RRGGBB'"
        
        sel, color = payload.split('|', 1)
        sel = sel.strip()
        color = color.strip()
        
        # Resolve numeric index
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                sel = core._element_map[index]['selector']
        
        try:
            element = find_element_with_context(driver, sel)
            
            if element.get_attribute('type') != 'color':
                return f"Error: Element {sel} is not a color picker"
            
            # Set color via JavaScript
            driver.execute_script(f"arguments[0].value = '{color}'; arguments[0].dispatchEvent(new Event('input')); arguments[0].dispatchEvent(new Event('change'));", element)
            
            return f"✓ Set color picker {sel} to {color}"
        
        except Exception as e:
            return f"Error setting color {sel}: {e}"
    
    elif action == "clear":
        """Clear input/textarea. Format: 'selector' or 'index'"""
        sel = payload.strip()
        
        # Resolve numeric index
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                sel = core._element_map[index]['selector']
        
        try:
            element = find_element_with_context(driver, sel)
            element.clear()
            
            # Also clear via JavaScript for contenteditable
            if element.get_attribute('contenteditable') == 'true':
                driver.execute_script("arguments[0].textContent = '';", element)
            
            return f"✓ Cleared {sel}"
        
        except Exception as e:
            return f"Error clearing {sel}: {e}"
    
    elif action == "get_value":
        """Get value/text from element. Format: 'selector' or 'index'"""
        sel = payload.strip()
        
        # Resolve numeric index
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                sel = core._element_map[index]['selector']
        
        try:
            element = find_element_with_context(driver, sel)
            
            # Get value based on element type
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
                from selenium.webdriver.support.ui import Select
                select = Select(element)
                value = select.first_selected_option.text
            elif tag == 'textarea':
                value = element.get_attribute('value') or element.text
            else:
                value = element.text or element.get_attribute('value') or element.get_attribute('textContent') or ''
            
            return f"Value of {sel}: {value}"
        
        except Exception as e:
            return f"Error getting value from {sel}: {e}"
    
    elif action == "submit":
        """Submit a form. Format: 'selector' or 'index' (finds form element or input within form)"""
        sel = payload.strip()
        
        # Resolve numeric index
        if sel.isdigit():
            index = int(sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                sel = core._element_map[index]['selector']
        
        try:
            element = find_element_with_context(driver, sel)
            
            # Find the form (either the element itself or its parent form)
            if element.tag_name.lower() == 'form':
                form = element
            else:
                # Find parent form
                form = driver.execute_script("return arguments[0].closest('form');", element)
                
                if not form:
                    return f"Error: Element {sel} is not within a form"
            
            # Submit the form
            form.submit()
            time.sleep(1)  # Wait for submission
            
            return f"✓ Submitted form"
        
        except Exception as e:
            return f"Error submitting form {sel}: {e}"
    
    elif action == "drag_and_drop":
        """Drag element to target. Format: 'source_selector|target_selector' or 'source_index|target_index'"""
        if '|' not in payload:
            return "Error: Format is 'source|target' where each can be selector or index"
        
        source_sel, target_sel = payload.split('|', 1)
        source_sel = source_sel.strip()
        target_sel = target_sel.strip()
        
        # Resolve source index
        if source_sel.isdigit():
            index = int(source_sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                source_sel = core._element_map[index]['selector']
        
        # Resolve target index
        if target_sel.isdigit():
            index = int(target_sel)
            if hasattr(core, '_element_map') and core._element_map and index in core._element_map:
                target_sel = core._element_map[index]['selector']
        
        try:
            source = find_element_with_context(driver, source_sel)
            target = find_element_with_context(driver, target_sel)
            
            # Use ActionChains for drag and drop
            action_chains = webdriver.ActionChains(driver)
            action_chains.drag_and_drop(source, target).perform()
            time.sleep(0.5)
            
            return f"✓ Dragged {source_sel} to {target_sel}"
        
        except Exception as e:
            return f"Error drag and drop {source_sel} -> {target_sel}: {e}"
    
    return None
