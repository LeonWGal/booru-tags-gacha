/**
 * Booru Tags Gacha - UI Theme Helper
 * Safe, non-blocking theme detection for Lobe Theme Neo.
 */

(function () {
    function detectLobeTheme() {
        try {
            const hasLobe = !!(
                document.getElementById('lobe-header') ||
                document.querySelector('.lobe-theme') ||
                document.querySelector('.ant-layout') ||
                document.documentElement.hasAttribute('data-theme') ||
                document.body.classList.contains('lobe-theme')
            );

            const containers = document.querySelectorAll('.booru-gacha-container');
            containers.forEach(function (container) {
                if (hasLobe && !container.classList.contains('is-lobe-theme')) {
                    container.classList.add('is-lobe-theme');
                } else if (!hasLobe && container.classList.contains('is-lobe-theme')) {
                    container.classList.remove('is-lobe-theme');
                }
            });
        } catch (e) {
            // Fail gracefully without interrupting WebUI
        }
    }

    if (typeof onUiLoaded === 'function') {
        onUiLoaded(detectLobeTheme);
    } else {
        window.addEventListener('DOMContentLoaded', detectLobeTheme, { once: true });
    }
})();
