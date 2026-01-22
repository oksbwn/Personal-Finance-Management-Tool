<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
    loading.value = true
    error.value = ''
    try {
        await authStore.login(email.value, password.value)
        router.push('/')
    } catch (e: any) {
        error.value = 'Invalid credentials or server error'
    } finally {
        loading.value = false
    }
}
</script>

<template>
    <div class="auth-container">
        <div class="auth-card">
            <h1>Sign In</h1>
            <p class="subtitle">Welcome back to WealthFam</p>
            
            <form @submit.prevent="handleLogin">
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" v-model="email" required placeholder="you@example.com" />
                </div>
                
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" v-model="password" required />
                </div>
                
                <div v-if="error" class="error-msg">{{ error }}</div>
                
                <button type="submit" class="btn btn-primary full-width" :disabled="loading">
                    {{ loading ? 'Signing in...' : 'Sign In' }}
                </button>
            </form>
            
            <div class="footer">
                <p>New here? <router-link to="/register">Create a Family Account</router-link></p>
            </div>
        </div>
    </div>
</template>

<style scoped>
.auth-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-background);
}
.auth-card {
    background: var(--color-surface);
    padding: var(--spacing-xl);
    border-radius: 0.5rem;
    box-shadow: var(--shadow-md);
    width: 100%;
    max-width: 400px;
}
h1 {
    font-size: var(--font-size-2xl);
    font-weight: bold;
    text-align: center;
    margin-bottom: var(--spacing-xs);
}
.subtitle {
    text-align: center;
    color: var(--color-text-muted);
    margin-bottom: var(--spacing-xl);
}
.form-group {
    margin-bottom: var(--spacing-md);
}
label {
    display: block;
    margin-bottom: var(--spacing-xs);
    font-weight: 500;
    font-size: var(--font-size-sm);
}
input {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    font-size: var(--font-size-base);
}
input:focus {
    outline: none;
    border-color: var(--color-primary);
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}
.full-width {
    width: 100%;
    margin-top: var(--spacing-md);
}
.error-msg {
    color: var(--color-danger);
    font-size: var(--font-size-sm);
    margin-top: var(--spacing-sm);
    text-align: center;
}
.footer {
    margin-top: var(--spacing-lg);
    text-align: center;
    font-size: var(--font-size-sm);
}
.footer a {
    color: var(--color-primary);
    text-decoration: none;
    font-weight: 500;
}
</style>
