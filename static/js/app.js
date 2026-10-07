import Alpine from 'alpinejs'
import sort from '@alpinejs/sort'
import persist from '@alpinejs/persist'
import './json-editor.js'
import L from 'leaflet'
 
Alpine.plugin(sort)
Alpine.plugin(persist)

window.Alpine = Alpine

Alpine.start()
