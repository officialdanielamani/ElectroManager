/**
 * Markdown Editor — toolbar + live preview toggle
 * Requires marked.js to be loaded before this script for preview rendering.
 *
 * Usage:
 *   initMdEditor(textareaElement)
 *   initMdEditor(textareaElement, { rows: 8 })
 */
(function () {

    var TOOLBAR = [
        { icon: 'bi-type-bold',          title: 'Bold',           wrap: ['**', '**'],     placeholder: 'bold text' },
        { icon: 'bi-type-italic',        title: 'Italic',         wrap: ['*', '*'],        placeholder: 'italic text' },
        { icon: 'bi-type-strikethrough', title: 'Strikethrough',  wrap: ['~~', '~~'],      placeholder: 'strikethrough' },
        { sep: true },
        { text: 'H1', title: 'Heading 1', linePrefix: '# ' },
        { text: 'H2', title: 'Heading 2', linePrefix: '## ' },
        { text: 'H3', title: 'Heading 3', linePrefix: '### ' },
        { sep: true },
        { icon: 'bi-code',       title: 'Inline Code', wrap: ['`', '`'],             placeholder: 'code' },
        { icon: 'bi-code-slash', title: 'Code Block',  blockWrap: ['```\n', '\n```'], placeholder: 'code here' },
        { sep: true },
        { icon: 'bi-list-ul', title: 'Unordered List', linePrefix: '- ' },
        { icon: 'bi-list-ol', title: 'Ordered List',   linePrefix: '1. ' },
        { icon: 'bi-quote',   title: 'Blockquote',     linePrefix: '> ' },
        { sep: true },
        { icon: 'bi-link',    title: 'Link',            wrap: ['[', '](url)'],        placeholder: 'link text' },
        { icon: 'bi-dash-lg', title: 'Horizontal Rule', insert: '\n\n---\n\n' },
        { icon: 'bi-table',   title: 'Table',           insert: '\n| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1   | Cell 2   |\n' },
    ];

    function wrapText(ta, before, after, placeholder) {
        var s = ta.selectionStart, e = ta.selectionEnd;
        var sel = ta.value.substring(s, e) || placeholder;
        var rep = before + sel + after;
        ta.value = ta.value.substring(0, s) + rep + ta.value.substring(e);
        if (sel === placeholder) {
            ta.setSelectionRange(s + before.length, s + before.length + sel.length);
        } else {
            ta.setSelectionRange(s, s + rep.length);
        }
        ta.focus();
        ta.dispatchEvent(new Event('input'));
    }

    function linePrefix(ta, prefix) {
        var s = ta.selectionStart;
        var lineStart = ta.value.lastIndexOf('\n', s - 1) + 1;
        if (ta.value.substring(lineStart).startsWith(prefix)) {
            // Toggle off
            ta.value = ta.value.substring(0, lineStart) + ta.value.substring(lineStart + prefix.length);
            ta.setSelectionRange(Math.max(lineStart, s - prefix.length), Math.max(lineStart, s - prefix.length));
        } else {
            ta.value = ta.value.substring(0, lineStart) + prefix + ta.value.substring(lineStart);
            ta.setSelectionRange(s + prefix.length, s + prefix.length);
        }
        ta.focus();
        ta.dispatchEvent(new Event('input'));
    }

    function blockWrap(ta, before, after, placeholder) {
        var s = ta.selectionStart, e = ta.selectionEnd;
        var sel = ta.value.substring(s, e) || placeholder;
        var rep = before + sel + after;
        ta.value = ta.value.substring(0, s) + rep + ta.value.substring(e);
        if (sel === placeholder) {
            ta.setSelectionRange(s + before.length, s + before.length + sel.length);
        }
        ta.focus();
        ta.dispatchEvent(new Event('input'));
    }

    function insertText(ta, text) {
        var s = ta.selectionStart;
        ta.value = ta.value.substring(0, s) + text + ta.value.substring(s);
        ta.setSelectionRange(s + text.length, s + text.length);
        ta.focus();
        ta.dispatchEvent(new Event('input'));
    }

    function renderMarkdown(text) {
        if (!text) return '<p class="text-muted fst-italic">Nothing to preview.</p>';
        if (typeof marked !== 'undefined') {
            try {
                return marked.parse(text, { gfm: true, breaks: true });
            } catch (e) { /* fall through */ }
        }
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\n/g, '<br>');
    }

    function makeBtn(cfg, disabled) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.title = cfg.title;
        btn.className = 'btn btn-sm btn-outline-secondary';
        if (disabled) btn.disabled = true;
        if (cfg.icon) {
            btn.innerHTML = '<i class="bi ' + cfg.icon + '"></i>';
        } else {
            btn.innerHTML = '<span class="fw-bold" style="font-size:0.78em;">' + cfg.text + '</span>';
        }
        return btn;
    }

    window.initMdEditor = function (ta, opts) {
        if (!ta || ta._mdEditorInit) return;
        ta._mdEditorInit = true;
        opts = opts || {};

        var isDisabled = ta.disabled || ta.readOnly;

        // ── Outer wrapper ──────────────────────────────────────────────
        var wrapper = document.createElement('div');
        wrapper.className = 'md-editor-wrapper border rounded overflow-hidden';
        ta.parentNode.insertBefore(wrapper, ta);

        // ── Toolbar ────────────────────────────────────────────────────
        var bar = document.createElement('div');
        bar.className = 'md-editor-toolbar d-flex flex-wrap align-items-center gap-1 px-2 py-1 border-bottom bg-light';

        var group = document.createElement('div');
        group.className = 'btn-group btn-group-sm';

        TOOLBAR.forEach(function (cfg) {
            if (cfg.sep) {
                bar.appendChild(group);
                bar.appendChild(document.createElement('div')).style.cssText = 'width:1px;background:#dee2e6;align-self:stretch;margin:2px 2px;';
                group = document.createElement('div');
                group.className = 'btn-group btn-group-sm';
                return;
            }
            var btn = makeBtn(cfg, isDisabled);
            btn.addEventListener('mousedown', function (ev) {
                ev.preventDefault(); // keep textarea focus
                if (cfg.wrap)      wrapText(ta,  cfg.wrap[0],      cfg.wrap[1],      cfg.placeholder || 'text');
                if (cfg.blockWrap) blockWrap(ta, cfg.blockWrap[0], cfg.blockWrap[1], cfg.placeholder || 'code');
                if (cfg.linePrefix) linePrefix(ta, cfg.linePrefix);
                if (cfg.insert)    insertText(ta, cfg.insert);
            });
            group.appendChild(btn);
        });
        bar.appendChild(group);

        // ── Preview toggle ─────────────────────────────────────────────
        var spacer = document.createElement('span');
        spacer.className = 'flex-fill';
        bar.appendChild(spacer);

        var prevBtn = document.createElement('button');
        prevBtn.type = 'button';
        prevBtn.className = 'btn btn-sm btn-outline-primary';
        prevBtn.innerHTML = '<i class="bi bi-eye"></i> Preview';
        prevBtn.title = 'Toggle markdown preview';
        bar.appendChild(prevBtn);

        // ── Preview pane ───────────────────────────────────────────────
        var previewPane = document.createElement('div');
        previewPane.className = 'md-editor-preview markdown-content px-3 py-2';
        previewPane.style.display = 'none';
        previewPane.style.minHeight = '100px';
        previewPane.style.overflowY = 'auto';

        // ── Assemble ───────────────────────────────────────────────────
        wrapper.appendChild(bar);

        // Move textarea into wrapper, remove its border (wrapper provides it)
        wrapper.appendChild(ta);
        ta.style.border = 'none';
        ta.style.borderRadius = '0';
        ta.style.resize = 'vertical';
        if (!ta.getAttribute('rows')) ta.setAttribute('rows', opts.rows || 6);

        wrapper.appendChild(previewPane);

        // ── Toggle logic ───────────────────────────────────────────────
        var inPreview = false;
        prevBtn.addEventListener('click', function () {
            inPreview = !inPreview;
            if (inPreview) {
                previewPane.innerHTML = renderMarkdown(ta.value);
                previewPane.style.minHeight = Math.max(100, ta.offsetHeight) + 'px';
                ta.style.display = 'none';
                previewPane.style.display = '';
                prevBtn.innerHTML = '<i class="bi bi-pencil"></i> Edit';
                prevBtn.classList.replace('btn-outline-primary', 'btn-primary');
                // disable format buttons during preview
                bar.querySelectorAll('.btn-group .btn').forEach(function (b) { b.disabled = true; });
            } else {
                previewPane.style.display = 'none';
                ta.style.display = '';
                prevBtn.innerHTML = '<i class="bi bi-eye"></i> Preview';
                prevBtn.classList.replace('btn-primary', 'btn-outline-primary');
                if (!isDisabled) {
                    bar.querySelectorAll('.btn-group .btn').forEach(function (b) { b.disabled = false; });
                }
                ta.focus();
            }
        });
    };

})();
