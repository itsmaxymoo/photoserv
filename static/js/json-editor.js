/**
 * CodeMirror 6 JSON Editor
 * Enhances textarea fields with JSON syntax highlighting and validation
 */

import { EditorView, basicSetup } from 'codemirror';
import { EditorState } from '@codemirror/state';
import { json } from '@codemirror/lang-json';

/**
 * Initialize CodeMirror for a textarea element
 * @param {HTMLTextAreaElement} textarea - The textarea to enhance
 * @returns {EditorView} The CodeMirror editor instance
 */
export function initJsonEditor(textarea) {
    if (!textarea) return null;
    
    // Skip if already initialized
    if (textarea.dataset.codemirrorInitialized === 'true') {
        return null;
    }
    
    // Mark as initialized
    textarea.dataset.codemirrorInitialized = 'true';
    
    // Hide the original textarea
    textarea.style.display = 'none';
    
    // Create a container for CodeMirror
    const editorContainer = document.createElement('div');
    editorContainer.className = 'codemirror-json-editor';
    textarea.parentNode.insertBefore(editorContainer, textarea.nextSibling);
    
    // Get initial value from textarea
    const initialValue = textarea.value || '';
    
    // Create CodeMirror editor
    const editor = new EditorView({
        state: EditorState.create({
            doc: initialValue,
            extensions: [
                basicSetup,
                json(),
                EditorView.updateListener.of((update) => {
                    if (update.docChanged) {
                        // Sync changes back to the textarea
                        textarea.value = update.state.doc.toString();
                        // Trigger change event for form validation
                        textarea.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }),
            ],
        }),
        parent: editorContainer,
    });
    
    return editor;
}

/**
 * Initialize all JSON editor textareas on the page
 * Looks for textareas with data-json-editor attribute
 */
export function initAllJsonEditors() {
    const textareas = document.querySelectorAll('textarea[data-json-editor]');
    const editors = [];
    
    textareas.forEach(textarea => {
        const editor = initJsonEditor(textarea);
        if (editor) {
            editors.push(editor);
        }
    });
    
    return editors;
}

// Auto-initialize on DOMContentLoaded
if (typeof window !== 'undefined') {
    // Use a flag to ensure we only initialize once
    let initialized = false;
    
    const init = () => {
        if (initialized) return;
        initialized = true;
        initAllJsonEditors();
    };
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}
