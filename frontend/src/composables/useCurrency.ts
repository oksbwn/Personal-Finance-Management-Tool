import { useSettingsStore } from '@/stores/settings'

export function useCurrency() {
    const settings = useSettingsStore()

    const formatAmount = (amount: number | string | null | undefined, currency = 'INR') => {
        if (amount === null || amount === undefined || amount === '') return '-'

        const val = Number(amount)
        if (isNaN(val)) return '-'

        // Apply Masking
        const maskedVal = val / (settings.maskingFactor || 1)

        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: currency,
            maximumFractionDigits: 0
        }).format(maskedVal)
    }

    return {
        formatAmount
    }
}
