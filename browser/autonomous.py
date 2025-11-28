
"""
Autonomous Browsing Mode
Uses Gemini Vision to navigate websites and achieve goals.
"""
import time
import os
from .core import get_driver, get_context_lines, set_context_lines, get_url_log
from .dispatcher import browser_automation
from .dispatcher import browser_automation
from .helpers import handle_manual_captcha
from ..notify import send_notification

def autonomous_browser(goal: str) -> str:
    print(f"\n[Browser] Autonomous mode activated for goal: {goal}")
    
    # Ensure browser is open and ALIVE
    driver = get_driver()
    if driver:
        try:
            # Ping the driver to see if it's alive
            driver.title
        except:
            print("[Browser] Driver is stale. Restarting...")
            driver = None

    if not driver:
        # Default start page
        start_url = "https://duckduckgo.com"
        
        # Load config for default page
        try:
            # Assuming agent_config.json is in the root of the workspace (3 levels up from here)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            config_path = os.path.join(base_dir, "agent_config.json")
            
            if os.path.exists(config_path):
                import json
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    start_url = config.get("default_browser_page", start_url)
        except Exception as e:
            print(f"[Browser] Warning: Could not load default page from config: {e}")
        
        # Simple heuristic: If goal looks like a URL, start there
        if goal.startswith("http"):
            start_url = goal
            
        browser_automation("open")
        browser_automation("visit", start_url)
        time.sleep(2)
    
    # Import LLM for decision making
    try:
        from ...llm_factory import create_llm
        import json
        
        # Load agent config to get browser model
        model_name = "gemini-2.0-flash-001" # Default
        try:
            # Assuming agent_config.json is in the root of the workspace (3 levels up from here)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            config_path = os.path.join(base_dir, "agent_config.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    if "browser_model" in config:
                        model_name = config["browser_model"]
                        print(f"[Browser] Using configured browser model: {model_name}")
                    elif "vision_model" in config:
                        model_name = config["vision_model"]
                        print(f"[Browser] Using configured vision model: {model_name}")
        except Exception as e:
            print(f"[Browser] Warning: Could not load agent_config.json: {e}")

        llm = create_llm(model_name)
    except Exception as e:
        return f"Error: Could not load LLM for autonomous browsing: {e}"
    
    # PLANNING PHASE
    print("[Browser] Generating initial plan...")
    planning_prompt = f"""You are an expert web browsing agent.
Goal: "{goal}"

Create a high-level plan to achieve this goal.
Also define specific SUCCESS CRITERIA (visual changes to look for, e.g. "Play button changes to Pause", "URL contains /success").

You must respond in JSON format with two keys: "plan" and "criteria".
{{
  "plan": "1. Step one\\n2. Step two...",
  "criteria": "- Visual change 1\\n- Visual change 2..."
}}
"""

    # Initial Plan
    history = []
    try:
        plan_data = {}
        for attempt in range(2):
            response = llm.generate([{'role': 'user', 'content': planning_prompt}], temperature=0.3, max_tokens=500)
            if response:
                print(f"[Browser] Raw Planning Response: {response[:200]}...") # Debug log
                try:
                    import json
                    cleaned_response = response.strip()
                    if cleaned_response.startswith("```json"):
                        cleaned_response = cleaned_response[7:]
                    if cleaned_response.startswith("```"):
                        cleaned_response = cleaned_response[3:]
                    if cleaned_response.endswith("```"):
                        cleaned_response = cleaned_response[:-3]
                    plan_data = json.loads(cleaned_response.strip())
                    break
                except:
                    # Fallback: Try to parse text if JSON fails
                    print("[Browser] JSON parse failed, using raw text as plan.")
                    plan_data = {"plan": response.strip(), "criteria": "See plan."}
                    break
            print(f"[Browser] Planning LLM empty/invalid response (Attempt {attempt+1}/2). Retrying...")

        if plan_data:
            plan = plan_data.get("plan", "")
            criteria = plan_data.get("criteria", "")
            full_plan = f"PLAN:\n{plan}\n\nCRITERIA:\n{criteria}"
            print(f"[Browser] Initial Plan & Criteria:\n{full_plan}")
            history = [f"Plan & Criteria:\n{full_plan}"]
        else:
            print("[Browser] Planning failed: LLM returned no valid response.")
            history = ["Plan: (LLM failed to generate plan, proceeding with exploration)"]
    except Exception as e:
        print(f"[Browser] Planning failed: {e}")
        history = []
    
    # Autonomous browsing loop
    max_steps = 10
    
    for step in range(max_steps):
        # Check if agent has been stopped (e.g., via /stop command)
        # Check for stop signal file (created by agent.stop())
        # Check for stop signal file (created by agent.stop())
        stop_file = "/tmp/agent_stop_signal"
        if os.path.exists(stop_file):
            print("[Browser] Stop signal detected. Exiting autonomous mode...")
            try:
                os.remove(stop_file)
            except:
                pass
            return f"Browser automation stopped by user after {step} steps."
        
        # Browser Memory Compaction
        if len(history) > 15:
            # Smart Summarization
            print("[Browser] History getting long, compacting with summary...")
            
            # Construct prompt for summarization
            summary_prompt = f"""You are an autonomous browser agent.
Goal: "{goal}"

Current History:
{chr(10).join(history)}

Summarize the history so far. Crucially, you MUST preserve:
1. What has been FOUND or LEARNED so far (specific data, facts, URLs).
2. What was the original REQUEST/GOAL.
3. What is currently PENDING or FAILED.

Format:
[Summary: <concise summary of actions>]
[Findings: <key data found>]
[Pending: <what is left to do>]
"""
            try:
                # Use a cheap/fast call if possible, or just the main LLM
                summary = llm.generate([{'role': 'user', 'content': summary_prompt}])
                
                # Keep last 3 steps for immediate context
                recent = history[-3:]
                
                # Create new history
                history = [f"Previous Steps Summary:\n{summary}"] + recent
                print(f"[Browser] History compacted to {len(history)} items.")
            except Exception as e:
                print(f"[Browser] Smart compaction failed ({e}), falling back to simple truncation.")
                recent = history[-5:]
                compacted_msg = f"Step 1-{len(history)-5}: [Previous actions compacted. See recent history.]"
                history = [compacted_msg] + recent

        # Check for global stop signal
        if os.path.exists("/tmp/agent_stop_signal"):
            print("[Browser] Stop signal detected. Exiting autonomous mode.")
            return "Browser automation stopped by user."

        # Check for CAPTCHA before taking action/screenshot
        # check_captcha() -> Removed auto-detection. Agent must detect it.
        
        # Capture screenshot with SoM
        # Returns (path, result_string) tuple
        print(f"[Browser] Step {step}: Capturing screenshot with SoM...")
        try:
            ret = browser_automation("capture_with_som")
            print(f"[Browser] capture_with_som returned type: {type(ret)}")
            if isinstance(ret, tuple):
                print(f"[Browser] capture_with_som returned {len(ret)} items")
            else:
                print(f"[Browser] capture_with_som returned: {ret}")
            
            clean_path, screenshot_path, snap_result = ret
        except Exception as e:
            print(f"[Browser] CRITICAL ERROR calling capture_with_som: {e}")
            import traceback
            traceback.print_exc()
            return f"Error: Browser automation crashed: {e}"
        
        if not screenshot_path or not os.path.exists(screenshot_path):
             # Fallback to parsing if return value is empty (legacy support)
             for line in snap_result.split('\n'):
                if 'Marked screenshot saved:' in line:
                    screenshot_path = line.split('Marked screenshot saved:')[1].strip()
                    break
        
        if not screenshot_path:
            return f"Error: Could not get screenshot for autonomous browsing.\nStep {step + 1} snap result: {snap_result}"
        
        # Loop Detection
        loop_warning = ""
        if len(history) >= 2:
            # Extract commands from history
            commands = []
            for entry in history:
                if "Step" in entry and ":" in entry:
                    # Extract "CLICK 5" from "Step 2: CLICK 5"
                    parts = entry.split(":", 1)
                    if len(parts) > 1:
                        cmd_part = parts[1].strip()
                        # Ignore "Result:" lines if they got mixed in (though they shouldn't with this filter)
                        if not cmd_part.startswith("Result:") and not cmd_part.startswith("ERROR"):
                             commands.append(cmd_part)
            
            if len(commands) >= 3:
                # Check for triple repeat - NOTIFY USER ONLY
                if commands[-1] == commands[-2] == commands[-3]:
                    print(f"[Browser] Loop detected ({commands[-1]} x3). Notifying user.")
                    send_notification(f"Agent likely looping on command: {commands[-1]}", title="Browser Loop Detected", urgency="normal")
                    # Do NOT stop, do NOT warn agent (as per user request)

        # Get page title and URL
        try:
            page_title = driver.title
            current_url = driver.current_url
        except:
            page_title = "Unknown"
            current_url = "Unknown"

        # Always use Vision Mode
        use_vision = True
        
        # Build prompt for LLM decision making
        # Build prompt for LLM decision making
        import json
        url_log_str = json.dumps(get_url_log()[-10:], indent=2) if get_url_log() else "[]"
        
        prompt = f"""You are controlling a web browser to achieve this goal: "{goal}"
        
Current Page Title: {page_title}
Current URL: {current_url}
Current page state (Two images attached: 1. Clean view, 2. Set-of-Marks view with numbered elements):
{snap_result}

History of actions taken:
{chr(10).join(history) if history else "None yet"}
{loop_warning}

Based on the screenshot and goal, decide the NEXT SINGLE ACTION to take.

FORMAT:
You must respond in JSON format with the following keys:
{{
  "current_page_summary": "Brief summary of what is on the current page",
  "previous_action_analysis": "What did I do in the last step and did it work?",
  "next_steps_plan": "What are the immediate next steps?",
  "thought": "Concise reasoning about state and next step",
  "command": "ACTION"
}}

COMMAND FORMATS:
- GOTO <url> - Visit a URL directly.
- CLICK <number> - Click numbered element (SoM). Preferred over selectors.
- TYPE <selector>|<text>|ENTER - Type text. selector can be number or CSS. Append |ENTER to submit.
- SCROLL <page> - Page-based navigation. Use 'next', 'prev', 'page 2', 'page 3', 'top', 'bottom'.
- FIND <type>|<query> - Search page. Types: text, link, button, input, any. Returns top 20 matches.
- SELECT <number>|<option> - Select from dropdown.
- CHECKBOX <number>|check - Check/uncheck/toggle checkbox.
- RADIO <number> - Select radio button.
- DATEPICKER <number>|2025-01-01 - Set date.
- SUBMIT <number> - Submit form.
- FILL_FORM <json> - Bulk fill. e.g. {{"#user": "me", "#pass": "123"}}.
- NEW_TAB <url> / SWITCH_TAB <index> / CLOSE_TAB <index> - Manage tabs.
- OPEN_IN_NEW_TAB <number> - Open element in new tab (Ctrl+Click).
- SCROLL_ELEMENT <selector>|<dir> - Scroll specific element (up/down/left/right).
- SWITCH_FRAME <index/selector> - Switch to iframe. SWITCH_DEFAULT_CONTENT to go back.
- MEDIA <selector>|<action> - play/pause/mute/seek <sec>.
- GET_CLIPBOARD / GET_CONSOLE_LOGS / CHECK_DOWNLOADS - System tools.
- PRESS <key_combo> - Press keys (e.g., 'enter', 'escape', 'down', 'ctrl+t', 'ctrl+w').
- CAPTCHA - Report that a CAPTCHA/Cloudflare screen is blocking the view.
- DONE - Goal is complete.
- FAILED <reason> - Cannot complete goal.

STRATEGY:
1. **Research vs Task**: 
   - If **RESEARCHING**, use **TABS** to multitask if needed, but prefer single-tab navigation for simplicity. Check `URL_LOG` to avoid loops.
   - If **EXECUTING**, go directly to the goal. Use `FILL_FORM` for efficiency.
2. **Search First**: When visiting a new page, use `FIND text|<keyword>` to quickly locate info.
3. **Vision First**: Look at the screenshot. Identify the element you want. Use `CLICK <number>`.
4. **Avoid Re-Clicking**: If you clicked a toggle button (like Play/Pause) and the state changed (e.g., aria-label 'Play' -> 'Pause'), DO NOT CLICK IT AGAIN unless you want to revert the state.
5. **Efficient Navigation**: Use `SCROLL page N`. Use `SCROLL_ELEMENT` for internal scrollbars.
6. **Debugging**: If page is broken, check `GET_CONSOLE_LOGS`. If "Copy" button clicked, check `GET_CLIPBOARD`.
7. **Forms**: Use specific actions like `SELECT`, `CHECKBOX` or `FILL_FORM`.
8. **Completion**: If Success Criteria are met, output 'COMMAND: DONE'.

URL_LOG:
{url_log_str}
"""

        # Get LLM decision with vision
        try:
            # Inject URL log
            # Inject URL log
            final_prompt = prompt

            messages = [{
                'role': 'user',
                'content': {
                    'image': [clean_path, screenshot_path],
                    'text': final_prompt
                }
            }]
            
            command_line = ""
            decision = ""
            
            # JSON Mode Execution
            lines = []
            try:
                decision = llm.generate(messages, temperature=0.3, max_tokens=1000).strip()
                print(f"[Browser] LLM JSON Decision: {decision}")
                
                import json
                cleaned_decision = decision
                if cleaned_decision.startswith("```json"):
                    cleaned_decision = cleaned_decision[7:]
                if cleaned_decision.startswith("```"):
                    cleaned_decision = cleaned_decision[3:]
                if cleaned_decision.endswith("```"):
                    cleaned_decision = cleaned_decision[:-3]
                data = json.loads(cleaned_decision.strip())
                command_line = data.get("command", "").strip()
                
                # Print Reasoning
                print(f"\n[Browser Reasoning]")
                print(f"  Summary: {data.get('current_page_summary', 'N/A')}")
                print(f"  Analysis: {data.get('previous_action_analysis', 'N/A')}")
                print(f"  Plan: {data.get('next_steps_plan', 'N/A')}")
                print(f"  Thought: {data.get('thought', 'N/A')}")
                print(f"  Command: {command_line}\n")
                
                if command_line.startswith("FILL_FORM"):
                    payload = command_line[9:].strip()
                    result = browser_automation("fill_form", payload)
                    history.append(f"Step {step + 1}: {command_line}")
                    continue
                
            except Exception as e:
                print(f"[Browser] JSON Parsing Failed: {e}")
                # Fallback to text parsing if JSON fails
                lines = decision.strip().split('\n')
                for line in reversed(lines):
                    if "COMMAND:" in line:
                        command_line = line.split("COMMAND:")[1].strip()
                        break
            
        except Exception as e:
            return f"Error getting LLM decision at step {step + 1}: {e}\n\nActions taken:\n" + "\n".join(history)
        
        if not command_line:
             # If still no command, try to infer from the whole text if it's short
             if len(decision) < 50 and any(v in decision.upper() for v in ["CLICK", "TYPE", "GOTO"]):
                 command_line = decision.strip()
             else:
                 print(f"[Browser] Could not parse command from: {decision}")
                 # Don't fail immediately, maybe just scroll or wait?
                 # But better to return error so loop detection catches it
                 history.append(f"Step {step + 1}: ERROR - Could not parse command from LLM response.")
                 continue
        
        for line in lines:
            line = line.strip()
            if line.startswith("THOUGHT:"):
                print(f"[Browser] Thought: {line[8:].strip()}")
            elif line.startswith("COMMAND:"):
                command_line = line[8:].strip()
                break
            # Fallback for legacy/single-line responses
            elif any(line.upper().startswith(p) for p in ["GOTO", "CLICK", "TYPE", "SEARCH", "SCROLL", "DONE", "FAILED", "RIGHT_CLICK", "FIND", "PRESS", "FOCUS", "QUICK_FIND", "QUICK_LINK", "CAPTCHA"]):
                command_line = line
                break
        
        if not command_line:
            print(f"[Browser] Could not parse command from: {decision}")
            history.append(f"Step {step + 1}: ERROR - Could not parse command")
            continue

        decision_upper = command_line.upper().strip()
        
        if decision_upper.startswith("DONE"):
            print("[Browser] Goal achieved!")
            send_notification(f"Browser Goal Achieved: {goal}", title="Browser Agent", urgency="normal")
            
            # Final Summary Generation
            summary_prompt = f"""You have completed the goal: "{goal}"
            
            History of actions:
            {chr(10).join(history)}
            
            Final Page State:
            {snap_result}
            
            Please provide a comprehensive summary of the task.
            Include:
            1. Task Completion Status (Success/Partial Success)
            2. Key Findings (data, facts, URLs found)
            3. Summary of actions taken
            
            Format:
            TASK_COMPLETION: <status>
            SUMMARY: <summary>
            FINDINGS: <findings>
            """
            try:
                final_summary = llm.generate([{'role': 'user', 'content': summary_prompt}], temperature=0.3)
            except:
                final_summary = "Task completed successfully."
                
            return final_summary
        
        elif decision_upper.startswith("CAPTCHA"):
            print("[Browser] Agent detected CAPTCHA. Triggering manual resolution...")
            history.append(f"Step {step + 1}: CAPTCHA detected")
            handle_manual_captcha()
            # After return, we assume it's resolved or timed out
            history.append("Result: Manual CAPTCHA resolution attempted.")
            time.sleep(2)

        elif decision_upper.startswith("FAILED"):
            reason = command_line.split("FAILED", 1)[1].strip() if "FAILED" in command_line else "Unknown"
            print(f"[Browser] Failed: {reason}")
            send_notification(f"Browser Goal Failed: {reason}", title="Browser Agent", urgency="critical")
            return f"Failed to achieve goal: {reason}\n\nActions taken:\n" + "\n".join(history)
        
        elif decision_upper.startswith("GOTO"):
            # Extract URL
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid GOTO format")
                continue
            
            url = parts[1].strip()
            history.append(f"Step {step + 1}: GOTO {url}")
            result = browser_automation("visit", url)
            print(f"[Browser] Goto result: {result}")
            history.append(f"Result: {result}")
            time.sleep(2)

        elif decision_upper.startswith("FIND"):
            # Extract text
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid FIND format")
                continue
            
            text = parts[1].strip()
            history.append(f"Step {step + 1}: FIND {text}")
            result = browser_automation("find_element", text)
            print(f"[Browser] Find result: {result}")
            
            # CRITICAL: Add result to history so LLM knows what was found
            history.append(f"Result: {result}")
            
            # Don't sleep too long for find, it's fast
            time.sleep(0.5)

        elif decision_upper.startswith("PRESS"):
            # Extract key combo
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid PRESS format")
                continue
            
            keys = parts[1].strip()
            history.append(f"Step {step + 1}: PRESS {keys}")
            result = browser_automation("press_key", keys)
            print(f"[Browser] Press result: {result}")
            history.append(f"Result: {result}")
            time.sleep(1)

        elif decision_upper.startswith("QUICK_FIND"):
            # Extract text
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid QUICK_FIND format")
                continue
            
            text = parts[1].strip()
            history.append(f"Step {step + 1}: QUICK_FIND {text}")
            result = browser_automation("quick_find", {"text": text})
            print(f"[Browser] Quick Find result: {result}")
            history.append(f"Result: {result}")
            time.sleep(1)

        elif decision_upper.startswith("QUICK_LINK"):
            # Extract text
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid QUICK_LINK format")
                continue
            
            text = parts[1].strip()
            history.append(f"Step {step + 1}: QUICK_LINK {text}")
            # Call dedicated quick_link action
            result = browser_automation("quick_link", {"text": text})
            print(f"[Browser] Quick Link result: {result}")
            history.append(f"Result: {result}")
            time.sleep(1)
        
        elif decision_upper.startswith("FOCUS"):
            # Extract selector
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid FOCUS format")
                continue
            
            target = parts[1].strip()
            history.append(f"Step {step + 1}: FOCUS {target}")
            result = browser_automation("focus", target)
            print(f"[Browser] Focus result: {result}")
            history.append(f"Result: {result}")
            time.sleep(0.5)

        elif decision_upper.startswith("RIGHT_CLICK"):
            # Extract number
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid RIGHT_CLICK format")
                continue
            
            target = parts[1].strip()
            history.append(f"Step {step + 1}: RIGHT_CLICK {target}")
            result = browser_automation("right_click", target)
            print(f"[Browser] Right Click result: {result}")
            history.append(f"Result: {result}")
            time.sleep(1)

        elif decision_upper.startswith("OPEN_IN_NEW_TAB"):
            # Extract number
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid OPEN_IN_NEW_TAB format")
                continue
            
            target = parts[1].strip()
            history.append(f"Step {step + 1}: OPEN_IN_NEW_TAB {target}")
            result = browser_automation("open_in_new_tab", target)
            print(f"[Browser] Open in New Tab result: {result}")
            history.append(f"Result: {result}")
            time.sleep(2)

        elif decision_upper.startswith("CLICK"):
            # Extract number
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid CLICK format")
                continue
            
            target = parts[1].strip()
            
            # STATE VERIFICATION: Capture element state BEFORE click
            element_before = None
            url_before = None
            try:
                from . import core
                if get_driver():
                    url_before = get_driver().current_url
                
                if hasattr(core, '_element_map') and core._element_map:
                    elem_id = int(target)
                    if elem_id in core._element_map:
                        element_before = core._element_map[elem_id].copy()
            except:
                pass
            
            history.append(f"Step {step + 1}: CLICK {target}")
            result = browser_automation("click", target)
            print(f"[Browser] Click result: {result}")
            history.append(f"Result: {result}")
            time.sleep(3)  # Wait for UI to update
            
            # STATE VERIFICATION: Re-capture and compare
            if element_before:
                try:
                    # Re-capture element map and current URL
                    _, _, _ = browser_automation("capture_with_som")
                    url_after = get_driver().current_url if get_driver() else None
                    
                    # Check if element state changed or URL changed
                    if hasattr(core, '_element_map') and core._element_map:
                        if elem_id in core._element_map:
                            element_after = core._element_map[elem_id]
                            
                            text_before = element_before.get('text', '').strip()
                            text_after = element_after.get('text', '').strip()
                            
                            if text_before != text_after:
                                verification_msg = f"VERIFICATION: Element [{elem_id}] content changed. Action likely successful. [SUCCESS]"
                            elif url_before and url_after and url_before != url_after:
                                verification_msg = f"VERIFICATION: URL changed from ...{url_before[-20:]} to ...{url_after[-20:]}. Action likely successful. [SUCCESS]"
                            else:
                                verification_msg = f"VERIFICATION: Element [{elem_id}] unchanged and URL did not change. Action may have failed. [FAILED]"
                        else:
                            # Element disappeared (might mean navigation or dialog closed)
                            verification_msg = f"VERIFICATION: Element [{elem_id}] no longer visible (page changed or element removed). [SUCCESS]"
                            history.append(verification_msg)
                except Exception as e:
                    print(f"[Browser] Verification failed: {e}")
        
        elif decision_upper.startswith("TYPE"):
            # Extract selector|text
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid TYPE format")
                continue
            
            payload = parts[1].strip()
            history.append(f"Step {step + 1}: TYPE {payload}")
            result = browser_automation("type", payload)
            print(f"[Browser] Type result: {result}")
            history.append(f"Result: {result}")
            time.sleep(1)
        
        elif decision_upper.startswith("SEARCH"):
            # Extract query
            parts = command_line.split(None, 1)
            if len(parts) < 2:
                history.append(f"Step {step + 1}: ERROR - Invalid SEARCH format")
                continue
            
            query = parts[1].strip()
            history.append(f"Step {step + 1}: SEARCH {query}")
            result = browser_automation("search", query)
            print(f"[Browser] Search result: {result}")
            history.append(f"Result: {result}")
            time.sleep(2)
        
        elif decision_upper.startswith("SCROLL"):
            history.append(f"Step {step + 1}: SCROLL")
            result = browser_automation("scroll")
            history.append(f"Result: {result}")
            time.sleep(1)
        
        else:
            print(f"[Browser] Unknown decision format: {decision}")
            history.append(f"Step {step + 1}: ERROR - Unknown action '{decision}'")
            continue
        
        # Update context lines for status bar
        total_lines = sum(len(entry.split('\n')) for entry in history)
        set_context_lines(total_lines)
    
    # Max steps reached
    final_snap = browser_automation("snap")
    return f"Reached max steps ({max_steps}) without completing goal: {goal}\n\nActions taken:\n" + "\n".join(history) + f"\n\nFinal state:\n{final_snap}"
