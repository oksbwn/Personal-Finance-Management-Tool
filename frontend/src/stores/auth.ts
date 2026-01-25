import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'

interface User {
    id: string
    email: string
    role: string
    tenant_id: string
    full_name?: string
    avatar?: string
}

export const useAuthStore = defineStore('auth', () => {
    const user = ref<User | null>(null)

    const get_url_token = () => {
        const urlParams = new URLSearchParams(window.location.search)
        return urlParams.get('auth_token')
    }

    const token = ref<string | null>(get_url_token() || localStorage.getItem('access_token'))

    if (get_url_token()) {
        localStorage.setItem('access_token', token.value!)
        // Clean up URL after consumption
        const url = new URL(window.location.href)
        url.searchParams.delete('auth_token')
        window.history.replaceState({}, '', url.pathname + url.search)
    }

    const isAuthenticated = computed(() => !!token.value)

    async function fetchUser() {
        if (!token.value) return
        try {
            const response = await apiClient.get('/auth/me')
            user.value = response.data
        } catch (error) {
            console.error("Failed to fetch user profile", error)
        }
    }

    async function login(email: string, password: string) {
        try {
            const formData = new FormData()
            formData.append('username', email)
            formData.append('password', password)

            const response = await apiClient.post('/auth/login', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            })

            token.value = response.data.access_token
            if (token.value) {
                localStorage.setItem('access_token', token.value)
                await fetchUser()
            }
        } catch (error) {
            throw error
        }
    }

    function logout() {
        token.value = null
        user.value = null
        localStorage.removeItem('access_token')
    }

    if (token.value) {
        fetchUser()
    }

    return {
        user,
        token,
        isAuthenticated,
        login,
        logout,
        fetchUser
    }
})
