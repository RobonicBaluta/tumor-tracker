import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import { i18n } from './i18n'
import { vTooltip } from './directives/tooltip'

createApp(App).use(i18n).directive('tooltip', vTooltip).mount('#app')
