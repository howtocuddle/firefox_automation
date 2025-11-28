import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from .utils import resolve_som_index, find_element_with_context

def select_option(driver, payload):
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

def checkbox(driver, payload):
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

def radio(driver, payload):
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

def slider(driver, payload):
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

def datepicker(driver, payload):
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

def colorpicker(driver, payload):
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

def get_value(driver, payload):
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

def submit_form(driver, payload):
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

def fill_form(driver, payload, perform_action_callback):
    """
    Fills multiple form fields.
    Requires a callback to perform_action to avoid circular imports.
    """
    try:
        data = json.loads(payload)
        results = []
        success_count = 0
        
        for sel, val in data.items():
            try:
                # Determine action based on element type or value
                real_sel, _, _ = resolve_som_index(sel)
                elem = find_element_with_context(driver, real_sel)
                tag = elem.tag_name.lower()
                type_attr = elem.get_attribute('type')
                
                res = ""
                if tag == 'select':
                    res = perform_action_callback("select", f"{sel}|{val}")
                elif type_attr in ['checkbox']:
                    res = perform_action_callback("checkbox", f"{sel}|{val}")
                elif type_attr in ['radio']:
                    res = perform_action_callback("radio", sel)
                else:
                    res = perform_action_callback("type", f"{sel}|{val}")
                
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
