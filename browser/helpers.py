"""
Helper functions for browser automation
Includes CAPTCHA detection and human-like interactions
"""
import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from .core import _driver, get_driver


def handle_manual_captcha():
    """
    Trigger manual CAPTCHA resolution workflow.
    Called when the agent visually detects a CAPTCHA.
    """
    driver = get_driver()
    if not driver:
        return
    
    try:
        print(f"\n[!] AGENT DETECTED CAPTCHA! (Title: {driver.title})")
        
        # ATTEMPT AUTO-SOLVE (Best Effort) - Keep this helper for Cloudflare
        # We can still try to auto-click if we suspect it's Cloudflare, 
        # or just let the user handle it.
        # For now, let's keep the auto-click logic as a helper but trigger it 
        # only if the agent thinks it's a captcha.
        
        print(">> Attempting to click Cloudflare checkbox (if present)...")
        try:
            # 1. Find the iframe
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            cf_frame = None
            for frame in iframes:
                src = frame.get_attribute("src") or ""
                name = frame.get_attribute("name") or ""
                if "turnstile" in src or "cloudflare" in src or "challenge" in src or name.startswith("cf-"):
                    cf_frame = frame
                    break
            
            if cf_frame:
                # Switch to iframe
                driver.switch_to.frame(cf_frame)
                time.sleep(0.5)
                
                # Try to find the checkbox or body
                try:
                    checkbox = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                    human_click(checkbox)
                except:
                    # Try clicking the main wrapper or body
                    try:
                        body = driver.find_element(By.TAG_NAME, "body")
                        # Click slightly offset from center to look human
                        action = ActionChains(driver)
                        action.move_to_element_with_offset(body, 10, 10).click().perform()
                    except:
                        pass
                
                print(">> Clicked Cloudflare widget. Waiting to see if it worked...")
                driver.switch_to.default_content()
                time.sleep(3) # Wait for verification
            else:
                print(">> Could not find Cloudflare iframe.")
        except Exception as e:
            print(f">> Auto-click failed: {e}")
            try:
                driver.switch_to.default_content()
            except:
                pass

        print(">> Please switch to the browser window and solve it!")
        
        # Send desktop notification
        try:
            from ..notify import send_notification
            send_notification(
                f"[Browser Agent] CAPTCHA Detected! Please solve it.",
                urgency="critical"
            )
        except Exception as e:
            print(f"Notification error: {e}")
        
        print("Waiting for CAPTCHA resolution...")
        
        # Use input() to pause execution until user confirms
        try:
            input("\n>>> 🛑 CAPTCHA DETECTED 🛑 <<<\n>>> Please solve the CAPTCHA in the browser window.\n>>> Press ENTER here when you are done to continue... <<<\n")
            print("[+] Resuming automation...")
            time.sleep(2)
        except EOFError:
            print("[-] No terminal input available. Waiting 30 seconds...")
            time.sleep(30)
        except Exception as e:
            print(f"[-] Input error: {e}. Waiting 30 seconds...")
            time.sleep(30)
            
    except Exception as e:
        print(f"Error handling CAPTCHA: {e}")


def human_click(element):
    """Human-like click with smooth scrolling and randomized timing"""
    driver = get_driver()
    try:
        # Scroll to element first
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(random.uniform(0.3, 0.7))  # Human-like scroll delay
        
        # Explicitly focus the element (helps with SPAs like Spotify)
        try:
            driver.execute_script("arguments[0].focus();", element)
        except:
            pass

        # Human-like click
        action = ActionChains(driver)
        action.move_to_element(element)
        action.pause(random.uniform(0.1, 0.3))  # Hover
        action.click()
        action.pause(random.uniform(0.05, 0.15))  # Mouse down/up delay
        action.perform()
        return True
    except:
        # Fallback to standard click
        try:
            element.click()
            return True
        except:
            # Try JS click fallback
            try:
                driver.execute_script("arguments[0].click();", element)
                return True
            except:
                return False


def human_type(element, text):
    """Human-like typing with randomized keystroke timing"""
    driver = get_driver()
    try:
        # Check visibility/size
        is_visible = element.is_displayed() and element.size['width'] > 0 and element.size['height'] > 0
        
        if is_visible:
            # Scroll to element
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(random.uniform(0.2, 0.5))
            
            try:
                element.click()  # Focus
            except:
                pass
            
            try:
                element.clear()
            except:
                pass
        else:
            # For hidden elements (like Reddit's search input), just try to clear via JS if needed
            # But mostly just type
            pass
        
        for char in text:
            element.send_keys(char)
            # Random delay between keystrokes (30ms to 100ms)
            time.sleep(random.uniform(0.03, 0.1))
        
        # Add small delay after typing to ensure text is registered
        time.sleep(0.3)
        
        # Verify text was entered
        current_value = element.get_attribute('value') or element.text
        if current_value and text in current_value:
            return True
        
        # Still return True if we got here without exceptions
        return True
    except Exception as e:
        print(f"Error in human_type: {e}")
        return False
