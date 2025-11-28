"""
Browser Content Extraction
Handles screenshots, Set-of-Marks (SoM), and text content extraction
"""
import os
import time
import json
from PIL import Image
import pytesseract
from ...safety import get_workspace_path
from .core import get_driver
from . import core  # Import module to modify global variables

def perform_content_action(action: str, payload: str = None) -> str:
    driver = get_driver()
    if not driver:
        return "Error: Browser not open."

    if action == "scan":
        # Identify interactive elements
        script = """
        var items = [];
        var elements = document.querySelectorAll('a, button, input, textarea, [role="button"]');
        for (var i=0; i<elements.length; i++) {
            var el = elements[i];
            var rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden') {
                var text = el.innerText || el.value || el.getAttribute('aria-label') || '';
                text = text.trim().substring(0, 200); // significantly increased limit
                if (text || el.tagName === 'INPUT') {
                    var selector = el.tagName.toLowerCase();
                    if (el.id) selector += '#' + el.id;
                    else if (el.className) {
                            // Use first 3 classes for selector, no truncation
                            var classes = el.className.split(' ').filter(c => c.length > 0 && !c.includes(':'));
                            if (classes.length > 0) selector += '.' + classes.slice(0, 3).join('.');
                    }
                    
                    // Add href for links
                    var extra = '';
                    if (el.tagName === 'A') extra = ' (' + el.href + ')';
                    
                    items.push(i + '|' + el.tagName + '|' + text + '|' + selector + '|' + extra);
                }
            }
        }
        return items;
        """
        items = driver.execute_script(script)
        output = ["Interactive Elements:"]
        for item in items[:300]: # Increased from 50 to 300
            idx, tag, text, sel, extra = item.split('|', 4)
            output.append(f"{idx}. {tag}: {text} -> {sel}{extra}")
        return "\n".join(output)

    elif action == "screenshot":
        try:
            timestamp = int(time.time())
            filename = f"screenshot_{timestamp}.png"
            screenshots_dir = os.path.join(get_workspace_path(), "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            path = os.path.join(screenshots_dir, filename)
            driver.save_screenshot(path)
            
            result = f"Screenshot saved: {path}\n\n"
            
            # OCR the screenshot (CPU-based, lightweight)
            import shutil
            if shutil.which("tesseract"):
                try:
                    img = Image.open(path)
                    text = pytesseract.image_to_string(img)
                    text = text.strip()
                    
                    if text:
                        result += f"Extracted Text (OCR):\n{text[:500]}" + ("...\n" if len(text) > 500 else "\n")
                    else:
                        result += "(No text detected via OCR)\n"
                except Exception as ocr_error:
                    result += f"(OCR failed: {ocr_error})\n"
            else:
                result += "(OCR skipped: 'tesseract' binary not found)\n"
            
            # Vision analysis skipped (user preference)
            
            return result
                
        except Exception as e:
            return f"Error taking screenshot: {e}"

    elif action == "snap":
        """Screenshot with Set-of-Marks (SoM) - DOM-based injection."""
        clean_path, path, result = _perform_snap(driver)
        return result

    elif action == "capture_with_som":
        """Internal action for autonomous mode: returns (clean_path, marked_path, result) tuple."""
        return _perform_snap(driver)

    elif action == "get_content":
        """
        Enhanced multi-layer content extraction for any website.
        """
        try:
            # Load content extraction script
            content_js_path = os.path.join(os.path.dirname(__file__), 'browser_content.js')
            with open(content_js_path, 'r') as f:
                script = f.read()
            
            content_data = driver.execute_script(script)
            
            # Format output as structured text
            output = []
            
            # Page Info
            output.append("=== PAGE INFO ===")
            output.append(f"Title: {content_data['pageInfo'].get('title', 'N/A')}")
            output.append(f"URL: {content_data['pageInfo'].get('url', 'N/A')}")
            if content_data['pageInfo'].get('mainTopic'):
                output.append(f"Main Topic: {content_data['pageInfo']['mainTopic']}")
            if content_data['pageInfo'].get('description'):
                output.append(f"Description: {content_data['pageInfo']['description'][:200]}")
            
            # Main Content
            output.append("\n=== MAIN CONTENT ===")
            if content_data.get('mainContent'):
                output.append(content_data['mainContent'])
            else:
                output.append("(No main content detected)")
            
            # Interactive Elements
            interactive = content_data.get('interactive', {})
            
            if interactive.get('forms') or interactive.get('buttons') or interactive.get('inputs'):
                output.append("\n=== INTERACTIVE ELEMENTS ===")
                
                # Forms
                if interactive.get('forms'):
                    output.append("\nForms:")
                    for form in interactive['forms'][:5]:
                        output.append(f"  • {form['action']}: {form['fields']}")
                
                # Buttons
                if interactive.get('buttons'):
                    output.append("\nButtons:")
                    for btn in interactive['buttons'][:10]:
                        output.append(f"  • \"{btn['text']}\" → {btn['selector']}")
                
                # Inputs
                if interactive.get('inputs'):
                    output.append("\nInputs:")
                    for inp in interactive['inputs'][:10]:
                        output.append(f"  • {inp['label']} ({inp['type']}) → {inp['selector']}")
            
            # Links
            if interactive.get('links'):
                links = interactive['links']
                if links.get('navigation') or links.get('content'):
                    output.append("\nLinks:")
                    if links.get('navigation'):
                        output.append(f"  Navigation: {', '.join(links['navigation'][:8])}")
                    if links.get('content'):
                        output.append("  Content Links:")
                        for link in links['content'][:5]:
                            output.append(f"    - {link['text']} ({link['href']})")
            
            # Navigation
            nav = content_data.get('navigation', {})
            if nav.get('breadcrumbs'):
                output.append("\n=== NAVIGATION ===")
                output.append(f"Breadcrumbs: {' > '.join(nav['breadcrumbs'][:6])}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"Error extracting content: {e}"

    return None


def _perform_snap(driver):
    try:
        # Ensure screenshots directory exists
        screenshots_dir = os.path.join(get_workspace_path(), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        timestamp = int(time.time())
        filename = f"screenshot_{timestamp}.png"
        path = os.path.join(screenshots_dir, filename)
        
        # 0. Wait for page load and DOM stability
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            # Basic load wait
            WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            
            # Smart DOM stability wait
            print("[Browser] Waiting for DOM stability...")
            start_time = time.time()
            last_count = 0
            stable_count = 0
            
            while time.time() - start_time < 5.0: # Max 5s wait
                current_count = driver.execute_script("return document.querySelectorAll('*').length")
                
                if current_count == last_count:
                    stable_count += 1
                else:
                    stable_count = 0
                    
                if stable_count >= 3: # Stable for 3 checks (approx 1.5s)
                    break
                    
                last_count = current_count
                time.sleep(0.5)
                
        except Exception as e:
            print(f"[Browser] Warning: DOM wait failed: {e}")

        # 1. Take CLEAN screenshot for OCR (before markers)
        clean_path = path.replace(".png", "_clean.png")
        driver.save_screenshot(clean_path)

        # 2. Load and execute Set-of-Marks JavaScript
        som_js_path = os.path.join(os.path.dirname(__file__), 'browser_som.js')
        with open(som_js_path, 'r') as f:
            mark_script = f.read()

        # Execute marking script with retry logic
        max_retries = 10
        elements_data = []
        
        print("[Browser] Waiting for page to load interactive elements...")
        for attempt in range(max_retries):
            result_data = driver.execute_script(mark_script)
            
            # Handle new object format with debug info
            if isinstance(result_data, dict) and 'items' in result_data:
                elements_data = result_data['items']
                debug_info = result_data.get('debug', {})
                print(f"[Browser] SoM Debug: Viewport {debug_info.get('viewport')}, Candidates {debug_info.get('totalCandidates')}, Processed {debug_info.get('processed')}, Filtered {debug_info.get('filtered')}")
            else:
                # Fallback for old format (list)
                elements_data = result_data
            
            if elements_data and len(elements_data) > 0:
                break
            
            time.sleep(1)
        
        # Wait a split second for rendering markers
        time.sleep(0.5)
        
        # 3. Take MARKED Screenshot (for Vision)
        driver.save_screenshot(path)
        
        # Optimize Image for Vision (Resize if too large)
        try:
            img = Image.open(path)
            max_width = 2048
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                img.save(path)
                print(f"[Browser] Optimized screenshot: {img.width}x{img.height} -> {max_width}x{new_height}")
        except Exception as e:
            print(f"[Browser] Image optimization failed: {e}")
        
        # 4. Remove markers
        cleanup_script = "var c = document.getElementById('agent-som-container'); if(c) c.remove();"
        driver.execute_script(cleanup_script)
        
        # 5. Process Data
        element_map = {}
        if elements_data:
            for item in elements_data:
                try:
                    # Ensure ID is an integer for compatibility with actions.py
                    elem_id = int(item['id'])
                    element_map[elem_id] = item
                except ValueError:
                    pass # Skip items with non-integer IDs
        
        # Cache element map in core module
        core._element_map = element_map
        core._last_scan_url = driver.current_url
        
        print(f"[Browser] Updated element map with {len(element_map)} items")
        
        result = f"Marked screenshot saved: {path}\n\n"
        
        # 6. OCR of CLEAN Viewport
        import shutil
        if shutil.which("tesseract"):
            try:
                # Use clean_path for OCR
                with Image.open(clean_path) as img:
                    text = pytesseract.image_to_string(img)
                    text = text.strip()
                    if text:
                        result += f"Viewport Text (OCR):\n{text[:2000]}" + ("...\n" if len(text) > 2000 else "\n")
                    else:
                        result += "(No text detected via OCR)\n"
                
                # Cleanup clean screenshot - SKIPPED for dual-image strategy
                # try:
                #     os.remove(clean_path)
                # except:
                #     pass
            except Exception as ocr_error:
                result += f"(OCR failed: {ocr_error})\n"
        else:
            result += "(OCR skipped: 'tesseract' binary not found)\n"

        # Element summary

        # Scroll Status
        try:
            scroll_script = """
            return JSON.stringify({
                scrollTop: window.scrollY,
                scrollHeight: document.documentElement.scrollHeight,
                clientHeight: document.documentElement.clientHeight
            });
            """
            scroll_info = json.loads(driver.execute_script(scroll_script))
            scrollTop = scroll_info['scrollTop']
            scrollHeight = scroll_info['scrollHeight']
            clientHeight = scroll_info['clientHeight']
            
            if scrollHeight > clientHeight:
                percentage = int((scrollTop / (scrollHeight - clientHeight)) * 100)
                result += f"Scroll: {percentage}% (View: {scrollTop}-{scrollTop+clientHeight} / Total: {scrollHeight})\n"
            else:
                result += "Scroll: 100% (Single Page)\n"
        except:
            result += "Scroll: Unknown\n"

        # Element summary
        result += f"\n\nInteractive Elements (Total: {len(element_map)}):\n"
        for idx, info in sorted(element_map.items())[:30]:  # Show first 30
            text_preview = info['text'][:50] + ('...' if len(info['text']) > 50 else '')
            result += f"  [{idx}] {info.get('tag', 'UNKNOWN')}: {text_preview}\n"
            if info.get('href'):
                result += f"      → {info['href']}\n"
        
        if len(element_map) > 30:
            result += f"  ... and {len(element_map) - 30} more elements\n"
        
        result += "\nUse 'click' with a number (e.g., 'click 5') to interact with marked elements.\n"
        
        return clean_path, path, result
        
    except Exception as e:
        print(f"[Browser] CRITICAL SNAP ERROR: {e}")
        import traceback
        traceback.print_exc()
        return "", "", f"Error creating marked screenshot: {e}"
