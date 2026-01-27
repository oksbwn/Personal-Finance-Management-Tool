<template>
    <MainLayout>
        <div class="loan-details-container animate-in">
            <div class="mb-6">
                <button @click="router.back()" class="back-link">
                    <span>← Back to Loans</span>
                </button>
            </div>

            <div v-if="loading" class="text-center py-12">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            </div>

            <div v-else-if="loan">
                <div class="details-header">
                    <div>
                        <div style="display: flex; align-items: center; gap: 0.75rem;">
                            <span style="font-size: 2rem;">{{ getLoanIcon(loan.loan_type) }}</span>
                            <h1 class="page-title">{{ loan.name }}</h1>
                        </div>
                        <p class="subtitle">
                            {{ loan.tenure_months }} Months {{ loan.loan_type?.replace('_', ' ') }} @ {{
                                loan.interest_rate }}% Interest
                        </p>
                    </div>
                    <div class="header-right">
                        <p class="header-label">Current Outstanding</p>
                        <p class="header-value">{{ formatCurrency(loan.outstanding_balance) }}</p>
                    </div>
                </div>

                <!-- Stats Cards -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                    <div class="stat-card-mini">
                        <p class="stat-label-mini">Principal Amount</p>
                        <p class="stat-value-mini">{{ formatCurrency(loan.principal_amount) }}</p>
                    </div>
                    <div class="stat-card-mini">
                        <p class="stat-label-mini">EMI Amount</p>
                        <p class="stat-value-mini">{{ formatCurrency(loan.emi_amount) }}</p>
                    </div>
                    <div class="stat-card-mini">
                        <p class="stat-label-mini">Next Due Date</p>
                        <p class="stat-value-mini">{{ formatDate(loan.next_emi_date) }}</p>
                    </div>
                    <div class="stat-card-mini">
                        <p class="stat-label-mini">Progress</p>
                        <div class="flex items-center space-x-2">
                            <div class="w-full bg-gray-200 rounded-full h-2 mt-1">
                                <div class="bg-blue-600 h-2 rounded-full"
                                    :style="{ width: loan.progress_percentage + '%' }"></div>
                            </div>
                            <span class="text-sm font-bold">{{ loan.progress_percentage }}%</span>
                        </div>
                    </div>
                </div>

                <!-- AI Insights Section -->
                <div class="ai-insights-section">
                    <div class="ai-header">
                        <h3 class="ai-title">✨ AI Loan Advisor</h3>
                        <button @click="generateInsights" :disabled="insightLoading" class="btn-ai">
                            <span v-if="insightLoading">Analyzing...</span>
                            <span v-else>Generate Insights</span>
                        </button>
                    </div>

                    <div v-if="insights" class="ai-content">
                        <div v-html="renderedInsights"></div>
                    </div>
                    <div v-else class="ai-empty">
                        Click generate to get personalized advice on prepayment and interest savings.
                    </div>
                </div>

                <!-- Content Split -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
                    <!-- Chart Section -->
                    <div class="chart-card">
                        <h3 class="card-title">Principal vs Interest</h3>
                        <div class="relative h-64">
                            <Pie v-if="chartData" :data="chartData" :options="chartOptions" />
                        </div>
                        <div
                            style="margin-top: 1rem; text-align: center; font-size: 0.875rem; color: var(--color-text-muted);">
                            Total Interest Payable: <span style="font-weight: 700; color: var(--color-text-main);">{{
                                formatCurrency(totalInterest) }}</span>
                        </div>
                    </div>

                    <!-- Amortization Schedule -->
                    <div class="lg:col-span-2 table-card">
                        <h3 class="card-title">Amortization Schedule</h3>
                        <div style="overflow-x: auto; max-height: 500px; overflow-y: auto;">
                            <table class="amortization-table">
                                <thead>
                                    <tr>
                                        <th>#</th>
                                        <th>Date</th>
                                        <th style="text-align: right;">EMI</th>
                                        <th style="text-align: right;">Principal</th>
                                        <th style="text-align: right;">Interest</th>
                                        <th style="text-align: right;">Balance</th>
                                        <th style="text-align: center;">Status</th>
                                        <th style="text-align: center;">Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="item in loan.amortization_schedule" :key="item.installment_no">
                                        <td>{{ item.installment_no }}</td>
                                        <td>{{ formatDate(item.due_date) }}</td>
                                        <td style="text-align: right; font-weight: 600;">{{ formatCurrency(item.emi) }}
                                        </td>
                                        <td style="text-align: right; color: var(--color-success);">{{
                                            formatCurrency(item.principal_component) }}</td>
                                        <td style="text-align: right; color: var(--color-danger);">{{
                                            formatCurrency(item.interest_component) }}</td>
                                        <td style="text-align: right; color: var(--color-text-muted);">{{
                                            formatCurrency(item.closing_balance) }}</td>
                                        <td style="text-align: center;">
                                            <span class="status-badge" :class="{
                                                'status-paid': item.status === 'PAID',
                                                'status-unpaid': item.status === 'PENDING',
                                                'status-overdue': item.status === 'OVERDUE'
                                            }">
                                                {{ item.status }}
                                            </span>
                                        </td>
                                        <td style="text-align: center;">
                                            <button v-if="item.status !== 'PAID'" @click="openRepaymentModal(item)"
                                                class="btn-pay-mini">
                                                Pay Now
                                            </button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Repayment Modal -->
            <div v-if="showRepaymentModal" class="modal-overlay-global">
                <div class="modal-global" style="max-width: 450px;">
                    <div class="modal-header">
                        <h2 class="modal-title">Record EMI Payment</h2>
                        <button class="btn-icon" @click="closeRepaymentModal">✕</button>
                    </div>

                    <form @submit.prevent="submitRepayment" style="padding-top: 1rem;">
                        <div style="display: flex; flex-direction: column; gap: 1.25rem;">
                            <div class="form-group">
                                <label class="form-label">Amount</label>
                                <input v-model.number="repaymentForm.amount" type="number" required class="form-input">
                            </div>

                            <div class="form-group">
                                <label class="form-label">Date</label>
                                <input v-model="repaymentForm.date" type="date" required class="form-input">
                            </div>

                            <div class="form-group">
                                <label class="form-label">Paid From</label>
                                <CustomSelect v-model="repaymentForm.bank_account_id" :options="accountOptions"
                                    placeholder="Select Bank Account" />
                            </div>

                            <div class="form-group">
                                <label class="form-label">Notes (Optional)</label>
                                <input v-model="repaymentForm.description" type="text" class="form-input"
                                    placeholder="e.g. Paid via mobile app">
                            </div>
                        </div>

                        <div class="modal-footer">
                            <button type="button" @click="closeRepaymentModal" class="btn btn-outline"
                                style="min-width: 100px;">Cancel</button>
                            <button type="submit" class="btn btn-primary" style="min-width: 140px;"
                                :disabled="isSubmitting">
                                {{ isSubmitting ? 'Recording...' : 'Record Payment' }}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </MainLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi as api } from '@/api/client'
