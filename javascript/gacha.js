/**
 * Booru Tags Gacha - Interactive UI & Theme Helper
 * - Interactive tag chips (Click: Copy, Shift+Click: Add to Include, Alt+Click: Add to Prompt)
 * - Toast notification feedback
 * - Safe theme detection for Lobe Theme Neo & Gradio 4
 */

(function () {
    let toastTimeout = null;

    function showGachaToast(message, icon) {
        try {
            let toast = document.getElementById('gacha_toast');
            if (!toast) {
                toast = document.createElement('div');
                toast.id = 'gacha_toast';
                toast.className = 'gacha-toast';
                document.body.appendChild(toast);
            }

            toast.innerHTML = (icon ? `<span>${icon}</span> ` : '') + `<span>${message}</span>`;
            toast.classList.add('show');

            if (toastTimeout) {
                clearTimeout(toastTimeout);
            }
            toastTimeout = setTimeout(function () {
                toast.classList.remove('show');
            }, 1800);
        } catch (e) {
            // Fail gracefully
        }
    }

    function getActivePromptTextarea() {
        const root = typeof gradioApp === 'function' ? gradioApp() : document;
        const txt2img = root.querySelector('#txt2img_prompt textarea');
        const img2img = root.querySelector('#img2img_prompt textarea');
        const txt2imgTab = root.querySelector('#tab_txt2img');
        if (txt2imgTab && txt2imgTab.style.display !== 'none' && txt2img) {
            return txt2img;
        }
        const img2imgTab = root.querySelector('#tab_img2img');
        if (img2imgTab && img2imgTab.style.display !== 'none' && img2img) {
            return img2img;
        }
        return txt2img || img2img;
    }

    function updateComponentInput(element, value) {
        if (!element) return;
        element.value = value;
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        if (typeof updateInput === 'function') {
            try {
                updateInput(element);
            } catch (e) {}
        }
    }

    function setupTagChipsInteraction() {
        document.addEventListener('click', function (e) {
            const chip = e.target.closest('.gacha-chip');
            if (!chip) return;

            const tag = chip.getAttribute('data-tag') || chip.textContent.trim().replace(/\s+/g, '_');
            if (!tag) return;

            // Shift + Click: Add to Include Tags
            if (e.shiftKey) {
                e.preventDefault();
                e.stopPropagation();
                const container = chip.closest('.booru-gacha-container') || document;
                const textareas = container.querySelectorAll('textarea');
                let includeBox = null;
                textareas.forEach(function (ta) {
                    if (ta.placeholder && ta.placeholder.includes('1girl') || (ta.id && ta.id.includes('include'))) {
                        includeBox = ta;
                    }
                });
                if (!includeBox && textareas.length > 0) {
                    includeBox = textareas[0];
                }

                if (includeBox) {
                    const cur = includeBox.value.trim();
                    const nextVal = cur ? `${cur}, ${tag}` : tag;
                    updateComponentInput(includeBox, nextVal);
                    showGachaToast(`Include: +${tag}`, '➕');
                }
                return;
            }

            // Alt + Click: Add to Active Prompt
            if (e.altKey) {
                e.preventDefault();
                e.stopPropagation();
                const promptTa = getActivePromptTextarea();
                if (promptTa) {
                    const cur = promptTa.value.trim();
                    const nextVal = cur ? `${cur}, ${tag}` : tag;
                    updateComponentInput(promptTa, nextVal);
                    showGachaToast(`Prompt: +${tag}`, '✨');
                }
                return;
            }

            // Standard Click: Copy to clipboard
            e.preventDefault();
            e.stopPropagation();
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(tag).then(function () {
                    showGachaToast(`Copied: ${tag}`, '📋');
                }).catch(function () {
                    showGachaToast(`Copied: ${tag}`, '📋');
                });
            } else {
                showGachaToast(`Copied: ${tag}`, '📋');
            }
        });
    }

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

    function init() {
        detectLobeTheme();
        setupTagChipsInteraction();
    }

    if (typeof onUiLoaded === 'function') {
        onUiLoaded(init);
    } else {
        window.addEventListener('DOMContentLoaded', init, { once: true });
    }
})();
