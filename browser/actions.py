"""
Browser Actions - Refactored
Handles interaction with page elements: click, type, scroll, etc.
Delegates implementation to submodules in actions_impl.
"""
import os
import time
from .core import get_driver
from .actions_impl.utils import remove_overlays
from .actions_impl import interaction, nav, forms, search, system

def perform_action(action: str, payload: str = None) -> str:
    driver = get_driver()
    if not driver:
        return "Error: Browser not open."

    # Auto-remove overlays before any action
    remove_overlays(driver)
    driver.switch_to.default_content()

    # Dispatch to implementation modules
    
    # Interaction
    if action == "click":
        return interaction.click(driver, payload)
    elif action == "hover":
        return interaction.hover(driver, payload)
    elif action == "focus":
        return interaction.focus(driver, payload)
    elif action == "right_click":
        return interaction.right_click(driver, payload)
    elif action == "type":
        return interaction.type_text(driver, payload)
    elif action == "clear":
        return interaction.clear(driver, payload)
    elif action == "drag_and_drop":
        return interaction.drag_and_drop(driver, payload)
    elif action == "upload_file":
        return interaction.upload_file(driver, payload)
        
    # Navigation
    elif action == "scroll":
        return nav.scroll(driver, payload)
    elif action == "scroll_element":
        return nav.scroll_element(driver, payload)
    elif action == "switch_frame":
        return nav.switch_frame(driver, payload)
    elif action == "switch_default_content":
        return nav.switch_default_content(driver, payload)
    elif action == "new_tab":
        return nav.new_tab(driver, payload)
    elif action == "switch_tab":
        return nav.switch_tab(driver, payload)
    elif action == "open_in_new_tab":
        return nav.open_in_new_tab(driver, payload)
    elif action == "close_tab":
        return nav.close_tab(driver, payload)
    elif action == "list_tabs":
        return nav.list_tabs(driver, payload)
        
    # Forms
    elif action == "select":
        return forms.select_option(driver, payload)
    elif action == "checkbox":
        return forms.checkbox(driver, payload)
    elif action == "radio":
        return forms.radio(driver, payload)
    elif action == "slider":
        return forms.slider(driver, payload)
    elif action == "datepicker":
        return forms.datepicker(driver, payload)
    elif action == "colorpicker":
        return forms.colorpicker(driver, payload)
    elif action == "get_value":
        return forms.get_value(driver, payload)
    elif action == "submit":
        return forms.submit_form(driver, payload)
    elif action == "fill_form":
        # Pass perform_action as callback to handle recursion
        return forms.fill_form(driver, payload, perform_action)
        
    # Search
    elif action == "find_element":
        return search.find_element(driver, payload)
    elif action == "find_on_page":
        return search.find_on_page(driver, payload)
    elif action == "quick_find":
        return search.quick_find(driver, payload)
        
    # System
    elif action == "get_clipboard":
        return system.get_clipboard(driver)
    elif action == "get_console_logs":
        return system.get_console_logs(driver)
    elif action == "handle_alert":
        return system.handle_alert(driver, payload)
    elif action == "set_zoom":
        return system.set_zoom(driver, payload)
    elif action == "check_downloads":
        return system.check_downloads(driver)
    elif action == "press_key":
        return system.press_key(driver, payload)
    elif action == "media_control":
        return system.media_control(driver, payload)

    # No action matched
    return None
