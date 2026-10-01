import { createRouter, createWebHistory } from 'vue-router'
import HubView from './views/HubView.vue'
import PantryView from './views/PantryView.vue'
import ProfileView from './views/ProfileView.vue'
import SettingsView from './views/SettingsView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'hub', component: HubView },
    { path: '/pantry', name: 'pantry', component: PantryView },
    { path: '/profile', name: 'profile', component: ProfileView },
    { path: '/settings', name: 'settings', component: SettingsView },
  ],
})
