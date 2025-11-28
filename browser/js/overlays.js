// overlays.js - Remove annoying DOM elements

(function () {
    const annoyanceSelectors = [
        // Cookie banners (generic)
        '#onetrust-banner-sdk',
        '.onetrust-banner-sdk',
        '#cookie-banner',
        '.cookie-banner',
        '[id*="cookie"]',
        '[class*="cookie"]',
        '[id*="consent"]',
        '[class*="consent"]',
        '[id*="gdpr"]',
        '[class*="gdpr"]',

        // Sign-in prompts / Overlays
        '[id*="signin"]',
        '[class*="signin"]',
        '[id*="signup"]',
        '[class*="signup"]',
        '[id*="subscribe"]',
        '[class*="subscribe"]',
        '[id*="newsletter"]',
        '[class*="newsletter"]',
        '[class*="overlay"]',
        '[id*="overlay"]',
        '[class*="modal"]',
        '[id*="modal"]',
        '[class*="popup"]',
        '[id*="popup"]',

        // Specifics
        '#google-one-tap-container', // Google One Tap
        'div#credential_picker_container', // Google Sign-in
        'iframe[src*="google.com/gsi"]', // Google One Tap Iframe
        'iframe[id*="google-one-tap"]',
        '.fc-consent-root', // Funding Choices
        '.evidon-banner',
        '#usercentrics-root',
        '#cmp-root',
        '#CybotCookiebotDialog',
        '#onetrust-consent-sdk',
        '.tp-modal', // Piano / Tinypass
        '.tp-backdrop',
        '#sp-message-container', // Sourcepoint
        '.sp-message-open'
    ];

    let removedCount = 0;

    function removeAnnoyances() {
        annoyanceSelectors.forEach(selector => {
            try {
                const elements = document.querySelectorAll(selector);
                elements.forEach(el => {
                    // Safety check: Don't remove small buttons or inputs, mostly large containers
                    // Or check if it covers a significant portion of the screen
                    // For now, be aggressive as per user request

                    // Filter out likely false positives (e.g. "cookie-header" in a doc)
                    // Check z-index? Fixed position?
                    const style = window.getComputedStyle(el);
                    if (style.position === 'fixed' || style.position === 'absolute' || style.position === 'sticky' || style.zIndex > 100) {
                        el.remove();
                        removedCount++;
                    }
                });
            } catch (e) {
                // Ignore invalid selectors
            }
        });

        // Also enable scrolling if it was disabled by a modal
        document.body.style.overflow = 'auto';
        document.documentElement.style.overflow = 'auto';
    }

    // Run immediately
    removeAnnoyances();

    // And observe for new ones
    const observer = new MutationObserver((mutations) => {
        removeAnnoyances();
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    console.log(`[Agent] Removed ${removedCount} annoyance elements.`);
})();
