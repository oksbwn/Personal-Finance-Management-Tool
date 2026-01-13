<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter, useRoute } from 'vue-router'
import ToastContainer from '@/components/ToastContainer.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

// Sidebar State
const isSidebarCollapsed = ref(true)
function toggleSidebar() { isSidebarCollapsed.value = !isSidebarCollapsed.value }

// User Menu State
const showUserMenu = ref(false)
const showAvatarModal = ref(false)
const selectedAvatar = ref(localStorage.getItem('user_avatar') || 'default')
const userMenuContainer = ref<HTMLElement | null>(null)

const AVATARS = {
    'default': '👤',
    'male': '👨‍💼',
    'female': '👩‍💼',
    'kid': '🧒'
}

function toggleUserMenu() { showUserMenu.value = !showUserMenu.value }

function selectAvatar(type: string) {
    selectedAvatar.value = type
    localStorage.setItem('user_avatar', type)
    showAvatarModal.value = false
    showUserMenu.value = false
}

function logout() {
    auth.logout()
    router.push('/login')
}

// Close menu when clicking outside
function handleClickOutside(event: MouseEvent) {
    if (userMenuContainer.value && !userMenuContainer.value.contains(event.target as Node)) {
        showUserMenu.value = false
    }
}

onMounted(() => {
    document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
    document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
    <div class="app-layout">
        <!-- Global Top Header -->
        <header class="global-header glass">
            <div class="header-left">
                <div class="brand">
                    <span class="logo-icon">✨</span>
                    <span class="brand-text">Family Finance</span>
                    <span class="brand-tagline">Whole family finance</span>
                </div>
            </div>
            
            <div class="header-center">
                <div class="search-bar">
                    <input type="text" placeholder="Search transactions..." />
                </div>
            </div>

            <div class="header-right">
                <div class="notification-trigger">
                    <div class="notification-bell">🔔</div>
                </div>

                <div class="user-menu-container" ref="userMenuContainer">
                    <div class="user-menu-trigger" @click.stop="toggleUserMenu">
                        <div class="user-avatar">
                            {{ AVATARS[selectedAvatar as keyof typeof AVATARS] }}
                        </div>
                    </div>

                    <!-- Dropdown Menu -->
                    <transition name="fade">
                        <div v-if="showUserMenu" class="dropdown-menu">
                            <div class="dropdown-header">
                                <div class="user-name">{{ auth.user?.email }}</div>
                                <div class="user-role">Family Member</div>
                            </div>
                            <div class="dropdown-divider"></div>
                            <button class="dropdown-item" @click="showAvatarModal = true">
                                🎨 Change Avatar
                            </button>
                            <button class="dropdown-item danger" @click="logout">
                                🚪 Logout
                            </button>
                        </div>
                    </transition>
                </div>
            </div>
        </header>

        <!-- Main Body -->
        <div class="app-body">
            <aside class="sidebar" :class="{ 'collapsed': isSidebarCollapsed }">
                <div class="sidebar-toggle-area">
                    <button class="collapse-btn" @click="toggleSidebar">
                        {{ isSidebarCollapsed ? '→' : '←' }}
                    </button>
                </div>

                <nav class="sidebar-nav">
                    <router-link to="/" class="nav-item" active-class="active">
                        <span class="icon">📊</span>
                        <span class="label" v-if="!isSidebarCollapsed">Dashboard</span>
                    </router-link>
                    <router-link to="/transactions" class="nav-item" active-class="active">
                        <span class="icon">💸</span>
                        <span class="label" v-if="!isSidebarCollapsed">Transactions</span>
                    </router-link>
                    <router-link to="/budgets" class="nav-item" active-class="active">
                        <span class="icon">📉</span>
                        <span class="label" v-if="!isSidebarCollapsed">Budgets</span>
                    </router-link>
                    <router-link to="/settings" class="nav-item" active-class="active">
                        <span class="icon">⚙️</span>
                        <span class="label" v-if="!isSidebarCollapsed">Settings</span>
                    </router-link>
                </nav>
                
                <!-- Sidebar Footer Removed as requested -->
            </aside>
            
            <main class="main-content">
                <div class="page-container">
                    <slot></slot>
                </div>
            </main>
        </div>

        <!-- Avatar Selection Modal -->
        <div v-if="showAvatarModal" class="modal-overlay">
            <div class="modal avatar-modal">
                <h2>Choose Your Avatar</h2>
                <div class="avatar-grid">
                    <button class="avatar-option" :class="{ 'selected': selectedAvatar === 'male' }" @click="selectAvatar('male')">👨‍💼 <span>Dad</span></button>
                    <button class="avatar-option" :class="{ 'selected': selectedAvatar === 'female' }" @click="selectAvatar('female')">👩‍💼 <span>Mom</span></button>
                    <button class="avatar-option" :class="{ 'selected': selectedAvatar === 'kid' }" @click="selectAvatar('kid')">🧒 <span>Kid</span></button>
                    <button class="avatar-option" :class="{ 'selected': selectedAvatar === 'default' }" @click="selectAvatar('default')">👤 <span>Default</span></button>
                </div>
                <button class="btn btn-outline" @click="showAvatarModal = false" style="margin-top: 1rem; width: 100%">Cancel</button>
            </div>
        </div>

        <ToastContainer />
    </div>
</template>

<style scoped>
.app-layout {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--color-background);
}

/* Global Header */
.global-header {
    height: 52px;
    background: white;
    border-bottom: 1px solid var(--color-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--spacing-lg);
    z-index: 100;
    box-shadow: var(--shadow-sm);
}
.glass {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
}
.header-left { display: flex; align-items: center; }
.brand { display: flex; align-items: baseline; gap: 0.75rem; }
.brand-text { font-size: 1.25rem; font-weight: 700; color: var(--color-primary); }
.brand-tagline { font-size: 0.8rem; color: var(--color-text-muted); font-weight: 500; }
.logo-icon { font-size: 1.5rem; }

.header-center { flex: 1; display: flex; justify-content: center; }
.search-bar input {
    background: var(--color-background);
    border: 1px solid var(--color-border);
    padding: 0.5rem 1rem;
    border-radius: 2rem;
    width: 300px;
    transition: all 0.2s;
}
.search-bar input:focus {
    width: 400px;
    border-color: var(--color-primary);
    outline: none;
}

.header-right { display: flex; align-items: center; gap: var(--spacing-lg); }
.notification-trigger { 
    display: flex; align-items: center; justify-content: center;
    width: 40px; height: 40px; 
    border-radius: 50%;
    cursor: pointer; transition: background 0.2s;
}
.notification-trigger:hover { background: var(--color-background); }
.user-menu-container { position: relative; }
.user-menu-trigger {
    display: flex; align-items: center; gap: var(--spacing-lg);
    cursor: pointer; padding: 0.5rem; border-radius: 0.5rem;
    transition: background 0.2s;
}
.user-menu-trigger:hover { background: var(--color-background); }

.notification-bell { font-size: 1.2rem; }
.user-avatar {
    width: 32px; height: 32px;
    background: var(--color-primary-light);
    color: var(--color-primary-dark);
    font-size: 1rem;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    border: 2px solid white;
    box-shadow: 0 0 0 1px var(--color-border);
}

/* Dropdown Menu */
.dropdown-menu {
    position: absolute;
    top: 100%; right: 0;
    margin-top: 0.5rem;
    background: white;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    box-shadow: var(--shadow-lg);
    width: 200px;
    padding: 0.5rem;
    z-index: 200;
}
.dropdown-header { padding: 0.5rem 1rem; }
.user-name { font-weight: 600; font-size: 0.9rem; color: var(--color-text-main); }
.user-role { font-size: 0.75rem; color: var(--color-text-muted); }
.dropdown-divider { height: 1px; background: var(--color-border); margin: 0.5rem 0; }
.dropdown-item {
    display: flex; align-items: center; gap: 0.5rem;
    width: 100%; padding: 0.5rem 1rem;
    text-align: left; background: none; border: none;
    font-size: 0.9rem; color: var(--color-text-main);
    cursor: pointer; border-radius: 0.25rem;
}
.dropdown-item:hover { background: var(--color-background); }
.dropdown-item.danger { color: var(--color-danger); }
.dropdown-item.danger:hover { background: #fef2f2; }

/* Transitions */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* Avatar Modal */
.modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 200;
    backdrop-filter: blur(2px);
}
.modal {
    background: white;
    padding: 2rem;
    border-radius: 1rem;
    box-shadow: var(--shadow-lg);
    border: 1px solid var(--color-border);
}

.avatar-modal { text-align: center; max-width: 500px; width: 90%; }
.avatar-grid {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem;
    margin-top: 1.5rem;
}
.avatar-option {
    background: var(--color-background);
    border: 2px solid transparent;
    padding: 1.5rem; border-radius: 0.75rem;
    cursor: pointer; transition: all 0.2s;
    font-size: 2.5rem;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.avatar-option span { 
    display: block; font-size: 0.9rem; margin-top: 0.5rem; 
    color: var(--color-text-muted); font-weight: 500;
}
.avatar-option:hover { 
    border-color: var(--color-primary-light); 
    background: white; 
    transform: translateY(-2px);
    box-shadow: var(--shadow-md); 
}
.avatar-option.selected {
    border-color: var(--color-primary);
    background: var(--color-primary-light);
    color: var(--color-primary-dark);
}
.avatar-option.selected span { color: var(--color-primary-dark); }

/* App Body & Sidebar (Existing) */
.app-body { display: flex; flex: 1; overflow: hidden; }
.sidebar { background: white; border-right: 1px solid var(--color-border); width: var(--sidebar-width); transition: width var(--transition-normal); display: flex; flex-direction: column; }
.sidebar.collapsed { width: var(--sidebar-collapsed-width); }
.sidebar-toggle-area { padding: var(--spacing-sm); display: flex; justify-content: flex-end; border-bottom: 1px solid var(--color-border); }
.collapse-btn { background: none; border: none; cursor: pointer; color: var(--color-text-muted); font-size: 1.2rem; padding: 0.25rem 0.5rem; }
.collapse-btn:hover { color: var(--color-primary); }
.sidebar-nav { flex: 1; padding: var(--spacing-sm) var(--spacing-xs); display: flex; flex-direction: column; gap: 2px; }
.nav-item { display: flex; align-items: center; padding: 0.5rem 0.75rem; color: var(--color-text-muted); text-decoration: none; border-radius: 0.5rem; white-space: nowrap; overflow: hidden; transition: all 0.2s; font-size: 0.875rem; }
.nav-item:hover { color: var(--color-primary-dark); background: var(--color-primary-light); }
.nav-item.active { background: var(--color-primary); color: white; box-shadow: var(--shadow-sm); }
.nav-item .icon { font-size: 1.1rem; min-width: 20px; margin-right: 10px; text-align: center; }
.sidebar.collapsed .nav-item { justify-content: center; padding: 0.75rem 0; }
.sidebar.collapsed .nav-item .icon { margin-right: 0; }
.main-content { flex: 1; overflow-y: auto; background: var(--color-background); padding: var(--spacing-lg); }
.page-container { max-width: 1600px; margin: 0 auto; }
</style>
