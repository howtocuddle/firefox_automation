return (function () {
    const result = {
        pageInfo: {},
        mainContent: '',
        interactive: {
            forms: [],
            buttons: [],
            inputs: [],
            links: { navigation: [], content: [] }
        },
        navigation: { menu: [], breadcrumbs: [] }
    };

    // === PAGE INFO ===
    result.pageInfo.title = document.title;
    result.pageInfo.url = window.location.href;
    const h1 = document.querySelector('h1');
    result.pageInfo.mainTopic = h1 ? h1.innerText.trim() : '';
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) result.pageInfo.description = metaDesc.getAttribute('content');

    // === READABILITY ALGORITHM ===
    // Find main content by analyzing text density and semantic elements
    function getTextDensity(el) {
        const text = el.innerText || '';
        const html = el.innerHTML || '';
        return text.length / (html.length + 1);
    }

    function isVisible(el) {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    // Find candidate content containers
    const candidates = [];
    const contentSelectors = [
        'main', 'article', '[role="main"]',
        '.content', '.main-content', '.post-content', '.article-content',
        '#content', '#main-content', '.entry-content'
    ];

    // Try semantic elements first
    for (const selector of contentSelectors) {
        const els = document.querySelectorAll(selector);
        for (const el of els) {
            if (isVisible(el)) {
                const text = el.innerText.trim();
                if (text.length > 200) {
                    candidates.push({
                        el: el,
                        score: text.length * getTextDensity(el),
                        text: text
                    });
                }
            }
        }
    }

    // If no semantic candidates, scan all divs/sections
    if (candidates.length === 0) {
        const divs = document.querySelectorAll('div, section');
        for (const div of divs) {
            if (isVisible(div)) {
                const text = div.innerText.trim();
                if (text.length > 300) {
                    candidates.push({
                        el: div,
                        score: text.length * getTextDensity(div),
                        text: text
                    });
                }
            }
        }
    }

    // Pick best candidate
    if (candidates.length > 0) {
        candidates.sort((a, b) => b.score - a.score);
        const mainEl = candidates[0].el;

        // Extract structured content with headings
        const contentParts = [];
        const walker = document.createTreeWalker(
            mainEl,
            NodeFilter.SHOW_ELEMENT,
            {
                acceptNode: function (node) {
                    if (!isVisible(node)) return NodeFilter.FILTER_REJECT;
                    const tag = node.tagName.toLowerCase();
                    if (['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'blockquote'].includes(tag)) {
                        return NodeFilter.FILTER_ACCEPT;
                    }
                    return NodeFilter.FILTER_SKIP;
                }
            }
        );

        let node;
        while (node = walker.nextNode()) {
            const text = node.innerText.trim();
            if (text.length > 20) {
                const tag = node.tagName.toLowerCase();
                if (tag.startsWith('h')) {
                    contentParts.push('\\n## ' + text);
                } else if (tag === 'li') {
                    contentParts.push('  • ' + text);
                } else {
                    contentParts.push(text);
                }
            }
        }

        result.mainContent = contentParts.join('\\n').substring(0, 2000);
    } else {
        // Fallback: get body text
        result.mainContent = document.body.innerText.substring(0, 2000);
    }

    // === INTERACTIVE ELEMENTS ===
    // Forms
    const forms = document.querySelectorAll('form');
    for (const form of forms) {
        if (!isVisible(form)) continue;
        const inputs = form.querySelectorAll('input, textarea, select');
        const fields = [];
        for (const input of inputs) {
            const name = input.name || input.id || input.placeholder || input.type;
            fields.push(name);
        }
        if (fields.length > 0) {
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            const action = submitBtn ? submitBtn.innerText || submitBtn.value : 'Submit';
            result.interactive.forms.push({
                action: action,
                fields: fields.join(', ')
            });
        }
    }

    // Buttons
    const buttons = document.querySelectorAll('button, [role="button"], input[type="button"], input[type="submit"]');
    for (const btn of buttons) {
        if (!isVisible(btn)) continue;
        const text = btn.innerText || btn.value || btn.getAttribute('aria-label') || '';
        if (text.trim()) {
            let selector = btn.tagName.toLowerCase();
            if (btn.id) selector += '#' + btn.id;
            else if (btn.className) {
                const classes = btn.className.split(' ').filter(c => c.length > 0);
                if (classes.length > 0) selector += '.' + classes.slice(0, 2).join('.');
            }
            result.interactive.buttons.push({
                text: text.trim().substring(0, 50),
                selector: selector
            });
        }
    }

    // Inputs (standalone)
    const inputs = document.querySelectorAll('input:not([type="hidden"]), textarea, select');
    for (const input of inputs) {
        if (!isVisible(input)) continue;
        // Skip if already in a form
        if (input.closest('form')) continue;

        const label = input.getAttribute('placeholder') || input.getAttribute('aria-label') || input.name || input.id;
        if (label) {
            let selector = input.tagName.toLowerCase();
            if (input.name) selector += `[name="${input.name}"]`;
            else if (input.id) selector += '#' + input.id;

            result.interactive.inputs.push({
                label: label.substring(0, 50),
                type: input.type || 'text',
                selector: selector
            });
        }
    }

    // Links - Navigation vs Content
    const links = document.querySelectorAll('a[href]');
    const navElements = document.querySelectorAll('nav, [role="navigation"], header, .header, .navbar, .menu');

    for (const link of links) {
        if (!isVisible(link)) continue;
        const text = link.innerText.trim();
        if (!text || text.length > 100) continue;

        const href = link.href;
        const isNav = Array.from(navElements).some(nav => nav.contains(link));

        if (isNav && result.interactive.links.navigation.length < 10) {
            result.interactive.links.navigation.push(text);
        } else if (!isNav && result.interactive.links.content.length < 10) {
            result.interactive.links.content.push({ text: text, href: href.substring(0, 80) });
        }
    }

    // === NAVIGATION ===
    // Breadcrumbs
    const breadcrumbSelectors = ['[aria-label*="breadcrumb" i]', '.breadcrumb', '.breadcrumbs', 'nav ol', 'nav ul'];
    for (const selector of breadcrumbSelectors) {
        const bc = document.querySelector(selector);
        if (bc && isVisible(bc)) {
            const items = bc.querySelectorAll('a, li');
            for (const item of items) {
                const text = item.innerText.trim();
                if (text) result.navigation.breadcrumbs.push(text);
            }
            if (result.navigation.breadcrumbs.length > 0) break;
        }
    }

    return result;
})();
