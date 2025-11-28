import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

def find_element(driver, payload):
    if not payload:
        return "Error: Text to find required."
    
    script = f"""
    var text = "{payload.lower()}";
    var elements = document.querySelectorAll('a, button, input, textarea, [role="button"]');
    var found = [];
    
    for (var i=0; i<elements.length; i++) {{
        var el = elements[i];
        var elText = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('alt') || '').toLowerCase();
        
        if (elText.includes(text) && el.offsetParent !== null) {{
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

def find_on_page(driver, payload):
    if not payload or '|' not in payload:
        return "Error: Format is 'type|query'. Types: text, link, button, input, any."
    
    parts = payload.split('|', 1)
    search_type = parts[0].strip().lower()
    query = parts[1].strip().lower()
    
    if not query:
        return "Error: Query cannot be empty."

    try:
        # JavaScript to find, filter, and rank elements
        results = driver.execute_script("""
            const type = arguments[0];
            const query = arguments[1];
            const results = [];
            
            function isVisible(elem) {
                if (!elem) return false;
                const style = window.getComputedStyle(elem);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const rect = elem.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
            }
            
            function getSoMID(elem) {
                return elem.getAttribute('data-som-id') || null;
            }
            
            const allElems = document.querySelectorAll('*');
            
            for (let elem of allElems) {
                if (!isVisible(elem)) continue;
                
                let match = false;
                let text = elem.innerText || elem.textContent || "";
                text = text.trim().replace(/\\s+/g, ' ');
                const textLower = text.toLowerCase();
                
                // Filter by type
                if (type === 'link' && elem.tagName !== 'A') continue;
                if (type === 'button' && elem.tagName !== 'BUTTON' && elem.getAttribute('role') !== 'button') continue;
                if (type === 'input' && elem.tagName !== 'INPUT' && elem.tagName !== 'TEXTAREA') continue;
                if (type === 'text' && (elem.tagName === 'SCRIPT' || elem.tagName === 'STYLE' || elem.children.length > 0)) continue; // Leaf nodes for text
                
                // Match query
                if (textLower.includes(query)) {
                    match = true;
                } else if (type === 'input' || type === 'any') {
                    const placeholder = elem.getAttribute('placeholder') || "";
                    if (placeholder.toLowerCase().includes(query)) match = true;
                    const value = elem.value || "";
                    if (value.toLowerCase().includes(query)) match = true;
                }
                
                if (match) {
                    // Scoring
                    let score = 0;
                    if (textLower === query) score += 100; // Exact match
                    else if (textLower.startsWith(query)) score += 50; // Starts with
                    else score += 10; // Contains
                    
                    if (type === 'text') {
                        // Prefer longer context for text (up to a limit)
                        score += Math.min(text.length, 200) / 10;
                    }
                    
                    results.push({
                        id: getSoMID(elem),
                        tag: elem.tagName,
                        text: text.substring(0, 100) + (text.length > 100 ? "..." : ""),
                        score: score
                    });
                }
            }
            
            // Sort by score desc
            results.sort((a, b) => b.score - a.score);
            return results.slice(0, 20);
        """, search_type, query)
        
        if not results:
            return f"No results found for '{query}' (type: {search_type})."
        
        output = [f"Found {len(results)} matches for '{query}':"]
        for res in results:
            som_id = f"[{res['id']}]" if res['id'] else "[No ID]"
            output.append(f"- {som_id} {res['tag']}: \"{res['text']}\"")
            
        return "\n".join(output)
        
    except Exception as e:
        return f"Error finding on page: {e}"

def quick_find(driver, payload):
    if not payload:
        return "Error: Text required"
    
    # Handle "text|true" for links_only
    links_only = False
    text = payload
    if "|" in payload:
        parts = payload.split("|")
        text = parts[0]
        if len(parts) > 1 and parts[1].strip().lower() == "true":
            links_only = True
    
    try:
        trigger_key = "'" if links_only else "/"
        actions = webdriver.ActionChains(driver)
        actions.send_keys(trigger_key).perform()
        time.sleep(0.2)
        actions.send_keys(text).perform()
        
        mode_str = "Links" if links_only else "Text"
        return f"Quick Find ({mode_str}): '{text}'"
    except Exception as e:
        return f"Error: {e}"
