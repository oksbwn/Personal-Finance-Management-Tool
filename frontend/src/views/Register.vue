<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import apiClient from '@/api/client'

const router = useRouter()

// Register form usually needs Tenant Name + User Details
const familyName = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function handleRegister() {
    if (password.value !== confirmPassword.value) {
        error.value = "Passwords do not match"
        return
    }
    
    loading.value = true
    error.value = ''
    
    try {
        // Construct payload matching backend expectation
        // backend expects { tenant: {name}, user: {email, password} }
        await apiClient.post('/auth/register', {
            tenant: { name: familyName.value },
            user: { email: email.value, password: password.value }
        })
        
        // Auto redirect to login or auto-login could be done here.
        router.push('/login')
    } catch (e: any) {
        error.value = e.response?.data?.detail || 'Registration failed'
    } finally {
        loading.value = false
    }
}
</script>

<template>
    <div class="auth-container">
        <div class="auth-card">
            <h1>Create Account</h1>
            <p class="subtitle">Start your WealthFam journey</p>
            
            <form @submit.prevent="handleRegister">
                <div class="form-group">
                    <label>Family Name</label>
                    <input type="text" v-model="familyName" required placeholder="The Smiths" />
                </div>
                
                <div class="form-group">
                    <label>Email</label>
                    <input type="email" v-model="email" required placeholder="admin@example.com" />
                </div>
                
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" v-model="password" required />
                </div>
                 <div class="form-group">
                    <label>Confirm Password</label>
                    <input type="password" v-model="confirmPassword" required />
                </div>
                
                <div v-if="error" class="error-msg">{{ error }}</div>
                
                <button type="submit" class="btn btn-primary full-width" :disabled="loading">
                    {{ loading ? 'Creating...' : 'Register' }}
                </button>
            </form>
            
            <div class="footer">
                <p>Already have an account? <router-link to="/login">Sign In</router-link></p>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* Reuse styles from Login (could be extracted to Layout or CSS class) */
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
