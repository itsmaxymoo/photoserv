import Alpine from 'alpinejs'
import sort from '@alpinejs/sort'
import persist from '@alpinejs/persist'
import './json-editor.js'
import L from 'leaflet'
 
Alpine.plugin(sort)
Alpine.plugin(persist)

window.Alpine = Alpine
window.htmx = require('htmx.org');

document.body.addEventListener('htmx:configRequest', (event) => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
    if (csrfToken) {
        event.detail.headers['X-CSRFToken'] = csrfToken
    }
})

document.body.addEventListener('htmx:afterSwap', (event) => {
    Alpine.initTree(event.detail.target)
})

Alpine.start()
