"""
Browser Action Dispatcher
Aggregates actions from different modules into a single interface.
"""
from .core import get_driver, open_browser, close_browser, force_cleanup
from .actions import perform_action as do_action
from .navigation import perform_navigation as do_navigation
from .content import perform_content_action as do_content

def browser_automation(action: str, payload: str = None) -> str:
    """
    Low-level browser control.
    Dispatches commands to appropriate modules.
    """
    # Core actions
    if action == "open":
        return open_browser(url=payload)
    elif action == "close":
        return close_browser()
    elif action == "nuke":
        return force_cleanup()
    
    # Check if driver is alive for other actions
    driver = get_driver()
    if not driver:
         # Auto-restart if session is lost and action requires browser
         # This logic is also in individual modules but good to have here as a catch-all check
         # or we can let modules handle it.
         # For "open" it's handled above.
         pass

    # Try Navigation
    res = do_navigation(action, payload)
    if res is not None:
        return res
        
    # Try Actions
    res = do_action(action, payload)
    if res is not None:
        return res
        
    # Try Content
    res = do_content(action, payload)
    if res is not None:
        return res
        
    return f"Unknown action: {action}"
