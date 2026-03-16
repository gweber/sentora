/**
 * Sentora frontend entry point.
 *
 * Bootstraps Vue 3 with Pinia (state management) and Vue Router.
 * CSS is imported here globally; component-scoped styles live in their .vue files.
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
