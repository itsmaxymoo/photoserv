import Alpine from 'alpinejs'
import sort from '@alpinejs/sort'
// Import but don't call - it auto-initializes on DOMContentLoaded
import './json-editor.js'
 
Alpine.plugin(sort)

window.Alpine = Alpine

Alpine.start()
