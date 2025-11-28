"""
XPath Journal - Learns and caches robust XPaths for browser automation.
"""
import json
import os
from urllib.parse import urlparse
from selenium.webdriver.remote.webelement import WebElement

JOURNAL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'xpath_journal.json')

def get_domain(url):
    """Extract domain from URL."""
    try:
        if not url: return "unknown"
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.replace('www.', '')
    except:
        return "unknown"

def load_journal():
    """Load the journal from disk."""
    if not os.path.exists(JOURNAL_PATH):
        return {}
    try:
        with open(JOURNAL_PATH, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_journal(data):
    """Save the journal to disk."""
    try:
        with open(JOURNAL_PATH, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[XPath Journal] Error saving journal: {e}")

def get_xpath(url, name):
    """
    Retrieve a cached XPath for a given name on a specific domain.
    
    Args:
        url: Current page URL
        name: Name of the element (e.g., "Search", "Login")
        
    Returns:
        str: XPath if found, else None
    """
    domain = get_domain(url)
    journal = load_journal()
    
    if domain in journal and name in journal[domain]:
        return journal[domain][name]
    return None

def save_xpath(url, name, xpath):
    """
    Save an XPath for a given name on a specific domain.
    """
    domain = get_domain(url)
    journal = load_journal()
    
    if domain not in journal:
        journal[domain] = {}
    
    journal[domain][name] = xpath
    save_journal(journal)
    print(f"[XPath Journal] Learned XPath for '{name}' on {domain}: {xpath}")

def generate_robust_xpath(element: WebElement, driver) -> str:
    """
    Generate a robust XPath for a given WebElement.
    Prioritizes ID > Name > Placeholder > Aria-Label > Text > Class.
    """
    try:
        # 1. ID (if valid and not dynamic-looking)
        el_id = element.get_attribute("id")
        if el_id and not any(char.isdigit() for char in el_id[-4:]): # Heuristic for dynamic IDs
            return f"//*[@id='{el_id}']"
        
        tag = element.tag_name
        
        # 2. Name
        name = element.get_attribute("name")
        if name:
            return f"//{tag}[@name='{name}']"
        
        # 3. Placeholder
        placeholder = element.get_attribute("placeholder")
        if placeholder:
            return f"//{tag}[@placeholder='{placeholder}']"
        
        # 4. Aria-Label
        aria = element.get_attribute("aria-label")
        if aria:
            return f"//{tag}[@aria-label='{aria}']"
        
        # 5. Title
        title = element.get_attribute("title")
        if title:
            return f"//{tag}[@title='{title}']"
            
        # 6. Type (for inputs, combined with other attributes if possible, or just type if unique)
        el_type = element.get_attribute("type")
        if tag == "input" and el_type:
            # Check if unique
            others = driver.find_elements("xpath", f"//input[@type='{el_type}']")
            if len(others) == 1:
                return f"//input[@type='{el_type}']"
        
        # 7. Text Content (for buttons/links)
        text = element.text
        if text and len(text) < 50:
            return f"//{tag}[contains(text(), '{text}')]"
            
        # 8. Class (risky, but better than nothing if unique)
        cls = element.get_attribute("class")
        if cls:
            # Take the first class usually
            first_cls = cls.split()[0] if cls.split() else ""
            if first_cls:
                return f"//{tag}[contains(@class, '{first_cls}')]"
        
        return None
    except Exception as e:
        print(f"[XPath Journal] Error generating XPath: {e}")
        return None

def extract_element_name(element: WebElement) -> str:
    """
    Extract a meaningful name for an element to use as a journal key.
    Prioritizes: Aria-Label > Text > Title > Name > ID > Placeholder > Alt.
    Returns None if no good name is found.
    """
    try:
        # 1. Aria-Label (often best for interactive elements)
        aria = element.get_attribute("aria-label")
        if aria and len(aria) < 50:
            return aria.strip()
            
        # 2. Text Content (for buttons/links)
        text = element.text
        if text:
            clean_text = text.strip().replace("\n", " ")
            if 2 <= len(clean_text) < 30: # meaningful length
                return clean_text
        
        # 3. Title
        title = element.get_attribute("title")
        if title and len(title) < 50:
            return title.strip()
            
        # 4. Name attribute
        name = element.get_attribute("name")
        if name and len(name) < 30:
            return name.strip()
            
        # 5. Placeholder
        placeholder = element.get_attribute("placeholder")
        if placeholder and len(placeholder) < 50:
            return placeholder.strip()
            
        # 6. ID (if meaningful)
        el_id = element.get_attribute("id")
        if el_id and len(el_id) < 30 and not any(char.isdigit() for char in el_id[-4:]):
            return el_id.strip()
            
        # 7. Alt text (images)
        alt = element.get_attribute("alt")
        if alt and len(alt) < 50:
            return alt.strip()
            
        return None
    except:
        return None
