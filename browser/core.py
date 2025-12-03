"""
Browser Core - Driver Management
Handles browser lifecycle: open, close, driver access
"""
import os
import time
import shutil
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from ...safety import get_workspace_path

from .config import BrowserConfig

# Global driver instance
_driver = None

# Global element map for Set-of-Marks (SoM)
_element_map = {}
_last_scan_url = None
_browser_context_lines = 0
_url_log = [] # List of {"url": str, "title": str, "timestamp": float}

def log_url(url, title=""):
    """Logs a visited URL."""
    global _url_log
    # Avoid duplicates if same as last
    if _url_log and _url_log[-1]['url'] == url:
        return
    _url_log.append({
        "url": url,
        "title": title,
        "timestamp": time.time()
    })

def get_url_log():
    global _url_log
    return _url_log


def get_profile_path():
    return BrowserConfig.PROFILE_PATH


def force_cleanup():
    """Kills stale browser and driver processes safely."""
    global _driver
    import subprocess
    try:
        # Kill geckodriver
        subprocess.run(["pkill", "geckodriver"], stderr=subprocess.DEVNULL)
        
        # Kill ONLY agent-spawned browsers using the profile path pattern
        subprocess.run(["pkill", "-f", "-9", "/tmp/agent_profile_"], stderr=subprocess.DEVNULL)
        
        # Reset driver variable
        _driver = None
        
        return "Agent browser processes nuked (safe mode)."
    except Exception as e:
        return f"Error nuking: {e}"


def get_driver():
    global _driver
    return _driver


def get_context_lines():
    global _browser_context_lines
    return _browser_context_lines


def set_context_lines(lines):
    global _browser_context_lines
    _browser_context_lines = lines


def open_browser(url=None):
    global _driver
    
    # Check if driver is actually alive
    if _driver is not None:
        try:
            _driver.title
            if url:
                _driver.get(url)
                return f"Browser already open. Navigated to {url}"
            return "Browser already open."
        except:
            _driver = None  # It's dead, proceed to restart

    # Always force cleanup to ensure no zombie processes prevent startup
    force_cleanup()

    try:
        # Clone profile
        original_profile = get_profile_path()
        profile_path = BrowserConfig.get_temp_profile_path()
        
        if os.path.exists(profile_path):
            shutil.rmtree(profile_path)

        try:
            if os.path.exists(original_profile):
                shutil.copytree(original_profile, profile_path, ignore=shutil.ignore_patterns("lock", ".parentlock", "parent.lock"))
            else:
                os.makedirs(profile_path, exist_ok=True)
        except:
            pass
        
        # Cleanup locks
        for lock in ["lock", ".parentlock", "parent.lock"]:
            try:
                os.remove(os.path.join(profile_path, lock))
            except:
                pass

        options = Options()
        options.binary_location = BrowserConfig.BINARY_LOCATION
        options.add_argument("-profile")
        options.add_argument(profile_path)
        
        # Configure download directory
        download_dir = BrowserConfig.DOWNLOAD_DIR
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", download_dir)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf,application/zip,image/png,image/jpeg")
        
        # Reset Window Scaling (User requested "normal" window)
        # options.set_preference("layout.css.devPixelsPerPx", "0.75") # REMOVED
        
        # Stealth Preferences
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference('useAutomationExtension', False)
        options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Use cached geckodriver to avoid GitHub API rate limits
        geckodriver_path = None
        wdm_cache = os.path.expanduser("~/.wdm/drivers/geckodriver")
        
        # Search for cached geckodriver
        if os.path.exists(wdm_cache):
            for root, dirs, files in os.walk(wdm_cache):
                if "geckodriver" in files:
                    geckodriver_path = os.path.join(root, "geckodriver")
                    break
        
        # Fall back to system path
        if not geckodriver_path:
            geckodriver_path = shutil.which("geckodriver")

        # Fall back to manager if no cache found
        if not geckodriver_path:
            geckodriver_path = GeckoDriverManager().install()
        
        service = Service(geckodriver_path)
        _driver = webdriver.Firefox(service=service, options=options)
        _driver.set_page_load_timeout(BrowserConfig.PAGE_LOAD_TIMEOUT)
        
        # NOTE: selenium-stealth only supports Chrome. Firefox stealth is handled via preferences above.
        # The dom.webdriver.enabled=False preference is the Firefox equivalent.
        
        # Navigate to URL if provided, otherwise blank page
        target = url if url else "about:blank"
        _driver.get(target)
        
        if url:
            return f"Browser opened and navigated to: {url}"
        return "Browser opened."
        
    except Exception as e:
        return f"Failed to open browser: {e}"


def close_browser():
    global _driver
    if _driver:
        try:
            _driver.quit()
        except:
            pass
        _driver = None
        return "Browser closed."
    return "Browser not open."
