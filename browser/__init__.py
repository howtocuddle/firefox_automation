"""
Browser Tool Package
"""
from .core import open_browser, close_browser, get_driver, force_cleanup
from .dispatcher import browser_automation
from .autonomous import autonomous_browser
from .research import research
from .interface import browser
from .helpers import handle_manual_captcha
