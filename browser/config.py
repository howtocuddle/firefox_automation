
import os

class BrowserConfig:
    """
    Centralized configuration for the Browser Agent.
    Reads from environment variables or defaults.
    """
    
    # Browser Profile
    PROFILE_PATH = os.environ.get("BROWSER_PROFILE_PATH", "/home/rootp/snap/firefox/common/.mozilla/firefox/8g3pkm7z.default")
    BINARY_LOCATION = os.environ.get("BROWSER_BINARY_LOCATION", "/usr/bin/firefox")
    
    # Downloads
    DOWNLOAD_DIR = os.environ.get("BROWSER_DOWNLOAD_DIR", os.path.join(os.getcwd(), "downloads"))
    
    # Timeouts (seconds)
    PAGE_LOAD_TIMEOUT = int(os.environ.get("BROWSER_PAGE_LOAD_TIMEOUT", 60))
    IMPLICIT_WAIT = int(os.environ.get("BROWSER_IMPLICIT_WAIT", 2))
    
    # Stealth
    HEADLESS = os.environ.get("BROWSER_HEADLESS", "false").lower() == "true"
    
    # Load config override
    try:
        import json
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        config_path = os.path.join(base_dir, 'agent_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                if "browser_headless" in config:
                    HEADLESS = config["browser_headless"]
    except:
        pass
    
    @classmethod
    def get_temp_profile_path(cls):
        import time
        # Use a local directory in user home to avoid Snap confinement issues with /tmp
        base_path = os.path.expanduser("~/agent_browser_profiles")
        if not os.path.exists(base_path):
            os.makedirs(base_path, exist_ok=True)
        return os.path.join(base_path, f"profile_{int(time.time())}")