import CustomSelect from '@/components/CustomSelect.vue'
import { useNotificationStore } from '@/stores/notification'
import { useCurrency } from '@/composables/useCurrency'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { Pie } from 'vue-chartjs'
import { marked } from 'marked'

ChartJS.register(ArcElement, Tooltip, Legend)

const loanTypeOptions = [
    { label: 'Home Loan', value: 'HOME_LOAN', icon: '🏠' },
    { label: 'Personal Loan', value: 'PERSONAL_LOAN', icon: '👤' },
    { label: 'Car Loan', value: 'CAR_LOAN', icon: '🚗' },
    { label: 'Education Loan', value: 'EDUCATION_LOAN', icon: '🎓' },
    { label: 'Credit Card', value: 'CREDIT_CARD', icon: '💳' },
    { label: 'Other', value: 'OTHER', icon: '💰' }
]

const getLoanIcon = (type: string) => {
    const opt = loanTypeOptions.find(o => o.value === type)
    return opt ? opt.icon : '💰'
}

const route = useRoute()
const router = useRouter()
const notificationStore = useNotificationStore()
const { formatAmount } = useCurrency()
const loading = ref(true)
const loan = ref<any>(null)
const accounts = ref<any[]>([])
const insightLoading = ref(false)
const insights = ref<string | null>(null)
const isSubmitting = ref(false)

const showRepaymentModal = ref(false)
const repaymentForm = ref({
    amount: 0,
    date: new Date().toISOString().split('T')[0],
    bank_account_id: '',
    installment_no: null as number | null,
    description: ''
})

const accountOptions = computed(() => {
    return accounts.value
        .filter(a => a.type === 'BANK' || a.type === 'WALLET')
        .map(a => ({ label: a.name, value: a.id }))
})

const openRepaymentModal = (item: any) => {
    repaymentForm.value = {
        amount: item.emi,
        date: item.due_date.split('T')[0],
        bank_account_id: loan.value.bank_account_id || '',
        installment_no: item.installment_no,
        description: `EMI #${item.installment_no} for ${loan.value.name}`
    }
    showRepaymentModal.value = true
}

const closeRepaymentModal = () => {
    showRepaymentModal.value = false
}

const submitRepayment = async () => {
    if (!repaymentForm.value.bank_account_id) {
        notificationStore.error("Please select a bank account")
        return
    }

    isSubmitting.value = true
    try {
        const id = route.params.id as string
        await api.recordLoanRepayment(id, repaymentForm.value)
        notificationStore.success("Repayment recorded successfully")
        closeRepaymentModal()
        fetchLoanDetails()
    } catch (e) {
        console.error("Failed to record repayment", e)
        notificationStore.error("Failed to record repayment")
    } finally {
        isSubmitting.value = false
    }
}

const renderedInsights = computed(() => {
    return insights.value ? marked(insights.value) : ''
})

const formatDate = (dateStr: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
    })
}

const formatCurrency = (amount: any) => formatAmount(amount)

const totalInterest = computed(() => {
    if (!loan.value || !loan.value.amortization_schedule) return 0
    return loan.value.amortization_schedule.reduce((sum: number, item: any) => sum + Number(item.interest_component), 0)
})

