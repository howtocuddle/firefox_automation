"""
Deep Research Mode
Autonomously browses multiple pages to gather information.
"""
import time
from .dispatcher import browser_automation
from . import core

def research(query: str, depth: int = 3, sources: int = 5) -> str:
    """
    Deep research mode - Perplexity Comet style.
    Autonomously browses multiple pages, extracts information, and synthesizes an answer.
    """
    try:
        # Ensure browser is open
        open_res = browser_automation("open")
        if "Failed" in open_res:
            return f"Error: {open_res}"
        
        report = [f"# Deep Research: {query}\n"]
        
        # 1. Search for the query
        browser_automation("web_search", query)
        time.sleep(2)
        
        # 2. Get search results using snap
        snap_result = browser_automation("snap")
        report.append("## Search Results\n")
        report.append(snap_result[:500] + "...\n")
        
        # 3. Extract links from element map
        links = []
        if core._element_map:
            for idx, info in core._element_map.items():
                if info.get('href') and 'http' in info['href']:
                    links.append({
                        'url': info['href'],
                        'title': info['text'][:100]
                    })
                if len(links) >= sources:
                    break
        
        if not links:
            return "No search results found to research."
        
        # 4. Visit each source and extract key information
        findings = []
        for i, link in enumerate(links[:sources]):
            try:
                report.append(f"\n## Source {i+1}: {link['title']}\n")
                report.append(f"URL: {link['url']}\n")
                
                browser_automation("visit", link['url'])
                time.sleep(2)
                
                # Use snap to understand the page
                snap_result = browser_automation("snap")
                
                # Extract just the vision description
                vision_start = snap_result.find("Visual Description")
                if vision_start != -1:
                    vision_end = snap_result.find("\n\nInteractive Elements", vision_start)
                    if vision_end == -1:
                        vision_end = len(snap_result)
                    summary = snap_result[vision_start:vision_end]
                else:
                    # Fall back to body text
                    summary = browser_automation("get_content")[:1000]
                
                findings.append({
                    'url': link['url'],
                    'title': link['title'],
                    'summary': summary
                })
                
                report.append(f"Summary: {summary[:300]}...\n")
                
            except Exception as e:
                report.append(f"Error visiting source: {e}\n")
                continue
        
        # 5. Return findings without LLM synthesis
        report.append("\n## Findings\n")
        for i, f in enumerate(findings):
            report.append(f"### Source {i+1}: {f['title']}\nURL: {f['url']}\n{f['summary']}\n")
        
        return "\n".join(report)
        
    except Exception as e:
        return f"Research error: {e}"
