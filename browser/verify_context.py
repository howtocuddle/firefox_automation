
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.tools.browser.interface import browser
from src.tools.browser import autonomous

def test_context_transfer():
    print("Testing Context Transfer...")
    
    # Mock autonomous_browser to check arguments
    with patch('src.tools.browser.interface.autonomous_browser') as mock_auto:
        mock_auto.return_value = "Mock Success"
        
        test_context = "SYSTEM PROMPT: You are a helpful agent."
        browser("Test Goal", context=test_context)
        
        # Verify call args
        args, kwargs = mock_auto.call_args
        if kwargs.get('context') == test_context:
            print("PASS: Context passed to autonomous_browser.")
        else:
            print(f"FAIL: Context mismatch. Got: {kwargs.get('context')}")

def test_notification_trigger():
    print("\nTesting Notification Trigger...")
    
    # Mock send_notification
    with patch('src.tools.browser.autonomous.send_notification') as mock_notify:
        # Mock dependencies to avoid real browser/LLM
        with patch('src.tools.browser.autonomous.get_driver') as mock_driver:
            mock_driver.return_value = MagicMock()
            
            with patch('src.tools.browser.autonomous.browser_automation') as mock_ba:
                mock_ba.return_value = "Mock Result"
                
                # Mock LLM to return DONE
                with patch('src.llm_gemini.GeminiLLM') as MockLLM:
                    instance = MockLLM.return_value
                    instance.generate.return_value = "COMMAND: DONE"
                    
                    # Run autonomous browser
                    autonomous.autonomous_browser("Test Goal", context="Test Context")
                    
                    # Verify notification
                    if mock_notify.called:
                        print("PASS: Notification sent on DONE.")
                    else:
                        print("FAIL: Notification NOT sent.")

if __name__ == "__main__":
    test_context_transfer()
    test_notification_trigger()
