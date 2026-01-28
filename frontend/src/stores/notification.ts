import { defineStore } from 'pinia'
import { ref } from 'vue'

export type NotificationType = 'success' | 'error' | 'info' | 'warning'

export interface Notification {
    id: string;
    type: NotificationType;
    message: string;
    duration?: number;
}

export const useNotificationStore = defineStore('notification', () => {
    const notifications = ref<Notification[]>([])

    function add(type: NotificationType, message: string, duration: number = 3000) {
        const id = Date.now().toString() + Math.random().toString()
        notifications.value.push({ id, type, message, duration })

        if (duration > 0) {
            setTimeout(() => {
                remove(id)
            }, duration)
        }
    }

    function remove(id: string) {
        notifications.value = notifications.value.filter(n => n.id !== id)
    }

    function success(message: string) { add('success', message) }
    function error(message: string) { add('error', message) }
    function info(message: string) { add('info', message) }
    function warning(message: string) { add('warning', message) }

    return {
        notifications,
        add,
        remove,
        success,
        error,
        info,
        warning
    }
})
