import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
    // Default to 1 (no masking)
    const maskingFactor = ref<number>(Number(localStorage.getItem('maskingFactor')) || 1)

    // Persist changes
    watch(maskingFactor, (val) => {
        localStorage.setItem('maskingFactor', val.toString())
    })

    return {
        maskingFactor
    }
})