const chartData = computed(() => {
    if (!loan.value) return null
    return {
        labels: ['Principal', 'Total Interest'],
        datasets: [
            {
                backgroundColor: ['#3B82F6', '#EF4444'],
                data: [Number(loan.value.principal_amount), totalInterest.value]
            }
        ]
    }
})

const chartOptions = {
    responsive: true,
    maintainAspectRatio: false
}

const fetchLoanDetails = async () => {
    loading.value = true
    try {
        const [loanRes, accRes] = await Promise.all([
            api.getLoanDetails(route.params.id as string),
            api.getAccounts()
        ])
        loan.value = loanRes.data
        accounts.value = accRes.data
    } catch (e) {
        console.error("Failed to fetch loan details", e)
        notificationStore.error("Failed to load loan details")
    } finally {
        loading.value = false
    }
}

const generateInsights = async () => {
    insightLoading.value = true
    try {
        const id = route.params.id as string
        const response = await api.getLoanInsights(id)
        insights.value = response.data.insights
        notificationStore.success("AI Insights generated!")
    } catch (e) {
        console.error("Failed to generate insights", e)
        notificationStore.error("Failed to generate AI insights. Please check if AI is enabled in settings.")
    } finally {
        insightLoading.value = false
    }
}

onMounted(() => {
    fetchLoanDetails()
})
</script>

<style scoped>
.loan-details-container {
    width: 100%;
    margin: 0 auto;
    padding-bottom: 3rem;
}

.back-link {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--color-primary);
    text-decoration: none;
    font-size: 0.875rem;
    font-weight: 500;
    margin-bottom: 1.5rem;
    cursor: pointer;
    background: none;
    border: none;
    padding: 0;
}

.back-link:hover {
    color: var(--color-primary-dark);
}

.details-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 2rem;
}

.page-title {
    font-size: 1.75rem;
    font-weight: 800;
    color: var(--color-text-main);
    margin: 0;
}

.subtitle {
    font-size: 0.875rem;
    color: var(--color-text-muted);
    margin-top: 0.25rem;
}

.header-right {
    text-align: right;
}

.header-label {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.05em;
}

.header-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-main);
}

.grid {
    display: grid;
}

.grid-cols-1 {
    grid-template-columns: repeat(1, minmax(0, 1fr));
}

@media (min-width: 768px) {
    .md\:grid-cols-4 {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }
}

@media (min-width: 1024px) {
    .lg\:grid-cols-3 {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

.gap-4 {
    gap: 1rem;
}

.gap-8 {
    gap: 2rem;
}

.mb-8 {
    margin-bottom: 2rem;
}

.stat-card-mini {
    background: white;
    padding: 1rem;
    border-radius: 0.75rem;
    border: 1px solid var(--color-border);
}

.stat-label-mini {
    font-size: 0.65rem;
    color: var(--color-text-muted);
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 0.25rem;
}

.stat-value-mini {
    font-weight: 700;
    font-size: 1.125rem;
    color: var(--color-text-main);
}

.ai-insights-section {
    background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
    border-radius: 1rem;
    padding: 1.5rem;
    border: 1px solid #ddd6fe;
    margin-bottom: 2rem;
}

.ai-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.ai-title {
    font-weight: 700;
    font-size: 1.125rem;
    color: #4c1d95;
    margin: 0;
}

.ai-content {
    background: white;
    padding: 1.25rem;
    border-radius: 0.75rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.ai-empty {
    text-align: center;
    padding: 1rem;
    color: #6d28d9;
    font-style: italic;
    font-size: 0.875rem;
}

.btn-ai {
    background: #7c3aed;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 0.5rem;
    font-weight: 600;
    font-size: 0.8125rem;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-ai:hover {
    background: #6d28d9;
}

.chart-card,
.table-card {
    background: white;
    padding: 1.5rem;
    border-radius: 1rem;
    border: 1px solid var(--color-border);
}

.card-title {
    font-weight: 700;
    font-size: 1rem;
    margin-bottom: 1.25rem;
    color: var(--color-text-main);
}

.amortization-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8125rem;
}

.amortization-table th {
    text-align: left;
    padding: 0.75rem 1rem;
    background: var(--color-background);
    color: var(--color-text-muted);
    font-weight: 700;
    text-transform: uppercase;
    font-size: 0.65rem;
    position: sticky;
    top: 0;
}

.amortization-table td {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--color-border);
}

.amortization-table tr:hover {
    background: var(--color-background);
}

.status-badge {
    padding: 0.125rem 0.5rem;
    border-radius: 2rem;
    font-size: 0.7rem;
    font-weight: 600;
}

.status-paid {
    background: #d1fae5;
    color: #065f46;
}

.status-unpaid {
    background: #fef3c7;
    color: #92400e;
}

.animate-in {
    animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.btn-pay-mini {
    padding: 0.25rem 0.75rem;
    background: #3B82F6;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
}

.btn-pay-mini:hover {
    background: #2563EB;
}

.status-overdue {
    background: #fee2e2;
    color: #991b1b;
}
</style>
