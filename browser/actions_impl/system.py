import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from ....safety import get_workspace_path
from .utils import resolve_som_index, find_element_with_context

def get_clipboard(driver):
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

def get_console_logs(driver):
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

def handle_alert(driver, payload):
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

def set_zoom(driver, payload):
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

def check_downloads(driver):
    try:
        download_dir = get_workspace_path()
        if not os.path.exists(download_dir):
             # Fallback to ~/Downloads if workspace path not suitable or empty
             # But safety module says get_workspace_path is the way.
             # Actually, the browser is configured to download to a specific dir?
             # We should check config. But here we assume workspace or standard.
             pass

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

def press_key(driver, payload):
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

def media_control(driver, payload):
    if '|' not in payload:
        return "Error: Format is 'selector|action'. Action: play, pause, mute, unmute, seek <sec>."
    
    parts = payload.split('|', 1)
    sel = parts[0].strip()
    cmd_part = parts[1].strip().lower()
    
    try:
        selector, _, _ = resolve_som_index(sel)
    except ValueError as e:
        return f"Error: {e}"
    
    try:
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
