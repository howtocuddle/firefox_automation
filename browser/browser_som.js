// Remove existing markers if any
var existing = document.getElementById('agent-som-container');
if (existing) existing.remove();

var items = [];

var container = document.createElement('div');
container.id = 'agent-som-container';
container.style.position = 'absolute';
container.style.top = '0';
container.style.left = '0';
container.style.width = '100%';
container.style.height = '100%';
container.style.zIndex = '2147483647'; //Max Z-Index
container.style.pointerEvents = 'none'; // Click through
document.body.appendChild(container);

var counter = 0;
var processed = new Set();
var processedCount = 0;
var filteredCount = 0;
var candidateCount = 0;

function getSelector(el) {
    var selector = el.tagName.toLowerCase();
    if (el.id) selector += '#' + el.id;
    else if (el.className && typeof el.className === 'string') {
        var classes = el.className.split(' ').filter(c => c.length > 0 && !c.includes(':'));
        if (classes.length > 0) selector += '.' + classes.slice(0, 2).join('.');
    }
    return selector;
}

function collectElements(root, offset = { x: 0, y: 0 }, path = []) {
    // 1. Semantic Elements
    var semantic = root.querySelectorAll('a, button, input, textarea, form, label, [role="button"], [role="link"], [role="search"], [role="searchbox"], [onclick], select, svg[role="button"], svg[aria-label], [tabindex]:not([tabindex="-1"]), [data-testid], [contenteditable], [role="textbox"]');
    var semantic = root.querySelectorAll('a, button, input, textarea, [role="button"], [role="link"], [onclick], select, svg[role="button"], svg[aria-label], [tabindex]:not([tabindex="-1"]), [data-testid], [contenteditable], [role="textbox"]');
    var candidates = Array.from(semantic);
    candidateCount += candidates.length;

    // 2. Cursor Pointer Elements
    var potential = root.querySelectorAll('div, span, img, li, h1, h2, h3, h4, h5, h6, i, p');
    potential.forEach(el => {
        if (!processed.has(el)) {
            var style = window.getComputedStyle(el);
            if (style.cursor === 'pointer') {
                candidates.push(el);
                candidateCount++;
            }
        }
    });

    // 3. Iframes (Recurse)
    var iframes = root.querySelectorAll('iframe, frame');
    iframes.forEach(iframe => {
        try {
            var rect = iframe.getBoundingClientRect();
            // Skip invisible iframes
            if (rect.width < 10 || rect.height < 10) return;

            var doc = iframe.contentDocument;
            if (doc) {
                var newOffset = {
                    x: offset.x + rect.left,
                    y: offset.y + rect.top
                };
                var iframeSelector = getSelector(iframe);
                // Add src to selector for robustness if available
                // if (iframe.src) iframeSelector += `[src="${iframe.src}"]`; 
                // Actually, src might be too long or dynamic. Let's stick to simple selector + index if needed.
                // But actions.py needs to find it.

                collectElements(doc, newOffset, [...path, iframeSelector]);
            }
        } catch (e) {
            // Cross-origin access denied
        }
    });

    // 4. Shadow Roots (Recurse)
    // We need to walk ALL elements to find shadow roots, querySelectorAll doesn't find shadow roots directly
    var allEls = root.querySelectorAll('*');
    allEls.forEach(el => {
        if (el.shadowRoot) {
            if (el.shadowRoot) {
                var hostSelector = getSelector(el);
                // Shadow DOM elements return viewport-relative coordinates (unlike iframes),
                // so we do NOT add the host's offset. We pass the current offset (from parent iframes) unchanged.
                collectElements(el.shadowRoot, offset, [...path, hostSelector + " >> shadow-root"]);
            }
        }
    });

    for (var i = 0; i < candidates.length; i++) {
        var el = candidates[i];
        if (processed.has(el)) continue;
        processed.add(el);
        processedCount++;

        var rect = el.getBoundingClientRect();

        // Filter invisible or tiny elements
        // EXCEPTION: Always include search-related inputs even if they seem small/weird, as long as they are not display:none
        var isSearch = (el.tagName === 'INPUT' && (el.type === 'search' || el.name === 'q' || (el.id && el.id.toLowerCase().includes('search')) || (el.className && typeof el.className === 'string' && el.className.toLowerCase().includes('search'))));

        if (!isSearch) {
            if (rect.width < 15 || rect.height < 15 || window.getComputedStyle(el).visibility === 'hidden' || window.getComputedStyle(el).display === 'none') {
                filteredCount++;
                continue;
            }
        } else {
            // For search inputs, only filter if strictly display:none
            if (window.getComputedStyle(el).display === 'none') {
                filteredCount++;
                continue;
            }
        }

        // Filter empty non-semantic elements
        var isSemantic = ['BUTTON', 'INPUT', 'A', 'TEXTAREA', 'SELECT', 'SVG'].includes(el.tagName);
        if (!isSemantic) {
            var txt = el.innerText || el.textContent || '';
            var hasContent = txt.trim().length > 0 || el.getAttribute('aria-label') || el.getAttribute('title') || el.tagName === 'IMG';
            if (!hasContent) {
                filteredCount++;
                continue;
            }
        }

        // Calculate absolute position including offsets from parent frames
        var absLeft = rect.left + offset.x;
        var absTop = rect.top + offset.y;

        // Special handling for tiny search inputs: borrow rect from visible parent
        if (isSearch && (rect.width < 5 || rect.height < 5)) {
            var parent = el.parentElement;
            while (parent && parent !== document.body) {
                var pRect = parent.getBoundingClientRect();
                if (pRect.width >= 20 && pRect.height >= 20 && window.getComputedStyle(parent).display !== 'none') {
                    // Use parent's rect for coordinates/marker
                    rect = pRect;
                    absLeft = rect.left + offset.x;
                    absTop = rect.top + offset.y;
                    break;
                }
                parent = parent.parentElement;
            }
        }

        // Filter off-screen elements (Viewport check relative to main window)
        var viewportWidth = window.innerWidth || document.documentElement.clientWidth;
        var viewportHeight = window.innerHeight || document.documentElement.clientHeight;

        // Relaxed filtering: Allow elements slightly off-screen (e.g. sticky headers)
        // absTop can be slightly negative if the element is fixed/sticky at the top
        if (absTop > viewportHeight || absLeft > viewportWidth || absTop + rect.height < -50 || absLeft + rect.width < 0) {
            filteredCount++;
            continue;
        }

        if (counter > 300) break;

        var text = el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('alt') || '';
        text = text.trim().substring(0, 100);

        var marker = document.createElement('div');
        marker.innerText = counter;
        marker.style.position = 'absolute';

        // CENTER the marker on the element instead of top-left
        // This improves accuracy when sending dual images (clean + marked)
        var centerX = absLeft + rect.width / 2;
        var centerY = absTop + rect.height / 2;

        // Approximate marker dimensions (14px font + 4px padding + 4px border ≈ 30px width, 22px height)
        var markerWidth = 30;
        var markerHeight = 22;

        marker.style.left = (centerX - markerWidth / 2 + window.scrollX) + 'px';
        marker.style.top = (centerY - markerHeight / 2 + window.scrollY) + 'px';
        marker.style.backgroundColor = '#FFD700'; // Gold
        marker.style.color = 'black';
        marker.style.border = '2px solid #000';
        marker.style.borderRadius = '4px';
        marker.style.padding = '2px 5px';
        marker.style.fontSize = '14px';
        marker.style.fontWeight = 'bold';
        marker.style.fontFamily = 'monospace';
        marker.style.boxShadow = '0px 2px 4px rgba(0,0,0,0.5)';
        marker.style.zIndex = '2147483647';
        marker.style.minWidth = '20px';
        marker.style.textAlign = 'center';

        container.appendChild(marker);

        // Store metadata
        var localSelector = getSelector(el);
        var fullPath = [...path, localSelector].join(' >> ');

        items.push({
            id: counter,
            tag: el.tagName,
            href: el.href || '',
            rect: {
                left: absLeft,
                top: absTop,
                right: absLeft + rect.width,
                bottom: absTop + rect.height,
                width: rect.width,
                height: rect.height
            },
            text: text,
            selector: fullPath,
            center: {
                x: Math.round(absLeft + rect.width / 2),
                y: Math.round(absTop + rect.height / 2)
            },
            // For verification: store viewport-relative coords too
            viewportCoords: {
                left: Math.round(rect.left),
                top: Math.round(rect.top),
                centerX: Math.round(rect.left + rect.width / 2),
                centerY: Math.round(rect.top + rect.height / 2)
            }
        });
        counter++;
    }
}

collectElements(document);

return {
    items: items,
    debug: {
        total: counter,
        viewport: (window.innerWidth || document.documentElement.clientWidth) + 'x' + (window.innerHeight || document.documentElement.clientHeight),
        totalCandidates: candidateCount,
        processed: processedCount,
        filtered: filteredCount
    }
};
